#include "mesh/OpenSubdiv_regular_evaluator.hpp"

#include "mesh/Face.hpp"
#include "mesh/Mesh.hpp"

#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <array>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>

namespace
{
constexpr const char *kOpenSubdivRegularEnv =
    "SLIMED_USE_OPENSUBDIV_REGULAR";

bool env_value_is_enabled(const char *value)
{
    if (value == nullptr || value[0] == '\0')
    {
        return false;
    }
    const std::string text(value);
    return text != "0" && text != "false" && text != "FALSE" &&
           text != "off" && text != "OFF";
}
} // namespace

bool opensubdiv_regular_production_routing_requested()
{
    return env_value_is_enabled(std::getenv(kOpenSubdivRegularEnv));
}

#ifdef USE_OPENSUBDIV_REGULAR

#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>
#include <opensubdiv/version.h>

#include <memory>

using namespace OpenSubdiv;

namespace
{
constexpr int kRegularControlPointCount = 12;
constexpr int kDerivativeRowCount = 7;
// OpenSubdiv-enabled binaries may route supported regular faces only when the
// separate runtime opt-in is also present. Default builds use the stub below.
constexpr bool kOpenSubdivRegularProductionRouteEnabled = true;
constexpr double kOpenSubdivRegularRowTolerance = 5.0e-6;
constexpr double kOpenSubdivRegularResidualScaleFloor = 1.0e-12;

class RegularCacheFingerprintBuilder
{
  public:
    void add_uint64(std::uint64_t value)
    {
        for (int shift = 0; shift < 64; shift += 8)
        {
            hash_ ^= static_cast<unsigned char>((value >> shift) & 0xffu);
            hash_ *= 1099511628211ull;
        }
    }

    void add_int(int value)
    {
        add_uint64(static_cast<std::uint64_t>(static_cast<std::int64_t>(value)));
    }

    void add_bool(bool value) { add_uint64(value ? 1u : 0u); }

    void add_double(double value)
    {
        std::uint64_t bits = 0;
        static_assert(sizeof(bits) == sizeof(value), "double fingerprint width");
        std::memcpy(&bits, &value, sizeof(bits));
        add_uint64(bits);
    }

    void add_matrix(const Matrix &matrix)
    {
        add_int(matrix.nrow());
        add_int(matrix.ncol());
        for (int row = 0; row < matrix.nrow(); ++row)
        {
            for (int column = 0; column < matrix.ncol(); ++column)
            {
                add_double(matrix.get(row, column));
            }
        }
    }

    std::uint64_t value() const { return hash_; }

  private:
    std::uint64_t hash_ = 1469598103934665603ull;
};

std::uint64_t regular_limit_surface_cache_fingerprint(const Mesh &mesh)
{
    RegularCacheFingerprintBuilder fingerprint;
    fingerprint.add_uint64(1u); // Cache schema version.
    fingerprint.add_int(OPENSUBDIV_VERSION_NUMBER);
    fingerprint.add_int(static_cast<int>(Sdc::SCHEME_LOOP));
    fingerprint.add_int(
        static_cast<int>(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY));
    fingerprint.add_int(3); // Adaptive refinement depth.
    fingerprint.add_bool(true); // First derivatives.
    fingerprint.add_bool(true); // Second derivatives.
    fingerprint.add_int(static_cast<int>(sizeof(double)));
    fingerprint.add_double(kOpenSubdivRegularRowTolerance);

    fingerprint.add_uint64(mesh.vertices.size());
    fingerprint.add_uint64(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        fingerprint.add_int(face.index);
        fingerprint.add_bool(face.isBoundary);
        fingerprint.add_bool(face.isGhost);
        fingerprint.add_uint64(face.adjacentVertices.size());
        for (int source : face.adjacentVertices)
        {
            fingerprint.add_int(source);
        }
        fingerprint.add_uint64(face.oneRingVertices.size());
        for (int source : face.oneRingVertices)
        {
            fingerprint.add_int(source);
        }
    }

    fingerprint.add_matrix(mesh.param.VWU);
    fingerprint.add_matrix(mesh.param.gaussQuadratureCoeff);
    fingerprint.add_uint64(mesh.param.shapeFunctions.size());
    for (const Matrix &rows : mesh.param.shapeFunctions)
    {
        fingerprint.add_matrix(rows);
    }
    return fingerprint.value();
}

struct RefinerDeleter
{
    void operator()(Far::TopologyRefiner *refiner) const
    {
        delete refiner;
    }
};

std::unique_ptr<Far::TopologyRefiner, RefinerDeleter>
create_refiner_for_mesh(const Mesh &mesh)
{
    using Descriptor = Far::TopologyDescriptor;

    std::vector<int> vertsPerFace;
    std::vector<int> vertIndices;
    vertsPerFace.reserve(mesh.faces.size());
    vertIndices.reserve(mesh.faces.size() * 3);

    for (const Face &face : mesh.faces)
    {
        if (face.adjacentVertices.size() != 3)
        {
            throw std::runtime_error(
                "OpenSubdiv regular routing requires triangular faces.");
        }
        vertsPerFace.push_back(3);
        for (int vertex : face.adjacentVertices)
        {
            if (vertex < 0 ||
                vertex >= static_cast<int>(mesh.vertices.size()))
            {
                throw std::runtime_error(
                    "OpenSubdiv regular routing found an invalid face vertex index.");
            }
            vertIndices.push_back(vertex);
        }
    }

    Descriptor desc;
    desc.numVertices = static_cast<int>(mesh.vertices.size());
    desc.numFaces = static_cast<int>(vertsPerFace.size());
    desc.numVertsPerFace = vertsPerFace.data();
    desc.vertIndicesPerFace = vertIndices.data();

    Sdc::Options options;
    options.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);

    return std::unique_ptr<Far::TopologyRefiner, RefinerDeleter>(
        Far::TopologyRefinerFactory<Descriptor>::Create(
            desc,
            Far::TopologyRefinerFactory<Descriptor>::Options(
                Sdc::SCHEME_LOOP, options)));
}

