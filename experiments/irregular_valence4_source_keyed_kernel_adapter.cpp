#include "irregular_valence4_source_keyed_kernel_adapter.hpp"

#include "energy_force/Valence4_face_loop_route_preflight.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/Valence4_topology_source_mapping.hpp"
#include "Parameters.hpp"

#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
using namespace valence4_source_keyed_proof;
using namespace slimed::valence4_route_preflight;

constexpr int kFaceCount = 8;
constexpr int kSourceCount = 6;
constexpr int kSampleCount = 3;
constexpr double kTolerance = 1.0e-12;

using IndependentOracle =
    std::array<std::array<std::array<long double, kAxisCount>,
                          kForceKindCount>,
               kSourceCount>;

struct InputPackage
{
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

    FormulaParameters parameters;
    std::vector<Vec3> coordinates;
    std::vector<SourceKeyedFaceRows> rows;
    std::vector<SourceKeyedFaceForces> forces;
};

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
    std::string parameterTag;
    if (!(input >> parameterTag) || parameterTag != "PARAMETERS" ||
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
    const std::array<double, 8> parameterValues = {
        package.parameters.kCurv,
        package.parameters.spontCurv,
        package.parameters.uSurf,
        package.parameters.area0,
        package.parameters.uVol,
        package.parameters.vol0,
        package.parameters.area,
        package.parameters.volume};
    if (!std::all_of(parameterValues.begin(),
                     parameterValues.end(),
                     [](const double value) {
                         return std::isfinite(value);
                     }))
    {
        return false;
    }

    std::string coordinateTag;
    int coordinateCount = 0;
    if (!(input >> coordinateTag >> coordinateCount) ||
        coordinateTag != "COORDINATES" ||
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
                !std::isfinite(package.coordinates[source][axis]))
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
                          target.coefficients[source]))
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
                          faceForces.forces[source][kind][axis]))
                    {
                        return false;
                    }
                }
            }
        }
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

IndependentOracle independent_scatter_oracle(
    const InputPackage &package)
{
    IndependentOracle oracle{};
    for (int face = 0; face < kFaceCount; ++face)
    {
        std::array<bool, kSourceCount> seen{};
        const SourceKeyedFaceForces &faceForces = package.forces[face];
        if (faceForces.sourceIds.size() != faceForces.forces.size())
        {
            throw std::invalid_argument(
                "independent oracle rejected force cardinality drift");
        }
        for (std::size_t position = 0;
             position < faceForces.sourceIds.size();
             ++position)
        {
            const int sourceId = faceForces.sourceIds[position];
            if (sourceId < 0 || sourceId >= kSourceCount ||
                seen[sourceId])
            {
                throw std::invalid_argument(
                    "independent oracle rejected invalid source-key binding");
            }
            seen[sourceId] = true;
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    oracle[sourceId][kind][axis] +=
                        static_cast<long double>(
                            faceForces.forces[position][kind][axis]);
                }
            }
        }
        if (!std::all_of(seen.begin(), seen.end(), [](bool value) {
                return value;
            }))
        {
            throw std::invalid_argument(
                "independent oracle rejected incomplete source coverage");
        }
    }
    return oracle;
}

double compare_with_independent_oracle(
    const std::vector<SourceForceKinds> &candidate,
    const IndependentOracle &oracle)
{
    if (candidate.size() != kSourceCount)
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                maximum = std::max(
                    maximum,
                    std::abs(candidate[source][kind][axis] -
                             static_cast<double>(
                                 oracle[source][kind][axis])));
            }
        }
    }
    return maximum;
}

double compare_adapted_inputs(
    const PreparedSourceKeyedKernelCall &candidate,
    const PreparedSourceKeyedKernelCall &reference)
{
    if (candidate.sourceCount != reference.sourceCount ||
        candidate.faces.size() != reference.faces.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (std::size_t face = 0; face < reference.faces.size(); ++face)
    {
        const PreparedSourceKeyedFace &actual = candidate.faces[face];
        const PreparedSourceKeyedFace &expected = reference.faces[face];
        if (actual.mapping.faceIndex != expected.mapping.faceIndex ||
            actual.mapping.orientedFaceVertices !=
                expected.mapping.orientedFaceVertices ||
            actual.mapping.originalSourceIds !=
                expected.mapping.originalSourceIds ||
            actual.samples.size() != expected.samples.size() ||
            actual.forces.size() != expected.forces.size())
        {
            return std::numeric_limits<double>::infinity();
        }
        for (std::size_t sample = 0; sample < expected.samples.size();
             ++sample)
        {
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                const SourceKeyedRow &actualRow =
                    actual.samples[sample].rows[row];
                const SourceKeyedRow &expectedRow =
                    expected.samples[sample].rows[row];
                if (actualRow.sourceIds != expectedRow.sourceIds ||
                    actualRow.coefficients.size() !=
                        expectedRow.coefficients.size())
                {
                    return std::numeric_limits<double>::infinity();
                }
                for (std::size_t source = 0;
                     source < expectedRow.coefficients.size();
                     ++source)
                {
                    maximum = std::max(
                        maximum,
                        std::abs(actualRow.coefficients[source] -
                                 expectedRow.coefficients[source]));
                }
            }
        }
        for (std::size_t source = 0; source < expected.forces.size();
             ++source)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    maximum = std::max(
                        maximum,
                        std::abs(actual.forces[source][kind][axis] -
                                 expected.forces[source][kind][axis]));
                }
            }
        }
    }
    return maximum;
}

