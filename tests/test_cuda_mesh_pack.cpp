#include <algorithm>
#include <cstdint>
#include <limits>
#include <memory>
#include <numeric>
#include <vector>

#include <gtest/gtest.h>

#include "Parameters.hpp"
#include "cuda/Cuda_mesh_pack.hpp"
#include "cuda/detail/Cuda_checked_arithmetic.hpp"
#include "mesh/Mesh.hpp"

namespace
{
using namespace slimed::cuda_residency;

struct RegularPackFixture
{
    Param param;
    std::unique_ptr<Mesh> mesh;

    RegularPackFixture()
    {
        param.VERBOSE_MODE = false;
        param.boundaryCondition = BoundaryType::Fixed;
        param.kCurv = 41.25;
        param.uSurf = 127.5;
        param.uVol = 9.75;
        param.kReg = 22.0;
        param.area0 = 19.5;
        param.area = 20.25;
        param.vol0 = 6.0;
        param.vol = 5.5;
        param.gamaShape = 0.15;
        param.gamaArea = 0.35;
        mesh = std::make_unique<Mesh>(param);

        for (int id = 0; id < 14; ++id)
        {
            Vertex vertex(id,
                          static_cast<double>(id) + 0.1,
                          static_cast<double>(id) + 0.2,
                          static_cast<double>(id) + 0.3);
            vertex.coordPrev = Matrix(3, 1, true);
            vertex.coordRef = Matrix(3, 1, true);
            // Vertex's legacy implicit copy constructor requires every Matrix
            // member to own storage before vector permutations.
            vertex.normVector = Matrix(3, 1, true);
            for (int axis = 0; axis < 3; ++axis)
            {
                vertex.coordPrev.set(axis, 0,
                                     100.0 + 10.0 * id + axis);
                vertex.coordRef.set(axis, 0,
                                    200.0 + 10.0 * id + axis);
            }
            vertex.isBoundary = (id == 0 || id == 13);
            vertex.isGhost = (id == 13);
            mesh->vertices.push_back(vertex);
        }

        Face face0;
        face0.index = 0;
        face0.adjacentVertices = {0, 1, 2};
        face0.oneRingVertices.resize(12);
        face0.normVector = Matrix(3, 1, true);
        std::iota(face0.oneRingVertices.begin(),
                  face0.oneRingVertices.end(), 0);
        face0.spontCurvature = 0.125;

        Face face1;
        face1.index = 1;
        face1.isBoundary = true;
        face1.adjacentVertices = {2, 3, 4};
        face1.oneRingVertices = {13, 12, 11, 10, 9, 8,
                                 7, 6, 5, 4, 3, 2};
        face1.normVector = Matrix(3, 1, true);
        face1.spontCurvature = -0.25;

        Face ghost;
        ghost.index = 2;
        ghost.isBoundary = true;
        ghost.isGhost = true;
        ghost.adjacentVertices = {0, 1, 13};
        ghost.oneRingVertices.clear();
        ghost.normVector = Matrix(3, 1, true);

        mesh->faces = {face0, face1, ghost};
    }
};

RegularMeshPackRequest current_request()
{
    RegularMeshPackRequest request;
    request.generations.topology = 17;
    request.generations.numericalPlan = 4;
    request.generations.parameters = 9;
    request.generations.acceptedCoordinates = 23;
    request.generations.referenceCoordinates = 8;
    request.enforceExpectedTopologyGeneration = true;
    request.expectedTopologyGeneration = 17;
    return request;
}

std::vector<std::vector<std::uint64_t>> independent_incidence_oracle(
    const Mesh &mesh)
{
    std::vector<std::vector<std::uint64_t>> grouped(
        mesh.vertices.size());
    std::uint64_t faceOrdinal = 0;
    for (std::size_t faceId = 0; faceId < mesh.faces.size(); ++faceId)
    {
        const Face &face = mesh.faces[faceId];
        if (face.isGhost)
        {
            continue;
        }
        for (std::uint64_t local = 0; local < kRegularControlCount; ++local)
        {
            const std::uint64_t occurrence =
                faceOrdinal * kRegularControlCount + local;
            const int source = face.oneRingVertices[static_cast<std::size_t>(local)];
            grouped[static_cast<std::size_t>(source)].push_back(occurrence);
        }
        ++faceOrdinal;
    }
    return grouped;
}

CudaEligibilityRequest eligible_request()
{
    CudaEligibilityRequest request;
    request.backend = BackendChoice::Cuda;
    request.packRequest = current_request();
    request.cudaExplicitlySelected = true;
    request.cudaCompiledByExplicitOptIn = true;
    request.deviceAvailable = true;
    request.driverRuntimeCompatible = true;
    request.doublePrecisionSupported = true;
    request.launchLimitsSupported = true;
    request.memoryBudgetAvailable = true;
    request.fixedBoundaryProven = true;
    return request;
}

TEST(CudaMeshPack, ExactRoundTripPreservesCanonicalInputs)
{
    RegularPackFixture fixture;
    const RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_TRUE(result.ok()) << result.error.message;
    const RegularMeshPack &pack = result.pack;

    EXPECT_EQ(pack.vertexCount, 14U);
    EXPECT_EQ(pack.faceCount, 3U);
    EXPECT_EQ(pack.evaluatedFaceCount, 2U);
    EXPECT_EQ(pack.evaluatedFaceIds, (std::vector<std::int32_t>{0, 1}));
    EXPECT_EQ(pack.orientedFaceVertexIds,
              (std::vector<std::int32_t>{0, 1, 2, 2, 3, 4}));
    EXPECT_EQ(pack.oneRingSourceIds.size(), 24U);
    EXPECT_EQ(pack.oneRingSourceIds.front(), 0);
    EXPECT_EQ(pack.oneRingSourceIds[11], 11);
    EXPECT_EQ(pack.oneRingSourceIds[12], 13);
    EXPECT_EQ(pack.oneRingSourceIds.back(), 2);
    EXPECT_EQ(pack.faceBoundaryMask,
              (std::vector<std::uint8_t>{0, 1, 1}));
    EXPECT_EQ(pack.faceGhostMask,
              (std::vector<std::uint8_t>{0, 0, 1}));
    EXPECT_EQ(pack.evaluatedFaceSpontaneousCurvature,
              (std::vector<double>{0.125, -0.25}));

    for (std::size_t faceOrdinal = 0;
         faceOrdinal < pack.evaluatedFaceIds.size();
         ++faceOrdinal)
    {
        const int faceId = pack.evaluatedFaceIds[faceOrdinal];
        const Face &cpuFace = fixture.mesh->faces[static_cast<std::size_t>(faceId)];
        for (std::size_t local = 0; local < 3; ++local)
        {
            EXPECT_EQ(pack.orientedFaceVertexIds[3U * faceOrdinal + local],
                      cpuFace.adjacentVertices[local]);
        }
        for (std::size_t local = 0; local < kRegularControlCount; ++local)
        {
            EXPECT_EQ(pack.oneRingSourceIds[
                          kRegularControlCount * faceOrdinal + local],
                      cpuFace.oneRingVertices[local]);
        }
    }

    for (int id = 0; id < 14; ++id)
    {
        const Vertex &cpuVertex = fixture.mesh->vertices[static_cast<std::size_t>(id)];
        for (int axis = 0; axis < 3; ++axis)
        {
            EXPECT_DOUBLE_EQ(pack.acceptedCoordinates[3U * id + axis],
                             cpuVertex.coord.get(axis, 0));
            EXPECT_DOUBLE_EQ(pack.previousCoordinates[3U * id + axis],
                             cpuVertex.coordPrev.get(axis, 0));
            EXPECT_DOUBLE_EQ(pack.referenceCoordinates[3U * id + axis],
                             cpuVertex.coordRef.get(axis, 0));
        }
    }

    ASSERT_EQ(pack.quadratureSamples.size(), 9U);
    ASSERT_EQ(pack.quadratureCoefficients.size(), 3U);
    ASSERT_EQ(pack.shapeWeights.size(), 3U * 7U * 12U);
    for (int sample = 0; sample < 3; ++sample)
    {
        for (int column = 0; column < 3; ++column)
        {
            EXPECT_DOUBLE_EQ(pack.quadratureSamples[3U * sample + column],
                             fixture.param.VWU.get(sample, column));
        }
        EXPECT_DOUBLE_EQ(pack.quadratureCoefficients[sample],
                         fixture.param.gaussQuadratureCoeff.get(sample, 0));
        for (int row = 0; row < 7; ++row)
        {
            for (int local = 0; local < 12; ++local)
            {
                const std::size_t offset =
                    static_cast<std::size_t>((sample * 7 + row) * 12 + local);
                EXPECT_DOUBLE_EQ(pack.shapeWeights[offset],
                                 fixture.param.shapeFunctions[sample].get(row,
                                                                          local));
            }
        }
    }
    EXPECT_DOUBLE_EQ(pack.parameters.kCurv, fixture.param.kCurv);
    EXPECT_DOUBLE_EQ(pack.parameters.uSurf, fixture.param.uSurf);
    EXPECT_DOUBLE_EQ(pack.parameters.area0, fixture.param.area0);
    EXPECT_EQ(pack.parameters.nFaceX, fixture.param.nFaceX);
    EXPECT_EQ(pack.parameters.nFaceY, fixture.param.nFaceY);
    EXPECT_EQ(pack.parameters.boundaryMode, PackedBoundaryMode::Fixed);
    EXPECT_EQ(pack.generations.acceptedCoordinates, 23U);
}

TEST(CudaMeshPack, IncidenceMatchesIndependentGroupedTupleOracle)
{
    RegularPackFixture fixture;
    const RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_TRUE(result.ok()) << result.error.message;
    const RegularMeshPack &pack = result.pack;
    const auto oracle = independent_incidence_oracle(*fixture.mesh);

    ASSERT_EQ(pack.sourceOffsets.size(), oracle.size() + 1U);
    EXPECT_EQ(pack.sourceOffsets.front(), 0U);
    EXPECT_EQ(pack.sourceOffsets.back(), 24U);
    for (std::size_t source = 0; source < oracle.size(); ++source)
    {
        const std::vector<std::uint64_t> actual(
            pack.sourceOccurrences.begin() + pack.sourceOffsets[source],
            pack.sourceOccurrences.begin() + pack.sourceOffsets[source + 1U]);
        EXPECT_EQ(actual, oracle[source]) << "source " << source;
    }
    EXPECT_EQ(oracle[0], (std::vector<std::uint64_t>{0}));
    EXPECT_EQ(oracle[2], (std::vector<std::uint64_t>{2, 23}));
    EXPECT_EQ(oracle[13], (std::vector<std::uint64_t>{12}));
}

TEST(CudaMeshPack, FaceLocalPermutationIsPreservedInCanonicalOccurrences)
{
    RegularPackFixture fixture;
    const RegularMeshPackResult first =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_TRUE(first.ok());

    std::reverse(fixture.mesh->faces[1].oneRingVertices.begin(),
                 fixture.mesh->faces[1].oneRingVertices.end());
    const RegularMeshPackResult second =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_TRUE(second.ok()) << second.error.message;

    EXPECT_EQ(second.pack.evaluatedFaceIds, first.pack.evaluatedFaceIds);
    EXPECT_EQ(std::vector<std::int32_t>(second.pack.oneRingSourceIds.begin(),
                                        second.pack.oneRingSourceIds.begin() + 12),
              std::vector<std::int32_t>(first.pack.oneRingSourceIds.begin(),
                                        first.pack.oneRingSourceIds.begin() + 12));
    EXPECT_NE(std::vector<std::int32_t>(second.pack.oneRingSourceIds.begin() + 12,
                                        second.pack.oneRingSourceIds.end()),
              std::vector<std::int32_t>(first.pack.oneRingSourceIds.begin() + 12,
                                        first.pack.oneRingSourceIds.end()));
    EXPECT_EQ(second.pack.acceptedCoordinates,
              first.pack.acceptedCoordinates);
    EXPECT_EQ(second.pack.referenceCoordinates,
              first.pack.referenceCoordinates);

    const auto oracle = independent_incidence_oracle(*fixture.mesh);
    for (std::size_t source = 0; source < oracle.size(); ++source)
    {
        const std::vector<std::uint64_t> actual(
            second.pack.sourceOccurrences.begin() +
                second.pack.sourceOffsets[source],
            second.pack.sourceOccurrences.begin() +
                second.pack.sourceOffsets[source + 1U]);
        EXPECT_EQ(actual, oracle[source]);
    }
}

TEST(CudaMeshPack, RejectsVertexAndFaceStorageIdentityDriftAtomically)
{
    RegularPackFixture fixture;
    std::swap(fixture.mesh->vertices[0], fixture.mesh->vertices[1]);
    RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::InvalidIndex);
    EXPECT_EQ(result.error.operation, "mesh_pack.vertex_identity");
    EXPECT_TRUE(result.pack.acceptedCoordinates.empty());
    EXPECT_TRUE(result.pack.sourceOffsets.empty());

