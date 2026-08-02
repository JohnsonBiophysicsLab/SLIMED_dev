#include <cuda_runtime.h>
#include <omp.h>

#include "mesh/Gauss_quadrature.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
constexpr int kSamples = 3;
constexpr int kRows = 7;
constexpr int kControls = 12;
constexpr int kAxes = 3;
constexpr int kBlockSize = 256;
constexpr double kAbsoluteTolerance = 1.0e-12;
constexpr int kNoCudaDeviceExitCode = 77;
constexpr std::size_t kRowComponentsPerBatch = kSamples * kRows * kAxes;
constexpr std::size_t kControlComponentsPerBatch = kControls * kAxes;
constexpr std::size_t kDeviceBytesPerBatch =
    (kControlComponentsPerBatch + kRowComponentsPerBatch +
     kRowComponentsPerBatch + kControlComponentsPerBatch) *
    sizeof(double);

using Clock = std::chrono::steady_clock;

std::size_t checked_multiply(
    const std::size_t left,
    const std::size_t right,
    const char *label)
{
    if (right != 0 && left > std::numeric_limits<std::size_t>::max() / right)
        throw std::invalid_argument(std::string(label) + " multiplication overflows");
    return left * right;
}

std::size_t checked_add(
    const std::size_t left,
    const std::size_t right,
    const char *label)
{
    if (left > std::numeric_limits<std::size_t>::max() - right)
        throw std::invalid_argument(std::string(label) + " addition overflows");
    return left + right;
}

std::size_t checked_double_count(
    const std::size_t batchSize,
    const std::size_t componentsPerBatch,
    const char *label)
{
    const std::size_t count =
        checked_multiply(batchSize, componentsPerBatch, label);
    checked_multiply(count, sizeof(double), label);
    return count;
}

std::size_t checked_device_bytes(
    const std::size_t batchSize, const std::size_t weightBytes)
{
    const std::size_t dynamicBytes =
        checked_multiply(batchSize, kDeviceBytesPerBatch, "device bytes");
    return checked_add(weightBytes, dynamicBytes, "device bytes");
}

void validate_batch_cardinality(const std::size_t batchSize)
{
    if (batchSize == 0)
        throw std::invalid_argument("batch size must be positive");
    if (batchSize > static_cast<std::size_t>(
                        std::numeric_limits<long long>::max()))
        throw std::invalid_argument("batch size exceeds OpenMP loop range");
    checked_double_count(
        batchSize, kRowComponentsPerBatch, "row-buffer cardinality");
    checked_double_count(
        batchSize, kControlComponentsPerBatch, "control-buffer cardinality");
    checked_device_bytes(batchSize, kSamples * kRows * kControls * sizeof(double));
}

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

class CudaEvent
{
public:
    CudaEvent()
    {
        cuda_check(cudaEventCreate(&event_), "cudaEventCreate");
    }

    CudaEvent(const CudaEvent &) = delete;
    CudaEvent &operator=(const CudaEvent &) = delete;

    ~CudaEvent()
    {
        cudaEventDestroy(event_);
    }

    cudaEvent_t get() const
    {
        return event_;
    }

private:
    cudaEvent_t event_{};
};

struct Distribution
{
    double medianMilliseconds = 0.0;
    double p95Milliseconds = 0.0;
};

