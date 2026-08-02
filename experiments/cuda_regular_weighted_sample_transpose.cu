#include <cuda_runtime.h>

#include "mesh/Gauss_quadrature.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
constexpr int kSamples = 3;
constexpr int kRows = 7;
constexpr int kControls = 12;
constexpr int kAxes = 3;
constexpr int kDeterminismRepetitions = 20;
constexpr double kAbsoluteTolerance = 1.0e-12;
constexpr long double kAdjointTolerance = 1.0e-12L;
constexpr int kNoCudaDeviceExitCode = 77;
constexpr int kPermutation[kControls] = {5, 0, 11, 3, 8, 1, 10, 6, 2, 9, 4, 7};

__host__ __device__ std::size_t weight_index(
    const int sample, const int row, const int control)
{
    return (static_cast<std::size_t>(sample) * kRows + row) * kControls + control;
}

__host__ __device__ std::size_t control_index(
    const std::size_t batch, const int control, const int axis)
{
    return (batch * kControls + control) * kAxes + axis;
}

__host__ __device__ std::size_t row_index(
    const std::size_t batch,
    const int sample,
    const int row,
    const int axis)
{
    return ((batch * kSamples + sample) * kRows + row) * kAxes + axis;
}

std::string json_escape(const std::string &value)
{
    std::string escaped;
    escaped.reserve(value.size());
    for (const char character : value)
    {
        switch (character)
        {
        case '\\':
            escaped += "\\\\";
            break;
        case '"':
            escaped += "\\\"";
            break;
        case '\n':
            escaped += "\\n";
            break;
        case '\r':
            escaped += "\\r";
            break;
        case '\t':
            escaped += "\\t";
            break;
        default:
            escaped += character;
        }
    }
    return escaped;
}

void cuda_check(const cudaError_t error, const char *operation)
{
    if (error != cudaSuccess)
        throw std::runtime_error(
            std::string(operation) + ": " + cudaGetErrorString(error));
}

class DeviceDoubles
{
public:
    explicit DeviceDoubles(const std::size_t count) : pointer_(nullptr)
    {
        cuda_check(
            cudaMalloc(reinterpret_cast<void **>(&pointer_), count * sizeof(double)),
            "cudaMalloc");
    }

    DeviceDoubles(const DeviceDoubles &) = delete;
    DeviceDoubles &operator=(const DeviceDoubles &) = delete;

    ~DeviceDoubles()
    {
        if (pointer_ != nullptr)
            cudaFree(pointer_);
    }

    double *get() const
    {
        return pointer_;
    }

private:
    double *pointer_;
};

struct Comparison
{
    double maximumAbsoluteDelta = 0.0;
    double maximumRelativeDelta = 0.0;
};

struct AdjointCheck
{
    long double left = 0.0L;
    long double right = 0.0L;
    long double residual = 0.0L;
};

struct CudaOutputs
{
    std::vector<double> forward;
    std::vector<double> transpose;
    bool bitwiseDeterministic = true;
};

std::vector<double> production_regular_weights()
{
    Matrix vwu;
    Matrix quadratureWeights;
    get_gauss_quadrature_weight_VWU(2, vwu, quadratureWeights);
    if (vwu.nrow() != kSamples || vwu.ncol() != 3 ||
        quadratureWeights.nrow() != kSamples)
        throw std::runtime_error("production quadrature shape drifted");

    std::vector<Matrix> shapeFunctions;
    get_shapefunction_vector(vwu, shapeFunctions);
    if (shapeFunctions.size() != kSamples)
        throw std::runtime_error("production shape-function sample count drifted");

    std::vector<double> weights(kSamples * kRows * kControls);
    for (int sample = 0; sample < kSamples; ++sample)
    {
        if (shapeFunctions[sample].nrow() != kRows ||
            shapeFunctions[sample].ncol() != kControls)
            throw std::runtime_error("production shape-function dimensions drifted");
        for (int row = 0; row < kRows; ++row)
            for (int control = 0; control < kControls; ++control)
                weights[weight_index(sample, row, control)] =
                    shapeFunctions[sample].get(row, control);
    }
    return weights;
}