double compare_scattered(const std::vector<SourceForceKinds> &candidate,
                         const std::vector<SourceForceKinds> &reference)
{
    if (candidate.size() != reference.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (std::size_t source = 0; source < reference.size(); ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                maximum = std::max(
                    maximum,
                    std::abs(candidate[source][kind][axis] -
                             reference[source][kind][axis]));
            }
        }
    }
    return maximum;
}

InputPackage permuted_bindings(const InputPackage &package)
{
    InputPackage permuted = package;
    for (SourceKeyedFaceRows &faceRows : permuted.rows)
    {
        for (SourceKeyedSampleRows &sample : faceRows.samples)
        {
            for (SourceKeyedRow &row : sample.rows)
            {
                std::reverse(row.sourceIds.begin(), row.sourceIds.end());
                std::reverse(row.coefficients.begin(),
                             row.coefficients.end());
            }
        }
    }
    for (SourceKeyedFaceForces &faceForces : permuted.forces)
    {
        std::reverse(faceForces.sourceIds.begin(),
                     faceForces.sourceIds.end());
        std::reverse(faceForces.forces.begin(), faceForces.forces.end());
    }
    return permuted;
}

InputPackage split_duplicate_rows(const InputPackage &package)
{
    InputPackage duplicated = package;
    for (SourceKeyedFaceRows &faceRows : duplicated.rows)
    {
        for (SourceKeyedSampleRows &sample : faceRows.samples)
        {
            for (SourceKeyedRow &row : sample.rows)
            {
                const int sourceId = row.sourceIds.front();
                const double half = std::ldexp(
                    row.coefficients.front(), -1);
                row.coefficients.front() = half;
                row.sourceIds.push_back(sourceId);
                row.coefficients.push_back(half);
                std::reverse(row.sourceIds.begin(), row.sourceIds.end());
                std::reverse(row.coefficients.begin(),
                             row.coefficients.end());
            }
        }
    }
    return duplicated;
}

template <typename Mutation>
bool rejected(Mutation mutation,
              const std::vector<SourceMappingView> &baseMappings,
              const InputPackage &basePackage)
{
    std::vector<SourceMappingView> mappings = baseMappings;
    InputPackage package = basePackage;
    mutation(mappings, package);
    try
    {
        (void)prepare_source_keyed_kernel_call(
            SourceKeyedKernelCallInput{
                kSourceCount, mappings, package.rows, package.forces});
    }
    catch (const std::invalid_argument &)
    {
        return true;
    }
    return false;
}

struct ScientificForceAlgebraProof
{
    bool executed = false;
    bool finite = true;
    bool nonzero = false;
    double maxForceDifference = 0.0;
    std::array<double, kForceKindCount> maxAbsForce{{0.0, 0.0, 0.0}};
    std::vector<Valence4FaceScientificObservables> faceObservables;
};

