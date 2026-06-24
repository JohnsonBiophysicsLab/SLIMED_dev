#include <array>
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

std::vector<Matrix> make_regular_energy_force_control_point_fixtures()
{
    Matrix flat(12, 3, true);
    Matrix gentlyCurved(12, 3, true);
    Matrix mixedSign(12, 3, true);
    Matrix anisotropic(12, 3, true);
    for (int control = 0; control < 12; ++control)
    {
        const double index = static_cast<double>(control);

        flat.set(control, 0, 0.2 + 0.35 * index);
        flat.set(control, 1, -0.4 + 0.08 * index * index);
        flat.set(control, 2, 0.0);

        gentlyCurved.set(control, 0, 0.2 + 0.35 * index);
        gentlyCurved.set(control, 1, -0.4 + 0.08 * index * index);
        gentlyCurved.set(control, 2, 0.1 * std::sin(0.5 * index));

        mixedSign.set(control, 0, -1.5 + 0.17 * index * index);
        mixedSign.set(control, 1, 2.0 - 0.31 * index);
        mixedSign.set(control, 2, -0.75 + 0.04 * index * index * index);

        anisotropic.set(control, 0, 4.0 + std::cos(0.25 * index));
        anisotropic.set(control, 1, -3.0 + std::sin(0.3 * index));
        anisotropic.set(control, 2, 1.0 + 0.125 * index);
    }

    return {flat, gentlyCurved, mixedSign, anisotropic};
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

void expect_matrix_exactly_matches(const Matrix &expected,
                                   const Matrix &actual)
{
    ASSERT_EQ(actual.nrow(), expected.nrow());
    ASSERT_EQ(actual.ncol(), expected.ncol());
    for (int row = 0; row < expected.nrow(); ++row)
    {
        for (int col = 0; col < expected.ncol(); ++col)
        {
            EXPECT_DOUBLE_EQ(actual.get(row, col), expected.get(row, col))
                << "row " << row << " col " << col;
        }
    }
}

void expect_evaluation_matches_rows(const LimitSurfaceEvaluation &evaluation,
                                    const Matrix &directRows)
{
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
}

void expect_column_near_values(const Matrix &column,
                               const std::array<double, 3> &expected,
                               const double tolerance)
{
    ASSERT_EQ(column.nrow(), 3);
    ASSERT_EQ(column.ncol(), 1);
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_NEAR(column.get(axis, 0), expected[axis], tolerance)
            << "axis " << axis;
    }
}

std::array<double, 3> column_to_array(const Matrix &column)
{
    return {column.get(0, 0), column.get(1, 0), column.get(2, 0)};
}

std::array<double, 3> cross_array(const std::array<double, 3> &lhs,
                                  const std::array<double, 3> &rhs)
{
    return {
        lhs[1] * rhs[2] - lhs[2] * rhs[1],
        lhs[2] * rhs[0] - lhs[0] * rhs[2],
        lhs[0] * rhs[1] - lhs[1] * rhs[0],
    };
}

double norm_array(const std::array<double, 3> &values)
{
    return std::sqrt(values[0] * values[0] +
                     values[1] * values[1] +
                     values[2] * values[2]);
}

std::array<double, 3> normalized_array(const std::array<double, 3> &values)
{
    const double norm = norm_array(values);
    return {values[0] / norm, values[1] / norm, values[2] / norm};
}

