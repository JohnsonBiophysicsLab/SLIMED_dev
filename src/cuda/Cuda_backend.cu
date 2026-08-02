#include "cuda/Cuda_backend.hpp"

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

} // namespace

struct DeviceContext::Impl
{
    CUdevice device = 0;
    CUcontext context = nullptr;
    CUstream stream = nullptr;
    bool retained = false;

    ~Impl() noexcept
    {
        if (stream != nullptr && context != nullptr)
        {
            if (cuCtxPushCurrent(context) == CUDA_SUCCESS)
            {
                (void)cuStreamDestroy(stream);
                CUcontext popped = nullptr;
                (void)cuCtxPopCurrent(&popped);
            }
        }
        if (retained)
            (void)cuDevicePrimaryCtxRelease(device);
    }
};

DeviceContext::DeviceContext(std::unique_ptr<Impl> impl,
                             DeviceCapabilities capabilities)
    : impl_(std::move(impl)), capabilities_(std::move(capabilities))
{
}

DeviceContext::DeviceContext(DeviceContext &&) noexcept = default;
DeviceContext &DeviceContext::operator=(DeviceContext &&) noexcept = default;
DeviceContext::~DeviceContext() = default;

const DeviceCapabilities &DeviceContext::capabilities() const noexcept
{
    return capabilities_;
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
    impl->retained = true;
    report.device.primaryContextRetained = true;

    status = cuCtxPushCurrent(impl->context);
    if (status != CUDA_SUCCESS)
    {
        report.error = driver_error(status, ErrorCode::ContextStackFailed,
                                    "cuCtxPushCurrent");
        return result;
    }

    const CUresult memoryStatus =
        cuMemGetInfo(&report.device.freeMemoryBytes,
                     &report.device.totalMemoryBytes);
    CUresult streamStatus = CUDA_SUCCESS;
    if (memoryStatus == CUDA_SUCCESS)
        streamStatus = cuStreamCreate(&impl->stream, CU_STREAM_NON_BLOCKING);

    CUcontext popped = nullptr;
    const CUresult popStatus = cuCtxPopCurrent(&popped);
    if (popStatus != CUDA_SUCCESS)
    {
        report.error = driver_error(popStatus, ErrorCode::ContextStackFailed,
                                    "cuCtxPopCurrent");
        return result;
    }
    if (memoryStatus != CUDA_SUCCESS)
    {
        report.error = driver_error(memoryStatus,
                                    ErrorCode::CapabilityQueryFailed,
                                    "cuMemGetInfo");
        return result;
    }
    if (streamStatus != CUDA_SUCCESS)
    {
        report.error = driver_error(streamStatus,
                                    ErrorCode::StreamCreationFailed,
                                    "cuStreamCreate");
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
    return create_device_context(deviceOrdinal).report;
}

} // namespace slimed::cuda_backend
