#include <gtest/gtest.h>

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

#include "io/io.hpp"
#include "mesh/Mesh.hpp"

using namespace slimed::loop_topology;

static_assert(sizeof(LoopTopologyTransaction) > 0,
              "Mesh.hpp must claim the transaction friend type by definition");

namespace
{
struct Fixture
{
    std::vector<std::vector<double>> coordinates;
    std::vector<std::vector<int>> faces;
};

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

std::vector<std::vector<int>> read_int_csv(const std::string& path)
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
    return rows;
}

Fixture read_fixture(const std::string& root)
{
    return {read_double_csv(root + "/vertices.csv"),
            read_int_csv(root + "/faces.csv")};
}

std::vector<std::vector<int>> face_vertices(const Mesh& mesh)
{
    std::vector<std::vector<int>> result;
    result.reserve(mesh.faces.size());
    for (const Face& face : mesh.faces)
    {
        result.push_back(face.adjacentVertices);
    }
    return result;
}

void append_vector(std::ostringstream& output, const std::vector<int>& values)
{
    output << values.size() << ':';
    for (const int value : values)
    {
        output << value << ',';
    }
}

void append_matrix(std::ostringstream& output, const Matrix& matrix)
{
    for (int row = 0; row < 3; ++row)
    {
        output << matrix.get(row, 0) << ',';
    }
}

std::string full_observable_snapshot(const Mesh& mesh)
{
    std::ostringstream output;
    output << std::setprecision(std::numeric_limits<double>::max_digits10)
           << mesh.topology_generation() << '|' << mesh.vertices.size()
           << '|' << mesh.faces.size() << '|';
    for (const Vertex& vertex : mesh.vertices)
    {
        output << 'v' << vertex.index << ',' << vertex.layerIndex << ','
               << static_cast<int>(vertex.type) << ','
               << vertex.reflectiveVertexIndex << ',' << vertex.isBoundary
               << ',' << vertex.isGhost << ';';
        append_matrix(output, vertex.coord);
        append_matrix(output, vertex.coordPrev);
        append_matrix(output, vertex.coordRef);
        append_matrix(output, vertex.normVector);
        append_matrix(output, vertex.force.forceTotal);
        append_matrix(output, vertex.forcePrev.forceTotal);
        append_vector(output, vertex.adjacentVertices);
        append_vector(output, vertex.adjacentFaces);
    }
    for (const Face& face : mesh.faces)
    {
        output << 'f' << face.index << ',' << face.layerIndex << ','
               << face.isBoundary << ',' << face.isGhost << ','
               << face.isInsertionPatch << ',' << face.spontCurvature << ','
               << face.meanCurvature << ',' << face.elementArea << ','
               << face.elementVolume << ',' << face.energyPrev.energyTotal
               << ',' << face.energy.energyTotal << ';';
        append_matrix(output, face.normVector);
        append_vector(output, face.adjacentVertices);
        append_vector(output, face.adjacentFaces);
        append_vector(output, face.oneRingVertices);
    }
    return output.str();
}

std::string nonconnectivity_snapshot(const Mesh& mesh)
{
    std::ostringstream output;
    output << std::setprecision(std::numeric_limits<double>::max_digits10)
           << mesh.vertices.size() << '|' << mesh.faces.size() << '|';
    for (const Vertex& vertex : mesh.vertices)
    {
        output << vertex.index << ',' << vertex.layerIndex << ','
               << static_cast<int>(vertex.type) << ','
               << vertex.reflectiveVertexIndex << ',' << vertex.isBoundary
               << ',' << vertex.isGhost << ';';
        append_matrix(output, vertex.coord);
        append_matrix(output, vertex.coordPrev);
        append_matrix(output, vertex.coordRef);
        append_matrix(output, vertex.normVector);
        append_matrix(output, vertex.force.forceTotal);
        append_matrix(output, vertex.forcePrev.forceTotal);
    }
    for (const Face& face : mesh.faces)
    {
        output << face.index << ',' << face.layerIndex << ','
               << face.isBoundary << ',' << face.isGhost << ','
               << face.isInsertionPatch << ',' << face.spontCurvature << ','
               << face.meanCurvature << ',' << face.elementArea << ','
               << face.elementVolume << ',' << face.energyPrev.energyTotal
               << ',' << face.energy.energyTotal << ';';
        append_matrix(output, face.normVector);
    }
    return output.str();
}

