// Independent exact-dyadic to directed-MPFR boundary for the proof package.
// It intentionally contains no topology-provider or representation code.

#include <gmp.h>
#include <mpfr.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr mpfr_prec_t kPrecision = 544;
constexpr long kCommonExponent = -1074;

std::uint64_t parse_bits(std::string const &text) {
    if (text.size() != 16) throw std::runtime_error("binary64 label length");
    std::uint64_t bits = 0;
    std::istringstream input(text);
    input >> std::hex >> bits;
    if (!input || !input.eof()) throw std::runtime_error("binary64 label syntax");
    std::uint64_t const exponent = (bits >> 52) & 0x7ffU;
    if (exponent == 0x7ffU) throw std::runtime_error("nonfinite binary64 label");
    return bits;
}

std::vector<std::string> split(std::string const &value, char delimiter) {
    std::vector<std::string> result;
    std::istringstream input(value);
    std::string item;
    while (std::getline(input, item, delimiter)) result.push_back(item);
    if (result.empty() || result.back().empty()) throw std::runtime_error("empty list item");
    return result;
}

std::string bits_label(double value) {
    if (!std::isfinite(value)) throw std::runtime_error("nonfinite serialized interval");
    std::uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    std::ostringstream output;
    output << std::hex << std::setfill('0') << std::setw(16) << bits;
    return output.str();
}

