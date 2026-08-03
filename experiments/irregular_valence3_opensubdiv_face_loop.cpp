#include "energy_force/Valence3_opensubdiv_face_loop.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
using slimed::opensubdiv_valence3_phase3::Valence3Phase3Request;
using slimed::opensubdiv_valence3_phase3::Valence3Phase3Result;
using slimed::opensubdiv_valence3_phase3::
    evaluate_guarded_valence3_phase3_face_loop;

void append_matrix(std::vector<double> &values, const Matrix &matrix)
{
    values.push_back(matrix.mat == nullptr ? 0.0 : 1.0);
    if (matrix.mat == nullptr)
    {
        return;
    }
    values.push_back(matrix.nrow());
    values.push_back(matrix.ncol());
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        for (int column = 0; column < matrix.ncol(); ++column)
        {
            values.push_back(matrix.get(row, column));
        }
    }
}

std::array<const Matrix *, 8> force_terms(const Force &force)
{
    return {{
        &force.forceCurvature,
        &force.forceArea,
        &force.forceVolume,
        &force.forceThickness,
        &force.forceTilt,
        &force.forceRegularization,
        &force.forceHarmonicBond,
        &force.forceTotal,
    }};
}

std::array<double, 10> energy_values(const Energy &energy)
{
    return {{
        energy.energyCurvature,
        energy.energyArea,
        energy.energyVolume,
        energy.energyThickness,
        energy.energyTilt,
        energy.energyRegularization,
        energy.energyHarmonicBond,
        energy.energyGagScaffolding,
        energy.energyIdealizedProteinLattice,
        energy.energyTotal,
    }};
}

std::vector<double> mesh_state(const Mesh &mesh)
{
    std::vector<double> values{mesh.param.area, mesh.param.vol};
    const auto globalEnergy = energy_values(mesh.param.energy);
    values.insert(values.end(), globalEnergy.begin(), globalEnergy.end());
    for (const Vertex &vertex : mesh.vertices)
    {
        values.push_back(vertex.index);
        append_matrix(values, vertex.coord);
        append_matrix(values, vertex.coordRef);
        for (const Matrix *force : force_terms(vertex.force))
        {
            append_matrix(values, *force);
        }
    }
    for (const Face &face : mesh.faces)
    {
        values.push_back(face.index);
        values.push_back(face.elementArea);
        values.push_back(face.elementVolume);
        values.push_back(face.meanCurvature);
        append_matrix(values, face.normVector);
        const auto faceEnergy = energy_values(face.energy);
        values.insert(values.end(), faceEnergy.begin(), faceEnergy.end());
    }
    return values;
}

std::vector<std::vector<int>> one_rings(const Mesh &mesh)
{
    std::vector<std::vector<int>> rings;
    rings.reserve(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        rings.push_back(face.oneRingVertices);
    }
    return rings;
}

void configure_fixture(Mesh &mesh,
                       const std::vector<std::vector<double>> &vertices,
                       const std::vector<std::vector<int>> &faces,
                       const bool perturb)
{
    mesh.setup_from_vertices_faces(vertices, faces);
    if (perturb)
    {
        mesh.vertices[0].coord.set(
            0, 0, mesh.vertices[0].coord.get(0, 0) + 0.071);
        mesh.vertices[0].coord.set(
            1, 0, mesh.vertices[0].coord.get(1, 0) - 0.043);
        mesh.vertices[0].coord.set(
            2, 0, mesh.vertices[0].coord.get(2, 0) + 0.029);
    }
    mesh.update_previous_coord_for_vertex();
    mesh.update_reference_coord_from_previous_coord();
    mesh.param.area = 0.0;
    mesh.param.vol = 0.0;
    for (const Face &face : mesh.faces)
    {
        std::array<std::array<double, 3>, 3> point{};
        for (int corner = 0; corner < 3; ++corner)
        {
            const Matrix &coordinate =
                mesh.vertices[face.adjacentVertices[corner]].coord;
            for (int axis = 0; axis < 3; ++axis)
            {
                point[corner][axis] = coordinate.get(axis, 0);
            }
        }
        std::array<double, 3> first{};
        std::array<double, 3> second{};
        for (int axis = 0; axis < 3; ++axis)
        {
            first[axis] = point[1][axis] - point[0][axis];
            second[axis] = point[2][axis] - point[0][axis];
        }
        const std::array<double, 3> areaVector{{
            first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0],
        }};
        mesh.param.area += 0.5 * std::sqrt(
            areaVector[0] * areaVector[0] +
            areaVector[1] * areaVector[1] +
            areaVector[2] * areaVector[2]);
        mesh.param.vol += point[0][0] * areaVector[0] / 6.0;
    }
    mesh.param.area0 = 0.91 * mesh.param.area;
    mesh.param.vol0 = mesh.param.vol == 0.0 ? 1.0 : 0.89 * mesh.param.vol;
}

