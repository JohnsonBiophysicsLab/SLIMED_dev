#include "energy_force/Valence4_face_loop_route_preflight.hpp"

#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"

#include <cstddef>
#include <string>
#include <utility>

namespace slimed::valence4_route_preflight
{
namespace
{
Valence4FaceLoopRoutePreflightResult reject(std::string reason)
{
    Valence4FaceLoopRoutePreflightResult result;
    result.rejectionReason = std::move(reason);
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
} // namespace slimed::valence4_route_preflight
