#include "energy_force/Valence5_opensubdiv_face_loop.hpp"

#include "mesh/Mesh.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace slimed::opensubdiv_valence5_phase2
{
namespace
{
using source_keyed_kernel::PreparedSourceKeyedFace;
using source_keyed_kernel::PreparedSourceKeyedKernelCall;
using source_keyed_kernel::SourceForceKinds;
using source_keyed_kernel::SourceKeyedFaceForces;
using source_keyed_kernel::SourceKeyedKernelCallInput;
using source_keyed_kernel::SourceMappingView;
using source_keyed_kernel::Vec3;

constexpr std::size_t kReviewedSampleCount = 3;
constexpr int kReviewedQuadratureOrder = 2;
constexpr double kLegacyVolumeQuadratureFactor = 0.16666666666;
constexpr const char *kPhase2RuntimeOptIn =
    "SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2";
constexpr const char *kProductionRuntimeOptIn =
    "SLIMED_USE_OPENSUBDIV_VALENCE5";
constexpr std::array<std::array<double, 3>, kReviewedSampleCount>
    kReviewedSamples{{
        {{1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0}},
        {{1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0}},
        {{4.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0}},
    }};
constexpr std::array<double, kReviewedSampleCount> kReviewedWeights{{
    1.0 / 3.0,
    1.0 / 3.0,
    1.0 / 3.0,
}};

bool matrix_is_finite(const Matrix &matrix)
{
    if (matrix.mat == nullptr)
    {
        return false;
    }
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        for (int column = 0; column < matrix.ncol(); ++column)
        {
            if (!std::isfinite(matrix.get(row, column)))
            {
                return false;
            }
        }
    }
    return true;
}

std::vector<SourceMappingView> mappings_for_rows(
    const Mesh &mesh,
    const std::vector<source_keyed_kernel::SourceKeyedFaceRows> &rows)
{
    if (rows.size() != mesh.faces.size())
    {
        throw std::invalid_argument(
            "valence-5 Phase 2 requires complete row coverage");
    }

    std::vector<SourceMappingView> mappings;
    mappings.reserve(rows.size());
    for (std::size_t faceIndex = 0; faceIndex < rows.size(); ++faceIndex)
    {
        const auto &faceRows = rows[faceIndex];
        if (faceRows.faceIndex != static_cast<int>(faceIndex) ||
            faceRows.samples.size() != kReviewedSampleCount)
        {
            throw std::invalid_argument(
                "valence-5 Phase 2 rejected face identity or sample-count "
                "drift");
        }
        const std::vector<int> &sourceIds =
            faceRows.samples.front().rows.front().sourceIds;
        if (sourceIds.size() != 9u)
        {
            throw std::invalid_argument(
                "valence-5 Phase 2 requires exactly nine original sources "
                "per face");
        }
        SourceMappingView mapping;
        mapping.faceIndex = static_cast<int>(faceIndex);
        mapping.orientedFaceVertices = faceRows.orientedFaceVertices;
        mapping.originalSourceIds = sourceIds;
        mapping.productionOneRingEmpty =
            mesh.faces[faceIndex].oneRingVertices.empty();
        mapping.productionOneRingBypassed =
            !mapping.productionOneRingEmpty;
        mappings.push_back(std::move(mapping));
    }
    return mappings;
}

std::vector<SourceKeyedFaceForces> zero_forces_for_mappings(
    const std::vector<SourceMappingView> &mappings)
{
    std::vector<SourceKeyedFaceForces> forces;
    forces.reserve(mappings.size());
    for (const SourceMappingView &mapping : mappings)
    {
        SourceKeyedFaceForces faceForces;
        faceForces.faceIndex = mapping.faceIndex;
        faceForces.sourceIds = mapping.originalSourceIds;
        faceForces.forces.resize(mapping.originalSourceIds.size());
        forces.push_back(std::move(faceForces));
    }
    return forces;
}

std::vector<Matrix> coordinates_for_sources(
    const Mesh &mesh,
    const std::vector<int> &sourceIds)
{
    std::vector<Matrix> coordinates;
    coordinates.reserve(sourceIds.size());
    for (const int sourceId : sourceIds)
    {
        if (sourceId < 0 ||
            sourceId >= static_cast<int>(mesh.vertices.size()))
        {
            throw std::invalid_argument(
                "valence-5 Phase 2 source id is out of range");
        }
        coordinates.push_back(mesh.vertices[sourceId].coord);
    }
    return coordinates;
}

std::vector<Matrix> shape_functions_for_face(
    const PreparedSourceKeyedFace &face)
{
    const std::vector<int> &sourceIds =
        face.mapping.originalSourceIds;
    std::vector<Matrix> shapeFunctions;
    shapeFunctions.reserve(face.samples.size());
    for (const auto &sample : face.samples)
    {
        Matrix rows(source_keyed_kernel::kDerivativeRowCount,
                    static_cast<int>(sourceIds.size()),
                    true);
        for (int rowIndex = 0;
             rowIndex < source_keyed_kernel::kDerivativeRowCount;
             ++rowIndex)
        {
            const auto &row = sample.rows[rowIndex];
            if (row.sourceIds != sourceIds ||
                row.coefficients.size() != sourceIds.size())
            {
                throw std::invalid_argument(
                    "valence-5 Phase 2 rejected row/source mapping drift");
            }
            for (std::size_t source = 0; source < sourceIds.size(); ++source)
            {
                rows.set(rowIndex,
                         static_cast<int>(source),
                         row.coefficients[source]);
            }
        }
        shapeFunctions.push_back(std::move(rows));
    }
    return shapeFunctions;
}

Vec3 cross(const Vec3 &left, const Vec3 &right)
{
    return {{
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    }};
}

double norm(const Vec3 &value)
{
    return std::sqrt(value[0] * value[0] +
                     value[1] * value[1] +
                     value[2] * value[2]);
}

guarded_source_keyed_face_loop::GuardedFaceGeometry evaluate_geometry(
    const Mesh &mesh,
    const PreparedSourceKeyedFace &face)
{
    guarded_source_keyed_face_loop::GuardedFaceGeometry geometry;
    geometry.faceIndex = face.mapping.faceIndex;
    const auto coordinates = coordinates_for_sources(
        mesh, face.mapping.originalSourceIds);

    if (face.samples.size() != kReviewedSampleCount ||
        mesh.param.gaussQuadratureCoeff.nrow() !=
            static_cast<int>(kReviewedSampleCount) ||
        mesh.param.gaussQuadratureCoeff.ncol() != 1)
    {
        throw std::invalid_argument(
            "valence-5 Phase 2 geometry rejected quadrature cardinality "
            "drift");
    }

    for (std::size_t sampleIndex = 0;
         sampleIndex < face.samples.size();
         ++sampleIndex)
    {
        std::array<Vec3, 3> evaluated{};
        for (int rowIndex = 0; rowIndex < 3; ++rowIndex)
        {
            const auto &row = face.samples[sampleIndex].rows[rowIndex];
            for (std::size_t source = 0;
                 source < coordinates.size();
                 ++source)
            {
                for (int axis = 0;
                     axis < source_keyed_kernel::kAxisCount;
                     ++axis)
                {
                    evaluated[rowIndex][axis] +=
                        row.coefficients[source] *
                        coordinates[source].get(axis, 0);
                }
            }
        }
        const Vec3 areaVector = cross(evaluated[1], evaluated[2]);
        const double weight = mesh.param.gaussQuadratureCoeff.get(
            static_cast<int>(sampleIndex), 0);
        geometry.elementArea += 0.5 * weight * norm(areaVector);
        geometry.elementVolume +=
            kLegacyVolumeQuadratureFactor * weight *
            evaluated[0][0] * areaVector[0];
    }
    if (!std::isfinite(geometry.elementArea) ||
        !std::isfinite(geometry.elementVolume) ||
        geometry.elementArea < 0.0)
    {
        throw std::invalid_argument(
            "valence-5 Phase 2 geometry produced invalid output");
    }
    return geometry;
}

struct ScientificDryRun
{
    std::vector<Valence5Phase2FaceObservables> observables;
    std::vector<SourceForceKinds> sourceForces;
};

ScientificDryRun evaluate_scientific_dry_run(
    Mesh &mesh,
    const PreparedSourceKeyedKernelCall &prepared,
    const double totalArea,
    const double totalVolume)
{
    Param stagedParam = mesh.param;
    Mesh evaluator(stagedParam);
    // Construction initializes Param-owned derived tables. Restore the exact
    // caller state and replace only the staged global geometry.
    stagedParam = mesh.param;
    stagedParam.area = totalArea;
    stagedParam.vol = totalVolume;

    SourceKeyedKernelCallInput scientificInput;
    scientificInput.sourceCount = prepared.sourceCount;
    scientificInput.mappings.reserve(prepared.faces.size());
    scientificInput.rows.reserve(prepared.faces.size());
    scientificInput.forces.reserve(prepared.faces.size());

    ScientificDryRun dryRun;
    dryRun.observables.reserve(prepared.faces.size());
    for (const PreparedSourceKeyedFace &preparedFace : prepared.faces)
    {
        const int faceIndex = preparedFace.mapping.faceIndex;
        const int localSourceCount = static_cast<int>(
            preparedFace.mapping.originalSourceIds.size());
        const auto coordinates = coordinates_for_sources(
            mesh, preparedFace.mapping.originalSourceIds);
        const auto shapeFunctions = shape_functions_for_face(preparedFace);

        Face &formulaFace = mesh.faces[faceIndex];
        Matrix normal = mat_calloc(source_keyed_kernel::kAxisCount, 1);
        Matrix bending = mat_calloc(
            localSourceCount, source_keyed_kernel::kAxisCount);
        Matrix area = mat_calloc(
            localSourceCount, source_keyed_kernel::kAxisCount);
        Matrix volume = mat_calloc(
            localSourceCount, source_keyed_kernel::kAxisCount);
        double meanCurvature = 0.0;
        double bendingEnergy = 0.0;
        evaluator.element_energy_force_regular(
            coordinates,
            formulaFace,
            formulaFace.spontCurvature,
            meanCurvature,
            normal,
            bendingEnergy,
            bending,
            area,
            volume,
            false,
            &shapeFunctions);
        if (!std::isfinite(meanCurvature) ||
            !std::isfinite(bendingEnergy) ||
            !matrix_is_finite(normal) ||
            !matrix_is_finite(bending) ||
            !matrix_is_finite(area) ||
            !matrix_is_finite(volume))
        {
            throw std::invalid_argument(
                "valence-5 Phase 2 scientific dry run produced nonfinite "
                "output");
        }

        Valence5Phase2FaceObservables observable;
        observable.faceIndex = faceIndex;
        observable.meanCurvature = meanCurvature;
        observable.bendingEnergy = bendingEnergy;
        for (int axis = 0; axis < source_keyed_kernel::kAxisCount; ++axis)
        {
            observable.normal[axis] = normal.get(axis, 0);
        }
        dryRun.observables.push_back(observable);

        SourceKeyedFaceForces faceForces;
        faceForces.faceIndex = faceIndex;
        faceForces.sourceIds = preparedFace.mapping.originalSourceIds;
        faceForces.forces.resize(faceForces.sourceIds.size());
        const std::array<const Matrix *, source_keyed_kernel::kForceKindCount>
            forceMatrices{{&bending, &area, &volume}};
        for (int source = 0; source < localSourceCount; ++source)
        {
            for (int kind = 0;
                 kind < source_keyed_kernel::kForceKindCount;
                 ++kind)
            {
                for (int axis = 0;
                     axis < source_keyed_kernel::kAxisCount;
                     ++axis)
                {
                    faceForces.forces[source][kind][axis] =
                        forceMatrices[kind]->get(source, axis);
                }
            }
        }

        source_keyed_kernel::SourceKeyedFaceRows faceRows;
        faceRows.faceIndex = faceIndex;
        faceRows.orientedFaceVertices =
            preparedFace.mapping.orientedFaceVertices;
        faceRows.samples = preparedFace.samples;
        scientificInput.mappings.push_back(preparedFace.mapping);
        scientificInput.rows.push_back(std::move(faceRows));
        scientificInput.forces.push_back(std::move(faceForces));
    }

    const PreparedSourceKeyedKernelCall scientificPrepared =
        source_keyed_kernel::prepare_source_keyed_kernel_call(
            scientificInput);
    dryRun.sourceForces =
        source_keyed_kernel::accumulate_source_keyed_force_contributions(
            scientificPrepared);
    return dryRun;
}

double maximum_face_observable_difference(
    const Mesh &mesh,
    const std::vector<Valence5Phase2FaceObservables> &expected)
{
    if (expected.size() != mesh.faces.size())
    {
        return INFINITY;
    }
    double maximum = 0.0;
    for (std::size_t faceIndex = 0; faceIndex < mesh.faces.size(); ++faceIndex)
    {
        const Face &actual = mesh.faces[faceIndex];
        const auto &reference = expected[faceIndex];
        maximum = std::max(maximum,
                           std::abs(actual.meanCurvature -
                                    reference.meanCurvature));
        maximum = std::max(maximum,
                           std::abs(actual.energy.energyCurvature -
                                    reference.bendingEnergy));
        for (int axis = 0; axis < source_keyed_kernel::kAxisCount; ++axis)
        {
            maximum = std::max(maximum,
                               std::abs(actual.normVector.get(axis, 0) -
                                        reference.normal[axis]));
        }
    }
    return maximum;
}

double maximum_source_force_difference(
    const Mesh &mesh,
    const std::vector<SourceForceKinds> &expected)
{
    if (expected.size() != mesh.vertices.size())
    {
        return INFINITY;
    }
    double maximum = 0.0;
    for (std::size_t source = 0; source < mesh.vertices.size(); ++source)
    {
        const std::array<const Matrix *, source_keyed_kernel::kForceKindCount>
            actual{{
                &mesh.vertices[source].force.forceCurvature,
                &mesh.vertices[source].force.forceArea,
                &mesh.vertices[source].force.forceVolume,
            }};
        for (int kind = 0;
             kind < source_keyed_kernel::kForceKindCount;
             ++kind)
        {
            for (int axis = 0;
                 axis < source_keyed_kernel::kAxisCount;
                 ++axis)
            {
                maximum = std::max(
                    maximum,
                    std::abs(actual[kind]->get(axis, 0) -
                             expected[source][kind][axis]));
            }
        }
    }
    return maximum;
}

bool output_state_is_finite(const Mesh &mesh)
{
    const Energy &energy = mesh.param.energy;
    const std::array<double, 12> globals{{
        mesh.param.area,
        mesh.param.vol,
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
    if (!std::all_of(globals.begin(), globals.end(),
                     [](const double value) { return std::isfinite(value); }))
    {
        return false;
    }
    for (const Face &face : mesh.faces)
    {
        if (!std::isfinite(face.elementArea) ||
            !std::isfinite(face.elementVolume) ||
            !std::isfinite(face.meanCurvature) ||
            !std::isfinite(face.energy.energyCurvature) ||
            !std::isfinite(face.energy.energyRegularization) ||
            !std::isfinite(face.energy.energyTotal) ||
            !matrix_is_finite(face.normVector))
        {
            return false;
        }
    }
    for (const Vertex &vertex : mesh.vertices)
    {
        const std::array<const Matrix *, 8> forces{{
            &vertex.force.forceCurvature,
            &vertex.force.forceArea,
            &vertex.force.forceVolume,
            &vertex.force.forceThickness,
            &vertex.force.forceTilt,
            &vertex.force.forceRegularization,
            &vertex.force.forceHarmonicBond,
            &vertex.force.forceTotal,
        }};
        if (std::any_of(forces.begin(), forces.end(),
                        [](const Matrix *force) {
                            return !matrix_is_finite(*force);
                        }))
        {
            return false;
        }
    }
    return true;
}
} // namespace

bool opensubdiv_valence5_phase2_requested()
{
    const char *value = std::getenv(kPhase2RuntimeOptIn);
    return value != nullptr && std::string(value) == "1";
}

bool opensubdiv_valence5_production_routing_requested()
{
    const char *value = std::getenv(kProductionRuntimeOptIn);
    return value != nullptr && std::string(value) == "1";
}

static Valence5Phase2Result evaluate_guarded_valence5_face_loop(
    Mesh &mesh,
    const Valence5Phase2Request &request,
    const bool runtimeOptInRequested,
    const char *runtimeGate)
{
    Valence5Phase2Result result;
    result.explicitRequestReceived =
        request.reviewerApprovedExplicitRequest;
    result.runtimeOptInRequested = runtimeOptInRequested;
    if (!result.explicitRequestReceived)
    {
        result.rejectionReason =
            "valence-5 Option B Phase 2 remains default-off without an "
            "explicit reviewer-approved request";
        return result;
    }
    if (!result.runtimeOptInRequested)
    {
        result.rejectionReason =
            "valence-5 Option B route requires " +
            std::string(runtimeGate) + "=1";
        return result;
    }

    if (mesh.param.gaussQuadratureN != kReviewedQuadratureOrder ||
        mesh.param.VWU.nrow() != static_cast<int>(kReviewedSampleCount) ||
        mesh.param.VWU.ncol() != 3)
    {
        result.rejectionReason =
            "valence-5 Phase 2 requires the exact ordered N=2 quadrature "
            "sample plan";
        return result;
    }
    for (int sample = 0;
         sample < static_cast<int>(kReviewedSampleCount);
         ++sample)
    {
        for (int coordinate = 0; coordinate < 3; ++coordinate)
        {
            if (mesh.param.VWU.get(sample, coordinate) !=
                kReviewedSamples[sample][coordinate])
            {
                result.rejectionReason =
                    "valence-5 Phase 2 rejected ordered quadrature sample "
                    "drift";
                return result;
            }
        }
    }
    result.exactQuadratureSamplePlanValidated = true;

    if (mesh.param.gaussQuadratureCoeff.nrow() !=
            static_cast<int>(kReviewedSampleCount) ||
        mesh.param.gaussQuadratureCoeff.ncol() != 1)
    {
        result.rejectionReason =
            "valence-5 Phase 2 requires exactly three reviewed quadrature "
            "weights";
        return result;
    }
    for (int sample = 0;
         sample < static_cast<int>(kReviewedSampleCount);
         ++sample)
    {
        if (mesh.param.gaussQuadratureCoeff.get(sample, 0) !=
            kReviewedWeights[sample])
        {
            result.rejectionReason =
                "valence-5 Phase 2 rejected quadrature weight drift";
            return result;
        }
    }
    result.exactQuadratureWeightsValidated = true;

    result.opensubdivRowProviderExecuted = true;
    opensubdiv_valence5::OpenSubdivValence5RowProviderRequest rowRequest;
    rowRequest.phase1ProviderExplicitRequest = true;
    result.rowProvider =
        opensubdiv_valence5::build_guarded_opensubdiv_valence5_rows(
            mesh, rowRequest);
    if (!result.rowProvider.accepted)
    {
        result.rejectionReason = result.rowProvider.rejectionReason;
        return result;
    }
    result.opensubdivRowsGenerated = true;

    PreparedSourceKeyedKernelCall prepared;
    ScientificDryRun dryRun;
    try
    {
        SourceKeyedKernelCallInput input;
        input.sourceCount = static_cast<int>(mesh.vertices.size());
        input.mappings = mappings_for_rows(mesh, result.rowProvider.rows);
        input.rows = result.rowProvider.rows;
        input.forces = zero_forces_for_mappings(input.mappings);
        prepared = source_keyed_kernel::prepare_source_keyed_kernel_call(input);
        result.sourceKeyedRowsPrepared = true;

        result.faceGeometry.reserve(prepared.faces.size());
        for (const PreparedSourceKeyedFace &face : prepared.faces)
        {
            auto geometry = evaluate_geometry(mesh, face);
            result.totalArea += geometry.elementArea;
            result.totalVolume += geometry.elementVolume;
            result.faceGeometry.push_back(std::move(geometry));
        }
        if (!std::isfinite(result.totalArea) ||
            !std::isfinite(result.totalVolume) ||
            result.totalArea < 0.0)
        {
            throw std::invalid_argument(
                "valence-5 Phase 2 geometry produced invalid global output");
        }
        result.geometryStaged = true;

        dryRun = evaluate_scientific_dry_run(
            mesh, prepared, result.totalArea, result.totalVolume);
        result.faceObservables = dryRun.observables;
        result.scientificDryRunExecuted = true;

        guarded_source_keyed_face_loop::
            validate_guarded_source_keyed_production_face_loop(
                mesh,
                result.faceGeometry,
                result.totalArea,
                result.totalVolume,
                prepared);
        result.completeTransactionValidatedBeforeMutation = true;
        // The shared executor repeats the complete validation immediately
        // before its first write.
        guarded_source_keyed_face_loop::
            execute_guarded_source_keyed_production_face_loop(
                mesh,
                result.faceGeometry,
                result.totalArea,
                result.totalVolume,
                prepared);
    }
    catch (const std::invalid_argument &error)
    {
        result.rejectionReason = error.what();
        return result;
    }

    result.maxFaceObservableDifference =
        maximum_face_observable_difference(mesh, dryRun.observables);
    result.maxSourceForceDifference =
        maximum_source_force_difference(mesh, dryRun.sourceForces);
    result.faceObservablesMatchDryRun =
        result.maxFaceObservableDifference <= kReviewedProductionTolerance;
    result.sourceForcesMatchDryRun =
        result.maxSourceForceDifference <= kReviewedProductionTolerance;
    result.outputStateFinite = output_state_is_finite(mesh);
    if (!result.faceObservablesMatchDryRun ||
        !result.sourceForcesMatchDryRun ||
        !result.outputStateFinite)
    {
        // This is a postcondition failure, not an input rejection: the input
        // transaction has already passed its atomic preflight and executed.
        throw std::runtime_error(
            "valence-5 Phase 2 production postcondition failed");
    }

    result.accepted = true;
    result.currentStateCleared = true;
    result.productionCompletionPhasesExecuted = true;
    result.totalForcePublicationExecuted = true;
    result.totalEnergyPublicationExecuted = true;
    result.boundaryHandlingExecuted = true;
    result.productionRouteEnabled = false;
    result.actualProductionForcePathExecuted = true;
    result.productionFaceLoopExecuted = true;
    result.productionOneRingsPopulated = false;
    result.defaultEvaluatorCaller = false;
    result.phase3ActivationAuthorized = false;
    result.rejectionReason.clear();
    return result;
}

Valence5Phase2Result evaluate_guarded_valence5_phase2_face_loop(
    Mesh &mesh,
    const Valence5Phase2Request &request)
{
    return evaluate_guarded_valence5_face_loop(
        mesh,
        request,
        opensubdiv_valence5_phase2_requested(),
        kPhase2RuntimeOptIn);
}

Valence5Phase2Result evaluate_guarded_valence5_production_route(Mesh &mesh)
{
    Valence5Phase2Request request;
    request.reviewerApprovedExplicitRequest = true;
    Valence5Phase2Result result = evaluate_guarded_valence5_face_loop(
        mesh,
        request,
        opensubdiv_valence5_production_routing_requested(),
        kProductionRuntimeOptIn);
    if (!result.accepted)
    {
        return result;
    }
    result.productionRouteEnabled = true;
    result.defaultEvaluatorCaller = true;
    result.phase3ActivationAuthorized = true;
    return result;
}
} // namespace slimed::opensubdiv_valence5_phase2