struct BenchmarkCase
{
    std::size_t batchSize = 0;
    std::size_t deviceBytes = 0;
    double correctnessForwardMaximum = 0.0;
    double correctnessTransposeMaximum = 0.0;
    Distribution serialCpu;
    Distribution openmpCpu;
    Distribution cudaKernel;
    Distribution hostToDevice;
    Distribution deviceToHost;
    Distribution cudaEndToEnd;
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
    std::vector<double> controls(checked_double_count(
        batchSize, kControlComponentsPerBatch, "control fixture cardinality"));
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
    std::vector<double> gradients(checked_double_count(
        batchSize, kRowComponentsPerBatch, "row-gradient fixture cardinality"));
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

void evaluate_serial(
    const std::vector<double> &weights,
    const std::vector<double> &controls,
    const std::vector<double> &rowGradients,
    std::vector<double> &forward,
    std::vector<double> &transpose,
    const std::size_t batchSize)
{
    for (std::size_t batch = 0; batch < batchSize; ++batch)
    {
        for (int sample = 0; sample < kSamples; ++sample)
            for (int row = 0; row < kRows; ++row)
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    double sum = 0.0;
                    for (int control = 0; control < kControls; ++control)
                        sum += weights[weight_index(sample, row, control)] *
                               controls[control_index(batch, control, axis)];
                    forward[row_index(batch, sample, row, axis)] = sum;
                }
        for (int control = 0; control < kControls; ++control)
            for (int axis = 0; axis < kAxes; ++axis)
            {
                double sum = 0.0;
                for (int sample = 0; sample < kSamples; ++sample)
                    for (int row = 0; row < kRows; ++row)
                        sum += weights[weight_index(sample, row, control)] *
                               rowGradients[row_index(batch, sample, row, axis)];
                transpose[control_index(batch, control, axis)] = sum;
            }
    }
}

void evaluate_openmp(
    const std::vector<double> &weights,
    const std::vector<double> &controls,
    const std::vector<double> &rowGradients,
    std::vector<double> &forward,
    std::vector<double> &transpose,
    const std::size_t batchSize)
{
#pragma omp parallel for schedule(static)
    for (long long signedBatch = 0;
         signedBatch < static_cast<long long>(batchSize);
         ++signedBatch)
    {
        const std::size_t batch = static_cast<std::size_t>(signedBatch);
        for (int sample = 0; sample < kSamples; ++sample)
            for (int row = 0; row < kRows; ++row)
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    double sum = 0.0;
                    for (int control = 0; control < kControls; ++control)
                        sum += weights[weight_index(sample, row, control)] *
                               controls[control_index(batch, control, axis)];
                    forward[row_index(batch, sample, row, axis)] = sum;
                }
        for (int control = 0; control < kControls; ++control)
            for (int axis = 0; axis < kAxes; ++axis)
            {
                double sum = 0.0;
                for (int sample = 0; sample < kSamples; ++sample)
                    for (int row = 0; row < kRows; ++row)
                        sum += weights[weight_index(sample, row, control)] *
                               rowGradients[row_index(batch, sample, row, axis)];
                transpose[control_index(batch, control, axis)] = sum;
            }
    }
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

unsigned int block_count(const std::size_t outputCount)
{
    const std::size_t count =
        outputCount / kBlockSize + (outputCount % kBlockSize != 0 ? 1 : 0);
    if (count > std::numeric_limits<unsigned int>::max())
        throw std::invalid_argument("batch size exceeds one-dimensional grid limit");
    return static_cast<unsigned int>(count);
}

void launch_kernels(
    const double *weights,
    const double *controls,
    const double *rowGradients,
    double *forward,
    double *transpose,
    const std::size_t forwardCount,
    const std::size_t transposeCount)
{
    forward_weighted_samples<<<block_count(forwardCount), kBlockSize>>>(
        weights, controls, forward, forwardCount);
    cuda_check(cudaGetLastError(), "forward_weighted_samples launch");
    transpose_weighted_samples<<<block_count(transposeCount), kBlockSize>>>(
        weights, rowGradients, transpose, transposeCount);
    cuda_check(cudaGetLastError(), "transpose_weighted_samples launch");
}

Distribution distribution(std::vector<double> samples)
{
    if (samples.empty())
        throw std::invalid_argument("timing distribution is empty");
    std::sort(samples.begin(), samples.end());
    Distribution result;
    const std::size_t middle = samples.size() / 2;
    result.medianMilliseconds = samples.size() % 2 == 0
                                    ? (samples[middle - 1] + samples[middle]) / 2.0
                                    : samples[middle];
    const std::size_t p95Index = static_cast<std::size_t>(
        std::ceil(0.95 * static_cast<double>(samples.size()))) - 1;
    result.p95Milliseconds = samples[p95Index];
    return result;
}

