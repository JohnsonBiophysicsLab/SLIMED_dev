#include "irregular_valence4_source_keyed_kernel_adapter.hpp"

#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"
#include "Parameters.hpp"

#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
using namespace valence4_source_keyed_proof;

constexpr int kFaceCount = 8;
constexpr int kSourceCount = 6;
constexpr int kSampleCount = 3;
constexpr double kTolerance = 1.0e-12;

using IndependentOracle =
    std::array<std::array<std::array<long double, kAxisCount>,
                          kForceKindCount>,
               kSourceCount>;

struct InputPackage
{
    std::vector<SourceKeyedFaceRows> rows;
    std::vector<SourceKeyedFaceForces> forces;
};

bool read_package(const std::string &path, InputPackage &package)
{
    std::ifstream input(path);
    int faces = 0;
    int samples = 0;
    int rows = 0;
    int sources = 0;
    if (!(input >> faces >> samples >> rows >> sources) ||
        faces != kFaceCount || samples != kSampleCount ||
        rows != kDerivativeRowCount || sources != kSourceCount)
    {
        return false;
    }

    package.rows.resize(kFaceCount);
    package.forces.resize(kFaceCount);
    for (int face = 0; face < kFaceCount; ++face)
    {
        int encodedFace = -1;
        if (!(input >> encodedFace) || encodedFace != face)
        {
            return false;
        }
        SourceKeyedFaceRows &faceRows = package.rows[face];
        faceRows.faceIndex = face;
        for (int corner = 0; corner < 3; ++corner)
        {
            if (!(input >> faceRows.orientedFaceVertices[corner]))
            {
                return false;
            }
        }
        faceRows.samples.resize(kSampleCount);
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            int encodedSample = -1;
            if (!(input >> encodedSample) || encodedSample != sample)
            {
                return false;
            }
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                SourceKeyedRow &target =
                    faceRows.samples[sample].rows[row];
                target.sourceIds.resize(kSourceCount);
                target.coefficients.resize(kSourceCount);
                for (int source = 0; source < kSourceCount; ++source)
                {
                    if (!(input >> target.sourceIds[source] >>
                          target.coefficients[source]))
                    {
                        return false;
                    }
                }
            }
        }

        SourceKeyedFaceForces &faceForces = package.forces[face];
        faceForces.faceIndex = face;
        faceForces.sourceIds.resize(kSourceCount);
        faceForces.forces.resize(kSourceCount);
        for (int source = 0; source < kSourceCount; ++source)
        {
            if (!(input >> faceForces.sourceIds[source]))
            {
                return false;
            }
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    if (!(input >>
                          faceForces.forces[source][kind][axis]))
                    {
                        return false;
                    }
                }
            }
        }
    }
    double trailing = 0.0;
    return !(input >> trailing);
}

std::vector<SourceMappingView> mapping_views(
    const Mesh &mesh,
    const Valence4TopologySourceMappingResult &mapping)
{
    std::vector<SourceMappingView> views;
    if (!mapping.supported || mapping.byFace.size() != mesh.faces.size())
    {
        return views;
    }
    views.reserve(mapping.byFace.size());
    for (std::size_t face = 0; face < mapping.byFace.size(); ++face)
    {
        views.push_back(SourceMappingView{
            mapping.byFace[face].faceIndex,
            mapping.byFace[face].orientedFaceVertices,
            mapping.byFace[face].originalSourceIds,
            mesh.faces[face].oneRingVertices.empty()});
    }
    return views;
}

