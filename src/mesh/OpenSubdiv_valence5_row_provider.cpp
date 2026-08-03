#include "mesh/OpenSubdiv_valence5_row_provider.hpp"

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

#ifdef USE_OPENSUBDIV_VALENCE5
#include <opensubdiv/far/patchMap.h>
#include <opensubdiv/far/patchTableFactory.h>
#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>
#endif

namespace slimed::opensubdiv_valence5
{
namespace
{
using source_keyed_kernel::SourceKeyedFaceRows;
using source_keyed_kernel::SourceKeyedRow;
using source_keyed_kernel::SourceKeyedSampleRows;

constexpr int kApprovedFaceCount = 20;
constexpr int kApprovedSourceCount = 12;
constexpr int kFaceSourceCount = 9;
constexpr int kSampleCount = 3;
constexpr int kDerivativeRowCount = source_keyed_kernel::kDerivativeRowCount;
constexpr double kInvariantTolerance = 1.0e-12;

constexpr std::array<std::array<int, 3>, kApprovedFaceCount> kApprovedFaces{{
    {{0, 11, 5}}, {{0, 5, 1}}, {{0, 1, 7}}, {{0, 7, 10}}, {{0, 10, 11}},
    {{1, 5, 9}}, {{5, 11, 4}}, {{11, 10, 2}}, {{10, 7, 6}}, {{7, 1, 8}},
    {{3, 9, 4}}, {{3, 4, 2}}, {{3, 2, 6}}, {{3, 6, 8}}, {{3, 8, 9}},
    {{4, 9, 5}}, {{2, 4, 11}}, {{6, 2, 10}}, {{8, 6, 7}}, {{9, 8, 1}},
}};

constexpr std::array<std::array<int, kFaceSourceCount>, kApprovedFaceCount>
    kApprovedFaceSources{{
        {{0, 1, 2, 4, 5, 7, 9, 10, 11}},
        {{0, 1, 4, 5, 7, 8, 9, 10, 11}},
        {{0, 1, 5, 6, 7, 8, 9, 10, 11}},
        {{0, 1, 2, 5, 6, 7, 8, 10, 11}},
        {{0, 1, 2, 4, 5, 6, 7, 10, 11}},
        {{0, 1, 3, 4, 5, 7, 8, 9, 11}},
        {{0, 1, 2, 3, 4, 5, 9, 10, 11}},
        {{0, 2, 3, 4, 5, 6, 7, 10, 11}},
        {{0, 1, 2, 3, 6, 7, 8, 10, 11}},
        {{0, 1, 3, 5, 6, 7, 8, 9, 10}},
        {{1, 2, 3, 4, 5, 6, 8, 9, 11}},
        {{2, 3, 4, 5, 6, 8, 9, 10, 11}},
        {{2, 3, 4, 6, 7, 8, 9, 10, 11}},
        {{1, 2, 3, 4, 6, 7, 8, 9, 10}},
        {{1, 2, 3, 4, 5, 6, 7, 8, 9}},
        {{0, 1, 2, 3, 4, 5, 8, 9, 11}},
        {{0, 2, 3, 4, 5, 6, 9, 10, 11}},
        {{0, 2, 3, 4, 6, 7, 8, 10, 11}},
        {{0, 1, 2, 3, 6, 7, 8, 9, 10}},
        {{0, 1, 3, 4, 5, 6, 7, 8, 9}},
    }};

OpenSubdivValence5RowProviderResult reject(
    const std::string &reason,
    const bool opensubdivCompiled,
    const bool explicitRequestReceived)
{
    OpenSubdivValence5RowProviderResult result;
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
        if (vertex.index != source || vertex.adjacentVertices.size() != 5u)
        {
            return false;
        }
    }
    for (int face = 0; face < kApprovedFaceCount; ++face)
    {
        const Face &actual = mesh.faces[face];
        if (actual.index != face || actual.isGhost || actual.isBoundary ||
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

#ifdef USE_OPENSUBDIV_VALENCE5
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
    std::vector<int> verticesPerFace(kApprovedFaceCount, 3);
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

bool exact_source_mapping(
    const std::map<int, double> &aggregated,
    const std::array<int, kFaceSourceCount> &expected)
{
    if (aggregated.size() != expected.size())
    {
        return false;
    }
    return std::equal(
        aggregated.begin(), aggregated.end(), expected.begin(),
        [](const auto &entry, const int sourceId) {
            return entry.first == sourceId;
        });
}
#endif
} // namespace

OpenSubdivValence5RowProviderResult
build_guarded_opensubdiv_valence5_rows(
    const Mesh &mesh,
    const OpenSubdivValence5RowProviderRequest &request)
{
    if (!request.phase1ProviderExplicitRequest)
    {
        return reject(
            "valence-5 OpenSubdiv Phase 1 row provider remains default-off",
#ifdef USE_OPENSUBDIV_VALENCE5
            true,
#else
            false,
#endif
            false);
    }

#ifndef USE_OPENSUBDIV_VALENCE5
    return reject(
        "valence-5 OpenSubdiv Phase 1 row provider requires an explicitly "
        "OpenSubdiv-enabled valence-5 build",
        false,
        true);
#else
    if (!exact_topology_identity(mesh))
    {
        return reject(
            "valence-5 OpenSubdiv Phase 1 row provider rejected topology "
            "identity, orientation, cardinality, or valence",
            true,
            true);
    }

    std::unique_ptr<Far::TopologyRefiner, RefinerDeleter> refiner =
        create_refiner(mesh);
    if (!refiner)
    {
        return reject(
            "valence-5 OpenSubdiv Phase 1 row provider could not create "
            "the reviewed topology refiner",
            true,
            true);
    }

    Far::PatchTableFactory::Options patchOptions(5);
    refiner->RefineAdaptive(patchOptions.GetRefineAdaptiveOptions());
    std::unique_ptr<const Far::PatchTable, DeleteConst<Far::PatchTable>>
        patchTable(Far::PatchTableFactory::Create(*refiner, patchOptions));
    if (!patchTable ||
        patchTable->GetNumPtexFaces() != kApprovedFaceCount)
    {
        return reject(
            "valence-5 OpenSubdiv Phase 1 row provider requires exactly "
            "twenty reviewed Ptex faces",
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
            "valence-5 OpenSubdiv Phase 1 row provider requires the "
            "complete 20 x 3 stencil plan",
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
        const std::vector<int> sourceIds(
            kApprovedFaceSources[face].begin(),
            kApprovedFaceSources[face].end());

        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            const Far::PatchMap::Handle *handle = patchMap.FindPatch(
                face, sampleS[sample], sampleT[sample]);
            if (!handle ||
                patchTable->GetPatchParam(*handle).GetFaceId() != face)
            {
                return reject(
                    "valence-5 OpenSubdiv Phase 1 row provider found "
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
                    "valence-5 OpenSubdiv Phase 1 row provider omitted "
                    "derivative weights",
                    true,
                    true);
            }

            SourceKeyedSampleRows &sampleRows = faceRows.samples[sample];
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                const std::map<int, double> aggregated =
                    aggregate_row(stencil, weights[row]);
                if (!exact_source_mapping(
                        aggregated, kApprovedFaceSources[face]))
                {
                    return reject(
                        "valence-5 OpenSubdiv Phase 1 row provider source "
                        "mapping escaped the reviewed nine-source set",
                        true,
                        true);
                }
                SourceKeyedRow &target = sampleRows.rows[row];
                target.sourceIds = sourceIds;
                target.coefficients.reserve(kFaceSourceCount);
                for (const int sourceId : sourceIds)
                {
                    const double coefficient = aggregated.at(sourceId);
                    if (!std::isfinite(coefficient))
                    {
                        return reject(
                            "valence-5 OpenSubdiv Phase 1 row provider "
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
                        "valence-5 OpenSubdiv Phase 1 rows violated "
                        "constant-field partition or derivative-sum invariants",
                        true,
                        true);
                }
            }
            if (sampleRows.rows[5].sourceIds !=
                    sampleRows.rows[6].sourceIds ||
                sampleRows.rows[5].coefficients !=
                    sampleRows.rows[6].coefficients)
            {
                return reject(
                    "valence-5 OpenSubdiv Phase 1 mixed derivative rows drifted",
                    true,
                    true);
            }
        }
        stagedRows.push_back(std::move(faceRows));
    }

    OpenSubdivValence5RowProviderResult result;
    result.accepted = true;
    result.opensubdivCompiled = true;
    result.explicitRequestReceived = true;
    result.exactTopologyIdentityValidated = true;
    result.topologySourceMappingValidated = true;
    result.ptexFaceIdentityValidated = true;
    result.exactSamplePlanValidated = true;
    result.exactNineSourceCoverageValidated = true;
    result.doublePrecisionRowsGenerated = true;
    result.constantFieldInvariantsValidated = true;
    result.mixedDerivativeRowsDuplicated = true;
    result.rowsGenerated = true;
    result.rows = std::move(stagedRows);
    return result;
#endif
}
} // namespace slimed::opensubdiv_valence5