template <typename Real>
double stencil_weight_for_source(const Far::LimitStencilReal<Real> &stencil,
                                 const Real *weights,
                                 const int sourceId)
{
    double result = 0.0;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int index = 0; index < stencil.GetSize(); ++index)
    {
        if (indices[index] == sourceId)
        {
            result += static_cast<double>(weights[index]);
        }
    }
    return result;
}

template <typename Real>
Matrix shape_function_from_stencil(const Far::LimitStencilReal<Real> &stencil,
                                   const std::vector<int> &sourceIds)
{
    const std::array<const Real *, kDerivativeRowCount> rowWeights = {
        stencil.GetWeights(),
        stencil.GetDuWeights(),
        stencil.GetDvWeights(),
        stencil.GetDuuWeights(),
        stencil.GetDvvWeights(),
        stencil.GetDuvWeights(),
        stencil.GetDuvWeights(),
    };

    Matrix shapeFunction(kDerivativeRowCount, kRegularControlPointCount, true);
    for (int row = 0; row < kDerivativeRowCount; ++row)
    {
        for (int col = 0; col < kRegularControlPointCount; ++col)
        {
            shapeFunction.set(row,
                              col,
                              stencil_weight_for_source(stencil,
                                                        rowWeights[row],
                                                        sourceIds[col]));
        }
    }
    return shapeFunction;
}

template <typename Real>
std::set<int> stencil_source_set(const Far::LimitStencilReal<Real> &stencil)
{
    std::set<int> sources;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int index = 0; index < stencil.GetSize(); ++index)
    {
        sources.insert(indices[index]);
    }
    return sources;
}

template <typename Real>
bool stencil_sources_match_face_one_ring(
    const Far::LimitStencilReal<Real> &stencil,
    const std::vector<int> &sourceIds)
{
    return stencil_source_set(stencil) ==
           std::set<int>(sourceIds.begin(), sourceIds.end());
}

double max_abs_matrix_difference(const Matrix &lhs, const Matrix &rhs)
{
    if (lhs.nrow() != rhs.nrow() || lhs.ncol() != rhs.ncol())
    {
        throw std::runtime_error(
            "OpenSubdiv regular row diagnostics require matching matrix dimensions.");
    }

    double maxDifference = 0.0;
    for (int row = 0; row < lhs.nrow(); ++row)
    {
        for (int col = 0; col < lhs.ncol(); ++col)
        {
            maxDifference = std::max(maxDifference,
                                     std::abs(lhs.get(row, col) -
                                              rhs.get(row, col)));
        }
    }
    return maxDifference;
}

bool shape_functions_match_frozen_regular_rows(
    const std::vector<Matrix> &shapeFunctions,
    const std::vector<Matrix> &frozenRows)
{
    if (shapeFunctions.size() != frozenRows.size())
    {
        return false;
    }
    for (int sample = 0; sample < static_cast<int>(shapeFunctions.size());
         ++sample)
    {
        if (max_abs_matrix_difference(shapeFunctions[sample],
                                      frozenRows[sample]) >
            kOpenSubdivRegularRowTolerance)
        {
            return false;
        }
    }
    return true;
}

void update_max_abs_matrix_difference(double &target,
                                      const Matrix &lhs,
                                      const Matrix &rhs)
{
    target = std::max(target, max_abs_matrix_difference(lhs, rhs));
}

void update_max_abs_vector_difference(double &target,
                                      const std::vector<double> &lhs,
                                      const std::vector<double> &rhs)
{
    if (lhs.size() != rhs.size())
    {
        throw std::runtime_error(
            "OpenSubdiv regular parity recheck requires matching vector dimensions.");
    }

    for (std::size_t index = 0; index < lhs.size(); ++index)
    {
        target = std::max(target, std::abs(lhs[index] - rhs[index]));
    }
}

void update_max_abs_matrix_difference_with_location(double &target,
                                                   int &targetFaceIndex,
                                                   int &targetRow,
                                                   int &targetSourceId,
                                                   int &targetAxis,
                                                   double &targetDirectValue,
                                                   double &targetRoutedValue,
                                                   double &targetSignedDelta,
                                                   const int faceIndex,
                                                   const std::vector<int> &sourceIds,
                                                   const Matrix &lhs,
                                                   const Matrix &rhs)
{
    if (lhs.nrow() != rhs.nrow() || lhs.ncol() != rhs.ncol())
    {
        throw std::runtime_error(
            "OpenSubdiv regular residual diagnostics require matching matrix dimensions.");
    }
    if (lhs.nrow() > static_cast<int>(sourceIds.size()))
    {
        throw std::runtime_error(
            "OpenSubdiv regular residual diagnostics require source ids for every force row.");
    }

    for (int row = 0; row < lhs.nrow(); ++row)
    {
        for (int axis = 0; axis < lhs.ncol(); ++axis)
        {
            const double difference =
                std::abs(lhs.get(row, axis) - rhs.get(row, axis));
            if (difference > target)
            {
                target = difference;
                targetFaceIndex = faceIndex;
                targetRow = row;
                targetSourceId = sourceIds[row];
                targetAxis = axis;
                targetDirectValue = lhs.get(row, axis);
                targetRoutedValue = rhs.get(row, axis);
                targetSignedDelta = targetRoutedValue - targetDirectValue;
            }
        }
    }
}

