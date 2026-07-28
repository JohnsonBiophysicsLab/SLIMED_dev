/**
 * @file Valence4_production_face_loop.hpp
 * @brief Internal guarded entry into the production membrane face loop.
 */

#pragma once

#include "energy_force/Valence4_face_loop_route_preflight.hpp"

class Mesh;

namespace slimed::valence4_route_preflight
{
/**
 * Commit a fully validated valence-4 transaction through the shared production
 * membrane face loop and completion phase.
 *
 * Callers must validate the complete transaction and all destinations before
 * invoking this internal boundary. The function does not install a default
 * route or populate Face::oneRingVertices.
 */
void execute_guarded_valence4_production_face_loop(
    Mesh &mesh,
    const Valence4FaceGeometryStagingResult &geometry,
    const Valence4FaceLoopScientificRequestResult &scientific);
} // namespace slimed::valence4_route_preflight
