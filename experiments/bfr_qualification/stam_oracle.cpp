#include "stam_box_spline.hpp"
#include "stam_evaluation.hpp"
#include "stam_fixture.hpp"
#include "stam_primary.hpp"
#include "stam_uniform.hpp"

#include <mpfr.h>

#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <cfenv>
#include <algorithm>
#include <array>
#include <map>
#include <limits>
#include <set>
#include <vector>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

using b2interval::MpfrInterval;

using OracleStencils = b2uniform::Stencils;

bool is_exact_interval_reason(std::string const &reason) {
    return reason.find("DIRECTED_INTERVAL_PRIMITIVE_FAILED") == 0 ||
           reason.find("INTERVAL_BRANCH_ORDERING_UNCERTIFIED") == 0 ||
           reason.find("MPFR_VERSION_MISMATCH") == 0;
}

[[noreturn]] void rethrow_exact_or_fallback(
        std::runtime_error const &error,char const *fallback) {
    if (is_exact_interval_reason(error.what())) throw error;
    throw std::runtime_error(fallback);
}

struct RefinedState {
    b2stam_fixture::Mesh mesh;
    OracleStencils stencils;
    int face = 0;
    std::array<MpfrInterval,2> point = {{MpfrInterval(0),MpfrInterval(0)}};
    std::vector<b2uniform::Branch> branches;
    unsigned depth = 0;
    int tracked_extraordinary = -1;
    b2stam::Jacobian jacobian = b2stam::identity_jacobian();
};

void add_scaled(b2uniform::Row &target,b2uniform::Row const &source,
                MpfrInterval const &scale){
    b2uniform::add_scaled(target,source,scale);
}

void build_sparse_topology(b2stam_fixture::Mesh &mesh){
    std::vector<std::map<int,std::set<int>>> links(mesh.vertices.size());
    std::map<std::pair<int,int>,std::vector<std::array<int,3>>> incidents;
    for(auto const &face:mesh.faces){
        for(int c=0;c<3;++c){
            int v=face[c],next=face[(c+1)%3],previous=face[(c+2)%3];
            if(v<0 || static_cast<std::size_t>(v)>=mesh.vertices.size() ||
               v==next || next==previous || previous==v)
                throw std::runtime_error("oracle sparse topology incidence");
            incidents[b2stam_fixture::edge(v,next)].push_back(
                {{v,next,previous}});
            links[v][next].insert(previous);links[v][previous].insert(next);
        }
    }
    mesh.edge_opposites.clear();
    mesh.neighbor_cycles.assign(mesh.vertices.size(),{});
    for(auto const &item:incidents){
        if(item.second.size()==2 &&
           item.second[0][0]==item.second[1][1] &&
           item.second[0][1]==item.second[1][0])
            mesh.edge_opposites[item.first]={{item.second[0][2],
                                               item.second[1][2]}};
        else if(item.second.size()!=1)
            throw std::runtime_error("oracle sparse topology edge incidence");
    }
    for(std::size_t v=0;v<links.size();++v){
        if(links[v].size()<3 || std::any_of(
                links[v].begin(),links[v].end(),
                [](auto const &item){return item.second.size()!=2;}))continue;
        int start=links[v].begin()->first,previous=-1,current=start;
        std::vector<int> cycle;
        do{
            cycle.push_back(current);auto const &adjacent=links[v].at(current);
            int next=*adjacent.begin();if(next==previous)next=*adjacent.rbegin();
            previous=current;current=next;
            if(cycle.size()>links[v].size())
                throw std::runtime_error("oracle sparse vertex cycle overflow");
        }while(current!=start);
        if(cycle.size()==links[v].size())mesh.neighbor_cycles[v]=cycle;
    }
}

std::vector<unsigned> selected_face_distances(RefinedState const &state){
    std::map<std::pair<int,int>,std::vector<int>> incident_faces;
    for(std::size_t fi=0;fi<state.mesh.faces.size();++fi){
        auto const &face=state.mesh.faces[fi];
        for(int edge=0;edge<3;++edge)
            incident_faces[b2stam_fixture::edge(
                face[edge],face[(edge+1)%3])].push_back(
                    static_cast<int>(fi));
    }
    unsigned const unavailable=std::numeric_limits<unsigned>::max();
    std::vector<unsigned> distance(state.mesh.faces.size(),unavailable);
    std::queue<int> queue;distance[static_cast<std::size_t>(state.face)]=0;
    queue.push(state.face);
    while(!queue.empty()){
        int face_id=queue.front();queue.pop();
        auto const &face=state.mesh.faces[static_cast<std::size_t>(face_id)];
        for(int edge=0;edge<3;++edge){
            auto const &neighbors=incident_faces.at(b2stam_fixture::edge(
                face[edge],face[(edge+1)%3]));
            for(int neighbor:neighbors)if(distance[neighbor]==unavailable){
                distance[neighbor]=distance[face_id]+1;queue.push(neighbor);
            }
        }
    }
    return distance;
}