void update_max_row_weight_difference_with_location(
    OpenSubdivRegularProductionParityRecheck &recheck,
    const int faceIndex,
    const int sampleIndex,
    const std::vector<int> &sourceIds,
    const Matrix &directRows,
    const Matrix &routedRows)
{
    if (directRows.nrow() != routedRows.nrow() ||
        directRows.ncol() != routedRows.ncol())
    {
        throw std::runtime_error(
            "OpenSubdiv regular row residual diagnostics require matching matrix dimensions.");
    }
    if (directRows.ncol() > static_cast<int>(sourceIds.size()))
    {
        throw std::runtime_error(
            "OpenSubdiv regular row residual diagnostics require source ids for every row-weight column.");
    }

    for (int row = 0; row < directRows.nrow(); ++row)
    {
        for (int col = 0; col < directRows.ncol(); ++col)
        {
            const double difference =
                std::abs(directRows.get(row, col) - routedRows.get(row, col));
            if (difference > recheck.maxRoutedRowWeightDifferenceVsSlimedRows)
            {
                recheck.maxRoutedRowWeightDifferenceVsSlimedRows = difference;
                recheck.maxRoutedRowWeightDifferenceFaceIndex = faceIndex;
                recheck.maxRoutedRowWeightDifferenceSampleIndex = sampleIndex;
                recheck.maxRoutedRowWeightDifferenceRow = row;
                recheck.maxRoutedRowWeightDifferenceSourceColumn = col;
                recheck.maxRoutedRowWeightDifferenceSourceId =
                    sourceIds[col];
                recheck.maxRoutedRowWeightDifferenceDirectValue =
                    directRows.get(row, col);
                recheck.maxRoutedRowWeightDifferenceRoutedValue =
                    routedRows.get(row, col);
                recheck.maxRoutedRowWeightDifferenceSignedDelta =
                    recheck.maxRoutedRowWeightDifferenceRoutedValue -
                    recheck.maxRoutedRowWeightDifferenceDirectValue;
            }
        }
    }
}

std::vector<Matrix> control_point_rows_to_columns_for_face(const Mesh &mesh,
                                                           const Face &face)
{
    std::vector<Matrix> columns;
    columns.reserve(face.oneRingVertices.size());
    for (int sourceId : face.oneRingVertices)
    {
        Matrix column(3, 1, true);
        column.set(0, 0, mesh.vertices[sourceId].coord.get(0, 0));
        column.set(1, 0, mesh.vertices[sourceId].coord.get(1, 0));
        column.set(2, 0, mesh.vertices[sourceId].coord.get(2, 0));
        columns.push_back(column);
    }
    return columns;
}

void accumulate_scatter_rows(std::vector<double> &target,
                             const Face &face,
                             const Matrix &fBend,
                             const Matrix &fArea,
                             const Matrix &fVolume)
{
    constexpr int kForceComponentsPerVertex = 9;
    for (int row = 0; row < static_cast<int>(face.oneRingVertices.size()); ++row)
    {
        const int sourceId = face.oneRingVertices[row];
        const int baseIndex = sourceId * kForceComponentsPerVertex;
        for (int axis = 0; axis < 3; ++axis)
        {
            target[baseIndex + axis] += fBend.get(row, axis);
            target[baseIndex + 3 + axis] += fArea.get(row, axis);
            target[baseIndex + 6 + axis] += fVolume.get(row, axis);
        }
    }
}

void update_max_abs_scatter_difference_with_location(
    OpenSubdivRegularProductionParityRecheck &recheck,
    const std::vector<double> &lhs,
    const std::vector<double> &rhs)
{
    if (lhs.size() != rhs.size())
    {
        throw std::runtime_error(
            "OpenSubdiv regular parity recheck requires matching scatter dimensions.");
    }

    constexpr int kForceComponentsPerVertex = 9;
    for (std::size_t index = 0; index < lhs.size(); ++index)
    {
        const double difference = std::abs(lhs[index] - rhs[index]);
        if (difference > recheck.maxScatterDifference)
        {
            recheck.maxScatterDifference = difference;
            recheck.maxScatterDifferenceVertexIndex =
                static_cast<int>(index / kForceComponentsPerVertex);
            recheck.maxScatterDifferenceComponent =
                static_cast<int>(index % kForceComponentsPerVertex);
            if (recheck.maxScatterDifferenceComponent < 3)
            {
                recheck.maxScatterDifferenceForceKind = "fBend";
                recheck.maxScatterDifferenceAxis =
                    recheck.maxScatterDifferenceComponent;
            }
            else if (recheck.maxScatterDifferenceComponent < 6)
            {
                recheck.maxScatterDifferenceForceKind = "fArea";
                recheck.maxScatterDifferenceAxis =
                    recheck.maxScatterDifferenceComponent - 3;
            }
            else
            {
                recheck.maxScatterDifferenceForceKind = "fVolume";
                recheck.maxScatterDifferenceAxis =
                    recheck.maxScatterDifferenceComponent - 6;
            }
            recheck.maxScatterDifferenceDirectValue = lhs[index];
            recheck.maxScatterDifferenceRoutedValue = rhs[index];
            recheck.maxScatterDifferenceSignedDelta =
                recheck.maxScatterDifferenceRoutedValue -
                recheck.maxScatterDifferenceDirectValue;
        }
    }
}

double residual_component_scale(const double directValue,
                                const double routedValue)
{
    return std::max(kOpenSubdivRegularResidualScaleFloor,
                    std::max(std::abs(directValue),
                             std::abs(routedValue)));
}

double relative_residual_to_component_scale(const double residual,
                                            const double directValue,
                                            const double routedValue,
                                            double &scale)
{
    scale = residual_component_scale(directValue, routedValue);
    return residual / scale;
}

