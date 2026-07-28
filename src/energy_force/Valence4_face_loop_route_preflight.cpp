#include "energy_force/Valence4_face_loop_route_preflight.hpp"

#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <utility>

namespace slimed::valence4_route_preflight
{
Valence4FaceLoopScientificRequestResult
evaluate_scientific_request_with_evaluator(
    Mesh &mesh,
    Mesh &scientificEvaluator,
    const Valence4FaceLoopScientificRequest &request,
    bool stagedGeometryUsed);

namespace
{
constexpr std::size_t kReviewedSampleCountPerFace = 3;
constexpr double kLegacyVolumeQuadratureFactor = 0.16666666666;

Valence4FaceLoopRoutePreflightResult reject(std::string reason)
{
    Valence4FaceLoopRoutePreflightResult result;
    result.rejectionReason = std::move(reason);
    return result;
}

Valence4FaceLoopRouteRequestResult reject_request(
    std::string reason,
    Valence4FaceLoopRoutePreflightResult preflight,
    const bool explicitRouteRequested)
{
    Valence4FaceLoopRouteRequestResult result;
    result.rejectionReason = std::move(reason);
    result.preflight = std::move(preflight);
    result.explicitRouteRequested = explicitRouteRequested;
    return result;
}

Valence4FaceLoopScientificRequestResult reject_scientific_request(
    std::string reason,
    const bool explicitRouteRequested)
{
    Valence4FaceLoopScientificRequestResult result;
    result.rejectionReason = std::move(reason);
    result.explicitRouteRequested = explicitRouteRequested;
    return result;
}

Valence4FaceGeometryStagingResult reject_geometry_staging(
    std::string reason,
    const bool explicitStagingRequested)
{
    Valence4FaceGeometryStagingResult result;
    result.rejectionReason = std::move(reason);
    result.explicitStagingRequested = explicitStagingRequested;
    return result;
}

Valence4VertexForcePublicationResult reject_publication_request(
    std::string reason,
    const bool explicitPublicationRequested)
{
    Valence4VertexForcePublicationResult result;
    result.rejectionReason = std::move(reason);
    result.explicitPublicationRequested = explicitPublicationRequested;
    return result;
}

Valence4FaceObservablePublicationResult
reject_face_observable_publication_request(
    std::string reason,
    const bool explicitPublicationRequested)
{
    Valence4FaceObservablePublicationResult result;
    result.rejectionReason = std::move(reason);
    result.explicitPublicationRequested = explicitPublicationRequested;
    return result;
}

Valence4FaceLoopPublicationResult
reject_face_loop_publication_request(
    std::string reason,
    const bool explicitPublicationRequested)
{
    Valence4FaceLoopPublicationResult result;
    result.rejectionReason = std::move(reason);
    result.explicitPublicationRequested = explicitPublicationRequested;
    return result;
}

Valence4GeometryAwareAtomicCompositionResult
reject_geometry_aware_composition_request(
    std::string reason,
    const bool explicitCompositionRequested)
{
    Valence4GeometryAwareAtomicCompositionResult result;
    result.rejectionReason = std::move(reason);
    result.explicitCompositionRequested = explicitCompositionRequested;
    return result;
}

Valence4ProductionCallerShadowResult
reject_production_caller_shadow_request(
    std::string reason,
    const bool explicitShadowRequested)
{
    Valence4ProductionCallerShadowResult result;
    result.rejectionReason = std::move(reason);
    result.explicitShadowRequested = explicitShadowRequested;
    return result;
}

std::vector<source_keyed_kernel::SourceKeyedFaceForces>
zero_forces_for_mappings(
    const std::vector<source_keyed_kernel::SourceMappingView> &mappings)
{
    std::vector<source_keyed_kernel::SourceKeyedFaceForces> forces;
    forces.reserve(mappings.size());
    for (const auto &mapping : mappings)
    {
        source_keyed_kernel::SourceKeyedFaceForces faceForces;
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
                "valence-4 scientific request source id is out of range");
        }
        coordinates.push_back(mesh.vertices[sourceId].coord);
    }
    return coordinates;
}

std::vector<Matrix> shape_functions_for_face(
    const source_keyed_kernel::PreparedSourceKeyedFace &face)
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
                    "valence-4 scientific request row/source mapping drifted");
            }
            for (std::size_t sourcePosition = 0;
                 sourcePosition < sourceIds.size();
                 ++sourcePosition)
            {
                rows.set(rowIndex,
                         static_cast<int>(sourcePosition),
                         row.coefficients[sourcePosition]);
            }
        }
        shapeFunctions.push_back(std::move(rows));
    }
    return shapeFunctions;
}

source_keyed_kernel::Vec3 cross(
    const source_keyed_kernel::Vec3 &left,
    const source_keyed_kernel::Vec3 &right)
{
    return {{
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    }};
}

double norm(const source_keyed_kernel::Vec3 &value)
{
    return std::sqrt(value[0] * value[0] +
                     value[1] * value[1] +
                     value[2] * value[2]);
}

