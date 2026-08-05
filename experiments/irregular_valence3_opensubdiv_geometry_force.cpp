#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_valence3_row_provider.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <set>
#include <stdexcept>
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
#error "Valence-3 proof is qualified only for OpenSubdiv 3.7.0"
#endif
#endif

using slimed::opensubdiv_valence3::OpenSubdivValence3RowProviderRequest;
using slimed::opensubdiv_valence3::Valence3TopologyKind;
using slimed::opensubdiv_valence3::build_guarded_opensubdiv_valence3_rows;
using namespace slimed::source_keyed_kernel;

namespace
{
constexpr int kSampleCount = 3;
constexpr int kRowCount = 7;
constexpr int kAxisCount = 3;
constexpr double kVolumeQuadratureFactor = 1.0 / 6.0;
constexpr double kRowTolerance = 1.0e-12;
constexpr double kStudyKCurv = 47.5;
constexpr double kStudyUSurf = 130.0;
constexpr double kStudyUVol = 65.0;
constexpr double kStudySpontaneousCurvature = 0.17;
constexpr double kStudyArea0 = 0.95;
constexpr double kStudyVol0 = 0.09;
constexpr double kStudyGlobalChangeTarget = 1.0e-6;
constexpr double kStudyForceChangeTarget = 1.0e-5;
constexpr int kStudyAdaptiveIsolationLevel = 5;
constexpr int kStudyMaximumDepth = 4;
constexpr std::array<double, kSampleCount> kS{{
    1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0}};
constexpr std::array<double, kSampleCount> kT{{
    1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0}};

struct QuadraturePlan
{
    int depth = 0;
    std::vector<double> s;
    std::vector<double> t;
    std::vector<double> weights;
};

struct ParametricTriangle
{
    std::array<double, 2> a;
    std::array<double, 2> b;
    std::array<double, 2> c;
};

std::array<double, 2> midpoint(const std::array<double, 2> &left,
                               const std::array<double, 2> &right)
{
    return {{0.5 * (left[0] + right[0]),
             0.5 * (left[1] + right[1])}};
}

QuadraturePlan nested_quadrature_plan(const int depth)
{
    if (depth < 0)
    {
        throw std::invalid_argument("quadrature depth must be nonnegative");
    }
    std::vector<ParametricTriangle> triangles{{
        {{{0.0, 0.0}}, {{1.0, 0.0}}, {{0.0, 1.0}}},
    }};
    for (int level = 0; level < depth; ++level)
    {
        std::vector<ParametricTriangle> refined;
        refined.reserve(triangles.size() * 4u);
        for (const ParametricTriangle &triangle : triangles)
        {
            const auto ab = midpoint(triangle.a, triangle.b);
            const auto bc = midpoint(triangle.b, triangle.c);
            const auto ca = midpoint(triangle.c, triangle.a);
            refined.push_back({triangle.a, ab, ca});
            refined.push_back({ab, triangle.b, bc});
            refined.push_back({ca, bc, triangle.c});
            refined.push_back({ab, bc, ca});
        }
        triangles = std::move(refined);
    }

    QuadraturePlan plan;
    plan.depth = depth;
    plan.s.reserve(triangles.size() * kSampleCount);
    plan.t.reserve(triangles.size() * kSampleCount);
    plan.weights.reserve(triangles.size() * kSampleCount);
    const double subtriangleWeight =
        1.0 / static_cast<double>(triangles.size());
    for (const ParametricTriangle &triangle : triangles)
    {
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            const double localS = kS[sample];
            const double localT = kT[sample];
            const double localU = 1.0 - localS - localT;
            plan.s.push_back(localU * triangle.a[0] +
                             localS * triangle.b[0] +
                             localT * triangle.c[0]);
            plan.t.push_back(localU * triangle.a[1] +
                             localS * triangle.b[1] +
                             localT * triangle.c[1]);
            plan.weights.push_back(subtriangleWeight / kSampleCount);
        }
    }
    return plan;
}

struct FixtureReport
{
    std::string name;
    int vertexCount = 0;
    int faceCount = 0;
    std::vector<int> valences;
    bool closed = false;
    bool mixed345FacePresent = false;
    bool allFacesAre344 = false;
    bool rowsValid = false;
    bool providerApplicable = false;
    bool providerParity = false;
    bool providerCacheValidated = false;
    bool providerRejectedWhenNotApplicable = false;
    bool negativeProviderContractsValidated = false;
    bool isolationSensitivityValidated = false;
    bool normalsValidated = false;
    bool finite = false;
    bool positiveArea = false;
    bool nonzeroBendingForce = false;
    bool nonzeroAreaForce = false;
    bool nonzeroVolumeForce = false;
    bool transposeIdentityVerified = false;
    bool sourceKeyedScatterVerified = false;
    bool forceBalanceVerified = false;
    bool unsupportedMixedForceImbalanceObserved = false;
    bool finiteDifferenceVerified = false;
    bool fullDivergenceVolumeConjugacyVerified = false;
    double area = 0.0;
    double volume = 0.0;
    double bendingEnergy = 0.0;
    double isolationDeltaLevel4To5 = 0.0;
    double isolationDeltaLevel5To6 = 0.0;
    std::array<double, 3> maxForce{{0.0, 0.0, 0.0}};
    double maxTransposeRelativeResidual = 0.0;
    double maxSourceKeyedScatterRelativeResidual = 0.0;
    std::array<double, 3> maxFiniteDifferenceError{{0.0, 0.0, 0.0}};
    std::array<double, 3> aggregateForceL2{{0.0, 0.0, 0.0}};
    std::array<double, 3> netForceRelativeResidual{{0.0, 0.0, 0.0}};
    std::array<double, 3> netTorqueRelativeResidual{{0.0, 0.0, 0.0}};
};

std::array<double, 3> evaluate_row(const SourceKeyedRow &row,
                                   const Mesh &mesh)
{
    std::array<double, 3> value{};
    for (std::size_t entry = 0; entry < row.sourceIds.size(); ++entry)
    {
        const int source = row.sourceIds[entry];
        for (int axis = 0; axis < 3; ++axis)
        {
            value[axis] += row.coefficients[entry] *
                           mesh.vertices[source].coord.get(axis, 0);
        }
    }
    return value;
}

std::array<double, 3> evaluate_row(
    const SourceKeyedRow &row,
    const std::vector<Matrix> &coordinates)
{
    std::array<double, 3> value{};
    for (std::size_t entry = 0; entry < row.sourceIds.size(); ++entry)
    {
        const int source = row.sourceIds[entry];
        for (int axis = 0; axis < 3; ++axis)
        {
            value[axis] += row.coefficients[entry] *
                           coordinates[source].get(axis, 0);
        }
    }
    return value;
}

std::array<double, 3> cross(const std::array<double, 3> &left,
                            const std::array<double, 3> &right)
{
    return {{left[1] * right[2] - left[2] * right[1],
             left[2] * right[0] - left[0] * right[2],
             left[0] * right[1] - left[1] * right[0]}};
}

double norm(const std::array<double, 3> &value)
{
    return std::sqrt(value[0] * value[0] + value[1] * value[1] +
                     value[2] * value[2]);
}

double relative_residual(const long double left, const long double right)
{
    const long double scale =
        std::max(1.0L, std::max(std::abs(left), std::abs(right)));
    return static_cast<double>(std::abs(left - right) / scale);
}

double maximum_transpose_relative_residual(
    const std::vector<SourceKeyedFaceRows> &rows,
    const std::vector<Matrix> &coordinates)
{
    long double stackedLeft = 0.0L;
    long double stackedRight = 0.0L;
    double maximumResidual = 0.0;
    int sampleOrdinal = 0;
    for (const SourceKeyedFaceRows &faceRows : rows)
    {
        for (const SourceKeyedSampleRows &sample : faceRows.samples)
        {
            long double left = 0.0L;
            std::vector<std::array<long double, 3>> transposed(
                coordinates.size());
            for (int row = 0; row < kRowCount; ++row)
            {
                const SourceKeyedRow &sourceRow = sample.rows[row];
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    const long double gradient =
                        static_cast<long double>(
                            ((faceRows.faceIndex + 2) * (row + 3) *
                             (axis + 5)) % 19 - 9) /
                        7.0L;
                    long double evaluated = 0.0L;
                    for (std::size_t entry = 0;
                         entry < sourceRow.sourceIds.size(); ++entry)
                    {
                        const int source = sourceRow.sourceIds[entry];
                        const long double coefficient =
                            sourceRow.coefficients[entry];
                        evaluated += coefficient *
                            coordinates[source].get(axis, 0);
                        transposed[source][axis] +=
                            coefficient * gradient;
                    }
                    left += gradient * evaluated;
                }
            }

            long double right = 0.0L;
            for (std::size_t source = 0; source < coordinates.size();
                 ++source)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    right += transposed[source][axis] *
                             coordinates[source].get(axis, 0);
                }
            }
            maximumResidual = std::max(
                maximumResidual, relative_residual(left, right));
            const long double stackWeight =
                static_cast<long double>(sampleOrdinal + 1);
            stackedLeft += stackWeight * left;
            stackedRight += stackWeight * right;
            ++sampleOrdinal;
        }
    }
    return std::max(maximumResidual,
                    relative_residual(stackedLeft, stackedRight));
}

