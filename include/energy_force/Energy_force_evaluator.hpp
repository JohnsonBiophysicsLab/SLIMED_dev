/**
 * @file Energy_force_evaluator.hpp
 * @brief Defines the narrow energy/force evaluator boundary.
 */
#pragma once

class Mesh;

/**
 * @brief Behavior-preserving facade for recomputing mesh energy and forces.
 *
 * The evaluator mutates Mesh state in the same way as Mesh::Compute_Energy_And_Force:
 * it refreshes area/volume, clears and recomputes current forces and face
 * energies, updates Param::energy, applies optional scaffolding energy/force,
 * and applies boundary force handling. It does not update previous-coordinate,
 * previous-force, checkpoint, record, or optimizer state.
 */
class EnergyForceEvaluator
{
public:
    void evaluate(Mesh &mesh) const;
};