Valence4FaceGeometry evaluate_face_geometry(
    const Mesh &mesh,
    const source_keyed_kernel::PreparedSourceKeyedFace &face)
{
    Valence4FaceGeometry geometry;
    geometry.faceIndex = face.mapping.faceIndex;
    const std::vector<int> &sourceIds =
        face.mapping.originalSourceIds;
    const std::vector<Matrix> coordinates =
        coordinates_for_sources(mesh, sourceIds);

    if (mesh.param.gaussQuadratureCoeff.nrow() !=
            static_cast<int>(face.samples.size()) ||
        mesh.param.gaussQuadratureCoeff.ncol() != 1)
    {
        throw std::invalid_argument(
            "valence-4 geometry staging quadrature weights must match "
            "the reviewed sample count");
    }

    for (std::size_t sampleIndex = 0;
         sampleIndex < face.samples.size();
         ++sampleIndex)
    {
        const source_keyed_kernel::SourceKeyedSampleRows &sample =
            face.samples[sampleIndex];
        std::array<source_keyed_kernel::Vec3, 3> evaluated{};
        for (int row = 0; row < 3; ++row)
        {
            const source_keyed_kernel::SourceKeyedRow &weightedRow =
                sample.rows[row];
            for (std::size_t source = 0;
                 source < sourceIds.size();
                 ++source)
            {
                for (int axis = 0;
                     axis < source_keyed_kernel::kAxisCount;
                     ++axis)
                {
                    evaluated[row][axis] +=
                        weightedRow.coefficients[source] *
                        coordinates[source].get(axis, 0);
                }
            }
        }
        const source_keyed_kernel::Vec3 areaVector =
            cross(evaluated[1], evaluated[2]);
        const double coefficient =
            mesh.param.gaussQuadratureCoeff.get(
                static_cast<int>(sampleIndex), 0);
        geometry.elementArea +=
            0.5 * coefficient * norm(areaVector);
        // Match Mesh::enumerate_regular_patch_area_volume_with_limit_surface_evaluator.
        geometry.elementVolume +=
            kLegacyVolumeQuadratureFactor * coefficient *
            evaluated[0][0] * areaVector[0];
    }

    if (!std::isfinite(geometry.elementArea) ||
        !std::isfinite(geometry.elementVolume) ||
        geometry.elementArea < 0.0)
    {
        throw std::invalid_argument(
            "valence-4 geometry staging produced invalid output");
    }
    return geometry;
}

bool matrix_is_finite(const Matrix &matrix)
{
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

std::vector<Valence4FaceGeometry>
validate_geometry_aware_publication(
    const Valence4FaceGeometryStagingResult &geometryResult,
    const Valence4FaceLoopScientificRequestResult &scientificResult,
    const Mesh &mesh)
{
    if (!geometryResult.accepted ||
        !geometryResult.productionGeometryEvaluated)
    {
        throw std::invalid_argument(
            "valence-4 geometry-aware publication requires a complete "
            "accepted geometry stage");
    }
    if (!scientificResult.accepted ||
        !scientificResult.productionScientificAlgebraExecuted ||
        !scientificResult.stagedGeometryUsedForScientificEvaluation)
    {
        throw std::invalid_argument(
            "valence-4 geometry-aware publication requires scientific "
            "evaluation against staged geometry");
    }
    if (!std::isfinite(geometryResult.totalArea) ||
        !std::isfinite(geometryResult.totalVolume) ||
        geometryResult.totalArea < 0.0 ||
        scientificResult.scientificGlobalArea !=
            geometryResult.totalArea ||
        scientificResult.scientificGlobalVolume !=
            geometryResult.totalVolume)
    {
        throw std::invalid_argument(
            "valence-4 geometry-aware publication rejected staged global "
            "geometry/scientific binding drift");
    }
    if (geometryResult.faceGeometry.empty() ||
        geometryResult.faceGeometry.size() != mesh.faces.size())
    {
        throw std::invalid_argument(
            "valence-4 geometry-aware publication rejected face geometry "
            "cardinality drift");
    }

    std::vector<Valence4FaceGeometry> staged(mesh.faces.size());
    std::vector<bool> assigned(mesh.faces.size(), false);
    for (std::size_t facePosition = 0;
         facePosition < mesh.faces.size();
         ++facePosition)
    {
        const Face &face = mesh.faces[facePosition];
        if (face.index != static_cast<int>(facePosition))
        {
            throw std::invalid_argument(
                "valence-4 geometry-aware publication rejected face "
                "identity drift");
        }
        if (!face.oneRingVertices.empty())
        {
            throw std::invalid_argument(
                "valence-4 geometry-aware publication requires empty "
                "production one-rings");
        }
    }
    for (const Valence4FaceGeometry &geometry :
         geometryResult.faceGeometry)
    {
        if (geometry.faceIndex < 0 ||
            geometry.faceIndex >= static_cast<int>(mesh.faces.size()))
        {
            throw std::invalid_argument(
                "valence-4 geometry-aware publication rejected out-of-range "
                "face geometry identity");
        }
        const std::size_t faceIndex =
            static_cast<std::size_t>(geometry.faceIndex);
        if (assigned[faceIndex])
        {
            throw std::invalid_argument(
                "valence-4 geometry-aware publication rejected duplicate "
                "face geometry identity");
        }
        if (!std::isfinite(geometry.elementArea) ||
            !std::isfinite(geometry.elementVolume) ||
            geometry.elementArea < 0.0)
        {
            throw std::invalid_argument(
                "valence-4 geometry-aware publication rejected invalid face "
                "geometry");
        }
        staged[faceIndex] = geometry;
        assigned[faceIndex] = true;
    }
    if (!std::all_of(assigned.begin(), assigned.end(),
                     [](const bool value) { return value; }))
    {
        throw std::invalid_argument(
            "valence-4 geometry-aware publication rejected incomplete face "
            "geometry coverage");
    }

    double stagedArea = 0.0;
    double stagedVolume = 0.0;
    for (const Valence4FaceGeometry &geometry : staged)
    {
        stagedArea += geometry.elementArea;
        stagedVolume += geometry.elementVolume;
    }
    if (stagedArea != geometryResult.totalArea ||
        stagedVolume != geometryResult.totalVolume)
    {
        throw std::invalid_argument(
            "valence-4 geometry-aware publication rejected face/global "
            "geometry accumulation drift");
    }
    return staged;
}

struct PreparedGeometryAwareComposition
{
    bool accepted = false;
    std::string rejectionReason;
    Valence4FaceGeometryStagingResult geometry;
    Valence4FaceLoopScientificRequestResult scientific;
};

PreparedGeometryAwareComposition
prepare_geometry_aware_composition(
    Mesh &mesh,
    const std::vector<source_keyed_kernel::SourceKeyedFaceRows> &rows)
{
    PreparedGeometryAwareComposition prepared;

    Valence4FaceGeometryStagingRequest geometryRequest;
    geometryRequest.reviewerApprovedExplicitStaging = true;
    geometryRequest.rows = rows;
    prepared.geometry =
        stage_guarded_valence4_face_geometry(mesh, geometryRequest);
    if (!prepared.geometry.accepted)
    {
        prepared.rejectionReason = prepared.geometry.rejectionReason;
        return prepared;
    }

    Param stagedParam = mesh.param;
    Mesh stagedScientificEvaluator(stagedParam);
    // Mesh construction initializes Param-owned derived tables. Restore the
    // caller's complete parameter state so staging and scientific evaluation
    // use the same quadrature plan, then replace only the staged globals.
    stagedParam = mesh.param;
    stagedParam.area = prepared.geometry.totalArea;
    stagedParam.vol = prepared.geometry.totalVolume;

    Valence4FaceLoopScientificRequest scientificRequest;
    scientificRequest.reviewerApprovedExplicitRequest = true;
    scientificRequest.rows = rows;
    prepared.scientific =
        evaluate_scientific_request_with_evaluator(
            mesh,
            stagedScientificEvaluator,
            scientificRequest,
            true);
    if (!prepared.scientific.accepted)
    {
        prepared.rejectionReason = prepared.scientific.rejectionReason;
        return prepared;
    }

    prepared.accepted = true;
    return prepared;
}

void validate_production_caller_shadow_destinations(const Mesh &mesh)
{
    for (std::size_t source = 0; source < mesh.vertices.size(); ++source)
    {
        const Vertex &vertex = mesh.vertices[source];
        if (vertex.index != static_cast<int>(source))
        {
            throw std::invalid_argument(
                "valence-4 production caller shadow rejected vertex "
                "identity drift");
        }
        const std::array<const Matrix *,
                         source_keyed_kernel::kForceKindCount>
            destinations{{
                &vertex.force.forceCurvature,
                &vertex.force.forceArea,
                &vertex.force.forceVolume}};
        for (const Matrix *destination : destinations)
        {
            if (destination->mat == nullptr ||
                destination->nrow() != source_keyed_kernel::kAxisCount ||
                destination->ncol() != 1)
            {
                throw std::invalid_argument(
                    "valence-4 production caller shadow rejected vertex "
                    "destination shape drift");
            }
        }
    }
    for (std::size_t faceIndex = 0;
         faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        const Face &face = mesh.faces[faceIndex];
        if (face.index != static_cast<int>(faceIndex) ||
            !face.oneRingVertices.empty())
        {
            throw std::invalid_argument(
                "valence-4 production caller shadow rejected face identity "
                "or one-ring drift");
        }
    }
}
} // namespace