bool all_volume_forces_zero(const Mesh &mesh)
{
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            if (vertex.force.forceVolume.get(axis, 0) != 0.0)
            {
                return false;
            }
        }
    }
    return true;
}

bool state_changed(const std::vector<double> &before, const Mesh &mesh)
{
    return before != mesh_state(mesh);
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 5)
    {
        std::cerr << "usage: valence3_phase3 TETRA_VERTICES TETRA_FACES "
                     "MIXED_VERTICES MIXED_FACES\n";
        return 2;
    }

    const auto tetraVertices = read_data_from_csv<double>(argv[1]);
    const auto tetraFaces = read_data_from_csv<int>(argv[2]);
    const auto mixedVertices = read_data_from_csv<double>(argv[3]);
    const auto mixedFaces = read_data_from_csv<int>(argv[4]);

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 0.0;
    Mesh mesh(param);
    configure_fixture(mesh, tetraVertices, tetraFaces, true);

    Param fallbackParam;
    fallbackParam.VERBOSE_MODE = false;
    fallbackParam.boundaryCondition = BoundaryType::Fixed;
    fallbackParam.kCurv = 47.5;
    fallbackParam.uSurf = 130.0;
    fallbackParam.uVol = 0.0;
    Mesh fallbackMesh(fallbackParam);
    configure_fixture(fallbackMesh, tetraVertices, tetraFaces, true);
    const std::vector<double> fallbackInitial = mesh_state(fallbackMesh);
    bool defaultEvaluatorStillUnsupported = false;
    try
    {
        fallbackMesh.Compute_Energy_And_Force();
    }
    catch (const std::runtime_error &error)
    {
        defaultEvaluatorStillUnsupported =
            std::string(error.what()).find("Unsupported membrane") !=
                std::string::npos &&
            fallbackInitial == mesh_state(fallbackMesh);
    }

    const std::vector<double> initial = mesh_state(mesh);
    const auto initialOneRings = one_rings(mesh);
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3");
    const Valence3Phase3Result missingExplicit =
        evaluate_guarded_valence3_phase3_face_loop(mesh, {});
    Valence3Phase3Request request;
    request.scientificBaselineAcceptedExplicitRequest = true;
    const Valence3Phase3Result missingRuntime =
        evaluate_guarded_valence3_phase3_face_loop(mesh, request);
    setenv("SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3", "true", 1);
    const Valence3Phase3Result invalidRuntime =
        evaluate_guarded_valence3_phase3_face_loop(mesh, request);
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3");
    const bool defaultOffAtomic =
        !missingExplicit.accepted && !missingRuntime.accepted &&
        !invalidRuntime.accepted &&
        mesh_state(mesh) == initial && one_rings(mesh) == initialOneRings;

    Param volumeParam;
    volumeParam.VERBOSE_MODE = false;
    volumeParam.boundaryCondition = BoundaryType::Fixed;
    volumeParam.kCurv = 47.5;
    volumeParam.uSurf = 130.0;
    volumeParam.uVol = 65.0;
    Mesh volumeMesh(volumeParam);
    configure_fixture(volumeMesh, tetraVertices, tetraFaces, true);
    const std::vector<double> volumeInitial = mesh_state(volumeMesh);

    Param mixedParam;
    mixedParam.VERBOSE_MODE = false;
    mixedParam.boundaryCondition = BoundaryType::Fixed;
    mixedParam.kCurv = 47.5;
    mixedParam.uSurf = 130.0;
    mixedParam.uVol = 0.0;
    Mesh mixedMesh(mixedParam);
    configure_fixture(mixedMesh, mixedVertices, mixedFaces, false);
    const std::vector<double> mixedInitial = mesh_state(mixedMesh);

    setenv("SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3", "1", 1);
    const Valence3Phase3Result volumeRejected =
        evaluate_guarded_valence3_phase3_face_loop(volumeMesh, request);
    const Valence3Phase3Result mixedRejected =
        evaluate_guarded_valence3_phase3_face_loop(mixedMesh, request);
    const Valence3Phase3Result result =
        evaluate_guarded_valence3_phase3_face_loop(mesh, request);

    const bool volumeRejectionAtomic =
        !volumeRejected.accepted &&
        volumeInitial == mesh_state(volumeMesh) &&
        volumeRejected.rejectionReason.find("nonzero volume") !=
            std::string::npos;
    const bool mixedRejectionAtomic =
        !mixedRejected.accepted && mixedInitial == mesh_state(mixedMesh) &&
        !mixedRejected.rowProvider.accepted;

    if (!result.rowProvider.opensubdivCompiled)
    {
        const bool passed = defaultEvaluatorStillUnsupported &&
            defaultOffAtomic && volumeRejectionAtomic &&
            mixedRejectionAtomic && !result.accepted &&
            mesh_state(mesh) == initial &&
            one_rings(mesh) == initialOneRings &&
            !result.actualProductionForcePathExecuted &&
            !result.productionFaceLoopExecuted &&
            !result.productionRouteEnabled &&
            !result.defaultEvaluatorCaller &&
            !result.phase4ActivationAuthorized;
        std::cout << "{\"status\":\""
                  << (passed ? "passed" : "failed")
                  << "\",\"dependency_disabled_contract_passed\":"
                  << (passed ? "true" : "false")
                  << ",\"production_route_enabled\":false}"
                  << '\n';
        return passed ? 0 : 3;
    }

    const bool oneRingsPreserved = one_rings(mesh) == initialOneRings;
    const bool passed = defaultEvaluatorStillUnsupported &&
        defaultOffAtomic && volumeRejectionAtomic &&
        mixedRejectionAtomic && result.accepted &&
        result.explicitRequestReceived && result.runtimeOptInRequested &&
        result.exactBaselineIdentityValidated &&
        result.exactQuadratureSamplePlanValidated &&
        result.exactQuadratureWeightsValidated &&
        result.zeroVolumeConstraintValidated &&
        result.volumeFunctionalDecisionPending &&
        result.sourceKeyedRowsPrepared && result.geometryStaged &&
        result.scientificDryRunExecuted &&
        result.completeTransactionValidatedBeforeMutation &&
        result.actualProductionForcePathExecuted &&
        result.productionFaceLoopExecuted && result.outputStateFinite &&
        result.faceObservablesMatchDryRun &&
        result.sourceForcesMatchDryRun &&
        result.totalArea > 0.0 && state_changed(initial, mesh) &&
        oneRingsPreserved && all_volume_forces_zero(mesh) &&
        !result.productionRouteEnabled &&
        !result.productionOneRingsPopulated &&
        !result.defaultEvaluatorCaller &&
        !result.phase4ActivationAuthorized;

    std::cout << std::setprecision(17)
              << "{\"status\":\"" << (passed ? "passed" : "failed")
              << "\",\"phase3_integration_only\":true"
              << ",\"default_evaluator_still_unsupported\":"
              << (defaultEvaluatorStillUnsupported ? "true" : "false")
              << ",\"default_off_rejections_atomic\":"
              << (defaultOffAtomic ? "true" : "false")
              << ",\"nonzero_volume_rejection_atomic\":"
              << (volumeRejectionAtomic ? "true" : "false")
              << ",\"mixed_345_rejection_atomic\":"
              << (mixedRejectionAtomic ? "true" : "false")
              << ",\"exact_baseline_identity_validated\":"
              << (result.exactBaselineIdentityValidated ? "true" : "false")
              << ",\"complete_transaction_validated_before_mutation\":"
              << (result.completeTransactionValidatedBeforeMutation
                      ? "true" : "false")
              << ",\"production_face_loop_executed\":"
              << (result.productionFaceLoopExecuted ? "true" : "false")
              << ",\"production_one_rings_preserved\":"
              << (oneRingsPreserved ? "true" : "false")
              << ",\"zero_volume_force_verified\":"
              << (all_volume_forces_zero(mesh) ? "true" : "false")
              << ",\"volume_functional_decision_pending\":true"
              << ",\"face_observable_dry_run_max_abs_difference\":"
              << result.maxFaceObservableDifference
              << ",\"source_force_dry_run_max_abs_difference\":"
              << result.maxSourceForceDifference
              << ",\"total_area\":" << result.totalArea
              << ",\"total_legacy_volume\":"
              << result.totalLegacyVolume
              << ",\"production_route_enabled\":false"
              << ",\"default_evaluator_caller\":false"
              << ",\"phase4_activation_authorized\":false}"
              << '\n';
    return passed ? 0 : 4;
}
