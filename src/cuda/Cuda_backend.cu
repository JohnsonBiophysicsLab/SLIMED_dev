#include "cuda/Cuda_backend.hpp"
#include "cuda/detail/Cuda_context_lifetime.hpp"

#include <cuda.h>
#include <cuda_runtime_api.h>

#include <array>
#include <memory>
#include <string>
#include <utility>

namespace slimed::cuda_backend
{
namespace
{

ErrorCode classify_driver_error(const CUresult status,
                                const ErrorCode fallback) noexcept
{
    if (status == CUDA_ERROR_NO_DEVICE)
        return ErrorCode::NoDevice;
    if (status == CUDA_ERROR_SYSTEM_DRIVER_MISMATCH)
        return ErrorCode::InsufficientDriver;
    if (status == CUDA_ERROR_INVALID_DEVICE)
        return ErrorCode::InvalidDeviceOrdinal;
    return fallback;
}

Error driver_error(const CUresult status, const ErrorCode fallback,
                   const char *operation)
{
    const char *description = nullptr;
    const CUresult descriptionStatus = cuGetErrorString(status, &description);
    Error error;
    error.code = classify_driver_error(status, fallback);
    error.operation = operation;
    error.nativeCode = static_cast<int>(status);
    error.message =
        descriptionStatus == CUDA_SUCCESS && description != nullptr
            ? description
            : "CUDA driver API returned an unknown error";
    return error;
}

Error runtime_error(const cudaError_t status, const char *operation)
{
    Error error;
    error.code = status == cudaErrorInsufficientDriver
                     ? ErrorCode::InsufficientDriver
                     : ErrorCode::CapabilityQueryFailed;
    error.operation = operation;
    error.nativeCode = static_cast<int>(status);
    error.message = cudaGetErrorString(status);
    return error;
}

bool driver_attribute(const CUdevice device, const CUdevice_attribute attribute,
                      int &value, BackendReport &report,
                      const char *operation)
{
    const CUresult status = cuDeviceGetAttribute(&value, attribute, device);
    if (status == CUDA_SUCCESS)
        return true;
    report.error =
        driver_error(status, ErrorCode::CapabilityQueryFailed, operation);
    return false;
}

detail::OpaqueHandle opaque_context(const CUcontext context) noexcept
{
    return reinterpret_cast<detail::OpaqueHandle>(context);
}

detail::OpaqueHandle opaque_stream(const CUstream stream) noexcept
{
    return reinterpret_cast<detail::OpaqueHandle>(stream);
}

int push_context(void *, const detail::OpaqueHandle context) noexcept
{
    return static_cast<int>(
        cuCtxPushCurrent(reinterpret_cast<CUcontext>(context)));
}

int pop_context(void *, detail::OpaqueHandle *context) noexcept
{
    CUcontext popped = nullptr;
    const CUresult status = cuCtxPopCurrent(&popped);
    *context = opaque_context(popped);
    return static_cast<int>(status);
}

int destroy_stream(void *, const detail::OpaqueHandle stream) noexcept
{
    return static_cast<int>(
        cuStreamDestroy(reinterpret_cast<CUstream>(stream)));
}

int release_primary_context(void *, const int device) noexcept
{
    return static_cast<int>(cuDevicePrimaryCtxRelease(device));
}

detail::LifetimeDriverCalls lifetime_driver_calls() noexcept
{
    detail::LifetimeDriverCalls calls;
    calls.successCode = static_cast<int>(CUDA_SUCCESS);
    calls.pushContext = push_context;
    calls.popContext = pop_context;
    calls.destroyStream = destroy_stream;
    calls.releasePrimaryContext = release_primary_context;
    return calls;
}

Error lifetime_error(const detail::LifetimeFailure failure,
                     const ErrorCode code, const bool cleanup)
{
    Error error;
    error.code = code;
    error.nativeCode = failure.nativeCode;
    if (cleanup)
        error.operation = detail::lifetime_operation_name(failure.operation);
    else if (failure.operation == detail::LifetimeOperation::PushContext)
        error.operation = "cuCtxPushCurrent";
    else if (failure.operation == detail::LifetimeOperation::PopContext)
        error.operation = "cuCtxPopCurrent";
    else
        error.operation = "context_stack";

    if (failure.operation ==
        detail::LifetimeOperation::UnexpectedPoppedContext)
    {
        error.message =
            "CUDA popped a context different from the retained primary context";
        return error;
    }

    const char *description = nullptr;
    const CUresult status = static_cast<CUresult>(failure.nativeCode);
    const CUresult descriptionStatus = cuGetErrorString(status, &description);
    error.message =
        descriptionStatus == CUDA_SUCCESS && description != nullptr
            ? description
            : "CUDA driver API returned an unknown lifetime error";
    return error;
}

} // namespace

struct DeviceContext::Impl
{
    CUdevice device = 0;
    CUcontext context = nullptr;
    detail::ContextLifetime lifetime{lifetime_driver_calls()};

