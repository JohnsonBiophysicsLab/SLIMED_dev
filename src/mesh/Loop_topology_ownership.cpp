#include "mesh/Loop_topology_ownership.hpp"

#include <algorithm>
#include <array>
#include <map>
#include <queue>
#include <set>
#include <tuple>

namespace
{
struct ParsedFace
{
    LoopTopologyFaceId id = -1;
    std::array<LoopTopologyVertexId, 3> vertices{{-1, -1, -1}};
};

LoopTopologyEdgeKey edge_key(LoopTopologyVertexId a,
                             LoopTopologyVertexId b)
{
    return {std::min(a, b), std::max(a, b)};
}

std::array<LoopTopologyVertexId, 3> canonical_face(
    std::array<LoopTopologyVertexId, 3> vertices)
{
    std::sort(vertices.begin(), vertices.end());
    return vertices;
}

bool check_enabled(unsigned int checks, unsigned int check)
{
    return (checks & check) != 0u;
}

std::size_t count_graph_components(
    const std::vector<std::set<LoopTopologyVertexId>>& adjacency,
    const std::vector<bool>& included)
{
    std::vector<bool> visited(adjacency.size(), false);
    std::size_t components = 0;
    for (std::size_t start = 0; start < adjacency.size(); ++start)
    {
        if (!included[start] || visited[start])
        {
            continue;
        }
        ++components;
        std::queue<std::size_t> pending;
        pending.push(start);
        visited[start] = true;
        while (!pending.empty())
        {
            const std::size_t current = pending.front();
            pending.pop();
            for (const int neighbor : adjacency[current])
            {
                const std::size_t neighbor_index =
                    static_cast<std::size_t>(neighbor);
                if (!visited[neighbor_index])
                {
                    visited[neighbor_index] = true;
                    pending.push(neighbor_index);
                }
            }
        }
    }
    return components;
}

std::size_t count_boundary_loops(
    const std::vector<std::set<LoopTopologyVertexId>>& adjacency,
    const std::vector<bool>& included)
{
    std::vector<bool> visited(adjacency.size(), false);
    std::size_t loops = 0;
    for (std::size_t start = 0; start < adjacency.size(); ++start)
    {
        if (!included[start] || visited[start])
        {
            continue;
        }
        bool is_cycle = true;
        std::queue<std::size_t> pending;
        pending.push(start);
        visited[start] = true;
        while (!pending.empty())
        {
            const std::size_t current = pending.front();
            pending.pop();
            is_cycle = is_cycle && adjacency[current].size() == 2u;
            for (const int neighbor : adjacency[current])
            {
                const std::size_t neighbor_index =
                    static_cast<std::size_t>(neighbor);
                if (!visited[neighbor_index])
                {
                    visited[neighbor_index] = true;
                    pending.push(neighbor_index);
                }
            }
        }
        loops += is_cycle ? 1u : 0u;
    }
    return loops;
}

std::vector<LoopTopologyFaceId> incident_faces_ccw(
    LoopTopologyVertexId vertex,
    const std::vector<ParsedFace>& faces,
    const std::map<LoopTopologyEdgeKey, LoopTopologyEdge>& edges,
    bool vertex_link_valid)
{
    std::vector<LoopTopologyFaceId> incident;
    std::map<LoopTopologyFaceId, LoopTopologyFaceId> successor;
    for (const ParsedFace& face : faces)
    {
        const auto position =
            std::find(face.vertices.begin(), face.vertices.end(), vertex);
        if (position == face.vertices.end())
        {
            continue;
        }
        incident.push_back(face.id);
        if (!vertex_link_valid)
        {
            continue;
        }
        const std::size_t local = static_cast<std::size_t>(
            std::distance(face.vertices.begin(), position));
        const int previous = face.vertices[(local + 2u) % 3u];
        const auto edge = edges.find(edge_key(vertex, previous));
        if (edge == edges.end() || edge->second.incident_faces.size() != 2u)
        {
            vertex_link_valid = false;
            continue;
        }
        const auto& edge_faces = edge->second.incident_faces;
        successor[face.id] = edge_faces[0] == face.id
                                 ? edge_faces[1]
                                 : edge_faces[0];
    }

    std::sort(incident.begin(), incident.end());
    if (!vertex_link_valid || incident.empty())
    {
        return incident;
    }

    std::vector<LoopTopologyFaceId> ordered;
    ordered.reserve(incident.size());
    std::set<LoopTopologyFaceId> visited;
    LoopTopologyFaceId current = incident.front();
    while (visited.insert(current).second)
    {
        ordered.push_back(current);
        const auto next = successor.find(current);
        if (next == successor.end())
        {
            return incident;
        }
        current = next->second;
    }
    if (current != incident.front() || ordered.size() != incident.size())
    {
        return incident;
    }
    return ordered;
}
} // namespace