void set_matrix_marker(Matrix& matrix, double marker)
{
    matrix = mat_calloc(3, 1);
    for (int row = 0; row < 3; ++row)
    {
        matrix.set(row, 0, marker + static_cast<double>(row) * 0.01);
    }
}

void populate_mesh(Mesh& mesh, const Fixture& fixture)
{
    mesh.vertices.reserve(fixture.coordinates.size());
    for (std::size_t vertex = 0; vertex < fixture.coordinates.size(); ++vertex)
    {
        const auto& coordinate = fixture.coordinates[vertex];
        mesh.vertices.emplace_back(static_cast<int>(vertex), coordinate[0],
                                   coordinate[1], coordinate[2]);
        Vertex& installed = mesh.vertices.back();
        installed.layerIndex = static_cast<int>(vertex % 3u) - 1;
        installed.type = vertex % 2u == 0u ? VertexType::Real
                                           : VertexType::FixedBoundary;
        installed.reflectiveVertexIndex =
            static_cast<int>((vertex + 1u) % fixture.coordinates.size());
        installed.isBoundary = vertex % 3u == 0u;
        installed.isGhost = vertex % 5u == 0u;
        set_matrix_marker(installed.coordPrev, 10.0 + vertex);
        set_matrix_marker(installed.coordRef, 20.0 + vertex);
        set_matrix_marker(installed.normVector, 30.0 + vertex);
        set_matrix_marker(installed.force.forceTotal, 40.0 + vertex);
        set_matrix_marker(installed.forcePrev.forceTotal, 50.0 + vertex);
        installed.adjacentVertices = {901, static_cast<int>(vertex)};
        installed.adjacentFaces = {902, static_cast<int>(vertex)};
    }

    mesh.faces.reserve(fixture.faces.size());
    for (std::size_t face = 0; face < fixture.faces.size(); ++face)
    {
        mesh.faces.emplace_back();
        Face& installed = mesh.faces.back();
        installed.index = static_cast<int>(face);
        installed.layerIndex = static_cast<int>(face % 3u) - 1;
        installed.isBoundary = face % 2u == 0u;
        installed.isGhost = face % 3u == 0u;
        installed.isInsertionPatch = face % 5u == 0u;
        installed.spontCurvature = 0.25 + static_cast<double>(face);
        installed.meanCurvature = 0.5 + static_cast<double>(face);
        installed.elementArea = 1.0 + static_cast<double>(face);
        installed.elementVolume = 2.0 + static_cast<double>(face);
        installed.energyPrev.energyTotal = 3.0 + static_cast<double>(face);
        installed.energy.energyTotal = 4.0 + static_cast<double>(face);
        set_matrix_marker(installed.normVector, 60.0 + face);
        installed.adjacentVertices = fixture.faces[face];
        installed.adjacentFaces = {903, static_cast<int>(face)};
        installed.oneRingVertices = {904, static_cast<int>(face)};
    }
}

Param quiet_param()
{
    Param param;
    param.VERBOSE_MODE = false;
    return param;
}

const std::string kFlipRoot =
    "./data/fixtures/candidates/b2p_single_flip_family";

const LoopTopologyEdge* find_edge(const LoopTopologyOwnership& ownership,
                                  int first,
                                  int second)
{
    const LoopTopologyEdgeKey key{std::min(first, second),
                                  std::max(first, second)};
    const auto found = std::lower_bound(
        ownership.edges.begin(), ownership.edges.end(), key,
        [](const LoopTopologyEdge& edge, const LoopTopologyEdgeKey& value) {
            return edge.key < value;
        });
    return found != ownership.edges.end() && found->key == key
               ? &*found
               : nullptr;
}
} // namespace