IndependentOracle independent_scatter_oracle(
    const InputPackage &package)
{
    IndependentOracle oracle{};
    for (int face = 0; face < kFaceCount; ++face)
    {
        std::array<bool, kSourceCount> seen{};
        const SourceKeyedFaceForces &faceForces = package.forces[face];
        if (faceForces.sourceIds.size() != faceForces.forces.size())
        {
            throw std::invalid_argument(
                "independent oracle rejected force cardinality drift");
        }
        for (std::size_t position = 0;
             position < faceForces.sourceIds.size();
             ++position)
        {
            const int sourceId = faceForces.sourceIds[position];
            if (sourceId < 0 || sourceId >= kSourceCount ||
                seen[sourceId])
            {
                throw std::invalid_argument(
                    "independent oracle rejected invalid source-key binding");
            }
            seen[sourceId] = true;
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    oracle[sourceId][kind][axis] +=
                        static_cast<long double>(
                            faceForces.forces[position][kind][axis]);
                }
            }
        }
        if (!std::all_of(seen.begin(), seen.end(), [](bool value) {
                return value;
            }))
        {
            throw std::invalid_argument(
                "independent oracle rejected incomplete source coverage");
        }
    }
    return oracle;
}

double compare_with_independent_oracle(
    const std::vector<SourceForceKinds> &candidate,
    const IndependentOracle &oracle)
{
    if (candidate.size() != kSourceCount)
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                maximum = std::max(
                    maximum,
                    std::abs(candidate[source][kind][axis] -
                             static_cast<double>(
                                 oracle[source][kind][axis])));
            }
        }
    }
    return maximum;
}

double compare_adapted_inputs(const AdaptedKernelInput &candidate,
                              const AdaptedKernelInput &reference)
{
    if (candidate.sourceCount != reference.sourceCount ||
        candidate.faces.size() != reference.faces.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (std::size_t face = 0; face < reference.faces.size(); ++face)
    {
        const AdaptedFaceKernelInput &actual = candidate.faces[face];
        const AdaptedFaceKernelInput &expected = reference.faces[face];
        if (actual.mapping.faceIndex != expected.mapping.faceIndex ||
            actual.mapping.orientedFaceVertices !=
                expected.mapping.orientedFaceVertices ||
            actual.mapping.originalSourceIds !=
                expected.mapping.originalSourceIds ||
            actual.samples.size() != expected.samples.size() ||
            actual.forces.size() != expected.forces.size())
        {
            return std::numeric_limits<double>::infinity();
        }
        for (std::size_t sample = 0; sample < expected.samples.size();
             ++sample)
        {
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                const SourceKeyedRow &actualRow =
                    actual.samples[sample].rows[row];
                const SourceKeyedRow &expectedRow =
                    expected.samples[sample].rows[row];
                if (actualRow.sourceIds != expectedRow.sourceIds ||
                    actualRow.coefficients.size() !=
                        expectedRow.coefficients.size())
                {
                    return std::numeric_limits<double>::infinity();
                }
                for (std::size_t source = 0;
                     source < expectedRow.coefficients.size();
                     ++source)
                {
                    maximum = std::max(
                        maximum,
                        std::abs(actualRow.coefficients[source] -
                                 expectedRow.coefficients[source]));
                }
            }
        }
        for (std::size_t source = 0; source < expected.forces.size();
             ++source)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    maximum = std::max(
                        maximum,
                        std::abs(actual.forces[source][kind][axis] -
                                 expected.forces[source][kind][axis]));
                }
            }
        }
    }
    return maximum;
}

double compare_scattered(const std::vector<SourceForceKinds> &candidate,
                         const std::vector<SourceForceKinds> &reference)
{
    if (candidate.size() != reference.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (std::size_t source = 0; source < reference.size(); ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                maximum = std::max(
                    maximum,
                    std::abs(candidate[source][kind][axis] -
                             reference[source][kind][axis]));
            }
        }
    }
    return maximum;
}

InputPackage permuted_bindings(const InputPackage &package)
{
    InputPackage permuted = package;
    for (SourceKeyedFaceRows &faceRows : permuted.rows)
    {
        for (SourceKeyedSampleRows &sample : faceRows.samples)
        {
            for (SourceKeyedRow &row : sample.rows)
            {
                std::reverse(row.sourceIds.begin(), row.sourceIds.end());
                std::reverse(row.coefficients.begin(),
                             row.coefficients.end());
            }
        }
    }
    for (SourceKeyedFaceForces &faceForces : permuted.forces)
    {
        std::reverse(faceForces.sourceIds.begin(),
                     faceForces.sourceIds.end());
        std::reverse(faceForces.forces.begin(), faceForces.forces.end());
    }
    return permuted;
}

