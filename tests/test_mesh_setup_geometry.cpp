#include "test_mesh_setup_geometry.hpp"

#include <cstdint>
#include <cstring>
#include <set>
#include <stdexcept>
#include <string>

#include "io/io.hpp"

namespace
{
void populate_regular_legacy_patch(Mesh &mesh)
{
    mesh.vertices.clear();
    mesh.vertices.resize(24);
    for (int vertex = 0; vertex < static_cast<int>(mesh.vertices.size()); ++vertex)
    {
        mesh.vertices[vertex].index = vertex;
    }

    mesh.vertices[3].adjacentVertices = {6, 7, 2, 4, 0, 1};
    mesh.vertices[6].adjacentVertices = {3, 7, 2, 10, 5, 9};
    mesh.vertices[7].adjacentVertices = {3, 6, 4, 10, 8, 11};
    mesh.vertices[2].adjacentVertices = {3, 6, 0, 5};
    mesh.vertices[4].adjacentVertices = {3, 7, 1, 8};
    mesh.vertices[10].adjacentVertices = {6, 7, 9, 11};
    mesh.vertices[0].adjacentVertices = {2, 3};
    mesh.vertices[1].adjacentVertices = {3, 4};
    mesh.vertices[5].adjacentVertices = {2, 6};
    mesh.vertices[8].adjacentVertices = {4, 7};
    mesh.vertices[9].adjacentVertices = {6, 10};
    mesh.vertices[11].adjacentVertices = {7, 10};
    mesh.vertices[3].adjacentFaces.assign(6, 0);
    mesh.vertices[6].adjacentFaces.assign(6, 0);
    mesh.vertices[7].adjacentFaces.assign(6, 0);

    mesh.vertices[3].coord.set(0, 0, 1.0);
    mesh.vertices[6].coord.set(1, 0, 1.0);
    mesh.vertices[7].coord.set(2, 0, 1.0);

    mesh.faces.clear();
    mesh.faces.resize(1);
    mesh.faces[0].index = 0;
    mesh.faces[0].adjacentVertices = {3, 6, 7};
}

void populate_closed_valence_five_fixture(Mesh &mesh)
{
    const auto verticesData = read_data_from_csv<double>(
        "./data/fixtures/closed_valence5/vertices.csv");
    const auto facesData = read_data_from_csv<int>(
        "./data/fixtures/closed_valence5/faces.csv");
    mesh.setup_from_vertices_faces(verticesData, facesData);
}

template <typename Value>
void append_object_bytes(std::vector<unsigned char> &bytes, const Value &value)
{
    const std::size_t offset = bytes.size();
    bytes.resize(offset + sizeof(Value));
    std::memcpy(bytes.data() + offset, &value, sizeof(Value));
}

std::vector<unsigned char> face_index_bytes(const Mesh &mesh)
{
    std::vector<unsigned char> bytes;
    const std::uint64_t faceCount = mesh.faces.size();
    append_object_bytes(bytes, faceCount);
    for (const Face &face : mesh.faces)
    {
        const std::uint64_t adjacentCount = face.adjacentVertices.size();
        append_object_bytes(bytes, adjacentCount);
        for (const int vertex : face.adjacentVertices)
        {
            append_object_bytes(bytes, vertex);
        }
        const std::uint64_t oneRingCount = face.oneRingVertices.size();
        append_object_bytes(bytes, oneRingCount);
        for (const int vertex : face.oneRingVertices)
        {
            append_object_bytes(bytes, vertex);
        }
    }
    return bytes;
}

void expect_legacy_one_ring_rejection_without_face_mutation(
    Mesh &mesh,
    const LegacyOneRingReasonCode reasonCode)
{
    const std::vector<unsigned char> before = face_index_bytes(mesh);
    try
    {
        mesh.set_one_ring_vertices_sorted();
        FAIL() << "Expected legacy one-ring setup to reject";
    }
    catch (const std::runtime_error &error)
    {
        EXPECT_NE(std::string(error.what()).find(
                      legacy_one_ring_reason_code_name(reasonCode)),
                  std::string::npos);
    }
    EXPECT_EQ(face_index_bytes(mesh), before);
}
} // namespace

/**
 * @brief test default mesh initiation
 * 
 */
