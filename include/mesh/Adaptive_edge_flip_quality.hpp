/**
 * @file Adaptive_edge_flip_quality.hpp
 * @brief Side-effect-free proof metric for a single oriented edge-flip hinge.
 *
 * This header does not select edges or mutate Mesh topology. It exists only
 * to make the proposed geometric feasibility gate independently testable.
 */

#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

namespace slimed::adaptive_edge_flip_proof
{
using Point3 = std::array<double, 3>;

struct EdgeFlipQualityOptions
{
    /** Required excess over pi in the old edge's opposite-angle sum. */
    double delaunayAngleHysteresisRadians = 1.0e-6;

    /** Required increase in the worst angle of the two-triangle hinge. */
    double minimumAngleImprovementRadians = 1.0e-6;

    /** Required increase in the worse of the two mean-ratio qualities. */
    double minimumMeanRatioImprovement = 0.0;

    /** Minimum dimensionless double-area / maximum-edge-squared ratio. */
    double relativeDegeneracyTolerance = 1.0e-12;

    /** Minimum cosine between each proposed normal and the old mean normal. */
    double minimumOrientationCosine = 0.0;
};

struct EdgeFlipQualityEvaluation
{
    bool validOptions = false;
    bool finiteInput = false;
    bool originalTrianglesNondegenerate = false;
    bool flippedTrianglesNondegenerate = false;
    bool intrinsicDelaunayViolation = false;
    bool minimumAngleImproved = false;
    bool meanRatioImproved = false;
    bool orientationPreserved = false;
    bool accepted = false;