Matrix make_regular_lattice_probe_control_points()
{
    constexpr int n = 6;
    const auto vertex_id = [](const int i, const int j) {
        return j * 7 + i;
    };
    const std::vector<int> oneRing = {
        vertex_id(2, 1),
        vertex_id(1, 2),
        vertex_id(3, 1),
        vertex_id(2, 2),
        vertex_id(1, 3),
        vertex_id(4, 1),
        vertex_id(3, 2),
        vertex_id(2, 3),
        vertex_id(1, 4),
        vertex_id(4, 2),
        vertex_id(3, 3),
        vertex_id(2, 4),
    };

    Matrix controlPoints(12, 3, true);
    for (int row = 0; row < static_cast<int>(oneRing.size()); ++row)
    {
        const int vertex = oneRing[row];
        const int i = vertex % (n + 1);
        const int j = vertex / (n + 1);
        controlPoints.set(row, 0, static_cast<double>(i) + 0.5 * static_cast<double>(j));
        controlPoints.set(row, 1, std::sqrt(3.0) / 2.0 * static_cast<double>(j));
        controlPoints.set(row, 2, 0.03 * std::sin(0.7 * static_cast<double>(i + j)));
    }
    return controlPoints;
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

AreaVolume direct_irregular_patch_area_volume(const Param &param,
                                              const Matrix &controlPoints)
{
    AreaVolume result;
    Matrix carriedIrregularPatch = controlPoints;

    for (int depth = 0; depth < param.subDivideTimes; ++depth)
    {
        Matrix subdividedNodes = param.subMatrix.irregM * carriedIrregularPatch;

        const std::vector<Matrix> regularSubpatches = {
            param.subMatrix.irregM1 * subdividedNodes,
            param.subMatrix.irregM2 * subdividedNodes,
            param.subMatrix.irregM3 * subdividedNodes,
        };
        for (const Matrix &regularSubpatch : regularSubpatches)
        {
            const AreaVolume subpatchAreaVolume =
                direct_regular_patch_area_volume(param, regularSubpatch);
            result.area += subpatchAreaVolume.area;
            result.volume += subpatchAreaVolume.volume;
        }

        carriedIrregularPatch = param.subMatrix.irregM4 * subdividedNodes;
    }

    return result;
}

void populate_synthetic_irregular_patch_mesh(Mesh &mesh)
{
    const std::vector<std::vector<double>> coordinates = {
        {-0.70, -0.86, 0.01},
        {-0.18, -0.92, -0.02},
        {0.00, 0.00, 0.04},
        {0.58, -0.78, 0.03},
        {-0.78, -0.05, -0.03},
        {-0.12, 0.56, 0.02},
        {0.64, 0.08, -0.01},
        {1.16, -0.58, 0.05},
        {-0.30, 1.12, -0.04},
        {0.54, 1.06, 0.03},
        {1.20, 0.46, 0.00},
    };

    mesh.vertices.clear();
    mesh.vertices.resize(coordinates.size());
    for (int vertexIndex = 0; vertexIndex < static_cast<int>(coordinates.size()); ++vertexIndex)
    {
        Vertex &vertex = mesh.vertices[vertexIndex];
        vertex.index = vertexIndex;
        vertex.coord.set(0, 0, coordinates[vertexIndex][0]);
        vertex.coord.set(1, 0, coordinates[vertexIndex][1]);
        vertex.coord.set(2, 0, coordinates[vertexIndex][2]);
    }

    mesh.faces.clear();
    mesh.faces.resize(1);

    Face &face = mesh.faces.front();
    face.index = 0;
    face.adjacentVertices = {2, 5, 6};
    face.oneRingVertices = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
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

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularLatticeProbeFrozenOutputsMatchCurrentEvaluator)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    const std::array<std::array<std::array<double, 3>, 7>, 3> expected = {{
        {{
            {{3.4999999999999982, 2.0207259421636894, -0.003450545921933364}},
            {{0.99999999999999978, -3.6236828367093433e-17, -0.019210698845634439}},
            {{0.50000000000000022, 0.86602540378443882, -0.019210698845634439}},
            {{3.3306690738754696e-16, 3.4587734865006226e-17, 0.0017240750489055767}},
            {{-1.1102230246251565e-16, -1.1674737245020074e-16, 0.0017240750489055771}},
            {{-5.5511151231257827e-17, -1.9572029680632367e-16, 0.0017240750489055834}},
            {{-5.5511151231257827e-17, -1.9572029680632367e-16, 0.0017240750489055834}},
        }},
        {{
            {{3.3500000000000001, 1.9918584287042085, -0.0002322832431500952}},
            {{0.99999999999999978, -1.2002033867471152e-16, -0.019363657606087825}},
            {{0.50000000000000033, 0.86602540378443882, -0.019363657606087818}},
            {{2.7755575615628914e-16, 4.1296024847155701e-16, 0.00011143007653501233}},
            {{1.1102230246251565e-16, 1.1399713609118315e-16, 0.0001114300765350122}},
            {{5.5511151231257827e-17, -2.6556107582143733e-16, 0.0001114300765350114}},
            {{5.5511151231257827e-17, -2.6556107582143733e-16, 0.0001114300765350114}},
        }},
        {{
            {{3.4750000000000001, 2.4681724007856505, -0.007865622601230705}},
            {{0.99999999999999978, -2.5312096407330787e-16, -0.018545015988735949}},
            {{0.50000000000000022, 0.86602540378443882, -0.018545015988735942}},
            {{-2.7755575615628914e-16, -5.2999475976476768e-16, 0.0039817780102243674}},
            {{-4.4408920985006262e-16, -8.1361688734307423e-16, 0.0039817780102243709}},
            {{2.2204460492503131e-16, 2.0460560118955678e-16, 0.0039817780102243657}},
            {{2.2204460492503131e-16, 2.0460560118955678e-16, 0.0039817780102243657}},
        }},
    }};

    const Matrix controlPoints = make_regular_lattice_probe_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (int sample = 0; sample < static_cast<int>(barycentricSamples.size()); ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "sample " << sample);
        const LimitSurfaceEvaluation evaluation =
            evaluator.evaluate(Matrix({barycentricSamples[sample]}), controlPoints);

        expect_column_near_values(evaluation.position, expected[sample][0], 1.0e-14);
        expect_column_near_values(evaluation.firstDerivativeV, expected[sample][1], 1.0e-14);
        expect_column_near_values(evaluation.firstDerivativeW, expected[sample][2], 1.0e-14);
        expect_column_near_values(evaluation.secondDerivativeVV, expected[sample][3], 1.0e-14);
        expect_column_near_values(evaluation.secondDerivativeWW, expected[sample][4], 1.0e-14);
        expect_column_near_values(evaluation.mixedDerivativeVW, expected[sample][5], 1.0e-14);
        expect_column_near_values(evaluation.mixedDerivativeWV, expected[sample][6], 1.0e-14);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularLatticeProbeFrozenIntegrandsMatchCurrentEvaluator)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    const std::array<std::array<double, 3>, 3> expectedCross = {{
        {{0.016636953224771819, 0.0096053494228172127, 0.8660254037844386}},
        {{0.016769419397055833, 0.0096818288030438952, 0.86602540378443871}},
        {{0.016060454959833926, 0.0092725079943679605, 0.86602540378443871}},
    }};
    const std::array<std::array<double, 3>, 3> expectedUnitNormal = {{
        {{0.019205974104791867, 0.011088574319450555, 0.9997540567950941}},
        {{0.019358819135302421, 0.011176819438960107, 0.99975012619599879}},
        {{0.018540765478688707, 0.010704515940102625, 0.99977080041075028}},
    }};
    const std::array<double, 3> expectedAreaIntegrand = {{
        0.8662384492448586,
        0.86624185493191563,
        0.86622394195613328,
    }};
    const std::array<double, 3> expectedLegacyVolumeIntegrand = {{
        0.058229336286701336,
        0.056177554980137046,
        0.055810080985422894,
    }};

    const Matrix controlPoints = make_regular_lattice_probe_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (int sample = 0; sample < static_cast<int>(barycentricSamples.size()); ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "sample " << sample);
        const LimitSurfaceEvaluation evaluation =
            evaluator.evaluate(Matrix({barycentricSamples[sample]}), controlPoints);

        const std::array<double, 3> tangentCross =
            cross_array(column_to_array(evaluation.firstDerivativeV),
                        column_to_array(evaluation.firstDerivativeW));
        const std::array<double, 3> unitNormal = normalized_array(tangentCross);
        const double areaIntegrand = norm_array(tangentCross);
        const double legacyVolumeIntegrand =
            evaluation.position.get(0, 0) * tangentCross[0];

        for (int axis = 0; axis < 3; ++axis)
        {
            EXPECT_NEAR(tangentCross[axis], expectedCross[sample][axis], 1.0e-14)
                << "cross axis " << axis;
            EXPECT_NEAR(unitNormal[axis], expectedUnitNormal[sample][axis], 1.0e-14)
                << "unit normal axis " << axis;
        }
        EXPECT_NEAR(areaIntegrand, expectedAreaIntegrand[sample], 1.0e-14);
        EXPECT_NEAR(legacyVolumeIntegrand,
                    expectedLegacyVolumeIntegrand[sample],
                    1.0e-14);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, SlimedLoopRegularPatchRejectsIrregularControlCount)
{
    Matrix vwu({{1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0}});
    Matrix irregularControlPoints(11, 3, true);
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    EXPECT_THROW(evaluator.evaluate(vwu, irregularControlPoints), std::invalid_argument);
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularEnergyForceGeometryExtractionMatchesParamShapeFunctions)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    Matrix controlPoints = make_deterministic_regular_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    ASSERT_FALSE(param.shapeFunctions.empty());
    ASSERT_EQ(param.shapeFunctions.size(),
              static_cast<std::size_t>(param.gaussQuadratureCoeff.nrow()));

    for (int sample = 0; sample < static_cast<int>(param.shapeFunctions.size()); ++sample)
    {
        SCOPED_TRACE(sample);
        const Matrix &shapeFunction = param.shapeFunctions[sample];
        const Matrix directRows = shapeFunction * controlPoints;
        const LimitSurfaceEvaluation evaluation =
            evaluator.evaluate_shape_function(shapeFunction, controlPoints);

        expect_evaluation_matches_rows(evaluation, directRows);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularEnergyForceGeometryRowsMatchLegacyMultiplicationForFixtures)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    const SlimedLoopLimitSurfaceEvaluator evaluator;
    const std::vector<Matrix> controlPointFixtures =
        make_regular_energy_force_control_point_fixtures();
    const std::vector<Matrix> shapeFunctionBaseline = param.shapeFunctions;

    ASSERT_FALSE(param.shapeFunctions.empty());
    ASSERT_EQ(param.shapeFunctions.size(),
              static_cast<std::size_t>(param.gaussQuadratureCoeff.nrow()));

    for (int fixture = 0; fixture < static_cast<int>(controlPointFixtures.size()); ++fixture)
    {
        SCOPED_TRACE(::testing::Message() << "fixture " << fixture);
        const Matrix &controlPoints = controlPointFixtures[fixture];
        ASSERT_EQ(controlPoints.nrow(), evaluator.regular_patch_control_point_count());
        ASSERT_EQ(controlPoints.ncol(), SlimedLoopLimitSurfaceEvaluator::kSpatialDimension);

        for (int sample = 0; sample < static_cast<int>(param.shapeFunctions.size()); ++sample)
        {
            SCOPED_TRACE(::testing::Message() << "sample " << sample);
            const Matrix &shapeFunction = param.shapeFunctions[sample];
            Matrix legacyRows(7, 3, true);

            multiplication(shapeFunction, controlPoints, legacyRows);

            const LimitSurfaceEvaluation evaluation =
                evaluator.evaluate_shape_function(shapeFunction, controlPoints);

            expect_evaluation_matches_rows(evaluation, legacyRows);
        }
    }

    ASSERT_EQ(shapeFunctionBaseline.size(), param.shapeFunctions.size());
    for (int sample = 0; sample < static_cast<int>(shapeFunctionBaseline.size()); ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "shape function baseline " << sample);
        expect_matrix_exactly_matches(shapeFunctionBaseline[sample],
                                      param.shapeFunctions[sample]);
    }
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

