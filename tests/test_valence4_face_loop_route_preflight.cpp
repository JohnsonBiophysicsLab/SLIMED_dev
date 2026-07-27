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
