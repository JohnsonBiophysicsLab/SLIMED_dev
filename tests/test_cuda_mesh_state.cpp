#include "cuda/Cuda_mesh_state.hpp"
#include "cuda/detail/Cuda_mesh_state_core.hpp"

#include <gtest/gtest.h>

#include <algorithm>
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

struct FakeDevice
{
    static constexpr int kInjected = 73;
    std::unordered_map<DeviceBufferHandle, std::vector<std::uint8_t>> memory;
    DeviceBufferHandle nextHandle = 1;
    std::size_t freeBytes = std::size_t{1} << 30;
    std::size_t totalBytes = std::size_t{2} << 30;
    std::uint64_t allocationCalls = 0;
    std::uint64_t copyCalls = 0;
    std::uint64_t synchronizeCalls = 0;
    std::uint64_t failAllocationCall = 0;
    std::uint64_t failCopyCall = 0;
    std::uint64_t failSynchronizeCall = 0;

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