template <typename Function>
Distribution measure_host(
    Function function, const int warmups, const int repetitions)
{
    for (int index = 0; index < warmups; ++index)
        function();
    std::vector<double> samples;
    samples.reserve(repetitions);
    for (int index = 0; index < repetitions; ++index)
    {
        const auto start = Clock::now();
        function();
        const auto stop = Clock::now();
        samples.push_back(
            std::chrono::duration<double, std::milli>(stop - start).count());
    }
    return distribution(std::move(samples));
}

template <typename Function>
Distribution measure_cuda_events(
    Function function, const int warmups, const int repetitions)
{
    for (int index = 0; index < warmups; ++index)
        function();
    cuda_check(cudaDeviceSynchronize(), "cudaDeviceSynchronize warmup");
    CudaEvent start;
    CudaEvent stop;
    std::vector<double> samples;
    samples.reserve(repetitions);
    for (int index = 0; index < repetitions; ++index)
    {
        cuda_check(cudaEventRecord(start.get()), "cudaEventRecord start");
        function();
        cuda_check(cudaEventRecord(stop.get()), "cudaEventRecord stop");
        cuda_check(cudaEventSynchronize(stop.get()), "cudaEventSynchronize stop");
        float milliseconds = 0.0F;
        cuda_check(
            cudaEventElapsedTime(&milliseconds, start.get(), stop.get()),
            "cudaEventElapsedTime");
        samples.push_back(milliseconds);
    }
    return distribution(std::move(samples));
}

double maximum_absolute_delta(
    const std::vector<double> &candidate,
    const std::vector<double> &reference)
{
    if (candidate.size() != reference.size())
        throw std::invalid_argument("comparison cardinality mismatch");
    double maximum = 0.0;
    for (std::size_t index = 0; index < candidate.size(); ++index)
    {
        if (!std::isfinite(candidate[index]) || !std::isfinite(reference[index]))
            throw std::runtime_error("benchmark correctness input is nonfinite");
        maximum = std::max(maximum, std::abs(candidate[index] - reference[index]));
    }
    return maximum;
}