void populate_residual_tolerance_envelope(
    OpenSubdivRegularProductionParityRecheck &recheck)
{
    recheck.routedResidualCurrentAbsoluteTolerance =
        kOpenSubdivRegularRowTolerance;
    recheck.maxFAreaDifferenceRelativeToComponentScale =
        relative_residual_to_component_scale(
            recheck.maxFAreaDifference,
            recheck.maxFAreaDifferenceDirectValue,
            recheck.maxFAreaDifferenceRoutedValue,
            recheck.maxFAreaDifferenceComponentScale);
    recheck.maxFVolumeDifferenceRelativeToComponentScale =
        relative_residual_to_component_scale(
            recheck.maxFVolumeDifference,
            recheck.maxFVolumeDifferenceDirectValue,
            recheck.maxFVolumeDifferenceRoutedValue,
            recheck.maxFVolumeDifferenceComponentScale);
    recheck.maxScatterDifferenceRelativeToComponentScale =
        relative_residual_to_component_scale(
            recheck.maxScatterDifference,
            recheck.maxScatterDifferenceDirectValue,
            recheck.maxScatterDifferenceRoutedValue,
            recheck.maxScatterDifferenceComponentScale);
    recheck.routedResidualRequiredAbsoluteTolerance =
        std::max(recheck.maxFAreaDifference,
                 std::max(recheck.maxFVolumeDifference,
                          recheck.maxScatterDifference));
    recheck.routedResidualRequiredRelativeTolerance =
        std::max(recheck.maxFAreaDifferenceRelativeToComponentScale,
                 std::max(recheck.maxFVolumeDifferenceRelativeToComponentScale,
                          recheck.maxScatterDifferenceRelativeToComponentScale));
    recheck.routedResidualRequiredToleranceMultiplier =
        recheck.routedResidualRequiredAbsoluteTolerance /
        recheck.routedResidualCurrentAbsoluteTolerance;
    if (recheck.maxFAreaDifference >= recheck.maxFVolumeDifference &&
        recheck.maxFAreaDifference >= recheck.maxScatterDifference)
    {
        recheck.routedResidualRequiredToleranceSource = "fArea";
        recheck.routedResidualRequiredToleranceSourceRelative =
            recheck.maxFAreaDifferenceRelativeToComponentScale;
    }
    else if (recheck.maxFVolumeDifference >= recheck.maxScatterDifference)
    {
        recheck.routedResidualRequiredToleranceSource = "fVolume";
        recheck.routedResidualRequiredToleranceSourceRelative =
            recheck.maxFVolumeDifferenceRelativeToComponentScale;
    }
    else
    {
        recheck.routedResidualRequiredToleranceSource = "scatter";
        recheck.routedResidualRequiredToleranceSourceRelative =
            recheck.maxScatterDifferenceRelativeToComponentScale;
    }
    recheck.routedResidualsExceedCurrentTolerance =
        recheck.maxFAreaDifference > kOpenSubdivRegularRowTolerance ||
        recheck.maxFVolumeDifference > kOpenSubdivRegularRowTolerance ||
        recheck.maxScatterDifference > kOpenSubdivRegularRowTolerance;
}

void populate_residual_readiness_decision(
    OpenSubdivRegularProductionParityRecheck &recheck)
{
    if (!recheck.generatedRoutedRows || recheck.comparedFaceCount == 0)
    {
        recheck.routedResidualReadinessDecision = "unavailable";
        recheck.routedResidualActivationBlocker = "no_routed_rows";
        return;
    }
    if (!recheck.directRowsOverrideMatch)
    {
        recheck.routedResidualReadinessDecision =
            "blocked_by_direct_row_override";
        recheck.routedResidualActivationBlocker = "direct_row_override";
        return;
    }
    if (recheck.routedResidualsExceedCurrentTolerance)
    {
        recheck.routedResidualReadinessDecision =
            "blocked_by_routed_residual_tolerance";
        recheck.routedResidualActivationBlocker =
            recheck.routedResidualRequiredToleranceSource;
        return;
    }
    if (recheck.directVsRoutedMatch)
    {
        recheck.routedResidualReadinessDecision =
            recheck.routeInstalledInProduction
                ? "guarded_route_active"
                : "candidate_needs_serial_openmp_and_reviewer_approval";
        recheck.routedResidualActivationBlocker = "none";
        return;
    }
    recheck.routedResidualReadinessDecision =
        "blocked_by_unclassified_parity_gap";
    recheck.routedResidualActivationBlocker = "unclassified_parity_gap";
}

void populate_residual_activation_policy_decision(
    OpenSubdivRegularProductionParityRecheck &recheck)
{
    recheck.routedResidualCurrentPolicySatisfied = false;
    recheck.routedResidualActivationAllowedByCurrentPolicy = false;

    if (!recheck.generatedRoutedRows || recheck.comparedFaceCount == 0)
    {
        recheck.routedResidualActivationPolicyDecision =
            "unavailable_no_routed_rows";
        return;
    }
    if (!recheck.directRowsOverrideMatch)
    {
        recheck.routedResidualActivationPolicyDecision =
            "blocked_by_direct_row_override";
        return;
    }
    if (recheck.routedResidualsExceedCurrentTolerance)
    {
        recheck.routedResidualActivationPolicyDecision =
            "blocked_pending_residual_tolerance_policy";
        return;
    }

    recheck.routedResidualCurrentPolicySatisfied = true;
    if (recheck.directVsRoutedMatch)
    {
        recheck.routedResidualActivationAllowedByCurrentPolicy = true;
        recheck.routedResidualActivationPolicyDecision =
            recheck.routeInstalledInProduction
                ? "current_policy_satisfied_route_active"
                : "current_policy_satisfied_pending_serial_openmp_and_reviewer_approval";
        return;
    }

    recheck.routedResidualActivationPolicyDecision =
        "blocked_by_unclassified_parity_gap";
}

