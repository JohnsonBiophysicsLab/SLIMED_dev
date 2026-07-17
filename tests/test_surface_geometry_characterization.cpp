#include <array>
#include <algorithm>
#include <cstdlib>
#include <cmath>
#include <string>
#include <stdexcept>
#include <vector>

#include <gtest/gtest.h>

#include "Parameters.hpp"
#include "mesh/Gauss_quadrature.hpp"
#include "mesh/Limit_surface_evaluator.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_regular_evaluator.hpp"

namespace
{
constexpr double kTolerance = 1.0e-12;

class ScopedEnvVar
{
public:
    ScopedEnvVar(const char *name, const char *value)
        : name_(name)
    {
        const char *previous = std::getenv(name_);
        if (previous != nullptr)
        {
            hadPrevious_ = true;
            previous_ = previous;
        }
        if (value == nullptr)
        {
            unsetenv(name_);
        }
        else
        {
            setenv(name_, value, 1);
        }
    }

    ~ScopedEnvVar()
    {
        if (hadPrevious_)
        {
            setenv(name_, previous_.c_str(), 1);
        }
        else
        {
            unsetenv(name_);
        }
    }

private:
    const char *name_;
    bool hadPrevious_ = false;
    std::string previous_;
};

double row_sum(const Matrix &matrix, const int row)
{
    double sum = 0.0;
    for (int col = 0; col < matrix.ncol(); ++col)
    {
        sum += matrix.get(row, col);
    }
    return sum;
}

double column_sum(const Matrix &matrix, const int col)
{
    double sum = 0.0;
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        sum += matrix.get(row, col);
    }
    return sum;
}

int count_ghost_vertices(const Mesh &mesh)
{
    int count = 0;
    for (const Vertex &vertex : mesh.vertices)
    {
        if (vertex.isGhost)
        {
            ++count;
        }
    }
    return count;
}

int count_ghost_faces(const Mesh &mesh)
{
    int count = 0;
    for (const Face &face : mesh.faces)
    {
        if (face.isGhost)
        {
            ++count;
        }
    }
    return count;
}

void expect_row_stochastic(const Matrix &matrix)
{
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        SCOPED_TRACE(row);
        EXPECT_NEAR(row_sum(matrix, row), 1.0, kTolerance);
        for (int col = 0; col < matrix.ncol(); ++col)
        {
            EXPECT_GE(matrix.get(row, col), -kTolerance);
        }
    }
}

void expect_selection_rows(const Matrix &matrix)
{
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        int selectedColumnCount = 0;
        for (int col = 0; col < matrix.ncol(); ++col)
        {
            const double value = matrix.get(row, col);
            if (std::abs(value) > kTolerance)
            {
                ++selectedColumnCount;
                EXPECT_NEAR(value, 1.0, kTolerance);
            }
        }
        EXPECT_EQ(selectedColumnCount, 1);
    }
}

Matrix make_deterministic_regular_control_points()
{
    Matrix controlPoints(12, 3, true);
    for (int control = 0; control < controlPoints.nrow(); ++control)
    {
        controlPoints.set(control, 0, 0.25 + 0.5 * control);
        controlPoints.set(control, 1, -1.0 + 0.125 * control * control);
        controlPoints.set(control, 2, 2.0 - 0.2 * control);
    }
    return controlPoints;
}

std::vector<Matrix> make_regular_energy_force_control_point_fixtures()
{
    Matrix flat(12, 3, true);
    Matrix gentlyCurved(12, 3, true);
    Matrix mixedSign(12, 3, true);
    Matrix anisotropic(12, 3, true);
    for (int control = 0; control < 12; ++control)
    {
        const double index = static_cast<double>(control);

        flat.set(control, 0, 0.2 + 0.35 * index);
        flat.set(control, 1, -0.4 + 0.08 * index * index);
        flat.set(control, 2, 0.0);

        gentlyCurved.set(control, 0, 0.2 + 0.35 * index);
        gentlyCurved.set(control, 1, -0.4 + 0.08 * index * index);
        gentlyCurved.set(control, 2, 0.1 * std::sin(0.5 * index));

        mixedSign.set(control, 0, -1.5 + 0.17 * index * index);
        mixedSign.set(control, 1, 2.0 - 0.31 * index);
        mixedSign.set(control, 2, -0.75 + 0.04 * index * index * index);

        anisotropic.set(control, 0, 4.0 + std::cos(0.25 * index));
        anisotropic.set(control, 1, -3.0 + std::sin(0.3 * index));
        anisotropic.set(control, 2, 1.0 + 0.125 * index);
    }

    return {flat, gentlyCurved, mixedSign, anisotropic};
}

void expect_column_matches_row(const Matrix &column,
                               const Matrix &rows,
                               const int row)
{
    ASSERT_EQ(column.nrow(), 3);
    ASSERT_EQ(column.ncol(), 1);
    ASSERT_EQ(rows.ncol(), 3);
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_DOUBLE_EQ(column.get(axis, 0), rows.get(row, axis));
    }
}

void expect_matrix_exactly_matches(const Matrix &expected,
                                   const Matrix &actual)
{
    ASSERT_EQ(actual.nrow(), expected.nrow());
    ASSERT_EQ(actual.ncol(), expected.ncol());
    for (int row = 0; row < expected.nrow(); ++row)
    {
        for (int col = 0; col < expected.ncol(); ++col)
        {
            EXPECT_DOUBLE_EQ(actual.get(row, col), expected.get(row, col))
                << "row " << row << " col " << col;
        }
    }
}

void expect_evaluation_matches_rows(const LimitSurfaceEvaluation &evaluation,
                                    const Matrix &directRows)
{
    expect_column_matches_row(evaluation.position,
                              directRows,
                              static_cast<int>(LimitSurfaceDerivativeRow::Position));
    expect_column_matches_row(evaluation.firstDerivativeV,
                              directRows,
                              static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeV));
    expect_column_matches_row(evaluation.firstDerivativeW,
                              directRows,
                              static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeW));
    expect_column_matches_row(evaluation.secondDerivativeVV,
                              directRows,
                              static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeVV));
    expect_column_matches_row(evaluation.secondDerivativeWW,
                              directRows,
                              static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeWW));
    expect_column_matches_row(evaluation.mixedDerivativeVW,
                              directRows,
                              static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeVW));
    expect_column_matches_row(evaluation.mixedDerivativeWV,
                              directRows,
                              static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeWV));
}

void expect_column_near_values(const Matrix &column,
                               const std::array<double, 3> &expected,
                               const double tolerance)
{
    ASSERT_EQ(column.nrow(), 3);
    ASSERT_EQ(column.ncol(), 1);
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_NEAR(column.get(axis, 0), expected[axis], tolerance)
            << "axis " << axis;
    }
}

std::array<double, 3> column_to_array(const Matrix &column)
{
    return {column.get(0, 0), column.get(1, 0), column.get(2, 0)};
}

std::array<double, 3> cross_array(const std::array<double, 3> &lhs,
                                  const std::array<double, 3> &rhs)
{
    return {
        lhs[1] * rhs[2] - lhs[2] * rhs[1],
        lhs[2] * rhs[0] - lhs[0] * rhs[2],
        lhs[0] * rhs[1] - lhs[1] * rhs[0],
    };
}

double norm_array(const std::array<double, 3> &values)
{
    return std::sqrt(values[0] * values[0] +
                     values[1] * values[1] +
                     values[2] * values[2]);
}

std::array<double, 3> normalized_array(const std::array<double, 3> &values)
{
    const double norm = norm_array(values);
    return {values[0] / norm, values[1] / norm, values[2] / norm};
}

Matrix make_regular_lattice_probe_control_points()
{
    constexpr int n = 6;
    const auto vertex_id = [](const int i, const int j) {
        return j * 7 + i;
    };
    const std::vector<int> oneRing = {
        vertex_id(2, 1),
        vertex_id(1, 2),
        vertex_id(3, 1),
        vertex_id(2, 2),
        vertex_id(1, 3),
        vertex_id(4, 1),
        vertex_id(3, 2),
        vertex_id(2, 3),
        vertex_id(1, 4),
        vertex_id(4, 2),
        vertex_id(3, 3),
        vertex_id(2, 4),
    };

    Matrix controlPoints(12, 3, true);
    for (int row = 0; row < static_cast<int>(oneRing.size()); ++row)
    {
        const int vertex = oneRing[row];
        const int i = vertex % (n + 1);
        const int j = vertex / (n + 1);
        controlPoints.set(row, 0, static_cast<double>(i) + 0.5 * static_cast<double>(j));
        controlPoints.set(row, 1, std::sqrt(3.0) / 2.0 * static_cast<double>(j));
        controlPoints.set(row, 2, 0.03 * std::sin(0.7 * static_cast<double>(i + j)));
    }
    return controlPoints;
}

struct AreaVolume
{
    double area = 0.0;
    double volume = 0.0;
};

constexpr double kLegacyVolumeQuadratureFactor = 0.16666666666;

Matrix make_one_ring_control_points(const Mesh &mesh, const Face &face)
{
    Matrix controlPoints(face.oneRingVertices.size(), 3, true);
    for (int row = 0; row < controlPoints.nrow(); ++row)
    {
        const Matrix &coord = mesh.vertices[face.oneRingVertices[row]].coord;
        for (int axis = 0; axis < controlPoints.ncol(); ++axis)
        {
            controlPoints.set(row, axis, coord(axis, 0));
        }
    }
    return controlPoints;
}

AreaVolume direct_regular_patch_area_volume(const Param &param,
                                            const Matrix &controlPoints)
{
    AreaVolume result;
    for (int i = 0; i < param.shapeFunctions.size(); ++i)
    {
        const Matrix &sf = param.shapeFunctions[i];
        Matrix x = sf.get_row(0) * controlPoints;
        Matrix a_3 = cross_row(sf.get_row(1) * controlPoints,
                               sf.get_row(2) * controlPoints);
        const double sqa = a_3.calculate_norm();
        const double coeff = param.gaussQuadratureCoeff(i, 0);
        result.area += 0.5 * coeff * sqa;
        result.volume += kLegacyVolumeQuadratureFactor * coeff * dot_row(x, a_3);
    }
    return result;
}

