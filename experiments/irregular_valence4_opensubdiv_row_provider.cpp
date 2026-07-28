#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_valence4_row_provider.hpp"

#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>

using slimed::opensubdiv_valence4::
    OpenSubdivValence4RowProviderRequest;
using slimed::opensubdiv_valence4::
    OpenSubdivValence4RowProviderResult;
using slimed::opensubdiv_valence4::
    build_guarded_opensubdiv_valence4_rows;
using namespace slimed::source_keyed_kernel;

namespace
{
bool package_is_complete(
    const OpenSubdivValence4RowProviderResult &result)
{
    if (result.rows.size() != 8u)
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
                if (row.sourceIds !=
                        std::vector<int>({0, 1, 2, 3, 4, 5}) ||
                    row.coefficients.size() != 6u)
                {
                    return false;
                }
                for (const double coefficient : row.coefficients)
                {
                    if (!std::isfinite(coefficient))
                    {
                        return false;
                    }
                }
            }
            if (sample.rows[5].coefficients !=
                sample.rows[6].coefficients)
            {
                return false;
            }
        }
    }
    return true;
}

void print_rows(
    const std::vector<SourceKeyedFaceRows> &faces)
{
    std::cout << "[";
    for (std::size_t face = 0; face < faces.size(); ++face)
    {
        if (face > 0)
        {
            std::cout << ",";
        }
        const SourceKeyedFaceRows &faceRows = faces[face];
        std::cout << "{\"face\":" << faceRows.faceIndex
                  << ",\"oriented_face_vertices\":["
                  << faceRows.orientedFaceVertices[0] << ","
                  << faceRows.orientedFaceVertices[1] << ","
                  << faceRows.orientedFaceVertices[2]
                  << "],\"samples\":[";
        for (std::size_t sample = 0;
             sample < faceRows.samples.size();
             ++sample)
        {
            if (sample > 0)
            {
                std::cout << ",";
            }
            std::cout << "{\"sample\":" << sample << ",\"rows\":[";
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                if (row > 0)
                {
                    std::cout << ",";
                }
                std::cout << "[";
                const SourceKeyedRow &sourceRow =
                    faceRows.samples[sample].rows[row];
                for (std::size_t source = 0;
                     source < sourceRow.coefficients.size();
                     ++source)
                {
                    if (source > 0)
                    {
                        std::cout << ",";
                    }
                    std::cout << sourceRow.coefficients[source];
                }
                std::cout << "]";
            }
            std::cout << "]}";
        }
        std::cout << "]}";
    }
    std::cout << "]";
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 3)
    {
        std::cerr << "usage: " << argv[0]
                  << " VERTICES.csv FACES.csv\n";
        return 2;
    }

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(
        read_data_from_csv<double>(argv[1]),
        read_data_from_csv<int>(argv[2]));

    const OpenSubdivValence4RowProviderResult defaultOff =
        build_guarded_opensubdiv_valence4_rows(mesh, {});
    OpenSubdivValence4RowProviderRequest request;
    request.reviewerApprovedExplicitRequest = true;
    const OpenSubdivValence4RowProviderResult generated =
        build_guarded_opensubdiv_valence4_rows(mesh, request);

    bool oneRingsEmpty = true;
    for (const Face &face : mesh.faces)
    {
        oneRingsEmpty =
            oneRingsEmpty && face.oneRingVertices.empty();
    }
    const bool passed =
        !defaultOff.accepted && defaultOff.rows.empty() &&
        generated.accepted && generated.opensubdivCompiled &&
        generated.topologySourceMappingValidated &&
        generated.ptexFaceIdentityValidated &&
        generated.exactSamplePlanValidated &&
        generated.exactSourceCoverageValidated &&
        generated.doublePrecisionRowsGenerated &&
        generated.constantFieldInvariantsValidated &&
        generated.mixedDerivativeRowsDuplicated &&
        generated.rowsGenerated &&
        package_is_complete(generated) && oneRingsEmpty &&
        !generated.productionRouteEnabled &&
        !generated.actualProductionForcePathExecuted &&
        !generated.productionFaceLoopExecuted &&
        !generated.productionOneRingsPopulated &&
        !generated.defaultEvaluatorCaller;

    std::cout << std::setprecision(17);
    std::cout << "{\"kind\":\"guarded_production_opensubdiv_"
                 "valence4_row_provider\"";
    std::cout << ",\"provider_passed\":"
              << (passed ? "true" : "false");
    std::cout << ",\"default_off_request_rejected\":"
              << (!defaultOff.accepted ? "true" : "false");
    std::cout << ",\"opensubdiv_compiled\":"
              << (generated.opensubdivCompiled ? "true" : "false");
    std::cout << ",\"explicit_request_accepted\":"
              << (generated.accepted ? "true" : "false");
    std::cout << ",\"topology_source_mapping_validated\":"
              << (generated.topologySourceMappingValidated
                      ? "true"
                      : "false");
    std::cout << ",\"ptex_face_identity_validated\":"
              << (generated.ptexFaceIdentityValidated
                      ? "true"
                      : "false");
    std::cout << ",\"exact_sample_plan_validated\":"
              << (generated.exactSamplePlanValidated
                      ? "true"
                      : "false");
    std::cout << ",\"exact_source_coverage_validated\":"
              << (generated.exactSourceCoverageValidated
                      ? "true"
                      : "false");
    std::cout << ",\"double_precision_rows_generated\":"
              << (generated.doublePrecisionRowsGenerated
                      ? "true"
                      : "false");
    std::cout << ",\"constant_field_invariants_validated\":"
              << (generated.constantFieldInvariantsValidated
                      ? "true"
                      : "false");
    std::cout << ",\"mixed_derivative_rows_duplicated\":"
              << (generated.mixedDerivativeRowsDuplicated
                      ? "true"
                      : "false");
    std::cout << ",\"production_one_rings_empty\":"
              << (oneRingsEmpty ? "true" : "false");
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_route_enabled\":false";
    std::cout << ",\"actual_production_force_path_executed\":false";
    std::cout << ",\"production_face_loop_executed\":false";
    std::cout << ",\"rows\":";
    print_rows(generated.rows);
    std::cout << ",\"passed\":"
              << (passed ? "true" : "false") << "}\n";
    return passed ? 0 : 1;
}