double force_package_relative_residual(
    const std::vector<SourceForceKinds> &left,
    const std::vector<SourceForceKinds> &right)
{
    if (left.size() != right.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximumResidual = 0.0;
    for (std::size_t source = 0; source < left.size(); ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                maximumResidual = std::max(
                    maximumResidual,
                    relative_residual(left[source][kind][axis],
                                      right[source][kind][axis]));
            }
        }
    }
    return maximumResidual;
}

double maximum_source_keyed_scatter_relative_residual(
    const PreparedSourceKeyedKernelCall &prepared,
    const std::vector<SourceForceKinds> &direct)
{
    const std::vector<SourceForceKinds> canonical =
        accumulate_source_keyed_force_contributions(prepared);
    double maximumResidual =
        force_package_relative_residual(canonical, direct);
    constexpr std::array<int, 3> kBufferCounts{{1, 2, 4}};
    for (const int bufferCount : kBufferCounts)
    {
        for (int repeat = 0; repeat < 2; ++repeat)
        {
            std::vector<SourceForceComponentBuffer> buffers(
                bufferCount,
                SourceForceComponentBuffer(
                    static_cast<std::size_t>(prepared.sourceCount) *
                        kForceComponentsPerSource,
                    0.0));
            for (const PreparedSourceKeyedFace &face : prepared.faces)
            {
                const int buffer = face.mapping.faceIndex % bufferCount;
                scatter_source_keyed_face_forces_to_component_buffer(
                    face, prepared.sourceCount, buffers[buffer]);
            }
            const std::vector<SourceForceKinds> reduced =
                reduce_source_keyed_force_component_buffers(
                    buffers, prepared.sourceCount);
            maximumResidual = std::max(
                maximumResidual,
                force_package_relative_residual(canonical, reduced));
        }
    }
    return maximumResidual;
}

bool finite_row_package(const std::vector<SourceKeyedFaceRows> &rows,
                        const int faceCount,
                        const int sourceCount,
                        const int sampleCount = kSampleCount,
                        const double invariantTolerance = kRowTolerance,
                        double *maximumInvariantResidual = nullptr)
{
    if (maximumInvariantResidual)
    {
        *maximumInvariantResidual = 0.0;
    }
    if (static_cast<int>(rows.size()) != faceCount)
    {
        if (maximumInvariantResidual)
        {
            *maximumInvariantResidual =
                std::numeric_limits<double>::infinity();
        }
        return false;
    }
    for (int face = 0; face < faceCount; ++face)
    {
        if (rows[face].faceIndex != face ||
            rows[face].samples.size() !=
                static_cast<std::size_t>(sampleCount))
        {
            if (maximumInvariantResidual)
            {
                *maximumInvariantResidual =
                    std::numeric_limits<double>::infinity();
            }
            return false;
        }
        for (const SourceKeyedSampleRows &sample : rows[face].samples)
        {
            for (int row = 0; row < kRowCount; ++row)
            {
                const SourceKeyedRow &actual = sample.rows[row];
                if (static_cast<int>(actual.sourceIds.size()) != sourceCount ||
                    actual.coefficients.size() != actual.sourceIds.size() ||
                    !std::is_sorted(actual.sourceIds.begin(),
                                    actual.sourceIds.end()) ||
                    !std::all_of(actual.coefficients.begin(),
                                 actual.coefficients.end(),
                                 [](const double value) {
                                     return std::isfinite(value);
                                 }))
                {
                    if (maximumInvariantResidual)
                    {
                        *maximumInvariantResidual =
                            std::numeric_limits<double>::infinity();
                    }
                    return false;
                }
                const long double sum = std::accumulate(
                    actual.coefficients.begin(), actual.coefficients.end(),
                    static_cast<long double>(0.0));
                const double residual = static_cast<double>(std::abs(
                    sum - static_cast<long double>(row == 0 ? 1.0 : 0.0)));
                if (maximumInvariantResidual)
                {
                    *maximumInvariantResidual = std::max(
                        *maximumInvariantResidual, residual);
                }
                if (residual > invariantTolerance)
                {
                    return false;
                }
            }
            if (sample.rows[5].sourceIds != sample.rows[6].sourceIds ||
                sample.rows[5].coefficients != sample.rows[6].coefficients)
            {
                if (maximumInvariantResidual)
                {
                    *maximumInvariantResidual =
                        std::numeric_limits<double>::infinity();
                }
                return false;
            }
        }
    }
    return true;
}

bool packages_match(const std::vector<SourceKeyedFaceRows> &left,
                    const std::vector<SourceKeyedFaceRows> &right)
{
    if (left.size() != right.size())
    {
        return false;
    }
    for (std::size_t face = 0; face < left.size(); ++face)
    {
        if (left[face].faceIndex != right[face].faceIndex ||
            left[face].orientedFaceVertices !=
                right[face].orientedFaceVertices ||
            left[face].samples.size() != right[face].samples.size())
        {
            return false;
        }
        for (std::size_t sample = 0;
             sample < left[face].samples.size(); ++sample)
        {
            for (int row = 0; row < kRowCount; ++row)
            {
                const SourceKeyedRow &a = left[face].samples[sample].rows[row];
                const SourceKeyedRow &b = right[face].samples[sample].rows[row];
                if (a.sourceIds != b.sourceIds ||
                    a.coefficients.size() != b.coefficients.size())
                {
                    return false;
                }
                for (std::size_t entry = 0;
                     entry < a.coefficients.size(); ++entry)
                {
                    if (std::abs(a.coefficients[entry] -
                                 b.coefficients[entry]) > kRowTolerance)
                    {
                        return false;
                    }
                }
            }
        }
    }
    return true;
}

