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
    case TransferReason::CandidateGeometry: return "candidate_geometry";
    case TransferReason::GeometryDiagnostics: return "geometry_diagnostics";
    case TransferReason::CandidateMembrane: return "candidate_membrane";
    case TransferReason::MembraneDiagnostics: return "membrane_diagnostics";
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

DriverStatus release_retryable_handle(
    DeviceBufferHandle &handle,
    const std::function<DriverStatus(DeviceBufferHandle)> &release)
{
    if (!handle)
        return {};
    DriverStatus status = release(handle);
    if (status.success)
        handle = 0;
    return status;
}

bool StreamCleanupState::pending() const noexcept { return pending_; }

void StreamCleanupState::overlay(DeviceStateReport &report) const
{
    if (!pending_)
        return;
    report.available = false;
    report.phase = TransactionPhase::Closing;
    report.cleanupPending = true;
    report.cleanupError = error_;
}

DeviceStateError StreamCleanupState::guard(
    const char *operation, DeviceStateReport &report) const
{
    if (!pending_)
        return {};
    DeviceStateError blocked = error(
        DeviceStateErrorCode::CleanupFailed, operation,
        "CUDA stream cleanup is pending; call retry_cleanup or close");
    overlay(report);
    report.error = blocked;
    return blocked;
}

