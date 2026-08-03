#include <cmath>
#include <limits>

#include <gtest/gtest.h>

#include "mesh/Adaptive_edge_flip_quality.hpp"

namespace
{
using slimed::adaptive_edge_flip_proof::EdgeFlipQualityOptions;
using slimed::adaptive_edge_flip_proof::Point3;
using slimed::adaptive_edge_flip_proof::evaluate_edge_flip_quality;

TEST(AdaptiveEdgeFlipQualityProof, AcceptsClearlyImprovedPlanarHinge)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{3.0, 0.0, 0.0}};
    const Point3 c{{0.0, 1.0, 0.0}};
    const Point3 d{{1.0, -0.1, 0.0}};

    const auto result = evaluate_edge_flip_quality(a, b, c, d);

    EXPECT_TRUE(result.validOptions);
    EXPECT_TRUE(result.finiteInput);
    EXPECT_TRUE(result.originalTrianglesNondegenerate);
    EXPECT_TRUE(result.flippedTrianglesNondegenerate);
    EXPECT_TRUE(result.intrinsicDelaunayViolation);
    EXPECT_TRUE(result.minimumAngleImproved);
    EXPECT_TRUE(result.meanRatioImproved);
    EXPECT_TRUE(result.orientationPreserved);
    EXPECT_TRUE(result.accepted);
    EXPECT_GT(result.minimumAngleAfter, result.minimumAngleBefore);
    EXPECT_GE(result.minimumMeanRatioAfter,
              result.minimumMeanRatioBefore);
}

TEST(AdaptiveEdgeFlipQualityProof, RejectsDelaunayNeutralRectangleByHysteresis)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{1.0, 1.0, 0.0}};
    const Point3 c{{0.0, 1.0, 0.0}};
    const Point3 d{{1.0, 0.0, 0.0}};

    const auto result = evaluate_edge_flip_quality(a, b, c, d);

    EXPECT_TRUE(result.originalTrianglesNondegenerate);
    EXPECT_TRUE(result.flippedTrianglesNondegenerate);
    EXPECT_FALSE(result.intrinsicDelaunayViolation);
    EXPECT_FALSE(result.minimumAngleImproved);
    EXPECT_FALSE(result.accepted);
}

TEST(AdaptiveEdgeFlipQualityProof, HonorsMinimumAngleHysteresis)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{3.0, 0.0, 0.0}};
    const Point3 c{{0.0, 1.0, 0.0}};
    const Point3 d{{1.0, -0.1, 0.0}};
    const auto baseline = evaluate_edge_flip_quality(a, b, c, d);
    ASSERT_TRUE(baseline.accepted);

    EdgeFlipQualityOptions options;
    options.minimumAngleImprovementRadians =
        baseline.minimumAngleAfter - baseline.minimumAngleBefore + 1.0e-9;
    const auto result = evaluate_edge_flip_quality(a, b, c, d, options);

    EXPECT_TRUE(result.intrinsicDelaunayViolation);
    EXPECT_FALSE(result.minimumAngleImproved);
    EXPECT_FALSE(result.accepted);
}

TEST(AdaptiveEdgeFlipQualityProof, HonorsDelaunayAndMeanRatioHysteresis)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{3.0, 0.0, 0.0}};
    const Point3 c{{0.0, 1.0, 0.0}};
    const Point3 d{{1.0, -0.1, 0.0}};
    const auto baseline = evaluate_edge_flip_quality(a, b, c, d);
    ASSERT_TRUE(baseline.accepted);

    constexpr double kPi = 3.14159265358979323846;
    EdgeFlipQualityOptions delaunayOptions;
    delaunayOptions.delaunayAngleHysteresisRadians =
        baseline.oppositeAngleSumBefore - kPi + 1.0e-9;
    const auto delaunay =
        evaluate_edge_flip_quality(a, b, c, d, delaunayOptions);
    EXPECT_FALSE(delaunay.intrinsicDelaunayViolation);
    EXPECT_FALSE(delaunay.accepted);

    EdgeFlipQualityOptions ratioOptions;
    ratioOptions.minimumMeanRatioImprovement =
        baseline.minimumMeanRatioAfter - baseline.minimumMeanRatioBefore +
        1.0e-9;
    const auto ratio = evaluate_edge_flip_quality(a, b, c, d, ratioOptions);
    EXPECT_FALSE(ratio.meanRatioImproved);
    EXPECT_FALSE(ratio.accepted);
}

TEST(AdaptiveEdgeFlipQualityProof, RejectsDegenerateProposedDiagonal)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{2.0, 0.0, 0.0}};
    const Point3 c{{0.0, 1.0, 0.0}};
    const Point3 d = c;

    const auto result = evaluate_edge_flip_quality(a, b, c, d);

    EXPECT_TRUE(result.originalTrianglesNondegenerate);
    EXPECT_FALSE(result.flippedTrianglesNondegenerate);
    EXPECT_FALSE(result.accepted);
}