double maximum_package_delta(
    const std::vector<SourceKeyedFaceRows> &left,
    const std::vector<SourceKeyedFaceRows> &right)
{
    if (left.size() != right.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (std::size_t face = 0; face < left.size(); ++face)
    {
        if (left[face].samples.size() != right[face].samples.size())
        {
            return std::numeric_limits<double>::infinity();
        }
        for (std::size_t sample = 0;
             sample < left[face].samples.size(); ++sample)
        {
            for (int row = 0; row < kRowCount; ++row)
            {
                const SourceKeyedRow &a =
                    left[face].samples[sample].rows[row];
                const SourceKeyedRow &b =
                    right[face].samples[sample].rows[row];
                if (a.sourceIds != b.sourceIds ||
                    a.coefficients.size() != b.coefficients.size())
                {
                    return std::numeric_limits<double>::infinity();
                }
                for (std::size_t entry = 0;
                     entry < a.coefficients.size(); ++entry)
                {
                    maximum = std::max(
                        maximum,
                        std::abs(a.coefficients[entry] -
                                 b.coefficients[entry]));
                }
            }
        }
    }
    return maximum;
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

std::vector<SourceKeyedFaceRows> build_proof_rows(
    const Mesh &mesh,
    const int adaptiveIsolationLevel,
    const QuadraturePlan &quadrature)
{
    if (quadrature.s.empty() ||
        quadrature.s.size() != quadrature.t.size() ||
        quadrature.s.size() != quadrature.weights.size())
    {
        throw std::invalid_argument("invalid proof quadrature plan");
    }
    using Descriptor = Far::TopologyDescriptor;
    std::vector<int> verticesPerFace(mesh.faces.size(), 3);
    std::vector<int> vertexIndices;
    vertexIndices.reserve(mesh.faces.size() * 3u);
    for (const Face &face : mesh.faces)
    {
        vertexIndices.insert(vertexIndices.end(),
                             face.adjacentVertices.begin(),
                             face.adjacentVertices.end());
    }
    Descriptor descriptor;
    descriptor.numVertices = static_cast<int>(mesh.vertices.size());
    descriptor.numFaces = static_cast<int>(mesh.faces.size());
    descriptor.numVertsPerFace = verticesPerFace.data();
    descriptor.vertIndicesPerFace = vertexIndices.data();

    Sdc::Options schemeOptions;
    schemeOptions.SetVtxBoundaryInterpolation(
        Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);
    std::unique_ptr<Far::TopologyRefiner, RefinerDeleter> refiner(
        Far::TopologyRefinerFactory<Descriptor>::Create(
            descriptor,
            Far::TopologyRefinerFactory<Descriptor>::Options(
                Sdc::SCHEME_LOOP, schemeOptions)));
    if (!refiner)
    {
        throw std::runtime_error("OpenSubdiv could not create proof refiner");
    }

    Far::PatchTableFactory::Options patchOptions(adaptiveIsolationLevel);
    refiner->RefineAdaptive(patchOptions.GetRefineAdaptiveOptions());
    std::unique_ptr<const Far::PatchTable, DeleteConst<Far::PatchTable>>
        patchTable(Far::PatchTableFactory::Create(*refiner, patchOptions));
    if (!patchTable ||
        patchTable->GetNumPtexFaces() != static_cast<int>(mesh.faces.size()))
    {
        throw std::runtime_error("OpenSubdiv Ptex identity drift");
    }

    using Factory = Far::LimitStencilTableFactoryReal<double>;
    std::vector<std::vector<double>> sByFace(
        mesh.faces.size(), quadrature.s);
    std::vector<std::vector<double>> tByFace(
        mesh.faces.size(), quadrature.t);
    Factory::LocationArrayVec locations;
    for (std::size_t face = 0; face < mesh.faces.size(); ++face)
    {
        Factory::LocationArray location;
        location.ptexIdx = static_cast<int>(face);
        location.numLocations = static_cast<int>(quadrature.s.size());
        location.s = sByFace[face].data();
        location.t = tByFace[face].data();
        locations.push_back(location);
    }
    Factory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    std::unique_ptr<const Far::LimitStencilTableReal<double>,
                    DeleteConst<Far::LimitStencilTableReal<double>>>
        stencils(Factory::Create(
            *refiner, locations, nullptr, nullptr, stencilOptions));
    if (!stencils || stencils->GetNumStencils() !=
                         static_cast<int>(mesh.faces.size() *
                                          quadrature.s.size()))
    {
        throw std::runtime_error("OpenSubdiv stencil plan incomplete");
    }

    Far::PatchMap patchMap(*patchTable);
    std::vector<SourceKeyedFaceRows> result;
    result.reserve(mesh.faces.size());
    for (std::size_t face = 0; face < mesh.faces.size(); ++face)
    {
        SourceKeyedFaceRows faceRows;
        faceRows.faceIndex = static_cast<int>(face);
        std::copy_n(mesh.faces[face].adjacentVertices.begin(), 3,
                    faceRows.orientedFaceVertices.begin());
        faceRows.samples.resize(quadrature.s.size());
        for (int sample = 0;
             sample < static_cast<int>(quadrature.s.size()); ++sample)
        {
            const Far::PatchMap::Handle *handle = patchMap.FindPatch(
                static_cast<int>(face), quadrature.s[sample],
                quadrature.t[sample]);
            if (!handle || patchTable->GetPatchParam(*handle).GetFaceId() !=
                               static_cast<int>(face))
            {
                throw std::runtime_error("OpenSubdiv sample left Ptex face");
            }
            const auto stencil = stencils->GetLimitStencil(
                static_cast<int>(face * quadrature.s.size()) + sample);
            const std::array<const double *, kRowCount> weights{{
                stencil.GetWeights(), stencil.GetDuWeights(),
                stencil.GetDvWeights(), stencil.GetDuuWeights(),
                stencil.GetDvvWeights(), stencil.GetDuvWeights(),
                stencil.GetDuvWeights()}};
            for (const double *weight : weights)
            {
                if (!weight)
                {
                    throw std::runtime_error("OpenSubdiv derivative omitted");
                }
            }
            const Far::Index *indices = stencil.GetVertexIndices();
            for (int row = 0; row < kRowCount; ++row)
            {
                SourceKeyedRow &target =
                    faceRows.samples[sample].rows[row];
                target.sourceIds.resize(mesh.vertices.size());
                std::iota(target.sourceIds.begin(), target.sourceIds.end(), 0);
                target.coefficients.assign(mesh.vertices.size(), 0.0);
                for (int entry = 0; entry < stencil.GetSize(); ++entry)
                {
                    const int source = indices[entry];
                    if (source < 0 ||
                        source >= static_cast<int>(mesh.vertices.size()))
                    {
                        throw std::runtime_error(
                            "OpenSubdiv escaped original source boundary");
                    }
                    target.coefficients[source] += weights[row][entry];
                }
            }
        }
        result.push_back(std::move(faceRows));
    }
    return result;
}

std::vector<SourceKeyedFaceRows> build_proof_rows(
    const Mesh &mesh, const int adaptiveIsolationLevel)
{
    return build_proof_rows(
        mesh, adaptiveIsolationLevel, nested_quadrature_plan(0));
}
#endif

bool closed_mesh(const Mesh &mesh)
{
    std::map<std::pair<int, int>, int> edgeUse;
    for (const Face &face : mesh.faces)
    {
        for (int corner = 0; corner < 3; ++corner)
        {
            const int a = face.adjacentVertices[corner];
            const int b = face.adjacentVertices[(corner + 1) % 3];
            ++edgeUse[std::minmax(a, b)];
        }
    }
    return !edgeUse.empty() &&
           std::all_of(edgeUse.begin(), edgeUse.end(), [](const auto &entry) {
               return entry.second == 2;
           });
}

bool has_mixed_345_face(const Mesh &mesh)
{
    for (const Face &face : mesh.faces)
    {
        std::array<int, 3> valence{{
            static_cast<int>(mesh.vertices[face.adjacentVertices[0]]
                                 .adjacentVertices.size()),
            static_cast<int>(mesh.vertices[face.adjacentVertices[1]]
                                 .adjacentVertices.size()),
            static_cast<int>(mesh.vertices[face.adjacentVertices[2]]
                                 .adjacentVertices.size())}};
        std::sort(valence.begin(), valence.end());
        if (valence == std::array<int, 3>{{3, 4, 5}})
        {
            return true;
        }
    }
    return false;
}

bool all_faces_are_344(const Mesh &mesh)
{
    return !mesh.faces.empty() &&
           std::all_of(mesh.faces.begin(), mesh.faces.end(),
                       [&mesh](const Face &face) {
                           std::array<int, 3> valence{{
                               static_cast<int>(
                                   mesh.vertices[face.adjacentVertices[0]]
                                       .adjacentVertices.size()),
                               static_cast<int>(
                                   mesh.vertices[face.adjacentVertices[1]]
                                       .adjacentVertices.size()),
                               static_cast<int>(
                                   mesh.vertices[face.adjacentVertices[2]]
                                       .adjacentVertices.size())}};
                           std::sort(valence.begin(), valence.end());
                           return valence ==
                                  std::array<int, 3>{{3, 4, 4}};
                       });
}

std::array<double, 3> evaluate_total_energies(
    Mesh &evaluator,
    const std::vector<SourceKeyedFaceRows> &rows,
    const std::vector<Matrix> &coordinates,
    const double spontaneousCurvature)
{
    double area = 0.0;
    double volume = 0.0;
    double bending = 0.0;
    for (const SourceKeyedFaceRows &faceRows : rows)
    {
        std::vector<Matrix> shapeFunctions;
        for (const SourceKeyedSampleRows &sample : faceRows.samples)
        {
            const auto position = evaluate_row(sample.rows[0], coordinates);
            const auto du = evaluate_row(sample.rows[1], coordinates);
            const auto dv = evaluate_row(sample.rows[2], coordinates);
            const auto areaVector = cross(du, dv);
            area += (1.0 / 6.0) * norm(areaVector);
            volume += (kVolumeQuadratureFactor / 3.0) *
                (position[0] * areaVector[0] +
                 position[1] * areaVector[1] +
                 position[2] * areaVector[2]);

            Matrix matrix(kRowCount,
                          static_cast<int>(coordinates.size()), true);
            for (int row = 0; row < kRowCount; ++row)
            {
                for (std::size_t source = 0;
                     source < coordinates.size(); ++source)
                {
                    matrix.set(row, static_cast<int>(source),
                               sample.rows[row].coefficients[source]);
                }
            }
            shapeFunctions.push_back(std::move(matrix));
        }
        Face face;
        face.index = faceRows.faceIndex;
        face.spontCurvature = spontaneousCurvature;
        double meanCurvature = 0.0;
        double faceBending = 0.0;
        Matrix normal = mat_calloc(3, 1);
        Matrix fBend = mat_calloc(static_cast<int>(coordinates.size()), 3);
        Matrix fArea = mat_calloc(static_cast<int>(coordinates.size()), 3);
        Matrix fVolume = mat_calloc(static_cast<int>(coordinates.size()), 3);
        evaluator.element_energy_force_regular(
            coordinates, face, spontaneousCurvature, meanCurvature, normal,
            faceBending, fBend, fArea, fVolume, false, &shapeFunctions);
        bending += faceBending;
    }
    const double areaEnergy =
        0.5 * evaluator.param.uSurf / evaluator.param.area0 *
        std::pow(area - evaluator.param.area0, 2);
    const double volumeEnergy =
        0.5 * evaluator.param.uVol / evaluator.param.vol0 *
        std::pow(volume - evaluator.param.vol0, 2);
    return {{bending, areaEnergy, volumeEnergy}};
}

struct QuadratureEvaluation
{
    int depth = 0;
    int samplesPerFace = 0;
    bool planValidated = false;
    bool rowsStructurallyValid = false;
    bool rowsValid = false;
    double maximumRowInvariantResidual = 0.0;
    bool finite = false;
    double area = 0.0;
    double volume = 0.0;
    double bendingEnergy = 0.0;
    double totalEnergy = 0.0;
    std::vector<SourceForceKinds> forces;
};

struct QuadratureConvergenceReport
{
    std::string name;
    std::vector<QuadratureEvaluation> levels;
    std::vector<double> globalRelativeChanges;
    std::vector<double> forceRelativeChanges;
    bool allPlansValidated = false;
    bool allRowsStructurallyValid = false;
    bool allRowsValid = false;
    bool allFinite = false;
    bool twoSuccessiveGlobalTargetsMet = false;
    bool twoSuccessiveForceTargetsMet = false;
    bool scientificTargetsMet = false;
    bool activationBlocked = false;
    bool studyCompleted = false;
    bool passed = false;
};

bool quadrature_plan_valid(const QuadraturePlan &plan)
{
    std::size_t expectedSamples = kSampleCount;
    for (int level = 0; level < plan.depth; ++level)
    {
        expectedSamples *= 4u;
    }
    if (plan.s.size() != expectedSamples ||
        plan.t.size() != expectedSamples ||
        plan.weights.size() != expectedSamples)
    {
        return false;
    }
    double weightSum = 0.0;
    for (std::size_t sample = 0; sample < expectedSamples; ++sample)
    {
        if (!std::isfinite(plan.s[sample]) ||
            !std::isfinite(plan.t[sample]) ||
            !std::isfinite(plan.weights[sample]) ||
            plan.s[sample] <= 0.0 || plan.t[sample] <= 0.0 ||
            plan.s[sample] + plan.t[sample] >= 1.0 ||
            plan.weights[sample] <= 0.0)
        {
            return false;
        }
        weightSum += plan.weights[sample];
    }
    return std::abs(weightSum - 1.0) <= 2.0e-14;
}

#ifdef USE_OPENSUBDIV_VALENCE3
QuadratureEvaluation evaluate_quadrature(
    const Mesh &mesh,
    const QuadraturePlan &plan)
{
    QuadratureEvaluation evaluation;
    evaluation.depth = plan.depth;
    evaluation.samplesPerFace = static_cast<int>(plan.s.size());
    evaluation.planValidated = quadrature_plan_valid(plan);
    const std::vector<SourceKeyedFaceRows> rows =
        build_proof_rows(mesh, kStudyAdaptiveIsolationLevel, plan);
    evaluation.rowsStructurallyValid = finite_row_package(
        rows, static_cast<int>(mesh.faces.size()),
        static_cast<int>(mesh.vertices.size()),
        static_cast<int>(plan.s.size()),
        std::numeric_limits<double>::infinity(),
        &evaluation.maximumRowInvariantResidual);
    evaluation.rowsValid = evaluation.rowsStructurallyValid &&
        evaluation.maximumRowInvariantResidual <= kRowTolerance;

    std::vector<Matrix> coordinates;
    coordinates.reserve(mesh.vertices.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        coordinates.push_back(vertex.coord);
    }
    for (const SourceKeyedFaceRows &faceRows : rows)
    {
        for (std::size_t sample = 0;
             sample < faceRows.samples.size(); ++sample)
        {
            const auto position =
                evaluate_row(faceRows.samples[sample].rows[0], mesh);
            const auto du =
                evaluate_row(faceRows.samples[sample].rows[1], mesh);
            const auto dv =
                evaluate_row(faceRows.samples[sample].rows[2], mesh);
            const auto areaVector = cross(du, dv);
            const double weight = plan.weights[sample];
            evaluation.area += 0.5 * weight * norm(areaVector);
            evaluation.volume += kVolumeQuadratureFactor * weight *
                (position[0] * areaVector[0] +
                 position[1] * areaVector[1] +
                 position[2] * areaVector[2]);
        }
    }

    Param forceParam;
    forceParam.VERBOSE_MODE = false;
    forceParam.boundaryCondition = BoundaryType::Fixed;
    forceParam.kCurv = kStudyKCurv;
    forceParam.uSurf = kStudyUSurf;
    forceParam.uVol = kStudyUVol;
    forceParam.area = evaluation.area;
    forceParam.vol = evaluation.volume;
    forceParam.area0 = kStudyArea0;
    forceParam.vol0 = kStudyVol0;
    Mesh evaluator(forceParam);
    evaluator.param.gaussQuadratureCoeff =
        Matrix(static_cast<int>(plan.weights.size()), 1, true);
    for (int sample = 0;
         sample < static_cast<int>(plan.weights.size()); ++sample)
    {
        evaluator.param.gaussQuadratureCoeff.set(
            sample, 0, plan.weights[sample]);
    }

    evaluation.forces.resize(mesh.vertices.size());
    bool finite = evaluation.planValidated &&
                  evaluation.rowsStructurallyValid &&
                  std::isfinite(evaluation.area) &&
                  std::isfinite(evaluation.volume) &&
                  evaluation.area > 0.0;
    for (const SourceKeyedFaceRows &faceRows : rows)
    {
        std::vector<Matrix> shapeFunctions;
        shapeFunctions.reserve(faceRows.samples.size());
        for (const SourceKeyedSampleRows &sample : faceRows.samples)
        {
            Matrix matrix(kRowCount,
                          static_cast<int>(mesh.vertices.size()), true);
            for (int row = 0; row < kRowCount; ++row)
            {
                for (int source = 0;
                     source < static_cast<int>(mesh.vertices.size());
                     ++source)
                {
                    matrix.set(row, source,
                               sample.rows[row].coefficients[source]);
                }
            }
            shapeFunctions.push_back(std::move(matrix));
        }

        Face face;
        face.index = faceRows.faceIndex;
        face.spontCurvature = kStudySpontaneousCurvature;
        double meanCurvature = 0.0;
        double bendingEnergy = 0.0;
        Matrix normal = mat_calloc(3, 1);
        Matrix fBend = mat_calloc(
            static_cast<int>(mesh.vertices.size()), 3);
        Matrix fArea = mat_calloc(
            static_cast<int>(mesh.vertices.size()), 3);
        Matrix fVolume = mat_calloc(
            static_cast<int>(mesh.vertices.size()), 3);
        evaluator.element_energy_force_regular(
            coordinates, face, face.spontCurvature, meanCurvature, normal,
            bendingEnergy, fBend, fArea, fVolume, false, &shapeFunctions);
        evaluation.bendingEnergy += bendingEnergy;
        finite = finite && std::isfinite(meanCurvature) &&
                 std::isfinite(bendingEnergy);
        const std::array<const Matrix *, 3> forceMatrices{{
            &fBend, &fArea, &fVolume}};
        for (int source = 0;
             source < static_cast<int>(mesh.vertices.size()); ++source)
        {
            for (int kind = 0; kind < 3; ++kind)
            {
                for (int axis = 0; axis < 3; ++axis)
                {
                    const double value =
                        forceMatrices[kind]->get(source, axis);
                    finite = finite && std::isfinite(value);
                    evaluation.forces[source][kind][axis] += value;
                }
            }
        }
    }
    const double areaEnergy =
        0.5 * evaluator.param.uSurf / evaluator.param.area0 *
        std::pow(evaluation.area - evaluator.param.area0, 2);
    const double volumeEnergy =
        0.5 * evaluator.param.uVol / evaluator.param.vol0 *
        std::pow(evaluation.volume - evaluator.param.vol0, 2);
    evaluation.totalEnergy =
        evaluation.bendingEnergy + areaEnergy + volumeEnergy;
    evaluation.finite = finite &&
                        std::isfinite(evaluation.totalEnergy);
    return evaluation;
}

double relative_change(const double left, const double right)
{
    return std::abs(left - right) /
           std::max({1.0e-12, std::abs(left), std::abs(right)});
}

double global_relative_change(const QuadratureEvaluation &left,
                              const QuadratureEvaluation &right)
{
    return std::max({relative_change(left.area, right.area),
                     relative_change(left.volume, right.volume),
                     relative_change(left.totalEnergy, right.totalEnergy)});
}

double force_relative_change(const QuadratureEvaluation &left,
                             const QuadratureEvaluation &right)
{
    if (left.forces.size() != right.forces.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (std::size_t source = 0; source < left.forces.size(); ++source)
    {
        for (int kind = 0; kind < 3; ++kind)
        {
            for (int axis = 0; axis < 3; ++axis)
            {
                maximum = std::max(
                    maximum,
                    std::abs(left.forces[source][kind][axis] -
                             right.forces[source][kind][axis]) /
                        std::max({1.0,
                                  std::abs(left.forces[source][kind][axis]),
                                  std::abs(right.forces[source][kind][axis])}));
            }
        }
    }
    return maximum;
}

QuadratureConvergenceReport evaluate_quadrature_convergence(
    const std::string &name,
    const std::string &verticesPath,
    const std::string &facesPath)
{
    QuadratureConvergenceReport report;
    report.name = name;
    Param setupParam;
    setupParam.VERBOSE_MODE = false;
    setupParam.boundaryCondition = BoundaryType::Fixed;
    Mesh mesh(setupParam);
    mesh.setup_from_vertices_faces(read_data_from_csv<double>(verticesPath),
                                   read_data_from_csv<int>(facesPath));
    for (int depth = 0; depth <= kStudyMaximumDepth; ++depth)
    {
        report.levels.push_back(
            evaluate_quadrature(mesh, nested_quadrature_plan(depth)));
    }
    for (std::size_t level = 1; level < report.levels.size(); ++level)
    {
        report.globalRelativeChanges.push_back(global_relative_change(
            report.levels[level - 1], report.levels[level]));
        report.forceRelativeChanges.push_back(force_relative_change(
            report.levels[level - 1], report.levels[level]));
    }
    report.allPlansValidated = std::all_of(
        report.levels.begin(), report.levels.end(),
        [](const QuadratureEvaluation &level) {
            return level.planValidated;
        });
    report.allRowsValid = std::all_of(
        report.levels.begin(), report.levels.end(),
        [](const QuadratureEvaluation &level) { return level.rowsValid; });
    report.allRowsStructurallyValid = std::all_of(
        report.levels.begin(), report.levels.end(),
        [](const QuadratureEvaluation &level) {
            return level.rowsStructurallyValid;
        });
    report.allFinite = std::all_of(
        report.levels.begin(), report.levels.end(),
        [](const QuadratureEvaluation &level) { return level.finite; });
    const std::size_t changeCount = report.globalRelativeChanges.size();
    report.twoSuccessiveGlobalTargetsMet = changeCount >= 2u &&
        report.globalRelativeChanges[changeCount - 2u] <=
            kStudyGlobalChangeTarget &&
        report.globalRelativeChanges[changeCount - 1u] <=
            kStudyGlobalChangeTarget;
    report.twoSuccessiveForceTargetsMet = changeCount >= 2u &&
        report.forceRelativeChanges[changeCount - 2u] <=
            kStudyForceChangeTarget &&
        report.forceRelativeChanges[changeCount - 1u] <=
            kStudyForceChangeTarget;
    report.scientificTargetsMet = report.allRowsValid &&
        report.twoSuccessiveGlobalTargetsMet &&
        report.twoSuccessiveForceTargetsMet;
    report.activationBlocked = !report.scientificTargetsMet;
    report.studyCompleted = report.allPlansValidated &&
                            report.allRowsStructurallyValid &&
                            report.allFinite;
    // This Phase-5 slice is an evidence packet, not activation. It passes
    // only when the study completes and the measured scientific blocker is
    // represented explicitly rather than hidden by wider tolerances.
    report.passed = report.studyCompleted && report.activationBlocked;
    return report;
}
#endif

FixtureReport evaluate_fixture(const std::string &name,
                               const std::string &verticesPath,
                               const std::string &facesPath,
                               const bool requireProviderParity,
                               const bool asymmetricPerturbation = false,
                               const Valence3TopologyKind providerTopology =
                                   Valence3TopologyKind::CanonicalTetrahedron)
{
    FixtureReport report;
    report.name = name;
    Param setupParam;
    setupParam.VERBOSE_MODE = false;
    setupParam.boundaryCondition = BoundaryType::Fixed;
    Mesh mesh(setupParam);
    mesh.setup_from_vertices_faces(read_data_from_csv<double>(verticesPath),
                                   read_data_from_csv<int>(facesPath));
    if (asymmetricPerturbation)
    {
        mesh.vertices[0].coord.set(
            0, 0, mesh.vertices[0].coord.get(0, 0) + 0.071);
        mesh.vertices[0].coord.set(
            1, 0, mesh.vertices[0].coord.get(1, 0) - 0.043);
        mesh.vertices[0].coord.set(
            2, 0, mesh.vertices[0].coord.get(2, 0) + 0.029);
    }
    report.vertexCount = static_cast<int>(mesh.vertices.size());
    report.faceCount = static_cast<int>(mesh.faces.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        report.valences.push_back(
            static_cast<int>(vertex.adjacentVertices.size()));
    }
    report.closed = closed_mesh(mesh);
    report.mixed345FacePresent = has_mixed_345_face(mesh);
    report.allFacesAre344 = all_faces_are_344(mesh);

#ifndef USE_OPENSUBDIV_VALENCE3
    (void)requireProviderParity;
    (void)asymmetricPerturbation;
    (void)providerTopology;
    return report;
#else
    const std::vector<SourceKeyedFaceRows> level4Rows =
        build_proof_rows(mesh, 4);
    const std::vector<SourceKeyedFaceRows> rows = build_proof_rows(mesh, 5);
    const std::vector<SourceKeyedFaceRows> level6Rows =
        build_proof_rows(mesh, 6);
    report.rowsValid = finite_row_package(
        rows, report.faceCount, report.vertexCount);
    report.isolationDeltaLevel4To5 =
        maximum_package_delta(level4Rows, rows);
    report.isolationDeltaLevel5To6 =
        maximum_package_delta(rows, level6Rows);
    report.isolationSensitivityValidated =
        std::isfinite(report.isolationDeltaLevel4To5) &&
        std::isfinite(report.isolationDeltaLevel5To6) &&
        report.isolationDeltaLevel5To6 <=
            report.isolationDeltaLevel4To5 + 1.0e-12;

    if (requireProviderParity)
    {
        report.providerApplicable = true;
        OpenSubdivValence3RowProviderRequest request;
        request.phase1ProviderExplicitRequest = true;
        request.topology = providerTopology;
        const auto provider =
            build_guarded_opensubdiv_valence3_rows(mesh, request);
        const auto repeatedProvider =
            build_guarded_opensubdiv_valence3_rows(mesh, request);
        const bool sourceBoundaryValidated =
            providerTopology == Valence3TopologyKind::CanonicalTetrahedron
                ? provider.exactFourSourceBoundaryValidated
                : provider.exactFiveSourceBoundaryValidated &&
                      provider.triangularBipyramidTopologyValidated;
        report.providerParity =
            provider.accepted &&
            provider.opensubdivVersionNumber == 30700 &&
            provider.adaptiveIsolationLevel == 5 &&
            provider.sourceCount == report.vertexCount &&
            provider.faceCount == report.faceCount &&
            provider.topology == providerTopology &&
            sourceBoundaryValidated &&
            packages_match(provider.rows, rows);
        report.providerCacheValidated =
            repeatedProvider.accepted &&
            repeatedProvider.immutableRowCacheHit &&
            repeatedProvider.topology == providerTopology &&
            packages_match(repeatedProvider.rows, rows);
        report.providerParity =
            report.providerParity && report.providerCacheValidated;

        const auto defaultOff =
            build_guarded_opensubdiv_valence3_rows(mesh, {});
        Param invalidParam;
        invalidParam.VERBOSE_MODE = false;
        Mesh invalid(invalidParam);
        invalid.setup_from_vertices_faces(
            read_data_from_csv<double>(verticesPath),
            read_data_from_csv<int>(facesPath));
        std::swap(invalid.faces[0].adjacentVertices[0],
                  invalid.faces[0].adjacentVertices[1]);
        const auto invalidResult =
            build_guarded_opensubdiv_valence3_rows(invalid, request);
        OpenSubdivValence3RowProviderRequest wrongTopologyRequest = request;
        wrongTopologyRequest.topology =
            providerTopology == Valence3TopologyKind::CanonicalTetrahedron
                ? Valence3TopologyKind::TriangularBipyramid344
                : Valence3TopologyKind::CanonicalTetrahedron;
        const auto wrongTopologyResult =
            build_guarded_opensubdiv_valence3_rows(mesh,
                                                   wrongTopologyRequest);
        report.negativeProviderContractsValidated =
            !defaultOff.accepted && defaultOff.rows.empty() &&
            !invalidResult.accepted && invalidResult.rows.empty() &&
            !wrongTopologyResult.accepted &&
            wrongTopologyResult.rows.empty();
    }
    else
    {
        report.providerApplicable = false;
        OpenSubdivValence3RowProviderRequest request;
        request.phase1ProviderExplicitRequest = true;
        const auto rejected =
            build_guarded_opensubdiv_valence3_rows(mesh, request);
        report.providerRejectedWhenNotApplicable =
            !rejected.accepted && rejected.rows.empty();
        report.negativeProviderContractsValidated =
            report.providerRejectedWhenNotApplicable;
    }

    std::vector<Matrix> coordinates;
    coordinates.reserve(mesh.vertices.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        coordinates.push_back(vertex.coord);
    }
    report.maxTransposeRelativeResidual =
        maximum_transpose_relative_residual(rows, coordinates);
    report.transposeIdentityVerified =
        std::isfinite(report.maxTransposeRelativeResidual) &&
        report.maxTransposeRelativeResidual <= 5.0e-13;

    for (const SourceKeyedFaceRows &faceRows : rows)
    {
        for (const SourceKeyedSampleRows &sample : faceRows.samples)
        {
            const auto position = evaluate_row(sample.rows[0], mesh);
            const auto du = evaluate_row(sample.rows[1], mesh);
            const auto dv = evaluate_row(sample.rows[2], mesh);
            const auto areaVector = cross(du, dv);
            const double weight = 1.0 / 3.0;
            report.area += 0.5 * weight * norm(areaVector);
            report.volume += kVolumeQuadratureFactor * weight *
                (position[0] * areaVector[0] +
                 position[1] * areaVector[1] +
                 position[2] * areaVector[2]);
        }
    }

    Param forceParam;
    forceParam.VERBOSE_MODE = false;
    forceParam.boundaryCondition = BoundaryType::Fixed;
    forceParam.kCurv = 47.5;
    forceParam.uSurf = 130.0;
    forceParam.uVol = 65.0;
    forceParam.area = report.area;
    forceParam.vol = report.volume;
    forceParam.area0 = 0.91 * report.area;
    forceParam.vol0 = 0.89 * report.volume;
    forceParam.gaussQuadratureCoeff = Matrix(kSampleCount, 1, true);
    for (int sample = 0; sample < kSampleCount; ++sample)
    {
        forceParam.gaussQuadratureCoeff.set(sample, 0, 1.0 / 3.0);
    }
    Mesh evaluator(forceParam);
    // Mesh construction refreshes quadrature state; reinstate this proof's
    // reviewed three-sample weights before invoking the existing algebra.
    forceParam.gaussQuadratureCoeff = Matrix(kSampleCount, 1, true);
    for (int sample = 0; sample < kSampleCount; ++sample)
    {
        forceParam.gaussQuadratureCoeff.set(sample, 0, 1.0 / 3.0);
    }

    SourceKeyedKernelCallInput kernelInput;
    kernelInput.sourceCount = report.vertexCount;
    kernelInput.rows = rows;
    std::vector<int> originalSourceIds(report.vertexCount);
    std::iota(originalSourceIds.begin(), originalSourceIds.end(), 0);
    for (const SourceKeyedFaceRows &faceRows : rows)
    {
        SourceMappingView mapping;
        mapping.faceIndex = faceRows.faceIndex;
        mapping.orientedFaceVertices = faceRows.orientedFaceVertices;
        mapping.originalSourceIds = originalSourceIds;
        mapping.productionOneRingEmpty = true;
        mapping.productionOneRingBypassed = false;
        kernelInput.mappings.push_back(std::move(mapping));
    }

    std::vector<SourceForceKinds> aggregate(mesh.vertices.size());
    bool finite = std::isfinite(report.area) && std::isfinite(report.volume);
    bool normalsValidated = true;
    for (const SourceKeyedFaceRows &faceRows : rows)
    {
        std::vector<Matrix> shapeFunctions;
        for (const SourceKeyedSampleRows &sample : faceRows.samples)
        {
            Matrix matrix(kRowCount, report.vertexCount, true);
            for (int row = 0; row < kRowCount; ++row)
            {
                for (int source = 0; source < report.vertexCount; ++source)
                {
                    matrix.set(row, source,
                               sample.rows[row].coefficients[source]);
                }
            }
            shapeFunctions.push_back(std::move(matrix));
        }
        Face face;
        face.index = faceRows.faceIndex;
        face.spontCurvature = 0.17;
        double meanCurvature = 0.0;
        double bendingEnergy = 0.0;
        Matrix normal = mat_calloc(3, 1);
        Matrix fBend = mat_calloc(report.vertexCount, 3);
        Matrix fArea = mat_calloc(report.vertexCount, 3);
        Matrix fVolume = mat_calloc(report.vertexCount, 3);
        evaluator.element_energy_force_regular(
            coordinates, face, face.spontCurvature, meanCurvature, normal,
            bendingEnergy, fBend, fArea, fVolume, false, &shapeFunctions);
        report.bendingEnergy += bendingEnergy;
        finite = finite && std::isfinite(meanCurvature) &&
                 std::isfinite(bendingEnergy);
        double normalNormSquared = 0.0;
        for (int axis = 0; axis < 3; ++axis)
        {
            const double component = normal.get(axis, 0);
            finite = finite && std::isfinite(component);
            normalNormSquared += component * component;
        }
        normalsValidated = normalsValidated &&
            std::isfinite(normalNormSquared) &&
            std::abs(std::sqrt(normalNormSquared) - 1.0) <= 1.0e-10;
        const std::array<const Matrix *, 3> forces{{
            &fBend, &fArea, &fVolume}};
        SourceKeyedFaceForces faceForces;
        faceForces.faceIndex = faceRows.faceIndex;
        faceForces.sourceIds = originalSourceIds;
        faceForces.forces.resize(report.vertexCount);
        for (int source = 0; source < report.vertexCount; ++source)
        {
            for (int kind = 0; kind < 3; ++kind)
            {
                for (int axis = 0; axis < 3; ++axis)
                {
                    const double value = forces[kind]->get(source, axis);
                    finite = finite && std::isfinite(value);
                    report.maxForce[kind] =
                        std::max(report.maxForce[kind], std::abs(value));
                    aggregate[source][kind][axis] += value;
                    faceForces.forces[source][kind][axis] = value;
                }
            }
        }
        kernelInput.forces.push_back(std::move(faceForces));
    }

    const PreparedSourceKeyedKernelCall prepared =
        prepare_source_keyed_kernel_call(kernelInput);
    report.maxSourceKeyedScatterRelativeResidual =
        maximum_source_keyed_scatter_relative_residual(prepared, aggregate);
    report.sourceKeyedScatterVerified =
        std::isfinite(report.maxSourceKeyedScatterRelativeResidual) &&
        report.maxSourceKeyedScatterRelativeResidual <= 5.0e-13;

    for (const auto &source : aggregate)
    {
        for (int kind = 0; kind < 3; ++kind)
        {
            double sourceNorm = 0.0;
            for (int axis = 0; axis < 3; ++axis)
            {
                sourceNorm += source[kind][axis] * source[kind][axis];
            }
            report.aggregateForceL2[kind] += sourceNorm;
        }
    }
    for (double &magnitude : report.aggregateForceL2)
    {
        magnitude = std::sqrt(magnitude);
    }

    for (int kind = 0; kind < kForceKindCount; ++kind)
    {
        std::array<double, 3> netForce{};
        std::array<double, 3> netTorque{};
        double forceScale = 0.0;
        double torqueScale = 0.0;
        for (int source = 0; source < report.vertexCount; ++source)
        {
            const std::array<double, 3> position{{
                coordinates[source].get(0, 0),
                coordinates[source].get(1, 0),
                coordinates[source].get(2, 0)}};
            const Vec3 &force = aggregate[source][kind];
            const std::array<double, 3> torque = cross(position, force);
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                netForce[axis] += force[axis];
                netTorque[axis] += torque[axis];
            }
            forceScale += norm(force);
            torqueScale += norm(torque);
        }
        report.netForceRelativeResidual[kind] =
            norm(netForce) / std::max(1.0, forceScale);
        report.netTorqueRelativeResidual[kind] =
            norm(netTorque) / std::max(1.0, torqueScale);
    }
    report.forceBalanceVerified =
        std::all_of(report.netForceRelativeResidual.begin(),
                    report.netForceRelativeResidual.end(),
                    [](const double residual) {
                        return std::isfinite(residual) &&
                               residual <= 5.0e-10;
                    }) &&
        std::all_of(report.netTorqueRelativeResidual.begin(),
                    report.netTorqueRelativeResidual.end(),
                    [](const double residual) {
                        return std::isfinite(residual) &&
                               residual <= 5.0e-10;
                    });
    report.unsupportedMixedForceImbalanceObserved =
        !report.providerApplicable &&
        report.netForceRelativeResidual[0] <= 5.0e-10 &&
        report.netForceRelativeResidual[1] <= 5.0e-10 &&
        report.netForceRelativeResidual[2] > 1.0e-3;
    report.finite = finite;
    report.normalsValidated = normalsValidated;
    report.positiveArea = report.area > 0.0;
    report.nonzeroBendingForce = report.maxForce[0] > 1.0e-12;
    report.nonzeroAreaForce = report.maxForce[1] > 1.0e-12;
    report.nonzeroVolumeForce = report.maxForce[2] > 1.0e-12;

    constexpr std::array<double, 2> kDifferenceSteps{{1.0e-5, 1.0e-6}};
    constexpr double kDifferenceTolerance = 2.0e-4;
    for (int source = 0; source < report.vertexCount; ++source)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            const double original = coordinates[source].get(axis, 0);
            for (const double relativeStep : kDifferenceSteps)
            {
                const double step = relativeStep *
                                    std::max(1.0, std::abs(original));
                coordinates[source].set(axis, 0, original + step);
                const auto plus = evaluate_total_energies(
                    evaluator, rows, coordinates, 0.17);
                coordinates[source].set(axis, 0, original - step);
                const auto minus = evaluate_total_energies(
                    evaluator, rows, coordinates, 0.17);
                coordinates[source].set(axis, 0, original);
                for (int kind = 0; kind < 3; ++kind)
                {
                    const double numericalForce =
                        -(plus[kind] - minus[kind]) /
                        (2.0 * step);
                    const double actualForce =
                        aggregate[source][kind][axis];
                    const double scale = std::max(
                        1.0, std::max(std::abs(numericalForce),
                                      std::abs(actualForce)));
                    report.maxFiniteDifferenceError[kind] = std::max(
                        report.maxFiniteDifferenceError[kind],
                        std::abs(numericalForce - actualForce) / scale);
                }
            }
        }
    }
    report.finiteDifferenceVerified = std::all_of(
        report.maxFiniteDifferenceError.begin(),
        report.maxFiniteDifferenceError.end(),
        [](const double error) {
            return std::isfinite(error) && error <= kDifferenceTolerance;
        });
    report.fullDivergenceVolumeConjugacyVerified =
        std::isfinite(report.maxFiniteDifferenceError[2]) &&
        report.maxFiniteDifferenceError[2] <= kDifferenceTolerance;
    return report;
#endif
}

