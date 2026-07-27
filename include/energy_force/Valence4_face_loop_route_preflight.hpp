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

struct Valence4FaceLoopScientificRequest
{
    bool reviewerApprovedExplicitRequest = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;
};

struct Valence4FaceGeometry
{
    int faceIndex = -1;
    double elementArea = 0.0;
    double elementVolume = 0.0;
};

struct Valence4FaceGeometryStagingRequest
{
    bool reviewerApprovedExplicitStaging = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;
};

struct Valence4FaceGeometryStagingResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitStagingRequested = false;
    bool productionGeometryEvaluated = false;
    double totalArea = 0.0;
    double totalVolume = 0.0;
    std::vector<Valence4FaceGeometry> faceGeometry;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
};

struct Valence4FaceScientificObservables
{
    int faceIndex = -1;
    double meanCurvature = 0.0;
    double bendingEnergy = 0.0;
    source_keyed_kernel::Vec3 normal{{0.0, 0.0, 0.0}};
};

struct Valence4FaceLoopScientificRequestResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitRouteRequested = false;
    bool productionScientificAlgebraExecuted = false;
    std::vector<Valence4FaceScientificObservables> faceObservables;
    Valence4FaceLoopRouteRequestResult sourceKeyedRequest;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
};

struct Valence4VertexForcePublicationRequest
{
    bool reviewerApprovedExplicitPublication = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;
};

struct Valence4VertexForcePublicationResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitPublicationRequested = false;
    bool vertexForcePublicationExecuted = false;
    Valence4FaceLoopScientificRequestResult scientificRequest;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
};

struct Valence4FaceObservablePublicationRequest
{
    bool reviewerApprovedExplicitPublication = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;
};

struct Valence4FaceObservablePublicationResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitPublicationRequested = false;
    bool faceObservablePublicationExecuted = false;
    Valence4FaceLoopScientificRequestResult scientificRequest;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
};

struct Valence4FaceLoopPublicationRequest
{
    bool reviewerApprovedExplicitPublication = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;
};

struct Valence4FaceLoopPublicationResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitPublicationRequested = false;
    bool vertexForcePublicationExecuted = false;
    bool faceObservablePublicationExecuted = false;
    bool atomicFaceLoopPublicationExecuted = false;
    Valence4FaceLoopScientificRequestResult scientificRequest;

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

/**
 * Stage production-equivalent area and legacy visible volume for an explicit
 * valence-4 row package without mutating Mesh state.
 *
 * The complete source mapping, row package, sample cardinality, quadrature
 * shape, and finite output are validated before a successful result is
 * returned. The route remains default-off and caller-owned.
 */
Valence4FaceGeometryStagingResult
stage_guarded_valence4_face_geometry(
    const Mesh &mesh,
    const Valence4FaceGeometryStagingRequest &request);

/**
 * Evaluate reviewer-approved source-keyed rows against the current mesh
 * coordinates and scientific parameters without installing a production
 * route or mutating mesh-owned observables and forces.
 *
 * The complete row package is validated before the existing
 * variable-cardinality scientific algebra is invoked. The returned
 * observables and source-keyed force contributions are owned by the caller.
 */
Valence4FaceLoopScientificRequestResult
evaluate_guarded_valence4_face_loop_scientific_request(
    Mesh &mesh,
    const Valence4FaceLoopScientificRequest &request);

/**
 * Publish the three reduced membrane-force families for an explicitly
 * approved valence-4 scientific request.
 *
 * The request remains default-off. The complete scientific request and all
 * six vertex destinations are validated before forceCurvature, forceArea,
 * and forceVolume are overwritten. Face state, forceTotal, other force
 * families, one-rings, and routing remain unchanged.
 */
Valence4VertexForcePublicationResult
evaluate_guarded_valence4_vertex_force_publication(
    Mesh &mesh,
    const Valence4VertexForcePublicationRequest &request);

/**
 * Publish caller-owned face observables after validating the complete face
 * package and allocating every replacement normal.
 *
 * The helper overwrites only meanCurvature, energy.energyCurvature, and the
 * face normal. Area, volume, other energy fields, topology, vertex state,
 * one-rings, and routing remain unchanged.
 */
void publish_valence4_face_scientific_observables_to_faces(
    const std::vector<Valence4FaceScientificObservables> &observables,
    Mesh &mesh);

/**
 * Publish face observables for an explicitly approved valence-4 scientific
 * request without installing or executing a production route.
 */
Valence4FaceObservablePublicationResult
evaluate_guarded_valence4_face_observable_publication(
    Mesh &mesh,
    const Valence4FaceObservablePublicationRequest &request);

/**
 * Atomically publish a complete accepted scientific result to the reviewed
 * vertex-force and face-observable destinations.
 *
 * Every source, destination, face identity, observable, and replacement
 * normal is validated or allocated before the first Mesh write. The helper
 * does not populate one-rings, calculate total force/energy, or enable a
 * production route.
 */
void publish_valence4_face_loop_scientific_result_atomically(
    const Valence4FaceLoopScientificRequestResult &scientificResult,
    Mesh &mesh);

/**
 * Evaluate and atomically publish the reviewed valence-4 face-loop result.
 *
 * This is a default-off production-shaped transaction boundary. It remains
 * outside the real production face loop and does not authorize routing.
 */
Valence4FaceLoopPublicationResult
evaluate_guarded_valence4_face_loop_publication(
    Mesh &mesh,
    const Valence4FaceLoopPublicationRequest &request);
} // namespace slimed::valence4_route_preflight
