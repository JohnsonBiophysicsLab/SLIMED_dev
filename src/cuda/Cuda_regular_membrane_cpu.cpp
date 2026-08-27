#include "cuda/detail/Cuda_regular_membrane_cpu.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>

namespace slimed::cuda_residency::detail
{
namespace
{
using Vec3 = std::array<double, 3>;
using Mat3 = std::array<Vec3, 3>;

constexpr double kLegacyVolumeQuadratureFactor = 0.16666666666;

Vec3 add(const Vec3 &left, const Vec3 &right)
{
    return {left[0] + right[0], left[1] + right[1], left[2] + right[2]};
}

Vec3 subtract(const Vec3 &left, const Vec3 &right)
{
    return {left[0] - right[0], left[1] - right[1], left[2] - right[2]};
}

Vec3 scale(const Vec3 &value, double factor)
{
    return {value[0] * factor, value[1] * factor, value[2] * factor};
}

double dot(const Vec3 &left, const Vec3 &right)
{
    return left[0] * right[0] + left[1] * right[1] +
           left[2] * right[2];
}

Vec3 cross(const Vec3 &left, const Vec3 &right)
{
    return {left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0]};
}

Mat3 outer(const Vec3 &left, const Vec3 &right)
{
    Mat3 result{};
    for (std::size_t row = 0; row < 3; ++row)
        for (std::size_t column = 0; column < 3; ++column)
            result[row][column] = left[row] * right[column];
    return result;
}

void add_scaled(Mat3 &destination, const Mat3 &source, double factor)
{
    for (std::size_t row = 0; row < 3; ++row)
        for (std::size_t column = 0; column < 3; ++column)
            destination[row][column] += factor * source[row][column];
}

Vec3 transpose_multiply(const Mat3 &matrix, const Vec3 &value)
{
    Vec3 result{};
    for (std::size_t column = 0; column < 3; ++column)
        for (std::size_t row = 0; row < 3; ++row)
            result[column] += value[row] * matrix[row][column];
    return result;
}

bool finite(const Vec3 &value)
{
    return std::isfinite(value[0]) && std::isfinite(value[1]) &&
           std::isfinite(value[2]);
}

bool finite(const Mat3 &value)
{
    return finite(value[0]) && finite(value[1]) && finite(value[2]);
}

RegularMembraneCpuResult fail(RegularMembraneCpuResult result,
                              RegularMembraneStatus status,
                              std::size_t evaluated,
                              std::size_t sample,
                              const char *message)
{
    result.status = status;
    result.failedEvaluatedFace = evaluated;
    result.failedSample = static_cast<std::uint32_t>(sample);
    result.message = message;
    return result;
}

} // namespace

const char *regular_membrane_status_name(RegularMembraneStatus status) noexcept
{
    switch (status)
    {
    case RegularMembraneStatus::None: return "none";
    case RegularMembraneStatus::InvalidSource: return "invalid_source";
    case RegularMembraneStatus::DegenerateSample: return "degenerate_sample";
    case RegularMembraneStatus::NonFiniteIntermediate:
        return "nonfinite_intermediate";
    case RegularMembraneStatus::NonFiniteOutput: return "nonfinite_output";
    }
    return "unknown";
}

