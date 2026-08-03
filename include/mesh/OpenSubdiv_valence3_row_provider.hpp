/**
 * @file OpenSubdiv_valence3_row_provider.hpp
 * @brief Guarded stock OpenSubdiv rows for the candidate valence-3 tetrahedron.
 */

#pragma once

#include "energy_force/Source_keyed_kernel_call.hpp"

#include <string>
#include <vector>

class Mesh;

namespace slimed::opensubdiv_valence3
{
struct OpenSubdivValence3RowProviderRequest
{
    bool phase1ProviderExplicitRequest = false;
};

struct OpenSubdivValence3RowProviderResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool opensubdivCompiled = false;
    bool explicitRequestReceived = false;
    bool exactTopologyIdentityValidated = false;
    bool topologySourceMappingValidated = false;
    bool ptexFaceIdentityValidated = false;
    bool exactSamplePlanValidated = false;
    bool exactFourSourceBoundaryValidated = false;
    bool doublePrecisionRowsGenerated = false;
    bool constantFieldInvariantsValidated = false;
    bool mixedDerivativeRowsDuplicated = false;
    int opensubdivVersionNumber = 0;
    int adaptiveIsolationLevel = 0;
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
 * Build caller-owned 4 x 3 x 7 x 4 stock whole-Ptex rows for the canonical
 * closed valence-3 tetrahedron candidate.
 *
 * The provider is proof-only. It requires an explicit request, validates the
 * complete topology and source boundary before returning rows, and never
 * mutates Mesh state or enables production routing.
 */
OpenSubdivValence3RowProviderResult
build_guarded_opensubdiv_valence3_rows(
    const Mesh &mesh,
    const OpenSubdivValence3RowProviderRequest &request);
} // namespace slimed::opensubdiv_valence3
