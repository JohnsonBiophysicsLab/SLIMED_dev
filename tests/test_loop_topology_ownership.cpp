#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <regex>
#include <sstream>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include "mesh/Loop_topology_ownership.hpp"

class LoopTopologyOwnershipTestAccess
{
public:
    enum Check : unsigned int
    {
        triangle = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::triangle),
        vertex_range = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::vertex_range),
        repeated_vertex = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::repeated_vertex),
        duplicate_face = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::duplicate_face),
        unused_vertex = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::unused_vertex),
        edge_incidence = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::edge_incidence),
        edge_orientation = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::edge_orientation),
        vertex_link = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::vertex_link),
        connected_mesh = static_cast<unsigned int>(
            LoopTopologyOwnershipIndex::ValidationCheck::connected_mesh)
    };

    static LoopTopologyBuildResult build_omitting(
        std::size_t vertex_count,
        const std::vector<Face>& faces,
        Check omitted)
    {
        return LoopTopologyOwnershipIndex::build_with_validation_checks(
            vertex_count, faces,
            LoopTopologyOwnershipIndex::all_validation_checks &
                ~static_cast<unsigned int>(omitted));
    }
};

namespace
{
struct Fixture
{
    std::size_t vertex_count = 0;
    std::vector<std::vector<double>> coordinates;
    std::vector<Face> faces;
};

void append_face(std::vector<Face>& faces,
                 std::initializer_list<int> vertices)
{
    faces.emplace_back();
    faces.back().adjacentVertices.assign(vertices.begin(), vertices.end());
}

std::vector<Face> tetrahedron_faces(int offset = 0,
                                    std::size_t extra_capacity = 0)
{
    std::vector<Face> faces;
    faces.reserve(4u + extra_capacity);
    append_face(faces, {offset + 0, offset + 2, offset + 1});
    append_face(faces, {offset + 0, offset + 1, offset + 3});
    append_face(faces, {offset + 0, offset + 3, offset + 2});
    append_face(faces, {offset + 1, offset + 2, offset + 3});
    return faces;
}

std::vector<std::vector<double>> read_double_csv(const std::string& path)
{
    std::ifstream input(path);
    EXPECT_TRUE(input.good()) << path;
    std::vector<std::vector<double>> rows;
    std::string line;
    while (std::getline(input, line))
    {
        if (line.empty())
        {
            continue;
        }
        std::vector<double> row;
        std::stringstream stream(line);
        std::string field;
        while (std::getline(stream, field, ','))
        {
            row.push_back(std::stod(field));
        }
        rows.push_back(std::move(row));
    }
    return rows;
}

std::vector<Face> read_face_csv(const std::string& path)
{
    std::ifstream input(path);
    EXPECT_TRUE(input.good()) << path;
    std::vector<std::vector<int>> rows;
    std::string line;
    while (std::getline(input, line))
    {
        if (line.empty())
        {
            continue;
        }
        std::vector<int> row;
        std::stringstream stream(line);
        std::string field;
        while (std::getline(stream, field, ','))
        {
            row.push_back(std::stoi(field));
        }
        rows.push_back(std::move(row));
    }
    std::vector<Face> faces;
    faces.reserve(rows.size());
    for (const auto& row : rows)
    {
        faces.emplace_back();
        faces.back().adjacentVertices = row;
    }
    return faces;
}

Fixture read_fixture(const std::string& root)
{
    Fixture fixture;
    fixture.coordinates = read_double_csv(root + "/vertices.csv");
    fixture.vertex_count = fixture.coordinates.size();
    fixture.faces = read_face_csv(root + "/faces.csv");
    return fixture;
}

std::vector<std::vector<int>> face_vertices(const std::vector<Face>& faces)
{
    std::vector<std::vector<int>> output;
    for (const Face& face : faces)
    {
        output.push_back(face.adjacentVertices);
    }
    return output;
}

std::string read_text(const std::string& path)
{
    std::ifstream input(path);
    EXPECT_TRUE(input.good()) << path;
    return std::string(std::istreambuf_iterator<char>(input),
                       std::istreambuf_iterator<char>());
}

std::vector<int> integer_array_after(const std::string& text,
                                     const std::string& key,
                                     std::size_t start)
{
    const std::size_t key_position = text.find('"' + key + '"', start);
    EXPECT_NE(key_position, std::string::npos) << key;
    const std::size_t array_start = text.find('[', key_position);
    EXPECT_NE(array_start, std::string::npos) << key;
    int depth = 0;
    std::size_t array_end = array_start;
    for (; array_end < text.size(); ++array_end)
    {
        if (text[array_end] == '[')
        {
            ++depth;
        }
        else if (text[array_end] == ']' && --depth == 0)
        {
            break;
        }
    }
    EXPECT_LT(array_end, text.size()) << key;
    const std::string array_text =
        text.substr(array_start, array_end - array_start + 1u);
    std::vector<int> values;
    const std::regex integer("-?[0-9]+");
    for (std::sregex_iterator it(array_text.begin(), array_text.end(), integer),
                              end;
         it != end; ++it)
    {
        values.push_back(std::stoi(it->str()));
    }
    return values;
}

bool has_edge(const LoopTopologyOwnership& ownership, int a, int b)
{
    const LoopTopologyEdgeKey key{std::min(a, b), std::max(a, b)};
    return std::binary_search(
        ownership.edges.begin(), ownership.edges.end(), key,
        [](const auto& lhs, const auto& rhs) {
            if constexpr (std::is_same_v<std::decay_t<decltype(lhs)>,
                                         LoopTopologyEdge>)
            {
                return lhs.key < rhs;
            }
            else
            {
                return lhs < rhs.key;
            }
        });
}

std::string ownership_bytes(const LoopTopologyOwnership& ownership)
{
    std::ostringstream output;
    for (const auto& edge : ownership.edges)
    {
        output << 'e' << edge.key.first << ',' << edge.key.second << ':';
        for (std::size_t index = 0; index < edge.incident_faces.size(); ++index)
        {
            const auto& halfedge = edge.halfedges[index];
            output << edge.incident_faces[index] << '@' << halfedge.from_vertex
                   << '>' << halfedge.to_vertex << ';';
        }
    }
    for (const auto& vertex : ownership.vertices)
    {
        output << 'v' << vertex.vertex << ':';
        for (const int face : vertex.incident_faces_ccw)
        {
            output << face << ',';
        }
    }
    return output.str();
}

void expect_accepted_fixture(const std::string& root,
                             std::size_t expected_vertices,
                             std::size_t expected_edges,
                             std::size_t expected_faces,
                             const std::vector<std::size_t>& expected_valences,
                             long long expected_euler)
{
    const Fixture fixture = read_fixture(root);
    ASSERT_EQ(fixture.vertex_count, expected_vertices);
    ASSERT_EQ(fixture.faces.size(), expected_faces);
    const auto result = LoopTopologyOwnershipIndex::build(
        fixture.vertex_count, fixture.faces);
    ASSERT_TRUE(result.accepted())
        << loop_topology_reason_code_name(result.reason);
    ASSERT_TRUE(result.ownership.has_value());
    EXPECT_EQ(result.ownership->edges.size(), expected_edges);
    EXPECT_EQ(result.diagnostics.edge_count, expected_edges);
    EXPECT_EQ(result.diagnostics.vertex_valences, expected_valences);
    EXPECT_EQ(result.diagnostics.euler_characteristic, expected_euler);
    EXPECT_EQ(result.diagnostics.connected_component_count, 1u);
    EXPECT_EQ(result.diagnostics.boundary_loop_count, 0u);
    EXPECT_TRUE(result.diagnostics.duplicate_faces.empty());
    EXPECT_TRUE(result.diagnostics.repeated_vertex_faces.empty());
    EXPECT_TRUE(result.diagnostics.inconsistently_oriented_edges.empty());
    EXPECT_TRUE(result.diagnostics.vertex_link_degree_failures.empty());
    EXPECT_TRUE(result.diagnostics.disconnected_vertex_links.empty());
    EXPECT_TRUE(result.diagnostics.unused_vertices.empty());
    for (const auto& edge : result.ownership->edges)
    {
        ASSERT_EQ(edge.incident_faces.size(), 2u);
        ASSERT_EQ(edge.halfedges.size(), 2u);
        EXPECT_EQ(edge.halfedges[0].from_vertex,
                  edge.halfedges[1].to_vertex);
        EXPECT_EQ(edge.halfedges[0].to_vertex,
                  edge.halfedges[1].from_vertex);
    }
}

void expect_rejected_without_face_mutation(
    std::size_t vertex_count,
    const std::vector<Face>& faces,
    LoopTopologyReasonCode expected_reason)
{
    const auto before = face_vertices(faces);
    const auto result = LoopTopologyOwnershipIndex::build(vertex_count, faces);
    EXPECT_FALSE(result.accepted());
    EXPECT_EQ(result.reason, expected_reason);
    EXPECT_FALSE(result.ownership.has_value());
    EXPECT_EQ(face_vertices(faces), before);
}

std::vector<Face> pinched_vertex_faces()
{
    std::vector<Face> faces;
    faces.reserve(8u);
    append_face(faces, {0, 2, 1});
    append_face(faces, {0, 1, 3});
    append_face(faces, {0, 3, 2});
    append_face(faces, {1, 2, 3});
    append_face(faces, {0, 5, 4});
    append_face(faces, {0, 4, 6});
    append_face(faces, {0, 6, 5});
    append_face(faces, {4, 5, 6});
    return faces;
}

std::vector<Face> disconnected_faces()
{
    std::vector<Face> faces;
    faces.reserve(8u);
    append_face(faces, {0, 2, 1});
    append_face(faces, {0, 1, 3});
    append_face(faces, {0, 3, 2});
    append_face(faces, {1, 2, 3});
    append_face(faces, {4, 6, 5});
    append_face(faces, {4, 5, 7});
    append_face(faces, {4, 7, 6});
    append_face(faces, {5, 6, 7});
    return faces;
}
} // namespace