DeviceStateError StreamCleanupState::attempt(
    const std::function<DriverStatus()> &close,
    DeviceStateReport &report)
{
    const DriverStatus status = close();
    if (!status.success)
    {
        pending_ = true;
        error_ = error(DeviceStateErrorCode::CleanupFailed,
                       status.operation.empty() ? "close_cuda_stream"
                                                : status.operation,
                       status.message, status.nativeCode);
        overlay(report);
        report.error = error_;
        return error_;
    }
    pending_ = false;
    error_ = {};
    return {};
}

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
    BufferGroup geometry;
    BufferGroup membrane;
    BufferGroup deferredCleanup;
    std::uint64_t vertexCount = 0;
    std::uint64_t faceCount = 0;
    std::uint64_t evaluatedFaceCount = 0;
    bool initialized = false;
    bool closing = false;
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

    void refresh_cleanup_state()
    {
        report.cleanupPendingBytes = group_bytes(deferredCleanup);
        report.cleanupPending = report.cleanupPendingBytes != 0;
        if (!report.cleanupPending)
            report.cleanupError = {};
    }

    DeviceStateError cleanup_blocked(const char *operation)
    {
        return error(DeviceStateErrorCode::CleanupFailed, operation,
                     "device cleanup is pending; call retry_cleanup before changing state");
    }

    bool valid_operations() const
    {
        return operations.queryMemory && operations.allocate &&
               operations.release && operations.copyHostToDevice &&
               operations.copyDeviceToHost && operations.computeGeometry &&
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

    std::vector<HostView> geometry_views(const RegularMeshPack &pack,
                                         bool &ok) const
    {
        std::vector<HostView> result(4);
        if (pack.faceCount > std::numeric_limits<std::size_t>::max() /
                                 sizeof(double) ||
            pack.faceCount > std::numeric_limits<std::size_t>::max() /
                                 sizeof(std::int32_t))
        {
            ok = false;
            return result;
        }
        const std::size_t faces = static_cast<std::size_t>(pack.faceCount);
        result[0].bytes = faces * sizeof(double);
        result[1].bytes = faces * sizeof(double);
        result[2].bytes = sizeof(std::int32_t);
        result[3].bytes = 2 * sizeof(double);
        return result;
    }

    std::vector<HostView> membrane_views(const RegularMeshPack &pack,
                                         bool &ok) const
    {
        std::vector<HostView> result(9);
        std::uint64_t faceDoubles = 0;
        std::uint64_t occurrenceCount = 0;
        std::uint64_t occurrenceDoubles = 0;
        std::uint64_t sampleCount = 0;
        std::uint64_t sampleVectorDoubles = 0;
        ok = multiply(pack.faceCount, sizeof(double), faceDoubles) &&
             multiply(pack.evaluatedFaceCount, kRegularControlCount,
                      occurrenceCount) &&
             multiply(occurrenceCount, 9U, occurrenceDoubles) &&
             multiply(occurrenceDoubles, sizeof(double), occurrenceDoubles) &&
             multiply(pack.evaluatedFaceCount, kQuadratureSampleCount,
                      sampleCount) &&
             multiply(sampleCount, 3U, sampleVectorDoubles) &&
             multiply(sampleVectorDoubles, sizeof(double),
                      sampleVectorDoubles) &&
             faceDoubles <= std::numeric_limits<std::size_t>::max() &&
             occurrenceDoubles <= std::numeric_limits<std::size_t>::max() &&
             sampleCount <= std::numeric_limits<std::size_t>::max() /
                                sizeof(double) &&
             sampleVectorDoubles <= std::numeric_limits<std::size_t>::max();
        ok = ok && faceDoubles <=
                       std::numeric_limits<std::size_t>::max() / 3U;
        if (!ok)
            return result;
        const std::size_t faces = static_cast<std::size_t>(faceDoubles);
        const std::size_t samples =
            static_cast<std::size_t>(sampleCount) * sizeof(double);
        result[0].bytes = faces;
        result[1].bytes = faces;
        result[2].bytes = faces * 3U;
        result[3].bytes = static_cast<std::size_t>(occurrenceDoubles);
        result[4].bytes = samples;
        result[5].bytes = samples;
        result[6].bytes = static_cast<std::size_t>(sampleVectorDoubles);
        result[7].bytes = samples;
        result[8].bytes = 3U * sizeof(std::int32_t);
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
        std::vector<DeviceBuffer> retained;
        retained.reserve(group.buffers.size());
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
            if (!status.success)
                retained.push_back(buffer);
        }
        group.buffers = std::move(retained);
        return first;
    }

    void defer_failed_releases(BufferGroup &group,
                               const DeviceStateError &cleanup)
    {
        for (auto &buffer : group.buffers)
            deferredCleanup.buffers.push_back(std::move(buffer));
        group.buffers.clear();
        report.cleanupError = cleanup;
        refresh_cleanup_state();
    }

    DeviceStateError release_pending(std::vector<PendingGroup> &pending,
                                     const DeviceStateError &primary)
    {
        DeviceStateError cleanup;
        for (auto &item : pending)
        {
            DeviceStateError released = release_group(item.staged);
            if (!released.ok())
            {
                defer_failed_releases(item.staged, released);
                if (cleanup.ok())
                    cleanup = released;
            }
        }
        if (cleanup.ok())
            return primary;
        cleanup.message += "; cleanup followed " +
                           std::string(device_state_error_code_name(primary.code)) +
                           " at " + primary.operation;
        report.cleanupError = cleanup;
        return cleanup;
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

        for (auto &item : pending)
        {
            for (auto &buffer : item.staged.buffers)
            {
                if (buffer.capacityBytes == 0)
                    continue;
                status = operations.allocate(buffer.capacityBytes, buffer.handle);
                if (!status.success)
                {
                    const DeviceStateError primary = error(
                        DeviceStateErrorCode::AllocationFailed,
                        status.operation.empty() ? "allocate" : status.operation,
                        status.message, status.nativeCode);
                    return release_pending(pending, primary);
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
                    const DeviceStateError primary = error(
                        DeviceStateErrorCode::TransferFailed,
                        status.operation.empty() ? "copy_host_to_device"
                                                 : status.operation,
                        status.message, status.nativeCode);
                    return release_pending(pending, primary);
                }
                copied.push_back({item.reason,
                                  static_cast<std::uint64_t>(view.bytes)});
            }
        }
        status = operations.synchronize();
        if (!status.success)
        {
            const DeviceStateError primary = error(
                DeviceStateErrorCode::SynchronizationFailed,
                status.operation.empty() ? "synchronize" : status.operation,
                status.message, status.nativeCode);
            return release_pending(pending, primary);
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
                               group_bytes(reference) + group_bytes(geometry) +
                               group_bytes(membrane);
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
        report.capacityBytes[static_cast<std::size_t>(
            TransferReason::CandidateGeometry)] = group_bytes(geometry);
        report.capacityBytes[static_cast<std::size_t>(
            TransferReason::CandidateMembrane)] = group_bytes(membrane);
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
    if (s.closing)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "ensure_resident", "device state is closing"));
    if (s.report.cleanupPending)
        return s.record(s.cleanup_blocked("ensure_resident"));
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
    const bool coordinatesChanged = !s.initialized ||
        pack.generations.acceptedCoordinates != old.acceptedCoordinates;
    if (coordinatesChanged)
        pending.push_back({&s.coordinates, {},
                           TransferReason::AcceptedCoordinates,
                           s.coordinate_views(pack, viewsOk)});
    if (!s.initialized ||
        pack.generations.referenceCoordinates != old.referenceCoordinates)
        pending.push_back({&s.reference, {},
                           TransferReason::ReferenceCoordinates,
                           s.reference_views(pack, viewsOk)});
    if (topologyChanged)
        pending.push_back({&s.geometry, {},
                           TransferReason::CandidateGeometry,
                           s.geometry_views(pack, viewsOk)});
    if (topologyChanged)
        pending.push_back({&s.membrane, {},
                           TransferReason::CandidateMembrane,
                           s.membrane_views(pack, viewsOk)});
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
        if (!released.ok())
        {
            s.defer_failed_releases(oldGroup, released);
            if (cleanup.ok())
                cleanup = released;
        }
    }
    s.report.residentGenerations = pack.generations;
    if (coordinatesChanged)
    {
        s.report.acceptedCoordinateSlot = 0;
        s.report.candidateCoordinateSlot = 1;
        s.report.previousCoordinateSlot = 2;
    }
    s.report.candidateGeneration = 0;
    s.vertexCount = pack.vertexCount;
    s.faceCount = pack.faceCount;
    s.evaluatedFaceCount = pack.evaluatedFaceCount;
    ++s.report.allocationEpoch;
    s.initialized = true;
    s.refresh_resident_bytes();
    if (!cleanup.ok())
        s.report.cleanupError = cleanup;
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::prepare_candidate(
    const std::vector<double> &coordinates, std::uint64_t generation)
{
    auto &s = *impl_;
    s.report.lastDirtyGroups.fill(false);
    if (!s.initialized || s.closed || s.closing ||
        s.report.phase != TransactionPhase::IdleAccepted)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "prepare_candidate",
                              "candidate preparation requires initialized idle state"));
    if (s.report.cleanupPending)
        return s.record(s.cleanup_blocked("prepare_candidate"));
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
    s.report.lastDirtyGroups[static_cast<std::size_t>(
        TransferReason::CandidateCoordinates)] = true;
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

