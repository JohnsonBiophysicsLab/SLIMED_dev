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

__device__ double dot3(const double left[3], const double right[3])
{
    return left[0] * right[0] + left[1] * right[1] +
           left[2] * right[2];
}

__device__ void cross3(const double left[3], const double right[3],
                       double result[3])
{
    result[0] = left[1] * right[2] - left[2] * right[1];
    result[1] = left[2] * right[0] - left[0] * right[2];
    result[2] = left[0] * right[1] - left[1] * right[0];
}

__device__ void add3(const double left[3], const double right[3],
                     double result[3])
{
    for (int axis = 0; axis < 3; ++axis)
        result[axis] = left[axis] + right[axis];
}

__device__ void linear3(const double left[3], double leftFactor,
                        const double right[3], double rightFactor,
                        double result[3])
{
    for (int axis = 0; axis < 3; ++axis)
        result[axis] = leftFactor * left[axis] +
                       rightFactor * right[axis];
}

__device__ bool finite3(const double value[3])
{
    return isfinite(value[0]) && isfinite(value[1]) && isfinite(value[2]);
}

__device__ void add_outer_scaled(double matrix[3][3],
                                 const double left[3],
                                 const double right[3], double factor)
{
    for (int row = 0; row < 3; ++row)
        for (int column = 0; column < 3; ++column)
            matrix[row][column] +=
                factor * left[row] * right[column];
}

__device__ void transpose_multiply3(const double matrix[3][3],
                                    const double value[3],
                                    double result[3])
{
    for (int column = 0; column < 3; ++column)
    {
        result[column] = 0.0;
        for (int row = 0; row < 3; ++row)
            result[column] += value[row] * matrix[row][column];
    }
}

__device__ void record_membrane_status(std::int32_t *diagnostics,
                                       std::int32_t code,
                                       std::uint64_t evaluated,
                                       std::uint32_t sample)
{
    if (atomicCAS(diagnostics, 0, code) == 0)
    {
        diagnostics[1] = static_cast<std::int32_t>(evaluated);
        diagnostics[2] = static_cast<std::int32_t>(sample);
    }
}

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

