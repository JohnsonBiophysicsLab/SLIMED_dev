#include "energy_force/Valence4_face_loop_route_preflight.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

using namespace slimed::source_keyed_kernel;
using namespace slimed::valence4_route_preflight;

namespace
{
void seed_reference_coordinates_from_current(Mesh &mesh)
{
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.coordRef = vertex.coord;
    }
}

void seed_stale_completion_state(Mesh &mesh)
{
    for (Face &face : mesh.faces)
    {
        face.energy.energyThickness = 7000.0 + face.index;
    }
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.force.forceThickness.set_all(
            8000.0 + vertex.index);
    }
}

bool one_rings_empty(const Mesh &mesh)
{
    for (const Face &face : mesh.faces)
    {
        if (!face.oneRingVertices.empty())
        {
            return false;
        }
    }
    return true;
}

bool completion_state_is_consistent(const Mesh &mesh)
{
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            const double expectedTotal =
                vertex.force.forceCurvature.get(axis, 0) +
                vertex.force.forceArea.get(axis, 0) +
                vertex.force.forceVolume.get(axis, 0) +
                vertex.force.forceThickness.get(axis, 0) +
                vertex.force.forceTilt.get(axis, 0) +
                vertex.force.forceRegularization.get(axis, 0) +
                vertex.force.forceHarmonicBond.get(axis, 0);
            if (vertex.force.forceTotal.get(axis, 0) !=
                expectedTotal)
            {
                return false;
            }
        }
    }

    Energy expectedTotalEnergy;
    for (const Face &face : mesh.faces)
    {
        if (face.energy.energyThickness != 0.0)
        {
            return false;
        }
        Energy expectedFace = face.energy;
        expectedFace.calculateTotalEnergy();
        if (face.energy.energyTotal != expectedFace.energyTotal)
        {
            return false;
        }
        expectedTotalEnergy += face.energy;
    }
    expectedTotalEnergy.energyArea =
        0.5 * mesh.param.uSurf / mesh.param.area0 *
        std::pow(mesh.param.area - mesh.param.area0, 2.0);
    expectedTotalEnergy.energyVolume =
        0.5 * mesh.param.uVol / mesh.param.vol0 *
        std::pow(mesh.param.vol - mesh.param.vol0, 2.0);
    expectedTotalEnergy.calculateTotalEnergy();
    return mesh.param.energy.energyTotal ==
           expectedTotalEnergy.energyTotal;
}

bool force_output_is_nonzero(const Mesh &mesh)
{
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            if (std::abs(vertex.force.forceCurvature.get(axis, 0)) >
                    1.0e-12 ||
                std::abs(vertex.force.forceArea.get(axis, 0)) >
                    1.0e-12 ||
                std::abs(vertex.force.forceVolume.get(axis, 0)) >
                    1.0e-12)
            {
                return true;
            }
        }
    }
    return false;
}

void print_vector3(const Matrix &matrix)
{
    std::cout << "[";
    for (int axis = 0; axis < kAxisCount; ++axis)
    {
        if (axis > 0)
        {
            std::cout << ",";
        }
        std::cout << matrix.get(axis, 0);
    }
    std::cout << "]";
}

void print_vertex_forces(const Mesh &mesh)
{
    std::cout << "[";
    for (std::size_t source = 0; source < mesh.vertices.size();
         ++source)
    {
        if (source > 0)
        {
            std::cout << ",";
        }
        const Vertex &vertex = mesh.vertices[source];
        std::cout << "{\"source_id\":" << vertex.index
                  << ",\"fBend\":";
        print_vector3(vertex.force.forceCurvature);
        std::cout << ",\"fArea\":";
        print_vector3(vertex.force.forceArea);
        std::cout << ",\"fVolume\":";
        print_vector3(vertex.force.forceVolume);
        std::cout << ",\"fTotal\":";
        print_vector3(vertex.force.forceTotal);
        std::cout << "}";
    }
    std::cout << "]";
}

void print_face_observables(const Mesh &mesh)
{
    std::cout << "[";
    for (std::size_t faceIndex = 0; faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        if (faceIndex > 0)
        {
            std::cout << ",";
        }
        const Face &face = mesh.faces[faceIndex];
        std::cout << "{\"face\":" << face.index
                  << ",\"mean_curvature\":" << face.meanCurvature
                  << ",\"bending_energy\":"
                  << face.energy.energyCurvature
                  << ",\"area\":" << face.elementArea
                  << ",\"legacy_volume\":" << face.elementVolume
                  << ",\"normal\":";
        print_vector3(face.normVector);
        std::cout << "}";
    }
    std::cout << "]";
}