AreaVolume direct_irregular_patch_area_volume(const Param &param,
                                              const Matrix &controlPoints)
{
    AreaVolume result;
    Matrix carriedIrregularPatch = controlPoints;

    for (int depth = 0; depth < param.subDivideTimes; ++depth)
    {
        Matrix subdividedNodes = param.subMatrix.irregM * carriedIrregularPatch;

        const std::vector<Matrix> regularSubpatches = {
            param.subMatrix.irregM1 * subdividedNodes,
            param.subMatrix.irregM2 * subdividedNodes,
            param.subMatrix.irregM3 * subdividedNodes,
        };
        for (const Matrix &regularSubpatch : regularSubpatches)
        {
            const AreaVolume subpatchAreaVolume =
                direct_regular_patch_area_volume(param, regularSubpatch);
            result.area += subpatchAreaVolume.area;
            result.volume += subpatchAreaVolume.volume;
        }

        carriedIrregularPatch = param.subMatrix.irregM4 * subdividedNodes;
    }

    return result;
}

void populate_synthetic_irregular_patch_mesh(Mesh &mesh)
{
    const std::vector<std::vector<double>> coordinates = {
        {-0.70, -0.86, 0.01},
        {-0.18, -0.92, -0.02},
        {0.00, 0.00, 0.04},
        {0.58, -0.78, 0.03},
        {-0.78, -0.05, -0.03},
        {-0.12, 0.56, 0.02},
        {0.64, 0.08, -0.01},
        {1.16, -0.58, 0.05},
        {-0.30, 1.12, -0.04},
        {0.54, 1.06, 0.03},
        {1.20, 0.46, 0.00},
    };

    mesh.vertices.clear();
    mesh.vertices.resize(coordinates.size());
    for (int vertexIndex = 0; vertexIndex < static_cast<int>(coordinates.size()); ++vertexIndex)
    {
        Vertex &vertex = mesh.vertices[vertexIndex];
        vertex.index = vertexIndex;
        vertex.coordRef = Matrix(3, 1, true);
        vertex.coord.set(0, 0, coordinates[vertexIndex][0]);
        vertex.coord.set(1, 0, coordinates[vertexIndex][1]);
        vertex.coord.set(2, 0, coordinates[vertexIndex][2]);
        vertex.coordRef.set(0, 0, coordinates[vertexIndex][0]);
        vertex.coordRef.set(1, 0, coordinates[vertexIndex][1]);
        vertex.coordRef.set(2, 0, coordinates[vertexIndex][2]);
    }

    mesh.faces.clear();
    mesh.faces.resize(1);

    Face &face = mesh.faces.front();
    face.index = 0;
    face.adjacentVertices = {2, 5, 6};
    face.oneRingVertices = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
}

Matrix make_force_scatter_control_points()
{
    Matrix controlPoints(12, 3, true);
    for (int control = 0; control < controlPoints.nrow(); ++control)
    {
        const double index = static_cast<double>(control);
        controlPoints.set(control, 0, -1.2 + 0.37 * index + 0.02 * index * index);
        controlPoints.set(control, 1, 0.8 + 0.11 * index * index - 0.003 * index * index * index);
        controlPoints.set(control, 2, 0.15 * std::sin(0.45 * index) +
                                      0.07 * std::cos(0.25 * index));
    }
    return controlPoints;
}

std::vector<Matrix> control_point_rows_to_columns(const Matrix &controlPoints)
{
    std::vector<Matrix> coordinates(controlPoints.nrow());
    for (int row = 0; row < controlPoints.nrow(); ++row)
    {
        coordinates[row] = Matrix(3, 1, true);
        for (int axis = 0; axis < controlPoints.ncol(); ++axis)
        {
            coordinates[row].set(axis, 0, controlPoints.get(row, axis));
        }
    }
    return coordinates;
}

void populate_regular_force_scatter_mesh(Mesh &mesh,
                                         const Matrix &controlPoints,
                                         const std::vector<int> &oneRingOrder)
{
    mesh.vertices.clear();
    mesh.vertices.resize(oneRingOrder.size());
    for (int row = 0; row < static_cast<int>(oneRingOrder.size()); ++row)
    {
        const int vertexIndex = oneRingOrder[row];
        Vertex &vertex = mesh.vertices[vertexIndex];
        vertex.index = vertexIndex;
        vertex.coordRef = Matrix(3, 1, true);
        for (int axis = 0; axis < controlPoints.ncol(); ++axis)
        {
            vertex.coord.set(axis, 0, controlPoints.get(row, axis));
            vertex.coordRef.set(axis, 0, controlPoints.get(row, axis));
        }
    }

    mesh.faces.clear();
    mesh.faces.resize(1);
    Face &face = mesh.faces.front();
    face.index = 0;
    face.isBoundary = false;
    face.isGhost = false;
    face.adjacentVertices = {oneRingOrder[3], oneRingOrder[6], oneRingOrder[7]};
    face.oneRingVertices = oneRingOrder;
    face.spontCurvature = 0.18;
}

void expect_force_component_matches_row(const Matrix &component,
                                        const Matrix &localRows,
                                        const int row,
                                        const std::string &label)
{
    ASSERT_EQ(component.nrow(), 3);
    ASSERT_EQ(component.ncol(), 1);
    ASSERT_EQ(localRows.ncol(), 3);
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_NEAR(component.get(axis, 0), localRows.get(row, axis), 1.0e-10)
            << label << " row " << row << " axis " << axis;
    }
}

void expect_regular_weighted_samples_preserve_source_id_rows(
    const std::vector<Matrix> &shapeFunctions,
    const Matrix &controlPoints,
    const std::vector<int> &sourceIds)
{
    const SlimedLoopLimitSurfaceEvaluator evaluator;
    ASSERT_EQ(controlPoints.nrow(), evaluator.regular_patch_control_point_count());
    ASSERT_EQ(sourceIds.size(), static_cast<std::size_t>(controlPoints.nrow()));

    for (int sample = 0; sample < static_cast<int>(shapeFunctions.size()); ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "sample " << sample);
        const Matrix &shapeFunction = shapeFunctions[sample];
        const LimitSurfaceWeightedSample weightedSample =
            evaluator.evaluate_weighted_shape_function(shapeFunction,
                                                       controlPoints,
                                                       sourceIds);

        expect_evaluation_matches_rows(weightedSample.evaluation,
                                       shapeFunction * controlPoints);
        for (int localControl = 0; localControl < controlPoints.nrow(); ++localControl)
        {
            SCOPED_TRACE(::testing::Message() << "local control " << localControl);
            const int sourceId = sourceIds[localControl];
            for (int row = 0; row < SlimedLoopLimitSurfaceEvaluator::kShapeFunctionRowCount; ++row)
            {
                EXPECT_DOUBLE_EQ(
                    weightedSample.row_weight(static_cast<LimitSurfaceDerivativeRow>(row),
                                              sourceId),
                    shapeFunction.get(row, localControl));
            }
        }
    }
}

void expect_matrix_near(const Matrix &actual,
                        const Matrix &expected,
                        const double tolerance,
                        const std::string &label)
{
    ASSERT_EQ(actual.nrow(), expected.nrow()) << label;
    ASSERT_EQ(actual.ncol(), expected.ncol()) << label;
    for (int row = 0; row < actual.nrow(); ++row)
    {
        for (int col = 0; col < actual.ncol(); ++col)
        {
            EXPECT_NEAR(actual.get(row, col), expected.get(row, col), tolerance)
                << label << " row " << row << " col " << col;
        }
    }
}

struct IrregularForceRouteResult
{
    double meanCurv = 0.0;
    double eBend = 0.0;
    Matrix normVector = mat_calloc(3, 1);
    Matrix fBend = mat_calloc(11, 3);
    Matrix fArea = mat_calloc(11, 3);
    Matrix fVolume = mat_calloc(11, 3);
};

struct IrregularPatchOutput
{
    double area = 0.0;
    double volume = 0.0;
    IrregularForceRouteResult force;
};

void add_back_projected_force_rows(const Matrix &childToOriginal,
                                   const Matrix &childForce,
                                   Matrix &originalForce)
{
    Matrix originalContribution = childToOriginal.get_transposed() * childForce;
    originalForce += originalContribution;
}

IrregularForceRouteResult direct_irregular_patch_energy_force(Mesh &mesh,
                                                              Face &face)
{
    IrregularForceRouteResult result;
    Matrix carriedPatch = make_one_ring_control_points(mesh, face);
    Matrix carriedToOriginal(11, 11, true);
    carriedToOriginal.set_identity();

    const std::array<const Matrix *, 3> regularChildSelectors = {
        &mesh.param.subMatrix.irregM1,
        &mesh.param.subMatrix.irregM2,
        &mesh.param.subMatrix.irregM3,
    };

    for (int depth = 0; depth < mesh.param.subDivideTimes; ++depth)
    {
        Matrix subdividedNodes = mesh.param.subMatrix.irregM * carriedPatch;
        Matrix subdividedNodesToOriginal = mesh.param.subMatrix.irregM * carriedToOriginal;

        for (const Matrix *regularChildSelector : regularChildSelectors)
        {
            Matrix childControlPoints = (*regularChildSelector) * subdividedNodes;
            Matrix childToOriginal = (*regularChildSelector) * subdividedNodesToOriginal;

            double childMeanCurv = 0.0;
            double childEBend = 0.0;
            Matrix childNormVector = mat_calloc(3, 1);
            Matrix childFBend = mat_calloc(12, 3);
            Matrix childFArea = mat_calloc(12, 3);
            Matrix childFVolume = mat_calloc(12, 3);

            mesh.element_energy_force_regular(control_point_rows_to_columns(childControlPoints),
                                              face,
                                              face.spontCurvature,
                                              childMeanCurv,
                                              childNormVector,
                                              childEBend,
                                              childFBend,
                                              childFArea,
                                              childFVolume);

            result.eBend += childEBend;
            result.meanCurv += childMeanCurv;
            result.normVector += childNormVector;
            add_back_projected_force_rows(childToOriginal, childFBend, result.fBend);
            add_back_projected_force_rows(childToOriginal, childFArea, result.fArea);
            add_back_projected_force_rows(childToOriginal, childFVolume, result.fVolume);
        }

        carriedPatch = mesh.param.subMatrix.irregM4 * subdividedNodes;
        carriedToOriginal = mesh.param.subMatrix.irregM4 * subdividedNodesToOriginal;
    }

    get_unit_vector(result.normVector);
    return result;
}

