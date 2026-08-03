#include "cuda/Cuda_mesh_state.hpp"
#include "cuda/detail/Cuda_mesh_state_core.hpp"
#include "mesh/Mesh.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <type_traits>
#include <unordered_map>
#include <vector>

namespace
{

using namespace slimed::cuda_residency;
using namespace slimed::cuda_residency::detail;

RegularMeshPack make_pack(std::uint64_t generation = 1)
{
    RegularMeshPack pack;
    pack.generations = {generation, generation, generation, generation,
                        generation};
    pack.vertexCount = 12;
    pack.faceCount = 1;
    pack.evaluatedFaceCount = 1;
    pack.vertexBoundaryMask.assign(12, 0);
    pack.vertexGhostMask.assign(12, 0);
    pack.faceBoundaryMask.assign(1, 0);
    pack.faceGhostMask.assign(1, 0);
    pack.evaluatedFaceIds = {0};
    pack.orientedFaceVertexIds = {0, 1, 2};
    for (std::int32_t source = 0; source < 12; ++source)
        pack.oneRingSourceIds.push_back(source);
    pack.evaluatedFaceInsertionMask = {0};
    pack.evaluatedFaceSpontaneousCurvature = {0.25};
    for (std::uint64_t offset = 0; offset <= 12; ++offset)
        pack.sourceOffsets.push_back(offset);
    for (std::uint64_t occurrence = 0; occurrence < 12; ++occurrence)
        pack.sourceOccurrences.push_back(occurrence);
    pack.quadratureSamples.assign(9, 1.0 / 3.0);
    pack.quadratureCoefficients.assign(3, 1.0 / 3.0);
    pack.shapeWeights.assign(252, 0.125);
    for (std::uint64_t value = 0; value < 36; ++value)
    {
        pack.acceptedCoordinates.push_back(static_cast<double>(value));
        pack.previousCoordinates.push_back(static_cast<double>(value) - 0.5);
        pack.referenceCoordinates.push_back(static_cast<double>(value) + 0.5);
    }
    pack.parameters.kCurv = 2.0;
    pack.parameters.area0 = 3.0;
    return pack;
}

RegularMeshPack make_geometry_pack()
{
    RegularMeshPack pack = make_pack();
    std::fill(pack.shapeWeights.begin(), pack.shapeWeights.end(), 0.0);
    std::fill(pack.acceptedCoordinates.begin(),
              pack.acceptedCoordinates.end(), 0.0);
    std::fill(pack.previousCoordinates.begin(),
              pack.previousCoordinates.end(), 0.0);
    std::fill(pack.referenceCoordinates.begin(),
              pack.referenceCoordinates.end(), 0.0);
    const double controls[3][3]{{2.0, 0.0, 0.0},
                                {2.0, 1.0, 0.0},
                                {2.0, 0.0, 1.0}};
    for (std::size_t source = 0; source < 3; ++source)
        for (std::size_t axis = 0; axis < 3; ++axis)
        {
            pack.acceptedCoordinates[source * 3 + axis] =
                controls[source][axis];
            pack.previousCoordinates[source * 3 + axis] =
                controls[source][axis];
            pack.referenceCoordinates[source * 3 + axis] =
                controls[source][axis];
        }
    for (std::size_t sample = 0; sample < 3; ++sample)
    {
        const std::size_t base = sample * 7 * 12;
        pack.shapeWeights[base] = 1.0;
        pack.shapeWeights[base + 12] = -1.0;
        pack.shapeWeights[base + 12 + 1] = 1.0;
        pack.shapeWeights[base + 24] = -1.0;
        pack.shapeWeights[base + 24 + 2] = 1.0;
    }
    return pack;
}

struct FakeDevice
{
    static constexpr int kInjected = 73;
    std::unordered_map<DeviceBufferHandle, std::vector<std::uint8_t>> memory;
    DeviceBufferHandle nextHandle = 1;
    std::size_t freeBytes = std::size_t{1} << 30;
    std::size_t totalBytes = std::size_t{2} << 30;
    std::uint64_t allocationCalls = 0;
    std::uint64_t copyCalls = 0;
    std::uint64_t copyToHostCalls = 0;
    std::uint64_t geometryCalls = 0;
    std::uint64_t synchronizeCalls = 0;
    std::uint64_t releaseCalls = 0;
    std::uint64_t failAllocationCall = 0;
    std::uint64_t failCopyCall = 0;
    std::uint64_t failCopyToHostCall = 0;
    std::uint64_t failGeometryCall = 0;
    std::uint64_t failSynchronizeCall = 0;
    std::uint64_t failReleaseCall = 0;

