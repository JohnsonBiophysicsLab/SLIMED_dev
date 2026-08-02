#include "cuda/Cuda_backend.hpp"
#include "cuda/detail/Cuda_context_lifetime.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <string>
#include <type_traits>
#include <vector>

namespace
{

using slimed::cuda_backend::detail::ContextLifetime;
using slimed::cuda_backend::detail::LifetimeDriverCalls;
using slimed::cuda_backend::detail::LifetimeOperation;
using slimed::cuda_backend::detail::OpaqueHandle;

struct FakeLifetimeDriver
{
    static constexpr int kFailure = 41;

    std::vector<OpaqueHandle> contextStack{11};
    std::vector<std::string> calls;
    int failPush = 0;
    int failPop = 0;
    int failDestroy = 0;
    int failRelease = 0;

    LifetimeDriverCalls driverCalls() noexcept
    {
        LifetimeDriverCalls result;
        result.userData = this;
        result.pushContext = pushContext;
        result.popContext = popContext;
        result.destroyStream = destroyStream;
        result.releasePrimaryContext = releasePrimaryContext;
        return result;
    }

    int count(const std::string &operation) const
    {
        return static_cast<int>(
            std::count(calls.begin(), calls.end(), operation));
    }

    static int pushContext(void *data, const OpaqueHandle context) noexcept
    {
        auto &driver = *static_cast<FakeLifetimeDriver *>(data);
        driver.calls.emplace_back("push");
        if (driver.failPush > 0)
        {
            --driver.failPush;
            return kFailure;
        }
        driver.contextStack.push_back(context);
        return 0;
    }

    static int popContext(void *data, OpaqueHandle *context) noexcept
    {
        auto &driver = *static_cast<FakeLifetimeDriver *>(data);
        driver.calls.emplace_back("pop");
        if (driver.failPop > 0)
        {
            --driver.failPop;
            return kFailure;
        }
        if (driver.contextStack.empty())
            return kFailure;
        *context = driver.contextStack.back();
        driver.contextStack.pop_back();
        return 0;
    }

    static int destroyStream(void *data, const OpaqueHandle) noexcept
    {
        auto &driver = *static_cast<FakeLifetimeDriver *>(data);
        driver.calls.emplace_back("destroy_stream");
        if (driver.failDestroy > 0)
        {
            --driver.failDestroy;
            return kFailure;
        }
        return 0;
    }

    static int releasePrimaryContext(void *data, const int) noexcept
    {
        auto &driver = *static_cast<FakeLifetimeDriver *>(data);
        driver.calls.emplace_back("release_primary");
        if (driver.failRelease > 0)
        {
            --driver.failRelease;
            return kFailure;
        }
        return 0;
    }
};

TEST(CudaBackendStubTest, PublicContextIsMoveOnlyAndHidesImplementation)
{
    static_assert(!std::is_copy_constructible<
                  slimed::cuda_backend::DeviceContext>::value);
    static_assert(!std::is_copy_assignable<
                  slimed::cuda_backend::DeviceContext>::value);
    static_assert(std::is_move_constructible<
                  slimed::cuda_backend::DeviceContext>::value);
    static_assert(std::is_move_assignable<
                  slimed::cuda_backend::DeviceContext>::value);
    SUCCEED();
}

TEST(CudaBackendStubTest, QueryReportsStructuredCompileTimeUnavailability)
{
    const auto report = slimed::cuda_backend::query_backend(3);

    EXPECT_FALSE(report.compiled);
    EXPECT_FALSE(report.available);
    EXPECT_EQ(report.device.requestedDeviceOrdinal, 3);
    EXPECT_EQ(report.error.code,
              slimed::cuda_backend::ErrorCode::NotCompiled);
    EXPECT_EQ(report.error.operation, "compile_time");
    EXPECT_EQ(report.error.nativeCode, 0);
    EXPECT_FALSE(report.error.message.empty());
}

TEST(CudaBackendStubTest, ContextCreationNeverReturnsPartialStubContext)
{
    auto result = slimed::cuda_backend::create_device_context();

    EXPECT_FALSE(result.ok());
    EXPECT_EQ(result.context, nullptr);
    EXPECT_FALSE(result.report.available);
    EXPECT_EQ(result.report.error.code,
              slimed::cuda_backend::ErrorCode::NotCompiled);
}

TEST(CudaBackendStubTest, ErrorCodeNamesAreStableAndComplete)
{
    using slimed::cuda_backend::ErrorCode;
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(ErrorCode::None),
                 "none");
    EXPECT_STREQ(
        slimed::cuda_backend::error_code_name(ErrorCode::NotCompiled),
        "not_compiled");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(ErrorCode::NoDevice),
                 "no_device");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::InsufficientDriver),
                 "insufficient_driver");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::InvalidDeviceOrdinal),
                 "invalid_device_ordinal");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::InitializationFailed),
                 "initialization_failed");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::CapabilityQueryFailed),
                 "capability_query_failed");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::ContextCreationFailed),
                 "context_creation_failed");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::StreamCreationFailed),
                 "stream_creation_failed");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::ContextStackFailed),
                 "context_stack_failed");
    EXPECT_STREQ(slimed::cuda_backend::error_code_name(
                     ErrorCode::CleanupFailed),
                 "cleanup_failed");
}

