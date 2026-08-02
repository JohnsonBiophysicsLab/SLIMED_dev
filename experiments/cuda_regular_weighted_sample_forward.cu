#include <cuda_runtime.h>

#include "mesh/Gauss_quadrature.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
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
constexpr double kAbsoluteTolerance = 1.0e-12;
constexpr int kNoCudaDeviceExitCode = 77;

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

__host__ __device__ std::size_t output_index(
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

std::vector<double> cpu_reference(
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
                    output[output_index(batch, sample, row, axis)] = sum;
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

bool all_finite(const std::vector<double> &values)
{
    return std::all_of(values.begin(), values.end(), [](const double value) {
        return std::isfinite(value);
    });
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
                "usage: cuda_regular_weighted_sample_forward "
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

        const std::vector<double> weights = production_regular_weights();
        const std::vector<double> controls = deterministic_controls(batchSize);
        const std::vector<double> reference =
            cpu_reference(weights, controls, batchSize);
        if (!all_finite(weights) || !all_finite(controls) ||
            !all_finite(reference))
            throw std::runtime_error("CPU fixture/reference contains nonfinite values");

        std::vector<double> candidate(reference.size(), 0.0);
        DeviceDoubles deviceWeights(weights.size());
        DeviceDoubles deviceControls(controls.size());
        DeviceDoubles deviceOutput(candidate.size());
        cuda_check(
            cudaMemcpy(deviceWeights.get(), weights.data(),
                       weights.size() * sizeof(double), cudaMemcpyHostToDevice),
            "cudaMemcpy weights host-to-device");
        cuda_check(
            cudaMemcpy(deviceControls.get(), controls.data(),
                       controls.size() * sizeof(double), cudaMemcpyHostToDevice),
            "cudaMemcpy controls host-to-device");

        constexpr int blockSize = 256;
        const std::size_t blockCount =
            (candidate.size() + blockSize - 1) / blockSize;
        if (blockCount > static_cast<std::size_t>(
                             std::numeric_limits<unsigned int>::max()))
            throw std::invalid_argument("batch size exceeds one-dimensional grid limit");
        forward_weighted_samples<<<static_cast<unsigned int>(blockCount), blockSize>>>(
            deviceWeights.get(), deviceControls.get(), deviceOutput.get(),
            candidate.size());
        cuda_check(cudaGetLastError(), "forward_weighted_samples launch");
        cuda_check(
            cudaMemcpy(candidate.data(), deviceOutput.get(),
                       candidate.size() * sizeof(double), cudaMemcpyDeviceToHost),
            "cudaMemcpy output device-to-host");
        if (!all_finite(candidate))
            throw std::runtime_error("CUDA output contains nonfinite values");

        double maximumAbsoluteDelta = 0.0;
        double maximumRelativeDelta = 0.0;
        std::size_t maximumDeltaIndex = 0;
        for (std::size_t index = 0; index < candidate.size(); ++index)
        {
            const double absoluteDelta =
                std::abs(candidate[index] - reference[index]);
            const double relativeDelta =
                absoluteDelta / std::max(1.0, std::abs(reference[index]));
            if (absoluteDelta > maximumAbsoluteDelta)
            {
                maximumAbsoluteDelta = absoluteDelta;
                maximumDeltaIndex = index;
            }
            maximumRelativeDelta = std::max(maximumRelativeDelta, relativeDelta);
        }
        const bool passed = maximumAbsoluteDelta <= kAbsoluteTolerance;

        std::cout << std::setprecision(17)
                  << "{\"status\":\"" << (passed ? "passed" : "failed")
                  << "\",\"proof\":\"regular_weighted_sample_forward\""
                  << ",\"fixture\":\"production get_shapefunction_vector N=2\""
                  << ",\"cpu_reference_order\":\"batch,sample,row,axis,control\""
                  << ",\"random_seed\":\"deterministic_formula_no_rng\""
                  << ",\"batch_size\":" << batchSize
                  << ",\"samples\":" << kSamples
                  << ",\"rows\":" << kRows
                  << ",\"controls\":" << kControls
                  << ",\"axes\":" << kAxes
                  << ",\"output_components\":" << candidate.size()
                  << ",\"all_finite\":true"
                  << ",\"absolute_tolerance\":" << kAbsoluteTolerance
                  << ",\"max_absolute_delta\":" << maximumAbsoluteDelta
                  << ",\"max_relative_delta_diagnostic\":"
                  << maximumRelativeDelta
                  << ",\"max_delta_index\":" << maximumDeltaIndex
                  << ",\"device\":\"" << json_escape(deviceProperties.name) << "\""
                  << ",\"compute_capability\":\"" << deviceProperties.major << '.'
                  << deviceProperties.minor << "\""
                  << ",\"global_memory_bytes\":"
                  << deviceProperties.totalGlobalMem
                  << ",\"driver_api_version\":" << driverVersion
                  << ",\"runtime_api_version\":" << runtimeVersion
                  << ",\"compile_compute_arch\":\""
                  << json_escape(computeArchitecture) << "\""
                  << ",\"compile_sm_code\":\"" << json_escape(smCode) << "\""
                  << ",\"floating_point_atomics\":false}\n";
        return passed ? 0 : 2;
    }
    catch (const std::exception &error)
    {
        std::cerr << "CUDA forward proof failed: " << error.what() << '\n';
        return 1;
    }
}
