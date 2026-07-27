#include "energy_force/Valence4_face_loop_route_preflight.hpp"

#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <utility>

namespace slimed::valence4_route_preflight
{
namespace
{
constexpr std::size_t kReviewedSampleCountPerFace = 3;

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

Valence4VertexForcePublicationResult reject_publication_request(
    std::string reason,
    const bool explicitPublicationRequested)
{
    Valence4VertexForcePublicationResult result;
    result.rejectionReason = std::move(reason);
    result.explicitPublicationRequested = explicitPublicationRequested;
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

Valence4FaceLoopScientificRequestResult
evaluate_guarded_valence4_face_loop_scientific_request(
    Mesh &mesh,
    const Valence4FaceLoopScientificRequest &request)
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
            mesh.element_energy_force_regular(
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
    result.faceObservables = std::move(observables);
    result.sourceKeyedRequest = std::move(sourceKeyedResult);
    return result;
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
} // namespace slimed::valence4_route_preflight
