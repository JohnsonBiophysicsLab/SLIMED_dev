/**
 * @file OpenSubdiv_valence3_row_provider.hpp
 * @brief Guarded stock OpenSubdiv rows for reviewed valence-3 candidates.
 */

#pragma once

#include "energy_force/Source_keyed_kernel_call.hpp"

#include <string>
#include <vector>

class Mesh;

namespace slimed::opensubdiv_valence3
{
enum class Valence3TopologyKind
{
    CanonicalTetrahedron = 0,
    TriangularBipyramid344 = 1,
};

struct OpenSubdivValence3RowProviderRequest
{
    bool phase1ProviderExplicitRequest = false;
    Valence3TopologyKind topology = Valence3TopologyKind::CanonicalTetrahedron;
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
    bool exactFiveSourceBoundaryValidated = false;
    bool triangularBipyramidTopologyValidated = false;
    int sourceCount = 0;
    int faceCount = 0;
    Valence3TopologyKind topology = Valence3TopologyKind::CanonicalTetrahedron;
    bool doublePrecisionRowsGenerated = false;
    bool constantFieldInvariantsValidated = false;
    bool mixedDerivativeRowsDuplicated = false;
    int opensubdivVersionNumber = 0;
    int adaptiveIsolationLevel = 0;
    bool rowsGenerated = false;
    bool immutableRowCacheHit = false;
    bool immutableRowCachePopulated = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionMeshMutated = false;
    bool productionOneRingsMutated = false;
    bool defaultEvaluatorCaller = false;
};

/**
 * Build caller-owned stock whole-Ptex rows for an explicitly selected,
 * reviewed closed valence-3 candidate. The default selection remains the
 * canonical 4 x 3 x 7 x 4 tetrahedron package. Phase-5 proof callers may
 * explicitly request the 6 x 3 x 7 x 5 triangular-bipyramid package.
 *
 * The provider is proof-only. It requires an explicit request, validates the
 * complete selected topology and source boundary before returning rows, and
 * never mutates Mesh state or enables production routing. Production callers
 * do not select the broader topology and remain tetrahedron-only.
 */
OpenSubdivValence3RowProviderResult
build_guarded_opensubdiv_valence3_rows(
    const Mesh &mesh,
    const OpenSubdivValence3RowProviderRequest &request);
} // namespace slimed::opensubdiv_valence3
