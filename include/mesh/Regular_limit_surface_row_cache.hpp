/**
 * @file Regular_limit_surface_row_cache.hpp
 * @brief Backend-neutral ownership for immutable regular limit-surface rows.
 */

#pragma once

#include <cstdint>
#include <memory>
#include <mutex>
#include <vector>

#include "linalg/Linear_algebra.hpp"

class Mesh;

using RegularLimitSurfaceRowTable = std::vector<std::vector<Matrix>>;

struct RegularLimitSurfaceRowCacheStats
{
    std::uint64_t fingerprint = 0;
    int buildCount = 0;
    int hitCount = 0;
    int missCount = 0;
    bool populated = false;
};

class RegularLimitSurfaceRowCache
{
  public:
    RegularLimitSurfaceRowCache() = default;

    RegularLimitSurfaceRowCache(const RegularLimitSurfaceRowCache &)
    {
        // A copied mesh starts without backend state.
    }

    RegularLimitSurfaceRowCache &operator=(const RegularLimitSurfaceRowCache &other)
    {
        if (this != &other)
        {
            invalidate();
        }
        return *this;
    }

    RegularLimitSurfaceRowCache(RegularLimitSurfaceRowCache &&other) noexcept
    {
        std::lock_guard<std::mutex> lock(other.mutex_);
        transfer_from(other);
    }

    RegularLimitSurfaceRowCache &operator=(RegularLimitSurfaceRowCache &&other) noexcept
    {
        if (this != &other)
        {
            std::scoped_lock lock(mutex_, other.mutex_);
            transfer_from(other);
        }
        return *this;
    }

    void invalidate()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        table_.reset();
        fingerprint_ = 0;
    }

  private:
    void transfer_from(RegularLimitSurfaceRowCache &other)
    {
        table_ = std::move(other.table_);
        fingerprint_ = other.fingerprint_;
        buildCount_ = other.buildCount_;
        hitCount_ = other.hitCount_;
        missCount_ = other.missCount_;
        other.fingerprint_ = 0;
        other.buildCount_ = 0;
        other.hitCount_ = 0;
        other.missCount_ = 0;
    }

    friend std::shared_ptr<const RegularLimitSurfaceRowTable>
    cached_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh);
    friend RegularLimitSurfaceRowCacheStats
    regular_limit_surface_row_cache_stats(const Mesh &mesh);

    mutable std::mutex mutex_;
    std::shared_ptr<const RegularLimitSurfaceRowTable> table_;
    std::uint64_t fingerprint_ = 0;
    int buildCount_ = 0;
    int hitCount_ = 0;
    int missCount_ = 0;
};
