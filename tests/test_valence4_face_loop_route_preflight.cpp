#include <algorithm>
#include <cmath>
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
