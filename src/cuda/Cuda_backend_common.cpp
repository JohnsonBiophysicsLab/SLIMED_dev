#include "cuda/Cuda_backend.hpp"

namespace slimed::cuda_backend
{

const char *error_code_name(const ErrorCode code) noexcept
{
    switch (code)
    {
    case ErrorCode::None:
        return "none";
    case ErrorCode::NotCompiled:
        return "not_compiled";
    case ErrorCode::NoDevice:
        return "no_device";
    case ErrorCode::InsufficientDriver:
        return "insufficient_driver";
    case ErrorCode::InvalidDeviceOrdinal:
        return "invalid_device_ordinal";
    case ErrorCode::InitializationFailed:
        return "initialization_failed";
    case ErrorCode::CapabilityQueryFailed:
        return "capability_query_failed";
    case ErrorCode::ContextCreationFailed:
        return "context_creation_failed";
    case ErrorCode::StreamCreationFailed:
        return "stream_creation_failed";
    case ErrorCode::ContextStackFailed:
        return "context_stack_failed";
    case ErrorCode::CleanupFailed:
        return "cleanup_failed";
    }
    return "unknown";
}

} // namespace slimed::cuda_backend