const char* loop_topology_reason_code_name(LoopTopologyReasonCode code)
{
    switch (code)
    {
    case LoopTopologyReasonCode::none:
        return "none";
    case LoopTopologyReasonCode::non_triangular_face:
        return "non_triangular_face";
    case LoopTopologyReasonCode::vertex_id_out_of_range:
        return "vertex_id_out_of_range";
    case LoopTopologyReasonCode::repeated_vertex_in_face:
        return "repeated_vertex_in_face";
    case LoopTopologyReasonCode::duplicate_face:
        return "duplicate_face";
    case LoopTopologyReasonCode::unused_vertex:
        return "unused_vertex";
    case LoopTopologyReasonCode::edge_has_one_incident_face:
        return "edge_has_one_incident_face";
    case LoopTopologyReasonCode::edge_has_more_than_two_incident_faces:
        return "edge_has_more_than_two_incident_faces";
    case LoopTopologyReasonCode::inconsistent_shared_edge_orientation:
        return "inconsistent_shared_edge_orientation";
    case LoopTopologyReasonCode::vertex_link_not_connected_degree_two_cycle:
        return "vertex_link_not_connected_degree_two_cycle";
    case LoopTopologyReasonCode::disconnected_mesh:
        return "disconnected_mesh";
    }
    return "unknown";
}

LoopTopologyBuildResult LoopTopologyOwnershipIndex::build(
    std::size_t vertex_count,
    const std::vector<Face>& faces)
{
    return build_with_validation_checks(vertex_count, faces,
                                        all_validation_checks);
}

