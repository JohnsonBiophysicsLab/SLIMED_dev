#include <cmath>
#include <stdexcept>
#include <vector>

#include <gtest/gtest.h>

#include "Parameters.hpp"
#include "mesh/Gauss_quadrature.hpp"
#include "mesh/Limit_surface_evaluator.hpp"
#include "mesh/Mesh.hpp"

namespace
{
constexpr double kTolerance = 1.0e-12;

double row_sum(const Matrix &matrix, const int row)
{
    double sum = 0.0;
    for (int col = 0; col < matrix.ncol(); ++col)
    {
        sum += matrix.get(row, col);
    }
    return sum;
}

double column_sum(const Matrix &matrix, const int col)
{
    double sum = 0.0;
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        sum += matrix.get(row, col);
    }
    return sum;
}

int count_ghost_vertices(const Mesh &mesh)
{
    int count = 0;
    for (const Vertex &vertex : mesh.vertices)
    {
        if (vertex.isGhost)
        {
            ++count;
        }
    }
    return count;
}

int count_ghost_faces(const Mesh &mesh)
{
    int count = 0;
    for (const Face &face : mesh.faces)
    {
        if (face.isGhost)
        {
            ++count;
        }
    }
    return count;
}

void expect_row_stochastic(const Matrix &matrix)
{
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        SCOPED_TRACE(row);
        EXPECT_NEAR(row_sum(matrix, row), 1.0, kTolerance);
        for (int col = 0; col < matrix.ncol(); ++col)
        {
            EXPECT_GE(matrix.get(row, col), -kTolerance);
        }
    }
}

void expect_selection_rows(const Matrix &matrix)
{
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        int selectedColumnCount = 0;
        for (int col = 0; col < matrix.ncol(); ++col)
        {
            const double value = matrix.get(row, col);
            if (std::abs(value) > kTolerance)
            {
                ++selectedColumnCount;
                EXPECT_NEAR(value, 1.0, kTolerance);
            }
        }
        EXPECT_EQ(selectedColumnCount, 1);
    }
}

Matrix make_deterministic_regular_control_points()
{
    Matrix controlPoints(12, 3, true);
    for (int control = 0; control < controlPoints.nrow(); ++control)
    {
        controlPoints.set(control, 0, 0.25 + 0.5 * control);
        controlPoints.set(control, 1, -1.0 + 0.125 * control * control);
        controlPoints.set(control, 2, 2.0 - 0.2 * control);
    }
    return controlPoints;
}

void expect_column_matches_row(const Matrix &column,
                               const Matrix &rows,
                               const int row)
{
    ASSERT_EQ(column.nrow(), 3);
    ASSERT_EQ(column.ncol(), 1);
    ASSERT_EQ(rows.ncol(), 3);
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_DOUBLE_EQ(column.get(axis, 0), rows.get(row, axis));
    }
}

struct AreaVolume
{
    double area = 0.0;
    double volume = 0.0;
};

constexpr double kLegacyVolumeQuadratureFactor = 0.16666666666;

Matrix make_one_ring_control_points(const Mesh &mesh, const Face &face)
{
    Matrix controlPoints(face.oneRingVertices.size(), 3, true);
    for (int row = 0; row < controlPoints.nrow(); ++row)
    {
        const Matrix &coord = mesh.vertices[face.oneRingVertices[row]].coord;
        for (int axis = 0; axis < controlPoints.ncol(); ++axis)
        {
            controlPoints.set(row, axis, coord(axis, 0));
        }
    }
    return controlPoints;
}

AreaVolume direct_regular_patch_area_volume(const Param &param,
                                            const Matrix &controlPoints)
{
    AreaVolume result;
    for (int i = 0; i < param.shapeFunctions.size(); ++i)
    {
        const Matrix &sf = param.shapeFunctions[i];
        Matrix x = sf.get_row(0) * controlPoints;
        Matrix a_3 = cross_row(sf.get_row(1) * controlPoints,
                               sf.get_row(2) * controlPoints);
        const double sqa = a_3.calculate_norm();
        const double coeff = param.gaussQuadratureCoeff(i, 0);
        result.area += 0.5 * coeff * sqa;
        result.volume += kLegacyVolumeQuadratureFactor * coeff * dot_row(x, a_3);
    }
    return result;
}
} // namespace

