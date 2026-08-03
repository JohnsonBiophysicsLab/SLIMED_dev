#include "mesh/OpenSubdiv_valence3_row_provider.hpp"

#include "mesh/Mesh.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <memory>
#include <numeric>
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
#endif

namespace slimed::opensubdiv_valence3
{
namespace
{
using source_keyed_kernel::SourceKeyedFaceRows;
using source_keyed_kernel::SourceKeyedRow;
using source_keyed_kernel::SourceKeyedSampleRows;

constexpr int kApprovedFaceCount = 4;
constexpr int kApprovedSourceCount = 4;
constexpr int kSampleCount = 3;
constexpr int kDerivativeRowCount = source_keyed_kernel::kDerivativeRowCount;
constexpr double kInvariantTolerance = 1.0e-12;

constexpr std::array<std::array<int, 3>, kApprovedFaceCount> kApprovedFaces{{
    {{0, 2, 1}},
    {{0, 1, 3}},
    {{0, 3, 2}},
    {{1, 2, 3}},
}};

constexpr std::array<int, kApprovedSourceCount> kApprovedSources{{0, 1, 2, 3}};

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

bool exact_topology_identity(const Mesh &mesh)
{
    if (mesh.vertices.size() != kApprovedSourceCount ||
        mesh.faces.size() != kApprovedFaceCount)
    {
        return false;
    }
    for (int source = 0; source < kApprovedSourceCount; ++source)
    {
        const Vertex &vertex = mesh.vertices[source];
        if (vertex.index != source || vertex.isBoundary || vertex.isGhost ||
            vertex.adjacentVertices.size() != 3u)
        {
            return false;
        }
    }
    for (int face = 0; face < kApprovedFaceCount; ++face)
    {
        const Face &actual = mesh.faces[face];
        if (actual.index != face || actual.isGhost || actual.isBoundary ||
            !actual.oneRingVertices.empty() ||
            actual.adjacentVertices.size() != 3u ||
            !std::equal(kApprovedFaces[face].begin(),
                        kApprovedFaces[face].end(),
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
create_refiner(const Mesh &mesh)
{
    using Descriptor = Far::TopologyDescriptor;
    std::array<int, kApprovedFaceCount> verticesPerFace{{3, 3, 3, 3}};
    std::vector<int> vertexIndices;
    vertexIndices.reserve(kApprovedFaceCount * 3u);
    for (const Face &face : mesh.faces)
    {
        vertexIndices.insert(vertexIndices.end(),
                             face.adjacentVertices.begin(),
                             face.adjacentVertices.end());
    }

    Descriptor descriptor;
    descriptor.numVertices = kApprovedSourceCount;
    descriptor.numFaces = kApprovedFaceCount;
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
    if (!exact_topology_identity(mesh))
    {
        return reject(
            "valence-3 OpenSubdiv Phase 1 row provider rejected topology "
            "identity, orientation, cardinality, valence, or one-ring state",
            true,
            true);
    }

    std::unique_ptr<Far::TopologyRefiner, RefinerDeleter> refiner =
        create_refiner(mesh);
    if (!refiner)
    {
        return reject(
            "valence-3 OpenSubdiv Phase 1 row provider could not create "
            "the canonical topology refiner",
            true,
            true);
    }

    Far::PatchTableFactory::Options patchOptions(5);
    refiner->RefineAdaptive(patchOptions.GetRefineAdaptiveOptions());
    std::unique_ptr<const Far::PatchTable, DeleteConst<Far::PatchTable>>
        patchTable(Far::PatchTableFactory::Create(*refiner, patchOptions));
    if (!patchTable || patchTable->GetNumPtexFaces() != kApprovedFaceCount)
    {
        return reject(
            "valence-3 OpenSubdiv Phase 1 row provider requires exactly "
            "four canonical Ptex faces",
            true,
            true);
    }

    const std::array<double, kSampleCount> sampleS{{
        1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0}};
    const std::array<double, kSampleCount> sampleT{{
        1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0}};
    std::vector<std::array<double, kSampleCount>> sByFace(
        kApprovedFaceCount, sampleS);
    std::vector<std::array<double, kSampleCount>> tByFace(
        kApprovedFaceCount, sampleT);
    using DoubleFactory = Far::LimitStencilTableFactoryReal<double>;
    DoubleFactory::LocationArrayVec locations;
    locations.reserve(kApprovedFaceCount);
    for (int face = 0; face < kApprovedFaceCount; ++face)
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
        stencils->GetNumStencils() != kApprovedFaceCount * kSampleCount)
    {
        return reject(
            "valence-3 OpenSubdiv Phase 1 row provider requires the "
            "complete 4 x 3 stencil plan",
            true,
            true);
    }

    Far::PatchMap patchMap(*patchTable);
    std::vector<SourceKeyedFaceRows> stagedRows;
    stagedRows.reserve(kApprovedFaceCount);
    for (int face = 0; face < kApprovedFaceCount; ++face)
    {
        SourceKeyedFaceRows faceRows;
        faceRows.faceIndex = face;
        faceRows.orientedFaceVertices = kApprovedFaces[face];
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
                    if (entry.first < 0 || entry.first >= kApprovedSourceCount)
                    {
                        return reject(
                            "valence-3 OpenSubdiv Phase 1 row provider "
                            "escaped the canonical four-source boundary",
                            true,
                            true);
                    }
                }

                SourceKeyedRow &target = sampleRows.rows[row];
                target.sourceIds.assign(kApprovedSources.begin(),
                                        kApprovedSources.end());
                target.coefficients.reserve(kApprovedSourceCount);
                for (const int sourceId : kApprovedSources)
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
    result.exactFourSourceBoundaryValidated = true;
    result.doublePrecisionRowsGenerated = true;
    result.constantFieldInvariantsValidated = true;
    result.mixedDerivativeRowsDuplicated = true;
    result.rowsGenerated = true;
    result.rows = std::move(stagedRows);
    return result;
#endif
}
} // namespace slimed::opensubdiv_valence3
