#include "energy_force/Source_keyed_kernel_call.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"
#include "Parameters.hpp"

#include <omp.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
using namespace slimed::source_keyed_kernel;

constexpr int kFaceCount = 8;
constexpr int kSourceCount = 6;
constexpr int kSampleCount = 3;
constexpr int kForceComponents = kSourceCount * kForceKindCount * kAxisCount;
constexpr int kRepeats = 5;
constexpr double kTolerance = 1.0e-12;

constexpr std::array<std::array<int, 3>, kFaceCount> kOrientedFaces{{
    {{0, 2, 3}},
    {{0, 3, 4}},
    {{0, 4, 5}},
    {{0, 5, 2}},
    {{1, 3, 2}},
    {{1, 4, 3}},
    {{1, 5, 4}},
    {{1, 2, 5}},
}};

using NestedForceOracle =
    std::array<std::array<std::array<long double, kAxisCount>,
                          kForceKindCount>,
               kSourceCount>;

struct RawForceOracle
{
    std::array<long double, kForceComponents> values{};
    std::array<int, kForceComponents> collisionCounts{};
};

struct FormulaParameters
{
    double kCurv = 0.0;
    double spontCurv = 0.0;
    double uSurf = 0.0;
    double area0 = 0.0;
    double uVol = 0.0;
    double vol0 = 0.0;
    double area = 0.0;
    double volume = 0.0;
};

struct FaceObservable
{
    double meanCurvature = 0.0;
    double bendingEnergy = 0.0;
    std::array<double, kAxisCount> normal{};
    double area = 0.0;
    double fullVolume = 0.0;
    double legacyVisibleVolume = 0.0;
    std::array<std::array<std::array<double, kAxisCount>,
                          kForceKindCount>,
               kSourceCount>
        forces{};
};

struct GlobalObservable
{
    double bendingEnergy = 0.0;
    double area = 0.0;
    double fullVolume = 0.0;
    double legacyVisibleVolume = 0.0;
    double areaConstraintEnergy = 0.0;
    double volumeConstraintEnergy = 0.0;
    double totalEnergy = 0.0;
};

struct InputPackage
{
    FormulaParameters parameters;
    std::vector<Vec3> coordinates;
    std::vector<SourceKeyedFaceRows> rows;
    std::vector<SourceKeyedFaceForces> forces;
    std::array<FaceObservable, kFaceCount> expectedFaces{};
    GlobalObservable expectedGlobal;
};

struct ShadowOutput
{
    std::array<FaceObservable, kFaceCount> faces{};
    std::array<double, kForceComponents> vertexForces{};
    std::array<int, kForceComponents> collisionCounts{};
    GlobalObservable global;
    int requestedThreads = 0;
    int actualThreads = 0;
    bool finite = true;
    bool proofOnly = true;
    bool productionCallShadow = true;
    bool notProductionRouting = true;
    bool productionRouteEnabled = false;
    bool actualProductionForcePathExecuted = false;
    bool productionFaceLoopExecuted = false;
    bool productionOneRingsPopulated = false;
};

struct Comparison
{
    double maxFaceObservableDelta = 0.0;
    double maxVertexForceDelta = 0.0;
    double maxGlobalObservableDelta = 0.0;
    double minCanonicalNormalDot = 1.0;
    bool finite = true;
    bool collisionCoverage = true;
};

struct ThreadSummary
{
    int requestedThreads = 0;
    std::array<int, kRepeats> actualThreads{};
    double maxOracleDelta = 0.0;
    double maxSerialDelta = 0.0;
    double maxRepeatDelta = 0.0;
    double minCanonicalNormalDot = 1.0;
    bool finite = true;
    bool collisionCoverage = true;
    bool passed = true;
};

int force_index(const int source, const int kind, const int axis)
{
    return source * (kForceKindCount * kAxisCount) +
           kind * kAxisCount + axis;
}

bool finite_value(const double value)
{
    return std::isfinite(value);
}