TEST(LoopTopologyOwnership, AcceptsDeclaredClosedFixtureFamilies)
{
    expect_accepted_fixture(
        "./data/fixtures/candidates/closed_valence3_tetrahedron",
        4, 6, 4, {3, 3, 3, 3}, 2);
    expect_accepted_fixture(
        "./data/fixtures/candidates/closed_valence4_octahedron",
        6, 12, 8, {4, 4, 4, 4, 4, 4}, 2);
    expect_accepted_fixture(
        "./data/fixtures/closed_valence5",
        12, 30, 20, {5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5}, 2);
    expect_accepted_fixture(
        "./data/fixtures/candidates/closed_mixed_valence345",
        6, 12, 8, {5, 5, 4, 3, 4, 3}, 2);
    expect_accepted_fixture(
        "./data/fixtures/candidates/b2p_valence789",
        13, 33, 22, {9, 3, 7, 5, 8, 4, 5, 5, 5, 3, 4, 4, 4}, 2);
}

TEST(LoopTopologyOwnership, OrdersIncidentFacesCounterClockwiseFromConnectivity)
{
    const Fixture fixture = read_fixture(
        "./data/fixtures/candidates/b2p_valence789");
    const auto result = LoopTopologyOwnershipIndex::build(
        fixture.vertex_count, fixture.faces);
    ASSERT_TRUE(result.accepted());
    for (const auto& vertex : result.ownership->vertices)
    {
        ASSERT_EQ(vertex.incident_faces_ccw.size(),
                  result.diagnostics.vertex_valences[vertex.vertex]);
        for (std::size_t index = 0;
             index < vertex.incident_faces_ccw.size(); ++index)
        {
            const int current_id = vertex.incident_faces_ccw[index];
            const int next_id = vertex.incident_faces_ccw[
                (index + 1u) % vertex.incident_faces_ccw.size()];
            const auto& current = fixture.faces[current_id].adjacentVertices;
            const auto position = std::find(current.begin(), current.end(),
                                            vertex.vertex);
            ASSERT_NE(position, current.end());
            const std::size_t local = static_cast<std::size_t>(
                std::distance(current.begin(), position));
            const int previous = current[(local + 2u) % 3u];
            const auto& next = fixture.faces[next_id].adjacentVertices;
            const auto next_vertex =
                std::find(next.begin(), next.end(), vertex.vertex);
            ASSERT_NE(next_vertex, next.end());
            const std::size_t next_local = static_cast<std::size_t>(
                std::distance(next.begin(), next_vertex));
            EXPECT_EQ(next[(next_local + 1u) % 3u], previous);
        }
    }
}

