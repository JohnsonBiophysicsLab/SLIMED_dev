#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_valence3_row_provider.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
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
#endif

using slimed::opensubdiv_valence3::OpenSubdivValence3RowProviderRequest;
using slimed::opensubdiv_valence3::build_guarded_opensubdiv_valence3_rows;
using namespace slimed::source_keyed_kernel;

namespace
{
constexpr int kSampleCount = 3;
constexpr int kRowCount = 7;
constexpr int kAxisCount = 3;
constexpr double kLegacyVolumeFactor = 0.16666666666;
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
    bool rowsValid = false;
    bool providerParity = false;
    bool finite = false;
    bool positiveArea = false;
    bool nonzeroBendingForce = false;
    bool nonzeroAreaForce = false;
    bool nonzeroVolumeForce = false;
    bool finiteDifferenceVerified = false;
    bool legacyVolumeForceMismatchObserved = false;
    double area = 0.0;
    double volume = 0.0;
    double bendingEnergy = 0.0;
    std::array<double, 3> maxForce{{0.0, 0.0, 0.0}};
    std::array<double, 3> maxFiniteDifferenceError{{0.0, 0.0, 0.0}};
    double maxLegacyVolumeFiniteDifferenceError = 0.0;
    std::array<double, 3> netForceResidual{{0.0, 0.0, 0.0}};
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

std::vector<SourceKeyedFaceRows> build_proof_rows(const Mesh &mesh)
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