    DeviceOperations operations()
    {
        DeviceOperations ops;
        ops.queryMemory = [this](std::size_t &free, std::size_t &total) {
            free = freeBytes;
            total = totalBytes;
            return DriverStatus{};
        };
        ops.allocate = [this](std::size_t bytes, DeviceBufferHandle &handle) {
            ++allocationCalls;
            if (allocationCalls == failAllocationCall)
                return DriverStatus{false, kInjected, "fake_allocate",
                                    "injected allocation failure"};
            handle = nextHandle++;
            memory.emplace(handle, std::vector<std::uint8_t>(bytes));
            return DriverStatus{};
        };
        ops.release = [this](DeviceBufferHandle handle) {
            ++releaseCalls;
            if (releaseCalls == failReleaseCall)
                return DriverStatus{false, kInjected, "fake_release",
                                    "injected release failure"};
            memory.erase(handle);
            return DriverStatus{};
        };
        ops.copyHostToDevice =
            [this](DeviceBufferHandle handle, const void *source,
                   std::size_t bytes) {
                ++copyCalls;
                if (copyCalls == failCopyCall)
                    return DriverStatus{false, kInjected, "fake_copy",
                                        "injected copy failure"};
                auto found = memory.find(handle);
                if (found == memory.end() || bytes > found->second.size())
                    return DriverStatus{false, kInjected, "fake_copy",
                                        "invalid fake destination"};
                std::memcpy(found->second.data(), source, bytes);
                return DriverStatus{};
            };
        ops.copyDeviceToHost =
            [this](void *destination, DeviceBufferHandle handle,
                   std::size_t bytes) {
                ++copyToHostCalls;
                if (copyToHostCalls == failCopyToHostCall)
                    return DriverStatus{false, kInjected,
                                        "fake_copy_to_host",
                                        "injected device-to-host copy failure"};
                auto found = memory.find(handle);
                if (found == memory.end() || bytes > found->second.size())
                    return DriverStatus{false, kInjected, "fake_copy_to_host",
                                        "invalid fake source"};
                std::memcpy(destination, found->second.data(), bytes);
                return DriverStatus{};
            };
        ops.computeGeometry = [this](const GeometryLaunch &launch) {
            ++geometryCalls;
            if (geometryCalls == failGeometryCall)
                return DriverStatus{false, kInjected,
                                    "fake_compute_geometry",
                                    "injected geometry failure"};
            const auto read_i32 = [this](DeviceBufferHandle handle,
                                         std::size_t index) {
                std::int32_t value = 0;
                std::memcpy(&value,
                            memory.at(handle).data() + index * sizeof(value),
                            sizeof(value));
                return value;
            };
            const auto read_double = [this](DeviceBufferHandle handle,
                                            std::size_t index) {
                double value = 0.0;
                std::memcpy(&value,
                            memory.at(handle).data() + index * sizeof(value),
                            sizeof(value));
                return value;
            };
            const auto write_double = [this](DeviceBufferHandle handle,
                                             std::size_t index,
                                             double value) {
                std::memcpy(memory.at(handle).data() + index * sizeof(value),
                            &value, sizeof(value));
            };
            std::fill(memory.at(launch.faceAreas).begin(),
                      memory.at(launch.faceAreas).end(), 0);
            std::fill(memory.at(launch.faceVolumes).begin(),
                      memory.at(launch.faceVolumes).end(), 0);
            std::fill(memory.at(launch.status).begin(),
                      memory.at(launch.status).end(), 0);
            for (std::size_t evaluated = 0;
                 evaluated < launch.evaluatedFaceCount; ++evaluated)
            {
                const std::size_t face = static_cast<std::size_t>(
                    read_i32(launch.evaluatedFaceIds, evaluated));
                double area = 0.0;
                double volume = 0.0;
                for (std::size_t sample = 0; sample < 3; ++sample)
                {
                    double rows[3][3]{};
                    for (std::size_t row = 0; row < 3; ++row)
                        for (std::size_t local = 0; local < 12; ++local)
                        {
                            const std::size_t source = static_cast<std::size_t>(
                                read_i32(launch.oneRingSourceIds,
                                         evaluated * 12 + local));
                            const double weight = read_double(
                                launch.shapeWeights,
                                (sample * 7 + row) * 12 + local);
                            for (std::size_t axis = 0; axis < 3; ++axis)
                                rows[row][axis] += weight * read_double(
                                    launch.coordinates, source * 3 + axis);
                        }
                    const double cross[3]{
                        rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1],
                        rows[1][2] * rows[2][0] - rows[1][0] * rows[2][2],
                        rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0],
                    };
                    const double norm = std::sqrt(cross[0] * cross[0] +
                                                  cross[1] * cross[1] +
                                                  cross[2] * cross[2]);
                    const double coefficient = read_double(
                        launch.quadratureCoefficients, sample);
                    area += 0.5 * coefficient * norm;
                    volume += 0.16666666666 * coefficient *
                              rows[0][0] * cross[0];
                }
                write_double(launch.faceAreas, face, area);
                write_double(launch.faceVolumes, face, volume);
            }
            double totalArea = 0.0;
            double totalVolume = 0.0;
            for (std::size_t face = 0; face < launch.faceCount; ++face)
            {
                totalArea += read_double(launch.faceAreas, face);
                totalVolume += read_double(launch.faceVolumes, face);
            }
            write_double(launch.totals, 0, totalArea);
            write_double(launch.totals, 1, totalVolume);
            return DriverStatus{};
        };
        ops.synchronize = [this]() {
            ++synchronizeCalls;
            if (synchronizeCalls == failSynchronizeCall)
                return DriverStatus{false, kInjected, "fake_synchronize",
                                    "injected synchronization failure"};
            return DriverStatus{};
        };
        return ops;
    }

    std::vector<double> doubles(DeviceBufferHandle handle,
                                std::size_t count) const
    {
        const auto &bytes = memory.at(handle);
        std::vector<double> result(count);
        std::memcpy(result.data(), bytes.data(), count * sizeof(double));
        return result;
    }
};

TEST(CudaMeshStateStubTest, DefaultBuildReportsStructuredUnavailability)
{
    const auto result = create_cuda_mesh_state(make_pack());
    EXPECT_FALSE(result.ok());
    EXPECT_FALSE(result.report.compiled);
    EXPECT_FALSE(result.report.available);
    EXPECT_EQ(result.report.error.code, DeviceStateErrorCode::NotCompiled);
}

TEST(CudaMeshStateStubTest, PublicStateIsMoveOnly)
{
    static_assert(!std::is_copy_constructible<CudaMeshState>::value);
    static_assert(!std::is_copy_assignable<CudaMeshState>::value);
    static_assert(std::is_move_constructible<CudaMeshState>::value);
    static_assert(std::is_move_assignable<CudaMeshState>::value);
    SUCCEED();
}

TEST(CudaMeshStateCoreTest, InitialUploadIsReasonedAndSameGenerationsAreNoOp)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const DeviceStateReport before = created.state->report();

    EXPECT_EQ(before.phase, TransactionPhase::IdleAccepted);
    EXPECT_EQ(before.allocationEpoch, 1);
    EXPECT_GT(before.residentBytes, 0u);
    EXPECT_GT(before.capacityBytes[static_cast<std::size_t>(
                  TransferReason::CandidateCoordinates)],
              0u);
    EXPECT_EQ(before.transfers[static_cast<std::size_t>(TransferReason::Topology)]
                  .completedOperations,
              9);
    EXPECT_EQ(before.transfers[static_cast<std::size_t>(
                  TransferReason::NumericalPlan)].completedOperations,
              3);
    EXPECT_EQ(before.transfers[static_cast<std::size_t>(TransferReason::Parameters)]
                  .completedOperations,
              3);
    EXPECT_EQ(before.transfers[static_cast<std::size_t>(
                  TransferReason::AcceptedCoordinates)].completedOperations,
              2);
    EXPECT_EQ(before.transfers[static_cast<std::size_t>(
                  TransferReason::ReferenceCoordinates)].completedOperations,
              1);

    ASSERT_TRUE(created.state->ensure_resident(make_pack()).ok());
    const DeviceStateReport after = created.state->report();
    EXPECT_EQ(after.allocationEpoch, before.allocationEpoch);
    EXPECT_EQ(after.successfulAllocations, before.successfulAllocations);
    EXPECT_EQ(after.synchronizations, before.synchronizations);
    EXPECT_TRUE(std::none_of(after.lastDirtyGroups.begin(),
                             after.lastDirtyGroups.end(),
                             [](bool dirty) { return dirty; }));
    for (std::size_t reason = 0; reason < after.transfers.size(); ++reason)
    {
        EXPECT_EQ(after.transfers[reason].attemptedOperations,
                  before.transfers[reason].attemptedOperations);
        EXPECT_EQ(after.transfers[reason].completedOperations,
                  before.transfers[reason].completedOperations);
        EXPECT_EQ(after.transfers[reason].attemptedBytes,
                  before.transfers[reason].attemptedBytes);
        EXPECT_EQ(after.transfers[reason].completedBytes,
                  before.transfers[reason].completedBytes);
    }
}