bool read_package(const std::string &path, InputPackage &package)
{
    std::ifstream input(path);
    int faces = 0;
    int samples = 0;
    int rows = 0;
    int sources = 0;
    if (!(input >> faces >> samples >> rows >> sources) ||
        faces != kFaceCount || samples != kSampleCount ||
        rows != kDerivativeRowCount || sources != kSourceCount)
    {
        return false;
    }

    std::string tag;
    if (!(input >> tag) || tag != "PARAMETERS" ||
        !(input >> package.parameters.kCurv >>
          package.parameters.spontCurv >>
          package.parameters.uSurf >>
          package.parameters.area0 >>
          package.parameters.uVol >>
          package.parameters.vol0 >>
          package.parameters.area >>
          package.parameters.volume))
    {
        return false;
    }
    const std::array<double, 8> parameters{{
        package.parameters.kCurv,
        package.parameters.spontCurv,
        package.parameters.uSurf,
        package.parameters.area0,
        package.parameters.uVol,
        package.parameters.vol0,
        package.parameters.area,
        package.parameters.volume,
    }};
    if (!std::all_of(parameters.begin(), parameters.end(), finite_value))
    {
        return false;
    }

    int coordinateCount = 0;
    if (!(input >> tag >> coordinateCount) || tag != "COORDINATES" ||
        coordinateCount != kSourceCount)
    {
        return false;
    }
    package.coordinates.resize(kSourceCount);
    for (int source = 0; source < kSourceCount; ++source)
    {
        int encodedSource = -1;
        if (!(input >> encodedSource) || encodedSource != source)
        {
            return false;
        }
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            if (!(input >> package.coordinates[source][axis]) ||
                !finite_value(package.coordinates[source][axis]))
            {
                return false;
            }
        }
    }

    package.rows.resize(kFaceCount);
    package.forces.resize(kFaceCount);
    for (int face = 0; face < kFaceCount; ++face)
    {
        int encodedFace = -1;
        if (!(input >> encodedFace) || encodedFace != face)
        {
            return false;
        }
        SourceKeyedFaceRows &faceRows = package.rows[face];
        faceRows.faceIndex = face;
        for (int corner = 0; corner < 3; ++corner)
        {
            if (!(input >> faceRows.orientedFaceVertices[corner]))
            {
                return false;
            }
        }
        faceRows.samples.resize(kSampleCount);
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            int encodedSample = -1;
            if (!(input >> encodedSample) || encodedSample != sample)
            {
                return false;
            }
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                SourceKeyedRow &target =
                    faceRows.samples[sample].rows[row];
                target.sourceIds.resize(kSourceCount);
                target.coefficients.resize(kSourceCount);
                for (int source = 0; source < kSourceCount; ++source)
                {
                    if (!(input >> target.sourceIds[source] >>
                          target.coefficients[source]) ||
                        !finite_value(target.coefficients[source]))
                    {
                        return false;
                    }
                }
            }
        }

        SourceKeyedFaceForces &faceForces = package.forces[face];
        faceForces.faceIndex = face;
        faceForces.sourceIds.resize(kSourceCount);
        faceForces.forces.resize(kSourceCount);
        for (int source = 0; source < kSourceCount; ++source)
        {
            if (!(input >> faceForces.sourceIds[source]))
            {
                return false;
            }
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    if (!(input >>
                          faceForces.forces[source][kind][axis]) ||
                        !finite_value(
                            faceForces.forces[source][kind][axis]))
                    {
                        return false;
                    }
                }
            }
        }
    }

    int observableFaceCount = 0;
    if (!(input >> tag >> observableFaceCount) ||
        tag != "FACE_OBSERVABLES" ||
        observableFaceCount != kFaceCount)
    {
        return false;
    }
    for (int face = 0; face < kFaceCount; ++face)
    {
        int encodedFace = -1;
        FaceObservable &observable = package.expectedFaces[face];
        if (!(input >> encodedFace) || encodedFace != face ||
            !(input >> observable.meanCurvature >>
              observable.bendingEnergy >>
              observable.normal[0] >>
              observable.normal[1] >>
              observable.normal[2] >>
              observable.area >>
              observable.fullVolume >>
              observable.legacyVisibleVolume))
        {
            return false;
        }
    }
    if (!(input >> tag) || tag != "GLOBAL_OBSERVABLES" ||
        !(input >> package.expectedGlobal.bendingEnergy >>
          package.expectedGlobal.area >>
          package.expectedGlobal.fullVolume >>
          package.expectedGlobal.legacyVisibleVolume >>
          package.expectedGlobal.areaConstraintEnergy >>
          package.expectedGlobal.volumeConstraintEnergy >>
          package.expectedGlobal.totalEnergy))
    {
        return false;
    }
    double trailing = 0.0;
    return !(input >> trailing);
}

std::vector<SourceMappingView> mapping_views(
    const Mesh &mesh,
    const Valence4TopologySourceMappingResult &mapping)
{
    std::vector<SourceMappingView> views;
    if (!mapping.supported || mapping.byFace.size() != mesh.faces.size())
    {
        return views;
    }
    views.reserve(mapping.byFace.size());
    for (std::size_t face = 0; face < mapping.byFace.size(); ++face)
    {
        views.push_back(SourceMappingView{
            mapping.byFace[face].faceIndex,
            mapping.byFace[face].orientedFaceVertices,
            mapping.byFace[face].originalSourceIds,
            mesh.faces[face].oneRingVertices.empty()});
    }
    return views;
}

void validate_prepared(const PreparedSourceKeyedKernelCall &prepared)
{
    if (prepared.sourceCount != kSourceCount ||
        prepared.faces.size() != kFaceCount)
    {
        throw std::invalid_argument(
            "face-loop shadow rejected package cardinality drift");
    }
    const std::vector<int> canonicalSources{0, 1, 2, 3, 4, 5};
    for (int face = 0; face < kFaceCount; ++face)
    {
        const PreparedSourceKeyedFace &preparedFace = prepared.faces[face];
        if (preparedFace.mapping.faceIndex != face ||
            preparedFace.mapping.orientedFaceVertices !=
                kOrientedFaces[face] ||
            preparedFace.mapping.originalSourceIds != canonicalSources ||
            !preparedFace.mapping.productionOneRingEmpty ||
            preparedFace.samples.size() != kSampleCount ||
            preparedFace.forces.size() != kSourceCount)
        {
            throw std::invalid_argument(
                "face-loop shadow rejected mapping or face shape drift");
        }
        for (const SourceKeyedSampleRows &sample : preparedFace.samples)
        {
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                const SourceKeyedRow &sourceRow = sample.rows[row];
                if (sourceRow.sourceIds != canonicalSources ||
                    sourceRow.coefficients.size() != kSourceCount ||
                    !std::all_of(sourceRow.coefficients.begin(),
                                 sourceRow.coefficients.end(),
                                 finite_value))
                {
                    throw std::invalid_argument(
                        "face-loop shadow rejected a late malformed row");
                }
            }
        }
        for (const SourceForceKinds &sourceForces : preparedFace.forces)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                if (!std::all_of(sourceForces[kind].begin(),
                                 sourceForces[kind].end(),
                                 finite_value))
                {
                    throw std::invalid_argument(
                        "face-loop shadow rejected nonfinite force evidence");
                }
            }
        }
    }
}

Param proof_parameters(const InputPackage &package)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.kCurv = package.parameters.kCurv;
    param.uSurf = package.parameters.uSurf;
    param.area0 = package.parameters.area0;
    param.area = package.parameters.area;
    param.uVol = package.parameters.uVol;
    param.vol0 = package.parameters.vol0;
    param.vol = package.parameters.volume;
    param.gaussQuadratureCoeff = Matrix(kSampleCount, 1, true);
    for (int sample = 0; sample < kSampleCount; ++sample)
    {
        param.gaussQuadratureCoeff.set(sample, 0, 1.0 / 3.0);
    }
    return param;
}

std::array<double, 3> cross3(const std::array<double, 3> &left,
                             const std::array<double, 3> &right)
{
    return {{
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    }};
}

double dot3(const std::array<double, 3> &left,
            const std::array<double, 3> &right)
{
    return left[0] * right[0] + left[1] * right[1] +
           left[2] * right[2];
}