    ~Impl() noexcept
    {
        try
        {
            (void)cleanup();
        }
        catch (...)
        {
        }
    }

    Error cleanup()
    {
        const detail::LifetimeFailure failure = lifetime.cleanup();
        return failure.ok()
                   ? Error{}
                   : lifetime_error(failure, ErrorCode::CleanupFailed, true);
    }
};

DeviceContext::DeviceContext(std::unique_ptr<Impl> impl,
                             DeviceCapabilities capabilities)
    : impl_(std::move(impl)), capabilities_(std::move(capabilities))
{
}

DeviceContext::DeviceContext(DeviceContext &&) noexcept = default;
DeviceContext &DeviceContext::operator=(DeviceContext &&) noexcept = default;
DeviceContext::~DeviceContext()
{
    try
    {
        (void)close();
    }
    catch (...)
    {
    }
}

const DeviceCapabilities &DeviceContext::capabilities() const noexcept
{
    return capabilities_;
}

Error DeviceContext::close()
{
    if (impl_ == nullptr)
        return {};
    Error error = impl_->cleanup();
    if (error.ok())
        impl_.reset();
    return error;
}

ContextResult create_device_context(const int deviceOrdinal)
{
    ContextResult result;
    BackendReport &report = result.report;
    report.compiled = true;
    report.device.requestedDeviceOrdinal = deviceOrdinal;

    CUresult status = cuInit(0);
    if (status != CUDA_SUCCESS)
    {
        report.error =
            driver_error(status, ErrorCode::InitializationFailed, "cuInit");
        return result;
    }

    status = cuDeviceGetCount(&report.device.deviceCount);
    if (status != CUDA_SUCCESS)
    {
        report.error = driver_error(status, ErrorCode::CapabilityQueryFailed,
                                    "cuDeviceGetCount");
        return result;
    }
    if (report.device.deviceCount == 0)
    {
        report.error.code = ErrorCode::NoDevice;
        report.error.operation = "cuDeviceGetCount";
        report.error.message = "no CUDA devices were reported by the driver";
        return result;
    }
    if (deviceOrdinal < 0 || deviceOrdinal >= report.device.deviceCount)
    {
        report.error.code = ErrorCode::InvalidDeviceOrdinal;
        report.error.operation = "device_ordinal";
        report.error.message = "requested CUDA device ordinal is out of range";
        return result;
    }

    auto impl = std::make_unique<DeviceContext::Impl>();
    status = cuDeviceGet(&impl->device, deviceOrdinal);
    if (status != CUDA_SUCCESS)
    {
        report.error = driver_error(status, ErrorCode::CapabilityQueryFailed,
                                    "cuDeviceGet");
        return result;
    }

    std::array<char, 256> name{};
    status = cuDeviceGetName(name.data(), static_cast<int>(name.size()),
                             impl->device);
    if (status != CUDA_SUCCESS)
    {
        report.error = driver_error(status, ErrorCode::CapabilityQueryFailed,
                                    "cuDeviceGetName");
        return result;
    }
    report.device.name = name.data();

    if (!driver_attribute(impl->device,
                          CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR,
                          report.device.computeCapabilityMajor, report,
                          "cuDeviceGetAttribute compute capability major") ||
        !driver_attribute(impl->device,
                          CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR,
                          report.device.computeCapabilityMinor, report,
                          "cuDeviceGetAttribute compute capability minor"))
        return result;

    status = cuDriverGetVersion(&report.device.driverVersion);
    if (status != CUDA_SUCCESS)
    {
        report.error = driver_error(status, ErrorCode::CapabilityQueryFailed,
                                    "cuDriverGetVersion");
        return result;
    }

    const cudaError_t runtimeStatus =
        cudaRuntimeGetVersion(&report.device.runtimeVersion);
    if (runtimeStatus != cudaSuccess)
    {
        report.error = runtime_error(runtimeStatus, "cudaRuntimeGetVersion");
        return result;
    }

    status = cuDeviceTotalMem(&report.device.totalMemoryBytes, impl->device);
    if (status != CUDA_SUCCESS)
    {
        report.error = driver_error(status, ErrorCode::CapabilityQueryFailed,
                                    "cuDeviceTotalMem");
        return result;
    }

    int memoryPoolsSupported = 0;
    if (!driver_attribute(impl->device,
                          CU_DEVICE_ATTRIBUTE_MEMORY_POOLS_SUPPORTED,
                          memoryPoolsSupported, report,
                          "cuDeviceGetAttribute memory pools"))
        return result;
    report.device.memoryPoolsSupported = memoryPoolsSupported != 0;

    if (!driver_attribute(impl->device,
                          CU_DEVICE_ATTRIBUTE_MULTIPROCESSOR_COUNT,
                          report.device.multiprocessorCount, report,
                          "cuDeviceGetAttribute multiprocessor count") ||
        !driver_attribute(impl->device, CU_DEVICE_ATTRIBUTE_WARP_SIZE,
                          report.device.warpSize, report,
                          "cuDeviceGetAttribute warp size") ||
        !driver_attribute(impl->device,
                          CU_DEVICE_ATTRIBUTE_MAX_THREADS_PER_BLOCK,
                          report.device.maximumThreadsPerBlock, report,
                          "cuDeviceGetAttribute max threads per block") ||
        !driver_attribute(impl->device,
                          CU_DEVICE_ATTRIBUTE_ASYNC_ENGINE_COUNT,
                          report.device.asynchronousEngineCount, report,
                          "cuDeviceGetAttribute async engine count"))
        return result;

    status = cuDevicePrimaryCtxRetain(&impl->context, impl->device);
    if (status != CUDA_SUCCESS)
    {
        report.error = driver_error(status, ErrorCode::ContextCreationFailed,
                                    "cuDevicePrimaryCtxRetain");
        return result;
    }
    impl->lifetime.markPrimaryContextRetained(
        static_cast<int>(impl->device), opaque_context(impl->context));
    report.device.primaryContextRetained = true;

    const auto finishFailure = [&report, &impl](Error primaryError) {
        Error cleanupError = impl->cleanup();
        if (!cleanupError.ok())
        {
            cleanupError.message += "; preceding failure in " +
                                    primaryError.operation + ": " +
                                    primaryError.message;
            report.error = std::move(cleanupError);
        }
        else
            report.error = std::move(primaryError);
    };

    detail::LifetimeFailure lifetimeStatus = impl->lifetime.pushContext();
    if (!lifetimeStatus.ok())
    {
        finishFailure(lifetime_error(lifetimeStatus,
                                     ErrorCode::ContextStackFailed, false));
        return result;
    }

    const CUresult memoryStatus =
        cuMemGetInfo(&report.device.freeMemoryBytes,
                     &report.device.totalMemoryBytes);
    CUresult streamStatus = CUDA_SUCCESS;
    CUstream stream = nullptr;
    if (memoryStatus == CUDA_SUCCESS)
    {
        streamStatus = cuStreamCreate(&stream, CU_STREAM_NON_BLOCKING);
        if (streamStatus == CUDA_SUCCESS)
            impl->lifetime.markStreamCreated(opaque_stream(stream));
    }

    lifetimeStatus = impl->lifetime.popContext();
    if (!lifetimeStatus.ok())
    {
        finishFailure(lifetime_error(lifetimeStatus,
                                     ErrorCode::ContextStackFailed, false));
        return result;
    }
    if (memoryStatus != CUDA_SUCCESS)
    {
        finishFailure(driver_error(memoryStatus,
                                   ErrorCode::CapabilityQueryFailed,
                                   "cuMemGetInfo"));
        return result;
    }
    if (streamStatus != CUDA_SUCCESS)
    {
        finishFailure(driver_error(streamStatus,
                                   ErrorCode::StreamCreationFailed,
                                   "cuStreamCreate"));
        return result;
    }

    report.device.nonblockingStreamOwned = true;
    report.available = true;
    result.context.reset(
        new DeviceContext(std::move(impl), report.device));
    return result;
}

BackendReport query_backend(const int deviceOrdinal)
{
    ContextResult result = create_device_context(deviceOrdinal);
    if (result.context != nullptr)
    {
        const Error cleanupError = result.context->close();
        if (!cleanupError.ok())
        {
            result.report.available = false;
            result.report.error = cleanupError;
        }
    }
    return result.report;
}

} // namespace slimed::cuda_backend