    std::swap(fixture.mesh->vertices[0], fixture.mesh->vertices[1]);
    std::swap(fixture.mesh->faces[0], fixture.mesh->faces[1]);
    result = build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::InvalidIndex);
    EXPECT_EQ(result.error.operation, "mesh_pack.face_identity");
    EXPECT_TRUE(result.pack.evaluatedFaceIds.empty());
    EXPECT_TRUE(result.pack.sourceOffsets.empty());
}

TEST(CudaMeshPack, DuplicateSourceFailsWithoutPublishingPartialPack)
{
    RegularPackFixture fixture;
    fixture.mesh->faces[0].oneRingVertices[8] =
        fixture.mesh->faces[0].oneRingVertices[1];
    const RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::DuplicateSourceInFace);
    EXPECT_EQ(result.error.faceIndex, 0);
    EXPECT_EQ(result.error.localControl, 8);
    EXPECT_TRUE(result.pack.oneRingSourceIds.empty());
    EXPECT_TRUE(result.pack.sourceOffsets.empty());
}

TEST(CudaMeshPack, RejectsStaleTopologyBeforeReadingMesh)
{
    RegularPackFixture fixture;
    RegularMeshPackRequest request = current_request();
    request.expectedTopologyGeneration = 18;
    fixture.mesh->faces.clear();
    const RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, request);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::StaleTopology);
    EXPECT_EQ(result.error.operation, "mesh_pack.topology_generation");
}

