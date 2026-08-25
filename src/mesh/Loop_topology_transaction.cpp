#include "mesh/Loop_topology_transaction.hpp"

#include <algorithm>
#include <limits>
#include <type_traits>
#include <utility>

#include "mesh/Mesh.hpp"

namespace slimed::loop_topology
{

namespace
{
using IntVector = std::vector<int>;

struct DerivedConnectivity
{
    std::vector<IntVector> face_neighbors;
    std::vector<IntVector> face_one_rings;
    std::vector<IntVector> vertex_faces;
    std::vector<IntVector> vertex_neighbors;
};

LoopTopologyEdgeKey undirected_edge(int first, int second)
{
    return {std::min(first, second), std::max(first, second)};
}

bool build_derived_connectivity(
    const std::vector<IntVector>& candidate_face_vertices,
    const LoopTopologyOwnership& ownership,
    DerivedConnectivity& derived)
{
    derived.face_neighbors.assign(candidate_face_vertices.size(),
                                  IntVector(3u, -1));
    derived.face_one_rings.resize(candidate_face_vertices.size());
    derived.vertex_faces.resize(ownership.vertices.size());
    derived.vertex_neighbors.resize(ownership.vertices.size());

    for (const LoopTopologyEdge& edge : ownership.edges)
    {
        if (edge.incident_faces.size() != 2u)
        {
            return false;
        }
        for (std::size_t side = 0; side < 2u; ++side)
        {
            const int face_id = edge.incident_faces[side];
            if (face_id < 0 ||
                static_cast<std::size_t>(face_id) >=
                    candidate_face_vertices.size())
            {
                return false;
            }
            const IntVector& vertices =
                candidate_face_vertices[static_cast<std::size_t>(face_id)];
            bool installed = false;
            for (std::size_t local = 0; local < 3u; ++local)
            {
                if (undirected_edge(vertices[local],
                                    vertices[(local + 1u) % 3u]) == edge.key)
                {
                    if (installed ||
                        derived.face_neighbors[
                            static_cast<std::size_t>(face_id)][local] != -1)
                    {
                        return false;
                    }
                    derived.face_neighbors[
                        static_cast<std::size_t>(face_id)][local] =
                        edge.incident_faces[1u - side];
                    installed = true;
                }
            }
            if (!installed)
            {
                return false;
            }
        }
    }

    for (const IntVector& neighbors : derived.face_neighbors)
    {
        if (std::find(neighbors.begin(), neighbors.end(), -1) !=
            neighbors.end())
        {
            return false;
        }
    }

    for (const LoopTopologyVertexOwnership& vertex : ownership.vertices)
    {
        if (vertex.vertex < 0 ||
            static_cast<std::size_t>(vertex.vertex) >=
                ownership.vertices.size())
        {
            return false;
        }
        const std::size_t vertex_id =
            static_cast<std::size_t>(vertex.vertex);
        derived.vertex_faces[vertex_id] = vertex.incident_faces_ccw;
        IntVector& neighbors = derived.vertex_neighbors[vertex_id];
        neighbors.reserve(vertex.incident_faces_ccw.size());
        for (const int face_id : vertex.incident_faces_ccw)
        {
            if (face_id < 0 ||
                static_cast<std::size_t>(face_id) >=
                    candidate_face_vertices.size())
            {
                return false;
            }
            const IntVector& face =
                candidate_face_vertices[static_cast<std::size_t>(face_id)];
            const auto position =
                std::find(face.begin(), face.end(), vertex.vertex);
            if (position == face.end())
            {
                return false;
            }
            const std::size_t local = static_cast<std::size_t>(
                std::distance(face.begin(), position));
            neighbors.push_back(face[(local + 1u) % 3u]);
        }
        IntVector unique_neighbors = neighbors;
        std::sort(unique_neighbors.begin(), unique_neighbors.end());
        if (std::adjacent_find(unique_neighbors.begin(),
                               unique_neighbors.end()) !=
            unique_neighbors.end())
        {
            return false;
        }
    }
    return true;
}

std::vector<std::vector<int>> face_vertices(const Mesh& mesh)
{
    std::vector<std::vector<int>> connectivity;
    connectivity.reserve(mesh.faces.size());
    for (const Face& face : mesh.faces)
    {
        connectivity.push_back(face.adjacentVertices);
    }
    return connectivity;
}

bool face_vertices_equal(
    const Mesh& mesh,
    const std::vector<std::vector<int>>& expected) noexcept
{
    if (mesh.faces.size() != expected.size())
    {
        return false;
    }
    for (std::size_t face = 0; face < mesh.faces.size(); ++face)
    {
        if (mesh.faces[face].adjacentVertices != expected[face])
        {
            return false;
        }
    }
    return true;
}

LoopTopologyTransactionResult result(
    LoopTopologyTransactionReason reason,
    LoopTopologyReasonCode topology_reason = LoopTopologyReasonCode::none)
{
    return {reason, topology_reason};
}
} // namespace

static_assert(noexcept(std::declval<IntVector&>().swap(
                  std::declval<IntVector&>())),
              "topology commit requires noexcept vector swaps");

const char* loop_topology_transaction_reason_name(
    LoopTopologyTransactionReason reason_code)
{
    switch (reason_code)
    {
    case LoopTopologyTransactionReason::none:
        return "none";
    case LoopTopologyTransactionReason::already_staged:
        return "already_staged";
    case LoopTopologyTransactionReason::not_staged:
        return "not_staged";
    case LoopTopologyTransactionReason::already_finalized:
        return "already_finalized";
    case LoopTopologyTransactionReason::face_count_changed:
        return "face_count_changed";
    case LoopTopologyTransactionReason::topology_unchanged:
        return "topology_unchanged";
    case LoopTopologyTransactionReason::topology_rejected:
        return "topology_rejected";
    case LoopTopologyTransactionReason::derived_rebuild_failed:
        return "derived_rebuild_failed";
    case LoopTopologyTransactionReason::source_generation_changed:
        return "source_generation_changed";
    case LoopTopologyTransactionReason::source_cardinality_changed:
        return "source_cardinality_changed";
    case LoopTopologyTransactionReason::source_connectivity_changed:
        return "source_connectivity_changed";
    case LoopTopologyTransactionReason::generation_overflow:
        return "generation_overflow";
    case LoopTopologyTransactionReason::invalidation_failed:
        return "invalidation_failed";
    }
    return "unknown";
}

LoopTopologyTransaction::LoopTopologyTransaction(Mesh& mesh)
    : mesh_(mesh),
      source_generation_(mesh.topology_generation()),
      source_vertex_count_(mesh.vertices.size()),
      source_face_count_(mesh.faces.size()),
      source_face_vertices_(face_vertices(mesh))
{
}

LoopTopologyTransactionResult LoopTopologyTransaction::stage(
    const std::vector<std::vector<int>>& candidate_face_vertices)
{
    if (state_ == LoopTopologyTransactionState::staged)
    {
        return result(LoopTopologyTransactionReason::already_staged);
    }
    if (state_ != LoopTopologyTransactionState::open)
    {
        return result(LoopTopologyTransactionReason::already_finalized);
    }
    if (candidate_face_vertices.size() != source_face_count_)
    {
        state_ = LoopTopologyTransactionState::rejected;
        return result(LoopTopologyTransactionReason::face_count_changed);
    }
    if (candidate_face_vertices == source_face_vertices_)
    {
        state_ = LoopTopologyTransactionState::rejected;
        return result(LoopTopologyTransactionReason::topology_unchanged);
    }

    std::vector<Face> candidate_faces;
    candidate_faces.reserve(candidate_face_vertices.size());
    for (const IntVector& vertices : candidate_face_vertices)
    {
        candidate_faces.emplace_back();
        candidate_faces.back().adjacentVertices = vertices;
    }
    LoopTopologyBuildResult candidate_validation =
        LoopTopologyOwnershipIndex::build(source_vertex_count_,
                                          candidate_faces);
    if (!candidate_validation.accepted())
    {
        const LoopTopologyReasonCode topology_reason =
            candidate_validation.reason;
        validation_ = std::move(candidate_validation);
        state_ = LoopTopologyTransactionState::rejected;
        return result(LoopTopologyTransactionReason::topology_rejected,
                      topology_reason);
    }

    DerivedConnectivity derived;
    if (!build_derived_connectivity(candidate_face_vertices,
                                    *candidate_validation.ownership,
                                    derived))
    {
        validation_ = std::move(candidate_validation);
        state_ = LoopTopologyTransactionState::rejected;
        return result(LoopTopologyTransactionReason::derived_rebuild_failed);
    }

    validation_ = std::move(candidate_validation);
    staged_face_vertices_ = candidate_face_vertices;
    staged_face_neighbors_ = std::move(derived.face_neighbors);
    staged_face_one_rings_ = std::move(derived.face_one_rings);
    staged_vertex_faces_ = std::move(derived.vertex_faces);
    staged_vertex_neighbors_ = std::move(derived.vertex_neighbors);
    state_ = LoopTopologyTransactionState::staged;
    return result(LoopTopologyTransactionReason::none);
}

LoopTopologyTransactionResult LoopTopologyTransaction::commit() noexcept
{
    if (state_ != LoopTopologyTransactionState::staged)
    {
        return result(state_ == LoopTopologyTransactionState::open
                          ? LoopTopologyTransactionReason::not_staged
                          : LoopTopologyTransactionReason::already_finalized);
    }
    if (mesh_.topology_generation() != source_generation_)
    {
        state_ = LoopTopologyTransactionState::rejected;
        return result(
            LoopTopologyTransactionReason::source_generation_changed);
    }
    if (mesh_.vertices.size() != source_vertex_count_ ||
        mesh_.faces.size() != source_face_count_)
    {
        state_ = LoopTopologyTransactionState::rejected;
        return result(
            LoopTopologyTransactionReason::source_cardinality_changed);
    }
    if (!face_vertices_equal(mesh_, source_face_vertices_))
    {
        state_ = LoopTopologyTransactionState::rejected;
        return result(
            LoopTopologyTransactionReason::source_connectivity_changed);
    }
    if (source_generation_ ==
        std::numeric_limits<std::uint64_t>::max())
    {
        state_ = LoopTopologyTransactionState::rejected;
        return result(LoopTopologyTransactionReason::generation_overflow);
    }

    try
    {
        mesh_.invalidate_topology_derived_state();
    }
    catch (...)
    {
        state_ = LoopTopologyTransactionState::rejected;
        return result(LoopTopologyTransactionReason::invalidation_failed);
    }

    for (std::size_t face = 0; face < mesh_.faces.size(); ++face)
    {
        mesh_.faces[face].adjacentVertices.swap(staged_face_vertices_[face]);
        mesh_.faces[face].adjacentFaces.swap(staged_face_neighbors_[face]);
        mesh_.faces[face].oneRingVertices.swap(staged_face_one_rings_[face]);
    }
    for (std::size_t vertex = 0; vertex < mesh_.vertices.size(); ++vertex)
    {
        mesh_.vertices[vertex].adjacentFaces.swap(staged_vertex_faces_[vertex]);
        mesh_.vertices[vertex].adjacentVertices.swap(
            staged_vertex_neighbors_[vertex]);
    }
    state_ = LoopTopologyTransactionState::committed;
    return result(LoopTopologyTransactionReason::none);
}

LoopTopologyTransactionResult LoopTopologyTransaction::rollback() noexcept
{
    if (state_ != LoopTopologyTransactionState::staged)
    {
        return result(state_ == LoopTopologyTransactionState::open
                          ? LoopTopologyTransactionReason::not_staged
                          : LoopTopologyTransactionReason::already_finalized);
    }
    state_ = LoopTopologyTransactionState::rolled_back;
    return result(LoopTopologyTransactionReason::none);
}

} // namespace slimed::loop_topology
