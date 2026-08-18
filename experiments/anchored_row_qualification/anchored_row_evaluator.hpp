#pragma once

#include <cfenv>
#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <vector>

// The one proof-only binary64 evaluator used by both the selected
// representation executable and the Bfr/D12 workload driver.  Keeping the
// round points here prevents the D12 workload from silently drifting to a
// second implementation of the selected representation.
namespace anchoredrow {

inline double rounded_sub(double left, double right) {
    volatile double result = left - right;
    return result;
}

inline double rounded_mul(double left, double right) {
    volatile double result = left * right;
    return result;
}

inline double rounded_add(double left, double right) {
    volatile double result = left + right;
    return result;
}

inline double rounded_sqrt(double value) {
    volatile double result = std::sqrt(value);
    return result;
}

inline double evaluate(bool position, std::size_t anchor,
                       std::vector<double> const &coefficients,
                       std::vector<double> const &sources) {
    if (coefficients.empty() || coefficients.size() != sources.size() ||
        anchor >= sources.size()) {
        throw std::runtime_error("row cardinality or anchor index");
    }
    if (std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("rounding mode before row");
    }
    volatile double accumulator = 0.0;
    double const anchor_value = sources[anchor];
    for (std::size_t index = 0; index < sources.size(); ++index) {
        double const delta = rounded_sub(sources[index], anchor_value);
        double const term = rounded_mul(coefficients[index], delta);
        accumulator = rounded_add(accumulator, term);
        if (!std::isfinite(delta) || !std::isfinite(term) ||
            !std::isfinite(static_cast<double>(accumulator))) {
            throw std::runtime_error("nonfinite intermediate");
        }
    }
    double result = static_cast<double>(accumulator);
    if (position) {
        result = rounded_add(anchor_value, result);
    }
    if (std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("rounding mode after row");
    }
    if (!std::isfinite(result)) {
        throw std::runtime_error("nonfinite result");
    }
    return result;
}

}  // namespace anchoredrow