InputPackage split_duplicate_rows(const InputPackage &package)
{
    InputPackage duplicated = package;
    for (SourceKeyedFaceRows &faceRows : duplicated.rows)
    {
        for (SourceKeyedSampleRows &sample : faceRows.samples)
        {
            for (SourceKeyedRow &row : sample.rows)
            {
                const int sourceId = row.sourceIds.front();
                const double half = std::ldexp(
                    row.coefficients.front(), -1);
                row.coefficients.front() = half;
                row.sourceIds.push_back(sourceId);
                row.coefficients.push_back(half);
                std::reverse(row.sourceIds.begin(), row.sourceIds.end());
                std::reverse(row.coefficients.begin(),
                             row.coefficients.end());
            }
        }
    }
    return duplicated;
}

template <typename Mutation>
bool rejected(Mutation mutation,
              const std::vector<SourceMappingView> &baseMappings,
              const InputPackage &basePackage)
{
    std::vector<SourceMappingView> mappings = baseMappings;
    InputPackage package = basePackage;
    mutation(mappings, package);
    try
    {
        (void)adapt_source_keyed_kernel_input(
            kSourceCount, mappings, package.rows, package.forces);
    }
    catch (const std::invalid_argument &)
    {
        return true;
    }
    return false;
}

bool all_production_one_rings_empty(const Mesh &mesh)
{
    return std::all_of(
        mesh.faces.begin(), mesh.faces.end(), [](const Face &face) {
            return face.oneRingVertices.empty();
        });
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: adapter vertices.csv faces.csv package.txt\n";
        return 2;
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(read_data_from_csv<double>(argv[1]),
                                   read_data_from_csv<int>(argv[2]));

    const Valence4TopologySourceMappingResult guardedMapping =
        build_guarded_valence4_topology_source_mapping(mesh);
    const std::vector<SourceMappingView> mappings =
        mapping_views(mesh, guardedMapping);
    InputPackage package;
    if (mappings.size() != kFaceCount ||
        !read_package(argv[3], package))
    {
        std::cerr << "failed to read source-keyed proof package\n";
        return 1;
    }

    const AdaptedKernelInput adapted =
        adapt_source_keyed_kernel_input(
            kSourceCount, mappings, package.rows, package.forces);
    const std::vector<SourceForceKinds> scattered =
        scatter_by_original_source_id(adapted);
    const IndependentOracle oracle = independent_scatter_oracle(package);
    const double maxOracleDelta =
        compare_with_independent_oracle(scattered, oracle);

    const InputPackage permutedPackage = permuted_bindings(package);
    const AdaptedKernelInput permutedAdapted =
        adapt_source_keyed_kernel_input(
            kSourceCount,
            mappings,
            permutedPackage.rows,
            permutedPackage.forces);
    const std::vector<SourceForceKinds> permutedScattered =
        scatter_by_original_source_id(permutedAdapted);
    const IndependentOracle permutedOracle =
        independent_scatter_oracle(permutedPackage);
    const double maxPermutationAdaptedDelta =
        compare_adapted_inputs(permutedAdapted, adapted);
    const double maxPermutationScatterDelta =
        compare_scattered(permutedScattered, scattered);
    const double maxPermutationOracleDelta =
        compare_with_independent_oracle(permutedScattered,
                                        permutedOracle);

    const InputPackage duplicatedPackage =
        split_duplicate_rows(permutedPackage);
    const AdaptedKernelInput duplicatedAdapted =
        adapt_source_keyed_kernel_input(
            kSourceCount,
            mappings,
            duplicatedPackage.rows,
            duplicatedPackage.forces);
    const std::vector<SourceForceKinds> duplicatedScattered =
        scatter_by_original_source_id(duplicatedAdapted);
    const double maxDuplicateAggregationDelta =
        compare_adapted_inputs(duplicatedAdapted, adapted);
    const double maxDuplicateScatterDelta =
        compare_scattered(duplicatedScattered, scattered);

    const bool outOfRangeRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].sourceIds[0] = -1;
        },
        mappings,
        package);
    const bool cardinalityRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].coefficients.pop_back();
        },
        mappings,
        package);
    const bool incompleteRowCoverageRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].sourceIds.pop_back();
            input.rows[0].samples[0].rows[0].coefficients.pop_back();
        },
        mappings,
        package);
    const bool forceDuplicateRejected = rejected(
        [](auto &, auto &input) {
            input.forces[0].sourceIds[1] =
                input.forces[0].sourceIds[0];
        },
        mappings,
        package);
    const bool nonfiniteRowRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].coefficients[0] =
                std::numeric_limits<double>::infinity();
        },
        mappings,
        package);
    const bool nonfiniteForceRejected = rejected(
        [](auto &, auto &input) {
            input.forces[0].forces[0][0][0] =
                std::numeric_limits<double>::quiet_NaN();
        },
        mappings,
        package);
    const bool orientationRejected = rejected(
        [](auto &, auto &input) {
            std::swap(input.rows[0].orientedFaceVertices[1],
                      input.rows[0].orientedFaceVertices[2]);
        },
        mappings,
        package);
    const bool mappingDriftRejected = rejected(
        [](auto &views, auto &) {
            views[0].originalSourceIds[0] =
                views[0].originalSourceIds[1];
        },
        mappings,
        package);
    const bool nonemptyOneRingRejected = rejected(
        [](auto &views, auto &) {
            views[0].productionOneRingEmpty = false;
        },
        mappings,
        package);
    const bool mixedRowRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[6].coefficients[0] +=
                1.0e-4;
        },
        mappings,
        package);

    const bool productionOneRingsEmpty =
        all_production_one_rings_empty(mesh);
    const bool permutationInvariant =
        maxPermutationAdaptedDelta <= kTolerance &&
        maxPermutationScatterDelta <= kTolerance &&
        maxPermutationOracleDelta <= kTolerance;
    const bool duplicateRowsAggregated =
        maxDuplicateAggregationDelta <= kTolerance &&
        maxDuplicateScatterDelta <= kTolerance;
    const bool negativeGatesPassed =
        outOfRangeRejected && cardinalityRejected &&
        incompleteRowCoverageRejected && forceDuplicateRejected &&
        nonfiniteRowRejected && nonfiniteForceRejected &&
        orientationRejected && mappingDriftRejected &&
        nonemptyOneRingRejected && mixedRowRejected;
    const bool passed =
        adapted.faces.size() == kFaceCount &&
        adapted.sourceCount == kSourceCount &&
        maxOracleDelta <= kTolerance && productionOneRingsEmpty &&
        permutationInvariant && duplicateRowsAggregated &&
        negativeGatesPassed;

    std::cout << std::setprecision(17);
    std::cout << '{';
    std::cout << "\"kind\":\"proof_only_valence4_source_keyed_kernel_adapter\",";
    std::cout << "\"proof_only\":true,";
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"production_route_enabled\":false,";
    std::cout << "\"actual_production_force_path_executed\":false,";
    std::cout << "\"backend_neutral_adapter_api\":true,";
    std::cout << "\"guarded_topology_source_mapping_consumed\":true,";
    std::cout << "\"proof_provided_opensubdiv_rows_consumed\":true,";
    std::cout << "\"existing_force_algebra_contributions_consumed\":true,";
    std::cout << "\"variable_cardinality_source_keyed\":true,";
    std::cout << "\"canonicalized_by_original_source_id\":true,";
    std::cout << "\"face_count\":" << adapted.faces.size() << ',';
    std::cout << "\"source_count\":" << adapted.sourceCount << ',';
    std::cout << "\"sample_count_per_face\":3,";
    std::cout << "\"row_count_per_sample\":7,";
    std::cout << "\"force_component_layout\":\"6 sources x 3 force kinds x 3 axes\",";
    std::cout << "\"independent_fixed_source_layout_oracle_passed\":"
              << (maxOracleDelta <= kTolerance ? "true" : "false") << ',';
    std::cout << "\"max_scatter_oracle_delta\":"
              << maxOracleDelta << ',';
    std::cout << "\"source_binding_permutation_invariant\":"
              << (permutationInvariant ? "true" : "false") << ',';
    std::cout << "\"permuted_row_columns_canonicalized\":"
              << (maxPermutationAdaptedDelta <= kTolerance ? "true" : "false")
              << ',';
    std::cout << "\"permuted_force_columns_canonicalized\":"
              << (maxPermutationScatterDelta <= kTolerance ? "true" : "false")
              << ',';
    std::cout << "\"independent_permuted_scatter_oracle_passed\":"
              << (maxPermutationOracleDelta <= kTolerance ? "true" : "false")
              << ',';
    std::cout << "\"max_permutation_adapted_delta\":"
              << maxPermutationAdaptedDelta << ',';
    std::cout << "\"max_permutation_scatter_delta\":"
              << maxPermutationScatterDelta << ',';
    std::cout << "\"max_permutation_oracle_delta\":"
              << maxPermutationOracleDelta << ',';
    std::cout << "\"duplicate_row_entries_aggregated_by_source_id\":"
              << (duplicateRowsAggregated ? "true" : "false") << ',';
    std::cout << "\"max_duplicate_row_aggregation_delta\":"
              << maxDuplicateAggregationDelta << ',';
    std::cout << "\"max_duplicate_row_scatter_delta\":"
              << maxDuplicateScatterDelta << ',';
    std::cout << "\"production_one_rings_empty\":"
              << (productionOneRingsEmpty ? "true" : "false") << ',';
    std::cout << "\"production_one_rings_mutated\":false,";
    std::cout << "\"negative_gates\":{";
    std::cout << "\"out_of_range_source_id\":"
              << (outOfRangeRejected ? "true" : "false") << ',';
    std::cout << "\"inconsistent_row_cardinality\":"
              << (cardinalityRejected ? "true" : "false") << ',';
    std::cout << "\"incomplete_row_source_coverage\":"
              << (incompleteRowCoverageRejected ? "true" : "false") << ',';
    std::cout << "\"duplicate_force_source_id\":"
              << (forceDuplicateRejected ? "true" : "false") << ',';
    std::cout << "\"nonfinite_row_data\":"
              << (nonfiniteRowRejected ? "true" : "false") << ',';
    std::cout << "\"nonfinite_force_data\":"
              << (nonfiniteForceRejected ? "true" : "false") << ',';
    std::cout << "\"orientation_drift\":"
              << (orientationRejected ? "true" : "false") << ',';
    std::cout << "\"mapping_drift\":"
              << (mappingDriftRejected ? "true" : "false") << ',';
    std::cout << "\"nonempty_production_one_ring\":"
              << (nonemptyOneRingRejected ? "true" : "false") << ',';
    std::cout << "\"mixed_row_drift\":"
              << (mixedRowRejected ? "true" : "false") << ',';
    std::cout << "\"all_passed\":"
              << (negativeGatesPassed ? "true" : "false") << "},";
    std::cout << "\"residual_boundary\":"
                 "\"production valence-4 kernel call integration and "
                 "serial/OpenMP observable parity remain separately reviewed "
                 "work\",";
    std::cout << "\"passed\":" << (passed ? "true" : "false");
    std::cout << "}\n";
    return passed ? 0 : 1;
}
