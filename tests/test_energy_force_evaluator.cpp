#include <cmath>
#include <limits>
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

Param make_scaffold_characterization_param()
{
    Param param = make_tiny_flat_param();
    param.sideX = 40.0;
    param.sideY = 40.0;
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

int first_force_visible_vertex_index(const Mesh &mesh)
{
    for (int i = 0; i < static_cast<int>(mesh.vertices.size()); ++i)
    {
        if (!mesh.vertices[i].isGhost && !mesh.vertices[i].isBoundary)
        {
            return i;
        }
    }
    return -1;
}

void configure_single_harmonic_scaffold(Mesh &mesh, int vertexIndex)
{
    mesh.param.isEnergyHarmonicBondIncluded = true;
    mesh.param.isGagScaffoldingEnergyIncluded = false;
    mesh.param.isIdealizedProteinLatticeEnergyIncluded = false;
    mesh.param.springConst = 2.0;
    mesh.param.lbond = 3.0;

    mesh.param.scaffoldingPoints.assign(1, Matrix(3, 1));
    mesh.param.scaffoldingPoints[0].set(0, 0, mesh.vertices[vertexIndex].coord(0, 0));
    mesh.param.scaffoldingPoints[0].set(1, 0, mesh.vertices[vertexIndex].coord(1, 0));
    mesh.param.scaffoldingPoints[0].set(2, 0, mesh.vertices[vertexIndex].coord(2, 0) - 5.0);
    mesh.param.scaffoldingPoints_correspondingVertexIndex = {vertexIndex};

    mesh.param.energy.energyHarmonicBond = std::numeric_limits<double>::quiet_NaN();
    mesh.param.energy.energyGagScaffolding = std::numeric_limits<double>::quiet_NaN();
    mesh.param.energy.energyIdealizedProteinLattice = std::numeric_limits<double>::quiet_NaN();
}

Matrix make_scaffold_point(double x, double y, double z)
{
    Matrix point(3, 1);
    point.set(0, 0, x);
    point.set(1, 0, y);
    point.set(2, 0, z);
    return point;
}

std::vector<int> first_force_visible_vertex_indices(const Mesh &mesh, int count)
{
    std::vector<int> indices;
    indices.reserve(count);
    for (int i = 0; i < static_cast<int>(mesh.vertices.size()) &&
                    static_cast<int>(indices.size()) < count; ++i)
    {
        if (!mesh.vertices[i].isGhost && !mesh.vertices[i].isBoundary)
        {
            indices.push_back(i);
        }
    }
    return indices;
}

void configure_two_subunit_idealized_lattice_scaffold(Mesh &mesh,
                                                      const std::vector<int> &vertexIndices)
{
    mesh.param.isEnergyHarmonicBondIncluded = true;
    mesh.param.isGagScaffoldingEnergyIncluded = false;
    mesh.param.isIdealizedProteinLatticeEnergyIncluded = true;
    mesh.param.idealizedProteinLatticeFileName =
        "./tests/fixtures/idealized_two_subunit_lattice.dat";
    mesh.param.springConst = 0.0;
    mesh.param.lbond = 0.0;
    mesh.param.gagKsigma = 3.0;
    mesh.param.gagKtheta = 0.0;
    mesh.param.gagKphi = 0.0;
    mesh.param.gagKomega = 0.0;

    mesh.param.scaffoldingPoints = {
        make_scaffold_point(0.0, 0.0, 0.0),
        make_scaffold_point(4.0, 0.0, 0.0),
    };
    mesh.param.scaffoldingPoints_correspondingVertexIndex = vertexIndices;

    mesh.param.energy.energyHarmonicBond = std::numeric_limits<double>::quiet_NaN();
    mesh.param.energy.energyGagScaffolding = std::numeric_limits<double>::quiet_NaN();
    mesh.param.energy.energyIdealizedProteinLattice = std::numeric_limits<double>::quiet_NaN();
}

double expected_single_harmonic_scaffold_energy()
{
    const double distance = 5.0;
    const double springConst = 2.0;
    const double lbond = 3.0;
    return 0.5 * springConst * std::pow(distance - lbond, 2.0);
}

double expected_two_subunit_idealized_lattice_energy()
{
    const double sigmaDelta = 0.5;
    const double gagKsigma = 3.0;
    return 0.5 * gagKsigma * sigmaDelta * sigmaDelta;
}

Matrix expected_single_harmonic_scaffold_force()
{
    Matrix force(3, 1);
    force.set(2, 0, -4.0);
    return force;
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

struct FaceGeometry
{
    double area = 0.0;
    double volume = 0.0;
};

std::vector<FaceGeometry> copy_face_geometry(const Mesh &mesh)
{
    std::vector<FaceGeometry> geometry;
    geometry.reserve(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        geometry.push_back({face.elementArea, face.elementVolume});
    }
    return geometry;
}

void expect_same_face_geometry(const std::vector<FaceGeometry> &expected,
                               const Mesh &actual,
                               const double expectedGhostArea,
                               const double expectedGhostVolume)
{
    ASSERT_EQ(expected.size(), actual.faces.size());
    for (int i = 0; i < static_cast<int>(expected.size()); ++i)
    {
        if (actual.faces[i].isGhost)
        {
            EXPECT_DOUBLE_EQ(expectedGhostArea, actual.faces[i].elementArea)
                << "ghost face " << i << " elementArea";
            EXPECT_DOUBLE_EQ(expectedGhostVolume, actual.faces[i].elementVolume)
                << "ghost face " << i << " elementVolume";
        }
        else
        {
            EXPECT_DOUBLE_EQ(expected[i].area, actual.faces[i].elementArea)
                << "face " << i << " elementArea";
            EXPECT_DOUBLE_EQ(expected[i].volume, actual.faces[i].elementVolume)
                << "face " << i << " elementVolume";
        }
    }
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

TEST(EnergyForceEvaluatorTest, SharedHelperRefreshesStaleGeometryAreaAndVolume)
{
    Param expectedParam = make_scaffold_characterization_param();
    Param evaluatorParam = make_scaffold_characterization_param();
    Mesh expectedMesh(expectedParam);
    Mesh evaluatorMesh(evaluatorParam);
    initialize_area_reference(expectedMesh);
    initialize_area_reference(evaluatorMesh);

    for (int i = 0; i < static_cast<int>(expectedMesh.vertices.size()); ++i)
    {
        const double displacement = 0.05 * std::sin(0.7 * static_cast<double>(i));
        expectedMesh.vertices[i].coord.set(2, 0, displacement);
        evaluatorMesh.vertices[i].coord.set(2, 0, displacement);
    }

    expectedMesh.calculate_element_area_volume();
    expectedMesh.sum_membrane_area_and_volume(expectedMesh.param.area,
                                              expectedMesh.param.vol);
    const std::vector<FaceGeometry> expectedGeometry =
        copy_face_geometry(expectedMesh);

    evaluatorMesh.param.area = -123.0;
    evaluatorMesh.param.vol = 456.0;
    for (Face &face : evaluatorMesh.faces)
    {
        face.elementArea = -1.0;
        face.elementVolume = 2.0;
    }

    evaluate_energy_force(evaluatorMesh);

    EXPECT_DOUBLE_EQ(expectedMesh.param.area, evaluatorMesh.param.area);
    EXPECT_DOUBLE_EQ(expectedMesh.param.vol, evaluatorMesh.param.vol);
    expect_same_face_geometry(expectedGeometry, evaluatorMesh, -1.0, 2.0);
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

TEST(EnergyForceEvaluatorTest, SharedHelperRecordsScaffoldEnergyAndForceSideEffects)
{
    Param baselineParam = make_scaffold_characterization_param();
    Mesh baselineMesh(baselineParam);
    initialize_area_reference(baselineMesh);
    evaluate_energy_force(baselineMesh);

    Param scaffoldParam = make_scaffold_characterization_param();
    Mesh scaffoldMesh(scaffoldParam);
    initialize_area_reference(scaffoldMesh);
    const int bondedVertexIndex = first_force_visible_vertex_index(scaffoldMesh);
    ASSERT_GE(bondedVertexIndex, 0);
    configure_single_harmonic_scaffold(scaffoldMesh, bondedVertexIndex);

    evaluate_energy_force(scaffoldMesh);

    const double expectedEnergy = expected_single_harmonic_scaffold_energy();
    const Matrix expectedForce = expected_single_harmonic_scaffold_force();
    EXPECT_TRUE(std::isfinite(scaffoldMesh.param.energy.energyHarmonicBond));
    EXPECT_TRUE(std::isfinite(scaffoldMesh.param.energy.energyGagScaffolding));
    EXPECT_TRUE(std::isfinite(scaffoldMesh.param.energy.energyIdealizedProteinLattice));
    EXPECT_DOUBLE_EQ(expectedEnergy, scaffoldMesh.param.energy.energyHarmonicBond);
    EXPECT_DOUBLE_EQ(0.0, scaffoldMesh.param.energy.energyGagScaffolding);
    EXPECT_DOUBLE_EQ(0.0, scaffoldMesh.param.energy.energyIdealizedProteinLattice);
    EXPECT_NEAR(expectedEnergy,
                scaffoldMesh.param.energy.energyTotal - baselineMesh.param.energy.energyTotal,
                1.0e-10);

    ASSERT_EQ(1, static_cast<int>(scaffoldMesh.forceOnScaffoldingPoints.size()));
    for (int component = 0; component < 3; ++component)
    {
        const double expectedComponent = expectedForce(component, 0);
        const double harmonicForce =
            scaffoldMesh.vertices[bondedVertexIndex].force.forceHarmonicBond(component, 0);
        EXPECT_DOUBLE_EQ(expectedComponent, harmonicForce)
            << "bonded vertex harmonic force component " << component;
        EXPECT_NEAR(expectedComponent,
                    scaffoldMesh.vertices[bondedVertexIndex].force.forceTotal(component, 0)
                        - baselineMesh.vertices[bondedVertexIndex].force.forceTotal(component, 0),
                    1.0e-10)
            << "bonded vertex total force scaffold delta component " << component;
        EXPECT_DOUBLE_EQ(-expectedComponent,
                         scaffoldMesh.forceOnScaffoldingPoints[0](component, 0))
            << "scaffold point force component " << component;
        EXPECT_DOUBLE_EQ(-expectedComponent,
                         scaffoldMesh.forceTotalOnScaffolding(component, 0))
            << "total scaffold force component " << component;
    }
}

TEST(EnergyForceEvaluatorTest, SharedHelperRecordsIdealizedLatticeScaffoldEnergy)
{
    Param baselineParam = make_scaffold_characterization_param();
    Mesh baselineMesh(baselineParam);
    initialize_area_reference(baselineMesh);
    evaluate_energy_force(baselineMesh);

    Param latticeParam = make_scaffold_characterization_param();
    Mesh latticeMesh(latticeParam);
    initialize_area_reference(latticeMesh);
    const std::vector<int> bondedVertexIndices =
        first_force_visible_vertex_indices(latticeMesh, 2);
    ASSERT_EQ(2, static_cast<int>(bondedVertexIndices.size()));
    configure_two_subunit_idealized_lattice_scaffold(latticeMesh, bondedVertexIndices);
    ASSERT_TRUE(latticeMesh.initialize_gag_scaffolding_topology());
    ASSERT_TRUE(latticeMesh.gagScaffoldingTopologyInitialized);
    ASSERT_EQ(1, static_cast<int>(latticeMesh.gagInteractions.size()));

    latticeMesh.param.scaffoldingPoints[1].set(0, 0, 4.5);

    evaluate_energy_force(latticeMesh);

    const double expectedEnergy = expected_two_subunit_idealized_lattice_energy();
    EXPECT_TRUE(std::isfinite(latticeMesh.param.energy.energyHarmonicBond));
    EXPECT_TRUE(std::isfinite(latticeMesh.param.energy.energyGagScaffolding));
    EXPECT_TRUE(std::isfinite(latticeMesh.param.energy.energyIdealizedProteinLattice));
    EXPECT_DOUBLE_EQ(0.0, latticeMesh.param.energy.energyHarmonicBond);
    EXPECT_DOUBLE_EQ(0.0, latticeMesh.param.energy.energyGagScaffolding);
    EXPECT_DOUBLE_EQ(expectedEnergy,
                     latticeMesh.param.energy.energyIdealizedProteinLattice);
    EXPECT_NEAR(expectedEnergy,
                latticeMesh.param.energy.energyTotal - baselineMesh.param.energy.energyTotal,
                1.0e-10);
    ASSERT_EQ(2, static_cast<int>(latticeMesh.forceOnScaffoldingPoints.size()));
}
