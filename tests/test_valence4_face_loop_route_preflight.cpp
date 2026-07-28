#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <gtest/gtest.h>

#include "Parameters.hpp"
#include "energy_force/Source_keyed_kernel_call.hpp"
#include "energy_force/Valence4_face_loop_route_preflight.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_valence4_row_provider.hpp"

namespace
{
using namespace slimed::source_keyed_kernel;
using namespace slimed::valence4_route_preflight;

struct ApprovedValence4MeshFixture
{
    Param param;
    std::unique_ptr<Mesh> mesh;

    ApprovedValence4MeshFixture()
    {
        param.VERBOSE_MODE = false;
        param.boundaryCondition = BoundaryType::Fixed;
        param.subDivideTimes = 2;
        param.kCurv = 47.5;
        param.uSurf = 130.0;
        param.area0 = 2.75;
        param.area = 5.5;
        param.uVol = 65.0;
        param.vol0 = 0.82;
        param.vol = 0.25;

        const auto verticesData = read_data_from_csv<double>(
            "./data/fixtures/candidates/closed_valence4_octahedron/vertices.csv");
        const auto facesData = read_data_from_csv<int>(
            "./data/fixtures/candidates/closed_valence4_octahedron/faces.csv");
        mesh = std::make_unique<Mesh>(param);
        mesh->setup_from_vertices_faces(verticesData, facesData);
    }
};

SourceKeyedFaceRows make_rows_for_mapping(
    const SourceMappingView &mapping)
{
    SourceKeyedFaceRows rows;
    rows.faceIndex = mapping.faceIndex;
    rows.orientedFaceVertices = mapping.orientedFaceVertices;
    rows.samples.resize(3);

    std::vector<int> reversedSourceIds = mapping.originalSourceIds;
    std::reverse(reversedSourceIds.begin(), reversedSourceIds.end());
    for (std::size_t sampleIndex = 0;
         sampleIndex < rows.samples.size();
         ++sampleIndex)
    {
        for (int rowIndex = 0; rowIndex < kDerivativeRowCount; ++rowIndex)
        {
            SourceKeyedRow &row =
                rows.samples[sampleIndex].rows[rowIndex];
            row.sourceIds = reversedSourceIds;
            row.coefficients.reserve(reversedSourceIds.size());
            const double rowBase =
                rowIndex >= 5 ? 5.0 : static_cast<double>(rowIndex);
            for (const int sourceId : reversedSourceIds)
            {
                row.coefficients.push_back(
                    rowBase +
                    0.1 * static_cast<double>(sampleIndex) +
                    0.01 * static_cast<double>(mapping.faceIndex + 1) +
                    0.001 * static_cast<double>(sourceId + 1));
            }
        }
    }
    return rows;
}

SourceKeyedFaceForces make_forces_for_mapping(
    const SourceMappingView &mapping)
{
    SourceKeyedFaceForces forces;
    forces.faceIndex = mapping.faceIndex;
    forces.sourceIds = mapping.originalSourceIds;
    std::reverse(forces.sourceIds.begin(), forces.sourceIds.end());
    forces.forces.resize(forces.sourceIds.size());
    for (std::size_t position = 0; position < forces.sourceIds.size();
         ++position)
    {
        const int sourceId = forces.sourceIds[position];
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                forces.forces[position][kind][axis] =
                    1000.0 * static_cast<double>(mapping.faceIndex + 1) +
                    100.0 * static_cast<double>(sourceId + 1) +
                    10.0 * static_cast<double>(kind) +
                    static_cast<double>(axis);
            }
        }
    }
    return forces;
}

Valence4FaceLoopRouteRequest make_request_from_preflight(
    const Valence4FaceLoopRoutePreflightResult &preflight,
    const bool reviewerApprovedExplicitRequest)
{
    Valence4FaceLoopRouteRequest request;
    request.reviewerApprovedExplicitRequest = reviewerApprovedExplicitRequest;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(make_rows_for_mapping(mapping));
        request.forces.push_back(make_forces_for_mapping(mapping));
    }
    return request;
}

SourceKeyedFaceRows make_scientific_rows_for_mapping(
    const SourceMappingView &mapping)
{
    SourceKeyedFaceRows rows;
    rows.faceIndex = mapping.faceIndex;
    rows.orientedFaceVertices = mapping.orientedFaceVertices;
    rows.samples.resize(3);
    for (SourceKeyedSampleRows &sample : rows.samples)
    {
        for (SourceKeyedRow &row : sample.rows)
        {
            row.sourceIds = mapping.originalSourceIds;
            row.coefficients.assign(mapping.originalSourceIds.size(),
                                    0.0);
        }
        const auto sourcePosition = [&mapping](const int sourceId) {
            const auto found =
                std::find(mapping.originalSourceIds.begin(),
                          mapping.originalSourceIds.end(),
                          sourceId);
            if (found == mapping.originalSourceIds.end())
            {
                throw std::runtime_error(
                    "scientific test fixture source is absent");
            }
            return static_cast<std::size_t>(
                found - mapping.originalSourceIds.begin());
        };
        const std::size_t corner0 =
            sourcePosition(mapping.orientedFaceVertices[0]);
        const std::size_t corner1 =
            sourcePosition(mapping.orientedFaceVertices[1]);
        const std::size_t corner2 =
            sourcePosition(mapping.orientedFaceVertices[2]);
        sample.rows[0].coefficients[corner0] = 1.0 / 3.0;
        sample.rows[0].coefficients[corner1] = 1.0 / 3.0;
        sample.rows[0].coefficients[corner2] = 1.0 / 3.0;
        sample.rows[1].coefficients[corner0] = -1.0;
        sample.rows[1].coefficients[corner1] = 1.0;
        sample.rows[2].coefficients[corner0] = -1.0;
        sample.rows[2].coefficients[corner2] = 1.0;
    }
    return rows;
}

Valence4FaceLoopScientificRequest make_scientific_request(
    const Valence4FaceLoopRoutePreflightResult &preflight,
    const bool reviewerApprovedExplicitRequest)
{
    Valence4FaceLoopScientificRequest request;
    request.reviewerApprovedExplicitRequest =
        reviewerApprovedExplicitRequest;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    return request;
}

Valence4FaceGeometryStagingRequest make_geometry_staging_request(
    const Valence4FaceLoopRoutePreflightResult &preflight,
    const bool reviewerApprovedExplicitStaging)
{
    Valence4FaceGeometryStagingRequest request;
    request.reviewerApprovedExplicitStaging =
        reviewerApprovedExplicitStaging;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    return request;
}

Valence4GeometryAwareAtomicCompositionRequest
make_geometry_aware_composition_request(
    const Valence4FaceLoopRoutePreflightResult &preflight,
    const bool reviewerApprovedExplicitComposition)
{
    Valence4GeometryAwareAtomicCompositionRequest request;
    request.reviewerApprovedExplicitComposition =
        reviewerApprovedExplicitComposition;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    return request;
}

Valence4ProductionCallerShadowRequest
make_production_caller_shadow_request(
    const Valence4FaceLoopRoutePreflightResult &preflight,
    const bool reviewerApprovedExplicitShadow)
{
    Valence4ProductionCallerShadowRequest request;
    request.reviewerApprovedExplicitShadow =
        reviewerApprovedExplicitShadow;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    return request;
}

Valence4FaceGeometry geometry_oracle(
    const Mesh &mesh,
    const SourceMappingView &mapping)
{
    std::array<Vec3, 3> corners{};
    for (int corner = 0; corner < 3; ++corner)
    {
        const Matrix &coordinate =
            mesh.vertices[mapping.orientedFaceVertices[corner]].coord;
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            corners[corner][axis] = coordinate.get(axis, 0);
        }
    }
    Vec3 position{};
    Vec3 derivativeV{};
    Vec3 derivativeW{};
    for (int axis = 0; axis < kAxisCount; ++axis)
    {
        position[axis] =
            (corners[0][axis] + corners[1][axis] +
             corners[2][axis]) /
            3.0;
        derivativeV[axis] =
            corners[1][axis] - corners[0][axis];
        derivativeW[axis] =
            corners[2][axis] - corners[0][axis];
    }
    const Vec3 areaVector{{
        derivativeV[1] * derivativeW[2] -
            derivativeV[2] * derivativeW[1],
        derivativeV[2] * derivativeW[0] -
            derivativeV[0] * derivativeW[2],
        derivativeV[0] * derivativeW[1] -
            derivativeV[1] * derivativeW[0],
    }};
    double weightSum = 0.0;
    for (int sample = 0;
         sample < mesh.param.gaussQuadratureCoeff.nrow();
         ++sample)
    {
        weightSum +=
            mesh.param.gaussQuadratureCoeff.get(sample, 0);
    }

    Valence4FaceGeometry geometry;
    geometry.faceIndex = mapping.faceIndex;
    geometry.elementArea =
        0.5 * weightSum *
        std::sqrt(areaVector[0] * areaVector[0] +
                  areaVector[1] * areaVector[1] +
                  areaVector[2] * areaVector[2]);
    geometry.elementVolume =
        0.16666666666 * weightSum *
        position[0] * areaVector[0];
    return geometry;
}

void seed_mesh_owned_scientific_state(Mesh &mesh)
{
    for (Face &face : mesh.faces)
    {
        face.meanCurvature = 100.0 + face.index;
        face.energy.energyCurvature = 200.0 + face.index;
    }
    for (Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            const double sentinel =
                1000.0 + 10.0 * vertex.index + axis;
            vertex.force.forceCurvature.set(axis, 0, sentinel);
            vertex.force.forceArea.set(axis, 0, -sentinel);
            vertex.force.forceVolume.set(axis, 0, 2.0 * sentinel);
        }
    }
}

void expect_mesh_owned_scientific_state_unchanged(const Mesh &mesh)
{
    for (const Face &face : mesh.faces)
    {
        EXPECT_DOUBLE_EQ(face.meanCurvature,
                         100.0 + face.index);
        EXPECT_DOUBLE_EQ(face.energy.energyCurvature,
                         200.0 + face.index);
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            const double sentinel =
                1000.0 + 10.0 * vertex.index + axis;
            EXPECT_DOUBLE_EQ(
                vertex.force.forceCurvature.get(axis, 0),
                sentinel);
            EXPECT_DOUBLE_EQ(vertex.force.forceArea.get(axis, 0),
                             -sentinel);
            EXPECT_DOUBLE_EQ(
                vertex.force.forceVolume.get(axis, 0),
                2.0 * sentinel);
        }
    }
}