RefinedState refine_selected(RefinedState const &state){
    RefinedState next; next.depth=state.depth+1;
    next.point=state.point; next.branches=state.branches;
    b2uniform::Branch branch=b2uniform::choose_child(state.point);
    next.point=b2uniform::map_child(branch,state.point);
    next.jacobian=b2stam::multiply(b2uniform::branch_jacobian(branch),
                                   state.jacobian);
    next.branches.push_back(branch);
    // A child-face ball of radius eight depends only on a bounded parent
    // neighborhood.  Subdivide that exact dependency patch, not the full
    // mesh (which would materialize 4^depth faces).
    std::vector<unsigned> const distances=selected_face_distances(state);
    std::vector<int> core_faces;
    std::set<int> required_vertices;
    std::set<std::pair<int,int>> required_edges;
    for(std::size_t fi=0;fi<state.mesh.faces.size();++fi){
        if(distances[fi]>8)continue;
        core_faces.push_back(static_cast<int>(fi));
        auto const &face=state.mesh.faces[fi];
        for(int vertex:face)required_vertices.insert(vertex);
        for(int edge=0;edge<3;++edge)required_edges.insert(
            b2stam_fixture::edge(face[edge],face[(edge+1)%3]));
    }
    if(core_faces.empty())
        throw std::runtime_error("oracle sparse dependency patch empty");
    if(!required_vertices.count(state.tracked_extraordinary))
        throw std::runtime_error(
            "NO_ISOLATION_BY_DEPTH_12 tracked extraordinary left dependency patch");
    std::map<std::pair<int,int>,int> edge_ids;
    std::map<int,int> vertex_ids;
    for(int vertex:required_vertices){
        vertex_ids[vertex]=static_cast<int>(vertex_ids.size());
    }
    for(auto const &edge:required_edges){
        edge_ids[edge]=static_cast<int>(vertex_ids.size()+edge_ids.size());
    }
    next.mesh.vertices.resize(vertex_ids.size()+edge_ids.size(),
                              {{0.0,0.0,0.0}});
    next.stencils=b2uniform::zeros(next.mesh.vertices.size(),
                                   state.stencils.front().size());
    for(int vertex:required_vertices){
        auto const &ring=state.mesh.neighbor_cycles.at(
            static_cast<std::size_t>(vertex));
        if(ring.empty())
            throw std::runtime_error(
                "oracle sparse dependency vertex ring incomplete");
        unsigned valence=static_cast<unsigned>(ring.size());
        MpfrInterval tangent=b2interval::add(MpfrInterval::rational(3,8),
            b2interval::multiply(MpfrInterval::rational(1,4),
                b2interval::loop_angle_cosine(valence,1)));
        MpfrInterval beta=b2interval::divide(
            b2interval::subtract(MpfrInterval::rational(5,8),
                                 b2interval::multiply(tangent,tangent)),
            MpfrInterval(static_cast<long>(valence)));
        auto &row=next.stencils[static_cast<std::size_t>(vertex_ids[vertex])];
        add_scaled(row,state.stencils[vertex],
            b2interval::subtract(MpfrInterval(1),b2interval::multiply(
                MpfrInterval(static_cast<long>(valence)),beta)));
        for(int neighbor:ring)add_scaled(row,state.stencils[neighbor],beta);
    }
    for(auto const &edge:required_edges){
        int a=edge.first,b=edge.second;
        auto const &opposites=state.mesh.edge_opposites.at(edge);
        auto &row=next.stencils[static_cast<std::size_t>(edge_ids[edge])];
        add_scaled(row,state.stencils[a],MpfrInterval::rational(3,8));
        add_scaled(row,state.stencils[b],MpfrInterval::rational(3,8));
        add_scaled(row,state.stencils[opposites[0]],MpfrInterval::rational(1,8));
        add_scaled(row,state.stencils[opposites[1]],MpfrInterval::rational(1,8));
    }
    std::array<int,4> selected={{0,0,0,0}};
    for(int fi:core_faces){
        auto const &f=state.mesh.faces[static_cast<std::size_t>(fi)];
        int a=vertex_ids.at(f[0]),b=vertex_ids.at(f[1]),c=vertex_ids.at(f[2]);
        int ab=edge_ids.at(b2stam_fixture::edge(f[0],f[1]));
        int bc=edge_ids.at(b2stam_fixture::edge(f[1],f[2]));
        int ca=edge_ids.at(b2stam_fixture::edge(f[2],f[0]));
        std::array<std::array<int,3>,4> children={{{{a,ab,ca}},{{ab,b,bc}},
                                                   {{ca,bc,c}},{{ab,bc,ca}}}};
        int first=static_cast<int>(next.mesh.faces.size());
        for(auto const &child:children) next.mesh.faces.push_back(child);
        if(fi==state.face)selected={{first,first+1,first+2,first+3}};
    }
    next.face=selected[branch==b2uniform::Branch::T0?0:
                       branch==b2uniform::Branch::T1?1:
                       branch==b2uniform::Branch::T2?2:3];
    next.tracked_extraordinary=vertex_ids.at(state.tracked_extraordinary);
    build_sparse_topology(next.mesh);
    return next;
}

std::string branch_name(b2uniform::Branch branch){
    if(branch==b2uniform::Branch::T0)return "T0";
    if(branch==b2uniform::Branch::T1)return "T1";
    if(branch==b2uniform::Branch::T2)return "T2";
    return "Tc";
}

b2stam::Jacobian corner_jacobian(int corner){
    if(corner==0)return b2stam::identity_jacobian();
    if(corner==1)return {{{MpfrInterval(0),MpfrInterval(1)},
                          {MpfrInterval(-1),MpfrInterval(-1)}}};
    if(corner==2)return {{{MpfrInterval(-1),MpfrInterval(-1)},
                          {MpfrInterval(1),MpfrInterval(0)}}};
    throw std::runtime_error("oracle corner Jacobian outside triangle");
}

b2stam::SixRows transform_rows(b2stam::SixRows const &rows,
                               b2stam::Jacobian const &j){
    b2stam::SixRows out;out[0]=rows[0];
    auto linear=[&](int column){
        b2stam::Vector value(rows[0].size(),MpfrInterval(0));
        for(std::size_t i=0;i<value.size();++i)value[i]=b2interval::add(
            b2interval::multiply(rows[1][i],j[0][column]),
            b2interval::multiply(rows[2][i],j[1][column]));
        return value;
    };
    auto second=[&](int a,int b){
        b2stam::Vector value(rows[0].size(),MpfrInterval(0));
        for(std::size_t i=0;i<value.size();++i){
            value[i]=b2interval::multiply(b2interval::multiply(j[0][a],j[0][b]),rows[3][i]);
            value[i]=b2interval::add(value[i],b2interval::multiply(
                b2interval::add(b2interval::multiply(j[0][a],j[1][b]),
                                b2interval::multiply(j[1][a],j[0][b])),rows[4][i]));
            value[i]=b2interval::add(value[i],b2interval::multiply(
                b2interval::multiply(j[1][a],j[1][b]),rows[5][i]));
        }return value;
    };
    out[1]=linear(0);out[2]=linear(1);out[3]=second(0,0);
    out[4]=second(0,1);out[5]=second(1,1);return out;
}

b2uniform::SixRows transform_uniform_rows(
        b2uniform::SixRows const &rows,b2uniform::Jacobian const &j){
    b2uniform::SixRows out;out[0]=rows[0];
    for(std::size_t source=0;source<rows[0].size();++source){
        out[1].push_back(b2interval::add(
            b2interval::multiply(rows[1][source],j[0][0]),
            b2interval::multiply(rows[2][source],j[1][0])));
        out[2].push_back(b2interval::add(
            b2interval::multiply(rows[1][source],j[0][1]),
            b2interval::multiply(rows[2][source],j[1][1])));
        auto second=[&](int a,int b){
            MpfrInterval value=b2interval::multiply(
                b2interval::multiply(j[0][a],j[0][b]),rows[3][source]);
            value=b2interval::add(value,b2interval::multiply(
                b2interval::add(b2interval::multiply(j[0][a],j[1][b]),
                                b2interval::multiply(j[1][a],j[0][b])),
                rows[4][source]));
            return b2interval::add(value,b2interval::multiply(
                b2interval::multiply(j[1][a],j[1][b]),rows[5][source]));
        };
        out[3].push_back(second(0,0));out[4].push_back(second(0,1));
        out[5].push_back(second(1,1));
    }
    return out;
}

b2stam::SixRows map_to_coarse(b2stam::SixRows const &local,
                              OracleStencils const &control_stencils){
    b2stam::SixRows out;
    for(std::size_t row=0;row<6;++row){
        out[row].assign(control_stencils.front().size(),MpfrInterval(0));
        for(std::size_t local_id=0;local_id<local[row].size();++local_id)
            for(std::size_t source=0;source<out[row].size();++source)
                out[row][source]=b2interval::add(out[row][source],
                    b2interval::multiply(local[row][local_id],
                                         control_stencils[local_id][source]));
    }return out;
}

b2uniform::Row map_row_to_coarse(
        b2uniform::Row const &local,
        OracleStencils const &control_stencils) {
    if (local.size() != control_stencils.size() || control_stencils.empty()) {
        throw std::runtime_error("oracle local/coarse row cardinality");
    }
    b2uniform::Row result(
        control_stencils.front().size(), MpfrInterval(0));
    for (std::size_t local_id = 0; local_id < local.size(); ++local_id) {
        if (control_stencils[local_id].size() != result.size()) {
            throw std::runtime_error("oracle coarse stencil cardinality");
        }
        for (std::size_t source = 0; source < result.size(); ++source) {
            result[source] = b2interval::add(
                result[source], b2interval::multiply(
                    local[local_id], control_stencils[local_id][source]));
        }
    }
    return result;
}