TEST(LoopTopologyTransaction, StageAndExplicitRollbackLeaveExactLiveState)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");
    const Fixture candidate = read_fixture(kFlipRoot + "/flip_000");
    Param param = quiet_param();
    Mesh mesh(param);
    populate_mesh(mesh, base);
    const std::string before = full_observable_snapshot(mesh);

    LoopTopologyTransaction transaction(mesh);
    const auto staged = transaction.stage(candidate.faces);
    ASSERT_TRUE(staged.accepted());
    EXPECT_EQ(transaction.state(), LoopTopologyTransactionState::staged);
    EXPECT_TRUE(transaction.validation_result().accepted());
    EXPECT_EQ(full_observable_snapshot(mesh), before);

    const auto rolled_back = transaction.rollback();
    EXPECT_TRUE(rolled_back.accepted());
    EXPECT_EQ(transaction.state(), LoopTopologyTransactionState::rolled_back);
    EXPECT_EQ(full_observable_snapshot(mesh), before);
    EXPECT_EQ(transaction.commit().reason,
              LoopTopologyTransactionReason::already_finalized);
}

TEST(LoopTopologyTransaction,
     CommitInstallsPrebuiltConnectivityAndAdvancesGenerationOnce)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");
    const Fixture candidate = read_fixture(kFlipRoot + "/flip_000");
    Param param = quiet_param();
    Mesh mesh(param);
    populate_mesh(mesh, base);
    const std::uint64_t generation_before = mesh.topology_generation();
    const std::string nonconnectivity_before =
        nonconnectivity_snapshot(mesh);

    LoopTopologyTransaction transaction(mesh);
    ASSERT_TRUE(transaction.stage(candidate.faces).accepted());
    const LoopTopologyOwnership expected =
        *transaction.validation_result().ownership;
    ASSERT_TRUE(transaction.commit().accepted());

    EXPECT_EQ(transaction.state(), LoopTopologyTransactionState::committed);
    EXPECT_EQ(mesh.topology_generation(), generation_before + 1u);
    EXPECT_EQ(face_vertices(mesh), candidate.faces);
    EXPECT_EQ(nonconnectivity_snapshot(mesh), nonconnectivity_before);

    const auto installed = LoopTopologyOwnershipIndex::build(
        mesh.vertices.size(), mesh.faces);
    ASSERT_TRUE(installed.accepted());
    EXPECT_EQ(installed.ownership, transaction.validation_result().ownership);
    ASSERT_EQ(expected.vertices.size(), mesh.vertices.size());
    for (const LoopTopologyVertexOwnership& vertex : expected.vertices)
    {
        const Vertex& installed_vertex =
            mesh.vertices[static_cast<std::size_t>(vertex.vertex)];
        EXPECT_EQ(installed_vertex.adjacentFaces,
                  vertex.incident_faces_ccw);
        ASSERT_EQ(installed_vertex.adjacentVertices.size(),
                  vertex.incident_faces_ccw.size());
        for (std::size_t index = 0;
             index < vertex.incident_faces_ccw.size(); ++index)
        {
            const auto& face = candidate.faces[static_cast<std::size_t>(
                vertex.incident_faces_ccw[index])];
            const auto position =
                std::find(face.begin(), face.end(), vertex.vertex);
            ASSERT_NE(position, face.end());
            const std::size_t local = static_cast<std::size_t>(
                std::distance(face.begin(), position));
            EXPECT_EQ(installed_vertex.adjacentVertices[index],
                      face[(local + 1u) % 3u]);
        }
    }
    for (std::size_t face = 0; face < mesh.faces.size(); ++face)
    {
        EXPECT_TRUE(mesh.faces[face].oneRingVertices.empty());
        ASSERT_EQ(mesh.faces[face].adjacentFaces.size(), 3u);
        for (std::size_t local = 0; local < 3u; ++local)
        {
            const int first = candidate.faces[face][local];
            const int second = candidate.faces[face][(local + 1u) % 3u];
            const LoopTopologyEdge* edge = find_edge(expected, first, second);
            ASSERT_NE(edge, nullptr);
            ASSERT_EQ(edge->incident_faces.size(), 2u);
            const int expected_neighbor = edge->incident_faces[0] ==
                                                  static_cast<int>(face)
                                              ? edge->incident_faces[1]
                                              : edge->incident_faces[0];
            EXPECT_EQ(mesh.faces[face].adjacentFaces[local],
                      expected_neighbor);
        }
    }
    EXPECT_EQ(transaction.rollback().reason,
              LoopTopologyTransactionReason::already_finalized);
}

