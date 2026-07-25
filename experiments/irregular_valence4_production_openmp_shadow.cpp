#include "io/io.hpp"
#include "mesh/Mesh.hpp"

#include <omp.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace
{
constexpr int kFaceCount = 8;
constexpr int kSourceCount = 6;
constexpr int kForceKinds = 3;
constexpr int kAxes = 3;
constexpr int kComponents = kSourceCount * kForceKinds * kAxes;
constexpr int kRepeats = 5;
constexpr double kTolerance = 1.0e-12;

using SourceVector = std::array<double, kAxes>;
using ForceKinds = std::array<SourceVector, kForceKinds>;
using FaceForces = std::array<ForceKinds, kSourceCount>;
using Contributions = std::array<FaceForces, kFaceCount>;
using Oracle = std::array<
    std::array<std::array<long double, kAxes>, kForceKinds>,
    kSourceCount>;

class ScopedCoutSilencer
{
  public:
    ScopedCoutSilencer() : original_(std::cout.rdbuf(buffer_.rdbuf())) {}
    ~ScopedCoutSilencer() { std::cout.rdbuf(original_); }

  private:
    std::ostringstream buffer_;
    std::streambuf *original_;
};

struct ThreadRun
{
    int requestedThreads = 0;
    std::array<int, kRepeats> actualThreads{};
    double maxOracleDelta = 0.0;
    double maxRepeatDelta = 0.0;
    bool finite = true;
    bool passed = true;
};

int flat_index(const int source, const int kind, const int axis)
{
    return source * 9 + kind * 3 + axis;
}

bool read_contributions(const std::string &path, Contributions &values)
{
    std::ifstream input(path);
    int faceCount = 0;
    if (!(input >> faceCount) || faceCount != kFaceCount)
    {
        return false;
    }
    for (int expectedFace = 0; expectedFace < kFaceCount; ++expectedFace)
    {
        int face = -1;
        if (!(input >> face) || face != expectedFace)
        {
            return false;
        }
        for (int kind = 0; kind < kForceKinds; ++kind)
        {
            for (int source = 0; source < kSourceCount; ++source)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    if (!(input >> values[face][source][kind][axis]))
                    {
                        return false;
                    }
                }
            }
        }
    }
    double extra = 0.0;
    return !(input >> extra);
}

Oracle accumulate_oracle(const Contributions &values)
{
    Oracle oracle{};
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKinds; ++kind)
        {
            for (int axis = 0; axis < kAxes; ++axis)
            {
                long double sum = 0.0L;
                for (int face = 0; face < kFaceCount; ++face)
                {
                    sum += static_cast<long double>(
                        values[face][source][kind][axis]);
                }
                oracle[source][kind][axis] = sum;
            }
        }
    }
    return oracle;
}

std::array<double, kComponents> flatten_oracle(const Oracle &oracle)
{
    std::array<double, kComponents> flattened{};
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKinds; ++kind)
        {
            for (int axis = 0; axis < kAxes; ++axis)
            {
                const int destination =
                    source * (kForceKinds * kAxes) + kind * kAxes + axis;
                flattened[destination] =
                    static_cast<double>(oracle[source][kind][axis]);
            }
        }
    }
    return flattened;
}

double max_delta(const std::array<double, kComponents> &left,
                 const std::array<double, kComponents> &right)
{
    double result = 0.0;
    for (int index = 0; index < kComponents; ++index)
    {
        result = std::max(result, std::abs(left[index] - right[index]));
    }
    return result;
}

bool all_finite(const Contributions &values)
{
    for (const FaceForces &face : values)
    {
        for (const ForceKinds &source : face)
        {
            for (const SourceVector &kind : source)
            {
                for (const double value : kind)
                {
                    if (!std::isfinite(value))
                    {
                        return false;
                    }
                }
            }
        }
    }
    return true;
}

int nonzero_face_count(const Contributions &values)
{
    int count = 0;
    for (const FaceForces &face : values)
    {
        bool nonzero = false;
        for (const ForceKinds &source : face)
        {
            for (const SourceVector &kind : source)
            {
                for (const double value : kind)
                {
                    nonzero = nonzero || std::abs(value) > kTolerance;
                }
            }
        }
        count += nonzero ? 1 : 0;
    }
    return count;
}

