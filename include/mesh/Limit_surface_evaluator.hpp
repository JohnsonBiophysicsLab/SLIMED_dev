/**
 * @file Limit_surface_evaluator.hpp
 * @brief Backend-neutral contract for evaluating Loop limit-surface samples.
 */

#pragma once

#include "linalg/Linear_algebra.hpp"

/**
 * @brief Row semantics for SLIMED's regular-patch limit-surface shape matrix.
 *
 * The current SLIMED Loop backend evaluates a regular triangular patch with a
 * 7 x 12 matrix: one row of position weights, two rows of first derivatives,
 * two rows of pure second derivatives, and two rows for the mixed derivative.
 */
enum class LimitSurfaceDerivativeRow
{
    Position = 0,
    FirstDerivativeV = 1,
    FirstDerivativeW = 2,
    SecondDerivativeVV = 3,
    SecondDerivativeWW = 4,
    MixedDerivativeVW = 5,
    MixedDerivativeWV = 6
};

/**
 * @brief Geometry evaluated at one limit-surface quadrature/sample point.
 *
 * All vectors are 3 x 1 column matrices. The derivative names follow the
 * existing SLIMED barycentric convention used by get_shapefunction(v,w,u).
 */
struct LimitSurfaceEvaluation
{
    Matrix position = Matrix(3, 1, true);
    Matrix firstDerivativeV = Matrix(3, 1, true);
    Matrix firstDerivativeW = Matrix(3, 1, true);
    Matrix secondDerivativeVV = Matrix(3, 1, true);
    Matrix secondDerivativeWW = Matrix(3, 1, true);
    Matrix mixedDerivativeVW = Matrix(3, 1, true);
    Matrix mixedDerivativeWV = Matrix(3, 1, true);
};

/**
 * @brief Interface for evaluating a regular limit-surface patch.
 *
 * Implementations consume the ordered 12-control-vertex regular patch used by
 * Face::oneRingVertices and return the geometry quantities required by area,
 * curvature, energy, and force calculations. Irregular 11-control patches are
 * intentionally outside this first contract slice.
 */
class LimitSurfaceEvaluator
{
public:
    virtual ~LimitSurfaceEvaluator() = default;

    virtual int regular_patch_control_point_count() const = 0;

    virtual LimitSurfaceEvaluation evaluate(const Matrix &vwu,
                                            const Matrix &controlPoints) const = 0;
};

/**
 * @brief Current SLIMED Loop backend wrapper for regular 12-control patches.
 *
 * This class adapts the existing get_shapefunction implementation without
 * changing production behavior or introducing an external subdivision backend.
 */
class SlimedLoopLimitSurfaceEvaluator final : public LimitSurfaceEvaluator
{
public:
    static constexpr int kShapeFunctionRowCount = 7;
    static constexpr int kRegularPatchControlPointCount = 12;
    static constexpr int kSpatialDimension = 3;

    int regular_patch_control_point_count() const override;

    Matrix shape_function(const Matrix &vwu) const;

    LimitSurfaceEvaluation evaluate(const Matrix &vwu,
                                    const Matrix &controlPoints) const override;

    LimitSurfaceEvaluation evaluate_shape_function(const Matrix &shapeFunction,
                                                   const Matrix &controlPoints) const;
};
