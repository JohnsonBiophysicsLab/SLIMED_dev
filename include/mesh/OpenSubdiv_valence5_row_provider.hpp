/**
 * @file OpenSubdiv_valence5_row_provider.hpp
 * @brief Guarded stock OpenSubdiv rows for the accepted valence-5 fixture.
 */

#pragma once

#include "energy_force/Source_keyed_kernel_call.hpp"

#include <string>
#include <vector>

class Mesh;

namespace slimed::opensubdiv_valence5
{
struct OpenSubdivValence5RowProviderRequest
{
    bool phase1ProviderExplicitRequest = false;
};

struct OpenSubdivValence5RowProviderResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool opensubdivCompiled = false;
    bool explicitRequestReceived = false;
    bool exactTopologyIdentityValidated = false;
    bool topologySourceMappingValidated = false;
    bool ptexFaceIdentityValidated = false;
    bool exactSamplePlanValidated = false;
    bool exactNineSourceCoverageValidated = false;
    bool doublePrecisionRowsGenerated = false;
    bool constantFieldInvariantsValidated = false;
    bool mixedDerivativeRowsDuplicated = false;
    bool rowsGenerated = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionMeshMutated = false;
    bool productionOneRingsMutated = false;
    bool defaultEvaluatorCaller = false;
};

/**
 * Build caller-owned 20 x 3 x 7 stock whole-Ptex rows for the reviewed
 * closed positive-depth valence-5 topology.
 *
 * Each row is keyed by the exact nine original source IDs supported by that
 * face. The complete package is returned only after topology orientation,
 * Ptex identity, sample order, source mapping, finite coefficients,
 * constant-field invariants, and mixed-derivative duplication pass. The
 * function accepts Mesh by const reference, never invokes production force
 * algebra, never mutates one-rings or Mesh state, and never enables routing.
 * Default builds return an explicit dependency-disabled rejection.
 */
OpenSubdivValence5RowProviderResult
build_guarded_opensubdiv_valence5_rows(
    const Mesh &mesh,
    const OpenSubdivValence5RowProviderRequest &request);
} // namespace slimed::opensubdiv_valence5
