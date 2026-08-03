#include "cuda/detail/Cuda_mesh_state_core.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <type_traits>
#include <utility>
#include <vector>

namespace slimed::cuda_residency
{

const char *device_state_error_code_name(DeviceStateErrorCode code) noexcept
{
    switch (code)
    {
    case DeviceStateErrorCode::None: return "none";
    case DeviceStateErrorCode::NotCompiled: return "not_compiled";
    case DeviceStateErrorCode::InitializationFailed: return "initialization_failed";
    case DeviceStateErrorCode::InvalidConfiguration: return "invalid_configuration";
    case DeviceStateErrorCode::InvalidPackedInput: return "invalid_packed_input";
    case DeviceStateErrorCode::InvalidTransition: return "invalid_transition";
    case DeviceStateErrorCode::StaleGeneration: return "stale_generation";
    case DeviceStateErrorCode::ArithmeticOverflow: return "arithmetic_overflow";
    case DeviceStateErrorCode::MemoryQueryFailed: return "memory_query_failed";
    case DeviceStateErrorCode::MemoryBudgetExceeded: return "memory_budget_exceeded";
    case DeviceStateErrorCode::AllocationFailed: return "allocation_failed";
    case DeviceStateErrorCode::TransferFailed: return "transfer_failed";
    case DeviceStateErrorCode::SynchronizationFailed: return "synchronization_failed";
    case DeviceStateErrorCode::CandidateFailed: return "candidate_failed";
    case DeviceStateErrorCode::CleanupFailed: return "cleanup_failed";
    }
    return "unknown";
}

const char *transfer_reason_name(TransferReason reason) noexcept
{
    switch (reason)
    {
    case TransferReason::Topology: return "topology";
    case TransferReason::NumericalPlan: return "numerical_plan";
    case TransferReason::Parameters: return "parameters";
    case TransferReason::AcceptedCoordinates: return "accepted_coordinates";
    case TransferReason::ReferenceCoordinates: return "reference_coordinates";
    case TransferReason::CandidateCoordinates: return "candidate_coordinates";
    case TransferReason::Count: break;
    }
    return "unknown";
}

namespace detail
{
namespace
{

static_assert(std::is_trivially_copyable<PackedRegularParameters>::value,
              "packed parameters must remain byte-copyable to device storage");

struct HostView
{
    const void *data = nullptr;
    std::size_t bytes = 0;
};

struct DeviceBuffer
{
    DeviceBufferHandle handle = 0;
    std::size_t capacityBytes = 0;
    std::size_t logicalBytes = 0;
};

struct BufferGroup
{
    std::vector<DeviceBuffer> buffers;
};

struct PendingGroup
{
    BufferGroup *destination = nullptr;
    BufferGroup staged;
    TransferReason reason = TransferReason::Topology;
    std::vector<HostView> views;
};

template <typename T>
bool make_view(const std::vector<T> &values, HostView &view)
{
    if (values.size() > std::numeric_limits<std::size_t>::max() / sizeof(T))
        return false;
    view.data = values.empty() ? nullptr : values.data();
    view.bytes = values.size() * sizeof(T);
    return true;
}

template <typename T>
bool exact_size(const std::vector<T> &values, std::uint64_t count)
{
    return count <= std::numeric_limits<std::size_t>::max() &&
           values.size() == static_cast<std::size_t>(count);
}

bool multiply(std::uint64_t a, std::uint64_t b, std::uint64_t &value)
{
    if (a != 0 && b > std::numeric_limits<std::uint64_t>::max() / a)
        return false;
    value = a * b;
    return true;
}

bool add_size(std::size_t a, std::size_t b, std::size_t &value)
{
    if (b > std::numeric_limits<std::size_t>::max() - a)
        return false;
    value = a + b;
    return true;
}

bool next_capacity(std::size_t prior, std::size_t required,
                   std::size_t &capacity)
{
    if (required == 0)
    {
        capacity = 0;
        return true;
    }
    capacity = std::max<std::size_t>(prior, 64);
    while (capacity < required)
    {
        if (capacity > std::numeric_limits<std::size_t>::max() / 2)
            return false;
        capacity *= 2;
    }
    return true;
}

DeviceStateError error(DeviceStateErrorCode code, const std::string &operation,
                       const std::string &message, int nativeCode = 0)
{
    return {code, operation, nativeCode, message};
}

bool generations_nonzero(const MeshPackGenerations &g)
{
    return g.topology && g.numericalPlan && g.parameters &&
           g.acceptedCoordinates && g.referenceCoordinates;
}

DeviceStateError validate_pack(const RegularMeshPack &pack)
{
    std::uint64_t evaluated3 = 0, ring = 0, vertex3 = 0;
    if (!multiply(pack.evaluatedFaceCount, 3, evaluated3) ||
        !multiply(pack.evaluatedFaceCount, kRegularControlCount, ring) ||
        !multiply(pack.vertexCount, kCoordinateAxisCount, vertex3))
        return error(DeviceStateErrorCode::ArithmeticOverflow, "validate_pack",
                     "packed cardinality multiplication overflowed");

    if (!generations_nonzero(pack.generations))
        return error(DeviceStateErrorCode::InvalidPackedInput, "validate_pack",
                     "all resident generations must be nonzero");

    const bool sizesOk =
        exact_size(pack.vertexBoundaryMask, pack.vertexCount) &&
        exact_size(pack.vertexGhostMask, pack.vertexCount) &&
        exact_size(pack.faceBoundaryMask, pack.faceCount) &&
        exact_size(pack.faceGhostMask, pack.faceCount) &&
        exact_size(pack.evaluatedFaceIds, pack.evaluatedFaceCount) &&
        exact_size(pack.orientedFaceVertexIds, evaluated3) &&
        exact_size(pack.oneRingSourceIds, ring) &&
        exact_size(pack.evaluatedFaceInsertionMask, pack.evaluatedFaceCount) &&
        exact_size(pack.evaluatedFaceSpontaneousCurvature,
                   pack.evaluatedFaceCount) &&
        pack.vertexCount != std::numeric_limits<std::uint64_t>::max() &&
        exact_size(pack.sourceOffsets, pack.vertexCount + 1) &&
        exact_size(pack.sourceOccurrences, ring) &&
        exact_size(pack.quadratureSamples, 9) &&
        exact_size(pack.quadratureCoefficients, 3) &&
        exact_size(pack.shapeWeights, 252) &&
        exact_size(pack.acceptedCoordinates, vertex3) &&
        exact_size(pack.previousCoordinates, vertex3) &&
        exact_size(pack.referenceCoordinates, vertex3);
    if (!sizesOk)
        return error(DeviceStateErrorCode::InvalidPackedInput, "validate_pack",
                     "packed arrays do not match their declared cardinalities");

    if (pack.sourceOffsets.empty() || pack.sourceOffsets.front() != 0 ||
        pack.sourceOffsets.back() != pack.sourceOccurrences.size())
        return error(DeviceStateErrorCode::InvalidPackedInput, "validate_pack",
                     "source incidence offsets do not span the occurrence array");

    const auto finite = [](const std::vector<double> &values) {
        return std::all_of(values.begin(), values.end(),
                           [](double value) { return std::isfinite(value); });
    };
    if (!finite(pack.acceptedCoordinates) || !finite(pack.previousCoordinates) ||
        !finite(pack.referenceCoordinates))
        return error(DeviceStateErrorCode::InvalidPackedInput, "validate_pack",
                     "coordinate arrays contain a nonfinite value");
    return {};
}

std::size_t group_bytes(const BufferGroup &group)
{
    std::size_t total = 0;
    for (const auto &buffer : group.buffers)
        total += buffer.capacityBytes;
    return total;
}

} // namespace

struct MeshStateCore::Impl
{
    DeviceOperations operations;
    DeviceStateConfig config;
    DeviceStateReport report;
    BufferGroup topology;
    BufferGroup numericalPlan;
    BufferGroup parameters;
    BufferGroup coordinates;
    BufferGroup reference;
    bool initialized = false;
    bool closed = false;

