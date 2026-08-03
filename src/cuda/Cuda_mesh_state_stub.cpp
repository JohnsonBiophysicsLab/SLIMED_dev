#include "cuda/Cuda_mesh_state.hpp"

namespace slimed::cuda_residency
{

namespace
{
DeviceStateError unavailable(const char *operation)
{
    return {DeviceStateErrorCode::NotCompiled, operation, 0,
            "CUDA device state is not compiled; use the explicit cuda_mesh_state_report target"};
}
} // namespace

CudaMeshStateResult create_cuda_mesh_state(const RegularMeshPack &,
                                           const DeviceStateConfig &)
{
    CudaMeshStateResult result;
    result.report.compiled = false;
    result.report.available = false;
    result.report.error = unavailable("create_cuda_mesh_state");
    return result;
}

} // namespace slimed::cuda_residency
