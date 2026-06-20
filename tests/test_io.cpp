#include "test_io.hpp"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace
{
std::filesystem::path create_clean_test_dir(const std::string &name)
{
    const std::filesystem::path dir = std::filesystem::temp_directory_path() / ("slimed_" + name);
    std::filesystem::remove_all(dir);
    std::filesystem::create_directories(dir);
    return dir;
}

Param load_example_param()
{
    Param param;
    EXPECT_TRUE(import_param_file(param, "./data/example/example.params"));
    param.VERBOSE_MODE = false;
    param.meshpointOutput = false;
    param.xyzOutput = false;
    param.surfacepointOutput = false;
    return param;
}

void initialize_flat_example_mesh(Mesh &mesh)
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
    mesh.Compute_Energy_And_Force();
    mesh.update_previous_coord_for_vertex();
    mesh.update_previous_force_for_vertex();
}
}

/**
 * @brief Test import_kv_string function
 *
 */
TEST(PopSpaceTest, BasicTest)
{
    EXPECT_EQ(pop_space("Hello World"), "HelloWorld");
    EXPECT_EQ(pop_space("Spaces   Removed"), "SpacesRemoved");
    EXPECT_EQ(pop_space("\tTabs\tRemoved"), "TabsRemoved");
    EXPECT_EQ(pop_space("Mixed\t\tSpaces \tRemoved"), "MixedSpacesRemoved");
}

TEST(TrimTrailingSemicolonTest, BasicTest)
{
    EXPECT_EQ(trim_trailing_semicolon("slimed_restart.chk;"), "slimed_restart.chk");
    EXPECT_EQ(trim_trailing_semicolon("false;"), "false");
    EXPECT_EQ(trim_trailing_semicolon("slimed_restart.chk"), "slimed_restart.chk");
    EXPECT_EQ(trim_trailing_semicolon(""), "");
}

/**
 * @brief Test import_kv_string function
 *
 */
TEST(ImportKVStringTest, BoundaryTypeTest)
{
    Param param;
    import_kv_string("boundaryType", "Periodic", param);
    EXPECT_EQ(param.boundaryCondition, BoundaryType::Periodic);

    import_kv_string("boundaryType", "Free", param);
    EXPECT_EQ(param.boundaryCondition, BoundaryType::Free);

    import_kv_string("boundaryType", "Unknown", param);
    EXPECT_EQ(param.boundaryCondition, BoundaryType::Fixed);
}

TEST(ParamDefaultTest, AreaAndVolumeDefaultsAreInitialized)
{
    Param param;

    EXPECT_TRUE(param.setRelaxAreaToDefault);
    EXPECT_DOUBLE_EQ(param.kSpring, 0.0);
    EXPECT_DOUBLE_EQ(param.area0, 0.0);
    EXPECT_DOUBLE_EQ(param.area, 0.0);
    EXPECT_DOUBLE_EQ(param.vol0, 0.0);
    EXPECT_DOUBLE_EQ(param.vol, 0.0);
    EXPECT_DOUBLE_EQ(param.insertCurv, 0.0);
    EXPECT_DOUBLE_EQ(param.spontCurv, 0.0);
    EXPECT_DOUBLE_EQ(param.dFaceX, 0.0);
    EXPECT_DOUBLE_EQ(param.dFaceY, 0.0);
    EXPECT_DOUBLE_EQ(param.meanL, 0.0);
    EXPECT_EQ(param.subDivideTimes, 0);
    EXPECT_DOUBLE_EQ(param.elementTriangleArea0, 0.0);
}

TEST(ParamImportTest, ExplicitRelaxAreaDisablesDefaultRelaxedArea)
{
    Param param;

    EXPECT_TRUE(import_kv_string("relaxArea", "123.5", param));

    EXPECT_FALSE(param.setRelaxAreaToDefault);
    EXPECT_DOUBLE_EQ(param.area0, 123.5);
}

/**
 * @brief Test the import_param_file function.
 *
 * Using the following physical constants:
 * c0Insertion = 0.8				# spontaneous curvature of insertion
 *   c0Membrane = 0.0				# spontaneous curvature of membrane
 *   kcMembraneBending = 83.4		# membrane bending constant (pN.nm)
 *   usMembraneStretching = 250.0	# membrane streching modulus (pN/nm)
 *   uvVolumeConstraint = 0.0		# volume constraint coefficient (pN/nm^2)
 *   isGlobalConstraint = false      # true to enable global mode for area and volume
 *   KBT = 4.17                      # 1KbT = 4.17 pN.nm
 *
 *    # dynamics model parameters
 *    timeStep = 0.001                  # in us
 *    diffConst = 1.0                # diffusion constant, nm^2/us
 * This test case checks whether the import_param_file function correctly reads and updates the Param object.
 */
