#include "test_optimization_algorithm.hpp"

TEST(ThermalFluctuationTest, DisabledSwitchSkipsTrial)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    Record record(1);
    Model model(mesh, record);

    EXPECT_FALSE(model.simulated_annealing_next_step());
    EXPECT_TRUE(model.thermalFluctuationRecords.empty());
}

TEST(ThermalFluctuationTest, EnabledSwitchAttemptsMetropolisTrial)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Free;
    param.sideX = 25.0;
    param.sideY = 25.0;
    param.lFace = 5.0;
    param.KBT = 1.0e12;
    param.randomSeed = 11;
    param.thermalFluctuationEnabled = true;
    param.thermalFluctuationInterval = 1;
    param.thermalFluctuationTemperatureKelvin = 298.0;
    param.thermalFluctuationMinTemperatureKelvin = 298.0;
    param.thermalFluctuationCoolingRate = 1.0;
    param.thermalFluctuationStepScale = 1.0e-5;

    Mesh mesh(param);
    mesh.setup_flat();
    mesh.calculate_element_area_volume();
    double initArea = 0.0;
    mesh.sum_membrane_area_and_volume(initArea, mesh.param.vol0);
    mesh.update_previous_coord_for_vertex();
    mesh.update_reference_coord_from_previous_coord();
    mesh.Compute_Energy_And_Force();

    std::vector<Matrix> coordsBefore(mesh.vertices.size(), Matrix(3, 1));
    for (int i = 0; i < mesh.vertices.size(); i++)
    {
        coordsBefore[i] = mesh.vertices[i].coord;
    }

    Record record(2);
    Model model(mesh, record);
    model.iteration = 0;

    EXPECT_TRUE(model.simulated_annealing_next_step());
    ASSERT_EQ(model.thermalFluctuationRecords.size(), 1);
    EXPECT_DOUBLE_EQ(model.thermalFluctuationRecords[0].temperatureKelvin, 298.0);
    EXPECT_NEAR(model.thermalFluctuationRecords[0].kBT, 4.11433402, 1.0e-8);
    EXPECT_TRUE(std::isfinite(model.thermalFluctuationRecords[0].deltaEnergy));
    EXPECT_TRUE(std::isfinite(model.thermalFluctuationRecords[0].acceptanceProbability));
    EXPECT_GE(model.thermalFluctuationRecords[0].acceptanceProbability, 0.0);
    EXPECT_LE(model.thermalFluctuationRecords[0].acceptanceProbability, 1.0);

    bool movedAtLeastOneVertex = false;
    for (int i = 0; i < mesh.vertices.size(); i++)
    {
        if (!mesh.vertices[i].isGhost &&
            mesh.vertices[i].type != VertexType::Ghost &&
            (mesh.vertices[i].coord(0, 0) != coordsBefore[i](0, 0) ||
             mesh.vertices[i].coord(1, 0) != coordsBefore[i](1, 0) ||
             mesh.vertices[i].coord(2, 0) != coordsBefore[i](2, 0)))
        {
            movedAtLeastOneVertex = true;
            break;
        }
    }
    if (model.thermalFluctuationRecords[0].accepted)
    {
        EXPECT_TRUE(movedAtLeastOneVertex);
    }
}

// Test for reseting NCG direction vector to (0, 0, 0) vectors
/*
TEST(NCGOptimizerTest, ResetNCGDirectionTest)
{
    Param param = Param();
    Mesh mesh = Mesh(param);
    Record record(param.maxIterations);
    Model model = Model(mesh, record);

    model.ncgDirection0[0].forceTotal.set(0, 0, 0.369);
    model.ncgDirection0[0].forceTotal.set(1, 0, 0.8666033);

    // Reset
    model.reset_ncg_direction();

    // Assert
    EXPECT_DOUBLE_EQ(model.ncgDirection0[0].forceTotal.get(0, 0), 0);
    EXPECT_DOUBLE_EQ(model.ncgDirection0[0].forceTotal.get(1, 0), 0);

    // Add additional assertions if needed
}
*/