double double_from_bits(std::string const &text) {
    std::uint64_t const bits = parse_bits(text);
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

void require_clean_mpfr_flags(char const *operation) {
    mpfr_flags_t const forbidden = MPFR_FLAGS_NAN | MPFR_FLAGS_DIVBY0 |
                                   MPFR_FLAGS_OVERFLOW | MPFR_FLAGS_UNDERFLOW |
                                   MPFR_FLAGS_ERANGE;
    if ((mpfr_flags_save() & forbidden) != 0) {
        throw std::runtime_error(std::string(operation) + " raised forbidden MPFR flags");
    }
}

struct Interval {
    mpfr_t lo;
    mpfr_t hi;

    Interval() {
        mpfr_init2(lo, kPrecision);
        mpfr_init2(hi, kPrecision);
        mpfr_set_zero(lo, 1);
        mpfr_set_zero(hi, 1);
    }
    Interval(Interval const &other) : Interval() {
        mpfr_set(lo, other.lo, MPFR_RNDD);
        mpfr_set(hi, other.hi, MPFR_RNDU);
    }
    Interval &operator=(Interval const &other) {
        if (this != &other) {
            mpfr_set(lo, other.lo, MPFR_RNDD);
            mpfr_set(hi, other.hi, MPFR_RNDU);
        }
        return *this;
    }
    ~Interval() {
        mpfr_clear(lo);
        mpfr_clear(hi);
    }
};

Interval interval_from_fraction(std::string const &numerator,
                                std::string const &denominator) {
    mpz_t denominator_value;
    mpz_init(denominator_value);
    bool const valid_denominator =
        mpz_set_str(denominator_value, denominator.c_str(), 10) == 0 &&
        mpz_sgn(denominator_value) > 0;
    mpz_clear(denominator_value);
    if (!valid_denominator) throw std::runtime_error("rational denominator");
    mpq_t value;
    mpq_init(value);
    std::string const text = numerator + "/" + denominator;
    if (mpq_set_str(value, text.c_str(), 10) != 0) {
        mpq_clear(value);
        throw std::runtime_error("rational input syntax");
    }
    mpq_canonicalize(value);
    if (mpz_sgn(mpq_denref(value)) <= 0) {
        mpq_clear(value);
        throw std::runtime_error("rational denominator");
    }
    Interval result;
    mpfr_clear_flags();
    mpfr_set_q(result.lo, value, MPFR_RNDD);
    mpfr_set_q(result.hi, value, MPFR_RNDU);
    require_clean_mpfr_flags("rational import");
    mpq_t lower, upper;
    mpq_init(lower);
    mpq_init(upper);
    mpfr_get_q(lower, result.lo);
    mpfr_get_q(upper, result.hi);
    bool const contained = mpq_cmp(lower, value) <= 0 && mpq_cmp(upper, value) >= 0;
    mpq_clear(lower);
    mpq_clear(upper);
    mpq_clear(value);
    if (!contained) throw std::runtime_error("rational import lost containment");
    return result;
}

Interval interval_from_bits(std::string const &label) {
    Interval result;
    double const value = double_from_bits(label);
    mpfr_clear_flags();
    int const lower = mpfr_set_d(result.lo, value, MPFR_RNDN);
    int const upper = mpfr_set_d(result.hi, value, MPFR_RNDN);
    require_clean_mpfr_flags("binary64 exact import");
    if (lower != 0 || upper != 0) {
        throw std::runtime_error("binary64 import was inexact");
    }
    return result;
}

Interval interval_add(Interval const &left, Interval const &right) {
    Interval result;
    mpfr_clear_flags();
    mpfr_add(result.lo, left.lo, right.lo, MPFR_RNDD);
    mpfr_add(result.hi, left.hi, right.hi, MPFR_RNDU);
    require_clean_mpfr_flags("interval addition");
    return result;
}

Interval interval_subtract(Interval const &left, Interval const &right) {
    Interval result;
    mpfr_clear_flags();
    mpfr_sub(result.lo, left.lo, right.hi, MPFR_RNDD);
    mpfr_sub(result.hi, left.hi, right.lo, MPFR_RNDU);
    require_clean_mpfr_flags("interval subtraction");
    return result;
}

Interval interval_multiply(Interval const &left, Interval const &right) {
    Interval result;
    std::array<mpfr_t, 4> lower;
    std::array<mpfr_t, 4> upper;
    for (std::size_t index = 0; index < 4; ++index) {
        mpfr_init2(lower[index], kPrecision);
        mpfr_init2(upper[index], kPrecision);
    }
    mpfr_srcptr left_values[2] = {left.lo, left.hi};
    mpfr_srcptr right_values[2] = {right.lo, right.hi};
    mpfr_clear_flags();
    std::size_t index = 0;
    for (std::size_t i = 0; i < 2; ++i) {
        for (std::size_t j = 0; j < 2; ++j, ++index) {
            mpfr_mul(lower[index], left_values[i], right_values[j], MPFR_RNDD);
            mpfr_mul(upper[index], left_values[i], right_values[j], MPFR_RNDU);
        }
    }
    mpfr_set(result.lo, lower[0], MPFR_RNDD);
    mpfr_set(result.hi, upper[0], MPFR_RNDU);
    for (index = 1; index < 4; ++index) {
        if (mpfr_cmp(lower[index], result.lo) < 0) {
            mpfr_set(result.lo, lower[index], MPFR_RNDD);
        }
        if (mpfr_cmp(upper[index], result.hi) > 0) {
            mpfr_set(result.hi, upper[index], MPFR_RNDU);
        }
    }
    require_clean_mpfr_flags("interval multiplication");
    for (index = 0; index < 4; ++index) {
        mpfr_clear(lower[index]);
        mpfr_clear(upper[index]);
    }
    return result;
}

Interval interval_square_root(Interval const &value) {
    if (mpfr_sgn(value.lo) < 0) throw std::runtime_error("negative interval radicand");
    Interval result;
    mpfr_clear_flags();
    mpfr_sqrt(result.lo, value.lo, MPFR_RNDD);
    mpfr_sqrt(result.hi, value.hi, MPFR_RNDU);
    require_clean_mpfr_flags("interval square root");
    return result;
}

struct Integrands {
    Interval area;
    Interval volume;
};

Integrands regular_integrands(std::array<Interval, 9> const &values) {
    Interval const cx = interval_subtract(
        interval_multiply(values[4], values[8]),
        interval_multiply(values[5], values[7]));
    Interval const cy = interval_subtract(
        interval_multiply(values[5], values[6]),
        interval_multiply(values[3], values[8]));
    Interval const cz = interval_subtract(
        interval_multiply(values[3], values[7]),
        interval_multiply(values[4], values[6]));
    Interval const radicand = interval_add(
        interval_add(interval_multiply(cx, cx), interval_multiply(cy, cy)),
        interval_multiply(cz, cz));
    Integrands result;
    result.area = interval_square_root(radicand);
    result.volume = interval_multiply(values[0], cx);
    return result;
}

void difference_upper(mpfr_t output, Interval const &left,
                      Interval const &right) {
    mpfr_t lower, upper, lower_abs, upper_abs;
    mpfr_init2(lower, kPrecision);
    mpfr_init2(upper, kPrecision);
    mpfr_init2(lower_abs, kPrecision);
    mpfr_init2(upper_abs, kPrecision);
    mpfr_clear_flags();
    mpfr_sub(lower, left.lo, right.hi, MPFR_RNDD);
    mpfr_sub(upper, left.hi, right.lo, MPFR_RNDU);
    mpfr_abs(lower_abs, lower, MPFR_RNDU);
    mpfr_abs(upper_abs, upper, MPFR_RNDU);
    mpfr_max(output, lower_abs, upper_abs, MPFR_RNDU);
    require_clean_mpfr_flags("interval absolute difference");
    mpfr_clear(lower);
    mpfr_clear(upper);
    mpfr_clear(lower_abs);
    mpfr_clear(upper_abs);
}

std::array<Interval, 9> parse_fraction_vector(
    std::vector<std::string> const &fields, std::size_t offset) {
    std::array<Interval, 9> result;
    for (std::size_t index = 0; index < result.size(); ++index) {
        result[index] = interval_from_fraction(fields[offset + 2 * index],
                                               fields[offset + 2 * index + 1]);
    }
    return result;
}

void emit_integrand_comparison(Integrands const &candidate,
                               Integrands const &analytic) {
    mpfr_t area_difference, volume_difference;
    mpfr_init2(area_difference, kPrecision);
    mpfr_init2(volume_difference, kPrecision);
    difference_upper(area_difference, candidate.area, analytic.area);
    difference_upper(volume_difference, candidate.volume, analytic.volume);
    mpq_t target;
    mpq_init(target);
    mpq_set_si(target, 5, 1000000);
    bool const area_pass = mpfr_cmp_q(area_difference, target) <= 0;
    bool const volume_pass = mpfr_cmp_q(volume_difference, target) <= 0;
    double const area_serialized = mpfr_get_d(area_difference, MPFR_RNDU);
    double const volume_serialized = mpfr_get_d(volume_difference, MPFR_RNDU);
    if (!std::isfinite(area_serialized) || !std::isfinite(volume_serialized)) {
        throw std::runtime_error("nonfinite integrand difference");
    }
    std::cout << (area_pass ? "PASS" : "FAIL") << ' '
              << (volume_pass ? "PASS" : "FAIL") << ' '
              << bits_label(area_serialized) << ' '
              << bits_label(volume_serialized) << '\n';
    mpq_clear(target);
    mpfr_clear(area_difference);
    mpfr_clear(volume_difference);
}

int regular_integrand_stream() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) throw std::runtime_error("empty integrand request");
        std::vector<std::string> const fields = split(line, ' ');
        if (fields[0] == "E") {
            if (fields.size() != 37) throw std::runtime_error("exact integrand request arity");
            Integrands const candidate = regular_integrands(
                parse_fraction_vector(fields, 1));
            Integrands const analytic = regular_integrands(
                parse_fraction_vector(fields, 19));
            emit_integrand_comparison(candidate, analytic);
        } else if (fields[0] == "B") {
            if (fields.size() != 21) throw std::runtime_error("binary integrand request arity");
            Integrands candidate;
            candidate.area = interval_from_bits(fields[1]);
            candidate.volume = interval_from_bits(fields[2]);
            Integrands const analytic = regular_integrands(
                parse_fraction_vector(fields, 3));
            emit_integrand_comparison(candidate, analytic);
        } else {
            throw std::runtime_error("integrand request mode");
        }
    }
    return 0;
}