LoopTopologyBuildResult
LoopTopologyOwnershipIndex::build_with_validation_checks(
    std::size_t vertex_count,
    const std::vector<Face>& faces,
    unsigned int validation_checks)
{
    LoopTopologyBuildResult result;
    result.diagnostics.vertex_count = vertex_count;
    result.diagnostics.face_count = faces.size();
    result.diagnostics.vertex_valences.assign(vertex_count, 0u);

    std::vector<ParsedFace> usable_faces;
    for (std::size_t face_index = 0; face_index < faces.size(); ++face_index)
    {
        const LoopTopologyFaceId face_id =
            static_cast<LoopTopologyFaceId>(face_index);
        const std::vector<int>& vertices = faces[face_index].adjacentVertices;
        if (vertices.size() != 3u)
        {
            result.diagnostics.non_triangular_faces.push_back(face_id);
            continue;
        }
        ParsedFace parsed{face_id,
                          {{vertices[0], vertices[1], vertices[2]}}};
        bool in_range = true;
        for (const int vertex : parsed.vertices)
        {
            in_range = in_range && vertex >= 0 &&
                       static_cast<std::size_t>(vertex) < vertex_count;
        }
        if (!in_range)
        {
            result.diagnostics.vertex_id_out_of_range_faces.push_back(face_id);
            continue;
        }
        if (parsed.vertices[0] == parsed.vertices[1] ||
            parsed.vertices[1] == parsed.vertices[2] ||
            parsed.vertices[2] == parsed.vertices[0])
        {
            result.diagnostics.repeated_vertex_faces.push_back(face_id);
            continue;
        }
        usable_faces.push_back(parsed);
    }

    std::map<std::array<int, 3>, LoopTopologyFaceId> first_face_by_vertices;
    std::set<LoopTopologyFaceId> duplicate_face_ids;
    std::vector<ParsedFace> unique_faces;
    for (const ParsedFace& face : usable_faces)
    {
        const auto inserted = first_face_by_vertices.emplace(
            canonical_face(face.vertices), face.id);
        if (!inserted.second)
        {
            result.diagnostics.duplicate_faces.push_back(
                {inserted.first->second, face.id});
            duplicate_face_ids.insert(face.id);
            continue;
        }
        unique_faces.push_back(face);
    }

    std::map<LoopTopologyEdgeKey, LoopTopologyEdge> diagnostic_edges;
    for (const ParsedFace& face : usable_faces)
    {
        for (std::size_t local = 0; local < 3u; ++local)
        {
            const int from = face.vertices[local];
            const int to = face.vertices[(local + 1u) % 3u];
            const LoopTopologyEdgeKey key = edge_key(from, to);
            LoopTopologyEdge& edge = diagnostic_edges[key];
            edge.key = key;
            edge.incident_faces.push_back(face.id);
            edge.halfedges.push_back({from, to, face.id});
        }
    }

    std::map<LoopTopologyEdgeKey, LoopTopologyEdge> ownership_edges;
    std::vector<bool> vertex_used(vertex_count, false);
    std::vector<std::set<int>> vertex_adjacency(vertex_count);
    for (const ParsedFace& face : unique_faces)
    {
        for (std::size_t local = 0; local < 3u; ++local)
        {
            const int from = face.vertices[local];
            const int to = face.vertices[(local + 1u) % 3u];
            const LoopTopologyEdgeKey key = edge_key(from, to);
            LoopTopologyEdge& edge = ownership_edges[key];
            edge.key = key;
            edge.incident_faces.push_back(face.id);
            edge.halfedges.push_back({from, to, face.id});
            vertex_used[static_cast<std::size_t>(from)] = true;
            vertex_used[static_cast<std::size_t>(to)] = true;
            vertex_adjacency[static_cast<std::size_t>(from)].insert(to);
            vertex_adjacency[static_cast<std::size_t>(to)].insert(from);
        }
    }

    result.diagnostics.edge_count = diagnostic_edges.size();
    for (const auto& item : diagnostic_edges)
    {
        result.diagnostics.edge_incidence_counts.push_back(
            {item.first, item.second.incident_faces.size()});
        if (item.second.incident_faces.size() == 2u)
        {
            const auto& first = item.second.halfedges[0];
            const auto& second = item.second.halfedges[1];
            if (first.from_vertex != second.to_vertex ||
                first.to_vertex != second.from_vertex)
            {
                result.diagnostics.inconsistently_oriented_edges.push_back(
                    item.first);
            }
        }
    }

    for (std::size_t vertex = 0; vertex < vertex_count; ++vertex)
    {
        result.diagnostics.vertex_valences[vertex] =
            vertex_adjacency[vertex].size();
        if (!vertex_used[vertex])
        {
            result.diagnostics.unused_vertices.push_back(
                static_cast<int>(vertex));
        }
    }
    result.diagnostics.connected_component_count =
        count_graph_components(vertex_adjacency, vertex_used);

    std::vector<std::set<int>> boundary_adjacency(vertex_count);
    std::vector<bool> boundary_vertex(vertex_count, false);
    for (const auto& item : ownership_edges)
    {
        if (item.second.incident_faces.size() == 1u)
        {
            const int a = item.first.first;
            const int b = item.first.second;
            boundary_adjacency[static_cast<std::size_t>(a)].insert(b);
            boundary_adjacency[static_cast<std::size_t>(b)].insert(a);
            boundary_vertex[static_cast<std::size_t>(a)] = true;
            boundary_vertex[static_cast<std::size_t>(b)] = true;
        }
    }
    result.diagnostics.boundary_loop_count =
        count_boundary_loops(boundary_adjacency, boundary_vertex);
    result.diagnostics.euler_characteristic =
        static_cast<long long>(vertex_count) -
        static_cast<long long>(diagnostic_edges.size()) +
        static_cast<long long>(faces.size());

    std::vector<bool> valid_vertex_link(vertex_count, false);
    for (std::size_t vertex = 0; vertex < vertex_count; ++vertex)
    {
        if (!vertex_used[vertex])
        {
            continue;
        }
        bool edge_prerequisites_hold = true;
        for (const int neighbor : vertex_adjacency[vertex])
        {
            const auto edge = ownership_edges.find(
                edge_key(static_cast<int>(vertex), neighbor));
            if (edge == ownership_edges.end() ||
                edge->second.incident_faces.size() != 2u)
            {
                edge_prerequisites_hold = false;
                break;
            }
        }
        if (!edge_prerequisites_hold)
        {
            continue;
        }

        std::map<int, std::set<int>> link_adjacency;
        for (const ParsedFace& face : unique_faces)
        {
            const auto position = std::find(face.vertices.begin(),
                                            face.vertices.end(),
                                            static_cast<int>(vertex));
            if (position == face.vertices.end())
            {
                continue;
            }
            std::array<int, 2> other{{-1, -1}};
            std::size_t output = 0;
            for (const int face_vertex : face.vertices)
            {
                if (face_vertex != static_cast<int>(vertex))
                {
                    other[output++] = face_vertex;
                }
            }
            link_adjacency[other[0]].insert(other[1]);
            link_adjacency[other[1]].insert(other[0]);
        }
        bool degree_two = !link_adjacency.empty();
        for (const auto& link_vertex : link_adjacency)
        {
            degree_two = degree_two && link_vertex.second.size() == 2u;
        }
        if (!degree_two)
        {
            result.diagnostics.vertex_link_degree_failures.push_back(
                static_cast<int>(vertex));
            continue;
        }
        std::set<int> visited;
        std::queue<int> pending;
        pending.push(link_adjacency.begin()->first);
        visited.insert(link_adjacency.begin()->first);
        while (!pending.empty())
        {
            const int current = pending.front();
            pending.pop();
            for (const int neighbor : link_adjacency[current])
            {
                if (visited.insert(neighbor).second)
                {
                    pending.push(neighbor);
                }
            }
        }
        if (visited.size() != link_adjacency.size())
        {
            result.diagnostics.disconnected_vertex_links.push_back(
                static_cast<int>(vertex));
            continue;
        }
        valid_vertex_link[vertex] = true;
    }

    auto has_unattributed_edge_count = [&](bool more_than_two) {
        for (const auto& item : diagnostic_edges)
        {
            bool derived_from_duplicate = false;
            for (const int face : item.second.incident_faces)
            {
                derived_from_duplicate = derived_from_duplicate ||
                    duplicate_face_ids.count(face) != 0u;
            }
            if (derived_from_duplicate)
            {
                continue;
            }
            const std::size_t count = item.second.incident_faces.size();
            if ((more_than_two && count > 2u) ||
                (!more_than_two && count == 1u))
            {
                return true;
            }
        }
        return false;
    };

    if (check_enabled(validation_checks,
                      static_cast<unsigned int>(ValidationCheck::triangle)) &&
        !result.diagnostics.non_triangular_faces.empty())
    {
        result.reason = LoopTopologyReasonCode::non_triangular_face;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::vertex_range)) &&
             !result.diagnostics.vertex_id_out_of_range_faces.empty())
    {
        result.reason = LoopTopologyReasonCode::vertex_id_out_of_range;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::repeated_vertex)) &&
             !result.diagnostics.repeated_vertex_faces.empty())
    {
        result.reason = LoopTopologyReasonCode::repeated_vertex_in_face;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::duplicate_face)) &&
             !result.diagnostics.duplicate_faces.empty())
    {
        result.reason = LoopTopologyReasonCode::duplicate_face;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::unused_vertex)) &&
             !result.diagnostics.unused_vertices.empty())
    {
        result.reason = LoopTopologyReasonCode::unused_vertex;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::edge_incidence)) &&
             has_unattributed_edge_count(true))
    {
        result.reason =
            LoopTopologyReasonCode::edge_has_more_than_two_incident_faces;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::edge_incidence)) &&
             has_unattributed_edge_count(false))
    {
        result.reason = LoopTopologyReasonCode::edge_has_one_incident_face;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::edge_orientation)) &&
             !result.diagnostics.inconsistently_oriented_edges.empty())
    {
        result.reason =
            LoopTopologyReasonCode::inconsistent_shared_edge_orientation;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::vertex_link)) &&
             (!result.diagnostics.vertex_link_degree_failures.empty() ||
              !result.diagnostics.disconnected_vertex_links.empty()))
    {
        result.reason = LoopTopologyReasonCode::
            vertex_link_not_connected_degree_two_cycle;
    }
    else if (check_enabled(validation_checks,
                           static_cast<unsigned int>(ValidationCheck::connected_mesh)) &&
             result.diagnostics.connected_component_count != 1u)
    {
        result.reason = LoopTopologyReasonCode::disconnected_mesh;
    }

    if (result.reason != LoopTopologyReasonCode::none)
    {
        return result;
    }

    LoopTopologyOwnership candidate;
    candidate.edges.reserve(ownership_edges.size());
    for (auto& item : ownership_edges)
    {
        auto& edge = item.second;
        std::vector<std::size_t> order(edge.incident_faces.size());
        for (std::size_t index = 0; index < order.size(); ++index)
        {
            order[index] = index;
        }
        std::sort(order.begin(), order.end(), [&](std::size_t lhs,
                                                   std::size_t rhs) {
            return edge.incident_faces[lhs] < edge.incident_faces[rhs];
        });
        LoopTopologyEdge ordered_edge;
        ordered_edge.key = edge.key;
        for (const std::size_t index : order)
        {
            ordered_edge.incident_faces.push_back(edge.incident_faces[index]);
            ordered_edge.halfedges.push_back(edge.halfedges[index]);
        }
        candidate.edges.push_back(std::move(ordered_edge));
    }
    candidate.vertices.reserve(vertex_count);
    for (std::size_t vertex = 0; vertex < vertex_count; ++vertex)
    {
        candidate.vertices.push_back(
            {static_cast<int>(vertex),
             incident_faces_ccw(static_cast<int>(vertex), unique_faces,
                                ownership_edges,
                                valid_vertex_link[vertex])});
    }
    result.ownership = std::move(candidate);
    return result;
}