std::vector<Matrix> shape_functions_for_face(
    const Mesh &mesh,
    const Face &face,
    Far::TopologyRefiner &refiner)
{
    if (face.oneRingVertices.size() != kRegularControlPointCount)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing is limited to 12-control regular faces.");
    }
    if (face.index < 0 || face.index >= static_cast<int>(mesh.faces.size()))
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing requires Face::index to address Mesh::faces.");
    }
    if (mesh.param.shapeFunctions.size() != 3u ||
        mesh.param.gaussQuadratureCoeff.nrow() != 3)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing requires the frozen three-sample regular quadrature plan.");
    }

    std::vector<double> s(mesh.param.shapeFunctions.size(), 0.0);
    std::vector<double> t(mesh.param.shapeFunctions.size(), 0.0);

    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        Matrix vwu = mesh.param.VWU.get_row(sample);
        s[sample] = vwu.get(0, 0);
        t[sample] = vwu.get(0, 1);
    }

    using DoubleFactory = Far::LimitStencilTableFactoryReal<double>;
    DoubleFactory::LocationArray location;
    location.ptexIdx = face.index;
    location.numLocations = static_cast<int>(mesh.param.shapeFunctions.size());
    location.s = s.data();
    location.t = t.data();

    DoubleFactory::LocationArrayVec locations;
    locations.push_back(location);

    DoubleFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;

    const Far::LimitStencilTableReal<double> *rawStencils =
        DoubleFactory::Create(refiner, locations, 0, 0, stencilOptions);
    if (rawStencils == nullptr)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing failed to create limit stencils.");
    }
    std::unique_ptr<const Far::LimitStencilTableReal<double>> stencils(rawStencils);

    std::vector<Matrix> shapeFunctions;
    shapeFunctions.reserve(mesh.param.shapeFunctions.size());
    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        shapeFunctions.push_back(
            shape_function_from_stencil(stencils->GetLimitStencil(sample),
                                        face.oneRingVertices));
    }
    return shapeFunctions;
}

void append_row_diagnostics_for_face(
    const Mesh &mesh,
    const Face &face,
    Far::TopologyRefiner &refiner,
    OpenSubdivRegularRowDiagnostics &diagnostics)
{
    if (face.oneRingVertices.size() != kRegularControlPointCount)
    {
        throw std::runtime_error(
            "OpenSubdiv regular row diagnostics are limited to regular "
            "12-control faces.");
    }
    if (mesh.param.shapeFunctions.size() != 3u ||
        mesh.param.gaussQuadratureCoeff.nrow() != 3)
    {
        throw std::runtime_error(
            "OpenSubdiv regular row diagnostics require the frozen "
            "three-sample regular quadrature plan.");
    }

    std::vector<double> s(mesh.param.shapeFunctions.size(), 0.0);
    std::vector<double> t(mesh.param.shapeFunctions.size(), 0.0);
    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        Matrix vwu = mesh.param.VWU.get_row(sample);
        s[sample] = vwu.get(0, 0);
        t[sample] = vwu.get(0, 1);
    }

    using DoubleFactory = Far::LimitStencilTableFactoryReal<double>;
    DoubleFactory::LocationArray location;
    location.ptexIdx = face.index;
    location.numLocations = static_cast<int>(mesh.param.shapeFunctions.size());
    location.s = s.data();
    location.t = t.data();

    DoubleFactory::LocationArrayVec locations;
    locations.push_back(location);

    DoubleFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;

    const Far::LimitStencilTableReal<double> *rawStencils =
        DoubleFactory::Create(refiner, locations, 0, 0, stencilOptions);
    if (rawStencils == nullptr)
    {
        throw std::runtime_error(
            "OpenSubdiv regular row diagnostics failed to create limit stencils.");
    }
    std::unique_ptr<const Far::LimitStencilTableReal<double>> stencils(rawStencils);

    ++diagnostics.comparedFaceCount;
    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        const Far::LimitStencilReal<double> stencil =
            stencils->GetLimitStencil(sample);
        const Matrix openSubdivRows =
            shape_function_from_stencil(stencil, face.oneRingVertices);
        const double maxDifference =
            max_abs_matrix_difference(openSubdivRows,
                                      mesh.param.shapeFunctions[sample]);

        OpenSubdivRegularRowDiagnosticSample sampleDiagnostic;
        sampleDiagnostic.faceIndex = face.index;
        sampleDiagnostic.sampleIndex = sample;
        sampleDiagnostic.stencilSourcesMatchFaceOneRing =
            stencil_sources_match_face_one_ring(stencil, face.oneRingVertices);
        sampleDiagnostic.maxAbsWeightDifferenceVsSlimedRows = maxDifference;
        diagnostics.samples.push_back(sampleDiagnostic);

        ++diagnostics.comparedSampleCount;
        diagnostics.maxAbsWeightDifferenceVsSlimedRows =
            std::max(diagnostics.maxAbsWeightDifferenceVsSlimedRows,
                     maxDifference);
        diagnostics.regularRowsMatchSlimedRows =
            diagnostics.regularRowsMatchSlimedRows &&
            sampleDiagnostic.stencilSourcesMatchFaceOneRing &&
            maxDifference <= kOpenSubdivRegularRowTolerance;
    }
}
} // namespace

std::vector<std::vector<Matrix>>
build_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh)
{
    if (!opensubdiv_regular_production_routing_requested())
    {
        return {};
    }
    if (!kOpenSubdivRegularProductionRouteEnabled)
    {
        static bool warned = false;
        if (!warned)
        {
            std::cerr
                << "OpenSubdiv regular production routing was requested, "
                   "but the parity candidate remains reviewer-gated and is "
                   "not installed in production. Falling back to the direct "
                   "regular path.\n";
            warned = true;
        }
        return {};
    }

    auto refiner = create_refiner_for_mesh(mesh);
    if (!refiner)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing failed to create topology refiner.");
    }

    Far::TopologyRefiner::AdaptiveOptions adaptiveOptions(3);
    refiner->RefineAdaptive(adaptiveOptions);

    std::vector<std::vector<Matrix>> routedShapeFunctions(mesh.faces.size());
    bool skippedUnsupportedFace = false;
    for (const Face &face : mesh.faces)
    {
        if (face.isBoundary || face.isGhost)
        {
            continue;
        }
        if (face.oneRingVertices.size() != kRegularControlPointCount)
        {
            skippedUnsupportedFace = true;
            continue;
        }
        std::vector<Matrix> shapeFunctions =
            shape_functions_for_face(mesh, face, *refiner);
        if (!shape_functions_match_frozen_regular_rows(
                shapeFunctions, mesh.param.shapeFunctions))
        {
            skippedUnsupportedFace = true;
            continue;
        }
        routedShapeFunctions[face.index] = std::move(shapeFunctions);
    }
    if (skippedUnsupportedFace)
    {
        static bool warned = false;
        if (!warned)
        {
            std::cerr
                << "OpenSubdiv regular routing skipped unsupported or "
                   "non-equivalent faces; their existing direct/subdivision "
                   "paths remain active.\n";
            warned = true;
        }
    }
    return routedShapeFunctions;
}

