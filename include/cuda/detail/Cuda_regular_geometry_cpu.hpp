#ifndef SLIMED_CUDA_REGULAR_GEOMETRY_CPU_HPP
#define SLIMED_CUDA_REGULAR_GEOMETRY_CPU_HPP

#include "cuda/Cuda_mesh_pack.hpp"

#include <vector>

namespace slimed::cuda_residency::detail
{

struct RegularGeometryCpuResult
{
    std::vector<double> faceAreas;
    std::vector<double> faceVolumes;
    double totalArea = 0.0;
    double totalVolume = 0.0;
};

/** Independent host oracle for the packed regular geometry contract. */
RegularGeometryCpuResult evaluate_regular_geometry_cpu(
    const RegularMeshPack &pack,
    const std::vector<double> &coordinates);

} // namespace slimed::cuda_residency::detail

#endif