std::vector<double> deterministic_controls(const std::size_t batchSize)
{
    std::vector<double> controls(batchSize * kControls * kAxes);
    for (std::size_t batch = 0; batch < batchSize; ++batch)
        for (int control = 0; control < kControls; ++control)
            for (int axis = 0; axis < kAxes; ++axis)
            {
                const long long raw = static_cast<long long>(
                    ((batch + 1) * 17 + (control + 3) * 29 + (axis + 5) * 11) %
                    257);
                controls[control_index(batch, control, axis)] =
                    static_cast<double>(raw - 128) / 16.0;
            }
    return controls;
}

std::vector<double> deterministic_row_gradients(const std::size_t batchSize)
{
    std::vector<double> gradients(batchSize * kSamples * kRows * kAxes);
    for (std::size_t batch = 0; batch < batchSize; ++batch)
        for (int sample = 0; sample < kSamples; ++sample)
            for (int row = 0; row < kRows; ++row)
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    const long long raw = static_cast<long long>(
                        ((batch + 7) * 23 + (sample + 2) * 31 +
                         (row + 4) * 19 + (axis + 1) * 13) %
                        263);
                    gradients[row_index(batch, sample, row, axis)] =
                        static_cast<double>(raw - 131) / 32.0;
                }
    return gradients;
}

std::vector<double> permute_weights(const std::vector<double> &weights)
{
    std::vector<double> permuted(weights.size());
    for (int sample = 0; sample < kSamples; ++sample)
        for (int row = 0; row < kRows; ++row)
            for (int control = 0; control < kControls; ++control)
                permuted[weight_index(sample, row, control)] =
                    weights[weight_index(sample, row, kPermutation[control])];
    return permuted;
}

std::vector<double> permute_controls(
    const std::vector<double> &controls, const std::size_t batchSize)
{
    std::vector<double> permuted(controls.size());
    for (std::size_t batch = 0; batch < batchSize; ++batch)
        for (int control = 0; control < kControls; ++control)
            for (int axis = 0; axis < kAxes; ++axis)
                permuted[control_index(batch, control, axis)] =
                    controls[control_index(batch, kPermutation[control], axis)];
    return permuted;
}

std::vector<double> cpu_forward(
    const std::vector<double> &weights,
    const std::vector<double> &controls,
    const std::size_t batchSize)
{
    std::vector<double> output(batchSize * kSamples * kRows * kAxes, 0.0);
    for (std::size_t batch = 0; batch < batchSize; ++batch)
        for (int sample = 0; sample < kSamples; ++sample)
            for (int row = 0; row < kRows; ++row)
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    double sum = 0.0;
                    for (int control = 0; control < kControls; ++control)
                        sum += weights[weight_index(sample, row, control)] *
                               controls[control_index(batch, control, axis)];
                    output[row_index(batch, sample, row, axis)] = sum;
                }
    return output;
}

std::vector<double> cpu_transpose(
    const std::vector<double> &weights,
    const std::vector<double> &rowGradients,
    const std::size_t batchSize)
{
    std::vector<double> output(batchSize * kControls * kAxes, 0.0);
    for (std::size_t batch = 0; batch < batchSize; ++batch)
        for (int control = 0; control < kControls; ++control)
            for (int axis = 0; axis < kAxes; ++axis)
            {
                double sum = 0.0;
                for (int sample = 0; sample < kSamples; ++sample)
                    for (int row = 0; row < kRows; ++row)
                        sum += weights[weight_index(sample, row, control)] *
                               rowGradients[row_index(batch, sample, row, axis)];
                output[control_index(batch, control, axis)] = sum;
            }
    return output;
}

