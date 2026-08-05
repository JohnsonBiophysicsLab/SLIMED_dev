#include "mesh/OpenSubdiv_valence3_row_provider.hpp"

#include "mesh/Mesh.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <memory>
#include <mutex>
#include <numeric>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#ifdef USE_OPENSUBDIV_VALENCE3
#include <opensubdiv/far/patchMap.h>
#include <opensubdiv/far/patchTableFactory.h>
#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>
#include <opensubdiv/version.h>

#if OPENSUBDIV_VERSION_NUMBER != 30700
#error "Valence-3 proof rows are qualified only for OpenSubdiv 3.7.0"
#endif
#endif

namespace slimed::opensubdiv_valence3
{
namespace
{
using source_keyed_kernel::SourceKeyedFaceRows;
using source_keyed_kernel::SourceKeyedRow;
using source_keyed_kernel::SourceKeyedSampleRows;

constexpr int kSampleCount = 3;
constexpr int kDerivativeRowCount = source_keyed_kernel::kDerivativeRowCount;
constexpr double kInvariantTolerance = 1.0e-12;

struct ApprovedTopology
{
    Valence3TopologyKind kind;
    const char *name;
    int sourceCount;
    std::vector<int> valences;
    std::vector<std::array<int, 3>> faces;
};

const ApprovedTopology *approved_topology(const Valence3TopologyKind kind)
{
    static const ApprovedTopology tetrahedron{
        Valence3TopologyKind::CanonicalTetrahedron,
        "canonical valence-3 tetrahedron",
        4,
        {3, 3, 3, 3},
        {{{0, 2, 1}}, {{0, 1, 3}}, {{0, 3, 2}}, {{1, 2, 3}}},
    };
    static const ApprovedTopology triangularBipyramid{
        Valence3TopologyKind::TriangularBipyramid344,
        "closed valence-3 3/4/4 triangular bipyramid",
        5,
        {3, 3, 4, 4, 4},
        {{{0, 2, 3}}, {{0, 3, 4}}, {{0, 4, 2}},
         {{1, 3, 2}}, {{1, 4, 3}}, {{1, 2, 4}}},
    };
    switch (kind)
    {
    case Valence3TopologyKind::CanonicalTetrahedron:
        return &tetrahedron;
    case Valence3TopologyKind::TriangularBipyramid344:
        return &triangularBipyramid;
    }
    return nullptr;
}

std::size_t topology_cache_index(const Valence3TopologyKind kind)
{
    return kind == Valence3TopologyKind::TriangularBipyramid344 ? 1u : 0u;
}

OpenSubdivValence3RowProviderResult reject(
    const std::string &reason,
    const bool opensubdivCompiled,
    const bool explicitRequestReceived)
{
    OpenSubdivValence3RowProviderResult result;
    result.rejectionReason = reason;
    result.opensubdivCompiled = opensubdivCompiled;
    result.explicitRequestReceived = explicitRequestReceived;
    return result;
}

bool exact_topology_identity(const Mesh &mesh,
                             const ApprovedTopology &topology)
{
    if (mesh.vertices.size() !=
            static_cast<std::size_t>(topology.sourceCount) ||
        mesh.faces.size() != topology.faces.size())
    {
        return false;
    }
    for (int source = 0; source < topology.sourceCount; ++source)
    {
        const Vertex &vertex = mesh.vertices[source];
        if (vertex.index != source || vertex.isBoundary || vertex.isGhost ||
            vertex.adjacentVertices.size() !=
                static_cast<std::size_t>(topology.valences[source]))
        {
            return false;
        }
    }
    for (std::size_t face = 0; face < topology.faces.size(); ++face)
    {
        const Face &actual = mesh.faces[face];
        if (actual.index != static_cast<int>(face) || actual.isGhost ||
            actual.isBoundary ||
            !actual.oneRingVertices.empty() ||
            actual.adjacentVertices.size() != 3u ||
            !std::equal(topology.faces[face].begin(),
                        topology.faces[face].end(),
                        actual.adjacentVertices.begin()))
        {
            return false;
        }
    }
    return true;
}

bool rows_are_identical(const SourceKeyedRow &left,
                        const SourceKeyedRow &right)
{
    return left.sourceIds == right.sourceIds &&
           left.coefficients == right.coefficients;
}

#ifdef USE_OPENSUBDIV_VALENCE3
using namespace OpenSubdiv;

struct RefinerDeleter
{
    void operator()(Far::TopologyRefiner *value) const { delete value; }
};

template <typename Value>
struct DeleteConst
{
    void operator()(const Value *value) const { delete value; }
};

std::unique_ptr<Far::TopologyRefiner, RefinerDeleter>
create_refiner(const Mesh &mesh, const ApprovedTopology &topology)
{
    using Descriptor = Far::TopologyDescriptor;
    std::vector<int> verticesPerFace(topology.faces.size(), 3);
    std::vector<int> vertexIndices;
    vertexIndices.reserve(topology.faces.size() * 3u);
    for (const Face &face : mesh.faces)
    {
        vertexIndices.insert(vertexIndices.end(),
                             face.adjacentVertices.begin(),
                             face.adjacentVertices.end());
    }

    Descriptor descriptor;
    descriptor.numVertices = topology.sourceCount;
    descriptor.numFaces = static_cast<int>(topology.faces.size());
    descriptor.numVertsPerFace = verticesPerFace.data();
    descriptor.vertIndicesPerFace = vertexIndices.data();

    Sdc::Options options;
    options.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);
    return std::unique_ptr<Far::TopologyRefiner, RefinerDeleter>(
        Far::TopologyRefinerFactory<Descriptor>::Create(
            descriptor,
            Far::TopologyRefinerFactory<Descriptor>::Options(
                Sdc::SCHEME_LOOP, options)));
}

std::map<int, double> aggregate_row(
    const Far::LimitStencilReal<double> &stencil,
    const double *weights)
{
    std::map<int, double> aggregated;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int entry = 0; entry < stencil.GetSize(); ++entry)
    {
        aggregated[indices[entry]] += weights[entry];
    }
    return aggregated;
}
#endif
} // namespace