Valence4FaceLoopRoutePreflightResult
build_guarded_valence4_face_loop_route_preflight(const Mesh &mesh)
{
    const Valence4TopologySourceMappingResult topology =
        build_guarded_valence4_topology_source_mapping(mesh);
    if (!topology.supported)
    {
        return reject(topology.rejectionReason);
    }
    if (topology.byFace.size() != mesh.faces.size())
    {
        return reject(
            "valence-4 face-loop preflight requires one mapping per face");
    }

    Valence4FaceLoopRoutePreflightResult result;
    result.sourceCount = static_cast<int>(mesh.vertices.size());
    if (result.sourceCount <= 0)
    {
        return reject(
            "valence-4 face-loop preflight requires at least one source");
    }

    result.mappings.reserve(topology.byFace.size());
    for (std::size_t facePosition = 0;
         facePosition < topology.byFace.size();
         ++facePosition)
    {
        const Valence4FaceTopologySourceMapping &mapping =
            topology.byFace[facePosition];
        if (mapping.faceIndex != static_cast<int>(facePosition))
        {
            return reject(
                "valence-4 face-loop preflight requires stable face order");
        }
        if (mapping.faceIndex < 0 ||
            mapping.faceIndex >= static_cast<int>(mesh.faces.size()))
        {
            return reject(
                "valence-4 face-loop preflight found an out-of-range face");
        }

        const Face &face = mesh.faces[mapping.faceIndex];
        source_keyed_kernel::SourceMappingView view;
        view.faceIndex = mapping.faceIndex;
        view.orientedFaceVertices = mapping.orientedFaceVertices;
        view.originalSourceIds = mapping.originalSourceIds;
        view.productionOneRingEmpty = face.oneRingVertices.empty();
        if (!view.productionOneRingEmpty)
        {
            return reject(
                "valence-4 face-loop preflight requires empty production "
                "one-rings");
        }
        if (view.originalSourceIds.empty())
        {
            return reject(
                "valence-4 face-loop preflight requires source coverage");
        }
        result.mappings.push_back(std::move(view));
    }

    result.supported = true;
    result.rejectionReason.clear();
    return result;
}

