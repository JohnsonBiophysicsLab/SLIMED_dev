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

/**
 * @brief Return per-face regular shape-function rows for the explicit
 * OpenSubdiv route.
 *
 * The returned outer vector is indexed like Mesh::faces. Entries are populated
 * only for supported non-boundary, non-ghost 12-control faces. Unsupported
 * selected faces fail loudly instead of falling back silently.
 */
std::vector<std::vector<Matrix>>
build_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh);