void accumulate_visible_observables(
    const PreparedSourceKeyedFace &preparedFace,
    const InputPackage &package,
    FaceObservable &observable)
{
    for (const SourceKeyedSampleRows &sample : preparedFace.samples)
    {
        std::array<std::array<double, 3>, 3> evaluated{};
        for (int row = 0; row < 3; ++row)
        {
            for (int source = 0; source < kSourceCount; ++source)
            {
                const int sourceId = sample.rows[row].sourceIds[source];
                const double coefficient =
                    sample.rows[row].coefficients[source];
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    evaluated[row][axis] +=
                        coefficient * package.coordinates[sourceId][axis];
                }
            }
        }
        const std::array<double, 3> areaVector =
            cross3(evaluated[1], evaluated[2]);
        const double areaMagnitude =
            std::sqrt(dot3(areaVector, areaVector));
        const double quadratureWeight = 1.0 / 3.0;
        observable.area +=
            0.5 * quadratureWeight * areaMagnitude;
        observable.fullVolume +=
            (1.0 / 6.0) * quadratureWeight *
            dot3(evaluated[0], areaVector);
        observable.legacyVisibleVolume +=
            (1.0 / 6.0) * quadratureWeight *
            evaluated[0][0] * areaVector[0];
    }
}

FaceObservable evaluate_face(
    Mesh &formulaMesh,
    const PreparedSourceKeyedFace &preparedFace,
    const InputPackage &package)
{
    const std::vector<int> &sourceIds =
        preparedFace.mapping.originalSourceIds;
    std::vector<Matrix> coordinates(
        kSourceCount, Matrix(kAxisCount, 1, true));
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            coordinates[source].set(
                axis, 0, package.coordinates[sourceIds[source]][axis]);
        }
    }

    std::vector<Matrix> shapeFunctions;
    shapeFunctions.reserve(kSampleCount);
    for (const SourceKeyedSampleRows &sample : preparedFace.samples)
    {
        Matrix rows(kDerivativeRowCount, kSourceCount, true);
        for (int row = 0; row < kDerivativeRowCount; ++row)
        {
            for (int source = 0; source < kSourceCount; ++source)
            {
                rows.set(row, source,
                         sample.rows[row].coefficients[source]);
            }
        }
        shapeFunctions.push_back(std::move(rows));
    }

    Face face;
    face.index = preparedFace.mapping.faceIndex;
    face.spontCurvature = package.parameters.spontCurv;
    Matrix normal = mat_calloc(kAxisCount, 1);
    Matrix bending = mat_calloc(kSourceCount, kAxisCount);
    Matrix area = mat_calloc(kSourceCount, kAxisCount);
    Matrix volume = mat_calloc(kSourceCount, kAxisCount);
    FaceObservable observable;
    formulaMesh.element_energy_force_regular(
        coordinates,
        face,
        face.spontCurvature,
        observable.meanCurvature,
        normal,
        observable.bendingEnergy,
        bending,
        area,
        volume,
        false,
        &shapeFunctions);
    for (int axis = 0; axis < kAxisCount; ++axis)
    {
        observable.normal[axis] = normal.get(axis, 0);
    }
    const std::array<const Matrix *, kForceKindCount> forceMatrices{{
        &bending, &area, &volume,
    }};
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                observable.forces[sourceIds[source]][kind][axis] =
                    forceMatrices[kind]->get(source, axis);
            }
        }
    }
    accumulate_visible_observables(preparedFace, package, observable);
    return observable;
}

void finalize_global(const FormulaParameters &parameters,
                     GlobalObservable &global)
{
    global.areaConstraintEnergy =
        parameters.uSurf == 0.0 || parameters.area0 == 0.0
            ? 0.0
            : 0.5 * (parameters.uSurf / parameters.area0) *
                  std::pow(global.area - parameters.area0, 2);
    global.volumeConstraintEnergy =
        parameters.uVol == 0.0 || parameters.vol0 == 0.0
            ? 0.0
            : 0.5 * (parameters.uVol / parameters.vol0) *
                  std::pow(global.fullVolume - parameters.vol0, 2);
    global.totalEnergy =
        global.bendingEnergy + global.areaConstraintEnergy +
        global.volumeConstraintEnergy;
}

void accumulate_face(const FaceObservable &face,
                     std::array<double, kForceComponents> &forceBuffer,
                     std::array<int, kForceComponents> &collisionBuffer,
                     GlobalObservable &global)
{
    global.bendingEnergy += face.bendingEnergy;
    global.area += face.area;
    global.fullVolume += face.fullVolume;
    global.legacyVisibleVolume += face.legacyVisibleVolume;
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                const int index = force_index(source, kind, axis);
                forceBuffer[index] += face.forces[source][kind][axis];
                ++collisionBuffer[index];
            }
        }
    }
}

void run_serial(const PreparedSourceKeyedKernelCall &prepared,
                const InputPackage &package,
                ShadowOutput &output)
{
    validate_prepared(prepared);
    output = ShadowOutput{};
    output.requestedThreads = 1;
    output.actualThreads = 1;
    Param formulaParam = proof_parameters(package);
    Mesh formulaMesh(formulaParam);
    for (int face = 0; face < kFaceCount; ++face)
    {
        output.faces[face] =
            evaluate_face(formulaMesh, prepared.faces[face], package);
        accumulate_face(output.faces[face],
                        output.vertexForces,
                        output.collisionCounts,
                        output.global);
    }
    finalize_global(package.parameters, output.global);
}

