// Proof-only anchored-difference evaluator.  This file has no production caller.

#pragma STDC FENV_ACCESS ON

#include <cfenv>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifdef ANCHORED_ROW_GMP_INTEGRAND
#include <gmp.h>
#endif

namespace {

class Sha256 {
public:
    Sha256() { reset(); }

    void update(void const *data, std::size_t size) {
        unsigned char const *bytes = static_cast<unsigned char const *>(data);
        total_bytes_ += static_cast<std::uint64_t>(size);
        while (size != 0) {
            std::size_t const take = std::min(size, block_.size() - used_);
            std::memcpy(block_.data() + used_, bytes, take);
            used_ += take;
            bytes += take;
            size -= take;
            if (used_ == block_.size()) {
                transform(block_.data());
                used_ = 0;
            }
        }
    }

    void update(std::string const &value) { update(value.data(), value.size()); }

    std::string finish_hex() {
        std::uint64_t const bit_count = total_bytes_ * UINT64_C(8);
        unsigned char marker = 0x80U;
        update_without_count(&marker, 1);
        unsigned char zero = 0;
        while (used_ != 56U) update_without_count(&zero, 1);
        std::array<unsigned char, 8> length{};
        for (std::size_t index = 0; index < length.size(); ++index) {
            length[7U - index] = static_cast<unsigned char>(
                bit_count >> (index * 8U));
        }
        update_without_count(length.data(), length.size());
        std::ostringstream output;
        output << std::hex << std::setfill('0');
        for (std::uint32_t word : state_) output << std::setw(8) << word;
        return output.str();
    }

private:
    static std::uint32_t rotate_right(std::uint32_t value, unsigned shift) {
        return (value >> shift) | (value << (32U - shift));
    }

    void reset() {
        state_ = {{UINT32_C(0x6a09e667), UINT32_C(0xbb67ae85),
                   UINT32_C(0x3c6ef372), UINT32_C(0xa54ff53a),
                   UINT32_C(0x510e527f), UINT32_C(0x9b05688c),
                   UINT32_C(0x1f83d9ab), UINT32_C(0x5be0cd19)}};
        block_.fill(0);
        used_ = 0;
        total_bytes_ = 0;
    }

    void update_without_count(void const *data, std::size_t size) {
        unsigned char const *bytes = static_cast<unsigned char const *>(data);
        while (size != 0) {
            std::size_t const take = std::min(size, block_.size() - used_);
            std::memcpy(block_.data() + used_, bytes, take);
            used_ += take;
            bytes += take;
            size -= take;
            if (used_ == block_.size()) {
                transform(block_.data());
                used_ = 0;
            }
        }
    }

    void transform(unsigned char const *block) {
        static std::array<std::uint32_t, 64> const constants = {{
            UINT32_C(0x428a2f98), UINT32_C(0x71374491), UINT32_C(0xb5c0fbcf), UINT32_C(0xe9b5dba5),
            UINT32_C(0x3956c25b), UINT32_C(0x59f111f1), UINT32_C(0x923f82a4), UINT32_C(0xab1c5ed5),
            UINT32_C(0xd807aa98), UINT32_C(0x12835b01), UINT32_C(0x243185be), UINT32_C(0x550c7dc3),
            UINT32_C(0x72be5d74), UINT32_C(0x80deb1fe), UINT32_C(0x9bdc06a7), UINT32_C(0xc19bf174),
            UINT32_C(0xe49b69c1), UINT32_C(0xefbe4786), UINT32_C(0x0fc19dc6), UINT32_C(0x240ca1cc),
            UINT32_C(0x2de92c6f), UINT32_C(0x4a7484aa), UINT32_C(0x5cb0a9dc), UINT32_C(0x76f988da),
            UINT32_C(0x983e5152), UINT32_C(0xa831c66d), UINT32_C(0xb00327c8), UINT32_C(0xbf597fc7),
            UINT32_C(0xc6e00bf3), UINT32_C(0xd5a79147), UINT32_C(0x06ca6351), UINT32_C(0x14292967),
            UINT32_C(0x27b70a85), UINT32_C(0x2e1b2138), UINT32_C(0x4d2c6dfc), UINT32_C(0x53380d13),
            UINT32_C(0x650a7354), UINT32_C(0x766a0abb), UINT32_C(0x81c2c92e), UINT32_C(0x92722c85),
            UINT32_C(0xa2bfe8a1), UINT32_C(0xa81a664b), UINT32_C(0xc24b8b70), UINT32_C(0xc76c51a3),
            UINT32_C(0xd192e819), UINT32_C(0xd6990624), UINT32_C(0xf40e3585), UINT32_C(0x106aa070),
            UINT32_C(0x19a4c116), UINT32_C(0x1e376c08), UINT32_C(0x2748774c), UINT32_C(0x34b0bcb5),
            UINT32_C(0x391c0cb3), UINT32_C(0x4ed8aa4a), UINT32_C(0x5b9cca4f), UINT32_C(0x682e6ff3),
            UINT32_C(0x748f82ee), UINT32_C(0x78a5636f), UINT32_C(0x84c87814), UINT32_C(0x8cc70208),
            UINT32_C(0x90befffa), UINT32_C(0xa4506ceb), UINT32_C(0xbef9a3f7), UINT32_C(0xc67178f2),
        }};
        std::array<std::uint32_t, 64> words{};
        for (std::size_t index = 0; index < 16U; ++index) {
            words[index] = (static_cast<std::uint32_t>(block[index * 4U]) << 24U) |
                (static_cast<std::uint32_t>(block[index * 4U + 1U]) << 16U) |
                (static_cast<std::uint32_t>(block[index * 4U + 2U]) << 8U) |
                static_cast<std::uint32_t>(block[index * 4U + 3U]);
        }
        for (std::size_t index = 16U; index < words.size(); ++index) {
            std::uint32_t const s0 = rotate_right(words[index - 15U], 7U) ^
                rotate_right(words[index - 15U], 18U) ^
                (words[index - 15U] >> 3U);
            std::uint32_t const s1 = rotate_right(words[index - 2U], 17U) ^
                rotate_right(words[index - 2U], 19U) ^
                (words[index - 2U] >> 10U);
            words[index] = words[index - 16U] + s0 + words[index - 7U] + s1;
        }
        std::array<std::uint32_t, 8> work = state_;
        for (std::size_t index = 0; index < words.size(); ++index) {
            std::uint32_t const upper = rotate_right(work[4], 6U) ^
                rotate_right(work[4], 11U) ^ rotate_right(work[4], 25U);
            std::uint32_t const choose = (work[4] & work[5]) ^
                ((~work[4]) & work[6]);
            std::uint32_t const temporary1 = work[7] + upper + choose +
                constants[index] + words[index];
            std::uint32_t const lower = rotate_right(work[0], 2U) ^
                rotate_right(work[0], 13U) ^ rotate_right(work[0], 22U);
            std::uint32_t const majority = (work[0] & work[1]) ^
                (work[0] & work[2]) ^ (work[1] & work[2]);
            std::uint32_t const temporary2 = lower + majority;
            work[7] = work[6]; work[6] = work[5]; work[5] = work[4];
            work[4] = work[3] + temporary1;
            work[3] = work[2]; work[2] = work[1]; work[1] = work[0];
            work[0] = temporary1 + temporary2;
        }
        for (std::size_t index = 0; index < state_.size(); ++index) {
            state_[index] += work[index];
        }
    }

    std::array<std::uint32_t, 8> state_{};
    std::array<unsigned char, 64> block_{};
    std::size_t used_ = 0;
    std::uint64_t total_bytes_ = 0;
};

class OutcomeStream {
public:
    OutcomeStream() { digest_.update("anchored-row-candidate-outcome-v1\0", 34); }

    void add(bool passed, std::string const &exact_value,
             std::string const &target, std::string const &reason) {
        unsigned char outcome = passed ? 1U : 0U;
        digest_.update(&outcome, 1);
        add_string(exact_value);
        add_string(target);
        add_string(reason);
        ++count_;
    }

    std::uint64_t count() const { return count_; }
    std::string finish_hex() { return digest_.finish_hex(); }

private:
    void add_string(std::string const &value) {
        std::array<unsigned char, 8> length{};
        std::uint64_t const size = static_cast<std::uint64_t>(value.size());
        for (std::size_t index = 0; index < length.size(); ++index) {
            length[7U - index] = static_cast<unsigned char>(
                size >> (index * 8U));
        }
        digest_.update(length.data(), length.size());
        digest_.update(value);
    }

    Sha256 digest_;
    std::uint64_t count_ = 0;
};

// Every finite binary64 value over the common denominator 2^1074 has a
// numerator below 2^2098.  Thirty-four two's-complement limbs leave ample
// headroom for the exact sums of every validated B2 row without importing a
// second arbitrary-precision implementation into the representation binary.
struct FixedInt {
    std::array<std::uint64_t, 34> limbs{};

    static FixedInt power_of_two(unsigned bit) {
        if (bit >= 34U * 64U) throw std::runtime_error("fixed integer overflow");
        FixedInt result;
        result.limbs[bit / 64U] = UINT64_C(1) << (bit % 64U);
        return result;
    }

    static FixedInt shifted(std::uint64_t value, unsigned shift) {
        FixedInt result;
        unsigned const limb = shift / 64U;
        unsigned const offset = shift % 64U;
        if (limb >= result.limbs.size()) throw std::runtime_error("fixed integer overflow");
        result.limbs[limb] = value << offset;
        if (offset && limb + 1 < result.limbs.size()) {
            result.limbs[limb + 1] = value >> (64U - offset);
        } else if (offset && value >> (64U - offset)) {
            throw std::runtime_error("fixed integer overflow");
        }
        return result;
    }

    FixedInt &operator+=(FixedInt const &right) {
        std::uint64_t carry = 0;
        for (std::size_t index = 0; index < limbs.size(); ++index) {
            std::uint64_t const left_value = limbs[index];
            std::uint64_t const first = left_value + right.limbs[index];
            std::uint64_t const first_carry = first < left_value;
            std::uint64_t const second = first + carry;
            std::uint64_t const second_carry = second < first;
            limbs[index] = second;
            carry = first_carry | second_carry;
        }
        return *this;
    }

    FixedInt operator-() const {
        FixedInt result;
        for (std::size_t index = 0; index < limbs.size(); ++index) {
            result.limbs[index] = ~limbs[index];
        }
        FixedInt one;
        one.limbs[0] = 1;
        result += one;
        return result;
    }

    FixedInt &operator-=(FixedInt const &right) {
        return *this += -right;
    }

    friend FixedInt operator-(FixedInt left, FixedInt const &right) {
        left -= right;
        return left;
    }

    friend bool operator==(FixedInt const &left, FixedInt const &right) {
        return left.limbs == right.limbs;
    }

    friend bool operator!=(FixedInt const &left, FixedInt const &right) {
        return !(left == right);
    }

    std::string twos_complement_hex() const {
        std::ostringstream output;
        output << std::hex << std::setfill('0');
        for (std::size_t index = limbs.size(); index != 0; --index) {
            output << std::setw(16) << limbs[index - 1U];
        }
        return output.str();
    }
};

// The exhaustive component audit needs products of exact coefficient and
// coordinate dyadics, and squared comparisons against the frozen normalized
// targets.  This small unsigned magnitude type is deliberately local to the
// proof executable: the representation evaluator above continues to use the
// fixed-width 34-limb form.  Only addition, subtraction, multiplication, and
// powers of two are implemented, so there is no floating or MPFR oracle hiding
// behind the audit boundary.
struct BigUnsigned {
    std::vector<std::uint64_t> limbs;

    void normalize() {
        while (!limbs.empty() && limbs.back() == 0) limbs.pop_back();
    }

    bool is_zero() const { return limbs.empty(); }

    static BigUnsigned from_uint64(std::uint64_t value) {
        BigUnsigned result;
        if (value != 0) result.limbs.push_back(value);
        return result;
    }

    static BigUnsigned power_of_two(unsigned bit) {
        BigUnsigned result;
        result.limbs.assign(static_cast<std::size_t>(bit / 64U) + 1U, 0);
        result.limbs[bit / 64U] = UINT64_C(1) << (bit % 64U);
        return result;
    }

    static BigUnsigned shifted(std::uint64_t value, unsigned shift) {
        if (value == 0) return BigUnsigned();
        BigUnsigned result;
        std::size_t const word = shift / 64U;
        unsigned const offset = shift % 64U;
        result.limbs.assign(word + (offset == 0 ? 1U : 2U), 0);
        result.limbs[word] = value << offset;
        if (offset != 0) result.limbs[word + 1U] = value >> (64U - offset);
        result.normalize();
        return result;
    }

    static BigUnsigned from_hex(std::string const &text) {
        if (text.empty()) throw std::runtime_error("empty unsigned hex integer");
        BigUnsigned result;
        for (char character : text) {
            unsigned digit = 0;
            if (character >= '0' && character <= '9') {
                digit = static_cast<unsigned>(character - '0');
            } else if (character >= 'a' && character <= 'f') {
                digit = 10U + static_cast<unsigned>(character - 'a');
            } else {
                throw std::runtime_error("unsigned hex integer syntax");
            }
            result = result.multiplied_small(16U);
            result += from_uint64(digit);
        }
        result.normalize();
        return result;
    }

    friend int compare(BigUnsigned const &left, BigUnsigned const &right) {
        if (left.limbs.size() != right.limbs.size()) {
            return left.limbs.size() < right.limbs.size() ? -1 : 1;
        }
        for (std::size_t index = left.limbs.size(); index != 0; --index) {
            std::uint64_t const a = left.limbs[index - 1U];
            std::uint64_t const b = right.limbs[index - 1U];
            if (a != b) return a < b ? -1 : 1;
        }
        return 0;
    }

    BigUnsigned &operator+=(BigUnsigned const &right) {
        std::size_t const size = std::max(limbs.size(), right.limbs.size());
        limbs.resize(size, 0);
        std::uint64_t carry = 0;
        for (std::size_t index = 0; index < size; ++index) {
            std::uint64_t const addend =
                index < right.limbs.size() ? right.limbs[index] : 0;
            std::uint64_t const original = limbs[index];
            std::uint64_t const first = original + addend;
            std::uint64_t const first_carry = first < original;
            std::uint64_t const second = first + carry;
            std::uint64_t const second_carry = second < first;
            limbs[index] = second;
            carry = first_carry | second_carry;
        }
        if (carry != 0) limbs.push_back(carry);
        return *this;
    }

    BigUnsigned &operator-=(BigUnsigned const &right) {
        if (compare(*this, right) < 0) {
            throw std::runtime_error("negative unsigned subtraction");
        }
        std::uint64_t borrow = 0;
        for (std::size_t index = 0; index < limbs.size(); ++index) {
            std::uint64_t const subtrahend =
                index < right.limbs.size() ? right.limbs[index] : 0;
            std::uint64_t const original = limbs[index];
            std::uint64_t const first = original - subtrahend;
            std::uint64_t const first_borrow = original < subtrahend;
            std::uint64_t const second = first - borrow;
            std::uint64_t const second_borrow = first < borrow;
            limbs[index] = second;
            borrow = first_borrow | second_borrow;
        }
        if (borrow != 0) throw std::runtime_error("unsigned subtraction borrow");
        normalize();
        return *this;
    }

