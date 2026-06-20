#include "energy_force/Energy_force_evaluator.hpp"

#include "mesh/Mesh.hpp"

void EnergyForceEvaluator::evaluate(Mesh &mesh) const
{
    mesh.Compute_Energy_And_Force();
}
