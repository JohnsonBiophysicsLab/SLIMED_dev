#include "mesh/Limit_surface_evaluator.hpp"

#include <cstddef>
#include <stdexcept>
#include <string>

#include "mesh/Gauss_quadrature.hpp"

namespace
{
constexpr int kLimitSurfaceDerivativeRowCount = 7;

void validate_matrix_dimensions(const Matrix &matrix,
                                const int expectedRows,
                                const int expectedCols,
                                const char *name)
{
    if (matrix.nrow() != expectedRows || matrix.ncol() != expectedCols)
    {
        throw std::invalid_argument(std::string(name) + " has incompatible dimensions");
    }
}

Matrix shape_row_to_column(const Matrix &shapeDotControlPoints,
                           const LimitSurfaceDerivativeRow row)
{
    Matrix column(3, 1, true);
    const int rowIndex = static_cast<int>(row);
    for (int axis = 0; axis < 3; ++axis)
    {
        column.set(axis, 0, shapeDotControlPoints.get(rowIndex, axis));
    }
    return column;
}
} // namespace

double LimitSurfaceWeightedSample::row_weight(const LimitSurfaceDerivativeRow row,
                                              const int sourceId) const
{
    const int rowIndex = static_cast<int>(row);
    if (rowIndex < 0 || rowIndex >= kLimitSurfaceDerivativeRowCount)
    {
        throw std::invalid_argument("row is outside the limit-surface derivative row range");
    }
    validate_matrix_dimensions(rowWeights,
                               kLimitSurfaceDerivativeRowCount,
                               static_cast<int>(sourceIds.size()),
                               "rowWeights");

    double weight = 0.0;
    for (int sourceIndex = 0; sourceIndex < static_cast<int>(sourceIds.size()); ++sourceIndex)
    {
        if (sourceIds[sourceIndex] == sourceId)
        {
            weight += rowWeights.get(rowIndex, sourceIndex);
        }
    }
    return weight;
}

int SlimedLoopLimitSurfaceEvaluator::regular_patch_control_point_count() const
{
    return kRegularPatchControlPointCount;
}

Matrix SlimedLoopLimitSurfaceEvaluator::shape_function(const Matrix &vwu) const
{
    validate_matrix_dimensions(vwu, 1, 3, "vwu");

    Matrix shapeFunction(kShapeFunctionRowCount,
                         kRegularPatchControlPointCount,
                         true);
    get_shapefunction(vwu, shapeFunction);
    return shapeFunction;
}

LimitSurfaceEvaluation SlimedLoopLimitSurfaceEvaluator::evaluate(
    const Matrix &vwu,
    const Matrix &controlPoints) const
{
    return evaluate_shape_function(shape_function(vwu), controlPoints);
}

LimitSurfaceWeightedSample SlimedLoopLimitSurfaceEvaluator::evaluate_weighted(
    const Matrix &vwu,
    const Matrix &controlPoints,
    const std::vector<int> &sourceIds) const
{
    return evaluate_weighted_shape_function(shape_function(vwu),
                                            controlPoints,
                                            sourceIds);
}

LimitSurfaceEvaluation SlimedLoopLimitSurfaceEvaluator::evaluate_shape_function(
    const Matrix &shapeFunction,
    const Matrix &controlPoints) const
{
    validate_matrix_dimensions(shapeFunction,
                               kShapeFunctionRowCount,
                               kRegularPatchControlPointCount,
                               "shapeFunction");
    validate_matrix_dimensions(controlPoints,
                               kRegularPatchControlPointCount,
                               kSpatialDimension,
                               "controlPoints");

    Matrix shapeDotControlPoints = shapeFunction * controlPoints;

    LimitSurfaceEvaluation evaluation;
    evaluation.position = shape_row_to_column(shapeDotControlPoints,
                                              LimitSurfaceDerivativeRow::Position);
    evaluation.firstDerivativeV = shape_row_to_column(shapeDotControlPoints,
                                                      LimitSurfaceDerivativeRow::FirstDerivativeV);
    evaluation.firstDerivativeW = shape_row_to_column(shapeDotControlPoints,
                                                      LimitSurfaceDerivativeRow::FirstDerivativeW);
    evaluation.secondDerivativeVV = shape_row_to_column(shapeDotControlPoints,
                                                        LimitSurfaceDerivativeRow::SecondDerivativeVV);
    evaluation.secondDerivativeWW = shape_row_to_column(shapeDotControlPoints,
                                                        LimitSurfaceDerivativeRow::SecondDerivativeWW);
    evaluation.mixedDerivativeVW = shape_row_to_column(shapeDotControlPoints,
                                                       LimitSurfaceDerivativeRow::MixedDerivativeVW);
    evaluation.mixedDerivativeWV = shape_row_to_column(shapeDotControlPoints,
                                                       LimitSurfaceDerivativeRow::MixedDerivativeWV);
    return evaluation;
}

LimitSurfaceWeightedSample SlimedLoopLimitSurfaceEvaluator::evaluate_weighted_shape_function(
    const Matrix &shapeFunction,
    const Matrix &controlPoints,
    const std::vector<int> &sourceIds) const
{
    validate_matrix_dimensions(shapeFunction,
                               kShapeFunctionRowCount,
                               kRegularPatchControlPointCount,
                               "shapeFunction");
    validate_matrix_dimensions(controlPoints,
                               kRegularPatchControlPointCount,
                               kSpatialDimension,
                               "controlPoints");
    if (sourceIds.size() != static_cast<std::size_t>(kRegularPatchControlPointCount))
    {
        throw std::invalid_argument("sourceIds has incompatible dimensions");
    }

    LimitSurfaceWeightedSample sample;
    sample.evaluation = evaluate_shape_function(shapeFunction, controlPoints);
    sample.sourceIds = sourceIds;
    sample.rowWeights = shapeFunction;
    return sample;
}
