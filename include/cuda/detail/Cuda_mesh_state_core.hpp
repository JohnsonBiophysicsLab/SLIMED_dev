#ifndef SLIMED_CUDA_MESH_STATE_CORE_HPP
#define SLIMED_CUDA_MESH_STATE_CORE_HPP

#include "cuda/Cuda_mesh_state.hpp"

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>

namespace slimed::cuda_residency::detail
{

using DeviceBufferHandle = std::uintptr_t;

struct DriverStatus
{
    bool success = true;
    int nativeCode = 0;
    std::string operation;
    std::string message;
};

struct DeviceOperations
{
    std::function<DriverStatus(std::size_t &, std::size_t &)> queryMemory;
    std::function<DriverStatus(std::size_t, DeviceBufferHandle &)> allocate;
    std::function<DriverStatus(DeviceBufferHandle)> release;
    std::function<DriverStatus(DeviceBufferHandle, const void *, std::size_t)>
        copyHostToDevice;
    std::function<DriverStatus()> synchronize;
};

struct MeshStateCoreResult;

class MeshStateCore final
{
  public:
    MeshStateCore(const MeshStateCore &) = delete;
    MeshStateCore &operator=(const MeshStateCore &) = delete;
    ~MeshStateCore();

    DeviceStateError ensure_resident(const RegularMeshPack &pack);
    DeviceStateError prepare_candidate(const std::vector<double> &coordinates,
                                       std::uint64_t generation);
    DeviceStateError mark_computing();
    DeviceStateError mark_validated();
    DeviceStateError commit();
    DeviceStateError rollback();
    DeviceStateError fail_candidate(const std::string &operation,
                                    const std::string &message);
    DeviceStateError recover();
    DeviceStateError close();
    const DeviceStateReport &report() const noexcept;

    DeviceBufferHandle accepted_coordinate_handle_for_testing() const noexcept;

  private:
    struct Impl;
    MeshStateCore(DeviceOperations operations, DeviceStateConfig config);
    std::unique_ptr<Impl> impl_;

    friend struct MeshStateCoreResult;
    friend MeshStateCoreResult create_mesh_state_core(
        DeviceOperations, const RegularMeshPack &, const DeviceStateConfig &);
};

struct MeshStateCoreResult
{
    std::unique_ptr<MeshStateCore> state;
    DeviceStateReport report;
};

MeshStateCoreResult create_mesh_state_core(
    DeviceOperations operations,
    const RegularMeshPack &pack,
    const DeviceStateConfig &config = DeviceStateConfig{});

} // namespace slimed::cuda_residency::detail

#endif
