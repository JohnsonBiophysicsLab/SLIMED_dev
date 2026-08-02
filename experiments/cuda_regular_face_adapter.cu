// Experimental Step 5 CUDA adapter/residency proof.
//
// This translation unit reuses the reviewed Step 4 weighted-sample kernels by
// inclusion. It is compiled only by scripts/run_cuda_regular_face_adapter.py
// and never enters a default Make target or production route.

#define main cuda_regular_weighted_sample_benchmark_main
#include "cuda_regular_weighted_sample_benchmark.cu"
#undef main

#include "mesh/Mesh.hpp"

#include <array>

namespace
{
constexpr double kStateIncrement = 1.0e-7;

struct FormulaDryRun
{
    bool finite = false;
    bool nonzero = false;
    double meanCurvature = 0.0;
    double bendingEnergy = 0.0;
    double maximumAbsoluteForce = 0.0;
};

struct ResidentCase
{
    std::size_t batchSize = 0;
    int residentIterations = 0;
    std::size_t deviceBytes = 0;
    double correctnessForwardMaximum = 0.0;
    double correctnessTransposeMaximum = 0.0;
    Distribution serialCpu;
    Distribution openmpCpu;
    Distribution cudaResidentKernel;
    Distribution cudaResidentEndToEnd;
};

template <typename Reset, typename Function>
Distribution measure_host_after_reset(
    Reset reset,
    Function function,
    const int warmups,
    const int repetitions)
{
    for (int index = 0; index < warmups; ++index)
    {
        reset();
        function();
    }
    std::vector<double> samples;
    samples.reserve(repetitions);
    for (int index = 0; index < repetitions; ++index)
    {
        reset();
        const auto start = Clock::now();
        function();
        const auto stop = Clock::now();
        samples.push_back(
            std::chrono::duration<double, std::milli>(stop - start).count());
    }
    return distribution(std::move(samples));
}

template <typename Reset, typename Function>
Distribution measure_cuda_events_after_reset(
    Reset reset,
    Function function,
    const int warmups,
    const int repetitions)
{
    for (int index = 0; index < warmups; ++index)
    {
        reset();
        function();
    }
    cuda_check(cudaDeviceSynchronize(), "cudaDeviceSynchronize resident warmup");
    CudaEvent start;
    CudaEvent stop;
    std::vector<double> samples;
    samples.reserve(repetitions);
    for (int index = 0; index < repetitions; ++index)
    {
        reset();
        cuda_check(cudaEventRecord(start.get()), "cudaEventRecord resident start");
        function();
        cuda_check(cudaEventRecord(stop.get()), "cudaEventRecord resident stop");
        cuda_check(cudaEventSynchronize(stop.get()),
                   "cudaEventSynchronize resident stop");
        float milliseconds = 0.0F;
        cuda_check(cudaEventElapsedTime(&milliseconds, start.get(), stop.get()),
                   "cudaEventElapsedTime resident");
        samples.push_back(milliseconds);
    }
    return distribution(std::move(samples));
}

std::vector<double> regular_face_controls(const std::size_t batchSize)
{
    // Actual regular-lattice one-ring order used by the existing adapter
    // proof: source ids 9,15,10,16,22,11,17,23,29,18,24,30 on a 7x7 grid.
    constexpr std::array<int, kControls> sourceIds = {
        9, 15, 10, 16, 22, 11, 17, 23, 29, 18, 24, 30};
    std::vector<double> controls(checked_double_count(
        batchSize, kControlComponentsPerBatch, "adapter controls"));
    for (std::size_t batch = 0; batch < batchSize; ++batch)
    {
        for (int control = 0; control < kControls; ++control)
        {
            const int sourceId = sourceIds[control];
            const int i = sourceId % 7;
            const int j = sourceId / 7;
            controls[control_index(batch, control, 0)] =
                static_cast<double>(i) + 0.5 * static_cast<double>(j) +
                1.0e-5 * static_cast<double>(batch % 31);
            controls[control_index(batch, control, 1)] =
                0.8660254037844386 * static_cast<double>(j) -
                1.0e-5 * static_cast<double>(batch % 29);
            controls[control_index(batch, control, 2)] =
                0.03 * std::sin(0.7 * static_cast<double>(i + j)) +
                1.0e-6 * static_cast<double>((batch + control) % 23);
        }
    }
    return controls;
}

void advance_serial(
    std::vector<double> &controls,
    std::vector<double> &rowGradients)
{
    for (std::size_t index = 0; index < controls.size(); ++index)
        controls[index] +=
            kStateIncrement * static_cast<double>(static_cast<int>(index % 13) - 6);
    for (std::size_t index = 0; index < rowGradients.size(); ++index)
        rowGradients[index] +=
            kStateIncrement * static_cast<double>(static_cast<int>(index % 17) - 8);
}

void advance_openmp(
    std::vector<double> &controls,
    std::vector<double> &rowGradients)
{
#pragma omp parallel for schedule(static)
    for (long long index = 0;
         index < static_cast<long long>(controls.size());
         ++index)
        controls[static_cast<std::size_t>(index)] +=
            kStateIncrement * static_cast<double>(static_cast<int>(index % 13) - 6);
#pragma omp parallel for schedule(static)
    for (long long index = 0;
         index < static_cast<long long>(rowGradients.size());
         ++index)
        rowGradients[static_cast<std::size_t>(index)] +=
            kStateIncrement * static_cast<double>(static_cast<int>(index % 17) - 8);
}

__global__ void advance_resident_state(
    double *controls,
    const std::size_t controlCount,
    double *rowGradients,
    const std::size_t rowCount)
{
    const std::size_t index =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index < controlCount)
        controls[index] +=
            kStateIncrement * static_cast<double>(static_cast<int>(index % 13) - 6);
    if (index < rowCount)
        rowGradients[index] +=
            kStateIncrement * static_cast<double>(static_cast<int>(index % 17) - 8);
}