__global__ void forward_weighted_samples(
    const double *weights,
    const double *controls,
    double *output,
    const std::size_t outputCount)
{
    const std::size_t outputIndex =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (outputIndex >= outputCount)
        return;

    std::size_t remainder = outputIndex;
    const int axis = static_cast<int>(remainder % kAxes);
    remainder /= kAxes;
    const int row = static_cast<int>(remainder % kRows);
    remainder /= kRows;
    const int sample = static_cast<int>(remainder % kSamples);
    const std::size_t batch = remainder / kSamples;

    double sum = 0.0;
    for (int control = 0; control < kControls; ++control)
        sum += weights[weight_index(sample, row, control)] *
               controls[control_index(batch, control, axis)];
    output[outputIndex] = sum;
}

__global__ void transpose_weighted_samples(
    const double *weights,
    const double *rowGradients,
    double *output,
    const std::size_t outputCount)
{
    const std::size_t outputIndex =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (outputIndex >= outputCount)
        return;

    std::size_t remainder = outputIndex;
    const int axis = static_cast<int>(remainder % kAxes);
    remainder /= kAxes;
    const int control = static_cast<int>(remainder % kControls);
    const std::size_t batch = remainder / kControls;

    double sum = 0.0;
    for (int sample = 0; sample < kSamples; ++sample)
        for (int row = 0; row < kRows; ++row)
            sum += weights[weight_index(sample, row, control)] *
                   rowGradients[row_index(batch, sample, row, axis)];
    output[outputIndex] = sum;
}

bool all_finite(const std::vector<double> &values)
{
    return std::all_of(values.begin(), values.end(), [](const double value) {
        return std::isfinite(value);
    });
}

Comparison compare_vectors(
    const std::vector<double> &candidate,
    const std::vector<double> &reference)
{
    if (candidate.size() != reference.size())
        throw std::invalid_argument("comparison cardinality mismatch");
    Comparison comparison;
    for (std::size_t index = 0; index < candidate.size(); ++index)
    {
        const double absoluteDelta = std::abs(candidate[index] - reference[index]);
        const double relativeDelta =
            absoluteDelta / std::max(1.0, std::abs(reference[index]));
        comparison.maximumAbsoluteDelta =
            std::max(comparison.maximumAbsoluteDelta, absoluteDelta);
        comparison.maximumRelativeDelta =
            std::max(comparison.maximumRelativeDelta, relativeDelta);
    }
    return comparison;
}

AdjointCheck adjoint_check(
    const std::vector<double> &rowGradients,
    const std::vector<double> &forward,
    const std::vector<double> &controls,
    const std::vector<double> &transpose)
{
    if (rowGradients.size() != forward.size() ||
        controls.size() != transpose.size())
        throw std::invalid_argument("adjoint cardinality mismatch");
    AdjointCheck result;
    for (std::size_t index = 0; index < forward.size(); ++index)
        result.left += static_cast<long double>(rowGradients[index]) *
                       static_cast<long double>(forward[index]);
    for (std::size_t index = 0; index < transpose.size(); ++index)
        result.right += static_cast<long double>(transpose[index]) *
                        static_cast<long double>(controls[index]);
    const long double scale =
        std::max({1.0L, std::abs(result.left), std::abs(result.right)});
    result.residual = std::abs(result.left - result.right) / scale;
    return result;
}

Comparison compare_permuted_transpose(
    const std::vector<double> &permuted,
    const std::vector<double> &natural,
    const std::size_t batchSize)
{
    std::vector<double> expected(permuted.size());
    for (std::size_t batch = 0; batch < batchSize; ++batch)
        for (int control = 0; control < kControls; ++control)
            for (int axis = 0; axis < kAxes; ++axis)
                expected[control_index(batch, control, axis)] =
                    natural[control_index(batch, kPermutation[control], axis)];
    return compare_vectors(permuted, expected);
}

unsigned int block_count(const std::size_t outputCount)
{
    constexpr std::size_t blockSize = 256;
    const std::size_t count = (outputCount + blockSize - 1) / blockSize;
    if (count > std::numeric_limits<unsigned int>::max())
        throw std::invalid_argument("batch size exceeds one-dimensional grid limit");
    return static_cast<unsigned int>(count);
}