void perturb_synthetic_irregular_patch(Mesh &mesh, const int variant)
{
    for (Vertex &vertex : mesh.vertices)
    {
        const double row = static_cast<double>(vertex.index + 1);
        const double variantScale = static_cast<double>(variant + 1);
        vertex.coord.set(0, 0, vertex.coord(0, 0) + 0.035 * variantScale * std::sin(0.31 * row));
        vertex.coord.set(1, 0, vertex.coord(1, 0) - 0.025 * variantScale * std::cos(0.27 * row));
        vertex.coord.set(2, 0, vertex.coord(2, 0) + 0.018 * variantScale * std::sin(0.43 * row));
        for (int axis = 0; axis < 3; ++axis)
        {
            vertex.coordRef.set(axis, 0, vertex.coord(axis, 0));
        }
    }
}

IrregularPatchOutput compute_synthetic_irregular_patch_output(const int variant)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.subDivideTimes = 2;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    param.area0 = 2.75;
    param.vol0 = 0.82;

    Mesh mesh(param);
    populate_synthetic_irregular_patch_mesh(mesh);
    perturb_synthetic_irregular_patch(mesh, variant);

    mesh.calculate_element_area_volume();
    mesh.sum_membrane_area_and_volume(mesh.param.area, mesh.param.vol);

    IrregularPatchOutput output;
    output.area = mesh.param.area;
    output.volume = mesh.param.vol;
    output.force = direct_irregular_patch_energy_force(mesh, mesh.faces.front());
    return output;
}

void scatter_irregular_force_rows(const IrregularForceRouteResult &force,
                                  const std::vector<int> &targetVertices,
                                  std::vector<double> &components)
{
    ASSERT_EQ(targetVertices.size(), 11);
    for (int row = 0; row < static_cast<int>(targetVertices.size()); ++row)
    {
        const int base = targetVertices[row] * 9;
        for (int axis = 0; axis < 3; ++axis)
        {
            components[base + axis] += force.fBend.get(row, axis);
            components[base + 3 + axis] += force.fArea.get(row, axis);
            components[base + 6 + axis] += force.fVolume.get(row, axis);
        }
    }
}

std::vector<double> reduce_thread_buffers(const std::vector<std::vector<double>> &threadBuffers)
{
    if (threadBuffers.empty())
    {
        return {};
    }
    std::vector<double> reduced(threadBuffers.front().size(), 0.0);
    for (const std::vector<double> &threadBuffer : threadBuffers)
    {
        if (threadBuffer.size() != reduced.size())
        {
            return {};
        }
        for (int component = 0; component < static_cast<int>(reduced.size()); ++component)
        {
            reduced[component] += threadBuffer[component];
        }
    }
    return reduced;
}

double max_abs_delta(const std::vector<double> &lhs, const std::vector<double> &rhs)
{
    if (lhs.size() != rhs.size())
    {
        return std::numeric_limits<double>::infinity();
    }
    double maxDelta = 0.0;
    for (int component = 0; component < static_cast<int>(lhs.size()); ++component)
    {
        maxDelta = std::max(maxDelta, std::abs(lhs[component] - rhs[component]));
    }
    return maxDelta;
}
} // namespace