TEST(CudaMeshStateCoreTest,
     CandidateGeometryIsDeterministicAndPreservesBoundaryGhostSemantics)
{
    FakeDevice device;
    RegularMeshPack pack = make_geometry_pack();
    pack.faceCount = 2;
    pack.faceBoundaryMask = {1, 0};
    pack.faceGhostMask = {0, 1};
    auto created = create_mesh_state_core(device.operations(), pack);
    ASSERT_NE(created.state, nullptr);
    auto facade = CudaMeshStateFactory::create(
        std::move(created.state), created.report,
        []() { return DriverStatus{}; });
    ASSERT_NE(facade, nullptr);

    std::vector<double> firstAreas;
    std::vector<double> firstVolumes;
    for (std::uint64_t repeat = 0; repeat < 20; ++repeat)
    {
        ASSERT_TRUE(facade->prepare_candidate(
            pack.acceptedCoordinates, 2 + repeat).ok());
        GeometryCandidateResult geometry =
            facade->compute_candidate_geometry();
        ASSERT_TRUE(geometry.ok()) << geometry.error.message;
        ASSERT_EQ(geometry.faceAreas.size(), 2u);
        ASSERT_EQ(geometry.faceVolumes.size(), 2u);
        EXPECT_DOUBLE_EQ(geometry.faceAreas[0], 0.5);
        EXPECT_DOUBLE_EQ(geometry.faceAreas[1], 0.0);
        EXPECT_NEAR(geometry.faceVolumes[0], 0.33333333332, 1.0e-15);
        EXPECT_DOUBLE_EQ(geometry.faceVolumes[1], 0.0);
        EXPECT_DOUBLE_EQ(geometry.totalArea, geometry.faceAreas[0]);
        EXPECT_DOUBLE_EQ(geometry.totalVolume, geometry.faceVolumes[0]);
        if (repeat == 0)
        {
            firstAreas = geometry.faceAreas;
            firstVolumes = geometry.faceVolumes;
        }
        else
        {
            EXPECT_EQ(std::memcmp(firstAreas.data(), geometry.faceAreas.data(),
                                  firstAreas.size() * sizeof(double)), 0);
            EXPECT_EQ(std::memcmp(firstVolumes.data(), geometry.faceVolumes.data(),
                                  firstVolumes.size() * sizeof(double)), 0);
        }
        EXPECT_TRUE(facade->rollback().ok());
    }
    EXPECT_EQ(facade->report().phase, TransactionPhase::IdleAccepted);
}

TEST(CudaMeshStateCoreTest,
     CandidateGeometryRespectsControlPermutationAndDegenerateInputs)
{
    FakeDevice naturalDevice;
    RegularMeshPack naturalPack = make_geometry_pack();
    auto naturalCreated = create_mesh_state_core(naturalDevice.operations(),
                                                  naturalPack);
    ASSERT_NE(naturalCreated.state, nullptr);
    auto natural = CudaMeshStateFactory::create(
        std::move(naturalCreated.state), naturalCreated.report,
        []() { return DriverStatus{}; });
    ASSERT_TRUE(natural->prepare_candidate(
        naturalPack.acceptedCoordinates, 2).ok());
    const GeometryCandidateResult expected =
        natural->compute_candidate_geometry();
    ASSERT_TRUE(expected.ok());

    FakeDevice permutedDevice;
    RegularMeshPack permutedPack = make_geometry_pack();
    std::swap(permutedPack.oneRingSourceIds[1],
              permutedPack.oneRingSourceIds[2]);
    for (std::size_t sample = 0; sample < 3; ++sample)
        for (std::size_t row = 0; row < 7; ++row)
            std::swap(permutedPack.shapeWeights[(sample * 7 + row) * 12 + 1],
                      permutedPack.shapeWeights[(sample * 7 + row) * 12 + 2]);
    auto permutedCreated = create_mesh_state_core(
        permutedDevice.operations(), permutedPack);
    ASSERT_NE(permutedCreated.state, nullptr);
    auto permuted = CudaMeshStateFactory::create(
        std::move(permutedCreated.state), permutedCreated.report,
        []() { return DriverStatus{}; });
    ASSERT_TRUE(permuted->prepare_candidate(
        permutedPack.acceptedCoordinates, 2).ok());
    const GeometryCandidateResult reordered =
        permuted->compute_candidate_geometry();
    ASSERT_TRUE(reordered.ok());
    EXPECT_EQ(reordered.faceAreas, expected.faceAreas);
    EXPECT_EQ(reordered.faceVolumes, expected.faceVolumes);

    FakeDevice curvedDevice;
    RegularMeshPack curvedPack = make_geometry_pack();
    const std::size_t sampleOne = 7 * 12;
    curvedPack.shapeWeights[sampleOne + 12] = -2.0;
    curvedPack.shapeWeights[sampleOne + 12 + 1] = 2.0;
    const std::size_t sampleTwo = 2 * 7 * 12;
    curvedPack.shapeWeights[sampleTwo + 24] = -3.0;
    curvedPack.shapeWeights[sampleTwo + 24 + 2] = 3.0;
    auto curvedCreated = create_mesh_state_core(curvedDevice.operations(),
                                                 curvedPack);
    ASSERT_NE(curvedCreated.state, nullptr);
    auto curved = CudaMeshStateFactory::create(
        std::move(curvedCreated.state), curvedCreated.report,
        []() { return DriverStatus{}; });
    ASSERT_TRUE(curved->prepare_candidate(
        curvedPack.acceptedCoordinates, 2).ok());
    const GeometryCandidateResult sampleVarying =
        curved->compute_candidate_geometry();
    ASSERT_TRUE(sampleVarying.ok());
    EXPECT_NEAR(sampleVarying.totalArea, 1.0, 1.0e-12);
    EXPECT_NEAR(sampleVarying.totalVolume, 0.66666666664, 1.0e-12);

    FakeDevice degenerateDevice;
    RegularMeshPack degeneratePack = make_geometry_pack();
    std::fill(degeneratePack.acceptedCoordinates.begin(),
              degeneratePack.acceptedCoordinates.end(), 2.0);
    auto degenerateCreated = create_mesh_state_core(
        degenerateDevice.operations(), degeneratePack);
    ASSERT_NE(degenerateCreated.state, nullptr);
    auto degenerate = CudaMeshStateFactory::create(
        std::move(degenerateCreated.state), degenerateCreated.report,
        []() { return DriverStatus{}; });
    ASSERT_TRUE(degenerate->prepare_candidate(
        degeneratePack.acceptedCoordinates, 2).ok());
    const GeometryCandidateResult flat =
        degenerate->compute_candidate_geometry();
    ASSERT_TRUE(flat.ok());
    EXPECT_DOUBLE_EQ(flat.totalArea, 0.0);
    EXPECT_DOUBLE_EQ(flat.totalVolume, 0.0);
}