TEST(LoopTopologyOwnership, SingleFlipFamilyMatchesAuthoritativeMetadata)
{
    const std::string root =
        "./data/fixtures/candidates/b2p_single_flip_family";
    const std::string metadata = read_text(root + "/family_metadata.json");
    const Fixture base = read_fixture(root + "/base");
    const auto base_before = face_vertices(base.faces);
    const auto base_result = LoopTopologyOwnershipIndex::build(
        base.vertex_count, base.faces);
    ASSERT_TRUE(base_result.accepted());

    for (const std::string member : {"flip_000", "flip_001", "flip_002"})
    {
        const std::size_t member_position = metadata.find(
            "\"member\": \"" + member + "\"");
        ASSERT_NE(member_position, std::string::npos);
        const std::size_t rewritten_position =
            metadata.find("\"rewritten\"", member_position);
        ASSERT_NE(rewritten_position, std::string::npos);
        const auto old_edge = integer_array_after(
            metadata, "old_edge", rewritten_position);
        const auto new_edge = integer_array_after(
            metadata, "new_edge", rewritten_position);
        const auto boundary = integer_array_after(
            metadata, "quad_boundary_cycle", rewritten_position);
        const auto base_rows = integer_array_after(
            metadata, "rewritten_base_rows", rewritten_position);
        const auto member_rows = integer_array_after(
            metadata, "rewritten_member_rows", rewritten_position);
        const auto base_oriented_faces = integer_array_after(
            metadata, "base_oriented_faces", rewritten_position);
        const auto member_oriented_faces = integer_array_after(
            metadata, "member_oriented_faces", rewritten_position);
        const auto endpoint_valences = integer_array_after(
            metadata, "endpoint_valences", member_position);
        const auto opposite_valences = integer_array_after(
            metadata, "opposite_valences", member_position);

        ASSERT_EQ(old_edge.size(), 2u);
        ASSERT_EQ(new_edge.size(), 2u);
        ASSERT_EQ(boundary.size(), 4u);
        ASSERT_EQ(base_rows.size(), 2u);
        ASSERT_EQ(member_rows.size(), 2u);
        ASSERT_EQ(base_oriented_faces.size(), 6u);
        ASSERT_EQ(member_oriented_faces.size(), 6u);
        ASSERT_EQ(endpoint_valences.size(), 2u);
        ASSERT_EQ(opposite_valences.size(), 2u);

        const Fixture variant = read_fixture(root + "/" + member);
        const auto variant_before = face_vertices(variant.faces);
        const auto variant_result = LoopTopologyOwnershipIndex::build(
            variant.vertex_count, variant.faces);
        ASSERT_TRUE(variant_result.accepted()) << member;

        EXPECT_TRUE(has_edge(*base_result.ownership,
                             old_edge[0], old_edge[1]));
        EXPECT_FALSE(has_edge(*variant_result.ownership,
                              old_edge[0], old_edge[1]));
        EXPECT_FALSE(has_edge(*base_result.ownership,
                              new_edge[0], new_edge[1]));
        EXPECT_TRUE(has_edge(*variant_result.ownership,
                             new_edge[0], new_edge[1]));
        for (std::size_t index = 0; index < boundary.size(); ++index)
        {
            const int a = boundary[index];
            const int b = boundary[(index + 1u) % boundary.size()];
            EXPECT_TRUE(has_edge(*base_result.ownership, a, b));
            EXPECT_TRUE(has_edge(*variant_result.ownership, a, b));
        }
        for (std::size_t row = 0; row < 2u; ++row)
        {
            EXPECT_EQ(base.faces[base_rows[row]].adjacentVertices,
                      (std::vector<int>{base_oriented_faces[row * 3u],
                                        base_oriented_faces[row * 3u + 1u],
                                        base_oriented_faces[row * 3u + 2u]}));
            EXPECT_EQ(variant.faces[member_rows[row]].adjacentVertices,
                      (std::vector<int>{member_oriented_faces[row * 3u],
                                        member_oriented_faces[row * 3u + 1u],
                                        member_oriented_faces[row * 3u + 2u]}));
        }

        std::vector<std::size_t> actual_endpoints{
            base_result.diagnostics.vertex_valences[old_edge[0]],
            base_result.diagnostics.vertex_valences[old_edge[1]]};
        std::vector<std::size_t> actual_opposites{
            base_result.diagnostics.vertex_valences[new_edge[0]],
            base_result.diagnostics.vertex_valences[new_edge[1]]};
        std::sort(actual_endpoints.begin(), actual_endpoints.end());
        std::sort(actual_opposites.begin(), actual_opposites.end());
        EXPECT_EQ(actual_endpoints,
                  (std::vector<std::size_t>{
                      static_cast<std::size_t>(endpoint_valences[0]),
                      static_cast<std::size_t>(endpoint_valences[1])}));
        EXPECT_EQ(actual_opposites,
                  (std::vector<std::size_t>{
                      static_cast<std::size_t>(opposite_valences[0]),
                      static_cast<std::size_t>(opposite_valences[1])}));
        for (const int vertex : old_edge)
        {
            EXPECT_EQ(variant_result.diagnostics.vertex_valences[vertex] + 1u,
                      base_result.diagnostics.vertex_valences[vertex]);
        }
        for (const int vertex : new_edge)
        {
            EXPECT_EQ(variant_result.diagnostics.vertex_valences[vertex],
                      base_result.diagnostics.vertex_valences[vertex] + 1u);
        }
        EXPECT_EQ(face_vertices(variant.faces), variant_before);
    }
    EXPECT_EQ(face_vertices(base.faces), base_before);
}

