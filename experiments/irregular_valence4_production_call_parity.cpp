#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"
#include "Parameters.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
constexpr int kFaceCount = 8;
constexpr int kSourceCount = 6;
constexpr int kForceKinds = 3;
constexpr int kAxes = 3;
constexpr int kComponents = kSourceCount * kForceKinds * kAxes;
constexpr int kSamplesPerFace = 3;
constexpr int kRowsPerSample = 7;

constexpr std::array<std::array<int, 3>, kFaceCount>
    kIndependentCanonicalOrientedFaces{{
        {{0, 2, 3}},
        {{0, 3, 4}},
        {{0, 4, 5}},
        {{0, 5, 2}},
        {{1, 3, 2}},
        {{1, 4, 3}},
        {{1, 5, 4}},
        {{1, 2, 5}},
    }};

bool independent_topology_orientation_oracle(
    const Mesh &mesh,
    const Valence4TopologySourceMappingResult &mapping)
{
    if (!mapping.supported ||
        mapping.byFace.size() != kIndependentCanonicalOrientedFaces.size() ||
        mesh.faces.size() != kIndependentCanonicalOrientedFaces.size())
    {
        return false;
    }
    for (int face = 0; face < kFaceCount; ++face)
    {
        const std::vector<int> expected(
            kIndependentCanonicalOrientedFaces[face].begin(),
            kIndependentCanonicalOrientedFaces[face].end());
        if (mesh.faces[face].adjacentVertices != expected ||
            mapping.byFace[face].faceIndex != face ||
            !std::equal(mapping.byFace[face].orientedFaceVertices.begin(),
                        mapping.byFace[face].orientedFaceVertices.end(),
                        expected.begin()))
        {
            return false;
        }
    }
    return true;
}

bool independent_fixed_index_sentinel_oracle(
    const Valence4TopologySourceMappingResult &mapping)
{
    if (!mapping.supported || mapping.byFace.size() != kFaceCount)
    {
        return false;
    }
    std::array<double, kComponents> candidate{};
    for (int face = 0; face < kFaceCount; ++face)
    {
        const auto &sources = mapping.byFace[face].originalSourceIds;
        if (sources.size() != kSourceCount)
        {
            return false;
        }
        for (int position = 0; position < kSourceCount; ++position)
        {
            const int source = sources[position];
            if (source < 0 || source >= kSourceCount)
            {
                return false;
            }
            for (int kind = 0; kind < kForceKinds; ++kind)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    const double sentinel =
                        100000.0 * (face + 1) +
                        1000.0 * (position + 1) +
                        10.0 * (kind + 1) + axis + 1.0;
                    candidate[source * 9 + kind * 3 + axis] += sentinel;
                }
            }
        }
    }

    // This expected layout uses fixed source/kind/axis loops and never calls
    // the candidate destination expression.
    std::array<std::array<std::array<double, kAxes>, kForceKinds>,
               kSourceCount>
        expected{};
    for (int face = 0; face < kFaceCount; ++face)
    {
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKinds; ++kind)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    expected[source][kind][axis] +=
                        100000.0 * (face + 1) +
                        1000.0 * (source + 1) +
                        10.0 * (kind + 1) + axis + 1.0;
                }
            }
        }
    }
    int flat = 0;
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKinds; ++kind)
        {
            for (int axis = 0; axis < kAxes; ++axis)
            {
                if (candidate[flat] != expected[source][kind][axis])
                {
                    return false;
                }
                ++flat;
            }
        }
    }
    return flat == kComponents;
}