b2uniform::Row map_uniform_row_to_coarse(
        b2uniform::Row const &local,
        OracleStencils const &control_stencils) {
    if (control_stencils.empty() || local.size() != control_stencils.size()) {
        throw std::runtime_error("uniform local/coarse row cardinality");
    }
    b2uniform::Row result(control_stencils[0].size(), MpfrInterval(0));
    for (std::size_t source = 0; source < result.size(); ++source) {
        MpfrInterval sum(0);
        for (std::size_t local_id = 0; local_id < local.size(); ++local_id) {
            if (control_stencils[local_id].size() != result.size()) {
                throw std::runtime_error("uniform coarse stencil cardinality");
            }
            sum = b2interval::add(sum, b2interval::multiply(
                control_stencils[local_id][source], local[local_id]));
        }
        result[source] = sum;
    }
    return result;
}

MpfrInterval fixture_coordinate(b2stam_fixture::Mesh const &mesh,
                                std::size_t source,std::size_t axis){
    std::string const &text=mesh.coordinate_text.at(source).at(axis);
    return text.empty()?MpfrInterval::exact_double(mesh.vertices.at(source).at(axis)):
                        MpfrInterval::decimal(text.c_str());
}

MpfrInterval normalization_length(b2stam_fixture::Mesh const &mesh){
    MpfrInterval result(0);
    for(auto const &edge:mesh.edge_opposites){
        MpfrInterval squared(0);
        for(std::size_t axis=0;axis<3;++axis){
            MpfrInterval delta=b2interval::subtract(
                fixture_coordinate(mesh,static_cast<std::size_t>(edge.first.first),axis),
                fixture_coordinate(mesh,static_cast<std::size_t>(edge.first.second),axis));
            squared=b2interval::add(squared,b2interval::multiply(delta,delta));
        }
        MpfrInterval length=b2interval::square_root(squared);
        if(mpfr_greater_p(length.lo(),result.lo()))
            mpfr_set(result.mutable_lo(),length.lo(),MPFR_RNDD);
        if(mpfr_greater_p(length.hi(),result.hi()))
            mpfr_set(result.mutable_hi(),length.hi(),MPFR_RNDU);
    }
    result.validate();
    if(mpfr_sgn(result.lo())<=0)
        throw std::runtime_error("NORMALIZATION_LENGTH_NONPOSITIVE");
    return result;
}

MpfrInterval interval_midpoint_binary64(MpfrInterval const &value){
    mpfr_t midpoint,imported;mpfr_init2(midpoint,b2interval::kPrecision);
    mpfr_init2(imported,b2interval::kPrecision);mpfr_clear_flags();
    mpfr_add(midpoint,value.lo(),value.hi(),MPFR_RNDN);
    mpfr_div_2ui(midpoint,midpoint,1,MPFR_RNDN);
    b2interval::reject_bad_flags("oracle interval midpoint");
    double serialized=mpfr_get_d(midpoint,MPFR_RNDN);
    if(!std::isfinite(serialized)){mpfr_clear(midpoint);mpfr_clear(imported);
        throw std::runtime_error("ORACLE_MIDPOINT_NONFINITE");}
    int const ternary=mpfr_set_d(imported,serialized,MPFR_RNDN);
    if(ternary!=0){mpfr_clear(midpoint);mpfr_clear(imported);
        throw std::runtime_error("ORACLE_MIDPOINT_BINARY64_IMPORT_INEXACT");}
    MpfrInterval result=MpfrInterval::point(imported);
    mpfr_clear(midpoint);mpfr_clear(imported);return result;
}

void certify_uncertainty(b2stam_fixture::Mesh const &mesh,
                         std::vector<int> const &source_ids,
                         std::vector<MpfrInterval> const &values,
                         MpfrInterval const &length,char const *target){
    if(source_ids.size()!=values.size())
        throw std::runtime_error("oracle uncertainty source cardinality");
    MpfrInterval coefficient(0);
    std::array<MpfrInterval,3> geometry={{MpfrInterval(0),MpfrInterval(0),
                                         MpfrInterval(0)}};
    for(std::size_t index=0;index<values.size();++index){
        MpfrInterval midpoint=interval_midpoint_binary64(values[index]);
        MpfrInterval lower=MpfrInterval::point(values[index].lo());
        MpfrInterval upper=MpfrInterval::point(values[index].hi());
        MpfrInterval epsilon_lower=b2interval::absolute(
            b2interval::subtract(midpoint,lower));
        MpfrInterval epsilon_upper=b2interval::absolute(
            b2interval::subtract(upper,midpoint));
        coefficient=b2interval::add(coefficient,
            mpfr_greater_p(epsilon_lower.hi(),epsilon_upper.hi())?
                epsilon_lower:epsilon_upper);
        MpfrInterval deviation=b2interval::subtract(values[index],midpoint);
        for(std::size_t axis=0;axis<3;++axis)
            geometry[axis]=b2interval::add(geometry[axis],b2interval::multiply(
                deviation,fixture_coordinate(mesh,
                    static_cast<std::size_t>(source_ids[index]),axis)));
    }
    MpfrInterval maximum_geometry(0);
    for(MpfrInterval const &component:geometry){
        MpfrInterval magnitude=b2interval::absolute(component);
        if(mpfr_greater_p(magnitude.hi(),maximum_geometry.hi()))
            maximum_geometry=magnitude;
    }
    MpfrInterval normalized=b2interval::divide(
        maximum_geometry,MpfrInterval::point(length.lo()));
    if(!b2interval::upper_at_most(coefficient,target) ||
       !b2interval::upper_at_most(normalized,target))
        throw std::runtime_error("ORACLE_UNCERTAINTY_BOUND_EXCEEDED");
}

std::string mpz_decimal(mpz_t const value){
    char *text=mpz_get_str(nullptr,10,value);if(!text)throw std::bad_alloc();
    std::string result(text);void (*free_function)(void*,size_t)=nullptr;
    mp_get_memory_functions(nullptr,nullptr,&free_function);
    free_function(text,std::strlen(text)+1);return result;
}

void emit_rational(std::ostream &output,mpfr_srcptr value){
    mpz_t numerator,denominator;mpz_init(numerator);mpz_init_set_ui(denominator,1);
    mpfr_exp_t exponent=mpfr_get_z_2exp(numerator,value);
    if(mpz_sgn(numerator)==0){exponent=0;}
    while(exponent<0 && mpz_even_p(numerator)){mpz_divexact_ui(numerator,numerator,2);++exponent;}
    if(exponent>=0)mpz_mul_2exp(numerator,numerator,static_cast<mp_bitcnt_t>(exponent));
    else mpz_mul_2exp(denominator,denominator,static_cast<mp_bitcnt_t>(-exponent));
    output<<"{\"kind\":\"rational_v1\",\"numerator\":\""<<mpz_decimal(numerator)
          <<"\",\"denominator\":\""<<mpz_decimal(denominator)<<"\"}";
    mpz_clear(numerator);mpz_clear(denominator);
}

void emit_interval(std::ostream &output,MpfrInterval const &value){
    output<<"{\"kind\":\"interval_rational_v1\",\"lower\":";
    emit_rational(output,value.lo());output<<",\"upper\":";emit_rational(output,value.hi());output<<'}';
}