TEST(LoopTopologyOwnership, RejectsEachAdversarialClassWithoutMutation)
{
    auto boundary = tetrahedron_faces();
    boundary.pop_back();
    expect_rejected_without_face_mutation(
        4, boundary, LoopTopologyReasonCode::edge_has_one_incident_face);

    auto non_manifold_edge = tetrahedron_faces(0, 1);
    append_face(non_manifold_edge, {0, 1, 4});
    expect_rejected_without_face_mutation(
        5, non_manifold_edge,
        LoopTopologyReasonCode::edge_has_more_than_two_incident_faces);

    auto duplicate = tetrahedron_faces(0, 1);
    append_face(duplicate, {0, 2, 1});
    expect_rejected_without_face_mutation(
        4, duplicate, LoopTopologyReasonCode::duplicate_face);

    auto repeated = tetrahedron_faces(0, 1);
    append_face(repeated, {0, 0, 1});
    expect_rejected_without_face_mutation(
        4, repeated, LoopTopologyReasonCode::repeated_vertex_in_face);

    auto same_direction = tetrahedron_faces();
    same_direction[0].adjacentVertices = {0, 1, 2};
    expect_rejected_without_face_mutation(
        4, same_direction,
        LoopTopologyReasonCode::inconsistent_shared_edge_orientation);

    expect_rejected_without_face_mutation(
        7, pinched_vertex_faces(),
        LoopTopologyReasonCode::vertex_link_not_connected_degree_two_cycle);
    expect_rejected_without_face_mutation(
        5, tetrahedron_faces(), LoopTopologyReasonCode::unused_vertex);
    expect_rejected_without_face_mutation(
        8, disconnected_faces(), LoopTopologyReasonCode::disconnected_mesh);
}