TEST(CudaMeshPack, RejectsIrregularAndOutOfRangeTopologyPrecisely)
{
    RegularPackFixture fixture;
    fixture.mesh->faces[0].oneRingVertices.pop_back();
    RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::UnsupportedTopology);
    EXPECT_EQ(result.error.faceIndex, 0);

    fixture.mesh->faces[0].oneRingVertices.push_back(99);
    result = build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::InvalidIndex);
    EXPECT_EQ(result.error.sourceId, 99);
}

TEST(CudaMeshPack, RejectsMalformedOrEmptyTriangleTopology)
{
    RegularPackFixture fixture;
    fixture.mesh->faces[0].adjacentVertices = {0, 0, 2};
    RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::InvalidIndex);
    EXPECT_EQ(result.error.operation, "mesh_pack.oriented_face");

    fixture.mesh->faces[0].adjacentVertices = {0, 1, 13};
    result = build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::InvalidIndex);
    EXPECT_EQ(result.error.operation,
              "mesh_pack.oriented_face_membership");

    fixture.mesh->faces.clear();
    result = build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error.code, MeshPackErrorCode::InvalidCardinality);
}

TEST(CudaMeshPack, BoundaryAndGhostMasksPreserveNonEvaluatedTopology)
{
    RegularPackFixture fixture;
    const RegularMeshPackResult result =
        build_regular_mesh_pack(*fixture.mesh, current_request());
    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.pack.evaluatedFaceIds,
              (std::vector<std::int32_t>{0, 1}));
    EXPECT_EQ(result.pack.faceGhostMask[2], 1U);
    EXPECT_EQ(result.pack.faceBoundaryMask[1], 1U);
    EXPECT_EQ(result.pack.faceBoundaryMask[2], 1U);
    EXPECT_EQ(result.pack.vertexGhostMask[13], 1U);
    EXPECT_EQ(result.pack.vertexBoundaryMask[13], 1U);
}