    BigUnsigned multiplied_small(std::uint64_t right) const {
        if (right == 0 || is_zero()) return BigUnsigned();
        BigUnsigned result;
        result.limbs.assign(limbs.size() + 1U, 0);
        std::uint64_t carry = 0;
        for (std::size_t index = 0; index < limbs.size(); ++index) {
            // Split each 64-bit word into 32-bit halves so the implementation
            // remains portable under -Wpedantic without compiler extensions.
            std::uint64_t const low = limbs[index] & UINT64_C(0xffffffff);
            std::uint64_t const high = limbs[index] >> 32U;
            std::uint64_t const right_low = right & UINT64_C(0xffffffff);
            std::uint64_t const right_high = right >> 32U;
            std::uint64_t const p0 = low * right_low;
            std::uint64_t const p1 = low * right_high;
            std::uint64_t const p2 = high * right_low;
            std::uint64_t const p3 = high * right_high;
            std::uint64_t const middle = (p0 >> 32U) +
                (p1 & UINT64_C(0xffffffff)) +
                (p2 & UINT64_C(0xffffffff));
            std::uint64_t word = (p0 & UINT64_C(0xffffffff)) |
                (middle << 32U);
            std::uint64_t high_word = p3 + (p1 >> 32U) + (p2 >> 32U) +
                (middle >> 32U);
            std::uint64_t const before = word;
            word += carry;
            if (word < before) ++high_word;
            result.limbs[index] = word;
            carry = high_word;
        }
        result.limbs[limbs.size()] = carry;
        result.normalize();
        return result;
    }

    BigUnsigned shifted_left(unsigned bits) const {
        if (is_zero()) return BigUnsigned();
        std::size_t const words = bits / 64U;
        unsigned const offset = bits % 64U;
        BigUnsigned result;
        result.limbs.assign(limbs.size() + words + (offset == 0 ? 0U : 1U), 0);
        for (std::size_t index = 0; index < limbs.size(); ++index) {
            result.limbs[index + words] |= limbs[index] << offset;
            if (offset != 0) {
                result.limbs[index + words + 1U] |=
                    limbs[index] >> (64U - offset);
            }
        }
        result.normalize();
        return result;
    }

    friend BigUnsigned operator-(BigUnsigned left, BigUnsigned const &right) {
        left -= right;
        return left;
    }

    friend BigUnsigned operator*(BigUnsigned const &left,
                                 BigUnsigned const &right) {
        if (left.is_zero() || right.is_zero()) return BigUnsigned();
        BigUnsigned result;
        for (std::size_t index = 0; index < right.limbs.size(); ++index) {
            BigUnsigned partial = left.multiplied_small(right.limbs[index]);
            if (!partial.is_zero()) {
                partial.limbs.insert(partial.limbs.begin(), index, 0);
                result += partial;
            }
        }
        result.normalize();
        return result;
    }

    std::pair<long double, int> normalized_long_double() const {
        if (is_zero()) return std::make_pair(0.0L, 0);
        std::uint64_t const top = limbs.back();
        unsigned leading = 0;
        for (std::uint64_t mask = UINT64_C(1) << 63U;
             mask != 0 && (top & mask) == 0; mask >>= 1U) {
            ++leading;
        }
        unsigned const top_bits = 64U - leading;
        int const exponent = static_cast<int>((limbs.size() - 1U) * 64U +
                                               top_bits - 1U);
        long double mantissa = static_cast<long double>(top) /
            std::ldexp(1.0L, static_cast<int>(top_bits - 1U));
        if (limbs.size() >= 2U) {
            mantissa += static_cast<long double>(limbs[limbs.size() - 2U]) /
                std::ldexp(1.0L, static_cast<int>(top_bits - 1U + 64U));
        }
        return std::make_pair(mantissa, exponent);
    }

    std::string to_hex() const {
        if (is_zero()) return "0";
        std::ostringstream output;
        output << std::hex << std::nouppercase;
        output << limbs.back();
        output << std::setfill('0');
        for (std::size_t index = limbs.size() - 1U; index != 0; --index) {
            output << std::setw(16) << limbs[index - 1U];
        }
        return output.str();
    }
};

struct BigSigned {
    bool negative = false;
    BigUnsigned magnitude;

    static BigSigned from_parts(bool sign, BigUnsigned value) {
        BigSigned result;
        result.negative = sign && !value.is_zero();
        result.magnitude = std::move(value);
        return result;
    }

    BigSigned operator-() const {
        return from_parts(!negative, magnitude);
    }

    BigSigned &operator+=(BigSigned const &right) {
        if (negative == right.negative) {
            magnitude += right.magnitude;
        } else {
            int const ordering = compare(magnitude, right.magnitude);
            if (ordering >= 0) {
                magnitude -= right.magnitude;
            } else {
                BigUnsigned replacement = right.magnitude - magnitude;
                magnitude = std::move(replacement);
                negative = right.negative;
            }
        }
        if (magnitude.is_zero()) negative = false;
        return *this;
    }

    BigSigned &operator-=(BigSigned const &right) {
        return *this += -right;
    }

    friend BigSigned operator-(BigSigned left, BigSigned const &right) {
        left -= right;
        return left;
    }

    friend BigSigned operator*(BigSigned const &left, BigSigned const &right) {
        return from_parts(left.negative != right.negative,
                          left.magnitude * right.magnitude);
    }
};

BigSigned exact_binary64_big(std::uint64_t bits) {
    std::uint64_t const exponent = (bits >> 52U) & UINT64_C(0x7ff);
    std::uint64_t const fraction = bits & UINT64_C(0x000fffffffffffff);
    if (exponent == UINT64_C(0x7ff)) throw std::runtime_error("nonfinite exact dyadic");
    std::uint64_t const significand = exponent == 0
        ? fraction : (UINT64_C(0x0010000000000000) | fraction);
    BigUnsigned value = BigUnsigned::shifted(
        significand, exponent == 0 ? 0U : static_cast<unsigned>(exponent - 1U));
    return BigSigned::from_parts((bits >> 63U) != 0, std::move(value));
}

std::string canonical_binary64_label(std::uint64_t bits) {
    std::ostringstream output;
    output << std::hex << std::nouppercase << std::setfill('0')
           << std::setw(16) << bits;
    return output.str();
}

std::string signed_dyadic_json(BigSigned const &value,
                               unsigned denominator_power = 1074U) {
    if (denominator_power != 1074U && denominator_power != 2148U) {
        throw std::runtime_error("signed dyadic denominator power");
    }
    int const sign = value.magnitude.is_zero() ? 0 : (value.negative ? -1 : 1);
    std::ostringstream output;
    // RFC 8785 member order is unsigned UTF-8 lexical order.
    output << "{\"denominator_power\":" << denominator_power
           << ",\"kind\":\"signed_dyadic_v1\""
           << ",\"numerator_hex\":\"" << value.magnitude.to_hex() << "\""
           << ",\"sign\":" << sign << '}';
    return output.str();
}

std::string integer_array_json(std::vector<int> const &values) {
    std::ostringstream output;
    output << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) output << ',';
        output << values[index];
    }
    output << ']';
    return output.str();
}

std::string string_array_json(std::vector<std::string> const &values) {
    std::ostringstream output;
    output << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) output << ',';
        output << '\"' << values[index] << '\"';
    }
    output << ']';
    return output.str();
}

std::string dyadic_array_json(std::vector<BigSigned> const &values) {
    std::ostringstream output;
    output << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) output << ',';
        output << signed_dyadic_json(values[index]);
    }
    output << ']';
    return output.str();
}

constexpr char kCandidateValuesMagic[] =
    "anchored-row-candidate-values-v1";
constexpr std::uint64_t kCandidatePayloadMaximum = UINT64_C(1) << 20U;
constexpr std::uint64_t kCandidateRecordMaximum =
    (UINT64_C(1) << 63U) - UINT64_C(1);

void write_uint64_be(std::ostream &output, std::uint64_t value) {
    std::array<char, 8> bytes{};
    for (std::size_t index = 0; index < bytes.size(); ++index) {
        bytes[7U - index] = static_cast<char>(
            (value >> (index * 8U)) & UINT64_C(0xff));
    }
    output.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
}

std::uint64_t read_uint64_be_for_self_test(std::string const &bytes,
                                           std::size_t &offset) {
    if (offset > bytes.size() || bytes.size() - offset < 8U) {
        throw std::runtime_error("candidate observation truncated frame self-test");
    }
    std::uint64_t value = 0;
    for (std::size_t index = 0; index < 8U; ++index) {
        value = (value << 8U) |
            static_cast<unsigned char>(bytes[offset + index]);
    }
    offset += 8U;
    return value;
}

class CandidateValueStream {
public:
    explicit CandidateValueStream(std::ostream &output) : output_(output) {
        // sizeof includes exactly the protocol's required terminating NUL.
        output_.write(kCandidateValuesMagic,
                      static_cast<std::streamsize>(sizeof(kCandidateValuesMagic)));
        require_output();
    }

    void add(std::uint64_t expected_key_ordinal,
             std::string const &canonical_payload) {
        if (canonical_payload.empty() ||
            canonical_payload.size() > kCandidatePayloadMaximum) {
            throw std::runtime_error("candidate observation payload length");
        }
        if (record_count_ == kCandidateRecordMaximum) {
            throw std::runtime_error("candidate observation record count");
        }
        write_uint64_be(output_, expected_key_ordinal);
        write_uint64_be(output_,
                        static_cast<std::uint64_t>(canonical_payload.size()));
        output_.write(canonical_payload.data(),
                      static_cast<std::streamsize>(canonical_payload.size()));
        ++record_count_;
        require_output();
    }

    std::uint64_t record_count() const { return record_count_; }

private:
    void require_output() const {
        if (!output_) throw std::runtime_error("candidate observation output failure");
    }

    std::ostream &output_;
    std::uint64_t record_count_ = 0;
};

double from_bits(std::string const &text) {
    if (text.size() != 16) throw std::runtime_error("binary64 label length");
    std::uint64_t bits = 0;
    std::istringstream input(text);
    input >> std::hex >> bits;
    if (!input || !input.eof()) throw std::runtime_error("binary64 label syntax");
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    if (!std::isfinite(value)) throw std::runtime_error("nonfinite input");
    return value;
}

std::string to_bits(double value) {
    if (!std::isfinite(value)) throw std::runtime_error("nonfinite result");
    std::uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    std::ostringstream output;
    output << std::hex << std::setfill('0') << std::setw(16) << bits;
    return output.str();
}

std::vector<std::string> split(std::string const &value, char delimiter) {
    std::vector<std::string> result;
    std::istringstream input(value);
    std::string item;
    while (std::getline(input, item, delimiter)) result.push_back(item);
    if (result.empty() || result.back().empty()) throw std::runtime_error("empty list item");
    return result;
}

double rounded_sub(double left, double right) {
    volatile double result = left - right;
    return result;
}

double rounded_mul(double left, double right) {
    volatile double result = left * right;
    return result;
}

double rounded_add(double left, double right) {
    volatile double result = left + right;
    return result;
}

double rounded_sqrt(double value) {
    volatile double result = std::sqrt(value);
    return result;
}

double evaluate(bool position, std::size_t anchor,
                std::vector<double> const &coefficients,
                std::vector<double> const &sources) {
    if (coefficients.empty() || coefficients.size() != sources.size() ||
        anchor >= sources.size()) {
        throw std::runtime_error("row cardinality or anchor index");
    }
    if (std::fegetround() != FE_TONEAREST) throw std::runtime_error("rounding mode before row");
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
    if (position) result = rounded_add(anchor_value, result);
    if (std::fegetround() != FE_TONEAREST) throw std::runtime_error("rounding mode after row");
    if (!std::isfinite(result)) throw std::runtime_error("nonfinite result");
    return result;
}

bool is_position(std::string const &kind) {
    if (kind == "position") return true;
    if (kind == "du" || kind == "dv" || kind == "duu" ||
        kind == "duv" || kind == "dvv") return false;
    throw std::runtime_error("unknown row kind");
}

std::size_t parse_size(std::string const &text, char const *label) {
    try {
        std::size_t consumed = 0;
        std::size_t const value = std::stoull(text, &consumed, 10);
        if (consumed != text.size()) throw std::runtime_error(label);
        return value;
    } catch (std::exception const &) {
        throw std::runtime_error(label);
    }
}

std::vector<int> parse_ids(std::string const &text) {
    std::vector<int> result;
    for (std::string const &item : split(text, ',')) {
        try {
            std::size_t consumed = 0;
            long const value = std::stol(item, &consumed, 10);
            if (consumed != item.size() || value < 0 ||
                value > static_cast<long>(std::numeric_limits<int>::max())) {
                throw std::runtime_error("source id syntax");
            }
            result.push_back(static_cast<int>(value));
        } catch (std::exception const &) {
            throw std::runtime_error("source id syntax");
        }
    }
    return result;
}

std::uint64_t bits_from_label(std::string const &text) {
    if (text.size() != 16) throw std::runtime_error("binary64 label length");
    std::uint64_t bits = 0;
    std::istringstream input(text);
    input >> std::hex >> bits;
    if (!input || !input.eof()) throw std::runtime_error("binary64 label syntax");
    std::uint64_t const exponent = (bits >> 52) & UINT64_C(0x7ff);
    if (exponent == UINT64_C(0x7ff)) throw std::runtime_error("nonfinite input");
    return bits;
}

FixedInt exact_binary64_numerator(std::uint64_t bits) {
    std::uint64_t const exponent = (bits >> 52) & UINT64_C(0x7ff);
    std::uint64_t const fraction = bits & UINT64_C(0x000fffffffffffff);
    if (exponent == UINT64_C(0x7ff)) throw std::runtime_error("nonfinite exact dyadic");
    FixedInt result = FixedInt::shifted(
        exponent == 0 ? fraction : (UINT64_C(0x0010000000000000) | fraction),
        exponent == 0 ? 0U : static_cast<unsigned>(exponent - 1));
    return (bits >> 63) ? -result : result;
}

struct AuditFailure {
    bool present = false;
    std::uint64_t row = 0;
    int anchor = -1;
    int relabel = -1;
    int challenge = -1;
};

void record_failure(AuditFailure &failure, std::uint64_t row, int anchor,
                    int relabel, int challenge = -1) {
    if (!failure.present) {
        failure.present = true;
        failure.row = row;
        failure.anchor = anchor;
        failure.relabel = relabel;
        failure.challenge = challenge;
    }
}

void emit_failure(char const *name, AuditFailure const &failure) {
    std::cout << "\"" << name << "\":";
    if (!failure.present) {
        std::cout << "null";
        return;
    }
    std::cout << "{\"anchor_index\":" << failure.anchor
              << ",\"challenge_index\":" << failure.challenge
              << ",\"relabel_index\":" << failure.relabel
              << ",\"row_ordinal\":" << failure.row << '}';
}

