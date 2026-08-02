#ifndef SLIMED_CUDA_CONTEXT_LIFETIME_HPP
#define SLIMED_CUDA_CONTEXT_LIFETIME_HPP

#include <cstdint>

namespace slimed::cuda_backend::detail
{

using OpaqueHandle = std::uintptr_t;

enum class LifetimeOperation
{
    None = 0,
    PushContext,
    PopContext,
    DestroyStream,
    ReleasePrimaryContext,
    UnexpectedPoppedContext,
};

struct LifetimeFailure
{
    LifetimeOperation operation = LifetimeOperation::None;
    int nativeCode = 0;

    bool ok() const noexcept
    {
        return operation == LifetimeOperation::None;
    }
};

struct LifetimeDriverCalls
{
    void *userData = nullptr;
    int successCode = 0;
    int (*pushContext)(void *, OpaqueHandle) noexcept = nullptr;
    int (*popContext)(void *, OpaqueHandle *) noexcept = nullptr;
    int (*destroyStream)(void *, OpaqueHandle) noexcept = nullptr;
    int (*releasePrimaryContext)(void *, int) noexcept = nullptr;
};

inline const char *lifetime_operation_name(
    const LifetimeOperation operation) noexcept
{
    switch (operation)
    {
    case LifetimeOperation::None:
        return "none";
    case LifetimeOperation::PushContext:
        return "cleanup.cuCtxPushCurrent";
    case LifetimeOperation::PopContext:
        return "cleanup.cuCtxPopCurrent";
    case LifetimeOperation::DestroyStream:
        return "cleanup.cuStreamDestroy";
    case LifetimeOperation::ReleasePrimaryContext:
        return "cleanup.cuDevicePrimaryCtxRelease";
    case LifetimeOperation::UnexpectedPoppedContext:
        return "cleanup.unexpected_popped_context";
    }
    return "cleanup.unknown";
}

// Tracks only driver-resource lifetime. It deliberately owns no scientific
// data. Failed cleanup operations leave their state marked as live so a later
// explicit close or the destructor can retry without double destruction or
// release.
class ContextLifetime final
{
  public:
    explicit ContextLifetime(LifetimeDriverCalls calls) noexcept
        : calls_(calls)
    {
    }

    ContextLifetime(const ContextLifetime &) = delete;
    ContextLifetime &operator=(const ContextLifetime &) = delete;

    void markPrimaryContextRetained(const int device,
                                    const OpaqueHandle context) noexcept
    {
        device_ = device;
        context_ = context;
        retained_ = true;
    }

    void markStreamCreated(const OpaqueHandle stream) noexcept
    {
        stream_ = stream;
    }

    LifetimeFailure pushContext() noexcept
    {
        if (pushed_)
            return {};
        const int status = calls_.pushContext(calls_.userData, context_);
        if (status != calls_.successCode)
            return {LifetimeOperation::PushContext, status};
        pushed_ = true;
        return {};
    }

    LifetimeFailure popContext() noexcept
    {
        if (!pushed_)
            return {};
        OpaqueHandle popped = 0;
        const int status = calls_.popContext(calls_.userData, &popped);
        if (status != calls_.successCode)
            return {LifetimeOperation::PopContext, status};
        if (popped != context_)
            return {LifetimeOperation::UnexpectedPoppedContext, 0};
        pushed_ = false;
        return {};
    }

    LifetimeFailure cleanup() noexcept
    {
        LifetimeFailure firstFailure;
        const auto remember = [&firstFailure](const LifetimeFailure failure) {
            if (firstFailure.ok() && !failure.ok())
                firstFailure = failure;
        };

        if (stream_ != 0)
        {
            if (!pushed_)
                remember(pushContext());
            if (pushed_)
            {
                const int status =
                    calls_.destroyStream(calls_.userData, stream_);
                if (status == calls_.successCode)
                    stream_ = 0;
                else
                    remember({LifetimeOperation::DestroyStream, status});
            }
        }

        if (pushed_)
            remember(popContext());

        // Never release a shared primary-context reference while its context
        // may still be current or while a stream is still owned.
        if (retained_ && !pushed_ && stream_ == 0)
        {
            const int status =
                calls_.releasePrimaryContext(calls_.userData, device_);
            if (status == calls_.successCode)
                retained_ = false;
            else
                remember(
                    {LifetimeOperation::ReleasePrimaryContext, status});
        }
        return firstFailure;
    }

    bool retained() const noexcept
    {
        return retained_;
    }

    bool pushed() const noexcept
    {
        return pushed_;
    }

    bool ownsStream() const noexcept
    {
        return stream_ != 0;
    }

  private:
    LifetimeDriverCalls calls_;
    int device_ = 0;
    OpaqueHandle context_ = 0;
    OpaqueHandle stream_ = 0;
    bool retained_ = false;
    bool pushed_ = false;
};

} // namespace slimed::cuda_backend::detail

#endif