TEST(AdaptiveEdgeFlipQualityProof, RejectsDegenerateOriginalTriangle)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b = a;
    const Point3 c{{0.0, 1.0, 0.0}};
    const Point3 d{{1.0, -0.1, 0.0}};

    const auto result = evaluate_edge_flip_quality(a, b, c, d);

    EXPECT_FALSE(result.originalTrianglesNondegenerate);
    EXPECT_FALSE(result.accepted);
}

TEST(AdaptiveEdgeFlipQualityProof, RejectsNonplanarOrientationFailure)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{1.0, 0.0, 0.0}};
    const Point3 c{{0.0, 1.0, 1.0}};
    const Point3 d{{0.0, -1.0, 1.0}};

    const auto result = evaluate_edge_flip_quality(a, b, c, d);

    EXPECT_TRUE(result.originalTrianglesNondegenerate);
    EXPECT_TRUE(result.flippedTrianglesNondegenerate);
    EXPECT_FALSE(result.orientationPreserved);
    EXPECT_FALSE(result.accepted);
}

TEST(AdaptiveEdgeFlipQualityProof, IsInvariantUnderRigidScaleAndRelabeling)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{3.0, 0.0, 0.0}};
    const Point3 c{{0.0, 1.0, 0.0}};
    const Point3 d{{1.0, -0.1, 0.0}};
    const auto baseline = evaluate_edge_flip_quality(a, b, c, d);
    ASSERT_TRUE(baseline.accepted);

    const auto transform = [](const Point3 &point) {
        constexpr double scale = 7.25;
        return Point3{{10.0 - scale * point[1],
                       -4.0 + scale * point[0],
                       2.5 + scale * point[2]}};
    };
    const auto transformed = evaluate_edge_flip_quality(
        transform(a), transform(b), transform(c), transform(d));
    EXPECT_EQ(transformed.accepted, baseline.accepted);
    EXPECT_EQ(transformed.intrinsicDelaunayViolation,
              baseline.intrinsicDelaunayViolation);
    EXPECT_EQ(transformed.minimumAngleImproved,
              baseline.minimumAngleImproved);
    EXPECT_EQ(transformed.meanRatioImproved, baseline.meanRatioImproved);
    EXPECT_EQ(transformed.orientationPreserved,
              baseline.orientationPreserved);
    EXPECT_NEAR(transformed.minimumAngleBefore,
                baseline.minimumAngleBefore, 1.0e-14);
    EXPECT_NEAR(transformed.minimumAngleAfter,
                baseline.minimumAngleAfter, 1.0e-14);

    const auto relabeled = evaluate_edge_flip_quality(b, a, d, c);
    EXPECT_EQ(relabeled.accepted, baseline.accepted);
    EXPECT_NEAR(relabeled.oppositeAngleSumBefore,
                baseline.oppositeAngleSumBefore, 1.0e-14);
    EXPECT_NEAR(relabeled.minimumAngleBefore,
                baseline.minimumAngleBefore, 1.0e-14);
    EXPECT_NEAR(relabeled.minimumAngleAfter,
                baseline.minimumAngleAfter, 1.0e-14);
}

TEST(AdaptiveEdgeFlipQualityProof, RejectsNonfiniteInputAndInvalidOptions)
{
    const Point3 a{{0.0, 0.0, 0.0}};
    const Point3 b{{3.0, 0.0, 0.0}};
    const Point3 c{{0.0, 1.0, 0.0}};
    Point3 d{{1.0, -0.1, 0.0}};
    d[2] = std::numeric_limits<double>::infinity();
    const auto nonfinite = evaluate_edge_flip_quality(a, b, c, d);
    EXPECT_TRUE(nonfinite.validOptions);
    EXPECT_FALSE(nonfinite.finiteInput);
    EXPECT_FALSE(nonfinite.accepted);

    EdgeFlipQualityOptions options;
    options.minimumMeanRatioImprovement = -1.0;
    const auto invalid = evaluate_edge_flip_quality(a, b, c, c, options);
    EXPECT_FALSE(invalid.validOptions);
    EXPECT_FALSE(invalid.accepted);

    options = {};
    options.minimumOrientationCosine = -0.1;
    const auto unsafeOrientationOption =
        evaluate_edge_flip_quality(a, b, c, c, options);
    EXPECT_FALSE(unsafeOrientationOption.validOptions);
    EXPECT_FALSE(unsafeOrientationOption.accepted);
}
} // namespace