TEST(CudaMeshStateCoreTest,
     CandidateGeometryMatchesProductionCpuRegularMeshGeometry)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;
    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();
    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index);
        vertex.coord.set(2, 0, 0.01 * std::sin(0.7 * index) +
                                   0.005 * std::cos(0.3 * index));
        vertex.coordPrev = Matrix(3, 1, true);
        vertex.coordRef = Matrix(3, 1, true);
        for (int axis = 0; axis < 3; ++axis)
        {
            vertex.coordPrev.set(axis, 0, vertex.coord.get(axis, 0));
            vertex.coordRef.set(axis, 0, vertex.coord.get(axis, 0));
        }
    }

    RegularMeshPackRequest request;
    request.generations = {1, 1, 1, 1, 1};
    const RegularMeshPackResult packed =
        build_regular_mesh_pack(mesh, request);
    ASSERT_TRUE(packed.ok()) << packed.error.message;
    mesh.calculate_element_area_volume();

    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), packed.pack);
    ASSERT_NE(created.state, nullptr);
    auto state = CudaMeshStateFactory::create(
        std::move(created.state), created.report,
        []() { return DriverStatus{}; });
    ASSERT_TRUE(state->prepare_candidate(
        packed.pack.acceptedCoordinates, 2).ok());
    const GeometryCandidateResult geometry =
        state->compute_candidate_geometry();
    ASSERT_TRUE(geometry.ok()) << geometry.error.message;
    ASSERT_EQ(geometry.faceAreas.size(), mesh.faces.size());
    ASSERT_EQ(geometry.faceVolumes.size(), mesh.faces.size());

    double expectedArea = 0.0;
    double expectedVolume = 0.0;
    for (const Face &face : mesh.faces)
    {
        const double area = face.isGhost ? 0.0 : face.elementArea;
        const double volume = face.isGhost ? 0.0 : face.elementVolume;
        EXPECT_NEAR(geometry.faceAreas[face.index], area, 1.0e-12);
        EXPECT_NEAR(geometry.faceVolumes[face.index], volume, 1.0e-12);
        expectedArea += area;
        expectedVolume += volume;
    }
    EXPECT_NEAR(geometry.totalArea, expectedArea, 1.0e-12);
    EXPECT_NEAR(geometry.totalVolume, expectedVolume, 1.0e-12);
}

TEST(CudaMeshStateCoreTest,
     CandidateGeometryFailuresRemainRecoverableAndNeverValidate)
{
    FakeDevice device;
    const RegularMeshPack pack = make_geometry_pack();
    auto created = create_mesh_state_core(device.operations(), pack);
    ASSERT_NE(created.state, nullptr);
    auto state = CudaMeshStateFactory::create(
        std::move(created.state), created.report,
        []() { return DriverStatus{}; });

    ASSERT_TRUE(state->prepare_candidate(pack.acceptedCoordinates, 2).ok());
    device.failGeometryCall = device.geometryCalls + 1;
    GeometryCandidateResult failed = state->compute_candidate_geometry();
    EXPECT_EQ(failed.error.code, DeviceStateErrorCode::CandidateFailed);
    EXPECT_EQ(state->report().phase, TransactionPhase::Failed);
    EXPECT_EQ(state->report().lastOutcome, TransactionOutcome::Failed);
    ASSERT_TRUE(state->recover().ok());

    ASSERT_TRUE(state->prepare_candidate(pack.acceptedCoordinates, 2).ok());
    device.failGeometryCall = 0;
    device.failCopyToHostCall = device.copyToHostCalls + 1;
    failed = state->compute_candidate_geometry();
    EXPECT_EQ(failed.error.code, DeviceStateErrorCode::TransferFailed);
    EXPECT_EQ(state->report().phase, TransactionPhase::Failed);
    EXPECT_EQ(state->report().lastOutcome, TransactionOutcome::Failed);
    ASSERT_TRUE(state->recover().ok());

    ASSERT_TRUE(state->prepare_candidate(pack.acceptedCoordinates, 2).ok());
    device.failCopyToHostCall = 0;
    device.failSynchronizeCall = device.synchronizeCalls + 1;
    failed = state->compute_candidate_geometry();
    EXPECT_EQ(failed.error.code, DeviceStateErrorCode::SynchronizationFailed);
    EXPECT_EQ(state->report().phase, TransactionPhase::Failed);
    EXPECT_EQ(state->report().lastOutcome, TransactionOutcome::Failed);
    EXPECT_EQ(state->report().residentGenerations.acceptedCoordinates, 1u);
    ASSERT_TRUE(state->recover().ok());
    EXPECT_EQ(state->report().phase, TransactionPhase::IdleAccepted);
}

TEST(CudaMeshStateCoreTest, UpdateAllocationFailurePreservesResidentState)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const auto accepted =
        created.state->accepted_coordinate_handle_for_testing();
    const auto before = created.state->report();
    const std::size_t liveBuffers = device.memory.size();
    RegularMeshPack changed = make_pack();
    changed.generations.parameters = 2;
    device.failAllocationCall = device.allocationCalls + 2;

    EXPECT_EQ(created.state->ensure_resident(changed).code,
              DeviceStateErrorCode::AllocationFailed);
    EXPECT_EQ(created.state->report().residentGenerations.parameters, 1);
    EXPECT_EQ(created.state->report().allocationEpoch, before.allocationEpoch);
    EXPECT_EQ(created.state->accepted_coordinate_handle_for_testing(), accepted);
    EXPECT_EQ(device.memory.size(), liveBuffers);
}