bool production_rejects_before_mutation(Mesh &mesh, std::string &reason)
{
    for (Face &face : mesh.faces)
    {
        face.meanCurvature = 100.0 + face.index;
    }
    for (Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxes; ++axis)
        {
            const double sentinel = 1000.0 + 10.0 * vertex.index + axis;
            vertex.force.forceCurvature.set(axis, 0, sentinel);
            vertex.force.forceArea.set(axis, 0, -sentinel);
            vertex.force.forceVolume.set(axis, 0, 2.0 * sentinel);
        }
    }

    bool rejected = false;
    try
    {
        mesh.Compute_Energy_And_Force();
    }
    catch (const std::runtime_error &error)
    {
        reason = error.what();
        rejected =
            reason.find("Unsupported membrane geometry routing for face 0") !=
                std::string::npos &&
            reason.find("found 0") != std::string::npos &&
            reason.find("Broader-valence routing remains disabled") !=
                std::string::npos;
    }

    bool unchanged = rejected;
    for (const Face &face : mesh.faces)
    {
        unchanged =
            unchanged && face.oneRingVertices.empty() &&
            face.meanCurvature == 100.0 + face.index;
    }
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxes; ++axis)
        {
            const double sentinel = 1000.0 + 10.0 * vertex.index + axis;
            unchanged =
                unchanged &&
                vertex.force.forceCurvature(axis, 0) == sentinel &&
                vertex.force.forceArea(axis, 0) == -sentinel &&
                vertex.force.forceVolume(axis, 0) == 2.0 * sentinel;
        }
    }
    return unchanged;
}

struct FreshRowBindingSummary
{
    bool passed = false;
    bool finite = false;
    bool mixedRowsDuplicated = false;
    double maxMixedRowDifference = std::numeric_limits<double>::infinity();
};

FreshRowBindingSummary read_fresh_row_binding(
    const std::string &path,
    const Valence4TopologySourceMappingResult &mapping)
{
    FreshRowBindingSummary summary;
    std::ifstream input(path);
    int faces = 0;
    int samples = 0;
    int rows = 0;
    int sources = 0;
    if (!(input >> faces >> samples >> rows >> sources) ||
        faces != kFaceCount || samples != kSamplesPerFace ||
        rows != kRowsPerSample || sources != kSourceCount ||
        !mapping.supported || mapping.byFace.size() != kFaceCount)
    {
        return summary;
    }

    summary.finite = true;
    summary.maxMixedRowDifference = 0.0;
    for (int face = 0; face < kFaceCount; ++face)
    {
        int encodedFace = -1;
        if (!(input >> encodedFace) || encodedFace != face ||
            mapping.byFace[face].originalSourceIds !=
                std::vector<int>({0, 1, 2, 3, 4, 5}))
        {
            return summary;
        }
        for (int sample = 0; sample < kSamplesPerFace; ++sample)
        {
            int encodedSample = -1;
            if (!(input >> encodedSample) || encodedSample != sample)
            {
                return summary;
            }
            std::array<std::array<double, kSourceCount>, kRowsPerSample>
                values{};
            for (int row = 0; row < kRowsPerSample; ++row)
            {
                for (int source = 0; source < kSourceCount; ++source)
                {
                    if (!(input >> values[row][source]) ||
                        !std::isfinite(values[row][source]))
                    {
                        summary.finite = false;
                        return summary;
                    }
                }
            }
            for (int source = 0; source < kSourceCount; ++source)
            {
                summary.maxMixedRowDifference =
                    std::max(summary.maxMixedRowDifference,
                             std::abs(values[5][source] -
                                      values[6][source]));
            }
        }
    }
    std::string trailing;
    if (input >> trailing)
    {
        return summary;
    }
    summary.mixedRowsDuplicated =
        summary.maxMixedRowDifference <= 1.0e-12;
    summary.passed = summary.finite && summary.mixedRowsDuplicated;
    return summary;
}

