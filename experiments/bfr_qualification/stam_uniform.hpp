#pragma once

#include "stam_box_spline.hpp"

#include <array>
#include <cstddef>
#include <stdexcept>
#include <vector>

namespace b2uniform {

using b2interval::MpfrInterval;
using Row = std::vector<MpfrInterval>;
using Stencils = std::vector<Row>;
using SixRows = std::array<Row, 6>;
using Jacobian = std::array<std::array<MpfrInterval, 2>, 2>;

enum class Branch { T0, T1, T2, Tc };

inline Stencils zeros(std::size_t rows, std::size_t columns) {
    return Stencils(rows, Row(columns, MpfrInterval(0)));
}

inline Stencils identity(std::size_t size) {
    Stencils value = zeros(size, size);
    for (std::size_t index = 0; index < size; ++index) {
        value[index][index] = MpfrInterval(1);
    }
    return value;
}

inline void add_scaled(Row &target, Row const &source,
                       MpfrInterval const &scale) {
    if (target.size() != source.size()) {
        throw std::runtime_error("uniform stencil shape mismatch");
    }
    for (std::size_t index = 0; index < target.size(); ++index) {
        target[index] = b2interval::add(
            target[index], b2interval::multiply(scale, source[index]));
    }
}

inline Stencils refine_local(Stencils const &input, unsigned valence) {
    if (input.size() != valence + 6 || input.empty()) {
        throw std::runtime_error("uniform local stencil cardinality");
    }
    std::size_t const columns = input.front().size();
    Stencils output = zeros(valence + 12, columns);
    MpfrInterval const tangent = b2interval::add(
        MpfrInterval::rational(3, 8),
        b2interval::multiply(
            MpfrInterval::rational(1, 4),
            b2interval::loop_angle_cosine(valence, 1)));
    MpfrInterval const beta = b2interval::divide(
        b2interval::subtract(MpfrInterval::rational(5, 8),
                             b2interval::multiply(tangent, tangent)),
        MpfrInterval(static_cast<long>(valence)));
    add_scaled(output[0], input[0], b2interval::subtract(
        MpfrInterval(1), b2interval::multiply(
            MpfrInterval(static_cast<long>(valence)), beta)));
    for (unsigned ring = 0; ring < valence; ++ring) {
        add_scaled(output[0], input[1 + ring], beta);
        Row &edge = output[1 + ring];
        add_scaled(edge, input[0], MpfrInterval::rational(3, 8));
        add_scaled(edge, input[1 + ring], MpfrInterval::rational(3, 8));
        add_scaled(edge, input[1 + ((ring + valence - 1) % valence)],
                   MpfrInterval::rational(1, 8));
        add_scaled(edge, input[1 + ((ring + 1) % valence)],
                   MpfrInterval::rational(1, 8));
    }
    std::size_t const outer = valence + 1;
    add_scaled(output[outer], input[0], MpfrInterval::rational(1, 8));
    add_scaled(output[outer], input[1], MpfrInterval::rational(3, 8));
    add_scaled(output[outer], input[valence], MpfrInterval::rational(3, 8));
    add_scaled(output[outer], input[outer], MpfrInterval::rational(1, 8));

    for (std::pair<std::size_t, long> const &term :
         std::vector<std::pair<std::size_t, long>>{
             {0,1},{1,10},{2,1},{valence,1},{outer,1},{outer+1,1},{outer+2,1}}) {
        add_scaled(output[outer + 1], input[term.first],
                   MpfrInterval::rational(term.second, 16));
    }
    add_scaled(output[outer + 2], input[0], MpfrInterval::rational(1, 8));
    add_scaled(output[outer + 2], input[1], MpfrInterval::rational(3, 8));
    add_scaled(output[outer + 2], input[2], MpfrInterval::rational(3, 8));
    add_scaled(output[outer + 2], input[outer + 2],
               MpfrInterval::rational(1, 8));

    for (std::pair<std::size_t, long> const &term :
         std::vector<std::pair<std::size_t, long>>{
             {0,1},{1,1},{valence-1,1},{valence,10},{outer,1},
             {outer+3,1},{outer+4,1}}) {
        add_scaled(output[outer + 3], input[term.first],
                   MpfrInterval::rational(term.second, 16));
    }
    add_scaled(output[outer + 4], input[0], MpfrInterval::rational(1, 8));
    add_scaled(output[outer + 4], input[valence - 1],
               MpfrInterval::rational(3, 8));
    add_scaled(output[outer + 4], input[valence],
               MpfrInterval::rational(3, 8));
    add_scaled(output[outer + 4], input[outer + 4],
               MpfrInterval::rational(1, 8));

    auto eighth = [&](std::size_t row, std::size_t column, long numerator) {
        add_scaled(output[valence + 6 + row], input[column],
                   MpfrInterval::rational(numerator, 8));
    };
    eighth(0,1,3); eighth(0,valence,1); eighth(1,1,3);
    eighth(2,1,3); eighth(2,2,1); eighth(3,1,1);
    eighth(3,valence,3); eighth(4,valence,3);
    eighth(5,valence-1,1); eighth(5,valence,3);
    long const outer_weights[6][5] = {
        {3,1,0,0,0}, {1,3,1,0,0}, {0,1,3,0,0},
        {3,0,0,1,0}, {1,0,0,3,1}, {0,0,0,1,3},
    };
    for (std::size_t row = 0; row < 6; ++row) {
        for (std::size_t column = 0; column < 5; ++column) {
            if (outer_weights[row][column]) {
                eighth(row, outer + column, outer_weights[row][column]);
            }
        }
    }
    return output;
}

inline std::array<std::size_t, 12> picked_labels(unsigned valence,
                                                 Branch branch) {
    if (branch == Branch::T1) {
        return {{3,1,valence+4,2,valence+1,valence+9,valence+3,
                 valence+2,valence+5,valence+8,valence+7,valence+10}};
    }
    if (branch == Branch::Tc) {
        return {{valence+4,3,valence+3,2,1,valence+7,valence+2,
                 valence+1,valence,valence+10,valence+5,valence+6}};
    }
    if (branch == Branch::T2) {
        return {{1,valence,2,valence+1,valence+6,valence+3,valence+2,
                 valence+5,valence+12,valence+7,valence+10,valence+11}};
    }
    throw std::runtime_error("uniform extraordinary T0 is not regular");
}

inline Stencils pick_regular(Stencils const &refined, unsigned valence,
                             Branch branch) {
    std::array<std::size_t, 12> const labels = picked_labels(valence, branch);
    Stencils result;
    result.reserve(12);
    for (std::size_t label : labels) {
        result.push_back(refined.at(label - 1));
    }
    return result;
}

inline Stencils regular_to_local(Stencils const &regular) {
    static std::size_t const labels[12] = {4,7,3,1,2,5,8,11,10,6,12,9};
    if (regular.size() != 12) {
        throw std::runtime_error("uniform regular stencil cardinality");
    }
    Stencils local;
    local.reserve(12);
    for (std::size_t label : labels) {
        local.push_back(regular[label - 1]);
    }
    return local;
}

inline Stencils local_to_regular(Stencils const &local) {
    static std::size_t const labels[12] = {4,7,3,1,2,5,8,11,10,6,12,9};
    if (local.size() != 12) {
        throw std::runtime_error("uniform local N=6 stencil cardinality");
    }
    Stencils regular = zeros(12, local.front().size());
    for (std::size_t index = 0; index < 12; ++index) {
        regular[labels[index] - 1] = local[index];
    }
    return regular;
}

inline Branch choose_child(std::array<MpfrInterval,2> const &point) {
    MpfrInterval const half = MpfrInterval::rational(1,2);
    MpfrInterval const sum = b2interval::add(point[0], point[1]);
    if (mpfr_lessequal_p(sum.hi(), half.lo())) return Branch::T0;
    if (mpfr_greaterequal_p(point[0].lo(), half.hi())) return Branch::T1;
    if (mpfr_greaterequal_p(point[1].lo(), half.hi())) return Branch::T2;
    return Branch::Tc;
}

inline Jacobian branch_jacobian(Branch branch) {
    if (branch == Branch::Tc) {
        return {{{MpfrInterval(2),MpfrInterval(2)},
                 {MpfrInterval(-2),MpfrInterval(0)}}};
    }
    return {{{MpfrInterval(2),MpfrInterval(0)},
             {MpfrInterval(0),MpfrInterval(2)}}};
}

inline std::array<MpfrInterval,2> map_child(
    Branch branch, std::array<MpfrInterval,2> const &point) {
    if (branch == Branch::T0) {
        return {{b2interval::multiply(MpfrInterval(2), point[0]),
                 b2interval::multiply(MpfrInterval(2), point[1])}};
    }
    if (branch == Branch::T1) {
        return {{b2interval::subtract(
                     b2interval::multiply(MpfrInterval(2), point[0]),
                     MpfrInterval(1)),
                 b2interval::multiply(MpfrInterval(2), point[1])}};
    }
    if (branch == Branch::T2) {
        return {{b2interval::multiply(MpfrInterval(2), point[0]),
                 b2interval::subtract(
                     b2interval::multiply(MpfrInterval(2), point[1]),
                     MpfrInterval(1))}};
    }
    return {{b2interval::subtract(
                 b2interval::multiply(
                     MpfrInterval(2), b2interval::add(point[0], point[1])),
                 MpfrInterval(1)),
             b2interval::subtract(MpfrInterval(1),
                                  b2interval::multiply(
                                      MpfrInterval(2), point[0]))}};
}

inline Jacobian multiply_jacobian(Jacobian const &left,
                                  Jacobian const &right) {
    Jacobian result = {{{MpfrInterval(0),MpfrInterval(0)},
                        {MpfrInterval(0),MpfrInterval(0)}}};
    for (std::size_t i=0;i<2;++i) for (std::size_t k=0;k<2;++k)
        for (std::size_t j=0;j<2;++j)
            result[i][j]=b2interval::add(result[i][j],
                b2interval::multiply(left[i][k],right[k][j]));
    return result;
}

inline Row combine_box(b2stam::BoxSplineRow const &basis,
                       Stencils const &controls) {
    Row result(controls.front().size(), MpfrInterval(0));
    for (std::size_t i=0;i<12;++i) for (std::size_t j=0;j<result.size();++j)
        result[j]=b2interval::add(result[j],
            b2interval::multiply(basis[i],controls[i][j]));
    return result;
}

inline SixRows evaluate_regular(Stencils const &controls,
                                std::array<MpfrInterval,2> const &point,
                                Jacobian const &jacobian) {
    using b2stam::BoxSplineRow;
    BoxSplineRow b=b2stam::box_spline_row(point[0],point[1],0,0);
    BoxSplineRow s=b2stam::box_spline_row(point[0],point[1],1,0);
    BoxSplineRow t=b2stam::box_spline_row(point[0],point[1],0,1);
    BoxSplineRow ss=b2stam::box_spline_row(point[0],point[1],2,0);
    BoxSplineRow st=b2stam::box_spline_row(point[0],point[1],1,1);
    BoxSplineRow tt=b2stam::box_spline_row(point[0],point[1],0,2);
    auto linear=[&](std::size_t column){
        BoxSplineRow out;
        for(std::size_t i=0;i<12;++i) out[i]=b2interval::add(
            b2interval::multiply(jacobian[0][column],s[i]),
            b2interval::multiply(jacobian[1][column],t[i]));
        return out;
    };
    auto second=[&](std::size_t a,std::size_t c){
        BoxSplineRow out;
        for(std::size_t i=0;i<12;++i){
            out[i]=b2interval::multiply(b2interval::multiply(
                jacobian[0][a],jacobian[0][c]),ss[i]);
            out[i]=b2interval::add(out[i],b2interval::multiply(
                b2interval::add(b2interval::multiply(jacobian[0][a],jacobian[1][c]),
                                b2interval::multiply(jacobian[1][a],jacobian[0][c])),st[i]));
            out[i]=b2interval::add(out[i],b2interval::multiply(
                b2interval::multiply(jacobian[1][a],jacobian[1][c]),tt[i]));
        }
        return out;
    };
    return {{combine_box(b,controls),combine_box(linear(0),controls),
             combine_box(linear(1),controls),combine_box(second(0,0),controls),
             combine_box(second(0,1),controls),combine_box(second(1,1),controls)}};
}

struct DepthRows { unsigned depth; SixRows rows; };

inline std::vector<DepthRows> regular_depth_rows(double xi,double eta){
    Stencils controls=local_to_regular(identity(12));
    std::array<MpfrInterval,2> point={{MpfrInterval::exact_double(xi),
                                      MpfrInterval::exact_double(eta)}};
    Jacobian jac={{{MpfrInterval(1),MpfrInterval(0)},
                   {MpfrInterval(0),MpfrInterval(1)}}};
    std::vector<DepthRows> result;
    for(unsigned depth=0;depth<5;++depth){
        result.push_back({depth,evaluate_regular(controls,point,jac)});
        if(depth==4)break;
        Branch branch=choose_child(point);point=map_child(branch,point);
        jac=multiply_jacobian(branch_jacobian(branch),jac);
        Stencils local=regular_to_local(controls);
        Stencils refined=refine_local(local,6);
        if(branch==Branch::T0){
            Stencils next_local(refined.begin(),refined.begin()+12);
            controls=local_to_regular(next_local);
        }else controls=pick_regular(refined,6,branch);
    }
    return result;
}

inline std::vector<DepthRows> uniform_depth_rows(unsigned valence,
                                                 double xi, double eta) {
    Stencils controls=identity(valence+6);
    std::array<MpfrInterval,2> point={{MpfrInterval::exact_double(xi),
                                      MpfrInterval::exact_double(eta)}};
    Jacobian jac={{{MpfrInterval(1),MpfrInterval(0)},
                   {MpfrInterval(0),MpfrInterval(1)}}};
    bool regular=false; unsigned first=0; std::vector<DepthRows> out;
    for(unsigned depth=1;depth<=30;++depth){
        Branch branch=choose_child(point);
        point=map_child(branch,point);
        jac=multiply_jacobian(branch_jacobian(branch),jac);
        if(!regular){
            Stencils refined=refine_local(controls,valence);
            if(branch==Branch::T0){
                controls.assign(refined.begin(),refined.begin()+valence+6);
            }else{
                controls=pick_regular(refined,valence,branch);
                regular=true;first=depth;
                if(first>12) throw std::runtime_error("NO_ISOLATION_BY_DEPTH_12");
            }
        }else{
            Stencils local=regular_to_local(controls);
            Stencils refined=refine_local(local,6);
            if(branch==Branch::T0){
                Stencils next_local(refined.begin(),refined.begin()+12);
                controls=local_to_regular(next_local);
            }else controls=pick_regular(refined,6,branch);
        }
        if(regular && depth>=first){
            out.push_back({depth,evaluate_regular(controls,point,jac)});
            if(out.size()==5) return out;
        }
    }
    throw std::runtime_error("REGULAR_SUPPORT_NOT_REACHED_BY_DEPTH_30");
}

}  // namespace b2uniform