constexpr int kForceFamilyCount = 16;
using VertexForceSnapshot =
    std::array<std::array<double, kAxisCount>, kForceFamilyCount>;

std::array<Matrix *, kForceFamilyCount> mutable_force_matrices(
    Vertex &vertex)
{
    return {{
        &vertex.force.forceCurvature,
        &vertex.force.forceArea,
        &vertex.force.forceVolume,
        &vertex.force.forceThickness,
        &vertex.force.forceTilt,
        &vertex.force.forceRegularization,
        &vertex.force.forceHarmonicBond,
        &vertex.force.forceTotal,
        &vertex.forcePrev.forceCurvature,
        &vertex.forcePrev.forceArea,
        &vertex.forcePrev.forceVolume,
        &vertex.forcePrev.forceThickness,
        &vertex.forcePrev.forceTilt,
        &vertex.forcePrev.forceRegularization,
        &vertex.forcePrev.forceHarmonicBond,
        &vertex.forcePrev.forceTotal,
    }};
}

std::array<const Matrix *, kForceFamilyCount> force_matrices(
    const Vertex &vertex)
{
    return {{
        &vertex.force.forceCurvature,
        &vertex.force.forceArea,
        &vertex.force.forceVolume,
        &vertex.force.forceThickness,
        &vertex.force.forceTilt,
        &vertex.force.forceRegularization,
        &vertex.force.forceHarmonicBond,
        &vertex.force.forceTotal,
        &vertex.forcePrev.forceCurvature,
        &vertex.forcePrev.forceArea,
        &vertex.forcePrev.forceVolume,
        &vertex.forcePrev.forceThickness,
        &vertex.forcePrev.forceTilt,
        &vertex.forcePrev.forceRegularization,
        &vertex.forcePrev.forceHarmonicBond,
        &vertex.forcePrev.forceTotal,
    }};
}

void seed_all_vertex_forces(Mesh &mesh)
{
    for (Vertex &vertex : mesh.vertices)
    {
        const auto matrices = mutable_force_matrices(vertex);
        for (int family = 0; family < kForceFamilyCount; ++family)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                matrices[family]->set(
                    axis,
                    0,
                    100000.0 * vertex.index +
                        1000.0 * family + axis + 0.25);
            }
        }
    }
}

void seed_reference_coordinates_from_current(Mesh &mesh)
{
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.coordRef = vertex.coord;
    }
}

std::vector<VertexForceSnapshot> capture_all_vertex_forces(
    const Mesh &mesh)
{
    std::vector<VertexForceSnapshot> snapshot(mesh.vertices.size());
    for (std::size_t source = 0; source < mesh.vertices.size(); ++source)
    {
        const auto matrices = force_matrices(mesh.vertices[source]);
        for (int family = 0; family < kForceFamilyCount; ++family)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                snapshot[source][family][axis] =
                    matrices[family]->get(axis, 0);
            }
        }
    }
    return snapshot;
}

void seed_publication_unrelated_state(Mesh &mesh)
{
    for (Face &face : mesh.faces)
    {
        face.meanCurvature = 2000.0 + face.index;
        face.elementArea = 3000.0 + face.index;
        face.elementVolume = 4000.0 + face.index;
        face.energy.energyCurvature = 5000.0 + face.index;
    }
    for (Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            vertex.coord.set(
                axis, 0, 6000.0 + 10.0 * vertex.index + axis);
        }
    }
}

void expect_publication_unrelated_state_unchanged(const Mesh &mesh)
{
    for (const Face &face : mesh.faces)
    {
        EXPECT_DOUBLE_EQ(face.meanCurvature,
                         2000.0 + face.index);
        EXPECT_DOUBLE_EQ(face.elementArea,
                         3000.0 + face.index);
        EXPECT_DOUBLE_EQ(face.elementVolume,
                         4000.0 + face.index);
        EXPECT_DOUBLE_EQ(face.energy.energyCurvature,
                         5000.0 + face.index);
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            EXPECT_DOUBLE_EQ(
                vertex.coord.get(axis, 0),
                6000.0 + 10.0 * vertex.index + axis);
        }
    }
}

void seed_face_observable_publication_state(Mesh &mesh)
{
    for (Face &face : mesh.faces)
    {
        face.meanCurvature = 7100.0 + face.index;
        face.normVector = Matrix(2, 1, true);
        face.normVector.set(0, 0, 7200.0 + face.index);
        face.normVector.set(1, 0, 7300.0 + face.index);
        face.elementArea = 7400.0 + face.index;
        face.elementVolume = 7500.0 + face.index;
        face.energy.energyCurvature = 7600.0 + face.index;
        face.energy.energyArea = 7700.0 + face.index;
        face.energy.energyVolume = 7800.0 + face.index;
        face.energy.energyThickness = 7900.0 + face.index;
        face.energy.energyTilt = 8000.0 + face.index;
        face.energy.energyRegularization = 8100.0 + face.index;
        face.energy.energyHarmonicBond = 8200.0 + face.index;
        face.energy.energyGagScaffolding = 8300.0 + face.index;
        face.energy.energyIdealizedProteinLattice =
            8400.0 + face.index;
        face.energy.energyTotal = 8500.0 + face.index;
        face.energyPrev.energyCurvature = 8600.0 + face.index;
        face.energyPrev.energyArea = 8700.0 + face.index;
        face.energyPrev.energyVolume = 8800.0 + face.index;
        face.energyPrev.energyThickness = 8900.0 + face.index;
        face.energyPrev.energyTilt = 9000.0 + face.index;
        face.energyPrev.energyRegularization = 9100.0 + face.index;
        face.energyPrev.energyHarmonicBond = 9200.0 + face.index;
        face.energyPrev.energyGagScaffolding = 9300.0 + face.index;
        face.energyPrev.energyIdealizedProteinLattice =
            9400.0 + face.index;
        face.energyPrev.energyTotal = 9500.0 + face.index;
    }
}

std::vector<std::array<double, kAxisCount>> capture_vertex_coordinates(
    const Mesh &mesh)
{
    std::vector<std::array<double, kAxisCount>> coordinates(
        mesh.vertices.size());
    for (std::size_t source = 0; source < mesh.vertices.size(); ++source)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            coordinates[source][axis] =
                mesh.vertices[source].coord.get(axis, 0);
        }
    }
    return coordinates;
}

std::vector<const void *> capture_face_normal_allocations(
    const Mesh &mesh)
{
    std::vector<const void *> allocations;
    allocations.reserve(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        allocations.push_back(face.normVector.mat);
    }
    return allocations;
}

void expect_energy_equal(const Energy &actual,
                         const Energy &expected,
                         const bool ignoreCurvature)
{
    if (!ignoreCurvature)
    {
        EXPECT_DOUBLE_EQ(actual.energyCurvature,
                         expected.energyCurvature);
    }
    EXPECT_DOUBLE_EQ(actual.energyArea, expected.energyArea);
    EXPECT_DOUBLE_EQ(actual.energyVolume, expected.energyVolume);
    EXPECT_DOUBLE_EQ(actual.energyThickness, expected.energyThickness);
    EXPECT_DOUBLE_EQ(actual.energyTilt, expected.energyTilt);
    EXPECT_DOUBLE_EQ(actual.energyRegularization,
                     expected.energyRegularization);
    EXPECT_DOUBLE_EQ(actual.energyHarmonicBond,
                     expected.energyHarmonicBond);
    EXPECT_DOUBLE_EQ(actual.energyGagScaffolding,
                     expected.energyGagScaffolding);
    EXPECT_DOUBLE_EQ(actual.energyIdealizedProteinLattice,
                     expected.energyIdealizedProteinLattice);
    EXPECT_DOUBLE_EQ(actual.energyTotal, expected.energyTotal);
}

void expect_only_face_observables_published(
    const Mesh &mesh,
    const std::vector<Face> &before,
    const std::vector<Valence4FaceScientificObservables> &expected)
{
    ASSERT_EQ(mesh.faces.size(), before.size());
    ASSERT_EQ(mesh.faces.size(), expected.size());
    for (std::size_t faceIndex = 0;
         faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        const Face &actual = mesh.faces[faceIndex];
        const Face &reference = before[faceIndex];
        const Valence4FaceScientificObservables &observable =
            expected[faceIndex];
        EXPECT_EQ(observable.faceIndex,
                  static_cast<int>(faceIndex));
        EXPECT_DOUBLE_EQ(actual.meanCurvature,
                         observable.meanCurvature);
        EXPECT_DOUBLE_EQ(actual.energy.energyCurvature,
                         observable.bendingEnergy);
        ASSERT_NE(actual.normVector.mat, nullptr);
        ASSERT_EQ(actual.normVector.nrow(), kAxisCount);
        ASSERT_EQ(actual.normVector.ncol(), 1);
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            EXPECT_DOUBLE_EQ(actual.normVector.get(axis, 0),
                             observable.normal[axis]);
        }

        EXPECT_EQ(actual.index, reference.index);
        EXPECT_EQ(actual.layerIndex, reference.layerIndex);
        EXPECT_EQ(actual.isBoundary, reference.isBoundary);
        EXPECT_EQ(actual.isGhost, reference.isGhost);
        EXPECT_EQ(actual.isInsertionPatch,
                  reference.isInsertionPatch);
        EXPECT_EQ(actual.adjacentVertices,
                  reference.adjacentVertices);
        EXPECT_EQ(actual.oneRingVertices,
                  reference.oneRingVertices);
        EXPECT_EQ(actual.adjacentFaces, reference.adjacentFaces);
        EXPECT_DOUBLE_EQ(actual.spontCurvature,
                         reference.spontCurvature);
        EXPECT_DOUBLE_EQ(actual.elementArea,
                         reference.elementArea);
        EXPECT_DOUBLE_EQ(actual.elementVolume,
                         reference.elementVolume);
        expect_energy_equal(actual.energy, reference.energy, true);
        expect_energy_equal(actual.energyPrev,
                            reference.energyPrev,
                            false);
    }
}