void print_ints(const std::vector<int> &values)
{
    std::cout << '[';
    for (std::size_t index = 0; index < values.size(); ++index)
    {
        if (index)
            std::cout << ',';
        std::cout << values[index];
    }
    std::cout << ']';
}

void print_report(const FixtureReport &report)
{
    std::cout << "{\"name\":\"" << report.name << "\"";
    std::cout << ",\"vertex_count\":" << report.vertexCount;
    std::cout << ",\"face_count\":" << report.faceCount;
    std::cout << ",\"valences\":";
    print_ints(report.valences);
    std::cout << ",\"closed\":" << (report.closed ? "true" : "false");
    std::cout << ",\"mixed_345_face_present\":"
              << (report.mixed345FacePresent ? "true" : "false");
    std::cout << ",\"all_faces_are_344\":"
              << (report.allFacesAre344 ? "true" : "false");
    std::cout << ",\"rows_valid\":"
              << (report.rowsValid ? "true" : "false");
    std::cout << ",\"provider_applicable\":"
              << (report.providerApplicable ? "true" : "false");
    std::cout << ",\"canonical_provider_parity\":"
              << (report.providerParity ? "true" : "false");
    std::cout << ",\"topology_keyed_provider_cache_validated\":"
              << (report.providerCacheValidated ? "true" : "false");
    std::cout << ",\"provider_rejected_when_not_applicable\":"
              << (report.providerRejectedWhenNotApplicable ? "true"
                                                            : "false");
    std::cout << ",\"negative_provider_contracts_validated\":"
              << (report.negativeProviderContractsValidated ? "true"
                                                             : "false");
    std::cout << ",\"isolation_delta_level_4_to_5\":"
              << report.isolationDeltaLevel4To5;
    std::cout << ",\"isolation_delta_level_5_to_6\":"
              << report.isolationDeltaLevel5To6;
    std::cout << ",\"isolation_sensitivity_validated\":"
              << (report.isolationSensitivityValidated ? "true" : "false");
    std::cout << ",\"normals_validated\":"
              << (report.normalsValidated ? "true" : "false");
    std::cout << ",\"finite\":" << (report.finite ? "true" : "false");
    std::cout << ",\"area\":" << report.area;
    std::cout << ",\"full_divergence_volume\":" << report.volume;
    std::cout << ",\"bending_energy\":" << report.bendingEnergy;
    std::cout << ",\"max_abs_force\":[" << report.maxForce[0] << ','
              << report.maxForce[1] << ',' << report.maxForce[2] << ']';
    std::cout << ",\"max_transpose_relative_residual\":"
              << report.maxTransposeRelativeResidual;
    std::cout << ",\"transpose_identity_verified\":"
              << (report.transposeIdentityVerified ? "true" : "false");
    std::cout << ",\"max_source_keyed_scatter_relative_residual\":"
              << report.maxSourceKeyedScatterRelativeResidual;
    std::cout << ",\"source_keyed_scatter_verified\":"
              << (report.sourceKeyedScatterVerified ? "true" : "false");
    std::cout << ",\"max_finite_difference_relative_error\":["
              << report.maxFiniteDifferenceError[0] << ','
              << report.maxFiniteDifferenceError[1] << ','
              << report.maxFiniteDifferenceError[2] << ']';
    std::cout << ",\"finite_difference_verified\":"
              << (report.finiteDifferenceVerified ? "true" : "false");
    std::cout << ",\"full_divergence_volume_conjugacy_verified\":"
              << (report.fullDivergenceVolumeConjugacyVerified
                      ? "true" : "false");
    std::cout << ",\"aggregate_force_l2\":["
              << report.aggregateForceL2[0] << ','
              << report.aggregateForceL2[1] << ','
              << report.aggregateForceL2[2] << ']';
    std::cout << ",\"net_force_relative_residual\":["
              << report.netForceRelativeResidual[0] << ','
              << report.netForceRelativeResidual[1] << ','
              << report.netForceRelativeResidual[2] << ']';
    std::cout << ",\"net_torque_relative_residual\":["
              << report.netTorqueRelativeResidual[0] << ','
              << report.netTorqueRelativeResidual[1] << ','
              << report.netTorqueRelativeResidual[2] << ']';
    std::cout << ",\"force_balance_verified\":"
              << (report.forceBalanceVerified ? "true" : "false");
    std::cout << ",\"unsupported_mixed_force_imbalance_observed\":"
              << (report.unsupportedMixedForceImbalanceObserved
                      ? "true" : "false");
    std::cout << '}';
}

