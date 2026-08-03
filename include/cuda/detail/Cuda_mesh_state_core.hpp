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

struct GeometryLaunch
{
    DeviceBufferHandle evaluatedFaceIds = 0;
    DeviceBufferHandle oneRingSourceIds = 0;
    DeviceBufferHandle quadratureCoefficients = 0;
    DeviceBufferHandle shapeWeights = 0;
    DeviceBufferHandle coordinates = 0;
    DeviceBufferHandle faceAreas = 0;
    DeviceBufferHandle faceVolumes = 0;
    DeviceBufferHandle status = 0;
    DeviceBufferHandle totals = 0;
    std::uint64_t vertexCount = 0;
    std::uint64_t faceCount = 0;
    std::uint64_t evaluatedFaceCount = 0;
};

struct MembraneLaunch
{
    DeviceBufferHandle evaluatedFaceIds = 0;
    DeviceBufferHandle oneRingSourceIds = 0;
    DeviceBufferHandle spontaneousCurvatures = 0;
    DeviceBufferHandle packedParameters = 0;
    DeviceBufferHandle quadratureCoefficients = 0;
    DeviceBufferHandle shapeWeights = 0;
    DeviceBufferHandle coordinates = 0;
    DeviceBufferHandle faceAreas = 0;
    DeviceBufferHandle faceVolumes = 0;
    DeviceBufferHandle geometryTotals = 0;
    DeviceBufferHandle faceBendingEnergies = 0;
    DeviceBufferHandle faceMeanCurvatures = 0;
    DeviceBufferHandle faceNormals = 0;
    DeviceBufferHandle occurrenceForces = 0;
    DeviceBufferHandle sampleSurfaceMeasures = 0;
    DeviceBufferHandle sampleMeanCurvatures = 0;
    DeviceBufferHandle sampleNormals = 0;
    DeviceBufferHandle sampleBendingEnergies = 0;
    DeviceBufferHandle statusDiagnostics = 0;
    std::uint64_t vertexCount = 0;
    std::uint64_t faceCount = 0;
    std::uint64_t evaluatedFaceCount = 0;
};

DriverStatus release_retryable_handle(
    DeviceBufferHandle &handle,
    const std::function<DriverStatus(DeviceBufferHandle)> &release);

class StreamCleanupState final
{
  public:
    bool pending() const noexcept;
    void overlay(DeviceStateReport &report) const;
    DeviceStateError guard(const char *operation,
                           DeviceStateReport &report) const;
    DeviceStateError attempt(const std::function<DriverStatus()> &close,
                             DeviceStateReport &report);

  private:
    bool pending_ = false;
    DeviceStateError error_;
};

struct DeviceOperations
{
    std::function<DriverStatus(std::size_t &, std::size_t &)> queryMemory;
    std::function<DriverStatus(std::size_t, DeviceBufferHandle &)> allocate;
    std::function<DriverStatus(DeviceBufferHandle)> release;
    std::function<DriverStatus(DeviceBufferHandle, const void *, std::size_t)>
        copyHostToDevice;
    std::function<DriverStatus(void *, DeviceBufferHandle, std::size_t)>
        copyDeviceToHost;
    std::function<DriverStatus(const GeometryLaunch &)> computeGeometry;
    std::function<DriverStatus(const MembraneLaunch &)> computeMembrane;
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
    GeometryCandidateResult compute_candidate_geometry();
    MembraneCandidateResult compute_candidate_membrane();
    DeviceStateError mark_computing();
    DeviceStateError mark_validated();
    DeviceStateError commit();
    DeviceStateError rollback();
    DeviceStateError fail_candidate(const std::string &operation,
                                    const std::string &message);
    DeviceStateError recover();
    DeviceStateError retry_cleanup();
    DeviceStateError close();
    const DeviceStateReport &report() const noexcept;

    DeviceBufferHandle accepted_coordinate_handle_for_testing() const noexcept;
    DeviceBufferHandle candidate_coordinate_handle_for_testing() const noexcept;
    DeviceBufferHandle previous_coordinate_handle_for_testing() const noexcept;

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

struct CudaMeshStateFactory
{
    static std::unique_ptr<CudaMeshState> create(
        std::unique_ptr<MeshStateCore> core,
        DeviceStateReport report,
        std::function<DriverStatus()> closeStream);
};

} // namespace slimed::cuda_residency::detail

#endif