void expect_face_observable_publication_state_unchanged(
    const Mesh &mesh,
    const std::vector<Face> &before)
{
    ASSERT_EQ(mesh.faces.size(), before.size());
    for (std::size_t faceIndex = 0;
         faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        const Face &actual = mesh.faces[faceIndex];
        const Face &reference = before[faceIndex];
        EXPECT_EQ(actual.index, reference.index);
        EXPECT_EQ(actual.layerIndex, reference.layerIndex);
        EXPECT_EQ(actual.isBoundary, reference.isBoundary);
        EXPECT_EQ(actual.isGhost, reference.isGhost);
        EXPECT_EQ(actual.isInsertionPatch,
                  reference.isInsertionPatch);
        EXPECT_EQ(actual.adjacentVertices,
                  reference.adjacentVertices);
        EXPECT_EQ(actual.oneRingVertices,
                  reference.oneRingVertices);
        EXPECT_EQ(actual.adjacentFaces, reference.adjacentFaces);
        EXPECT_DOUBLE_EQ(actual.spontCurvature,
                         reference.spontCurvature);
        EXPECT_DOUBLE_EQ(actual.meanCurvature,
                         reference.meanCurvature);
        ASSERT_NE(actual.normVector.mat, nullptr);
        ASSERT_NE(reference.normVector.mat, nullptr);
        ASSERT_EQ(actual.normVector.nrow(),
                  reference.normVector.nrow());
        ASSERT_EQ(actual.normVector.ncol(),
                  reference.normVector.ncol());
        for (int row = 0; row < actual.normVector.nrow(); ++row)
        {
            for (int column = 0;
                 column < actual.normVector.ncol();
                 ++column)
            {
                EXPECT_DOUBLE_EQ(actual.normVector.get(row, column),
                                 reference.normVector.get(row, column));
            }
        }
        EXPECT_DOUBLE_EQ(actual.elementArea,
                         reference.elementArea);
        EXPECT_DOUBLE_EQ(actual.elementVolume,
                         reference.elementVolume);
        expect_energy_equal(actual.energy, reference.energy, false);
        expect_energy_equal(actual.energyPrev,
                            reference.energyPrev,
                            false);
    }
}

std::vector<Valence4FaceScientificObservables>
make_face_observables(const Mesh &mesh)
{
    std::vector<Valence4FaceScientificObservables> observables;
    observables.reserve(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        Valence4FaceScientificObservables observable;
        observable.faceIndex = face.index;
        observable.meanCurvature = 101.0 + face.index;
        observable.bendingEnergy = 201.0 + face.index;
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            observable.normal[axis] =
                301.0 + 10.0 * face.index + axis;
        }
        observables.push_back(observable);
    }
    return observables;
}

void expect_only_membrane_forces_published(
    const Mesh &mesh,
    const std::vector<VertexForceSnapshot> &before,
    const std::vector<SourceForceKinds> &expected)
{
    ASSERT_EQ(mesh.vertices.size(), before.size());
    ASSERT_EQ(mesh.vertices.size(), expected.size());
    for (std::size_t source = 0; source < mesh.vertices.size(); ++source)
    {
        const auto matrices = force_matrices(mesh.vertices[source]);
        for (int family = 0; family < kForceFamilyCount; ++family)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                if (family < kForceKindCount)
                {
                    EXPECT_DOUBLE_EQ(
                        matrices[family]->get(axis, 0),
                        expected[source][family][axis]);
                }
                else
                {
                    EXPECT_DOUBLE_EQ(
                        matrices[family]->get(axis, 0),
                        before[source][family][axis]);
                }
            }
        }
    }
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}
} // namespace