TEST(SurfaceSubdivisionCharacterization, SyntheticIrregularPatchAreaVolumeUsesSubdivisionFixture)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.subDivideTimes = 2;
    Mesh mesh(param);
    populate_synthetic_irregular_patch_mesh(mesh);
    const Face &fixtureFace = mesh.faces.front();

    ASSERT_EQ(fixtureFace.oneRingVertices.size(), 11);
    ASSERT_GT(param.subDivideTimes, 0);

    const AreaVolume expected = direct_irregular_patch_area_volume(
        param,
        make_one_ring_control_points(mesh, fixtureFace));

    mesh.calculate_element_area_volume();

    EXPECT_TRUE(std::isfinite(mesh.faces.front().elementArea));
    EXPECT_TRUE(std::isfinite(mesh.faces.front().elementVolume));
    EXPECT_GT(mesh.faces.front().elementArea, 0.0);
    EXPECT_NEAR(mesh.faces.front().elementArea, expected.area, 1.0e-12);
    EXPECT_NEAR(mesh.faces.front().elementVolume, expected.volume, 1.0e-12);

    double area = 0.0;
    double volume = 0.0;
    mesh.sum_membrane_area_and_volume(area, volume);

    EXPECT_NEAR(area, expected.area, 1.0e-12);
    EXPECT_NEAR(volume, expected.volume, 1.0e-12);
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