TEST(LoopTopologyTransaction,
     CommitInterlocksConnectivityBlindRestartCheckpointWrite)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");
    const Fixture candidate = read_fixture(kFlipRoot + "/flip_000");
    Param param = quiet_param();
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(base.coordinates, base.faces);
    ASSERT_EQ(mesh.topology_generation_installed_by_setup(),
              mesh.topology_generation());

    Record record(1);
    Model model(mesh, record);
    const std::filesystem::path directory =
        std::filesystem::temp_directory_path() /
        "slimed_l7d_checkpoint_write_interlock";
    std::filesystem::remove_all(directory);
    ASSERT_TRUE(std::filesystem::create_directories(directory));
    const std::filesystem::path checkpoint = directory / "restart.chk";
    const std::string sentinel = "existing-checkpoint-remains-unchanged\n";
    {
        std::ofstream output(checkpoint);
        ASSERT_TRUE(output.is_open());
        output << sentinel;
    }

    LoopTopologyTransaction transaction(mesh);
    ASSERT_TRUE(transaction.stage(candidate.faces).accepted());
    ASSERT_TRUE(transaction.commit().accepted());
    ASSERT_GT(mesh.topology_generation(),
              mesh.topology_generation_installed_by_setup());

    EXPECT_FALSE(write_model_restart_checkpoint(
        model, checkpoint.string(), 1));
    std::ifstream input(checkpoint);
    ASSERT_TRUE(input.is_open());
    const std::string retained((std::istreambuf_iterator<char>(input)),
                               std::istreambuf_iterator<char>());
    EXPECT_EQ(retained, sentinel);
    EXPECT_FALSE(std::filesystem::exists(checkpoint.string() + ".tmp"));
}

TEST(LoopTopologyTransaction,
     ValidatorRejectionRetainsNestedReasonAndLeavesExactLiveState)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");
    Param param = quiet_param();
    Mesh mesh(param);
    populate_mesh(mesh, base);
    const std::string before = full_observable_snapshot(mesh);
    auto invalid = base.faces;
    invalid[0][2] = invalid[0][1];

    LoopTopologyTransaction transaction(mesh);
    const auto rejected = transaction.stage(invalid);
    EXPECT_EQ(rejected.reason,
              LoopTopologyTransactionReason::topology_rejected);
    EXPECT_EQ(rejected.topology_reason,
              LoopTopologyReasonCode::repeated_vertex_in_face);
    EXPECT_EQ(transaction.validation_result().reason,
              LoopTopologyReasonCode::repeated_vertex_in_face);
    EXPECT_EQ(transaction.state(), LoopTopologyTransactionState::rejected);
    EXPECT_EQ(full_observable_snapshot(mesh), before);
    EXPECT_EQ(transaction.commit().reason,
              LoopTopologyTransactionReason::already_finalized);
    EXPECT_EQ(full_observable_snapshot(mesh), before);
}

TEST(LoopTopologyTransaction,
     FixedCardinalityAndNoOpPoliciesRejectBeforeLiveMutation)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");

    Param no_op_param = quiet_param();
    Mesh no_op_mesh(no_op_param);
    populate_mesh(no_op_mesh, base);
    const std::string no_op_before = full_observable_snapshot(no_op_mesh);
    LoopTopologyTransaction no_op(no_op_mesh);
    EXPECT_EQ(no_op.stage(base.faces).reason,
              LoopTopologyTransactionReason::topology_unchanged);
    EXPECT_EQ(full_observable_snapshot(no_op_mesh), no_op_before);

    Param count_param = quiet_param();
    Mesh count_mesh(count_param);
    populate_mesh(count_mesh, base);
    const std::string count_before = full_observable_snapshot(count_mesh);
    auto fewer_faces = base.faces;
    fewer_faces.pop_back();
    LoopTopologyTransaction changed_count(count_mesh);
    EXPECT_EQ(changed_count.stage(fewer_faces).reason,
              LoopTopologyTransactionReason::face_count_changed);
    EXPECT_EQ(full_observable_snapshot(count_mesh), count_before);
}