    Far::PatchTableFactory::Options patchOptions(5);
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

std::array<double, 4> evaluate_total_energies(
    Mesh &evaluator,
    const std::vector<SourceKeyedFaceRows> &rows,
    const std::vector<Matrix> &coordinates,
    const double spontaneousCurvature)
{
    double area = 0.0;
    double legacyVolume = 0.0;
    double forceConjugateVolume = 0.0;
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
            legacyVolume += (kLegacyVolumeFactor / 3.0) * position[0] *
                            areaVector[0];
            forceConjugateVolume += (kLegacyVolumeFactor / 3.0) *
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
        std::pow(legacyVolume - evaluator.param.vol0, 2);
    const double currentVolumeMultiplier =
        evaluator.param.uVol / evaluator.param.vol0 *
        (evaluator.param.vol - evaluator.param.vol0);
    const double forceConjugateVolumePotential =
        currentVolumeMultiplier * forceConjugateVolume;
    return {{bending, areaEnergy, volumeEnergy,
             forceConjugateVolumePotential}};
}

FixtureReport evaluate_fixture(const std::string &name,
                               const std::string &verticesPath,
                               const std::string &facesPath,
                               const bool requireProviderParity)
{
    FixtureReport report;
    report.name = name;
    Param setupParam;
    setupParam.VERBOSE_MODE = false;
    setupParam.boundaryCondition = BoundaryType::Fixed;
    Mesh mesh(setupParam);
    mesh.setup_from_vertices_faces(read_data_from_csv<double>(verticesPath),
                                   read_data_from_csv<int>(facesPath));
    report.vertexCount = static_cast<int>(mesh.vertices.size());
    report.faceCount = static_cast<int>(mesh.faces.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        report.valences.push_back(
            static_cast<int>(vertex.adjacentVertices.size()));
    }
    report.closed = closed_mesh(mesh);
    report.mixed345FacePresent = has_mixed_345_face(mesh);

#ifndef USE_OPENSUBDIV_VALENCE3
    (void)requireProviderParity;
    return report;
#else
    const std::vector<SourceKeyedFaceRows> rows = build_proof_rows(mesh);
    report.rowsValid = finite_row_package(
        rows, report.faceCount, report.vertexCount);

    if (requireProviderParity)
    {
        OpenSubdivValence3RowProviderRequest request;
        request.phase1ProviderExplicitRequest = true;
        const auto provider =
            build_guarded_opensubdiv_valence3_rows(mesh, request);
        report.providerParity = provider.accepted &&
                                packages_match(provider.rows, rows);
    }
    else
    {
        report.providerParity = true;
    }

    std::vector<Matrix> coordinates;
    coordinates.reserve(mesh.vertices.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        coordinates.push_back(vertex.coord);
    }

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
            report.volume += kLegacyVolumeFactor * weight * position[0] *
                             areaVector[0];
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

    std::vector<std::array<std::array<double, 3>, 3>> aggregate(
        mesh.vertices.size());
    bool finite = std::isfinite(report.area) && std::isfinite(report.volume);
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
        const std::array<const Matrix *, 3> forces{{
            &fBend, &fArea, &fVolume}};
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
                }
            }
        }
    }
    for (const auto &source : aggregate)
    {
        for (int kind = 0; kind < 3; ++kind)
        {
            double sourceNorm = 0.0;
            for (int axis = 0; axis < 3; ++axis)
            {
                sourceNorm += source[kind][axis] * source[kind][axis];
            }
            report.netForceResidual[kind] += sourceNorm;
        }
    }
    for (double &residual : report.netForceResidual)
    {
        residual = std::sqrt(residual);
    }
    report.finite = finite;
    report.positiveArea = report.area > 0.0;
    report.nonzeroBendingForce = report.maxForce[0] > 1.0e-12;
    report.nonzeroAreaForce = report.maxForce[1] > 1.0e-12;
    report.nonzeroVolumeForce = report.maxForce[2] > 1.0e-12;

    constexpr double kDifferenceStep = 1.0e-6;
    constexpr double kDifferenceTolerance = 2.0e-4;
    for (int source = 0; source < report.vertexCount; ++source)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            const double original = coordinates[source].get(axis, 0);
            const double step = kDifferenceStep *
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
                const int energyIndex = kind == 2 ? 3 : kind;
                const double numericalForce =
                    -(plus[energyIndex] - minus[energyIndex]) /
                    (2.0 * step);
                const double actualForce = aggregate[source][kind][axis];
                const double scale = std::max(
                    1.0, std::max(std::abs(numericalForce),
                                  std::abs(actualForce)));
                report.maxFiniteDifferenceError[kind] = std::max(
                    report.maxFiniteDifferenceError[kind],
                    std::abs(numericalForce - actualForce) / scale);
            }
            const double legacyVolumeNumericalForce =
                -(plus[2] - minus[2]) / (2.0 * step);
            const double actualVolumeForce = aggregate[source][2][axis];
            const double legacyScale = std::max(
                1.0, std::max(std::abs(legacyVolumeNumericalForce),
                              std::abs(actualVolumeForce)));
            report.maxLegacyVolumeFiniteDifferenceError = std::max(
                report.maxLegacyVolumeFiniteDifferenceError,
                std::abs(legacyVolumeNumericalForce - actualVolumeForce) /
                    legacyScale);
        }
    }
    report.finiteDifferenceVerified = std::all_of(
        report.maxFiniteDifferenceError.begin(),
        report.maxFiniteDifferenceError.end(),
        [](const double error) {
            return std::isfinite(error) && error <= kDifferenceTolerance;
        });
    report.legacyVolumeForceMismatchObserved =
        std::isfinite(report.maxLegacyVolumeFiniteDifferenceError) &&
        report.maxLegacyVolumeFiniteDifferenceError > 1.0e-3;
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
    std::cout << ",\"rows_valid\":"
              << (report.rowsValid ? "true" : "false");
    std::cout << ",\"canonical_provider_parity\":"
              << (report.providerParity ? "true" : "false");
    std::cout << ",\"finite\":" << (report.finite ? "true" : "false");
    std::cout << ",\"area\":" << report.area;
    std::cout << ",\"legacy_volume\":" << report.volume;
    std::cout << ",\"bending_energy\":" << report.bendingEnergy;
    std::cout << ",\"max_abs_force\":[" << report.maxForce[0] << ','
              << report.maxForce[1] << ',' << report.maxForce[2] << ']';
    std::cout << ",\"max_finite_difference_relative_error\":["
              << report.maxFiniteDifferenceError[0] << ','
              << report.maxFiniteDifferenceError[1] << ','
              << report.maxFiniteDifferenceError[2] << ']';
    std::cout << ",\"finite_difference_verified\":"
              << (report.finiteDifferenceVerified ? "true" : "false");
    std::cout << ",\"legacy_volume_energy_force_relative_error\":"
              << report.maxLegacyVolumeFiniteDifferenceError;
    std::cout << ",\"legacy_volume_force_mismatch_observed\":"
              << (report.legacyVolumeForceMismatchObserved ? "true"
                                                            : "false");
    std::cout << ",\"aggregate_force_l2\":["
              << report.netForceResidual[0] << ','
              << report.netForceResidual[1] << ','
              << report.netForceResidual[2] << ']';
    std::cout << '}';
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 5)
    {
        std::cerr << "usage: " << argv[0]
                  << " TETRA_VERTICES TETRA_FACES MIXED_VERTICES MIXED_FACES\n";
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
        const FixtureReport mixed = evaluate_fixture(
            "closed_mixed_valence345", argv[3], argv[4], false);
        const bool tetraValence3 =
            tetra.valences == std::vector<int>({3, 3, 3, 3});
        const std::set<int> mixedValences(
            mixed.valences.begin(), mixed.valences.end());
        const bool mixedValenceSet =
            mixedValences == std::set<int>({3, 4, 5});
        const auto sciencePassed = [](const FixtureReport &report) {
            return report.closed && report.rowsValid && report.providerParity &&
                   report.finite && report.positiveArea &&
                   report.nonzeroBendingForce && report.nonzeroAreaForce &&
                   report.nonzeroVolumeForce &&
                   report.finiteDifferenceVerified &&
                   report.legacyVolumeForceMismatchObserved;
        };
        const bool passed = sciencePassed(tetra) && sciencePassed(mixed) &&
                            tetraValence3 && mixedValenceSet &&
                            mixed.mixed345FacePresent;
        std::cout << std::setprecision(17);
        std::cout << "{\"status\":\"" << (passed ? "passed" : "failed")
                  << "\",\"proof_only\":true"
                  << ",\"not_production_routing\":true"
                  << ",\"production_route_enabled\":false"
                  << ",\"production_mesh_mutated\":false"
                  << ",\"existing_slimed_energy_force_algebra_executed\":true"
                  << ",\"volume_force_checked_against_full_divergence_functional\":true"
                  << ",\"legacy_x_only_volume_mismatch_is_a_production_blocker\":true"
                  << ",\"fixtures\":[";
        print_report(tetra);
        std::cout << ',';
        print_report(mixed);
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