    double oppositeAngleSumBefore =
        std::numeric_limits<double>::quiet_NaN();
    double minimumAngleBefore =
        std::numeric_limits<double>::quiet_NaN();
    double minimumAngleAfter =
        std::numeric_limits<double>::quiet_NaN();
    double minimumMeanRatioBefore =
        std::numeric_limits<double>::quiet_NaN();
    double minimumMeanRatioAfter =
        std::numeric_limits<double>::quiet_NaN();
};

namespace detail
{
inline Point3 subtract(const Point3 &left, const Point3 &right)
{
    return {{left[0] - right[0],
             left[1] - right[1],
             left[2] - right[2]}};
}

inline double dot(const Point3 &left, const Point3 &right)
{
    return left[0] * right[0] +
           left[1] * right[1] +
           left[2] * right[2];
}

inline Point3 cross(const Point3 &left, const Point3 &right)
{
    return {{left[1] * right[2] - left[2] * right[1],
             left[2] * right[0] - left[0] * right[2],
             left[0] * right[1] - left[1] * right[0]}};
}

inline double norm(const Point3 &value)
{
    return std::sqrt(dot(value, value));
}

inline bool finite(const Point3 &value)
{
    return std::isfinite(value[0]) &&
           std::isfinite(value[1]) &&
           std::isfinite(value[2]);
}

inline double angle(const Point3 &left, const Point3 &right)
{
    const double denominator = norm(left) * norm(right);
    if (!(denominator > 0.0) || !std::isfinite(denominator))
    {
        return std::numeric_limits<double>::quiet_NaN();
    }
    const double cosine = std::clamp(dot(left, right) / denominator,
                                     -1.0,
                                     1.0);
    return std::acos(cosine);
}

struct TriangleMetrics
{
    bool nondegenerate = false;
    double minimumAngle = std::numeric_limits<double>::quiet_NaN();
    double meanRatio = std::numeric_limits<double>::quiet_NaN();
    Point3 orientedDoubleArea{{0.0, 0.0, 0.0}};
};

inline TriangleMetrics triangle_metrics(const Point3 &first,
                                        const Point3 &second,
                                        const Point3 &third,
                                        const double relativeTolerance)
{
    TriangleMetrics metrics;
    const Point3 firstToSecond = subtract(second, first);
    const Point3 firstToThird = subtract(third, first);
    const Point3 secondToThird = subtract(third, second);
    metrics.orientedDoubleArea = cross(firstToSecond, firstToThird);

    const double firstEdgeSquared = dot(firstToSecond, firstToSecond);
    const double secondEdgeSquared = dot(firstToThird, firstToThird);
    const double thirdEdgeSquared = dot(secondToThird, secondToThird);
    const double maximumEdgeSquared = std::max(
        firstEdgeSquared,
        std::max(secondEdgeSquared, thirdEdgeSquared));
    const double doubleArea = norm(metrics.orientedDoubleArea);
    metrics.nondegenerate =
        std::isfinite(doubleArea) &&
        std::isfinite(maximumEdgeSquared) &&
        maximumEdgeSquared > 0.0 &&
        doubleArea / maximumEdgeSquared > relativeTolerance;
    if (!metrics.nondegenerate)
    {
        return metrics;
    }

    const double firstAngle = angle(firstToSecond, firstToThird);
    const double secondAngle = angle(subtract(first, second),
                                     subtract(third, second));
    const double thirdAngle = angle(subtract(first, third),
                                    subtract(second, third));
    metrics.minimumAngle = std::min(firstAngle,
                                    std::min(secondAngle, thirdAngle));
    constexpr double kTwoSqrtThree = 3.4641016151377545871;
    metrics.meanRatio =
        kTwoSqrtThree * doubleArea /
        (firstEdgeSquared + secondEdgeSquared + thirdEdgeSquared);
    return metrics;
}

inline bool preserves_orientation(const TriangleMetrics &firstBefore,
                                  const TriangleMetrics &secondBefore,
                                  const TriangleMetrics &firstAfter,
                                  const TriangleMetrics &secondAfter,
                                  const double minimumCosine)
{
    const Point3 reference{{
        firstBefore.orientedDoubleArea[0] +
            secondBefore.orientedDoubleArea[0],
        firstBefore.orientedDoubleArea[1] +
            secondBefore.orientedDoubleArea[1],
        firstBefore.orientedDoubleArea[2] +
            secondBefore.orientedDoubleArea[2],
    }};
    const double referenceNorm = norm(reference);
    const double firstAfterNorm = norm(firstAfter.orientedDoubleArea);
    const double secondAfterNorm = norm(secondAfter.orientedDoubleArea);
    if (!(referenceNorm > 0.0) || !(firstAfterNorm > 0.0) ||
        !(secondAfterNorm > 0.0))
    {
        return false;
    }
    return dot(firstAfter.orientedDoubleArea, reference) >
               minimumCosine * firstAfterNorm * referenceNorm &&
           dot(secondAfter.orientedDoubleArea, reference) >
               minimumCosine * secondAfterNorm * referenceNorm;
}
} // namespace detail

/**
 * Evaluate the flip of the shared edge (a,b).
 *
 * The old oriented faces must be (a,b,c) and (b,a,d). The proposed oriented
 * faces are (c,d,b) and (d,c,a), which replace diagonal (a,b) with (c,d).
 * Acceptance requires a hysteretic intrinsic-Delaunay violation, improvement
 * of the worst triangle angle and mean-ratio quality, finite nondegenerate
 * triangles, and preservation of the local orientation.
 */
inline EdgeFlipQualityEvaluation evaluate_edge_flip_quality(
    const Point3 &a,
    const Point3 &b,
    const Point3 &c,
    const Point3 &d,
    const EdgeFlipQualityOptions &options = {})
{
    EdgeFlipQualityEvaluation result;
    constexpr double kPi = 3.14159265358979323846;
    result.validOptions =
        std::isfinite(options.delaunayAngleHysteresisRadians) &&
        options.delaunayAngleHysteresisRadians >= 0.0 &&
        std::isfinite(options.minimumAngleImprovementRadians) &&
        options.minimumAngleImprovementRadians >= 0.0 &&
        std::isfinite(options.minimumMeanRatioImprovement) &&
        options.minimumMeanRatioImprovement >= 0.0 &&
        std::isfinite(options.relativeDegeneracyTolerance) &&
        options.relativeDegeneracyTolerance >= 0.0 &&
        std::isfinite(options.minimumOrientationCosine) &&
        options.minimumOrientationCosine >= -1.0 &&
        options.minimumOrientationCosine < 1.0;
    if (!result.validOptions)
    {
        return result;
    }

    result.finiteInput = detail::finite(a) && detail::finite(b) &&
                         detail::finite(c) && detail::finite(d);
    if (!result.finiteInput)
    {
        return result;
    }

    const detail::TriangleMetrics firstBefore =
        detail::triangle_metrics(a, b, c,
                                 options.relativeDegeneracyTolerance);
    const detail::TriangleMetrics secondBefore =
        detail::triangle_metrics(b, a, d,
                                 options.relativeDegeneracyTolerance);
    result.originalTrianglesNondegenerate =
        firstBefore.nondegenerate && secondBefore.nondegenerate;
    if (!result.originalTrianglesNondegenerate)
    {
        return result;
    }

    result.oppositeAngleSumBefore =
        detail::angle(detail::subtract(a, c), detail::subtract(b, c)) +
        detail::angle(detail::subtract(b, d), detail::subtract(a, d));
    result.intrinsicDelaunayViolation =
        result.oppositeAngleSumBefore >
        kPi + options.delaunayAngleHysteresisRadians;

    const detail::TriangleMetrics firstAfter =
        detail::triangle_metrics(c, d, b,
                                 options.relativeDegeneracyTolerance);
    const detail::TriangleMetrics secondAfter =
        detail::triangle_metrics(d, c, a,
                                 options.relativeDegeneracyTolerance);
    result.flippedTrianglesNondegenerate =
        firstAfter.nondegenerate && secondAfter.nondegenerate;
    if (!result.flippedTrianglesNondegenerate)
    {
        return result;
    }

    result.minimumAngleBefore = std::min(firstBefore.minimumAngle,
                                         secondBefore.minimumAngle);
    result.minimumAngleAfter = std::min(firstAfter.minimumAngle,
                                        secondAfter.minimumAngle);
    result.minimumMeanRatioBefore = std::min(firstBefore.meanRatio,
                                             secondBefore.meanRatio);
    result.minimumMeanRatioAfter = std::min(firstAfter.meanRatio,
                                            secondAfter.meanRatio);
    result.minimumAngleImproved =
        result.minimumAngleAfter >
        result.minimumAngleBefore +
            options.minimumAngleImprovementRadians;
    result.meanRatioImproved =
        result.minimumMeanRatioAfter >=
        result.minimumMeanRatioBefore +
            options.minimumMeanRatioImprovement;
    result.orientationPreserved = detail::preserves_orientation(
        firstBefore,
        secondBefore,
        firstAfter,
        secondAfter,
        options.minimumOrientationCosine);

    result.accepted = result.intrinsicDelaunayViolation &&
                      result.minimumAngleImproved &&
                      result.meanRatioImproved &&
                      result.orientationPreserved;
    return result;
}
} // namespace slimed::adaptive_edge_flip_proof