void exact_numerator_from_bits(mpz_t output, std::uint64_t bits) {
    bool const negative = (bits >> 63) != 0;
    std::uint64_t const exponent = (bits >> 52) & 0x7ffU;
    std::uint64_t const fraction = bits & UINT64_C(0x000fffffffffffff);
    if (exponent == 0) {
        mpz_set_ui(output, fraction);
    } else {
        mpz_set_ui(output, fraction | UINT64_C(0x0010000000000000));
        mpz_mul_2exp(output, output, static_cast<mp_bitcnt_t>(exponent - 1));
    }
    if (negative) mpz_neg(output, output);
}

bool exactly_representable_at_precision(mpz_t numerator) {
    if (mpz_sgn(numerator) == 0) return true;
    mpz_t magnitude;
    mpz_init(magnitude);
    mpz_abs(magnitude, numerator);
    mp_bitcnt_t const trailing = mpz_scan1(magnitude, 0);
    mpz_fdiv_q_2exp(magnitude, magnitude, trailing);
    bool const result = mpz_sizeinbase(magnitude, 2) <= kPrecision;
    mpz_clear(magnitude);
    return result;
}

void require_outward_import(mpz_t numerator) {
    mpfr_t lower, upper;
    mpfr_init2(lower, kPrecision);
    mpfr_init2(upper, kPrecision);
    mpfr_clear_flags();
    int const lower_ternary = mpfr_set_z_2exp(lower, numerator, kCommonExponent, MPFR_RNDD);
    mpfr_flags_t const lower_flags = mpfr_flags_save();
    mpfr_clear_flags();
    int const upper_ternary = mpfr_set_z_2exp(upper, numerator, kCommonExponent, MPFR_RNDU);
    mpfr_flags_t const upper_flags = mpfr_flags_save();
    if (mpfr_nan_p(lower) || mpfr_nan_p(upper) || mpfr_inf_p(lower) || mpfr_inf_p(upper) ||
        mpfr_cmp(lower, upper) > 0) {
        throw std::runtime_error("invalid directed endpoint");
    }
    mpq_t exact, lower_q, upper_q;
    mpq_init(exact);
    mpq_init(lower_q);
    mpq_init(upper_q);
    mpq_set_z(exact, numerator);
    mpq_div_2exp(exact, exact, 1074);
    mpfr_get_q(lower_q, lower);
    mpfr_get_q(upper_q, upper);
    if (mpq_cmp(lower_q, exact) > 0 || mpq_cmp(upper_q, exact) < 0) {
        throw std::runtime_error("directed endpoint lost containment");
    }
    bool const exact_at_precision = exactly_representable_at_precision(numerator);
    if ((exact_at_precision && (lower_ternary != 0 || upper_ternary != 0)) ||
        (!exact_at_precision && (lower_ternary >= 0 || upper_ternary <= 0))) {
        throw std::runtime_error("directed ternary sign mismatch");
    }
    mpfr_flags_t const forbidden = MPFR_FLAGS_NAN | MPFR_FLAGS_DIVBY0 |
                                   MPFR_FLAGS_OVERFLOW | MPFR_FLAGS_UNDERFLOW |
                                   MPFR_FLAGS_ERANGE;
    if ((lower_flags & forbidden) != 0 || (upper_flags & forbidden) != 0) {
        throw std::runtime_error("directed import raised forbidden flags");
    }
    mpq_clear(exact);
    mpq_clear(lower_q);
    mpq_clear(upper_q);
    mpfr_clear(lower);
    mpfr_clear(upper);
}