    explicit Impl(DeviceOperations ops, DeviceStateConfig cfg)
        : operations(std::move(ops)), config(cfg)
    {
        report.compiled = true;
        report.available = true;
    }

    DeviceStateError record(DeviceStateError value)
    {
        report.error = value;
        return value;
    }

    void clear_error() { report.error = {}; }

    bool valid_operations() const
    {
        return operations.queryMemory && operations.allocate &&
               operations.release && operations.copyHostToDevice &&
               operations.synchronize;
    }

    std::vector<HostView> topology_views(const RegularMeshPack &pack,
                                         bool &ok) const
    {
        std::vector<HostView> result(8);
        ok = make_view(pack.vertexBoundaryMask, result[0]) &&
             make_view(pack.vertexGhostMask, result[1]) &&
             make_view(pack.faceBoundaryMask, result[2]) &&
             make_view(pack.faceGhostMask, result[3]) &&
             make_view(pack.evaluatedFaceIds, result[4]) &&
             make_view(pack.orientedFaceVertexIds, result[5]) &&
             make_view(pack.oneRingSourceIds, result[6]) &&
             make_view(pack.sourceOffsets, result[7]);
        HostView occurrences;
        ok = ok && make_view(pack.sourceOccurrences, occurrences);
        result.push_back(occurrences);
        return result;
    }