int audit_stream() {
    if (std::fesetround(FE_TONEAREST) != 0 || std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    static std::array<std::string, 5> const challenge_labels = {{
        "c130000000000000", "bff0000000000000", "4130000000000000",
        "3ff0000000000000", "0000000000000000",
    }};
    std::array<double, 5> challenges;
    for (std::size_t index = 0; index < challenges.size(); ++index) {
        challenges[index] = from_bits(challenge_labels[index]);
    }

    std::uint64_t rows = 0;
    std::uint64_t structure_cells = 0;
    std::uint64_t constant_cells = 0;
    std::uint64_t relabel_cells = 0;
    std::uint64_t structure_failures = 0;
    std::uint64_t constant_failures = 0;
    std::uint64_t relabel_failures = 0;
    AuditFailure first_structure, first_constant, first_relabel;
    OutcomeStream structure_outcomes, constant_outcomes, relabel_outcomes;

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) throw std::runtime_error("empty audit request");
        std::vector<std::string> const fields = split(line, ' ');
        if (fields.size() != 5) throw std::runtime_error("audit request field count");
        bool const position = is_position(fields[0]);
        std::size_t const vertex_count = parse_size(fields[1], "vertex count syntax");
        std::vector<int> const anchors = parse_ids(fields[2]);
        std::vector<int> const source_ids = parse_ids(fields[3]);
        std::vector<std::string> const coefficient_labels = split(fields[4], ',');
        if (vertex_count == 0 || anchors.size() != 3 || source_ids.empty() ||
            source_ids.size() != coefficient_labels.size() ||
            !std::is_sorted(source_ids.begin(), source_ids.end()) ||
            std::adjacent_find(source_ids.begin(), source_ids.end()) != source_ids.end() ||
            source_ids.back() >= static_cast<int>(vertex_count)) {
            throw std::runtime_error("audit row cardinality or source order");
        }
        std::vector<double> coefficients;
        std::vector<FixedInt> exact_coefficients;
        coefficients.reserve(coefficient_labels.size());
        exact_coefficients.reserve(coefficient_labels.size());
        for (std::string const &label : coefficient_labels) {
            std::uint64_t const bits = bits_from_label(label);
            coefficients.push_back(from_bits(label));
            exact_coefficients.push_back(exact_binary64_numerator(bits));
        }
        FixedInt exact_sum;
        for (FixedInt const &value : exact_coefficients) exact_sum += value;
        FixedInt const target = position ? FixedInt::power_of_two(1074) : FixedInt();

        for (int anchor_index = 0; anchor_index < 3; ++anchor_index) {
            int const anchor_source = anchors[static_cast<std::size_t>(anchor_index)];
            std::vector<int>::const_iterator const anchor_iterator =
                std::lower_bound(source_ids.begin(), source_ids.end(), anchor_source);
            ++structure_cells;
            if (anchor_iterator == source_ids.end() || *anchor_iterator != anchor_source) {
                ++structure_failures;
                record_failure(first_structure, rows, anchor_index, 0);
                structure_outcomes.add(false, "anchor_absent", "exact_sum_rule",
                                       "STRUCTURE_ANCHOR_ABSENT");
                continue;
            }
            std::size_t const original_anchor = static_cast<std::size_t>(
                anchor_iterator - source_ids.begin());
            std::vector<FixedInt> expected_effective = exact_coefficients;
            expected_effective[original_anchor] += target - exact_sum;
            FixedInt effective_sum;
            for (FixedInt const &value : expected_effective) effective_sum += value;
            bool const structure_passed = effective_sum == target;
            structure_outcomes.add(
                structure_passed, effective_sum.twos_complement_hex(),
                target.twos_complement_hex(),
                structure_passed ? "" : "EXACT_SUM_RULE_FAILED");
            if (!structure_passed) {
                ++structure_failures;
                record_failure(first_structure, rows, anchor_index, 0);
            }

            for (int relabel = 0; relabel < 3; ++relabel) {
                std::vector<std::pair<int, std::size_t> > permutation;
                permutation.reserve(source_ids.size());
                for (std::size_t index = 0; index < source_ids.size(); ++index) {
                    int mapped = source_ids[index];
                    if (relabel == 1) mapped = static_cast<int>(vertex_count) - 1 - mapped;
                    if (relabel == 2) mapped = (mapped + 1) % static_cast<int>(vertex_count);
                    permutation.push_back(std::make_pair(mapped, index));
                }
                std::sort(permutation.begin(), permutation.end());
                std::vector<double> mapped_coefficients;
                std::vector<FixedInt> mapped_exact;
                std::vector<int> mapped_ids;
                for (std::pair<int, std::size_t> const &entry : permutation) {
                    mapped_ids.push_back(entry.first);
                    mapped_coefficients.push_back(coefficients[entry.second]);
                    mapped_exact.push_back(exact_coefficients[entry.second]);
                }
                int mapped_anchor = anchor_source;
                if (relabel == 1) mapped_anchor = static_cast<int>(vertex_count) - 1 - mapped_anchor;
                if (relabel == 2) mapped_anchor = (mapped_anchor + 1) % static_cast<int>(vertex_count);
                std::size_t const mapped_anchor_index = static_cast<std::size_t>(
                    std::lower_bound(mapped_ids.begin(), mapped_ids.end(), mapped_anchor) -
                    mapped_ids.begin());
                if (mapped_anchor_index >= mapped_ids.size() ||
                    mapped_ids[mapped_anchor_index] != mapped_anchor) {
                    throw std::runtime_error("mapped anchor absent");
                }

                for (int challenge = 0; challenge < 5; ++challenge) {
                    ++constant_cells;
                    std::vector<double> sources(mapped_ids.size(),
                                                challenges[static_cast<std::size_t>(challenge)]);
                    double const observed = evaluate(position, mapped_anchor_index,
                                                     mapped_coefficients, sources);
                    double const expected = position
                        ? challenges[static_cast<std::size_t>(challenge)] : 0.0;
                    bool const constant_passed =
                        to_bits(observed) == to_bits(expected);
                    constant_outcomes.add(
                        constant_passed, to_bits(observed), to_bits(expected),
                        constant_passed ? "" : "CONSTANT_BITS_MISMATCH");
                    if (!constant_passed) {
                        ++constant_failures;
                        record_failure(first_constant, rows, anchor_index,
                                       relabel, challenge);
                    }
                }

                if (relabel != 0) {
                    ++relabel_cells;
                    FixedInt mapped_sum;
                    for (FixedInt const &value : mapped_exact) mapped_sum += value;
                    mapped_exact[mapped_anchor_index] += target - mapped_sum;
                    bool identical = true;
                    for (std::size_t index = 0; index < permutation.size(); ++index) {
                        if (mapped_exact[index] !=
                            expected_effective[permutation[index].second]) {
                            identical = false;
                            break;
                        }
                    }
                    relabel_outcomes.add(
                        identical, "inverse_canonical_exact_coefficients",
                        "bitwise_equal_fixed_dyadic_numerators",
                        identical ? "" : "RELABEL_EXACT_MISMATCH");
                    if (!identical) {
                        ++relabel_failures;
                        record_failure(first_relabel, rows, anchor_index, relabel);
                    }
                }
            }
        }
        ++rows;
    }
    if (std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("rounding mode after audit");
    }
    if (structure_outcomes.count() != structure_cells ||
        constant_outcomes.count() != constant_cells ||
        relabel_outcomes.count() != relabel_cells) {
        throw std::runtime_error("preoracle outcome commitment incomplete");
    }
    std::cout << "{\"constant_cell_count\":" << constant_cells
              << ",\"constant_failure_count\":" << constant_failures << ',';
    std::cout << "\"constant_result_stream_sha256\":\""
              << constant_outcomes.finish_hex() << "\",";
    emit_failure("first_constant_failure", first_constant);
    std::cout << ',';
    emit_failure("first_relabel_exact_failure", first_relabel);
    std::cout << ',';
    emit_failure("first_structure_failure", first_structure);
    std::cout << ",\"kind\":\"anchored_row_preoracle_audit\""
              << ",\"relabel_exact_cell_count\":" << relabel_cells
              << ",\"relabel_exact_failure_count\":" << relabel_failures
              << ",\"relabel_exact_result_stream_sha256\":\""
              << relabel_outcomes.finish_hex() << "\""
              << ",\"row_count\":" << rows
              << ",\"status\":\""
              << ((structure_failures || constant_failures || relabel_failures)
                      ? "candidate_failure" : "ok")
              << "\",\"structure_cell_count\":" << structure_cells
              << ",\"structure_failure_count\":" << structure_failures
              << ",\"structure_result_stream_sha256\":\""
              << structure_outcomes.finish_hex() << "\"}\n";
    return 0;
}

std::string candidate_structure_payload(
    std::vector<int> const &source_ids,
    std::vector<std::string> const &provider_coefficient_bits,
    std::vector<BigSigned> const &effective_coefficients) {
    if (source_ids.empty() ||
        source_ids.size() != provider_coefficient_bits.size() ||
        source_ids.size() != effective_coefficients.size()) {
        throw std::runtime_error("candidate structure observation cardinality");
    }
    // Closed candidate_structure_observation_v1 in RFC 8785 member order.
    return std::string("{\"canonical_source_ids\":") +
        integer_array_json(source_ids) +
        ",\"effective_coefficients\":" +
        dyadic_array_json(effective_coefficients) +
        ",\"kind\":\"candidate_structure_observation_v1\"" +
        ",\"provider_coefficient_bits\":" +
        string_array_json(provider_coefficient_bits) + "}";
}

std::string candidate_binary64_payload(std::uint64_t observed_bits) {
    // Closed candidate_binary64_observation_v1 in RFC 8785 member order.
    return std::string("{\"kind\":\"candidate_binary64_observation_v1\"") +
        ",\"observed_bits\":\"" + canonical_binary64_label(observed_bits) +
        "\"}";
}

std::string candidate_emitted_geometry_payload(
    std::string const &axis, std::uint64_t observed_bits) {
    if (axis != "x" && axis != "y" && axis != "z") {
        throw std::runtime_error("candidate emitted geometry axis");
    }
    // Closed candidate_emitted_geometry_observation_v1 in RFC 8785 order.
    return std::string("{\"axis\":\"") + axis +
        "\",\"kind\":\"candidate_emitted_geometry_observation_v1\"" +
        ",\"observed_bits\":\"" + canonical_binary64_label(observed_bits) +
        "\"}";
}

std::string candidate_dyadic_vector_payload(
    std::vector<int> const &source_ids,
    std::vector<BigSigned> const &values) {
    if (source_ids.empty() || source_ids.size() != values.size()) {
        throw std::runtime_error("candidate dyadic observation cardinality");
    }
    // Closed candidate_dyadic_vector_observation_v1 in RFC 8785 member order.
    return std::string("{\"kind\":\"candidate_dyadic_vector_observation_v1\"") +
        ",\"source_ids\":" + integer_array_json(source_ids) +
        ",\"values\":" + dyadic_array_json(values) + "}";
}

std::string candidate_exact_geometry_payload(
    std::string const &axis, BigSigned const &observed) {
    if (axis != "x" && axis != "y" && axis != "z") {
        throw std::runtime_error("candidate exact geometry axis");
    }
    return std::string("{\"axis\":\"") + axis +
        "\",\"kind\":\"candidate_exact_geometry_observation_v1\"" +
        ",\"observed\":" + signed_dyadic_json(observed, 2148U) + "}";
}

std::string candidate_basis_payload(std::uint64_t emitted_bits) {
    return std::string("{\"emitted_basis_bits\":\"") +
        canonical_binary64_label(emitted_bits) +
        "\",\"kind\":\"candidate_basis_observation_v1\"}";
}

std::string candidate_row_signature_entries(
    std::vector<int> const &source_ids,
    std::vector<std::string> const &coefficient_bits,
    std::vector<BigSigned> const &effective) {
    if (source_ids.empty() || source_ids.size() != coefficient_bits.size() ||
        source_ids.size() != effective.size()) {
        throw std::runtime_error("candidate row signature cardinality");
    }
    std::ostringstream output;
    output << '[';
    for (std::size_t index = 0; index < source_ids.size(); ++index) {
        if (index != 0) output << ',';
        output << '[' << source_ids[index] << ",\""
               << coefficient_bits[index] << "\","
               << signed_dyadic_json(effective[index]) << ']';
    }
    output << ']';
    return output.str();
}

std::string candidate_row_signature_payload(
    std::vector<int> const &disabled_ids,
    std::vector<std::string> const &disabled_bits,
    std::vector<BigSigned> const &disabled_effective,
    std::vector<int> const &serial_ids,
    std::vector<std::string> const &serial_bits,
    std::vector<BigSigned> const &serial_effective) {
    return std::string("{\"cache_disabled_entries\":") +
        candidate_row_signature_entries(
            disabled_ids, disabled_bits, disabled_effective) +
        ",\"kind\":\"candidate_row_signature_observation_v1\"" +
        ",\"serial_cache_entries\":" + candidate_row_signature_entries(
            serial_ids, serial_bits, serial_effective) + "}";
}

enum class PreoracleObservationSelection {
    Structure,
    ConstantField,
    RelabelExact,
    RegularExactRows,
    EmittedGeometry,
};