TEST(CudaMeshStateCoreTest, OnlyChangedGenerationUploadsItsGroup)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const DeviceStateReport before = created.state->report();
    RegularMeshPack changed = make_pack();
    changed.generations.parameters = 2;
    changed.parameters.kCurv = 9.0;

    ASSERT_TRUE(created.state->ensure_resident(changed).ok());
    const DeviceStateReport after = created.state->report();
    EXPECT_EQ(after.allocationEpoch, before.allocationEpoch + 1);
    EXPECT_EQ(after.residentGenerations.parameters, 2);
    for (std::size_t reason = 0;
         reason < static_cast<std::size_t>(TransferReason::Count); ++reason)
    {
        const auto delta = after.transfers[reason].completedOperations -
                           before.transfers[reason].completedOperations;
        EXPECT_EQ(delta, reason == static_cast<std::size_t>(
                                      TransferReason::Parameters)
                             ? 3u
                             : 0u);
    }
}

TEST(CudaMeshStateCoreTest,
     SelectiveUpdatesAfterCommitsPreserveAllCoordinateRolesAndBytes)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    std::vector<double> candidate(36, 42.0);
    ASSERT_TRUE(created.state->prepare_candidate(candidate, 2).ok());
    ASSERT_TRUE(created.state->mark_computing().ok());
    ASSERT_TRUE(created.state->mark_validated().ok());
    ASSERT_TRUE(created.state->commit().ok());

    const auto accepted =
        created.state->accepted_coordinate_handle_for_testing();
    const auto candidateHandle =
        created.state->candidate_coordinate_handle_for_testing();
    const auto previous =
        created.state->previous_coordinate_handle_for_testing();
    const auto acceptedBytes = device.memory.at(accepted);
    const auto candidateBytes = device.memory.at(candidateHandle);
    const auto previousBytes = device.memory.at(previous);
    DeviceStateReport before = created.state->report();

    RegularMeshPack changed = make_pack();
    changed.generations.acceptedCoordinates = 2;
    changed.generations.parameters = 2;
    changed.parameters.kCurv = 8.0;
    ASSERT_TRUE(created.state->ensure_resident(changed).ok());
    const DeviceStateReport afterParameters = created.state->report();
    EXPECT_EQ(created.state->accepted_coordinate_handle_for_testing(), accepted);
    EXPECT_EQ(created.state->candidate_coordinate_handle_for_testing(),
              candidateHandle);
    EXPECT_EQ(created.state->previous_coordinate_handle_for_testing(), previous);
    EXPECT_EQ(device.memory.at(accepted), acceptedBytes);
    EXPECT_EQ(device.memory.at(candidateHandle), candidateBytes);
    EXPECT_EQ(device.memory.at(previous), previousBytes);
    EXPECT_EQ(created.state->report().residentGenerations.acceptedCoordinates,
              2);
    EXPECT_EQ(created.state->report().transfers[static_cast<std::size_t>(
                  TransferReason::AcceptedCoordinates)].completedOperations,
              before.transfers[static_cast<std::size_t>(
                  TransferReason::AcceptedCoordinates)].completedOperations);
    EXPECT_EQ(afterParameters.residentGenerations.parameters, 2);
    EXPECT_EQ(afterParameters.transfers[static_cast<std::size_t>(
                  TransferReason::Parameters)].completedOperations,
              before.transfers[static_cast<std::size_t>(
                  TransferReason::Parameters)].completedOperations + 3);

    changed.generations.numericalPlan = 2;
    changed.shapeWeights[0] += 0.01;
    ASSERT_TRUE(created.state->ensure_resident(changed).ok());
    const DeviceStateReport afterPlan = created.state->report();
    EXPECT_EQ(afterPlan.residentGenerations.numericalPlan, 2);
    EXPECT_EQ(afterPlan.transfers[static_cast<std::size_t>(
                  TransferReason::NumericalPlan)].completedOperations,
              afterParameters.transfers[static_cast<std::size_t>(
                  TransferReason::NumericalPlan)].completedOperations + 3);
    changed.generations.referenceCoordinates = 2;
    changed.referenceCoordinates[0] += 0.02;
    ASSERT_TRUE(created.state->ensure_resident(changed).ok());
    const DeviceStateReport afterReference = created.state->report();
    EXPECT_EQ(created.state->accepted_coordinate_handle_for_testing(), accepted);
    EXPECT_EQ(created.state->candidate_coordinate_handle_for_testing(),
              candidateHandle);
    EXPECT_EQ(created.state->previous_coordinate_handle_for_testing(), previous);
    EXPECT_EQ(device.memory.at(accepted), acceptedBytes);
    EXPECT_EQ(device.memory.at(candidateHandle), candidateBytes);
    EXPECT_EQ(device.memory.at(previous), previousBytes);
    EXPECT_EQ(afterReference.residentGenerations.referenceCoordinates, 2);
    EXPECT_EQ(afterReference.transfers[static_cast<std::size_t>(
                  TransferReason::ReferenceCoordinates)].completedOperations,
              afterPlan.transfers[static_cast<std::size_t>(
                  TransferReason::ReferenceCoordinates)].completedOperations + 1);
    EXPECT_EQ(afterReference.transfers[static_cast<std::size_t>(
                  TransferReason::AcceptedCoordinates)].completedOperations,
              before.transfers[static_cast<std::size_t>(
                  TransferReason::AcceptedCoordinates)].completedOperations);
}

TEST(CudaMeshStateCoreTest, AllocationFailureLeavesNoPartialInitialState)
{
    FakeDevice device;
    device.failAllocationCall = 4;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    EXPECT_EQ(created.state, nullptr);
    EXPECT_EQ(created.report.error.code,
              DeviceStateErrorCode::AllocationFailed);
    EXPECT_TRUE(device.memory.empty());
}

TEST(CudaMeshStateCoreTest, CopyFailurePreservesResidentGenerationAndStorage)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const auto accepted =
        created.state->accepted_coordinate_handle_for_testing();
    const DeviceStateReport before = created.state->report();
    const std::size_t liveBuffers = device.memory.size();
    RegularMeshPack changed = make_pack();
    changed.generations.parameters = 2;
    device.failCopyCall = device.copyCalls + 2;

    const DeviceStateError failure = created.state->ensure_resident(changed);
    EXPECT_EQ(failure.code, DeviceStateErrorCode::TransferFailed);
    EXPECT_EQ(created.state->report().residentGenerations.parameters, 1);
    EXPECT_EQ(created.state->report().allocationEpoch, before.allocationEpoch);
    EXPECT_EQ(created.state->accepted_coordinate_handle_for_testing(), accepted);
    EXPECT_EQ(device.memory.size(), liveBuffers);
}

