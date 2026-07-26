#include "energy_force/Valence4_face_loop_route_preflight.hpp"

#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"

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
} // namespace slimed::valence4_route_preflight