TEST(SurfaceShapeFunctionsCharacterization, PartitionOfUnityAndDerivativeSums)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
        {1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0},
    };

    for (const auto &sample : barycentricSamples)
    {
        SCOPED_TRACE(::testing::Message()
                     << "v=" << sample[0] << ", w=" << sample[1] << ", u=" << sample[2]);

        Matrix vwu({sample});
        Matrix shapefunction(7, 12, true);
        get_shapefunction(vwu, shapefunction);

        ASSERT_EQ(shapefunction.nrow(), 7);
        ASSERT_EQ(shapefunction.ncol(), 12);
        EXPECT_NEAR(row_sum(shapefunction, 0), 1.0, kTolerance);

        for (int derivativeRow = 1; derivativeRow < shapefunction.nrow(); ++derivativeRow)
        {
            EXPECT_NEAR(row_sum(shapefunction, derivativeRow), 0.0, kTolerance);
        }

        for (int col = 0; col < shapefunction.ncol(); ++col)
        {
            EXPECT_NEAR(shapefunction.get(5, col), shapefunction.get(6, col), kTolerance);
        }
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, SlimedLoopShapeFunctionRowsMatchCurrentContract)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (const auto &sample : barycentricSamples)
    {
        SCOPED_TRACE(::testing::Message()
                     << "v=" << sample[0] << ", w=" << sample[1] << ", u=" << sample[2]);

        Matrix vwu({sample});
        Matrix shapefunction = evaluator.shape_function(vwu);

        ASSERT_EQ(shapefunction.nrow(), SlimedLoopLimitSurfaceEvaluator::kShapeFunctionRowCount);
        ASSERT_EQ(shapefunction.ncol(), evaluator.regular_patch_control_point_count());
        EXPECT_NEAR(row_sum(shapefunction, static_cast<int>(LimitSurfaceDerivativeRow::Position)),
                    1.0,
                    kTolerance);

        for (int derivativeRow = static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeV);
             derivativeRow < shapefunction.nrow();
             ++derivativeRow)
        {
            EXPECT_NEAR(row_sum(shapefunction, derivativeRow), 0.0, kTolerance);
        }

        for (int col = 0; col < shapefunction.ncol(); ++col)
        {
            EXPECT_NEAR(shapefunction.get(static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeVW), col),
                        shapefunction.get(static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeWV), col),
                        kTolerance);
        }
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, SlimedLoopEvaluationMatchesDirectShapeFunctionProduct)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    Matrix controlPoints = make_deterministic_regular_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (const auto &sample : barycentricSamples)
    {
        SCOPED_TRACE(::testing::Message()
                     << "v=" << sample[0] << ", w=" << sample[1] << ", u=" << sample[2]);

        Matrix vwu({sample});
        Matrix shapefunction(7, 12, true);
        get_shapefunction(vwu, shapefunction);

        const Matrix directRows = shapefunction * controlPoints;
        const LimitSurfaceEvaluation evaluation = evaluator.evaluate(vwu, controlPoints);
        const LimitSurfaceEvaluation cachedEvaluation =
            evaluator.evaluate_shape_function(shapefunction, controlPoints);

        expect_column_matches_row(evaluation.position,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::Position));
        expect_column_matches_row(evaluation.firstDerivativeV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeV));
        expect_column_matches_row(evaluation.firstDerivativeW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeW));
        expect_column_matches_row(evaluation.secondDerivativeVV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeVV));
        expect_column_matches_row(evaluation.secondDerivativeWW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeWW));
        expect_column_matches_row(evaluation.mixedDerivativeVW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeVW));
        expect_column_matches_row(evaluation.mixedDerivativeWV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeWV));
        expect_column_matches_row(cachedEvaluation.position,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::Position));
        expect_column_matches_row(cachedEvaluation.firstDerivativeV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeV));
        expect_column_matches_row(cachedEvaluation.firstDerivativeW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeW));
        expect_column_matches_row(cachedEvaluation.secondDerivativeVV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeVV));
        expect_column_matches_row(cachedEvaluation.secondDerivativeWW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeWW));
        expect_column_matches_row(cachedEvaluation.mixedDerivativeVW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeVW));
        expect_column_matches_row(cachedEvaluation.mixedDerivativeWV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeWV));
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, SlimedLoopRegularPatchRejectsIrregularControlCount)
{
    Matrix vwu({{1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0}});
    Matrix irregularControlPoints(11, 3, true);
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    EXPECT_THROW(evaluator.evaluate(vwu, irregularControlPoints), std::invalid_argument);
}

TEST(SurfaceQuadratureCharacterization, SupportedRulesHaveBarycentricCoordinatesAndUnitWeight)
{
    const std::vector<std::pair<int, int>> supportedRules = {
        {1, 1},
        {2, 3},
        {4, 6},
        {5, 7},
        {6, 12},
    };

    for (const auto &[order, expectedPointCount] : supportedRules)
    {
        SCOPED_TRACE(order);

        Matrix vwu;
        Matrix weight;
        get_gauss_quadrature_weight_VWU(order, vwu, weight);

        ASSERT_EQ(vwu.nrow(), expectedPointCount);
        ASSERT_EQ(vwu.ncol(), 3);
        ASSERT_EQ(weight.nrow(), expectedPointCount);
        ASSERT_EQ(weight.ncol(), 1);
        EXPECT_NEAR(column_sum(weight, 0), 1.0, kTolerance);

        for (int row = 0; row < vwu.nrow(); ++row)
        {
            EXPECT_NEAR(row_sum(vwu, row), 1.0, kTolerance);
            for (int col = 0; col < vwu.ncol(); ++col)
            {
                EXPECT_GE(vwu.get(row, col), -kTolerance);
                EXPECT_LE(vwu.get(row, col), 1.0 + kTolerance);
            }
        }
    }
}