    std::vector<HostView> numerical_views(const RegularMeshPack &pack,
                                          bool &ok) const
    {
        std::vector<HostView> result(3);
        ok = make_view(pack.quadratureSamples, result[0]) &&
             make_view(pack.quadratureCoefficients, result[1]) &&
             make_view(pack.shapeWeights, result[2]);
        return result;
    }

    std::vector<HostView> parameter_views(const RegularMeshPack &pack,
                                          bool &ok) const
    {
        std::vector<HostView> result(3);
        ok = make_view(pack.evaluatedFaceInsertionMask, result[0]) &&
             make_view(pack.evaluatedFaceSpontaneousCurvature, result[1]);
        result[2] = {&pack.parameters, sizeof(pack.parameters)};
        return result;
    }

    std::vector<HostView> coordinate_views(const RegularMeshPack &pack,
                                           bool &ok) const
    {
        std::vector<HostView> result(3);
        ok = make_view(pack.acceptedCoordinates, result[0]) &&
             make_view(pack.previousCoordinates, result[2]);
        result[1] = {nullptr, result[0].bytes};
        return result;
    }

    std::vector<HostView> reference_views(const RegularMeshPack &pack,
                                          bool &ok) const
    {
        std::vector<HostView> result(1);
        ok = make_view(pack.referenceCoordinates, result[0]);
        return result;
    }

    DeviceStateError stage_group(PendingGroup &pending)
    {
        const BufferGroup &old = *pending.destination;
        pending.staged.buffers.resize(pending.views.size());
        for (std::size_t i = 0; i < pending.views.size(); ++i)
        {
            const auto prior = i < old.buffers.size()
                                   ? old.buffers[i].capacityBytes
                                   : std::size_t{0};
            auto &buffer = pending.staged.buffers[i];
            if (!next_capacity(prior, pending.views[i].bytes,
                               buffer.capacityBytes))
                return error(DeviceStateErrorCode::ArithmeticOverflow,
                             "capacity_growth",
                             "geometric device-buffer capacity overflowed");
            buffer.logicalBytes = pending.views[i].bytes;
        }
        return {};
    }

    DeviceStateError release_group(BufferGroup &group)
    {
        DeviceStateError first;
        for (auto &buffer : group.buffers)
        {
            if (!buffer.handle)
                continue;
            const DriverStatus status = operations.release(buffer.handle);
            if (status.success)
                ++report.successfulFrees;
            else if (first.ok())
                first = error(DeviceStateErrorCode::CleanupFailed,
                              status.operation.empty() ? "release" : status.operation,
                              status.message, status.nativeCode);
            buffer.handle = 0;
        }
        group.buffers.clear();
        return first;
    }

