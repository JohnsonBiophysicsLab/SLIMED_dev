#include "cuda/Cuda_mesh_pack.hpp"
#include "cuda/detail/Cuda_regular_membrane_cpu.hpp"
#include "mesh/Mesh.hpp"

#include <gtest/gtest.h>

#include <cmath>
#include <vector>

namespace
{
using namespace slimed::cuda_residency;
using namespace slimed::cuda_residency::detail;

TEST(CudaRegularMembraneCpuTest,
     PackedOracleMatchesProductionRegularFormulaAtEveryOutputLevel)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;
    param.kCurv = 2.75;
    param.uSurf = 1.25;
    param.uVol = 0.85;
    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();
    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index);
        vertex.coord.set(2, 0, 0.015 * std::sin(0.31 * index) +
                                   0.006 * std::cos(0.73 * index));
        vertex.coordPrev = vertex.coord;
        vertex.coordRef = vertex.coord;
    }
    mesh.calculate_element_area_volume();

    RegularMeshPackRequest request;
    request.generations = {1, 1, 1, 1, 1};
    const RegularMeshPackResult packed =
        build_regular_mesh_pack(mesh, request);
    ASSERT_TRUE(packed.ok()) << packed.error.message;
    const RegularMembraneCpuResult oracle = evaluate_regular_membrane_cpu(
        packed.pack, packed.pack.acceptedCoordinates);
    ASSERT_TRUE(oracle.ok()) << oracle.message;

    ASSERT_EQ(oracle.occurrenceForces.size(),
              packed.pack.evaluatedFaceCount * kRegularControlCount * 9U);
    ASSERT_EQ(oracle.sampleSurfaceMeasures.size(),
              packed.pack.evaluatedFaceCount * kQuadratureSampleCount);
    for (std::size_t evaluated = 0;
         evaluated < static_cast<std::size_t>(packed.pack.evaluatedFaceCount);
         ++evaluated)
    {
        Face &face = mesh.faces[static_cast<std::size_t>(
            packed.pack.evaluatedFaceIds[evaluated])];
        std::vector<Matrix> coordinates;
        coordinates.reserve(face.oneRingVertices.size());
        for (const int source : face.oneRingVertices)
            coordinates.push_back(mesh.vertices[source].coord);
        double meanCurvature = 0.0;
        double bendingEnergy = 0.0;
        Matrix normal = mat_calloc(3, 1);
        Matrix bending = mat_calloc(kRegularControlCount, 3);
        Matrix area = mat_calloc(kRegularControlCount, 3);
        Matrix volume = mat_calloc(kRegularControlCount, 3);
        mesh.element_energy_force_regular(
            coordinates, face, face.spontCurvature, meanCurvature, normal,
            bendingEnergy, bending, area, volume, true);

        EXPECT_NEAR(oracle.faceBendingEnergies[face.index], bendingEnergy,
                    1.0e-11);
        EXPECT_NEAR(oracle.faceMeanCurvatures[face.index], meanCurvature,
                    1.0e-11);
        for (std::size_t axis = 0; axis < 3; ++axis)
            EXPECT_NEAR(oracle.faceNormals[face.index * 3 + axis],
                        normal.get(static_cast<int>(axis), 0), 1.0e-11);
        for (std::size_t local = 0; local < kRegularControlCount; ++local)
        {
            const std::size_t base =
                (evaluated * kRegularControlCount + local) * 9U;
            for (std::size_t axis = 0; axis < 3; ++axis)
            {
                EXPECT_NEAR(oracle.occurrenceForces[base + axis],
                            bending.get(static_cast<int>(local),
                                        static_cast<int>(axis)),
                            1.0e-10);
                EXPECT_NEAR(oracle.occurrenceForces[base + 3 + axis],
                            area.get(static_cast<int>(local),
                                     static_cast<int>(axis)),
                            1.0e-10);
                EXPECT_NEAR(oracle.occurrenceForces[base + 6 + axis],
                            volume.get(static_cast<int>(local),
                                       static_cast<int>(axis)),
                            1.0e-10);
            }
        }
    }
}

TEST(CudaRegularMembraneCpuTest, DegenerateSamplesReturnStructuredStatus)
{
    RegularMeshPack pack;
    pack.vertexCount = kRegularControlCount;
    pack.faceCount = 1;
    pack.evaluatedFaceCount = 1;
    pack.evaluatedFaceIds = {0};
    pack.oneRingSourceIds.resize(kRegularControlCount);
    for (std::size_t local = 0; local < kRegularControlCount; ++local)
        pack.oneRingSourceIds[local] = static_cast<std::int32_t>(local);
    pack.evaluatedFaceSpontaneousCurvature = {0.0};
    pack.quadratureCoefficients.assign(kQuadratureSampleCount, 1.0 / 3.0);
    pack.shapeWeights.assign(kQuadratureSampleCount * kShapeRowCount *
                                 kRegularControlCount,
                             0.0);
    const std::vector<double> coordinates(kRegularControlCount * 3U, 2.0);
    const RegularMembraneCpuResult result =
        evaluate_regular_membrane_cpu(pack, coordinates);
    EXPECT_FALSE(result.ok());
    EXPECT_EQ(result.status, RegularMembraneStatus::DegenerateSample);
    EXPECT_EQ(result.failedEvaluatedFace, 0u);
    EXPECT_EQ(result.failedSample, 0u);
}

} // namespace