GeometryCandidateResult MeshStateCore::compute_candidate_geometry()
{
    auto &s = *impl_;
    GeometryCandidateResult result;
    result.coordinateGeneration = s.report.candidateGeneration;
    s.report.lastDirtyGroups.fill(false);
    if (s.report.phase != TransactionPhase::CandidatePrepared ||
        s.topology.buffers.size() < 7 || s.numericalPlan.buffers.size() < 3 ||
        s.coordinates.buffers.size() != 3 || s.geometry.buffers.size() != 4)
    {
        result.error = error(DeviceStateErrorCode::InvalidTransition,
                             "compute_candidate_geometry",
                             "geometry requires a prepared candidate and complete resident buffers");
        s.record(result.error);
        return result;
    }
    if (s.report.cleanupPending)
    {
        result.error = s.cleanup_blocked("compute_candidate_geometry");
        s.record(result.error);
        return result;
    }

    s.report.phase = TransactionPhase::Computing;
    s.report.lastDirtyGroups[static_cast<std::size_t>(
        TransferReason::CandidateGeometry)] = true;
    const GeometryLaunch launch{
        s.topology.buffers[4].handle,
        s.topology.buffers[6].handle,
        s.numericalPlan.buffers[1].handle,
        s.numericalPlan.buffers[2].handle,
        s.coordinates.buffers[s.report.candidateCoordinateSlot].handle,
        s.geometry.buffers[0].handle,
        s.geometry.buffers[1].handle,
        s.geometry.buffers[2].handle,
        s.geometry.buffers[3].handle,
        s.vertexCount,
        s.faceCount,
        s.evaluatedFaceCount,
    };
    DriverStatus status = s.operations.computeGeometry(launch);
    if (!status.success)
    {
        result.error = error(DeviceStateErrorCode::CandidateFailed,
                             status.operation.empty() ? "compute_geometry"
                                                      : status.operation,
                             status.message, status.nativeCode);
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    status = s.operations.synchronize();
    if (!status.success)
    {
        result.error = error(DeviceStateErrorCode::SynchronizationFailed,
                             status.operation.empty() ? "synchronize_geometry"
                                                      : status.operation,
                             status.message, status.nativeCode);
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    ++s.report.synchronizations;

    result.faceAreas.resize(static_cast<std::size_t>(s.faceCount));
    result.faceVolumes.resize(static_cast<std::size_t>(s.faceCount));
    double totals[2]{};
    std::int32_t geometryStatus = 0;
    auto &counter = s.report.transfers[static_cast<std::size_t>(
        TransferReason::GeometryDiagnostics)];
    std::uint64_t diagnosticBytes = 0;
    const auto copy = [&](void *destination, DeviceBufferHandle source,
                          std::size_t bytes) -> bool {
        ++counter.attemptedOperations;
        counter.attemptedBytes += bytes;
        diagnosticBytes += bytes;
        const DriverStatus copied =
            s.operations.copyDeviceToHost(destination, source, bytes);
        if (!copied.success)
        {
            result.error = error(DeviceStateErrorCode::TransferFailed,
                                 copied.operation.empty() ? "copy_geometry_diagnostic"
                                                          : copied.operation,
                                 copied.message, copied.nativeCode);
            return false;
        }
        return true;
    };
    const std::size_t faceDoubleBytes = result.faceAreas.size() * sizeof(double);
    if (!copy(result.faceAreas.data(), s.geometry.buffers[0].handle,
              faceDoubleBytes) ||
        !copy(result.faceVolumes.data(), s.geometry.buffers[1].handle,
              faceDoubleBytes) ||
        !copy(&geometryStatus, s.geometry.buffers[2].handle,
              sizeof(geometryStatus)) ||
        !copy(totals, s.geometry.buffers[3].handle, sizeof(totals)))
    {
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    status = s.operations.synchronize();
    if (!status.success)
    {
        result.error = error(DeviceStateErrorCode::SynchronizationFailed,
                             status.operation.empty() ? "synchronize_geometry_diagnostic"
                                                      : status.operation,
                             status.message, status.nativeCode);
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    ++s.report.synchronizations;
    counter.completedOperations += 4;
    counter.completedBytes += diagnosticBytes;
    result.totalArea = totals[0];
    result.totalVolume = totals[1];
    const bool finiteFaces =
        std::all_of(result.faceAreas.begin(), result.faceAreas.end(),
                    [](double value) { return std::isfinite(value) && value >= 0.0; }) &&
        std::all_of(result.faceVolumes.begin(), result.faceVolumes.end(),
                    [](double value) { return std::isfinite(value); });
    if (geometryStatus != 0 || !finiteFaces ||
        !std::isfinite(result.totalArea) || result.totalArea < 0.0 ||
        !std::isfinite(result.totalVolume))
    {
        result.error = error(DeviceStateErrorCode::CandidateFailed,
                             "validate_candidate_geometry",
                             "device geometry produced nonfinite or invalid output");
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    s.report.phase = TransactionPhase::Validated;
    s.clear_error();
    return result;
}

MembraneCandidateResult MeshStateCore::compute_candidate_membrane()
{
    auto &s = *impl_;
    MembraneCandidateResult result;
    result.coordinateGeneration = s.report.candidateGeneration;
    s.report.lastDirtyGroups.fill(false);
    if (s.report.phase != TransactionPhase::CandidatePrepared ||
        s.topology.buffers.size() < 7 || s.parameters.buffers.size() < 3 ||
        s.numericalPlan.buffers.size() < 3 ||
        s.coordinates.buffers.size() != 3 || s.geometry.buffers.size() != 4 ||
        s.membrane.buffers.size() != 9)
    {
        result.error = error(DeviceStateErrorCode::InvalidTransition,
                             "compute_candidate_membrane",
                             "membrane evaluation requires a prepared candidate and complete resident buffers");
        s.record(result.error);
        return result;
    }
    if (!s.operations.computeMembrane)
    {
        result.error = error(DeviceStateErrorCode::InvalidConfiguration,
                             "compute_candidate_membrane",
                             "the device driver does not provide the Step-5 membrane operation");
        s.record(result.error);
        return result;
    }
    if (s.report.cleanupPending)
    {
        result.error = s.cleanup_blocked("compute_candidate_membrane");
        s.record(result.error);
        return result;
    }

    s.report.phase = TransactionPhase::Computing;
    s.report.lastDirtyGroups[static_cast<std::size_t>(
        TransferReason::CandidateMembrane)] = true;
    const MembraneLaunch launch{
        s.topology.buffers[4].handle,
        s.topology.buffers[6].handle,
        s.parameters.buffers[1].handle,
        s.parameters.buffers[2].handle,
        s.numericalPlan.buffers[1].handle,
        s.numericalPlan.buffers[2].handle,
        s.coordinates.buffers[s.report.candidateCoordinateSlot].handle,
        s.geometry.buffers[0].handle,
        s.geometry.buffers[1].handle,
        s.geometry.buffers[3].handle,
        s.membrane.buffers[0].handle,
        s.membrane.buffers[1].handle,
        s.membrane.buffers[2].handle,
        s.membrane.buffers[3].handle,
        s.membrane.buffers[4].handle,
        s.membrane.buffers[5].handle,
        s.membrane.buffers[6].handle,
        s.membrane.buffers[7].handle,
        s.membrane.buffers[8].handle,
        s.vertexCount,
        s.faceCount,
        s.evaluatedFaceCount,
    };
    DriverStatus driverStatus = s.operations.computeMembrane(launch);
    if (!driverStatus.success)
    {
        result.error = error(DeviceStateErrorCode::CandidateFailed,
                             driverStatus.operation.empty()
                                 ? "compute_membrane"
                                 : driverStatus.operation,
                             driverStatus.message, driverStatus.nativeCode);
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    driverStatus = s.operations.synchronize();
    if (!driverStatus.success)
    {
        result.error = error(DeviceStateErrorCode::SynchronizationFailed,
                             driverStatus.operation.empty()
                                 ? "synchronize_membrane"
                                 : driverStatus.operation,
                             driverStatus.message, driverStatus.nativeCode);
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    ++s.report.synchronizations;

    const std::size_t faces = static_cast<std::size_t>(s.faceCount);
    const std::size_t evaluated =
        static_cast<std::size_t>(s.evaluatedFaceCount);
    result.faceAreas.resize(faces);
    result.faceVolumes.resize(faces);
    result.faceBendingEnergies.resize(faces);
    result.faceMeanCurvatures.resize(faces);
    result.faceNormals.resize(faces * 3U);
    result.occurrenceForces.resize(evaluated * kRegularControlCount * 9U);
    result.sampleSurfaceMeasures.resize(evaluated * kQuadratureSampleCount);
    result.sampleMeanCurvatures.resize(evaluated * kQuadratureSampleCount);
    result.sampleNormals.resize(evaluated * kQuadratureSampleCount * 3U);
    result.sampleBendingEnergies.resize(evaluated * kQuadratureSampleCount);
    double totals[2]{};
    std::int32_t diagnostics[3]{};
    auto &counter = s.report.transfers[static_cast<std::size_t>(
        TransferReason::MembraneDiagnostics)];
    std::uint64_t completedOperations = 0;
    std::uint64_t diagnosticBytes = 0;
    const auto copy = [&](void *destination, DeviceBufferHandle source,
                          std::size_t bytes) -> bool {
        if (bytes == 0)
            return true;
        ++counter.attemptedOperations;
        counter.attemptedBytes += bytes;
        const DriverStatus copied =
            s.operations.copyDeviceToHost(destination, source, bytes);
        if (!copied.success)
        {
            result.error = error(
                DeviceStateErrorCode::TransferFailed,
                copied.operation.empty() ? "copy_membrane_diagnostic"
                                         : copied.operation,
                copied.message, copied.nativeCode);
            return false;
        }
        ++completedOperations;
        diagnosticBytes += bytes;
        return true;
    };
    const std::size_t faceBytes = faces * sizeof(double);
    if (!copy(result.faceAreas.data(), s.geometry.buffers[0].handle,
              faceBytes) ||
        !copy(result.faceVolumes.data(), s.geometry.buffers[1].handle,
              faceBytes) ||
        !copy(totals, s.geometry.buffers[3].handle, sizeof(totals)) ||
        !copy(result.faceBendingEnergies.data(), s.membrane.buffers[0].handle,
              faceBytes) ||
        !copy(result.faceMeanCurvatures.data(), s.membrane.buffers[1].handle,
              faceBytes) ||
        !copy(result.faceNormals.data(), s.membrane.buffers[2].handle,
              result.faceNormals.size() * sizeof(double)) ||
        !copy(result.occurrenceForces.data(), s.membrane.buffers[3].handle,
              result.occurrenceForces.size() * sizeof(double)) ||
        !copy(result.sampleSurfaceMeasures.data(),
              s.membrane.buffers[4].handle,
              result.sampleSurfaceMeasures.size() * sizeof(double)) ||
        !copy(result.sampleMeanCurvatures.data(),
              s.membrane.buffers[5].handle,
              result.sampleMeanCurvatures.size() * sizeof(double)) ||
        !copy(result.sampleNormals.data(), s.membrane.buffers[6].handle,
              result.sampleNormals.size() * sizeof(double)) ||
        !copy(result.sampleBendingEnergies.data(),
              s.membrane.buffers[7].handle,
              result.sampleBendingEnergies.size() * sizeof(double)) ||
        !copy(diagnostics, s.membrane.buffers[8].handle,
              sizeof(diagnostics)))
    {
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    driverStatus = s.operations.synchronize();
    if (!driverStatus.success)
    {
        result.error = error(DeviceStateErrorCode::SynchronizationFailed,
                             driverStatus.operation.empty()
                                 ? "synchronize_membrane_diagnostic"
                                 : driverStatus.operation,
                             driverStatus.message, driverStatus.nativeCode);
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    ++s.report.synchronizations;
    counter.completedOperations += completedOperations;
    counter.completedBytes += diagnosticBytes;
    result.totalArea = totals[0];
    result.totalVolume = totals[1];
    result.status = static_cast<MembraneStatusCode>(diagnostics[0]);
    result.failedEvaluatedFace = diagnostics[1] < 0
                                     ? 0U
                                     : static_cast<std::uint64_t>(diagnostics[1]);
    result.failedSample = diagnostics[2] < 0
                              ? 0U
                              : static_cast<std::uint32_t>(diagnostics[2]);
    const auto allFinite = [](const std::vector<double> &values) {
        return std::all_of(values.begin(), values.end(),
                           [](double value) { return std::isfinite(value); });
    };
    const auto normalsValid = [](const std::vector<double> &values,
                                 bool allowZero) {
        if (values.size() % 3U != 0U)
            return false;
        for (std::size_t index = 0; index < values.size(); index += 3U)
        {
            const double squared = values[index] * values[index] +
                                   values[index + 1U] * values[index + 1U] +
                                   values[index + 2U] * values[index + 2U];
            if (allowZero && squared == 0.0)
                continue;
            if (!std::isfinite(squared) || std::abs(squared - 1.0) > 1.0e-10)
                return false;
        }
        return true;
    };
    double summedArea = 0.0;
    double summedVolume = 0.0;
    for (std::size_t face = 0; face < result.faceAreas.size(); ++face)
    {
        summedArea += result.faceAreas[face];
        summedVolume += result.faceVolumes[face];
    }
    const auto totalMatches = [](double actual, double expected) {
        return std::abs(actual - expected) <=
               1.0e-12 * std::max(1.0, std::abs(expected));
    };
    const bool valid =
        result.status == MembraneStatusCode::None &&
        allFinite(result.faceAreas) &&
        std::all_of(result.faceAreas.begin(), result.faceAreas.end(),
                    [](double value) { return value >= 0.0; }) &&
        allFinite(result.faceVolumes) &&
        allFinite(result.faceBendingEnergies) &&
        std::all_of(result.faceBendingEnergies.begin(),
                    result.faceBendingEnergies.end(),
                    [](double value) { return value >= 0.0; }) &&
        allFinite(result.faceMeanCurvatures) && allFinite(result.faceNormals) &&
        normalsValid(result.faceNormals, true) &&
        allFinite(result.occurrenceForces) &&
        allFinite(result.sampleSurfaceMeasures) &&
        std::all_of(result.sampleSurfaceMeasures.begin(),
                    result.sampleSurfaceMeasures.end(),
                    [](double value) { return value > 0.0; }) &&
        allFinite(result.sampleMeanCurvatures) &&
        allFinite(result.sampleNormals) &&
        normalsValid(result.sampleNormals, false) &&
        allFinite(result.sampleBendingEnergies) &&
        std::all_of(result.sampleBendingEnergies.begin(),
                    result.sampleBendingEnergies.end(),
                    [](double value) { return value >= 0.0; }) &&
        std::isfinite(result.totalArea) && result.totalArea >= 0.0 &&
        std::isfinite(result.totalVolume) &&
        totalMatches(result.totalArea, summedArea) &&
        totalMatches(result.totalVolume, summedVolume);
    if (!valid)
    {
        result.error = error(DeviceStateErrorCode::CandidateFailed,
                             "validate_candidate_membrane",
                             "device membrane evaluation reported a degeneracy or nonfinite output");
        s.report.phase = TransactionPhase::Failed;
        s.report.lastOutcome = TransactionOutcome::Failed;
        s.record(result.error);
        return result;
    }
    s.report.phase = TransactionPhase::Validated;
    s.clear_error();
    return result;
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

DeviceStateError MeshStateCore::retry_cleanup()
{
    auto &s = *impl_;
    if (s.closed || s.closing)
        return s.record(error(DeviceStateErrorCode::InvalidTransition,
                              "retry_cleanup",
                              "use close to retry cleanup while closing"));
    if (!s.report.cleanupPending)
    {
        s.clear_error();
        return {};
    }
    DeviceStateError released = s.release_group(s.deferredCleanup);
    s.refresh_cleanup_state();
    if (!released.ok())
    {
        s.report.cleanupError = released;
        return s.record(released);
    }
    s.clear_error();
    return {};
}

DeviceStateError MeshStateCore::close()
{
    if (!impl_ || impl_->closed)
        return {};
    auto &s = *impl_;
    if (!s.closing)
    {
        for (BufferGroup *group : {&s.membrane, &s.geometry, &s.reference, &s.coordinates, &s.parameters,
                                   &s.numericalPlan, &s.topology})
        {
            for (auto &buffer : group->buffers)
                s.deferredCleanup.buffers.push_back(std::move(buffer));
            group->buffers.clear();
        }
        s.closing = true;
        s.initialized = false;
        s.report.available = false;
        s.report.phase = TransactionPhase::Closing;
        s.report.residentBytes = 0;
        s.refresh_cleanup_state();
    }
    DeviceStateError result = s.release_group(s.deferredCleanup);
    s.refresh_cleanup_state();
    if (!result.ok())
    {
        s.report.cleanupError = result;
        return s.record(result);
    }
    s.closed = true;
    s.closing = false;
    s.report.phase = TransactionPhase::Closed;
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

DeviceBufferHandle MeshStateCore::candidate_coordinate_handle_for_testing() const noexcept
{
    if (!impl_ || impl_->coordinates.buffers.size() < 3)
        return 0;
    return impl_->coordinates
        .buffers[impl_->report.candidateCoordinateSlot]
        .handle;
}

DeviceBufferHandle MeshStateCore::previous_coordinate_handle_for_testing() const noexcept
{
    if (!impl_ || impl_->coordinates.buffers.size() < 3)
        return 0;
    return impl_->coordinates
        .buffers[impl_->report.previousCoordinateSlot]
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

struct CudaMeshState::Impl
{
    std::function<detail::DriverStatus()> closeStream;
    std::unique_ptr<detail::MeshStateCore> core;
    detail::StreamCleanupState streamCleanup;
    DeviceStateReport report;
    bool closed = false;

    void refresh()
    {
        report = core->report();
        streamCleanup.overlay(report);
    }

    DeviceStateError guard(const char *operation)
    {
        return streamCleanup.guard(operation, report);
    }
};

CudaMeshState::CudaMeshState(std::unique_ptr<Impl> impl)
    : impl_(std::move(impl))
{
}
CudaMeshState::CudaMeshState(CudaMeshState &&) noexcept = default;
CudaMeshState &CudaMeshState::operator=(CudaMeshState &&) noexcept = default;
CudaMeshState::~CudaMeshState()
{
    if (impl_)
        close();
}

DeviceStateError CudaMeshState::ensure_resident(const RegularMeshPack &pack)
{
    DeviceStateError blocked = impl_->guard("ensure_resident");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->ensure_resident(pack);
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::prepare_candidate(
    const std::vector<double> &coordinates, std::uint64_t generation)
{
    DeviceStateError blocked = impl_->guard("prepare_candidate");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->prepare_candidate(coordinates,
                                                              generation);
    impl_->refresh();
    return result;
}

GeometryCandidateResult CudaMeshState::compute_candidate_geometry()
{
    GeometryCandidateResult result;
    DeviceStateError blocked = impl_->guard("compute_candidate_geometry");
    if (!blocked.ok())
    {
        result.error = blocked;
        return result;
    }
    result = impl_->core->compute_candidate_geometry();
    impl_->refresh();
    return result;
}

MembraneCandidateResult CudaMeshState::compute_candidate_membrane()
{
    MembraneCandidateResult result;
    DeviceStateError blocked = impl_->guard("compute_candidate_membrane");
    if (!blocked.ok())
    {
        result.error = blocked;
        return result;
    }
    result = impl_->core->compute_candidate_membrane();
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::mark_computing()
{
    DeviceStateError blocked = impl_->guard("mark_computing");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->mark_computing();
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::mark_validated()
{
    DeviceStateError blocked = impl_->guard("mark_validated");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->mark_validated();
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::commit()
{
    DeviceStateError blocked = impl_->guard("commit");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->commit();
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::rollback()
{
    DeviceStateError blocked = impl_->guard("rollback");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->rollback();
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::fail_candidate(const std::string &operation,
                                                const std::string &message)
{
    DeviceStateError blocked = impl_->guard("fail_candidate");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->fail_candidate(operation, message);
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::recover()
{
    DeviceStateError blocked = impl_->guard("recover");
    if (!blocked.ok())
        return blocked;
    DeviceStateError result = impl_->core->recover();
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::retry_cleanup()
{
    if (!impl_ || impl_->closed)
        return {};
    if (impl_->streamCleanup.pending() ||
        impl_->report.phase == TransactionPhase::Closing)
        return close();
    DeviceStateError result = impl_->core->retry_cleanup();
    impl_->refresh();
    return result;
}

DeviceStateError CudaMeshState::close()
{
    if (!impl_ || impl_->closed)
        return {};
    DeviceStateError result = impl_->core->close();
    impl_->refresh();
    if (!result.ok())
        return result;
    result = impl_->streamCleanup.attempt(impl_->closeStream, impl_->report);
    if (result.ok())
    {
        impl_->refresh();
        impl_->closed = true;
    }
    return result;
}

const DeviceStateReport &CudaMeshState::report() const noexcept
{
    return impl_->report;
}

std::unique_ptr<CudaMeshState> detail::CudaMeshStateFactory::create(
    std::unique_ptr<MeshStateCore> core,
    DeviceStateReport report,
    std::function<DriverStatus()> closeStream)
{
    auto impl = std::make_unique<CudaMeshState::Impl>();
    impl->core = std::move(core);
    impl->closeStream = std::move(closeStream);
    impl->report = std::move(report);
    return std::unique_ptr<CudaMeshState>(new CudaMeshState(std::move(impl)));
}

} // namespace slimed::cuda_residency
