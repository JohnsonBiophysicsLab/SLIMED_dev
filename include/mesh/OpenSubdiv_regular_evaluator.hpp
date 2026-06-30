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
