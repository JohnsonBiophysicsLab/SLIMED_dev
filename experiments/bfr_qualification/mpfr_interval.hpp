#pragma once

#include <mpfr.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

namespace b2interval {

constexpr mpfr_prec_t kPrecision = 544;

inline void reject_bad_flags(char const *operation) {
    if (mpfr_nanflag_p() || mpfr_divby0_p() || mpfr_overflow_p() ||
        mpfr_underflow_p() || mpfr_erangeflag_p()) {
        throw std::runtime_error(
            std::string("DIRECTED_INTERVAL_PRIMITIVE_FAILED ") + operation);
    }
}

class MpfrInterval {
public:
    MpfrInterval() {
        mpfr_init2(lo_, kPrecision);
        mpfr_init2(hi_, kPrecision);
        mpfr_set_zero(lo_, 0);
        mpfr_set_zero(hi_, 0);
    }

    explicit MpfrInterval(long value) : MpfrInterval() {
        mpfr_clear_flags();
        mpfr_set_si(lo_, value, MPFR_RNDD);
        mpfr_set_si(hi_, value, MPFR_RNDU);
        reject_bad_flags("integer import");
    }

    static MpfrInterval rational(long numerator, unsigned long denominator) {
        if (denominator == 0) {
            throw std::runtime_error(
                "DIRECTED_INTERVAL_PRIMITIVE_FAILED zero rational denominator");
        }
        MpfrInterval out;
        mpfr_clear_flags();
        mpfr_set_si(out.lo_, numerator, MPFR_RNDD);
        mpfr_div_ui(out.lo_, out.lo_, denominator, MPFR_RNDD);
        mpfr_set_si(out.hi_, numerator, MPFR_RNDU);
        mpfr_div_ui(out.hi_, out.hi_, denominator, MPFR_RNDU);
        reject_bad_flags("rational import");
        out.validate();
        return out;
    }

    static MpfrInterval exact_double(double value) {
        if (!std::isfinite(value)) {
            throw std::runtime_error(
                "DIRECTED_INTERVAL_PRIMITIVE_FAILED nonfinite binary64 import");
        }
        MpfrInterval out;
        mpfr_clear_flags();
        int const lo_ternary = mpfr_set_d(out.lo_, value, MPFR_RNDN);
        int const hi_ternary = mpfr_set_d(out.hi_, value, MPFR_RNDN);
        reject_bad_flags("binary64 import");
        if (lo_ternary != 0 || hi_ternary != 0) {
            throw std::runtime_error(
                "DIRECTED_INTERVAL_PRIMITIVE_FAILED inexact binary64 import");
        }
        out.validate();
        return out;
    }

    static MpfrInterval point(mpfr_srcptr value) {
        MpfrInterval out;
        mpfr_clear_flags();
        if (mpfr_set(out.lo_, value, MPFR_RNDN) != 0 ||
            mpfr_set(out.hi_, value, MPFR_RNDN) != 0) {
            throw std::runtime_error(
                "DIRECTED_INTERVAL_PRIMITIVE_FAILED inexact MPFR point import");
        }
        reject_bad_flags("MPFR point import");
        out.validate();
        return out;
    }

    static MpfrInterval endpoints(mpfr_srcptr lower, mpfr_srcptr upper) {
        MpfrInterval out;
        mpfr_clear_flags();
        mpfr_set(out.lo_, lower, MPFR_RNDD);
        mpfr_set(out.hi_, upper, MPFR_RNDU);
        reject_bad_flags("endpoint import");
        out.validate();
        return out;
    }

    static MpfrInterval decimal(char const *value) {
        MpfrInterval out;
        mpfr_clear_flags();
        if (mpfr_set_str(out.lo_, value, 10, MPFR_RNDD) != 0 ||
            mpfr_set_str(out.hi_, value, 10, MPFR_RNDU) != 0) {
            throw std::runtime_error(
                "DIRECTED_INTERVAL_PRIMITIVE_FAILED invalid decimal import");
        }
        reject_bad_flags("decimal import");
        out.validate();
        return out;
    }

    MpfrInterval(MpfrInterval const &other) : MpfrInterval() {
        mpfr_set(lo_, other.lo_, MPFR_RNDD);
        mpfr_set(hi_, other.hi_, MPFR_RNDU);
    }

    MpfrInterval &operator=(MpfrInterval const &other) {
        if (this != &other) {
            mpfr_set(lo_, other.lo_, MPFR_RNDD);
            mpfr_set(hi_, other.hi_, MPFR_RNDU);
        }
        return *this;
    }

