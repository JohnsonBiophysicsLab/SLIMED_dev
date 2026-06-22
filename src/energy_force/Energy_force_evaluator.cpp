#include "energy_force/Energy_force_evaluator.hpp"

#include "mesh/Mesh.hpp"

void EnergyForceEvaluator::evaluate(Mesh &mesh) const
{
    mesh.Compute_Energy_And_Force();
}

void evaluate_energy_force(Mesh &mesh)
{
    EnergyForceEvaluator evaluator;
    evaluator.evaluate(mesh);
}