TEST(MeshInitTest, DefaultInitTest){
    Param param;
    param.VERBOSE_MODE = false; // mute output
    Mesh mesh(param);
}

/**
 * @brief Construct a new TEST object, unit-test mesh::setup_flat()
 * 
 */
TEST(MeshInitTest, SetupFlatTest){
    Param param;
    param.VERBOSE_MODE = false; // mute output
    Mesh mesh(param);
    mesh.setup_flat();
}


TEST(MeshFunctionTest, SortVerticesOfFacesTest){
    Param param;
    param.VERBOSE_MODE = false; // mute output
    Mesh mesh(param);
    mesh.setup_flat();
    mesh.sort_vertices_on_faces();

    // Expected output:
    // 21 , 22 , 0 , 
    // 22 , 1 , 0 , 
    // 22 , 23 , 1 ,
    /*
    std::cout << mesh.faces[0].adjacentVertices[0] << " , "
            << mesh.faces[0].adjacentVertices[1] << " , "
            << mesh.faces[0].adjacentVertices[2] << " , " << std::endl;
    std::cout << mesh.faces[1].adjacentVertices[0] << " , "
            << mesh.faces[1].adjacentVertices[1] << " , "
            << mesh.faces[1].adjacentVertices[2] << " , " << std::endl;
    std::cout << mesh.faces[2].adjacentVertices[0] << " , "
            << mesh.faces[2].adjacentVertices[1] << " , "
            << mesh.faces[2].adjacentVertices[2] << " , " << std::endl;
    */
    EXPECT_EQ(mesh.faces[1].adjacentVertices[0], 22);
    EXPECT_EQ(mesh.faces[1].adjacentVertices[1], 1);
    EXPECT_EQ(mesh.faces[1].adjacentVertices[2], 0);
}

/**
 * @brief Construct a new TEST, unit-test mesh::faces_share_edge()
 * 
 * Four test cases including 0-3 common vertices between two faces.
 * 
 * See mesh::faces_share_edge()
 * 
 */
TEST(MeshFunctionTest, FacesShareEdgeTest){
    Param param;
    param.VERBOSE_MODE = false; // mute output
    Mesh mesh(param);

    // Create faces and test share edge
    Face face1;
    Face face2;
    face1.adjacentVertices = std::vector<int>{1, 2, 3};
    face2.adjacentVertices = std::vector<int>{2, 3, 4};
    bool shareEdge = mesh.faces_share_edge(face1, face2);
    EXPECT_TRUE(shareEdge);

    // Function should return true if two inputs are the same
    shareEdge = mesh.faces_share_edge(face1, face1);
    EXPECT_TRUE(shareEdge);

    // Two cases that should return false:
    Face face3;
    Face face4;
    face3.adjacentVertices = std::vector<int>{2, 42, 13};
    face4.adjacentVertices = std::vector<int>{20, 43, 44};
    
    // Only 1 common vertex
    shareEdge = mesh.faces_share_edge(face1, face3);
    EXPECT_FALSE(shareEdge);

    // No common vertex
    shareEdge = mesh.faces_share_edge(face1, face4);
    EXPECT_FALSE(shareEdge);
}

TEST(LegacyOneRingSafety,
     PureClassifierStagesRegularOrderingWithoutMutation)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.faces[0].oneRingVertices = {91, 92, 93};
    const std::vector<unsigned char> before = face_index_bytes(mesh);

    const LegacyOneRingClassification first =
        mesh.classify_legacy_one_ring(mesh.faces[0]);
    const LegacyOneRingClassification second =
        mesh.classify_legacy_one_ring(mesh.faces[0]);

    EXPECT_EQ(face_index_bytes(mesh), before);
    EXPECT_EQ(first.reasonCode, LegacyOneRingReasonCode::ReadyRegular);
    EXPECT_STREQ(legacy_one_ring_reason_code_name(first.reasonCode),
                 "READY_REGULAR");
    EXPECT_EQ(first.cornerValences,
              (std::array<std::size_t, 3>{{6u, 6u, 6u}}));
    EXPECT_EQ(first.adjacentFaceCardinalities,
              (std::array<std::size_t, 3>{{6u, 6u, 6u}}));
    EXPECT_TRUE(first.extraordinaryCornerCandidates.empty());
    EXPECT_EQ(first.candidateExtraordinaryCorner, -1);
    EXPECT_TRUE(first.duplicateSourceIds.empty());
    EXPECT_TRUE(first.everyRequiredIndexAssignedUniquely);
    EXPECT_EQ(first.orientedFaceVertices, (std::vector<int>{3, 6, 7}));
    EXPECT_EQ(first.assembledOneRing,
              (std::vector<int>{0, 1, 2, 3, 4, 5,
                                6, 7, 8, 9, 10, 11}));
    EXPECT_EQ(second.reasonCode, first.reasonCode);
    EXPECT_EQ(second.orientedFaceVertices, first.orientedFaceVertices);
    EXPECT_EQ(second.assembledOneRing, first.assembledOneRing);

    mesh.set_one_ring_vertices_sorted();
    EXPECT_EQ(mesh.faces[0].adjacentVertices,
              first.orientedFaceVertices);
    EXPECT_EQ(mesh.faces[0].oneRingVertices, first.assembledOneRing);
}