void run_openmp(const PreparedSourceKeyedKernelCall &prepared,
                const InputPackage &package,
                const int requestedThreads,
                ShadowOutput &output)
{
    // Validation intentionally completes before the caller-owned output is
    // reset, so a malformed late face cannot partially mutate observables.
    validate_prepared(prepared);
    output = ShadowOutput{};
    output.requestedThreads = requestedThreads;
    std::vector<std::array<double, kForceComponents>> forceBuffers(
        requestedThreads);
    std::vector<std::array<int, kForceComponents>> collisionBuffers(
        requestedThreads);
    std::vector<GlobalObservable> scalarBuffers(requestedThreads);
    int actualThreads = 0;
    omp_set_dynamic(0);
#pragma omp parallel num_threads(requestedThreads)
    {
        const int thread = omp_get_thread_num();
        Param formulaParam = proof_parameters(package);
        Mesh formulaMesh(formulaParam);
#pragma omp single
        actualThreads = omp_get_num_threads();
#pragma omp for schedule(static)
        for (int face = 0; face < kFaceCount; ++face)
        {
            output.faces[face] =
                evaluate_face(formulaMesh, prepared.faces[face], package);
            accumulate_face(output.faces[face],
                            forceBuffers[thread],
                            collisionBuffers[thread],
                            scalarBuffers[thread]);
        }
    }
    output.actualThreads = actualThreads;
    for (int thread = 0; thread < actualThreads; ++thread)
    {
        output.global.bendingEnergy +=
            scalarBuffers[thread].bendingEnergy;
        output.global.area += scalarBuffers[thread].area;
        output.global.fullVolume += scalarBuffers[thread].fullVolume;
        output.global.legacyVisibleVolume +=
            scalarBuffers[thread].legacyVisibleVolume;
        for (int index = 0; index < kForceComponents; ++index)
        {
            output.vertexForces[index] += forceBuffers[thread][index];
            output.collisionCounts[index] +=
                collisionBuffers[thread][index];
        }
    }
    finalize_global(package.parameters, output.global);
}

NestedForceOracle force_oracle(const InputPackage &package)
{
    NestedForceOracle oracle{};
    for (const SourceKeyedFaceForces &face : package.forces)
    {
        for (int position = 0; position < kSourceCount; ++position)
        {
            const int source = face.sourceIds[position];
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    oracle[source][kind][axis] +=
                        static_cast<long double>(
                            face.forces[position][kind][axis]);
                }
            }
        }
    }
    return oracle;
}

RawForceOracle independent_raw_force_oracle(
    const InputPackage &package,
    const NestedForceOracle &nested)
{
    RawForceOracle oracle;
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                // This explicit destination formula is independent of the
                // candidate scatter helper.
                const int destination =
                    source * 9 + kind * 3 + axis;
                oracle.values[destination] =
                    nested[source][kind][axis];
            }
        }
    }
    for (const SourceKeyedFaceForces &face : package.forces)
    {
        for (int position = 0; position < kSourceCount; ++position)
        {
            const int source = face.sourceIds[position];
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    const int destination =
                        source * 9 + kind * 3 + axis;
                    ++oracle.collisionCounts[destination];
                }
            }
        }
    }
    return oracle;
}

std::array<double, 3> canonical_face_normal(
    const InputPackage &package,
    const int face)
{
    const Vec3 &a = package.coordinates[kOrientedFaces[face][0]];
    const Vec3 &b = package.coordinates[kOrientedFaces[face][1]];
    const Vec3 &c = package.coordinates[kOrientedFaces[face][2]];
    std::array<double, 3> edge1{};
    std::array<double, 3> edge2{};
    for (int axis = 0; axis < 3; ++axis)
    {
        edge1[axis] = b[axis] - a[axis];
        edge2[axis] = c[axis] - a[axis];
    }
    std::array<double, 3> normal = cross3(edge1, edge2);
    const double magnitude = std::sqrt(dot3(normal, normal));
    for (double &component : normal)
    {
        component /= magnitude;
    }
    return normal;
}

bool record_checked_delta(const double left,
                          const double right,
                          double &maximum)
{
    if (!finite_value(left) || !finite_value(right))
    {
        return false;
    }
    const double delta = std::abs(left - right);
    if (!finite_value(delta))
    {
        return false;
    }
    maximum = std::max(maximum, delta);
    return true;
}

bool record_global_delta(const GlobalObservable &left,
                         const GlobalObservable &right,
                         double &maximum)
{
    bool finite = true;
    finite =
        record_checked_delta(
            left.bendingEnergy, right.bendingEnergy, maximum) &&
        finite;
    finite =
        record_checked_delta(left.area, right.area, maximum) &&
        finite;
    finite =
        record_checked_delta(
            left.fullVolume, right.fullVolume, maximum) &&
        finite;
    finite =
        record_checked_delta(
            left.legacyVisibleVolume,
            right.legacyVisibleVolume,
            maximum) &&
        finite;
    finite =
        record_checked_delta(
            left.areaConstraintEnergy,
            right.areaConstraintEnergy,
            maximum) &&
        finite;
    finite =
        record_checked_delta(
            left.volumeConstraintEnergy,
            right.volumeConstraintEnergy,
            maximum) &&
        finite;
    finite =
        record_checked_delta(
            left.totalEnergy, right.totalEnergy, maximum) &&
        finite;
    return finite;
}

bool record_face_delta(const FaceObservable &left,
                       const FaceObservable &right,
                       double &observableMaximum,
                       double &forceMaximum)
{
    bool finite = true;
    finite =
        record_checked_delta(
            left.meanCurvature, right.meanCurvature,
            observableMaximum) &&
        finite;
    finite =
        record_checked_delta(
            left.bendingEnergy, right.bendingEnergy,
            observableMaximum) &&
        finite;
    finite =
        record_checked_delta(left.area, right.area,
                             observableMaximum) &&
        finite;
    finite =
        record_checked_delta(
            left.fullVolume, right.fullVolume,
            observableMaximum) &&
        finite;
    finite =
        record_checked_delta(
            left.legacyVisibleVolume,
            right.legacyVisibleVolume,
            observableMaximum) &&
        finite;
    for (int axis = 0; axis < kAxisCount; ++axis)
    {
        finite =
            record_checked_delta(
                left.normal[axis], right.normal[axis],
                observableMaximum) &&
            finite;
    }
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                finite =
                    record_checked_delta(
                        left.forces[source][kind][axis],
                        right.forces[source][kind][axis],
                        forceMaximum) &&
                    finite;
            }
        }
    }
    return finite;
}