TEST(CudaMeshStateCoreTest, CandidateDirtyStateCoversSuccessAndFailure)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    std::vector<double> candidate(36, 6.0);
    const std::size_t candidateReason = static_cast<std::size_t>(
        TransferReason::CandidateCoordinates);

    ASSERT_TRUE(created.state->prepare_candidate(candidate, 2).ok());
    for (std::size_t reason = 0;
         reason < created.state->report().lastDirtyGroups.size(); ++reason)
        EXPECT_EQ(created.state->report().lastDirtyGroups[reason],
                  reason == candidateReason);
    ASSERT_TRUE(created.state->rollback().ok());

    const TransferCounter beforeCopyFailure = created.state->report().transfers[
        candidateReason];
    device.failCopyCall = device.copyCalls + 1;
    EXPECT_EQ(created.state->prepare_candidate(candidate, 2).code,
              DeviceStateErrorCode::TransferFailed);
    EXPECT_TRUE(created.state->report().lastDirtyGroups[candidateReason]);
    EXPECT_EQ(created.state->report().transfers[candidateReason]
                  .attemptedOperations,
              beforeCopyFailure.attemptedOperations + 1);
    EXPECT_EQ(created.state->report().transfers[candidateReason]
                  .completedOperations,
              beforeCopyFailure.completedOperations);

    candidate[0] = std::numeric_limits<double>::quiet_NaN();
    EXPECT_EQ(created.state->prepare_candidate(candidate, 2).code,
              DeviceStateErrorCode::InvalidPackedInput);
    EXPECT_TRUE(std::none_of(
        created.state->report().lastDirtyGroups.begin(),
        created.state->report().lastDirtyGroups.end(),
        [](bool dirty) { return dirty; }));

    candidate[0] = 6.0;
    device.failCopyCall = 0;
    device.failSynchronizeCall = device.synchronizeCalls + 1;
    const TransferCounter beforeSynchronizationFailure =
        created.state->report().transfers[candidateReason];
    EXPECT_EQ(created.state->prepare_candidate(candidate, 2).code,
              DeviceStateErrorCode::SynchronizationFailed);
    EXPECT_TRUE(created.state->report().lastDirtyGroups[candidateReason]);
    EXPECT_EQ(created.state->report().transfers[candidateReason]
                  .attemptedOperations,
              beforeSynchronizationFailure.attemptedOperations + 1);
    EXPECT_EQ(created.state->report().transfers[candidateReason]
                  .completedOperations,
              beforeSynchronizationFailure.completedOperations);
}

TEST(CudaMeshStateCoreTest, StreamDestroyFailureRetainsHandleForRepeatedClose)
{
    DeviceBufferHandle streamHandle = 91;
    std::uint64_t destroyCalls = 0;
    const auto destroy = [&destroyCalls](DeviceBufferHandle) {
        ++destroyCalls;
        if (destroyCalls == 1)
            return DriverStatus{false, FakeDevice::kInjected,
                                "fake_stream_destroy",
                                "injected stream-destroy failure"};
        return DriverStatus{};
    };

    EXPECT_FALSE(release_retryable_handle(streamHandle, destroy).success);
    EXPECT_EQ(streamHandle, 91u);
    EXPECT_EQ(destroyCalls, 1u);
    EXPECT_TRUE(release_retryable_handle(streamHandle, destroy).success);
    EXPECT_EQ(streamHandle, 0u);
    EXPECT_EQ(destroyCalls, 2u);
    EXPECT_TRUE(release_retryable_handle(streamHandle, destroy).success);
    EXPECT_EQ(destroyCalls, 2u);
}

TEST(CudaMeshStateCoreTest,
     FacadeStreamCleanupDebtSurvivesRejectedCallsAndRetriesToClosed)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    std::uint64_t destroyCalls = 0;
    const auto destroy = [&destroyCalls]() {
        ++destroyCalls;
        if (destroyCalls == 1)
            return DriverStatus{false, FakeDevice::kInjected,
                                "fake_stream_destroy",
                                "injected stream-destroy failure"};
        return DriverStatus{};
    };
    auto facade = CudaMeshStateFactory::create(
        std::move(created.state), created.report, destroy);
    ASSERT_NE(facade, nullptr);

    EXPECT_EQ(facade->close().code, DeviceStateErrorCode::CleanupFailed);
    EXPECT_EQ(facade->report().phase, TransactionPhase::Closing);
    EXPECT_TRUE(facade->report().cleanupPending);
    EXPECT_FALSE(facade->report().cleanupError.ok());

    EXPECT_EQ(facade->prepare_candidate(make_pack().acceptedCoordinates, 2).code,
              DeviceStateErrorCode::CleanupFailed);
    EXPECT_EQ(facade->report().phase, TransactionPhase::Closing);
    EXPECT_TRUE(facade->report().cleanupPending);
    EXPECT_FALSE(facade->report().cleanupError.ok());

    EXPECT_TRUE(facade->retry_cleanup().ok());
    EXPECT_EQ(facade->report().phase, TransactionPhase::Closed);
    EXPECT_FALSE(facade->report().cleanupPending);
    EXPECT_TRUE(facade->report().cleanupError.ok());
    EXPECT_EQ(destroyCalls, 2u);
    EXPECT_TRUE(facade->retry_cleanup().ok());
    EXPECT_EQ(destroyCalls, 2u);
}

