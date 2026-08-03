#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_valence5_row_provider.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using slimed::opensubdiv_valence5::OpenSubdivValence5RowProviderRequest;
using slimed::opensubdiv_valence5::OpenSubdivValence5RowProviderResult;
using slimed::opensubdiv_valence5::build_guarded_opensubdiv_valence5_rows;
using namespace slimed::source_keyed_kernel;

namespace
{
using OneRings = std::vector<std::vector<int>>;

OneRings snapshot_one_rings(const Mesh &mesh)
{
    OneRings result;
    result.reserve(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        result.push_back(face.oneRingVertices);
    }
    return result;
}

bool package_is_complete(const OpenSubdivValence5RowProviderResult &result)
{
    if (result.rows.size() != 20u)
    {
        return false;
    }
    for (std::size_t face = 0; face < result.rows.size(); ++face)
    {
        const SourceKeyedFaceRows &faceRows = result.rows[face];
        if (faceRows.faceIndex != static_cast<int>(face) ||
            faceRows.samples.size() != 3u)
        {
            return false;
        }
        for (const SourceKeyedSampleRows &sample : faceRows.samples)
        {
            for (const SourceKeyedRow &row : sample.rows)
            {
                if (row.sourceIds.size() != 9u ||
                    !std::is_sorted(row.sourceIds.begin(), row.sourceIds.end()) ||
                    std::adjacent_find(row.sourceIds.begin(), row.sourceIds.end()) !=
                        row.sourceIds.end() ||
                    row.coefficients.size() != 9u ||
                    !std::all_of(
                        row.coefficients.begin(), row.coefficients.end(),
                        [](const double value) { return std::isfinite(value); }))
                {
                    return false;
                }
            }
            if (sample.rows[5].sourceIds != sample.rows[6].sourceIds ||
                sample.rows[5].coefficients != sample.rows[6].coefficients)
            {
                return false;
            }
        }
    }
    return true;
}

void print_rows(const std::vector<SourceKeyedFaceRows> &faces)
{
    std::cout << '[';
    for (std::size_t face = 0; face < faces.size(); ++face)
    {
        if (face != 0)
        {
            std::cout << ',';
        }
        const SourceKeyedFaceRows &faceRows = faces[face];
        const std::vector<int> sourceIds = faceRows.samples.empty()
            ? std::vector<int>{}
            : faceRows.samples.front().rows.front().sourceIds;
        std::cout << "{\"face\":" << faceRows.faceIndex
                  << ",\"oriented_face_vertices\":["
                  << faceRows.orientedFaceVertices[0] << ','
                  << faceRows.orientedFaceVertices[1] << ','
                  << faceRows.orientedFaceVertices[2]
                  << "],\"source_ids\":[";
        for (std::size_t source = 0; source < sourceIds.size(); ++source)
        {
            if (source != 0)
            {
                std::cout << ',';
            }
            std::cout << sourceIds[source];
        }
        std::cout << "],\"samples\":[";
        for (std::size_t sample = 0; sample < faceRows.samples.size(); ++sample)
        {
            if (sample != 0)
            {
                std::cout << ',';
            }
            std::cout << "{\"sample\":" << sample << ",\"rows\":[";
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                if (row != 0)
                {
                    std::cout << ',';
                }
                std::cout << '[';
                const std::vector<double> &coefficients =
                    faceRows.samples[sample].rows[row].coefficients;
                for (std::size_t source = 0; source < coefficients.size(); ++source)
                {
                    if (source != 0)
                    {
                        std::cout << ',';
                    }
                    std::cout << coefficients[source];
                }
                std::cout << ']';
            }
            std::cout << "]}";
        }
        std::cout << "]}";
    }
    std::cout << ']';
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 3)
    {
        std::cerr << "usage: " << argv[0] << " VERTICES.csv FACES.csv\n";
        return 2;
    }

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(
        read_data_from_csv<double>(argv[1]),
        read_data_from_csv<int>(argv[2]));
    const OneRings before = snapshot_one_rings(mesh);

    const OpenSubdivValence5RowProviderResult defaultOff =
        build_guarded_opensubdiv_valence5_rows(mesh, {});
    OpenSubdivValence5RowProviderRequest request;
    request.phase1ProviderExplicitRequest = true;
    const OpenSubdivValence5RowProviderResult generated =
        build_guarded_opensubdiv_valence5_rows(mesh, request);
    const bool oneRingsUnchanged = before == snapshot_one_rings(mesh);

    Mesh invalid(param);
    invalid.setup_from_vertices_faces(
        read_data_from_csv<double>(argv[1]),
        read_data_from_csv<int>(argv[2]));
    std::swap(invalid.faces[0].adjacentVertices[0],
              invalid.faces[0].adjacentVertices[1]);
    const OpenSubdivValence5RowProviderResult invalidResult =
        build_guarded_opensubdiv_valence5_rows(invalid, request);

    const bool dependencyDisabledContract =
        !generated.opensubdivCompiled && !generated.accepted &&
        generated.explicitRequestReceived && generated.rows.empty();
    const bool providerPassed =
        generated.opensubdivCompiled && generated.accepted &&
        generated.explicitRequestReceived &&
        generated.exactTopologyIdentityValidated &&
        generated.topologySourceMappingValidated &&
        generated.ptexFaceIdentityValidated &&
        generated.exactSamplePlanValidated &&
        generated.exactNineSourceCoverageValidated &&
        generated.doublePrecisionRowsGenerated &&
        generated.constantFieldInvariantsValidated &&
        generated.mixedDerivativeRowsDuplicated && generated.rowsGenerated &&
        package_is_complete(generated) && !invalidResult.accepted &&
        invalidResult.rows.empty() && oneRingsUnchanged &&
        !generated.productionRouteEnabled &&
        !generated.actualProductionForcePathExecuted &&
        !generated.productionFaceLoopExecuted &&
        !generated.productionMeshMutated &&
        !generated.productionOneRingsMutated &&
        !generated.defaultEvaluatorCaller;
    const bool passed =
        !defaultOff.accepted && defaultOff.rows.empty() &&
        (providerPassed || dependencyDisabledContract);

    std::cout << std::setprecision(17);
    std::cout << "{\"kind\":\"guarded_opensubdiv_valence5_phase1_row_provider\"";
    std::cout << ",\"passed\":" << (passed ? "true" : "false");
    std::cout << ",\"provider_passed\":"
              << (providerPassed ? "true" : "false");
    std::cout << ",\"dependency_disabled_contract_passed\":"
              << (dependencyDisabledContract ? "true" : "false");
    std::cout << ",\"default_off_request_rejected\":"
              << (!defaultOff.accepted ? "true" : "false");
    std::cout << ",\"opensubdiv_compiled\":"
              << (generated.opensubdivCompiled ? "true" : "false");
    std::cout << ",\"explicit_request_accepted\":"
              << (generated.accepted ? "true" : "false");
    std::cout << ",\"exact_topology_identity_validated\":"
              << (generated.exactTopologyIdentityValidated ? "true" : "false");
    std::cout << ",\"topology_source_mapping_validated\":"
              << (generated.topologySourceMappingValidated ? "true" : "false");
    std::cout << ",\"ptex_face_identity_validated\":"
              << (generated.ptexFaceIdentityValidated ? "true" : "false");
    std::cout << ",\"exact_sample_plan_validated\":"
              << (generated.exactSamplePlanValidated ? "true" : "false");
    std::cout << ",\"exact_nine_source_coverage_validated\":"
              << (generated.exactNineSourceCoverageValidated ? "true" : "false");
    std::cout << ",\"double_precision_rows_generated\":"
              << (generated.doublePrecisionRowsGenerated ? "true" : "false");
    std::cout << ",\"constant_field_invariants_validated\":"
              << (generated.constantFieldInvariantsValidated ? "true" : "false");
    std::cout << ",\"mixed_derivative_rows_duplicated\":"
              << (generated.mixedDerivativeRowsDuplicated ? "true" : "false");
    std::cout << ",\"invalid_topology_rejected\":"
              << (!invalidResult.accepted ? "true" : "false");
    std::cout << ",\"production_one_rings_unchanged\":"
              << (oneRingsUnchanged ? "true" : "false");
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_route_enabled\":false";
    std::cout << ",\"actual_production_force_path_executed\":false";
    std::cout << ",\"production_face_loop_executed\":false";
    std::cout << ",\"production_mesh_mutated\":false";
    std::cout << ",\"rows\":";
    print_rows(generated.rows);
    std::cout << "}\n";
    return passed ? 0 : 1;
}
