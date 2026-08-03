#include "energy_force/Valence3_opensubdiv_face_loop.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "model/Model.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
using slimed::opensubdiv_valence3_phase3::Valence3Phase3Request;
using slimed::opensubdiv_valence3_phase3::Valence3Phase3Result;
using slimed::opensubdiv_valence3_phase3::
    evaluate_guarded_valence3_phase3_face_loop;
using slimed::opensubdiv_valence3_phase3::
    evaluate_guarded_valence3_opensubdiv_production_route;

class ScopedCoutSilence
{
public:
    ScopedCoutSilence() : previous_(std::cout.rdbuf(sink_.rdbuf())) {}
    ~ScopedCoutSilence() { std::cout.rdbuf(previous_); }

    ScopedCoutSilence(const ScopedCoutSilence &) = delete;
    ScopedCoutSilence &operator=(const ScopedCoutSilence &) = delete;

private:
    std::ostringstream sink_;
    std::streambuf *previous_;
};

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
        mesh.param.vol +=
            (point[0][0] * areaVector[0] +
             point[0][1] * areaVector[1] +
             point[0][2] * areaVector[2]) / 6.0;
    }
    mesh.param.area0 = 0.91 * mesh.param.area;
    mesh.param.vol0 = mesh.param.vol == 0.0 ? 1.0 : 0.89 * mesh.param.vol;
}

bool has_nonzero_volume_force(const Mesh &mesh)
{
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            if (std::abs(vertex.force.forceVolume.get(axis, 0)) > 1.0e-12)
            {
                return true;
            }
        }
    }
    return false;
}

bool state_changed(const std::vector<double> &before, const Mesh &mesh)
{
    return before != mesh_state(mesh);
}

double maximum_state_difference(const std::vector<double> &left,
                                const std::vector<double> &right)
{
    if (left.size() != right.size())
    {
        return INFINITY;
    }
    double maximum = 0.0;
    for (std::size_t index = 0; index < left.size(); ++index)
    {
        maximum = std::max(maximum, std::abs(left[index] - right[index]));
    }
    return maximum;
}