TEST(CudaMeshStateCoreTest,
     FacadeKeepsDriverAliveThroughCoreDestructorCleanupRetry)
{
    auto device = std::make_shared<FakeDevice>();
    DeviceOperations raw = device->operations();
    std::weak_ptr<FakeDevice> weakDevice = device;
    auto expiredDuringOperation = std::make_shared<bool>(false);
    auto releaseAttempts = std::make_shared<std::uint64_t>(0);

    DeviceOperations guarded;
    guarded.queryMemory =
        [weakDevice, expiredDuringOperation, query = raw.queryMemory](
            std::size_t &free, std::size_t &total) {
            auto owner = weakDevice.lock();
            if (!owner)
            {
                *expiredDuringOperation = true;
                return DriverStatus{false, FakeDevice::kInjected,
                                    "expired_query", "driver expired"};
            }
            return query(free, total);
        };
    guarded.allocate =
        [weakDevice, expiredDuringOperation, allocate = raw.allocate](
            std::size_t bytes, DeviceBufferHandle &handle) {
            auto owner = weakDevice.lock();
            if (!owner)
            {
                *expiredDuringOperation = true;
                return DriverStatus{false, FakeDevice::kInjected,
                                    "expired_allocate", "driver expired"};
            }
            return allocate(bytes, handle);
        };
    guarded.release =
        [weakDevice, expiredDuringOperation, releaseAttempts,
         release = raw.release](DeviceBufferHandle handle) {
            ++*releaseAttempts;
            auto owner = weakDevice.lock();
            if (!owner)
            {
                *expiredDuringOperation = true;
                return DriverStatus{false, FakeDevice::kInjected,
                                    "expired_release", "driver expired"};
            }
            return release(handle);
        };
    guarded.copyHostToDevice =
        [weakDevice, expiredDuringOperation,
         copy = raw.copyHostToDevice](DeviceBufferHandle handle,
                                      const void *source, std::size_t bytes) {
            auto owner = weakDevice.lock();
            if (!owner)
            {
                *expiredDuringOperation = true;
                return DriverStatus{false, FakeDevice::kInjected,
                                    "expired_copy", "driver expired"};
            }
            return copy(handle, source, bytes);
        };
    guarded.copyDeviceToHost =
        [weakDevice, expiredDuringOperation,
         copy = raw.copyDeviceToHost](void *destination,
                                      DeviceBufferHandle handle,
                                      std::size_t bytes) {
            auto owner = weakDevice.lock();
            if (!owner)
            {
                *expiredDuringOperation = true;
                return DriverStatus{false, FakeDevice::kInjected,
                                    "expired_copy_to_host",
                                    "driver expired"};
            }
            return copy(destination, handle, bytes);
        };
    guarded.computeGeometry =
        [weakDevice, expiredDuringOperation,
         compute = raw.computeGeometry](const GeometryLaunch &launch) {
            auto owner = weakDevice.lock();
            if (!owner)
            {
                *expiredDuringOperation = true;
                return DriverStatus{false, FakeDevice::kInjected,
                                    "expired_compute_geometry",
                                    "driver expired"};
            }
            return compute(launch);
        };
    guarded.synchronize =
        [weakDevice, expiredDuringOperation,
         synchronize = raw.synchronize]() {
            auto owner = weakDevice.lock();
            if (!owner)
            {
                *expiredDuringOperation = true;
                return DriverStatus{false, FakeDevice::kInjected,
                                    "expired_synchronize", "driver expired"};
            }
            return synchronize();
        };

    auto created = create_mesh_state_core(guarded, make_pack());
    ASSERT_NE(created.state, nullptr);
    device->failReleaseCall = 1;
    {
        auto facade = CudaMeshStateFactory::create(
            std::move(created.state), created.report,
            [device]() { return DriverStatus{}; });
        ASSERT_NE(facade, nullptr);
        device.reset();
        EXPECT_FALSE(weakDevice.expired());
    }

    EXPECT_GE(*releaseAttempts, 2u);
    EXPECT_FALSE(*expiredDuringOperation);
    EXPECT_TRUE(weakDevice.expired());
}

TEST(CudaMeshStateCoreTest,
     FailedStagingReleaseRetainsOwnershipAndCanBeRetried)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const std::size_t liveBuffers = device.memory.size();
    RegularMeshPack changed = make_pack();
    changed.generations.parameters = 2;
    device.failCopyCall = device.copyCalls + 2;
    device.failReleaseCall = device.releaseCalls + 1;

    EXPECT_EQ(created.state->ensure_resident(changed).code,
              DeviceStateErrorCode::CleanupFailed);
    EXPECT_EQ(created.state->report().residentGenerations.parameters, 1);
    EXPECT_TRUE(created.state->report().cleanupPending);
    EXPECT_GT(created.state->report().cleanupPendingBytes, 0u);
    EXPECT_EQ(device.memory.size(), liveBuffers + 1);
    EXPECT_EQ(created.state->prepare_candidate(
                  std::vector<double>(36, 3.0), 2).code,
              DeviceStateErrorCode::CleanupFailed);

    device.failReleaseCall = 0;
    ASSERT_TRUE(created.state->retry_cleanup().ok());
    EXPECT_FALSE(created.state->report().cleanupPending);
    EXPECT_EQ(created.state->report().cleanupPendingBytes, 0u);
    EXPECT_EQ(device.memory.size(), liveBuffers);
}

TEST(CudaMeshStateCoreTest,
     PublishedReplacementReportsCleanupDebtWithoutAmbiguousFailure)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const std::size_t liveBuffers = device.memory.size();
    RegularMeshPack changed = make_pack();
    changed.generations.parameters = 2;
    device.failReleaseCall = device.releaseCalls + 1;

    EXPECT_TRUE(created.state->ensure_resident(changed).ok());
    EXPECT_EQ(created.state->report().residentGenerations.parameters, 2);
    EXPECT_TRUE(created.state->report().cleanupPending);
    EXPECT_FALSE(created.state->report().cleanupError.ok());
    EXPECT_EQ(device.memory.size(), liveBuffers + 1);
    EXPECT_EQ(created.state->ensure_resident(changed).code,
              DeviceStateErrorCode::CleanupFailed);

    device.failReleaseCall = 0;
    ASSERT_TRUE(created.state->retry_cleanup().ok());
    EXPECT_FALSE(created.state->report().cleanupPending);
    EXPECT_EQ(device.memory.size(), liveBuffers);
    EXPECT_TRUE(created.state->ensure_resident(changed).ok());
}

TEST(CudaMeshStateCoreTest, CloseFailureRetainsHandlesAndCloseIsRetryable)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    device.failReleaseCall = device.releaseCalls + 1;

    EXPECT_EQ(created.state->close().code,
              DeviceStateErrorCode::CleanupFailed);
    EXPECT_EQ(created.state->report().phase, TransactionPhase::Closing);
    EXPECT_FALSE(created.state->report().available);
    EXPECT_TRUE(created.state->report().cleanupPending);
    EXPECT_FALSE(device.memory.empty());

    device.failReleaseCall = 0;
    EXPECT_TRUE(created.state->close().ok());
    EXPECT_EQ(created.state->report().phase, TransactionPhase::Closed);
    EXPECT_FALSE(created.state->report().cleanupPending);
    EXPECT_TRUE(device.memory.empty());
}

TEST(CudaMeshStateCoreTest,
     ResidencySynchronizationFailureRollsBackAllGroups)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const auto before = created.state->report();
    const std::size_t liveBuffers = device.memory.size();
    RegularMeshPack changed = make_pack();
    changed.generations.parameters = 2;
    device.failSynchronizeCall = device.synchronizeCalls + 1;

    EXPECT_EQ(created.state->ensure_resident(changed).code,
              DeviceStateErrorCode::SynchronizationFailed);
    EXPECT_EQ(created.state->report().residentGenerations.parameters, 1);
    EXPECT_EQ(created.state->report().allocationEpoch, before.allocationEpoch);
    EXPECT_EQ(device.memory.size(), liveBuffers);
    EXPECT_FALSE(created.state->report().cleanupPending);
}