Valence4FaceLoopRouteRequestResult
evaluate_guarded_valence4_face_loop_route_request(
    const Mesh &mesh,
    const Valence4FaceLoopRouteRequest &request)
{
    Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    const bool explicitRouteRequested =
        request.reviewerApprovedExplicitRequest;
    if (!preflight.supported)
    {
        return reject_request(preflight.rejectionReason,
                              std::move(preflight),
                              explicitRouteRequested);
    }
    if (!request.reviewerApprovedExplicitRequest)
    {
        return reject_request(
            "valence-4 face-loop route request remains default-off without "
            "an explicit reviewer-approved request",
            std::move(preflight),
            explicitRouteRequested);
    }
    for (const auto &faceRows : request.rows)
    {
        if (faceRows.samples.size() != kReviewedSampleCountPerFace)
        {
            return reject_request(
                "valence-4 face-loop route request requires exactly three "
                "samples per face",
                std::move(preflight),
                explicitRouteRequested);
        }
    }

    slimed::source_keyed_kernel::SourceKeyedKernelCallInput input;
    input.sourceCount = preflight.sourceCount;
    input.mappings = preflight.mappings;
    input.rows = request.rows;
    input.forces = request.forces;

    Valence4FaceLoopRouteRequestResult result;
    result.explicitRouteRequested = true;
    result.preflight = std::move(preflight);
    try
    {
        result.prepared =
            slimed::source_keyed_kernel::prepare_source_keyed_kernel_call(
                input);
        result.accumulatedSourceForces =
            slimed::source_keyed_kernel::
                accumulate_source_keyed_force_contributions(
                    result.prepared);
    }
    catch (const std::invalid_argument &error)
    {
        result.rejectionReason = error.what();
        return result;
    }

    result.accepted = true;
    result.explicitRouteRequestAccepted = true;
    result.sourceKeyedAccumulationExecuted = true;
    result.rejectionReason.clear();
    return result;
}

Valence4FaceGeometryStagingResult
stage_guarded_valence4_face_geometry(
    const Mesh &mesh,
    const Valence4FaceGeometryStagingRequest &request)
{
    const bool explicitStagingRequested =
        request.reviewerApprovedExplicitStaging;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    if (!preflight.supported)
    {
        return reject_geometry_staging(preflight.rejectionReason,
                                       explicitStagingRequested);
    }
    if (!request.reviewerApprovedExplicitStaging)
    {
        return reject_geometry_staging(
            "valence-4 geometry staging remains default-off without an "
            "explicit reviewer-approved request",
            explicitStagingRequested);
    }
    for (const auto &faceRows : request.rows)
    {
        if (faceRows.samples.size() != kReviewedSampleCountPerFace)
        {
            return reject_geometry_staging(
                "valence-4 geometry staging requires exactly three "
                "samples per face",
                explicitStagingRequested);
        }
    }

    source_keyed_kernel::SourceKeyedKernelCallInput validationInput;
    validationInput.sourceCount = preflight.sourceCount;
    validationInput.mappings = preflight.mappings;
    validationInput.rows = request.rows;
    validationInput.forces =
        zero_forces_for_mappings(preflight.mappings);

    source_keyed_kernel::PreparedSourceKeyedKernelCall preparedRows;
    try
    {
        preparedRows =
            source_keyed_kernel::prepare_source_keyed_kernel_call(
                validationInput);
    }
    catch (const std::invalid_argument &error)
    {
        return reject_geometry_staging(error.what(),
                                       explicitStagingRequested);
    }

    Valence4FaceGeometryStagingResult result;
    result.explicitStagingRequested = true;
    result.faceGeometry.reserve(preparedRows.faces.size());
    try
    {
        for (const auto &preparedFace : preparedRows.faces)
        {
            Valence4FaceGeometry geometry =
                evaluate_face_geometry(mesh, preparedFace);
            result.totalArea += geometry.elementArea;
            result.totalVolume += geometry.elementVolume;
            result.faceGeometry.push_back(std::move(geometry));
        }
    }
    catch (const std::invalid_argument &error)
    {
        return reject_geometry_staging(error.what(),
                                       explicitStagingRequested);
    }
    if (!std::isfinite(result.totalArea) ||
        !std::isfinite(result.totalVolume) ||
        result.totalArea < 0.0)
    {
        return reject_geometry_staging(
            "valence-4 geometry staging produced invalid global output",
            explicitStagingRequested);
    }

    result.accepted = true;
    result.productionGeometryEvaluated = true;
    result.rejectionReason.clear();
    return result;
}

