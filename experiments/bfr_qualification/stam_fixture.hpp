#pragma once

#include <algorithm>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace b2stam_fixture {

struct Mesh {
    std::vector<std::array<double,3>> vertices;
    std::vector<std::array<std::string,3>> coordinate_text;
    std::vector<std::array<int,3>> faces;
    std::vector<std::vector<int>> neighbor_cycles;
    std::map<std::pair<int,int>, std::array<int,2>> edge_opposites;
};

inline std::vector<std::string> csv_fields(std::string const &line) {
    std::vector<std::string> fields; std::stringstream stream(line);
    std::string field;
    while (std::getline(stream,field,',')) fields.push_back(field);
    if (!line.empty() && line.back()==',') fields.push_back("");
    return fields;
}

inline int integer_field(std::string const &text) {
    errno=0; char *end=nullptr; long value=std::strtol(text.c_str(),&end,10);
    if(errno==ERANGE || end!=text.c_str()+text.size() || value<0 ||
       value>2147483647L) throw std::runtime_error("invalid oracle fixture index");
    return static_cast<int>(value);
}

inline double binary64_field(std::string const &text) {
    errno=0; char *end=nullptr; double value=std::strtod(text.c_str(),&end);
    if(errno==ERANGE || end!=text.c_str()+text.size() || !std::isfinite(value))
        throw std::runtime_error("invalid oracle fixture coordinate");
    return value;
}

inline std::uint64_t bits(double value){
    std::uint64_t result=0; std::memcpy(&result,&value,sizeof(result)); return result;
}

inline Mesh read(std::string const &directory) {
    Mesh mesh; std::ifstream vertices(directory+"/vertices.csv");
    std::ifstream faces(directory+"/faces.csv");
    if(!vertices || !faces) throw std::runtime_error("oracle fixture unavailable");
    std::string line;
    while(std::getline(vertices,line)){
        auto f=csv_fields(line); if(f.size()!=3) throw std::runtime_error("oracle xyz shape");
        mesh.vertices.push_back({{binary64_field(f[0]),binary64_field(f[1]),binary64_field(f[2])}});
        mesh.coordinate_text.push_back({{f[0],f[1],f[2]}});
    }
    while(std::getline(faces,line)){
        auto f=csv_fields(line); if(f.size()!=3) throw std::runtime_error("oracle triangle shape");
        mesh.faces.push_back({{integer_field(f[0]),integer_field(f[1]),integer_field(f[2])}});
    }
    if(!vertices.eof() || !faces.eof() || mesh.vertices.empty() || mesh.faces.empty())
        throw std::runtime_error("oracle fixture read incomplete");
    return mesh;
}

inline void mutate(Mesh &mesh,std::string const &mutation){
    if(mutation.empty() || mutation=="none") return;
    if(mutation=="coordinate_perturbation_v1"){
        if(mesh.vertices.size()<=1 || std::fegetround()!=FE_TONEAREST)
            throw std::runtime_error("oracle coordinate mutation precondition");
        std::array<std::uint64_t,3> const expected={{
            UINT64_C(0x3ff2b851eb851eb8),UINT64_C(0xbfe0cffc0ea99f27),
            UINT64_C(0x3fc0a3d70a3d70a4)}};
        std::array<std::uint64_t,3> const output={{
            UINT64_C(0x3ff2c851eb851eb8),UINT64_C(0xbfe0dffc0ea99f27),
            UINT64_C(0x3fc0c3d70a3d70a4)}};
        std::array<double,3> const delta={{0x1.0p-8,-0x1.0p-9,0x1.0p-10}};
        for(std::size_t axis=0;axis<3;++axis){
            if(bits(mesh.vertices[1][axis])!=expected[axis])
                throw std::runtime_error("oracle mutation input drift");
            mesh.vertices[1][axis]+=delta[axis];
            if(bits(mesh.vertices[1][axis])!=output[axis])
                throw std::runtime_error("oracle mutation output drift");
            mesh.coordinate_text[1][axis].clear();
        }
        return;
    }
    if(mutation=="reverse_face_zero_v1"){
        std::swap(mesh.faces.at(0)[1],mesh.faces.at(0)[2]);return;
    }
    if(mutation=="delete_face_zero_v1"){mesh.faces.erase(mesh.faces.begin());return;}
    if(mutation=="append_face_zero_v1"){mesh.faces.push_back(mesh.faces.at(0));return;}
    throw std::runtime_error("unknown oracle fixture mutation");
}

inline std::pair<int,int> edge(int a,int b){return a<b?std::make_pair(a,b):std::make_pair(b,a);}

