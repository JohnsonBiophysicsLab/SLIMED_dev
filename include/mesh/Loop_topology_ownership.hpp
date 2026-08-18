#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "mesh/Face.hpp"

using LoopTopologyVertexId = int;
using LoopTopologyFaceId = int;

struct LoopTopologyEdgeKey
{
    LoopTopologyVertexId first = -1;
    LoopTopologyVertexId second = -1;

    friend bool operator==(const LoopTopologyEdgeKey& lhs,
                           const LoopTopologyEdgeKey& rhs)
    {
        return lhs.first == rhs.first && lhs.second == rhs.second;
    }

    friend bool operator<(const LoopTopologyEdgeKey& lhs,
                          const LoopTopologyEdgeKey& rhs)
    {
        return std::tie(lhs.first, lhs.second) <
               std::tie(rhs.first, rhs.second);
    }
};

struct LoopTopologyHalfedgeDirection
{
    LoopTopologyVertexId from_vertex = -1;
    LoopTopologyVertexId to_vertex = -1;
    LoopTopologyFaceId face = -1;

    friend bool operator==(const LoopTopologyHalfedgeDirection& lhs,
                           const LoopTopologyHalfedgeDirection& rhs)
    {
        return lhs.from_vertex == rhs.from_vertex &&
               lhs.to_vertex == rhs.to_vertex && lhs.face == rhs.face;
    }
};

struct LoopTopologyEdge
{
    LoopTopologyEdgeKey key;
    std::vector<LoopTopologyFaceId> incident_faces;
    std::vector<LoopTopologyHalfedgeDirection> halfedges;

    friend bool operator==(const LoopTopologyEdge& lhs,
                           const LoopTopologyEdge& rhs)
    {
        return lhs.key == rhs.key &&
               lhs.incident_faces == rhs.incident_faces &&
               lhs.halfedges == rhs.halfedges;
    }
};

struct LoopTopologyVertexOwnership
{
    LoopTopologyVertexId vertex = -1;
    std::vector<LoopTopologyFaceId> incident_faces_ccw;

    friend bool operator==(const LoopTopologyVertexOwnership& lhs,
                           const LoopTopologyVertexOwnership& rhs)
    {
        return lhs.vertex == rhs.vertex &&
               lhs.incident_faces_ccw == rhs.incident_faces_ccw;
    }
};

struct LoopTopologyOwnership
{
    std::vector<LoopTopologyEdge> edges;
    std::vector<LoopTopologyVertexOwnership> vertices;

    friend bool operator==(const LoopTopologyOwnership& lhs,
                           const LoopTopologyOwnership& rhs)
    {
        return lhs.edges == rhs.edges && lhs.vertices == rhs.vertices;
    }
};

enum class LoopTopologyReasonCode
{
    none,
    non_triangular_face,
    vertex_id_out_of_range,
    repeated_vertex_in_face,
    duplicate_face,
    unused_vertex,
    edge_has_one_incident_face,
    edge_has_more_than_two_incident_faces,
    inconsistent_shared_edge_orientation,
    vertex_link_not_connected_degree_two_cycle,
    disconnected_mesh
};

const char* loop_topology_reason_code_name(LoopTopologyReasonCode code);

struct LoopTopologyEdgeIncidenceDiagnostic
{
    LoopTopologyEdgeKey edge;
    std::size_t incident_face_count = 0;

    friend bool operator==(const LoopTopologyEdgeIncidenceDiagnostic& lhs,
                           const LoopTopologyEdgeIncidenceDiagnostic& rhs)
    {
        return lhs.edge == rhs.edge &&
               lhs.incident_face_count == rhs.incident_face_count;
    }
};

struct LoopTopologyDuplicateFaceDiagnostic
{
    LoopTopologyFaceId first_face = -1;
    LoopTopologyFaceId duplicate_face = -1;

    friend bool operator==(const LoopTopologyDuplicateFaceDiagnostic& lhs,
                           const LoopTopologyDuplicateFaceDiagnostic& rhs)
    {
        return lhs.first_face == rhs.first_face &&
               lhs.duplicate_face == rhs.duplicate_face;
    }
};

struct LoopTopologyDiagnostics
{
    std::size_t vertex_count = 0;
    std::size_t face_count = 0;
    std::size_t edge_count = 0;
    std::size_t connected_component_count = 0;
    std::size_t boundary_loop_count = 0;
    long long euler_characteristic = 0;
    std::vector<std::size_t> vertex_valences;
    std::vector<LoopTopologyEdgeIncidenceDiagnostic> edge_incidence_counts;
    std::vector<LoopTopologyFaceId> non_triangular_faces;
    std::vector<LoopTopologyFaceId> vertex_id_out_of_range_faces;
    std::vector<LoopTopologyFaceId> repeated_vertex_faces;
    std::vector<LoopTopologyDuplicateFaceDiagnostic> duplicate_faces;
    std::vector<LoopTopologyEdgeKey> inconsistently_oriented_edges;
    std::vector<LoopTopologyVertexId> vertex_link_degree_failures;
    std::vector<LoopTopologyVertexId> disconnected_vertex_links;
    std::vector<LoopTopologyVertexId> unused_vertices;
};

struct LoopTopologyBuildResult
{
    LoopTopologyReasonCode reason = LoopTopologyReasonCode::none;
    LoopTopologyDiagnostics diagnostics;
    std::optional<LoopTopologyOwnership> ownership;

    bool accepted() const
    {
        return reason == LoopTopologyReasonCode::none && ownership.has_value();
    }
};

class LoopTopologyOwnershipIndex
{
public:
    static LoopTopologyBuildResult build(std::size_t vertex_count,
                                         const std::vector<Face>& faces);

private:
    enum class ValidationCheck : unsigned int
    {
        triangle = 1u << 0,
        vertex_range = 1u << 1,
        repeated_vertex = 1u << 2,
        duplicate_face = 1u << 3,
        unused_vertex = 1u << 4,
        edge_incidence = 1u << 5,
        edge_orientation = 1u << 6,
        vertex_link = 1u << 7,
        connected_mesh = 1u << 8
    };

    static constexpr unsigned int all_validation_checks =
        (1u << 9) - 1u;

    static LoopTopologyBuildResult build_with_validation_checks(
        std::size_t vertex_count,
        const std::vector<Face>& faces,
        unsigned int validation_checks);

    friend class LoopTopologyOwnershipTestAccess;
};