void effective_numerators(std::vector<std::string> const &labels,
                          bool position, std::size_t anchor) {
    if (labels.empty() || anchor >= labels.size()) throw std::runtime_error("row cardinality or anchor");
    mpz_t sum, value, target;
    mpz_init_set_ui(sum, 0);
    mpz_init(value);
    mpz_init_set_ui(target, 0);
    if (position) mpz_setbit(target, 1074);
    mpz_t *values = new mpz_t[labels.size()];
    for (std::size_t index = 0; index < labels.size(); ++index) {
        mpz_init(values[index]);
        exact_numerator_from_bits(values[index], parse_bits(labels[index]));
        mpz_add(sum, sum, values[index]);
    }
    mpz_sub(value, target, sum);
    mpz_add(values[anchor], values[anchor], value);
    for (std::size_t index = 0; index < labels.size(); ++index) {
        require_outward_import(values[index]);
    }
    for (std::size_t index = 0; index < labels.size(); ++index) {
        mpz_clear(values[index]);
    }
    delete[] values;
    mpz_clear(sum);
    mpz_clear(value);
    mpz_clear(target);
}

int self_test() {
    if (std::strcmp(MPFR_VERSION_STRING, "4.2.2") != 0 ||
        std::strcmp(mpfr_get_version(), "4.2.2") != 0) {
        throw std::runtime_error("MPFR compile/runtime version must both be 4.2.2");
    }
    effective_numerators({"3fe0000000000001", "3fd0000000000000",
                          "3fcffffffffffffc"}, true, 1);
    effective_numerators({"3ff0000000000001", "bfe0000000000000",
                          "bfd0000000000002"}, false, 2);
    std::cout << "{\"candidate_arithmetic_imported\":false,"
                 "\"directed_rounding\":true,\"exact_common_denominator_exponent\":-1074,"
                 "\"finite\":true,\"kind\":\"exact_dyadic_boundary_self_test\","
                 "\"mpfr_compile_version\":\"" << MPFR_VERSION_STRING << "\","
                 "\"mpfr_runtime_version\":\"" << mpfr_get_version() << "\","
                 "\"precision_bits\":544,\"status\":\"ok\"}\n";
    return 0;
}