    DeviceStateError allocate_and_copy(std::vector<PendingGroup> &pending)
    {
        std::size_t stagedBytes = 0;
        for (auto &item : pending)
        {
            DeviceStateError staged = stage_group(item);
            if (!staged.ok())
                return staged;
            if (!add_size(stagedBytes, group_bytes(item.staged), stagedBytes))
                return error(DeviceStateErrorCode::ArithmeticOverflow,
                             "memory_budget", "staged byte count overflowed");
        }

        std::size_t freeBytes = 0, totalBytes = 0;
        DriverStatus status = operations.queryMemory(freeBytes, totalBytes);
        if (!status.success)
            return error(DeviceStateErrorCode::MemoryQueryFailed,
                         status.operation.empty() ? "query_memory" : status.operation,
                         status.message, status.nativeCode);
        report.lastObservedFreeBytes = freeBytes;
        const std::size_t numerator = config.memoryBudgetNumerator;
        const std::size_t denominator = config.memoryBudgetDenominator;
        if (numerator != 0 && freeBytes >
                                  std::numeric_limits<std::size_t>::max() /
                                      numerator)
            return error(DeviceStateErrorCode::ArithmeticOverflow,
                         "memory_budget", "memory budget multiplication overflowed");
        report.lastMemoryBudgetBytes = freeBytes * numerator / denominator;
        if (stagedBytes > report.lastMemoryBudgetBytes)
            return error(DeviceStateErrorCode::MemoryBudgetExceeded,
                         "memory_budget",
                         "staged device storage exceeds the configured fraction of current free memory");

        auto release_pending = [&]() {
            for (auto &item : pending)
                release_group(item.staged);
        };

        for (auto &item : pending)
        {
            for (auto &buffer : item.staged.buffers)
            {
                if (buffer.capacityBytes == 0)
                    continue;
                status = operations.allocate(buffer.capacityBytes, buffer.handle);
                if (!status.success)
                {
                    release_pending();
                    return error(DeviceStateErrorCode::AllocationFailed,
                                 status.operation.empty() ? "allocate" : status.operation,
                                 status.message, status.nativeCode);
                }
                ++report.successfulAllocations;
            }
        }

        struct PendingTransfer
        {
            TransferReason reason;
            std::uint64_t bytes;
        };
        std::vector<PendingTransfer> copied;
        for (auto &item : pending)
        {
            for (std::size_t i = 0; i < item.views.size(); ++i)
            {
                const HostView &view = item.views[i];
                if (!view.data || view.bytes == 0)
                    continue;
                auto &counter = report.transfers[static_cast<std::size_t>(item.reason)];
                ++counter.attemptedOperations;
                counter.attemptedBytes += view.bytes;
                status = operations.copyHostToDevice(
                    item.staged.buffers[i].handle, view.data, view.bytes);
                if (!status.success)
                {
                    release_pending();
                    return error(DeviceStateErrorCode::TransferFailed,
                                 status.operation.empty() ? "copy_host_to_device"
                                                          : status.operation,
                                 status.message, status.nativeCode);
                }
                copied.push_back({item.reason,
                                  static_cast<std::uint64_t>(view.bytes)});
            }
        }
        status = operations.synchronize();
        if (!status.success)
        {
            release_pending();
            return error(DeviceStateErrorCode::SynchronizationFailed,
                         status.operation.empty() ? "synchronize" : status.operation,
                         status.message, status.nativeCode);
        }
        ++report.synchronizations;
        for (const auto &entry : copied)
        {
            auto &counter = report.transfers[static_cast<std::size_t>(entry.reason)];
            ++counter.completedOperations;
            counter.completedBytes += entry.bytes;
        }
        return {};
    }