TEST(LoopTopologyOwnership, FailsClosedForMalformedFaces)
{
    auto non_triangle = tetrahedron_faces(0, 1);
    append_face(non_triangle, {0, 1, 2, 3});
    expect_rejected_without_face_mutation(
        4, non_triangle, LoopTopologyReasonCode::non_triangular_face);

    auto out_of_range = tetrahedron_faces(0, 1);
    append_face(out_of_range, {0, 1, 4});
    expect_rejected_without_face_mutation(
        4, out_of_range, LoopTopologyReasonCode::vertex_id_out_of_range);
}

TEST(LoopTopologyOwnership, DeterministicOrderingAndCoordinateIndependence)
{
    Fixture fixture = read_fixture(
        "./data/fixtures/candidates/b2p_valence789");
    const auto first = LoopTopologyOwnershipIndex::build(
        fixture.vertex_count, fixture.faces);
    const auto second = LoopTopologyOwnershipIndex::build(
        fixture.vertex_count, fixture.faces);
    ASSERT_TRUE(first.accepted());
    ASSERT_TRUE(second.accepted());
    EXPECT_EQ(ownership_bytes(*first.ownership),
              ownership_bytes(*second.ownership));

    for (std::size_t vertex = 0; vertex < fixture.coordinates.size(); ++vertex)
    {
        for (std::size_t axis = 0; axis < fixture.coordinates[vertex].size();
             ++axis)
        {
            fixture.coordinates[vertex][axis] +=
                static_cast<double>((vertex + 1u) * (axis + 2u));
        }
    }
    const auto coordinate_changed = LoopTopologyOwnershipIndex::build(
        fixture.coordinates.size(), fixture.faces);
    ASSERT_TRUE(coordinate_changed.accepted());
    EXPECT_EQ(ownership_bytes(*first.ownership),
              ownership_bytes(*coordinate_changed.ownership));
}