BenchmarkCase benchmark_case(
    const std::vector<double> &weights,
    const std::size_t batchSize,
    const int warmups,
    const int repetitions)
{
    const std::vector<double> controls = deterministic_controls(batchSize);
    const std::vector<double> rowGradients =
        deterministic_row_gradients(batchSize);
    validate_batch_cardinality(batchSize);
    const std::size_t rowCount = checked_double_count(
        batchSize, kRowComponentsPerBatch, "benchmark row cardinality");
    const std::size_t controlCount = checked_double_count(
        batchSize, kControlComponentsPerBatch, "benchmark control cardinality");
    std::vector<double> serialForward(rowCount);
    std::vector<double> serialTranspose(controlCount);
    std::vector<double> openmpForward(serialForward.size());
    std::vector<double> openmpTranspose(serialTranspose.size());
    std::vector<double> cudaForward(serialForward.size());
    std::vector<double> cudaTranspose(serialTranspose.size());

    DeviceDoubles deviceWeights(weights.size());
    DeviceDoubles deviceControls(controls.size());
    DeviceDoubles deviceRowGradients(rowGradients.size());
    DeviceDoubles deviceForward(cudaForward.size());
    DeviceDoubles deviceTranspose(cudaTranspose.size());
    cuda_check(
        cudaMemcpy(deviceWeights.get(), weights.data(), weights.size() * sizeof(double),
                   cudaMemcpyHostToDevice),
        "cudaMemcpy benchmark weights");
    cuda_check(
        cudaMemcpy(deviceControls.get(), controls.data(), controls.size() * sizeof(double),
                   cudaMemcpyHostToDevice),
        "cudaMemcpy benchmark controls");
    cuda_check(
        cudaMemcpy(deviceRowGradients.get(), rowGradients.data(),
                   rowGradients.size() * sizeof(double), cudaMemcpyHostToDevice),
        "cudaMemcpy benchmark row gradients");

    evaluate_serial(
        weights, controls, rowGradients, serialForward, serialTranspose, batchSize);
    evaluate_openmp(
        weights, controls, rowGradients, openmpForward, openmpTranspose, batchSize);
    launch_kernels(
        deviceWeights.get(), deviceControls.get(), deviceRowGradients.get(),
        deviceForward.get(), deviceTranspose.get(), cudaForward.size(),
        cudaTranspose.size());
    cuda_check(
        cudaMemcpy(cudaForward.data(), deviceForward.get(),
                   cudaForward.size() * sizeof(double), cudaMemcpyDeviceToHost),
        "cudaMemcpy correctness forward");
    cuda_check(
        cudaMemcpy(cudaTranspose.data(), deviceTranspose.get(),
                   cudaTranspose.size() * sizeof(double), cudaMemcpyDeviceToHost),
        "cudaMemcpy correctness transpose");

    BenchmarkCase result;
    result.batchSize = batchSize;
    result.deviceBytes =
        checked_device_bytes(batchSize, weights.size() * sizeof(double));
    result.correctnessForwardMaximum = std::max(
        maximum_absolute_delta(openmpForward, serialForward),
        maximum_absolute_delta(cudaForward, serialForward));
    result.correctnessTransposeMaximum = std::max(
        maximum_absolute_delta(openmpTranspose, serialTranspose),
        maximum_absolute_delta(cudaTranspose, serialTranspose));
    if (result.correctnessForwardMaximum > kAbsoluteTolerance ||
        result.correctnessTransposeMaximum > kAbsoluteTolerance)
        throw std::runtime_error("benchmark correctness prerequisite failed");

    result.serialCpu = measure_host(
        [&]() {
            evaluate_serial(weights, controls, rowGradients, serialForward,
                            serialTranspose, batchSize);
        },
        warmups, repetitions);
    result.openmpCpu = measure_host(
        [&]() {
            evaluate_openmp(weights, controls, rowGradients, openmpForward,
                            openmpTranspose, batchSize);
        },
        warmups, repetitions);
    result.cudaKernel = measure_cuda_events(
        [&]() {
            launch_kernels(
                deviceWeights.get(), deviceControls.get(),
                deviceRowGradients.get(), deviceForward.get(),
                deviceTranspose.get(), cudaForward.size(), cudaTranspose.size());
        },
        warmups, repetitions);
    result.hostToDevice = measure_host(
        [&]() {
            cuda_check(
                cudaMemcpy(deviceControls.get(), controls.data(),
                           controls.size() * sizeof(double), cudaMemcpyHostToDevice),
                "cudaMemcpy timed controls host-to-device");
            cuda_check(
                cudaMemcpy(deviceRowGradients.get(), rowGradients.data(),
                           rowGradients.size() * sizeof(double),
                           cudaMemcpyHostToDevice),
                "cudaMemcpy timed row gradients host-to-device");
        },
        warmups, repetitions);
    result.deviceToHost = measure_host(
        [&]() {
            cuda_check(
                cudaMemcpy(cudaForward.data(), deviceForward.get(),
                           cudaForward.size() * sizeof(double),
                           cudaMemcpyDeviceToHost),
                "cudaMemcpy timed forward device-to-host");
            cuda_check(
                cudaMemcpy(cudaTranspose.data(), deviceTranspose.get(),
                           cudaTranspose.size() * sizeof(double),
                           cudaMemcpyDeviceToHost),
                "cudaMemcpy timed transpose device-to-host");
        },
        warmups, repetitions);
    result.cudaEndToEnd = measure_host(
        [&]() {
            cuda_check(
                cudaMemcpy(deviceControls.get(), controls.data(),
                           controls.size() * sizeof(double), cudaMemcpyHostToDevice),
                "cudaMemcpy end-to-end controls");
            cuda_check(
                cudaMemcpy(deviceRowGradients.get(), rowGradients.data(),
                           rowGradients.size() * sizeof(double),
                           cudaMemcpyHostToDevice),
                "cudaMemcpy end-to-end row gradients");
            launch_kernels(
                deviceWeights.get(), deviceControls.get(),
                deviceRowGradients.get(), deviceForward.get(),
                deviceTranspose.get(), cudaForward.size(), cudaTranspose.size());
            cuda_check(
                cudaMemcpy(cudaForward.data(), deviceForward.get(),
                           cudaForward.size() * sizeof(double),
                           cudaMemcpyDeviceToHost),
                "cudaMemcpy end-to-end forward");
            cuda_check(
                cudaMemcpy(cudaTranspose.data(), deviceTranspose.get(),
                           cudaTranspose.size() * sizeof(double),
                           cudaMemcpyDeviceToHost),
                "cudaMemcpy end-to-end transpose");
        },
        warmups, repetitions);

    const volatile double checksum =
        serialForward.front() + serialTranspose.back() + openmpForward.front() +
        openmpTranspose.back() + cudaForward.front() + cudaTranspose.back();
    (void)checksum;
    return result;
}