CudaOutputs run_cuda_case(
    const std::vector<double> &weights,
    const std::vector<double> &controls,
    const std::vector<double> &rowGradients,
    const std::size_t batchSize)
{
    CudaOutputs result{
        std::vector<double>(batchSize * kSamples * kRows * kAxes),
        std::vector<double>(batchSize * kControls * kAxes),
        true};
    DeviceDoubles deviceWeights(weights.size());
    DeviceDoubles deviceControls(controls.size());
    DeviceDoubles deviceRowGradients(rowGradients.size());
    DeviceDoubles deviceForward(result.forward.size());
    DeviceDoubles deviceTranspose(result.transpose.size());
    cuda_check(
        cudaMemcpy(deviceWeights.get(), weights.data(), weights.size() * sizeof(double),
                   cudaMemcpyHostToDevice),
        "cudaMemcpy weights host-to-device");
    cuda_check(
        cudaMemcpy(deviceControls.get(), controls.data(), controls.size() * sizeof(double),
                   cudaMemcpyHostToDevice),
        "cudaMemcpy controls host-to-device");
    cuda_check(
        cudaMemcpy(deviceRowGradients.get(), rowGradients.data(),
                   rowGradients.size() * sizeof(double), cudaMemcpyHostToDevice),
        "cudaMemcpy row gradients host-to-device");

    std::vector<double> firstForward(result.forward.size());
    std::vector<double> firstTranspose(result.transpose.size());
    constexpr int blockSize = 256;
    for (int repetition = 0; repetition < kDeterminismRepetitions; ++repetition)
    {
        forward_weighted_samples<<<block_count(result.forward.size()), blockSize>>>(
            deviceWeights.get(), deviceControls.get(), deviceForward.get(),
            result.forward.size());
        cuda_check(cudaGetLastError(), "forward_weighted_samples launch");
        transpose_weighted_samples<<<block_count(result.transpose.size()), blockSize>>>(
            deviceWeights.get(), deviceRowGradients.get(), deviceTranspose.get(),
            result.transpose.size());
        cuda_check(cudaGetLastError(), "transpose_weighted_samples launch");
        cuda_check(
            cudaMemcpy(result.forward.data(), deviceForward.get(),
                       result.forward.size() * sizeof(double), cudaMemcpyDeviceToHost),
            "cudaMemcpy forward output device-to-host");
        cuda_check(
            cudaMemcpy(result.transpose.data(), deviceTranspose.get(),
                       result.transpose.size() * sizeof(double), cudaMemcpyDeviceToHost),
            "cudaMemcpy transpose output device-to-host");
        if (repetition == 0)
        {
            firstForward = result.forward;
            firstTranspose = result.transpose;
        }
        else if (std::memcmp(result.forward.data(), firstForward.data(),
                             result.forward.size() * sizeof(double)) != 0 ||
                 std::memcmp(result.transpose.data(), firstTranspose.data(),
                             result.transpose.size() * sizeof(double)) != 0)
        {
            result.bitwiseDeterministic = false;
        }
    }
    result.forward = std::move(firstForward);
    result.transpose = std::move(firstTranspose);
    return result;
}

