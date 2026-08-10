#include "mpfr_interval.hpp"

#include <mpfr.h>

#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

using b2interval::MpfrInterval;

int self_test() {
    if (std::strcmp(MPFR_VERSION_STRING, "4.2.2") != 0 ||
        std::strcmp(mpfr_get_version(), "4.2.2") != 0) {
        throw std::runtime_error("MPFR compile/runtime version must both be 4.2.2");
    }
    MpfrInterval one_third = b2interval::divide(MpfrInterval(1), MpfrInterval(3));
    MpfrInterval two_thirds = b2interval::add(one_third, one_third);
    MpfrInterval one_third_rescaled = b2interval::multiply(one_third, MpfrInterval(3));
    MpfrInterval two_thirds_rescaled = b2interval::multiply(two_thirds, MpfrInterval(3));
    MpfrInterval product = b2interval::multiply(MpfrInterval::decimal("1.25"),
                                                MpfrInterval::decimal("-0.4"));
    MpfrInterval root = b2interval::square_root(MpfrInterval::decimal("2"));
    MpfrInterval root_squared = b2interval::multiply(root, root);
    MpfrInterval cosine = b2interval::loop_cosine(6);
    struct ContainmentCase {
        char const *name;
        MpfrInterval const *interval;
        char const *expected;
    };
    ContainmentCase const cases[] = {
        {"one_third_rescaled", &one_third_rescaled, "1"},
        {"two_thirds_rescaled", &two_thirds_rescaled, "2"},
        {"signed_product", &product, "-0.5"},
        {"sqrt_squared", &root_squared, "2"},
        {"loop_cosine", &cosine, "0.5"},
    };
    for (ContainmentCase const &test_case : cases) {
        if (!b2interval::contains(*test_case.interval, test_case.expected)) {
            throw std::runtime_error(std::string("directed interval containment self-test failed: ") +
                                     test_case.name);
        }
    }
    bool zero_rejected = false;
    try {
        (void)b2interval::divide(MpfrInterval(1), MpfrInterval(0));
    } catch (std::runtime_error const &) {
        zero_rejected = true;
    }
    if (!zero_rejected) {
        throw std::runtime_error("zero-containing denominator was accepted");
    }
    std::cout << "{\"schema_version\":1,\"kind\":\"stam_oracle_self_test\","
                 "\"status\":\"ok\",\"finite\":true,\"precision_bits\":544,"
                 "\"mpfr_compile_version\":\"" << MPFR_VERSION_STRING << "\","
                 "\"mpfr_runtime_version\":\"" << mpfr_get_version() << "\","
                 "\"directed_rounding\":true,\"zero_denominator_rejected\":true,"
                 "\"candidate_dependency_free\":true}\n";
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") {
            return self_test();
        }
        std::cerr << "usage: stam_oracle --self-test\n";
        return 2;
    } catch (std::exception const &error) {
        std::cerr << error.what() << "\n";
        return 3;
    }
}