std::vector<std::size_t> parse_batch_sizes(const std::string &text)
{
    std::vector<std::size_t> values;
    std::size_t start = 0;
    while (start < text.size())
    {
        const std::size_t comma = text.find(',', start);
        const std::string token = text.substr(start, comma - start);
        std::size_t consumed = 0;
        const unsigned long long value = std::stoull(token, &consumed);
        if (consumed != token.size() || value == 0)
            throw std::invalid_argument("batch sizes must be positive integers");
        if (value > std::numeric_limits<std::size_t>::max())
            throw std::invalid_argument("batch size exceeds size_t range");
        const std::size_t batchSize = static_cast<std::size_t>(value);
        validate_batch_cardinality(batchSize);
        values.push_back(batchSize);
        if (comma == std::string::npos)
            break;
        start = comma + 1;
    }
    if (values.empty())
        throw std::invalid_argument("at least one batch size is required");
    if (!std::is_sorted(values.begin(), values.end()) ||
        std::adjacent_find(values.begin(), values.end()) != values.end())
        throw std::invalid_argument("batch sizes must be strictly increasing");
    return values;
}

int parse_positive_int(const char *value, const char *name, const int minimum)
{
    const std::string text(value);
    std::size_t consumed = 0;
    const long parsed = std::stol(text, &consumed);
    if (consumed != text.size() || parsed < minimum ||
        parsed > std::numeric_limits<int>::max())
        throw std::invalid_argument(
            std::string(name) + " must be an integer >= " +
            std::to_string(minimum));
    return static_cast<int>(parsed);
}

void print_distribution(const char *name, const Distribution &value)
{
    std::cout << "\"" << name << "\":{\"median_ms\":"
              << value.medianMilliseconds << ",\"p95_ms\":"
              << value.p95Milliseconds << '}';
}
} // namespace

