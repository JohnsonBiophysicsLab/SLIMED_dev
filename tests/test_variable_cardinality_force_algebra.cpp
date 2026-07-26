#include <cmath>
#include <vector>

#include <gtest/gtest.h>

#include "mesh/Mesh.hpp"

namespace
{
std::vector<Matrix> triangle_coordinates(const int cardinality)
{
    std::vector<Matrix> coordinates(cardinality, Matrix(3, 1, true));
    coordinates[1].set(0, 0, 1.0);
    coordinates[2].set(1, 0, 1.0);
    return coordinates;
}

std::vector<Matrix> triangle_shape_functions(const int cardinality)
{
    Matrix sample(7, cardinality, true);
    sample.set(0, 0, 1.0 / 3.0);
    sample.set(0, 1, 1.0 / 3.0);
    sample.set(0, 2, 1.0 / 3.0);
    sample.set(1, 0, -1.0);
    sample.set(1, 1, 1.0);
    sample.set(2, 0, -1.0);
    sample.set(2, 2, 1.0);
    return {sample, sample, sample};
}

struct FormulaResult
{
    double meanCurvature = 0.0;
    double bendingEnergy = 0.0;
    Matrix normal = mat_calloc(3, 1);
    Matrix bending;
    Matrix area;
    Matrix volume;

    explicit FormulaResult(const int cardinality)
        : bending(mat_calloc(cardinality, 3)),
          area(mat_calloc(cardinality, 3)),
          volume(mat_calloc(cardinality, 3))
    {
    }
};

FormulaResult evaluate_triangle(Mesh &mesh,
                                const int cardinality,
                                const std::vector<Matrix> *overrideRows)
{
    Face face;
    face.index = 0;
    face.spontCurvature = 0.2;
    FormulaResult result(cardinality);
    mesh.element_energy_force_regular(
        triangle_coordinates(cardinality),
        face,
        face.spontCurvature,
        result.meanCurvature,
        result.normal,
        result.bendingEnergy,
        result.bending,
        result.area,
        result.volume,
        false,
        overrideRows);
    return result;
}

void expect_finite(const FormulaResult &result)
{
    EXPECT_TRUE(std::isfinite(result.meanCurvature));
    EXPECT_TRUE(std::isfinite(result.bendingEnergy));
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_TRUE(std::isfinite(result.normal.get(axis, 0)));
    }
    for (const Matrix *force :
         {&result.bending, &result.area, &result.volume})
    {
        for (int source = 0; source < force->nrow(); ++source)
        {
            for (int axis = 0; axis < 3; ++axis)
            {
                EXPECT_TRUE(std::isfinite(force->get(source, axis)));
            }
        }
    }
}
} // namespace

TEST(VariableCardinalityForceAlgebraTest,
     ExplicitThreeSourceRowsMatchZeroPaddedTwelveSourceEvaluation)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.area0 = 2.75;
    param.area = 0.5;
    param.uVol = 65.0;
    param.vol0 = 0.82;
    param.vol = 0.25;
    Mesh mesh(param);

    const std::vector<Matrix> threeRows = triangle_shape_functions(3);
    const std::vector<Matrix> twelveRows = triangle_shape_functions(12);
    const FormulaResult three = evaluate_triangle(mesh, 3, &threeRows);
    const FormulaResult twelve = evaluate_triangle(mesh, 12, &twelveRows);
    expect_finite(three);
    expect_finite(twelve);

    EXPECT_NEAR(three.meanCurvature, twelve.meanCurvature, 1.0e-12);
    EXPECT_NEAR(three.bendingEnergy, twelve.bendingEnergy, 1.0e-12);
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_NEAR(three.normal.get(axis, 0),
                    twelve.normal.get(axis, 0),
                    1.0e-12);
    }
    for (const auto pair :
         {std::pair<const Matrix *, const Matrix *>{&three.bending,
                                                    &twelve.bending},
          {&three.area, &twelve.area},
          {&three.volume, &twelve.volume}})
    {
        for (int source = 0; source < 3; ++source)
        {
            for (int axis = 0; axis < 3; ++axis)
            {
                EXPECT_NEAR(pair.first->get(source, axis),
                            pair.second->get(source, axis),
                            1.0e-12);
            }
        }
        for (int source = 3; source < 12; ++source)
        {
            for (int axis = 0; axis < 3; ++axis)
            {
                EXPECT_NEAR(pair.second->get(source, axis), 0.0, 1.0e-12);
            }
        }
    }
}

TEST(VariableCardinalityForceAlgebraTest,
     RejectsImplicitOrDimensionMismatchedVariableCardinality)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    Face face;
    Matrix normal = mat_calloc(3, 1);
    Matrix bending = mat_calloc(3, 3);
    Matrix area = mat_calloc(3, 3);
    Matrix volume = mat_calloc(3, 3);
    double meanCurvature = 0.0;
    double bendingEnergy = 0.0;

    EXPECT_THROW(mesh.element_energy_force_regular(
                     triangle_coordinates(3),
                     face,
                     0.0,
                     meanCurvature,
                     normal,
                     bendingEnergy,
                     bending,
                     area,
                     volume),
                 std::invalid_argument);

    const std::vector<Matrix> rows = triangle_shape_functions(3);
    Matrix wrongBending = mat_calloc(4, 3);
    EXPECT_THROW(mesh.element_energy_force_regular(
                     triangle_coordinates(3),
                     face,
                     0.0,
                     meanCurvature,
                     normal,
                     bendingEnergy,
                     wrongBending,
                     area,
                     volume,
                     false,
                     &rows),
                 std::invalid_argument);

    Matrix wrongNormal = mat_calloc(2, 1);
    EXPECT_THROW(mesh.element_energy_force_regular(
                     triangle_coordinates(3),
                     face,
                     0.0,
                     meanCurvature,
                     wrongNormal,
                     bendingEnergy,
                     bending,
                     area,
                     volume,
                     false,
                     &rows),
                 std::invalid_argument);
}

TEST(VariableCardinalityForceAlgebraTest,
     RejectsMalformedLaterSampleBeforeMutatingCallerOutputs)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    Face face;
    Matrix normal = mat_calloc(3, 1);
    Matrix bending = mat_calloc(3, 3);
    Matrix area = mat_calloc(3, 3);
    Matrix volume = mat_calloc(3, 3);
    double meanCurvature = 11.0;
    double bendingEnergy = 12.0;
    normal.set(0, 0, 13.0);
    bending.set(0, 0, 14.0);
    area.set(0, 0, 15.0);
    volume.set(0, 0, 16.0);

    std::vector<Matrix> malformedRows = triangle_shape_functions(3);
    malformedRows[1] = Matrix(6, 3, true);
    EXPECT_THROW(mesh.element_energy_force_regular(
                     triangle_coordinates(3),
                     face,
                     0.0,
                     meanCurvature,
                     normal,
                     bendingEnergy,
                     bending,
                     area,
                     volume,
                     false,
                     &malformedRows),
                 std::invalid_argument);

    EXPECT_DOUBLE_EQ(meanCurvature, 11.0);
    EXPECT_DOUBLE_EQ(bendingEnergy, 12.0);
    EXPECT_DOUBLE_EQ(normal.get(0, 0), 13.0);
    EXPECT_DOUBLE_EQ(bending.get(0, 0), 14.0);
    EXPECT_DOUBLE_EQ(area.get(0, 0), 15.0);
    EXPECT_DOUBLE_EQ(volume.get(0, 0), 16.0);
}
