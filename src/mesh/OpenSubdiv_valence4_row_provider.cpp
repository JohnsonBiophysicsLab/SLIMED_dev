#include "mesh/OpenSubdiv_valence4_row_provider.hpp"

#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <memory>
#include <numeric>
#include <string>
#include <utility>
#include <vector>

#ifdef USE_OPENSUBDIV_REGULAR
#include <opensubdiv/far/patchMap.h>
#include <opensubdiv/far/patchTableFactory.h>
#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>
#endif

namespace slimed::opensubdiv_valence4
{
namespace
{
using source_keyed_kernel::SourceKeyedFaceRows;
using source_keyed_kernel::SourceKeyedRow;
using source_keyed_kernel::SourceKeyedSampleRows;

constexpr int kApprovedFaceCount = 8;
constexpr int kApprovedSourceCount = 6;
constexpr int kSampleCount = 3;
constexpr int kDerivativeRowCount =
    source_keyed_kernel::kDerivativeRowCount;

OpenSubdivValence4RowProviderResult reject(
    const std::string &reason,
    const bool opensubdivCompiled,
    const bool explicitRequestReceived)
{
    OpenSubdivValence4RowProviderResult result;
    result.rejectionReason = reason;
    result.opensubdivCompiled = opensubdivCompiled;
    result.explicitRequestReceived = explicitRequestReceived;
    return result;
}

#ifdef USE_OPENSUBDIV_REGULAR
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
    std::vector<int> verticesPerFace;
    std::vector<int> vertexIndices;
    verticesPerFace.reserve(mesh.faces.size());
    vertexIndices.reserve(mesh.faces.size() * 3u);
    for (const Face &face : mesh.faces)
    {
        if (face.adjacentVertices.size() != 3u)
        {
            return nullptr;
        }
        verticesPerFace.push_back(3);
        vertexIndices.insert(vertexIndices.end(),
                             face.adjacentVertices.begin(),
                             face.adjacentVertices.end());
    }

    Descriptor descriptor;
    descriptor.numVertices = static_cast<int>(mesh.vertices.size());
    descriptor.numFaces = static_cast<int>(mesh.faces.size());
    descriptor.numVertsPerFace = verticesPerFace.data();
    descriptor.vertIndicesPerFace = vertexIndices.data();

    Sdc::Options options;
    options.SetVtxBoundaryInterpolation(
        Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);
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
        aggregated[indices[entry]] +=
            static_cast<double>(weights[entry]);
    }
    return aggregated;
}

bool rows_are_identical(const SourceKeyedRow &lhs,
                        const SourceKeyedRow &rhs)
{
    return lhs.sourceIds == rhs.sourceIds &&
           lhs.coefficients == rhs.coefficients;
}
#endif
} // namespace