Valence4FaceLoopScientificRequestResult
evaluate_scientific_request_with_evaluator(
    Mesh &mesh,
    Mesh &scientificEvaluator,
    const Valence4FaceLoopScientificRequest &request,
    const bool stagedGeometryUsed)
{
    const bool explicitRouteRequested =
        request.reviewerApprovedExplicitRequest;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    if (!preflight.supported)
    {
        return reject_scientific_request(preflight.rejectionReason,
                                         explicitRouteRequested);
    }
    if (!request.reviewerApprovedExplicitRequest)
    {
        return reject_scientific_request(
            "valence-4 scientific request remains default-off without an "
            "explicit reviewer-approved request",
            explicitRouteRequested);
    }
    for (const auto &faceRows : request.rows)
    {
        if (faceRows.samples.size() != kReviewedSampleCountPerFace)
        {
            return reject_scientific_request(
                "valence-4 scientific request requires exactly three "
                "samples per face",
                explicitRouteRequested);
        }
    }

    source_keyed_kernel::SourceKeyedKernelCallInput validationInput;
    validationInput.sourceCount = preflight.sourceCount;
    validationInput.mappings = preflight.mappings;
    validationInput.rows = request.rows;
    validationInput.forces =
        zero_forces_for_mappings(preflight.mappings);

    source_keyed_kernel::PreparedSourceKeyedKernelCall preparedRows;
    try
    {
        preparedRows =
            source_keyed_kernel::prepare_source_keyed_kernel_call(
                validationInput);
    }
    catch (const std::invalid_argument &error)
    {
        return reject_scientific_request(error.what(),
                                         explicitRouteRequested);
    }

    std::vector<Valence4FaceScientificObservables> observables;
    std::vector<source_keyed_kernel::SourceKeyedFaceForces> forces;
    observables.reserve(preparedRows.faces.size());
    forces.reserve(preparedRows.faces.size());
    try
    {
        for (const auto &preparedFace : preparedRows.faces)
        {
            const int faceIndex = preparedFace.mapping.faceIndex;
            if (faceIndex < 0 ||
                faceIndex >= static_cast<int>(mesh.faces.size()))
            {
                throw std::invalid_argument(
                    "valence-4 scientific request face index is out of range");
            }
            const std::vector<int> &sourceIds =
                preparedFace.mapping.originalSourceIds;
            const int sourceCount =
                static_cast<int>(sourceIds.size());
            std::vector<Matrix> coordinates =
                coordinates_for_sources(mesh, sourceIds);
            std::vector<Matrix> shapeFunctions =
                shape_functions_for_face(preparedFace);

            Face &formulaFace = mesh.faces[faceIndex];
            Matrix normal = mat_calloc(
                source_keyed_kernel::kAxisCount, 1);
            Matrix bending = mat_calloc(
                sourceCount, source_keyed_kernel::kAxisCount);
            Matrix area = mat_calloc(
                sourceCount, source_keyed_kernel::kAxisCount);
            Matrix volume = mat_calloc(
                sourceCount, source_keyed_kernel::kAxisCount);
            double meanCurvature = 0.0;
            double bendingEnergy = 0.0;
            scientificEvaluator.element_energy_force_regular(
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
                    "valence-4 scientific request produced nonfinite output");
            }

            Valence4FaceScientificObservables faceObservables;
            faceObservables.faceIndex = faceIndex;
            faceObservables.meanCurvature = meanCurvature;
            faceObservables.bendingEnergy = bendingEnergy;
            for (int axis = 0;
                 axis < source_keyed_kernel::kAxisCount;
                 ++axis)
            {
                faceObservables.normal[axis] =
                    normal.get(axis, 0);
            }
            observables.push_back(faceObservables);

            source_keyed_kernel::SourceKeyedFaceForces faceForces;
            faceForces.faceIndex = faceIndex;
            faceForces.sourceIds = sourceIds;
            faceForces.forces.resize(sourceIds.size());
            const std::array<const Matrix *,
                             source_keyed_kernel::kForceKindCount>
                forceMatrices{{&bending, &area, &volume}};
            for (int sourcePosition = 0;
                 sourcePosition < sourceCount;
                 ++sourcePosition)
            {
                for (int kind = 0;
                     kind < source_keyed_kernel::kForceKindCount;
                     ++kind)
                {
                    for (int axis = 0;
                         axis < source_keyed_kernel::kAxisCount;
                         ++axis)
                    {
                        faceForces.forces[sourcePosition][kind][axis] =
                            forceMatrices[kind]->get(sourcePosition,
                                                     axis);
                    }
                }
            }
            forces.push_back(std::move(faceForces));
        }
    }
    catch (const std::invalid_argument &error)
    {
        return reject_scientific_request(error.what(),
                                         explicitRouteRequested);
    }

    Valence4FaceLoopRouteRequest sourceKeyedRequest;
    sourceKeyedRequest.reviewerApprovedExplicitRequest = true;
    sourceKeyedRequest.rows = request.rows;
    sourceKeyedRequest.forces = std::move(forces);
    Valence4FaceLoopRouteRequestResult sourceKeyedResult =
        evaluate_guarded_valence4_face_loop_route_request(
            mesh, sourceKeyedRequest);
    if (!sourceKeyedResult.accepted)
    {
        return reject_scientific_request(
            sourceKeyedResult.rejectionReason,
            explicitRouteRequested);
    }

    Valence4FaceLoopScientificRequestResult result;
    result.accepted = true;
    result.explicitRouteRequested = true;
    result.productionScientificAlgebraExecuted = true;
    result.stagedGeometryUsedForScientificEvaluation =
        stagedGeometryUsed;
    result.scientificGlobalArea = scientificEvaluator.param.area;
    result.scientificGlobalVolume = scientificEvaluator.param.vol;
    result.faceObservables = std::move(observables);
    result.sourceKeyedRequest = std::move(sourceKeyedResult);
    return result;
}

Valence4FaceLoopScientificRequestResult
evaluate_guarded_valence4_face_loop_scientific_request(
    Mesh &mesh,
    const Valence4FaceLoopScientificRequest &request)
{
    return evaluate_scientific_request_with_evaluator(
        mesh, mesh, request, false);
}

Valence4VertexForcePublicationResult
evaluate_guarded_valence4_vertex_force_publication(
    Mesh &mesh,
    const Valence4VertexForcePublicationRequest &request)
{
    if (!request.reviewerApprovedExplicitPublication)
    {
        return reject_publication_request(
            "valence-4 vertex-force publication remains default-off without "
            "an explicit reviewer-approved publication request",
            false);
    }

    Valence4FaceLoopScientificRequest scientificRequest;
    scientificRequest.reviewerApprovedExplicitRequest = true;
    scientificRequest.rows = request.rows;
    Valence4FaceLoopScientificRequestResult scientificResult =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, scientificRequest);
    if (!scientificResult.accepted)
    {
        Valence4VertexForcePublicationResult rejected =
            reject_publication_request(
                scientificResult.rejectionReason, true);
        rejected.scientificRequest = std::move(scientificResult);
        return rejected;
    }

    Valence4VertexForcePublicationResult result;
    result.explicitPublicationRequested = true;
    result.scientificRequest = std::move(scientificResult);
    try
    {
        source_keyed_kernel::
            publish_source_keyed_membrane_forces_to_vertices(
                result.scientificRequest.sourceKeyedRequest
                    .accumulatedSourceForces,
                mesh);
    }
    catch (const std::invalid_argument &error)
    {
        result.rejectionReason = error.what();
        return result;
    }

    result.accepted = true;
    result.vertexForcePublicationExecuted = true;
    result.rejectionReason.clear();
    return result;
}

