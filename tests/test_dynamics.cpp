#include <gtest/gtest.h>

#include <random>

#include "Dynamics.hpp"

namespace
{
Param quiet_dynamic_param()
{
    Param param;
    param.VERBOSE_MODE = false;
    param.randomSeed = 12345;
    param.diffConst = 1.0;
    param.timeStep = 0.25;
    param.KBT = 2.0;
    return param;
}
}

TEST(DynamicModelCharacterizationTest, ConstructorCopiesSeedButGeneratorKeepsDefaultState)
{
    Param param = quiet_dynamic_param();
    DynamicMesh mesh(param);
    Record record(1);

    DynamicModel model(mesh, record);

    EXPECT_EQ(model.randomSeed, param.randomSeed);

    std::mt19937 defaultGenerator;
    std::mt19937 seededGenerator(param.randomSeed);
    const auto firstDynamicDraw = model.gen();
    EXPECT_EQ(firstDynamicDraw, defaultGenerator());
    EXPECT_NE(firstDynamicDraw, seededGenerator());
    EXPECT_DOUBLE_EQ(model.normal_dist.mean(), 0.0);
    EXPECT_DOUBLE_EQ(model.normal_dist.stddev(), 1.0);
}

TEST(DynamicModelCharacterizationTest, NextStepConsumesCurrentCurvatureAndAreaForces)
{
    Param param = quiet_dynamic_param();
    DynamicMesh mesh(param);
    mesh.vertices.emplace_back(0, 0.0, 0.0, 0.0);
    mesh.matSurface = mat_calloc(1, 3);
    mesh.matSurface.set(0, 0, 1.0);
    mesh.matSurface.set(0, 1, 2.0);
    mesh.matSurface.set(0, 2, 3.0);

    mesh.vertices[0].force.forceCurvature.set(2, 0, 1.25);
    mesh.vertices[0].force.forceArea.set(2, 0, -0.75);

    Record record(1);
    DynamicModel model(mesh, record);
    model.randScaleConst = 0.0;
    model.forceScaleConst = 2.0;

    model.next_step();

    EXPECT_DOUBLE_EQ(mesh.matSurface(0, 0), 1.0);
    EXPECT_DOUBLE_EQ(mesh.matSurface(0, 1), 2.0);
    EXPECT_DOUBLE_EQ(mesh.matSurface(0, 2), 4.0);
}