TEST(ParamImportTest, ImportParamFile)
{
    // Create a Param object for testing
    Param testParam;

    // Specify the file path for the parameter file
    std::string filepath = "./data/example/example.params";

    // Call the import_param_file function
    bool result = import_param_file(testParam, filepath);

    // Check if the import was successful
    EXPECT_TRUE(result);

    // Check specific values in the Param object after import
    // Modify these expectations based on the actual structure of your Param object
    EXPECT_EQ(testParam.maxIterations, 10000); // Example expectation
    EXPECT_DOUBLE_EQ(testParam.insertCurv, 0.8);
    EXPECT_DOUBLE_EQ(testParam.spontCurv, 0.0);
    EXPECT_DOUBLE_EQ(testParam.kCurv, 83.4);
    EXPECT_DOUBLE_EQ(testParam.uSurf, 250.0);
    EXPECT_DOUBLE_EQ(testParam.uVol, 0.0);
    EXPECT_FALSE(testParam.isGlobalConstraint);
    EXPECT_DOUBLE_EQ(testParam.KBT, 4.17);
    EXPECT_FALSE(testParam.thermalFluctuationEnabled);
    EXPECT_EQ(testParam.thermalFluctuationInterval, 50);
    EXPECT_DOUBLE_EQ(testParam.thermalFluctuationTemperatureKelvin, 298.0);
    EXPECT_DOUBLE_EQ(testParam.thermalFluctuationMinTemperatureKelvin, 298.0);
    EXPECT_DOUBLE_EQ(testParam.thermalFluctuationCoolingRate, 1.0);
    EXPECT_DOUBLE_EQ(testParam.thermalFluctuationStepScale, 0.02);
    EXPECT_DOUBLE_EQ(testParam.timeStep, 0.001);
    EXPECT_DOUBLE_EQ(testParam.diffConst, 1.0);
    EXPECT_TRUE(testParam.setRelaxAreaToDefault);

    // Add more expectations based on your Param object - GPT
}

TEST(ParamImportTest, ExampleFlatMeshInitialEnergyAndForceAreFinite)
{
    Param param;
    ASSERT_TRUE(import_param_file(param, "./data/example/example.params"));
    param.VERBOSE_MODE = false;

    Mesh mesh(param);
    mesh.setup_flat();
    mesh.calculate_element_area_volume();
    if (mesh.param.setRelaxAreaToDefault)
    {
        mesh.sum_membrane_area_and_volume(mesh.param.area0, mesh.param.vol0);
    }
    else
    {
        double initArea = 0.0;
        mesh.sum_membrane_area_and_volume(initArea, mesh.param.vol0);
    }

    mesh.update_previous_coord_for_vertex();
    mesh.update_reference_coord_from_previous_coord();
    mesh.Compute_Energy_And_Force();

    EXPECT_TRUE(std::isfinite(mesh.param.area0));
    EXPECT_GT(mesh.param.area0, 0.0);
    EXPECT_TRUE(std::isfinite(mesh.param.vol0));
    EXPECT_DOUBLE_EQ(mesh.param.vol0, 0.0);
    EXPECT_TRUE(std::isfinite(mesh.param.energy.energyTotal));

    const double meanForce = mesh.calculate_mean_force();
    EXPECT_TRUE(std::isfinite(meanForce));

    for (const Vertex &vertex : mesh.vertices)
    {
        for (int component = 0; component < 3; ++component)
        {
            EXPECT_TRUE(std::isfinite(vertex.force.forceTotal(component, 0)))
                << "vertex " << vertex.index << " component " << component;
        }
    }
}

TEST(ImportKVStringTest, ThermalFluctuationParameters)
{
    Param param;
    EXPECT_TRUE(import_kv_string("thermalFluctuationEnabled", "true", param));
    EXPECT_TRUE(import_kv_string("thermalFluctuationInterval", "7", param));
    EXPECT_TRUE(import_kv_string("thermalFluctuationTemperatureKelvin", "310.0", param));
    EXPECT_TRUE(import_kv_string("thermalFluctuationMinTemperatureKelvin", "298.0", param));
    EXPECT_TRUE(import_kv_string("thermalFluctuationCoolingRate", "0.95", param));
    EXPECT_TRUE(import_kv_string("thermalFluctuationStepScale", "0.01", param));

    EXPECT_TRUE(param.thermalFluctuationEnabled);
    EXPECT_EQ(param.thermalFluctuationInterval, 7);
    EXPECT_DOUBLE_EQ(param.thermalFluctuationTemperatureKelvin, 310.0);
    EXPECT_DOUBLE_EQ(param.thermalFluctuationMinTemperatureKelvin, 298.0);
    EXPECT_DOUBLE_EQ(param.thermalFluctuationCoolingRate, 0.95);
    EXPECT_DOUBLE_EQ(param.thermalFluctuationStepScale, 0.01);
}

TEST(OutputCadenceTest, CheckpointAndSnapshotCadenceAreExplicit)
{
    Param param;
    param.checkpointOutputInterval = 3;

    EXPECT_FALSE(should_write_restart_checkpoint(param, 1));
    EXPECT_FALSE(should_write_restart_checkpoint(param, 2));
    EXPECT_TRUE(should_write_restart_checkpoint(param, 3));
    EXPECT_TRUE(should_write_restart_checkpoint(param, 6));

    param.checkpointOutputInterval = 0;
    EXPECT_FALSE(should_write_restart_checkpoint(param, 3));

    EXPECT_TRUE(should_write_periodic_vertex_snapshot(0));
    EXPECT_FALSE(should_write_periodic_vertex_snapshot(1));
    EXPECT_TRUE(should_write_periodic_vertex_snapshot(10000));
}

