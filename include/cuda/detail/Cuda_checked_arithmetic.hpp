#ifndef SLIMED_CUDA_CHECKED_ARITHMETIC_HPP
#define SLIMED_CUDA_CHECKED_ARITHMETIC_HPP

#include <cstdint>
#include <limits>

namespace slimed::cuda_residency::detail
{

inline bool checked_add(const std::uint64_t left,
                        const std::uint64_t right,
                        std::uint64_t &result) noexcept
{
    if (right > std::numeric_limits<std::uint64_t>::max() - left)
    {
        return false;
    }
    result = left + right;
    return true;
}

inline bool checked_multiply(const std::uint64_t left,
                             const std::uint64_t right,
                             std::uint64_t &result) noexcept
{
    if (left != 0 && right > std::numeric_limits<std::uint64_t>::max() / left)
    {
        return false;
    }
    result = left * right;
    return true;
}

} // namespace slimed::cuda_residency::detail

#endif