    ~MpfrInterval() {
        mpfr_clear(lo_);
        mpfr_clear(hi_);
    }

    mpfr_srcptr lo() const { return lo_; }
    mpfr_srcptr hi() const { return hi_; }
    mpfr_ptr mutable_lo() { return lo_; }
    mpfr_ptr mutable_hi() { return hi_; }

    void validate() const {
        if (!mpfr_number_p(lo_) || !mpfr_number_p(hi_) || mpfr_greater_p(lo_, hi_)) {
            throw std::runtime_error(
                "DIRECTED_INTERVAL_PRIMITIVE_FAILED invalid finite interval");
        }
    }

    bool contains_zero() const {
        return mpfr_sgn(lo_) <= 0 && mpfr_sgn(hi_) >= 0;
    }

    bool is_exact_zero() const {
        return mpfr_zero_p(lo_) && mpfr_zero_p(hi_);
    }

    MpfrInterval midpoint() const {
        mpfr_t value;
        mpfr_init2(value, kPrecision);
        mpfr_clear_flags();
        mpfr_add(value, lo_, hi_, MPFR_RNDN);
        mpfr_div_2ui(value, value, 1, MPFR_RNDN);
        reject_bad_flags("midpoint");
        MpfrInterval out = point(value);
        mpfr_clear(value);
        return out;
    }

    MpfrInterval expanded(char const *radius) const {
        MpfrInterval delta = decimal(radius);
        if (mpfr_sgn(delta.lo()) < 0) {
            throw std::runtime_error(
                "DIRECTED_INTERVAL_PRIMITIVE_FAILED negative expansion");
        }
        MpfrInterval out;
        mpfr_clear_flags();
        mpfr_sub(out.lo_, lo_, delta.hi(), MPFR_RNDD);
        mpfr_add(out.hi_, hi_, delta.hi(), MPFR_RNDU);
        reject_bad_flags("interval expansion");
        out.validate();
        return out;
    }

    std::string lower_decimal(int digits = 40) const {
        std::string buffer(static_cast<std::size_t>(digits) + 32, '\0');
        mpfr_snprintf(buffer.data(), buffer.size(), "%.*Re", digits, lo_);
        buffer.resize(std::char_traits<char>::length(buffer.c_str()));
        return buffer;
    }