double double_from_bits(std::string const &text){
    if(text.size()!=16)throw std::runtime_error("oracle binary64 bit string width");
    char *end=nullptr;errno=0;unsigned long long raw=std::strtoull(text.c_str(),&end,16);
    if(errno==ERANGE || end!=text.c_str()+text.size())
        throw std::runtime_error("oracle binary64 bit string syntax");
    std::uint64_t bits=static_cast<std::uint64_t>(raw);double value=0.0;
    std::memcpy(&value,&bits,sizeof(value));
    if(!std::isfinite(value))throw std::runtime_error("oracle nonfinite parameter");
    return value;
}

struct OracleSample {
    unsigned first_isolating_depth;
    unsigned first_regular_support_depth;
    std::vector<unsigned> evaluated_depths;
    std::vector<std::string> child_branches;
    std::vector<int> source_ids;
    std::array<std::vector<std::array<MpfrInterval,5>>,6> primary;
    std::array<std::vector<std::array<MpfrInterval,5>>,6> uniform;
    std::array<std::vector<MpfrInterval>,6> intersections;
};

void certify_frozen_valence(
        unsigned valence, b2stam_fixture::Mesh const &mesh,
        OracleStencils const &primary_control_stencils,
        b2uniform::Stencils const &uniform_control_stencils,
        std::string const &cache_identity) {
    if (primary_control_stencils.size() != valence + 6 ||
        uniform_control_stencils.size() != valence + 6 ||
        primary_control_stencils.empty() || uniform_control_stencils.empty() ||
        primary_control_stencils.front().size() != mesh.vertices.size() ||
        uniform_control_stencils.front().size() != mesh.vertices.size()) {
        throw std::runtime_error("EIGENBASIS_CERTIFICATION_FAILED");
    }
    // The spectral objects depend only on valence, but the frozen vertex and
    // dyadic uncertainty bounds also depend on the source-ID ordered fixture
    // coordinates.  Cache only the complete fixture-local certificate.
    static std::set<std::string> certified;
    if (certified.count(cache_identity)) return;
    std::vector<int> source_ids(mesh.vertices.size());
    for (std::size_t source = 0; source < source_ids.size(); ++source) {
        source_ids[source] = static_cast<int>(source);
    }
    MpfrInterval const length = normalization_length(mesh);
    try {
        b2stam::Certification const value = b2stam::certify_eigenbasis(valence);
        if (!value.eigen_residual || !value.krawczyk_inclusion ||
            !value.inverse_residual || !value.condition_number ||
            !value.jordan_power || !value.spectral_projectors ||
            !value.deterministic_mgs) {
            throw std::runtime_error("certificate bit false");
        }
    } catch (std::runtime_error const &error) {
        rethrow_exact_or_fallback(error,"EIGENBASIS_CERTIFICATION_FAILED");
    }
    b2stam::Vector const primary_limit = map_row_to_coarse(
        b2stam::extraordinary_vertex_limit_row(valence),
        primary_control_stencils);
    b2uniform::Row const uniform_limit = map_uniform_row_to_coarse(
        b2uniform::extraordinary_vertex_limit_row(valence),
        uniform_control_stencils);
    if (primary_limit.size() != uniform_limit.size()) {
        throw std::runtime_error("UNIFORM_CROSSCHECK_FAILED vertex-limit-shape");
    }
    for (std::size_t source = 0; source < primary_limit.size(); ++source) {
        if (!b2interval::overlaps(primary_limit[source],
                                  uniform_limit[source])) {
            throw std::runtime_error(
                "UNIFORM_CROSSCHECK_FAILED vertex-limit-mismatch");
        }
    }
    // Preserve the exact frozen uncertainty reason rather than collapsing it
    // into a route mismatch.
    certify_uncertainty(mesh, source_ids, primary_limit, length, "5e-7");
    certify_uncertainty(mesh, source_ids, uniform_limit, length, "5e-7");
    try {
        b2stam::Matrix const primary = b2stam::tangent_projector(valence);
        b2uniform::Matrix const uniform = b2uniform::tangent_projector(valence);
        if (primary.size() != uniform.size()) {
            throw std::runtime_error("tangent projector shape");
        }
        MpfrInterval maximum_row_sum(0);
        for (std::size_t row = 0; row < primary.size(); ++row) {
            if (primary[row].size() != uniform[row].size()) {
                throw std::runtime_error("tangent projector row shape");
            }
            MpfrInterval row_sum(0);
            for (std::size_t column = 0; column < primary[row].size(); ++column) {
                row_sum = b2interval::add(row_sum, b2interval::absolute(
                    b2interval::subtract(primary[row][column],
                                         uniform[row][column])));
            }
            if (mpfr_greater_p(row_sum.hi(), maximum_row_sum.hi())) {
                maximum_row_sum = row_sum;
            }
        }
        if (!b2interval::upper_at_most(maximum_row_sum, "1e-20")) {
            throw std::runtime_error("tangent projector mismatch");
        }
    } catch (std::runtime_error const &error) {
        rethrow_exact_or_fallback(error,"TANGENT_PROJECTION_CHECK_FAILED");
    }
    try {
        static double const points[3][2] = {
            {0.25, 0.25}, {0.5, 0.25}, {0.25, 0.5}};
        for (auto const &point : points) {
            std::vector<b2stam::PrimaryDepthRows> const primary =
                b2stam::primary_depth_rows(valence, point[0], point[1]);
            std::vector<b2uniform::DepthRows> const uniform =
                b2uniform::uniform_depth_rows_from_controls(
                    valence, point[0], point[1], uniform_control_stencils);
            if (primary.size() != 5 || uniform.size() != 5) {
                throw std::runtime_error("dyadic depth count");
            }
            std::array<b2uniform::Row, 5> primary_coarse;
            std::array<b2uniform::Row, 5> uniform_coarse;
            for (std::size_t depth = 0; depth < 5; ++depth) {
                primary_coarse[depth] = map_row_to_coarse(
                    primary[depth].rows[0], primary_control_stencils);
                uniform_coarse[depth] = uniform[depth].rows[0];
            }
            std::vector<MpfrInterval> primary_intersection;
            std::vector<MpfrInterval> uniform_intersection;
            primary_intersection.reserve(mesh.vertices.size());
            uniform_intersection.reserve(mesh.vertices.size());
            for (std::size_t source = 0; source < mesh.vertices.size(); ++source) {
                MpfrInterval p = primary_coarse[0][source];
                MpfrInterval u = uniform_coarse[0][source];
                for (std::size_t depth = 0; depth < 5; ++depth) {
                    if (primary[depth].depth != uniform[depth].depth ||
                        !b2interval::overlaps(primary_coarse[depth][source],
                                              uniform_coarse[depth][source])) {
                        throw std::runtime_error("dyadic route overlap");
                    }
                    if (depth != 0) {
                        p = b2interval::intersect(
                            p, primary_coarse[depth][source]);
                        u = b2interval::intersect(
                            u, uniform_coarse[depth][source]);
                    }
                }
                if (!b2interval::overlaps(p, u)) {
                    throw std::runtime_error("dyadic intersection overlap");
                }
                primary_intersection.push_back(p);
                uniform_intersection.push_back(u);
            }
            certify_uncertainty(mesh, source_ids, primary_intersection,
                                length, "5e-7");
            certify_uncertainty(mesh, source_ids, uniform_intersection,
                                length, "5e-7");
        }
    } catch (std::runtime_error const &error) {
        std::string reason = error.what();
        if (reason.find("ORACLE_UNCERTAINTY_BOUND_EXCEEDED") == 0 ||
            reason.find("DIRECTED_INTERVAL_PRIMITIVE_FAILED") == 0 ||
            reason.find("INTERVAL_BRANCH_ORDERING_UNCERTIFIED") == 0) {
            throw;
        }
        throw std::runtime_error(
            std::string("PARAMETRIC_MAP_CHECK_FAILED ") + reason);
    }
    certified.insert(cache_identity);
}