TEST(LegacyOneRingSafety,
     NoAdjacentFaceCountMatchRejectsBeforeMutation)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    Mesh mesh(param);
    populate_closed_valence_five_fixture(mesh);
    Face &face = mesh.faces[0];
    face.oneRingVertices = {81, 82, 83};
    for (const int vertex : face.adjacentVertices)
    {
        mesh.vertices[vertex].adjacentFaces.assign(6, 0);
    }

    const LegacyOneRingClassification classification =
        mesh.classify_legacy_one_ring(face);
    EXPECT_EQ(classification.reasonCode,
              LegacyOneRingReasonCode::NoAdjacentFaceCountMatch);
    EXPECT_TRUE(classification.extraordinaryCornerCandidates.empty());
    EXPECT_EQ(classification.candidateExtraordinaryCorner, -1);
    EXPECT_FALSE(classification.everyRequiredIndexAssignedUniquely);
    expect_legacy_one_ring_rejection_without_face_mutation(
        mesh, LegacyOneRingReasonCode::NoAdjacentFaceCountMatch);
}

TEST(LegacyOneRingSafety,
     AmbiguousAdjacentFaceCountMatchRejectsBeforeMutation)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    Mesh mesh(param);
    populate_closed_valence_five_fixture(mesh);
    Face &face = mesh.faces[0];
    face.oneRingVertices = {71, 72, 73};
    mesh.vertices[face.adjacentVertices[2]].adjacentFaces.assign(4, 0);

    const LegacyOneRingClassification classification =
        mesh.classify_legacy_one_ring(face);
    EXPECT_EQ(classification.reasonCode,
              LegacyOneRingReasonCode::AmbiguousAdjacentFaceCountMatch);
    EXPECT_EQ(classification.extraordinaryCornerCandidates,
              (std::vector<int>{0, 1}));
    EXPECT_EQ(classification.candidateExtraordinaryCorner, -1);
    EXPECT_FALSE(classification.everyRequiredIndexAssignedUniquely);
    expect_legacy_one_ring_rejection_without_face_mutation(
        mesh, LegacyOneRingReasonCode::AmbiguousAdjacentFaceCountMatch);
}