TEST(SurfaceShapeFunctionsCharacterization, PartitionOfUnityAndDerivativeSums)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
        {1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0},
    };

    for (const auto &sample : barycentricSamples)
    {
        SCOPED_TRACE(::testing::Message()
                     << "v=" << sample[0] << ", w=" << sample[1] << ", u=" << sample[2]);

        Matrix vwu({sample});
        Matrix shapefunction(7, 12, true);
        get_shapefunction(vwu, shapefunction);

        ASSERT_EQ(shapefunction.nrow(), 7);
        ASSERT_EQ(shapefunction.ncol(), 12);
        EXPECT_NEAR(row_sum(shapefunction, 0), 1.0, kTolerance);

        for (int derivativeRow = 1; derivativeRow < shapefunction.nrow(); ++derivativeRow)
        {
            EXPECT_NEAR(row_sum(shapefunction, derivativeRow), 0.0, kTolerance);
        }

        for (int col = 0; col < shapefunction.ncol(); ++col)
        {
            EXPECT_NEAR(shapefunction.get(5, col), shapefunction.get(6, col), kTolerance);
        }
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, SlimedLoopShapeFunctionRowsMatchCurrentContract)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (const auto &sample : barycentricSamples)
    {
        SCOPED_TRACE(::testing::Message()
                     << "v=" << sample[0] << ", w=" << sample[1] << ", u=" << sample[2]);

        Matrix vwu({sample});
        Matrix shapefunction = evaluator.shape_function(vwu);

        ASSERT_EQ(shapefunction.nrow(), SlimedLoopLimitSurfaceEvaluator::kShapeFunctionRowCount);
        ASSERT_EQ(shapefunction.ncol(), evaluator.regular_patch_control_point_count());
        EXPECT_NEAR(row_sum(shapefunction, static_cast<int>(LimitSurfaceDerivativeRow::Position)),
                    1.0,
                    kTolerance);

        for (int derivativeRow = static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeV);
             derivativeRow < shapefunction.nrow();
             ++derivativeRow)
        {
            EXPECT_NEAR(row_sum(shapefunction, derivativeRow), 0.0, kTolerance);
        }

        for (int col = 0; col < shapefunction.ncol(); ++col)
        {
            EXPECT_NEAR(shapefunction.get(static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeVW), col),
                        shapefunction.get(static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeWV), col),
                        kTolerance);
        }
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, SlimedLoopEvaluationMatchesDirectShapeFunctionProduct)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    Matrix controlPoints = make_deterministic_regular_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (const auto &sample : barycentricSamples)
    {
        SCOPED_TRACE(::testing::Message()
                     << "v=" << sample[0] << ", w=" << sample[1] << ", u=" << sample[2]);

        Matrix vwu({sample});
        Matrix shapefunction(7, 12, true);
        get_shapefunction(vwu, shapefunction);

        const Matrix directRows = shapefunction * controlPoints;
        const LimitSurfaceEvaluation evaluation = evaluator.evaluate(vwu, controlPoints);
        const LimitSurfaceEvaluation cachedEvaluation =
            evaluator.evaluate_shape_function(shapefunction, controlPoints);

        expect_column_matches_row(evaluation.position,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::Position));
        expect_column_matches_row(evaluation.firstDerivativeV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeV));
        expect_column_matches_row(evaluation.firstDerivativeW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeW));
        expect_column_matches_row(evaluation.secondDerivativeVV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeVV));
        expect_column_matches_row(evaluation.secondDerivativeWW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeWW));
        expect_column_matches_row(evaluation.mixedDerivativeVW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeVW));
        expect_column_matches_row(evaluation.mixedDerivativeWV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeWV));
        expect_column_matches_row(cachedEvaluation.position,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::Position));
        expect_column_matches_row(cachedEvaluation.firstDerivativeV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeV));
        expect_column_matches_row(cachedEvaluation.firstDerivativeW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::FirstDerivativeW));
        expect_column_matches_row(cachedEvaluation.secondDerivativeVV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeVV));
        expect_column_matches_row(cachedEvaluation.secondDerivativeWW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::SecondDerivativeWW));
        expect_column_matches_row(cachedEvaluation.mixedDerivativeVW,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeVW));
        expect_column_matches_row(cachedEvaluation.mixedDerivativeWV,
                                  directRows,
                                  static_cast<int>(LimitSurfaceDerivativeRow::MixedDerivativeWV));
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularLatticeProbeFrozenOutputsMatchCurrentEvaluator)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    const std::array<std::array<std::array<double, 3>, 7>, 3> expected = {{
        {{
            {{3.4999999999999982, 2.0207259421636894, -0.003450545921933364}},
            {{0.99999999999999978, -3.6236828367093433e-17, -0.019210698845634439}},
            {{0.50000000000000022, 0.86602540378443882, -0.019210698845634439}},
            {{3.3306690738754696e-16, 3.4587734865006226e-17, 0.0017240750489055767}},
            {{-1.1102230246251565e-16, -1.1674737245020074e-16, 0.0017240750489055771}},
            {{-5.5511151231257827e-17, -1.9572029680632367e-16, 0.0017240750489055834}},
            {{-5.5511151231257827e-17, -1.9572029680632367e-16, 0.0017240750489055834}},
        }},
        {{
            {{3.3500000000000001, 1.9918584287042085, -0.0002322832431500952}},
            {{0.99999999999999978, -1.2002033867471152e-16, -0.019363657606087825}},
            {{0.50000000000000033, 0.86602540378443882, -0.019363657606087818}},
            {{2.7755575615628914e-16, 4.1296024847155701e-16, 0.00011143007653501233}},
            {{1.1102230246251565e-16, 1.1399713609118315e-16, 0.0001114300765350122}},
            {{5.5511151231257827e-17, -2.6556107582143733e-16, 0.0001114300765350114}},
            {{5.5511151231257827e-17, -2.6556107582143733e-16, 0.0001114300765350114}},
        }},
        {{
            {{3.4750000000000001, 2.4681724007856505, -0.007865622601230705}},
            {{0.99999999999999978, -2.5312096407330787e-16, -0.018545015988735949}},
            {{0.50000000000000022, 0.86602540378443882, -0.018545015988735942}},
            {{-2.7755575615628914e-16, -5.2999475976476768e-16, 0.0039817780102243674}},
            {{-4.4408920985006262e-16, -8.1361688734307423e-16, 0.0039817780102243709}},
            {{2.2204460492503131e-16, 2.0460560118955678e-16, 0.0039817780102243657}},
            {{2.2204460492503131e-16, 2.0460560118955678e-16, 0.0039817780102243657}},
        }},
    }};

    const Matrix controlPoints = make_regular_lattice_probe_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (int sample = 0; sample < static_cast<int>(barycentricSamples.size()); ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "sample " << sample);
        const LimitSurfaceEvaluation evaluation =
            evaluator.evaluate(Matrix({barycentricSamples[sample]}), controlPoints);

        expect_column_near_values(evaluation.position, expected[sample][0], 1.0e-14);
        expect_column_near_values(evaluation.firstDerivativeV, expected[sample][1], 1.0e-14);
        expect_column_near_values(evaluation.firstDerivativeW, expected[sample][2], 1.0e-14);
        expect_column_near_values(evaluation.secondDerivativeVV, expected[sample][3], 1.0e-14);
        expect_column_near_values(evaluation.secondDerivativeWW, expected[sample][4], 1.0e-14);
        expect_column_near_values(evaluation.mixedDerivativeVW, expected[sample][5], 1.0e-14);
        expect_column_near_values(evaluation.mixedDerivativeWV, expected[sample][6], 1.0e-14);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularLatticeProbeFrozenIntegrandsMatchCurrentEvaluator)
{
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };
    const std::array<std::array<double, 3>, 3> expectedCross = {{
        {{0.016636953224771819, 0.0096053494228172127, 0.8660254037844386}},
        {{0.016769419397055833, 0.0096818288030438952, 0.86602540378443871}},
        {{0.016060454959833926, 0.0092725079943679605, 0.86602540378443871}},
    }};
    const std::array<std::array<double, 3>, 3> expectedUnitNormal = {{
        {{0.019205974104791867, 0.011088574319450555, 0.9997540567950941}},
        {{0.019358819135302421, 0.011176819438960107, 0.99975012619599879}},
        {{0.018540765478688707, 0.010704515940102625, 0.99977080041075028}},
    }};
    const std::array<double, 3> expectedAreaIntegrand = {{
        0.8662384492448586,
        0.86624185493191563,
        0.86622394195613328,
    }};
    const std::array<double, 3> expectedLegacyVolumeIntegrand = {{
        0.058229336286701336,
        0.056177554980137046,
        0.055810080985422894,
    }};

    const Matrix controlPoints = make_regular_lattice_probe_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    for (int sample = 0; sample < static_cast<int>(barycentricSamples.size()); ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "sample " << sample);
        const LimitSurfaceEvaluation evaluation =
            evaluator.evaluate(Matrix({barycentricSamples[sample]}), controlPoints);

        const std::array<double, 3> tangentCross =
            cross_array(column_to_array(evaluation.firstDerivativeV),
                        column_to_array(evaluation.firstDerivativeW));
        const std::array<double, 3> unitNormal = normalized_array(tangentCross);
        const double areaIntegrand = norm_array(tangentCross);
        const double legacyVolumeIntegrand =
            evaluation.position.get(0, 0) * tangentCross[0];

        for (int axis = 0; axis < 3; ++axis)
        {
            EXPECT_NEAR(tangentCross[axis], expectedCross[sample][axis], 1.0e-14)
                << "cross axis " << axis;
            EXPECT_NEAR(unitNormal[axis], expectedUnitNormal[sample][axis], 1.0e-14)
                << "unit normal axis " << axis;
        }
        EXPECT_NEAR(areaIntegrand, expectedAreaIntegrand[sample], 1.0e-14);
        EXPECT_NEAR(legacyVolumeIntegrand,
                    expectedLegacyVolumeIntegrand[sample],
                    1.0e-14);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, SlimedLoopRegularPatchRejectsIrregularControlCount)
{
    Matrix vwu({{1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0}});
    Matrix irregularControlPoints(11, 3, true);
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    EXPECT_THROW(evaluator.evaluate(vwu, irregularControlPoints), std::invalid_argument);
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularEnergyForceGeometryExtractionMatchesParamShapeFunctions)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    Matrix controlPoints = make_deterministic_regular_control_points();
    const SlimedLoopLimitSurfaceEvaluator evaluator;

    ASSERT_FALSE(param.shapeFunctions.empty());
    ASSERT_EQ(param.shapeFunctions.size(),
              static_cast<std::size_t>(param.gaussQuadratureCoeff.nrow()));

    for (int sample = 0; sample < static_cast<int>(param.shapeFunctions.size()); ++sample)
    {
        SCOPED_TRACE(sample);
        const Matrix &shapeFunction = param.shapeFunctions[sample];
        const Matrix directRows = shapeFunction * controlPoints;
        const LimitSurfaceEvaluation evaluation =
            evaluator.evaluate_shape_function(shapeFunction, controlPoints);

        expect_evaluation_matches_rows(evaluation, directRows);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularProductionSamplePlanMatchesFrozenDefaultQuadrature)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);

    ASSERT_EQ(param.gaussQuadratureN, 2);
    ASSERT_EQ(param.VWU.nrow(), 3);
    ASSERT_EQ(param.VWU.ncol(), 3);
    ASSERT_EQ(param.gaussQuadratureCoeff.nrow(), 3);
    ASSERT_EQ(param.gaussQuadratureCoeff.ncol(), 1);
    ASSERT_EQ(param.shapeFunctions.size(), 3u);

    const std::array<std::array<double, 3>, 3> expectedSamples = {{
        {{1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0}},
        {{1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0}},
        {{4.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0}},
    }};

    const SlimedLoopLimitSurfaceEvaluator evaluator;
    const Matrix controlPoints = make_regular_lattice_probe_control_points();
    const std::vector<int> sourceIds = {9, 2, 11, 0, 7, 4, 10, 1, 8, 3, 6, 5};

    for (int sample = 0; sample < 3; ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "sample " << sample);
        for (int coord = 0; coord < 3; ++coord)
        {
            EXPECT_DOUBLE_EQ(param.VWU.get(sample, coord), expectedSamples[sample][coord]);
        }
        EXPECT_DOUBLE_EQ(param.gaussQuadratureCoeff(sample, 0), 1.0 / 3.0);
        EXPECT_DOUBLE_EQ(0.5 * param.gaussQuadratureCoeff(sample, 0), 1.0 / 6.0);

        const Matrix &shapeFunction = param.shapeFunctions[sample];
        ASSERT_EQ(shapeFunction.nrow(), SlimedLoopLimitSurfaceEvaluator::kShapeFunctionRowCount);
        ASSERT_EQ(shapeFunction.ncol(),
                  SlimedLoopLimitSurfaceEvaluator::kRegularPatchControlPointCount);

        Matrix vwu({{expectedSamples[sample][0],
                     expectedSamples[sample][1],
                     expectedSamples[sample][2]}});
        const LimitSurfaceEvaluation evaluation =
            evaluator.evaluate_shape_function(shapeFunction, controlPoints);
        const LimitSurfaceWeightedSample weightedSample =
            evaluator.evaluate_weighted(vwu, controlPoints, sourceIds);

        expect_evaluation_matches_rows(evaluation, shapeFunction * controlPoints);
        expect_evaluation_matches_rows(weightedSample.evaluation,
                                       shapeFunction * controlPoints);
        for (int row = 0; row < SlimedLoopLimitSurfaceEvaluator::kShapeFunctionRowCount; ++row)
        {
            EXPECT_DOUBLE_EQ(shapeFunction.get(row, 5),
                             weightedSample.row_weight(
                                 static_cast<LimitSurfaceDerivativeRow>(row),
                                 sourceIds[5]));
        }

        const std::array<double, 3> tangentCross =
            cross_array(column_to_array(evaluation.firstDerivativeV),
                        column_to_array(evaluation.firstDerivativeW));
        EXPECT_GT(norm_array(tangentCross), 0.0);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularEnergyForceGeometryRowsMatchLegacyMultiplicationForFixtures)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    const SlimedLoopLimitSurfaceEvaluator evaluator;
    const std::vector<Matrix> controlPointFixtures =
        make_regular_energy_force_control_point_fixtures();
    const std::vector<Matrix> shapeFunctionBaseline = param.shapeFunctions;

    ASSERT_FALSE(param.shapeFunctions.empty());
    ASSERT_EQ(param.shapeFunctions.size(),
              static_cast<std::size_t>(param.gaussQuadratureCoeff.nrow()));

    for (int fixture = 0; fixture < static_cast<int>(controlPointFixtures.size()); ++fixture)
    {
        SCOPED_TRACE(::testing::Message() << "fixture " << fixture);
        const Matrix &controlPoints = controlPointFixtures[fixture];
        ASSERT_EQ(controlPoints.nrow(), evaluator.regular_patch_control_point_count());
        ASSERT_EQ(controlPoints.ncol(), SlimedLoopLimitSurfaceEvaluator::kSpatialDimension);

        for (int sample = 0; sample < static_cast<int>(param.shapeFunctions.size()); ++sample)
        {
            SCOPED_TRACE(::testing::Message() << "sample " << sample);
            const Matrix &shapeFunction = param.shapeFunctions[sample];
            Matrix legacyRows(7, 3, true);

            multiplication(shapeFunction, controlPoints, legacyRows);

            const LimitSurfaceEvaluation evaluation =
                evaluator.evaluate_shape_function(shapeFunction, controlPoints);

            expect_evaluation_matches_rows(evaluation, legacyRows);
        }
    }

    ASSERT_EQ(shapeFunctionBaseline.size(), param.shapeFunctions.size());
    for (int sample = 0; sample < static_cast<int>(shapeFunctionBaseline.size()); ++sample)
    {
        SCOPED_TRACE(::testing::Message() << "shape function baseline " << sample);
        expect_matrix_exactly_matches(shapeFunctionBaseline[sample],
                                      param.shapeFunctions[sample]);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, WeightedRegularSampleRowsAreKeyedBySourceId)
{
    const SlimedLoopLimitSurfaceEvaluator evaluator;
    const LimitSurfaceEvaluator &backend = evaluator;
    const Matrix controlPoints = make_force_scatter_control_points();
    const std::vector<int> sourceIds = {9, 2, 11, 0, 7, 4, 10, 1, 8, 3, 6, 5};
    const std::vector<std::vector<double>> barycentricSamples = {
        {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0},
        {0.20, 0.30, 0.50},
        {0.05, 0.85, 0.10},
    };

    for (const auto &sample : barycentricSamples)
    {
        SCOPED_TRACE(::testing::Message()
                     << "v=" << sample[0] << ", w=" << sample[1] << ", u=" << sample[2]);
        Matrix vwu({sample});
        const Matrix shapeFunction = evaluator.shape_function(vwu);
        const LimitSurfaceWeightedSample weightedSample =
            backend.evaluate_weighted(vwu, controlPoints, sourceIds);

        expect_evaluation_matches_rows(weightedSample.evaluation, shapeFunction * controlPoints);
        for (int localControl = 0; localControl < static_cast<int>(sourceIds.size()); ++localControl)
        {
            SCOPED_TRACE(::testing::Message() << "local control " << localControl);
            for (int row = 0; row < SlimedLoopLimitSurfaceEvaluator::kShapeFunctionRowCount; ++row)
            {
                EXPECT_DOUBLE_EQ(
                    weightedSample.row_weight(static_cast<LimitSurfaceDerivativeRow>(row),
                                              sourceIds[localControl]),
                    shapeFunction.get(row, localControl));
            }
        }
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, WeightedSampleAggregatesDuplicateSourceIds)
{
    const SlimedLoopLimitSurfaceEvaluator evaluator;
    const LimitSurfaceEvaluator &backend = evaluator;
    const Matrix controlPoints = make_force_scatter_control_points();
    const Matrix vwu({{0.25, 0.25, 0.50}});
    const Matrix shapeFunction = evaluator.shape_function(vwu);
    std::vector<int> duplicateSourceIds = {4, 4, 9, 9, 9, 1, 3, 5, 7, 11, 13, 15};

    const LimitSurfaceWeightedSample weightedSample =
        backend.evaluate_weighted(vwu, controlPoints, duplicateSourceIds);

    for (int row = 0; row < SlimedLoopLimitSurfaceEvaluator::kShapeFunctionRowCount; ++row)
    {
        EXPECT_DOUBLE_EQ(
            weightedSample.row_weight(static_cast<LimitSurfaceDerivativeRow>(row), 4),
            shapeFunction.get(row, 0) + shapeFunction.get(row, 1));
        EXPECT_DOUBLE_EQ(
            weightedSample.row_weight(static_cast<LimitSurfaceDerivativeRow>(row), 9),
            shapeFunction.get(row, 2) + shapeFunction.get(row, 3) + shapeFunction.get(row, 4));
        EXPECT_DOUBLE_EQ(
            weightedSample.row_weight(static_cast<LimitSurfaceDerivativeRow>(row), 42),
            0.0);
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract,
     RegularActualForceBackProjectionMatchesDirectFormulaRows)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    param.area0 = 2.75;
    param.vol0 = 0.82;

    const std::vector<int> naturalOrder = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};
    const std::vector<int> permutedSourceOrder = {9, 2, 11, 0, 7, 4, 10, 1, 8, 3, 6, 5};
    const std::vector<Matrix> controlPointFixtures =
        make_regular_energy_force_control_point_fixtures();

    for (int fixture = 0; fixture < static_cast<int>(controlPointFixtures.size()); ++fixture)
    {
        for (const std::vector<int> &oneRingOrder : {naturalOrder, permutedSourceOrder})
        {
            SCOPED_TRACE(::testing::Message() << "fixture " << fixture
                                              << " first source id " << oneRingOrder.front());
            Mesh mesh(param);
            populate_regular_force_scatter_mesh(mesh,
                                                controlPointFixtures[fixture],
                                                oneRingOrder);
            mesh.calculate_element_area_volume();
            mesh.sum_membrane_area_and_volume(mesh.param.area, mesh.param.vol);

            Face &face = mesh.faces.front();
            EXPECT_EQ(face.oneRingVertices, oneRingOrder);
            expect_regular_weighted_samples_preserve_source_id_rows(param.shapeFunctions,
                                                                    controlPointFixtures[fixture],
                                                                    face.oneRingVertices);
            double directMeanCurv = 0.0;
            double directEBend = 0.0;
            Matrix directNormVector = mat_calloc(3, 1);
            Matrix directFBend = mat_calloc(12, 3);
            Matrix directFArea = mat_calloc(12, 3);
            Matrix directFVolume = mat_calloc(12, 3);

            double backProjectedMeanCurv = 0.0;
            double backProjectedEBend = 0.0;
            Matrix backProjectedNormVector = mat_calloc(3, 1);
            Matrix backProjectedFBend = mat_calloc(12, 3);
            Matrix backProjectedFArea = mat_calloc(12, 3);
            Matrix backProjectedFVolume = mat_calloc(12, 3);

            const std::vector<Matrix> coordinateColumns =
                control_point_rows_to_columns(controlPointFixtures[fixture]);
            mesh.element_energy_force_regular(coordinateColumns,
                                              face,
                                              face.spontCurvature,
                                              directMeanCurv,
                                              directNormVector,
                                              directEBend,
                                              directFBend,
                                              directFArea,
                                              directFVolume);
            mesh.element_energy_force_regular(coordinateColumns,
                                              face,
                                              face.spontCurvature,
                                              backProjectedMeanCurv,
                                              backProjectedNormVector,
                                              backProjectedEBend,
                                              backProjectedFBend,
                                              backProjectedFArea,
                                              backProjectedFVolume,
                                              true);

            EXPECT_NEAR(backProjectedEBend, directEBend, 1.0e-12);
            EXPECT_NEAR(backProjectedMeanCurv, directMeanCurv, 1.0e-12);
            expect_matrix_near(backProjectedNormVector, directNormVector, 1.0e-12, "normal");
            expect_matrix_near(backProjectedFBend, directFBend, 1.0e-10, "curvature force");
            expect_matrix_near(backProjectedFArea, directFArea, 1.0e-10, "area force");
            expect_matrix_near(backProjectedFVolume, directFVolume, 1.0e-10, "volume force");

            bool observedActualForceContribution = false;
            for (int row = 0; row < 12; ++row)
            {
                for (int axis = 0; axis < 3; ++axis)
                {
                    observedActualForceContribution =
                        observedActualForceContribution ||
                        std::abs(backProjectedFBend.get(row, axis)) > 1.0e-12 ||
                        std::abs(backProjectedFArea.get(row, axis)) > 1.0e-12 ||
                        std::abs(backProjectedFVolume.get(row, axis)) > 1.0e-12;
                }
            }
            EXPECT_TRUE(observedActualForceContribution);
        }
    }
}