void publish_valence4_face_scientific_observables_to_faces(
    const std::vector<Valence4FaceScientificObservables> &observables,
    Mesh &mesh)
{
    if (observables.empty() ||
        observables.size() != mesh.faces.size())
    {
        throw std::invalid_argument(
            "valence-4 face-observable publication rejected face "
            "cardinality drift");
    }

    std::vector<Valence4FaceScientificObservables> staged(
        mesh.faces.size());
    std::vector<bool> assigned(mesh.faces.size(), false);
    for (std::size_t facePosition = 0;
         facePosition < mesh.faces.size();
         ++facePosition)
    {
        const Face &face = mesh.faces[facePosition];
        if (face.index != static_cast<int>(facePosition))
        {
            throw std::invalid_argument(
                "valence-4 face-observable publication rejected face "
                "identity drift");
        }
        if (!face.oneRingVertices.empty())
        {
            throw std::invalid_argument(
                "valence-4 face-observable publication requires empty "
                "production one-rings");
        }
    }
    for (const Valence4FaceScientificObservables &observable :
         observables)
    {
        if (observable.faceIndex < 0 ||
            observable.faceIndex >=
                static_cast<int>(mesh.faces.size()))
        {
            throw std::invalid_argument(
                "valence-4 face-observable publication rejected "
                "out-of-range face identity");
        }
        const std::size_t faceIndex =
            static_cast<std::size_t>(observable.faceIndex);
        if (assigned[faceIndex])
        {
            throw std::invalid_argument(
                "valence-4 face-observable publication rejected duplicate "
                "face identity");
        }
        if (!std::isfinite(observable.meanCurvature) ||
            !std::isfinite(observable.bendingEnergy))
        {
            throw std::invalid_argument(
                "valence-4 face-observable publication rejected nonfinite "
                "scalar data");
        }
        for (const double component : observable.normal)
        {
            if (!std::isfinite(component))
            {
                throw std::invalid_argument(
                    "valence-4 face-observable publication rejected "
                    "nonfinite normal data");
            }
        }
        staged[faceIndex] = observable;
        assigned[faceIndex] = true;
    }
    if (!std::all_of(assigned.begin(), assigned.end(),
                     [](const bool value) { return value; }))
    {
        throw std::invalid_argument(
            "valence-4 face-observable publication rejected incomplete "
            "face coverage");
    }

    std::vector<Matrix> stagedNormals;
    stagedNormals.reserve(staged.size());
    for (const Valence4FaceScientificObservables &observable : staged)
    {
        stagedNormals.emplace_back(
            source_keyed_kernel::kAxisCount, 1, true);
        for (int axis = 0;
             axis < source_keyed_kernel::kAxisCount;
             ++axis)
        {
            stagedNormals.back().set(
                axis, 0, observable.normal[axis]);
        }
    }

    // Validation and replacement-normal allocation finish before any write.
    for (std::size_t faceIndex = 0;
         faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        Face &face = mesh.faces[faceIndex];
        face.meanCurvature = staged[faceIndex].meanCurvature;
        face.energy.energyCurvature =
            staged[faceIndex].bendingEnergy;
        std::swap(face.normVector.mat,
                  stagedNormals[faceIndex].mat);
    }
}

Valence4FaceObservablePublicationResult
evaluate_guarded_valence4_face_observable_publication(
    Mesh &mesh,
    const Valence4FaceObservablePublicationRequest &request)
{
    if (!request.reviewerApprovedExplicitPublication)
    {
        return reject_face_observable_publication_request(
            "valence-4 face-observable publication remains default-off "
            "without an explicit reviewer-approved publication request",
            false);
    }

    Valence4FaceLoopScientificRequest scientificRequest;
    scientificRequest.reviewerApprovedExplicitRequest = true;
    scientificRequest.rows = request.rows;
    Valence4FaceLoopScientificRequestResult scientificResult =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, scientificRequest);
    if (!scientificResult.accepted)
    {
        Valence4FaceObservablePublicationResult rejected =
            reject_face_observable_publication_request(
                scientificResult.rejectionReason, true);
        rejected.scientificRequest = std::move(scientificResult);
        return rejected;
    }

    Valence4FaceObservablePublicationResult result;
    result.explicitPublicationRequested = true;
    result.scientificRequest = std::move(scientificResult);
    try
    {
        publish_valence4_face_scientific_observables_to_faces(
            result.scientificRequest.faceObservables,
            mesh);
    }
    catch (const std::invalid_argument &error)
    {
        result.rejectionReason = error.what();
        return result;
    }

    result.accepted = true;
    result.faceObservablePublicationExecuted = true;
    result.rejectionReason.clear();
    return result;
}

