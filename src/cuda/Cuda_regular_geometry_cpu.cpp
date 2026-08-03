#include "cuda/detail/Cuda_regular_geometry_cpu.hpp"

#include <cmath>
#include <cstddef>

namespace slimed::cuda_residency::detail
{
namespace
{
constexpr double kLegacyVolumeQuadratureFactor = 0.16666666666;
}

RegularGeometryCpuResult evaluate_regular_geometry_cpu(
    const RegularMeshPack &pack,
    const std::vector<double> &coordinates)
{
    RegularGeometryCpuResult result;
    result.faceAreas.assign(static_cast<std::size_t>(pack.faceCount), 0.0);
    result.faceVolumes.assign(static_cast<std::size_t>(pack.faceCount), 0.0);
    for (std::size_t evaluated = 0;
         evaluated < static_cast<std::size_t>(pack.evaluatedFaceCount);
         ++evaluated)
    {
        const std::size_t face = static_cast<std::size_t>(
            pack.evaluatedFaceIds[evaluated]);
        double area = 0.0;
        double volume = 0.0;
        for (std::size_t sample = 0; sample < kQuadratureSampleCount; ++sample)
        {
            double rows[3][3]{};
            for (std::size_t row = 0; row < 3; ++row)
                for (std::size_t local = 0; local < kRegularControlCount;
                     ++local)
                {
                    const std::size_t source = static_cast<std::size_t>(
                        pack.oneRingSourceIds[
                            evaluated * kRegularControlCount + local]);
                    const double weight = pack.shapeWeights[
                        (sample * kShapeRowCount + row) * kRegularControlCount +
                        local];
                    for (std::size_t axis = 0; axis < kCoordinateAxisCount;
                         ++axis)
                        rows[row][axis] += weight * coordinates[
                            source * kCoordinateAxisCount + axis];
                }
            const double cross[3]{
                rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1],
                rows[1][2] * rows[2][0] - rows[1][0] * rows[2][2],
                rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0],
            };
            const double norm = std::sqrt(cross[0] * cross[0] +
                                          cross[1] * cross[1] +
                                          cross[2] * cross[2]);
            const double coefficient = pack.quadratureCoefficients[sample];
            area += 0.5 * coefficient * norm;
            // Preserve production Mesh's legacy first-component dot_row
            // behavior exactly.
            volume += kLegacyVolumeQuadratureFactor * coefficient *
                      rows[0][0] * cross[0];
        }
        result.faceAreas[face] = area;
        result.faceVolumes[face] = volume;
    }
    for (std::size_t face = 0; face < result.faceAreas.size(); ++face)
    {
        result.totalArea += result.faceAreas[face];
        result.totalVolume += result.faceVolumes[face];
    }
    return result;
}

} // namespace slimed::cuda_residency::detail
