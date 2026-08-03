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

constexpr double kLegacyVolumeQuadratureFactor = 0.16666666666;

__global__ void regular_geometry_kernel(
    const std::int32_t *evaluatedFaceIds,
    const std::int32_t *oneRingSourceIds,
    const double *quadratureCoefficients,
    const double *shapeWeights,
    const double *coordinates,
    double *faceAreas,
    double *faceVolumes,
    std::int32_t *geometryStatus,
    std::uint64_t vertexCount,
    std::uint64_t faceCount,
    std::uint64_t evaluatedFaceCount)
{
    const std::uint64_t evaluated =
        static_cast<std::uint64_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (evaluated >= evaluatedFaceCount)
        return;
    const std::int32_t faceId = evaluatedFaceIds[evaluated];
    if (faceId < 0 || static_cast<std::uint64_t>(faceId) >= faceCount)
    {
        atomicExch(geometryStatus, 1);
        return;
    }

    double area = 0.0;
    double volume = 0.0;
    std::int32_t status = 0;
    for (std::uint32_t sample = 0; sample < kQuadratureSampleCount; ++sample)
    {
        double rows[3][3]{};
        for (std::uint32_t row = 0; row < 3; ++row)
            for (std::uint32_t local = 0; local < kRegularControlCount; ++local)
            {
                const std::int32_t sourceId =
                    oneRingSourceIds[evaluated * kRegularControlCount + local];
                if (sourceId < 0 ||
                    static_cast<std::uint64_t>(sourceId) >= vertexCount)
                {
                    status = 1;
                    continue;
                }
                const double weight = shapeWeights[
                    (sample * kShapeRowCount + row) * kRegularControlCount +
                    local];
                for (std::uint32_t axis = 0; axis < kCoordinateAxisCount; ++axis)
                    rows[row][axis] += weight * coordinates[
                        static_cast<std::uint64_t>(sourceId) *
                            kCoordinateAxisCount + axis];
            }
        const double cross[3]{
            rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1],
            rows[1][2] * rows[2][0] - rows[1][0] * rows[2][2],
            rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0],
        };
        const double norm = sqrt(cross[0] * cross[0] +
                                 cross[1] * cross[1] +
                                 cross[2] * cross[2]);
        const double coefficient = quadratureCoefficients[sample];
        area += 0.5 * coefficient * norm;
        volume += kLegacyVolumeQuadratureFactor * coefficient *
                  rows[0][0] * cross[0];
    }
    if (!isfinite(area) || area < 0.0 || !isfinite(volume))
        status = 1;
    faceAreas[faceId] = area;
    faceVolumes[faceId] = volume;
    if (status != 0)
        atomicExch(geometryStatus, 1);
}

__global__ void deterministic_geometry_reduction_kernel(
    const double *faceAreas,
    const double *faceVolumes,
    std::int32_t *geometryStatus,
    double *totals,
    std::uint64_t faceCount)
{
    if (blockIdx.x != 0 || threadIdx.x != 0)
        return;
    double area = 0.0;
    double volume = 0.0;
    for (std::uint64_t face = 0; face < faceCount; ++face)
    {
        area += faceAreas[face];
        volume += faceVolumes[face];
    }
    if (!isfinite(area) || area < 0.0 || !isfinite(volume))
        *geometryStatus = 1;
    totals[0] = area;
    totals[1] = volume;
}

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
        ops.copyDeviceToHost = [this](void *destination,
                                      detail::DeviceBufferHandle handle,
                                      std::size_t bytes) {
            cudaError_t code = cudaSetDevice(deviceOrdinal_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaSetDevice(copy_to_host)");
            return runtime_status(
                cudaMemcpyAsync(destination, reinterpret_cast<void *>(handle),
                                bytes, cudaMemcpyDeviceToHost, stream_),
                "cudaMemcpyAsync(device_to_host)");
        };
        ops.computeGeometry = [this](const detail::GeometryLaunch &launch) {
            cudaError_t code = cudaSetDevice(deviceOrdinal_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaSetDevice(compute_geometry)");
            if (launch.faceCount != 0)
            {
                code = cudaMemsetAsync(
                    reinterpret_cast<void *>(launch.faceAreas), 0,
                    launch.faceCount * sizeof(double), stream_);
                if (code == cudaSuccess)
                    code = cudaMemsetAsync(
                        reinterpret_cast<void *>(launch.faceVolumes), 0,
                        launch.faceCount * sizeof(double), stream_);
            }
            if (code == cudaSuccess)
                code = cudaMemsetAsync(
                    reinterpret_cast<void *>(launch.status), 0,
                    sizeof(std::int32_t), stream_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaMemsetAsync(geometry)");
            constexpr unsigned int threads = 128;
            const unsigned int blocks = static_cast<unsigned int>(
                (launch.evaluatedFaceCount + threads - 1) / threads);
            if (blocks != 0)
            {
                regular_geometry_kernel<<<blocks, threads, 0, stream_>>>(
                    reinterpret_cast<const std::int32_t *>(launch.evaluatedFaceIds),
                    reinterpret_cast<const std::int32_t *>(launch.oneRingSourceIds),
                    reinterpret_cast<const double *>(launch.quadratureCoefficients),
                    reinterpret_cast<const double *>(launch.shapeWeights),
                    reinterpret_cast<const double *>(launch.coordinates),
                    reinterpret_cast<double *>(launch.faceAreas),
                    reinterpret_cast<double *>(launch.faceVolumes),
                    reinterpret_cast<std::int32_t *>(launch.status),
                    launch.vertexCount, launch.faceCount,
                    launch.evaluatedFaceCount);
                code = cudaGetLastError();
                if (code != cudaSuccess)
                    return runtime_status(code, "regular_geometry_kernel");
            }
            deterministic_geometry_reduction_kernel<<<1, 1, 0, stream_>>>(
                reinterpret_cast<const double *>(launch.faceAreas),
                reinterpret_cast<const double *>(launch.faceVolumes),
                reinterpret_cast<std::int32_t *>(launch.status),
                reinterpret_cast<double *>(launch.totals), launch.faceCount);
            return runtime_status(cudaGetLastError(),
                                  "deterministic_geometry_reduction_kernel");
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