std::shared_ptr<const RegularLimitSurfaceRowTable>
cached_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh)
{
    if (!opensubdiv_regular_production_routing_requested())
    {
        return {};
    }

    const std::uint64_t requestedFingerprint =
        regular_limit_surface_cache_fingerprint(mesh);
    RegularLimitSurfaceRowCache &cache = mesh.regularLimitSurfaceRowCache_;
    std::lock_guard<std::mutex> lock(cache.mutex_);
    if (cache.table_ && cache.fingerprint_ == requestedFingerprint)
    {
        ++cache.hitCount_;
        return cache.table_;
    }

    ++cache.missCount_;
    cache.table_ = std::make_shared<const RegularLimitSurfaceRowTable>(
        build_opensubdiv_regular_shape_functions_by_face(mesh));
    cache.fingerprint_ = requestedFingerprint;
    ++cache.buildCount_;
    return cache.table_;
}

OpenSubdivRegularRowDiagnostics
diagnose_opensubdiv_regular_row_semantics(const Mesh &mesh)
{
    OpenSubdivRegularRowDiagnostics diagnostics;
    diagnostics.opensubdivCompiled = true;
    diagnostics.productionRouteEnabled = kOpenSubdivRegularProductionRouteEnabled;
    diagnostics.regularRowsMatchSlimedRows = true;

    if (mesh.vertices.empty() || mesh.faces.empty())
    {
        diagnostics.regularRowsMatchSlimedRows = false;
        return diagnostics;
    }

    auto refiner = create_refiner_for_mesh(mesh);
    if (!refiner)
    {
        throw std::runtime_error(
            "OpenSubdiv regular row diagnostics failed to create topology refiner.");
    }

    Far::TopologyRefiner::AdaptiveOptions adaptiveOptions(3);
    refiner->RefineAdaptive(adaptiveOptions);

    for (const Face &face : mesh.faces)
    {
        if (face.isBoundary || face.isGhost)
        {
            continue;
        }
        append_row_diagnostics_for_face(mesh, face, *refiner, diagnostics);
    }
    diagnostics.regularRowsMatchSlimedRows =
        diagnostics.regularRowsMatchSlimedRows &&
        diagnostics.comparedSampleCount > 0;
    return diagnostics;
}