void publish_valence4_face_loop_scientific_result_atomically(
    const Valence4FaceLoopScientificRequestResult &scientificResult,
    Mesh &mesh)
{
    if (!scientificResult.accepted ||
        !scientificResult.productionScientificAlgebraExecuted ||
        !scientificResult.sourceKeyedRequest.accepted ||
        !scientificResult.sourceKeyedRequest
             .sourceKeyedAccumulationExecuted)
    {
        throw std::invalid_argument(
            "valence-4 face-loop publication requires a complete accepted "
            "scientific result");
    }

    const std::vector<source_keyed_kernel::SourceForceKinds>
        stagedSourceForces =
            scientificResult.sourceKeyedRequest.accumulatedSourceForces;
    if (stagedSourceForces.empty() ||
        stagedSourceForces.size() != mesh.vertices.size())
    {
        throw std::invalid_argument(
            "valence-4 face-loop publication rejected source/vertex "
            "cardinality drift");
    }
    if (scientificResult.faceObservables.empty() ||
        scientificResult.faceObservables.size() != mesh.faces.size())
    {
        throw std::invalid_argument(
            "valence-4 face-loop publication rejected face cardinality "
            "drift");
    }

    for (const Face &face : mesh.faces)
    {
        if (!face.oneRingVertices.empty())
        {
            throw std::invalid_argument(
                "valence-4 face-loop publication requires empty production "
                "one-rings");
        }
    }

    for (std::size_t source = 0;
         source < stagedSourceForces.size();
         ++source)
    {
        const Vertex &vertex = mesh.vertices[source];
        if (vertex.index != static_cast<int>(source))
        {
            throw std::invalid_argument(
                "valence-4 face-loop publication rejected vertex identity "
                "drift");
        }
        const std::array<const Matrix *,
                         source_keyed_kernel::kForceKindCount>
            destinations{{
                &vertex.force.forceCurvature,
                &vertex.force.forceArea,
                &vertex.force.forceVolume}};
        for (int kind = 0;
             kind < source_keyed_kernel::kForceKindCount;
             ++kind)
        {
            const Matrix *destination = destinations[kind];
            if (destination->mat == nullptr ||
                destination->nrow() != source_keyed_kernel::kAxisCount ||
                destination->ncol() != 1)
            {
                throw std::invalid_argument(
                    "valence-4 face-loop publication rejected vertex "
                    "destination shape drift");
            }
            for (int axis = 0;
                 axis < source_keyed_kernel::kAxisCount;
                 ++axis)
            {
                if (!std::isfinite(
                        stagedSourceForces[source][kind][axis]))
                {
                    throw std::invalid_argument(
                        "valence-4 face-loop publication rejected nonfinite "
                        "force data");
                }
            }
        }
    }

    std::vector<Valence4FaceScientificObservables> stagedObservables(
        mesh.faces.size());
    std::vector<bool> assigned(mesh.faces.size(), false);
    for (std::size_t facePosition = 0;
         facePosition < mesh.faces.size();
         ++facePosition)
    {
        if (mesh.faces[facePosition].index !=
            static_cast<int>(facePosition))
        {
            throw std::invalid_argument(
                "valence-4 face-loop publication rejected face identity "
                "drift");
        }
    }
    for (const Valence4FaceScientificObservables &observable :
         scientificResult.faceObservables)
    {
        if (observable.faceIndex < 0 ||
            observable.faceIndex >=
                static_cast<int>(mesh.faces.size()))
        {
            throw std::invalid_argument(
                "valence-4 face-loop publication rejected out-of-range face "
                "identity");
        }
        const std::size_t faceIndex =
            static_cast<std::size_t>(observable.faceIndex);
        if (assigned[faceIndex])
        {
            throw std::invalid_argument(
                "valence-4 face-loop publication rejected duplicate face "
                "identity");
        }
        if (!std::isfinite(observable.meanCurvature) ||
            !std::isfinite(observable.bendingEnergy) ||
            !std::all_of(
                observable.normal.begin(),
                observable.normal.end(),
                [](const double value) {
                    return std::isfinite(value);
                }))
        {
            throw std::invalid_argument(
                "valence-4 face-loop publication rejected nonfinite face "
                "observable data");
        }
        stagedObservables[faceIndex] = observable;
        assigned[faceIndex] = true;
    }
    if (!std::all_of(assigned.begin(),
                     assigned.end(),
                     [](const bool value) { return value; }))
    {
        throw std::invalid_argument(
            "valence-4 face-loop publication rejected incomplete face "
            "coverage");
    }

    std::vector<Matrix> stagedNormals;
    stagedNormals.reserve(stagedObservables.size());
    for (const Valence4FaceScientificObservables &observable :
         stagedObservables)
    {
        stagedNormals.emplace_back(
            source_keyed_kernel::kAxisCount, 1, true);
        for (int axis = 0;
             axis < source_keyed_kernel::kAxisCount;
             ++axis)
        {
            stagedNormals.back().set(
                axis, 0, observable.normal[axis]);
        }
    }

    // The commit phase contains only fixed-shape writes and pointer swaps.
    for (std::size_t source = 0;
         source < stagedSourceForces.size();
         ++source)
    {
        Vertex &vertex = mesh.vertices[source];
        const std::array<Matrix *,
                         source_keyed_kernel::kForceKindCount>
            destinations{{
                &vertex.force.forceCurvature,
                &vertex.force.forceArea,
                &vertex.force.forceVolume}};
        for (int kind = 0;
             kind < source_keyed_kernel::kForceKindCount;
             ++kind)
        {
            for (int axis = 0;
                 axis < source_keyed_kernel::kAxisCount;
                 ++axis)
            {
                destinations[kind]->set(
                    axis, 0,
                    stagedSourceForces[source][kind][axis]);
            }
        }
    }
    for (std::size_t faceIndex = 0;
         faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        Face &face = mesh.faces[faceIndex];
        face.meanCurvature =
            stagedObservables[faceIndex].meanCurvature;
        face.energy.energyCurvature =
            stagedObservables[faceIndex].bendingEnergy;
        std::swap(face.normVector.mat,
                  stagedNormals[faceIndex].mat);
    }
}

Valence4FaceLoopPublicationResult
evaluate_guarded_valence4_face_loop_publication(
    Mesh &mesh,
    const Valence4FaceLoopPublicationRequest &request)
{
    if (!request.reviewerApprovedExplicitPublication)
    {
        return reject_face_loop_publication_request(
            "valence-4 face-loop publication remains default-off without "
            "an explicit reviewer-approved publication request",
            false);
    }

    Valence4FaceLoopScientificRequest scientificRequest;
    scientificRequest.reviewerApprovedExplicitRequest = true;
    scientificRequest.rows = request.rows;
    Valence4FaceLoopScientificRequestResult scientificResult =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, scientificRequest);
    if (!scientificResult.accepted)
    {
        Valence4FaceLoopPublicationResult rejected =
            reject_face_loop_publication_request(
                scientificResult.rejectionReason, true);
        rejected.scientificRequest = std::move(scientificResult);
        return rejected;
    }

    Valence4FaceLoopPublicationResult result;
    result.explicitPublicationRequested = true;
    result.scientificRequest = std::move(scientificResult);
    try
    {
        publish_valence4_face_loop_scientific_result_atomically(
            result.scientificRequest, mesh);
    }
    catch (const std::invalid_argument &error)
    {
        result.rejectionReason = error.what();
        return result;
    }

    result.accepted = true;
    result.vertexForcePublicationExecuted = true;
    result.faceObservablePublicationExecuted = true;
    result.atomicFaceLoopPublicationExecuted = true;
    result.rejectionReason.clear();
    return result;
}