__global__ void regular_membrane_kernel(
    const std::int32_t *evaluatedFaceIds,
    const std::int32_t *oneRingSourceIds,
    const double *spontaneousCurvatures,
    const PackedRegularParameters *parameters,
    const double *quadratureCoefficients,
    const double *shapeWeights,
    const double *coordinates,
    double *faceAreas,
    double *faceVolumes,
    double *faceBendingEnergies,
    double *faceMeanCurvatures,
    double *faceNormals,
    double *occurrenceForces,
    double *sampleSurfaceMeasures,
    double *sampleMeanCurvatures,
    double *sampleNormals,
    double *sampleBendingEnergies,
    std::int32_t *diagnostics,
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
        record_membrane_status(diagnostics, 1, evaluated, 0);
        return;
    }

    const PackedRegularParameters parameter = *parameters;
    const double uSurfPerArea =
        parameter.uSurf == 0.0 || parameter.area0 == 0.0
            ? 0.0
            : parameter.uSurf / parameter.area0;
    const double uVol =
        parameter.uVol == 0.0 || parameter.vol0 == 0.0
            ? 0.0
            : parameter.uVol / parameter.vol0;
    const double areaFactor =
        uSurfPerArea * (parameter.area - parameter.area0);
    const double volumeFactor =
        uVol * (parameter.vol - parameter.vol0) / 3.0;
    double area = 0.0;
    double volume = 0.0;
    double faceBending = 0.0;
    double faceMean = 0.0;
    double accumulatedNormal[3]{};

    for (std::uint32_t sample = 0; sample < kQuadratureSampleCount; ++sample)
    {
        double rows[kShapeRowCount][3]{};
        for (std::uint32_t row = 0; row < kShapeRowCount; ++row)
            for (std::uint32_t local = 0; local < kRegularControlCount;
                 ++local)
            {
                const std::int32_t sourceId = oneRingSourceIds[
                    evaluated * kRegularControlCount + local];
                if (sourceId < 0 ||
                    static_cast<std::uint64_t>(sourceId) >= vertexCount)
                {
                    record_membrane_status(diagnostics, 1, evaluated, sample);
                    return;
                }
                const double weight = shapeWeights[
                    (sample * kShapeRowCount + row) * kRegularControlCount +
                    local];
                for (std::uint32_t axis = 0; axis < 3; ++axis)
                    rows[row][axis] += weight * coordinates[
                        static_cast<std::uint64_t>(sourceId) * 3U + axis];
            }

        const double *x = rows[0];
        const double *a_1 = rows[1];
        const double *a_2 = rows[2];
        const double *a_11 = rows[3];
        const double *a_22 = rows[4];
        const double *a_12 = rows[5];
        const double *a_21 = rows[6];
        double xa[3];
        cross3(a_1, a_2, xa);
        const double sqa = sqrt(dot3(xa, xa));
        if (!(sqa > 0.0) || !isfinite(sqa))
        {
            record_membrane_status(diagnostics, 2, evaluated, sample);
            return;
        }
        const double inverseSqa = 1.0 / sqa;
        const double inverseSqaSquared = inverseSqa * inverseSqa;
        double tempLeft[3];
        double tempRight[3];
        double xa_1[3];
        double xa_2[3];
        cross3(a_11, a_2, tempLeft);
        cross3(a_1, a_21, tempRight);
        add3(tempLeft, tempRight, xa_1);
        cross3(a_12, a_2, tempLeft);
        cross3(a_1, a_22, tempRight);
        add3(tempLeft, tempRight, xa_2);
        const double sqa_1 = dot3(xa, xa_1) * inverseSqa;
        const double sqa_2 = dot3(xa, xa_2) * inverseSqa;
        double a_3[3];
        double a_31[3];
        double a_32[3];
        linear3(xa, inverseSqa, xa, 0.0, a_3);
        linear3(xa_1, sqa * inverseSqaSquared,
                xa, -sqa_1 * inverseSqaSquared, a_31);
        linear3(xa_2, sqa * inverseSqaSquared,
                xa, -sqa_2 * inverseSqaSquared, a_32);
        double a2x3[3];
        double a3x1[3];
        double a1[3];
        double a2[3];
        cross3(a_2, a_3, a2x3);
        cross3(a_3, a_1, a3x1);
        linear3(a2x3, inverseSqa, a2x3, 0.0, a1);
        linear3(a3x1, inverseSqa, a3x1, 0.0, a2);
        double a11[3];
        double a12[3];
        double a21[3];
        double a22[3];
        cross3(a_21, a_3, tempLeft);
        cross3(a_2, a_31, tempRight);
        add3(tempLeft, tempRight, tempLeft);
        linear3(tempLeft, sqa * inverseSqaSquared,
                a2x3, -sqa_1 * inverseSqaSquared, a11);
        cross3(a_22, a_3, tempLeft);
        cross3(a_2, a_32, tempRight);
        add3(tempLeft, tempRight, tempLeft);
        linear3(tempLeft, sqa * inverseSqaSquared,
                a2x3, -sqa_2 * inverseSqaSquared, a12);
        cross3(a_31, a_1, tempLeft);
        cross3(a_3, a_11, tempRight);
        add3(tempLeft, tempRight, tempLeft);
        linear3(tempLeft, sqa * inverseSqaSquared,
                a3x1, -sqa_1 * inverseSqaSquared, a21);
        cross3(a_32, a_1, tempLeft);
        cross3(a_3, a_12, tempRight);
        add3(tempLeft, tempRight, tempLeft);
        linear3(tempLeft, sqa * inverseSqaSquared,
                a3x1, -sqa_2 * inverseSqaSquared, a22);
        const double meanCurvature =
            0.5 * (dot3(a1, a_31) + dot3(a2, a_32));
        const double curvatureDifference =
            2.0 * meanCurvature - spontaneousCurvatures[evaluated];
        const double bendingEnergy =
            0.5 * parameter.kCurv * sqa * curvatureDifference *
            curvatureDifference;
        const double bendGradientFactor =
            -parameter.kCurv * curvatureDifference;
        const double bendAreaFactor =
            0.5 * parameter.kCurv * curvatureDifference *
            curvatureDifference;
        double n1Bend[3];
        double n2Bend[3];
        double m1Bend[3];
        double m2Bend[3];
        for (int axis = 0; axis < 3; ++axis)
        {
            n1Bend[axis] = bendGradientFactor *
                               (dot3(a1, a1) * a_31[axis] +
                                dot3(a1, a2) * a_32[axis]) +
                           bendAreaFactor * a1[axis];
            n2Bend[axis] = bendGradientFactor *
                               (dot3(a2, a1) * a_31[axis] +
                                dot3(a2, a2) * a_32[axis]) +
                           bendAreaFactor * a2[axis];
            m1Bend[axis] =
                parameter.kCurv * curvatureDifference * a1[axis];
            m2Bend[axis] =
                parameter.kCurv * curvatureDifference * a2[axis];
        }
        double n1Area[3];
        double n2Area[3];
        double n1Volume[3];
        double n2Volume[3];
        for (int axis = 0; axis < 3; ++axis)
        {
            n1Area[axis] = areaFactor * a1[axis];
            n2Area[axis] = areaFactor * a2[axis];
            n1Volume[axis] = volumeFactor *
                (dot3(x, a_3) * a1[axis] - dot3(x, a1) * a_3[axis]);
            n2Volume[axis] = volumeFactor *
                (dot3(x, a_3) * a2[axis] - dot3(x, a2) * a_3[axis]);
        }
        if (!finite3(xa_1) || !finite3(xa_2) || !finite3(a_3) ||
            !finite3(a_31) || !finite3(a_32) || !finite3(a1) ||
            !finite3(a2) || !finite3(a11) || !finite3(a12) ||
            !finite3(a21) || !finite3(a22) ||
            !isfinite(meanCurvature) || !isfinite(bendingEnergy) ||
            !finite3(n1Bend) || !finite3(n2Bend) ||
            !finite3(m1Bend) || !finite3(m2Bend) ||
            !finite3(n1Area) || !finite3(n2Area) ||
            !finite3(n1Volume) || !finite3(n2Volume))
        {
            record_membrane_status(diagnostics, 3, evaluated, sample);
            return;
        }

        const double coefficient = quadratureCoefficients[sample];
        const double halfCoefficient = 0.5 * coefficient;
        area += halfCoefficient * sqa;
        volume += kLegacyVolumeQuadratureFactor * coefficient * x[0] * xa[0];
        faceBending += halfCoefficient * bendingEnergy;
        faceMean += halfCoefficient * meanCurvature;
        for (int axis = 0; axis < 3; ++axis)
            accumulatedNormal[axis] += halfCoefficient * a_3[axis];
        const std::uint64_t sampleIndex =
            evaluated * kQuadratureSampleCount + sample;
        sampleSurfaceMeasures[sampleIndex] = sqa;
        sampleMeanCurvatures[sampleIndex] = meanCurvature;
        sampleBendingEnergies[sampleIndex] = bendingEnergy;
        for (int axis = 0; axis < 3; ++axis)
            sampleNormals[sampleIndex * 3U + axis] = a_3[axis];

        for (std::uint32_t local = 0; local < kRegularControlCount; ++local)
        {
            const double sf0 = shapeWeights[
                (sample * kShapeRowCount + 0U) * kRegularControlCount + local];
            const double sf1 = shapeWeights[
                (sample * kShapeRowCount + 1U) * kRegularControlCount + local];
            const double sf2 = shapeWeights[
                (sample * kShapeRowCount + 2U) * kRegularControlCount + local];
            const double sf3 = shapeWeights[
                (sample * kShapeRowCount + 3U) * kRegularControlCount + local];
            const double sf4 = shapeWeights[
                (sample * kShapeRowCount + 4U) * kRegularControlCount + local];
            const double sf5 = shapeWeights[
                (sample * kShapeRowCount + 5U) * kRegularControlCount + local];
            const double sf6 = shapeWeights[
                (sample * kShapeRowCount + 6U) * kRegularControlCount + local];
            double da1[3][3]{};
            add_outer_scaled(da1, a1, a_3, -sf3);
            add_outer_scaled(da1, a11, a_3, -sf1);
            add_outer_scaled(da1, a1, a_31, -sf1);
            add_outer_scaled(da1, a2, a_3, -sf6);
            add_outer_scaled(da1, a21, a_3, -sf2);
            add_outer_scaled(da1, a2, a_31, -sf2);
            double da2[3][3]{};
            add_outer_scaled(da2, a1, a_3, -sf5);
            add_outer_scaled(da2, a12, a_3, -sf1);
            add_outer_scaled(da2, a1, a_32, -sf1);
            add_outer_scaled(da2, a2, a_3, -sf4);
            add_outer_scaled(da2, a22, a_3, -sf2);
            add_outer_scaled(da2, a2, a_32, -sf2);
            double da1M1[3];
            double da2M2[3];
            transpose_multiply3(da1, m1Bend, da1M1);
            transpose_multiply3(da2, m2Bend, da2M2);
            double bending[3];
            double areaForce[3];
            double volumeForce[3];
            for (int axis = 0; axis < 3; ++axis)
            {
                bending[axis] = -sqa * halfCoefficient *
                    (da1M1[axis] + da2M2[axis] +
                     sf1 * n1Bend[axis] + sf2 * n2Bend[axis]);
                areaForce[axis] = -sqa * halfCoefficient *
                    (sf1 * n1Area[axis] + sf2 * n2Area[axis]);
                volumeForce[axis] = -sqa * halfCoefficient *
                    (sf1 * n1Volume[axis] + sf2 * n2Volume[axis] +
                     volumeFactor * sf0 * a_3[axis]);
            }
            if (!finite3(bending) || !finite3(areaForce) ||
                !finite3(volumeForce))
            {
                record_membrane_status(diagnostics, 4, evaluated, sample);
                return;
            }
            const std::uint64_t base =
                (evaluated * kRegularControlCount + local) * 9U;
            for (int axis = 0; axis < 3; ++axis)
            {
                occurrenceForces[base + axis] += bending[axis];
                occurrenceForces[base + 3U + axis] += areaForce[axis];
                occurrenceForces[base + 6U + axis] += volumeForce[axis];
            }
        }
    }
    const double normalNorm = sqrt(dot3(accumulatedNormal, accumulatedNormal));
    if (!(normalNorm > 0.0) || !isfinite(normalNorm))
    {
        record_membrane_status(diagnostics, 2, evaluated,
                               kQuadratureSampleCount);
        return;
    }
    for (int axis = 0; axis < 3; ++axis)
        faceNormals[static_cast<std::uint64_t>(faceId) * 3U + axis] =
            accumulatedNormal[axis] / normalNorm;
    if (!isfinite(area) || area < 0.0 || !isfinite(volume) ||
        !isfinite(faceBending) || !isfinite(faceMean))
    {
        record_membrane_status(diagnostics, 4, evaluated,
                               kQuadratureSampleCount);
        return;
    }
    faceAreas[faceId] = area;
    faceVolumes[faceId] = volume;
    faceBendingEnergies[faceId] = faceBending;
    faceMeanCurvatures[faceId] = faceMean;
}