TEST(SurfaceQuadratureCharacterization, ThirdOrderRuleCurrentlyLeavesCoordinatesUnchanged)
{
    Matrix vwu(1, 3, true);
    vwu.set_all(-9.0);
    Matrix weight;

    get_gauss_quadrature_weight_VWU(3, vwu, weight);

    ASSERT_EQ(weight.nrow(), 4);
    ASSERT_EQ(weight.ncol(), 1);
    EXPECT_NEAR(column_sum(weight, 0), 1.0, kTolerance);
    ASSERT_EQ(vwu.nrow(), 1);
    ASSERT_EQ(vwu.ncol(), 3);
    for (int col = 0; col < vwu.ncol(); ++col)
    {
        EXPECT_DOUBLE_EQ(vwu.get(0, col), -9.0);
    }
}

TEST(SurfaceSubdivisionCharacterization, IrregularPatchMatricesPreserveAffineWeights)
{
    Matrix subdivision;
    Matrix subPatch1;
    Matrix subPatch2;
    Matrix subPatch3;
    Matrix subPatch4;

    get_subdivision_matrices(subdivision, subPatch1, subPatch2, subPatch3, subPatch4);

    ASSERT_EQ(subdivision.nrow(), 17);
    ASSERT_EQ(subdivision.ncol(), 11);
    ASSERT_EQ(subPatch1.nrow(), 12);
    ASSERT_EQ(subPatch1.ncol(), 17);
    ASSERT_EQ(subPatch2.nrow(), 12);
    ASSERT_EQ(subPatch2.ncol(), 17);
    ASSERT_EQ(subPatch3.nrow(), 12);
    ASSERT_EQ(subPatch3.ncol(), 17);
    ASSERT_EQ(subPatch4.nrow(), 11);
    ASSERT_EQ(subPatch4.ncol(), 17);

    expect_row_stochastic(subdivision);
    expect_row_stochastic(subPatch1);
    expect_row_stochastic(subPatch2);
    expect_row_stochastic(subPatch3);
    expect_row_stochastic(subPatch4);
    expect_selection_rows(subPatch1);
    expect_selection_rows(subPatch2);
    expect_selection_rows(subPatch3);
    expect_selection_rows(subPatch4);
}

TEST(SurfaceFlatMeshCharacterization, PeriodicFlatMeshKeepsInteriorRegularAndPlanar)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;

    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();

    ASSERT_EQ(param.nFaceX, 8);
    ASSERT_EQ(param.nFaceY, 10);
    ASSERT_EQ(mesh.vertices.size(), 99);
    ASSERT_EQ(mesh.faces.size(), 160);
    EXPECT_EQ(count_ghost_vertices(mesh), 84);
    EXPECT_EQ(count_ghost_faces(mesh), 144);

    int physicalFaceCount = 0;
    for (const Face &face : mesh.faces)
    {
        if (!face.isGhost)
        {
            ++physicalFaceCount;
            EXPECT_EQ(face.oneRingVertices.size(), 12);
        }
    }
    ASSERT_EQ(physicalFaceCount, 16);

    mesh.calculate_element_area_volume();

    double area = 0.0;
    double volume = 0.0;
    mesh.sum_membrane_area_and_volume(area, volume);

    EXPECT_NEAR(area, physicalFaceCount * param.elementTriangleArea0, 1.0e-10);
    EXPECT_NEAR(volume, 0.0, 1.0e-10);

    for (const Face &face : mesh.faces)
    {
        if (face.isGhost)
        {
            EXPECT_DOUBLE_EQ(face.elementArea, 0.0);
            EXPECT_DOUBLE_EQ(face.elementVolume, 0.0);
        }
        else
        {
            EXPECT_NEAR(face.elementArea, param.elementTriangleArea0, 1.0e-11);
            EXPECT_NEAR(face.elementVolume, 0.0, 1.0e-11);
        }
    }
}

TEST(SurfaceFlatMeshCharacterization, RegularAreaVolumeUsesLimitSurfaceEvaluatorEquivalentToDirectRows)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;

    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();

    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index);
        vertex.coord.set(2, 0, 0.01 * std::sin(0.7 * index)
                                   + 0.005 * std::cos(0.3 * index));
    }

    std::vector<AreaVolume> expected(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        if (!face.isGhost)
        {
            ASSERT_EQ(face.oneRingVertices.size(), 12);
            expected[face.index] = direct_regular_patch_area_volume(
                param,
                make_one_ring_control_points(mesh, face));
        }
    }

    mesh.calculate_element_area_volume();

    for (const Face &face : mesh.faces)
    {
        if (!face.isGhost)
        {
            EXPECT_NEAR(face.elementArea, expected[face.index].area, 1.0e-12);
            EXPECT_NEAR(face.elementVolume, expected[face.index].volume, 1.0e-12);
        }
    }
}