TEST(SurfaceLimitSurfaceEvaluatorContract, RegularForceRowsScatterInOneRingOrder)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    param.area0 = 2.75;
    param.vol0 = 0.82;

    Mesh localMesh(param);
    const Matrix controlPoints = make_force_scatter_control_points();
    const std::vector<int> oneRingOrder = {9, 2, 11, 0, 7, 4, 10, 1, 8, 3, 6, 5};
    populate_regular_force_scatter_mesh(localMesh, controlPoints, oneRingOrder);
    localMesh.calculate_element_area_volume();
    localMesh.sum_membrane_area_and_volume(localMesh.param.area, localMesh.param.vol);

    Face &localFace = localMesh.faces.front();
    double meanCurv = 0.0;
    double eBend = 0.0;
    Matrix normVector = mat_calloc(3, 1);
    Matrix fBend = mat_calloc(12, 3);
    Matrix fArea = mat_calloc(12, 3);
    Matrix fVolume = mat_calloc(12, 3);

    localMesh.element_energy_force_regular(control_point_rows_to_columns(controlPoints),
                                           localFace,
                                           localFace.spontCurvature,
                                           meanCurv,
                                           normVector,
                                           eBend,
                                           fBend,
                                           fArea,
                                           fVolume);

    ASSERT_TRUE(std::isfinite(eBend));
    ASSERT_TRUE(std::isfinite(meanCurv));
    ASSERT_GT(std::abs(eBend), 1.0e-12);
    ASSERT_GT(normVector.calculate_norm(), 0.0);
    for (int row = 0; row < 12; ++row)
    {
        bool hasNonzeroForce = false;
        for (int axis = 0; axis < 3; ++axis)
        {
            hasNonzeroForce = hasNonzeroForce ||
                              std::abs(fBend.get(row, axis)) > 1.0e-12 ||
                              std::abs(fArea.get(row, axis)) > 1.0e-12 ||
                              std::abs(fVolume.get(row, axis)) > 1.0e-12;
        }
        EXPECT_TRUE(hasNonzeroForce) << "local force row " << row;
    }

    Mesh scatteredMesh(param);
    populate_regular_force_scatter_mesh(scatteredMesh, controlPoints, oneRingOrder);
    scatteredMesh.Compute_Energy_And_Force();

    EXPECT_NEAR(scatteredMesh.faces.front().energy.energyCurvature, eBend, 1.0e-10);
    EXPECT_NEAR(scatteredMesh.faces.front().meanCurvature, meanCurv, 1.0e-12);
    for (int axis = 0; axis < 3; ++axis)
    {
        EXPECT_NEAR(scatteredMesh.faces.front().normVector.get(axis, 0),
                    normVector.get(axis, 0),
                    1.0e-12)
            << "normal axis " << axis;
    }

    for (int row = 0; row < static_cast<int>(oneRingOrder.size()); ++row)
    {
        const int vertexIndex = oneRingOrder[row];
        const Force &force = scatteredMesh.vertices[vertexIndex].force;
        expect_force_component_matches_row(force.forceCurvature, fBend, row, "curvature");
        expect_force_component_matches_row(force.forceArea, fArea, row, "area");
        expect_force_component_matches_row(force.forceVolume, fVolume, row, "volume");
    }
}

TEST(SurfaceQuadratureCharacterization, SupportedRulesHaveBarycentricCoordinatesAndUnitWeight)
{
    const std::vector<std::pair<int, int>> supportedRules = {
        {1, 1},
        {2, 3},
        {4, 6},
        {5, 7},
        {6, 12},
    };

    for (const auto &[order, expectedPointCount] : supportedRules)
    {
        SCOPED_TRACE(order);

        Matrix vwu;
        Matrix weight;
        get_gauss_quadrature_weight_VWU(order, vwu, weight);

        ASSERT_EQ(vwu.nrow(), expectedPointCount);
        ASSERT_EQ(vwu.ncol(), 3);
        ASSERT_EQ(weight.nrow(), expectedPointCount);
        ASSERT_EQ(weight.ncol(), 1);
        EXPECT_NEAR(column_sum(weight, 0), 1.0, kTolerance);

        for (int row = 0; row < vwu.nrow(); ++row)
        {
            EXPECT_NEAR(row_sum(vwu, row), 1.0, kTolerance);
            for (int col = 0; col < vwu.ncol(); ++col)
            {
                EXPECT_GE(vwu.get(row, col), -kTolerance);
                EXPECT_LE(vwu.get(row, col), 1.0 + kTolerance);
            }
        }
    }
}

TEST(SurfaceQuadratureCharacterization, ThirdOrderRuleCurrentlyLeavesCoordinatesUnchanged)
{
    Matrix vwu(1, 3, true);
    vwu.set_all(-9.0);
    Matrix weight;

    get_gauss_quadrature_weight_VWU(3, vwu, weight);

    ASSERT_EQ(weight.nrow(), 4);
    ASSERT_EQ(weight.ncol(), 1);
    EXPECT_NEAR(column_sum(weight, 0), 1.0, kTolerance);
    ASSERT_EQ(vwu.nrow(), 1);
    ASSERT_EQ(vwu.ncol(), 3);
    for (int col = 0; col < vwu.ncol(); ++col)
    {
        EXPECT_DOUBLE_EQ(vwu.get(0, col), -9.0);
    }
}

