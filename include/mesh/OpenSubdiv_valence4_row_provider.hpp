/**
 * @file OpenSubdiv_valence4_row_provider.hpp
 * @brief Guarded OpenSubdiv rows for the approved closed valence-4 topology.
 */

#pragma once

#include "energy_force/Source_keyed_kernel_call.hpp"

#include <string>
#include <vector>

class Mesh;

namespace slimed::opensubdiv_valence4
{
struct OpenSubdivValence4RowProviderRequest
{
    bool reviewerApprovedExplicitRequest = false;
};

struct OpenSubdivValence4RowProviderResult
{
    bool accepted = false;
    std::string rejectionReason;
    bool opensubdivCompiled = false;
    bool explicitRequestReceived = false;
    bool topologySourceMappingValidated = false;
    bool ptexFaceIdentityValidated = false;
    bool exactSamplePlanValidated = false;
    bool exactSourceCoverageValidated = false;
    bool doublePrecisionRowsGenerated = false;
    bool constantFieldInvariantsValidated = false;
    bool mixedDerivativeRowsDuplicated = false;
    bool rowsGenerated = false;
    std::vector<source_keyed_kernel::SourceKeyedFaceRows> rows;

    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
    bool defaultEvaluatorCaller = false;
};

/**
 * Build a complete caller-owned 8 x 3 x 7 x 6 row package for the approved
 * canonical octahedron.
 *
 * The complete package is returned only after topology, Ptex face identity,
 * sample order, derivative order, source coverage, and finite coefficients
 * have all passed validation. The function never mutates Mesh state, never
 * populates Face::oneRingVertices, and never enables a production route.
 * Default builds return an explicit dependency-disabled rejection.
 */
OpenSubdivValence4RowProviderResult
build_guarded_opensubdiv_valence4_rows(
    const Mesh &mesh,
    const OpenSubdivValence4RowProviderRequest &request);
} // namespace slimed::opensubdiv_valence4