int capability() {
    std::cout << "{\"coverage\":\"UNCOVERED\","
                 "\"implementation_state\":\"INCOMPLETE\","
                 "\"kind\":\"independent_primary_capability\","
                 "\"missing_algorithms\":["
                 "\"stock_mask_interval_matrix_construction\","
                 "\"interval_eigenpair_krawczyk_certification\","
                 "\"repeated_eigenspace_spectral_projector_certification\","
                 "\"quartic_box_spline_interval_evaluation\","
                 "\"certified_parametric_branch_mapping\","
                 "\"independent_uniform_five_depth_intersection\"],"
                 "\"reason_code\":\"EIGENBASIS_CERTIFICATION_FAILED\","
                 "\"status\":\"honest_incomplete\","
                 "\"uniform_success_substituted_for_primary\":false}\n";
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") return self_test();
        if (argc == 2 && std::string(argv[1]) == "--capability") return capability();
        if (argc == 2 && std::string(argv[1]) == "--regular-integrand-stream") {
            return regular_integrand_stream();
        }
        if (argc == 5 && std::string(argv[1]) == "--import-row") {
            bool const position = std::string(argv[2]) == "position";
            if (!position && std::string(argv[2]) != "derivative") {
                throw std::runtime_error("row target syntax");
            }
            std::size_t consumed = 0;
            std::size_t const anchor = std::stoul(argv[3], &consumed, 10);
            if (consumed != std::strlen(argv[3])) throw std::runtime_error("anchor syntax");
            effective_numerators(split(argv[4], ','), position, anchor);
            std::cout << "{\"status\":\"ok\"}\n";
            return 0;
        }
        std::cerr << "usage: exact_dyadic_boundary --self-test | --capability | --regular-integrand-stream | --import-row TARGET ANCHOR COEFFICIENT_BITS\n";
        return 2;
    } catch (std::exception const &error) {
        std::cerr << error.what() << '\n';
        return 3;
    }
}