TEST(SurfaceSubdivisionCharacterization, IrregularPatchMatricesPreserveAffineWeights)
{
    Matrix subdivision;
    Matrix subPatch1;
    Matrix subPatch2;
    Matrix subPatch3;
    Matrix subPatch4;

    get_subdivision_matrices(subdivision, subPatch1, subPatch2, subPatch3, subPatch4);

    ASSERT_EQ(subdivision.nrow(), 17);
    ASSERT_EQ(subdivision.ncol(), 11);
    ASSERT_EQ(subPatch1.nrow(), 12);
    ASSERT_EQ(subPatch1.ncol(), 17);
    ASSERT_EQ(subPatch2.nrow(), 12);
    ASSERT_EQ(subPatch2.ncol(), 17);
    ASSERT_EQ(subPatch3.nrow(), 12);
    ASSERT_EQ(subPatch3.ncol(), 17);
    ASSERT_EQ(subPatch4.nrow(), 11);
    ASSERT_EQ(subPatch4.ncol(), 17);

    expect_row_stochastic(subdivision);
    expect_row_stochastic(subPatch1);
    expect_row_stochastic(subPatch2);
    expect_row_stochastic(subPatch3);
    expect_row_stochastic(subPatch4);
    expect_selection_rows(subPatch1);
    expect_selection_rows(subPatch2);
    expect_selection_rows(subPatch3);
    expect_selection_rows(subPatch4);
}

TEST(SurfaceSubdivisionCharacterization, SyntheticIrregularPatchAreaVolumeUsesSubdivisionFixture)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.subDivideTimes = 2;
    Mesh mesh(param);
    populate_synthetic_irregular_patch_mesh(mesh);
    const Face &fixtureFace = mesh.faces.front();

    ASSERT_EQ(fixtureFace.oneRingVertices.size(), 11);
    ASSERT_GT(param.subDivideTimes, 0);

    const AreaVolume expected = direct_irregular_patch_area_volume(
        param,
        make_one_ring_control_points(mesh, fixtureFace));

    mesh.calculate_element_area_volume();

    EXPECT_TRUE(std::isfinite(mesh.faces.front().elementArea));
    EXPECT_TRUE(std::isfinite(mesh.faces.front().elementVolume));
    EXPECT_GT(mesh.faces.front().elementArea, 0.0);
    EXPECT_NEAR(mesh.faces.front().elementArea, expected.area, 1.0e-12);
    EXPECT_NEAR(mesh.faces.front().elementVolume, expected.volume, 1.0e-12);

    double area = 0.0;
    double volume = 0.0;
    mesh.sum_membrane_area_and_volume(area, volume);

    EXPECT_NEAR(area, expected.area, 1.0e-12);
    EXPECT_NEAR(volume, expected.volume, 1.0e-12);
}

TEST(SurfaceSubdivisionCharacterization, SyntheticIrregularPatchEnergyForceRequiresSubdivisionDepth)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.subDivideTimes = 0;
    Mesh mesh(param);
    populate_synthetic_irregular_patch_mesh(mesh);

    ASSERT_EQ(mesh.faces.front().oneRingVertices.size(), 11);

    try
    {
        mesh.Compute_Energy_And_Force();
        FAIL() << "Expected unsupported irregular energy/force routing to throw";
    }
    catch (const std::runtime_error &error)
    {
        const std::string message = error.what();
        EXPECT_NE(message.find("Unsupported irregular membrane energy/force routing"),
                  std::string::npos);
        EXPECT_NE(message.find("11-control one-ring patches require Param::subDivideTimes > 0"),
                  std::string::npos);
        EXPECT_NE(message.find("regular 12-control force fallback remains disabled"),
                  std::string::npos);
    }
}

TEST(SurfaceSubdivisionCharacterization, SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.subDivideTimes = 2;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    param.area0 = 2.75;
    param.vol0 = 0.82;

    Mesh mesh(param);
    populate_synthetic_irregular_patch_mesh(mesh);
    Face &face = mesh.faces.front();

    ASSERT_EQ(face.oneRingVertices.size(), 11);
    ASSERT_GT(param.subDivideTimes, 0);

    mesh.calculate_element_area_volume();
    mesh.sum_membrane_area_and_volume(mesh.param.area, mesh.param.vol);
    const IrregularForceRouteResult expected =
        direct_irregular_patch_energy_force(mesh, face);

    ASSERT_TRUE(std::isfinite(expected.eBend));
    ASSERT_TRUE(std::isfinite(expected.meanCurv));
    ASSERT_GT(expected.normVector.calculate_norm(), 0.0);
    for (int row = 0; row < 11; ++row)
    {
        bool hasNonzeroForce = false;
        for (int axis = 0; axis < 3; ++axis)
        {
            hasNonzeroForce = hasNonzeroForce ||
                              std::abs(expected.fBend.get(row, axis)) > 1.0e-12 ||
                              std::abs(expected.fArea.get(row, axis)) > 1.0e-12 ||
                              std::abs(expected.fVolume.get(row, axis)) > 1.0e-12;
        }
        EXPECT_TRUE(hasNonzeroForce) << "original irregular force row " << row;
    }

    mesh.Compute_Energy_And_Force();

    EXPECT_NEAR(mesh.faces.front().energy.energyCurvature, expected.eBend, 1.0e-10);
    EXPECT_NEAR(mesh.faces.front().meanCurvature, expected.meanCurv, 1.0e-12);
    expect_matrix_near(mesh.faces.front().normVector,
                       expected.normVector,
                       1.0e-12,
                       "irregular normal");

    for (int row = 0; row < static_cast<int>(face.oneRingVertices.size()); ++row)
    {
        const int vertexIndex = face.oneRingVertices[row];
        const Force &force = mesh.vertices[vertexIndex].force;
        expect_force_component_matches_row(force.forceCurvature,
                                           expected.fBend,
                                           row,
                                           "irregular curvature");
        expect_force_component_matches_row(force.forceArea,
                                           expected.fArea,
                                           row,
                                           "irregular area");
        expect_force_component_matches_row(force.forceVolume,
                                           expected.fVolume,
                                           row,
                                           "irregular volume");
    }
}

TEST(SurfaceSubdivisionCharacterization, SyntheticIrregularPatchSerialOpenMpReductionToleranceEnvelope)
{
    constexpr int nVertices = 18;
    constexpr int nThreads = 3;
    constexpr double forceTolerance = 1.0e-10;
    constexpr double scalarTolerance = 1.0e-10;
    const std::vector<std::vector<int>> targetVertexRows = {
        {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
        {2, 11, 12, 3, 13, 14, 4, 15, 5, 16, 6},
        {1, 12, 17, 2, 11, 15, 3, 13, 7, 14, 8},
        {4, 16, 10, 5, 17, 12, 6, 11, 9, 15, 0},
    };
    const std::vector<int> openMpCompatibleThreadAssignment = {1, 0, 2, 1};

    std::vector<IrregularPatchOutput> outputs;
    for (int variant = 0; variant < static_cast<int>(targetVertexRows.size()); ++variant)
    {
        outputs.push_back(compute_synthetic_irregular_patch_output(variant));
    }

    std::vector<double> serialComponents(nVertices * 9, 0.0);
    double serialArea = 0.0;
    double serialVolume = 0.0;
    double serialCurvatureEnergy = 0.0;
    for (int face = 0; face < static_cast<int>(outputs.size()); ++face)
    {
        ASSERT_EQ(targetVertexRows[face].size(), 11);
        scatter_irregular_force_rows(outputs[face].force, targetVertexRows[face], serialComponents);
        serialArea += outputs[face].area;
        serialVolume += outputs[face].volume;
        serialCurvatureEnergy += outputs[face].force.eBend;
    }

    std::vector<std::vector<double>> threadForceComponents(
        nThreads, std::vector<double>(nVertices * 9, 0.0));
    std::vector<double> threadAreas(nThreads, 0.0);
    std::vector<double> threadVolumes(nThreads, 0.0);
    std::vector<double> threadCurvatureEnergies(nThreads, 0.0);
    for (int face = 0; face < static_cast<int>(outputs.size()); ++face)
    {
        const int thread = openMpCompatibleThreadAssignment[face];
        ASSERT_GE(thread, 0);
        ASSERT_LT(thread, nThreads);
        scatter_irregular_force_rows(outputs[face].force,
                                     targetVertexRows[face],
                                     threadForceComponents[thread]);
        threadAreas[thread] += outputs[face].area;
        threadVolumes[thread] += outputs[face].volume;
        threadCurvatureEnergies[thread] += outputs[face].force.eBend;
    }

    const std::vector<double> openMpCompatibleComponents =
        reduce_thread_buffers(threadForceComponents);
    const double openMpCompatibleArea =
        threadAreas[0] + threadAreas[1] + threadAreas[2];
    const double openMpCompatibleVolume =
        threadVolumes[0] + threadVolumes[1] + threadVolumes[2];
    const double openMpCompatibleCurvatureEnergy =
        threadCurvatureEnergies[0] + threadCurvatureEnergies[1] + threadCurvatureEnergies[2];

    EXPECT_GT(std::abs(serialCurvatureEnergy), 1.0e-12);
    EXPECT_LE(max_abs_delta(serialComponents, openMpCompatibleComponents), forceTolerance);
    EXPECT_NEAR(openMpCompatibleArea, serialArea, scalarTolerance);
    EXPECT_NEAR(openMpCompatibleVolume, serialVolume, scalarTolerance);
    EXPECT_NEAR(openMpCompatibleCurvatureEnergy, serialCurvatureEnergy, scalarTolerance);
}

TEST(SurfaceFlatMeshCharacterization, PeriodicFlatMeshKeepsInteriorRegularAndPlanar)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;

    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();

    ASSERT_EQ(param.nFaceX, 8);
    ASSERT_EQ(param.nFaceY, 10);
    ASSERT_EQ(mesh.vertices.size(), 99);
    ASSERT_EQ(mesh.faces.size(), 160);
    EXPECT_EQ(count_ghost_vertices(mesh), 84);
    EXPECT_EQ(count_ghost_faces(mesh), 144);

    int physicalFaceCount = 0;
    for (const Face &face : mesh.faces)
    {
        if (!face.isGhost)
        {
            ++physicalFaceCount;
            EXPECT_EQ(face.oneRingVertices.size(), 12);
        }
    }
    ASSERT_EQ(physicalFaceCount, 16);

    mesh.calculate_element_area_volume();

    double area = 0.0;
    double volume = 0.0;
    mesh.sum_membrane_area_and_volume(area, volume);

    EXPECT_NEAR(area, physicalFaceCount * param.elementTriangleArea0, 1.0e-10);
    EXPECT_NEAR(volume, 0.0, 1.0e-10);

    for (const Face &face : mesh.faces)
    {
        if (face.isGhost)
        {
            EXPECT_DOUBLE_EQ(face.elementArea, 0.0);
            EXPECT_DOUBLE_EQ(face.elementVolume, 0.0);
        }
        else
        {
            EXPECT_NEAR(face.elementArea, param.elementTriangleArea0, 1.0e-11);
            EXPECT_NEAR(face.elementVolume, 0.0, 1.0e-11);
        }
    }
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     DefaultRouteIsInactiveWithoutRuntimeOptIn)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", nullptr);

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);

    EXPECT_FALSE(opensubdiv_regular_production_routing_requested());
    EXPECT_TRUE(build_opensubdiv_regular_shape_functions_by_face(mesh).empty());
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     RowDiagnosticsDoNotEnableProductionRouting)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", nullptr);

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);

    const OpenSubdivRegularRowDiagnostics diagnostics =
        diagnose_opensubdiv_regular_row_semantics(mesh);
    EXPECT_FALSE(diagnostics.productionRouteEnabled);
    EXPECT_FALSE(opensubdiv_regular_production_routing_requested());
    EXPECT_TRUE(build_opensubdiv_regular_shape_functions_by_face(mesh).empty());
}

