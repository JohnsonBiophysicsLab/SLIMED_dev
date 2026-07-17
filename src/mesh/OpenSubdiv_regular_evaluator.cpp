#include "mesh/OpenSubdiv_regular_evaluator.hpp"

#include "mesh/Face.hpp"
#include "mesh/Mesh.hpp"

#include <cstdlib>
#include <array>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>

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

#include <memory>

using namespace OpenSubdiv;

namespace
{
constexpr int kRegularControlPointCount = 12;
constexpr int kDerivativeRowCount = 7;
constexpr bool kOpenSubdivRegularProductionRouteEnabled = false;
constexpr double kOpenSubdivRegularRowTolerance = 5.0e-6;
constexpr double kOpenSubdivRegularResidualScaleFloor = 1.0e-12;

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

double stencil_weight_for_source(const Far::LimitStencil &stencil,
                                 const float *weights,
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

Matrix shape_function_from_stencil(const Far::LimitStencil &stencil,
                                   const std::vector<int> &sourceIds)
{
    const std::array<const float *, kDerivativeRowCount> rowWeights = {
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

std::set<int> stencil_source_set(const Far::LimitStencil &stencil)
{
    std::set<int> sources;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int index = 0; index < stencil.GetSize(); ++index)
    {
        sources.insert(indices[index]);
    }
    return sources;
}

bool stencil_sources_match_face_one_ring(const Far::LimitStencil &stencil,
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
    recheck.routedResidualsExceedCurrentTolerance =
        recheck.maxFAreaDifference > kOpenSubdivRegularRowTolerance ||
        recheck.maxFVolumeDifference > kOpenSubdivRegularRowTolerance ||
        recheck.maxScatterDifference > kOpenSubdivRegularRowTolerance;
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

    std::vector<float> s(mesh.param.shapeFunctions.size(), 0.0f);
    std::vector<float> t(mesh.param.shapeFunctions.size(), 0.0f);

    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        Matrix vwu = mesh.param.VWU.get_row(sample);
        s[sample] = static_cast<float>(vwu.get(0, 0));
        t[sample] = static_cast<float>(vwu.get(0, 1));
    }

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = face.index;
    location.numLocations = static_cast<int>(mesh.param.shapeFunctions.size());
    location.s = s.data();
    location.t = t.data();

    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;

    const Far::LimitStencilTable *rawStencils =
        Far::LimitStencilTableFactory::Create(refiner,
                                              locations,
                                              0,
                                              0,
                                              stencilOptions);
    if (rawStencils == nullptr)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing failed to create limit stencils.");
    }
    std::unique_ptr<const Far::LimitStencilTable> stencils(rawStencils);

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

    std::vector<float> s(mesh.param.shapeFunctions.size(), 0.0f);
    std::vector<float> t(mesh.param.shapeFunctions.size(), 0.0f);
    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        Matrix vwu = mesh.param.VWU.get_row(sample);
        s[sample] = static_cast<float>(vwu.get(0, 0));
        t[sample] = static_cast<float>(vwu.get(0, 1));
    }

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = face.index;
    location.numLocations = static_cast<int>(mesh.param.shapeFunctions.size());
    location.s = s.data();
    location.t = t.data();

    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;

    const Far::LimitStencilTable *rawStencils =
        Far::LimitStencilTableFactory::Create(refiner,
                                              locations,
                                              0,
                                              0,
                                              stencilOptions);
    if (rawStencils == nullptr)
    {
        throw std::runtime_error(
            "OpenSubdiv regular row diagnostics failed to create limit stencils.");
    }
    std::unique_ptr<const Far::LimitStencilTable> stencils(rawStencils);

    ++diagnostics.comparedFaceCount;
    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        const Far::LimitStencil stencil = stencils->GetLimitStencil(sample);
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
                   "but the route is disabled because the OpenSubdiv-derived "
                   "rows do not yet preserve reviewed direct force/geometry "
                   "semantics. Falling back to the direct regular path.\n";
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
    for (const Face &face : mesh.faces)
    {
        if (face.isBoundary || face.isGhost)
        {
            continue;
        }
        if (face.oneRingVertices.size() != kRegularControlPointCount)
        {
            throw std::runtime_error(
                "OpenSubdiv regular routing was requested, but a non-regular "
                "face was encountered. This route is limited to regular "
                "12-control faces.");
        }
        routedShapeFunctions[face.index] =
            shape_functions_for_face(mesh, face, *refiner);
    }
    return routedShapeFunctions;
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
    recheck.routeInstalledInProduction = false;

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