    void refresh_resident_bytes()
    {
        report.residentBytes = group_bytes(topology) + group_bytes(numericalPlan) +
                               group_bytes(parameters) + group_bytes(coordinates) +
                               group_bytes(reference);
        report.capacityBytes[static_cast<std::size_t>(TransferReason::Topology)] =
            group_bytes(topology);
        report.capacityBytes[static_cast<std::size_t>(
            TransferReason::NumericalPlan)] = group_bytes(numericalPlan);
        report.capacityBytes[static_cast<std::size_t>(TransferReason::Parameters)] =
            group_bytes(parameters);
        report.capacityBytes[static_cast<std::size_t>(
            TransferReason::AcceptedCoordinates)] = group_bytes(coordinates);
        report.capacityBytes[static_cast<std::size_t>(
            TransferReason::ReferenceCoordinates)] = group_bytes(reference);
        report.capacityBytes[static_cast<std::size_t>(
            TransferReason::CandidateCoordinates)] =
            coordinates.buffers.size() > report.candidateCoordinateSlot
                ? coordinates.buffers[report.candidateCoordinateSlot].capacityBytes
                : 0;
    }
};

MeshStateCore::MeshStateCore(DeviceOperations operations, DeviceStateConfig config)
    : impl_(std::make_unique<Impl>(std::move(operations), config))
{
}

MeshStateCore::~MeshStateCore()
{
    if (impl_)
        close();
}

DeviceStateError MeshStateCore::ensure_resident(const RegularMeshPack &pack)
{
    auto &s = *impl_;
    if (s.closed)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "ensure_resident", "device state is closed"));
    if (s.report.phase != TransactionPhase::IdleAccepted)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "ensure_resident",
                              "resident generations may change only while idle"));
    DeviceStateError valid = validate_pack(pack);
    if (!valid.ok())
        return s.record(valid);

    const auto &old = s.report.residentGenerations;
    if (s.initialized &&
        (pack.generations.topology < old.topology ||
         pack.generations.numericalPlan < old.numericalPlan ||
         pack.generations.parameters < old.parameters ||
         pack.generations.acceptedCoordinates < old.acceptedCoordinates ||
         pack.generations.referenceCoordinates < old.referenceCoordinates))
        return s.record(error(DeviceStateErrorCode::StaleGeneration,
                              "ensure_resident",
                              "a packed generation is older than resident state"));

    const bool topologyChanged = !s.initialized ||
        pack.generations.topology != old.topology;
    if (s.initialized && topologyChanged &&
        (pack.generations.numericalPlan == old.numericalPlan ||
         pack.generations.parameters == old.parameters ||
         pack.generations.acceptedCoordinates == old.acceptedCoordinates ||
         pack.generations.referenceCoordinates == old.referenceCoordinates))
        return s.record(error(DeviceStateErrorCode::StaleGeneration,
                              "ensure_resident",
                              "topology replacement requires fresh dependent generations"));

    std::vector<PendingGroup> pending;
    s.report.lastDirtyGroups.fill(false);
    bool viewsOk = true;
    if (topologyChanged)
        pending.push_back({&s.topology, {}, TransferReason::Topology,
                           s.topology_views(pack, viewsOk)});
    if (!s.initialized || pack.generations.numericalPlan != old.numericalPlan)
        pending.push_back({&s.numericalPlan, {}, TransferReason::NumericalPlan,
                           s.numerical_views(pack, viewsOk)});
    if (!s.initialized || pack.generations.parameters != old.parameters)
        pending.push_back({&s.parameters, {}, TransferReason::Parameters,
                           s.parameter_views(pack, viewsOk)});
    if (!s.initialized ||
        pack.generations.acceptedCoordinates != old.acceptedCoordinates)
        pending.push_back({&s.coordinates, {},
                           TransferReason::AcceptedCoordinates,
                           s.coordinate_views(pack, viewsOk)});
    if (!s.initialized ||
        pack.generations.referenceCoordinates != old.referenceCoordinates)
        pending.push_back({&s.reference, {},
                           TransferReason::ReferenceCoordinates,
                           s.reference_views(pack, viewsOk)});
    if (!viewsOk)
        return s.record(error(DeviceStateErrorCode::ArithmeticOverflow,
                              "ensure_resident", "host buffer byte count overflowed"));
    if (pending.empty())
    {
        s.clear_error();
        return {};
    }
    for (const auto &item : pending)
        s.report.lastDirtyGroups[static_cast<std::size_t>(item.reason)] = true;

    DeviceStateError transfer = s.allocate_and_copy(pending);
    if (!transfer.ok())
        return s.record(transfer);

    DeviceStateError cleanup;
    for (auto &item : pending)
    {
        BufferGroup oldGroup = std::move(*item.destination);
        *item.destination = std::move(item.staged);
        DeviceStateError released = s.release_group(oldGroup);
        if (cleanup.ok() && !released.ok())
            cleanup = released;
    }
    s.report.residentGenerations = pack.generations;
    s.report.acceptedCoordinateSlot = 0;
    s.report.candidateCoordinateSlot = 1;
    s.report.previousCoordinateSlot = 2;
    s.report.candidateGeneration = 0;
    ++s.report.allocationEpoch;
    s.initialized = true;
    s.refresh_resident_bytes();
    if (!cleanup.ok())
        return s.record(cleanup);
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::prepare_candidate(
    const std::vector<double> &coordinates, std::uint64_t generation)
{
    auto &s = *impl_;
    if (!s.initialized || s.closed ||
        s.report.phase != TransactionPhase::IdleAccepted)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "prepare_candidate",
                              "candidate preparation requires initialized idle state"));
    if (generation <= s.report.residentGenerations.acceptedCoordinates)
        return s.record(error(DeviceStateErrorCode::StaleGeneration,
                              "prepare_candidate",
                              "candidate generation must be newer than accepted state"));
    if (s.coordinates.buffers.size() != 3 ||
        coordinates.size() > std::numeric_limits<std::size_t>::max() / sizeof(double) ||
        coordinates.size() * sizeof(double) != s.coordinates.buffers[0].logicalBytes ||
        !std::all_of(coordinates.begin(), coordinates.end(),
                     [](double value) { return std::isfinite(value); }))
        return s.record(error(DeviceStateErrorCode::InvalidPackedInput,
                              "prepare_candidate",
                              "candidate coordinates have invalid size or values"));

    const std::uint32_t candidateSlot = s.report.candidateCoordinateSlot;
    auto &counter = s.report.transfers[
        static_cast<std::size_t>(TransferReason::CandidateCoordinates)];
    const std::size_t bytes = coordinates.size() * sizeof(double);
    ++counter.attemptedOperations;
    counter.attemptedBytes += bytes;
    DriverStatus status = s.operations.copyHostToDevice(
        s.coordinates.buffers[candidateSlot].handle, coordinates.data(), bytes);
    if (!status.success)
        return s.record(error(DeviceStateErrorCode::TransferFailed,
                              status.operation.empty() ? "copy_candidate"
                                                       : status.operation,
                              status.message, status.nativeCode));
    status = s.operations.synchronize();
    if (!status.success)
        return s.record(error(DeviceStateErrorCode::SynchronizationFailed,
                              status.operation.empty() ? "synchronize_candidate"
                                                       : status.operation,
                              status.message, status.nativeCode));
    ++s.report.synchronizations;
    ++counter.completedOperations;
    counter.completedBytes += bytes;
    s.report.candidateGeneration = generation;
    s.report.phase = TransactionPhase::CandidatePrepared;
    s.report.lastOutcome = TransactionOutcome::None;
    ++s.report.transactionEpoch;
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::mark_computing()
{
    auto &s = *impl_;
    if (s.report.phase != TransactionPhase::CandidatePrepared)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "mark_computing", "candidate is not prepared"));
    s.report.phase = TransactionPhase::Computing;
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::mark_validated()
{
    auto &s = *impl_;
    if (s.report.phase != TransactionPhase::Computing)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "mark_validated", "candidate is not computing"));
    const DriverStatus status = s.operations.synchronize();
    if (!status.success)
    {
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        return s.record(error(DeviceStateErrorCode::SynchronizationFailed,
                              status.operation.empty() ? "validate_candidate"
                                                       : status.operation,
                              status.message, status.nativeCode));
    }
    ++s.report.synchronizations;
    s.report.phase = TransactionPhase::Validated;
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::commit()
{
    auto &s = *impl_;
    if (s.report.phase != TransactionPhase::Validated)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "commit", "only a validated candidate can commit"));
    const std::uint32_t oldAccepted = s.report.acceptedCoordinateSlot;
    const std::uint32_t oldCandidate = s.report.candidateCoordinateSlot;
    const std::uint32_t oldPrevious = s.report.previousCoordinateSlot;
    s.report.acceptedCoordinateSlot = oldCandidate;
    s.report.previousCoordinateSlot = oldAccepted;
    s.report.candidateCoordinateSlot = oldPrevious;
    s.report.residentGenerations.acceptedCoordinates =
        s.report.candidateGeneration;
    s.report.candidateGeneration = 0;
    s.refresh_resident_bytes();
    s.report.phase = TransactionPhase::IdleAccepted;
    s.report.lastOutcome = TransactionOutcome::Committed;
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::rollback()
{
    auto &s = *impl_;
    if (s.report.phase != TransactionPhase::CandidatePrepared &&
        s.report.phase != TransactionPhase::Computing &&
        s.report.phase != TransactionPhase::Validated)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "rollback", "no live candidate can be rolled back"));
    const DriverStatus status = s.operations.synchronize();
    if (!status.success)
    {
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        return s.record(error(DeviceStateErrorCode::SynchronizationFailed,
                              status.operation.empty() ? "rollback_synchronize"
                                                       : status.operation,
                              status.message, status.nativeCode));
    }
    ++s.report.synchronizations;
    s.report.candidateGeneration = 0;
    s.report.phase = TransactionPhase::IdleAccepted;
    s.report.lastOutcome = TransactionOutcome::RolledBack;
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::fail_candidate(const std::string &operation,
                                                const std::string &message)
{
    auto &s = *impl_;
    if (s.report.phase != TransactionPhase::CandidatePrepared &&
        s.report.phase != TransactionPhase::Computing &&
        s.report.phase != TransactionPhase::Validated)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "fail_candidate", "no live candidate can fail"));
    s.report.phase = TransactionPhase::Failed;
    s.report.lastOutcome = TransactionOutcome::Failed;
    return s.record(error(DeviceStateErrorCode::CandidateFailed,
                          operation, message));
}

