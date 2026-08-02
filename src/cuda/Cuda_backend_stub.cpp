#include "cuda/Cuda_backend.hpp"

#include <utility>

namespace slimed::cuda_backend
{

struct DeviceContext::Impl
{
};

DeviceContext::DeviceContext(std::unique_ptr<Impl> impl,
                             DeviceCapabilities capabilities)
    : impl_(std::move(impl)), capabilities_(std::move(capabilities))
{
}

DeviceContext::DeviceContext(DeviceContext &&) noexcept = default;
DeviceContext &DeviceContext::operator=(DeviceContext &&) noexcept = default;
DeviceContext::~DeviceContext()
{
    (void)close();
}

const DeviceCapabilities &DeviceContext::capabilities() const noexcept
{
    return capabilities_;
}

Error DeviceContext::close()
{
    impl_.reset();
    return {};
}

ContextResult create_device_context(const int deviceOrdinal)
{
    ContextResult result;
    result.report.compiled = false;
    result.report.available = false;
    result.report.device.requestedDeviceOrdinal = deviceOrdinal;
    result.report.error.code = ErrorCode::NotCompiled;
    result.report.error.operation = "compile_time";
    result.report.error.message =
        "CUDA backend is not compiled; use the explicit cuda_backend_report target";
    return result;
}

BackendReport query_backend(const int deviceOrdinal)
{
    return create_device_context(deviceOrdinal).report;
}

} // namespace slimed::cuda_backend