ScientificForceAlgebraProof invoke_scientific_force_algebra(
    const PreparedSourceKeyedKernelCall &prepared,
    const InputPackage &package)
{
    ScientificForceAlgebraProof result;
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
    Mesh formulaMesh(param);

    for (const PreparedSourceKeyedFace &preparedFace : prepared.faces)
    {
        const std::vector<int> &sourceIds =
            preparedFace.mapping.originalSourceIds;
        const int sourceCount = static_cast<int>(sourceIds.size());
        if (sourceCount <= 0 ||
            preparedFace.samples.size() != kSampleCount ||
            preparedFace.forces.size() != sourceIds.size())
        {
            throw std::invalid_argument(
                "scientific force proof received invalid prepared face shape");
        }

        std::vector<Matrix> coordinates(
            sourceCount, Matrix(kAxisCount, 1, true));
        for (int sourcePosition = 0;
             sourcePosition < sourceCount;
             ++sourcePosition)
        {
            const int sourceId = sourceIds[sourcePosition];
            if (sourceId < 0 ||
                sourceId >= static_cast<int>(package.coordinates.size()))
            {
                throw std::invalid_argument(
                    "scientific force proof source id is out of range");
            }
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                coordinates[sourcePosition].set(
                    axis, 0, package.coordinates[sourceId][axis]);
            }
        }

        std::vector<Matrix> shapeFunctions;
        shapeFunctions.reserve(preparedFace.samples.size());
        for (const SourceKeyedSampleRows &sample : preparedFace.samples)
        {
            Matrix rows(kDerivativeRowCount, sourceCount, true);
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                if (sample.rows[row].sourceIds != sourceIds ||
                    sample.rows[row].coefficients.size() != sourceIds.size())
                {
                    throw std::invalid_argument(
                        "scientific force proof row/source mapping drifted");
                }
                for (int sourcePosition = 0;
                     sourcePosition < sourceCount;
                     ++sourcePosition)
                {
                    rows.set(row,
                             sourcePosition,
                             sample.rows[row]
                                 .coefficients[sourcePosition]);
                }
            }
            shapeFunctions.push_back(std::move(rows));
        }

        Face face;
        face.index = preparedFace.mapping.faceIndex;
        face.spontCurvature = package.parameters.spontCurv;
        Matrix normal = mat_calloc(kAxisCount, 1);
        Matrix bending = mat_calloc(sourceCount, kAxisCount);
        Matrix area = mat_calloc(sourceCount, kAxisCount);
        Matrix volume = mat_calloc(sourceCount, kAxisCount);
        double meanCurvature = 0.0;
        double bendingEnergy = 0.0;
        formulaMesh.element_energy_force_regular(
            coordinates,
            face,
            face.spontCurvature,
            meanCurvature,
            normal,
            bendingEnergy,
            bending,
            area,
            volume,
            false,
            &shapeFunctions);
        result.executed = true;
        result.finite =
            result.finite && std::isfinite(meanCurvature) &&
            std::isfinite(bendingEnergy);
        Valence4FaceScientificObservables observables;
        observables.faceIndex = preparedFace.mapping.faceIndex;
        observables.meanCurvature = meanCurvature;
        observables.bendingEnergy = bendingEnergy;
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            result.finite =
                result.finite && std::isfinite(normal.get(axis, 0));
            observables.normal[axis] = normal.get(axis, 0);
        }
        result.faceObservables.push_back(observables);

        const std::array<const Matrix *, kForceKindCount> actual = {
            &bending, &area, &volume};
        for (int sourcePosition = 0;
             sourcePosition < sourceCount;
             ++sourcePosition)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    const double value =
                        actual[kind]->get(sourcePosition, axis);
                    const double expected =
                        preparedFace.forces[sourcePosition][kind][axis];
                    result.finite =
                        result.finite && std::isfinite(value);
                    result.maxAbsForce[kind] =
                        std::max(result.maxAbsForce[kind],
                                 std::abs(value));
                    result.maxForceDifference =
                        std::max(result.maxForceDifference,
                                 std::abs(value - expected));
                }
            }
        }
    }
    result.nonzero = std::all_of(
        result.maxAbsForce.begin(),
        result.maxAbsForce.end(),
        [](const double value) { return value > 1.0e-10; });
    return result;
}

struct MeshScientificState
{
    std::vector<Face> faces;
    std::vector<Vertex> vertices;
};

void seed_energy(Energy &energy, const double base)
{
    energy.energyCurvature = base + 1.0;
    energy.energyArea = base + 2.0;
    energy.energyVolume = base + 3.0;
    energy.energyThickness = base + 4.0;
    energy.energyTilt = base + 5.0;
    energy.energyRegularization = base + 6.0;
    energy.energyHarmonicBond = base + 7.0;
    energy.energyGagScaffolding = base + 8.0;
    energy.energyIdealizedProteinLattice = base + 9.0;
    energy.energyTotal = base + 10.0;
}

void seed_force(Force &force, const double base)
{
    const std::array<Matrix *, 8> matrices{{
        &force.forceCurvature,
        &force.forceArea,
        &force.forceVolume,
        &force.forceThickness,
        &force.forceTilt,
        &force.forceRegularization,
        &force.forceHarmonicBond,
        &force.forceTotal}};
    for (std::size_t kind = 0; kind < matrices.size(); ++kind)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            matrices[kind]->set(
                axis, 0, base + 10.0 * kind + axis);
        }
    }
}

void seed_mesh_scientific_state(Mesh &mesh)
{
    for (Face &face : mesh.faces)
    {
        face.meanCurvature = 100.0 + face.index;
        face.normVector = mat_calloc(kAxisCount, 1);
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            face.normVector.set(
                axis, 0, 200.0 + 10.0 * face.index + axis);
        }
        face.elementArea = 300.0 + face.index;
        face.elementVolume = 400.0 + face.index;
        seed_energy(face.energy, 500.0 + 20.0 * face.index);
        seed_energy(face.energyPrev, 700.0 + 20.0 * face.index);
    }
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.coordPrev = mat_calloc(kAxisCount, 1);
        vertex.coordRef = mat_calloc(kAxisCount, 1);
        vertex.normVector = mat_calloc(kAxisCount, 1);
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            vertex.coordPrev.set(
                axis, 0, 900.0 + 10.0 * vertex.index + axis);
            vertex.coordRef.set(
                axis, 0, 1000.0 + 10.0 * vertex.index + axis);
            vertex.normVector.set(
                axis, 0, 1100.0 + 10.0 * vertex.index + axis);
        }
        seed_force(vertex.force, 1200.0 + 100.0 * vertex.index);
        seed_force(vertex.forcePrev, 2000.0 + 100.0 * vertex.index);
    }
}