TEST(LoopTopologyOwnership, PreservesSignedOrientationUnderWholeMeshReversal)
{
    Fixture fixture = read_fixture(
        "./data/fixtures/candidates/closed_valence4_octahedron");
    const auto outward = LoopTopologyOwnershipIndex::build(
        fixture.vertex_count, fixture.faces);
    ASSERT_TRUE(outward.accepted());
    for (Face& face : fixture.faces)
    {
        std::swap(face.adjacentVertices[1], face.adjacentVertices[2]);
    }
    const auto reversed = LoopTopologyOwnershipIndex::build(
        fixture.vertex_count, fixture.faces);
    ASSERT_TRUE(reversed.accepted());
    ASSERT_EQ(outward.ownership->edges.size(), reversed.ownership->edges.size());
    EXPECT_EQ(outward.diagnostics.vertex_valences,
              reversed.diagnostics.vertex_valences);
    EXPECT_EQ(outward.diagnostics.euler_characteristic,
              reversed.diagnostics.euler_characteristic);
    for (std::size_t edge = 0; edge < outward.ownership->edges.size(); ++edge)
    {
        const auto& first = outward.ownership->edges[edge];
        const auto& second = reversed.ownership->edges[edge];
        ASSERT_EQ(first.key, second.key);
        ASSERT_EQ(first.incident_faces, second.incident_faces);
        ASSERT_EQ(first.halfedges.size(), second.halfedges.size());
        for (std::size_t halfedge = 0; halfedge < first.halfedges.size();
             ++halfedge)
        {
            EXPECT_EQ(first.halfedges[halfedge].from_vertex,
                      second.halfedges[halfedge].to_vertex);
            EXPECT_EQ(first.halfedges[halfedge].to_vertex,
                      second.halfedges[halfedge].from_vertex);
        }
    }
}

TEST(LoopTopologyOwnership, EveryValidationCheckHasRejectionSensitivity)
{
    auto non_triangle = tetrahedron_faces(0, 1);
    append_face(non_triangle, {0, 1, 2, 3});
    auto out_of_range = tetrahedron_faces(0, 1);
    append_face(out_of_range, {0, 1, 4});
    auto repeated = tetrahedron_faces(0, 1);
    append_face(repeated, {0, 0, 1});
    auto duplicate = tetrahedron_faces(0, 1);
    append_face(duplicate, {0, 2, 1});
    auto boundary = tetrahedron_faces();
    boundary.pop_back();
    auto same_direction = tetrahedron_faces();
    same_direction[0].adjacentVertices = {0, 1, 2};

    auto expect_sensitive = [](std::size_t vertex_count,
                               const std::vector<Face>& faces,
                               LoopTopologyOwnershipTestAccess::Check check)
    {
        EXPECT_FALSE(LoopTopologyOwnershipIndex::build(
                         vertex_count, faces).accepted());
        EXPECT_TRUE(LoopTopologyOwnershipTestAccess::build_omitting(
                        vertex_count, faces, check).accepted());
    };
    expect_sensitive(4, non_triangle, LoopTopologyOwnershipTestAccess::triangle);
    expect_sensitive(4, out_of_range, LoopTopologyOwnershipTestAccess::vertex_range);
    expect_sensitive(4, repeated, LoopTopologyOwnershipTestAccess::repeated_vertex);
    expect_sensitive(4, duplicate, LoopTopologyOwnershipTestAccess::duplicate_face);
    const auto unused = tetrahedron_faces();
    expect_sensitive(5, unused, LoopTopologyOwnershipTestAccess::unused_vertex);
    expect_sensitive(4, boundary, LoopTopologyOwnershipTestAccess::edge_incidence);
    expect_sensitive(4, same_direction, LoopTopologyOwnershipTestAccess::edge_orientation);
    const auto pinched = pinched_vertex_faces();
    expect_sensitive(7, pinched, LoopTopologyOwnershipTestAccess::vertex_link);
    const auto disconnected = disconnected_faces();
    expect_sensitive(8, disconnected, LoopTopologyOwnershipTestAccess::connected_mesh);
}

TEST(LoopTopologyOwnership, ConstructionTimingMeasurementOnLargestFixture)
{
    const Fixture fixture = read_fixture(
        "./data/fixtures/candidates/b2_readiness_v1/regular_all6_torus");
    constexpr int repetitions = 100;
    const auto start = std::chrono::steady_clock::now();
    for (int repetition = 0; repetition < repetitions; ++repetition)
    {
        const auto result = LoopTopologyOwnershipIndex::build(
            fixture.vertex_count, fixture.faces);
        ASSERT_TRUE(result.accepted());
    }
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now() - start).count();
    std::cout << "loop_topology_construction_average_us="
              << static_cast<double>(elapsed) / repetitions
              << " fixture_faces=" << fixture.faces.size() << '\n';
}