TEST(CudaBackendLifetimeTest,
     SuccessfulCleanupRestoresPrecedingContextAndReleasesExactlyOnce)
{
    FakeLifetimeDriver driver;
    ContextLifetime lifetime(driver.driverCalls());
    lifetime.markPrimaryContextRetained(3, 22);
    lifetime.markStreamCreated(33);

    EXPECT_TRUE(lifetime.cleanup().ok());
    EXPECT_EQ(driver.contextStack, std::vector<OpaqueHandle>({11}));
    EXPECT_EQ(driver.count("push"), 1);
    EXPECT_EQ(driver.count("destroy_stream"), 1);
    EXPECT_EQ(driver.count("pop"), 1);
    EXPECT_EQ(driver.count("release_primary"), 1);
    EXPECT_FALSE(lifetime.pushed());
    EXPECT_FALSE(lifetime.ownsStream());
    EXPECT_FALSE(lifetime.retained());

    EXPECT_TRUE(lifetime.cleanup().ok());
    EXPECT_EQ(driver.count("destroy_stream"), 1);
    EXPECT_EQ(driver.count("release_primary"), 1);
}

TEST(CudaBackendLifetimeTest,
     FailedCreationPopIsRetriedWithoutAnExtraPush)
{
    FakeLifetimeDriver driver;
    ContextLifetime lifetime(driver.driverCalls());
    lifetime.markPrimaryContextRetained(3, 22);
    ASSERT_TRUE(lifetime.pushContext().ok());
    lifetime.markStreamCreated(33);
    driver.failPop = 1;

    const auto popFailure = lifetime.popContext();
    EXPECT_EQ(popFailure.operation, LifetimeOperation::PopContext);
    EXPECT_TRUE(lifetime.pushed());
    EXPECT_EQ(driver.contextStack,
              std::vector<OpaqueHandle>({11, 22}));

    EXPECT_TRUE(lifetime.cleanup().ok());
    EXPECT_EQ(driver.contextStack, std::vector<OpaqueHandle>({11}));
    EXPECT_EQ(driver.count("push"), 1);
    EXPECT_EQ(driver.count("destroy_stream"), 1);
    EXPECT_EQ(driver.count("pop"), 2);
    EXPECT_EQ(driver.count("release_primary"), 1);
}

TEST(CudaBackendLifetimeTest,
     PushFailureDefersDestructionAndReleaseUntilRetry)
{
    FakeLifetimeDriver driver;
    ContextLifetime lifetime(driver.driverCalls());
    lifetime.markPrimaryContextRetained(3, 22);
    lifetime.markStreamCreated(33);
    driver.failPush = 1;

    const auto failure = lifetime.cleanup();
    EXPECT_EQ(failure.operation, LifetimeOperation::PushContext);
    EXPECT_TRUE(lifetime.retained());
    EXPECT_TRUE(lifetime.ownsStream());
    EXPECT_EQ(driver.contextStack, std::vector<OpaqueHandle>({11}));
    EXPECT_EQ(driver.count("destroy_stream"), 0);
    EXPECT_EQ(driver.count("release_primary"), 0);

    EXPECT_TRUE(lifetime.cleanup().ok());
    EXPECT_EQ(driver.contextStack, std::vector<OpaqueHandle>({11}));
    EXPECT_EQ(driver.count("destroy_stream"), 1);
    EXPECT_EQ(driver.count("release_primary"), 1);
}

TEST(CudaBackendLifetimeTest,
     DestroyFailureRestoresContextAndRetriesWithoutDoubleRelease)
{
    FakeLifetimeDriver driver;
    ContextLifetime lifetime(driver.driverCalls());
    lifetime.markPrimaryContextRetained(3, 22);
    lifetime.markStreamCreated(33);
    driver.failDestroy = 1;

    const auto failure = lifetime.cleanup();
    EXPECT_EQ(failure.operation, LifetimeOperation::DestroyStream);
    EXPECT_EQ(driver.contextStack, std::vector<OpaqueHandle>({11}));
    EXPECT_TRUE(lifetime.retained());
    EXPECT_TRUE(lifetime.ownsStream());
    EXPECT_EQ(driver.count("release_primary"), 0);

    EXPECT_TRUE(lifetime.cleanup().ok());
    EXPECT_EQ(driver.contextStack, std::vector<OpaqueHandle>({11}));
    EXPECT_EQ(driver.count("destroy_stream"), 2);
    EXPECT_EQ(driver.count("release_primary"), 1);
}

TEST(CudaBackendLifetimeTest,
     ReleaseFailureRetriesOnlyTheRetainedReference)
{
    FakeLifetimeDriver driver;
    ContextLifetime lifetime(driver.driverCalls());
    lifetime.markPrimaryContextRetained(3, 22);
    lifetime.markStreamCreated(33);
    driver.failRelease = 1;

    const auto failure = lifetime.cleanup();
    EXPECT_EQ(failure.operation,
              LifetimeOperation::ReleasePrimaryContext);
    EXPECT_EQ(driver.contextStack, std::vector<OpaqueHandle>({11}));
    EXPECT_TRUE(lifetime.retained());
    EXPECT_FALSE(lifetime.ownsStream());

    EXPECT_TRUE(lifetime.cleanup().ok());
    EXPECT_EQ(driver.count("push"), 1);
    EXPECT_EQ(driver.count("destroy_stream"), 1);
    EXPECT_EQ(driver.count("pop"), 1);
    EXPECT_EQ(driver.count("release_primary"), 2);
}

} // namespace