void validate_index_sentinel()
{
    std::vector<double> weights(kSamples * kRows * kControls, 0.0);
    std::vector<double> controls(kControls * kAxes, 0.0);
    std::vector<double> rowGradients(kSamples * kRows * kAxes, 0.0);

    // Literal terminal offsets independently exercise the flattened contracts:
    // weight[2,6,11], control[0,11,2], and row[0,2,6,2].
    weights[251] = 2.0;
    controls[35] = 3.0;
    rowGradients[62] = 5.0;
    const std::vector<double> cpuForward = cpu_forward(weights, controls, 1);
    const std::vector<double> cpuTranspose =
        cpu_transpose(weights, rowGradients, 1);
    const CudaOutputs cuda = run_cuda_case(weights, controls, rowGradients, 1);

    for (std::size_t index = 0; index < cpuForward.size(); ++index)
    {
        const double expected = index == 62 ? 6.0 : 0.0;
        if (cpuForward[index] != expected || cuda.forward[index] != expected)
            throw std::runtime_error("forward flattened-index sentinel failed");
    }
    for (std::size_t index = 0; index < cpuTranspose.size(); ++index)
    {
        const double expected = index == 35 ? 10.0 : 0.0;
        if (cpuTranspose[index] != expected || cuda.transpose[index] != expected)
            throw std::runtime_error("transpose flattened-index sentinel failed");
    }
    if (!cuda.bitwiseDeterministic)
        throw std::runtime_error("index sentinel CUDA repetitions were not deterministic");
}

std::size_t parse_batch_size(const char *value)
{
    const std::string text(value);
    std::size_t consumed = 0;
    const unsigned long long parsed = std::stoull(text, &consumed);
    if (consumed != text.size() || parsed == 0)
        throw std::invalid_argument("batch size must be a positive integer");
    const std::size_t maximum =
        std::numeric_limits<std::size_t>::max() /
        static_cast<std::size_t>(kSamples * kRows * kAxes);
    if (parsed > maximum)
        throw std::invalid_argument("batch size overflows output cardinality");
    return static_cast<std::size_t>(parsed);
}
} // namespace