TEST(ValenceFourFaceLoopRoutePreflight,
     ApprovedOctahedronBuildsInertSourceKeyedRouteCandidate)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);

    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    EXPECT_TRUE(preflight.rejectionReason.empty());
    EXPECT_EQ(preflight.sourceCount, 6);
    ASSERT_EQ(preflight.mappings.size(), mesh.faces.size());
    EXPECT_FALSE(preflight.productionRouteEnabled);
    EXPECT_FALSE(preflight.actualProductionForcePathExecuted);
    EXPECT_FALSE(preflight.productionFaceLoopExecuted);
    EXPECT_FALSE(preflight.productionOneRingsPopulated);

    const std::vector<int> expectedSourceIds{0, 1, 2, 3, 4, 5};
    for (const Face &face : mesh.faces)
    {
        const SourceMappingView &mapping = preflight.mappings[face.index];
        EXPECT_EQ(mapping.faceIndex, face.index);
        EXPECT_EQ(mapping.originalSourceIds, expectedSourceIds);
        EXPECT_TRUE(mapping.productionOneRingEmpty);
        for (int corner = 0; corner < 3; ++corner)
        {
            EXPECT_EQ(mapping.orientedFaceVertices[corner],
                      face.adjacentVertices[corner]);
        }
        EXPECT_TRUE(face.oneRingVertices.empty());
    }

    EXPECT_THROW(mesh.calculate_element_area_volume(), std::runtime_error);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     RejectsOneRingContractDriftWithoutPartialCandidate)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    mesh.faces[0].oneRingVertices = {0, 1, 2, 3, 4, 5};

    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);

    EXPECT_FALSE(preflight.supported);
    EXPECT_NE(preflight.rejectionReason.find("11/12-control"),
              std::string::npos);
    EXPECT_TRUE(preflight.mappings.empty());
    EXPECT_FALSE(preflight.productionRouteEnabled);
    EXPECT_FALSE(preflight.actualProductionForcePathExecuted);
    EXPECT_FALSE(preflight.productionFaceLoopExecuted);
    EXPECT_FALSE(preflight.productionOneRingsPopulated);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     PreflightMappingsFeedSourceKeyedValidationWithoutRouteExecution)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;

    SourceKeyedKernelCallInput input;
    input.sourceCount = preflight.sourceCount;
    input.mappings = preflight.mappings;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        input.rows.push_back(make_rows_for_mapping(mapping));
        input.forces.push_back(make_forces_for_mapping(mapping));
    }

    const PreparedSourceKeyedKernelCall prepared =
        prepare_source_keyed_kernel_call(input);
    EXPECT_EQ(prepared.sourceCount, preflight.sourceCount);
    ASSERT_EQ(prepared.faces.size(), preflight.mappings.size());
    const std::vector<SourceForceKinds> accumulated =
        accumulate_source_keyed_force_contributions(prepared);
    ASSERT_EQ(accumulated.size(),
              static_cast<std::size_t>(preflight.sourceCount));
    for (const SourceForceKinds &sourceForces : accumulated)
    {
        for (const Vec3 &force : sourceForces)
        {
            for (const double component : force)
            {
                EXPECT_NE(component, 0.0);
            }
        }
    }

    EXPECT_FALSE(preflight.productionRouteEnabled);
    EXPECT_FALSE(preflight.actualProductionForcePathExecuted);
    EXPECT_FALSE(preflight.productionFaceLoopExecuted);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ExplicitRouteRequestRejectsByDefaultBeforeSourceKeyedAccumulation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;

    const Valence4FaceLoopRouteRequest request =
        make_request_from_preflight(preflight, false);
    const Valence4FaceLoopRouteRequestResult result =
        evaluate_guarded_valence4_face_loop_route_request(mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_NE(result.rejectionReason.find("default-off"),
              std::string::npos);
    EXPECT_FALSE(result.explicitRouteRequested);
    EXPECT_FALSE(result.explicitRouteRequestAccepted);
    EXPECT_FALSE(result.sourceKeyedAccumulationExecuted);
    EXPECT_TRUE(result.preflight.supported);
    EXPECT_TRUE(result.prepared.faces.empty());
    EXPECT_TRUE(result.accumulatedSourceForces.empty());
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ExplicitRouteRequestPreparesCallerOwnedSourceKeyedAccumulationOnly)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;

    const Valence4FaceLoopRouteRequest request =
        make_request_from_preflight(preflight, true);
    const Valence4FaceLoopRouteRequestResult result =
        evaluate_guarded_valence4_face_loop_route_request(mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.rejectionReason.empty());
    EXPECT_TRUE(result.explicitRouteRequested);
    EXPECT_TRUE(result.explicitRouteRequestAccepted);
    EXPECT_TRUE(result.sourceKeyedAccumulationExecuted);
    EXPECT_EQ(result.prepared.sourceCount, preflight.sourceCount);
    ASSERT_EQ(result.prepared.faces.size(), preflight.mappings.size());
    ASSERT_EQ(result.accumulatedSourceForces.size(),
              static_cast<std::size_t>(preflight.sourceCount));
    for (const SourceForceKinds &sourceForces :
         result.accumulatedSourceForces)
    {
        for (const Vec3 &force : sourceForces)
        {
            for (const double component : force)
            {
                EXPECT_NE(component, 0.0);
            }
        }
    }
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ExplicitRouteRequestRejectsMalformedRowsWithoutPartialOutput)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;

    Valence4FaceLoopRouteRequest request =
        make_request_from_preflight(preflight, true);
    ASSERT_FALSE(request.rows.empty());
    request.rows.back().samples[0].rows[0].sourceIds[0] =
        preflight.sourceCount + 1;

    const Valence4FaceLoopRouteRequestResult result =
        evaluate_guarded_valence4_face_loop_route_request(mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitRouteRequested);
    EXPECT_FALSE(result.explicitRouteRequestAccepted);
    EXPECT_FALSE(result.sourceKeyedAccumulationExecuted);
    EXPECT_NE(result.rejectionReason.find("out-of-range"),
              std::string::npos);
    EXPECT_TRUE(result.prepared.faces.empty());
    EXPECT_TRUE(result.accumulatedSourceForces.empty());
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ExplicitRouteRequestRejectsTooFewSamplesWithoutPartialOutput)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;

    Valence4FaceLoopRouteRequest request =
        make_request_from_preflight(preflight, true);
    ASSERT_FALSE(request.rows.empty());
    request.rows.back().samples.resize(2);

    const Valence4FaceLoopRouteRequestResult result =
        evaluate_guarded_valence4_face_loop_route_request(mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitRouteRequested);
    EXPECT_FALSE(result.explicitRouteRequestAccepted);
    EXPECT_FALSE(result.sourceKeyedAccumulationExecuted);
    EXPECT_NE(result.rejectionReason.find("exactly three samples"),
              std::string::npos);
    EXPECT_TRUE(result.prepared.faces.empty());
    EXPECT_TRUE(result.accumulatedSourceForces.empty());
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ExplicitRouteRequestRejectsTooManySamplesWithoutPartialOutput)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;

    Valence4FaceLoopRouteRequest request =
        make_request_from_preflight(preflight, true);
    ASSERT_FALSE(request.rows.empty());
    request.rows.back().samples.push_back(
        request.rows.back().samples.back());

    const Valence4FaceLoopRouteRequestResult result =
        evaluate_guarded_valence4_face_loop_route_request(mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitRouteRequested);
    EXPECT_FALSE(result.explicitRouteRequestAccepted);
    EXPECT_FALSE(result.sourceKeyedAccumulationExecuted);
    EXPECT_NE(result.rejectionReason.find("exactly three samples"),
              std::string::npos);
    EXPECT_TRUE(result.prepared.faces.empty());
    EXPECT_TRUE(result.accumulatedSourceForces.empty());
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryStagingRejectsByDefaultWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    const Valence4FaceGeometryStagingRequest request =
        make_geometry_staging_request(preflight, false);
    const Valence4FaceGeometryStagingResult result =
        stage_guarded_valence4_face_geometry(mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitStagingRequested);
    EXPECT_FALSE(result.productionGeometryEvaluated);
    EXPECT_NE(result.rejectionReason.find("default-off"),
              std::string::npos);
    EXPECT_TRUE(result.faceGeometry.empty());
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryStagingMatchesIndependentOrientedTriangleOracle)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    const Valence4FaceGeometryStagingRequest request =
        make_geometry_staging_request(preflight, true);
    const Valence4FaceGeometryStagingResult result =
        stage_guarded_valence4_face_geometry(mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitStagingRequested);
    EXPECT_TRUE(result.productionGeometryEvaluated);
    ASSERT_EQ(result.faceGeometry.size(), preflight.mappings.size());
    double expectedArea = 0.0;
    double expectedVolume = 0.0;
    for (std::size_t face = 0;
         face < preflight.mappings.size();
         ++face)
    {
        const Valence4FaceGeometry expected =
            geometry_oracle(mesh, preflight.mappings[face]);
        EXPECT_EQ(result.faceGeometry[face].faceIndex,
                  expected.faceIndex);
        EXPECT_NEAR(result.faceGeometry[face].elementArea,
                    expected.elementArea, 1.0e-14);
        EXPECT_NEAR(result.faceGeometry[face].elementVolume,
                    expected.elementVolume, 1.0e-14);
        expectedArea += expected.elementArea;
        expectedVolume += expected.elementVolume;
    }
    EXPECT_NEAR(result.totalArea, expectedArea, 1.0e-14);
    EXPECT_NEAR(result.totalVolume, expectedVolume, 1.0e-14);
    EXPECT_GT(result.totalArea, 0.0);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryStagingRejectsLateNonfiniteRowWithoutPartialOutput)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    Valence4FaceGeometryStagingRequest request =
        make_geometry_staging_request(preflight, true);
    request.rows.back().samples.back().rows[2].coefficients.back() =
        std::numeric_limits<double>::infinity();
    const Valence4FaceGeometryStagingResult result =
        stage_guarded_valence4_face_geometry(mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitStagingRequested);
    EXPECT_FALSE(result.productionGeometryEvaluated);
    EXPECT_TRUE(result.faceGeometry.empty());
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ScientificRequestRejectsByDefaultBeforeScientificAlgebra)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_mesh_owned_scientific_state(mesh);

    const Valence4FaceLoopScientificRequest request =
        make_scientific_request(preflight, false);
    const Valence4FaceLoopScientificRequestResult result =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitRouteRequested);
    EXPECT_FALSE(result.productionScientificAlgebraExecuted);
    EXPECT_NE(result.rejectionReason.find("default-off"),
              std::string::npos);
    EXPECT_TRUE(result.faceObservables.empty());
    EXPECT_FALSE(result.sourceKeyedRequest.accepted);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    expect_mesh_owned_scientific_state_unchanged(mesh);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ScientificRequestEvaluatesRealCoordinatesIntoOwnedSourceForces)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    ASSERT_EQ(mesh.param.gaussQuadratureCoeff.nrow(), 3);
    ASSERT_EQ(mesh.param.gaussQuadratureCoeff.ncol(), 1);
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_mesh_owned_scientific_state(mesh);

    const Valence4FaceLoopScientificRequest request =
        make_scientific_request(preflight, true);
    const Valence4FaceLoopScientificRequestResult result =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitRouteRequested);
    EXPECT_TRUE(result.productionScientificAlgebraExecuted);
    ASSERT_EQ(result.faceObservables.size(), mesh.faces.size());
    for (std::size_t faceIndex = 0;
         faceIndex < result.faceObservables.size();
         ++faceIndex)
    {
        const Valence4FaceScientificObservables &observables =
            result.faceObservables[faceIndex];
        EXPECT_EQ(observables.faceIndex,
                  static_cast<int>(faceIndex));
        EXPECT_TRUE(std::isfinite(observables.meanCurvature));
        EXPECT_TRUE(std::isfinite(observables.bendingEnergy));
        for (const double component : observables.normal)
        {
            EXPECT_TRUE(std::isfinite(component));
        }
    }

    ASSERT_TRUE(result.sourceKeyedRequest.accepted)
        << result.sourceKeyedRequest.rejectionReason;
    EXPECT_TRUE(
        result.sourceKeyedRequest.sourceKeyedAccumulationExecuted);
    ASSERT_EQ(
        result.sourceKeyedRequest.accumulatedSourceForces.size(),
        mesh.vertices.size());
    bool foundNonzeroForce = false;
    for (const SourceForceKinds &sourceForces :
         result.sourceKeyedRequest.accumulatedSourceForces)
    {
        for (const Vec3 &force : sourceForces)
        {
            for (const double component : force)
            {
                EXPECT_TRUE(std::isfinite(component));
                foundNonzeroForce =
                    foundNonzeroForce || component != 0.0;
            }
        }
    }
    EXPECT_TRUE(foundNonzeroForce);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    expect_mesh_owned_scientific_state_unchanged(mesh);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ScientificRequestRejectsMalformedLateRowWithoutPartialOutput)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_mesh_owned_scientific_state(mesh);

    Valence4FaceLoopScientificRequest request =
        make_scientific_request(preflight, true);
    ASSERT_FALSE(request.rows.empty());
    request.rows.back().samples.back().rows[0].sourceIds[0] =
        preflight.sourceCount + 1;
    const Valence4FaceLoopScientificRequestResult result =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitRouteRequested);
    EXPECT_FALSE(result.productionScientificAlgebraExecuted);
    EXPECT_NE(result.rejectionReason.find("out-of-range"),
              std::string::npos);
    EXPECT_TRUE(result.faceObservables.empty());
    EXPECT_FALSE(result.sourceKeyedRequest.accepted);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    expect_mesh_owned_scientific_state_unchanged(mesh);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     VertexForcePublicationRejectsByDefaultWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_all_vertex_forces(mesh);
    const auto before = capture_all_vertex_forces(mesh);

    Valence4VertexForcePublicationRequest request;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    const Valence4VertexForcePublicationResult result =
        evaluate_guarded_valence4_vertex_force_publication(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitPublicationRequested);
    EXPECT_FALSE(result.vertexForcePublicationExecuted);
    EXPECT_NE(result.rejectionReason.find("default-off"),
              std::string::npos);
    EXPECT_FALSE(result.scientificRequest.accepted);
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     VertexForcePublicationOverwritesOnlyThreeMembraneFamilies)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_all_vertex_forces(mesh);
    const auto before = capture_all_vertex_forces(mesh);

    Valence4VertexForcePublicationRequest request;
    request.reviewerApprovedExplicitPublication = true;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    const Valence4VertexForcePublicationResult result =
        evaluate_guarded_valence4_vertex_force_publication(
            mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitPublicationRequested);
    EXPECT_TRUE(result.vertexForcePublicationExecuted);
    EXPECT_TRUE(result.scientificRequest.accepted);
    EXPECT_TRUE(
        result.scientificRequest.productionScientificAlgebraExecuted);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    expect_only_membrane_forces_published(
        mesh,
        before,
        result.scientificRequest.sourceKeyedRequest
            .accumulatedSourceForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     VertexForcePublicationRejectsMalformedLateRowWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_all_vertex_forces(mesh);
    const auto before = capture_all_vertex_forces(mesh);

    Valence4VertexForcePublicationRequest request;
    request.reviewerApprovedExplicitPublication = true;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    request.rows.back().samples.back().rows[0].sourceIds[0] =
        preflight.sourceCount + 1;
    const Valence4VertexForcePublicationResult result =
        evaluate_guarded_valence4_vertex_force_publication(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitPublicationRequested);
    EXPECT_FALSE(result.vertexForcePublicationExecuted);
    EXPECT_NE(result.rejectionReason.find("out-of-range"),
              std::string::npos);
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     VertexForcePublicationPrimitiveRejectsLateDestinationDriftAtomically)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_all_vertex_forces(mesh);
    const auto before = capture_all_vertex_forces(mesh);
    std::vector<SourceForceKinds> sourceForces(mesh.vertices.size());
    for (std::size_t source = 0; source < sourceForces.size(); ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                sourceForces[source][kind][axis] =
                    100.0 * source + 10.0 * kind + axis + 0.5;
            }
        }
    }

    mesh.vertices.back().index += 1;
    EXPECT_THROW(
        publish_source_keyed_membrane_forces_to_vertices(
            sourceForces, mesh),
        std::invalid_argument);
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);

    mesh.vertices.back().index -= 1;
    sourceForces.back()[2][2] =
        std::numeric_limits<double>::infinity();
    EXPECT_THROW(
        publish_source_keyed_membrane_forces_to_vertices(
            sourceForces, mesh),
        std::invalid_argument);
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);

    sourceForces.back()[2][2] = 1.0;
    mesh.faces.back().oneRingVertices = {0};
    EXPECT_THROW(
        publish_source_keyed_membrane_forces_to_vertices(
            sourceForces, mesh),
        std::invalid_argument);
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     VertexForcePublicationPrimitiveRejectsSourceCardinalityAtomically)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_all_vertex_forces(mesh);
    seed_publication_unrelated_state(mesh);
    const auto before = capture_all_vertex_forces(mesh);
    std::vector<SourceForceKinds> sourceForces(mesh.vertices.size());

    sourceForces.pop_back();
    EXPECT_THROW(
        publish_source_keyed_membrane_forces_to_vertices(
            sourceForces, mesh),
        std::invalid_argument);
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);
    expect_publication_unrelated_state_unchanged(mesh);

    sourceForces.resize(mesh.vertices.size() + 1);
    EXPECT_THROW(
        publish_source_keyed_membrane_forces_to_vertices(
            sourceForces, mesh),
        std::invalid_argument);
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);
    expect_publication_unrelated_state_unchanged(mesh);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     VertexForcePublicationPrimitiveRejectsNullLateDestinationAtomically)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_all_vertex_forces(mesh);
    seed_publication_unrelated_state(mesh);
    const auto before = capture_all_vertex_forces(mesh);
    std::vector<SourceForceKinds> sourceForces(mesh.vertices.size());
    Matrix originalVolume = mesh.vertices.back().force.forceVolume;

    mesh.vertices.back().force.forceVolume.free();
    ASSERT_EQ(mesh.vertices.back().force.forceVolume.mat, nullptr);
    EXPECT_THROW(
        publish_source_keyed_membrane_forces_to_vertices(
            sourceForces, mesh),
        std::invalid_argument);
    EXPECT_EQ(mesh.vertices.back().force.forceVolume.mat, nullptr);

    mesh.vertices.back().force.forceVolume = originalVolume;
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);
    expect_publication_unrelated_state_unchanged(mesh);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     VertexForcePublicationPrimitiveRejectsWrongShapedLateDestinationAtomically)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_all_vertex_forces(mesh);
    seed_publication_unrelated_state(mesh);
    const auto before = capture_all_vertex_forces(mesh);
    std::vector<SourceForceKinds> sourceForces(mesh.vertices.size());
    Matrix originalVolume = mesh.vertices.back().force.forceVolume;
    Matrix wrongShapedVolume(2, 1, true);
    wrongShapedVolume.set(0, 0, 7001.25);
    wrongShapedVolume.set(1, 0, 7002.25);
    mesh.vertices.back().force.forceVolume = wrongShapedVolume;

    EXPECT_THROW(
        publish_source_keyed_membrane_forces_to_vertices(
            sourceForces, mesh),
        std::invalid_argument);
    EXPECT_EQ(mesh.vertices.back().force.forceVolume.nrow(), 2);
    EXPECT_EQ(mesh.vertices.back().force.forceVolume.ncol(), 1);
    EXPECT_DOUBLE_EQ(
        mesh.vertices.back().force.forceVolume.get(0, 0),
        7001.25);
    EXPECT_DOUBLE_EQ(
        mesh.vertices.back().force.forceVolume.get(1, 0),
        7002.25);

    mesh.vertices.back().force.forceVolume = originalVolume;
    EXPECT_EQ(capture_all_vertex_forces(mesh), before);
    expect_publication_unrelated_state_unchanged(mesh);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     FaceObservablePublicationRejectsByDefaultWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);

    Valence4FaceObservablePublicationRequest request;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    const Valence4FaceObservablePublicationResult result =
        evaluate_guarded_valence4_face_observable_publication(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitPublicationRequested);
    EXPECT_FALSE(result.faceObservablePublicationExecuted);
    EXPECT_NE(result.rejectionReason.find("default-off"),
              std::string::npos);
    EXPECT_FALSE(result.scientificRequest.accepted);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     FaceObservablePublicationOverwritesOnlyCurrentFaceObservables)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);

    Valence4FaceObservablePublicationRequest request;
    request.reviewerApprovedExplicitPublication = true;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    const Valence4FaceObservablePublicationResult result =
        evaluate_guarded_valence4_face_observable_publication(
            mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitPublicationRequested);
    EXPECT_TRUE(result.faceObservablePublicationExecuted);
    EXPECT_TRUE(result.scientificRequest.accepted);
    EXPECT_TRUE(
        result.scientificRequest.productionScientificAlgebraExecuted);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    expect_only_face_observables_published(
        mesh,
        beforeFaces,
        result.scientificRequest.faceObservables);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     FaceObservablePublicationRejectsMalformedLateRowWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);

    Valence4FaceObservablePublicationRequest request;
    request.reviewerApprovedExplicitPublication = true;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    request.rows.back().samples.back().rows[0].sourceIds[0] =
        preflight.sourceCount + 1;
    const Valence4FaceObservablePublicationResult result =
        evaluate_guarded_valence4_face_observable_publication(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitPublicationRequested);
    EXPECT_FALSE(result.faceObservablePublicationExecuted);
    EXPECT_NE(result.rejectionReason.find("out-of-range"),
              std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     FaceObservablePublicationPrimitiveRejectsLateDriftAtomically)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    std::vector<Valence4FaceScientificObservables> observables =
        make_face_observables(mesh);

    observables.pop_back();
    EXPECT_THROW(
        publish_valence4_face_scientific_observables_to_faces(
            observables, mesh),
        std::invalid_argument);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);

    observables = make_face_observables(mesh);
    observables.back().faceIndex = observables.front().faceIndex;
    EXPECT_THROW(
        publish_valence4_face_scientific_observables_to_faces(
            observables, mesh),
        std::invalid_argument);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);

    observables = make_face_observables(mesh);
    observables.back().normal.back() =
        std::numeric_limits<double>::infinity();
    EXPECT_THROW(
        publish_valence4_face_scientific_observables_to_faces(
            observables, mesh),
        std::invalid_argument);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);

    observables = make_face_observables(mesh);
    mesh.faces.back().index += 1;
    EXPECT_THROW(
        publish_valence4_face_scientific_observables_to_faces(
            observables, mesh),
        std::invalid_argument);
    mesh.faces.back().index -= 1;
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);

    mesh.faces.back().oneRingVertices = {0};
    EXPECT_THROW(
        publish_valence4_face_scientific_observables_to_faces(
            observables, mesh),
        std::invalid_argument);
    mesh.faces.back().oneRingVertices.clear();
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     FaceObservablePublicationPrimitiveUsesFaceIdentityNotInputOrder)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    std::vector<Valence4FaceScientificObservables> observables =
        make_face_observables(mesh);
    const std::vector<Valence4FaceScientificObservables> expected =
        observables;
    std::reverse(observables.begin(), observables.end());

    EXPECT_NO_THROW(
        publish_valence4_face_scientific_observables_to_faces(
            observables, mesh));
    expect_only_face_observables_published(
        mesh, beforeFaces, expected);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     AtomicFaceLoopPublicationRejectsByDefaultWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);

    Valence4FaceLoopPublicationRequest request;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    const Valence4FaceLoopPublicationResult result =
        evaluate_guarded_valence4_face_loop_publication(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitPublicationRequested);
    EXPECT_FALSE(result.vertexForcePublicationExecuted);
    EXPECT_FALSE(result.faceObservablePublicationExecuted);
    EXPECT_FALSE(result.atomicFaceLoopPublicationExecuted);
    EXPECT_NE(result.rejectionReason.find("default-off"),
              std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     AtomicFaceLoopPublicationCommitsBothReviewedFamilies)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);

    Valence4FaceLoopPublicationRequest request;
    request.reviewerApprovedExplicitPublication = true;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    const Valence4FaceLoopPublicationResult result =
        evaluate_guarded_valence4_face_loop_publication(
            mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitPublicationRequested);
    EXPECT_TRUE(result.vertexForcePublicationExecuted);
    EXPECT_TRUE(result.faceObservablePublicationExecuted);
    EXPECT_TRUE(result.atomicFaceLoopPublicationExecuted);
    ASSERT_TRUE(result.scientificRequest.accepted);
    expect_only_membrane_forces_published(
        mesh,
        beforeForces,
        result.scientificRequest.sourceKeyedRequest
            .accumulatedSourceForces);
    expect_only_face_observables_published(
        mesh,
        beforeFaces,
        result.scientificRequest.faceObservables);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     AtomicFaceLoopPublicationRejectsMalformedRowsWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);

    Valence4FaceLoopPublicationRequest request;
    request.reviewerApprovedExplicitPublication = true;
    for (const SourceMappingView &mapping : preflight.mappings)
    {
        request.rows.push_back(
            make_scientific_rows_for_mapping(mapping));
    }
    request.rows.back().samples.back().rows[0].sourceIds[0] =
        preflight.sourceCount + 1;
    const Valence4FaceLoopPublicationResult result =
        evaluate_guarded_valence4_face_loop_publication(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitPublicationRequested);
    EXPECT_FALSE(result.atomicFaceLoopPublicationExecuted);
    EXPECT_NE(result.rejectionReason.find("out-of-range"),
              std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     AtomicFaceLoopPrimitiveRejectsLateFaceDriftBeforeVertexWrites)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    const Valence4FaceLoopScientificRequest request =
        make_scientific_request(preflight, true);
    Valence4FaceLoopScientificRequestResult scientificResult =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, request);
    ASSERT_TRUE(scientificResult.accepted)
        << scientificResult.rejectionReason;

    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    scientificResult.faceObservables.back().normal.back() =
        std::numeric_limits<double>::infinity();

    EXPECT_THROW(
        publish_valence4_face_loop_scientific_result_atomically(
            scientificResult, mesh),
        std::invalid_argument);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     AtomicFaceLoopPrimitiveRejectsLateVertexDriftBeforeFaceWrites)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    const Valence4FaceLoopScientificRequest request =
        make_scientific_request(preflight, true);
    const Valence4FaceLoopScientificRequestResult scientificResult =
        evaluate_guarded_valence4_face_loop_scientific_request(
            mesh, request);
    ASSERT_TRUE(scientificResult.accepted)
        << scientificResult.rejectionReason;

    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    Matrix originalVolume = mesh.vertices.back().force.forceVolume;
    Matrix wrongShapedVolume(2, 1, true);
    wrongShapedVolume.set(0, 0, 9701.25);
    wrongShapedVolume.set(1, 0, 9702.25);
    mesh.vertices.back().force.forceVolume = wrongShapedVolume;

    EXPECT_THROW(
        publish_valence4_face_loop_scientific_result_atomically(
            scientificResult, mesh),
        std::invalid_argument);
    EXPECT_EQ(mesh.vertices.back().force.forceVolume.nrow(), 2);
    EXPECT_EQ(mesh.vertices.back().force.forceVolume.ncol(), 1);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);

    mesh.vertices.back().force.forceVolume = originalVolume;
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryAwareAtomicCompositionRejectsByDefaultWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    const Valence4GeometryAwareAtomicCompositionRequest request =
        make_geometry_aware_composition_request(preflight, false);
    const Valence4GeometryAwareAtomicCompositionResult result =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitCompositionRequested);
    EXPECT_FALSE(result.stagedGeometryUsedForScientificEvaluation);
    EXPECT_FALSE(result.geometryPublicationExecuted);
    EXPECT_FALSE(result.vertexForcePublicationExecuted);
    EXPECT_FALSE(result.faceObservablePublicationExecuted);
    EXPECT_FALSE(result.atomicGeometryScientificPublicationExecuted);
    EXPECT_NE(result.rejectionReason.find("default-off"),
              std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryAwareAtomicCompositionUsesStagedGlobalsAndCommitsAllFamilies)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported) << preflight.rejectionReason;
    mesh.param.area = 1234.5;
    mesh.param.vol = -678.25;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);

    const Valence4GeometryAwareAtomicCompositionRequest request =
        make_geometry_aware_composition_request(preflight, true);
    const Valence4GeometryAwareAtomicCompositionResult result =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitCompositionRequested);
    EXPECT_TRUE(result.stagedGeometryUsedForScientificEvaluation);
    EXPECT_TRUE(result.geometryPublicationExecuted);
    EXPECT_TRUE(result.vertexForcePublicationExecuted);
    EXPECT_TRUE(result.faceObservablePublicationExecuted);
    EXPECT_TRUE(result.atomicGeometryScientificPublicationExecuted);
    ASSERT_TRUE(result.geometryStaging.accepted);
    ASSERT_TRUE(result.scientificRequest.accepted);
    EXPECT_TRUE(
        result.scientificRequest
            .stagedGeometryUsedForScientificEvaluation);
    EXPECT_DOUBLE_EQ(
        result.scientificRequest.scientificGlobalArea,
        result.geometryStaging.totalArea);
    EXPECT_DOUBLE_EQ(
        result.scientificRequest.scientificGlobalVolume,
        result.geometryStaging.totalVolume);
    EXPECT_NE(result.scientificRequest.scientificGlobalArea, 1234.5);
    EXPECT_NE(result.scientificRequest.scientificGlobalVolume, -678.25);

    double expectedArea = 0.0;
    double expectedVolume = 0.0;
    for (std::size_t faceIndex = 0;
         faceIndex < mesh.faces.size();
         ++faceIndex)
    {
        const Valence4FaceGeometry expectedGeometry =
            geometry_oracle(mesh, preflight.mappings[faceIndex]);
        expectedArea += expectedGeometry.elementArea;
        expectedVolume += expectedGeometry.elementVolume;
        EXPECT_NEAR(mesh.faces[faceIndex].elementArea,
                    expectedGeometry.elementArea,
                    1.0e-12);
        EXPECT_NEAR(mesh.faces[faceIndex].elementVolume,
                    expectedGeometry.elementVolume,
                    1.0e-12);

        const Valence4FaceScientificObservables &observable =
            result.scientificRequest.faceObservables[faceIndex];
        EXPECT_DOUBLE_EQ(mesh.faces[faceIndex].meanCurvature,
                         observable.meanCurvature);
        EXPECT_DOUBLE_EQ(
            mesh.faces[faceIndex].energy.energyCurvature,
            observable.bendingEnergy);
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            EXPECT_DOUBLE_EQ(
                mesh.faces[faceIndex].normVector.get(axis, 0),
                observable.normal[axis]);
        }
        expect_energy_equal(mesh.faces[faceIndex].energy,
                            beforeFaces[faceIndex].energy,
                            true);
        expect_energy_equal(mesh.faces[faceIndex].energyPrev,
                            beforeFaces[faceIndex].energyPrev,
                            false);
        EXPECT_EQ(mesh.faces[faceIndex].oneRingVertices,
                  beforeFaces[faceIndex].oneRingVertices);
    }
    EXPECT_NEAR(mesh.param.area, expectedArea, 1.0e-12);
    EXPECT_NEAR(mesh.param.vol, expectedVolume, 1.0e-12);
    expect_only_membrane_forces_published(
        mesh,
        beforeForces,
        result.scientificRequest.sourceKeyedRequest
            .accumulatedSourceForces);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryAwareScientificForcesIgnoreStaleMeshGlobals)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported);
    const Valence4GeometryAwareAtomicCompositionRequest request =
        make_geometry_aware_composition_request(preflight, true);

    mesh.param.area = 1.25;
    mesh.param.vol = 0.125;
    const Valence4GeometryAwareAtomicCompositionResult firstResult =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            mesh, request);
    ASSERT_TRUE(firstResult.accepted) << firstResult.rejectionReason;

    mesh.param.area = 12.5;
    mesh.param.vol = 1.25;
    const Valence4GeometryAwareAtomicCompositionResult secondResult =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            mesh, request);
    ASSERT_TRUE(secondResult.accepted) << secondResult.rejectionReason;

    EXPECT_DOUBLE_EQ(firstResult.geometryStaging.totalArea,
                     secondResult.geometryStaging.totalArea);
    EXPECT_DOUBLE_EQ(firstResult.geometryStaging.totalVolume,
                     secondResult.geometryStaging.totalVolume);
    EXPECT_EQ(
        firstResult.scientificRequest.sourceKeyedRequest
            .accumulatedSourceForces,
        secondResult.scientificRequest.sourceKeyedRequest
            .accumulatedSourceForces);
    EXPECT_DOUBLE_EQ(
        firstResult.scientificRequest.scientificGlobalArea,
        firstResult.geometryStaging.totalArea);
    EXPECT_DOUBLE_EQ(
        secondResult.scientificRequest.scientificGlobalVolume,
        secondResult.geometryStaging.totalVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryAwareScientificEvaluationPreservesNonuniformQuadrature)
{
    ApprovedValence4MeshFixture directFixture;
    Mesh &directMesh = *directFixture.mesh;
    directMesh.param.gaussQuadratureCoeff.set(0, 0, 0.8);
    directMesh.param.gaussQuadratureCoeff.set(1, 0, 0.1);
    directMesh.param.gaussQuadratureCoeff.set(2, 0, 0.1);
    const Valence4FaceLoopRoutePreflightResult directPreflight =
        build_guarded_valence4_face_loop_route_preflight(
            directMesh);
    ASSERT_TRUE(directPreflight.supported);
    Valence4GeometryAwareAtomicCompositionRequest request =
        make_geometry_aware_composition_request(
            directPreflight, true);
    for (SourceKeyedFaceRows &faceRows : request.rows)
    {
        for (std::size_t sampleIndex = 0;
             sampleIndex < faceRows.samples.size();
             ++sampleIndex)
        {
            const double firstScale =
                1.0 + 0.25 * static_cast<double>(sampleIndex);
            const double secondScale =
                1.0 + 0.5 * static_cast<double>(sampleIndex);
            for (double &coefficient :
                 faceRows.samples[sampleIndex]
                     .rows[1].coefficients)
            {
                coefficient *= firstScale;
            }
            for (double &coefficient :
                 faceRows.samples[sampleIndex]
                     .rows[2].coefficients)
            {
                coefficient *= secondScale;
            }
        }
    }

    Valence4FaceGeometryStagingRequest geometryRequest;
    geometryRequest.reviewerApprovedExplicitStaging = true;
    geometryRequest.rows = request.rows;
    const Valence4FaceGeometryStagingResult geometry =
        stage_guarded_valence4_face_geometry(
            directMesh, geometryRequest);
    ASSERT_TRUE(geometry.accepted) << geometry.rejectionReason;
    directMesh.param.area = geometry.totalArea;
    directMesh.param.vol = geometry.totalVolume;
    Valence4FaceLoopScientificRequest scientificRequest;
    scientificRequest.reviewerApprovedExplicitRequest = true;
    scientificRequest.rows = request.rows;
    const Valence4FaceLoopScientificRequestResult expected =
        evaluate_guarded_valence4_face_loop_scientific_request(
            directMesh, scientificRequest);
    ASSERT_TRUE(expected.accepted) << expected.rejectionReason;

    ApprovedValence4MeshFixture composedFixture;
    Mesh &composedMesh = *composedFixture.mesh;
    composedMesh.param.gaussQuadratureCoeff.set(0, 0, 0.8);
    composedMesh.param.gaussQuadratureCoeff.set(1, 0, 0.1);
    composedMesh.param.gaussQuadratureCoeff.set(2, 0, 0.1);
    composedMesh.param.area = geometry.totalArea + 100.0;
    composedMesh.param.vol = geometry.totalVolume - 50.0;
    const Valence4GeometryAwareAtomicCompositionResult actual =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            composedMesh, request);
    ASSERT_TRUE(actual.accepted) << actual.rejectionReason;

    EXPECT_EQ(
        actual.scientificRequest.sourceKeyedRequest
            .accumulatedSourceForces,
        expected.sourceKeyedRequest.accumulatedSourceForces);
    ASSERT_EQ(actual.scientificRequest.faceObservables.size(),
              expected.faceObservables.size());
    for (std::size_t face = 0;
         face < expected.faceObservables.size();
         ++face)
    {
        EXPECT_EQ(actual.scientificRequest.faceObservables[face].faceIndex,
                  expected.faceObservables[face].faceIndex);
        EXPECT_DOUBLE_EQ(
            actual.scientificRequest.faceObservables[face].meanCurvature,
            expected.faceObservables[face].meanCurvature);
        EXPECT_DOUBLE_EQ(
            actual.scientificRequest.faceObservables[face].bendingEnergy,
            expected.faceObservables[face].bendingEnergy);
        EXPECT_EQ(actual.scientificRequest.faceObservables[face].normal,
                  expected.faceObservables[face].normal);
    }
    EXPECT_DOUBLE_EQ(actual.scientificRequest.scientificGlobalArea,
                     geometry.totalArea);
    EXPECT_DOUBLE_EQ(actual.scientificRequest.scientificGlobalVolume,
                     geometry.totalVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryAwareCompositionRejectsMalformedLateRowWithoutMutation)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported);
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;
    Valence4GeometryAwareAtomicCompositionRequest request =
        make_geometry_aware_composition_request(preflight, true);
    request.rows.back().samples.back().rows.back()
        .coefficients.back() =
        std::numeric_limits<double>::infinity();

    const Valence4GeometryAwareAtomicCompositionResult result =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitCompositionRequested);
    EXPECT_FALSE(result.atomicGeometryScientificPublicationExecuted);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryAwarePrimitiveRejectsLateGeometryDriftBeforeAnyWrite)
{
    ApprovedValence4MeshFixture evaluatedFixture;
    Mesh &evaluatedMesh = *evaluatedFixture.mesh;
    const Valence4FaceLoopRoutePreflightResult evaluatedPreflight =
        build_guarded_valence4_face_loop_route_preflight(
            evaluatedMesh);
    ASSERT_TRUE(evaluatedPreflight.supported);
    Valence4GeometryAwareAtomicCompositionResult staged =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            evaluatedMesh,
            make_geometry_aware_composition_request(
                evaluatedPreflight, true));
    ASSERT_TRUE(staged.accepted) << staged.rejectionReason;
    staged.geometryStaging.faceGeometry.back().elementVolume =
        std::numeric_limits<double>::infinity();

    ApprovedValence4MeshFixture targetFixture;
    Mesh &target = *targetFixture.mesh;
    seed_face_observable_publication_state(target);
    seed_all_vertex_forces(target);
    const std::vector<Face> beforeFaces = target.faces;
    const auto beforeForces = capture_all_vertex_forces(target);
    const double beforeArea = target.param.area;
    const double beforeVolume = target.param.vol;

    EXPECT_THROW(
        publish_valence4_geometry_and_scientific_result_atomically(
            staged.geometryStaging,
            staged.scientificRequest,
            target),
        std::invalid_argument);
    expect_face_observable_publication_state_unchanged(
        target, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(target), beforeForces);
    EXPECT_DOUBLE_EQ(target.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(target.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     GeometryAwarePrimitiveRejectsLateDestinationDriftBeforeAnyWrite)
{
    ApprovedValence4MeshFixture evaluatedFixture;
    Mesh &evaluatedMesh = *evaluatedFixture.mesh;
    const Valence4FaceLoopRoutePreflightResult evaluatedPreflight =
        build_guarded_valence4_face_loop_route_preflight(
            evaluatedMesh);
    ASSERT_TRUE(evaluatedPreflight.supported);
    const Valence4GeometryAwareAtomicCompositionResult staged =
        evaluate_guarded_valence4_geometry_aware_atomic_composition(
            evaluatedMesh,
            make_geometry_aware_composition_request(
                evaluatedPreflight, true));
    ASSERT_TRUE(staged.accepted) << staged.rejectionReason;

    ApprovedValence4MeshFixture targetFixture;
    Mesh &target = *targetFixture.mesh;
    seed_face_observable_publication_state(target);
    seed_all_vertex_forces(target);
    const std::vector<Face> beforeFaces = target.faces;
    const auto beforeForces = capture_all_vertex_forces(target);
    const auto beforeNormalAllocations =
        capture_face_normal_allocations(target);
    const double beforeArea = target.param.area;
    const double beforeVolume = target.param.vol;
    Matrix originalVolume =
        target.vertices.back().force.forceVolume;
    target.vertices.back().force.forceVolume =
        Matrix(2, 1, true);

    EXPECT_THROW(
        publish_valence4_geometry_and_scientific_result_atomically(
            staged.geometryStaging,
            staged.scientificRequest,
            target),
        std::invalid_argument);
    EXPECT_EQ(capture_face_normal_allocations(target),
              beforeNormalAllocations);
    EXPECT_EQ(target.vertices.back().force.forceVolume.nrow(), 2);
    EXPECT_EQ(target.vertices.back().force.forceVolume.ncol(), 1);
    expect_face_observable_publication_state_unchanged(
        target, beforeFaces);
    EXPECT_DOUBLE_EQ(target.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(target.param.vol, beforeVolume);

    target.vertices.back().force.forceVolume = originalVolume;
    EXPECT_EQ(capture_all_vertex_forces(target), beforeForces);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ProductionCallerShadowRejectsBeforeClearingCurrentState)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported);
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    Valence4ProductionCallerShadowRequest request =
        make_production_caller_shadow_request(preflight, true);
    request.rows.back().samples.back().rows.back()
        .coefficients.back() =
        std::numeric_limits<double>::infinity();
    const Valence4ProductionCallerShadowResult malformed =
        evaluate_guarded_valence4_production_caller_shadow(
            mesh, request);

    EXPECT_FALSE(malformed.accepted);
    EXPECT_TRUE(malformed.explicitShadowRequested);
    EXPECT_FALSE(malformed.currentStateCleared);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ProductionCallerShadowRejectsMalformedCompletionDestinationBeforeClear)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported);
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.coordRef = vertex.coord;
    }
    Matrix malformedRegularization(4, 1, true);
    for (int row = 0; row < 4; ++row)
    {
        malformedRegularization.set(row, 0, 9000.0 + row);
    }
    mesh.vertices.back().force.forceRegularization =
        malformedRegularization;
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    const Valence4ProductionCallerShadowResult malformed =
        evaluate_guarded_valence4_production_caller_shadow(
            mesh,
            make_production_caller_shadow_request(
                preflight, true));

    EXPECT_FALSE(malformed.accepted);
    EXPECT_TRUE(malformed.explicitShadowRequested);
    EXPECT_FALSE(malformed.currentStateCleared);
    EXPECT_NE(malformed.rejectionReason.find("destination shape drift"),
              std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_EQ(
        mesh.vertices.back().force.forceRegularization.nrow(), 4);
    EXPECT_EQ(
        mesh.vertices.back().force.forceRegularization.ncol(), 1);
    EXPECT_DOUBLE_EQ(
        mesh.vertices.back().force.forceRegularization.get(3, 0),
        9003.0);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ProductionCallerShadowRejectsMalformedReferenceShapeBeforeClear)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported);
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.coordRef = vertex.coord;
    }
    Matrix malformedReference(2, 1, true);
    malformedReference.set(0, 0, 7100.0);
    malformedReference.set(1, 0, 7101.0);
    mesh.vertices.back().coordRef = malformedReference;
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    const Valence4ProductionCallerShadowResult malformed =
        evaluate_guarded_valence4_production_caller_shadow(
            mesh,
            make_production_caller_shadow_request(
                preflight, true));

    EXPECT_FALSE(malformed.accepted);
    EXPECT_TRUE(malformed.explicitShadowRequested);
    EXPECT_FALSE(malformed.currentStateCleared);
    EXPECT_NE(
        malformed.rejectionReason.find(
            "reference coordinate shape drift"),
        std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_EQ(mesh.vertices.back().coordRef.nrow(), 2);
    EXPECT_EQ(mesh.vertices.back().coordRef.ncol(), 1);
    EXPECT_DOUBLE_EQ(
        mesh.vertices.back().coordRef.get(1, 0), 7101.0);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ProductionCallerShadowRejectsNonfiniteReferenceBeforeClear)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported);
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.coordRef = vertex.coord;
    }
    mesh.vertices.back().coordRef.set(
        2, 0, std::numeric_limits<double>::infinity());
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    const Valence4ProductionCallerShadowResult malformed =
        evaluate_guarded_valence4_production_caller_shadow(
            mesh,
            make_production_caller_shadow_request(
                preflight, true));

    EXPECT_FALSE(malformed.accepted);
    EXPECT_TRUE(malformed.explicitShadowRequested);
    EXPECT_FALSE(malformed.currentStateCleared);
    EXPECT_NE(
        malformed.rejectionReason.find(
            "nonfinite reference coordinate"),
        std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_TRUE(std::isinf(
        mesh.vertices.back().coordRef.get(2, 0)));
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     ProductionCallerShadowRunsExactCompletionPhasesWithRouteDisabled)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const Valence4FaceLoopRoutePreflightResult preflight =
        build_guarded_valence4_face_loop_route_preflight(mesh);
    ASSERT_TRUE(preflight.supported);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.coordRef = vertex.coord;
    }
    for (Face &face : mesh.faces)
    {
        face.energy.energyThickness = 7000.0 + face.index;
    }
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.force.forceThickness.set_all(
            8000.0 + vertex.index);
    }

    const Valence4ProductionCallerShadowResult result =
        evaluate_guarded_valence4_production_caller_shadow(
            mesh,
            make_production_caller_shadow_request(
                preflight, true));

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitShadowRequested);
    EXPECT_TRUE(result.currentStateCleared);
    EXPECT_TRUE(result.geometryAwareAtomicCompositionExecuted);
    EXPECT_TRUE(result.productionCompletionPhasesExecuted);
    EXPECT_TRUE(result.totalForcePublicationExecuted);
    EXPECT_TRUE(result.totalEnergyPublicationExecuted);
    EXPECT_TRUE(result.boundaryHandlingExecuted);
    EXPECT_TRUE(result.composition.accepted);
    EXPECT_TRUE(
        result.composition
            .atomicGeometryScientificPublicationExecuted);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);

    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            EXPECT_DOUBLE_EQ(
                vertex.force.forceThickness.get(axis, 0), 0.0);
            const double expectedTotal =
                vertex.force.forceCurvature.get(axis, 0) +
                vertex.force.forceArea.get(axis, 0) +
                vertex.force.forceVolume.get(axis, 0) +
                vertex.force.forceThickness.get(axis, 0) +
                vertex.force.forceTilt.get(axis, 0) +
                vertex.force.forceRegularization.get(axis, 0) +
                vertex.force.forceHarmonicBond.get(axis, 0);
            EXPECT_DOUBLE_EQ(
                vertex.force.forceTotal.get(axis, 0),
                expectedTotal);
        }
    }

    Energy expectedTotalEnergy;
    for (const Face &face : mesh.faces)
    {
        EXPECT_DOUBLE_EQ(face.energy.energyThickness, 0.0);
        Energy expectedFace = face.energy;
        expectedFace.calculateTotalEnergy();
        EXPECT_DOUBLE_EQ(
            face.energy.energyTotal,
            expectedFace.energyTotal);
        expectedTotalEnergy += face.energy;
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
    expectedTotalEnergy.energyArea =
        0.5 * mesh.param.uSurf / mesh.param.area0 *
        std::pow(mesh.param.area - mesh.param.area0, 2.0);
    expectedTotalEnergy.energyVolume =
        0.5 * mesh.param.uVol / mesh.param.vol0 *
        std::pow(mesh.param.vol - mesh.param.vol0, 2.0);
    expectedTotalEnergy.calculateTotalEnergy();
    expect_energy_equal(
        mesh.param.energy, expectedTotalEnergy, false);
}