int preoracle_observation_stream(std::istream &input, std::ostream &output,
                                 PreoracleObservationSelection selection) {
    if (std::fesetround(FE_TONEAREST) != 0 ||
        std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    // Challenge traversal follows unsigned lexical JCS key order.  This is
    // deliberately independent of the display order in the authority list.
    static std::array<std::string, 5> const challenge_labels = {{
        "c130000000000000", "bff0000000000000", "4130000000000000",
        "3ff0000000000000", "0000000000000000",
    }};
    std::array<double, 5> challenges{};
    for (std::size_t index = 0; index < challenges.size(); ++index) {
        challenges[index] = from_bits(challenge_labels[index]);
    }

    CandidateValueStream observations(output);
    std::uint64_t observation_ordinal = 0;
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty()) throw std::runtime_error("empty observation request");
        std::vector<std::string> const fields = split(line, ' ');
        if (selection == PreoracleObservationSelection::EmittedGeometry) {
            if (fields.size() != 5) {
                throw std::runtime_error(
                    "emitted geometry observation request field count");
            }
            std::string const &axis = fields[0];
            bool const position = is_position(fields[1]);
            std::size_t const anchor =
                parse_size(fields[2], "anchor index syntax");
            std::vector<double> coefficients;
            for (std::string const &label : split(fields[3], ',')) {
                coefficients.push_back(from_bits(label));
            }
            std::vector<double> sources;
            for (std::string const &label : split(fields[4], ',')) {
                sources.push_back(from_bits(label));
            }
            if ((axis != "x" && axis != "y" && axis != "z") ||
                coefficients.empty() || coefficients.size() != sources.size() ||
                anchor >= sources.size()) {
                throw std::runtime_error(
                    "emitted geometry observation request shape");
            }
            double const observed = evaluate(
                position, anchor, coefficients, sources);
            observations.add(
                observation_ordinal++,
                candidate_emitted_geometry_payload(
                    axis, bits_from_label(to_bits(observed))));
            continue;
        }
        if (fields.size() != 5) {
            throw std::runtime_error("observation request field count");
        }
        bool const position = is_position(fields[0]);
        std::size_t const vertex_count =
            parse_size(fields[1], "vertex count syntax");
        std::vector<int> const anchors = parse_ids(fields[2]);
        std::vector<int> const source_ids = parse_ids(fields[3]);
        std::vector<std::string> const input_coefficient_labels =
            split(fields[4], ',');
        if (vertex_count == 0 || anchors.size() != 3 || source_ids.empty() ||
            source_ids.size() != input_coefficient_labels.size() ||
            !std::is_sorted(source_ids.begin(), source_ids.end()) ||
            std::adjacent_find(source_ids.begin(), source_ids.end()) !=
                source_ids.end() ||
            source_ids.back() >= static_cast<int>(vertex_count)) {
            throw std::runtime_error(
                "observation row cardinality or source order");
        }

        std::vector<double> coefficients;
        std::vector<BigSigned> exact_coefficients;
        std::vector<std::string> coefficient_labels;
        coefficients.reserve(input_coefficient_labels.size());
        exact_coefficients.reserve(input_coefficient_labels.size());
        coefficient_labels.reserve(input_coefficient_labels.size());
        for (std::string const &label : input_coefficient_labels) {
            std::uint64_t const bits = bits_from_label(label);
            coefficients.push_back(from_bits(label));
            exact_coefficients.push_back(exact_binary64_big(bits));
            coefficient_labels.push_back(canonical_binary64_label(bits));
        }
        BigSigned exact_sum;
        for (BigSigned const &value : exact_coefficients) exact_sum += value;
        BigSigned const target = position
            ? BigSigned::from_parts(false, BigUnsigned::power_of_two(1074U))
            : BigSigned();

        for (int anchor_index = 0; anchor_index < 3; ++anchor_index) {
            int const anchor_source =
                anchors[static_cast<std::size_t>(anchor_index)];
            std::vector<int>::const_iterator const anchor_iterator =
                std::lower_bound(source_ids.begin(), source_ids.end(),
                                 anchor_source);
            if (anchor_iterator == source_ids.end() ||
                *anchor_iterator != anchor_source) {
                // The validated runner owns missing-anchor result semantics;
                // a candidate cannot manufacture a result or reason for it.
                throw std::runtime_error("observation anchor absent");
            }
            std::size_t const original_anchor = static_cast<std::size_t>(
                anchor_iterator - source_ids.begin());
            std::vector<BigSigned> effective = exact_coefficients;
            effective[original_anchor] += target - exact_sum;
            if (selection == PreoracleObservationSelection::Structure) {
                observations.add(
                    observation_ordinal++,
                    candidate_structure_payload(source_ids, coefficient_labels,
                                                effective));
                continue;
            }
            if (selection == PreoracleObservationSelection::RegularExactRows) {
                observations.add(
                    observation_ordinal++,
                    candidate_dyadic_vector_payload(source_ids, effective));
                continue;
            }

            for (int relabel = 0; relabel < 3; ++relabel) {
                std::vector<std::pair<int, std::size_t> > permutation;
                permutation.reserve(source_ids.size());
                for (std::size_t index = 0; index < source_ids.size(); ++index) {
                    int mapped = source_ids[index];
                    if (relabel == 1) {
                        mapped = static_cast<int>(vertex_count) - 1 - mapped;
                    }
                    if (relabel == 2) {
                        mapped = (mapped + 1) % static_cast<int>(vertex_count);
                    }
                    permutation.push_back(std::make_pair(mapped, index));
                }
                std::sort(permutation.begin(), permutation.end());
                std::vector<int> mapped_ids;
                std::vector<double> mapped_coefficients;
                std::vector<BigSigned> mapped_exact;
                for (std::pair<int, std::size_t> const &entry : permutation) {
                    mapped_ids.push_back(entry.first);
                    mapped_coefficients.push_back(coefficients[entry.second]);
                    mapped_exact.push_back(exact_coefficients[entry.second]);
                }
                int mapped_anchor = anchor_source;
                if (relabel == 1) {
                    mapped_anchor = static_cast<int>(vertex_count) - 1 -
                        mapped_anchor;
                }
                if (relabel == 2) {
                    mapped_anchor = (mapped_anchor + 1) %
                        static_cast<int>(vertex_count);
                }
                std::vector<int>::const_iterator const mapped_anchor_iterator =
                    std::lower_bound(mapped_ids.begin(), mapped_ids.end(),
                                     mapped_anchor);
                if (mapped_anchor_iterator == mapped_ids.end() ||
                    *mapped_anchor_iterator != mapped_anchor) {
                    throw std::runtime_error("observation mapped anchor absent");
                }
                std::size_t const mapped_anchor_index =
                    static_cast<std::size_t>(mapped_anchor_iterator -
                                             mapped_ids.begin());

                if (selection == PreoracleObservationSelection::ConstantField) {
                    for (std::size_t challenge = 0;
                         challenge < challenges.size(); ++challenge) {
                        std::vector<double> sources(
                            mapped_ids.size(), challenges[challenge]);
                        double const observed = evaluate(
                            position, mapped_anchor_index, mapped_coefficients,
                            sources);
                        observations.add(
                            observation_ordinal++,
                            candidate_binary64_payload(
                                bits_from_label(to_bits(observed))));
                    }
                }

                if (selection == PreoracleObservationSelection::RelabelExact &&
                    relabel != 0) {
                    BigSigned mapped_sum;
                    for (BigSigned const &value : mapped_exact) {
                        mapped_sum += value;
                    }
                    mapped_exact[mapped_anchor_index] += target - mapped_sum;
                    std::vector<BigSigned> inverse_canonical(source_ids.size());
                    for (std::size_t mapped_index = 0;
                         mapped_index < permutation.size(); ++mapped_index) {
                        inverse_canonical[permutation[mapped_index].second] =
                            mapped_exact[mapped_index];
                    }
                    observations.add(
                        observation_ordinal++,
                        candidate_dyadic_vector_payload(source_ids,
                                                        inverse_canonical));
                }
            }
        }
    }
    if (std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("rounding mode after observation stream");
    }
    if (observations.record_count() != observation_ordinal) {
        throw std::runtime_error("candidate observation stream incomplete");
    }
    return 0;
}

int cache_observation_stream() {
    CandidateValueStream observations(std::cout);
    std::uint64_t ordinal = 0;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::vector<std::string> const fields = split(line, ' ');
        if (fields.size() != 7U) {
            throw std::runtime_error("cache observation request field count");
        }
        bool const position = is_position(fields[0]);
        std::size_t const vertex_count = parse_size(
            fields[1], "cache observation vertex count");
        std::vector<int> const anchors = parse_ids(fields[2]);
        std::vector<int> const disabled_ids = parse_ids(fields[3]);
        std::vector<std::string> const disabled_bits = split(fields[4], ',');
        std::vector<int> const serial_ids = parse_ids(fields[5]);
        std::vector<std::string> const serial_bits = split(fields[6], ',');
        if (vertex_count == 0U || anchors.size() != 3U ||
            disabled_ids.empty() || serial_ids.empty() ||
            disabled_ids.size() != disabled_bits.size() ||
            serial_ids.size() != serial_bits.size() ||
            !std::is_sorted(disabled_ids.begin(), disabled_ids.end()) ||
            !std::is_sorted(serial_ids.begin(), serial_ids.end())) {
            throw std::runtime_error("cache observation request shape");
        }
        std::vector<BigSigned> disabled_exact;
        std::vector<BigSigned> serial_exact;
        for (std::string const &label : disabled_bits) {
            disabled_exact.push_back(exact_binary64_big(
                bits_from_label(label)));
        }
        for (std::string const &label : serial_bits) {
            serial_exact.push_back(exact_binary64_big(bits_from_label(label)));
        }
        BigSigned disabled_sum;
        BigSigned serial_sum;
        for (BigSigned const &value : disabled_exact) disabled_sum += value;
        for (BigSigned const &value : serial_exact) serial_sum += value;
        BigSigned const target = position ?
            BigSigned::from_parts(false, BigUnsigned::power_of_two(1074U)) :
            BigSigned();
        for (int anchor_source : anchors) {
            std::vector<int>::const_iterator const disabled_anchor =
                std::lower_bound(disabled_ids.begin(), disabled_ids.end(),
                                 anchor_source);
            std::vector<int>::const_iterator const serial_anchor =
                std::lower_bound(serial_ids.begin(), serial_ids.end(),
                                 anchor_source);
            if (disabled_anchor == disabled_ids.end() ||
                *disabled_anchor != anchor_source ||
                serial_anchor == serial_ids.end() ||
                *serial_anchor != anchor_source) {
                throw std::runtime_error("cache observation anchor absent");
            }
            std::vector<BigSigned> disabled_effective = disabled_exact;
            std::vector<BigSigned> serial_effective = serial_exact;
            disabled_effective[static_cast<std::size_t>(
                disabled_anchor - disabled_ids.begin())] +=
                    target - disabled_sum;
            serial_effective[static_cast<std::size_t>(
                serial_anchor - serial_ids.begin())] += target - serial_sum;
            observations.add(ordinal++, candidate_row_signature_payload(
                disabled_ids, disabled_bits, disabled_effective,
                serial_ids, serial_bits, serial_effective));
        }
    }
    return 0;
}

int evaluate_line(std::string const &line) {
    std::vector<std::string> fields = split(line, ' ');
    if (fields.size() != 4) throw std::runtime_error("request field count");
    std::size_t anchor = 0;
    try {
        std::size_t consumed = 0;
        anchor = std::stoul(fields[1], &consumed, 10);
        if (consumed != fields[1].size()) throw std::runtime_error("anchor syntax");
    } catch (std::exception const &) {
        throw std::runtime_error("anchor syntax");
    }
    std::vector<std::string> coefficient_labels = split(fields[2], ',');
    std::vector<std::string> source_labels = split(fields[3], ',');
    if (coefficient_labels.size() != source_labels.size()) {
        throw std::runtime_error("request list cardinality");
    }
    std::vector<double> coefficients, sources;
    for (std::string const &label : coefficient_labels) coefficients.push_back(from_bits(label));
    for (std::string const &label : source_labels) sources.push_back(from_bits(label));
    std::cout << to_bits(evaluate(is_position(fields[0]), anchor, coefficients, sources)) << '\n';
    return 0;
}