DeviceStateError MeshStateCore::recover()
{
    auto &s = *impl_;
    if (s.report.phase != TransactionPhase::Failed)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "recover", "device state is not failed"));
    const DriverStatus status = s.operations.synchronize();
    if (!status.success)
        return s.record(error(DeviceStateErrorCode::SynchronizationFailed,
                              status.operation.empty() ? "recover_synchronize"
                                                       : status.operation,
                              status.message, status.nativeCode));
    ++s.report.synchronizations;
    s.report.candidateGeneration = 0;
    s.report.phase = TransactionPhase::IdleAccepted;
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::close()
{
    if (!impl_ || impl_->closed)
        return {};
    auto &s = *impl_;
    DeviceStateError result;
    for (BufferGroup *group : {&s.reference, &s.coordinates, &s.parameters,
                               &s.numericalPlan, &s.topology})
    {
        DeviceStateError released = s.release_group(*group);
        if (result.ok() && !released.ok())
            result = released;
    }
    s.closed = true;
    s.report.phase = TransactionPhase::Closed;
    s.report.available = false;
    s.report.residentBytes = 0;
    if (!result.ok())
        return s.record(result);
    s.clear_error();
    return {};
}

const DeviceStateReport &MeshStateCore::report() const noexcept
{
    return impl_->report;
}