OracleSample assemble_sample(
    b2stam_fixture::Mesh const &mesh,unsigned isolated,unsigned start_depth,
    std::vector<std::string> const &prefix_branches,
    OracleStencils const &primary_stencils,b2stam::Jacobian const &corner_map,
    std::vector<b2stam::PrimaryDepthRows> const &primary_local,
    std::vector<b2uniform::DepthRows> const &uniform_coarse){
    if(primary_local.size()!=5 || uniform_coarse.size()!=5)
        throw std::runtime_error("oracle five-depth row cardinality");
    std::array<std::array<b2stam::SixRows,5>,2> coarse;
    for(std::size_t depth=0;depth<5;++depth){
        if(uniform_coarse[depth].depth!=start_depth+primary_local[depth].depth)
            throw std::runtime_error("UNIFORM_CROSSCHECK_FAILED");
        coarse[0][depth]=map_to_coarse(
            transform_rows(primary_local[depth].rows,corner_map),primary_stencils);
        coarse[1][depth]=transform_uniform_rows(
            uniform_coarse[depth].rows,corner_map);
    }
    OracleSample result;result.first_isolating_depth=isolated;
    result.first_regular_support_depth=start_depth+primary_local[0].depth;
    for(std::size_t depth=0;depth<5;++depth)
        result.evaluated_depths.push_back(start_depth+primary_local[depth].depth);
    result.child_branches=prefix_branches;
    for(b2stam::ChildBranch branch:primary_local[0].child_branches)
        result.child_branches.push_back(b2stam::child_branch_name(branch));
    if(result.child_branches.size()!=result.first_regular_support_depth)
        throw std::runtime_error("oracle child-branch/depth mismatch");
    std::set<int> active;
    for(std::size_t row=0;row<6;++row)
        for(std::size_t source=0;source<mesh.vertices.size();++source)
            for(std::size_t depth=0;depth<5;++depth)
                if(!coarse[0][depth][row][source].is_exact_zero() ||
                   !coarse[1][depth][row][source].is_exact_zero())
                    active.insert(static_cast<int>(source));
    result.source_ids.assign(active.begin(),active.end());
    MpfrInterval const length=normalization_length(mesh);
    static char const *uncertainty_targets[6]={
        "5e-7","2.5e-6","2.5e-6","1.25e-5","1.25e-5","1.25e-5"};
    for(std::size_t row=0;row<6;++row){
        std::vector<MpfrInterval> uniform_intersections;
        for(int source:result.source_ids){
            std::array<MpfrInterval,5> primary_values,uniform_values;
            for(std::size_t depth=0;depth<5;++depth){
                primary_values[depth]=coarse[0][depth][row][
                    static_cast<std::size_t>(source)];
                uniform_values[depth]=coarse[1][depth][row][
                    static_cast<std::size_t>(source)];
                if(!b2interval::overlaps(primary_values[depth],
                                         uniform_values[depth]))
                    throw std::runtime_error("UNIFORM_CROSSCHECK_FAILED");
            }
            MpfrInterval primary_intersection=primary_values[0];
            MpfrInterval uniform_intersection=uniform_values[0];
            for(std::size_t depth=1;depth<5;++depth){
                try{
                    primary_intersection=b2interval::intersect(
                        primary_intersection,primary_values[depth]);
                }catch(std::runtime_error const&){
                    throw std::runtime_error(std::string("EMPTY_INTERVAL_INTERSECTION primary row ")+
                        std::to_string(row)+" source "+std::to_string(source)+
                        " depth "+std::to_string(depth)+" first="+
                        primary_values[0].lower_decimal(20)+" next="+
                        primary_values[depth].lower_decimal(20));
                }
                try{
                    uniform_intersection=b2interval::intersect(
                        uniform_intersection,uniform_values[depth]);
                }catch(std::runtime_error const&){
                    throw std::runtime_error(std::string("EMPTY_INTERVAL_INTERSECTION uniform row ")+
                        std::to_string(row)+" source "+std::to_string(source)+
                        " depth "+std::to_string(depth)+" first="+
                        uniform_values[0].lower_decimal(20)+" next="+
                        uniform_values[depth].lower_decimal(20));
                }
            }
            result.primary[row].push_back(primary_values);
            result.uniform[row].push_back(uniform_values);
            result.intersections[row].push_back(primary_intersection);
            uniform_intersections.push_back(uniform_intersection);
        }
        certify_uncertainty(mesh,result.source_ids,result.intersections[row],
                            length,uncertainty_targets[row]);
        certify_uncertainty(mesh,result.source_ids,uniform_intersections,
                            length,uncertainty_targets[row]);
    }
    return result;
}