TEST(CudaMeshPack, CheckedArithmeticRejectsOverflowAtBothOperations)
{
    std::uint64_t result = 0;
    EXPECT_TRUE(slimed::cuda_residency::detail::checked_add(4, 7, result));
    EXPECT_EQ(result, 11U);
    EXPECT_FALSE(slimed::cuda_residency::detail::checked_add(
        std::numeric_limits<std::uint64_t>::max(), 1, result));
    EXPECT_TRUE(slimed::cuda_residency::detail::checked_multiply(6, 7,
                                                                 result));
    EXPECT_EQ(result, 42U);
    EXPECT_FALSE(slimed::cuda_residency::detail::checked_multiply(
        std::numeric_limits<std::uint64_t>::max(), 2, result));
}

TEST(CudaEligibility, AllowsOnlyAnExplicitFullyProvenCudaEnvelope)
{
    RegularPackFixture fixture;
    const CudaEligibilityResult result =
        evaluate_cuda_eligibility(*fixture.mesh, eligible_request());
    EXPECT_TRUE(result.eligible);
    EXPECT_TRUE(result.issues.empty());
    EXPECT_TRUE(result.packedInput.ok());
}

TEST(CudaEligibility, CpuChoiceAlwaysLeavesExistingRouteAllowed)
{
    RegularPackFixture fixture;
    fixture.mesh->faces[0].oneRingVertices.clear();
    CudaEligibilityRequest request;
    request.backend = BackendChoice::Cpu;
    const CudaEligibilityResult result =
        evaluate_cuda_eligibility(*fixture.mesh, request);
    EXPECT_TRUE(result.eligible);
    EXPECT_TRUE(result.issues.empty());
    EXPECT_EQ(result.backend, BackendChoice::Cpu);
    EXPECT_TRUE(result.packedInput.pack.oneRingSourceIds.empty());
}