std::array<int, kComponents> collision_counts(
    const Contributions &values)
{
    std::array<int, kComponents> counts{};
    for (int face = 0; face < kFaceCount; ++face)
    {
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKinds; ++kind)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    if (std::abs(values[face][source][kind][axis]) >
                        std::numeric_limits<double>::epsilon())
                    {
                        ++counts[flat_index(source, kind, axis)];
                    }
                }
            }
        }
    }
    return counts;
}

ThreadRun run_threads(const Contributions &values,
                      const std::array<double, kComponents> &oracle,
                      const int requestedThreads)
{
    ThreadRun summary;
    summary.requestedThreads = requestedThreads;
    std::array<double, kComponents> first{};
    bool haveFirst = false;

    omp_set_dynamic(0);
    for (int repeat = 0; repeat < kRepeats; ++repeat)
    {
        std::vector<std::array<double, kComponents>> threadBuffers(
            requestedThreads);
        int actualThreads = 0;
#pragma omp parallel num_threads(requestedThreads)
        {
#pragma omp single
            actualThreads = omp_get_num_threads();
#pragma omp for schedule(static)
            for (int face = 0; face < kFaceCount; ++face)
            {
                const int thread = omp_get_thread_num();
                for (int source = 0; source < kSourceCount; ++source)
                {
                    for (int kind = 0; kind < kForceKinds; ++kind)
                    {
                        for (int axis = 0; axis < kAxes; ++axis)
                        {
                            threadBuffers[thread][flat_index(
                                source, kind, axis)] +=
                                values[face][source][kind][axis];
                        }
                    }
                }
            }
        }
        summary.actualThreads[repeat] = actualThreads;
        summary.passed =
            summary.passed && actualThreads == requestedThreads;

        std::array<double, kComponents> reduced{};
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKinds; ++kind)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    const int index = flat_index(source, kind, axis);
                    for (int thread = 0; thread < actualThreads; ++thread)
                    {
                        reduced[index] += threadBuffers[thread][index];
                    }
                }
            }
        }
        for (const double value : reduced)
        {
            summary.finite = summary.finite && std::isfinite(value);
        }
        summary.maxOracleDelta =
            std::max(summary.maxOracleDelta, max_delta(reduced, oracle));
        if (!haveFirst)
        {
            first = reduced;
            haveFirst = true;
        }
        else
        {
            summary.maxRepeatDelta =
                std::max(summary.maxRepeatDelta, max_delta(reduced, first));
        }
    }
    summary.passed =
        summary.passed && summary.finite &&
        summary.maxOracleDelta <= kTolerance &&
        summary.maxRepeatDelta <= kTolerance;
    return summary;
}

bool exact_layout_oracle_passed()
{
    Contributions sentinels{};
    std::array<double, kComponents> expected{};
    for (int face = 0; face < kFaceCount; ++face)
    {
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKinds; ++kind)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    const double sentinel =
                        1000000.0 * face + 10000.0 * (kind + 1) +
                        100.0 * source + axis + 1.0;
                    sentinels[face][source][kind][axis] = sentinel;

                    // This expected destination intentionally does not use
                    // flat_index(), which belongs to the shadow path.
                    const int expectedDestination =
                        source * (kForceKinds * kAxes) +
                        kind * kAxes + axis;
                    expected[expectedDestination] += sentinel;
                }
            }
        }
    }

    const ThreadRun sentinelRun = run_threads(sentinels, expected, 3);
    return sentinelRun.passed && sentinelRun.maxOracleDelta == 0.0 &&
           sentinelRun.maxRepeatDelta == 0.0;
}

void print_int_array(const std::vector<int> &values)
{
    std::cout << '[';
    for (std::size_t index = 0; index < values.size(); ++index)
    {
        if (index != 0)
        {
            std::cout << ',';
        }
        std::cout << values[index];
    }
    std::cout << ']';
}