OpenSubdivRegularProductionParityRecheck
diagnose_opensubdiv_regular_production_call_parity(Mesh &mesh)
{
    OpenSubdivRegularProductionParityRecheck recheck;
    recheck.opensubdivCompiled = true;
    recheck.runtimeOptInRequested =
        opensubdiv_regular_production_routing_requested();
    recheck.productionRouteEnabled = kOpenSubdivRegularProductionRouteEnabled;
    recheck.routeInstalledInProduction =
        kOpenSubdivRegularProductionRouteEnabled &&
        recheck.runtimeOptInRequested;

    if (!recheck.runtimeOptInRequested || mesh.vertices.empty() ||
        mesh.faces.empty())
    {
        return recheck;
    }

    auto refiner = create_refiner_for_mesh(mesh);
    if (!refiner)
    {
        throw std::runtime_error(
            "OpenSubdiv regular production parity recheck failed to create topology refiner.");
    }
    Far::TopologyRefiner::AdaptiveOptions adaptiveOptions(3);
    refiner->RefineAdaptive(adaptiveOptions);

    const std::vector<Matrix> originalShapeFunctions = mesh.param.shapeFunctions;
    const int scatterSize = static_cast<int>(mesh.vertices.size()) * 9;
    std::vector<double> directScatter(scatterSize, 0.0);
    std::vector<double> directRowsOverrideScatter(scatterSize, 0.0);
    std::vector<double> routedScatter(scatterSize, 0.0);

    bool allMatched = true;
    for (Face &face : mesh.faces)
    {
        if (face.isGhost || face.isBoundary)
        {
            continue;
        }
        if (face.oneRingVertices.size() != kRegularControlPointCount)
        {
            throw std::runtime_error(
                "OpenSubdiv regular production parity recheck is limited to "
                "12-control regular faces.");
        }

        const std::vector<Matrix> routedShapeFunctions =
            shape_functions_for_face(mesh, face, *refiner);
        recheck.generatedRoutedRows = true;
        ++recheck.comparedFaceCount;
        recheck.comparedSampleCount +=
            static_cast<int>(routedShapeFunctions.size());
        for (int sample = 0; sample < static_cast<int>(routedShapeFunctions.size());
             ++sample)
        {
            update_max_row_weight_difference_with_location(
                recheck,
                face.index,
                sample,
                face.oneRingVertices,
                originalShapeFunctions[sample],
                routedShapeFunctions[sample]);
        }

        const Matrix oneRingVertexMatrix = mesh.get_one_ring_vertex_matrix(face);
        double directArea = 0.0;
        double directVolume = 0.0;
        double directRowsOverrideArea = 0.0;
        double directRowsOverrideVolume = 0.0;
        double routedArea = 0.0;
        double routedVolume = 0.0;
        mesh.enumerate_regular_patch_area_volume_with_limit_surface_evaluator(
            oneRingVertexMatrix,
            directArea,
            directVolume,
            nullptr);
        mesh.enumerate_regular_patch_area_volume_with_limit_surface_evaluator(
            oneRingVertexMatrix,
            directRowsOverrideArea,
            directRowsOverrideVolume,
            &originalShapeFunctions);
        mesh.enumerate_regular_patch_area_volume_with_limit_surface_evaluator(
            oneRingVertexMatrix,
            routedArea,
            routedVolume,
            &routedShapeFunctions);

        recheck.maxAreaDifference =
            std::max(recheck.maxAreaDifference,
                     std::abs(directArea - routedArea));
        recheck.maxLegacyVolumeDifference =
            std::max(recheck.maxLegacyVolumeDifference,
                     std::abs(directVolume - routedVolume));
        recheck.maxDirectRowsOverrideAreaDifference =
            std::max(recheck.maxDirectRowsOverrideAreaDifference,
                     std::abs(directArea - directRowsOverrideArea));
        recheck.maxDirectRowsOverrideLegacyVolumeDifference =
            std::max(recheck.maxDirectRowsOverrideLegacyVolumeDifference,
                     std::abs(directVolume - directRowsOverrideVolume));

        const std::vector<Matrix> coordinateColumns =
            control_point_rows_to_columns_for_face(mesh, face);

        double directMeanCurv = 0.0;
        double directEBend = 0.0;
        Matrix directNorm = mat_calloc(3, 1);
        Matrix directFBend = mat_calloc(kRegularControlPointCount, 3);
        Matrix directFArea = mat_calloc(kRegularControlPointCount, 3);
        Matrix directFVolume = mat_calloc(kRegularControlPointCount, 3);

        mesh.param.shapeFunctions = originalShapeFunctions;
        mesh.element_energy_force_regular(coordinateColumns,
                                          face,
                                          face.spontCurvature,
                                          directMeanCurv,
                                          directNorm,
                                          directEBend,
                                          directFBend,
                                          directFArea,
                                          directFVolume,
                                          true);

        double directRowsOverrideMeanCurv = 0.0;
        double directRowsOverrideEBend = 0.0;
        Matrix directRowsOverrideNorm = mat_calloc(3, 1);
        Matrix directRowsOverrideFBend = mat_calloc(kRegularControlPointCount, 3);
        Matrix directRowsOverrideFArea = mat_calloc(kRegularControlPointCount, 3);
        Matrix directRowsOverrideFVolume = mat_calloc(kRegularControlPointCount, 3);

        mesh.param.shapeFunctions = originalShapeFunctions;
        mesh.element_energy_force_regular(coordinateColumns,
                                          face,
                                          face.spontCurvature,
                                          directRowsOverrideMeanCurv,
                                          directRowsOverrideNorm,
                                          directRowsOverrideEBend,
                                          directRowsOverrideFBend,
                                          directRowsOverrideFArea,
                                          directRowsOverrideFVolume,
                                          true,
                                          &originalShapeFunctions);

        double routedMeanCurv = 0.0;
        double routedEBend = 0.0;
        Matrix routedNorm = mat_calloc(3, 1);
        Matrix routedFBend = mat_calloc(kRegularControlPointCount, 3);
        Matrix routedFArea = mat_calloc(kRegularControlPointCount, 3);
        Matrix routedFVolume = mat_calloc(kRegularControlPointCount, 3);

        mesh.param.shapeFunctions = routedShapeFunctions;
        mesh.element_energy_force_regular(coordinateColumns,
                                          face,
                                          face.spontCurvature,
                                          routedMeanCurv,
                                          routedNorm,
                                          routedEBend,
                                          routedFBend,
                                          routedFArea,
                                          routedFVolume,
                                          true);
        mesh.param.shapeFunctions = originalShapeFunctions;

        recheck.maxMeanCurvatureDifference =
            std::max(recheck.maxMeanCurvatureDifference,
                     std::abs(directMeanCurv - routedMeanCurv));
        recheck.maxBendingEnergyDifference =
            std::max(recheck.maxBendingEnergyDifference,
                     std::abs(directEBend - routedEBend));
        update_max_abs_matrix_difference(recheck.maxNormalDifference,
                                         directNorm,
                                         routedNorm);
        update_max_abs_matrix_difference(recheck.maxFBendDifference,
                                         directFBend,
                                         routedFBend);
        recheck.maxDirectRowsOverrideMeanCurvatureDifference =
            std::max(recheck.maxDirectRowsOverrideMeanCurvatureDifference,
                     std::abs(directMeanCurv - directRowsOverrideMeanCurv));
        recheck.maxDirectRowsOverrideBendingEnergyDifference =
            std::max(recheck.maxDirectRowsOverrideBendingEnergyDifference,
                     std::abs(directEBend - directRowsOverrideEBend));
        update_max_abs_matrix_difference(
            recheck.maxDirectRowsOverrideNormalDifference,
            directNorm,
            directRowsOverrideNorm);
        update_max_abs_matrix_difference(
            recheck.maxDirectRowsOverrideFBendDifference,
            directFBend,
            directRowsOverrideFBend);
        update_max_abs_matrix_difference(
            recheck.maxDirectRowsOverrideFAreaDifference,
            directFArea,
            directRowsOverrideFArea);
        update_max_abs_matrix_difference(
            recheck.maxDirectRowsOverrideFVolumeDifference,
            directFVolume,
            directRowsOverrideFVolume);
        update_max_abs_matrix_difference_with_location(
            recheck.maxFAreaDifference,
            recheck.maxFAreaDifferenceFaceIndex,
            recheck.maxFAreaDifferenceLocalRow,
            recheck.maxFAreaDifferenceSourceId,
            recheck.maxFAreaDifferenceAxis,
            recheck.maxFAreaDifferenceDirectValue,
            recheck.maxFAreaDifferenceRoutedValue,
            recheck.maxFAreaDifferenceSignedDelta,
            face.index,
            face.oneRingVertices,
            directFArea,
            routedFArea);
        update_max_abs_matrix_difference_with_location(
            recheck.maxFVolumeDifference,
            recheck.maxFVolumeDifferenceFaceIndex,
            recheck.maxFVolumeDifferenceLocalRow,
            recheck.maxFVolumeDifferenceSourceId,
            recheck.maxFVolumeDifferenceAxis,
            recheck.maxFVolumeDifferenceDirectValue,
            recheck.maxFVolumeDifferenceRoutedValue,
            recheck.maxFVolumeDifferenceSignedDelta,
            face.index,
            face.oneRingVertices,
            directFVolume,
            routedFVolume);

        accumulate_scatter_rows(directScatter,
                                face,
                                directFBend,
                                directFArea,
                                directFVolume);
        accumulate_scatter_rows(directRowsOverrideScatter,
                                face,
                                directRowsOverrideFBend,
                                directRowsOverrideFArea,
                                directRowsOverrideFVolume);
        accumulate_scatter_rows(routedScatter,
                                face,
                                routedFBend,
                                routedFArea,
                                routedFVolume);
    }

    mesh.param.shapeFunctions = originalShapeFunctions;
    update_max_abs_vector_difference(
        recheck.maxDirectRowsOverrideScatterDifference,
        directScatter,
        directRowsOverrideScatter);
    update_max_abs_scatter_difference_with_location(recheck,
                                                    directScatter,
                                                    routedScatter);
    recheck.directRowsOverrideMatch =
        recheck.generatedRoutedRows && recheck.comparedFaceCount > 0 &&
        recheck.maxDirectRowsOverrideAreaDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideLegacyVolumeDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideMeanCurvatureDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideBendingEnergyDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideNormalDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideFBendDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideFAreaDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideFVolumeDifference <= kOpenSubdivRegularRowTolerance &&
        recheck.maxDirectRowsOverrideScatterDifference <= kOpenSubdivRegularRowTolerance;
    if (recheck.maxRoutedRowWeightDifferenceVsSlimedRows > 0.0)
    {
        recheck.maxFAreaDifferencePerRowWeightDifference =
            recheck.maxFAreaDifference /
            recheck.maxRoutedRowWeightDifferenceVsSlimedRows;
        recheck.maxFVolumeDifferencePerRowWeightDifference =
            recheck.maxFVolumeDifference /
            recheck.maxRoutedRowWeightDifferenceVsSlimedRows;
        recheck.maxScatterDifferencePerRowWeightDifference =
            recheck.maxScatterDifference /
            recheck.maxRoutedRowWeightDifferenceVsSlimedRows;
    }
    populate_residual_tolerance_envelope(recheck);
    allMatched = allMatched && recheck.generatedRoutedRows &&
                 recheck.comparedFaceCount > 0 &&
                 recheck.maxAreaDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxLegacyVolumeDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxMeanCurvatureDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxBendingEnergyDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxNormalDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxFBendDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxFAreaDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxFVolumeDifference <= kOpenSubdivRegularRowTolerance &&
                 recheck.maxScatterDifference <= kOpenSubdivRegularRowTolerance;
    recheck.directVsRoutedMatch = allMatched;
    recheck.routedResidualToleranceReviewRequired =
        recheck.directRowsOverrideMatch && !recheck.directVsRoutedMatch &&
        recheck.routedResidualsExceedCurrentTolerance;
    populate_residual_readiness_decision(recheck);
    populate_residual_activation_policy_decision(recheck);
    return recheck;
}