int main(int argc, char **argv)
{
    try
    {
        if (argc != 7)
            throw std::invalid_argument(
                "usage: cuda_regular_weighted_sample_benchmark "
                "BATCH_CSV WARMUPS REPETITIONS OMP_THREADS COMPUTE_ARCH SM_CODE");
        const std::vector<std::size_t> batchSizes = parse_batch_sizes(argv[1]);
        const int warmups = parse_positive_int(argv[2], "warmups", 1);
        const int repetitions = parse_positive_int(argv[3], "repetitions", 30);
        const int requestedThreads = parse_positive_int(argv[4], "OMP threads", 1);
        const std::string computeArchitecture(argv[5]);
        const std::string smCode(argv[6]);

        int deviceCount = 0;
        const cudaError_t countError = cudaGetDeviceCount(&deviceCount);
        if (countError == cudaErrorNoDevice ||
            countError == cudaErrorInsufficientDriver || deviceCount == 0)
        {
            std::cout << "{\"status\":\"skipped\","
                         "\"reason\":\"no usable CUDA device\"}\n";
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
        std::size_t freeDeviceBytes = 0;
        std::size_t totalDeviceBytes = 0;
        cuda_check(cudaMemGetInfo(&freeDeviceBytes, &totalDeviceBytes),
                   "cudaMemGetInfo");

        omp_set_dynamic(0);
        omp_set_num_threads(requestedThreads);
        int observedThreads = 0;
#pragma omp parallel
        {
#pragma omp master
            observedThreads = omp_get_num_threads();
        }
        if (observedThreads != requestedThreads)
            throw std::runtime_error("OpenMP runtime did not honor requested threads");

        const std::vector<double> weights = production_regular_weights();
        std::vector<BenchmarkCase> cases;
        cases.reserve(batchSizes.size());
        for (const std::size_t batchSize : batchSizes)
        {
            const std::size_t requiredBytes =
                checked_device_bytes(batchSize, weights.size() * sizeof(double));
            if (requiredBytes > freeDeviceBytes / 2)
                throw std::invalid_argument(
                    "batch exceeds the 50% free-device-memory safety budget");
            cases.push_back(
                benchmark_case(weights, batchSize, warmups, repetitions));
        }

        std::size_t breakEvenSerialBatch = 0;
        std::size_t breakEvenOpenmpBatch = 0;
        for (const BenchmarkCase &item : cases)
        {
            if (breakEvenSerialBatch == 0 &&
                item.cudaEndToEnd.medianMilliseconds <
                    item.serialCpu.medianMilliseconds)
                breakEvenSerialBatch = item.batchSize;
            if (breakEvenOpenmpBatch == 0 &&
                item.cudaEndToEnd.medianMilliseconds <
                    item.openmpCpu.medianMilliseconds)
                breakEvenOpenmpBatch = item.batchSize;
        }
        const BenchmarkCase &representative = cases.back();
        const double representativeSpeedup =
            representative.openmpCpu.medianMilliseconds /
            representative.cudaEndToEnd.medianMilliseconds;

        std::cout << std::setprecision(17)
                  << "{\"status\":\"passed\","
                     "\"benchmark\":\"regular_weighted_sample_forward_transpose\""
                  << ",\"random_seed\":\"deterministic_formula_no_rng\""
                  << ",\"warmups\":" << warmups
                  << ",\"repetitions\":" << repetitions
                  << ",\"absolute_tolerance\":" << kAbsoluteTolerance
                  << ",\"timing_clock\":\"steady_clock_host_and_cuda_events_kernel\""
                  << ",\"constant_weight_setup\":\"excluded_from_repeated_timings\""
                  << ",\"transfer_inclusive_dynamic_inputs\":"
                     "\"controls_and_row_gradients\""
                  << ",\"transfer_inclusive_outputs\":"
                     "\"forward_and_transpose\""
                  << ",\"device_bytes_per_batch\":" << kDeviceBytesPerBatch
                  << ",\"device_total_bytes\":" << totalDeviceBytes
                  << ",\"device_free_bytes_before_sweep\":" << freeDeviceBytes
                  << ",\"memory_safety_budget\":\"at_most_50_percent_of_free_device_memory\""
                  << ",\"openmp_requested_threads\":" << requestedThreads
                  << ",\"openmp_observed_threads\":" << observedThreads
                  << ",\"openmp_dynamic\":false"
                  << ",\"openmp_schedule\":\"static\""
                  << ",\"openmp_runtime_macro\":" << _OPENMP
                  << ",\"break_even_vs_serial_batch\":";
        if (breakEvenSerialBatch == 0)
            std::cout << "null";
        else
            std::cout << breakEvenSerialBatch;
        std::cout << ",\"break_even_vs_openmp_batch\":";
        if (breakEvenOpenmpBatch == 0)
            std::cout << "null";
        else
            std::cout << breakEvenOpenmpBatch;
        std::cout << ",\"largest_tested_batch\":" << representative.batchSize
                  << ",\"largest_tested_device_bytes\":"
                  << representative.deviceBytes
                  << ",\"largest_tested_fraction_of_total_device_memory\":"
                  << static_cast<double>(representative.deviceBytes) /
                         static_cast<double>(totalDeviceBytes)
                  << ",\"representative_batch\":" << representative.batchSize
                  << ",\"representative_transfer_inclusive_speedup_vs_openmp\":"
                  << representativeSpeedup
                  << ",\"production_integration_recommendation\":\""
                  << (representativeSpeedup > 1.0
                          ? "transfer_inclusive_evidence_supports_further_integration_review"
                          : "not_supported_without_better_transfer_amortization")
                  << "\",\"next_step_recommendation\":\""
                  << (representativeSpeedup > 1.0
                          ? "continue_opt_in_adapter_experiment"
                          : "adapter_may_only_test_data_residency_or_transfer_amortization")
                  << "\",\"device\":\"" << deviceProperties.name << "\""
                  << ",\"compute_capability\":\"" << deviceProperties.major << '.'
                  << deviceProperties.minor << "\""
                  << ",\"driver_api_version\":" << driverVersion
                  << ",\"runtime_api_version\":" << runtimeVersion
                  << ",\"compile_compute_arch\":\"" << computeArchitecture << "\""
                  << ",\"compile_sm_code\":\"" << smCode << "\""
                  << ",\"cases\":[";
        for (std::size_t index = 0; index < cases.size(); ++index)
        {
            if (index != 0)
                std::cout << ',';
            const BenchmarkCase &item = cases[index];
            std::cout << "{\"batch_size\":" << item.batchSize
                      << ",\"device_bytes\":" << item.deviceBytes
                      << ",\"correctness_forward_max_abs\":"
                      << item.correctnessForwardMaximum
                      << ",\"correctness_transpose_max_abs\":"
                      << item.correctnessTransposeMaximum << ',';
            print_distribution("serial_cpu", item.serialCpu);
            std::cout << ',';
            print_distribution("openmp_cpu", item.openmpCpu);
            std::cout << ',';
            print_distribution("cuda_kernel", item.cudaKernel);
            std::cout << ',';
            print_distribution("host_to_device", item.hostToDevice);
            std::cout << ',';
            print_distribution("device_to_host", item.deviceToHost);
            std::cout << ',';
            print_distribution("cuda_end_to_end", item.cudaEndToEnd);
            std::cout << ",\"kernel_speedup_vs_serial\":"
                      << item.serialCpu.medianMilliseconds /
                             item.cudaKernel.medianMilliseconds
                      << ",\"kernel_speedup_vs_openmp\":"
                      << item.openmpCpu.medianMilliseconds /
                             item.cudaKernel.medianMilliseconds
                      << ",\"end_to_end_speedup_vs_serial\":"
                      << item.serialCpu.medianMilliseconds /
                             item.cudaEndToEnd.medianMilliseconds
                      << ",\"end_to_end_speedup_vs_openmp\":"
                      << item.openmpCpu.medianMilliseconds /
                             item.cudaEndToEnd.medianMilliseconds
                      << '}';
        }
        std::cout << "]}\n";
        return 0;
    }
    catch (const std::exception &error)
    {
        std::cerr << "CUDA benchmark failed: " << error.what() << '\n';
        return 1;
    }
}