OpenSubdivValence3RowProviderResult
build_guarded_opensubdiv_valence3_rows(
    const Mesh &mesh,
    const OpenSubdivValence3RowProviderRequest &request)
{
    if (!request.phase1ProviderExplicitRequest)
    {
        return reject(
            "valence-3 OpenSubdiv Phase 1 row provider remains default-off",
#ifdef USE_OPENSUBDIV_VALENCE3
            true,
#else
            false,
#endif
            false);
    }

#ifndef USE_OPENSUBDIV_VALENCE3
    return reject(
        "valence-3 OpenSubdiv Phase 1 row provider requires an explicitly "
        "OpenSubdiv-enabled valence-3 build",
        false,
        true);
#else
    const ApprovedTopology *topology = approved_topology(request.topology);
    if (!topology)
    {
        return reject(
            "valence-3 OpenSubdiv row provider rejected an unknown topology "
            "selection",
            true,
            true);
    }
    if (!exact_topology_identity(mesh, *topology))
    {
        return reject(
            "valence-3 OpenSubdiv row provider rejected the selected " +
                std::string(topology->name) +
                " identity, orientation, cardinality, valence, or one-ring "
                "state",
            true,
            true);
    }

    // Each accepted provider package has one immutable identity: exact
    // topology and orientation, the fixed three-sample plan, Loop options,
    // isolation level five, and compile-time OpenSubdiv 3.7.0.
    // Coordinates are deliberately absent. Selected-topology preflight above
    // runs on every call before a cache hit.
    static std::mutex cacheMutex;
    static std::array<std::optional<OpenSubdivValence3RowProviderResult>, 2>
        cachedRows;
    const std::size_t cacheIndex = topology_cache_index(request.topology);
    {
        std::lock_guard<std::mutex> lock(cacheMutex);
        if (cachedRows[cacheIndex].has_value())
        {
            OpenSubdivValence3RowProviderResult result =
                *cachedRows[cacheIndex];
            result.immutableRowCacheHit = true;
            return result;
        }
    }

    std::unique_ptr<Far::TopologyRefiner, RefinerDeleter> refiner =
        create_refiner(mesh, *topology);
    if (!refiner)
    {
        return reject(
            "valence-3 OpenSubdiv Phase 1 row provider could not create "
            "the selected topology refiner",
            true,
            true);
    }

    Far::PatchTableFactory::Options patchOptions(5);
    refiner->RefineAdaptive(patchOptions.GetRefineAdaptiveOptions());
    std::unique_ptr<const Far::PatchTable, DeleteConst<Far::PatchTable>>
        patchTable(Far::PatchTableFactory::Create(*refiner, patchOptions));
    const int faceCount = static_cast<int>(topology->faces.size());
    if (!patchTable || patchTable->GetNumPtexFaces() != faceCount)
    {
        return reject(
            "valence-3 OpenSubdiv row provider found a Ptex face count "
            "different from the selected topology",
            true,
            true);
    }

    const std::array<double, kSampleCount> sampleS{{
        1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0}};
    const std::array<double, kSampleCount> sampleT{{
        1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0}};
    std::vector<std::array<double, kSampleCount>> sByFace(
        faceCount, sampleS);
    std::vector<std::array<double, kSampleCount>> tByFace(
        faceCount, sampleT);
    using DoubleFactory = Far::LimitStencilTableFactoryReal<double>;
    DoubleFactory::LocationArrayVec locations;
    locations.reserve(faceCount);
    for (int face = 0; face < faceCount; ++face)
    {
        DoubleFactory::LocationArray location;
        location.ptexIdx = face;
        location.numLocations = kSampleCount;
        location.s = sByFace[face].data();
        location.t = tByFace[face].data();
        locations.push_back(location);
    }
    DoubleFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    std::unique_ptr<const Far::LimitStencilTableReal<double>,
                    DeleteConst<Far::LimitStencilTableReal<double>>>
        stencils(DoubleFactory::Create(
            *refiner, locations, nullptr, nullptr, stencilOptions));
    if (!stencils ||
        stencils->GetNumStencils() != faceCount * kSampleCount)
    {
        return reject(
            "valence-3 OpenSubdiv Phase 1 row provider requires the "
            "complete selected-face x 3 stencil plan",
            true,
            true);
    }

    Far::PatchMap patchMap(*patchTable);
    std::vector<SourceKeyedFaceRows> stagedRows;
    stagedRows.reserve(faceCount);
    for (int face = 0; face < faceCount; ++face)
    {
        SourceKeyedFaceRows faceRows;
        faceRows.faceIndex = face;
        faceRows.orientedFaceVertices = topology->faces[face];
        faceRows.samples.resize(kSampleCount);

        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            const Far::PatchMap::Handle *handle = patchMap.FindPatch(
                face, sampleS[sample], sampleT[sample]);
            if (!handle ||
                patchTable->GetPatchParam(*handle).GetFaceId() != face)
            {
                return reject(
                    "valence-3 OpenSubdiv Phase 1 row provider found "
                    "Ptex face identity drift",
                    true,
                    true);
            }

            const Far::LimitStencilReal<double> stencil =
                stencils->GetLimitStencil(face * kSampleCount + sample);
            const std::array<const double *, kDerivativeRowCount> weights{{
                stencil.GetWeights(),
                stencil.GetDuWeights(),
                stencil.GetDvWeights(),
                stencil.GetDuuWeights(),
                stencil.GetDvvWeights(),
                stencil.GetDuvWeights(),
                stencil.GetDuvWeights(),
            }};
            if (std::any_of(weights.begin(), weights.end(),
                            [](const double *value) {
                                return value == nullptr;
                            }))
            {
                return reject(
                    "valence-3 OpenSubdiv Phase 1 row provider omitted "
                    "derivative weights",
                    true,
                    true);
            }

            SourceKeyedSampleRows &sampleRows = faceRows.samples[sample];
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                const std::map<int, double> aggregated =
                    aggregate_row(stencil, weights[row]);
                for (const auto &entry : aggregated)
                {
                    if (entry.first < 0 ||
                        entry.first >= topology->sourceCount)
                    {
                        return reject(
                            "valence-3 OpenSubdiv Phase 1 row provider "
                            "escaped the selected topology source boundary",
                            true,
                            true);
                    }
                }

                SourceKeyedRow &target = sampleRows.rows[row];
                target.sourceIds.resize(topology->sourceCount);
                std::iota(target.sourceIds.begin(),
                          target.sourceIds.end(), 0);
                target.coefficients.reserve(topology->sourceCount);
                for (int sourceId = 0;
                     sourceId < topology->sourceCount;
                     ++sourceId)
                {
                    const auto found = aggregated.find(sourceId);
                    const double coefficient =
                        found == aggregated.end() ? 0.0 : found->second;
                    if (!std::isfinite(coefficient))
                    {
                        return reject(
                            "valence-3 OpenSubdiv Phase 1 row provider "
                            "produced a nonfinite coefficient",
                            true,
                            true);
                    }
                    target.coefficients.push_back(coefficient);
                }
                const double sum = std::accumulate(
                    target.coefficients.begin(),
                    target.coefficients.end(),
                    0.0);
                const double expected = row == 0 ? 1.0 : 0.0;
                if (std::abs(sum - expected) > kInvariantTolerance)
                {
                    return reject(
                        "valence-3 OpenSubdiv Phase 1 rows violated "
                        "constant-field partition or derivative-sum invariants",
                        true,
                        true);
                }
            }
            if (!rows_are_identical(sampleRows.rows[5], sampleRows.rows[6]))
            {
                return reject(
                    "valence-3 OpenSubdiv Phase 1 mixed derivative rows drifted",
                    true,
                    true);
            }
        }
        stagedRows.push_back(std::move(faceRows));
    }

    OpenSubdivValence3RowProviderResult result;
    result.accepted = true;
    result.opensubdivCompiled = true;
    result.explicitRequestReceived = true;
    result.exactTopologyIdentityValidated = true;
    result.topologySourceMappingValidated = true;
    result.ptexFaceIdentityValidated = true;
    result.exactSamplePlanValidated = true;
    result.exactFourSourceBoundaryValidated = topology->sourceCount == 4;
    result.exactFiveSourceBoundaryValidated = topology->sourceCount == 5;
    result.triangularBipyramidTopologyValidated =
        topology->kind == Valence3TopologyKind::TriangularBipyramid344;
    result.sourceCount = topology->sourceCount;
    result.faceCount = faceCount;
    result.topology = topology->kind;
    result.doublePrecisionRowsGenerated = true;
    result.constantFieldInvariantsValidated = true;
    result.mixedDerivativeRowsDuplicated = true;
    result.opensubdivVersionNumber = OPENSUBDIV_VERSION_NUMBER;
    result.adaptiveIsolationLevel = 5;
    result.rowsGenerated = true;
    result.immutableRowCachePopulated = true;
    result.rows = std::move(stagedRows);
    {
        std::lock_guard<std::mutex> lock(cacheMutex);
        if (cachedRows[cacheIndex].has_value())
        {
            OpenSubdivValence3RowProviderResult cachedResult =
                *cachedRows[cacheIndex];
            cachedResult.immutableRowCacheHit = true;
            return cachedResult;
        }
        cachedRows[cacheIndex] = result;
    }
    return result;
#endif
}
} // namespace slimed::opensubdiv_valence3