int integrand_stream() {
    if (std::fesetround(FE_TONEAREST) != 0 ||
        std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    std::string line;
    while (std::getline(std::cin, line)) {
        std::vector<std::string> const labels = split(line, ',');
        if (labels.size() != 9) throw std::runtime_error("integrand vector cardinality");
        std::array<double, 9> values;
        for (std::size_t index = 0; index < values.size(); ++index) {
            values[index] = from_bits(labels[index]);
        }
        double const cx = rounded_sub(rounded_mul(values[4], values[8]),
                                      rounded_mul(values[5], values[7]));
        double const cy = rounded_sub(rounded_mul(values[5], values[6]),
                                      rounded_mul(values[3], values[8]));
        double const cz = rounded_sub(rounded_mul(values[3], values[7]),
                                      rounded_mul(values[4], values[6]));
        double const sx = rounded_mul(cx, cx);
        double const sy = rounded_mul(cy, cy);
        double const sz = rounded_mul(cz, cz);
        double const sxy = rounded_add(sx, sy);
        double const radicand = rounded_add(sxy, sz);
        if (radicand < 0.0 || !std::isfinite(radicand)) {
            throw std::runtime_error("invalid area radicand");
        }
        double const area = rounded_sqrt(radicand);
        double const volume = rounded_mul(values[0], cx);
        if (std::fegetround() != FE_TONEAREST || !std::isfinite(area) ||
            !std::isfinite(volume)) {
            throw std::runtime_error("integrand rounding environment or result");
        }
        std::cout << to_bits(area) << ' ' << to_bits(volume) << '\n';
    }
    return 0;
}

std::array<double, 3> emitted_geometry_from_request(
    std::vector<std::string> const &fields, std::size_t offset) {
    bool const position = is_position(fields[offset]);
    std::size_t const anchor = parse_size(
        fields[offset + 1U], "integrand anchor syntax");
    std::vector<double> coefficients;
    for (std::string const &label : split(fields[offset + 2U], ',')) {
        coefficients.push_back(from_bits(label));
    }
    std::array<std::vector<double>, 3> coordinates;
    for (std::size_t axis = 0; axis < coordinates.size(); ++axis) {
        for (std::string const &label : split(fields[offset + 3U + axis], ',')) {
            coordinates[axis].push_back(from_bits(label));
        }
        if (coordinates[axis].size() != coefficients.size()) {
            throw std::runtime_error("integrand emitted request cardinality");
        }
    }
    if (coefficients.empty() || anchor >= coefficients.size()) {
        throw std::runtime_error("integrand emitted anchor");
    }
    return {{evaluate(position, anchor, coefficients, coordinates[0]),
             evaluate(position, anchor, coefficients, coordinates[1]),
             evaluate(position, anchor, coefficients, coordinates[2])}};
}

#ifdef ANCHORED_ROW_GMP_INTEGRAND
class MpzValue {
public:
    MpzValue() { mpz_init(value); }
    MpzValue(MpzValue const &other) { mpz_init_set(value, other.value); }
    MpzValue &operator=(MpzValue const &other) {
        if (this != &other) mpz_set(value, other.value);
        return *this;
    }
    ~MpzValue() { mpz_clear(value); }
    mpz_t value;
};

std::string mpz_decimal(mpz_srcptr value) {
    std::vector<char> text(mpz_sizeinbase(value, 10) + 3U, '\0');
    if (mpz_get_str(text.data(), 10, value) == nullptr) {
        throw std::runtime_error("GMP decimal serialization");
    }
    return std::string(text.data());
}

void set_mpz_exact_binary64(mpz_t output, std::string const &label) {
    BigSigned const value = exact_binary64_big(bits_from_label(label));
    if (mpz_set_str(output, value.magnitude.to_hex().c_str(), 16) != 0) {
        throw std::runtime_error("GMP exact binary64 import");
    }
    if (value.negative) mpz_neg(output, output);
}

std::string rational_json(mpz_srcptr input, unsigned denominator_power) {
    MpzValue numerator;
    mpz_set(numerator.value, input);
    if (mpz_sgn(numerator.value) == 0) denominator_power = 0;
    while (denominator_power != 0U && mpz_even_p(numerator.value) != 0) {
        mpz_tdiv_q_2exp(numerator.value, numerator.value, 1U);
        --denominator_power;
    }
    MpzValue denominator;
    mpz_set_ui(denominator.value, 1U);
    mpz_mul_2exp(denominator.value, denominator.value, denominator_power);
    return std::string("{\"denominator\":\"") +
        mpz_decimal(denominator.value) +
        "\",\"kind\":\"rational_v1\",\"numerator\":\"" +
        mpz_decimal(numerator.value) + "\"}";
}

std::string interval_json(mpz_srcptr lower, mpz_srcptr upper,
                          unsigned denominator_power) {
    if (mpz_cmp(lower, upper) > 0) {
        throw std::runtime_error("integrand interval order");
    }
    return std::string("{\"kind\":\"interval_rational_v1\",\"lower\":") +
        rational_json(lower, denominator_power) + ",\"upper\":" +
        rational_json(upper, denominator_power) + "}";
}

std::array<MpzValue, 3> exact_geometry_from_request(
    std::vector<std::string> const &fields, std::size_t offset) {
    bool const position = is_position(fields[offset]);
    std::size_t const anchor = parse_size(
        fields[offset + 1U], "integrand anchor syntax");
    std::vector<std::string> const coefficients = split(
        fields[offset + 2U], ',');
    std::array<std::vector<std::string>, 3> coordinates{{
        split(fields[offset + 3U], ','), split(fields[offset + 4U], ','),
        split(fields[offset + 5U], ',')}};
    if (coefficients.empty() || anchor >= coefficients.size() ||
        coordinates[0].size() != coefficients.size() ||
        coordinates[1].size() != coefficients.size() ||
        coordinates[2].size() != coefficients.size()) {
        throw std::runtime_error("integrand exact request cardinality");
    }
    std::vector<MpzValue> effective(coefficients.size());
    MpzValue sum;
    for (std::size_t index = 0; index < coefficients.size(); ++index) {
        set_mpz_exact_binary64(effective[index].value, coefficients[index]);
        mpz_add(sum.value, sum.value, effective[index].value);
    }
    MpzValue target;
    if (position) {
        mpz_set_ui(target.value, 1U);
        mpz_mul_2exp(target.value, target.value, 1074U);
    }
    mpz_sub(target.value, target.value, sum.value);
    mpz_add(effective[anchor].value, effective[anchor].value, target.value);
    std::array<MpzValue, 3> result;
    MpzValue coordinate;
    for (std::size_t axis = 0; axis < result.size(); ++axis) {
        for (std::size_t index = 0; index < effective.size(); ++index) {
            set_mpz_exact_binary64(
                coordinate.value, coordinates[axis][index]);
            mpz_addmul(result[axis].value, effective[index].value,
                       coordinate.value);
        }
    }
    return result;
}

std::string exact_integrand_payload(
    std::vector<std::string> const &fields, bool area) {
    std::array<MpzValue, 3> const p = exact_geometry_from_request(fields, 1U);
    std::array<MpzValue, 3> const du = exact_geometry_from_request(fields, 7U);
    std::array<MpzValue, 3> const dv = exact_geometry_from_request(fields, 13U);
    std::array<MpzValue, 3> cross;
    MpzValue product;
    mpz_mul(cross[0].value, du[1].value, dv[2].value);
    mpz_mul(product.value, du[2].value, dv[1].value);
    mpz_sub(cross[0].value, cross[0].value, product.value);
    mpz_mul(cross[1].value, du[2].value, dv[0].value);
    mpz_mul(product.value, du[0].value, dv[2].value);
    mpz_sub(cross[1].value, cross[1].value, product.value);
    mpz_mul(cross[2].value, du[0].value, dv[1].value);
    mpz_mul(product.value, du[1].value, dv[0].value);
    mpz_sub(cross[2].value, cross[2].value, product.value);
    std::string interval;
    if (area) {
        MpzValue radicand;
        for (MpzValue const &component : cross) {
            mpz_addmul(radicand.value, component.value, component.value);
        }
        MpzValue scaled;
        mpz_mul_2exp(scaled.value, radicand.value, 1088U);
        MpzValue lower;
        MpzValue remainder;
        mpz_sqrtrem(lower.value, remainder.value, scaled.value);
        MpzValue upper;
        mpz_set(upper.value, lower.value);
        if (mpz_sgn(remainder.value) != 0) mpz_add_ui(upper.value, upper.value, 1U);
        interval = interval_json(lower.value, upper.value, 4840U);
    } else {
        MpzValue volume;
        mpz_mul(volume.value, p[0].value, cross[0].value);
        interval = interval_json(volume.value, volume.value, 6444U);
    }
    return std::string("{\"kind\":") +
        "\"candidate_exact_integrand_observation_v1\",\"observed_interval\":" +
        interval + ",\"view\":\"exact_effective\"}";
}
#endif

std::string emitted_integrand_payload(
    std::vector<std::string> const &fields, bool area) {
    std::array<double, 3> const p = emitted_geometry_from_request(fields, 1U);
    std::array<double, 3> const du = emitted_geometry_from_request(fields, 7U);
    std::array<double, 3> const dv = emitted_geometry_from_request(fields, 13U);
    double const cx = rounded_sub(rounded_mul(du[1], dv[2]),
                                  rounded_mul(du[2], dv[1]));
    double const cy = rounded_sub(rounded_mul(du[2], dv[0]),
                                  rounded_mul(du[0], dv[2]));
    double const cz = rounded_sub(rounded_mul(du[0], dv[1]),
                                  rounded_mul(du[1], dv[0]));
    double observed = 0.0;
    if (area) {
        double const radicand = rounded_add(
            rounded_add(rounded_mul(cx, cx), rounded_mul(cy, cy)),
            rounded_mul(cz, cz));
        if (radicand < 0.0 || !std::isfinite(radicand)) {
            throw std::runtime_error("invalid emitted integrand radicand");
        }
        observed = rounded_sqrt(radicand);
    } else {
        observed = rounded_mul(p[0], cx);
    }
    if (std::fegetround() != FE_TONEAREST || !std::isfinite(observed)) {
        throw std::runtime_error("emitted integrand observation nonfinite");
    }
    return std::string("{\"kind\":") +
        "\"candidate_emitted_integrand_observation_v1\",\"observed_bits\":\"" +
        to_bits(observed) + "\",\"view\":\"emitted_binary64\"}";
}

int integrand_observation_stream(std::string const &criterion) {
    bool const area = criterion == "regular_analytic_area_integrand";
    if (!area && criterion != "regular_analytic_legacy_volume_integrand") {
        throw std::runtime_error("unknown integrand observation criterion");
    }
    if (std::fesetround(FE_TONEAREST) != 0 ||
        std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    CandidateValueStream observations(std::cout);
    std::uint64_t ordinal = 0;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::vector<std::string> const fields = split(line, ' ');
        if (fields.size() != 19U ||
            (fields[0] != "E" && fields[0] != "B")) {
            throw std::runtime_error("integrand observation request shape");
        }
        if (fields[0] == "E") {
#ifdef ANCHORED_ROW_GMP_INTEGRAND
            observations.add(ordinal++, exact_integrand_payload(fields, area));
#else
            throw std::runtime_error(
                "exact integrand observation support unavailable");
#endif
        } else {
            observations.add(
                ordinal++, emitted_integrand_payload(fields, area));
        }
    }
    return 0;
}

std::vector<double> values_from_labels(std::string const &field) {
    std::vector<double> result;
    for (std::string const &label : split(field, ',')) {
        result.push_back(from_bits(label));
    }
    return result;
}

int fidelity_stream() {
    if (std::fesetround(FE_TONEAREST) != 0 ||
        std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    std::string line;
    while (std::getline(std::cin, line)) {
        std::vector<std::string> const fields = split(line, ' ');
        if (fields.size() != 8) throw std::runtime_error("fidelity request arity");
        bool const position = is_position(fields[0]);
        std::size_t const vertex_count = parse_size(fields[1], "vertex count syntax");
        std::vector<int> const anchors = parse_ids(fields[2]);
        std::vector<int> const source_ids = parse_ids(fields[3]);
        std::vector<double> const coefficients = values_from_labels(fields[4]);
        std::array<std::vector<double>, 3> coordinates = {{
            values_from_labels(fields[5]), values_from_labels(fields[6]),
            values_from_labels(fields[7]),
        }};
        if (vertex_count == 0 || anchors.size() != 3 || source_ids.empty() ||
            source_ids.size() != coefficients.size() ||
            !std::is_sorted(source_ids.begin(), source_ids.end()) ||
            std::adjacent_find(source_ids.begin(), source_ids.end()) != source_ids.end() ||
            source_ids.back() >= static_cast<int>(vertex_count) ||
            std::any_of(coordinates.begin(), coordinates.end(),
                        [&](std::vector<double> const &values) {
                            return values.size() != source_ids.size();
                        })) {
            throw std::runtime_error("fidelity row cardinality or source order");
        }

        std::vector<std::string> geometry;
        for (int relabel = 0; relabel < 3; ++relabel) {
            std::vector<std::pair<int, std::size_t> > permutation;
            for (std::size_t index = 0; index < source_ids.size(); ++index) {
                int mapped = source_ids[index];
                if (relabel == 1) mapped = static_cast<int>(vertex_count) - 1 - mapped;
                if (relabel == 2) mapped = (mapped + 1) % static_cast<int>(vertex_count);
                permutation.push_back(std::make_pair(mapped, index));
            }
            std::sort(permutation.begin(), permutation.end());
            std::vector<int> mapped_ids;
            std::vector<double> mapped_coefficients;
            std::array<std::vector<double>, 3> mapped_coordinates;
            for (std::pair<int, std::size_t> const &entry : permutation) {
                mapped_ids.push_back(entry.first);
                mapped_coefficients.push_back(coefficients[entry.second]);
                for (std::size_t axis = 0; axis < 3; ++axis) {
                    mapped_coordinates[axis].push_back(
                        coordinates[axis][entry.second]);
                }
            }
            for (int anchor_index = 0; anchor_index < 3; ++anchor_index) {
                int mapped_anchor = anchors[static_cast<std::size_t>(anchor_index)];
                if (relabel == 1) {
                    mapped_anchor = static_cast<int>(vertex_count) - 1 - mapped_anchor;
                }
                if (relabel == 2) {
                    mapped_anchor = (mapped_anchor + 1) % static_cast<int>(vertex_count);
                }
                std::vector<int>::const_iterator const iterator =
                    std::lower_bound(mapped_ids.begin(), mapped_ids.end(), mapped_anchor);
                if (iterator == mapped_ids.end() || *iterator != mapped_anchor) {
                    throw std::runtime_error("fidelity mapped anchor absent");
                }
                std::size_t const mapped_anchor_index =
                    static_cast<std::size_t>(iterator - mapped_ids.begin());
                for (std::size_t axis = 0; axis < 3; ++axis) {
                    geometry.push_back(to_bits(evaluate(
                        position, mapped_anchor_index, mapped_coefficients,
                        mapped_coordinates[axis])));
                }
            }
        }

        std::vector<std::string> basis;
        for (int anchor_index = 0; anchor_index < 3; ++anchor_index) {
            std::vector<int>::const_iterator const iterator =
                std::lower_bound(source_ids.begin(), source_ids.end(),
                                 anchors[static_cast<std::size_t>(anchor_index)]);
            if (iterator == source_ids.end() ||
                *iterator != anchors[static_cast<std::size_t>(anchor_index)]) {
                throw std::runtime_error("fidelity anchor absent");
            }
            std::size_t const anchor =
                static_cast<std::size_t>(iterator - source_ids.begin());
            for (std::size_t source_index = 0;
                 source_index < source_ids.size(); ++source_index) {
                std::vector<double> source_basis(source_ids.size(), 0.0);
                source_basis[source_index] = 1.0;
                basis.push_back(to_bits(evaluate(
                    position, anchor, coefficients, source_basis)));
            }
        }
        for (std::size_t index = 0; index < geometry.size(); ++index) {
            if (index) std::cout << ',';
            std::cout << geometry[index];
        }
        std::cout << '|';
        for (std::size_t index = 0; index < basis.size(); ++index) {
            if (index) std::cout << ',';
            std::cout << basis[index];
        }
        std::cout << '\n';
    }
    return 0;
}

struct ComponentRow {
    bool position = false;
    std::vector<int> source_ids;
    std::vector<double> coefficients;
    std::vector<BigSigned> exact_coefficients;
    std::array<std::vector<double>, 3> coordinates;
    std::array<std::vector<BigSigned>, 3> exact_coordinates;
};

struct ComponentFailure {
    bool present = false;
    std::uint64_t row = 0;
    int anchor = -1;
    int relabel = -1;
    int axis = -1;
    int pair = -1;
    int basis_source = -1;
};

struct ComponentStatistic {
    std::uint64_t cells = 0;
    std::uint64_t failures = 0;
    long double maximum = 0.0L;
    bool maximum_present = false;
    BigUnsigned maximum_numerator;
    BigUnsigned maximum_scale;
    unsigned maximum_denominator_power = 0;
    bool maximum_normalized = false;
    ComponentFailure maximum_witness;
    ComponentFailure first;
    OutcomeStream outcomes;
};

static std::array<char const *, 12> const kComponentCriteria = {{
    "anchor_sensitivity_exact_coeff",
    "anchor_sensitivity_exact_geometry",
    "anchor_sensitivity_emitted_geometry",
    "binary64_basis_probe_diagnostic",
    "binary64_direct_geometry_fidelity",
    "relabel_emitted_geometry_fidelity",
    "stabilization_6_7_exact_coeff",
    "stabilization_6_7_exact_geometry",
    "stabilization_6_7_emitted_geometry",
    "stabilization_7_8_exact_coeff",
    "stabilization_7_8_exact_geometry",
    "stabilization_7_8_emitted_geometry",
}};

enum ComponentCriterion : std::size_t {
    kAnchorExactCoefficient = 0,
    kAnchorExactGeometry = 1,
    kAnchorEmittedGeometry = 2,
    kBasisDiagnostic = 3,
    kDirectGeometry = 4,
    kRelabelGeometry = 5,
    kStabilization67ExactCoefficient = 6,
    kStabilization67ExactGeometry = 7,
    kStabilization67EmittedGeometry = 8,
    kStabilization78ExactCoefficient = 9,
    kStabilization78ExactGeometry = 10,
    kStabilization78EmittedGeometry = 11,
};

BigUnsigned absolute_difference(BigSigned const &left,
                                BigSigned const &right) {
    return (left - right).magnitude;
}

BigSigned signed_power_of_two(unsigned bit) {
    return BigSigned::from_parts(false, BigUnsigned::power_of_two(bit));
}

std::vector<BigSigned> effective_coefficients(ComponentRow const &row,
                                              int anchor_source) {
    std::vector<int>::const_iterator const iterator = std::lower_bound(
        row.source_ids.begin(), row.source_ids.end(), anchor_source);
    if (iterator == row.source_ids.end() || *iterator != anchor_source) {
        throw std::runtime_error("component anchor absent from support");
    }
    std::vector<BigSigned> result = row.exact_coefficients;
    BigSigned sum;
    for (BigSigned const &value : result) sum += value;
    BigSigned const target = row.position ? signed_power_of_two(1074U) : BigSigned();
    result[static_cast<std::size_t>(iterator - row.source_ids.begin())] +=
        target - sum;
    return result;
}

std::array<BigSigned, 3> exact_geometry(
        ComponentRow const &row, std::vector<BigSigned> const &effective) {
    if (effective.size() != row.source_ids.size()) {
        throw std::runtime_error("component exact geometry support");
    }
    std::array<BigSigned, 3> result;
    for (std::size_t axis = 0; axis < 3; ++axis) {
        for (std::size_t source = 0; source < effective.size(); ++source) {
            result[axis] += effective[source] * row.exact_coordinates[axis][source];
        }
    }
    return result;
}

typedef std::array<std::array<std::array<double, 3>, 3>, 3> EmittedGeometry;

EmittedGeometry emitted_geometry(ComponentRow const &row,
                                 std::size_t vertex_count,
                                 std::array<int, 3> const &anchors,
                                 bool all_relabels) {
    EmittedGeometry result{};
    int const relabel_count = all_relabels ? 3 : 1;
    for (int relabel = 0; relabel < relabel_count; ++relabel) {
        std::vector<std::pair<int, std::size_t> > permutation;
        for (std::size_t index = 0; index < row.source_ids.size(); ++index) {
            int mapped = row.source_ids[index];
            if (relabel == 1) mapped = static_cast<int>(vertex_count) - 1 - mapped;
            if (relabel == 2) mapped = (mapped + 1) % static_cast<int>(vertex_count);
            permutation.push_back(std::make_pair(mapped, index));
        }
        std::sort(permutation.begin(), permutation.end());
        std::vector<int> mapped_ids;
        std::vector<double> mapped_coefficients;
        std::array<std::vector<double>, 3> mapped_coordinates;
        for (std::pair<int, std::size_t> const &entry : permutation) {
            mapped_ids.push_back(entry.first);
            mapped_coefficients.push_back(row.coefficients[entry.second]);
            for (std::size_t axis = 0; axis < 3; ++axis) {
                mapped_coordinates[axis].push_back(
                    row.coordinates[axis][entry.second]);
            }
        }
        for (int anchor = 0; anchor < 3; ++anchor) {
            int mapped_anchor = anchors[static_cast<std::size_t>(anchor)];
            if (relabel == 1) {
                mapped_anchor = static_cast<int>(vertex_count) - 1 - mapped_anchor;
            }
            if (relabel == 2) {
                mapped_anchor = (mapped_anchor + 1) % static_cast<int>(vertex_count);
            }
            std::vector<int>::const_iterator const iterator = std::lower_bound(
                mapped_ids.begin(), mapped_ids.end(), mapped_anchor);
            if (iterator == mapped_ids.end() || *iterator != mapped_anchor) {
                throw std::runtime_error("component mapped anchor absent");
            }
            std::size_t const anchor_index = static_cast<std::size_t>(
                iterator - mapped_ids.begin());
            for (std::size_t axis = 0; axis < 3; ++axis) {
                result[static_cast<std::size_t>(relabel)]
                      [static_cast<std::size_t>(anchor)][axis] = evaluate(
                          row.position, anchor_index, mapped_coefficients,
                          mapped_coordinates[axis]);
            }
        }
    }
    return result;
}

BigUnsigned coefficient_l1(
        ComponentRow const &left_row, std::vector<BigSigned> const &left,
        ComponentRow const &right_row, std::vector<BigSigned> const &right) {
    BigUnsigned result;
    std::size_t left_index = 0;
    std::size_t right_index = 0;
    while (left_index < left.size() || right_index < right.size()) {
        if (right_index == right.size() ||
            (left_index < left.size() &&
             left_row.source_ids[left_index] < right_row.source_ids[right_index])) {
            result += left[left_index].magnitude;
            ++left_index;
        } else if (left_index == left.size() ||
                   right_row.source_ids[right_index] <
                       left_row.source_ids[left_index]) {
            result += right[right_index].magnitude;
            ++right_index;
        } else {
            result += absolute_difference(left[left_index], right[right_index]);
            ++left_index;
            ++right_index;
        }
    }
    return result;
}

std::pair<std::vector<int>, std::vector<BigSigned> > coefficient_difference(
        ComponentRow const &left_row, std::vector<BigSigned> const &left,
        ComponentRow const &right_row, std::vector<BigSigned> const &right) {
    std::vector<int> source_ids;
    std::vector<BigSigned> values;
    std::size_t left_index = 0;
    std::size_t right_index = 0;
    while (left_index < left.size() || right_index < right.size()) {
        if (right_index == right.size() ||
            (left_index < left.size() &&
             left_row.source_ids[left_index] <
                 right_row.source_ids[right_index])) {
            source_ids.push_back(left_row.source_ids[left_index]);
            values.push_back(left[left_index]);
            ++left_index;
        } else if (left_index == left.size() ||
                   right_row.source_ids[right_index] <
                       left_row.source_ids[left_index]) {
            source_ids.push_back(right_row.source_ids[right_index]);
            values.push_back(-right[right_index]);
            ++right_index;
        } else {
            source_ids.push_back(left_row.source_ids[left_index]);
            values.push_back(left[left_index] - right[right_index]);
            ++left_index;
            ++right_index;
        }
    }
    return std::make_pair(source_ids, values);
}

std::uint64_t component_target_numerator(bool position,
                                         std::string const &row_kind) {
    if (position) return 5U;
    if (row_kind == "du" || row_kind == "dv") return 25U;
    if (row_kind == "duu" || row_kind == "duv" || row_kind == "dvv") {
        return 125U;
    }
    throw std::runtime_error("component row target");
}

bool coefficient_within_target(BigUnsigned const &difference,
                               std::uint64_t target_numerator) {
    BigUnsigned const left = difference.multiplied_small(UINT64_C(10000000));
    BigUnsigned const right = BigUnsigned::power_of_two(1074U).multiplied_small(
        target_numerator);
    return compare(left, right) <= 0;
}

bool geometry_within_target(BigUnsigned const &difference,
                            BigUnsigned const &integer_boundary) {
    return compare(difference.multiplied_small(UINT64_C(10000000)),
                   integer_boundary) <= 0;
}

long double coefficient_magnitude(BigUnsigned const &difference) {
    std::pair<long double, int> const normalized =
        difference.normalized_long_double();
    if (normalized.first == 0.0L) return 0.0L;
    return std::ldexp(normalized.first, normalized.second - 1074);
}

long double geometry_magnitude(BigUnsigned const &difference,
                               BigUnsigned const &scale_numerator,
                               int denominator_exponent) {
    if (difference.is_zero()) return 0.0L;
    std::pair<long double, int> const numerator =
        difference.normalized_long_double();
    std::pair<long double, int> const scale =
        scale_numerator.normalized_long_double();
    if (scale.first == 0.0L) throw std::runtime_error("zero component scale");
    int const half_scale_exponent = scale.second / 2;
    bool const odd_scale_exponent = (scale.second % 2) != 0;
    long double const denominator_mantissa = std::sqrt(
        scale.first * (odd_scale_exponent ? 2.0L : 1.0L));
    int const exponent = numerator.second - half_scale_exponent + 1074 -
        denominator_exponent;
    return std::ldexp(numerator.first / denominator_mantissa, exponent);
}

void observe_component(ComponentStatistic &statistic, bool passed,
                       BigUnsigned const &numerator,
                       BigUnsigned const &scale_numerator,
                       unsigned denominator_power, bool normalized,
                       long double magnitude, std::uint64_t row,
                       int anchor = -1, int relabel = -1, int axis = -1,
                       int pair = -1, int basis_source = -1,
                       std::string const &cell_detail = "") {
    ++statistic.cells;
    if (!std::isfinite(magnitude) || magnitude < 0.0L) {
        throw std::runtime_error("nonfinite component magnitude");
    }
    std::string const exact_descriptor = normalized
        ? (numerator.to_hex() + "/(sqrt(" + scale_numerator.to_hex() +
           ")*2^" + std::to_string(denominator_power - 1074U) + ")")
        : (numerator.to_hex() + "/2^" +
           std::to_string(denominator_power));
    statistic.outcomes.add(
        passed, exact_descriptor + cell_detail, "row_order_0.1xD10",
        passed ? "" : "TARGET_EXCEEDED");
    bool replace_maximum = !statistic.maximum_present;
    if (statistic.maximum_present) {
        int ordering = 0;
        if (normalized) {
            BigUnsigned const left = (numerator * numerator) *
                statistic.maximum_scale;
            BigUnsigned const right =
                (statistic.maximum_numerator *
                 statistic.maximum_numerator) * scale_numerator;
            ordering = compare(left, right);
        } else {
            ordering = compare(numerator, statistic.maximum_numerator);
        }
        replace_maximum = ordering > 0;
    }
    if (replace_maximum) {
        statistic.maximum_present = true;
        statistic.maximum = magnitude;
        statistic.maximum_numerator = numerator;
        statistic.maximum_scale = scale_numerator;
        statistic.maximum_denominator_power = denominator_power;
        statistic.maximum_normalized = normalized;
        statistic.maximum_witness.present = true;
        statistic.maximum_witness.row = row;
        statistic.maximum_witness.anchor = anchor;
        statistic.maximum_witness.relabel = relabel;
        statistic.maximum_witness.axis = axis;
        statistic.maximum_witness.pair = pair;
        statistic.maximum_witness.basis_source = basis_source;
    }
    if (passed) return;
    ++statistic.failures;
    if (!statistic.first.present) {
        statistic.first.present = true;
        statistic.first.row = row;
        statistic.first.anchor = anchor;
        statistic.first.relabel = relabel;
        statistic.first.axis = axis;
        statistic.first.pair = pair;
        statistic.first.basis_source = basis_source;
    }
}

ComponentRow parse_component_row(
        std::string const &row_kind, std::string const &id_field,
        std::string const &coefficient_field, std::vector<int> const &union_ids,
        std::array<std::vector<std::string>, 3> const &coordinate_labels) {
    ComponentRow result;
    result.position = is_position(row_kind);
    result.source_ids = parse_ids(id_field);
    std::vector<std::string> const coefficient_labels =
        split(coefficient_field, ',');
    if (result.source_ids.empty() ||
        result.source_ids.size() != coefficient_labels.size() ||
        !std::is_sorted(result.source_ids.begin(), result.source_ids.end()) ||
        std::adjacent_find(result.source_ids.begin(), result.source_ids.end()) !=
            result.source_ids.end()) {
        throw std::runtime_error("component row support");
    }
    for (std::string const &label : coefficient_labels) {
        std::uint64_t const bits = bits_from_label(label);
        result.coefficients.push_back(from_bits(label));
        result.exact_coefficients.push_back(exact_binary64_big(bits));
    }
    for (std::size_t axis = 0; axis < 3; ++axis) {
        if (coordinate_labels[axis].size() != union_ids.size()) {
            throw std::runtime_error("component coordinate union size");
        }
        for (int source_id : result.source_ids) {
            std::vector<int>::const_iterator const iterator =
                std::lower_bound(union_ids.begin(), union_ids.end(), source_id);
            if (iterator == union_ids.end() || *iterator != source_id) {
                throw std::runtime_error("component source absent from coordinate union");
            }
            std::size_t const index = static_cast<std::size_t>(
                iterator - union_ids.begin());
            std::string const &label = coordinate_labels[axis][index];
            result.coordinates[axis].push_back(from_bits(label));
            result.exact_coordinates[axis].push_back(
                exact_binary64_big(bits_from_label(label)));
        }
    }
    return result;
}

void emit_component_failure(ComponentFailure const &failure) {
    if (!failure.present) {
        std::cout << "null";
        return;
    }
    std::cout << "{\"anchor_index\":";
    if (failure.anchor < 0) std::cout << "null"; else std::cout << failure.anchor;
    std::cout << ",\"anchor_pair_index\":";
    if (failure.pair < 0) std::cout << "null"; else std::cout << failure.pair;
    std::cout << ",\"axis_index\":";
    if (failure.axis < 0) std::cout << "null"; else std::cout << failure.axis;
    std::cout << ",\"basis_source_id\":";
    if (failure.basis_source < 0) std::cout << "null";
    else std::cout << failure.basis_source;
    std::cout << ",\"relabel_index\":";
    if (failure.relabel < 0) std::cout << "null"; else std::cout << failure.relabel;
    std::cout << ",\"row_ordinal\":" << failure.row << '}';
}

int component_audit_stream() {
    if (std::fesetround(FE_TONEAREST) != 0 ||
        std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    std::array<ComponentStatistic, kComponentCriteria.size()> statistics;
    std::uint64_t row_ordinal = 0;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) throw std::runtime_error("empty component request");
        std::vector<std::string> const fields = split(line, ' ');
        if (fields.size() != 15) {
            throw std::runtime_error("component request field count");
        }
        bool const transition67 = fields[0] == "6_7";
        if (!transition67 && fields[0] != "7_8") {
            throw std::runtime_error("component transition");
        }
        std::string const &row_kind = fields[1];
        std::size_t const vertex_count = parse_size(fields[2], "component vertex count");
        std::vector<int> const parsed_anchors = parse_ids(fields[3]);
        if (parsed_anchors.size() != 3 || vertex_count == 0) {
            throw std::runtime_error("component anchor count");
        }
        std::array<int, 3> const anchors = {{
            parsed_anchors[0], parsed_anchors[1], parsed_anchors[2],
        }};
        std::vector<int> const union_ids = parse_ids(fields[8]);
        if (union_ids.empty() || !std::is_sorted(union_ids.begin(), union_ids.end()) ||
            std::adjacent_find(union_ids.begin(), union_ids.end()) != union_ids.end() ||
            union_ids.back() >= static_cast<int>(vertex_count)) {
            throw std::runtime_error("component coordinate union order");
        }
        std::array<std::vector<std::string>, 3> const coordinate_labels = {{
            split(fields[9], ','), split(fields[10], ','), split(fields[11], ','),
        }};
        ComponentRow const low = parse_component_row(
            row_kind, fields[4], fields[5], union_ids, coordinate_labels);
        ComponentRow const high = parse_component_row(
            row_kind, fields[6], fields[7], union_ids, coordinate_labels);
        BigUnsigned const scale_numerator = BigUnsigned::from_hex(fields[12]);
        BigUnsigned const boundary1074 = BigUnsigned::from_hex(fields[13]);
        BigUnsigned const boundary2148 = BigUnsigned::from_hex(fields[14]);
        if (scale_numerator.is_zero() || boundary1074.is_zero() ||
            boundary2148.is_zero()) {
            throw std::runtime_error("component exact boundary");
        }
        std::uint64_t const target_numerator = component_target_numerator(
            high.position, row_kind);

        std::array<std::vector<BigSigned>, 3> high_effective;
        std::array<std::vector<BigSigned>, 3> low_effective;
        std::array<std::array<BigSigned, 3>, 3> high_exact_geometry;
        std::array<std::array<BigSigned, 3>, 3> low_exact_geometry;
        for (int anchor = 0; anchor < 3; ++anchor) {
            high_effective[static_cast<std::size_t>(anchor)] =
                effective_coefficients(high, anchors[static_cast<std::size_t>(anchor)]);
            low_effective[static_cast<std::size_t>(anchor)] =
                effective_coefficients(low, anchors[static_cast<std::size_t>(anchor)]);
            high_exact_geometry[static_cast<std::size_t>(anchor)] = exact_geometry(
                high, high_effective[static_cast<std::size_t>(anchor)]);
            low_exact_geometry[static_cast<std::size_t>(anchor)] = exact_geometry(
                low, low_effective[static_cast<std::size_t>(anchor)]);
        }
        EmittedGeometry const high_emitted = emitted_geometry(
            high, vertex_count, anchors, true);
        EmittedGeometry const low_emitted = emitted_geometry(
            low, vertex_count, anchors, false);

        static std::array<std::array<int, 2>, 3> const pairs = {{
            {{0, 1}}, {{0, 2}}, {{1, 2}},
        }};
        for (int pair = 0; pair < 3; ++pair) {
            int const left = pairs[static_cast<std::size_t>(pair)][0];
            int const right = pairs[static_cast<std::size_t>(pair)][1];
            BigUnsigned const coefficient_difference = coefficient_l1(
                high, high_effective[static_cast<std::size_t>(left)],
                high, high_effective[static_cast<std::size_t>(right)]);
            observe_component(statistics[kAnchorExactCoefficient],
                coefficient_within_target(coefficient_difference, target_numerator),
                coefficient_difference, BigUnsigned::from_uint64(1), 1074U,
                false, coefficient_magnitude(coefficient_difference), row_ordinal,
                -1, -1, -1, pair);
        }
        // Axis precedes anchor_pair in the frozen scientific key, so each
        // per-criterion outcome stream follows axis-major canonical order.
        for (int axis = 0; axis < 3; ++axis) {
            for (int pair = 0; pair < 3; ++pair) {
                int const left = pairs[static_cast<std::size_t>(pair)][0];
                int const right = pairs[static_cast<std::size_t>(pair)][1];
                BigUnsigned const exact_difference = absolute_difference(
                    high_exact_geometry[static_cast<std::size_t>(left)]
                                       [static_cast<std::size_t>(axis)],
                    high_exact_geometry[static_cast<std::size_t>(right)]
                                       [static_cast<std::size_t>(axis)]);
                observe_component(statistics[kAnchorExactGeometry],
                    geometry_within_target(exact_difference, boundary2148),
                    exact_difference, scale_numerator, 2148U, true,
                    geometry_magnitude(exact_difference, scale_numerator, 2148),
                    row_ordinal, -1, -1, axis, pair);
                BigUnsigned const emitted_difference = absolute_difference(
                    exact_binary64_big(bits_from_label(to_bits(
                        high_emitted[0][static_cast<std::size_t>(left)]
                                       [static_cast<std::size_t>(axis)]))),
                    exact_binary64_big(bits_from_label(to_bits(
                        high_emitted[0][static_cast<std::size_t>(right)]
                                       [static_cast<std::size_t>(axis)]))));
                observe_component(statistics[kAnchorEmittedGeometry],
                    geometry_within_target(emitted_difference, boundary1074),
                    emitted_difference, scale_numerator, 1074U, true,
                    geometry_magnitude(emitted_difference, scale_numerator, 1074),
                    row_ordinal, -1, -1, axis, pair);
            }
        }

        for (int anchor = 0; anchor < 3; ++anchor) {
            std::vector<int>::const_iterator const anchor_iterator =
                std::lower_bound(high.source_ids.begin(), high.source_ids.end(),
                                 anchors[static_cast<std::size_t>(anchor)]);
            if (anchor_iterator == high.source_ids.end() ||
                *anchor_iterator != anchors[static_cast<std::size_t>(anchor)]) {
                throw std::runtime_error("component basis anchor absent");
            }
            // The frozen fidelity diagnostic is one exact L1 decision for
            // every row/anchor/relabel group.  Each source-basis contribution
            // remains an individually ledgered cell, but individually small
            // errors may not hide a failing aggregate.
            for (int relabel = 0; relabel < 3; ++relabel) {
                std::vector<std::pair<int, std::size_t> > permutation;
                for (std::size_t source = 0; source < high.source_ids.size();
                     ++source) {
                    int mapped = high.source_ids[source];
                    if (relabel == 1) {
                        mapped = static_cast<int>(vertex_count) - 1 - mapped;
                    }
                    if (relabel == 2) {
                        mapped = (mapped + 1) % static_cast<int>(vertex_count);
                    }
                    permutation.push_back(std::make_pair(mapped, source));
                }
                std::sort(permutation.begin(), permutation.end());
                std::vector<int> mapped_ids;
                std::vector<double> mapped_coefficients;
                std::vector<std::size_t> canonical_to_mapped(
                    high.source_ids.size(), 0);
                for (std::size_t mapped_index = 0;
                     mapped_index < permutation.size(); ++mapped_index) {
                    mapped_ids.push_back(permutation[mapped_index].first);
                    mapped_coefficients.push_back(
                        high.coefficients[permutation[mapped_index].second]);
                    canonical_to_mapped[permutation[mapped_index].second] =
                        mapped_index;
                }
                int mapped_anchor = anchors[static_cast<std::size_t>(anchor)];
                if (relabel == 1) {
                    mapped_anchor = static_cast<int>(vertex_count) - 1 -
                        mapped_anchor;
                }
                if (relabel == 2) {
                    mapped_anchor = (mapped_anchor + 1) %
                        static_cast<int>(vertex_count);
                }
                std::vector<int>::const_iterator const mapped_anchor_iterator =
                    std::lower_bound(mapped_ids.begin(), mapped_ids.end(),
                                     mapped_anchor);
                if (mapped_anchor_iterator == mapped_ids.end() ||
                    *mapped_anchor_iterator != mapped_anchor) {
                    throw std::runtime_error("component mapped basis anchor absent");
                }
                std::size_t const mapped_anchor_index =
                    static_cast<std::size_t>(mapped_anchor_iterator -
                                             mapped_ids.begin());
                std::vector<double> source_basis(mapped_ids.size(), 0.0);
                std::vector<BigUnsigned> differences;
                differences.reserve(high.source_ids.size());
                BigUnsigned aggregate_l1;
                for (std::size_t source = 0; source < high.source_ids.size();
                     ++source) {
                    std::size_t const mapped_source =
                        canonical_to_mapped[source];
                    source_basis[mapped_source] = 1.0;
                    double const observed = evaluate(
                        high.position, mapped_anchor_index,
                        mapped_coefficients, source_basis);
                    source_basis[mapped_source] = 0.0;
                    BigUnsigned const difference = absolute_difference(
                        exact_binary64_big(bits_from_label(to_bits(observed))),
                        high_effective[static_cast<std::size_t>(anchor)][source]);
                    aggregate_l1 += difference;
                    differences.push_back(difference);
                }
                bool const group_passed = coefficient_within_target(
                    aggregate_l1, target_numerator);
                long double const group_magnitude =
                    coefficient_magnitude(aggregate_l1);
                std::vector<std::size_t> canonical_source_order(
                    differences.size(), 0);
                for (std::size_t source = 0; source < differences.size();
                     ++source) canonical_source_order[source] = source;
                std::sort(canonical_source_order.begin(),
                          canonical_source_order.end(),
                          [&high](std::size_t left, std::size_t right) {
                              return std::to_string(high.source_ids[left]) <
                                  std::to_string(high.source_ids[right]);
                          });
                for (std::size_t source : canonical_source_order) {
                    observe_component(statistics[kBasisDiagnostic],
                        group_passed, aggregate_l1,
                        BigUnsigned::from_uint64(1), 1074U, false,
                        group_magnitude, row_ordinal, anchor,
                        relabel, -1, -1, high.source_ids[source],
                        ";basis_contribution=" + differences[source].to_hex());
                }
            }

            for (int relabel = 0; relabel < 3; ++relabel) {
                for (int axis = 0; axis < 3; ++axis) {
                    BigSigned emitted = exact_binary64_big(bits_from_label(to_bits(
                        high_emitted[static_cast<std::size_t>(relabel)]
                                    [static_cast<std::size_t>(anchor)]
                                    [static_cast<std::size_t>(axis)])));
                    emitted.magnitude = emitted.magnitude.shifted_left(1074U);
                    BigUnsigned const direct_difference = absolute_difference(
                        emitted,
                        high_exact_geometry[static_cast<std::size_t>(anchor)]
                                           [static_cast<std::size_t>(axis)]);
                    observe_component(statistics[kDirectGeometry],
                        geometry_within_target(direct_difference, boundary2148),
                        direct_difference, scale_numerator, 2148U, true,
                        geometry_magnitude(direct_difference, scale_numerator, 2148),
                        row_ordinal, anchor, relabel, axis);
                    if (relabel != 0) {
                        BigUnsigned const relabel_difference = absolute_difference(
                            exact_binary64_big(bits_from_label(to_bits(
                                high_emitted[static_cast<std::size_t>(relabel)]
                                            [static_cast<std::size_t>(anchor)]
                                            [static_cast<std::size_t>(axis)]))),
                            exact_binary64_big(bits_from_label(to_bits(
                                high_emitted[0][static_cast<std::size_t>(anchor)]
                                               [static_cast<std::size_t>(axis)]))));
                        observe_component(statistics[kRelabelGeometry],
                            geometry_within_target(relabel_difference, boundary1074),
                            relabel_difference, scale_numerator, 1074U, true,
                            geometry_magnitude(relabel_difference, scale_numerator, 1074),
                            row_ordinal, anchor, relabel, axis);
                    }
                }
            }
        }

        std::size_t const stabilization_coefficient = transition67
            ? kStabilization67ExactCoefficient
            : kStabilization78ExactCoefficient;
        std::size_t const stabilization_exact_geometry = transition67
            ? kStabilization67ExactGeometry : kStabilization78ExactGeometry;
        std::size_t const stabilization_emitted_geometry = transition67
            ? kStabilization67EmittedGeometry : kStabilization78EmittedGeometry;
        for (int anchor = 0; anchor < 3; ++anchor) {
            BigUnsigned const coefficient_difference = coefficient_l1(
                high, high_effective[static_cast<std::size_t>(anchor)],
                low, low_effective[static_cast<std::size_t>(anchor)]);
            observe_component(statistics[stabilization_coefficient],
                coefficient_within_target(coefficient_difference, target_numerator),
                coefficient_difference, BigUnsigned::from_uint64(1), 1074U,
                false,
                coefficient_magnitude(coefficient_difference), row_ordinal, anchor);
            for (int axis = 0; axis < 3; ++axis) {
                BigUnsigned const exact_difference = absolute_difference(
                    high_exact_geometry[static_cast<std::size_t>(anchor)]
                                       [static_cast<std::size_t>(axis)],
                    low_exact_geometry[static_cast<std::size_t>(anchor)]
                                      [static_cast<std::size_t>(axis)]);
                observe_component(statistics[stabilization_exact_geometry],
                    geometry_within_target(exact_difference, boundary2148),
                    exact_difference, scale_numerator, 2148U, true,
                    geometry_magnitude(exact_difference, scale_numerator, 2148),
                    row_ordinal, anchor, -1, axis);
                BigUnsigned const emitted_difference = absolute_difference(
                    exact_binary64_big(bits_from_label(to_bits(
                        high_emitted[0][static_cast<std::size_t>(anchor)]
                                       [static_cast<std::size_t>(axis)]))),
                    exact_binary64_big(bits_from_label(to_bits(
                        low_emitted[0][static_cast<std::size_t>(anchor)]
                                      [static_cast<std::size_t>(axis)]))));
                observe_component(statistics[stabilization_emitted_geometry],
                    geometry_within_target(emitted_difference, boundary1074),
                    emitted_difference, scale_numerator, 1074U, true,
                    geometry_magnitude(emitted_difference, scale_numerator, 1074),
                    row_ordinal, anchor, -1, axis);
            }
        }
        ++row_ordinal;
    }
    if (std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("rounding mode after component audit");
    }
    bool any_failure = false;
    std::cout << "{\"criteria\":{";
    for (std::size_t index = 0; index < statistics.size(); ++index) {
        if (index != 0) std::cout << ',';
        ComponentStatistic &statistic = statistics[index];
        any_failure = any_failure || statistic.failures != 0;
        if (statistic.outcomes.count() != statistic.cells ||
            (statistic.cells != 0 && !statistic.maximum_present)) {
            throw std::runtime_error("component outcome commitment incomplete");
        }
        std::cout << '"' << kComponentCriteria[index]
                  << "\":{\"candidate_result_stream_sha256\":\""
                  << statistic.outcomes.finish_hex()
                  << "\",\"cell_count\":" << statistic.cells
                  << ",\"failure_count\":"
                  << statistic.failures << ",\"first_failure\":";
        emit_component_failure(statistic.first);
        std::cout << ",\"maximum\":" << std::setprecision(17)
                  << static_cast<double>(statistic.maximum)
                  << ",\"maximum_exact\":";
        if (statistic.maximum_present) {
            std::cout << "{\"denominator_power\":"
                      << statistic.maximum_denominator_power
                      << ",\"normalized_by_sqrt_scale\":"
                      << (statistic.maximum_normalized ? "true" : "false")
                      << ",\"numerator_hex\":\""
                      << statistic.maximum_numerator.to_hex()
                      << "\",\"scale_numerator_hex\":\""
                      << statistic.maximum_scale.to_hex() << "\"}";
        } else {
            std::cout << "null";
        }
        std::cout << ",\"maximum_witness\":";
        emit_component_failure(statistic.maximum_witness);
        std::cout << '}';
    }
    std::cout << "},\"kind\":\"anchored_row_component_audit\",\"row_count\":"
              << row_ordinal << ",\"status\":\""
              << (any_failure ? "candidate_failure" : "ok") << "\"}\n";
    return 0;
}

int component_observation_stream(std::string const &criterion) {
    if (std::find(kComponentCriteria.begin(), kComponentCriteria.end(),
                  criterion) == kComponentCriteria.end()) {
        throw std::runtime_error("unknown component observation criterion");
    }
    if (std::fesetround(FE_TONEAREST) != 0 ||
        std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    CandidateValueStream observations(std::cout);
    std::uint64_t ordinal = 0;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) throw std::runtime_error("empty component request");
        std::vector<std::string> const fields = split(line, ' ');
        if (fields.size() != 15U) {
            throw std::runtime_error("component request field count");
        }
        bool const transition67 = fields[0] == "6_7";
        if (!transition67 && fields[0] != "7_8") {
            throw std::runtime_error("component transition");
        }
        std::string const &row_kind = fields[1];
        std::size_t const vertex_count = parse_size(
            fields[2], "component vertex count");
        std::vector<int> const parsed_anchors = parse_ids(fields[3]);
        if (parsed_anchors.size() != 3U || vertex_count == 0U) {
            throw std::runtime_error("component anchor count");
        }
        std::array<int, 3> const anchors = {{
            parsed_anchors[0], parsed_anchors[1], parsed_anchors[2]}};
        std::vector<int> const union_ids = parse_ids(fields[8]);
        if (union_ids.empty() ||
            !std::is_sorted(union_ids.begin(), union_ids.end()) ||
            std::adjacent_find(union_ids.begin(), union_ids.end()) !=
                union_ids.end() ||
            union_ids.back() >= static_cast<int>(vertex_count)) {
            throw std::runtime_error("component coordinate union order");
        }
        std::array<std::vector<std::string>, 3> const coordinate_labels = {{
            split(fields[9], ','), split(fields[10], ','),
            split(fields[11], ',')}};
        ComponentRow const low = parse_component_row(
            row_kind, fields[4], fields[5], union_ids, coordinate_labels);
        ComponentRow const high = parse_component_row(
            row_kind, fields[6], fields[7], union_ids, coordinate_labels);
        std::array<std::vector<BigSigned>, 3> high_effective;
        std::array<std::vector<BigSigned>, 3> low_effective;
        std::array<std::array<BigSigned, 3>, 3> high_exact_geometry;
        std::array<std::array<BigSigned, 3>, 3> low_exact_geometry;
        for (int anchor = 0; anchor < 3; ++anchor) {
            high_effective[static_cast<std::size_t>(anchor)] =
                effective_coefficients(
                    high, anchors[static_cast<std::size_t>(anchor)]);
            low_effective[static_cast<std::size_t>(anchor)] =
                effective_coefficients(
                    low, anchors[static_cast<std::size_t>(anchor)]);
            high_exact_geometry[static_cast<std::size_t>(anchor)] =
                exact_geometry(
                    high, high_effective[static_cast<std::size_t>(anchor)]);
            low_exact_geometry[static_cast<std::size_t>(anchor)] =
                exact_geometry(
                    low, low_effective[static_cast<std::size_t>(anchor)]);
        }
        EmittedGeometry const high_emitted = emitted_geometry(
            high, vertex_count, anchors, true);
        EmittedGeometry const low_emitted = emitted_geometry(
            low, vertex_count, anchors, false);
        static std::array<std::array<int, 2>, 3> const pairs = {{
            {{0, 1}}, {{0, 2}}, {{1, 2}}}};
        static std::array<std::string, 3> const axes = {{"x", "y", "z"}};

        if (criterion == "anchor_sensitivity_exact_coeff") {
            for (std::array<int, 2> const &pair : pairs) {
                std::pair<std::vector<int>, std::vector<BigSigned> > diff =
                    coefficient_difference(
                        high, high_effective[static_cast<std::size_t>(pair[0])],
                        high, high_effective[static_cast<std::size_t>(pair[1])]);
                observations.add(ordinal++, candidate_dyadic_vector_payload(
                    diff.first, diff.second));
            }
        } else if (criterion == "anchor_sensitivity_exact_geometry" ||
                   criterion == "anchor_sensitivity_emitted_geometry") {
            for (std::size_t axis = 0; axis < axes.size(); ++axis) {
                for (std::array<int, 2> const &pair : pairs) {
                    if (criterion == "anchor_sensitivity_exact_geometry") {
                        observations.add(ordinal++,
                            candidate_exact_geometry_payload(
                                axes[axis],
                                high_exact_geometry[
                                    static_cast<std::size_t>(pair[0])][axis] -
                                high_exact_geometry[
                                    static_cast<std::size_t>(pair[1])][axis]));
                    } else {
                        double const difference = rounded_sub(
                            high_emitted[0][static_cast<std::size_t>(pair[0])]
                                             [axis],
                            high_emitted[0][static_cast<std::size_t>(pair[1])]
                                             [axis]);
                        observations.add(ordinal++,
                            candidate_emitted_geometry_payload(
                                axes[axis], bits_from_label(
                                    to_bits(difference))));
                    }
                }
            }
        } else if (criterion == "binary64_basis_probe_diagnostic") {
            for (int anchor = 0; anchor < 3; ++anchor) {
                for (int relabel = 0; relabel < 3; ++relabel) {
                    std::vector<std::pair<int, std::size_t> > permutation;
                    for (std::size_t source = 0;
                         source < high.source_ids.size(); ++source) {
                        int mapped = high.source_ids[source];
                        if (relabel == 1) {
                            mapped = static_cast<int>(vertex_count) - 1 - mapped;
                        }
                        if (relabel == 2) {
                            mapped = (mapped + 1) %
                                static_cast<int>(vertex_count);
                        }
                        permutation.push_back(std::make_pair(mapped, source));
                    }
                    std::sort(permutation.begin(), permutation.end());
                    std::vector<int> mapped_ids;
                    std::vector<double> mapped_coefficients;
                    std::vector<std::size_t> canonical_to_mapped(
                        high.source_ids.size(), 0U);
                    for (std::size_t mapped_index = 0;
                         mapped_index < permutation.size(); ++mapped_index) {
                        mapped_ids.push_back(permutation[mapped_index].first);
                        mapped_coefficients.push_back(
                            high.coefficients[permutation[mapped_index].second]);
                        canonical_to_mapped[permutation[mapped_index].second] =
                            mapped_index;
                    }
                    int mapped_anchor = anchors[static_cast<std::size_t>(anchor)];
                    if (relabel == 1) {
                        mapped_anchor = static_cast<int>(vertex_count) - 1 -
                            mapped_anchor;
                    }
                    if (relabel == 2) {
                        mapped_anchor = (mapped_anchor + 1) %
                            static_cast<int>(vertex_count);
                    }
                    std::vector<int>::const_iterator const anchor_iterator =
                        std::lower_bound(mapped_ids.begin(), mapped_ids.end(),
                                         mapped_anchor);
                    if (anchor_iterator == mapped_ids.end() ||
                        *anchor_iterator != mapped_anchor) {
                        throw std::runtime_error(
                            "component mapped basis anchor absent");
                    }
                    std::size_t const mapped_anchor_index =
                        static_cast<std::size_t>(anchor_iterator -
                                                 mapped_ids.begin());
                    std::vector<std::size_t> source_order(
                        high.source_ids.size());
                    for (std::size_t source = 0;
                         source < source_order.size(); ++source) {
                        source_order[source] = source;
                    }
                    std::sort(source_order.begin(), source_order.end(),
                        [&high](std::size_t left, std::size_t right) {
                            return std::to_string(high.source_ids[left]) <
                                std::to_string(high.source_ids[right]);
                        });
                    std::vector<double> source_basis(mapped_ids.size(), 0.0);
                    for (std::size_t source : source_order) {
                        std::size_t const mapped_source =
                            canonical_to_mapped[source];
                        source_basis[mapped_source] = 1.0;
                        double const emitted = evaluate(
                            high.position, mapped_anchor_index,
                            mapped_coefficients, source_basis);
                        source_basis[mapped_source] = 0.0;
                        observations.add(ordinal++, candidate_basis_payload(
                            bits_from_label(to_bits(emitted))));
                    }
                }
            }
        } else if (criterion == "binary64_direct_geometry_fidelity" ||
                   criterion == "relabel_emitted_geometry_fidelity") {
            for (int anchor = 0; anchor < 3; ++anchor) {
                int const relabel_start = criterion ==
                    "binary64_direct_geometry_fidelity" ? 0 : 1;
                for (int relabel = relabel_start; relabel < 3; ++relabel) {
                    for (std::size_t axis = 0; axis < axes.size(); ++axis) {
                        double observed = high_emitted[
                            static_cast<std::size_t>(relabel)]
                            [static_cast<std::size_t>(anchor)][axis];
                        if (criterion ==
                                "relabel_emitted_geometry_fidelity") {
                            observed = rounded_sub(
                                observed,
                                high_emitted[0][static_cast<std::size_t>(anchor)]
                                                 [axis]);
                        }
                        observations.add(ordinal++,
                            candidate_emitted_geometry_payload(
                                axes[axis], bits_from_label(to_bits(observed))));
                    }
                }
            }
        } else {
            bool const expected67 = criterion.find("stabilization_6_7_") == 0;
            bool const expected78 = criterion.find("stabilization_7_8_") == 0;
            if ((!expected67 && !expected78) || expected67 != transition67) {
                throw std::runtime_error(
                    "component stabilization criterion/transition");
            }
            bool const coefficient = criterion.find("_exact_coeff") !=
                std::string::npos;
            bool const exact_geometry_criterion =
                criterion.find("_exact_geometry") != std::string::npos;
            for (int anchor = 0; anchor < 3; ++anchor) {
                if (coefficient) {
                    std::pair<std::vector<int>, std::vector<BigSigned> > diff =
                        coefficient_difference(
                            high,
                            high_effective[static_cast<std::size_t>(anchor)],
                            low,
                            low_effective[static_cast<std::size_t>(anchor)]);
                    observations.add(ordinal++,
                        candidate_dyadic_vector_payload(
                            diff.first, diff.second));
                    continue;
                }
                for (std::size_t axis = 0; axis < axes.size(); ++axis) {
                    if (exact_geometry_criterion) {
                        observations.add(ordinal++,
                            candidate_exact_geometry_payload(
                                axes[axis],
                                high_exact_geometry[
                                    static_cast<std::size_t>(anchor)][axis] -
                                low_exact_geometry[
                                    static_cast<std::size_t>(anchor)][axis]));
                    } else {
                        double const difference = rounded_sub(
                            high_emitted[0][static_cast<std::size_t>(anchor)]
                                             [axis],
                            low_emitted[0][static_cast<std::size_t>(anchor)]
                                            [axis]);
                        observations.add(ordinal++,
                            candidate_emitted_geometry_payload(
                                axes[axis], bits_from_label(
                                    to_bits(difference))));
                    }
                }
            }
        }
    }
    return 0;
}

