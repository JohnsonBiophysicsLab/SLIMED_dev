#ifndef SLIMED_CUDA_BACKEND_HPP
#define SLIMED_CUDA_BACKEND_HPP

#include <cstddef>
#include <memory>
#include <string>

namespace slimed::cuda_backend
{

enum class ErrorCode
{
    None = 0,
    NotCompiled,
    NoDevice,
    InsufficientDriver,
    InvalidDeviceOrdinal,
    InitializationFailed,
    CapabilityQueryFailed,
    ContextCreationFailed,
    StreamCreationFailed,
    ContextStackFailed,
    CleanupFailed,
};

const char *error_code_name(ErrorCode code) noexcept;

struct Error
{
    ErrorCode code = ErrorCode::None;
    std::string operation;
    int nativeCode = 0;
    std::string message;

    bool ok() const noexcept
    {
        return code == ErrorCode::None;
    }
};

struct DeviceCapabilities
{
    int requestedDeviceOrdinal = 0;
    int deviceCount = 0;
    std::string name;
    int computeCapabilityMajor = 0;
    int computeCapabilityMinor = 0;
    int driverVersion = 0;
    int runtimeVersion = 0;
    std::size_t totalMemoryBytes = 0;
    std::size_t freeMemoryBytes = 0;
    int multiprocessorCount = 0;
    int warpSize = 0;
    int maximumThreadsPerBlock = 0;
    int asynchronousEngineCount = 0;
    bool memoryPoolsSupported = false;
    bool nonblockingStreamOwned = false;
    bool primaryContextRetained = false;
};

struct BackendReport
{
    bool compiled = false;
    bool available = false;
    DeviceCapabilities device;
    Error error;
};

struct ContextResult;

class DeviceContext final
{
  public:
    DeviceContext(const DeviceContext &) = delete;
    DeviceContext &operator=(const DeviceContext &) = delete;
    DeviceContext(DeviceContext &&) noexcept;
    DeviceContext &operator=(DeviceContext &&) noexcept;
    ~DeviceContext();

    const DeviceCapabilities &capabilities() const noexcept;
    Error close();

  private:
    struct Impl;

    DeviceContext(std::unique_ptr<Impl> impl, DeviceCapabilities capabilities);

    std::unique_ptr<Impl> impl_;
    DeviceCapabilities capabilities_;

    friend struct ContextResult;
    friend ContextResult create_device_context(int deviceOrdinal);
};

struct ContextResult
{
    std::unique_ptr<DeviceContext> context;
    BackendReport report;

    bool ok() const noexcept
    {
        return context != nullptr && report.compiled && report.available &&
               report.error.ok();
    }
};

ContextResult create_device_context(int deviceOrdinal = 0);
BackendReport query_backend(int deviceOrdinal = 0);

} // namespace slimed::cuda_backend

#endif
