#ifndef SLIMED_CUDA_MESH_STATE_HPP
#define SLIMED_CUDA_MESH_STATE_HPP

#include "cuda/Cuda_mesh_pack.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace slimed::cuda_residency
{

enum class DeviceStateErrorCode
{
    None = 0,
    NotCompiled,
    InitializationFailed,
    InvalidConfiguration,
    InvalidPackedInput,
    InvalidTransition,
    StaleGeneration,
    ArithmeticOverflow,
    MemoryQueryFailed,
    MemoryBudgetExceeded,
    AllocationFailed,
    TransferFailed,
    SynchronizationFailed,
    CandidateFailed,
    CleanupFailed,
};

const char *device_state_error_code_name(DeviceStateErrorCode code) noexcept;

struct DeviceStateError
{
    DeviceStateErrorCode code = DeviceStateErrorCode::None;
    std::string operation;
    int nativeCode = 0;
    std::string message;

    bool ok() const noexcept { return code == DeviceStateErrorCode::None; }
};

enum class TransactionPhase
{
    IdleAccepted = 0,
    CandidatePrepared,
    Computing,
    Validated,
    Failed,
    Closing,
    Closed,
};

enum class TransactionOutcome
{
    None = 0,
    Committed,
    RolledBack,
    Failed,
};

enum class TransferReason : std::size_t
{
    Topology = 0,
    NumericalPlan,
    Parameters,
    AcceptedCoordinates,
    ReferenceCoordinates,
    CandidateCoordinates,
    Count,
};

const char *transfer_reason_name(TransferReason reason) noexcept;

struct TransferCounter
{
    std::uint64_t attemptedOperations = 0;
    std::uint64_t completedOperations = 0;
    std::uint64_t attemptedBytes = 0;
    std::uint64_t completedBytes = 0;
};

struct DeviceStateConfig
{
    int deviceOrdinal = 0;
    std::uint32_t memoryBudgetNumerator = 1;
    std::uint32_t memoryBudgetDenominator = 2;
};

struct DeviceStateReport
{
    bool compiled = false;
    bool available = false;
    TransactionPhase phase = TransactionPhase::IdleAccepted;
    TransactionOutcome lastOutcome = TransactionOutcome::None;
    MeshPackGenerations residentGenerations;
    std::uint64_t candidateGeneration = 0;
    std::uint64_t allocationEpoch = 0;
    std::uint64_t transactionEpoch = 0;
    std::uint64_t successfulAllocations = 0;
    std::uint64_t successfulFrees = 0;
    std::uint64_t synchronizations = 0;
    std::size_t residentBytes = 0;
    std::size_t lastObservedFreeBytes = 0;
    std::size_t lastMemoryBudgetBytes = 0;
    bool cleanupPending = false;
    std::size_t cleanupPendingBytes = 0;
    std::uint32_t acceptedCoordinateSlot = 0;
    std::uint32_t candidateCoordinateSlot = 1;
    std::uint32_t previousCoordinateSlot = 2;
    std::array<bool, static_cast<std::size_t>(TransferReason::Count)>
        lastDirtyGroups{};
    std::array<std::size_t, static_cast<std::size_t>(TransferReason::Count)>
        capacityBytes{};
    std::array<TransferCounter,
               static_cast<std::size_t>(TransferReason::Count)>
        transfers{};
    DeviceStateError error;
    DeviceStateError cleanupError;
};

struct CudaMeshStateResult;

class CudaMeshState final
{
  public:
    CudaMeshState(const CudaMeshState &) = delete;
    CudaMeshState &operator=(const CudaMeshState &) = delete;
    CudaMeshState(CudaMeshState &&) noexcept;
    CudaMeshState &operator=(CudaMeshState &&) noexcept;
    ~CudaMeshState();

    DeviceStateError ensure_resident(const RegularMeshPack &pack);
    DeviceStateError prepare_candidate(
        const std::vector<double> &coordinates,
        std::uint64_t generation);
    DeviceStateError mark_computing();
    DeviceStateError mark_validated();
    DeviceStateError commit();
    DeviceStateError rollback();
    DeviceStateError fail_candidate(const std::string &operation,
                                    const std::string &message);
    DeviceStateError recover();
    DeviceStateError retry_cleanup();
    DeviceStateError close();
    const DeviceStateReport &report() const noexcept;

  private:
    struct Impl;
    explicit CudaMeshState(std::unique_ptr<Impl> impl);
    std::unique_ptr<Impl> impl_;

    friend struct CudaMeshStateResult;
    friend CudaMeshStateResult create_cuda_mesh_state(
        const RegularMeshPack &, const DeviceStateConfig &);
};

struct CudaMeshStateResult
{
    std::unique_ptr<CudaMeshState> state;
    DeviceStateReport report;

    bool ok() const noexcept
    {
        return state != nullptr && report.compiled && report.available &&
               report.error.ok();
    }
};

CudaMeshStateResult create_cuda_mesh_state(
    const RegularMeshPack &pack,
    const DeviceStateConfig &config = DeviceStateConfig{});

} // namespace slimed::cuda_residency

#endif