TEST(LoopTopologyTransaction,
     CompetingStagedCommitRejectsAfterAnotherTransactionAdvancesEpoch)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");
    const Fixture first = read_fixture(kFlipRoot + "/flip_000");
    const Fixture second = read_fixture(kFlipRoot + "/flip_001");
    Param param = quiet_param();
    Mesh mesh(param);
    populate_mesh(mesh, base);

    LoopTopologyTransaction first_transaction(mesh);
    LoopTopologyTransaction stale_transaction(mesh);
    ASSERT_TRUE(first_transaction.stage(first.faces).accepted());
    ASSERT_TRUE(stale_transaction.stage(second.faces).accepted());
    ASSERT_TRUE(first_transaction.commit().accepted());
    const std::string accepted_state = full_observable_snapshot(mesh);

    EXPECT_EQ(stale_transaction.commit().reason,
              LoopTopologyTransactionReason::source_generation_changed);
    EXPECT_EQ(stale_transaction.state(),
              LoopTopologyTransactionState::rejected);
    EXPECT_EQ(full_observable_snapshot(mesh), accepted_state);
}

TEST(LoopTopologyTransaction,
     UnversionedSourceConnectivityDriftIsDetectedBeforeInvalidation)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");
    const Fixture candidate = read_fixture(kFlipRoot + "/flip_000");
    Param param = quiet_param();
    Mesh mesh(param);
    populate_mesh(mesh, base);

    LoopTopologyTransaction transaction(mesh);
    ASSERT_TRUE(transaction.stage(candidate.faces).accepted());
    std::rotate(mesh.faces[0].adjacentVertices.begin(),
                mesh.faces[0].adjacentVertices.begin() + 1,
                mesh.faces[0].adjacentVertices.end());
    const std::string externally_changed = full_observable_snapshot(mesh);
    EXPECT_EQ(transaction.commit().reason,
              LoopTopologyTransactionReason::source_connectivity_changed);
    EXPECT_EQ(full_observable_snapshot(mesh), externally_changed);
}

TEST(LoopTopologyTransaction,
     SourceCardinalityDriftAndStateMachineMisuseFailClosed)
{
    const Fixture base = read_fixture(kFlipRoot + "/base");
    const Fixture candidate = read_fixture(kFlipRoot + "/flip_000");
    Param param = quiet_param();
    Mesh mesh(param);
    populate_mesh(mesh, base);

    LoopTopologyTransaction transaction(mesh);
    EXPECT_EQ(transaction.commit().reason,
              LoopTopologyTransactionReason::not_staged);
    EXPECT_EQ(transaction.rollback().reason,
              LoopTopologyTransactionReason::not_staged);
    ASSERT_TRUE(transaction.stage(candidate.faces).accepted());
    EXPECT_EQ(transaction.stage(candidate.faces).reason,
              LoopTopologyTransactionReason::already_staged);
    mesh.faces.pop_back();
    const std::string shortened = full_observable_snapshot(mesh);
    EXPECT_EQ(transaction.commit().reason,
              LoopTopologyTransactionReason::source_cardinality_changed);
    EXPECT_EQ(full_observable_snapshot(mesh), shortened);
    EXPECT_EQ(transaction.stage(candidate.faces).reason,
              LoopTopologyTransactionReason::already_finalized);
}

TEST(LoopTopologyTransaction, ReasonNamesAreStableAndMachineReadable)
{
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::none),
                 "none");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::already_staged),
                 "already_staged");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::not_staged),
                 "not_staged");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::already_finalized),
                 "already_finalized");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::face_count_changed),
                 "face_count_changed");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::topology_unchanged),
                 "topology_unchanged");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::topology_rejected),
                 "topology_rejected");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::derived_rebuild_failed),
                 "derived_rebuild_failed");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::source_generation_changed),
                 "source_generation_changed");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::source_cardinality_changed),
                 "source_cardinality_changed");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::source_connectivity_changed),
                 "source_connectivity_changed");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::generation_overflow),
                 "generation_overflow");
    EXPECT_STREQ(loop_topology_transaction_reason_name(
                     LoopTopologyTransactionReason::invalidation_failed),
                 "invalidation_failed");
}