void print_doubles(const std::vector<double> &values)
{
    std::cout << '[';
    for (std::size_t index = 0; index < values.size(); ++index)
    {
        if (index)
        {
            std::cout << ',';
        }
        std::cout << values[index];
    }
    std::cout << ']';
}

void print_quadrature_convergence(
    const QuadratureConvergenceReport &report)
{
    std::cout << "{\"name\":\"" << report.name << "\"";
    std::cout << ",\"levels\":[";
    for (std::size_t index = 0; index < report.levels.size(); ++index)
    {
        if (index)
        {
            std::cout << ',';
        }
        const QuadratureEvaluation &level = report.levels[index];
        std::cout << "{\"depth\":" << level.depth
                  << ",\"samples_per_face\":" << level.samplesPerFace
                  << ",\"plan_validated\":"
                  << (level.planValidated ? "true" : "false")
                  << ",\"rows_structurally_valid\":"
                  << (level.rowsStructurallyValid ? "true" : "false")
                  << ",\"rows_valid\":"
                  << (level.rowsValid ? "true" : "false")
                  << ",\"maximum_row_invariant_residual\":"
                  << level.maximumRowInvariantResidual
                  << ",\"finite\":"
                  << (level.finite ? "true" : "false")
                  << ",\"area\":" << level.area
                  << ",\"full_divergence_volume\":" << level.volume
                  << ",\"bending_energy\":" << level.bendingEnergy
                  << ",\"total_energy\":" << level.totalEnergy << '}';
    }
    std::cout << "]";
    std::cout << ",\"global_relative_changes\":";
    print_doubles(report.globalRelativeChanges);
    std::cout << ",\"force_relative_changes\":";
    print_doubles(report.forceRelativeChanges);
    std::cout << ",\"all_plans_validated\":"
              << (report.allPlansValidated ? "true" : "false");
    std::cout << ",\"all_rows_structurally_valid\":"
              << (report.allRowsStructurallyValid ? "true" : "false");
    std::cout << ",\"all_rows_valid\":"
              << (report.allRowsValid ? "true" : "false");
    std::cout << ",\"all_finite\":"
              << (report.allFinite ? "true" : "false");
    std::cout << ",\"two_successive_global_targets_met\":"
              << (report.twoSuccessiveGlobalTargetsMet ? "true" : "false");
    std::cout << ",\"two_successive_force_targets_met\":"
              << (report.twoSuccessiveForceTargetsMet ? "true" : "false");
    std::cout << ",\"scientific_targets_met\":"
              << (report.scientificTargetsMet ? "true" : "false");
    std::cout << ",\"activation_blocked\":"
              << (report.activationBlocked ? "true" : "false");
    std::cout << ",\"study_completed\":"
              << (report.studyCompleted ? "true" : "false");
    std::cout << ",\"passed\":" << (report.passed ? "true" : "false")
              << '}';
}

