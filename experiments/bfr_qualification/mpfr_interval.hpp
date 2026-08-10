#pragma once

#include <mpfr.h>

#include <algorithm>
#include <stdexcept>
#include <string>

namespace b2interval {

constexpr mpfr_prec_t kPrecision = 544;

inline void reject_bad_flags(char const *operation) {
    if (mpfr_nanflag_p() || mpfr_divby0_p() || mpfr_overflow_p() ||
        mpfr_underflow_p() || mpfr_erangeflag_p()) {
        throw std::runtime_error(std::string("MPFR flag failure in ") + operation);
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

    static MpfrInterval decimal(char const *value) {
        MpfrInterval out;
        mpfr_clear_flags();
        if (mpfr_set_str(out.lo_, value, 10, MPFR_RNDD) != 0 ||
            mpfr_set_str(out.hi_, value, 10, MPFR_RNDU) != 0) {
            throw std::runtime_error("invalid exact decimal interval");
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
            throw std::runtime_error("invalid finite interval");
        }
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
        throw std::runtime_error("division interval contains zero");
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
        throw std::runtime_error("square root interval has negative lower endpoint");
    }
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_sqrt(out.mutable_lo(), value.lo(), MPFR_RNDD);
    mpfr_sqrt(out.mutable_hi(), value.hi(), MPFR_RNDU);
    reject_bad_flags("square root");
    out.validate();
    return out;
}

inline MpfrInterval loop_cosine(unsigned long valence) {
    if (valence < 3) {
        throw std::runtime_error("invalid Loop valence");
    }
    MpfrInterval pi;
    mpfr_clear_flags();
    mpfr_const_pi(pi.mutable_lo(), MPFR_RNDD);
    mpfr_const_pi(pi.mutable_hi(), MPFR_RNDU);
    reject_bad_flags("pi");
    MpfrInterval angle = divide(multiply(MpfrInterval(2), pi), MpfrInterval(static_cast<long>(valence)));
    if (mpfr_sgn(angle.lo()) < 0 || mpfr_greater_p(angle.hi(), pi.lo())) {
        throw std::runtime_error("cosine monotonic domain was not certified");
    }
    MpfrInterval out;
    mpfr_clear_flags();
    mpfr_cos(out.mutable_lo(), angle.hi(), MPFR_RNDD);
    mpfr_cos(out.mutable_hi(), angle.lo(), MPFR_RNDU);
    reject_bad_flags("cosine");
    out.validate();
    return out;
}

inline bool contains(MpfrInterval const &interval, char const *decimal) {
    MpfrInterval point = MpfrInterval::decimal(decimal);
    return mpfr_lessequal_p(interval.lo(), point.lo()) &&
           mpfr_greaterequal_p(interval.hi(), point.hi());
}

}  // namespace b2interval