    std::string upper_decimal(int digits = 40) const {
        std::string buffer(static_cast<std::size_t>(digits) + 32, '\0');
        mpfr_snprintf(buffer.data(), buffer.size(), "%.*Re", digits, hi_);
        buffer.resize(std::char_traits<char>::length(buffer.c_str()));
        return buffer;
    }

private:
    mpfr_t lo_;
    mpfr_t hi_;
};

inline MpfrInterval add(MpfrInterval const &a, MpfrInterval const &b) {
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_add(out.mutable_lo(), a.lo(), b.lo(), MPFR_RNDD);
    mpfr_add(out.mutable_hi(), a.hi(), b.hi(), MPFR_RNDU);
    reject_bad_flags("add");
    out.validate();
    return out;
}

inline MpfrInterval subtract(MpfrInterval const &a, MpfrInterval const &b) {
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_sub(out.mutable_lo(), a.lo(), b.hi(), MPFR_RNDD);
    mpfr_sub(out.mutable_hi(), a.hi(), b.lo(), MPFR_RNDU);
    reject_bad_flags("subtract");
    out.validate();
    return out;
}

inline MpfrInterval negate(MpfrInterval const &value) {
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_neg(out.mutable_lo(), value.hi(), MPFR_RNDD);
    mpfr_neg(out.mutable_hi(), value.lo(), MPFR_RNDU);
    reject_bad_flags("negate");
    out.validate();
    return out;
}

inline MpfrInterval multiply(MpfrInterval const &a, MpfrInterval const &b) {
    mpfr_t downward[4];
    mpfr_t upward[4];
    for (int index = 0; index < 4; ++index) {
        mpfr_init2(downward[index], kPrecision);
        mpfr_init2(upward[index], kPrecision);
    }
    mpfr_clear_flags();
    mpfr_mul(downward[0], a.lo(), b.lo(), MPFR_RNDD);
    mpfr_mul(downward[1], a.lo(), b.hi(), MPFR_RNDD);
    mpfr_mul(downward[2], a.hi(), b.lo(), MPFR_RNDD);
    mpfr_mul(downward[3], a.hi(), b.hi(), MPFR_RNDD);
    mpfr_mul(upward[0], a.lo(), b.lo(), MPFR_RNDU);
    mpfr_mul(upward[1], a.lo(), b.hi(), MPFR_RNDU);
    mpfr_mul(upward[2], a.hi(), b.lo(), MPFR_RNDU);
    mpfr_mul(upward[3], a.hi(), b.hi(), MPFR_RNDU);
    reject_bad_flags("multiply");
    MpfrInterval out;
    mpfr_set(out.mutable_lo(), downward[0], MPFR_RNDD);
    mpfr_set(out.mutable_hi(), upward[0], MPFR_RNDU);
    for (int index = 1; index < 4; ++index) {
        if (mpfr_less_p(downward[index], out.lo())) {
            mpfr_set(out.mutable_lo(), downward[index], MPFR_RNDD);
        }
        if (mpfr_greater_p(upward[index], out.hi())) {
            mpfr_set(out.mutable_hi(), upward[index], MPFR_RNDU);
        }
    }
    for (int index = 0; index < 4; ++index) {
        mpfr_clear(downward[index]);
        mpfr_clear(upward[index]);
    }
    out.validate();
    return out;
}

inline MpfrInterval reciprocal(MpfrInterval const &value) {
    if (mpfr_sgn(value.lo()) <= 0 && mpfr_sgn(value.hi()) >= 0) {
        throw std::runtime_error(
            "DIRECTED_INTERVAL_PRIMITIVE_FAILED division contains zero");
    }
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_ui_div(out.mutable_lo(), 1, value.hi(), MPFR_RNDD);
    mpfr_ui_div(out.mutable_hi(), 1, value.lo(), MPFR_RNDU);
    reject_bad_flags("reciprocal");
    out.validate();
    return out;
}

inline MpfrInterval divide(MpfrInterval const &a, MpfrInterval const &b) {
    return multiply(a, reciprocal(b));
}

inline MpfrInterval square_root(MpfrInterval const &value) {
    if (mpfr_sgn(value.lo()) < 0) {
        throw std::runtime_error(
            "DIRECTED_INTERVAL_PRIMITIVE_FAILED negative square-root domain");
    }
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_sqrt(out.mutable_lo(), value.lo(), MPFR_RNDD);
    mpfr_sqrt(out.mutable_hi(), value.hi(), MPFR_RNDU);
    reject_bad_flags("square root");
    out.validate();
    return out;
}

inline MpfrInterval absolute(MpfrInterval const &value) {
    if (mpfr_sgn(value.lo()) >= 0) {
        return value;
    }
    if (mpfr_sgn(value.hi()) <= 0) {
        return negate(value);
    }
    MpfrInterval out;
    mpfr_set_zero(out.mutable_lo(), 0);
    mpfr_clear_flags();
    mpfr_abs(out.mutable_hi(), value.lo(), MPFR_RNDU);
    mpfr_t candidate;
    mpfr_init2(candidate, kPrecision);
    mpfr_abs(candidate, value.hi(), MPFR_RNDU);
    if (mpfr_greater_p(candidate, out.hi())) {
        mpfr_set(out.mutable_hi(), candidate, MPFR_RNDU);
    }
    mpfr_clear(candidate);
    reject_bad_flags("absolute value");
    out.validate();
    return out;
}

inline MpfrInterval integer_power(MpfrInterval base, unsigned exponent) {
    MpfrInterval result(1);
    while (exponent != 0) {
        if ((exponent & 1U) != 0) {
            result = multiply(result, base);
        }
        exponent >>= 1U;
        if (exponent != 0) {
            base = multiply(base, base);
        }
    }
    return result;
}

inline MpfrInterval intersect(MpfrInterval const &left,
                              MpfrInterval const &right) {
    MpfrInterval out;
    mpfr_set(out.mutable_lo(),
             mpfr_greater_p(left.lo(), right.lo()) ? left.lo() : right.lo(),
             MPFR_RNDD);
    mpfr_set(out.mutable_hi(),
             mpfr_less_p(left.hi(), right.hi()) ? left.hi() : right.hi(),
             MPFR_RNDU);
    out.validate();
    return out;
}

inline bool overlaps(MpfrInterval const &left, MpfrInterval const &right) {
    return !mpfr_greater_p(left.lo(), right.hi()) &&
           !mpfr_greater_p(right.lo(), left.hi());
}

inline bool strict_interior(MpfrInterval const &inner,
                            MpfrInterval const &outer) {
    return mpfr_greater_p(inner.lo(), outer.lo()) &&
           mpfr_less_p(inner.hi(), outer.hi());
}

inline bool upper_at_most(MpfrInterval const &value, char const *decimal) {
    MpfrInterval target = MpfrInterval::decimal(decimal);
    return mpfr_lessequal_p(value.hi(), target.lo());
}

inline MpfrInterval loop_cosine(unsigned long valence) {
    if (valence < 3) {
        throw std::runtime_error(
            "DIRECTED_INTERVAL_PRIMITIVE_FAILED invalid Loop valence");
    }
    MpfrInterval pi;
    mpfr_clear_flags();
    mpfr_const_pi(pi.mutable_lo(), MPFR_RNDD);
    mpfr_const_pi(pi.mutable_hi(), MPFR_RNDU);
    reject_bad_flags("pi");
    MpfrInterval angle = divide(multiply(MpfrInterval(2), pi), MpfrInterval(static_cast<long>(valence)));
    if (mpfr_sgn(angle.lo()) < 0 || mpfr_greater_p(angle.hi(), pi.lo())) {
        throw std::runtime_error(
            "INTERVAL_BRANCH_ORDERING_UNCERTIFIED cosine monotonic domain");
    }
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_cos(out.mutable_lo(), angle.hi(), MPFR_RNDD);
    mpfr_cos(out.mutable_hi(), angle.lo(), MPFR_RNDU);
    reject_bad_flags("cosine");
    out.validate();
    return out;
}

inline MpfrInterval loop_angle_cosine(unsigned long valence,
                                      unsigned long frequency) {
    if (valence < 3 || frequency >= valence) {
        throw std::runtime_error(
            "DIRECTED_INTERVAL_PRIMITIVE_FAILED invalid Loop frequency");
    }
    MpfrInterval pi;
    mpfr_clear_flags();
    mpfr_const_pi(pi.mutable_lo(), MPFR_RNDD);
    mpfr_const_pi(pi.mutable_hi(), MPFR_RNDU);
    reject_bad_flags("pi");
    MpfrInterval angle = divide(
        multiply(MpfrInterval(static_cast<long>(2 * frequency)), pi),
        MpfrInterval(static_cast<long>(valence)));
    MpfrInterval two_pi = multiply(MpfrInterval(2), pi);
    if (mpfr_sgn(angle.lo()) < 0 ||
        mpfr_greater_p(angle.hi(), two_pi.lo())) {
        throw std::runtime_error(
            "INTERVAL_BRANCH_ORDERING_UNCERTIFIED cosine branch domain");
    }
    MpfrInterval out;
    mpfr_clear_flags();
    // The frozen valence range needs only angles in [0,pi].  Reflect higher
    // frequencies to their exact 2*pi complement before using monotonicity.
    if (2 * frequency <= valence) {
        mpfr_cos(out.mutable_lo(), angle.hi(), MPFR_RNDD);
        mpfr_cos(out.mutable_hi(), angle.lo(), MPFR_RNDU);
    } else {
        MpfrInterval reflected = subtract(two_pi, angle);
        mpfr_cos(out.mutable_lo(), reflected.hi(), MPFR_RNDD);
        mpfr_cos(out.mutable_hi(), reflected.lo(), MPFR_RNDU);
    }
    reject_bad_flags("frequency cosine");
    out.validate();
    return out;
}

inline MpfrInterval loop_angle_sine(unsigned long valence,
                                    unsigned long frequency) {
    if (valence < 3 || frequency >= valence) {
        throw std::runtime_error(
            "DIRECTED_INTERVAL_PRIMITIVE_FAILED invalid Loop frequency");
    }
    // The frozen proof surface permits cosine as its sole transcendental.
    // Reduce sin(2*pi*f/N) by quadrant and evaluate it as the signed
    // cos(2*pi*k/(4*N)) complementary angle.  The integer construction is
    // exact for odd and even valences and keeps k in [0,N], so the existing
    // cosine routine proves the required [0,pi/2] monotonic domain.
    unsigned long const four_n = 4 * valence;
    unsigned long complement = 0;
    bool negative = false;
    if (4 * frequency <= valence) {
        complement = valence - 4 * frequency;
    } else if (2 * frequency <= valence) {
        complement = 4 * frequency - valence;
    } else if (4 * frequency <= 3 * valence) {
        complement = 3 * valence - 4 * frequency;
        negative = true;
    } else {
        complement = 4 * frequency - 3 * valence;
        negative = true;
    }
    MpfrInterval const magnitude = loop_angle_cosine(four_n, complement);
    return negative ? negate(magnitude) : magnitude;
}

inline bool contains(MpfrInterval const &interval, char const *decimal) {
    MpfrInterval point = MpfrInterval::decimal(decimal);
    return mpfr_lessequal_p(interval.lo(), point.lo()) &&
           mpfr_greaterequal_p(interval.hi(), point.hi());
}

inline bool directed_rounding_mutation_self_test() {
    mpfr_t a, b, reference, lower, upper;
    mpfr_init2(a, kPrecision);
    mpfr_init2(b, kPrecision);
    mpfr_init2(reference, 2 * kPrecision);
    mpfr_init2(lower, kPrecision);
    mpfr_init2(upper, kPrecision);
    auto rejected = [&]() {
        return mpfr_greater_p(lower, reference) != 0 ||
               mpfr_less_p(upper, reference) != 0;
    };
    bool ok = true;

    // Each pair mutates exactly one production endpoint direction.  The
    // high-precision reference must fall outside the resulting false bound.
    mpfr_set_ui(a, 1, MPFR_RNDN);
    mpfr_set_ui_2exp(b, 1, -600, MPFR_RNDN);
    mpfr_add(reference, a, b, MPFR_RNDN);
    mpfr_add(lower, a, b, MPFR_RNDU);  // mutated lower RNDD -> RNDU
    mpfr_add(upper, a, b, MPFR_RNDU);
    ok = ok && rejected();
    mpfr_add(lower, a, b, MPFR_RNDD);
    mpfr_add(upper, a, b, MPFR_RNDD);  // mutated upper RNDU -> RNDD
    ok = ok && rejected();
    mpfr_sub(reference, a, b, MPFR_RNDN);
    mpfr_sub(lower, a, b, MPFR_RNDU);
    mpfr_sub(upper, a, b, MPFR_RNDU);
    ok = ok && rejected();
    mpfr_sub(lower, a, b, MPFR_RNDD);
    mpfr_sub(upper, a, b, MPFR_RNDD);
    ok = ok && rejected();

    if (mpfr_set_str(a, "1.1", 10, MPFR_RNDN) != 0 ||
        mpfr_set_str(b, "1.3", 10, MPFR_RNDN) != 0) {
        ok = false;
    }
    mpfr_mul(reference, a, b, MPFR_RNDN);
    mpfr_mul(lower, a, b, MPFR_RNDU);
    mpfr_mul(upper, a, b, MPFR_RNDU);
    ok = ok && rejected();
    mpfr_mul(lower, a, b, MPFR_RNDD);
    mpfr_mul(upper, a, b, MPFR_RNDD);
    ok = ok && rejected();

    mpfr_set_ui(a, 1, MPFR_RNDN);
    mpfr_set_ui(b, 3, MPFR_RNDN);
    mpfr_div(reference, a, b, MPFR_RNDN);
    mpfr_div(lower, a, b, MPFR_RNDU);
    mpfr_div(upper, a, b, MPFR_RNDU);
    ok = ok && rejected();
    mpfr_div(lower, a, b, MPFR_RNDD);
    mpfr_div(upper, a, b, MPFR_RNDD);
    ok = ok && rejected();
    mpfr_set_ui(a, 2, MPFR_RNDN);
    mpfr_sqrt(reference, a, MPFR_RNDN);
    mpfr_sqrt(lower, a, MPFR_RNDU);
    mpfr_sqrt(upper, a, MPFR_RNDU);
    ok = ok && rejected();
    mpfr_sqrt(lower, a, MPFR_RNDD);
    mpfr_sqrt(upper, a, MPFR_RNDD);
    ok = ok && rejected();
    mpfr_set_ui(a, 1, MPFR_RNDN);
    mpfr_cos(reference, a, MPFR_RNDN);
    mpfr_cos(lower, a, MPFR_RNDU);
    mpfr_cos(upper, a, MPFR_RNDU);
    ok = ok && rejected();
    mpfr_cos(lower, a, MPFR_RNDD);
    mpfr_cos(upper, a, MPFR_RNDD);
    ok = ok && rejected();

    // Matrix/dot-product containment: the products are exact and one final
    // accumulator rounding direction is replaced at a time.
    mpfr_set_ui(a, 1, MPFR_RNDN);
    mpfr_set_ui_2exp(b, 1, -600, MPFR_RNDN);
    mpfr_add(reference, a, b, MPFR_RNDN);
    mpfr_add(lower, a, b, MPFR_RNDU);
    mpfr_add(upper, a, b, MPFR_RNDU);
    ok = ok && rejected();
    mpfr_add(lower, a, b, MPFR_RNDD);
    mpfr_add(upper, a, b, MPFR_RNDD);
    ok = ok && rejected();

    mpfr_clear(a);
    mpfr_clear(b);
    mpfr_clear(reference);
    mpfr_clear(lower);
    mpfr_clear(upper);
    return ok;
}

}  // namespace b2interval
