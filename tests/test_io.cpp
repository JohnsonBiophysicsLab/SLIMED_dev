#include "test_io.hpp"

#include <cmath>
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