#else

std::vector<std::vector<Matrix>>
build_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh)
{
    (void)mesh;
    if (opensubdiv_regular_production_routing_requested())
    {
        throw std::runtime_error(
            "SLIMED_USE_OPENSUBDIV_REGULAR was set, but this binary was not "
            "built with USE_OPENSUBDIV_REGULAR=1 and an explicit "
            "OPENSUBDIV_ROOT. Default builds remain OpenSubdiv-free.");
    }
    return {};
}

std::shared_ptr<const RegularLimitSurfaceRowTable>
cached_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh)
{
    if (!opensubdiv_regular_production_routing_requested())
    {
        return {};
    }
    (void)build_opensubdiv_regular_shape_functions_by_face(mesh);
    return {};
}

OpenSubdivRegularRowDiagnostics
diagnose_opensubdiv_regular_row_semantics(const Mesh &mesh)
{
    (void)mesh;
    OpenSubdivRegularRowDiagnostics diagnostics;
    diagnostics.opensubdivCompiled = false;
    diagnostics.productionRouteEnabled = false;
    diagnostics.regularRowsMatchSlimedRows = false;
    return diagnostics;
}

OpenSubdivRegularProductionParityRecheck
diagnose_opensubdiv_regular_production_call_parity(Mesh &mesh)
{
    (void)mesh;
    OpenSubdivRegularProductionParityRecheck recheck;
    recheck.opensubdivCompiled = false;
    recheck.runtimeOptInRequested =
        opensubdiv_regular_production_routing_requested();
    recheck.productionRouteEnabled = false;
    recheck.routeInstalledInProduction = false;
    if (recheck.runtimeOptInRequested)
    {
        throw std::runtime_error(
            "SLIMED_USE_OPENSUBDIV_REGULAR was set, but production parity "
            "recheck requires a binary built with USE_OPENSUBDIV_REGULAR=1 "
            "and an explicit OPENSUBDIV_ROOT.");
    }
    return recheck;
}

#endif

RegularLimitSurfaceRowCacheStats
regular_limit_surface_row_cache_stats(const Mesh &mesh)
{
    const RegularLimitSurfaceRowCache &cache =
        mesh.regularLimitSurfaceRowCache_;
    std::lock_guard<std::mutex> lock(cache.mutex_);
    RegularLimitSurfaceRowCacheStats stats;
    stats.fingerprint = cache.fingerprint_;
    stats.buildCount = cache.buildCount_;
    stats.hitCount = cache.hitCount_;
    stats.missCount = cache.missCount_;
    stats.populated = static_cast<bool>(cache.table_);
    return stats;
}