#ifndef USE_OPENSUBDIV_REGULAR
TEST(OpenSubdivRegularProductionRoutingGuard,
     DefaultBuildFailsLoudlyWhenRuntimeOptInIsRequested)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", "1");

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);

    EXPECT_TRUE(opensubdiv_regular_production_routing_requested());
    EXPECT_THROW(build_opensubdiv_regular_shape_functions_by_face(mesh),
                 std::runtime_error);
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     DefaultBuildReportsRowDiagnosticsUnavailable)
{
    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);

    const OpenSubdivRegularRowDiagnostics diagnostics =
        diagnose_opensubdiv_regular_row_semantics(mesh);
    EXPECT_FALSE(diagnostics.opensubdivCompiled);
    EXPECT_FALSE(diagnostics.productionRouteEnabled);
    EXPECT_FALSE(diagnostics.regularRowsMatchSlimedRows);
    EXPECT_EQ(diagnostics.comparedFaceCount, 0);
    EXPECT_EQ(diagnostics.comparedSampleCount, 0);
    EXPECT_TRUE(diagnostics.samples.empty());
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     DefaultBuildReportsProductionParityRecheckUnavailable)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", nullptr);

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);

    const OpenSubdivRegularProductionParityRecheck recheck =
        diagnose_opensubdiv_regular_production_call_parity(mesh);
    EXPECT_FALSE(recheck.opensubdivCompiled);
    EXPECT_FALSE(recheck.runtimeOptInRequested);
    EXPECT_FALSE(recheck.productionRouteEnabled);
    EXPECT_FALSE(recheck.routeInstalledInProduction);
    EXPECT_FALSE(recheck.generatedRoutedRows);
    EXPECT_FALSE(recheck.directVsRoutedMatch);
    EXPECT_EQ(recheck.comparedFaceCount, 0);
    EXPECT_EQ(recheck.comparedSampleCount, 0);
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     DefaultBuildFailsProductionParityRecheckWhenRuntimeOptInIsRequested)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", "1");

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);

    EXPECT_TRUE(opensubdiv_regular_production_routing_requested());
    EXPECT_THROW(diagnose_opensubdiv_regular_production_call_parity(mesh),
                 std::runtime_error);
}
#else
TEST(OpenSubdivRegularProductionRoutingGuard,
     OptInBuildKeepsUnprovenRegularRowsUnavailable)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", "1");

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;

    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();

    const std::vector<std::vector<Matrix>> routedShapeFunctions =
        build_opensubdiv_regular_shape_functions_by_face(mesh);
    EXPECT_TRUE(routedShapeFunctions.empty());
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     OptInRowDiagnosticsCompareOpenSubdivRowsAgainstSlimedRows)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", nullptr);

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;

    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();

    int physicalRegularFaceCount = 0;
    for (const Face &face : mesh.faces)
    {
        if (!face.isGhost && !face.isBoundary)
        {
            ASSERT_EQ(face.oneRingVertices.size(), 12);
            ++physicalRegularFaceCount;
        }
    }
    ASSERT_GT(physicalRegularFaceCount, 0);

    const OpenSubdivRegularRowDiagnostics diagnostics =
        diagnose_opensubdiv_regular_row_semantics(mesh);
    EXPECT_TRUE(diagnostics.opensubdivCompiled);
    EXPECT_FALSE(diagnostics.productionRouteEnabled);
    EXPECT_TRUE(diagnostics.regularRowsMatchSlimedRows);
    EXPECT_EQ(diagnostics.comparedFaceCount, physicalRegularFaceCount);
    EXPECT_EQ(diagnostics.comparedSampleCount,
              physicalRegularFaceCount *
                  static_cast<int>(mesh.param.shapeFunctions.size()));
    EXPECT_LE(diagnostics.maxAbsWeightDifferenceVsSlimedRows, 5.0e-6);
    ASSERT_EQ(diagnostics.samples.size(),
              static_cast<std::size_t>(diagnostics.comparedSampleCount));
    for (const OpenSubdivRegularRowDiagnosticSample &sample : diagnostics.samples)
    {
        EXPECT_TRUE(sample.stencilSourcesMatchFaceOneRing)
            << "face " << sample.faceIndex << " sample " << sample.sampleIndex;
        EXPECT_LE(sample.maxAbsWeightDifferenceVsSlimedRows, 5.0e-6)
            << "face " << sample.faceIndex << " sample " << sample.sampleIndex;
    }

    EXPECT_TRUE(build_opensubdiv_regular_shape_functions_by_face(mesh).empty());
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     OptInProductionCallParityRecheckReportsRemainingForceDeltaAndKeepsRouteDisabled)
{
    ScopedEnvVar env("SLIMED_USE_OPENSUBDIV_REGULAR", "1");

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    param.area0 = 2.75;
    param.vol0 = 0.82;

    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();

    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index);
        vertex.coord.set(2, 0, 0.03 * std::sin(0.7 * index)
                                   + 0.01 * std::cos(0.3 * index));
    }
    mesh.calculate_element_area_volume();
    mesh.sum_membrane_area_and_volume(mesh.param.area, mesh.param.vol);

    const OpenSubdivRegularProductionParityRecheck recheck =
        diagnose_opensubdiv_regular_production_call_parity(mesh);

    EXPECT_TRUE(recheck.opensubdivCompiled);
    EXPECT_TRUE(recheck.runtimeOptInRequested);
    EXPECT_FALSE(recheck.productionRouteEnabled);
    EXPECT_FALSE(recheck.routeInstalledInProduction);
    EXPECT_TRUE(recheck.generatedRoutedRows);
    EXPECT_TRUE(recheck.directRowsOverrideMatch);
    EXPECT_FALSE(recheck.directVsRoutedMatch);
    EXPECT_GT(recheck.comparedFaceCount, 0);
    EXPECT_EQ(recheck.comparedSampleCount,
              recheck.comparedFaceCount *
                  static_cast<int>(mesh.param.shapeFunctions.size()));
    EXPECT_LE(recheck.maxDirectRowsOverrideAreaDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideLegacyVolumeDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideMeanCurvatureDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideBendingEnergyDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideNormalDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideFBendDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideFAreaDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideFVolumeDifference, 1.0e-12);
    EXPECT_LE(recheck.maxDirectRowsOverrideScatterDifference, 1.0e-12);
    EXPECT_GT(recheck.maxRoutedRowWeightDifferenceVsSlimedRows, 0.0);
    EXPECT_LE(recheck.maxRoutedRowWeightDifferenceVsSlimedRows, 5.0e-6);
    EXPECT_GE(recheck.maxRoutedRowWeightDifferenceFaceIndex, 0);
    EXPECT_GE(recheck.maxRoutedRowWeightDifferenceSampleIndex, 0);
    EXPECT_LT(recheck.maxRoutedRowWeightDifferenceSampleIndex,
              static_cast<int>(mesh.param.shapeFunctions.size()));
    EXPECT_GE(recheck.maxRoutedRowWeightDifferenceRow, 0);
    EXPECT_LT(recheck.maxRoutedRowWeightDifferenceRow, 7);
    EXPECT_GE(recheck.maxRoutedRowWeightDifferenceSourceColumn, 0);
    EXPECT_LT(recheck.maxRoutedRowWeightDifferenceSourceColumn, 12);
    EXPECT_GE(recheck.maxRoutedRowWeightDifferenceSourceId, 0);
    ASSERT_LT(recheck.maxRoutedRowWeightDifferenceFaceIndex,
              static_cast<int>(mesh.faces.size()));
    EXPECT_EQ(
        recheck.maxRoutedRowWeightDifferenceSourceId,
        mesh.faces[recheck.maxRoutedRowWeightDifferenceFaceIndex]
            .oneRingVertices[recheck.maxRoutedRowWeightDifferenceSourceColumn]);
    EXPECT_TRUE(std::isfinite(
        recheck.maxRoutedRowWeightDifferenceDirectValue));
    EXPECT_TRUE(std::isfinite(
        recheck.maxRoutedRowWeightDifferenceRoutedValue));
    EXPECT_TRUE(std::isfinite(
        recheck.maxRoutedRowWeightDifferenceSignedDelta));
    EXPECT_NEAR(std::abs(recheck.maxRoutedRowWeightDifferenceSignedDelta),
                recheck.maxRoutedRowWeightDifferenceVsSlimedRows,
                1.0e-12);
    EXPECT_LE(recheck.maxAreaDifference, 5.0e-6);
    EXPECT_LE(recheck.maxLegacyVolumeDifference, 5.0e-6);
    EXPECT_LE(recheck.maxMeanCurvatureDifference, 5.0e-6);
    EXPECT_LE(recheck.maxBendingEnergyDifference, 5.0e-6);
    EXPECT_LE(recheck.maxNormalDifference, 5.0e-6);
    EXPECT_LE(recheck.maxFBendDifference, 5.0e-6);
    EXPECT_GT(recheck.maxFAreaDifference, 5.0e-6);
    EXPECT_GE(recheck.maxFAreaDifferenceFaceIndex, 0);
    EXPECT_GE(recheck.maxFAreaDifferenceLocalRow, 0);
    EXPECT_LT(recheck.maxFAreaDifferenceLocalRow, 12);
    EXPECT_GE(recheck.maxFAreaDifferenceSourceId, 0);
    ASSERT_LT(recheck.maxFAreaDifferenceFaceIndex,
              static_cast<int>(mesh.faces.size()));
    EXPECT_EQ(recheck.maxFAreaDifferenceSourceId,
              mesh.faces[recheck.maxFAreaDifferenceFaceIndex]
                  .oneRingVertices[recheck.maxFAreaDifferenceLocalRow]);
    EXPECT_GE(recheck.maxFAreaDifferenceAxis, 0);
    EXPECT_LT(recheck.maxFAreaDifferenceAxis, 3);
    EXPECT_TRUE(std::isfinite(recheck.maxFAreaDifferenceDirectValue));
    EXPECT_TRUE(std::isfinite(recheck.maxFAreaDifferenceRoutedValue));
    EXPECT_TRUE(std::isfinite(recheck.maxFAreaDifferenceSignedDelta));
    EXPECT_NEAR(std::abs(recheck.maxFAreaDifferenceSignedDelta),
                recheck.maxFAreaDifference,
                1.0e-12);
    EXPECT_GT(recheck.maxFVolumeDifference, 5.0e-6);
    EXPECT_GE(recheck.maxFVolumeDifferenceFaceIndex, 0);
    EXPECT_GE(recheck.maxFVolumeDifferenceLocalRow, 0);
    EXPECT_LT(recheck.maxFVolumeDifferenceLocalRow, 12);
    EXPECT_GE(recheck.maxFVolumeDifferenceSourceId, 0);
    ASSERT_LT(recheck.maxFVolumeDifferenceFaceIndex,
              static_cast<int>(mesh.faces.size()));
    EXPECT_EQ(recheck.maxFVolumeDifferenceSourceId,
              mesh.faces[recheck.maxFVolumeDifferenceFaceIndex]
                  .oneRingVertices[recheck.maxFVolumeDifferenceLocalRow]);
    EXPECT_GE(recheck.maxFVolumeDifferenceAxis, 0);
    EXPECT_LT(recheck.maxFVolumeDifferenceAxis, 3);
    EXPECT_TRUE(std::isfinite(recheck.maxFVolumeDifferenceDirectValue));
    EXPECT_TRUE(std::isfinite(recheck.maxFVolumeDifferenceRoutedValue));
    EXPECT_TRUE(std::isfinite(recheck.maxFVolumeDifferenceSignedDelta));
    EXPECT_NEAR(std::abs(recheck.maxFVolumeDifferenceSignedDelta),
                recheck.maxFVolumeDifference,
                1.0e-12);
    EXPECT_GT(recheck.maxScatterDifference, 5.0e-6);
    EXPECT_GE(recheck.maxScatterDifferenceVertexIndex, 0);
    EXPECT_GE(recheck.maxScatterDifferenceComponent, 0);
    EXPECT_LT(recheck.maxScatterDifferenceComponent, 9);
    EXPECT_TRUE(std::isfinite(recheck.maxScatterDifferenceDirectValue));
    EXPECT_TRUE(std::isfinite(recheck.maxScatterDifferenceRoutedValue));
    EXPECT_TRUE(std::isfinite(recheck.maxScatterDifferenceSignedDelta));
    EXPECT_NEAR(std::abs(recheck.maxScatterDifferenceSignedDelta),
                recheck.maxScatterDifference,
                1.0e-12);
    EXPECT_TRUE(std::isfinite(
        recheck.maxFAreaDifferencePerRowWeightDifference));
    EXPECT_TRUE(std::isfinite(
        recheck.maxFVolumeDifferencePerRowWeightDifference));
    EXPECT_TRUE(std::isfinite(
        recheck.maxScatterDifferencePerRowWeightDifference));
    EXPECT_GT(recheck.maxFAreaDifferencePerRowWeightDifference, 1.0);
    EXPECT_GT(recheck.maxFVolumeDifferencePerRowWeightDifference, 1.0);
    EXPECT_GT(recheck.maxScatterDifferencePerRowWeightDifference, 1.0);
    EXPECT_TRUE(build_opensubdiv_regular_shape_functions_by_face(mesh).empty());
}