void launch_resident_iteration(
    const double *weights,
    double *controls,
    double *rowGradients,
    double *forward,
    double *transpose,
    const std::size_t controlCount,
    const std::size_t rowCount)
{
    const std::size_t stateCount = std::max(controlCount, rowCount);
    advance_resident_state<<<block_count(stateCount), kBlockSize>>>(
        controls, controlCount, rowGradients, rowCount);
    cuda_check(cudaGetLastError(), "advance_resident_state launch");
    launch_kernels(weights,
                   controls,
                   rowGradients,
                   forward,
                   transpose,
                   rowCount,
                   controlCount);
}

void evaluate_serial_sequence(
    const std::vector<double> &weights,
    std::vector<double> &controls,
    std::vector<double> &rowGradients,
    std::vector<double> &forward,
    std::vector<double> &transpose,
    const std::size_t batchSize,
    const int iterations)
{
    for (int iteration = 0; iteration < iterations; ++iteration)
    {
        advance_serial(controls, rowGradients);
        evaluate_serial(
            weights, controls, rowGradients, forward, transpose, batchSize);
    }
}

void evaluate_openmp_sequence(
    const std::vector<double> &weights,
    std::vector<double> &controls,
    std::vector<double> &rowGradients,
    std::vector<double> &forward,
    std::vector<double> &transpose,
    const std::size_t batchSize,
    const int iterations)
{
    for (int iteration = 0; iteration < iterations; ++iteration)
    {
        advance_openmp(controls, rowGradients);
        evaluate_openmp(
            weights, controls, rowGradients, forward, transpose, batchSize);
    }
}

FormulaDryRun production_formula_dry_run(
    const std::vector<double> &controls)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    param.area0 = 2.75;
    param.area = 2.82;
    param.vol0 = 0.82;
    param.vol = 0.87;
    Mesh mesh(param);
    mesh.param.area = param.area;
    mesh.param.vol = param.vol;

    std::vector<Matrix> coordinateColumns(kControls);
    Face face;
    face.index = 0;
    face.spontCurvature = 0.18;
    for (int control = 0; control < kControls; ++control)
    {
        face.oneRingVertices.push_back(control);
        coordinateColumns[control] = Matrix(kAxes, 1, true);
        for (int axis = 0; axis < kAxes; ++axis)
            coordinateColumns[control].set(
                axis, 0, controls[control_index(0, control, axis)]);
    }

    Matrix normal = mat_calloc(3, 1);
    Matrix fBend = mat_calloc(kControls, kAxes);
    Matrix fArea = mat_calloc(kControls, kAxes);
    Matrix fVolume = mat_calloc(kControls, kAxes);
    FormulaDryRun result;
    mesh.element_energy_force_regular(coordinateColumns,
                                      face,
                                      face.spontCurvature,
                                      result.meanCurvature,
                                      normal,
                                      result.bendingEnergy,
                                      fBend,
                                      fArea,
                                      fVolume,
                                      false);
    result.finite = std::isfinite(result.meanCurvature) &&
                    std::isfinite(result.bendingEnergy);
    for (int axis = 0; axis < kAxes; ++axis)
        result.finite = result.finite && std::isfinite(normal.get(axis, 0));
    for (int row = 0; row < kControls; ++row)
        for (int axis = 0; axis < kAxes; ++axis)
        {
            const std::array<double, 3> values = {
                fBend.get(row, axis),
                fArea.get(row, axis),
                fVolume.get(row, axis)};
            for (const double value : values)
            {
                result.finite = result.finite && std::isfinite(value);
                result.maximumAbsoluteForce =
                    std::max(result.maximumAbsoluteForce, std::abs(value));
            }
        }
    result.nonzero = result.maximumAbsoluteForce > 0.0 &&
                     std::abs(result.bendingEnergy) > 0.0;
    return result;
}