int main(int argc, char **argv)
{
    try
    {
        if (argc != 4)
            throw std::invalid_argument(
                "usage: cuda_regular_weighted_sample_transpose "
                "BATCH_SIZE COMPUTE_ARCH SM_CODE");
        const std::size_t batchSize = parse_batch_size(argv[1]);
        const std::string computeArchitecture(argv[2]);
        const std::string smCode(argv[3]);

        int deviceCount = 0;
        const cudaError_t countError = cudaGetDeviceCount(&deviceCount);
        if (countError == cudaErrorNoDevice ||
            countError == cudaErrorInsufficientDriver || deviceCount == 0)
        {
            std::cout << "{\"status\":\"skipped\","
                      << "\"reason\":\"no usable CUDA device: "
                      << json_escape(cudaGetErrorString(countError)) << "\"}\n";
            return kNoCudaDeviceExitCode;
        }
        cuda_check(countError, "cudaGetDeviceCount");

        cudaDeviceProp deviceProperties{};
        cuda_check(cudaGetDeviceProperties(&deviceProperties, 0),
                   "cudaGetDeviceProperties");
        int driverVersion = 0;
        int runtimeVersion = 0;
        cuda_check(cudaDriverGetVersion(&driverVersion), "cudaDriverGetVersion");
        cuda_check(cudaRuntimeGetVersion(&runtimeVersion), "cudaRuntimeGetVersion");

        validate_index_sentinel();

        const std::vector<double> naturalWeights = production_regular_weights();
        const std::vector<double> naturalControls = deterministic_controls(batchSize);
        const std::vector<double> rowGradients =
            deterministic_row_gradients(batchSize);
        const std::vector<double> permutedWeights =
            permute_weights(naturalWeights);
        const std::vector<double> permutedControls =
            permute_controls(naturalControls, batchSize);

        const std::vector<double> naturalCpuForward =
            cpu_forward(naturalWeights, naturalControls, batchSize);
        const std::vector<double> naturalCpuTranspose =
            cpu_transpose(naturalWeights, rowGradients, batchSize);
        const std::vector<double> permutedCpuForward =
            cpu_forward(permutedWeights, permutedControls, batchSize);
        const std::vector<double> permutedCpuTranspose =
            cpu_transpose(permutedWeights, rowGradients, batchSize);
        if (!all_finite(naturalWeights) || !all_finite(naturalControls) ||
            !all_finite(rowGradients) || !all_finite(permutedWeights) ||
            !all_finite(permutedControls) || !all_finite(naturalCpuForward) ||
            !all_finite(naturalCpuTranspose) || !all_finite(permutedCpuForward) ||
            !all_finite(permutedCpuTranspose))
            throw std::runtime_error("CPU fixture/reference contains nonfinite values");

        const CudaOutputs naturalCuda = run_cuda_case(
            naturalWeights, naturalControls, rowGradients, batchSize);
        const CudaOutputs permutedCuda = run_cuda_case(
            permutedWeights, permutedControls, rowGradients, batchSize);
        if (!all_finite(naturalCuda.forward) ||
            !all_finite(naturalCuda.transpose) ||
            !all_finite(permutedCuda.forward) ||
            !all_finite(permutedCuda.transpose))
            throw std::runtime_error("CUDA output contains nonfinite values");

        const Comparison naturalForward =
            compare_vectors(naturalCuda.forward, naturalCpuForward);
        const Comparison naturalTranspose =
            compare_vectors(naturalCuda.transpose, naturalCpuTranspose);
        const Comparison permutedForward =
            compare_vectors(permutedCuda.forward, permutedCpuForward);
        const Comparison permutedTranspose =
            compare_vectors(permutedCuda.transpose, permutedCpuTranspose);
        const Comparison cpuForwardPermutation =
            compare_vectors(permutedCpuForward, naturalCpuForward);
        const Comparison cudaForwardPermutation =
            compare_vectors(permutedCuda.forward, naturalCuda.forward);
        const Comparison cpuTransposePermutation = compare_permuted_transpose(
            permutedCpuTranspose, naturalCpuTranspose, batchSize);
        const Comparison cudaTransposePermutation = compare_permuted_transpose(
            permutedCuda.transpose, naturalCuda.transpose, batchSize);

        const AdjointCheck naturalCpuAdjoint = adjoint_check(
            rowGradients, naturalCpuForward, naturalControls, naturalCpuTranspose);
        const AdjointCheck naturalCudaAdjoint = adjoint_check(
            rowGradients, naturalCuda.forward, naturalControls,
            naturalCuda.transpose);
        const AdjointCheck permutedCpuAdjoint = adjoint_check(
            rowGradients, permutedCpuForward, permutedControls,
            permutedCpuTranspose);
        const AdjointCheck permutedCudaAdjoint = adjoint_check(
            rowGradients, permutedCuda.forward, permutedControls,
            permutedCuda.transpose);

        const double maximumForwardDelta = std::max(
            naturalForward.maximumAbsoluteDelta,
            permutedForward.maximumAbsoluteDelta);
        const double maximumTransposeDelta = std::max(
            naturalTranspose.maximumAbsoluteDelta,
            permutedTranspose.maximumAbsoluteDelta);
        const double maximumForwardRelativeDelta = std::max(
            naturalForward.maximumRelativeDelta,
            permutedForward.maximumRelativeDelta);
        const double maximumTransposeRelativeDelta = std::max(
            naturalTranspose.maximumRelativeDelta,
            permutedTranspose.maximumRelativeDelta);
        const long double maximumCpuAdjointResidual = std::max(
            naturalCpuAdjoint.residual, permutedCpuAdjoint.residual);
        const long double maximumCudaAdjointResidual = std::max(
            naturalCudaAdjoint.residual, permutedCudaAdjoint.residual);

        const bool passed =
            maximumForwardDelta <= kAbsoluteTolerance &&
            maximumTransposeDelta <= kAbsoluteTolerance &&
            cpuForwardPermutation.maximumAbsoluteDelta <= kAbsoluteTolerance &&
            cudaForwardPermutation.maximumAbsoluteDelta <= kAbsoluteTolerance &&
            cpuTransposePermutation.maximumAbsoluteDelta <= kAbsoluteTolerance &&
            cudaTransposePermutation.maximumAbsoluteDelta <= kAbsoluteTolerance &&
            maximumCpuAdjointResidual <= kAdjointTolerance &&
            maximumCudaAdjointResidual <= kAdjointTolerance &&
            naturalCuda.bitwiseDeterministic &&
            permutedCuda.bitwiseDeterministic;

        std::cout << std::setprecision(17)
                  << "{\"status\":\"" << (passed ? "passed" : "failed")
                  << "\",\"proof\":\"regular_weighted_sample_transpose\""
                  << ",\"fixture\":\"production get_shapefunction_vector N=2\""
                  << ",\"cpu_forward_order\":\"batch,sample,row,axis,control\""
                  << ",\"cpu_transpose_order\":\"batch,control,axis,sample,row\""
                  << ",\"random_seed\":\"deterministic_formula_no_rng\""
                  << ",\"batch_size\":" << batchSize
                  << ",\"samples\":" << kSamples
                  << ",\"rows\":" << kRows
                  << ",\"controls\":" << kControls
                  << ",\"axes\":" << kAxes
                  << ",\"all_finite\":true"
                  << ",\"index_sentinel\":\"passed\""
                  << ",\"absolute_tolerance\":" << kAbsoluteTolerance
                  << ",\"adjoint_tolerance\":"
                  << static_cast<double>(kAdjointTolerance)
                  << ",\"adjoint_accumulator\":\"long double\""
                  << ",\"max_forward_absolute_delta\":" << maximumForwardDelta
                  << ",\"max_forward_relative_delta_diagnostic\":"
                  << maximumForwardRelativeDelta
                  << ",\"max_transpose_absolute_delta\":"
                  << maximumTransposeDelta
                  << ",\"max_transpose_relative_delta_diagnostic\":"
                  << maximumTransposeRelativeDelta
                  << ",\"max_cpu_adjoint_residual\":"
                  << static_cast<double>(maximumCpuAdjointResidual)
                  << ",\"max_cuda_adjoint_residual\":"
                  << static_cast<double>(maximumCudaAdjointResidual)
                  << ",\"cpu_forward_permutation_delta\":"
                  << cpuForwardPermutation.maximumAbsoluteDelta
                  << ",\"cuda_forward_permutation_delta\":"
                  << cudaForwardPermutation.maximumAbsoluteDelta
                  << ",\"cpu_transpose_permutation_delta\":"
                  << cpuTransposePermutation.maximumAbsoluteDelta
                  << ",\"cuda_transpose_permutation_delta\":"
                  << cudaTransposePermutation.maximumAbsoluteDelta
                  << ",\"determinism_repetitions\":"
                  << kDeterminismRepetitions
                  << ",\"natural_bitwise_deterministic\":"
                  << (naturalCuda.bitwiseDeterministic ? "true" : "false")
                  << ",\"permuted_bitwise_deterministic\":"
                  << (permutedCuda.bitwiseDeterministic ? "true" : "false")
                  << ",\"control_permutation\":[";
        for (int control = 0; control < kControls; ++control)
        {
            if (control != 0)
                std::cout << ',';
            std::cout << kPermutation[control];
        }
        std::cout << "]"
                  << ",\"duplicate_source_id_aggregation\":"
                     "\"host_mapping_contract_not_in_device_kernel\""
                  << ",\"floating_point_atomics\":false"
                  << ",\"device\":\"" << json_escape(deviceProperties.name)
                  << "\",\"compute_capability\":\""
                  << deviceProperties.major << '.' << deviceProperties.minor << "\""
                  << ",\"global_memory_bytes\":"
                  << deviceProperties.totalGlobalMem
                  << ",\"driver_api_version\":" << driverVersion
                  << ",\"runtime_api_version\":" << runtimeVersion
                  << ",\"compile_compute_arch\":\""
                  << json_escape(computeArchitecture) << "\""
                  << ",\"compile_sm_code\":\"" << json_escape(smCode)
                  << "\"}\n";
        return passed ? 0 : 2;
    }
    catch (const std::exception &error)
    {
        std::cerr << "CUDA transpose proof failed: " << error.what() << '\n';
        return 1;
    }
}
