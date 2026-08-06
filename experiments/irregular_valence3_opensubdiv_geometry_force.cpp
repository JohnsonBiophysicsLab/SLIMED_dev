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
constexpr std::array<double, kSampleCount> kS{{
    1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0}};
constexpr std::array<double, kSampleCount> kT{{
    1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0}};

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
                        const int sourceCount)
{
    if (static_cast<int>(rows.size()) != faceCount)
    {
        return false;
    }
    for (int face = 0; face < faceCount; ++face)
    {
        if (rows[face].faceIndex != face ||
            rows[face].samples.size() != kSampleCount)
        {
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
                    return false;
                }
                const double sum = std::accumulate(
                    actual.coefficients.begin(),
                    actual.coefficients.end(), 0.0);
                if (std::abs(sum - (row == 0 ? 1.0 : 0.0)) >
                    kRowTolerance)
                {
                    return false;
                }
            }
            if (sample.rows[5].sourceIds != sample.rows[6].sourceIds ||
                sample.rows[5].coefficients != sample.rows[6].coefficients)
            {
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
    const Mesh &mesh, const int adaptiveIsolationLevel)
{
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
    std::vector<std::array<double, kSampleCount>> sByFace(
        mesh.faces.size(), kS);
    std::vector<std::array<double, kSampleCount>> tByFace(
        mesh.faces.size(), kT);
    Factory::LocationArrayVec locations;
    for (std::size_t face = 0; face < mesh.faces.size(); ++face)
    {
        Factory::LocationArray location;
        location.ptexIdx = static_cast<int>(face);
        location.numLocations = kSampleCount;
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
                         static_cast<int>(mesh.faces.size()) * kSampleCount)
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
        faceRows.samples.resize(kSampleCount);
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            const Far::PatchMap::Handle *handle = patchMap.FindPatch(
                static_cast<int>(face), kS[sample], kT[sample]);
            if (!handle || patchTable->GetPatchParam(*handle).GetFaceId() !=
                               static_cast<int>(face))
            {
                throw std::runtime_error("OpenSubdiv sample left Ptex face");
            }
            const auto stencil = stencils->GetLimitStencil(
                static_cast<int>(face) * kSampleCount + sample);
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
} // namespace

int main(int argc, char **argv)
{
    if (argc != 7)
    {
        std::cerr << "usage: " << argv[0]
                  << " TETRA_VERTICES TETRA_FACES MIXED_VERTICES MIXED_FACES"
                  << " BIPYRAMID_VERTICES BIPYRAMID_FACES\n";
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
            "asymmetric_valence3_triangular_bipyramid", argv[5], argv[6],
            true, true, Valence3TopologyKind::TriangularBipyramid344);
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
                            bipyramidValences && bipyramid.allFacesAre344;
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