TEST(ValenceFourFaceLoopRoutePreflight,
     OpenSubdivProductionCallerRemainsDefaultOff)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    const Valence4OpenSubdivProductionCallerResult result =
        evaluate_guarded_valence4_opensubdiv_production_caller(
            mesh, {});

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitCallerRequested);
    EXPECT_FALSE(result.opensubdivRowProviderExecuted);
    EXPECT_FALSE(result.opensubdivRowsGenerated);
    EXPECT_FALSE(result.productionCallerShadowExecuted);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}

#ifndef USE_OPENSUBDIV_REGULAR
TEST(ValenceFourFaceLoopRoutePreflight,
     OpenSubdivProductionCallerRejectsExplicitRequestWithoutDependency)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    seed_reference_coordinates_from_current(mesh);
    seed_face_observable_publication_state(mesh);
    seed_all_vertex_forces(mesh);
    const std::vector<Face> beforeFaces = mesh.faces;
    const auto beforeForces = capture_all_vertex_forces(mesh);
    const double beforeArea = mesh.param.area;
    const double beforeVolume = mesh.param.vol;

    Valence4OpenSubdivProductionCallerRequest request;
    request.reviewerApprovedExplicitCaller = true;
    const Valence4OpenSubdivProductionCallerResult result =
        evaluate_guarded_valence4_opensubdiv_production_caller(
            mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.explicitCallerRequested);
    EXPECT_TRUE(result.opensubdivRowProviderExecuted);
    EXPECT_FALSE(result.opensubdivRowsGenerated);
    EXPECT_FALSE(result.productionCallerShadowExecuted);
    EXPECT_FALSE(result.rowProvider.accepted);
    EXPECT_TRUE(result.rowProvider.explicitRequestReceived);
    EXPECT_FALSE(result.rowProvider.opensubdivCompiled);
    EXPECT_TRUE(result.rowProvider.rows.empty());
    EXPECT_FALSE(result.callerShadow.accepted);
    EXPECT_NE(result.rejectionReason.find("OpenSubdiv-enabled build"),
              std::string::npos);
    expect_face_observable_publication_state_unchanged(
        mesh, beforeFaces);
    EXPECT_EQ(capture_all_vertex_forces(mesh), beforeForces);
    EXPECT_DOUBLE_EQ(mesh.param.area, beforeArea);
    EXPECT_DOUBLE_EQ(mesh.param.vol, beforeVolume);
}
#else
TEST(ValenceFourFaceLoopRoutePreflight,
     OpenSubdivProductionCallerRunsProviderFedCompletionShadow)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);
    seed_reference_coordinates_from_current(mesh);
    for (Face &face : mesh.faces)
    {
        face.energy.energyThickness = 7000.0 + face.index;
    }
    for (Vertex &vertex : mesh.vertices)
    {
        vertex.force.forceThickness.set_all(
            8000.0 + vertex.index);
    }

    Valence4OpenSubdivProductionCallerRequest request;
    request.reviewerApprovedExplicitCaller = true;
    const Valence4OpenSubdivProductionCallerResult result =
        evaluate_guarded_valence4_opensubdiv_production_caller(
            mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.explicitCallerRequested);
    EXPECT_TRUE(result.opensubdivRowProviderExecuted);
    EXPECT_TRUE(result.opensubdivRowsGenerated);
    EXPECT_TRUE(result.rowProvider.accepted);
    EXPECT_TRUE(result.rowProvider.rowsGenerated);
    EXPECT_TRUE(result.productionCallerShadowExecuted);
    EXPECT_TRUE(result.productionCompletionPhasesExecuted);
    EXPECT_TRUE(result.totalForcePublicationExecuted);
    EXPECT_TRUE(result.totalEnergyPublicationExecuted);
    EXPECT_TRUE(result.boundaryHandlingExecuted);
    EXPECT_TRUE(result.callerShadow.accepted);
    EXPECT_TRUE(result.callerShadow.currentStateCleared);
    EXPECT_TRUE(
        result.callerShadow.composition
            .atomicGeometryScientificPublicationExecuted);
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    EXPECT_FALSE(result.rowProvider.productionRouteEnabled);
    EXPECT_FALSE(result.callerShadow.productionRouteEnabled);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);

    for (const Vertex &vertex : mesh.vertices)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            EXPECT_DOUBLE_EQ(
                vertex.force.forceThickness.get(axis, 0), 0.0);
            const double expectedTotal =
                vertex.force.forceCurvature.get(axis, 0) +
                vertex.force.forceArea.get(axis, 0) +
                vertex.force.forceVolume.get(axis, 0) +
                vertex.force.forceThickness.get(axis, 0) +
                vertex.force.forceTilt.get(axis, 0) +
                vertex.force.forceRegularization.get(axis, 0) +
                vertex.force.forceHarmonicBond.get(axis, 0);
            EXPECT_DOUBLE_EQ(
                vertex.force.forceTotal.get(axis, 0),
                expectedTotal);
        }
    }
    for (const Face &face : mesh.faces)
    {
        EXPECT_DOUBLE_EQ(face.energy.energyThickness, 0.0);
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}
#endif

