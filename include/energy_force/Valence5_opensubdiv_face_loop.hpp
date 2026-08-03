/**
 * @file Valence5_opensubdiv_face_loop.hpp
 * @brief Guarded Option B Phase 2 stock valence-5 face-loop transaction.
 */

#pragma once

#include "energy_force/Guarded_source_keyed_production_face_loop.hpp"
#include "mesh/OpenSubdiv_valence5_row_provider.hpp"

#include <string>
#include <vector>

class Mesh;

namespace slimed::opensubdiv_valence5_phase2
{
constexpr double kReviewedProductionTolerance = 1.0e-10;

bool opensubdiv_valence5_phase2_requested();

/** Return whether the reviewed valence-5 production route is requested. */
bool opensubdiv_valence5_production_routing_requested();

struct Valence5Phase2Request
{
    bool reviewerApprovedExplicitRequest = false;
};

struct Valence5Phase2FaceObservables
{
    int faceIndex = -1;
    double meanCurvature = 0.0;
    double bendingEnergy = 0.0;
    source_keyed_kernel::Vec3 normal{{0.0, 0.0, 0.0}};
};

struct Valence5Phase2Result
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitRequestReceived = false;
    bool runtimeOptInRequested = false;
    bool exactQuadratureSamplePlanValidated = false;
    bool exactQuadratureWeightsValidated = false;
    bool opensubdivRowProviderExecuted = false;
    bool opensubdivRowsGenerated = false;
    bool sourceKeyedRowsPrepared = false;
    bool geometryStaged = false;
    bool scientificDryRunExecuted = false;
    bool completeTransactionValidatedBeforeMutation = false;
    bool currentStateCleared = false;
    bool productionCompletionPhasesExecuted = false;
    bool totalForcePublicationExecuted = false;
    bool totalEnergyPublicationExecuted = false;
    bool boundaryHandlingExecuted = false;
    bool outputStateFinite = false;
    bool faceObservablesMatchDryRun = false;
    bool sourceForcesMatchDryRun = false;
    double maxFaceObservableDifference = 0.0;
    double maxSourceForceDifference = 0.0;
    double totalArea = 0.0;
    double totalVolume = 0.0;
    std::vector<guarded_source_keyed_face_loop::GuardedFaceGeometry>
        faceGeometry;
    std::vector<Valence5Phase2FaceObservables> faceObservables;
    opensubdiv_valence5::OpenSubdivValence5RowProviderResult rowProvider;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
    bool phase3ActivationAuthorized = false;
};

/**
 * Execute the accepted stock valence-5 rows through the shared production
 * membrane face loop behind both an explicit request and the dedicated Phase
 * 2 runtime opt-in.
 *
 * The complete provider, source mapping, geometry, scientific dry run, and
 * production destinations are validated before mutation. This function is
 * deliberately not installed in Mesh::Compute_Energy_And_Force(); default
 * routing and Phase 3 activation remain separate decisions.
 */
Valence5Phase2Result evaluate_guarded_valence5_phase2_face_loop(
    Mesh &mesh,
    const Valence5Phase2Request &request);

/**
 * Execute the reviewed Option B transaction for the default production
 * evaluator when SLIMED_USE_OPENSUBDIV_VALENCE5=1 is explicitly set.
 *
 * An absent runtime request leaves the current fallback untouched. A present
 * request in a dependency-disabled build is rejected before mesh mutation.
 */
Valence5Phase2Result evaluate_guarded_valence5_production_route(Mesh &mesh);
} // namespace slimed::opensubdiv_valence5_phase2