OpenSubdivValence4RowProviderResult
build_guarded_opensubdiv_valence4_rows(
    const Mesh &mesh,
    const OpenSubdivValence4RowProviderRequest &request)
{
    if (!request.reviewerApprovedExplicitRequest)
    {
        return reject(
            "valence-4 OpenSubdiv row generation remains default-off",
#ifdef USE_OPENSUBDIV_REGULAR
            true,
#else
            false,
#endif
            false);
    }

#ifndef USE_OPENSUBDIV_REGULAR
    return reject(
        "valence-4 OpenSubdiv row generation requires an explicitly "
        "OpenSubdiv-enabled build",
        false,
        true);
#else
    const Valence4TopologySourceMappingResult topology =
        build_guarded_valence4_topology_source_mapping(mesh);
    if (!topology.supported ||
        topology.byFace.size() != kApprovedFaceCount)
    {
        return reject(
            topology.rejectionReason.empty()
                ? "valence-4 OpenSubdiv row generation rejected topology"
                : topology.rejectionReason,
            true,
            true);
    }

    std::unique_ptr<Far::TopologyRefiner, RefinerDeleter> refiner =
        create_refiner(mesh);
    if (!refiner)
    {
        return reject(
            "valence-4 OpenSubdiv row generation could not create the "
            "approved topology refiner",
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
            "valence-4 OpenSubdiv row generation requires exactly eight "
            "approved Ptex faces",
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
    using DoubleLimitFactory =
        Far::LimitStencilTableFactoryReal<double>;
    DoubleLimitFactory::LocationArrayVec locations;
    locations.reserve(kApprovedFaceCount);
    for (int face = 0; face < kApprovedFaceCount; ++face)
    {
        DoubleLimitFactory::LocationArray location;
        location.ptexIdx = face;
        location.numLocations = kSampleCount;
        location.s = sByFace[face].data();
        location.t = tByFace[face].data();
        locations.push_back(location);
    }

    DoubleLimitFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    std::unique_ptr<const Far::LimitStencilTableReal<double>,
                    DeleteConst<Far::LimitStencilTableReal<double>>>
        stencils(DoubleLimitFactory::Create(
            *refiner,
            locations,
            nullptr,
            nullptr,
            stencilOptions));
    if (!stencils ||
        stencils->GetNumStencils() !=
            kApprovedFaceCount * kSampleCount)
    {
        return reject(
            "valence-4 OpenSubdiv row generation requires the complete "
            "8 x 3 stencil plan",
            true,
            true);
    }

    Far::PatchMap patchMap(*patchTable);
    std::vector<SourceKeyedFaceRows> stagedRows;
    stagedRows.reserve(kApprovedFaceCount);
    for (int face = 0; face < kApprovedFaceCount; ++face)
    {
        const Valence4FaceTopologySourceMapping &mapping =
            topology.byFace[face];
        SourceKeyedFaceRows faceRows;
        faceRows.faceIndex = mapping.faceIndex;
        faceRows.orientedFaceVertices = mapping.orientedFaceVertices;
        faceRows.samples.resize(kSampleCount);

        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            const Far::PatchMap::Handle *handle =
                patchMap.FindPatch(
                    face, sampleS[sample], sampleT[sample]);
            if (!handle ||
                patchTable->GetPatchParam(*handle).GetFaceId() != face)
            {
                return reject(
                    "valence-4 OpenSubdiv row generation found Ptex face "
                    "identity drift",
                    true,
                    true);
            }

            const Far::LimitStencilReal<double> stencil =
                stencils->GetLimitStencil(
                    face * kSampleCount + sample);
            const std::array<const double *, kDerivativeRowCount>
                rowWeights{{
                    stencil.GetWeights(),
                    stencil.GetDuWeights(),
                    stencil.GetDvWeights(),
                    stencil.GetDuuWeights(),
                    stencil.GetDvvWeights(),
                    stencil.GetDuvWeights(),
                    stencil.GetDuvWeights(),
                }};
            if (std::any_of(
                    rowWeights.begin(),
                    rowWeights.end(),
                    [](const double *weights) {
                        return weights == nullptr;
                    }))
            {
                return reject(
                    "valence-4 OpenSubdiv row generation omitted "
                    "derivative weights",
                    true,
                    true);
            }

            SourceKeyedSampleRows &sampleRows =
                faceRows.samples[sample];
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                const std::map<int, double> aggregated =
                    aggregate_row(stencil, rowWeights[row]);
                if (aggregated.size() > kApprovedSourceCount)
                {
                    return reject(
                        "valence-4 OpenSubdiv row generation produced "
                        "unexpected source coverage",
                        true,
                        true);
                }
                SourceKeyedRow &target = sampleRows.rows[row];
                target.sourceIds = mapping.originalSourceIds;
                target.coefficients.reserve(kApprovedSourceCount);
                for (const int sourceId :
                     mapping.originalSourceIds)
                {
                    const auto found = aggregated.find(sourceId);
                    const double coefficient =
                        found == aggregated.end() ? 0.0
                                                  : found->second;
                    if (!std::isfinite(coefficient))
                    {
                        return reject(
                            "valence-4 OpenSubdiv row generation produced "
                            "a nonfinite coefficient",
                            true,
                            true);
                    }
                    target.coefficients.push_back(coefficient);
                }
                const double coefficientSum = std::accumulate(
                    target.coefficients.begin(),
                    target.coefficients.end(),
                    0.0);
                const double expectedSum = row == 0 ? 1.0 : 0.0;
                if (std::abs(coefficientSum - expectedSum) > 1.0e-12)
                {
                    return reject(
                        "valence-4 OpenSubdiv rows violated constant-field "
                        "partition or derivative-sum invariants",
                        true,
                        true);
                }
                for (const auto &entry : aggregated)
                {
                    if (std::find(mapping.originalSourceIds.begin(),
                                  mapping.originalSourceIds.end(),
                                  entry.first) ==
                        mapping.originalSourceIds.end())
                    {
                        return reject(
                            "valence-4 OpenSubdiv row generation escaped "
                            "the approved original source IDs",
                            true,
                            true);
                    }
                }
            }
            if (!rows_are_identical(sampleRows.rows[5],
                                    sampleRows.rows[6]))
            {
                return reject(
                    "valence-4 OpenSubdiv mixed derivative rows drifted",
                    true,
                    true);
            }
        }
        stagedRows.push_back(std::move(faceRows));
    }

    OpenSubdivValence4RowProviderResult result;
    result.accepted = true;
    result.opensubdivCompiled = true;
    result.explicitRequestReceived = true;
    result.topologySourceMappingValidated = true;
    result.ptexFaceIdentityValidated = true;
    result.exactSamplePlanValidated = true;
    result.exactSourceCoverageValidated = true;
    result.doublePrecisionRowsGenerated = true;
    result.constantFieldInvariantsValidated = true;
    result.mixedDerivativeRowsDuplicated = true;
    result.rowsGenerated = true;
    result.rows = std::move(stagedRows);
    return result;
#endif
}
} // namespace slimed::opensubdiv_valence4