TEST(CudaEligibility, ReportsAllRejectionsInStableMatrixOrder)
{
    RegularPackFixture fixture;
    fixture.mesh->faces[0].oneRingVertices.pop_back();
    fixture.param.isEnergyHarmonicBondIncluded = true;
    fixture.param.isGagScaffoldingEnergyIncluded = true;
    fixture.param.isIdealizedProteinLatticeEnergyIncluded = true;
    fixture.param.thermalFluctuationEnabled = true;
    fixture.param.isInsertionIncluded = true;

    CudaEligibilityRequest request;
    request.backend = BackendChoice::Cuda;
    request.alternateEvaluatorRequested = true;
    request.dynamicMeshEnabled = true;
    request.priorUnrecoveredCudaError = true;
    const CudaEligibilityResult result =
        evaluate_cuda_eligibility(*fixture.mesh, request);
    ASSERT_FALSE(result.eligible);

    std::vector<EligibilityIssueCode> codes;
    for (const EligibilityIssue &issue : result.issues)
    {
        codes.push_back(issue.code);
        EXPECT_FALSE(issue.operation.empty());
        EXPECT_FALSE(issue.message.empty());
    }
    EXPECT_EQ(codes,
              (std::vector<EligibilityIssueCode>{
                  EligibilityIssueCode::CudaNotExplicitlySelected,
                  EligibilityIssueCode::CudaNotCompiled,
                  EligibilityIssueCode::DeviceUnavailable,
                  EligibilityIssueCode::DriverRuntimeIncompatible,
                  EligibilityIssueCode::DoublePrecisionUnsupported,
                  EligibilityIssueCode::LaunchLimitsUnsupported,
                  EligibilityIssueCode::MemoryBudgetUnavailable,
                  EligibilityIssueCode::UnsupportedRegularTopology,
                  EligibilityIssueCode::AlternateEvaluatorUnsupported,
                  EligibilityIssueCode::ScaffoldUnsupported,
                  EligibilityIssueCode::GagUnsupported,
                  EligibilityIssueCode::IdealizedLatticeUnsupported,
                  EligibilityIssueCode::ThermalUnsupported,
                  EligibilityIssueCode::DynamicMeshUnsupported,
                  EligibilityIssueCode::InsertionUnsupported,
                  EligibilityIssueCode::BoundaryModeUnsupported,
                  EligibilityIssueCode::PriorCudaError,
              }));
}

TEST(CudaEligibility, InvalidPackedDataIsDistinctFromUnsupportedTopology)
{
    RegularPackFixture fixture;
    fixture.mesh->vertices.back().coordRef.set(
        0, 0, std::numeric_limits<double>::quiet_NaN());
    CudaEligibilityResult result =
        evaluate_cuda_eligibility(*fixture.mesh, eligible_request());
    ASSERT_FALSE(result.eligible);
    ASSERT_EQ(result.issues.size(), 1U);
    EXPECT_EQ(result.issues[0].code,
              EligibilityIssueCode::InvalidPackedInput);
    EXPECT_NE(result.issues[0].message.find("nonfinite_input"),
              std::string::npos);
}

TEST(CudaEligibility, StaleTopologyHasDedicatedStableEligibilityCode)
{
    RegularPackFixture fixture;
    CudaEligibilityRequest request = eligible_request();
    request.packRequest.expectedTopologyGeneration = 18;
    const CudaEligibilityResult result =
        evaluate_cuda_eligibility(*fixture.mesh, request);
    ASSERT_FALSE(result.eligible);
    ASSERT_EQ(result.issues.size(), 1U);
    EXPECT_EQ(result.issues[0].code, EligibilityIssueCode::StaleGeneration);
    EXPECT_STREQ(eligibility_issue_code_name(result.issues[0].code),
                 "stale_generation");
}

} // namespace
