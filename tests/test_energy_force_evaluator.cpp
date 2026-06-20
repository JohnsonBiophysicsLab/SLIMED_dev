#include <cmath>
#include <vector>

#include <gtest/gtest.h>

#include "energy_force/Energy_force_evaluator.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "Parameters.hpp"

namespace
{
Param make_tiny_flat_param()
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 15.0;
    param.sideY = 15.0;
    param.lFace = 5.0;
    param.isGlobalConstraint = false;
    param.setRelaxAreaToDefault = true;
    param.meshpointOutput = false;
    param.xyzOutput = false;
    param.surfacepointOutput = false;
    param.thermalFluctuationEnabled = false;
    return param;
}

void initialize_area_reference(Mesh &mesh)
{
    mesh.setup_flat();
    mesh.calculate_element_area_volume();
    double initArea = 0.0;
    if (mesh.param.setRelaxAreaToDefault)
    {
        mesh.sum_membrane_area_and_volume(mesh.param.area0, mesh.param.vol0);
    }
    else
    {
        mesh.sum_membrane_area_and_volume(initArea, mesh.param.vol0);
    }
    mesh.update_previous_coord_for_vertex();
    mesh.update_reference_coord_from_previous_coord();
}

std::vector<Force> copy_current_forces(const Mesh &mesh)
{
    std::vector<Force> forces;
    forces.reserve(mesh.vertices.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        forces.push_back(vertex.force);
    }
    return forces;
}

void poison_current_force_and_energy(Mesh &mesh)
{
    mesh.param.energy.energyTotal = 12345.0;
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.force.forceCurvature.set(0, 0, 10.0);
        vertex.force.forceArea.set(1, 0, -20.0);
        vertex.force.forceVolume.set(2, 0, 30.0);
        vertex.force.forceTotal.set(0, 0, 40.0);
        vertex.force.forceTotal.set(1, 0, 50.0);
        vertex.force.forceTotal.set(2, 0, 60.0);
    }
    for (Face &face : mesh.faces)
    {
        face.energy.energyCurvature = 77.0;
        face.energy.energyTotal = 88.0;
    }
}

void expect_same_forces(const std::vector<Force> &expected,
                        const Mesh &actual)
{
    ASSERT_EQ(expected.size(), actual.vertices.size());
    for (int i = 0; i < static_cast<int>(expected.size()); ++i)
    {
        for (int component = 0; component < 3; ++component)
        {
            EXPECT_DOUBLE_EQ(expected[i].forceCurvature(component, 0),
                             actual.vertices[i].force.forceCurvature(component, 0))
                << "vertex " << i << " forceCurvature component " << component;
            EXPECT_DOUBLE_EQ(expected[i].forceArea(component, 0),
                             actual.vertices[i].force.forceArea(component, 0))
                << "vertex " << i << " forceArea component " << component;
            EXPECT_DOUBLE_EQ(expected[i].forceVolume(component, 0),
                             actual.vertices[i].force.forceVolume(component, 0))
                << "vertex " << i << " forceVolume component " << component;
            EXPECT_DOUBLE_EQ(expected[i].forceRegularization(component, 0),
                             actual.vertices[i].force.forceRegularization(component, 0))
                << "vertex " << i << " forceRegularization component " << component;
            EXPECT_DOUBLE_EQ(expected[i].forceTotal(component, 0),
                             actual.vertices[i].force.forceTotal(component, 0))
                << "vertex " << i << " forceTotal component " << component;
        }
    }
}
}

TEST(EnergyForceEvaluatorTest, MatchesExistingMeshEnergyForceCall)
{
    Param directParam = make_tiny_flat_param();
    Param evaluatorParam = make_tiny_flat_param();
    Mesh directMesh(directParam);
    Mesh evaluatorMesh(evaluatorParam);
    initialize_area_reference(directMesh);
    initialize_area_reference(evaluatorMesh);

    directMesh.Compute_Energy_And_Force();
    EnergyForceEvaluator evaluator;
    evaluator.evaluate(evaluatorMesh);

    EXPECT_DOUBLE_EQ(directMesh.param.area, evaluatorMesh.param.area);
    EXPECT_DOUBLE_EQ(directMesh.param.vol, evaluatorMesh.param.vol);
    EXPECT_DOUBLE_EQ(directMesh.param.energy.energyCurvature,
                     evaluatorMesh.param.energy.energyCurvature);
    EXPECT_DOUBLE_EQ(directMesh.param.energy.energyArea,
                     evaluatorMesh.param.energy.energyArea);
    EXPECT_DOUBLE_EQ(directMesh.param.energy.energyVolume,
                     evaluatorMesh.param.energy.energyVolume);
    EXPECT_DOUBLE_EQ(directMesh.param.energy.energyRegularization,
                     evaluatorMesh.param.energy.energyRegularization);
    EXPECT_DOUBLE_EQ(directMesh.param.energy.energyTotal,
                     evaluatorMesh.param.energy.energyTotal);
    expect_same_forces(copy_current_forces(directMesh), evaluatorMesh);
}

TEST(EnergyForceEvaluatorTest, RepeatedEvaluationClearsStaleForceAndFaceEnergy)
{
    Param param = make_tiny_flat_param();
    Mesh mesh(param);
    initialize_area_reference(mesh);

    EnergyForceEvaluator evaluator;
    evaluator.evaluate(mesh);
    const Energy expectedEnergy = mesh.param.energy;
    const std::vector<Force> expectedForces = copy_current_forces(mesh);

    poison_current_force_and_energy(mesh);
    evaluator.evaluate(mesh);

    EXPECT_DOUBLE_EQ(expectedEnergy.energyCurvature, mesh.param.energy.energyCurvature);
    EXPECT_DOUBLE_EQ(expectedEnergy.energyArea, mesh.param.energy.energyArea);
    EXPECT_DOUBLE_EQ(expectedEnergy.energyVolume, mesh.param.energy.energyVolume);
    EXPECT_DOUBLE_EQ(expectedEnergy.energyRegularization, mesh.param.energy.energyRegularization);
    EXPECT_DOUBLE_EQ(expectedEnergy.energyTotal, mesh.param.energy.energyTotal);
    expect_same_forces(expectedForces, mesh);
}

TEST(EnergyForceEvaluatorTest, FlatExampleProducesFiniteEnergyAndForce)
{
    Param param;
    ASSERT_TRUE(import_param_file(param, "./data/example/example.params"));
    param.VERBOSE_MODE = false;
    param.meshpointOutput = false;
    param.xyzOutput = false;
    param.surfacepointOutput = false;

    Mesh mesh(param);
    initialize_area_reference(mesh);

    EnergyForceEvaluator evaluator;
    evaluator.evaluate(mesh);

    EXPECT_TRUE(std::isfinite(mesh.param.energy.energyTotal));
    EXPECT_TRUE(std::isfinite(mesh.calculate_mean_force()));
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int component = 0; component < 3; ++component)
        {
            EXPECT_TRUE(std::isfinite(vertex.force.forceTotal(component, 0)))
                << "vertex " << vertex.index << " component " << component;
        }
    }
}