DeviceBufferHandle MeshStateCore::accepted_coordinate_handle_for_testing() const noexcept
{
    if (!impl_ || impl_->coordinates.buffers.size() < 2)
        return 0;
    return impl_->coordinates
        .buffers[impl_->report.acceptedCoordinateSlot]
        .handle;
}

MeshStateCoreResult create_mesh_state_core(DeviceOperations operations,
                                           const RegularMeshPack &pack,
                                           const DeviceStateConfig &config)
{
    MeshStateCoreResult result;
    if (config.memoryBudgetDenominator == 0 ||
        config.memoryBudgetNumerator == 0 ||
        config.memoryBudgetNumerator > config.memoryBudgetDenominator)
    {
        result.report.compiled = true;
        result.report.available = false;
        result.report.error = error(DeviceStateErrorCode::InvalidConfiguration,
                                    "create_mesh_state_core",
                                    "memory budget must be a fraction in (0, 1]");
        return result;
    }
    auto state = std::unique_ptr<MeshStateCore>(
        new MeshStateCore(std::move(operations), config));
    if (!state->impl_->valid_operations())
    {
        result.report = state->report();
        result.report.available = false;
        result.report.error = error(DeviceStateErrorCode::InvalidConfiguration,
                                    "create_mesh_state_core",
                                    "device operation table is incomplete");
        return result;
    }
    DeviceStateError resident = state->ensure_resident(pack);
    result.report = state->report();
    if (!resident.ok())
        return result;
    result.state = std::move(state);
    return result;
}

} // namespace detail
} // namespace slimed::cuda_residency
