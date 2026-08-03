#include "cuda/Cuda_backend.hpp"

#include <cstdlib>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>

namespace
{
constexpr int kUnavailableExitCode = 77;

std::string json_escape(const std::string &text)
{
    std::string escaped;
    escaped.reserve(text.size());
    for (const char character : text)
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
            if (static_cast<unsigned char>(character) < 0x20)
            {
                constexpr char hex[] = "0123456789abcdef";
                escaped += "\\u00";
                escaped += hex[(static_cast<unsigned char>(character) >> 4) &
                               0x0f];
                escaped += hex[static_cast<unsigned char>(character) & 0x0f];
            }
            else
                escaped += character;
        }
    }
    return escaped;
}

int parse_integer(const char *value, const char *name, const bool positive)
{
    const std::string text(value);
    std::size_t consumed = 0;
    const long parsed = std::stol(text, &consumed);
    if (consumed != text.size() || parsed < 0 ||
        (positive && parsed == 0) ||
        parsed > std::numeric_limits<int>::max())
        throw std::invalid_argument(std::string(name) +
                                    " must be a valid nonnegative integer");
    return static_cast<int>(parsed);
}

void print_report(const slimed::cuda_backend::BackendReport &report,
                  const int requestedLifecycleIterations,
                  const int completedLifecycleIterations)
{
    const auto &device = report.device;
    const auto &error = report.error;
    std::cout << "{"
              << "\"status\":\""
              << (report.available ? "available" : "unavailable") << "\","
              << "\"compiled\":" << (report.compiled ? "true" : "false")
              << ",\"available\":" << (report.available ? "true" : "false")
              << ",\"requested_context_lifecycle_iterations\":"
              << requestedLifecycleIterations
              << ",\"completed_context_lifecycle_iterations\":"
              << completedLifecycleIterations
              << ",\"device\":{"
              << "\"requested_ordinal\":" << device.requestedDeviceOrdinal
              << ",\"device_count\":" << device.deviceCount
              << ",\"name\":\"" << json_escape(device.name) << "\""
              << ",\"compute_capability_major\":"
              << device.computeCapabilityMajor
              << ",\"compute_capability_minor\":"
              << device.computeCapabilityMinor
              << ",\"driver_version\":" << device.driverVersion
              << ",\"runtime_version\":" << device.runtimeVersion
              << ",\"total_memory_bytes\":" << device.totalMemoryBytes
              << ",\"free_memory_bytes\":" << device.freeMemoryBytes
              << ",\"multiprocessor_count\":" << device.multiprocessorCount
              << ",\"warp_size\":" << device.warpSize
              << ",\"maximum_threads_per_block\":"
              << device.maximumThreadsPerBlock
              << ",\"asynchronous_engine_count\":"
              << device.asynchronousEngineCount
              << ",\"memory_pools_supported\":"
              << (device.memoryPoolsSupported ? "true" : "false")
              << ",\"primary_context_retained\":"
              << (device.primaryContextRetained ? "true" : "false")
              << ",\"nonblocking_stream_owned\":"
              << (device.nonblockingStreamOwned ? "true" : "false") << "},"
              << "\"error\":{"
              << "\"code\":\""
              << slimed::cuda_backend::error_code_name(error.code) << "\""
              << ",\"operation\":\"" << json_escape(error.operation) << "\""
              << ",\"native_code\":" << error.nativeCode
              << ",\"message\":\"" << json_escape(error.message) << "\"}}\n";
}
} // namespace

int main(int argc, char **argv)
{
    try
    {
        int deviceOrdinal = 0;
        int lifecycleIterations = 1;
        for (int index = 1; index < argc; ++index)
        {
            const std::string argument(argv[index]);
            if (argument == "--device" && index + 1 < argc)
                deviceOrdinal =
                    parse_integer(argv[++index], "--device", false);
            else if (argument == "--lifecycle-iterations" && index + 1 < argc)
                lifecycleIterations = parse_integer(
                    argv[++index], "--lifecycle-iterations", true);
            else
                throw std::invalid_argument(
                    "usage: cuda_backend_report [--device N] "
                    "[--lifecycle-iterations N]");
        }

        slimed::cuda_backend::ContextResult finalResult;
        int completedLifecycleIterations = 0;
        for (int iteration = 0; iteration < lifecycleIterations; ++iteration)
        {
            auto result =
                slimed::cuda_backend::create_device_context(deviceOrdinal);
            if (!result.ok())
            {
                finalResult = std::move(result);
                break;
            }
            const auto cleanupError = result.context->close();
            if (!cleanupError.ok())
            {
                result.report.available = false;
                result.report.error = cleanupError;
                finalResult = std::move(result);
                break;
            }
            ++completedLifecycleIterations;
            if (iteration + 1 == lifecycleIterations)
                finalResult = std::move(result);
        }
        const auto &finalReport = finalResult.report;
        print_report(finalReport, lifecycleIterations,
                     completedLifecycleIterations);

        if (finalReport.available)
            return EXIT_SUCCESS;
        if (finalReport.error.code ==
                slimed::cuda_backend::ErrorCode::NotCompiled ||
            finalReport.error.code ==
                slimed::cuda_backend::ErrorCode::NoDevice ||
            finalReport.error.code ==
                slimed::cuda_backend::ErrorCode::InsufficientDriver)
            return kUnavailableExitCode;
        return EXIT_FAILURE;
    }
    catch (const std::exception &error)
    {
        std::cerr << "cuda_backend_report: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
