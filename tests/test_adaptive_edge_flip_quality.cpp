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
}
} // namespace