TEST(LegacyOneRingSafety,
     SingleAdjacentFaceCandidatePreservesHistoricalRotationAndOrientation)
{
    // Byte-for-byte integer snapshots from BASE
    // 6acac80f09bcfdc27dd3b3eca1f55be02379147a. The second dimension is
    // nonnegative/negative orientation-predicate outcome.
    const std::array<std::array<std::vector<int>, 2>, 3> expectedFaces{{
        {{{0, 11, 5}, {0, 5, 11}}},
        {{{0, 11, 5}, {11, 0, 5}}},
        {{{0, 11, 5}, {5, 11, 0}}},
    }};
    const std::array<std::array<std::vector<int>, 2>, 3> expectedRings{{
        {{{7, 10, 0, 1, 2, 11, 5, 9, 2, 4, 9},
          {7, 1, 0, 10, 9, 5, 11, 2, 9, 4, 2}}},
        {{{2, 4, 11, 10, 9, 5, 0, 7, 9, 1, 7},
          {2, 10, 11, 4, 7, 0, 5, 9, 7, 1, 9}}},
        {{{9, 1, 5, 4, 7, 0, 11, 2, 7, 10, 2},
          {9, 4, 5, 1, 2, 11, 0, 7, 2, 10, 7}}},
    }};

    for (int selected = 0; selected < 3; ++selected)
    {
        for (int negative = 0; negative < 2; ++negative)
        {
            Param param;
            param.VERBOSE_MODE = false;
            param.boundaryCondition = BoundaryType::Fixed;
            Mesh mesh(param);
            populate_closed_valence_five_fixture(mesh);
            mesh.faces.resize(1);
            Face &face = mesh.faces[0];
            const std::vector<int> original = face.adjacentVertices;
            face.oneRingVertices = {61, 62, 63};

            for (int corner = 0; corner < 3; ++corner)
            {
                mesh.vertices[original[corner]].adjacentFaces.assign(
                    corner == selected ? 5 : 6, 0);
                mesh.vertices[original[corner]].coord = Matrix(3, 1);
            }
            mesh.vertices[original[0]].coord.set(0, 0, 1.0);
            mesh.vertices[original[negative ? 2 : 1]].coord.set(1, 0, 1.0);
            mesh.vertices[original[negative ? 1 : 2]].coord.set(2, 0, 1.0);

            const std::vector<unsigned char> before = face_index_bytes(mesh);
            const LegacyOneRingClassification classification =
                mesh.classify_legacy_one_ring(face);
            EXPECT_EQ(
                classification.reasonCode,
                LegacyOneRingReasonCode::AdjacentVertexFaceCardinalityMismatch);
            EXPECT_EQ(classification.cornerValences,
                      (std::array<std::size_t, 3>{{5u, 5u, 5u}}));
            EXPECT_EQ(classification.extraordinaryCornerCandidates,
                      (std::vector<int>{selected}));
            EXPECT_EQ(classification.candidateExtraordinaryCorner, selected);
            EXPECT_TRUE(classification.everyRequiredIndexAssignedUniquely);
            EXPECT_EQ(classification.orientedFaceVertices,
                      expectedFaces[selected][negative]);
            EXPECT_EQ(classification.assembledOneRing,
                      expectedRings[selected][negative]);
            EXPECT_EQ(face_index_bytes(mesh), before);

            EXPECT_NO_THROW(mesh.set_one_ring_vertices_sorted());
            EXPECT_EQ(face.adjacentVertices,
                      expectedFaces[selected][negative]);
            EXPECT_EQ(face.oneRingVertices,
                      expectedRings[selected][negative]);
        }
    }
}

TEST(LegacyOneRingSafety,
     AmbiguousOppositeNodeRejectsBeforeMutation)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.faces[0].oneRingVertices = {51, 52, 53};
    mesh.vertices[3].adjacentVertices[3] = 20;
    mesh.vertices[6].adjacentVertices[3] = 20;

    const LegacyOneRingClassification classification =
        mesh.classify_legacy_one_ring(mesh.faces[0]);
    EXPECT_EQ(classification.reasonCode,
              LegacyOneRingReasonCode::OppositeNodeAmbiguous);
    EXPECT_FALSE(classification.everyRequiredIndexAssignedUniquely);
    EXPECT_TRUE(classification.orientedFaceVertices.empty());
    EXPECT_TRUE(classification.assembledOneRing.empty());
    expect_legacy_one_ring_rejection_without_face_mutation(
        mesh, LegacyOneRingReasonCode::OppositeNodeAmbiguous);
}

TEST(LegacyOneRingSafety,
     IncompleteOneRingRejectsBeforeMutationAndNeverStoresMinusOne)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.faces[0].oneRingVertices = {41, 42, 43};
    mesh.vertices[3].adjacentVertices[2] = 20;

    const LegacyOneRingClassification classification =
        mesh.classify_legacy_one_ring(mesh.faces[0]);
    EXPECT_EQ(classification.reasonCode,
              LegacyOneRingReasonCode::OppositeNodeMissing);
    EXPECT_FALSE(classification.everyRequiredIndexAssignedUniquely);
    EXPECT_TRUE(classification.orientedFaceVertices.empty());
    EXPECT_TRUE(classification.assembledOneRing.empty());
    expect_legacy_one_ring_rejection_without_face_mutation(
        mesh, LegacyOneRingReasonCode::OppositeNodeMissing);
    EXPECT_EQ(std::find(mesh.faces[0].oneRingVertices.begin(),
                        mesh.faces[0].oneRingVertices.end(),
                        -1),
              mesh.faces[0].oneRingVertices.end());
}

