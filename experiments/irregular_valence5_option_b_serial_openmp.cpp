#include <omp.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace
{
constexpr int kFaceCount = 20;
constexpr int kSourceCount = 12;
constexpr int kEnergyComponents = 10;
constexpr int kGeometryComponents = 6;
constexpr int kForceComponents = kSourceCount * 9;
constexpr double kTolerance = 1.0e-10;
constexpr int kRepeats = 5;
constexpr std::array<int, 3> kThreadCounts{{1, 2, 4}};

struct Package
{
    std::vector<double> faceEnergy;
    std::vector<double> faceGeometry;
    std::vector<double> perFaceForces;
    std::vector<double> expectedAggregateForces;
};

struct Accumulation
{
    double curvature = 0.0;
    double regularization = 0.0;
    double area = 0.0;
    double legacyVolume = 0.0;
    std::array<double, kForceComponents> forces{};
    std::vector<double> publishedEnergy;
    std::vector<double> publishedGeometry;
    std::vector<double> publishedForces;
    int actualThreads = 0;
};

bool read_values(std::istream &input, const std::string &label,
                 const std::size_t count, std::vector<double> &values)
{
    std::string actual;
    if (!(input >> actual) || actual != label)
        return false;
    values.resize(count);
    for (double &value : values)
        if (!(input >> value) || !std::isfinite(value))
            return false;
    return true;
}

bool load_package(const char *path, Package &package)
{
    std::ifstream input(path);
    std::string label;
    int faces = 0;
    int sources = 0;
    if (!(input >> label >> faces >> sources) || label != "COUNTS" ||
        faces != kFaceCount || sources != kSourceCount)
        return false;
    if (!read_values(input, "FACE_ENERGY", kFaceCount * kEnergyComponents,
                     package.faceEnergy) ||
        !read_values(input, "FACE_GEOMETRY", kFaceCount * kGeometryComponents,
                     package.faceGeometry) ||
        !read_values(input, "PER_FACE_SOURCE_FORCES",
                     kFaceCount * kForceComponents, package.perFaceForces) ||
        !read_values(input, "AGGREGATE_SOURCE_FORCES", kForceComponents,
                     package.expectedAggregateForces) ||
        !(input >> label) || label != "END")
        return false;
    input >> std::ws;
    return input.peek() == std::char_traits<char>::eof();
}

void accumulate_face(const Package &package, const int face,
                     Accumulation &result)
{
    result.curvature += package.faceEnergy[face * kEnergyComponents];
    result.regularization += package.faceEnergy[
        face * kEnergyComponents + 5];
    result.area += package.faceGeometry[face * kGeometryComponents + 4];
    result.legacyVolume += package.faceGeometry[
        face * kGeometryComponents + 5];
    for (int component = 0; component < kForceComponents; ++component)
        result.forces[component] += package.perFaceForces[
            face * kForceComponents + component];
}

void publish_face(const Package &package, const int face,
                  Accumulation &result)
{
    std::copy_n(package.faceEnergy.begin() + face * kEnergyComponents,
                kEnergyComponents,
                result.publishedEnergy.begin() + face * kEnergyComponents);
    std::copy_n(package.faceGeometry.begin() + face * kGeometryComponents,
                kGeometryComponents,
                result.publishedGeometry.begin() + face * kGeometryComponents);
    std::copy_n(package.perFaceForces.begin() + face * kForceComponents,
                kForceComponents,
                result.publishedForces.begin() + face * kForceComponents);
}

Accumulation make_output()
{
    Accumulation result;
    const double missing = std::numeric_limits<double>::quiet_NaN();
    result.publishedEnergy.assign(kFaceCount * kEnergyComponents, missing);
    result.publishedGeometry.assign(kFaceCount * kGeometryComponents, missing);
    result.publishedForces.assign(kFaceCount * kForceComponents, missing);
    return result;
}

Accumulation run_serial(const Package &package)
{
    Accumulation result = make_output();
    result.actualThreads = 1;
    for (int face = 0; face < kFaceCount; ++face)
    {
        accumulate_face(package, face, result);
        publish_face(package, face, result);
    }
    return result;
}

Accumulation run_openmp(const Package &package, const int requestedThreads)
{
    std::vector<Accumulation> partials(requestedThreads);
    Accumulation result = make_output();
    double curvature = 0.0;
    double regularization = 0.0;
    double area = 0.0;
    double legacyVolume = 0.0;
    omp_set_dynamic(0);
#pragma omp parallel num_threads(requestedThreads)
    {
        const int thread = omp_get_thread_num();
#pragma omp single
        result.actualThreads = omp_get_num_threads();
#pragma omp for schedule(static) reduction(+ : curvature, regularization, area, legacyVolume)
        for (int face = 0; face < kFaceCount; ++face)
        {
            curvature += package.faceEnergy[face * kEnergyComponents];
            regularization += package.faceEnergy[
                face * kEnergyComponents + 5];
            area += package.faceGeometry[face * kGeometryComponents + 4];
            legacyVolume += package.faceGeometry[
                face * kGeometryComponents + 5];
            for (int component = 0; component < kForceComponents; ++component)
                partials[thread].forces[component] += package.perFaceForces[
                    face * kForceComponents + component];
            publish_face(package, face, result);
        }
    }
    result.curvature = curvature;
    result.regularization = regularization;
    result.area = area;
    result.legacyVolume = legacyVolume;
    for (int thread = 0; thread < result.actualThreads; ++thread)
    {
        for (int component = 0; component < kForceComponents; ++component)
            result.forces[component] += partials[thread].forces[component];
    }
    return result;
}

double maximum_delta(const std::vector<double> &left,
                     const std::vector<double> &right)
{
    if (left.size() != right.size())
        return std::numeric_limits<double>::infinity();
    double maximum = 0.0;
    for (std::size_t index = 0; index < left.size(); ++index)
    {
        if (!std::isfinite(left[index]) || !std::isfinite(right[index]))
            return std::numeric_limits<double>::infinity();
        maximum = std::max(maximum, std::abs(left[index] - right[index]));
    }
    return maximum;
}

double accumulation_delta(const Accumulation &left,
                          const Accumulation &right)
{
    double maximum = std::max({
        std::abs(left.curvature - right.curvature),
        std::abs(left.regularization - right.regularization),
        std::abs(left.area - right.area),
        std::abs(left.legacyVolume - right.legacyVolume),
    });
    for (int component = 0; component < kForceComponents; ++component)
        maximum = std::max(
            maximum, std::abs(left.forces[component] - right.forces[component]));
    return maximum;
}

double force_kind_delta(const Accumulation &left,
                        const Accumulation &right, const int kind)
{
    double maximum = 0.0;
    for (int source = 0; source < kSourceCount; ++source)
        for (int axis = 0; axis < 3; ++axis)
        {
            const int component = source * 9 + kind * 3 + axis;
            maximum = std::max(
                maximum,
                std::abs(left.forces[component] - right.forces[component]));
        }
    return maximum;
}

void print_values(const std::array<double, kForceComponents> &values)
{
    std::cout << '[';
    for (int index = 0; index < kForceComponents; ++index)
    {
        if (index != 0)
            std::cout << ',';
        std::cout << values[index];
    }
    std::cout << ']';
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 2)
    {
        std::cerr << "usage: irregular_valence5_option_b_serial_openmp PACKAGE\n";
        return 2;
    }
    Package package;
    if (!load_package(argv[1], package))
    {
        std::cerr << "invalid Option B serial/OpenMP package\n";
        return 3;
    }
    const Accumulation serial = run_serial(package);
    double maxSerialOpenMp = 0.0;
    double maxRepeatability = 0.0;
    double maxPublication = 0.0;
    std::array<double, 3> maxForceKind{{0.0, 0.0, 0.0}};
    double maxCurvature = 0.0;
    double maxRegularization = 0.0;
    double maxArea = 0.0;
    double maxLegacyVolume = 0.0;
    std::array<int, 3> actualThreads{{0, 0, 0}};
    bool finite = true;

    for (std::size_t countIndex = 0; countIndex < kThreadCounts.size(); ++countIndex)
    {
        const int requested = kThreadCounts[countIndex];
        const Accumulation baseline = run_openmp(package, requested);
        actualThreads[countIndex] = baseline.actualThreads;
        maxSerialOpenMp = std::max(
            maxSerialOpenMp, accumulation_delta(serial, baseline));
        for (int kind = 0; kind < 3; ++kind)
            maxForceKind[kind] = std::max(
                maxForceKind[kind], force_kind_delta(serial, baseline, kind));
        maxCurvature = std::max(
            maxCurvature, std::abs(serial.curvature - baseline.curvature));
        maxRegularization = std::max(
            maxRegularization,
            std::abs(serial.regularization - baseline.regularization));
        maxArea = std::max(maxArea, std::abs(serial.area - baseline.area));
        maxLegacyVolume = std::max(
            maxLegacyVolume,
            std::abs(serial.legacyVolume - baseline.legacyVolume));
        maxPublication = std::max({
            maxPublication,
            maximum_delta(package.faceEnergy, baseline.publishedEnergy),
            maximum_delta(package.faceGeometry, baseline.publishedGeometry),
            maximum_delta(package.perFaceForces, baseline.publishedForces),
        });
        for (int repeat = 1; repeat < kRepeats; ++repeat)
        {
            const Accumulation candidate = run_openmp(package, requested);
            maxRepeatability = std::max({
                maxRepeatability,
                accumulation_delta(baseline, candidate),
                maximum_delta(baseline.publishedEnergy,
                              candidate.publishedEnergy),
                maximum_delta(baseline.publishedGeometry,
                              candidate.publishedGeometry),
                maximum_delta(baseline.publishedForces,
                              candidate.publishedForces),
            });
            finite = finite && candidate.actualThreads == requested;
        }
        finite = finite && baseline.actualThreads == requested;
    }
    const double aggregateDelta = maximum_delta(
        std::vector<double>(serial.forces.begin(), serial.forces.end()),
        package.expectedAggregateForces);
    const bool nonzero = std::any_of(
        serial.forces.begin(), serial.forces.end(),
        [](const double value) { return std::abs(value) > 1.0e-12; });
    finite = finite && std::isfinite(maxSerialOpenMp) &&
        std::isfinite(maxRepeatability) && std::isfinite(maxPublication) &&
        std::isfinite(aggregateDelta);
    const bool passed = finite && nonzero &&
        maxSerialOpenMp <= kTolerance && maxRepeatability <= kTolerance &&
        maxPublication == 0.0 && aggregateDelta <= 1.0e-12;

    std::cout << std::setprecision(17) << '{'
              << "\"status\":\"" << (passed ? "passed" : "failed") << "\","
              << "\"actual_openmp_executed\":true,"
              << "\"production_shape_replayed\":true,"
              << "\"finite\":" << (finite ? "true" : "false") << ','
              << "\"nonzero_stock_force\":" << (nonzero ? "true" : "false") << ','
              << "\"requested_thread_counts\":[1,2,4],"
              << "\"actual_thread_counts\":[" << actualThreads[0] << ','
              << actualThreads[1] << ',' << actualThreads[2] << "],"
              << "\"repeats_per_thread_count\":" << kRepeats << ','
              << "\"max_serial_openmp_accumulation_difference\":"
              << maxSerialOpenMp << ','
              << "\"max_fixed_thread_repeatability_difference\":"
              << maxRepeatability << ','
              << "\"max_face_publication_difference\":" << maxPublication << ','
              << "\"max_curvature_force_difference\":" << maxForceKind[0] << ','
              << "\"max_area_force_difference\":" << maxForceKind[1] << ','
              << "\"max_volume_force_difference\":" << maxForceKind[2] << ','
              << "\"max_curvature_energy_sum_difference\":" << maxCurvature << ','
              << "\"max_regularization_energy_sum_difference\":"
              << maxRegularization << ','
              << "\"max_area_sum_difference\":" << maxArea << ','
              << "\"max_legacy_volume_sum_difference\":"
              << maxLegacyVolume << ','
              << "\"serial_expected_aggregate_force_difference\":"
              << aggregateDelta << ','
              << "\"serial_curvature_energy_sum\":" << serial.curvature << ','
              << "\"serial_regularization_energy_sum\":"
              << serial.regularization << ','
              << "\"serial_area_sum\":" << serial.area << ','
              << "\"serial_legacy_volume_sum\":" << serial.legacyVolume << ','
              << "\"serial_aggregate_source_forces\":";
    print_values(serial.forces);
    std::cout << "}\n";
    return passed ? 0 : 4;
}