ResidentCase benchmark_resident_case(
    const std::vector<double> &weights,
    const std::size_t batchSize,
    const int residentIterations,
    const int warmups,
    const int repetitions)
{
    validate_batch_cardinality(batchSize);
    const std::vector<double> initialControls = regular_face_controls(batchSize);
    const std::vector<double> initialRowGradients =
        deterministic_row_gradients(batchSize);
    const std::size_t rowCount = checked_double_count(
        batchSize, kRowComponentsPerBatch, "resident row cardinality");
    const std::size_t controlCount = checked_double_count(
        batchSize, kControlComponentsPerBatch, "resident control cardinality");

    std::vector<double> serialControls = initialControls;
    std::vector<double> serialGradients = initialRowGradients;
    std::vector<double> serialForward(rowCount);
    std::vector<double> serialTranspose(controlCount);
    std::vector<double> openmpControls = initialControls;
    std::vector<double> openmpGradients = initialRowGradients;
    std::vector<double> openmpForward(rowCount);
    std::vector<double> openmpTranspose(controlCount);
    std::vector<double> cudaForward(rowCount);
    std::vector<double> cudaTranspose(controlCount);

    DeviceDoubles deviceWeights(weights.size());
    DeviceDoubles deviceControls(controlCount);
    DeviceDoubles deviceRowGradients(rowCount);
    DeviceDoubles deviceForward(rowCount);
    DeviceDoubles deviceTranspose(controlCount);
    cuda_check(cudaMemcpy(deviceWeights.get(),
                          weights.data(),
                          weights.size() * sizeof(double),
                          cudaMemcpyHostToDevice),
               "cudaMemcpy adapter weights");
    auto reset_device_inputs = [&]() {
        cuda_check(cudaMemcpy(deviceControls.get(),
                              initialControls.data(),
                              controlCount * sizeof(double),
                              cudaMemcpyHostToDevice),
                   "cudaMemcpy adapter controls");
        cuda_check(cudaMemcpy(deviceRowGradients.get(),
                              initialRowGradients.data(),
                              rowCount * sizeof(double),
                              cudaMemcpyHostToDevice),
                   "cudaMemcpy adapter row gradients");
    };
    auto run_device_sequence = [&]() {
        for (int iteration = 0; iteration < residentIterations; ++iteration)
            launch_resident_iteration(deviceWeights.get(),
                                      deviceControls.get(),
                                      deviceRowGradients.get(),
                                      deviceForward.get(),
                                      deviceTranspose.get(),
                                      controlCount,
                                      rowCount);
    };

    evaluate_serial_sequence(weights,
                             serialControls,
                             serialGradients,
                             serialForward,
                             serialTranspose,
                             batchSize,
                             residentIterations);
    evaluate_openmp_sequence(weights,
                             openmpControls,
                             openmpGradients,
                             openmpForward,
                             openmpTranspose,
                             batchSize,
                             residentIterations);
    reset_device_inputs();
    run_device_sequence();
    cuda_check(cudaMemcpy(cudaForward.data(),
                          deviceForward.get(),
                          rowCount * sizeof(double),
                          cudaMemcpyDeviceToHost),
               "cudaMemcpy adapter correctness forward");
    cuda_check(cudaMemcpy(cudaTranspose.data(),
                          deviceTranspose.get(),
                          controlCount * sizeof(double),
                          cudaMemcpyDeviceToHost),
               "cudaMemcpy adapter correctness transpose");

    ResidentCase result;
    result.batchSize = batchSize;
    result.residentIterations = residentIterations;
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
        throw std::runtime_error("resident adapter correctness prerequisite failed");

    std::vector<double> timedSerialControls(initialControls.size());
    std::vector<double> timedSerialGradients(initialRowGradients.size());
    std::vector<double> timedOpenmpControls(initialControls.size());
    std::vector<double> timedOpenmpGradients(initialRowGradients.size());
    result.serialCpu = measure_host_after_reset(
        [&]() {
            std::copy(initialControls.begin(),
                      initialControls.end(),
                      timedSerialControls.begin());
            std::copy(initialRowGradients.begin(),
                      initialRowGradients.end(),
                      timedSerialGradients.begin());
        },
        [&]() {
            evaluate_serial_sequence(weights,
                                     timedSerialControls,
                                     timedSerialGradients,
                                     serialForward,
                                     serialTranspose,
                                     batchSize,
                                     residentIterations);
        },
        warmups,
        repetitions);
    result.openmpCpu = measure_host_after_reset(
        [&]() {
            std::copy(initialControls.begin(),
                      initialControls.end(),
                      timedOpenmpControls.begin());
            std::copy(initialRowGradients.begin(),
                      initialRowGradients.end(),
                      timedOpenmpGradients.begin());
        },
        [&]() {
            evaluate_openmp_sequence(weights,
                                     timedOpenmpControls,
                                     timedOpenmpGradients,
                                     openmpForward,
                                     openmpTranspose,
                                     batchSize,
                                     residentIterations);
        },
        warmups,
        repetitions);
    result.cudaResidentKernel = measure_cuda_events_after_reset(
        reset_device_inputs,
        [&]() { run_device_sequence(); },
        warmups,
        repetitions);
    result.cudaResidentEndToEnd = measure_host(
        [&]() {
            reset_device_inputs();
            run_device_sequence();
            cuda_check(cudaMemcpy(cudaForward.data(),
                                  deviceForward.get(),
                                  rowCount * sizeof(double),
                                  cudaMemcpyDeviceToHost),
                       "cudaMemcpy resident forward");
            cuda_check(cudaMemcpy(cudaTranspose.data(),
                                  deviceTranspose.get(),
                                  controlCount * sizeof(double),
                                  cudaMemcpyDeviceToHost),
                       "cudaMemcpy resident transpose");
        },
        warmups,
        repetitions);
    return result;
}