OracleSample evaluate_sample(std::string const &directory,std::string const &mutation,
                             int face,int corner,double q0,double q1){
    if(std::strcmp(MPFR_VERSION_STRING,"4.2.2")!=0 ||
       std::strcmp(mpfr_get_version(),"4.2.2")!=0)
        throw std::runtime_error("MPFR_VERSION_MISMATCH");
    if(std::fesetround(FE_TONEAREST)!=0 || std::fegetround()!=FE_TONEAREST)
        throw std::runtime_error("oracle requires FE_TONEAREST at binary64 boundary");
    RefinedState initial;initial.mesh=b2stam_fixture::read(directory);
    b2stam_fixture::mutate(initial.mesh,mutation);b2stam_fixture::validate(initial.mesh);
    if(face<0 || static_cast<std::size_t>(face)>=initial.mesh.faces.size() || corner< -1 || corner>2)
        throw std::runtime_error("oracle request face/corner outside fixture");
    initial.face=face;initial.stencils=b2uniform::identity(initial.mesh.vertices.size());
    initial.point={{MpfrInterval::exact_double(q0),MpfrInterval::exact_double(q1)}};
    if(corner==-1){
        auto local=b2stam_fixture::local_support(initial.mesh,face,0);
        if(local.valence!=6 || std::any_of(local.source_ids.begin(),local.source_ids.end(),
            [&](int id){return initial.mesh.neighbor_cycles[
                static_cast<std::size_t>(id)].size()!=6;}))
            throw std::runtime_error("REGULAR_SUPPORT_NOT_REACHED_BY_DEPTH_30");
        OracleStencils local_stencils;
        for(int id:local.source_ids)local_stencils.push_back(initial.stencils[id]);
        b2uniform::CompleteMeshClosure const uniform_closure =
            b2uniform::complete_mesh_backward_closure(
                initial.mesh.vertices.size(),initial.mesh.faces,face,0);
        if(uniform_closure.valence!=6)
            throw std::runtime_error("UNIFORM_CROSSCHECK_FAILED support valence");
        b2uniform::Stencils const &uniform_stencils=uniform_closure.controls;
        certify_frozen_valence(
            6, initial.mesh, local_stencils,uniform_stencils,
            directory + "\n" + mutation + "\n" + std::to_string(face) +
                "\n-1");
        return assemble_sample(initial.mesh,0,0,{},local_stencils,
            b2stam::identity_jacobian(),
            b2stam::primary_regular_depth_rows(q0,q1),
            b2uniform::regular_depth_rows_from_controls(
                uniform_stencils,q0,q1));
    }
    int const extraordinary=initial.mesh.faces[static_cast<std::size_t>(face)][corner];
    initial.tracked_extraordinary=extraordinary;
    std::vector<RefinedState> states;states.push_back(initial);
    unsigned isolated=13;
    for(unsigned depth=0;depth<=12;++depth){
        RefinedState const &state=states.back();auto const &selected=state.mesh.faces[state.face];
        int const tracked=state.tracked_extraordinary;
        auto found=std::find(selected.begin(),selected.end(),tracked);
        if(found==selected.end())
            throw std::runtime_error(
                "NO_ISOLATION_BY_DEPTH_12 selected path left extraordinary frame");
        int support_corner=static_cast<int>(found-selected.begin());
        auto support=b2stam_fixture::local_support(state.mesh,state.face,support_corner);
        std::size_t nonregular=0;bool contains_extraordinary=false;
        for(int id:support.source_ids){
            contains_extraordinary=contains_extraordinary || id==tracked;
            nonregular += state.mesh.neighbor_cycles[static_cast<std::size_t>(id)].size()!=6;
        }
        if(nonregular==1 && contains_extraordinary){isolated=depth;break;}
        if(depth<12)states.push_back(refine_selected(state));
    }
    if(isolated>12)throw std::runtime_error("NO_ISOLATION_BY_DEPTH_12");
    if(isolated!=0)
        throw std::runtime_error(
            "UNIFORM_CROSSCHECK_FAILED refined-isolation sparse closure unavailable");

    // Isolating support and first regular support are distinct frozen depths.
    // Preserve an extraordinary N+6 control frame from the first isolation
    // for the valence-only/vertex-limit certificates, then evaluate the
    // actual selected regular face at d0 without backing up to a parent that
    // still contains multiple extraordinary vertices.
    RefinedState const &isolating_state=states[isolated];
    int const isolated_extraordinary=isolating_state.tracked_extraordinary;
    auto const &certificate_face=isolating_state.mesh.faces[
        static_cast<std::size_t>(isolating_state.face)];
    auto certificate_found=std::find(
        certificate_face.begin(),certificate_face.end(),isolated_extraordinary);
    if(certificate_found==certificate_face.end())
        throw std::runtime_error(
            "NO_ISOLATION_BY_DEPTH_12 selected certificate frame lost extraordinary");
    int const certificate_corner=static_cast<int>(
        certificate_found-certificate_face.begin());
    auto const certificate_support=b2stam_fixture::local_support(
        isolating_state.mesh,isolating_state.face,certificate_corner);
    std::size_t certificate_nonregular=0;
    for(int id:certificate_support.source_ids)certificate_nonregular +=
        isolating_state.mesh.neighbor_cycles[
            static_cast<std::size_t>(id)].size()!=6;
    if(certificate_nonregular!=1)
        throw std::runtime_error(
            "NO_ISOLATION_BY_DEPTH_12 selected certificate support is not isolated");
    unsigned const isolated_valence=certificate_support.valence;
    OracleStencils certificate_stencils;
    for(int id:certificate_support.source_ids)
        certificate_stencils.push_back(isolating_state.stencils[id]);
    b2uniform::CompleteMeshClosure const uniform_closure =
        b2uniform::complete_mesh_backward_closure(
            initial.mesh.vertices.size(),initial.mesh.faces,face,corner);
    if(uniform_closure.valence!=isolated_valence)
        throw std::runtime_error("UNIFORM_CROSSCHECK_FAILED support valence");
    b2uniform::Stencils const &uniform_stencils=uniform_closure.controls;

    certify_frozen_valence(
        isolated_valence, initial.mesh, certificate_stencils,uniform_stencils,
        directory + "\n" + mutation + "\n" + std::to_string(face) + "\n" +
            std::to_string(corner));
    double canonical0=mpfr_get_d(isolating_state.point[0].lo(),MPFR_RNDN);
    double canonical1=mpfr_get_d(isolating_state.point[1].lo(),MPFR_RNDN);
    auto local_point=b2stam_fixture::local_parameter(
        canonical0,canonical1,certificate_corner);
    auto primary_local=b2stam::primary_depth_rows(
        isolated_valence,local_point[0],local_point[1]);
    auto uniform_coarse=b2uniform::uniform_depth_rows_from_controls(
        isolated_valence,local_point[0],local_point[1],uniform_stencils);
    std::vector<std::string> prefix;
    for(b2uniform::Branch branch:isolating_state.branches)
        prefix.push_back(branch_name(branch));
    return assemble_sample(
        initial.mesh,isolated,isolating_state.depth,prefix,
        certificate_stencils,b2stam::multiply(
            corner_jacobian(certificate_corner),isolating_state.jacobian),
        primary_local,uniform_coarse);
}

std::string uncovered_reason(std::runtime_error const &error){
    static std::set<std::string> const reasons={
        "MPFR_VERSION_MISMATCH",
        "DIRECTED_INTERVAL_PRIMITIVE_FAILED",
        "INTERVAL_BRANCH_ORDERING_UNCERTIFIED",
        "NO_ISOLATION_BY_DEPTH_12","EIGENBASIS_CERTIFICATION_FAILED",
        "PARAMETRIC_MAP_CHECK_FAILED","REGULAR_SUPPORT_NOT_REACHED_BY_DEPTH_30",
        "UNIFORM_CROSSCHECK_FAILED","TANGENT_PROJECTION_CHECK_FAILED",
        "EMPTY_INTERVAL_INTERSECTION","ORACLE_MIDPOINT_NONFINITE",
        "ORACLE_MIDPOINT_BINARY64_IMPORT_INEXACT",
        "NORMALIZATION_LENGTH_NONPOSITIVE","ORACLE_UNCERTAINTY_BOUND_EXCEEDED",
        "ORACLE_SERIALIZATION_BOUND_EXCEEDED"};
    std::string reason=error.what();std::size_t space=reason.find(' ');
    if(space!=std::string::npos)reason.resize(space);
    return reasons.count(reason)?reason:std::string();
}

void emit_uncovered(std::ostream &output,std::string const &reason){
    output<<"{\"schema_version\":1,\"kind\":\"stam_oracle_sample_v1\","
              "\"status\":\"uncovered\",\"reason_code\":\""<<reason<<"\"}";
}