void print_thread_run(const ThreadRun &run)
{
    std::cout << "{\"requested_threads\":" << run.requestedThreads;
    std::cout << ",\"actual_threads\":[";
    for (int repeat = 0; repeat < kRepeats; ++repeat)
    {
        if (repeat != 0)
        {
            std::cout << ',';
        }
        std::cout << run.actualThreads[repeat];
    }
    std::cout << "]";
    std::cout << ",\"repeat_count\":" << kRepeats;
    std::cout << ",\"max_abs_oracle_difference\":"
              << run.maxOracleDelta;
    std::cout << ",\"max_abs_repeat_difference\":"
              << run.maxRepeatDelta;
    std::cout << ",\"finite\":" << (run.finite ? "true" : "false");
    std::cout << ",\"passed\":" << (run.passed ? "true" : "false");
    std::cout << '}';
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: shadow vertices.csv faces.csv contributions.txt\n";
        return 2;
    }

    Contributions contributions{};
    if (!read_contributions(argv[3], contributions))
    {
        std::cerr << "failed to read canonical face-force contributions\n";
        return 3;
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
    const auto verticesData = read_data_from_csv<double>(argv[1]);
    const auto facesData = read_data_from_csv<int>(argv[2]);
    Mesh mesh(param);
    {
        ScopedCoutSilencer silence;
        mesh.setup_from_vertices_faces(verticesData, facesData);
    }

    bool coordinatesMatch = mesh.vertices.size() == verticesData.size();
    for (std::size_t vertex = 0;
         coordinatesMatch && vertex < verticesData.size();
         ++vertex)
    {
        coordinatesMatch =
            mesh.vertices[vertex].index == static_cast<int>(vertex);
        for (int axis = 0; coordinatesMatch && axis < kAxes; ++axis)
        {
            coordinatesMatch =
                mesh.vertices[vertex].coord(axis, 0) ==
                verticesData[vertex][axis];
        }
    }
    bool connectivityMatches = mesh.faces.size() == facesData.size();
    bool allPhysical = connectivityMatches;
    bool productionOneRingsEmpty = connectivityMatches;
    for (std::size_t face = 0;
         connectivityMatches && face < facesData.size();
         ++face)
    {
        connectivityMatches =
            mesh.faces[face].index == static_cast<int>(face) &&
            mesh.faces[face].adjacentVertices == facesData[face];
        allPhysical =
            allPhysical && !mesh.faces[face].isGhost &&
            !mesh.faces[face].isBoundary;
        productionOneRingsEmpty =
            productionOneRingsEmpty &&
            mesh.faces[face].oneRingVertices.empty();
    }
    bool allValenceFour = mesh.vertices.size() == kSourceCount;
    for (const Vertex &vertex : mesh.vertices)
    {
        allValenceFour =
            allValenceFour && vertex.adjacentVertices.size() == 4;
    }
    const bool topologyIdentity =
        mesh.vertices.size() == kSourceCount &&
        mesh.faces.size() == kFaceCount &&
        coordinatesMatch && connectivityMatches &&
        allPhysical && allValenceFour;

    const Oracle sourceKeyedOracle = accumulate_oracle(contributions);
    const std::array<double, kComponents> flattenedOracle =
        flatten_oracle(sourceKeyedOracle);
    const std::array<int, kComponents> collisions =
        collision_counts(contributions);
    std::vector<int> uncoveredSlots;
    std::vector<int> singleContributionSlots;
    std::vector<int> unexpectedCollisionCountSlots;
    for (int index = 0; index < kComponents; ++index)
    {
        if (collisions[index] == 0)
        {
            uncoveredSlots.push_back(index);
        }
        else if (collisions[index] == 1)
        {
            singleContributionSlots.push_back(index);
        }
        if (collisions[index] != kFaceCount)
        {
            unexpectedCollisionCountSlots.push_back(index);
        }
    }

    const std::array<int, 5> requested{{1, 2, 3, 4, 8}};
    std::array<ThreadRun, requested.size()> runs;
    bool openMpPassed = true;
    for (std::size_t index = 0; index < requested.size(); ++index)
    {
        runs[index] =
            run_threads(contributions, flattenedOracle, requested[index]);
        openMpPassed = openMpPassed && runs[index].passed;
    }

    const bool finite = all_finite(contributions);
    const int contributingFaces = nonzero_face_count(contributions);
    const bool collisionCoverage = unexpectedCollisionCountSlots.empty();
    const bool layoutOraclePassed = exact_layout_oracle_passed();
    const bool passed =
        topologyIdentity && productionOneRingsEmpty &&
        layoutOraclePassed && finite &&
        contributingFaces == kFaceCount &&
        collisionCoverage && openMpPassed;

    std::cout << std::setprecision(17);
    std::cout << '{';
    std::cout << "\"kind\":\"proof_only_valence4_production_call_openmp_shadow\",";
    std::cout << "\"proof_only\":true,";
    std::cout << "\"production_call_shadow\":true,";
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"production_route_enabled\":false,";
    std::cout << "\"actual_production_force_path_executed\":false,";
    std::cout << "\"actual_openmp_runtime\":true,";
    std::cout << "\"omp_dynamic\":false,";
    std::cout << "\"fixture\":\"closed_valence4_octahedron\",";
    std::cout << "\"vertex_count\":" << mesh.vertices.size() << ',';
    std::cout << "\"face_count\":" << mesh.faces.size() << ',';
    std::cout << "\"all_valence_four\":"
              << (allValenceFour ? "true" : "false") << ',';
    std::cout << "\"all_faces_physical\":"
              << (allPhysical ? "true" : "false") << ',';
    std::cout << "\"coordinates_match_fixture\":"
              << (coordinatesMatch ? "true" : "false") << ',';
    std::cout << "\"oriented_connectivity_matches_fixture\":"
              << (connectivityMatches ? "true" : "false") << ',';
    std::cout << "\"production_topology_identity_passed\":"
              << (topologyIdentity ? "true" : "false") << ',';
    std::cout << "\"production_one_ring_count\":0,";
    std::cout << "\"production_one_rings_populated\":false,";
    std::cout << "\"production_one_rings_expected_empty\":"
              << (productionOneRingsEmpty ? "true" : "false") << ',';
    std::cout << "\"proposed_source_mapping_scope\":"
                 "\"proof-local original fixture source ids 0..5\",";
    std::cout << "\"force_buffer_shape\":\"6 sources x 9 components\",";
    std::cout << "\"total_force_components\":" << kComponents << ',';
    std::cout << "\"independent_exact_index_layout_oracle_passed\":"
              << (layoutOraclePassed ? "true" : "false") << ',';
    std::cout << "\"independent_accumulator\":"
                 "\"long double source-kind-axis before flattening\",";
    std::cout << "\"face_contribution_count\":" << kFaceCount << ',';
    std::cout << "\"nonzero_face_contribution_count\":"
              << contributingFaces << ',';
    std::cout << "\"all_face_contributions_finite\":"
              << (finite ? "true" : "false") << ',';
    std::cout << "\"collision_counts\":[";
    for (int index = 0; index < kComponents; ++index)
    {
        if (index != 0)
        {
            std::cout << ',';
        }
        std::cout << collisions[index];
    }
    std::cout << "],\"uncovered_component_slots\":";
    print_int_array(uncoveredSlots);
    std::cout << ",\"single_contribution_component_slots\":";
    print_int_array(singleContributionSlots);
    std::cout << ",\"unexpected_collision_count_component_slots\":";
    print_int_array(unexpectedCollisionCountSlots);
    std::cout << ",\"expected_collision_count_per_component\":"
              << kFaceCount;
    std::cout << ",\"collision_coverage_passed\":"
              << (collisionCoverage ? "true" : "false") << ',';
    std::cout << "\"absolute_tolerance\":" << kTolerance << ',';
    std::cout << "\"reduction_order\":"
                 "\"source, force kind, axis, ascending thread index\",";
    std::cout << "\"schedule\":\"static\",";
    std::cout << "\"thread_runs\":[";
    for (std::size_t index = 0; index < runs.size(); ++index)
    {
        if (index != 0)
        {
            std::cout << ',';
        }
        print_thread_run(runs[index]);
    }
    std::cout << "],\"actual_openmp_runtime_parity_passed\":"
              << (openMpPassed ? "true" : "false") << ',';
    std::cout << "\"passed\":" << (passed ? "true" : "false");
    std::cout << "}\n";
    return passed ? 0 : 1;
}