bool matrix_matches(const Matrix &candidate, const Matrix &reference)
{
    if (candidate.mat == nullptr || reference.mat == nullptr)
    {
        return candidate.mat == reference.mat;
    }
    if (candidate.nrow() != reference.nrow() ||
        candidate.ncol() != reference.ncol())
    {
        return false;
    }
    for (int row = 0; row < candidate.nrow(); ++row)
    {
        for (int column = 0; column < candidate.ncol(); ++column)
        {
            if (candidate.get(row, column) !=
                reference.get(row, column))
            {
                return false;
            }
        }
    }
    return true;
}

bool energy_matches(const Energy &candidate, const Energy &reference)
{
    return candidate.energyCurvature == reference.energyCurvature &&
           candidate.energyArea == reference.energyArea &&
           candidate.energyVolume == reference.energyVolume &&
           candidate.energyThickness == reference.energyThickness &&
           candidate.energyTilt == reference.energyTilt &&
           candidate.energyRegularization ==
               reference.energyRegularization &&
           candidate.energyHarmonicBond ==
               reference.energyHarmonicBond &&
           candidate.energyGagScaffolding ==
               reference.energyGagScaffolding &&
           candidate.energyIdealizedProteinLattice ==
               reference.energyIdealizedProteinLattice &&
           candidate.energyTotal == reference.energyTotal;
}

bool force_matches(const Force &candidate, const Force &reference)
{
    const std::array<const Matrix *, 8> candidateMatrices{{
        &candidate.forceCurvature,
        &candidate.forceArea,
        &candidate.forceVolume,
        &candidate.forceThickness,
        &candidate.forceTilt,
        &candidate.forceRegularization,
        &candidate.forceHarmonicBond,
        &candidate.forceTotal}};
    const std::array<const Matrix *, 8> referenceMatrices{{
        &reference.forceCurvature,
        &reference.forceArea,
        &reference.forceVolume,
        &reference.forceThickness,
        &reference.forceTilt,
        &reference.forceRegularization,
        &reference.forceHarmonicBond,
        &reference.forceTotal}};
    for (std::size_t index = 0;
         index < candidateMatrices.size();
         ++index)
    {
        if (!matrix_matches(*candidateMatrices[index],
                            *referenceMatrices[index]))
        {
            return false;
        }
    }
    return true;
}

bool face_matches(const Face &candidate, const Face &reference)
{
    return candidate.index == reference.index &&
           candidate.layerIndex == reference.layerIndex &&
           candidate.isBoundary == reference.isBoundary &&
           candidate.isGhost == reference.isGhost &&
           candidate.isInsertionPatch == reference.isInsertionPatch &&
           candidate.adjacentVertices == reference.adjacentVertices &&
           candidate.oneRingVertices == reference.oneRingVertices &&
           candidate.adjacentFaces == reference.adjacentFaces &&
           candidate.spontCurvature == reference.spontCurvature &&
           candidate.meanCurvature == reference.meanCurvature &&
           matrix_matches(candidate.normVector, reference.normVector) &&
           candidate.elementArea == reference.elementArea &&
           candidate.elementVolume == reference.elementVolume &&
           energy_matches(candidate.energyPrev, reference.energyPrev) &&
           energy_matches(candidate.energy, reference.energy);
}

bool vertex_matches(const Vertex &candidate, const Vertex &reference)
{
    return candidate.index == reference.index &&
           matrix_matches(candidate.coord, reference.coord) &&
           matrix_matches(candidate.coordPrev, reference.coordPrev) &&
           matrix_matches(candidate.coordRef, reference.coordRef) &&
           candidate.adjacentVertices == reference.adjacentVertices &&
           candidate.adjacentFaces == reference.adjacentFaces &&
           matrix_matches(candidate.normVector, reference.normVector) &&
           candidate.layerIndex == reference.layerIndex &&
           candidate.type == reference.type &&
           candidate.reflectiveVertexIndex ==
               reference.reflectiveVertexIndex &&
           candidate.isBoundary == reference.isBoundary &&
           force_matches(candidate.force, reference.force) &&
           force_matches(candidate.forcePrev, reference.forcePrev) &&
           candidate.isGhost == reference.isGhost;
}

MeshScientificState capture_mesh_scientific_state(const Mesh &mesh)
{
    MeshScientificState state;
    state.faces = mesh.faces;
    state.vertices = mesh.vertices;
    return state;
}

bool mesh_scientific_state_matches(const Mesh &mesh,
                                   const MeshScientificState &state)
{
    if (mesh.faces.size() != state.faces.size() ||
        mesh.vertices.size() != state.vertices.size())
    {
        return false;
    }
    for (std::size_t face = 0; face < mesh.faces.size(); ++face)
    {
        if (!face_matches(mesh.faces[face], state.faces[face]))
        {
            return false;
        }
    }
    for (std::size_t source = 0; source < mesh.vertices.size(); ++source)
    {
        if (!vertex_matches(mesh.vertices[source],
                            state.vertices[source]))
        {
            return false;
        }
    }
    return true;
}

