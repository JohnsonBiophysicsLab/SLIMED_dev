#include "test_optimization_algorithm.hpp"

#include <cmath>
#include <limits>

namespace
{
void set_force_total(Force &force, double x, double y, double z)
{
    force.forceTotal.set(0, 0, x);
    force.forceTotal.set(1, 0, y);
    force.forceTotal.set(2, 0, z);
}

void add_single_vertex(Mesh &mesh)
{
    mesh.vertices.resize(1);
    mesh.vertices[0].index = 0;
    mesh.vertices[0].coord.set(0, 0, 0.0);
    mesh.vertices[0].coord.set(1, 0, 0.0);
    mesh.vertices[0].coord.set(2, 0, 0.0);
}
}

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

TEST(OptimizationAlgorithmTest, SimpleQuadraticWolfeStepAcceptsKnownMinimum)
{
    OptimizationAlgorithm optimizer;
    const double minimizer = 2.0;
    const double x0 = 0.0;
    const double step = 1.0;
    const double force0 = minimizer - x0;
    const double direction = force0;
    const double x1 = x0 + step * direction;
    const double force1 = minimizer - x1;
    const double currentEnergy = 0.5 * (x0 - minimizer) * (x0 - minimizer);
    const double newEnergy = 0.5 * (x1 - minimizer) * (x1 - minimizer);
    const double initialDirectionalDerivative = -force0 * direction;
    const double trialDirectionalDerivative = -force1 * direction;

    EXPECT_DOUBLE_EQ(x1, minimizer);
    EXPECT_TRUE(optimizer.accepts_ncg_wolfe_step(currentEnergy,
                                                 newEnergy,
                                                 step,
                                                 initialDirectionalDerivative,
                                                 trialDirectionalDerivative));
}

TEST(OptimizationAlgorithmTest, ForceDotDirectionDefinesDescent)
{
    OptimizationAlgorithm optimizer;

    EXPECT_TRUE(optimizer.is_descent_direction(1.0));
    EXPECT_FALSE(optimizer.is_descent_direction(0.0));
    EXPECT_FALSE(optimizer.is_descent_direction(-1.0));
    EXPECT_FALSE(optimizer.is_descent_direction(std::numeric_limits<double>::quiet_NaN()));
}

TEST(OptimizationAlgorithmTest, FletcherReevesBetaRestartsForTinyOrNonFiniteInputs)
{
    OptimizationAlgorithm optimizer;

    EXPECT_DOUBLE_EQ(optimizer.compute_fletcher_reeves_beta(2.0, 8.0), 4.0);
    EXPECT_DOUBLE_EQ(optimizer.compute_fletcher_reeves_beta(0.0, 1.0), 0.0);
    EXPECT_DOUBLE_EQ(optimizer.compute_fletcher_reeves_beta(1.0, 0.0), 0.0);
    EXPECT_DOUBLE_EQ(optimizer.compute_fletcher_reeves_beta(std::numeric_limits<double>::quiet_NaN(), 1.0), 0.0);
    EXPECT_DOUBLE_EQ(optimizer.compute_fletcher_reeves_beta(1.0, std::numeric_limits<double>::infinity()), 0.0);
}

TEST(OptimizationAlgorithmTest, NcgDirectionRestartsWhenCombinedDirectionIsNotDescent)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    add_single_vertex(mesh);

    Record record(10);
    Model model(mesh, record);
    model.oa.usingNCG = true;

    set_force_total(mesh.vertices[0].forcePrev, 1.0, 0.0, 0.0);
    set_force_total(mesh.vertices[0].force, 1.0, 0.0, 0.0);
    set_force_total(model.ncgDirection0[0], -2.0, 0.0, 0.0);

    model.update_ncg_direction();

    EXPECT_EQ(model.oa.directionUpdateStatus,
              OptimizationAlgorithm::DirectionUpdateStatus::RestartedNonDescent);
    EXPECT_DOUBLE_EQ(model.ncgDirection0[0].forceTotal(0, 0), 1.0);
    EXPECT_DOUBLE_EQ(model.ncgDirection0[0].forceTotal(1, 0), 0.0);
    EXPECT_DOUBLE_EQ(model.ncgDirection0[0].forceTotal(2, 0), 0.0);
}