std::vector<int> parse_iteration_counts(const std::string &text)
{
    std::vector<int> values;
    std::size_t start = 0;
    while (start < text.size())
    {
        const std::size_t comma = text.find(',', start);
        const std::string token = text.substr(start, comma - start);
        values.push_back(parse_positive_int(token.c_str(), "resident iterations", 1));
        if (comma == std::string::npos)
            break;
        start = comma + 1;
    }
    if (values.empty() || !std::is_sorted(values.begin(), values.end()) ||
        std::adjacent_find(values.begin(), values.end()) != values.end())
        throw std::invalid_argument(
            "resident iterations must be strictly increasing");
    return values;
}
} // namespace

int main(int argc, char **argv)
{
    try
    {
        if (argc != 8)
            throw std::invalid_argument(
                "usage: cuda_regular_face_adapter BATCH_CSV ITERATION_CSV "
                "WARMUPS REPETITIONS OMP_THREADS COMPUTE_ARCH SM_CODE");
        const std::vector<std::size_t> batchSizes = parse_batch_sizes(argv[1]);
        const std::vector<int> iterationCounts = parse_iteration_counts(argv[2]);
        const int warmups = parse_positive_int(argv[3], "warmups", 1);
        const int repetitions = parse_positive_int(argv[4], "repetitions", 30);
        const int requestedThreads = parse_positive_int(argv[5], "OMP threads", 1);
        const std::string computeArchitecture(argv[6]);
        const std::string smCode(argv[7]);

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
        const FormulaDryRun formula =
            production_formula_dry_run(regular_face_controls(1));
        if (!formula.finite || !formula.nonzero)
            throw std::runtime_error("production CPU formula dry run failed");

        std::vector<ResidentCase> cases;
        for (const std::size_t batchSize : batchSizes)
        {
            const std::size_t requiredBytes =
                checked_device_bytes(batchSize, weights.size() * sizeof(double));
            if (requiredBytes > freeDeviceBytes / 2)
                throw std::invalid_argument(
                    "batch exceeds the 50% free-device-memory safety budget");
            for (const int residentIterations : iterationCounts)
                cases.push_back(benchmark_resident_case(weights,
                                                        batchSize,
                                                        residentIterations,
                                                        warmups,
                                                        repetitions));
        }

        std::cout << std::setprecision(17)
                  << "{\"status\":\"passed\","
                     "\"experiment\":\"regular_face_cuda_residency_adapter\""
                  << ",\"scope\":\"opt_in_adapter_only_no_production_route\""
                  << ",\"row_source\":\"Param::shapeFunctions_from_current_regular_formula\""
                  << ",\"cpu_formula_seam\":\"Mesh::element_energy_force_regular\""
                  << ",\"adapter_output_comparison\":\"forward_and_transpose_vs_explicit_order_CPU_weighted_rows_consumed_by_Mesh::element_energy_force_regular\""
                  << ",\"resident_state_model\":\"device_local_deterministic_update_surrogate\""
                  << ",\"resident_state_limitation\":\"upper_bound_not_a_production_integrator\""
                  << ",\"warmups\":" << warmups
                  << ",\"repetitions\":" << repetitions
                  << ",\"absolute_tolerance\":" << kAbsoluteTolerance
                  << ",\"openmp_requested_threads\":" << requestedThreads
                  << ",\"openmp_observed_threads\":" << observedThreads
                  << ",\"device_total_bytes\":" << totalDeviceBytes
                  << ",\"device_free_bytes_before_sweep\":" << freeDeviceBytes
                  << ",\"production_formula_dry_run\":{"
                  << "\"finite\":" << (formula.finite ? "true" : "false")
                  << ",\"nonzero\":" << (formula.nonzero ? "true" : "false")
                  << ",\"mean_curvature\":" << formula.meanCurvature
                  << ",\"bending_energy\":" << formula.bendingEnergy
                  << ",\"max_abs_force\":" << formula.maximumAbsoluteForce
                  << "},\"device\":\"" << deviceProperties.name << "\""
                  << ",\"compute_capability\":\"" << deviceProperties.major
                  << '.' << deviceProperties.minor << "\""
                  << ",\"driver_api_version\":" << driverVersion
                  << ",\"runtime_api_version\":" << runtimeVersion
                  << ",\"compile_compute_arch\":\"" << computeArchitecture
                  << "\",\"compile_sm_code\":\"" << smCode << "\""
                  << ",\"cases\":[";
        for (std::size_t index = 0; index < cases.size(); ++index)
        {
            if (index != 0)
                std::cout << ',';
            const ResidentCase &item = cases[index];
            std::cout << "{\"batch_size\":" << item.batchSize
                      << ",\"resident_iterations\":" << item.residentIterations
                      << ",\"device_bytes\":" << item.deviceBytes
                      << ",\"correctness_forward_max_abs\":"
                      << item.correctnessForwardMaximum
                      << ",\"correctness_transpose_max_abs\":"
                      << item.correctnessTransposeMaximum << ',';
            print_distribution("serial_cpu", item.serialCpu);
            std::cout << ',';
            print_distribution("openmp_cpu", item.openmpCpu);
            std::cout << ',';
            print_distribution("cuda_resident_kernel", item.cudaResidentKernel);
            std::cout << ',';
            print_distribution("cuda_resident_end_to_end",
                               item.cudaResidentEndToEnd);
            std::cout << ",\"resident_end_to_end_speedup_vs_openmp\":"
                      << item.openmpCpu.medianMilliseconds /
                             item.cudaResidentEndToEnd.medianMilliseconds
                      << '}';
        }
        std::cout << "],\"readiness\":{"
                     "\"correctness\":\"weighted_adapter_output_matches_cpu_seam_and_formula_dry_run_passed\","
                     "\"performance\":\"resident_upper_bound_only\","
                     "\"memory_ownership\":\"proof_local_raii_device_buffers\","
                     "\"fallback\":\"cuda_absence_is_machine_readable_skip\","
                     "\"error_handling\":\"checked_cuda_calls_cardinality_and_memory_budget\","
                     "\"remaining_risks\":[\"production_device_state_ownership\","
                     "\"full_gpu_force_formula\",\"scatter_and_reduction\","
                     "\"dynamic_simulation_input_producer\"],"
                     "\"production_routing_recommendation\":"
                     "\"not_ready_without_end_to_end_device_resident_pipeline\"}}\n";
        return 0;
    }
    catch (const std::exception &error)
    {
        std::cerr << "CUDA adapter failed: " << error.what() << '\n';
        return 1;
    }
}
