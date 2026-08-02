#include "cuda/Cuda_backend.hpp"

#include <gtest/gtest.h>

#include <type_traits>

namespace
{

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
}

} // namespace