RegularMembraneCpuResult evaluate_regular_membrane_cpu(
    const RegularMeshPack &pack,
    const std::vector<double> &coordinates)
{
    RegularMembraneCpuResult result;
    const std::size_t faceCount = static_cast<std::size_t>(pack.faceCount);
    const std::size_t evaluatedCount =
        static_cast<std::size_t>(pack.evaluatedFaceCount);
    result.faceAreas.assign(faceCount, 0.0);
    result.faceVolumes.assign(faceCount, 0.0);
    result.faceBendingEnergies.assign(faceCount, 0.0);
    result.faceMeanCurvatures.assign(faceCount, 0.0);
    result.faceNormals.assign(faceCount * 3, 0.0);
    result.occurrenceForces.assign(
        evaluatedCount * kRegularControlCount * 9U, 0.0);
    result.sampleSurfaceMeasures.assign(
        evaluatedCount * kQuadratureSampleCount, 0.0);
    result.sampleMeanCurvatures.assign(
        evaluatedCount * kQuadratureSampleCount, 0.0);
    result.sampleNormals.assign(
        evaluatedCount * kQuadratureSampleCount * 3U, 0.0);
    result.sampleBendingEnergies.assign(
        evaluatedCount * kQuadratureSampleCount, 0.0);

    const double uSurfPerArea =
        pack.parameters.uSurf == 0.0 || pack.parameters.area0 == 0.0
            ? 0.0
            : pack.parameters.uSurf / pack.parameters.area0;
    const double uVol =
        pack.parameters.uVol == 0.0 || pack.parameters.vol0 == 0.0
            ? 0.0
            : pack.parameters.uVol / pack.parameters.vol0;
    const double areaFactor =
        uSurfPerArea * (pack.parameters.area - pack.parameters.area0);
    const double volumeFactor =
        uVol * (pack.parameters.vol - pack.parameters.vol0) / 3.0;

    for (std::size_t evaluated = 0; evaluated < evaluatedCount; ++evaluated)
    {
        const std::int32_t faceId = pack.evaluatedFaceIds[evaluated];
        if (faceId < 0 || static_cast<std::size_t>(faceId) >= faceCount)
            return fail(std::move(result),
                        RegularMembraneStatus::InvalidSource, evaluated, 0,
                        "evaluated face ID is outside the declared face range");
        const std::size_t face = static_cast<std::size_t>(faceId);
        Vec3 accumulatedNormal{};
        for (std::size_t sample = 0; sample < kQuadratureSampleCount; ++sample)
        {
            Vec3 rows[kShapeRowCount]{};
            for (std::size_t row = 0; row < kShapeRowCount; ++row)
                for (std::size_t local = 0; local < kRegularControlCount;
                     ++local)
                {
                    const std::int32_t sourceId = pack.oneRingSourceIds[
                        evaluated * kRegularControlCount + local];
                    if (sourceId < 0 ||
                        static_cast<std::size_t>(sourceId) >=
                            static_cast<std::size_t>(pack.vertexCount))
                        return fail(std::move(result),
                                    RegularMembraneStatus::InvalidSource,
                                    evaluated, sample,
                                    "one-ring source ID is outside the vertex range");
                    const double weight = pack.shapeWeights[
                        (sample * kShapeRowCount + row) *
                            kRegularControlCount +
                        local];
                    const std::size_t source =
                        static_cast<std::size_t>(sourceId);
                    for (std::size_t axis = 0; axis < 3; ++axis)
                        rows[row][axis] +=
                            weight * coordinates[source * 3 + axis];
                }

            const Vec3 &x = rows[0];
            const Vec3 &a_1 = rows[1];
            const Vec3 &a_2 = rows[2];
            const Vec3 &a_11 = rows[3];
            const Vec3 &a_22 = rows[4];
            const Vec3 &a_12 = rows[5];
            const Vec3 &a_21 = rows[6];
            const Vec3 xa = cross(a_1, a_2);
            const double sqa = std::sqrt(dot(xa, xa));
            if (!(sqa > 0.0) || !std::isfinite(sqa))
                return fail(std::move(result),
                            RegularMembraneStatus::DegenerateSample,
                            evaluated, sample,
                            "regular membrane sample has zero or nonfinite surface measure");
            const double inverseSqa = 1.0 / sqa;
            const double inverseSqaSquared = inverseSqa * inverseSqa;
            const Vec3 xa_1 = add(cross(a_11, a_2), cross(a_1, a_21));
            const Vec3 xa_2 = add(cross(a_12, a_2), cross(a_1, a_22));
            const double sqa_1 = dot(xa, xa_1) * inverseSqa;
            const double sqa_2 = dot(xa, xa_2) * inverseSqa;
            const Vec3 a_3 = scale(xa, inverseSqa);
            const Vec3 a_31 = scale(
                subtract(scale(xa_1, sqa), scale(xa, sqa_1)),
                inverseSqaSquared);
            const Vec3 a_32 = scale(
                subtract(scale(xa_2, sqa), scale(xa, sqa_2)),
                inverseSqaSquared);
            const Vec3 a2x3 = cross(a_2, a_3);
            const Vec3 a3x1 = cross(a_3, a_1);
            const Vec3 a1 = scale(a2x3, inverseSqa);
            const Vec3 a2 = scale(a3x1, inverseSqa);
            const Vec3 a11 = scale(
                subtract(scale(add(cross(a_21, a_3), cross(a_2, a_31)),
                                     sqa),
                         scale(a2x3, sqa_1)),
                inverseSqaSquared);
            const Vec3 a12 = scale(
                subtract(scale(add(cross(a_22, a_3), cross(a_2, a_32)),
                                     sqa),
                         scale(a2x3, sqa_2)),
                inverseSqaSquared);
            const Vec3 a21 = scale(
                subtract(scale(add(cross(a_31, a_1), cross(a_3, a_11)),
                                     sqa),
                         scale(a3x1, sqa_1)),
                inverseSqaSquared);
            const Vec3 a22 = scale(
                subtract(scale(add(cross(a_32, a_1), cross(a_3, a_12)),
                                     sqa),
                         scale(a3x1, sqa_2)),
                inverseSqaSquared);
            const double meanCurvature =
                0.5 * (dot(a1, a_31) + dot(a2, a_32));
            const double curvatureDifference =
                2.0 * meanCurvature -
                pack.evaluatedFaceSpontaneousCurvature[evaluated];
            const double bendingEnergy =
                0.5 * pack.parameters.kCurv * sqa *
                curvatureDifference * curvatureDifference;

            const double bendGradientFactor =
                -pack.parameters.kCurv * curvatureDifference;
            const double bendAreaFactor =
                0.5 * pack.parameters.kCurv * curvatureDifference *
                curvatureDifference;
            const Vec3 n1Bend = add(
                scale(add(scale(a_31, dot(a1, a1)),
                          scale(a_32, dot(a1, a2))),
                      bendGradientFactor),
                scale(a1, bendAreaFactor));
            const Vec3 n2Bend = add(
                scale(add(scale(a_31, dot(a2, a1)),
                          scale(a_32, dot(a2, a2))),
                      bendGradientFactor),
                scale(a2, bendAreaFactor));
            const Vec3 m1Bend =
                scale(a1, pack.parameters.kCurv * curvatureDifference);
            const Vec3 m2Bend =
                scale(a2, pack.parameters.kCurv * curvatureDifference);
            const Vec3 n1Area = scale(a1, areaFactor);
            const Vec3 n2Area = scale(a2, areaFactor);
            const Vec3 n1Volume = scale(
                subtract(scale(a1, dot(x, a_3)),
                         scale(a_3, dot(x, a1))),
                volumeFactor);
            const Vec3 n2Volume = scale(
                subtract(scale(a2, dot(x, a_3)),
                         scale(a_3, dot(x, a2))),
                volumeFactor);

            if (!finite(xa_1) || !finite(xa_2) || !finite(a_3) ||
                !finite(a_31) || !finite(a_32) || !finite(a1) ||
                !finite(a2) || !finite(a11) || !finite(a12) ||
                !finite(a21) || !finite(a22) ||
                !std::isfinite(meanCurvature) ||
                !std::isfinite(bendingEnergy) || !finite(n1Bend) ||
                !finite(n2Bend) || !finite(m1Bend) || !finite(m2Bend) ||
                !finite(n1Area) || !finite(n2Area) || !finite(n1Volume) ||
                !finite(n2Volume))
                return fail(std::move(result),
                            RegularMembraneStatus::NonFiniteIntermediate,
                            evaluated, sample,
                            "regular membrane intermediate is nonfinite");

            const double coefficient = pack.quadratureCoefficients[sample];
            const double halfCoefficient = 0.5 * coefficient;
            result.faceAreas[face] += halfCoefficient * sqa;
            result.faceVolumes[face] +=
                kLegacyVolumeQuadratureFactor * coefficient * x[0] * xa[0];
            result.faceBendingEnergies[face] +=
                halfCoefficient * bendingEnergy;
            result.faceMeanCurvatures[face] +=
                halfCoefficient * meanCurvature;
            accumulatedNormal =
                add(accumulatedNormal, scale(a_3, halfCoefficient));
            const std::size_t sampleIndex =
                evaluated * kQuadratureSampleCount + sample;
            result.sampleSurfaceMeasures[sampleIndex] = sqa;
            result.sampleMeanCurvatures[sampleIndex] = meanCurvature;
            result.sampleBendingEnergies[sampleIndex] = bendingEnergy;
            for (std::size_t axis = 0; axis < 3; ++axis)
                result.sampleNormals[sampleIndex * 3 + axis] = a_3[axis];

            for (std::size_t local = 0; local < kRegularControlCount;
                 ++local)
            {
                const double *weights = &pack.shapeWeights[
                    sample * kShapeRowCount * kRegularControlCount + local];
                const double sf0 = weights[0 * kRegularControlCount];
                const double sf1 = weights[1 * kRegularControlCount];
                const double sf2 = weights[2 * kRegularControlCount];
                const double sf3 = weights[3 * kRegularControlCount];
                const double sf4 = weights[4 * kRegularControlCount];
                const double sf5 = weights[5 * kRegularControlCount];
                const double sf6 = weights[6 * kRegularControlCount];
                Mat3 da1{};
                add_scaled(da1, outer(a1, a_3), -sf3);
                add_scaled(da1, outer(a11, a_3), -sf1);
                add_scaled(da1, outer(a1, a_31), -sf1);
                add_scaled(da1, outer(a2, a_3), -sf6);
                add_scaled(da1, outer(a21, a_3), -sf2);
                add_scaled(da1, outer(a2, a_31), -sf2);
                Mat3 da2{};
                add_scaled(da2, outer(a1, a_3), -sf5);
                add_scaled(da2, outer(a12, a_3), -sf1);
                add_scaled(da2, outer(a1, a_32), -sf1);
                add_scaled(da2, outer(a2, a_3), -sf4);
                add_scaled(da2, outer(a22, a_3), -sf2);
                add_scaled(da2, outer(a2, a_32), -sf2);
                Vec3 bending = add(
                    add(transpose_multiply(da1, m1Bend),
                        transpose_multiply(da2, m2Bend)),
                    add(scale(n1Bend, sf1), scale(n2Bend, sf2)));
                bending = scale(bending, -sqa * halfCoefficient);
                Vec3 area = scale(
                    add(scale(n1Area, sf1), scale(n2Area, sf2)),
                    -sqa * halfCoefficient);
                Vec3 volume = add(
                    add(scale(n1Volume, sf1), scale(n2Volume, sf2)),
                    scale(a_3, volumeFactor * sf0));
                volume = scale(volume, -sqa * halfCoefficient);
                if (!finite(da1) || !finite(da2) || !finite(bending) ||
                    !finite(area) || !finite(volume))
                    return fail(std::move(result),
                                RegularMembraneStatus::NonFiniteOutput,
                                evaluated, sample,
                                "regular membrane occurrence force is nonfinite");
                const std::size_t base =
                    (evaluated * kRegularControlCount + local) * 9U;
                for (std::size_t axis = 0; axis < 3; ++axis)
                {
                    result.occurrenceForces[base + axis] += bending[axis];
                    result.occurrenceForces[base + 3 + axis] += area[axis];
                    result.occurrenceForces[base + 6 + axis] += volume[axis];
                }
            }
        }
        const double normalNorm = std::sqrt(dot(accumulatedNormal,
                                                accumulatedNormal));
        if (!(normalNorm > 0.0) || !std::isfinite(normalNorm))
            return fail(std::move(result),
                        RegularMembraneStatus::DegenerateSample, evaluated,
                        kQuadratureSampleCount,
                        "integrated face normal is zero or nonfinite");
        accumulatedNormal = scale(accumulatedNormal, 1.0 / normalNorm);
        for (std::size_t axis = 0; axis < 3; ++axis)
            result.faceNormals[face * 3 + axis] = accumulatedNormal[axis];
    }
    for (std::size_t face = 0; face < faceCount; ++face)
    {
        result.totalArea += result.faceAreas[face];
        result.totalVolume += result.faceVolumes[face];
    }
    const auto allFinite = [](const std::vector<double> &values) {
        return std::all_of(values.begin(), values.end(),
                           [](double value) { return std::isfinite(value); });
    };
    if (!allFinite(result.faceAreas) || !allFinite(result.faceVolumes) ||
        !allFinite(result.faceBendingEnergies) ||
        !allFinite(result.faceMeanCurvatures) ||
        !allFinite(result.faceNormals) || !allFinite(result.occurrenceForces) ||
        !allFinite(result.sampleSurfaceMeasures) ||
        !allFinite(result.sampleMeanCurvatures) ||
        !allFinite(result.sampleNormals) ||
        !allFinite(result.sampleBendingEnergies) ||
        !std::isfinite(result.totalArea) ||
        !std::isfinite(result.totalVolume))
        return fail(std::move(result),
                    RegularMembraneStatus::NonFiniteOutput, 0, 0,
                    "regular membrane result contains a nonfinite value");
    return result;
}

} // namespace slimed::cuda_residency::detail
