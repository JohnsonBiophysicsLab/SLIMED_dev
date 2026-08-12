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

namespace {

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
        "0000000000000000", "3ff0000000000000", "bff0000000000000",
        "4130000000000000", "c130000000000000",
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
                continue;
            }
            std::size_t const original_anchor = static_cast<std::size_t>(
                anchor_iterator - source_ids.begin());
            std::vector<FixedInt> expected_effective = exact_coefficients;
            expected_effective[original_anchor] += target - exact_sum;
            FixedInt effective_sum;
            for (FixedInt const &value : expected_effective) effective_sum += value;
            if (effective_sum != target) {
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
                    if (to_bits(observed) != to_bits(expected)) {
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
    std::cout << "{\"constant_cell_count\":" << constant_cells
              << ",\"constant_failure_count\":" << constant_failures << ',';
    emit_failure("first_constant_failure", first_constant);
    std::cout << ',';
    emit_failure("first_relabel_exact_failure", first_relabel);
    std::cout << ',';
    emit_failure("first_structure_failure", first_structure);
    std::cout << ",\"kind\":\"anchored_row_preoracle_audit\""
              << ",\"relabel_exact_cell_count\":" << relabel_cells
              << ",\"relabel_exact_failure_count\":" << relabel_failures
              << ",\"row_count\":" << rows
              << ",\"status\":\""
              << ((structure_failures || constant_failures || relabel_failures)
                      ? "candidate_failure" : "ok")
              << "\",\"structure_cell_count\":" << structure_cells
              << ",\"structure_failure_count\":" << structure_failures << "}\n";
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
    ComponentFailure first;
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
                       long double magnitude, std::uint64_t row,
                       int anchor = -1, int relabel = -1, int axis = -1,
                       int pair = -1, int basis_source = -1) {
    ++statistic.cells;
    if (!std::isfinite(magnitude) || magnitude < 0.0L) {
        throw std::runtime_error("nonfinite component magnitude");
    }
    statistic.maximum = std::max(statistic.maximum, magnitude);
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
                coefficient_magnitude(coefficient_difference), row_ordinal,
                -1, -1, -1, pair);
            for (int axis = 0; axis < 3; ++axis) {
                BigUnsigned const exact_difference = absolute_difference(
                    high_exact_geometry[static_cast<std::size_t>(left)]
                                       [static_cast<std::size_t>(axis)],
                    high_exact_geometry[static_cast<std::size_t>(right)]
                                       [static_cast<std::size_t>(axis)]);
                observe_component(statistics[kAnchorExactGeometry],
                    geometry_within_target(exact_difference, boundary2148),
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
            std::size_t const anchor_index = static_cast<std::size_t>(
                anchor_iterator - high.source_ids.begin());
            std::vector<double> source_basis(high.source_ids.size(), 0.0);
            for (std::size_t source = 0; source < high.source_ids.size(); ++source) {
                source_basis[source] = 1.0;
                double const observed = evaluate(high.position, anchor_index,
                                                 high.coefficients, source_basis);
                source_basis[source] = 0.0;
                BigUnsigned const difference = absolute_difference(
                    exact_binary64_big(bits_from_label(to_bits(observed))),
                    high_effective[static_cast<std::size_t>(anchor)][source]);
                observe_component(statistics[kBasisDiagnostic],
                    coefficient_within_target(difference, target_numerator),
                    coefficient_magnitude(difference), row_ordinal, anchor,
                    0, -1, -1, high.source_ids[source]);
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
                coefficient_magnitude(coefficient_difference), row_ordinal, anchor);
            for (int axis = 0; axis < 3; ++axis) {
                BigUnsigned const exact_difference = absolute_difference(
                    high_exact_geometry[static_cast<std::size_t>(anchor)]
                                       [static_cast<std::size_t>(axis)],
                    low_exact_geometry[static_cast<std::size_t>(anchor)]
                                      [static_cast<std::size_t>(axis)]);
                observe_component(statistics[stabilization_exact_geometry],
                    geometry_within_target(exact_difference, boundary2148),
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
        ComponentStatistic const &statistic = statistics[index];
        any_failure = any_failure || statistic.failures != 0;
        std::cout << '"' << kComponentCriteria[index] << "\":{\"cell_count\":"
                  << statistic.cells << ",\"failure_count\":"
                  << statistic.failures << ",\"first_failure\":";
        emit_component_failure(statistic.first);
        std::cout << ",\"maximum\":" << std::setprecision(17)
                  << static_cast<double>(statistic.maximum) << '}';
    }
    std::cout << "},\"kind\":\"anchored_row_component_audit\",\"row_count\":"
              << row_ordinal << ",\"status\":\""
              << (any_failure ? "candidate_failure" : "ok") << "\"}\n";
    return 0;
}

int self_test() {
    if (std::fesetround(FE_TONEAREST) != 0 || std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST unavailable");
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
    std::cout << "{\"candidate\":\"anchored_difference_rows_v1\","
                 "\"compiler_round_points\":\"volatile_binary64\","
                 "\"fma_contraction_permitted\":false,\"finite\":true,"
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
        if (argc == 2 && std::string(argv[1]) == "--fidelity-stream") {
            return fidelity_stream();
        }
        if (argc == 2 && std::string(argv[1]) == "--component-audit-stream") {
            return component_audit_stream();
        }
        if (argc == 2 && std::string(argv[1]) == "--audit-stream") {
            return audit_stream();
        }
        std::cerr << "usage: anchored_row_candidate --self-test | --evaluate-line REQUEST | --stream | --integrand-stream | --fidelity-stream | --component-audit-stream | --audit-stream\n";
        return 2;
    } catch (std::exception const &error) {
        std::cerr << error.what() << '\n';
        return 3;
    }
}