Comparison compare_output(const ShadowOutput &candidate,
                          const ShadowOutput &reference,
                          const InputPackage &package,
                          const RawForceOracle &oracle)
{
    Comparison result;
    for (int face = 0; face < kFaceCount; ++face)
    {
        const FaceObservable &actual = candidate.faces[face];
        const FaceObservable &expected = reference.faces[face];
        result.finite =
            record_face_delta(
                actual, expected,
                result.maxFaceObservableDelta,
                result.maxVertexForceDelta) &&
            result.finite;
        const std::array<double, 3> canonical =
            canonical_face_normal(package, face);
        const double normalDot = dot3(actual.normal, canonical);
        if (!finite_value(normalDot))
        {
            result.finite = false;
        }
        else
        {
            result.minCanonicalNormalDot =
                std::min(result.minCanonicalNormalDot, normalDot);
        }
    }
    for (int destination = 0;
         destination < kForceComponents;
         ++destination)
    {
        result.finite =
            record_checked_delta(
                candidate.vertexForces[destination],
                static_cast<double>(oracle.values[destination]),
                result.maxVertexForceDelta) &&
            result.finite;
        result.collisionCoverage =
            result.collisionCoverage &&
            oracle.collisionCounts[destination] == kFaceCount &&
            candidate.collisionCounts[destination] ==
                oracle.collisionCounts[destination];
    }
    result.finite =
        record_global_delta(
            candidate.global, reference.global,
            result.maxGlobalObservableDelta) &&
        result.finite;
    result.finite =
        result.finite &&
        finite_value(result.maxFaceObservableDelta) &&
        finite_value(result.maxVertexForceDelta) &&
        finite_value(result.maxGlobalObservableDelta) &&
        finite_value(result.minCanonicalNormalDot);
    return result;
}

double output_delta(const ShadowOutput &left,
                    const ShadowOutput &right)
{
    double result = 0.0;
    bool finite =
        record_global_delta(left.global, right.global, result);
    for (int face = 0; face < kFaceCount; ++face)
    {
        finite =
            record_face_delta(
                left.faces[face], right.faces[face],
                result, result) &&
            finite;
    }
    for (int index = 0; index < kForceComponents; ++index)
    {
        finite =
            record_checked_delta(
                left.vertexForces[index],
                right.vertexForces[index],
                result) &&
            finite;
        finite =
            left.collisionCounts[index] ==
                right.collisionCounts[index] &&
            finite;
    }
    finite =
        left.finite && right.finite &&
        left.proofOnly == right.proofOnly &&
        left.productionCallShadow == right.productionCallShadow &&
        left.notProductionRouting == right.notProductionRouting &&
        left.productionRouteEnabled == right.productionRouteEnabled &&
        left.actualProductionForcePathExecuted ==
            right.actualProductionForcePathExecuted &&
        left.productionFaceLoopExecuted ==
            right.productionFaceLoopExecuted &&
        left.productionOneRingsPopulated ==
            right.productionOneRingsPopulated &&
        finite;
    return finite ? result : std::numeric_limits<double>::infinity();
}

bool independent_layout_sentinel_passed()
{
    std::array<std::array<double, kForceComponents>, 3> buffers{};
    std::array<std::array<int, kForceComponents>, 3> collisionBuffers{};
    std::array<long double, kForceComponents> expected{};
    std::array<int, kForceComponents> expectedCollisions{};
    int actualThreads = 0;
    omp_set_dynamic(0);
#pragma omp parallel num_threads(3)
    {
        const int thread = omp_get_thread_num();
#pragma omp single
        actualThreads = omp_get_num_threads();
#pragma omp for schedule(static)
        for (int face = 0; face < kFaceCount; ++face)
        {
            for (int source = 0; source < kSourceCount; ++source)
            {
                for (int kind = 0; kind < kForceKindCount; ++kind)
                {
                    for (int axis = 0; axis < kAxisCount; ++axis)
                    {
                        const double sentinel =
                            1000000.0 * (face + 1) +
                            10000.0 * (source + 1) +
                            100.0 * (kind + 1) + axis + 1.0;
                        const int candidateDestination =
                            force_index(source, kind, axis);
                        buffers[thread][candidateDestination] +=
                            sentinel;
                        ++collisionBuffers[thread][
                            candidateDestination];
                    }
                }
            }
        }
    }
    for (int face = 0; face < kFaceCount; ++face)
    {
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    const int independentDestination =
                        source * 9 + kind * 3 + axis;
                    expected[independentDestination] +=
                        static_cast<long double>(
                            1000000.0 * (face + 1) +
                            10000.0 * (source + 1) +
                            100.0 * (kind + 1) + axis + 1.0);
                    ++expectedCollisions[independentDestination];
                }
            }
        }
    }
    if (actualThreads != 3)
    {
        return false;
    }
    for (int destination = 0;
         destination < kForceComponents;
         ++destination)
    {
        double reduced = 0.0;
        int collisions = 0;
        for (int thread = 0; thread < actualThreads; ++thread)
        {
            reduced += buffers[thread][destination];
            collisions += collisionBuffers[thread][destination];
        }
        if (reduced != static_cast<double>(expected[destination]) ||
            collisions != expectedCollisions[destination] ||
            expectedCollisions[destination] != kFaceCount)
        {
            return false;
        }
    }
    return true;
}

bool shadow_outputs_exactly_equal(const ShadowOutput &left,
                                  const ShadowOutput &right)
{
    for (int face = 0; face < kFaceCount; ++face)
    {
        const FaceObservable &leftFace = left.faces[face];
        const FaceObservable &rightFace = right.faces[face];
        if (leftFace.meanCurvature != rightFace.meanCurvature ||
            leftFace.bendingEnergy != rightFace.bendingEnergy ||
            leftFace.area != rightFace.area ||
            leftFace.fullVolume != rightFace.fullVolume ||
            leftFace.legacyVisibleVolume !=
                rightFace.legacyVisibleVolume)
        {
            return false;
        }
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            if (leftFace.normal[axis] != rightFace.normal[axis])
            {
                return false;
            }
        }
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    if (leftFace.forces[source][kind][axis] !=
                        rightFace.forces[source][kind][axis])
                    {
                        return false;
                    }
                }
            }
        }
    }
    for (int destination = 0;
         destination < kForceComponents;
         ++destination)
    {
        if (left.vertexForces[destination] !=
                right.vertexForces[destination] ||
            left.collisionCounts[destination] !=
                right.collisionCounts[destination])
        {
            return false;
        }
    }
    return
        left.global.bendingEnergy == right.global.bendingEnergy &&
        left.global.area == right.global.area &&
        left.global.fullVolume == right.global.fullVolume &&
        left.global.legacyVisibleVolume ==
            right.global.legacyVisibleVolume &&
        left.global.areaConstraintEnergy ==
            right.global.areaConstraintEnergy &&
        left.global.volumeConstraintEnergy ==
            right.global.volumeConstraintEnergy &&
        left.global.totalEnergy == right.global.totalEnergy &&
        left.requestedThreads == right.requestedThreads &&
        left.actualThreads == right.actualThreads &&
        left.finite == right.finite &&
        left.proofOnly == right.proofOnly &&
        left.productionCallShadow == right.productionCallShadow &&
        left.notProductionRouting == right.notProductionRouting &&
        left.productionRouteEnabled == right.productionRouteEnabled &&
        left.actualProductionForcePathExecuted ==
            right.actualProductionForcePathExecuted &&
        left.productionFaceLoopExecuted ==
            right.productionFaceLoopExecuted &&
        left.productionOneRingsPopulated ==
            right.productionOneRingsPopulated;
}

