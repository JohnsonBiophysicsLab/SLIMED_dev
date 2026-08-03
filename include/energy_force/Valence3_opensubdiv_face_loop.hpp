/**
 * @file Valence3_opensubdiv_face_loop.hpp
 * @brief Guarded proof-only valence-3 Phase-3 face-loop transaction.
 */

#pragma once

#include "energy_force/Guarded_source_keyed_production_face_loop.hpp"
#include "mesh/OpenSubdiv_valence3_row_provider.hpp"

#include <string>
#include <vector>

class Mesh;

namespace slimed::opensubdiv_valence3_phase3
{
constexpr double kReviewedPostconditionTolerance = 1.0e-10;

/** Exact-token integration-only gate. */
bool opensubdiv_valence3_phase3_requested();

struct Valence3Phase3Request
{
    bool scientificBaselineAcceptedExplicitRequest = false;
};

struct Valence3Phase3FaceObservables
{
    int faceIndex = -1;
    double meanCurvature = 0.0;
    double bendingEnergy = 0.0;
    source_keyed_kernel::Vec3 normal{{0.0, 0.0, 0.0}};
};

struct Valence3Phase3Result
{
    bool accepted = false;
    std::string rejectionReason;
    bool explicitRequestReceived = false;
    bool runtimeOptInRequested = false;
    bool exactBaselineIdentityValidated = false;
    bool exactQuadratureSamplePlanValidated = false;
    bool exactQuadratureWeightsValidated = false;
    bool zeroVolumeConstraintValidated = false;
    bool volumeFunctionalDecisionPending = true;
    bool opensubdivRowProviderExecuted = false;
    bool opensubdivRowsGenerated = false;
    bool sourceKeyedRowsPrepared = false;
    bool geometryStaged = false;
    bool scientificDryRunExecuted = false;
    bool completeTransactionValidatedBeforeMutation = false;
    bool outputStateFinite = false;
    bool faceObservablesMatchDryRun = false;
    bool sourceForcesMatchDryRun = false;
    double maxFaceObservableDifference = 0.0;
    double maxSourceForceDifference = 0.0;
    double totalArea = 0.0;
    double totalLegacyVolume = 0.0;
    std::vector<guarded_source_keyed_face_loop::GuardedFaceGeometry>
        faceGeometry;
    std::vector<Valence3Phase3FaceObservables> faceObservables;
    opensubdiv_valence3::OpenSubdivValence3RowProviderResult rowProvider;

    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionRouteEnabled = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
    bool phase4ActivationAuthorized = false;
};

/**
 * Execute the exact tetrahedron rows through the shared guarded production
 * face loop behind an explicit scientific request and the dedicated Phase-3
 * runtime gate.
 *
 * This integration baseline intentionally requires uVol == 0. The existing
 * legacy-volume energy and full-divergence force mismatch remains unresolved,
 * so a nonzero volume constraint is rejected before any Mesh write.
 */
Valence3Phase3Result evaluate_guarded_valence3_phase3_face_loop(
    Mesh &mesh,
    const Valence3Phase3Request &request);
} // namespace slimed::opensubdiv_valence3_phase3
