#include "mesh/Valence4_topology_source_mapping.hpp"

#include "mesh/Mesh.hpp"

#include <algorithm>
#include <array>
#include <set>
#include <sstream>
#include <utility>

namespace
{
constexpr int kApprovedVertexCount = 6;
constexpr int kApprovedFaceCount = 8;
constexpr std::array<std::array<int, 3>, kApprovedFaceCount>
    kApprovedOrientedFaces{{
        {{0, 2, 3}},
        {{0, 3, 4}},
        {{0, 4, 5}},
        {{0, 5, 2}},
        {{1, 3, 2}},
        {{1, 4, 3}},
        {{1, 5, 4}},
        {{1, 2, 5}},
    }};

Valence4TopologySourceMappingResult reject(const std::string &reason)
{
    Valence4TopologySourceMappingResult result;
    result.rejectionReason = reason;
    return result;
}

std::vector<int> derive_original_source_ids(const Mesh &mesh,
                                            const Face &face)
{
    std::set<int> sources;
    for (const int vertexIndex : face.adjacentVertices)
    {
        sources.insert(vertexIndex);
        for (const int neighborIndex :
             mesh.vertices[vertexIndex].adjacentVertices)
        {
            sources.insert(neighborIndex);
        }
    }
    return std::vector<int>(sources.begin(), sources.end());
}
} // namespace

Valence4TopologySourceMappingResult
build_guarded_valence4_topology_source_mapping(const Mesh &mesh)
{
    if (mesh.vertices.size() != kApprovedVertexCount ||
        mesh.faces.size() != kApprovedFaceCount)
    {
        return reject(
            "valence-4 source mapping is limited to the approved closed "
            "six-vertex, eight-face octahedron");
    }

    const std::vector<int> expectedSourceIds{0, 1, 2, 3, 4, 5};
    for (int sourceId = 0; sourceId < kApprovedVertexCount; ++sourceId)
    {
        const Vertex &vertex = mesh.vertices[sourceId];
        if (vertex.index != sourceId)
        {
            return reject(
                "valence-4 source mapping requires vertex indices to equal "
                "original source ids");
        }
        if (vertex.adjacentVertices.size() != 4u)
        {
            return reject(
                "valence-4 source mapping requires every approved source "
                "vertex to have valence four");
        }
    }

    Valence4TopologySourceMappingResult result;
    result.byFace.reserve(mesh.faces.size());
    for (int faceIndex = 0; faceIndex < kApprovedFaceCount; ++faceIndex)
    {
        const Face &face = mesh.faces[faceIndex];
        if (face.index != faceIndex)
        {
            return reject(
                "valence-4 source mapping requires stable face indices");
        }
        if (face.isGhost || face.isBoundary)
        {
            return reject(
                "valence-4 source mapping requires closed physical faces");
        }
        if (face.adjacentVertices.size() != 3u)
        {
            return reject(
                "valence-4 source mapping requires oriented triangular faces");
        }
        if (!std::equal(face.adjacentVertices.begin(),
                        face.adjacentVertices.end(),
                        kApprovedOrientedFaces[faceIndex].begin()))
        {
            return reject(
                "valence-4 source mapping requires the approved canonical "
                "face orientation and source identity");
        }
        if (!face.oneRingVertices.empty())
        {
            return reject(
                "valence-4 source mapping must not replace the production "
                "11/12-control Face::oneRingVertices contract");
        }

        Valence4FaceTopologySourceMapping mapping;
        mapping.faceIndex = faceIndex;
        for (int corner = 0; corner < 3; ++corner)
        {
            const int sourceId = face.adjacentVertices[corner];
            if (sourceId < 0 || sourceId >= kApprovedVertexCount)
            {
                return reject(
                    "valence-4 source mapping found an out-of-range oriented "
                    "face source id");
            }
            mapping.orientedFaceVertices[corner] = sourceId;
        }

        mapping.originalSourceIds =
            derive_original_source_ids(mesh, face);
        if (mapping.originalSourceIds != expectedSourceIds)
        {
            std::ostringstream message;
            message
                << "valence-4 source mapping requires exact original-source "
                   "coverage 0..5 on face "
                << faceIndex;
            return reject(message.str());
        }
        result.byFace.push_back(std::move(mapping));
    }

    result.supported = true;
    result.rejectionReason.clear();
    return result;
}