ShadowOutput fully_seeded_shadow_output()
{
    ShadowOutput output;
    for (int face = 0; face < kFaceCount; ++face)
    {
        FaceObservable &observable = output.faces[face];
        const double base = 1000.0 * (face + 1);
        observable.meanCurvature = base + 1.0;
        observable.bendingEnergy = base + 2.0;
        observable.area = base + 3.0;
        observable.fullVolume = base + 4.0;
        observable.legacyVisibleVolume = base + 5.0;
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            observable.normal[axis] = base + 10.0 + axis;
        }
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    observable.forces[source][kind][axis] =
                        base + 100.0 + source * 9 +
                        kind * 3 + axis;
                }
            }
        }
    }
    for (int destination = 0;
         destination < kForceComponents;
         ++destination)
    {
        output.vertexForces[destination] =
            20000.0 + destination;
        output.collisionCounts[destination] =
            30000 + destination;
    }
    output.global.bendingEnergy = 40001.0;
    output.global.area = 40002.0;
    output.global.fullVolume = 40003.0;
    output.global.legacyVisibleVolume = 40004.0;
    output.global.areaConstraintEnergy = 40005.0;
    output.global.volumeConstraintEnergy = 40006.0;
    output.global.totalEnergy = 40007.0;
    output.requestedThreads = 41;
    output.actualThreads = 43;
    output.finite = false;
    output.proofOnly = false;
    output.productionCallShadow = false;
    output.notProductionRouting = false;
    output.productionRouteEnabled = true;
    output.actualProductionForcePathExecuted = true;
    output.productionFaceLoopExecuted = true;
    output.productionOneRingsPopulated = true;
    return output;
}

bool malformed_late_face_is_atomic(
    const PreparedSourceKeyedKernelCall &prepared,
    const InputPackage &package)
{
    PreparedSourceKeyedKernelCall malformed = prepared;
    malformed.faces.back()
        .samples.back()
        .rows[kDerivativeRowCount - 1]
        .coefficients.pop_back();
    ShadowOutput output = fully_seeded_shadow_output();
    const ShadowOutput before = output;
    try
    {
        run_openmp(malformed, package, 3, output);
    }
    catch (const std::invalid_argument &)
    {
        return shadow_outputs_exactly_equal(output, before);
    }
    return false;
}

bool nonfinite_output_negative_regression_passed(
    const ShadowOutput &serial,
    const ShadowOutput &reference,
    const InputPackage &package,
    const RawForceOracle &oracle)
{
    const double nonfinite =
        std::numeric_limits<double>::quiet_NaN();
    const auto rejected =
        [&](const ShadowOutput &candidate)
        {
            const Comparison comparison =
                compare_output(
                    candidate, reference, package, oracle);
            return !comparison.finite &&
                   !finite_value(
                       output_delta(candidate, serial));
        };
    for (int face = 0; face < kFaceCount; ++face)
    {
        ShadowOutput candidate = serial;
        candidate.faces[face].meanCurvature = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.faces[face].bendingEnergy = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.faces[face].area = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.faces[face].fullVolume = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.faces[face].legacyVisibleVolume = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            candidate = serial;
            candidate.faces[face].normal[axis] = nonfinite;
            if (!rejected(candidate))
            {
                return false;
            }
        }
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    candidate = serial;
                    candidate.faces[face]
                        .forces[source][kind][axis] = nonfinite;
                    if (!rejected(candidate))
                    {
                        return false;
                    }
                }
            }
        }
    }
    for (int destination = 0;
         destination < kForceComponents;
         ++destination)
    {
        ShadowOutput candidate = serial;
        candidate.vertexForces[destination] = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
    }
    {
        ShadowOutput candidate = serial;
        candidate.global.bendingEnergy = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.global.area = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.global.fullVolume = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.global.legacyVisibleVolume = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.global.areaConstraintEnergy = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.global.volumeConstraintEnergy = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
        candidate = serial;
        candidate.global.totalEnergy = nonfinite;
        if (!rejected(candidate))
        {
            return false;
        }
    }
    return true;
}

bool collision_count_negative_regression_passed(
    const ShadowOutput &serial,
    const ShadowOutput &reference,
    const InputPackage &package,
    const RawForceOracle &oracle)
{
    for (int destination = 0;
         destination < kForceComponents;
         ++destination)
    {
        ShadowOutput candidate = serial;
        ++candidate.collisionCounts[destination];
        const Comparison comparison =
            compare_output(
                candidate, reference, package, oracle);
        if (comparison.collisionCoverage ||
            finite_value(output_delta(candidate, serial)))
        {
            return false;
        }
    }
    return true;
}

bool flipped_normal_oracle_rejected(
    const ShadowOutput &serial,
    const InputPackage &package,
    const RawForceOracle &oracle)
{
    ShadowOutput flipped = serial;
    for (double &component : flipped.faces[0].normal)
    {
        component = -component;
    }
    const Comparison comparison =
        compare_output(flipped, serial, package, oracle);
    return comparison.minCanonicalNormalDot < 0.0;
}

