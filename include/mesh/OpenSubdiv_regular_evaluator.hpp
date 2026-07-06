/**
 * @file OpenSubdiv_regular_evaluator.hpp
 * @brief Private opt-in OpenSubdiv regular-patch routing helpers.
 */

#pragma once

#include <vector>

#include "linalg/Linear_algebra.hpp"

class Mesh;
class Face;

bool opensubdiv_regular_production_routing_requested();

struct OpenSubdivRegularRowDiagnosticSample
{
    int faceIndex = -1;
    int sampleIndex = -1;
    bool stencilSourcesMatchFaceOneRing = false;
    double maxAbsWeightDifferenceVsSlimedRows = 0.0;
};

struct OpenSubdivRegularRowDiagnostics
{
    bool opensubdivCompiled = false;
    bool productionRouteEnabled = false;
    bool regularRowsMatchSlimedRows = false;
    int comparedFaceCount = 0;
    int comparedSampleCount = 0;
    double maxAbsWeightDifferenceVsSlimedRows = 0.0;
    std::vector<OpenSubdivRegularRowDiagnosticSample> samples;
};

struct OpenSubdivRegularProductionParityRecheck
{
    bool opensubdivCompiled = false;
    bool runtimeOptInRequested = false;
    bool productionRouteEnabled = false;
    bool routeInstalledInProduction = false;
    bool generatedRoutedRows = false;
    bool directVsRoutedMatch = false;
    int comparedFaceCount = 0;
    int comparedSampleCount = 0;
    double maxRoutedRowWeightDifferenceVsSlimedRows = 0.0;
    int maxRoutedRowWeightDifferenceFaceIndex = -1;
    int maxRoutedRowWeightDifferenceSampleIndex = -1;
    int maxRoutedRowWeightDifferenceRow = -1;
    int maxRoutedRowWeightDifferenceSourceColumn = -1;
    double maxRoutedRowWeightDifferenceDirectValue = 0.0;
    double maxRoutedRowWeightDifferenceRoutedValue = 0.0;
    double maxRoutedRowWeightDifferenceSignedDelta = 0.0;
    double maxAreaDifference = 0.0;
    double maxLegacyVolumeDifference = 0.0;
    double maxMeanCurvatureDifference = 0.0;
    double maxBendingEnergyDifference = 0.0;
    double maxNormalDifference = 0.0;
    double maxFBendDifference = 0.0;
    double maxFAreaDifference = 0.0;
    int maxFAreaDifferenceFaceIndex = -1;
    int maxFAreaDifferenceLocalRow = -1;
    int maxFAreaDifferenceAxis = -1;
    double maxFAreaDifferenceDirectValue = 0.0;
    double maxFAreaDifferenceRoutedValue = 0.0;
    double maxFAreaDifferenceSignedDelta = 0.0;
    double maxFVolumeDifference = 0.0;
    int maxFVolumeDifferenceFaceIndex = -1;
    int maxFVolumeDifferenceLocalRow = -1;
    int maxFVolumeDifferenceAxis = -1;
    double maxFVolumeDifferenceDirectValue = 0.0;
    double maxFVolumeDifferenceRoutedValue = 0.0;
    double maxFVolumeDifferenceSignedDelta = 0.0;
    double maxScatterDifference = 0.0;
    int maxScatterDifferenceVertexIndex = -1;
    int maxScatterDifferenceComponent = -1;
    double maxScatterDifferenceDirectValue = 0.0;
    double maxScatterDifferenceRoutedValue = 0.0;
    double maxScatterDifferenceSignedDelta = 0.0;
};

/**
 * @brief Return per-face regular shape-function rows for the explicit
 * OpenSubdiv route.
 *
 * The returned outer vector is indexed like Mesh::faces when the backend is
 * production-enabled. Empty results mean callers must use the direct regular
 * path.
 */
std::vector<std::vector<Matrix>>
build_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh);

/**
 * @brief Compare opt-in OpenSubdiv regular rows against SLIMED's current
 * regular shape-function rows without installing them in production.
 */
OpenSubdivRegularRowDiagnostics
diagnose_opensubdiv_regular_row_semantics(const Mesh &mesh);

/**
 * @brief Recheck the disabled regular OpenSubdiv route against the current
 * production regular call shape without installing the route.
 *
 * The diagnostic requires the runtime opt-in in OpenSubdiv-enabled builds and
 * reports whether per-face would-be-routed rows preserve area, legacy volume,
 * local force rows, scatter order, normal, mean curvature, and bending energy.
 */
OpenSubdivRegularProductionParityRecheck
diagnose_opensubdiv_regular_production_call_parity(Mesh &mesh);