void publish_valence4_geometry_and_scientific_result_atomically(
    const Valence4FaceGeometryStagingResult &geometryResult,
    const Valence4FaceLoopScientificRequestResult &scientificResult,
    Mesh &mesh)
{
    const std::vector<Valence4FaceGeometry> stagedGeometry =
        validate_geometry_aware_publication(
            geometryResult, scientificResult, mesh);

    // This call completes all scientific destination validation and normal
    // allocation before its fixed-shape, nonthrowing commit phase.
    publish_valence4_face_loop_scientific_result_atomically(
        scientificResult, mesh);

    // Geometry was validated before the first scientific write. These
    // remaining assignments are fixed-size scalar commits and cannot throw.
    for (std::size_t faceIndex = 0;
         faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        mesh.faces[faceIndex].elementArea =
            stagedGeometry[faceIndex].elementArea;
        mesh.faces[faceIndex].elementVolume =
            stagedGeometry[faceIndex].elementVolume;
    }
    mesh.param.area = geometryResult.totalArea;
    mesh.param.vol = geometryResult.totalVolume;
}

Valence4GeometryAwareAtomicCompositionResult
evaluate_guarded_valence4_geometry_aware_atomic_composition(
    Mesh &mesh,
    const Valence4GeometryAwareAtomicCompositionRequest &request)
{
    if (!request.reviewerApprovedExplicitComposition)
    {
        return reject_geometry_aware_composition_request(
            "valence-4 geometry-aware atomic composition remains default-off "
            "without an explicit reviewer-approved composition request",
            false);
    }

    PreparedGeometryAwareComposition prepared =
        prepare_geometry_aware_composition(mesh, request.rows);
    if (!prepared.accepted)
    {
        Valence4GeometryAwareAtomicCompositionResult rejected =
            reject_geometry_aware_composition_request(
                prepared.rejectionReason, true);
        rejected.geometryStaging = std::move(prepared.geometry);
        rejected.scientificRequest = std::move(prepared.scientific);
        return rejected;
    }

    Valence4GeometryAwareAtomicCompositionResult result;
    result.explicitCompositionRequested = true;
    result.geometryStaging = std::move(prepared.geometry);
    result.scientificRequest = std::move(prepared.scientific);
    try
    {
        publish_valence4_geometry_and_scientific_result_atomically(
            result.geometryStaging,
            result.scientificRequest,
            mesh);
    }
    catch (const std::invalid_argument &error)
    {
        result.rejectionReason = error.what();
        return result;
    }

    result.accepted = true;
    result.stagedGeometryUsedForScientificEvaluation = true;
    result.geometryPublicationExecuted = true;
    result.vertexForcePublicationExecuted = true;
    result.faceObservablePublicationExecuted = true;
    result.atomicGeometryScientificPublicationExecuted = true;
    result.rejectionReason.clear();
    return result;
}

Valence4ProductionCallerShadowResult
evaluate_guarded_valence4_production_caller_shadow(
    Mesh &mesh,
    const Valence4ProductionCallerShadowRequest &request)
{
    if (!request.reviewerApprovedExplicitShadow)
    {
        return reject_production_caller_shadow_request(
            "valence-4 production caller shadow remains default-off without "
            "an explicit reviewer-approved shadow request",
            false);
    }

    PreparedGeometryAwareComposition prepared =
        prepare_geometry_aware_composition(mesh, request.rows);
    if (!prepared.accepted)
    {
        Valence4ProductionCallerShadowResult rejected =
            reject_production_caller_shadow_request(
                prepared.rejectionReason, true);
        rejected.composition.geometryStaging =
            std::move(prepared.geometry);
        rejected.composition.scientificRequest =
            std::move(prepared.scientific);
        return rejected;
    }

    try
    {
        validate_production_caller_shadow_destinations(mesh);
        validate_geometry_aware_publication(
            prepared.geometry, prepared.scientific, mesh);
    }
    catch (const std::invalid_argument &error)
    {
        return reject_production_caller_shadow_request(
            error.what(), true);
    }

    mesh.clear_force_on_vertices_and_energy_on_faces();
    publish_valence4_geometry_and_scientific_result_atomically(
        prepared.geometry, prepared.scientific, mesh);

    Valence4ProductionCallerShadowResult result;
    result.explicitShadowRequested = true;
    result.currentStateCleared = true;
    result.composition.explicitCompositionRequested = true;
    result.composition.stagedGeometryUsedForScientificEvaluation = true;
    result.composition.geometryPublicationExecuted = true;
    result.composition.vertexForcePublicationExecuted = true;
    result.composition.faceObservablePublicationExecuted = true;
    result.composition.atomicGeometryScientificPublicationExecuted = true;
    result.composition.geometryStaging = std::move(prepared.geometry);
    result.composition.scientificRequest = std::move(prepared.scientific);
    result.composition.accepted = true;
    result.geometryAwareAtomicCompositionExecuted = true;

    mesh.complete_energy_force_after_membrane_accumulation();

    result.accepted = true;
    result.productionCompletionPhasesExecuted = true;
    result.totalForcePublicationExecuted = true;
    result.totalEnergyPublicationExecuted = true;
    result.boundaryHandlingExecuted = true;
    result.rejectionReason.clear();
    return result;
}
} // namespace slimed::valence4_route_preflight
