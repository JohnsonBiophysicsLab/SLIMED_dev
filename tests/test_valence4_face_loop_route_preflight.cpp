#include <algorithm>
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

Mesh make_approved_valence4_mesh()
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;

    const auto verticesData = read_data_from_csv<double>(
        "./data/fixtures/candidates/closed_valence4_octahedron/vertices.csv");
    const auto facesData = read_data_from_csv<int>(
        "./data/fixtures/candidates/closed_valence4_octahedron/faces.csv");
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(verticesData, facesData);
    return mesh;
}

SourceKeyedFaceRows make_rows_for_mapping(
    const SourceMappingView &mapping)
{
    SourceKeyedFaceRows rows;
    rows.faceIndex = mapping.faceIndex;
    rows.orientedFaceVertices = mapping.orientedFaceVertices;
    rows.samples.resize(1);

    std::vector<int> reversedSourceIds = mapping.originalSourceIds;
    std::reverse(reversedSourceIds.begin(), reversedSourceIds.end());
    for (int rowIndex = 0; rowIndex < kDerivativeRowCount; ++rowIndex)
    {
        SourceKeyedRow &row = rows.samples[0].rows[rowIndex];
        row.sourceIds = reversedSourceIds;
        row.coefficients.reserve(reversedSourceIds.size());
        const double rowBase =
            rowIndex >= 5 ? 5.0 : static_cast<double>(rowIndex);
        for (const int sourceId : reversedSourceIds)
        {
            row.coefficients.push_back(
                rowBase +
                0.01 * static_cast<double>(mapping.faceIndex + 1) +
                0.001 * static_cast<double>(sourceId + 1));
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
} // namespace

TEST(ValenceFourFaceLoopRoutePreflight,
     ApprovedOctahedronBuildsInertSourceKeyedRouteCandidate)
{
    Mesh mesh = make_approved_valence4_mesh();
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
    Mesh mesh = make_approved_valence4_mesh();
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
    Mesh mesh = make_approved_valence4_mesh();
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