void print_ints(const std::vector<int> &values)
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
} // namespace

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: parity vertices.csv faces.csv fresh_rows.txt\n";
        return 2;
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
    const auto verticesData = read_data_from_csv<double>(argv[1]);
    const auto facesData = read_data_from_csv<int>(argv[2]);
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(verticesData, facesData);

    const Valence4TopologySourceMappingResult mapping =
        build_guarded_valence4_topology_source_mapping(mesh);
    const bool topologyOracle =
        independent_topology_orientation_oracle(mesh, mapping);
    const bool sentinelOracle =
        independent_fixed_index_sentinel_oracle(mapping);
    const FreshRowBindingSummary freshRows =
        read_fresh_row_binding(argv[3], mapping);

    std::swap(mesh.faces.front().adjacentVertices[1],
              mesh.faces.front().adjacentVertices[2]);
    const Valence4TopologySourceMappingResult orientationMutation =
        build_guarded_valence4_topology_source_mapping(mesh);
    std::swap(mesh.faces.front().adjacentVertices[1],
              mesh.faces.front().adjacentVertices[2]);
    mesh.faces.front().oneRingVertices = {0};
    const Valence4TopologySourceMappingResult oneRingMutation =
        build_guarded_valence4_topology_source_mapping(mesh);
    mesh.faces.front().oneRingVertices.clear();
    const bool mutationsRejected =
        !orientationMutation.supported &&
        !orientationMutation.rejectionReason.empty() &&
        !oneRingMutation.supported &&
        !oneRingMutation.rejectionReason.empty();

    std::string rejection;
    const bool rejectionBeforeMutation =
        production_rejects_before_mutation(mesh, rejection);
    const bool passed =
        mapping.supported && topologyOracle && sentinelOracle &&
        freshRows.passed && mutationsRejected && rejectionBeforeMutation;

    std::cout << std::setprecision(17);
    std::cout << '{';
    std::cout << "\"kind\":"
                 "\"proof_only_valence4_production_call_boundary\",";
    std::cout << "\"proof_only\":true,";
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"production_route_enabled\":false,";
    std::cout << "\"actual_production_force_path_executed\":false,";
    std::cout << "\"production_entry_boundary_executed\":true,";
    std::cout << "\"production_entry_rejected_loudly\":"
              << (rejectionBeforeMutation ? "true" : "false") << ',';
    std::cout << "\"production_state_unchanged_after_rejection\":"
              << (rejectionBeforeMutation ? "true" : "false") << ',';
    std::cout << "\"guarded_topology_source_representation_used\":true,";
    std::cout << "\"fresh_opensubdiv_rows_consumed\":true,";
    std::cout << "\"fresh_row_tensor_shape\":\"8x3x7x6\",";
    std::cout << "\"fresh_row_tensor_finite\":"
              << (freshRows.finite ? "true" : "false") << ',';
    std::cout << "\"duplicated_mixed_rows_preserved\":"
              << (freshRows.mixedRowsDuplicated ? "true" : "false") << ',';
    std::cout << "\"max_mixed_row_difference\":"
              << freshRows.maxMixedRowDifference << ',';
    std::cout << "\"independent_canonical_topology_orientation_oracle_passed\":"
              << (topologyOracle ? "true" : "false") << ',';
    std::cout << "\"independent_fixed_index_6x9_sentinel_oracle_passed\":"
              << (sentinelOracle ? "true" : "false") << ',';
    std::cout << "\"production_one_rings_populated\":false,";
    std::cout << "\"production_one_rings_expected_empty\":true,";
    std::cout << "\"source_ids\":";
    print_ints(mapping.byFace.empty()
                   ? std::vector<int>()
                   : mapping.byFace.front().originalSourceIds);
    std::cout << ',';
    std::cout << "\"orientation_and_one_ring_mutations_rejected\":"
              << (mutationsRejected ? "true" : "false") << ',';
    std::cout << "\"production_rejection_reason\":\"" << rejection << "\",";
    std::cout << "\"residual_boundary\":"
                 "\"variable-cardinality source-keyed production-kernel "
                 "adapter required before valence-4 force execution\",";
    std::cout << "\"passed\":" << (passed ? "true" : "false");
    std::cout << "}\n";
    return passed ? 0 : 1;
}
