#pragma once

#include "stam_box_spline.hpp"
#include "stam_primary.hpp"

#include <array>
#include <cstddef>
#include <map>
#include <stdexcept>
#include <vector>

namespace b2stam {

enum class ChildBranch { T0, T1, T2, Tc };

inline char const *child_branch_name(ChildBranch branch) {
    switch (branch) {
        case ChildBranch::T0: return "T0";
        case ChildBranch::T1: return "T1";
        case ChildBranch::T2: return "T2";
        case ChildBranch::Tc: return "Tc";
    }
    throw std::runtime_error("unknown child branch");
}

using Jacobian = std::array<std::array<MpfrInterval, 2>, 2>;

inline Jacobian identity_jacobian() {
    return {{{MpfrInterval(1), MpfrInterval(0)},
             {MpfrInterval(0), MpfrInterval(1)}}};
}

inline Jacobian multiply(Jacobian const &left, Jacobian const &right) {
    Jacobian result = {{{MpfrInterval(0), MpfrInterval(0)},
                        {MpfrInterval(0), MpfrInterval(0)}}};
    for (std::size_t row = 0; row < 2; ++row) {
        for (std::size_t inner = 0; inner < 2; ++inner) {
            for (std::size_t column = 0; column < 2; ++column) {
                result[row][column] = b2interval::matrix_accumulate(
                    result[row][column],
                    b2interval::multiply(left[row][inner],
                                         right[inner][column]));
            }
        }
    }
    return result;
}

inline Matrix extended_subdivision_matrix(unsigned valence) {
    Matrix upper = stock_subdivision_matrix(valence);
    std::size_t const input_size = valence + 6;
    Matrix result = zero_matrix(valence + 12, input_size);
    for (std::size_t row = 0; row < upper.size(); ++row) {
        result[row] = upper[row];
    }
    std::size_t const ring_last = valence;
    std::size_t const outer = valence + 1;
    auto eighth = [&](std::size_t row, std::size_t column, long numerator) {
        result[valence + 6 + row][column] =
            MpfrInterval::rational(numerator, 8);
    };

    // Stam Appendix B, S21 (six by N+1).
    eighth(0, 1, 3); eighth(0, ring_last, 1);
    eighth(1, 1, 3);
    eighth(2, 1, 3); eighth(2, 2, 1);
    eighth(3, 1, 1); eighth(3, ring_last, 3);
    eighth(4, ring_last, 3);
    eighth(5, ring_last - 1, 1); eighth(5, ring_last, 3);

    // Stam Appendix B, S22 (six by five), whose columns are N+2..N+6.
    long const s22[6][5] = {
        {3,1,0,0,0}, {1,3,1,0,0}, {0,1,3,0,0},
        {3,0,0,1,0}, {1,0,0,3,1}, {0,0,0,1,3},
    };
    for (std::size_t row = 0; row < 6; ++row) {
        for (std::size_t column = 0; column < 5; ++column) {
            if (s22[row][column] != 0) {
                eighth(row, outer + column, s22[row][column]);
            }
        }
    }
    return result;
}

inline std::array<std::size_t, 12> picking_labels(unsigned valence,
                                                  ChildBranch branch) {
    if (branch == ChildBranch::T1) {
        return {{3, 1, valence + 4, 2, valence + 1, valence + 9,
                 valence + 3, valence + 2, valence + 5, valence + 8,
                 valence + 7, valence + 10}};
    }
    if (branch == ChildBranch::Tc) {
        // Fig. 4 patch 2 is rotated relative to the canonical (v,w) frame.
        // This ordering is the diagram's controls after applying the frozen
        // Tc(v,w)=(2v+2w-1,1-2v) orientation.
        return {{valence + 4, 3, valence + 3, 2, 1,
                 valence + 7, valence + 2, valence + 1, valence,
                 valence + 10, valence + 5, valence + 6}};
    }
    if (branch == ChildBranch::T2) {
        return {{1, valence, 2, valence + 1, valence + 6,
                 valence + 3, valence + 2, valence + 5,
                 valence + 12, valence + 7, valence + 10,
                 valence + 11}};
    }
    throw std::runtime_error("extraordinary child T0 lacks regular support");
}

inline Matrix regular_extraction(unsigned valence, ChildBranch branch) {
    Matrix extended = extended_subdivision_matrix(valence);
    std::array<std::size_t, 12> const labels = picking_labels(valence, branch);
    Matrix result = zero_matrix(12, valence + 6);
    for (std::size_t row = 0; row < labels.size(); ++row) {
        if (labels[row] == 0 || labels[row] > extended.size()) {
            throw std::runtime_error("published picking label outside extended matrix");
        }
        result[row] = extended[labels[row] - 1];
    }
    return result;
}

inline std::array<std::size_t, 12> regular_to_local_labels() {
    // N=6 local ordering (Stam Fig. 2) expressed in the regular control order
    // of Fig. 1.  Values are one-based labels in Fig. 1.
    return {{4, 7, 3, 1, 2, 5, 8, 11, 10, 6, 12, 9}};
}

inline Matrix local_from_regular() {
    Matrix result = zero_matrix(12, 12);
    std::array<std::size_t, 12> const labels = regular_to_local_labels();
    for (std::size_t local = 0; local < labels.size(); ++local) {
        result[local][labels[local] - 1] = MpfrInterval(1);
    }
    return result;
}

inline Matrix regular_from_local() {
    return transpose(local_from_regular());
}

inline Matrix regular_child_extraction(ChildBranch branch) {
    Matrix const local = local_from_regular();
    if (branch == ChildBranch::T0) {
        return multiply(
            multiply(regular_from_local(), stock_subdivision_matrix(6)),
            local);
    }
    return multiply(regular_extraction(6, branch), local);
}

struct ChildMap {
    ChildBranch branch;
    Jacobian jacobian;
    std::array<MpfrInterval, 2> offset;
};

inline ChildMap select_child(std::array<MpfrInterval, 2> const &point) {
    MpfrInterval const half = MpfrInterval::rational(1, 2);
    MpfrInterval const sum = b2interval::add(point[0], point[1]);
    if (mpfr_lessequal_p(sum.hi(), half.lo())) {
        return {ChildBranch::T0,
                {{{MpfrInterval(2), MpfrInterval(0)},
                  {MpfrInterval(0), MpfrInterval(2)}}},
                {{MpfrInterval(0), MpfrInterval(0)}}};
    }
    if (mpfr_greaterequal_p(point[0].lo(), half.hi())) {
        return {ChildBranch::T1,
                {{{MpfrInterval(2), MpfrInterval(0)},
                  {MpfrInterval(0), MpfrInterval(2)}}},
                {{MpfrInterval(-1), MpfrInterval(0)}}};
    }
    if (mpfr_greaterequal_p(point[1].lo(), half.hi())) {
        return {ChildBranch::T2,
                {{{MpfrInterval(2), MpfrInterval(0)},
                  {MpfrInterval(0), MpfrInterval(2)}}},
                {{MpfrInterval(0), MpfrInterval(-1)}}};
    }
    if (mpfr_sgn(sum.lo()) < 0 || mpfr_greater_p(sum.hi(), MpfrInterval(1).lo()) ||
        mpfr_sgn(point[0].lo()) < 0 || mpfr_sgn(point[1].lo()) < 0) {
        throw std::runtime_error("parameter interval outside closed unit triangle");
    }
    return {ChildBranch::Tc,
            {{{MpfrInterval(2), MpfrInterval(2)},
              {MpfrInterval(-2), MpfrInterval(0)}}},
            {{MpfrInterval(-1), MpfrInterval(1)}}};
}

inline std::array<MpfrInterval, 2> apply_child(
    ChildMap const &map, std::array<MpfrInterval, 2> const &point) {
    std::array<MpfrInterval, 2> result = map.offset;
    for (std::size_t row = 0; row < 2; ++row) {
        for (std::size_t column = 0; column < 2; ++column) {
            result[row] = b2interval::add(
                result[row],
                b2interval::multiply(map.jacobian[row][column], point[column]));
        }
    }
    for (MpfrInterval const &coordinate : result) {
        if (mpfr_sgn(coordinate.lo()) < 0 ||
            mpfr_greater_p(coordinate.hi(), MpfrInterval(1).lo())) {
            throw std::runtime_error("certified child map left the unit triangle");
        }
    }
    return result;
}

using SixRows = std::array<Vector, 6>;

struct CertifiedPowerData {
    Eigenbasis basis;
    Matrix inverse;
};

inline CertifiedPowerData const &certified_power_data(unsigned valence){
    static std::map<unsigned,CertifiedPowerData> cache;
    auto found=cache.find(valence);
    if(found==cache.end()){
        Eigenbasis basis=deterministic_eigenbasis(valence);
        Matrix inverse=interval_inverse(basis.vectors);
        found=cache.emplace(valence,CertifiedPowerData{
            std::move(basis),std::move(inverse)}).first;
    }
    return found->second;
}

inline Vector box_row_times_control(BoxSplineRow const &row,
                                    Matrix const &controls) {
    if (controls.size() != row.size()) {
        throw std::runtime_error("box-spline/control extraction shape mismatch");
    }
    Vector result(controls.front().size(), MpfrInterval(0));
    for (std::size_t basis = 0; basis < row.size(); ++basis) {
        for (std::size_t source = 0; source < result.size(); ++source) {
            result[source] = b2interval::add(
                result[source],
                b2interval::multiply(row[basis], controls[basis][source]));
        }
    }
    return result;
}

inline SixRows regular_rows(Matrix const &controls,
                            std::array<MpfrInterval, 2> const &point,
                            Jacobian const &map_to_local) {
    BoxSplineRow const value = box_spline_row(point[0], point[1], 0, 0);
    BoxSplineRow const ds = box_spline_row(point[0], point[1], 1, 0);
    BoxSplineRow const dt = box_spline_row(point[0], point[1], 0, 1);
    BoxSplineRow const dss = box_spline_row(point[0], point[1], 2, 0);
    BoxSplineRow const dst = box_spline_row(point[0], point[1], 1, 1);
    BoxSplineRow const dtt = box_spline_row(point[0], point[1], 0, 2);

    auto combine = [](BoxSplineRow const &left, MpfrInterval const &a,
                      BoxSplineRow const &right, MpfrInterval const &b) {
        BoxSplineRow result;
        for (std::size_t index = 0; index < result.size(); ++index) {
            result[index] = b2interval::add(
                b2interval::multiply(a, left[index]),
                b2interval::multiply(b, right[index]));
        }
        return result;
    };
    auto hessian = [&](std::size_t left, std::size_t right) {
        BoxSplineRow result;
        for (std::size_t index = 0; index < result.size(); ++index) {
            MpfrInterval term = b2interval::multiply(
                b2interval::multiply(map_to_local[0][left],
                                     map_to_local[0][right]), dss[index]);
            term = b2interval::add(
                term,
                b2interval::multiply(
                    b2interval::add(
                        b2interval::multiply(map_to_local[0][left],
                                             map_to_local[1][right]),
                        b2interval::multiply(map_to_local[1][left],
                                             map_to_local[0][right])),
                    dst[index]));
            term = b2interval::add(
                term,
                b2interval::multiply(
                    b2interval::multiply(map_to_local[1][left],
                                         map_to_local[1][right]), dtt[index]));
            result[index] = term;
        }
        return result;
    };

    BoxSplineRow const dx = combine(ds, map_to_local[0][0],
                                    dt, map_to_local[1][0]);
    BoxSplineRow const dy = combine(ds, map_to_local[0][1],
                                    dt, map_to_local[1][1]);
    return {{box_row_times_control(value, controls),
             box_row_times_control(dx, controls),
             box_row_times_control(dy, controls),
             box_row_times_control(hessian(0, 0), controls),
             box_row_times_control(hessian(0, 1), controls),
             box_row_times_control(hessian(1, 1), controls)}};
}

struct PrimaryDepthRows {
    unsigned depth;
    std::vector<ChildBranch> child_branches;
    SixRows rows;
};

inline std::vector<PrimaryDepthRows> primary_regular_depth_rows(
    double xi,double eta){
    std::array<MpfrInterval,2> point={{MpfrInterval::exact_double(xi),
                                      MpfrInterval::exact_double(eta)}};
    if(mpfr_sgn(point[0].lo())<0 || mpfr_sgn(point[1].lo())<0 ||
       mpfr_greater_p(b2interval::add(point[0],point[1]).hi(),
                      MpfrInterval(1).lo()))
        throw std::runtime_error("initial regular parameter outside triangle");
    Matrix controls=regular_from_local();
    Jacobian jacobian=identity_jacobian();
    std::vector<ChildBranch> branches;
    std::vector<PrimaryDepthRows> results;
    for(unsigned depth=0;depth<5;++depth){
        results.push_back({depth,branches,regular_rows(controls,point,jacobian)});
        if(depth==4)break;
        ChildMap child=select_child(point);point=apply_child(child,point);
        jacobian=multiply(child.jacobian,jacobian);branches.push_back(child.branch);
        controls=multiply(regular_child_extraction(child.branch),controls);
    }
    return results;
}

inline std::vector<PrimaryDepthRows> primary_depth_rows(
    unsigned valence, double xi, double eta) {
    std::array<MpfrInterval, 2> point = {{
        MpfrInterval::exact_double(xi), MpfrInterval::exact_double(eta)}};
    if (mpfr_sgn(point[0].lo()) < 0 || mpfr_sgn(point[1].lo()) < 0 ||
        mpfr_greater_p(b2interval::add(point[0], point[1]).hi(),
                       MpfrInterval(1).lo())) {
        throw std::runtime_error("initial parameter outside closed triangle");
    }

    CertifiedPowerData const &power=certified_power_data(valence);
    Eigenbasis const &basis=power.basis;
    Matrix const &inverse=power.inverse;
    Matrix controls = identity_matrix(valence + 6);
    Jacobian jacobian = identity_jacobian();
    bool regular = false;
    unsigned first_regular_depth = 0;
    std::vector<ChildBranch> branches;
    std::vector<PrimaryDepthRows> results;
    for (unsigned depth = 1; depth <= 30; ++depth) {
        ChildMap const child = select_child(point);
        point = apply_child(child, point);
        jacobian = multiply(child.jacobian, jacobian);
        branches.push_back(child.branch);
        if (!regular) {
            if (child.branch == ChildBranch::T0) {
                // This is intentionally formed through the certified
                // eigensystem, not direct repeated mask multiplication.
                controls = multiply(
                    multiply(basis.vectors,
                             certified_canonical_power(basis, valence, depth)),
                    inverse);
            } else {
                Matrix prior = multiply(
                    multiply(basis.vectors,
                             certified_canonical_power(
                                 basis, valence, depth - 1)),
                    inverse);
                controls = multiply(regular_extraction(valence, child.branch),
                                    prior);
                regular = true;
                first_regular_depth = depth;
                if (first_regular_depth > 12) {
                    throw std::runtime_error("NO_ISOLATION_BY_DEPTH_12");
                }
            }
        } else {
            controls = multiply(regular_child_extraction(child.branch), controls);
        }
        if (regular && depth >= first_regular_depth) {
            results.push_back({depth, branches,
                               regular_rows(controls, point, jacobian)});
            if (results.size() == 5) {
                return results;
            }
        }
    }
    throw std::runtime_error("REGULAR_SUPPORT_NOT_REACHED_BY_DEPTH_30");
}

inline bool primary_depth_intersection_self_test(unsigned valence,
                                                 double xi, double eta) {
    std::vector<PrimaryDepthRows> depths = primary_depth_rows(
        valence, xi, eta);
    if (depths.size() != 5) {
        return false;
    }
    for (std::size_t row = 0; row < 6; ++row) {
        for (std::size_t source = 0; source < valence + 6; ++source) {
            MpfrInterval intersection = depths[0].rows[row][source];
            for (std::size_t depth = 1; depth < depths.size(); ++depth) {
                try {
                    intersection = b2interval::intersect(
                        intersection, depths[depth].rows[row][source]);
                } catch (std::runtime_error const &) {
                    throw std::runtime_error(
                        std::string("empty primary depth intersection row ") +
                        std::to_string(row) + " source " +
                        std::to_string(source) + " depth " +
                        std::to_string(depths[depth].depth));
                }
            }
        }
    }
    return true;
}

}  // namespace b2stam