inline void validate(Mesh &mesh){
    std::vector<std::map<int,std::set<int>>> links(mesh.vertices.size());
    std::map<std::pair<int,int>,std::vector<std::array<int,3>>> incidents;
    std::set<std::array<int,3>> unique; std::vector<bool> referenced(mesh.vertices.size());
    for(auto const &face:mesh.faces){
        std::array<int,3> sorted=face;std::sort(sorted.begin(),sorted.end());
        if(!unique.insert(sorted).second) throw std::runtime_error("oracle duplicate face");
        for(int c=0;c<3;++c){
            int v=face[c],next=face[(c+1)%3],previous=face[(c+2)%3];
            if(v<0 || static_cast<std::size_t>(v)>=mesh.vertices.size() ||
               v==next || next==previous || previous==v)
                throw std::runtime_error("oracle invalid triangular incidence");
            referenced[static_cast<std::size_t>(v)]=true;
            incidents[edge(v,next)].push_back({{v,next,previous}});
            links[v][next].insert(previous);links[v][previous].insert(next);
        }
    }
    for(bool item:referenced) if(!item) throw std::runtime_error("oracle unreferenced vertex");
    for(auto const &item:incidents){
        if(item.second.size()!=2 || item.second[0][0]!=item.second[1][1] ||
           item.second[0][1]!=item.second[1][0])
            throw std::runtime_error("oracle nonclosed or unoriented edge");
        mesh.edge_opposites[item.first]={{item.second[0][2],item.second[1][2]}};
    }
    mesh.neighbor_cycles.resize(mesh.vertices.size());
    for(std::size_t v=0;v<links.size();++v){
        if(links[v].size()<3) throw std::runtime_error("oracle invalid vertex link");
        for(auto const &item:links[v]) if(item.second.size()!=2)
            throw std::runtime_error("oracle invalid vertex link degree");
        int start=links[v].begin()->first,previous=-1,current=start;
        do{
            mesh.neighbor_cycles[v].push_back(current);
            auto const &adjacent=links[v].at(current);
            int next=*adjacent.begin(); if(next==previous) next=*adjacent.rbegin();
            previous=current;current=next;
            if(mesh.neighbor_cycles[v].size()>links[v].size())
                throw std::runtime_error("oracle vertex link cycle overflow");
        }while(current!=start);
        if(mesh.neighbor_cycles[v].size()!=links[v].size())
            throw std::runtime_error("oracle disconnected vertex link");
    }
}

inline int opposite(Mesh const &mesh,int a,int b,int excluded){
    auto const &values=mesh.edge_opposites.at(edge(a,b));
    if(values[0]==excluded) return values[1];
    if(values[1]==excluded) return values[0];
    throw std::runtime_error("oracle edge exclusion mismatch");
}

struct LocalSupport {
    unsigned valence;
    std::vector<int> source_ids;
};

inline LocalSupport local_support(Mesh const &mesh,int face_index,int corner){
    if(face_index<0 || static_cast<std::size_t>(face_index)>=mesh.faces.size() ||
       corner<0 || corner>2) throw std::runtime_error("oracle face/corner outside fixture");
    auto const &face=mesh.faces[static_cast<std::size_t>(face_index)];
    int const extraordinary=face[corner];
    int const a=face[(corner+1)%3], b=face[(corner+2)%3];
    auto const &cycle=mesh.neighbor_cycles[static_cast<std::size_t>(extraordinary)];
    auto a_it=std::find(cycle.begin(),cycle.end(),a);
    if(a_it==cycle.end()) throw std::runtime_error("oracle corner neighbor absent");
    std::size_t a_index=static_cast<std::size_t>(a_it-cycle.begin());
    std::vector<int> forward,reverse;
    for(int direction: {1,-1}){
        std::vector<int> ring; std::size_t index=a_index;
        for(std::size_t count=0;count<cycle.size();++count){
            ring.push_back(cycle[index]); if(cycle[index]==b) break;
            index=(index+cycle.size()+direction)%cycle.size();
        }
        if(direction==1) forward=ring; else reverse=ring;
    }
    std::vector<int> ring;
    if(forward.size()==cycle.size()) ring=forward;
    else if(reverse.size()==cycle.size()) ring=reverse;
    else throw std::runtime_error("oracle oriented ring does not end at face neighbor");
    unsigned const valence=static_cast<unsigned>(ring.size());
    int const n2=opposite(mesh,a,b,extraordinary);
    int const n3=opposite(mesh,a,ring[1],extraordinary);
    int const n4=opposite(mesh,a,n3,ring[1]);
    int const n5=opposite(mesh,b,ring[valence-2],extraordinary);
    int const n6=opposite(mesh,b,n5,ring[valence-2]);
    std::vector<int> ids;ids.reserve(valence+6);ids.push_back(extraordinary);
    ids.insert(ids.end(),ring.begin(),ring.end());
    ids.insert(ids.end(),{n2,n3,n4,n5,n6});
    if(ids.size()!=valence+6)
        throw std::runtime_error("oracle local support is not N+6");
    return {valence,ids};
}

inline std::array<double,2> local_parameter(double q0,double q1,int corner){
    double const barycentric[3]={1.0-q0-q1,q0,q1};
    return {{barycentric[(corner+1)%3],barycentric[(corner+2)%3]}};
}

}  // namespace b2stam_fixture
