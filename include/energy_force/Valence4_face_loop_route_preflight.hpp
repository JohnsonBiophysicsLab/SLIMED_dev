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

struct Valence4FaceLoopRouteRequest
{
    bool reviewerApprovedExplicitRequest = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;
    std::vector<source_keyed_kernel::SourceKeyedFaceForces> forces;
};

struct Valence4FaceLoopRouteRequestResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitRouteRequested = false;
    bool explicitRouteRequestAccepted = false;
    bool sourceKeyedAccumulationExecuted = false;
    Valence4FaceLoopRoutePreflightResult preflight;
    source_keyed_kernel::PreparedSourceKeyedKernelCall prepared;
    std::vector<source_keyed_kernel::SourceForceKinds>
        accumulatedSourceForces;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
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

/**
 * Validate an explicit reviewer-approved valence-4 route request without
 * installing it in the default evaluator or mutating production mesh state.
 *
 * This boundary remains inert: a missing explicit request is rejected by
 * default, accepted requests only prepare caller-owned source-keyed rows and
 * accumulated forces, and route activation still requires later review.
 */
Valence4FaceLoopRouteRequestResult
evaluate_guarded_valence4_face_loop_route_request(
    const Mesh &mesh,
    const Valence4FaceLoopRouteRequest &request);
} // namespace slimed::valence4_route_preflight