double maximum_shadow_face_loop_delta(const Mesh &shadow,
                                      const Mesh &faceLoop)
{
    double maximum = 0.0;
    const auto include = [&maximum](const double left,
                                    const double right) {
        maximum = std::max(maximum, std::abs(left - right));
    };
    include(shadow.param.area, faceLoop.param.area);
    include(shadow.param.vol, faceLoop.param.vol);
    include(shadow.param.energy.energyTotal,
            faceLoop.param.energy.energyTotal);
    for (std::size_t faceIndex = 0;
         faceIndex < shadow.faces.size();
         ++faceIndex)
    {
        const Face &left = shadow.faces[faceIndex];
        const Face &right = faceLoop.faces[faceIndex];
        include(left.elementArea, right.elementArea);
        include(left.elementVolume, right.elementVolume);
        include(left.meanCurvature, right.meanCurvature);
        include(left.energy.energyCurvature,
                right.energy.energyCurvature);
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            include(left.normVector.get(axis, 0),
                    right.normVector.get(axis, 0));
        }
    }
    for (std::size_t source = 0;
         source < shadow.vertices.size();
         ++source)
    {
        const std::array<const Matrix *, 4> left{{
            &shadow.vertices[source].force.forceCurvature,
            &shadow.vertices[source].force.forceArea,
            &shadow.vertices[source].force.forceVolume,
            &shadow.vertices[source].force.forceTotal,
        }};
        const std::array<const Matrix *, 4> right{{
            &faceLoop.vertices[source].force.forceCurvature,
            &faceLoop.vertices[source].force.forceArea,
            &faceLoop.vertices[source].force.forceVolume,
            &faceLoop.vertices[source].force.forceTotal,
        }};
        for (std::size_t family = 0; family < left.size(); ++family)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                include(left[family]->get(axis, 0),
                        right[family]->get(axis, 0));
            }
        }
    }
    return maximum;
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
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.area0 = 2.75;
    param.area = 5.5;
    param.uVol = 65.0;
    param.vol0 = 0.82;
    param.vol = 0.25;

    Mesh defaultOffMesh(param);
    defaultOffMesh.setup_from_vertices_faces(
        read_data_from_csv<double>(argv[1]),
        read_data_from_csv<int>(argv[2]));
    const Valence4OpenSubdivProductionFaceLoopCallerResult defaultOff =
        evaluate_guarded_valence4_opensubdiv_production_face_loop_caller(
            defaultOffMesh, {});

    Mesh shadowMesh(param);
    shadowMesh.setup_from_vertices_faces(
        read_data_from_csv<double>(argv[1]),
        read_data_from_csv<int>(argv[2]));
    seed_reference_coordinates_from_current(shadowMesh);
    seed_stale_completion_state(shadowMesh);
    Valence4OpenSubdivProductionCallerRequest shadowRequest;
    shadowRequest.reviewerApprovedExplicitCaller = true;
    const Valence4OpenSubdivProductionCallerResult shadow =
        evaluate_guarded_valence4_opensubdiv_production_caller(
            shadowMesh, shadowRequest);

    Mesh mesh(param);
    mesh.setup_from_vertices_faces(
        read_data_from_csv<double>(argv[1]),
        read_data_from_csv<int>(argv[2]));
    seed_reference_coordinates_from_current(mesh);
    seed_stale_completion_state(mesh);

    Valence4OpenSubdivProductionFaceLoopCallerRequest request;
    request.reviewerApprovedExplicitCaller = true;
    const Valence4OpenSubdivProductionFaceLoopCallerResult called =
        evaluate_guarded_valence4_opensubdiv_production_face_loop_caller(
            mesh, request);

    const bool oneRingsStillEmpty = one_rings_empty(mesh);
    const bool totalsConsistent = completion_state_is_consistent(mesh);
    const bool nonzeroForces = force_output_is_nonzero(mesh);
    const double shadowFaceLoopDelta =
        shadow.accepted && called.accepted
            ? maximum_shadow_face_loop_delta(shadowMesh, mesh)
            : std::numeric_limits<double>::infinity();
    const bool shadowFaceLoopParityPassed =
        shadowFaceLoopDelta <= 1.0e-12;
    const bool passed =
        !defaultOff.accepted &&
        !defaultOff.opensubdivRowProviderExecuted &&
        shadow.accepted &&
        shadow.productionCallerShadowExecuted &&
        called.accepted &&
        called.exactQuadratureSamplePlanValidated &&
        called.exactQuadratureWeightsValidated &&
        called.opensubdivRowProviderExecuted &&
        called.opensubdivRowsGenerated &&
        called.rowProvider.accepted &&
        called.rowProvider.rowsGenerated &&
        called.completeTransactionValidatedBeforeMutation &&
        called.currentStateCleared &&
        called.productionCompletionPhasesExecuted &&
        called.totalForcePublicationExecuted &&
        called.totalEnergyPublicationExecuted &&
        called.boundaryHandlingExecuted &&
        shadowFaceLoopParityPassed &&
        oneRingsStillEmpty &&
        totalsConsistent &&
        nonzeroForces &&
        !called.productionRouteEnabled &&
        called.actualProductionForcePathExecuted &&
        called.productionFaceLoopExecuted &&
        !called.productionOneRingsPopulated &&
        !called.defaultEvaluatorCaller;

    std::cout << std::setprecision(17);
    std::cout << "{\"kind\":\"guarded_valence4_opensubdiv_"
                 "production_caller\"";
    std::cout << ",\"passed\":" << (passed ? "true" : "false");
    std::cout << ",\"default_off_caller_rejected\":"
              << (!defaultOff.accepted ? "true" : "false");
    std::cout << ",\"exact_quadrature_sample_plan_validated\":"
              << (called.exactQuadratureSamplePlanValidated
                      ? "true"
                      : "false");
    std::cout << ",\"exact_quadrature_weights_validated\":"
              << (called.exactQuadratureWeightsValidated
                      ? "true"
                      : "false");
    std::cout << ",\"opensubdiv_row_provider_executed\":"
              << (called.opensubdivRowProviderExecuted ? "true" : "false");
    std::cout << ",\"opensubdiv_rows_generated\":"
              << (called.opensubdivRowsGenerated ? "true" : "false");
    std::cout << ",\"row_provider_accepted\":"
              << (called.rowProvider.accepted ? "true" : "false");
    std::cout << ",\"row_provider_rows_generated\":"
              << (called.rowProvider.rowsGenerated ? "true" : "false");
    std::cout << ",\"production_caller_shadow_executed\":"
              << (shadow.productionCallerShadowExecuted
                      ? "true"
                      : "false");
    std::cout << ",\"complete_transaction_validated_before_mutation\":"
              << (called.completeTransactionValidatedBeforeMutation
                      ? "true"
                      : "false");
    std::cout << ",\"production_completion_phases_executed\":"
              << (called.productionCompletionPhasesExecuted
                      ? "true"
                      : "false");
    std::cout << ",\"total_force_publication_executed\":"
              << (called.totalForcePublicationExecuted
                      ? "true"
                      : "false");
    std::cout << ",\"total_energy_publication_executed\":"
              << (called.totalEnergyPublicationExecuted
                      ? "true"
                      : "false");
    std::cout << ",\"boundary_handling_executed\":"
              << (called.boundaryHandlingExecuted ? "true" : "false");
    std::cout << ",\"current_state_cleared\":"
              << (called.currentStateCleared
                      ? "true"
                      : "false");
    std::cout << ",\"atomic_geometry_scientific_publication_executed\":"
              << (called.completeTransactionValidatedBeforeMutation
                      ? "true"
                      : "false");
    std::cout << ",\"production_caller_shadow_totals_consistent\":"
              << (totalsConsistent ? "true" : "false");
    std::cout << ",\"nonzero_membrane_forces\":"
              << (nonzeroForces ? "true" : "false");
    std::cout << ",\"production_one_rings_empty\":"
              << (oneRingsStillEmpty ? "true" : "false");
    std::cout << ",\"shadow_face_loop_parity_passed\":"
              << (shadowFaceLoopParityPassed ? "true" : "false");
    std::cout << ",\"max_shadow_face_loop_delta\":"
              << shadowFaceLoopDelta;
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_route_enabled\":false";
    std::cout << ",\"actual_production_force_path_executed\":true";
    std::cout << ",\"production_face_loop_executed\":true";
    std::cout << ",\"default_evaluator_caller\":false";
    std::cout << ",\"area\":" << mesh.param.area;
    std::cout << ",\"legacy_volume\":" << mesh.param.vol;
    std::cout << ",\"energy_total\":" << mesh.param.energy.energyTotal;
    std::cout << ",\"vertex_forces\":";
    print_vertex_forces(mesh);
    std::cout << ",\"face_observables\":";
    print_face_observables(mesh);
    std::cout << "}\n";
    return passed ? 0 : 1;
}
