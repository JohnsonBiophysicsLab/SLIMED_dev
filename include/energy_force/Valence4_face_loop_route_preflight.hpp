/**
 * @file Valence4_face_loop_route_preflight.hpp
 * @brief Inert preflight for the approved valence-4 source-keyed route.
 */

#pragma once

#include "energy_force/Source_keyed_kernel_call.hpp"

#include <string>
#include <vector>

class Mesh;

namespace slimed::valence4_route_preflight
{
struct Valence4FaceLoopRoutePreflightResult
{
    bool supported = false;
    std::string rejectionReason;
    int sourceCount = 0;
    std::vector<source_keyed_kernel::SourceMappingView> mappings;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
};

/**
 * Build an owned, source-keyed face-loop route candidate for the approved
 * closed valence-4 topology.
 *
 * The preflight is production-facing but inert: it does not populate
 * Face::oneRingVertices, does not mutate Mesh/Face/Vertex state, does not
 * call the membrane force loop, and does not authorize route activation.
 */
Valence4FaceLoopRoutePreflightResult
build_guarded_valence4_face_loop_route_preflight(const Mesh &mesh);
} // namespace slimed::valence4_route_preflight