TEST(OpenSubdivRegularProductionRoutingGuard,
     RuntimeOptInFallsBackToDirectRegularProductionSemantics)
{
    auto configure_param = [](Param &param) {
        param.VERBOSE_MODE = false;
        param.boundaryCondition = BoundaryType::Periodic;
        param.sideX = 40.0;
        param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;
        param.kCurv = 47.5;
        param.uSurf = 130.0;
        param.uVol = 65.0;
        param.area0 = 2.75;
        param.vol0 = 0.82;
    };

    auto setup_mesh = [](Mesh &mesh) {
        ::testing::internal::CaptureStdout();
        mesh.setup_flat();
        ::testing::internal::GetCapturedStdout();

        for (Vertex &vertex : mesh.vertices)
        {
            const double index = static_cast<double>(vertex.index);
            vertex.coord.set(2, 0, 0.03 * std::sin(0.7 * index)
                                       + 0.01 * std::cos(0.3 * index));
        }
    };

    ScopedEnvVar disabledEnv("SLIMED_USE_OPENSUBDIV_REGULAR", nullptr);
    Param defaultParam;
    configure_param(defaultParam);
    Mesh defaultMesh(defaultParam);
    setup_mesh(defaultMesh);
    defaultMesh.calculate_element_area_volume();
    defaultMesh.sum_membrane_area_and_volume(defaultMesh.param.area,
                                             defaultMesh.param.vol);

    {
        ScopedEnvVar enabledEnv("SLIMED_USE_OPENSUBDIV_REGULAR", "1");
        Param routedParam;
        configure_param(routedParam);
        Mesh routedMesh(routedParam);
        setup_mesh(routedMesh);
        routedMesh.calculate_element_area_volume();
        routedMesh.sum_membrane_area_and_volume(routedMesh.param.area,
                                                routedMesh.param.vol);
        const std::vector<std::vector<Matrix>> routedShapeFunctions =
            build_opensubdiv_regular_shape_functions_by_face(routedMesh);

        ASSERT_EQ(routedMesh.faces.size(), defaultMesh.faces.size());
        ASSERT_EQ(routedMesh.vertices.size(), defaultMesh.vertices.size());
        EXPECT_TRUE(routedShapeFunctions.empty());

        EXPECT_NEAR(routedMesh.param.area,
                    defaultMesh.param.area,
                    1.0e-12);
        EXPECT_NEAR(routedMesh.param.vol,
                    defaultMesh.param.vol,
                    1.0e-12);

        for (int faceIndex = 0;
             faceIndex < static_cast<int>(defaultMesh.faces.size());
             ++faceIndex)
        {
            const Face &expected = defaultMesh.faces[faceIndex];
            const Face &actual = routedMesh.faces[faceIndex];
            if (expected.isGhost)
            {
                continue;
            }
            EXPECT_NEAR(actual.elementArea, expected.elementArea, 1.0e-12);
            EXPECT_NEAR(actual.elementVolume, expected.elementVolume, 1.0e-12);

            Matrix controlPoints = make_one_ring_control_points(defaultMesh,
                                                                expected);
            std::vector<Matrix> coordinateColumns =
                control_point_rows_to_columns(controlPoints);

            double defaultMeanCurv = 0.0;
            double defaultEBend = 0.0;
            Matrix defaultNorm = mat_calloc(3, 1);
            Matrix defaultFBend = mat_calloc(12, 3);
            Matrix defaultFArea = mat_calloc(12, 3);
            Matrix defaultFVolume = mat_calloc(12, 3);
            defaultMesh.element_energy_force_regular(coordinateColumns,
                                                     defaultMesh.faces[faceIndex],
                                                     expected.spontCurvature,
                                                     defaultMeanCurv,
                                                     defaultNorm,
                                                     defaultEBend,
                                                     defaultFBend,
                                                     defaultFArea,
                                                     defaultFVolume,
                                                     true);

            double routedMeanCurv = 0.0;
            double routedEBend = 0.0;
            Matrix routedNorm = mat_calloc(3, 1);
            Matrix routedFBend = mat_calloc(12, 3);
            Matrix routedFArea = mat_calloc(12, 3);
            Matrix routedFVolume = mat_calloc(12, 3);
            routedMesh.element_energy_force_regular(coordinateColumns,
                                                    routedMesh.faces[faceIndex],
                                                    actual.spontCurvature,
                                                    routedMeanCurv,
                                                    routedNorm,
                                                    routedEBend,
                                                    routedFBend,
                                                    routedFArea,
                                                    routedFVolume,
                                                    true);

            EXPECT_NEAR(routedMeanCurv, defaultMeanCurv, 1.0e-12);
            EXPECT_NEAR(routedEBend, defaultEBend, 1.0e-10);
            expect_matrix_near(routedNorm, defaultNorm, 1.0e-12, "fallback normal");
            expect_matrix_near(routedFBend,
                               defaultFBend,
                               1.0e-10,
                               "fallback curvature force");
            expect_matrix_near(routedFArea,
                               defaultFArea,
                               1.0e-10,
                               "fallback area force");
            expect_matrix_near(routedFVolume,
                               defaultFVolume,
                               1.0e-10,
                               "fallback volume force");
        }
    }
}
#endif

TEST(SurfaceFlatMeshCharacterization, RegularAreaVolumeUsesLimitSurfaceEvaluatorEquivalentToDirectRows)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;

    Mesh mesh(param);
    ::testing::internal::CaptureStdout();
    mesh.setup_flat();
    ::testing::internal::GetCapturedStdout();

    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index);
        vertex.coord.set(2, 0, 0.01 * std::sin(0.7 * index)
                                   + 0.005 * std::cos(0.3 * index));
    }

    std::vector<AreaVolume> expected(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        if (!face.isGhost)
        {
            ASSERT_EQ(face.oneRingVertices.size(), 12);
            expected[face.index] = direct_regular_patch_area_volume(
                param,
                make_one_ring_control_points(mesh, face));
        }
    }

    mesh.calculate_element_area_volume();

    for (const Face &face : mesh.faces)
    {
        if (!face.isGhost)
        {
            EXPECT_NEAR(face.elementArea, expected[face.index].area, 1.0e-12);
            EXPECT_NEAR(face.elementVolume, expected[face.index].volume, 1.0e-12);
        }
    }
}
