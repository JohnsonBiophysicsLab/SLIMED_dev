#ifndef SLIMED_CUDA_REGULAR_MEMBRANE_CPU_HPP
#define SLIMED_CUDA_REGULAR_MEMBRANE_CPU_HPP

#include "cuda/Cuda_mesh_pack.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace slimed::cuda_residency::detail
{

enum class RegularMembraneStatus : std::int32_t
{
    None = 0,
    InvalidSource = 1,
    DegenerateSample = 2,
    NonFiniteIntermediate = 3,
    NonFiniteOutput = 4,
};

const char *regular_membrane_status_name(RegularMembraneStatus status) noexcept;

/**
 * Host-side oracle for the packed regular membrane contract.
 *
 * Face arrays use declared face IDs. Sample arrays and occurrence forces use
 * evaluated-face order. Occurrence force components are ordered as
 * [bending xyz, area xyz, volume xyz]. No source-keyed scatter is performed.
 */
struct RegularMembraneCpuResult
{
    std::vector<double> faceAreas;
    std::vector<double> faceVolumes;
    std::vector<double> faceBendingEnergies;
    std::vector<double> faceMeanCurvatures;
    std::vector<double> faceNormals;
    std::vector<double> occurrenceForces;
    std::vector<double> sampleSurfaceMeasures;
    std::vector<double> sampleMeanCurvatures;
    std::vector<double> sampleNormals;
    std::vector<double> sampleBendingEnergies;
    double totalArea = 0.0;
    double totalVolume = 0.0;
    RegularMembraneStatus status = RegularMembraneStatus::None;
    std::uint64_t failedEvaluatedFace = 0;
    std::uint32_t failedSample = 0;
    std::string message;

    bool ok() const noexcept { return status == RegularMembraneStatus::None; }
};

RegularMembraneCpuResult evaluate_regular_membrane_cpu(
    const RegularMeshPack &pack,
    const std::vector<double> &coordinates);

} // namespace slimed::cuda_residency::detail

#endif
