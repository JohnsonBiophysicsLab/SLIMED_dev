#pragma once

#include "mpfr_interval.hpp"

#include <array>
#include <stdexcept>

namespace b2stam {

using BoxSplineRow = std::array<b2interval::MpfrInterval, 12>;

inline unsigned falling_factorial(unsigned value, unsigned order) {
    unsigned result = 1;
    for (unsigned index = 0; index < order; ++index) {
        result *= value - index;
    }
    return result;
}

inline BoxSplineRow box_spline_row(b2interval::MpfrInterval const &s,
                                   b2interval::MpfrInterval const &t,
                                   unsigned derivative_s,
                                   unsigned derivative_t) {
    if (derivative_s + derivative_t > 2) {
        throw std::runtime_error("quartic box-spline derivative order");
    }
    static unsigned const exponents[15][2] = {
        {0,0}, {1,0}, {0,1}, {2,0}, {1,1}, {0,2}, {3,0}, {2,1},
        {1,2}, {0,3}, {4,0}, {3,1}, {2,2}, {1,3}, {0,4},
    };
    // Rows are in the published Fig. 1 control order.  The polynomial
    // expansion naturally arrives in diagonal Bernstein order; the explicit
    // permutation here is therefore load-bearing for every picking matrix.
    static long const coefficients[12][15] = {
        {1,-2,-4,0,6,6,2,0,-6,-4,-1,-2,0,2,1},
        {1,-4,-2,6,6,0,-4,-6,0,2,1,2,0,-2,-1},
        {1,2,-2,0,-6,0,-4,0,6,2,2,4,0,-2,-1},
        {6,0,0,-12,-12,-12,8,12,12,8,-1,-2,0,-2,-1},
        {1,-2,2,0,-6,0,2,6,0,-4,-1,-2,0,4,2},
        {0,0,0,0,0,0,2,0,0,0,-1,-2,0,0,0},
        {1,4,2,6,6,0,-4,-6,-12,-4,-1,-2,0,4,2},
        {1,2,4,0,6,6,-4,-12,-6,-4,2,4,0,-2,-1},
        {0,0,0,0,0,0,0,0,0,2,0,0,0,-2,-1},
        {0,0,0,0,0,0,0,0,0,0,1,2,0,0,0},
        {0,0,0,0,0,0,2,6,6,2,-1,-2,0,-2,-1},
        {0,0,0,0,0,0,0,0,0,0,0,0,0,2,1},
    };
    BoxSplineRow result;
    result.fill(b2interval::MpfrInterval(0));
    for (std::size_t basis = 0; basis < result.size(); ++basis) {
        for (std::size_t monomial = 0; monomial < 15; ++monomial) {
            unsigned const s_exponent = exponents[monomial][0];
            unsigned const t_exponent = exponents[monomial][1];
            if (s_exponent < derivative_s || t_exponent < derivative_t ||
                coefficients[basis][monomial] == 0) {
                continue;
            }
            unsigned const derivative_multiplier =
                falling_factorial(s_exponent, derivative_s) *
                falling_factorial(t_exponent, derivative_t);
            b2interval::MpfrInterval term = b2interval::multiply(
                b2interval::integer_power(s, s_exponent - derivative_s),
                b2interval::integer_power(t, t_exponent - derivative_t));
            term = b2interval::multiply(
                b2interval::MpfrInterval(
                    static_cast<long>(derivative_multiplier)), term);
            term = b2interval::multiply(
                b2interval::MpfrInterval::rational(
                    coefficients[basis][monomial], 12), term);
            result[basis] = b2interval::add(result[basis], term);
        }
    }
    return result;
}

inline bool box_spline_partition_self_test() {
    b2interval::MpfrInterval const s =
        b2interval::MpfrInterval::rational(1, 3);
    b2interval::MpfrInterval const t =
        b2interval::MpfrInterval::rational(1, 3);
    unsigned const derivatives[6][2] = {
        {0,0}, {1,0}, {0,1}, {2,0}, {1,1}, {0,2},
    };
    for (auto const &derivative : derivatives) {
        BoxSplineRow row = box_spline_row(
            s, t, derivative[0], derivative[1]);
        b2interval::MpfrInterval sum(0);
        for (b2interval::MpfrInterval const &value : row) {
            sum = b2interval::add(sum, value);
        }
        b2interval::MpfrInterval residual = b2interval::subtract(
            sum, b2interval::MpfrInterval(
                derivative[0] == 0 && derivative[1] == 0 ? 1 : 0));
        if (!residual.contains_zero() ||
            !b2interval::upper_at_most(
                b2interval::absolute(residual), "1e-150")) {
            return false;
        }
    }
    return true;
}

}  // namespace b2stam