TEST(LegacyOneRingSafety,
     ReversedFaceDoesNotPublishStagedOrientationWhenRingIsIncomplete)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.faces[0].adjacentVertices = {3, 7, 6};
    mesh.faces[0].oneRingVertices = {31, 32, 33};
    mesh.vertices[3].adjacentVertices[2] = 20;

    const LegacyOneRingClassification classification =
        mesh.classify_legacy_one_ring(mesh.faces[0]);
    EXPECT_EQ(classification.reasonCode,
              LegacyOneRingReasonCode::OppositeNodeMissing);
    EXPECT_TRUE(classification.orientedFaceVertices.empty());
    expect_legacy_one_ring_rejection_without_face_mutation(
        mesh, LegacyOneRingReasonCode::OppositeNodeMissing);
    EXPECT_EQ(mesh.faces[0].adjacentVertices,
              (std::vector<int>{3, 7, 6}));
    EXPECT_EQ(mesh.faces[0].oneRingVertices,
              (std::vector<int>{31, 32, 33}));
}

TEST(LegacyOneRingSafety,
     CompleteReversedFacePublishesHistoricalOrientationAfterValidation)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.faces[0].adjacentVertices = {3, 7, 6};
    mesh.faces[0].oneRingVertices = {27, 28, 29};
    const std::vector<unsigned char> before = face_index_bytes(mesh);

    const LegacyOneRingClassification classification =
        mesh.classify_legacy_one_ring(mesh.faces[0]);
    EXPECT_EQ(classification.reasonCode,
              LegacyOneRingReasonCode::ReadyRegular);
    EXPECT_EQ(classification.orientedFaceVertices,
              (std::vector<int>{3, 6, 7}));
    EXPECT_EQ(classification.assembledOneRing,
              (std::vector<int>{0, 1, 2, 3, 4, 5,
                                6, 7, 8, 9, 10, 11}));
    EXPECT_EQ(face_index_bytes(mesh), before);

    mesh.set_one_ring_vertices_sorted();
    EXPECT_EQ(mesh.faces[0].adjacentVertices,
              classification.orientedFaceVertices);
    EXPECT_EQ(mesh.faces[0].oneRingVertices,
              classification.assembledOneRing);
}

TEST(LegacyOneRingSafety,
     LaterFaceRejectionLeavesEarlierReadyFaceByteIdentical)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.faces.clear();
    mesh.faces.resize(2);
    mesh.faces[0].index = 0;
    mesh.faces[0].adjacentVertices = {3, 6, 7};
    mesh.faces[0].oneRingVertices = {21, 22, 23};
    mesh.faces[1].index = 1;
    mesh.faces[1].adjacentVertices = {3, 6};
    mesh.faces[1].oneRingVertices = {24, 25, 26};

    expect_legacy_one_ring_rejection_without_face_mutation(
        mesh, LegacyOneRingReasonCode::InvalidFaceCornerCount);
}

TEST(LegacyOneRingSafety,
     InvalidCornerAndAdjacentVertexIndicesHaveDistinctRejectionCodes)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh invalidCornerMesh(param);
    populate_regular_legacy_patch(invalidCornerMesh);
    invalidCornerMesh.faces[0].adjacentVertices[2] = 99;
    invalidCornerMesh.faces[0].oneRingVertices = {17, 18, 19};
    EXPECT_EQ(invalidCornerMesh.classify_legacy_one_ring(
                  invalidCornerMesh.faces[0]).reasonCode,
              LegacyOneRingReasonCode::InvalidCornerVertexIndex);
    expect_legacy_one_ring_rejection_without_face_mutation(
        invalidCornerMesh,
        LegacyOneRingReasonCode::InvalidCornerVertexIndex);

    Mesh invalidAdjacentMesh(param);
    populate_regular_legacy_patch(invalidAdjacentMesh);
    invalidAdjacentMesh.faces[0].oneRingVertices = {14, 15, 16};
    // Make only the final d12 lookup return an invalid source. This ensures
    // the candidate-index guard cannot be masked by a later staged lookup.
    invalidAdjacentMesh.vertices[7].adjacentVertices[5] = 99;
    invalidAdjacentMesh.vertices[10].adjacentVertices[3] = 99;
    EXPECT_EQ(invalidAdjacentMesh.classify_legacy_one_ring(
                  invalidAdjacentMesh.faces[0]).reasonCode,
              LegacyOneRingReasonCode::InvalidAdjacentVertexIndex);
    expect_legacy_one_ring_rejection_without_face_mutation(
        invalidAdjacentMesh,
        LegacyOneRingReasonCode::InvalidAdjacentVertexIndex);
}