TEST(OptimizationAlgorithmTest, ZeroGradientLineSearchReportsConvergence)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    add_single_vertex(mesh);
    mesh.update_previous_coord_for_vertex();
    mesh.update_previous_force_for_vertex();
    mesh.param.energy.energyTotal = 0.0;

    Record record(10);
    Model model(mesh, record);
    model.oa.trialStepSize = 1.0;

    EXPECT_DOUBLE_EQ(model.linear_search_for_stepsize_to_minimize_energy(), 0.0);
    EXPECT_EQ(model.oa.lineSearchStatus,
              OptimizationAlgorithm::LineSearchStatus::ConvergedZeroGradient);
    EXPECT_DOUBLE_EQ(model.stepSize, 0.0);
}

TEST(OptimizationAlgorithmTest, LineSearchRejectsNonFiniteEnergyDerivativeAndTrialForce)
{
    OptimizationAlgorithm optimizer;
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double inf = std::numeric_limits<double>::infinity();

    EXPECT_FALSE(optimizer.accepts_ncg_wolfe_step(1.0, nan, 1.0, -1.0, 0.0));
    EXPECT_FALSE(optimizer.accepts_ncg_wolfe_step(1.0, 0.5, 1.0, -1.0, nan));
    EXPECT_FALSE(optimizer.accepts_simple_energy_decrease(1.0, nan, 1.0));
    EXPECT_FALSE(optimizer.accepts_simple_energy_decrease(1.0, 0.5, nan));
    EXPECT_FALSE(optimizer.accepts_simple_energy_decrease(1.0, 0.5, inf));
}

TEST(OptimizationAlgorithmTest, SimpleEnergyDecreaseRequiresFiniteTrialForce)
{
    OptimizationAlgorithm optimizer;

    EXPECT_TRUE(optimizer.accepts_simple_energy_decrease(1.0, 0.5, 0.0));
    EXPECT_FALSE(optimizer.accepts_simple_energy_decrease(
        1.0,
        0.5,
        std::numeric_limits<double>::quiet_NaN()));
    EXPECT_FALSE(optimizer.accepts_simple_energy_decrease(
        1.0,
        0.5,
        std::numeric_limits<double>::infinity()));
}

TEST(OptimizationAlgorithmTest, LineSearchFailsInsteadOfSucceedingOnNaNState)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    add_single_vertex(mesh);
    mesh.update_previous_coord_for_vertex();
    mesh.update_previous_force_for_vertex();
    mesh.param.energy.energyTotal = std::numeric_limits<double>::quiet_NaN();

    Record record(10);
    Model model(mesh, record);
    model.oa.trialStepSize = 1.0;

    EXPECT_DOUBLE_EQ(model.linear_search_for_stepsize_to_minimize_energy(), -1.0);
    EXPECT_EQ(model.oa.lineSearchStatus,
              OptimizationAlgorithm::LineSearchStatus::FailedNonFinite);
    EXPECT_DOUBLE_EQ(model.stepSize, -1.0);
}

TEST(OptimizationAlgorithmTest, LineSearchFailsInsteadOfSucceedingOnNaNForce)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    add_single_vertex(mesh);
    mesh.update_previous_coord_for_vertex();
    mesh.update_previous_force_for_vertex();
    set_force_total(mesh.vertices[0].forcePrev,
                    std::numeric_limits<double>::quiet_NaN(),
                    0.0,
                    0.0);
    mesh.param.energy.energyTotal = 0.0;

    Record record(10);
    Model model(mesh, record);
    model.oa.trialStepSize = 1.0;

    EXPECT_DOUBLE_EQ(model.linear_search_for_stepsize_to_minimize_energy(), -1.0);
    EXPECT_EQ(model.oa.lineSearchStatus,
              OptimizationAlgorithm::LineSearchStatus::FailedNonFinite);
    EXPECT_DOUBLE_EQ(model.stepSize, -1.0);
}