TEST(ValenceFourFaceLoopRoutePreflight,
     OpenSubdivRowProviderRemainsDefaultOff)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);

    const auto result =
        slimed::opensubdiv_valence4::
            build_guarded_opensubdiv_valence4_rows(
                mesh, {});

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.explicitRequestReceived);
    EXPECT_FALSE(result.rowsGenerated);
    EXPECT_TRUE(result.rows.empty());
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

#ifndef USE_OPENSUBDIV_REGULAR
TEST(ValenceFourFaceLoopRoutePreflight,
     OpenSubdivRowProviderRejectsExplicitRequestWithoutDependency)
{
    ApprovedValence4MeshFixture fixture;
    slimed::opensubdiv_valence4::
        OpenSubdivValence4RowProviderRequest request;
    request.reviewerApprovedExplicitRequest = true;

    const auto result =
        slimed::opensubdiv_valence4::
            build_guarded_opensubdiv_valence4_rows(
                *fixture.mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_FALSE(result.opensubdivCompiled);
    EXPECT_TRUE(result.explicitRequestReceived);
    EXPECT_FALSE(result.rowsGenerated);
    EXPECT_TRUE(result.rows.empty());
    EXPECT_NE(result.rejectionReason.find("OpenSubdiv-enabled build"),
              std::string::npos);
}
#else
TEST(ValenceFourFaceLoopRoutePreflight,
     OpenSubdivRowProviderReturnsCompleteApprovedPackage)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);
    slimed::opensubdiv_valence4::
        OpenSubdivValence4RowProviderRequest request;
    request.reviewerApprovedExplicitRequest = true;

    const auto result =
        slimed::opensubdiv_valence4::
            build_guarded_opensubdiv_valence4_rows(
                mesh, request);

    ASSERT_TRUE(result.accepted) << result.rejectionReason;
    EXPECT_TRUE(result.opensubdivCompiled);
    EXPECT_TRUE(result.explicitRequestReceived);
    EXPECT_TRUE(result.topologySourceMappingValidated);
    EXPECT_TRUE(result.ptexFaceIdentityValidated);
    EXPECT_TRUE(result.exactSamplePlanValidated);
    EXPECT_TRUE(result.exactSourceCoverageValidated);
    EXPECT_TRUE(result.doublePrecisionRowsGenerated);
    EXPECT_TRUE(result.constantFieldInvariantsValidated);
    EXPECT_TRUE(result.mixedDerivativeRowsDuplicated);
    EXPECT_TRUE(result.rowsGenerated);
    ASSERT_EQ(result.rows.size(), 8u);
    for (std::size_t face = 0; face < result.rows.size(); ++face)
    {
        const SourceKeyedFaceRows &faceRows = result.rows[face];
        EXPECT_EQ(faceRows.faceIndex, static_cast<int>(face));
        ASSERT_EQ(faceRows.samples.size(), 3u);
        for (const SourceKeyedSampleRows &sample :
             faceRows.samples)
        {
            for (int rowIndex = 0;
                 rowIndex < kDerivativeRowCount;
                 ++rowIndex)
            {
                const SourceKeyedRow &row =
                    sample.rows[rowIndex];
                EXPECT_EQ(row.sourceIds,
                          (std::vector<int>{0, 1, 2, 3, 4, 5}));
                ASSERT_EQ(row.coefficients.size(), 6u);
                double coefficientSum = 0.0;
                for (const double coefficient : row.coefficients)
                {
                    EXPECT_TRUE(std::isfinite(coefficient));
                    coefficientSum += coefficient;
                }
                EXPECT_NEAR(
                    coefficientSum,
                    rowIndex == 0 ? 1.0 : 0.0,
                    1.0e-12);
            }
            EXPECT_EQ(sample.rows[5].sourceIds,
                      sample.rows[6].sourceIds);
            EXPECT_EQ(sample.rows[5].coefficients,
                      sample.rows[6].coefficients);
        }
    }
    EXPECT_FALSE(result.productionRouteEnabled);
    EXPECT_FALSE(result.actualProductionForcePathExecuted);
    EXPECT_FALSE(result.productionFaceLoopExecuted);
    EXPECT_FALSE(result.productionOneRingsPopulated);
    EXPECT_FALSE(result.defaultEvaluatorCaller);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}