bool verify_output_and_checkpoint_round_trip(
    Mesh &mesh,
    const Param &fixtureParam,
    const std::vector<std::vector<double>> &vertices,
    const std::vector<std::vector<int>> &faces)
{
    ScopedCoutSilence silence;
    Record record(1);
    record.add(mesh.param.area, mesh.param.energy, mesh.calculate_mean_force());
    Model model(mesh, record);
    const auto nonce = std::chrono::steady_clock::now()
        .time_since_epoch().count();
    const std::filesystem::path directory =
        std::filesystem::temp_directory_path();
    const std::filesystem::path energyPath = directory /
        ("slimed_valence3_phase4_energy_" + std::to_string(nonce) + ".csv");
    const std::filesystem::path facePath = directory /
        ("slimed_valence3_phase4_faces_" + std::to_string(nonce) + ".csv");
    const std::filesystem::path checkpointPath = directory /
        ("slimed_valence3_phase4_restart_" + std::to_string(nonce) + ".chk");

    bool passed = write_energy_force_data_to_csv(model, energyPath.string()) &&
        write_element_face_energy_to_csv(model, facePath.string()) &&
        write_model_restart_checkpoint(model, checkpointPath.string(), 1) &&
        std::filesystem::file_size(energyPath) > 0 &&
        std::filesystem::file_size(facePath) > 0;

    Param restartParam = fixtureParam;
    Mesh restartMesh(restartParam);
    configure_fixture(restartMesh, vertices, faces, true);
    Record restartRecord(1);
    Model restartModel(restartMesh, restartRecord);
    passed = passed &&
        load_model_restart_checkpoint(restartModel, checkpointPath.string()) &&
        maximum_state_difference(
            mesh_state(model.mesh), mesh_state(restartModel.mesh)) <=
            slimed::opensubdiv_valence3_phase3::
                kReviewedPostconditionTolerance;

    std::error_code ignored;
    std::filesystem::remove(energyPath, ignored);
    std::filesystem::remove(facePath, ignored);
    std::filesystem::remove(checkpointPath, ignored);
    return passed;
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

    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE3");
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3");
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE4");
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE5");

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    Mesh mesh(param);
    configure_fixture(mesh, tetraVertices, tetraFaces, true);

    Param fallbackParam;
    fallbackParam.VERBOSE_MODE = false;
    fallbackParam.boundaryCondition = BoundaryType::Fixed;
    fallbackParam.kCurv = 47.5;
    fallbackParam.uSurf = 130.0;
    fallbackParam.uVol = 65.0;
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
    const Valence3Phase3Result mixedRejected =
        evaluate_guarded_valence3_phase3_face_loop(mixedMesh, request);
    setenv("SLIMED_USE_OPENSUBDIV_REGULAR", "1", 1);
    const auto uncachedStart = std::chrono::steady_clock::now();
    const Valence3Phase3Result result =
        evaluate_guarded_valence3_phase3_face_loop(mesh, request);
    const auto uncachedEnd = std::chrono::steady_clock::now();
    unsetenv("SLIMED_USE_OPENSUBDIV_REGULAR");
    const bool unrelatedRegularTokenIsolated = result.accepted;

    const bool mixedRejectionAtomic =
        !mixedRejected.accepted && mixedInitial == mesh_state(mixedMesh) &&
        !mixedRejected.rowProvider.accepted;

    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3");
    Param productionParam = param;
    Mesh productionMesh(productionParam);
    configure_fixture(productionMesh, tetraVertices, tetraFaces, true);
    const std::vector<double> productionInitial = mesh_state(productionMesh);
    Mesh productionWrapperDefaultOff(productionParam);
    configure_fixture(
        productionWrapperDefaultOff, tetraVertices, tetraFaces, true);
    const std::vector<double> productionWrapperDefaultOffInitial =
        mesh_state(productionWrapperDefaultOff);
    const Valence3Phase3Result productionWrapperMissingGate =
        evaluate_guarded_valence3_opensubdiv_production_route(
            productionWrapperDefaultOff);
    const bool productionWrapperDefaultOffAtomic =
        !productionWrapperMissingGate.accepted &&
        mesh_state(productionWrapperDefaultOff) ==
            productionWrapperDefaultOffInitial;
    setenv("SLIMED_USE_OPENSUBDIV_VALENCE3", "1", 1);
    bool dependencyDisabledProductionRejectedAtomically = false;
    if (!result.rowProvider.opensubdivCompiled)
    {
        try
        {
            productionMesh.Compute_Energy_And_Force();
        }
        catch (const std::runtime_error &error)
        {
            dependencyDisabledProductionRejectedAtomically =
                std::string(error.what()).find("OpenSubdiv-enabled") !=
                    std::string::npos &&
                mesh_state(productionMesh) == productionInitial;
        }
    }

    if (!result.rowProvider.opensubdivCompiled)
    {
        const bool passed = defaultEvaluatorStillUnsupported &&
            defaultOffAtomic &&
            mixedRejectionAtomic && !unrelatedRegularTokenIsolated &&
            !result.accepted &&
            mesh_state(mesh) == initial &&
            one_rings(mesh) == initialOneRings &&
            !result.actualProductionForcePathExecuted &&
            !result.productionFaceLoopExecuted &&
            !result.productionRouteEnabled &&
            !result.defaultEvaluatorCaller &&
            !result.phase4ActivationAuthorized &&
            dependencyDisabledProductionRejectedAtomically &&
            productionWrapperDefaultOffAtomic;
        std::cout << "{\"status\":\""
                  << (passed ? "passed" : "failed")
                  << "\",\"dependency_disabled_contract_passed\":"
                  << (passed ? "true" : "false")
                  << ",\"production_route_enabled\":false}"
                  << '\n';
        return passed ? 0 : 3;
    }

    const auto cachedStart = std::chrono::steady_clock::now();
    productionMesh.Compute_Energy_And_Force();
    const auto cachedEnd = std::chrono::steady_clock::now();
    const std::vector<double> productionFirst = mesh_state(productionMesh);
    productionMesh.Compute_Energy_And_Force();
    const double repeatedProductionMaxAbsDifference =
        maximum_state_difference(productionFirst, mesh_state(productionMesh));
    const bool repeatedProductionDeterministic =
        repeatedProductionMaxAbsDifference <=
        slimed::opensubdiv_valence3_phase3::kReviewedPostconditionTolerance;

    Mesh wrapperMesh(productionParam);
    configure_fixture(wrapperMesh, tetraVertices, tetraFaces, true);
    const Valence3Phase3Result productionResult =
        evaluate_guarded_valence3_opensubdiv_production_route(wrapperMesh);

    const std::vector<double> mixedProductionInitial = mesh_state(mixedMesh);
    bool mixedProductionRejectedAtomically = false;
    try
    {
        mixedMesh.Compute_Energy_And_Force();
    }
    catch (const std::runtime_error &)
    {
        mixedProductionRejectedAtomically =
            mesh_state(mixedMesh) == mixedProductionInitial;
    }

    Mesh conflictMesh(productionParam);
    configure_fixture(conflictMesh, tetraVertices, tetraFaces, true);
    const std::vector<double> conflictInitial = mesh_state(conflictMesh);
    setenv("SLIMED_USE_OPENSUBDIV_VALENCE4", "1", 1);
    setenv("SLIMED_USE_OPENSUBDIV_VALENCE5", "1", 1);
    bool conflictingRoutesRejectedAtomically = false;
    try
    {
        conflictMesh.Compute_Energy_And_Force();
    }
    catch (const std::runtime_error &error)
    {
        conflictingRoutesRejectedAtomically =
            std::string(error.what()).find("exactly one") !=
                std::string::npos &&
            mesh_state(conflictMesh) == conflictInitial;
    }
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE4");
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE5");
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE3");

    const auto uncachedMicroseconds =
        std::chrono::duration_cast<std::chrono::microseconds>(
            uncachedEnd - uncachedStart).count();
    const auto cachedMicroseconds =
        std::chrono::duration_cast<std::chrono::microseconds>(
            cachedEnd - cachedStart).count();
    const bool immutableRowCacheValidated =
        result.rowProvider.immutableRowCachePopulated &&
        !result.rowProvider.immutableRowCacheHit &&
        productionResult.rowProvider.immutableRowCacheHit;
    const bool outputCheckpointRoundTripValidated =
        verify_output_and_checkpoint_round_trip(
            productionMesh, productionParam, tetraVertices, tetraFaces);
    const bool productionActivationValidated =
        state_changed(productionInitial, productionMesh) &&
        repeatedProductionDeterministic &&
        productionWrapperDefaultOffAtomic &&
        mixedProductionRejectedAtomically &&
        conflictingRoutesRejectedAtomically &&
        productionResult.accepted &&
        productionResult.productionRouteEnabled &&
        productionResult.defaultEvaluatorCaller &&
        productionResult.phase4ActivationAuthorized &&
        immutableRowCacheValidated && outputCheckpointRoundTripValidated;

    const bool oneRingsPreserved = one_rings(mesh) == initialOneRings;
    const bool passed = defaultEvaluatorStillUnsupported &&
        defaultOffAtomic &&
        mixedRejectionAtomic && unrelatedRegularTokenIsolated &&
        result.accepted &&
        result.explicitRequestReceived && result.runtimeOptInRequested &&
        result.exactBaselineIdentityValidated &&
        result.exactQuadratureSamplePlanValidated &&
        result.exactQuadratureWeightsValidated &&
        result.fullDivergenceVolumeValidated &&
        !result.volumeFunctionalDecisionPending &&
        result.sourceKeyedRowsPrepared && result.geometryStaged &&
        result.scientificDryRunExecuted &&
        result.completeTransactionValidatedBeforeMutation &&
        result.actualProductionForcePathExecuted &&
        result.productionFaceLoopExecuted && result.outputStateFinite &&
        result.faceObservablesMatchDryRun &&
        result.sourceForcesMatchDryRun &&
        result.totalArea > 0.0 && state_changed(initial, mesh) &&
        oneRingsPreserved && has_nonzero_volume_force(mesh) &&
        std::abs(mesh.param.energy.energyVolume) > 1.0e-12 &&
        !result.productionRouteEnabled &&
        !result.productionOneRingsPopulated &&
        !result.defaultEvaluatorCaller &&
        !result.phase4ActivationAuthorized &&
        productionActivationValidated;

    std::cout << std::setprecision(17)
              << "{\"status\":\"" << (passed ? "passed" : "failed")
              << "\",\"phase3_integration_only\":true"
              << ",\"default_evaluator_still_unsupported\":"
              << (defaultEvaluatorStillUnsupported ? "true" : "false")
              << ",\"default_off_rejections_atomic\":"
              << (defaultOffAtomic ? "true" : "false")
              << ",\"nonzero_volume_constraint_accepted\":"
              << (result.accepted ? "true" : "false")
              << ",\"mixed_345_rejection_atomic\":"
              << (mixedRejectionAtomic ? "true" : "false")
              << ",\"unrelated_regular_token_isolated\":"
              << (unrelatedRegularTokenIsolated ? "true" : "false")
              << ",\"exact_baseline_identity_validated\":"
              << (result.exactBaselineIdentityValidated ? "true" : "false")
              << ",\"complete_transaction_validated_before_mutation\":"
              << (result.completeTransactionValidatedBeforeMutation
                      ? "true" : "false")
              << ",\"production_face_loop_executed\":"
              << (result.productionFaceLoopExecuted ? "true" : "false")
              << ",\"production_one_rings_preserved\":"
              << (oneRingsPreserved ? "true" : "false")
              << ",\"nonzero_volume_force_verified\":"
              << (has_nonzero_volume_force(mesh) ? "true" : "false")
              << ",\"full_divergence_volume_validated\":"
              << (result.fullDivergenceVolumeValidated ? "true" : "false")
              << ",\"volume_functional_decision_pending\":false"
              << ",\"face_observable_dry_run_max_abs_difference\":"
              << result.maxFaceObservableDifference
              << ",\"source_force_dry_run_max_abs_difference\":"
              << result.maxSourceForceDifference
              << ",\"total_area\":" << result.totalArea
              << ",\"total_volume\":"
              << result.totalVolume
              << ",\"production_route_enabled\":false"
              << ",\"default_evaluator_caller\":false"
              << ",\"phase4_activation_authorized\":false"
              << ",\"phase4_production_route_enabled\":"
              << (productionResult.productionRouteEnabled ? "true" : "false")
              << ",\"phase4_default_evaluator_caller\":"
              << (productionResult.defaultEvaluatorCaller ? "true" : "false")
              << ",\"phase4_activation_validated\":"
              << (productionActivationValidated ? "true" : "false")
              << ",\"production_wrapper_default_off_atomic\":"
              << (productionWrapperDefaultOffAtomic ? "true" : "false")
              << ",\"mixed_production_rejection_atomic\":"
              << (mixedProductionRejectedAtomically ? "true" : "false")
              << ",\"conflicting_routes_rejection_atomic\":"
              << (conflictingRoutesRejectedAtomically ? "true" : "false")
              << ",\"repeated_production_deterministic\":"
              << (repeatedProductionDeterministic ? "true" : "false")
              << ",\"repeated_production_max_abs_difference\":"
              << repeatedProductionMaxAbsDifference
              << ",\"immutable_row_cache_validated\":"
              << (immutableRowCacheValidated ? "true" : "false")
              << ",\"output_checkpoint_round_trip_validated\":"
              << (outputCheckpointRoundTripValidated ? "true" : "false")
              << ",\"uncached_transaction_microseconds\":"
              << uncachedMicroseconds
              << ",\"cached_transaction_microseconds\":"
              << cachedMicroseconds << "}"
              << '\n';
    return passed ? 0 : 4;
}