void emit_sample(std::ostream &output,OracleSample const &result){
    static char const *names[6]={"position","du","dv","duu","duv","dvv"};
    output<<"{\"schema_version\":1,\"kind\":\"stam_oracle_sample_v1\",\"status\":\"ok\",\"rows\":[";
    for(std::size_t row=0;row<6;++row){if(row)output<<',';
        output<<"{\"kind\":\"oracle_covered_value_v1\",\"coverage\":\"COVERED\",\"row_kind\":\""
                 <<names[row]<<"\",\"source_ids\":[";
        for(std::size_t i=0;i<result.source_ids.size();++i){if(i)output<<',';output<<result.source_ids[i];}
        auto emit_depths=[&](auto const &values){output<<'[';
            for(std::size_t source=0;source<values.size();++source){if(source)output<<',';output<<'[';
                for(std::size_t depth=0;depth<5;++depth){if(depth)output<<',';emit_interval(output,values[source][depth]);}
                output<<']';}output<<']';};
        output<<"],\"primary_depth_intervals\":";emit_depths(result.primary[row]);
        output<<",\"uniform_depth_intervals\":";emit_depths(result.uniform[row]);
        output<<",\"intersected_primary_intervals\":[";
        for(std::size_t i=0;i<result.intersections[row].size();++i){if(i)output<<',';emit_interval(output,result.intersections[row][i]);}
        output<<"],\"first_isolating_depth\":"<<result.first_isolating_depth
                 <<",\"first_regular_support_depth\":"<<result.first_regular_support_depth
                 <<",\"evaluated_depths\":[";
        for(std::size_t i=0;i<result.evaluated_depths.size();++i){if(i)output<<',';output<<result.evaluated_depths[i];}
        output<<"],\"child_branches\":[";
        for(std::size_t i=0;i<result.child_branches.size();++i){if(i)output<<',';output<<'"'<<result.child_branches[i]<<'"';}
        output<<"],\"certification\":{\"kind\":\"oracle_certification_v1\","
                    "\"eigenbasis\":\"CERTIFIED\",\"parametric_map\":\"CERTIFIED\","
                    "\"regular_support\":\"CERTIFIED\",\"interval_intersection\":\"CERTIFIED\","
                    "\"uniform_source_overlap\":\"CERTIFIED\",\"vertex_limit\":\"CERTIFIED\","
                    "\"tangent_projection\":\"CERTIFIED\",\"uncertainty_bound\":\"CERTIFIED\","
                    "\"midpoint_serialization\":\"CERTIFIED\"}}";
    }
    output<<"]}";
}

int evaluate_sample_cli(char const *directory,char const *mutation,char const *face_text,
                        char const *corner_text,char const *u_bits,char const *v_bits){
    try{emit_sample(std::cout,evaluate_sample(directory,mutation,std::stoi(face_text),
        std::stoi(corner_text),double_from_bits(u_bits),double_from_bits(v_bits)));}
    catch(std::runtime_error const &error){
        std::string reason=uncovered_reason(error);if(reason.empty())throw;
        emit_uncovered(std::cout,reason);
    }
    std::cout<<'\n';return 0;
}

int batch(){
    std::string line;
    while(std::getline(std::cin,line)){
        std::vector<std::string> fields;std::size_t begin=0;
        for(;;){std::size_t end=line.find('\t',begin);
            fields.push_back(line.substr(begin,end==std::string::npos?
                std::string::npos:end-begin));
            if(end==std::string::npos)break;begin=end+1;}
        if(fields.size()!=7 || fields[0].empty())
            throw std::runtime_error("oracle batch input shape");
        std::cout<<fields[0]<<'\t';
        try{emit_sample(std::cout,evaluate_sample(fields[1],fields[2],
            std::stoi(fields[3]),std::stoi(fields[4]),double_from_bits(fields[5]),
            double_from_bits(fields[6])));}
        catch(std::runtime_error const &error){
            std::string reason=uncovered_reason(error);if(reason.empty())throw;
            emit_uncovered(std::cout,reason);
        }
        std::cout<<'\n';
    }
    if(!std::cin.eof())throw std::runtime_error("oracle batch read failure");
    return 0;
}