TEST(OutputWriteTest, EnergyForceWriterClosesReadableFile)
{
    const std::filesystem::path dir = create_clean_test_dir("energy_force_writer");
    const std::filesystem::path outputPath = dir / "EnergyForce.csv";

    Param param = load_example_param();
    Mesh mesh(param);
    initialize_flat_example_mesh(mesh);
    Record record(2);
    record.add(mesh.param.area, mesh.param.energy, mesh.calculate_mean_force());
    Model model(mesh, record);

    ASSERT_TRUE(write_energy_force_data_to_csv(model, outputPath.string()));

    std::ifstream input(outputPath);
    ASSERT_TRUE(input.is_open());

    std::string header;
    std::string row;
    ASSERT_TRUE(static_cast<bool>(std::getline(input, header)));
    ASSERT_TRUE(static_cast<bool>(std::getline(input, row)));
    EXPECT_NE(header.find("E_Curvature"), std::string::npos);
    EXPECT_FALSE(row.empty());
}

TEST(CheckpointOutputTest, CheckpointOutputPathRespectsParams)
{
    const std::filesystem::path dir = create_clean_test_dir("checkpoint_output_path");

    Param param = load_example_param();
    param.checkpointOutputFile = (dir / "custom_restart.chk").string();
    Mesh mesh(param);
    initialize_flat_example_mesh(mesh);
    Record record(4);
    record.add(mesh.param.area, mesh.param.energy, mesh.calculate_mean_force());
    Model model(mesh, record);
    model.iteration = 2;
    model.stepSize = 0.125;

    ASSERT_TRUE(write_model_restart_checkpoint(model, model.mesh.param.checkpointOutputFile, 3));

    EXPECT_TRUE(std::filesystem::exists(dir / "custom_restart.chk"));
    EXPECT_FALSE(std::filesystem::exists(dir / "slimed_restart.chk"));
}

TEST(CheckpointRestartTest, RestartReadsExpectedCheckpointFields)
{
    const std::filesystem::path dir = create_clean_test_dir("checkpoint_restart_fields");
    const std::filesystem::path checkpointPath = dir / "restart.chk";

    Param param = load_example_param();
    Mesh mesh(param);
    initialize_flat_example_mesh(mesh);
    Record record(4);
    record.add(mesh.param.area, mesh.param.energy, mesh.calculate_mean_force());
    Model model(mesh, record);
    model.iteration = 4;
    model.stepSize = 0.25;
    model.oa.usingNCG = false;
    model.oa.trialStepSize = 0.5;
    model.currentCoolingStep = 7;
    model.mesh.param.springConst = 3.5;
    model.mesh.vertices[0].coord.set(0, 0, 12.25);
    model.ncgDirection0[0].forceTotal.set(1, 0, -2.0);

    ASSERT_TRUE(write_model_restart_checkpoint(model, checkpointPath.string(), 5));

    Param restartParam = load_example_param();
    Mesh restartMesh(restartParam);
    initialize_flat_example_mesh(restartMesh);
    Record restartRecord(4);
    restartRecord.add(restartMesh.param.area,
                      restartMesh.param.energy,
                      restartMesh.calculate_mean_force());
    Model restartModel(restartMesh, restartRecord);

    ASSERT_TRUE(load_model_restart_checkpoint(restartModel, checkpointPath.string()));

    EXPECT_EQ(restartModel.iteration, 5);
    EXPECT_DOUBLE_EQ(restartModel.stepSize, 0.25);
    EXPECT_FALSE(restartModel.oa.usingNCG);
    EXPECT_DOUBLE_EQ(restartModel.oa.trialStepSize, 0.5);
    EXPECT_EQ(restartModel.currentCoolingStep, 7);
    EXPECT_DOUBLE_EQ(restartModel.mesh.param.springConst, 3.5);
    EXPECT_DOUBLE_EQ(restartModel.mesh.vertices[0].coord(0, 0), 12.25);
    EXPECT_DOUBLE_EQ(restartModel.ncgDirection0[0].forceTotal(1, 0), -2.0);
    ASSERT_EQ(restartModel.record.energyVec.size(), model.record.energyVec.size());
    EXPECT_DOUBLE_EQ(restartModel.record.meanForce[0], model.record.meanForce[0]);
}

// Test import_mesh_from_vertices_faces function
TEST(ImportMeshTest, BasicTest)
{
    Param param;
    Mesh mesh(param);
    std::string verticesFilepath = "./data/example/vertices_flat.csv";
    std::string facesFilepath = "./data/example/faces_flat.csv";

    EXPECT_TRUE(import_mesh_from_vertices_faces(mesh, verticesFilepath, facesFilepath));

    // Add more assertions or checks based on your specific expectations
}