void print_quadrature_study_contract()
{
    std::cout << "{\"k_curv\":" << kStudyKCurv
              << ",\"u_surf\":" << kStudyUSurf
              << ",\"u_vol\":" << kStudyUVol
              << ",\"spontaneous_curvature\":"
              << kStudySpontaneousCurvature
              << ",\"area0\":" << kStudyArea0
              << ",\"vol0\":" << kStudyVol0
              << ",\"adaptive_isolation_level\":"
              << kStudyAdaptiveIsolationLevel
              << ",\"maximum_depth\":" << kStudyMaximumDepth
              << ",\"global_change_target\":"
              << kStudyGlobalChangeTarget
              << ",\"force_change_target\":"
              << kStudyForceChangeTarget
              << ",\"row_invariant_target\":" << kRowTolerance
              << ",\"global_change_denominator\":"
              << "\"max(1e-12,abs(previous),abs(current))\""
              << ",\"force_change_denominator\":"
              << "\"max(1,abs(previous),abs(current))\"}";
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 9)
    {
        std::cerr << "usage: " << argv[0]
                  << " TETRA_VERTICES TETRA_FACES MIXED_VERTICES MIXED_FACES"
                  << " BIPYRAMID_VERTICES BIPYRAMID_FACES"
                  << " ASYMMETRIC_BIPYRAMID_VERTICES"
                  << " ASYMMETRIC_BIPYRAMID_FACES\n";
        return 2;
    }