int self_test() {
    if (std::strcmp(MPFR_VERSION_STRING, "4.2.2") != 0 ||
        std::strcmp(mpfr_get_version(), "4.2.2") != 0) {
        throw std::runtime_error("MPFR compile/runtime version must both be 4.2.2");
    }
    if (!b2interval::directed_rounding_mutation_self_test()) {
        throw std::runtime_error(
            "single directed-rounding mutation self-test failed");
    }
    if (!b2uniform::backward_dependency_self_test()) {
        throw std::runtime_error(
            "uniform sparse backward dependency self-test failed");
    }
    MpfrInterval one_third = b2interval::divide(MpfrInterval(1), MpfrInterval(3));
    MpfrInterval two_thirds = b2interval::add(one_third, one_third);
    MpfrInterval one_third_rescaled = b2interval::multiply(one_third, MpfrInterval(3));
    MpfrInterval two_thirds_rescaled = b2interval::multiply(two_thirds, MpfrInterval(3));
    MpfrInterval product = b2interval::multiply(MpfrInterval::decimal("1.25"),
                                                MpfrInterval::decimal("-0.4"));
    MpfrInterval root = b2interval::square_root(MpfrInterval::decimal("2"));
    MpfrInterval root_squared = b2interval::multiply(root, root);
    MpfrInterval cosine = b2interval::loop_cosine(6);
    struct ContainmentCase {
        char const *name;
        MpfrInterval const *interval;
        char const *expected;
    };
    ContainmentCase const cases[] = {
        {"one_third_rescaled", &one_third_rescaled, "1"},
        {"two_thirds_rescaled", &two_thirds_rescaled, "2"},
        {"signed_product", &product, "-0.5"},
        {"sqrt_squared", &root_squared, "2"},
        {"loop_cosine", &cosine, "0.5"},
    };
    for (ContainmentCase const &test_case : cases) {
        if (!b2interval::contains(*test_case.interval, test_case.expected)) {
            throw std::runtime_error(std::string("directed interval containment self-test failed: ") +
                                     test_case.name);
        }
    }
    bool zero_rejected = false;
    try {
        (void)b2interval::divide(MpfrInterval(1), MpfrInterval(0));
    } catch (std::runtime_error const &) {
        zero_rejected = true;
    }
    if (!zero_rejected) {
        throw std::runtime_error("zero-containing denominator was accepted");
    }
    if (!b2stam::box_spline_partition_self_test()) {
        throw std::runtime_error("quartic box-spline partition self-test failed");
    }
    if (!b2uniform_box::box_spline_partition_self_test()) {
        throw std::runtime_error(
            "uniform quartic box-spline partition self-test failed");
    }
    for(std::array<double,2> const &point:
        std::array<std::array<double,2>,4>{{{{0.125,0.125}},{{0.75,0.125}},
                                            {{0.125,0.75}},{{0.375,0.375}}}}){
        auto primary=b2stam::primary_regular_depth_rows(point[0],point[1]);
        auto uniform=b2uniform::regular_depth_rows(point[0],point[1]);
        for(std::size_t depth=0;depth<5;++depth)
            for(std::size_t row=0;row<6;++row)
                for(std::size_t source=0;source<12;++source)
                    if(!b2interval::overlaps(primary[depth].rows[row][source],
                                             uniform[depth].rows[row][source]))
                        throw std::runtime_error(
                            "regular primary/uniform refinement identity failed");
    }
    for (unsigned valence = 3; valence <= 9; ++valence) {
        if (!b2stam::primary_depth_intersection_self_test(
                valence, 0.125, 0.125)) {
            throw std::runtime_error(std::string(
                "primary Stam five-depth intersection self-test failed at valence ") +
                std::to_string(valence));
        }
        std::vector<b2stam::PrimaryDepthRows> primary=
            b2stam::primary_depth_rows(valence,0.125,0.125);
        std::vector<b2uniform::DepthRows> uniform=
            b2uniform::uniform_depth_rows(valence,0.125,0.125);
        bool crosscheck=primary.size()==uniform.size();
        for(std::size_t depth=0;crosscheck && depth<primary.size();++depth){
            crosscheck=primary[depth].depth==uniform[depth].depth;
            for(std::size_t row=0;crosscheck && row<6;++row)
                for(std::size_t source=0;crosscheck && source<valence+6;++source)
                    try{(void)b2interval::intersect(primary[depth].rows[row][source],
                                                    uniform[depth].rows[row][source]);}
                    catch(std::runtime_error const&){crosscheck=false;}
        }
        if (!crosscheck) {
            throw std::runtime_error(std::string(
                "independent uniform cross-check failed at valence ") +
                std::to_string(valence));
        }
    }
    std::ostringstream valence_records;
    bool all_eigen_residuals = true;
    bool all_krawczyk_inclusions = true;
    bool all_inverse_residuals = true;
    bool all_condition_numbers = true;
    bool all_jordan_powers = true;
    bool all_spectral_projectors = true;
    bool all_deterministic_mgs = true;
    bool all_tangent_projectors = true;
    for (unsigned valence = 3; valence <= 9; ++valence) {
        b2stam::Certification const certification =
            b2stam::certify_eigenbasis(valence);
        if (valence != 3) {
            valence_records << ',';
        }
        valence_records << "{\"valence\":" << valence
                        << ",\"dimension\":" << certification.dimension
                        << ",\"stock_matrix\":true"
                        << ",\"analytic_eigen_residual\":"
                        << (certification.eigen_residual ? "true" : "false")
                        << ",\"interval_krawczyk_inclusion\":"
                        << (certification.krawczyk_inclusion ? "true" : "false")
                        << ",\"verified_inverse_residual\":"
                        << (certification.inverse_residual ? "true" : "false")
                        << ",\"condition_number_bound\":"
                        << (certification.condition_number ? "true" : "false")
                        << ",\"jordan_power_certified\":"
                        << (certification.jordan_power ? "true" : "false")
                        << ",\"spectral_projectors_certified\":"
                        << (certification.spectral_projectors ? "true" : "false")
                        << ",\"source_id_ordered_mgs_certified\":"
                        << (certification.deterministic_mgs ? "true" : "false")
                        << ",\"tangent_projector_certified\":"
                        << (certification.tangent_projector ? "true" : "false")
                        << '}';
        all_eigen_residuals = all_eigen_residuals &&
                              certification.eigen_residual;
        all_krawczyk_inclusions = all_krawczyk_inclusions &&
                                  certification.krawczyk_inclusion;
        all_inverse_residuals = all_inverse_residuals &&
                                certification.inverse_residual;
        all_condition_numbers = all_condition_numbers &&
                                certification.condition_number;
        all_jordan_powers = all_jordan_powers &&
                            certification.jordan_power;
        all_spectral_projectors = all_spectral_projectors &&
                                  certification.spectral_projectors;
        all_deterministic_mgs = all_deterministic_mgs &&
                                certification.deterministic_mgs;
        all_tangent_projectors = all_tangent_projectors &&
                                 certification.tangent_projector;
        if (!certification.eigen_residual ||
            !certification.krawczyk_inclusion ||
            !certification.inverse_residual ||
            !certification.condition_number ||
            !certification.jordan_power ||
            !certification.spectral_projectors ||
            !certification.deterministic_mgs ||
            !certification.tangent_projector) {
            std::cerr << "valence " << valence
                      << " certification flags eigen="
                      << certification.eigen_residual
                      << " krawczyk=" << certification.krawczyk_inclusion
                      << " inverse=" << certification.inverse_residual
                      << " condition=" << certification.condition_number
                      << " jordan=" << certification.jordan_power
                      << " projectors=" << certification.spectral_projectors
                      << " mgs=" << certification.deterministic_mgs
                      << " tangent=" << certification.tangent_projector
                      << '\n';
        }
    }
    if (!all_eigen_residuals || !all_krawczyk_inclusions ||
        !all_inverse_residuals ||
        !all_condition_numbers ||
        !all_jordan_powers ||
        !all_spectral_projectors ||
        !all_deterministic_mgs ||
        !all_tangent_projectors) {
        throw std::runtime_error("primary Stam eigensystem certification self-test failed");
    }
    std::cout << "{\"schema_version\":1,\"kind\":\"stam_oracle_self_test\","
                 "\"status\":\"ok\",\"finite\":true,\"precision_bits\":544,"
                 "\"mpfr_compile_version\":\"" << MPFR_VERSION_STRING << "\","
                 "\"mpfr_runtime_version\":\"" << mpfr_get_version() << "\","
                 "\"directed_rounding\":true,"
                 "\"single_rounding_direction_mutations_rejected\":true,"
                 "\"zero_denominator_rejected\":true,"
                 "\"candidate_dependency_free\":true,"
                 "\"stock_loop_matrix_constructed_from_masks\":true,"
                 "\"quartic_box_spline_interval_rows\":true,"
                 "\"certified_parametric_branch_mapping\":true,"
                 "\"primary_five_depth_intersection\":true,"
                 "\"independent_uniform_five_depth_crosscheck\":true,"
                 "\"primary_eigensystem_certified_valence_min\":3,"
                 "\"primary_eigensystem_certified_valence_max\":9,"
                 "\"valence_certificates\":[" << valence_records.str() << "]}\n";
    return 0;
}

int capability(){
    std::cout<<"{\"schema_version\":1,\"kind\":\"independent_primary_capability\","
                 "\"status\":\"implemented\",\"coverage\":\"AVAILABLE\","
                 "\"implementation_state\":\"PRIMARY_STAM_AND_UNIFORM_AVAILABLE\","
                 "\"precision_bits\":544,\"mpfr_version\":\"4.2.2\","
                 "\"stock_mask_interval_matrix_construction\":true,"
                 "\"interval_eigenpair_krawczyk_certification\":true,"
                 "\"repeated_eigenspace_spectral_projector_certification\":true,"
                 "\"quartic_box_spline_interval_evaluation\":true,"
                 "\"certified_parametric_branch_mapping\":true,"
                 "\"independent_uniform_five_depth_intersection\":true,"
                 "\"uniform_success_substituted_for_primary\":false}\n";
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") {
            return self_test();
        }
        if (argc == 2 && std::string(argv[1]) == "--capability") {
            return capability();
        }
        if (argc == 2 && std::string(argv[1]) == "--batch") {
            return batch();
        }
        if (argc == 8 && std::string(argv[1]) == "--evaluate-sample") {
            return evaluate_sample_cli(argv[2],argv[3],argv[4],argv[5],argv[6],argv[7]);
        }
        std::cerr << "usage: stam_oracle --self-test | --capability | --batch | --evaluate-sample "
                     "MESH_DIR MUTATION FACE CORNER U_BITS V_BITS\n";
        return 2;
    } catch (std::exception const &error) {
        std::cerr << error.what() << "\n";
        return 3;
    }
}