TEST(ValenceFourFaceLoopRoutePreflight,
     OpenSubdivRowProviderRejectsTopologyDriftAtomically)
{
    ApprovedValence4MeshFixture fixture;
    Mesh &mesh = *fixture.mesh;
    std::swap(mesh.faces[0].adjacentVertices[1],
              mesh.faces[0].adjacentVertices[2]);
    const auto beforeCoordinates = capture_vertex_coordinates(mesh);
    const std::vector<int> beforeOrientation =
        mesh.faces[0].adjacentVertices;
    slimed::opensubdiv_valence4::
        OpenSubdivValence4RowProviderRequest request;
    request.reviewerApprovedExplicitRequest = true;

    const auto result =
        slimed::opensubdiv_valence4::
            build_guarded_opensubdiv_valence4_rows(
                mesh, request);

    EXPECT_FALSE(result.accepted);
    EXPECT_TRUE(result.opensubdivCompiled);
    EXPECT_TRUE(result.explicitRequestReceived);
    EXPECT_FALSE(result.rowsGenerated);
    EXPECT_TRUE(result.rows.empty());
    EXPECT_NE(result.rejectionReason.find("canonical face orientation"),
              std::string::npos);
    EXPECT_EQ(capture_vertex_coordinates(mesh), beforeCoordinates);
    EXPECT_EQ(mesh.faces[0].adjacentVertices, beforeOrientation);
    for (const Face &face : mesh.faces)
    {
        EXPECT_TRUE(face.oneRingVertices.empty());
    }
}
#endif