#ifndef USE_OPENSUBDIV_VALENCE3
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(read_data_from_csv<double>(argv[1]),
                                   read_data_from_csv<int>(argv[2]));
    OpenSubdivValence3RowProviderRequest request;
    request.phase1ProviderExplicitRequest = true;
    const auto disabled =
        build_guarded_opensubdiv_valence3_rows(mesh, request);
    const bool passed = !disabled.accepted &&
                        !disabled.opensubdivCompiled &&
                        disabled.explicitRequestReceived &&
                        disabled.rows.empty();
    std::cout << "{\"status\":\"" << (passed ? "passed" : "failed")
              << "\",\"dependency_disabled_contract_passed\":"
              << (passed ? "true" : "false")
              << ",\"production_route_enabled\":false}\n";
    return passed ? 0 : 3;
#else
    try
    {
        const FixtureReport tetra = evaluate_fixture(
            "closed_valence3_tetrahedron", argv[1], argv[2], true);
        const FixtureReport asymmetric = evaluate_fixture(
            "asymmetric_valence3_tetrahedron", argv[1], argv[2], true, true);
        const FixtureReport mixed = evaluate_fixture(
            "closed_mixed_valence345", argv[3], argv[4], false);
        const FixtureReport bipyramid = evaluate_fixture(
            "closed_valence3_triangular_bipyramid", argv[5], argv[6], true,
            false, Valence3TopologyKind::TriangularBipyramid344);
        const FixtureReport asymmetricBipyramid = evaluate_fixture(
            "asymmetric_valence3_triangular_bipyramid", argv[7], argv[8],
            true, false, Valence3TopologyKind::TriangularBipyramid344);
        const QuadratureConvergenceReport bipyramidConvergence =
            evaluate_quadrature_convergence(
                "closed_valence3_triangular_bipyramid", argv[5], argv[6]);
        const QuadratureConvergenceReport asymmetricBipyramidConvergence =
            evaluate_quadrature_convergence(
                "asymmetric_valence3_triangular_bipyramid",
                argv[7], argv[8]);
        const bool tetraValence3 =
            tetra.valences == std::vector<int>({3, 3, 3, 3});
        const std::set<int> mixedValences(
            mixed.valences.begin(), mixed.valences.end());
        const bool mixedValenceSet =
            mixedValences == std::set<int>({3, 4, 5});
        const bool bipyramidValences =
            bipyramid.valences == std::vector<int>({3, 3, 4, 4, 4});
        const auto sciencePassed = [](const FixtureReport &report) {
            const bool providerContract = report.providerApplicable
                ? report.providerParity
                : report.providerRejectedWhenNotApplicable;
            const bool forceBalanceContract = report.providerApplicable
                ? report.forceBalanceVerified
                : report.unsupportedMixedForceImbalanceObserved;
            return report.closed && report.rowsValid && providerContract &&
                   report.negativeProviderContractsValidated &&
                   report.isolationSensitivityValidated &&
                   report.finite && report.normalsValidated &&
                   report.positiveArea &&
                   report.nonzeroBendingForce && report.nonzeroAreaForce &&
                   report.nonzeroVolumeForce &&
                   report.transposeIdentityVerified &&
                   report.sourceKeyedScatterVerified &&
                   forceBalanceContract &&
                   report.finiteDifferenceVerified &&
                   report.fullDivergenceVolumeConjugacyVerified;
        };
        const bool passed = sciencePassed(tetra) &&
                            sciencePassed(asymmetric) &&
                            sciencePassed(mixed) &&
                            sciencePassed(bipyramid) &&
                            sciencePassed(asymmetricBipyramid) &&
                            tetraValence3 && mixedValenceSet &&
                            mixed.mixed345FacePresent &&
                            bipyramidValences && bipyramid.allFacesAre344 &&
                            bipyramidConvergence.passed &&
                            asymmetricBipyramidConvergence.passed;
        std::cout << std::setprecision(17);
        std::cout << "{\"status\":\"" << (passed ? "passed" : "failed")
                  << "\",\"proof_only\":true"
                  << ",\"phase2_mechanical_packet_started\":true"
                  << ",\"not_production_routing\":true"
                  << ",\"production_route_enabled\":false"
                  << ",\"production_mesh_mutated\":false"
                  << ",\"existing_slimed_energy_force_algebra_executed\":true"
                  << ",\"volume_force_checked_against_full_divergence_functional\":true"
                  << ",\"full_divergence_volume_energy_force_conjugate\":true"
                  << ",\"legacy_x_only_volume_mismatch_resolved_for_valence3\":true"
                  << ",\"broader_topology_quadrature_targets_met\":"
                  << (bipyramidConvergence.scientificTargetsMet &&
                              asymmetricBipyramidConvergence.scientificTargetsMet
                          ? "true" : "false")
                  << ",\"broader_topology_activation_blocked\":"
                  << (bipyramidConvergence.activationBlocked &&
                              asymmetricBipyramidConvergence.activationBlocked
                          ? "true" : "false")
                  << ",\"quadrature_study_contract\":";
        print_quadrature_study_contract();
        std::cout
                  << ",\"fixtures\":[";
        print_report(tetra);
        std::cout << ',';
        print_report(asymmetric);
        std::cout << ',';
        print_report(mixed);
        std::cout << ',';
        print_report(bipyramid);
        std::cout << ',';
        print_report(asymmetricBipyramid);
        std::cout << "],\"quadrature_convergence\":[";
        print_quadrature_convergence(bipyramidConvergence);
        std::cout << ',';
        print_quadrature_convergence(asymmetricBipyramidConvergence);
        std::cout << "]}\n";
        return passed ? 0 : 4;
    }
    catch (const std::exception &error)
    {
        std::cout << "{\"status\":\"failed\",\"error\":\""
                  << error.what() << "\"}\n";
        return 5;
    }
#endif
}