void print_thread_summary(const ThreadSummary &summary)
{
    std::cout << "{\"requested_threads\":"
              << summary.requestedThreads << ",\"actual_threads\":[";
    for (int repeat = 0; repeat < kRepeats; ++repeat)
    {
        if (repeat != 0)
        {
            std::cout << ',';
        }
        std::cout << summary.actualThreads[repeat];
    }
    std::cout << "],\"repeat_count\":" << kRepeats;
    std::cout << ",\"max_abs_oracle_difference\":"
              << summary.maxOracleDelta;
    std::cout << ",\"max_abs_serial_difference\":"
              << summary.maxSerialDelta;
    std::cout << ",\"max_abs_repeat_difference\":"
              << summary.maxRepeatDelta;
    std::cout << ",\"min_canonical_normal_dot\":"
              << summary.minCanonicalNormalDot;
    std::cout << ",\"finite\":"
              << (summary.finite ? "true" : "false");
    std::cout << ",\"collision_coverage_passed\":"
              << (summary.collisionCoverage ? "true" : "false");
    std::cout << ",\"passed\":"
              << (summary.passed ? "true" : "false") << '}';
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: shadow vertices.csv faces.csv package.txt\n";
        return 2;
    }

    InputPackage package;
    if (!read_package(argv[3], package))
    {
        std::cerr << "failed to read face-loop observable package\n";
        return 3;
    }

    Param topologyParam;
    topologyParam.VERBOSE_MODE = false;
    topologyParam.boundaryCondition = BoundaryType::Fixed;
    topologyParam.subDivideTimes = 2;
    Mesh topologyMesh(topologyParam);
    std::ostringstream ignoredSetupOutput;
    std::streambuf *originalCout = std::cout.rdbuf(
        ignoredSetupOutput.rdbuf());
    topologyMesh.setup_from_vertices_faces(
        read_data_from_csv<double>(argv[1]),
        read_data_from_csv<int>(argv[2]));
    std::cout.rdbuf(originalCout);

    const Valence4TopologySourceMappingResult guardedMapping =
        build_guarded_valence4_topology_source_mapping(topologyMesh);
    const std::vector<SourceMappingView> mappings =
        mapping_views(topologyMesh, guardedMapping);
    const PreparedSourceKeyedKernelCall prepared =
        prepare_source_keyed_kernel_call(
            SourceKeyedKernelCallInput{
                kSourceCount, mappings, package.rows, package.forces});

    const bool oneRingsEmptyBefore = std::all_of(
        topologyMesh.faces.begin(),
        topologyMesh.faces.end(),
        [](const Face &face) { return face.oneRingVertices.empty(); });
    ShadowOutput oracleOutput;
    oracleOutput.global = package.expectedGlobal;
    oracleOutput.faces = package.expectedFaces;
    for (int face = 0; face < kFaceCount; ++face)
    {
        for (int position = 0; position < kSourceCount; ++position)
        {
            const int source =
                package.forces[face].sourceIds[position];
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    oracleOutput.faces[face]
                        .forces[source][kind][axis] =
                        package.forces[face]
                            .forces[position][kind][axis];
                }
            }
        }
    }
    const NestedForceOracle nestedOracle = force_oracle(package);
    const RawForceOracle rawOracle =
        independent_raw_force_oracle(package, nestedOracle);
    for (int destination = 0;
         destination < kForceComponents;
         ++destination)
    {
        oracleOutput.vertexForces[destination] =
            static_cast<double>(rawOracle.values[destination]);
        oracleOutput.collisionCounts[destination] =
            rawOracle.collisionCounts[destination];
    }

    ShadowOutput serial;
    run_serial(prepared, package, serial);
    const Comparison serialComparison =
        compare_output(serial, oracleOutput, package, rawOracle);

    const std::array<int, 5> requestedThreads{{1, 2, 3, 4, 8}};
    std::array<ThreadSummary, requestedThreads.size()> summaries{};
    bool openMpPassed = true;
    for (std::size_t run = 0; run < requestedThreads.size(); ++run)
    {
        ThreadSummary &summary = summaries[run];
        summary.requestedThreads = requestedThreads[run];
        ShadowOutput first;
        bool haveFirst = false;
        for (int repeat = 0; repeat < kRepeats; ++repeat)
        {
            ShadowOutput candidate;
            run_openmp(prepared, package, requestedThreads[run],
                       candidate);
            summary.actualThreads[repeat] = candidate.actualThreads;
            const Comparison comparison =
                compare_output(
                    candidate, oracleOutput, package, rawOracle);
            summary.maxOracleDelta = std::max({
                summary.maxOracleDelta,
                comparison.maxFaceObservableDelta,
                comparison.maxVertexForceDelta,
                comparison.maxGlobalObservableDelta,
            });
            summary.maxSerialDelta =
                std::max(summary.maxSerialDelta,
                         output_delta(candidate, serial));
            summary.minCanonicalNormalDot =
                std::min(summary.minCanonicalNormalDot,
                         comparison.minCanonicalNormalDot);
            summary.finite = summary.finite && comparison.finite;
            summary.collisionCoverage =
                summary.collisionCoverage &&
                comparison.collisionCoverage;
            summary.passed =
                summary.passed &&
                candidate.actualThreads == requestedThreads[run];
            if (!haveFirst)
            {
                first = candidate;
                haveFirst = true;
            }
            else
            {
                summary.maxRepeatDelta =
                    std::max(summary.maxRepeatDelta,
                             output_delta(candidate, first));
            }
        }
        summary.passed =
            summary.passed && summary.finite &&
            summary.collisionCoverage &&
            summary.minCanonicalNormalDot > 0.0 &&
            summary.maxOracleDelta <= kTolerance &&
            summary.maxSerialDelta <= kTolerance &&
            summary.maxRepeatDelta <= kTolerance;
        openMpPassed = openMpPassed && summary.passed;
    }

    const bool oneRingsEmptyAfter = std::all_of(
        topologyMesh.faces.begin(),
        topologyMesh.faces.end(),
        [](const Face &face) { return face.oneRingVertices.empty(); });
    const bool layoutOraclePassed =
        independent_layout_sentinel_passed();
    const bool lateMalformedAtomic =
        malformed_late_face_is_atomic(prepared, package);
    const bool nonfiniteNegativeRegression =
        nonfinite_output_negative_regression_passed(
            serial, oracleOutput, package, rawOracle);
    const bool collisionNegativeRegression =
        collision_count_negative_regression_passed(
            serial, oracleOutput, package, rawOracle);
    const bool flippedNormalRejected =
        flipped_normal_oracle_rejected(
            serial, package, rawOracle);
    const bool serialPassed =
        serialComparison.finite &&
        serialComparison.collisionCoverage &&
        serialComparison.minCanonicalNormalDot > 0.0 &&
        serialComparison.maxFaceObservableDelta <= kTolerance &&
        serialComparison.maxVertexForceDelta <= kTolerance &&
        serialComparison.maxGlobalObservableDelta <= kTolerance;
    const bool passed =
        serialPassed && openMpPassed && layoutOraclePassed &&
        lateMalformedAtomic && nonfiniteNegativeRegression &&
        collisionNegativeRegression && flippedNormalRejected &&
        oneRingsEmptyBefore && oneRingsEmptyAfter;

    std::cout << std::setprecision(17);
    std::cout << '{';
    std::cout << "\"kind\":\"proof_only_valence4_face_loop_observable_shadow\",";
    std::cout << "\"proof_only\":true,";
    std::cout << "\"production_call_shadow\":true,";
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"production_route_enabled\":false,";
    std::cout << "\"actual_production_force_path_executed\":false,";
    std::cout << "\"production_face_loop_executed\":false,";
    std::cout << "\"actual_openmp_runtime\":true,";
    std::cout << "\"schedule\":\"static\",";
    std::cout << "\"reduction_order\":\"ascending thread index\",";
    std::cout << "\"fixture\":\"approved_closed_valence4_octahedron\",";
    std::cout << "\"guarded_topology_source_mapping_consumed\":true,";
    std::cout << "\"source_keyed_kernel_helper_consumed\":true,";
    std::cout << "\"scientific_force_algebra\":\"Mesh::element_energy_force_regular\",";
    std::cout << "\"face_count\":8,\"source_count\":6,";
    std::cout << "\"force_buffer_shape\":\"6 sources x 9 components\",";
    std::cout << "\"total_force_components\":54,";
    std::cout << "\"expected_collision_count_per_component\":8,";
    std::cout << "\"all_collision_counts_exactly_eight\":"
              << (serialComparison.collisionCoverage ? "true" : "false")
              << ',';
    std::cout << "\"independent_long_double_nested_force_oracle\":true,";
    std::cout << "\"independent_raw_destination_formula\":"
                 "\"source * 9 + kind * 3 + axis\",";
    std::cout << "\"candidate_slots_compared_raw\":true,";
    std::cout << "\"candidate_collision_counts_compared_raw\":true,";
    std::cout << "\"independent_exact_layout_sentinel_passed\":"
              << (layoutOraclePassed ? "true" : "false") << ',';
    std::cout << "\"serial_oracle_parity_passed\":"
              << (serialPassed ? "true" : "false") << ',';
    std::cout << "\"serial_max_face_observable_delta\":"
              << serialComparison.maxFaceObservableDelta << ',';
    std::cout << "\"serial_max_vertex_force_delta\":"
              << serialComparison.maxVertexForceDelta << ',';
    std::cout << "\"serial_max_global_observable_delta\":"
              << serialComparison.maxGlobalObservableDelta << ',';
    std::cout << "\"serial_min_canonical_normal_dot\":"
              << serialComparison.minCanonicalNormalDot << ',';
    std::cout << "\"observables\":[\"bending_energy\",\"mean_curvature\","
                 "\"normals\",\"fBend\",\"fArea\",\"fVolume\","
                 "\"face_area\",\"global_area\",\"face_legacy_volume\","
                 "\"global_legacy_volume\",\"production_shaped_vertex_forces\"],";
    std::cout << "\"global_observables\":{";
    std::cout << "\"bending_energy\":" << serial.global.bendingEnergy << ',';
    std::cout << "\"area\":" << serial.global.area << ',';
    std::cout << "\"full_signed_volume\":" << serial.global.fullVolume << ',';
    std::cout << "\"legacy_visible_volume\":"
              << serial.global.legacyVisibleVolume << ',';
    std::cout << "\"area_constraint_energy\":"
              << serial.global.areaConstraintEnergy << ',';
    std::cout << "\"volume_constraint_energy\":"
              << serial.global.volumeConstraintEnergy << ',';
    std::cout << "\"total_energy\":" << serial.global.totalEnergy << "},";
    std::cout << "\"thread_runs\":[";
    for (std::size_t run = 0; run < summaries.size(); ++run)
    {
        if (run != 0)
        {
            std::cout << ',';
        }
        print_thread_summary(summaries[run]);
    }
    std::cout << "],\"actual_openmp_serial_parity_passed\":"
              << (openMpPassed ? "true" : "false") << ',';
    std::cout << "\"source_coverage_binding_passed\":true,";
    std::cout << "\"late_malformed_face_atomic_rejection\":"
              << (lateMalformedAtomic ? "true" : "false") << ',';
    std::cout << "\"late_malformed_complete_shadow_state_atomic\":"
              << (lateMalformedAtomic ? "true" : "false") << ',';
    std::cout << "\"nonfinite_output_negative_regression_passed\":"
              << (nonfiniteNegativeRegression ? "true" : "false")
              << ',';
    std::cout << "\"all_face_force_and_observable_fields_finite_checked\":true,";
    std::cout << "\"all_raw_force_slots_finite_checked\":true,";
    std::cout << "\"all_global_fields_finite_checked\":true,";
    std::cout << "\"collision_count_negative_regression_passed\":"
              << (collisionNegativeRegression ? "true" : "false")
              << ',';
    std::cout << "\"flipped_normal_orientation_rejected\":"
              << (flippedNormalRejected ? "true" : "false") << ',';
    std::cout << "\"production_one_rings_populated\":false,";
    std::cout << "\"production_one_rings_empty_before\":"
              << (oneRingsEmptyBefore ? "true" : "false") << ',';
    std::cout << "\"production_one_rings_empty_after\":"
              << (oneRingsEmptyAfter ? "true" : "false") << ',';
    std::cout << "\"absolute_tolerance\":" << kTolerance << ',';
    std::cout << "\"residual_boundary\":\"production valence-4 face-loop "
                 "routing and one-ring population remain separately "
                 "reviewed and unapproved\",";
    std::cout << "\"passed\":" << (passed ? "true" : "false");
    std::cout << "}\n";
    return passed ? 0 : 1;
}