bool mesh_state_mutation_gate_is_binding(
    Mesh &mesh,
    const MeshScientificState &state)
{
    const auto rejects = [&](const auto &mutation) {
        Mesh probe(mesh.param);
        probe.faces = state.faces;
        probe.vertices = state.vertices;
        mutation(probe);
        return !mesh_scientific_state_matches(probe, state);
    };
    return rejects([](Mesh &probe) {
               probe.faces[0].normVector.set(0, 0, 11.0);
           }) &&
           rejects([](Mesh &probe) {
               probe.faces[0].elementArea += 13.0;
           }) &&
           rejects([](Mesh &probe) {
               probe.faces[0].elementVolume -= 17.0;
           }) &&
           rejects([](Mesh &probe) {
               probe.faces[0].energy.energyArea += 19.0;
           }) &&
           rejects([](Mesh &probe) {
               probe.faces[0].energyPrev.energyVolume += 23.0;
           }) &&
           rejects([](Mesh &probe) {
               probe.faces[0].oneRingVertices.resize(1, 29);
           }) &&
           rejects([](Mesh &probe) {
               probe.vertices[0].coord.set(0, 0, 31.0);
           }) &&
           rejects([](Mesh &probe) {
               probe.vertices[0].coordPrev.set(1, 0, 37.0);
           }) &&
           rejects([](Mesh &probe) {
               probe.vertices[0].coordRef.set(2, 0, 41.0);
           }) &&
           rejects([](Mesh &probe) {
               probe.vertices[0].normVector.set(0, 0, 43.0);
           }) &&
           rejects([](Mesh &probe) {
               probe.vertices[0].force.forceTotal.set(1, 0, 47.0);
           }) &&
           rejects([](Mesh &probe) {
               probe.vertices[0].forcePrev.forceThickness.set(
                   2, 0, 53.0);
           });
}

double compare_face_observables(
    const std::vector<Valence4FaceScientificObservables> &candidate,
    const std::vector<Valence4FaceScientificObservables> &reference)
{
    if (candidate.size() != reference.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maximum = 0.0;
    for (std::size_t face = 0; face < reference.size(); ++face)
    {
        if (candidate[face].faceIndex != reference[face].faceIndex)
        {
            return std::numeric_limits<double>::infinity();
        }
        maximum = std::max(
            maximum,
            std::abs(candidate[face].meanCurvature -
                     reference[face].meanCurvature));
        maximum = std::max(
            maximum,
            std::abs(candidate[face].bendingEnergy -
                     reference[face].bendingEnergy));
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            maximum = std::max(
                maximum,
                std::abs(candidate[face].normal[axis] -
                         reference[face].normal[axis]));
        }
    }
    return maximum;
}

struct ScientificRequestCompositionProof
{
    bool defaultOffRejected = false;
    bool accepted = false;
    bool productionScientificAlgebraExecuted = false;
    bool callerOwnedOutput = false;
    bool meshStateUnchanged = false;
    bool meshStateMutationGateBinding = false;
    bool routeRemainedDisabled = false;
    double maxObservableDifference = 0.0;
    double maxSourceForceDifference = 0.0;
};

ScientificRequestCompositionProof invoke_guarded_scientific_request(
    Mesh &mesh,
    const InputPackage &package,
    const ScientificForceAlgebraProof &reference,
    const std::vector<SourceForceKinds> &referenceForces)
{
    ScientificRequestCompositionProof proof;
    seed_mesh_scientific_state(mesh);
    const MeshScientificState before =
        capture_mesh_scientific_state(mesh);

    Valence4FaceLoopScientificRequest defaultOffRequest;
    defaultOffRequest.rows = package.rows;
    const Valence4FaceLoopScientificRequestResult defaultOff =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, defaultOffRequest);
    proof.defaultOffRejected =
        !defaultOff.accepted &&
        !defaultOff.productionScientificAlgebraExecuted &&
        defaultOff.rejectionReason.find("default-off") !=
            std::string::npos &&
        mesh_scientific_state_matches(mesh, before);

    Valence4FaceLoopScientificRequest request;
    request.reviewerApprovedExplicitRequest = true;
    request.rows = package.rows;
    const Valence4FaceLoopScientificRequestResult result =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, request);
    proof.accepted = result.accepted;
    proof.productionScientificAlgebraExecuted =
        result.productionScientificAlgebraExecuted;
    proof.maxObservableDifference =
        compare_face_observables(result.faceObservables,
                                 reference.faceObservables);
    proof.maxSourceForceDifference =
        compare_scattered(
            result.sourceKeyedRequest.accumulatedSourceForces,
            referenceForces);
    proof.callerOwnedOutput =
        result.faceObservables.size() == kFaceCount &&
        result.sourceKeyedRequest.accumulatedSourceForces.size() ==
            kSourceCount;
    proof.meshStateUnchanged =
        mesh_scientific_state_matches(mesh, before);
    proof.meshStateMutationGateBinding =
        mesh_state_mutation_gate_is_binding(mesh, before);
    proof.routeRemainedDisabled =
        !result.productionRouteEnabled &&
        !result.actualProductionForcePathExecuted &&
        !result.productionFaceLoopExecuted &&
        !result.productionOneRingsPopulated &&
        !result.defaultEvaluatorCaller &&
        !result.sourceKeyedRequest.productionRouteEnabled &&
        !result.sourceKeyedRequest.actualProductionForcePathExecuted &&
        !result.sourceKeyedRequest.productionFaceLoopExecuted &&
        !result.sourceKeyedRequest.productionOneRingsPopulated &&
        !result.sourceKeyedRequest.defaultEvaluatorCaller;
    return proof;
}

