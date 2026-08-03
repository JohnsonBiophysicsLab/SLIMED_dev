#include "cuda/Cuda_mesh_state.hpp"

#include <utility>

namespace slimed::cuda_residency
{

struct CudaMeshState::Impl
{
    DeviceStateReport report;
};

CudaMeshState::CudaMeshState(std::unique_ptr<Impl> impl)
    : impl_(std::move(impl))
{
}
CudaMeshState::CudaMeshState(CudaMeshState &&) noexcept = default;
CudaMeshState &CudaMeshState::operator=(CudaMeshState &&) noexcept = default;
CudaMeshState::~CudaMeshState() = default;

namespace
{
DeviceStateError unavailable(const char *operation)
{
    return {DeviceStateErrorCode::NotCompiled, operation, 0,
            "CUDA device state is not compiled; use the explicit cuda_mesh_state_report target"};
}
} // namespace

DeviceStateError CudaMeshState::ensure_resident(const RegularMeshPack &)
{
    return unavailable("ensure_resident");
}
DeviceStateError CudaMeshState::prepare_candidate(const std::vector<double> &,
                                                   std::uint64_t)
{
    return unavailable("prepare_candidate");
}
DeviceStateError CudaMeshState::mark_computing()
{
    return unavailable("mark_computing");
}
DeviceStateError CudaMeshState::mark_validated()
{
    return unavailable("mark_validated");
}
DeviceStateError CudaMeshState::commit() { return unavailable("commit"); }
DeviceStateError CudaMeshState::rollback() { return unavailable("rollback"); }
DeviceStateError CudaMeshState::fail_candidate(const std::string &,
                                                const std::string &)
{
    return unavailable("fail_candidate");
}
DeviceStateError CudaMeshState::recover() { return unavailable("recover"); }
DeviceStateError CudaMeshState::close() { return unavailable("close"); }
const DeviceStateReport &CudaMeshState::report() const noexcept
{
    return impl_->report;
}

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