TEST(CudaMeshStateCoreTest, RollbackIsExactAndCommitSwapsCoordinateRoles)
{
    FakeDevice device;
    RegularMeshPack pack = make_pack();
    auto created = create_mesh_state_core(device.operations(), pack);
    ASSERT_NE(created.state, nullptr);
    const auto originalHandle =
        created.state->accepted_coordinate_handle_for_testing();
    const auto originalValues = device.doubles(originalHandle, 36);
    std::vector<double> candidate(36, 42.0);

    ASSERT_TRUE(created.state->prepare_candidate(candidate, 2).ok());
    ASSERT_TRUE(created.state->mark_computing().ok());
    ASSERT_TRUE(created.state->rollback().ok());
    EXPECT_EQ(created.state->accepted_coordinate_handle_for_testing(),
              originalHandle);
    EXPECT_EQ(created.state->report().residentGenerations.acceptedCoordinates,
              1);
    EXPECT_EQ(device.doubles(originalHandle, 36), originalValues);
    EXPECT_EQ(created.state->report().lastOutcome,
              TransactionOutcome::RolledBack);

    ASSERT_TRUE(created.state->prepare_candidate(candidate, 2).ok());
    ASSERT_TRUE(created.state->mark_computing().ok());
    ASSERT_TRUE(created.state->mark_validated().ok());
    ASSERT_TRUE(created.state->commit().ok());
    EXPECT_NE(created.state->accepted_coordinate_handle_for_testing(),
              originalHandle);
    EXPECT_EQ(created.state->report().acceptedCoordinateSlot, 1u);
    EXPECT_EQ(created.state->report().previousCoordinateSlot, 0u);
    EXPECT_EQ(created.state->report().candidateCoordinateSlot, 2u);
    EXPECT_EQ(created.state->report().residentGenerations.acceptedCoordinates,
              2);
    EXPECT_EQ(device.doubles(
                  created.state->accepted_coordinate_handle_for_testing(), 36),
              candidate);
}

TEST(CudaMeshStateCoreTest, WarmedTransactionsAllocateNothing)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const std::uint64_t allocations =
        created.state->report().successfulAllocations;
    std::vector<double> candidate(36, 4.0);
    for (std::uint64_t generation = 2; generation < 42; ++generation)
    {
        ASSERT_TRUE(created.state->prepare_candidate(candidate, generation).ok());
        ASSERT_TRUE(created.state->mark_computing().ok());
        if (generation % 2 == 0)
        {
            ASSERT_TRUE(created.state->mark_validated().ok());
            ASSERT_TRUE(created.state->commit().ok());
        }
        else
            ASSERT_TRUE(created.state->rollback().ok());
    }
    EXPECT_EQ(created.state->report().successfulAllocations, allocations);
    const auto &candidateTransfers = created.state->report().transfers[
        static_cast<std::size_t>(TransferReason::CandidateCoordinates)];
    EXPECT_EQ(candidateTransfers.completedOperations, 40);
    EXPECT_EQ(candidateTransfers.attemptedOperations,
              candidateTransfers.completedOperations);
}

TEST(CudaMeshStateCoreTest, SynchronizationFailureInvalidatesOnlyCandidate)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const auto accepted =
        created.state->accepted_coordinate_handle_for_testing();
    std::vector<double> candidate(36, 7.0);
    ASSERT_TRUE(created.state->prepare_candidate(candidate, 2).ok());
    ASSERT_TRUE(created.state->mark_computing().ok());
    device.failSynchronizeCall = device.synchronizeCalls + 1;

    EXPECT_EQ(created.state->mark_validated().code,
              DeviceStateErrorCode::SynchronizationFailed);
    EXPECT_EQ(created.state->report().phase, TransactionPhase::Failed);
    EXPECT_EQ(created.state->accepted_coordinate_handle_for_testing(), accepted);
    EXPECT_EQ(created.state->report().residentGenerations.acceptedCoordinates,
              1);
    device.failSynchronizeCall = 0;
    ASSERT_TRUE(created.state->recover().ok());
    EXPECT_EQ(created.state->report().phase, TransactionPhase::IdleAccepted);
}

TEST(CudaMeshStateCoreTest,
     CandidatePreparationSyncFailurePreservesAcceptedStateAndIsRetryable)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    ASSERT_NE(created.state, nullptr);
    const auto accepted =
        created.state->accepted_coordinate_handle_for_testing();
    const auto acceptedBytes = device.memory.at(accepted);
    std::vector<double> candidate(36, 9.0);
    device.failSynchronizeCall = device.synchronizeCalls + 1;

    EXPECT_EQ(created.state->prepare_candidate(candidate, 2).code,
              DeviceStateErrorCode::SynchronizationFailed);
    EXPECT_EQ(created.state->report().phase, TransactionPhase::IdleAccepted);
    EXPECT_EQ(created.state->report().candidateGeneration, 0);
    EXPECT_EQ(created.state->report().residentGenerations.acceptedCoordinates,
              1);
    EXPECT_EQ(created.state->accepted_coordinate_handle_for_testing(), accepted);
    EXPECT_EQ(device.memory.at(accepted), acceptedBytes);

    device.failSynchronizeCall = 0;
    ASSERT_TRUE(created.state->prepare_candidate(candidate, 2).ok());
    EXPECT_EQ(created.state->report().phase,
              TransactionPhase::CandidatePrepared);
}

TEST(CudaMeshStateCoreTest, MemoryBudgetRejectsBeforeAllocation)
{
    FakeDevice device;
    device.freeBytes = 64;
    auto created = create_mesh_state_core(device.operations(), make_pack());
    EXPECT_EQ(created.state, nullptr);
    EXPECT_EQ(created.report.error.code,
              DeviceStateErrorCode::MemoryBudgetExceeded);
    EXPECT_EQ(device.allocationCalls, 0u);
    EXPECT_TRUE(device.memory.empty());
}

TEST(CudaMeshStateCoreTest, StaleAndIllegalTransitionsAreRejected)
{
    FakeDevice device;
    auto created = create_mesh_state_core(device.operations(), make_pack(2));
    ASSERT_NE(created.state, nullptr);
    EXPECT_EQ(created.state->ensure_resident(make_pack(1)).code,
              DeviceStateErrorCode::StaleGeneration);
    EXPECT_EQ(created.state->commit().code,
              DeviceStateErrorCode::InvalidTransition);
}

} // namespace