int self_test() {
    if (std::fesetround(FE_TONEAREST) != 0 || std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
    }
    Sha256 sha_test;
    sha_test.update("abc");
    if (sha_test.finish_hex() !=
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") {
        throw std::runtime_error("SHA-256 self-test");
    }
    std::vector<double> coefficients{0.25, 0.5, 0.25};
    std::vector<double> constant(3, 1048576.0);
    double position = evaluate(true, 1, coefficients, constant);
    double derivative = evaluate(false, 1, coefficients, constant);
    if (to_bits(position) != "4130000000000000" ||
        to_bits(derivative) != "0000000000000000") {
        throw std::runtime_error("constant-field self-test");
    }
    BigUnsigned maximum_word = BigUnsigned::from_uint64(UINT64_MAX);
    BigUnsigned const square = maximum_word * maximum_word;
    if (square.limbs.size() != 2U || square.limbs[0] != 1U ||
        square.limbs[1] != UINT64_MAX - 1U ||
        compare(BigUnsigned::from_hex("10000000000000000"),
                BigUnsigned::power_of_two(64U)) != 0) {
        throw std::runtime_error("exact component integer self-test");
    }
    if (signed_dyadic_json(BigSigned()) !=
        "{\"denominator_power\":1074,\"kind\":\"signed_dyadic_v1\","
        "\"numerator_hex\":\"0\",\"sign\":0}") {
        throw std::runtime_error("canonical signed dyadic self-test");
    }
    static std::array<char const *, 7> const forbidden_members = {{
        "\"aggregate\"", "\"digest\"", "\"error\"", "\"outcome\"",
        "\"reason\"", "\"reference\"", "\"target\"",
    }};
    static std::array<PreoracleObservationSelection, 5> const selections = {{
        PreoracleObservationSelection::Structure,
        PreoracleObservationSelection::ConstantField,
        PreoracleObservationSelection::RelabelExact,
        PreoracleObservationSelection::RegularExactRows,
        PreoracleObservationSelection::EmittedGeometry,
    }};
    static std::array<char const *, 5> const observation_kinds = {{
        "candidate_structure_observation_v1",
        "candidate_binary64_observation_v1",
        "candidate_dyadic_vector_observation_v1",
        "candidate_dyadic_vector_observation_v1",
        "candidate_emitted_geometry_observation_v1",
    }};
    static std::array<std::uint64_t, 5> const expected_counts = {{
        3U, 45U, 6U, 3U, 1U,
    }};
    for (std::size_t selection_index = 0;
         selection_index < selections.size(); ++selection_index) {
        std::istringstream observation_input(
            selection_index == 4U
                ? "x position 1 "
                  "3fd0000000000000,3fe0000000000000,3fd0000000000000 "
                  "0000000000000000,3ff0000000000000,0000000000000000\n"
                : "position 3 0,1,2 0,1,2 "
                  "3fd0000000000000,3fe0000000000000,3fd0000000000000\n");
        std::ostringstream observation_output(std::ios::out | std::ios::binary);
        if (preoracle_observation_stream(
                observation_input, observation_output,
                selections[selection_index]) != 0) {
            throw std::runtime_error("candidate observation execution self-test");
        }
        std::string const framed = observation_output.str();
        if (framed.size() < sizeof(kCandidateValuesMagic) ||
            framed.compare(0, sizeof(kCandidateValuesMagic) - 1U,
                           kCandidateValuesMagic) != 0 ||
            framed[sizeof(kCandidateValuesMagic) - 1U] != '\0') {
            throw std::runtime_error("candidate observation magic self-test");
        }
        std::size_t offset = sizeof(kCandidateValuesMagic);
        std::uint64_t seen = 0;
        while (offset < framed.size()) {
            std::uint64_t const ordinal =
                read_uint64_be_for_self_test(framed, offset);
            std::uint64_t const payload_length =
                read_uint64_be_for_self_test(framed, offset);
            if (ordinal != seen++ || payload_length == 0 ||
                payload_length > kCandidatePayloadMaximum ||
                payload_length > framed.size() - offset) {
                throw std::runtime_error(
                    "candidate observation frame self-test");
            }
            std::string const payload = framed.substr(
                offset, static_cast<std::size_t>(payload_length));
            offset += static_cast<std::size_t>(payload_length);
            if (payload.front() != '{' || payload.back() != '}' ||
                payload.find('\n') != std::string::npos ||
                payload.find(' ') != std::string::npos ||
                payload.find(std::string("\"kind\":\"") +
                             observation_kinds[selection_index] + "\"") ==
                    std::string::npos) {
                throw std::runtime_error(
                    "candidate observation canonical self-test");
            }
            for (char const *member : forbidden_members) {
                if (payload.find(member) != std::string::npos) {
                    throw std::runtime_error(
                        "candidate observation authority leak self-test");
                }
            }
            if (selection_index == 0U &&
                (payload.find("{\"canonical_source_ids\":[0,1,2],"
                              "\"effective_coefficients\":[") != 0 ||
                 payload.find(",\"provider_coefficient_bits\":["
                              "\"3fd0000000000000\",\"3fe0000000000000\","
                              "\"3fd0000000000000\"]}") ==
                     std::string::npos)) {
                throw std::runtime_error(
                    "candidate structure observation self-test");
            }
            if (selection_index == 1U && seen == 1U && payload !=
                "{\"kind\":\"candidate_binary64_observation_v1\","
                "\"observed_bits\":\"c130000000000000\"}") {
                throw std::runtime_error(
                    "candidate binary64 observation payload self-test");
            }
            if (selection_index == 2U &&
                payload.find(",\"source_ids\":[0,1,2],\"values\":[") ==
                    std::string::npos) {
                throw std::runtime_error(
                    "candidate dyadic observation self-test");
            }
            if (selection_index == 3U &&
                payload.find(",\"source_ids\":[0,1,2],\"values\":[") ==
                    std::string::npos) {
                throw std::runtime_error(
                    "candidate regular exact observation self-test");
            }
            if (selection_index == 4U && payload !=
                "{\"axis\":\"x\",\"kind\":"
                "\"candidate_emitted_geometry_observation_v1\","
                "\"observed_bits\":\"3fe0000000000000\"}") {
                throw std::runtime_error(
                    "candidate emitted geometry observation self-test");
            }
        }
        if (offset != framed.size() || seen != expected_counts[selection_index]) {
            throw std::runtime_error("candidate observation coverage self-test");
        }
    }
#ifdef ANCHORED_ROW_GMP_INTEGRAND
    std::vector<std::string> const integrand_fields = split(
        "E position 0 3ff0000000000000,0000000000000000,0000000000000000 "
        "0000000000000000,3ff0000000000000,0000000000000000 "
        "0000000000000000,0000000000000000,3ff0000000000000 "
        "0000000000000000,0000000000000000,0000000000000000 "
        "du 0 0000000000000000,3ff0000000000000,0000000000000000 "
        "0000000000000000,3ff0000000000000,0000000000000000 "
        "0000000000000000,0000000000000000,3ff0000000000000 "
        "0000000000000000,0000000000000000,0000000000000000 "
        "dv 0 0000000000000000,0000000000000000,3ff0000000000000 "
        "0000000000000000,3ff0000000000000,0000000000000000 "
        "0000000000000000,0000000000000000,3ff0000000000000 "
        "0000000000000000,0000000000000000,0000000000000000", ' ');
    std::string const integrand_payload = exact_integrand_payload(
        integrand_fields, true);
    if (integrand_payload.find(
            "\"observed_interval\":{\"kind\":\"interval_rational_v1\","
            "\"lower\":{\"denominator\":\"1\",\"kind\":"
            "\"rational_v1\",\"numerator\":\"1\"}") ==
        std::string::npos) {
        throw std::runtime_error("candidate exact integrand self-test");
    }
#endif
    std::cout << "{\"candidate\":\"anchored_difference_rows_v1\","
                 "\"compiler_round_points\":\"volatile_binary64\","
                 "\"fma_contraction_permitted\":false,\"finite\":true,"
                 "\"integrand_exact_observation\":"
#ifdef ANCHORED_ROW_GMP_INTEGRAND
                 "true,"
#else
                 "false,"
#endif
                 "\"kind\":\"anchored_row_candidate_self_test\","
                 "\"rounding_mode\":\"FE_TONEAREST\",\"status\":\"ok\"}\n";
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") return self_test();
        if (argc == 3 && std::string(argv[1]) == "--evaluate-line") {
            if (std::fesetround(FE_TONEAREST) != 0) throw std::runtime_error("cannot set rounding mode");
            return evaluate_line(argv[2]);
        }
        if (argc == 2 && std::string(argv[1]) == "--stream") {
            if (std::fesetround(FE_TONEAREST) != 0) throw std::runtime_error("cannot set rounding mode");
            std::string line;
            while (std::getline(std::cin, line)) evaluate_line(line);
            return 0;
        }
        if (argc == 2 && std::string(argv[1]) == "--integrand-stream") {
            return integrand_stream();
        }
        if (argc == 3 &&
            std::string(argv[1]) == "--integrand-observation-stream") {
            return integrand_observation_stream(argv[2]);
        }
        if (argc == 2 && std::string(argv[1]) == "--fidelity-stream") {
            return fidelity_stream();
        }
        if (argc == 2 && std::string(argv[1]) == "--component-audit-stream") {
            return component_audit_stream();
        }
        if (argc == 3 &&
            std::string(argv[1]) == "--component-observation-stream") {
            return component_observation_stream(argv[2]);
        }
        if (argc == 2 &&
            std::string(argv[1]) == "--cache-observation-stream") {
            return cache_observation_stream();
        }
        if (argc == 3 &&
            std::string(argv[1]) == "--preoracle-observation-stream") {
            std::string const criterion = argv[2];
            if (criterion == "representation_structure") {
                return preoracle_observation_stream(
                    std::cin, std::cout,
                    PreoracleObservationSelection::Structure);
            }
            if (criterion == "constant_field_bits") {
                return preoracle_observation_stream(
                    std::cin, std::cout,
                    PreoracleObservationSelection::ConstantField);
            }
            if (criterion == "relabel_exact_effective_coefficients") {
                return preoracle_observation_stream(
                    std::cin, std::cout,
                    PreoracleObservationSelection::RelabelExact);
            }
            if (criterion == "regular_analytic_exact_rows") {
                return preoracle_observation_stream(
                    std::cin, std::cout,
                    PreoracleObservationSelection::RegularExactRows);
            }
            if (criterion == "regular_analytic_emitted_geometry" ||
                criterion == "emitted_direct_geometry_d10") {
                return preoracle_observation_stream(
                    std::cin, std::cout,
                    PreoracleObservationSelection::EmittedGeometry);
            }
            throw std::runtime_error(
                "unknown preoracle observation criterion");
        }
        if (argc == 2 && std::string(argv[1]) == "--audit-stream") {
            // Compatibility only.  Its candidate-owned decisions, aggregates,
            // maxima, and digests are explicitly non-authoritative after the
            // result-ledger amendment.  New evidence must consume the raw
            // observation stream above and derive every result in the runner.
            std::cerr << "warning: --audit-stream is legacy non-authoritative "
                         "compatibility output\n";
            return audit_stream();
        }
        std::cerr << "usage: anchored_row_candidate --self-test | --evaluate-line REQUEST | --stream | --integrand-stream | --integrand-observation-stream CRITERION | --fidelity-stream | --component-audit-stream | --component-observation-stream CRITERION | --cache-observation-stream | --preoracle-observation-stream CRITERION | --audit-stream (legacy non-authoritative)\n";
        return 2;
    } catch (std::exception const &error) {
        std::cerr << error.what() << '\n';
        return 3;
    }
}