TEST(LegacyOneRingSafety,
     FiveSixSixPredicateIsUnsupportedAndNeverExecutesLegacyMatrixSetup)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.vertices[3].adjacentVertices.pop_back();
    mesh.vertices[3].adjacentFaces.assign(5, 0);
    mesh.faces[0].oneRingVertices = {11, 12, 13};
    const std::vector<unsigned char> before = face_index_bytes(mesh);

    const LegacyOneRingClassification classification =
        mesh.classify_legacy_one_ring(mesh.faces[0]);
    EXPECT_EQ(classification.cornerValences,
              (std::array<std::size_t, 3>{{5u, 6u, 6u}}));
    EXPECT_EQ(classification.reasonCode,
              LegacyOneRingReasonCode::UnsupportedCornerValence);
    EXPECT_EQ(classification.extraordinaryCornerCandidates,
              (std::vector<int>{0}));
    EXPECT_EQ(classification.candidateExtraordinaryCorner, 0);
    EXPECT_FALSE(classification.everyRequiredIndexAssignedUniquely);

    EXPECT_NO_THROW(mesh.set_one_ring_vertices_sorted());
    EXPECT_EQ(face_index_bytes(mesh), before);
}

TEST(LegacyOneRingSafety,
     AcceptedIcosahedronAliasingIsDiagnosedButBytePreserved)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    Mesh mesh(param);
    populate_closed_valence_five_fixture(mesh);
    const std::vector<unsigned char> before = face_index_bytes(mesh);

    for (const Face &face : mesh.faces)
    {
        const LegacyOneRingClassification classification =
            mesh.classify_legacy_one_ring(face);
        EXPECT_EQ(classification.reasonCode,
                  LegacyOneRingReasonCode::ReadyAllValenceFiveAliased);
        EXPECT_EQ(classification.cornerValences,
                  (std::array<std::size_t, 3>{{5u, 5u, 5u}}));
        EXPECT_EQ(classification.adjacentFaceCardinalities,
                  (std::array<std::size_t, 3>{{5u, 5u, 5u}}));
        EXPECT_EQ(classification.extraordinaryCornerCandidates,
                  (std::vector<int>{0, 1, 2}));
        EXPECT_EQ(classification.candidateExtraordinaryCorner, 0);
        EXPECT_TRUE(classification.everyRequiredIndexAssignedUniquely);
        EXPECT_EQ(classification.assembledOneRing, face.oneRingVertices);
        EXPECT_EQ(classification.duplicateSourceIds.size(), 2u);
        EXPECT_EQ(std::set<int>(classification.assembledOneRing.begin(),
                                classification.assembledOneRing.end()).size(),
                  9u);
    }

    mesh.set_one_ring_vertices_sorted();
    EXPECT_EQ(face_index_bytes(mesh), before);
}

TEST(LegacyOneRingSafety,
     MissingOppositeNodeDiagnosticHonorsVerboseMode)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    populate_regular_legacy_patch(mesh);
    mesh.vertices[3].adjacentVertices.clear();

    ::testing::internal::CaptureStdout();
    EXPECT_EQ(mesh.find_opposite_node_index(3, 6, 7), -1);
    EXPECT_TRUE(::testing::internal::GetCapturedStdout().empty());

    param.VERBOSE_MODE = true;
    ::testing::internal::CaptureStdout();
    EXPECT_EQ(mesh.find_opposite_node_index(3, 6, 7), -1);
    const std::string verboseMessage =
        ::testing::internal::GetCapturedStdout();
    EXPECT_NE(verboseMessage.find(
                  "No efficent oneRingVerticesIndex is found!"),
              std::string::npos);
}