__global__ void deterministic_membrane_reduction_kernel(
    const double *faceAreas,
    const double *faceVolumes,
    std::int32_t *diagnostics,
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
        record_membrane_status(diagnostics, 4, 0,
                               kQuadratureSampleCount);
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
        ops.computeMembrane = [this](const detail::MembraneLaunch &launch) {
            cudaError_t code = cudaSetDevice(deviceOrdinal_);
            if (code != cudaSuccess)
                return runtime_status(code, "cudaSetDevice(compute_membrane)");
            const std::size_t faceBytes =
                static_cast<std::size_t>(launch.faceCount) * sizeof(double);
            const std::size_t evaluated =
                static_cast<std::size_t>(launch.evaluatedFaceCount);
            const std::size_t occurrenceBytes =
                evaluated * kRegularControlCount * 9U * sizeof(double);
            const std::size_t sampleBytes =
                evaluated * kQuadratureSampleCount * sizeof(double);
            const std::size_t sampleVectorBytes = sampleBytes * 3U;
            const auto clear = [this](detail::DeviceBufferHandle handle,
                                      std::size_t bytes) {
                if (bytes == 0)
                    return cudaSuccess;
                return cudaMemsetAsync(reinterpret_cast<void *>(handle), 0,
                                       bytes, stream_);
            };
            code = clear(launch.faceAreas, faceBytes);
            if (code == cudaSuccess)
                code = clear(launch.faceVolumes, faceBytes);
            if (code == cudaSuccess)
                code = clear(launch.geometryTotals, 2U * sizeof(double));
            if (code == cudaSuccess)
                code = clear(launch.faceBendingEnergies, faceBytes);
            if (code == cudaSuccess)
                code = clear(launch.faceMeanCurvatures, faceBytes);
            if (code == cudaSuccess)
                code = clear(launch.faceNormals, faceBytes * 3U);
            if (code == cudaSuccess)
                code = clear(launch.occurrenceForces, occurrenceBytes);
            if (code == cudaSuccess)
                code = clear(launch.sampleSurfaceMeasures, sampleBytes);
            if (code == cudaSuccess)
                code = clear(launch.sampleMeanCurvatures, sampleBytes);
            if (code == cudaSuccess)
                code = clear(launch.sampleNormals, sampleVectorBytes);
            if (code == cudaSuccess)
                code = clear(launch.sampleBendingEnergies, sampleBytes);
            if (code == cudaSuccess)
                code = clear(launch.statusDiagnostics,
                             3U * sizeof(std::int32_t));
            if (code != cudaSuccess)
                return runtime_status(code, "cudaMemsetAsync(membrane)");
            constexpr unsigned int threads = 128;
            const unsigned int blocks = static_cast<unsigned int>(
                (launch.evaluatedFaceCount + threads - 1) / threads);
            if (blocks != 0)
            {
                regular_membrane_kernel<<<blocks, threads, 0, stream_>>>(
                    reinterpret_cast<const std::int32_t *>(
                        launch.evaluatedFaceIds),
                    reinterpret_cast<const std::int32_t *>(
                        launch.oneRingSourceIds),
                    reinterpret_cast<const double *>(
                        launch.spontaneousCurvatures),
                    reinterpret_cast<const PackedRegularParameters *>(
                        launch.packedParameters),
                    reinterpret_cast<const double *>(
                        launch.quadratureCoefficients),
                    reinterpret_cast<const double *>(launch.shapeWeights),
                    reinterpret_cast<const double *>(launch.coordinates),
                    reinterpret_cast<double *>(launch.faceAreas),
                    reinterpret_cast<double *>(launch.faceVolumes),
                    reinterpret_cast<double *>(launch.faceBendingEnergies),
                    reinterpret_cast<double *>(launch.faceMeanCurvatures),
                    reinterpret_cast<double *>(launch.faceNormals),
                    reinterpret_cast<double *>(launch.occurrenceForces),
                    reinterpret_cast<double *>(launch.sampleSurfaceMeasures),
                    reinterpret_cast<double *>(launch.sampleMeanCurvatures),
                    reinterpret_cast<double *>(launch.sampleNormals),
                    reinterpret_cast<double *>(launch.sampleBendingEnergies),
                    reinterpret_cast<std::int32_t *>(
                        launch.statusDiagnostics),
                    launch.vertexCount, launch.faceCount,
                    launch.evaluatedFaceCount);
                code = cudaGetLastError();
                if (code != cudaSuccess)
                    return runtime_status(code, "regular_membrane_kernel");
            }
            deterministic_membrane_reduction_kernel<<<1, 1, 0, stream_>>>(
                reinterpret_cast<const double *>(launch.faceAreas),
                reinterpret_cast<const double *>(launch.faceVolumes),
                reinterpret_cast<std::int32_t *>(launch.statusDiagnostics),
                reinterpret_cast<double *>(launch.geometryTotals),
                launch.faceCount);
            return runtime_status(cudaGetLastError(),
                                  "deterministic_membrane_reduction_kernel");
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
