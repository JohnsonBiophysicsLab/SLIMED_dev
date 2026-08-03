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
        if (!stream_)
            return {};
        const cudaError_t code = cudaStreamDestroy(stream_);
        stream_ = nullptr;
        return runtime_status(code, "cudaStreamDestroy");
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

struct CudaMeshState::Impl
{
    std::unique_ptr<RuntimeDriver> driver;
    std::unique_ptr<detail::MeshStateCore> core;
    DeviceStateReport report;
    bool closed = false;

    void refresh() { report = core->report(); }
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
    DeviceStateError result = impl_->core->ensure_resident(pack);
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::prepare_candidate(
    const std::vector<double> &coordinates, std::uint64_t generation)
{
    DeviceStateError result = impl_->core->prepare_candidate(coordinates,
                                                              generation);
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::mark_computing()
{
    DeviceStateError result = impl_->core->mark_computing();
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::mark_validated()
{
    DeviceStateError result = impl_->core->mark_validated();
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::commit()
{
    DeviceStateError result = impl_->core->commit();
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::rollback()
{
    DeviceStateError result = impl_->core->rollback();
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::fail_candidate(const std::string &operation,
                                                const std::string &message)
{
    DeviceStateError result = impl_->core->fail_candidate(operation, message);
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::recover()
{
    DeviceStateError result = impl_->core->recover();
    impl_->refresh();
    return result;
}
DeviceStateError CudaMeshState::close()
{
    if (!impl_ || impl_->closed)
        return {};
    DeviceStateError result = impl_->core->close();
    impl_->refresh();
    const detail::DriverStatus stream = impl_->driver->close();
    impl_->closed = true;
    if (result.ok() && !stream.success)
    {
        result = {DeviceStateErrorCode::CleanupFailed, stream.operation,
                  stream.nativeCode, stream.message};
        impl_->report.error = result;
    }
    return result;
}
const DeviceStateReport &CudaMeshState::report() const noexcept
{
    return impl_->report;
}

CudaMeshStateResult create_cuda_mesh_state(const RegularMeshPack &pack,
                                           const DeviceStateConfig &config)
{
    CudaMeshStateResult result;
    result.report.compiled = true;
    auto driver = std::make_unique<RuntimeDriver>();
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
    auto impl = std::make_unique<CudaMeshState::Impl>();
    impl->driver = std::move(driver);
    impl->core = std::move(coreResult.state);
    impl->report = coreResult.report;
    result.state = std::unique_ptr<CudaMeshState>(
        new CudaMeshState(std::move(impl)));
    return result;
}

} // namespace slimed::cuda_residency