bool all_production_one_rings_empty(const Mesh &mesh)
{
    return std::all_of(
        mesh.faces.begin(), mesh.faces.end(), [](const Face &face) {
            return face.oneRingVertices.empty();
        });
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: adapter vertices.csv faces.csv package.txt\n";
        return 2;
    }

    InputPackage package;
    if (!read_package(argv[3], package))
    {
        std::cerr << "failed to read source-keyed proof package\n";
        return 1;
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
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
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(read_data_from_csv<double>(argv[1]),
                                   read_data_from_csv<int>(argv[2]));
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            mesh.vertices[source].coord.set(
                axis, 0, package.coordinates[source][axis]);
        }
    }
    for (Face &face : mesh.faces)
    {
        face.spontCurvature = package.parameters.spontCurv;
    }

    const Valence4TopologySourceMappingResult guardedMapping =
        build_guarded_valence4_topology_source_mapping(mesh);
    const std::vector<SourceMappingView> mappings =
        mapping_views(mesh, guardedMapping);
    if (mappings.size() != kFaceCount)
    {
        std::cerr << "failed to build guarded source mapping\n";
        return 1;
    }

    const PreparedSourceKeyedKernelCall adapted =
        prepare_source_keyed_kernel_call(
            SourceKeyedKernelCallInput{
                kSourceCount, mappings, package.rows, package.forces});
    const std::vector<SourceForceKinds> scattered =
        accumulate_source_keyed_force_contributions(adapted);
    const IndependentOracle oracle = independent_scatter_oracle(package);
    const double maxOracleDelta =
        compare_with_independent_oracle(scattered, oracle);

    const InputPackage permutedPackage = permuted_bindings(package);
    const PreparedSourceKeyedKernelCall permutedAdapted =
        prepare_source_keyed_kernel_call(
            SourceKeyedKernelCallInput{kSourceCount,
                                       mappings,
                                       permutedPackage.rows,
                                       permutedPackage.forces});
    const std::vector<SourceForceKinds> permutedScattered =
        accumulate_source_keyed_force_contributions(permutedAdapted);
    const IndependentOracle permutedOracle =
        independent_scatter_oracle(permutedPackage);
    const double maxPermutationAdaptedDelta =
        compare_adapted_inputs(permutedAdapted, adapted);
    const double maxPermutationScatterDelta =
        compare_scattered(permutedScattered, scattered);
    const double maxPermutationOracleDelta =
        compare_with_independent_oracle(permutedScattered,
                                        permutedOracle);

    const InputPackage duplicatedPackage =
        split_duplicate_rows(permutedPackage);
    const PreparedSourceKeyedKernelCall duplicatedAdapted =
        prepare_source_keyed_kernel_call(
            SourceKeyedKernelCallInput{kSourceCount,
                                       mappings,
                                       duplicatedPackage.rows,
                                       duplicatedPackage.forces});
    const std::vector<SourceForceKinds> duplicatedScattered =
        accumulate_source_keyed_force_contributions(duplicatedAdapted);
    const double maxDuplicateAggregationDelta =
        compare_adapted_inputs(duplicatedAdapted, adapted);
    const double maxDuplicateScatterDelta =
        compare_scattered(duplicatedScattered, scattered);
    const ScientificForceAlgebraProof scientificForceAlgebra =
        invoke_scientific_force_algebra(adapted, package);
    const ScientificRequestCompositionProof scientificRequest =
        invoke_guarded_scientific_request(
            mesh, package, scientificForceAlgebra, scattered);

    const bool outOfRangeRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].sourceIds[0] = -1;
        },
        mappings,
        package);
    const bool cardinalityRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].coefficients.pop_back();
        },
        mappings,
        package);
    const bool incompleteRowCoverageRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].sourceIds.pop_back();
            input.rows[0].samples[0].rows[0].coefficients.pop_back();
        },
        mappings,
        package);
    const bool forceDuplicateRejected = rejected(
        [](auto &, auto &input) {
            input.forces[0].sourceIds[1] =
                input.forces[0].sourceIds[0];
        },
        mappings,
        package);
    const bool nonfiniteRowRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[0].coefficients[0] =
                std::numeric_limits<double>::infinity();
        },
        mappings,
        package);
    const bool nonfiniteForceRejected = rejected(
        [](auto &, auto &input) {
            input.forces[0].forces[0][0][0] =
                std::numeric_limits<double>::quiet_NaN();
        },
        mappings,
        package);
    const bool orientationRejected = rejected(
        [](auto &, auto &input) {
            std::swap(input.rows[0].orientedFaceVertices[1],
                      input.rows[0].orientedFaceVertices[2]);
        },
        mappings,
        package);
    const bool mappingDriftRejected = rejected(
        [](auto &views, auto &) {
            views[0].originalSourceIds[0] =
                views[0].originalSourceIds[1];
        },
        mappings,
        package);
    const bool nonemptyOneRingRejected = rejected(
        [](auto &views, auto &) {
            views[0].productionOneRingEmpty = false;
        },
        mappings,
        package);
    const bool mixedRowRejected = rejected(
        [](auto &, auto &input) {
            input.rows[0].samples[0].rows[6].coefficients[0] +=
                1.0e-4;
        },
        mappings,
        package);

    const bool productionOneRingsEmpty =
        all_production_one_rings_empty(mesh);
    const bool permutationInvariant =
        maxPermutationAdaptedDelta <= kTolerance &&
        maxPermutationScatterDelta <= kTolerance &&
        maxPermutationOracleDelta <= kTolerance;
    const bool duplicateRowsAggregated =
        maxDuplicateAggregationDelta <= kTolerance &&
        maxDuplicateScatterDelta <= kTolerance;
    const bool negativeGatesPassed =
        outOfRangeRejected && cardinalityRejected &&
        incompleteRowCoverageRejected && forceDuplicateRejected &&
        nonfiniteRowRejected && nonfiniteForceRejected &&
        orientationRejected && mappingDriftRejected &&
        nonemptyOneRingRejected && mixedRowRejected;
    const bool passed =
        adapted.faces.size() == kFaceCount &&
        adapted.sourceCount == kSourceCount &&
        maxOracleDelta <= kTolerance && productionOneRingsEmpty &&
        permutationInvariant && duplicateRowsAggregated &&
        negativeGatesPassed && scientificForceAlgebra.executed &&
        scientificForceAlgebra.finite &&
        scientificForceAlgebra.nonzero &&
        scientificForceAlgebra.maxForceDifference <= kTolerance &&
        scientificRequest.defaultOffRejected &&
        scientificRequest.accepted &&
        scientificRequest.productionScientificAlgebraExecuted &&
        scientificRequest.callerOwnedOutput &&
        scientificRequest.meshStateUnchanged &&
        scientificRequest.meshStateMutationGateBinding &&
        scientificRequest.routeRemainedDisabled &&
        scientificRequest.maxObservableDifference <= kTolerance &&
        scientificRequest.maxSourceForceDifference <= kTolerance;

    std::cout << std::setprecision(17);
    std::cout << '{';
    std::cout << "\"kind\":\"proof_only_valence4_source_keyed_kernel_adapter\",";
    std::cout << "\"proof_only\":true,";
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"production_route_enabled\":false,";
    std::cout << "\"actual_production_force_path_executed\":false,";
    std::cout << "\"production_kernel_call_helper_executed\":true,";
    std::cout << "\"production_kernel_call_helper\":\""
                 "prepare_source_keyed_kernel_call\",";
    std::cout << "\"production_helper_output_owned_by_caller\":true,";
    std::cout << "\"backend_neutral_adapter_api\":true,";
    std::cout << "\"guarded_topology_source_mapping_consumed\":true,";
    std::cout << "\"proof_provided_opensubdiv_rows_consumed\":true,";
    std::cout << "\"existing_force_algebra_contributions_consumed\":true,";
    std::cout << "\"existing_scientific_force_algebra_invoked\":"
              << (scientificForceAlgebra.executed ? "true" : "false")
              << ',';
    std::cout << "\"scientific_force_algebra_function\":\""
                 "Mesh::element_energy_force_regular\",";
    std::cout << "\"scientific_force_algebra_variable_cardinality\":6,";
    std::cout << "\"scientific_force_algebra_finite\":"
              << (scientificForceAlgebra.finite ? "true" : "false") << ',';
    std::cout << "\"scientific_force_algebra_nonzero\":"
              << (scientificForceAlgebra.nonzero ? "true" : "false") << ',';
    std::cout << "\"max_scientific_force_algebra_difference\":"
              << scientificForceAlgebra.maxForceDifference << ',';
    std::cout << "\"max_abs_scientific_force_by_kind\":["
              << scientificForceAlgebra.maxAbsForce[0] << ','
              << scientificForceAlgebra.maxAbsForce[1] << ','
              << scientificForceAlgebra.maxAbsForce[2] << "],";
    std::cout << "\"guarded_scientific_request_composition\":{";
    std::cout << "\"fresh_opensubdiv_rows_consumed\":true,";
    std::cout << "\"default_off_request_rejected\":"
              << (scientificRequest.defaultOffRejected ? "true" : "false")
              << ',';
    std::cout << "\"explicit_request_accepted\":"
              << (scientificRequest.accepted ? "true" : "false") << ',';
    std::cout << "\"production_scientific_algebra_executed\":"
              << (scientificRequest.productionScientificAlgebraExecuted
                      ? "true"
                      : "false")
              << ',';
    std::cout << "\"caller_owned_output\":"
              << (scientificRequest.callerOwnedOutput ? "true" : "false")
              << ',';
    std::cout << "\"mesh_state_unchanged\":"
              << (scientificRequest.meshStateUnchanged ? "true" : "false")
              << ',';
    std::cout << "\"mesh_state_mutation_gate_binding\":"
              << (scientificRequest.meshStateMutationGateBinding
                      ? "true"
                      : "false")
              << ',';
    std::cout << "\"route_remained_disabled\":"
              << (scientificRequest.routeRemainedDisabled ? "true" : "false")
              << ',';
    std::cout << "\"max_observable_difference\":"
              << scientificRequest.maxObservableDifference << ',';
    std::cout << "\"max_source_force_difference\":"
              << scientificRequest.maxSourceForceDifference << "},";
    std::cout << "\"variable_cardinality_source_keyed\":true,";
    std::cout << "\"canonicalized_by_original_source_id\":true,";
    std::cout << "\"face_count\":" << adapted.faces.size() << ',';
    std::cout << "\"source_count\":" << adapted.sourceCount << ',';
    std::cout << "\"sample_count_per_face\":3,";
    std::cout << "\"row_count_per_sample\":7,";
    std::cout << "\"force_component_layout\":\"6 sources x 3 force kinds x 3 axes\",";
    std::cout << "\"independent_fixed_source_layout_oracle_passed\":"
              << (maxOracleDelta <= kTolerance ? "true" : "false") << ',';
    std::cout << "\"max_scatter_oracle_delta\":"
              << maxOracleDelta << ',';
    std::cout << "\"source_binding_permutation_invariant\":"
              << (permutationInvariant ? "true" : "false") << ',';
    std::cout << "\"permuted_row_columns_canonicalized\":"
              << (maxPermutationAdaptedDelta <= kTolerance ? "true" : "false")
              << ',';
    std::cout << "\"permuted_force_columns_canonicalized\":"
              << (maxPermutationScatterDelta <= kTolerance ? "true" : "false")
              << ',';
    std::cout << "\"independent_permuted_scatter_oracle_passed\":"
              << (maxPermutationOracleDelta <= kTolerance ? "true" : "false")
              << ',';
    std::cout << "\"max_permutation_adapted_delta\":"
              << maxPermutationAdaptedDelta << ',';
    std::cout << "\"max_permutation_scatter_delta\":"
              << maxPermutationScatterDelta << ',';
    std::cout << "\"max_permutation_oracle_delta\":"
              << maxPermutationOracleDelta << ',';
    std::cout << "\"duplicate_row_entries_aggregated_by_source_id\":"
              << (duplicateRowsAggregated ? "true" : "false") << ',';
    std::cout << "\"max_duplicate_row_aggregation_delta\":"
              << maxDuplicateAggregationDelta << ',';
    std::cout << "\"max_duplicate_row_scatter_delta\":"
              << maxDuplicateScatterDelta << ',';
    std::cout << "\"production_one_rings_empty\":"
              << (productionOneRingsEmpty ? "true" : "false") << ',';
    std::cout << "\"production_one_rings_mutated\":false,";
    std::cout << "\"negative_gates\":{";
    std::cout << "\"out_of_range_source_id\":"
              << (outOfRangeRejected ? "true" : "false") << ',';
    std::cout << "\"inconsistent_row_cardinality\":"
              << (cardinalityRejected ? "true" : "false") << ',';
    std::cout << "\"incomplete_row_source_coverage\":"
              << (incompleteRowCoverageRejected ? "true" : "false") << ',';
    std::cout << "\"duplicate_force_source_id\":"
              << (forceDuplicateRejected ? "true" : "false") << ',';
    std::cout << "\"nonfinite_row_data\":"
              << (nonfiniteRowRejected ? "true" : "false") << ',';
    std::cout << "\"nonfinite_force_data\":"
              << (nonfiniteForceRejected ? "true" : "false") << ',';
    std::cout << "\"orientation_drift\":"
              << (orientationRejected ? "true" : "false") << ',';
    std::cout << "\"mapping_drift\":"
              << (mappingDriftRejected ? "true" : "false") << ',';
    std::cout << "\"nonempty_production_one_ring\":"
              << (nonemptyOneRingRejected ? "true" : "false") << ',';
    std::cout << "\"mixed_row_drift\":"
              << (mixedRowRejected ? "true" : "false") << ',';
    std::cout << "\"all_passed\":"
              << (negativeGatesPassed ? "true" : "false") << "},";
    std::cout << "\"residual_boundary\":"
                 "\"fresh OpenSubdiv valence-4 rows now pass through the "
                 "guarded default-off scientific request without mesh "
                 "mutation; production face-loop integration remains a "
                 "separately reviewed boundary\",";
    std::cout << "\"passed\":" << (passed ? "true" : "false");
    std::cout << "}\n";
    return passed ? 0 : 1;
}
