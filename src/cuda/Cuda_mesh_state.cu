#include "cuda/Cuda_mesh_state.hpp"
#include "cuda/detail/Cuda_mesh_state_core.hpp"

#include <cuda_runtime_api.h>

#include <memory>
#include <sstream>
#include <utility>

namespace slimed::cuda_residency
{
namespace
{

detail::DriverStatus runtime_status(cudaError_t code, const char *operation)
{
    if (code == cudaSuccess)
        return {};
    return {false, static_cast<int>(code), operation,
            cudaGetErrorString(code) ? cudaGetErrorString(code)
                                     : "unknown CUDA runtime error"};
}

class RuntimeDriver
{
  public:
    detail::DriverStatus initialize(int deviceOrdinal)
    {
        int count = 0;
        cudaError_t code = cudaGetDeviceCount(&count);
        if (code != cudaSuccess)
            return runtime_status(code, "cudaGetDeviceCount");
        if (deviceOrdinal < 0 || deviceOrdinal >= count)
        {
            std::ostringstream message;
            message << "device ordinal " << deviceOrdinal
                    << " is outside [0, " << count << ')';
            return {false, static_cast<int>(cudaErrorInvalidDevice),
                    "cudaSetDevice", message.str()};
        }
        code = cudaSetDevice(deviceOrdinal);
        if (code != cudaSuccess)
            return runtime_status(code, "cudaSetDevice");
        code = cudaStreamCreateWithFlags(&stream_, cudaStreamNonBlocking);
        if (code != cudaSuccess)
            return runtime_status(code, "cudaStreamCreateWithFlags");
        deviceOrdinal_ = deviceOrdinal;
        return {};
    }

    detail::DeviceOperations operations()
    {
        detail::DeviceOperations ops;
        ops.queryMemory = [this](std::size_t &freeBytes,
                                 std::size_t &totalBytes) {
            cudaError_t code = cudaSetDevice(deviceOrdinal_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaSetDevice(query_memory)");
            return runtime_status(cudaMemGetInfo(&freeBytes, &totalBytes),
                                  "cudaMemGetInfo");
        };
        ops.allocate = [this](std::size_t bytes,
                              detail::DeviceBufferHandle &handle) {
            cudaError_t code = cudaSetDevice(deviceOrdinal_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaSetDevice(allocate)");
            void *pointer = nullptr;
            code = cudaMalloc(&pointer, bytes);
            if (code == cudaSuccess)
                handle = reinterpret_cast<detail::DeviceBufferHandle>(pointer);
            return runtime_status(code, "cudaMalloc");
        };
        ops.release = [this](detail::DeviceBufferHandle handle) {
            cudaError_t code = cudaSetDevice(deviceOrdinal_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaSetDevice(release)");
            return runtime_status(cudaFree(
                                      reinterpret_cast<void *>(handle)),
                                  "cudaFree");
        };
        ops.copyHostToDevice = [this](detail::DeviceBufferHandle handle,
                                      const void *source, std::size_t bytes) {
            cudaError_t code = cudaSetDevice(deviceOrdinal_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaSetDevice(copy)");
            return runtime_status(
                cudaMemcpyAsync(reinterpret_cast<void *>(handle), source, bytes,
                                cudaMemcpyHostToDevice, stream_),
                "cudaMemcpyAsync(host_to_device)");
        };
        ops.synchronize = [this]() {
            return runtime_status(cudaStreamSynchronize(stream_),
                                  "cudaStreamSynchronize");
        };
        return ops;
    }

    detail::DriverStatus close()
    {
        detail::DeviceBufferHandle handle =
            reinterpret_cast<detail::DeviceBufferHandle>(stream_);
        detail::DriverStatus status = detail::release_retryable_handle(
            handle, [](detail::DeviceBufferHandle value) {
                return runtime_status(
                    cudaStreamDestroy(reinterpret_cast<cudaStream_t>(value)),
                    "cudaStreamDestroy");
            });
        stream_ = reinterpret_cast<cudaStream_t>(handle);
        return status;
    }

    ~RuntimeDriver() { close(); }

  private:
    int deviceOrdinal_ = 0;
    cudaStream_t stream_ = nullptr;
};

DeviceStateError initialization_error(const detail::DriverStatus &status)
{
    return {DeviceStateErrorCode::InitializationFailed,
            status.operation.empty() ? "initialize_cuda_mesh_state"
                                     : status.operation,
            status.nativeCode, status.message};
}

} // namespace

CudaMeshStateResult create_cuda_mesh_state(const RegularMeshPack &pack,
                                           const DeviceStateConfig &config)
{
    CudaMeshStateResult result;
    result.report.compiled = true;
    auto driver = std::make_shared<RuntimeDriver>();
    const detail::DriverStatus initialized = driver->initialize(config.deviceOrdinal);
    if (!initialized.success)
    {
        result.report.error = initialization_error(initialized);
        return result;
    }
    auto coreResult = detail::create_mesh_state_core(driver->operations(), pack,
                                                     config);
    result.report = coreResult.report;
    if (!coreResult.state)
        return result;
    result.state = detail::CudaMeshStateFactory::create(
        std::move(coreResult.state), coreResult.report,
        [driver]() { return driver->close(); });
    return result;
}

} // namespace slimed::cuda_residency
