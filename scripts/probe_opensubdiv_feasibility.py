#!/usr/bin/env python3
"""Opt-in OpenSubdiv Far feasibility probe for SLIMED.

This script is intentionally inert for default builds. It only compiles a
temporary OpenSubdiv prototype when an OpenSubdiv install is discoverable or
when OPENSUBDIV_ROOT is supplied by the caller.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap


PROBE_SOURCE = r"""
#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/patchMap.h>
#include <opensubdiv/far/patchTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <string>
#include <vector>

using namespace OpenSubdiv;

#ifndef SLIMED_BACKPROJECTION_REPORT
#define SLIMED_BACKPROJECTION_REPORT 0
#endif

#ifndef SLIMED_AGGREGATE_SOURCE_COVERAGE_REPORT
#define SLIMED_AGGREGATE_SOURCE_COVERAGE_REPORT 0
#endif

#ifndef SLIMED_REGULAR_EQUIVALENCE_REPORT
#define SLIMED_REGULAR_EQUIVALENCE_REPORT 0
#endif

#ifndef SLIMED_FORCE_TRANSPOSE_REPORT
#define SLIMED_FORCE_TRANSPOSE_REPORT 0
#endif

#ifndef SLIMED_REGULAR_ACTUAL_FORCE_REPORT
#define SLIMED_REGULAR_ACTUAL_FORCE_REPORT 0
#endif

#ifndef SLIMED_REGULAR_ADAPTER_PROOF_REPORT
#define SLIMED_REGULAR_ADAPTER_PROOF_REPORT 0
#endif

#ifndef SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT
#define SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT 0
#endif

#ifndef SLIMED_BROADER_VALENCE_COVERAGE_REPORT
#define SLIMED_BROADER_VALENCE_COVERAGE_REPORT 0
#endif

#ifndef SLIMED_VALENCE4_MAPPING_PROOF_REPORT
#define SLIMED_VALENCE4_MAPPING_PROOF_REPORT 0
#endif

struct Point {
    float x;
    float y;
    float z;
};

struct MeshCase {
    std::string name;
    int numVertices = 0;
    std::vector<int> vertsPerFace;
    std::vector<int> vertIndices;
    std::vector<Point> points;
    std::vector<int> expectedLocalControlIds;
    int sampleFace = 0;
    int extraordinaryValence = 0;
};

static void append_face(MeshCase &mesh, int a, int b, int c) {
    mesh.vertsPerFace.push_back(3);
    mesh.vertIndices.push_back(a);
    mesh.vertIndices.push_back(b);
    mesh.vertIndices.push_back(c);
}

static MeshCase make_regular_lattice_case() {
    MeshCase mesh;
    mesh.name = "regular_triangular_lattice";
    const int n = 6;
    mesh.numVertices = (n + 1) * (n + 1);
    mesh.points.reserve(mesh.numVertices);
    for (int j = 0; j <= n; ++j) {
        for (int i = 0; i <= n; ++i) {
            mesh.points.push_back(Point{
                static_cast<float>(i + 0.5 * j),
                static_cast<float>(0.8660254037844386 * j),
                static_cast<float>(0.03 * std::sin(0.7 * (i + j)))});
        }
    }

    auto id = [n](int i, int j) { return j * (n + 1) + i; };
    for (int j = 0; j < n; ++j) {
        for (int i = 0; i < n; ++i) {
            if (i == 2 && j == 2) {
                mesh.sampleFace = static_cast<int>(mesh.vertsPerFace.size());
            }
            append_face(mesh, id(i, j), id(i + 1, j), id(i, j + 1));
            append_face(mesh, id(i + 1, j), id(i + 1, j + 1), id(i, j + 1));
        }
    }
    return mesh;
}

static MeshCase make_irregular_fixture_case() {
    MeshCase mesh;
    mesh.name = "synthetic_11_control_fixture_topology";
    mesh.numVertices = 11;
    mesh.points = {
        {-0.70f, -0.86f, 0.01f},
        {-0.18f, -0.92f, -0.02f},
        {0.00f, 0.00f, 0.04f},
        {0.58f, -0.78f, 0.03f},
        {-0.78f, -0.05f, -0.03f},
        {-0.12f, 0.56f, 0.02f},
        {0.64f, 0.08f, -0.01f},
        {1.16f, -0.58f, 0.05f},
        {-0.30f, 1.12f, -0.04f},
        {0.54f, 1.06f, 0.03f},
        {1.20f, 0.46f, 0.00f},
    };

    mesh.sampleFace = 0;
    mesh.expectedLocalControlIds = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    append_face(mesh, 2, 5, 6);
    append_face(mesh, 1, 2, 5);
    append_face(mesh, 9, 5, 6);
    append_face(mesh, 3, 6, 2);
    append_face(mesh, 0, 1, 2);
    append_face(mesh, 0, 2, 3);
    append_face(mesh, 4, 5, 1);
    append_face(mesh, 4, 9, 5);
    append_face(mesh, 7, 3, 6);
    append_face(mesh, 7, 6, 9);
    append_face(mesh, 4, 8, 9);
    append_face(mesh, 3, 7, 10);
    return mesh;
}

static void orient_triangles_consistently(MeshCase &mesh) {
    std::vector<std::array<int, 3>> faces;
    faces.reserve(mesh.vertsPerFace.size());
    for (int face = 0; face < static_cast<int>(mesh.vertsPerFace.size());
         ++face) {
        faces.push_back({mesh.vertIndices[3 * face],
                         mesh.vertIndices[3 * face + 1],
                         mesh.vertIndices[3 * face + 2]});
    }

    std::map<std::pair<int, int>, std::vector<int>> edgeFaces;
    for (int face = 0; face < static_cast<int>(faces.size()); ++face) {
        for (int edge = 0; edge < 3; ++edge) {
            int a = faces[face][edge];
            int b = faces[face][(edge + 1) % 3];
            edgeFaces[{std::min(a, b), std::max(a, b)}].push_back(face);
        }
    }

    std::vector<bool> visited(faces.size(), false);
    std::queue<int> pending;
    visited[0] = true;
    pending.push(0);

    while (!pending.empty()) {
        int face = pending.front();
        pending.pop();

        for (int edge = 0; edge < 3; ++edge) {
            int a = faces[face][edge];
            int b = faces[face][(edge + 1) % 3];
            std::vector<int> const &neighbors =
                edgeFaces[{std::min(a, b), std::max(a, b)}];
            for (int neighbor : neighbors) {
                if (neighbor == face || visited[neighbor]) {
                    continue;
                }

                for (int neighborEdge = 0; neighborEdge < 3; ++neighborEdge) {
                    int na = faces[neighbor][neighborEdge];
                    int nb = faces[neighbor][(neighborEdge + 1) % 3];
                    if (na == a && nb == b) {
                        std::swap(faces[neighbor][1], faces[neighbor][2]);
                        break;
                    }
                }
                visited[neighbor] = true;
                pending.push(neighbor);
            }
        }
    }

    mesh.vertIndices.clear();
    mesh.vertIndices.reserve(faces.size() * 3);
    for (std::array<int, 3> const &face : faces) {
        mesh.vertIndices.push_back(face[0]);
        mesh.vertIndices.push_back(face[1]);
        mesh.vertIndices.push_back(face[2]);
    }
}

static MeshCase make_oriented_irregular_fixture_case() {
    MeshCase mesh = make_irregular_fixture_case();
    mesh.name = "synthetic_11_control_fixture_oriented_topology";
    orient_triangles_consistently(mesh);
    return mesh;
}

static MeshCase make_padded_irregular_fixture_case() {
    MeshCase mesh = make_oriented_irregular_fixture_case();
    mesh.name = "synthetic_11_control_fixture_oriented_outer_annulus";

    float centroid[3] = {0.0f, 0.0f, 0.0f};
    for (int id : mesh.expectedLocalControlIds) {
        centroid[0] += mesh.points[id].x;
        centroid[1] += mesh.points[id].y;
        centroid[2] += mesh.points[id].z;
    }
    for (float &axis : centroid) {
        axis /= static_cast<float>(mesh.expectedLocalControlIds.size());
    }

    std::vector<int> boundaryLoop = {0, 1, 4, 8, 9, 7, 10, 3};
    std::vector<int> outerIds;
    outerIds.reserve(boundaryLoop.size());
    for (int id : boundaryLoop) {
        Point const &point = mesh.points[id];
        outerIds.push_back(static_cast<int>(mesh.points.size()));
        mesh.points.push_back(Point{
            centroid[0] + 1.45f * (point.x - centroid[0]),
            centroid[1] + 1.45f * (point.y - centroid[1]),
            centroid[2] + 0.50f * (point.z - centroid[2])});
    }

    mesh.numVertices = static_cast<int>(mesh.points.size());
    for (int i = 0; i < static_cast<int>(boundaryLoop.size()); ++i) {
        int next = (i + 1) % static_cast<int>(boundaryLoop.size());
        int a = boundaryLoop[i];
        int b = boundaryLoop[next];
        int outerA = outerIds[i];
        int outerB = outerIds[next];
        append_face(mesh, a, b, outerB);
        append_face(mesh, a, outerB, outerA);
    }

    return mesh;
}

static MeshCase make_extraordinary_valence_fan_case(int valence) {
    MeshCase mesh;
    mesh.name = "synthetic_extraordinary_valence_" + std::to_string(valence) +
                "_fan";
    mesh.sampleFace = 0;
    mesh.extraordinaryValence = valence;

    mesh.points.push_back(Point{0.0f, 0.0f, 0.06f});
    const float pi = 3.14159265358979323846f;
    for (int i = 0; i < valence; ++i) {
        float angle = 2.0f * pi * static_cast<float>(i) /
                      static_cast<float>(valence);
        mesh.points.push_back(Point{
            std::cos(angle),
            std::sin(angle),
            0.04f * std::sin(1.7f * angle)});
    }
    for (int i = 0; i < valence; ++i) {
        float angle = 2.0f * pi * (static_cast<float>(i) + 0.35f) /
                      static_cast<float>(valence);
        mesh.points.push_back(Point{
            1.85f * std::cos(angle),
            1.85f * std::sin(angle),
            0.02f * std::cos(1.3f * angle)});
    }

    mesh.numVertices = static_cast<int>(mesh.points.size());
    for (int id = 0; id < mesh.numVertices; ++id) {
        mesh.expectedLocalControlIds.push_back(id);
    }

    for (int i = 0; i < valence; ++i) {
        int next = (i + 1) % valence;
        int innerA = 1 + i;
        int innerB = 1 + next;
        int outerA = 1 + valence + i;
        int outerB = 1 + valence + next;

        append_face(mesh, 0, innerA, innerB);
        append_face(mesh, innerA, outerA, outerB);
        append_face(mesh, innerA, outerB, innerB);
    }

    return mesh;
}

#if SLIMED_VALENCE4_MAPPING_PROOF_REPORT
static MeshCase load_serialized_valence4_fixture(char const *verticesPath,
                                                 char const *facesPath) {
    MeshCase mesh;
    mesh.name = "approved_closed_valence4_regular_octahedron";
    mesh.sampleFace = 0;
    mesh.extraordinaryValence = 4;

    std::ifstream vertices(verticesPath);
    std::string line;
    while (std::getline(vertices, line)) {
        if (line.empty()) {
            continue;
        }
        std::replace(line.begin(), line.end(), ',', ' ');
        std::istringstream row(line);
        Point point;
        if (!(row >> point.x >> point.y >> point.z)) {
            mesh.numVertices = -1;
            return mesh;
        }
        mesh.points.push_back(point);
    }

    std::ifstream faces(facesPath);
    while (std::getline(faces, line)) {
        if (line.empty()) {
            continue;
        }
        std::replace(line.begin(), line.end(), ',', ' ');
        std::istringstream row(line);
        int a = -1;
        int b = -1;
        int c = -1;
        if (!(row >> a >> b >> c)) {
            mesh.numVertices = -1;
            return mesh;
        }
        append_face(mesh, a, b, c);
    }

    mesh.numVertices = static_cast<int>(mesh.points.size());
    for (int id = 0; id < mesh.numVertices; ++id) {
        mesh.expectedLocalControlIds.push_back(id);
    }
    return mesh;
}
#endif

static char const *patch_type_name(Far::PatchDescriptor::Type type) {
    switch (type) {
        case Far::PatchDescriptor::NON_PATCH:
            return "NON_PATCH";
        case Far::PatchDescriptor::POINTS:
            return "POINTS";
        case Far::PatchDescriptor::LINES:
            return "LINES";
        case Far::PatchDescriptor::QUADS:
            return "QUADS";
        case Far::PatchDescriptor::TRIANGLES:
            return "TRIANGLES";
        case Far::PatchDescriptor::LOOP:
            return "LOOP";
        case Far::PatchDescriptor::REGULAR:
            return "REGULAR";
        case Far::PatchDescriptor::GREGORY:
            return "GREGORY";
        case Far::PatchDescriptor::GREGORY_BOUNDARY:
            return "GREGORY_BOUNDARY";
        case Far::PatchDescriptor::GREGORY_BASIS:
            return "GREGORY_BASIS";
        case Far::PatchDescriptor::GREGORY_TRIANGLE:
            return "GREGORY_TRIANGLE";
    }
    return "UNKNOWN";
}

static int count_nonzero(float const *weights, int count) {
    int result = 0;
    for (int i = 0; i < count; ++i) {
        if (std::abs(weights[i]) > 1.0e-8f) {
            ++result;
        }
    }
    return result;
}

static std::set<int> expanded_source_ids(Far::ConstIndexArray const &patchVertices,
                                         float const *basisWeights,
                                         int controlCount,
                                         Far::StencilTable const *cvStencils,
                                         int originalVertexCount) {
    std::set<int> sourceIds;
    for (int basisIndex = 0; basisIndex < controlCount; ++basisIndex) {
        if (std::abs(basisWeights[basisIndex]) <= 1.0e-8f) {
            continue;
        }

        int patchVertex = patchVertices[basisIndex];
        if (cvStencils && patchVertex < cvStencils->GetNumStencils()) {
            Far::Stencil stencil = cvStencils->GetStencil(patchVertex);
            Far::Index const *indices = stencil.GetVertexIndices();
            float const *weights = stencil.GetWeights();
            for (int stencilIndex = 0; stencilIndex < stencil.GetSize();
                 ++stencilIndex) {
                if (std::abs(basisWeights[basisIndex] * weights[stencilIndex]) >
                    1.0e-8f) {
                    sourceIds.insert(indices[stencilIndex]);
                }
            }
        } else if (patchVertex < originalVertexCount) {
            sourceIds.insert(patchVertex);
        }
    }
    return sourceIds;
}

static int represented_expected_count(std::set<int> const &sourceIds,
                                      std::vector<int> const &expectedIds) {
    int represented = 0;
    for (int expectedId : expectedIds) {
        if (sourceIds.count(expectedId)) {
            ++represented;
        }
    }
    return represented;
}

static void print_int_array(std::vector<int> const &values) {
    std::cout << "[";
    for (int i = 0; i < static_cast<int>(values.size()); ++i) {
        if (i > 0) {
            std::cout << ",";
        }
        std::cout << values[i];
    }
    std::cout << "]";
}

static void print_int_set(std::set<int> const &values) {
    std::cout << "[";
    bool first = true;
    for (int value : values) {
        if (!first) {
            std::cout << ",";
        }
        first = false;
        std::cout << value;
    }
    std::cout << "]";
}

static std::vector<int> missing_expected_ids(
    std::set<int> const &sourceIds, std::vector<int> const &expectedIds) {
    std::vector<int> missing;
    for (int expectedId : expectedIds) {
        if (!sourceIds.count(expectedId)) {
            missing.push_back(expectedId);
        }
    }
    return missing;
}

static std::set<int> limit_weight_source_ids(Far::LimitStencil const &stencil,
                                             float const *weights) {
    std::set<int> sourceIds;
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        if (std::abs(weights[i]) > 1.0e-8f) {
            sourceIds.insert(indices[i]);
        }
    }
    return sourceIds;
}

static void merge_ids(std::set<int> &dest, std::set<int> const &src) {
    dest.insert(src.begin(), src.end());
}

static void print_coverage_summary(char const *name,
                                   std::set<int> const &sourceIds,
                                   std::vector<int> const &expectedIds) {
    std::vector<int> missing = missing_expected_ids(sourceIds, expectedIds);
    std::cout << ",\"" << name << "_source_ids\":";
    print_int_set(sourceIds);
    std::cout << ",\"" << name << "_source_count\":" << sourceIds.size();
    std::cout << ",\"" << name << "_expected_local_control_count\":"
              << represented_expected_count(sourceIds, expectedIds);
    std::cout << ",\"" << name
              << "_missing_expected_local_control_ids\":";
    print_int_array(missing);
    std::cout << ",\"" << name << "_all_expected_local_controls_represented\":"
              << (missing.empty() ? "true" : "false");
}

static void print_highlighted_id_coverage(std::set<int> const &valueIds,
                                          std::set<int> const &firstIds,
                                          std::set<int> const &secondIds) {
    std::cout << ",\"highlighted_ids\":{\"8\":{\"value\":"
              << (valueIds.count(8) ? "true" : "false")
              << ",\"first_derivative\":"
              << (firstIds.count(8) ? "true" : "false")
              << ",\"second_derivative\":"
              << (secondIds.count(8) ? "true" : "false")
              << "},\"10\":{\"value\":"
              << (valueIds.count(10) ? "true" : "false")
              << ",\"first_derivative\":"
              << (firstIds.count(10) ? "true" : "false")
              << ",\"second_derivative\":"
              << (secondIds.count(10) ? "true" : "false") << "}}";
}

struct AggregateSampleLocation {
    char const *label;
    float v;
    float w;
};

static std::vector<AggregateSampleLocation> aggregate_sample_locations() {
    return {
        {"centroid", 1.0f / 3.0f, 1.0f / 3.0f},
        {"pr50_regular_sample_1", 0.20f, 0.30f},
        {"pr50_regular_sample_2", 0.05f, 0.85f},
        {"grid_020_020", 0.20f, 0.20f},
        {"grid_060_020", 0.60f, 0.20f},
        {"grid_020_060", 0.20f, 0.60f},
        {"grid_010_010", 0.10f, 0.10f},
        {"grid_045_010", 0.45f, 0.10f},
        {"grid_010_045", 0.10f, 0.45f},
    };
}

static void print_string_set(std::set<std::string> const &values) {
    std::cout << "[";
    bool first = true;
    for (std::string const &value : values) {
        if (!first) {
            std::cout << ",";
        }
        first = false;
        std::cout << "\"" << value << "\"";
    }
    std::cout << "]";
}

static void print_aggregate_source_coverage(
    MeshCase const &mesh,
    Far::TopologyRefiner const &refiner,
    Far::PatchTable const *patchTable,
    Far::StencilTable const *cvStencils) {
    std::cout << ",\"aggregate_source_coverage\":{";
    if (!patchTable || !cvStencils) {
        std::cout << "\"available\":false}";
        return;
    }

    std::vector<AggregateSampleLocation> sampleLocations =
        aggregate_sample_locations();
    const int ptexFaceCount = patchTable->GetNumPtexFaces();
    std::vector<std::vector<float>> sValues(ptexFaceCount);
    std::vector<std::vector<float>> tValues(ptexFaceCount);
    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.reserve(ptexFaceCount);

    for (int ptexFace = 0; ptexFace < ptexFaceCount; ++ptexFace) {
        sValues[ptexFace].reserve(sampleLocations.size());
        tValues[ptexFace].reserve(sampleLocations.size());
        for (AggregateSampleLocation const &sample : sampleLocations) {
            sValues[ptexFace].push_back(sample.v);
            tValues[ptexFace].push_back(sample.w);
        }

        Far::LimitStencilTableFactory::LocationArray location;
        location.ptexIdx = ptexFace;
        location.numLocations = static_cast<int>(sampleLocations.size());
        location.s = sValues[ptexFace].data();
        location.t = tValues[ptexFace].data();
        locations.push_back(location);
    }

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    Far::LimitStencilTable const *stencils =
        Far::LimitStencilTableFactory::Create(
            refiner, locations, cvStencils, patchTable, stencilOptions);
    if (!stencils) {
        std::cout << "\"available\":false,\"reason\":\"limit_stencil_creation_failed\"}";
        return;
    }

    Far::PatchMap patchMap(*patchTable);
    std::set<int> sampledPatchIndices;
    std::set<std::string> sampledPatchTypes;
    int foundPatchLookups = 0;
    int requestedSamples = ptexFaceCount * static_cast<int>(sampleLocations.size());
    for (int ptexFace = 0; ptexFace < ptexFaceCount; ++ptexFace) {
        for (int sample = 0; sample < static_cast<int>(sampleLocations.size());
             ++sample) {
            Far::PatchMap::Handle const *handle = patchMap.FindPatch(
                ptexFace, sValues[ptexFace][sample], tValues[ptexFace][sample]);
            if (handle) {
                ++foundPatchLookups;
                sampledPatchIndices.insert(handle->patchIndex);
                sampledPatchTypes.insert(
                    patch_type_name(
                        patchTable->GetPatchDescriptor(*handle).GetType()));
            }
        }
    }

    std::set<int> valueIds;
    std::set<int> duIds;
    std::set<int> dvIds;
    std::set<int> firstIds;
    std::set<int> duuIds;
    std::set<int> duvIds;
    std::set<int> dvvIds;
    std::set<int> secondIds;

    for (int stencilIndex = 0; stencilIndex < stencils->GetNumStencils();
         ++stencilIndex) {
        Far::LimitStencil stencil = stencils->GetLimitStencil(stencilIndex);
        merge_ids(valueIds, limit_weight_source_ids(stencil, stencil.GetWeights()));
        merge_ids(duIds, limit_weight_source_ids(stencil, stencil.GetDuWeights()));
        merge_ids(dvIds, limit_weight_source_ids(stencil, stencil.GetDvWeights()));
        merge_ids(duuIds, limit_weight_source_ids(stencil, stencil.GetDuuWeights()));
        merge_ids(duvIds, limit_weight_source_ids(stencil, stencil.GetDuvWeights()));
        merge_ids(dvvIds, limit_weight_source_ids(stencil, stencil.GetDvvWeights()));
    }
    merge_ids(firstIds, duIds);
    merge_ids(firstIds, dvIds);
    merge_ids(secondIds, duuIds);
    merge_ids(secondIds, duvIds);
    merge_ids(secondIds, dvvIds);

    std::cout << "\"available\":true";
    std::cout << ",\"strategy\":\"all_ptex_faces_x_sample_grid\"";
    std::cout << ",\"ptex_face_count\":" << ptexFaceCount;
    std::cout << ",\"coarse_face_count\":" << mesh.vertsPerFace.size();
    std::cout << ",\"sample_location_count_per_face\":"
              << sampleLocations.size();
    std::cout << ",\"requested_sample_count\":" << requestedSamples;
    std::cout << ",\"evaluated_sample_count\":"
              << stencils->GetNumStencils();
    std::cout << ",\"found_patch_lookup_count\":" << foundPatchLookups;
    std::cout << ",\"unique_patch_count_sampled\":"
              << sampledPatchIndices.size();
    std::cout << ",\"sampled_patch_indices\":";
    print_int_set(sampledPatchIndices);
    std::cout << ",\"sampled_patch_types\":";
    print_string_set(sampledPatchTypes);
    std::cout << ",\"sample_locations\":[";
    for (int i = 0; i < static_cast<int>(sampleLocations.size()); ++i) {
        AggregateSampleLocation const &sample = sampleLocations[i];
        if (i > 0) {
            std::cout << ",";
        }
        std::cout << "{\"label\":\"" << sample.label << "\",\"v\":"
                  << sample.v << ",\"w\":" << sample.w
                  << ",\"s\":" << sample.v << ",\"t\":" << sample.w
                  << "}";
    }
    std::cout << "]";
    print_coverage_summary("value", valueIds, mesh.expectedLocalControlIds);
    print_coverage_summary("du", duIds, mesh.expectedLocalControlIds);
    print_coverage_summary("dv", dvIds, mesh.expectedLocalControlIds);
    print_coverage_summary("first_derivative",
                           firstIds,
                           mesh.expectedLocalControlIds);
    print_coverage_summary("duu", duuIds, mesh.expectedLocalControlIds);
    print_coverage_summary("duv", duvIds, mesh.expectedLocalControlIds);
    print_coverage_summary("dvv", dvvIds, mesh.expectedLocalControlIds);
    print_coverage_summary("second_derivative",
                           secondIds,
                           mesh.expectedLocalControlIds);
    print_highlighted_id_coverage(valueIds, firstIds, secondIds);
    std::cout << "}";

    delete stencils;
}

static void print_patch_table_report(Far::PatchTable const *patchTable,
                                     Far::StencilTable const *cvStencils,
                                     std::vector<int> const &expectedIds,
                                     int originalVertexCount,
                                     int sampleFace,
                                     float s,
                                     float t) {
    if (!patchTable) {
        std::cout << ",\"patch_table\":{\"available\":false}";
        return;
    }

    Far::PatchMap patchMap(*patchTable);
    Far::PatchMap::Handle const *handle = patchMap.FindPatch(sampleFace, s, t);
    if (!handle) {
        std::cout << ",\"patch_table\":{\"available\":true,\"found\":false}";
        return;
    }

    Far::PatchDescriptor descriptor = patchTable->GetPatchDescriptor(*handle);
    int const controlCount = descriptor.GetNumControlVertices();
    Far::ConstIndexArray patchVertices = patchTable->GetPatchVertices(*handle);
    std::vector<float> weights(controlCount);
    std::vector<float> du(controlCount);
    std::vector<float> dv(controlCount);
    std::vector<float> duu(controlCount);
    std::vector<float> duv(controlCount);
    std::vector<float> dvv(controlCount);

    patchTable->EvaluateBasis(
        *handle, s, t, weights.data(), du.data(), dv.data(), duu.data(),
        duv.data(), dvv.data());

    std::set<int> expandedBasis = expanded_source_ids(
        patchVertices, weights.data(), controlCount, cvStencils,
        originalVertexCount);
    std::set<int> expandedDu = expanded_source_ids(
        patchVertices, du.data(), controlCount, cvStencils, originalVertexCount);
    std::set<int> expandedDv = expanded_source_ids(
        patchVertices, dv.data(), controlCount, cvStencils, originalVertexCount);
    std::set<int> expandedDuu = expanded_source_ids(
        patchVertices, duu.data(), controlCount, cvStencils, originalVertexCount);
    std::set<int> expandedDuv = expanded_source_ids(
        patchVertices, duv.data(), controlCount, cvStencils, originalVertexCount);
    std::set<int> expandedDvv = expanded_source_ids(
        patchVertices, dvv.data(), controlCount, cvStencils, originalVertexCount);
    std::set<int> expandedAnySecond = expandedDuu;
    expandedAnySecond.insert(expandedDuv.begin(), expandedDuv.end());
    expandedAnySecond.insert(expandedDvv.begin(), expandedDvv.end());

    std::cout << ",\"patch_table\":{\"available\":true,\"found\":true";
    std::cout << ",\"patch_type\":\"" << patch_type_name(descriptor.GetType())
              << "\"";
    std::cout << ",\"patch_control_vertex_count\":" << controlCount;
    std::cout << ",\"patch_vertices\":[";
    for (int i = 0; i < patchVertices.size(); ++i) {
        if (i > 0) {
            std::cout << ",";
        }
        std::cout << patchVertices[i];
    }
    std::cout << "]";
    std::cout << ",\"nonzero_basis_weights\":"
              << count_nonzero(weights.data(), controlCount);
    std::cout << ",\"nonzero_du_weights\":"
              << count_nonzero(du.data(), controlCount);
    std::cout << ",\"nonzero_dv_weights\":"
              << count_nonzero(dv.data(), controlCount);
    std::cout << ",\"nonzero_second_derivative_weights\":"
              << std::max(count_nonzero(duu.data(), controlCount),
                          std::max(count_nonzero(duv.data(), controlCount),
                                   count_nonzero(dvv.data(), controlCount)));
    std::cout << ",\"cv_stencil_count\":"
              << (cvStencils ? cvStencils->GetNumStencils() : 0);
    std::cout << ",\"expanded_basis_source_count\":"
              << expandedBasis.size();
    std::cout << ",\"expanded_du_source_count\":" << expandedDu.size();
    std::cout << ",\"expanded_dv_source_count\":" << expandedDv.size();
    std::cout << ",\"expanded_second_derivative_source_count\":"
              << expandedAnySecond.size();
    std::cout << ",\"expanded_basis_expected_local_control_count\":"
              << represented_expected_count(expandedBasis, expectedIds);
    std::cout << ",\"expanded_first_derivative_expected_local_control_count\":"
              << std::max(represented_expected_count(expandedDu, expectedIds),
                          represented_expected_count(expandedDv, expectedIds));
    std::cout << ",\"expanded_second_derivative_expected_local_control_count\":"
              << represented_expected_count(expandedAnySecond, expectedIds);
    std::cout << "}";
}

static Far::TopologyRefiner *create_refiner(MeshCase const &mesh) {
    typedef Far::TopologyDescriptor Descriptor;

    Descriptor desc;
    desc.numVertices = mesh.numVertices;
    desc.numFaces = static_cast<int>(mesh.vertsPerFace.size());
    desc.numVertsPerFace = mesh.vertsPerFace.data();
    desc.vertIndicesPerFace = mesh.vertIndices.data();

    Sdc::Options options;
    options.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);

    return Far::TopologyRefinerFactory<Descriptor>::Create(
        desc,
        Far::TopologyRefinerFactory<Descriptor>::Options(
            Sdc::SCHEME_LOOP, options));
}

static void accumulate(Point const *points,
                       Far::LimitStencil const &stencil,
                       float const *weights,
                       float out[3]) {
    out[0] = out[1] = out[2] = 0.0f;
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        Point const &point = points[indices[i]];
        out[0] += weights[i] * point.x;
        out[1] += weights[i] * point.y;
        out[2] += weights[i] * point.z;
    }
}

static bool finite3(float const values[3]) {
    return std::isfinite(values[0]) && std::isfinite(values[1]) &&
           std::isfinite(values[2]);
}

static void print_vec3(char const *name, float const values[3]) {
    std::cout << ",\"" << name << "\":[" << std::setprecision(9)
              << values[0] << "," << values[1] << "," << values[2] << "]";
}

static void cross3(float const lhs[3], float const rhs[3], float out[3]) {
    out[0] = lhs[1] * rhs[2] - lhs[2] * rhs[1];
    out[1] = lhs[2] * rhs[0] - lhs[0] * rhs[2];
    out[2] = lhs[0] * rhs[1] - lhs[1] * rhs[0];
}

static double norm3(float const values[3]) {
    return std::sqrt(static_cast<double>(values[0]) * values[0] +
                     static_cast<double>(values[1]) * values[1] +
                     static_cast<double>(values[2]) * values[2]);
}

static void normalize3(float const values[3], float out[3]) {
    double length = norm3(values);
    if (length == 0.0) {
        out[0] = out[1] = out[2] = 0.0f;
        return;
    }
    out[0] = static_cast<float>(values[0] / length);
    out[1] = static_cast<float>(values[1] / length);
    out[2] = static_cast<float>(values[2] / length);
}

#if SLIMED_REGULAR_EQUIVALENCE_REPORT || SLIMED_REGULAR_ADAPTER_PROOF_REPORT
static constexpr double kRegularEquivalenceAbsTolerance = 5.0e-6;
static constexpr double kRegularEquivalenceRelTolerance = 5.0e-6;

struct DifferenceSummary {
    double maxAbs = 0.0;
    double maxRel = 0.0;

    bool passed() const {
        return maxAbs <= kRegularEquivalenceAbsTolerance &&
               maxRel <= kRegularEquivalenceRelTolerance;
    }
};

static double relative_difference(double actual, double expected) {
    return std::abs(actual - expected) / std::max(1.0, std::abs(expected));
}

static void update_summary(DifferenceSummary &summary,
                           double actual,
                           double expected) {
    summary.maxAbs = std::max(summary.maxAbs, std::abs(actual - expected));
    summary.maxRel =
        std::max(summary.maxRel, relative_difference(actual, expected));
}

static void compare_vec3(DifferenceSummary &sampleSummary,
                         DifferenceSummary &aggregateSummary,
                         float const actual[3],
                         double const expected[3]) {
    for (int axis = 0; axis < 3; ++axis) {
        update_summary(sampleSummary, actual[axis], expected[axis]);
        update_summary(aggregateSummary, actual[axis], expected[axis]);
    }
}

static void compare_scalar(DifferenceSummary &sampleSummary,
                           DifferenceSummary &aggregateSummary,
                           double actual,
                           double expected) {
    update_summary(sampleSummary, actual, expected);
    update_summary(aggregateSummary, actual, expected);
}

static void cross3(double const lhs[3], double const rhs[3], double out[3]) {
    out[0] = lhs[1] * rhs[2] - lhs[2] * rhs[1];
    out[1] = lhs[2] * rhs[0] - lhs[0] * rhs[2];
    out[2] = lhs[0] * rhs[1] - lhs[1] * rhs[0];
}

static double norm3(double const values[3]) {
    return std::sqrt(values[0] * values[0] + values[1] * values[1] +
                     values[2] * values[2]);
}

static void normalize3(double const values[3], double out[3]) {
    double length = norm3(values);
    if (length == 0.0) {
        out[0] = out[1] = out[2] = 0.0;
        return;
    }
    out[0] = values[0] / length;
    out[1] = values[1] / length;
    out[2] = values[2] / length;
}

static constexpr double kSlimedRegularExpected[3][7][3] = {
    {
        {3.4999999999999982, 2.0207259421636894, -0.003450545921933364},
        {0.99999999999999978, -3.6236828367093433e-17,
         -0.019210698845634439},
        {0.50000000000000022, 0.86602540378443882,
         -0.019210698845634439},
        {3.3306690738754696e-16, 3.4587734865006226e-17,
         0.0017240750489055767},
        {-1.1102230246251565e-16, -1.1674737245020074e-16,
         0.0017240750489055771},
        {-5.5511151231257827e-17, -1.9572029680632367e-16,
         0.0017240750489055834},
        {-5.5511151231257827e-17, -1.9572029680632367e-16,
         0.0017240750489055834},
    },
    {
        {3.3500000000000001, 1.9918584287042085, -0.0002322832431500952},
        {0.99999999999999978, -1.2002033867471152e-16,
         -0.019363657606087825},
        {0.50000000000000033, 0.86602540378443882,
         -0.019363657606087818},
        {2.7755575615628914e-16, 4.1296024847155701e-16,
         0.00011143007653501233},
        {1.1102230246251565e-16, 1.1399713609118315e-16,
         0.0001114300765350122},
        {5.5511151231257827e-17, -2.6556107582143733e-16,
         0.0001114300765350114},
        {5.5511151231257827e-17, -2.6556107582143733e-16,
         0.0001114300765350114},
    },
    {
        {3.4750000000000001, 2.4681724007856505, -0.007865622601230705},
        {0.99999999999999978, -2.5312096407330787e-16,
         -0.018545015988735949},
        {0.50000000000000022, 0.86602540378443882,
         -0.018545015988735942},
        {-2.7755575615628914e-16, -5.2999475976476768e-16,
         0.0039817780102243674},
        {-4.4408920985006262e-16, -8.1361688734307423e-16,
         0.0039817780102243709},
        {2.2204460492503131e-16, 2.0460560118955678e-16,
         0.0039817780102243657},
        {2.2204460492503131e-16, 2.0460560118955678e-16,
         0.0039817780102243657},
    },
};

static void print_regular_equivalence_sample(
    int sample,
    float const position[3],
    float const du[3],
    float const dv[3],
    float const duu[3],
    float const duv[3],
    float const dvv[3],
    float const tangentCross[3],
    float const unitNormal[3],
    double areaIntegrand,
    double legacyVolumeIntegrand,
    DifferenceSummary &aggregateSummary,
    DifferenceSummary &derivedAggregateSummary) {
    DifferenceSummary sampleSummary;
    DifferenceSummary derivedSummary;
    compare_vec3(sampleSummary,
                 aggregateSummary,
                 position,
                 kSlimedRegularExpected[sample][0]);
    compare_vec3(sampleSummary,
                 aggregateSummary,
                 du,
                 kSlimedRegularExpected[sample][1]);
    compare_vec3(sampleSummary,
                 aggregateSummary,
                 dv,
                 kSlimedRegularExpected[sample][2]);
    compare_vec3(sampleSummary,
                 aggregateSummary,
                 duu,
                 kSlimedRegularExpected[sample][3]);
    compare_vec3(sampleSummary,
                 aggregateSummary,
                 dvv,
                 kSlimedRegularExpected[sample][4]);
    compare_vec3(sampleSummary,
                 aggregateSummary,
                 duv,
                 kSlimedRegularExpected[sample][5]);
    compare_vec3(sampleSummary,
                 aggregateSummary,
                 duv,
                 kSlimedRegularExpected[sample][6]);

    double expectedCross[3];
    double expectedUnitNormal[3];
    cross3(kSlimedRegularExpected[sample][1],
           kSlimedRegularExpected[sample][2],
           expectedCross);
    normalize3(expectedCross, expectedUnitNormal);
    double expectedAreaIntegrand = norm3(expectedCross);
    double expectedLegacyVolumeIntegrand =
        kSlimedRegularExpected[sample][0][0] * expectedCross[0];

    compare_vec3(derivedSummary,
                 derivedAggregateSummary,
                 tangentCross,
                 expectedCross);
    compare_vec3(derivedSummary,
                 derivedAggregateSummary,
                 unitNormal,
                 expectedUnitNormal);
    compare_scalar(derivedSummary,
                   derivedAggregateSummary,
                   areaIntegrand,
                   expectedAreaIntegrand);
    compare_scalar(derivedSummary,
                   derivedAggregateSummary,
                   legacyVolumeIntegrand,
                   expectedLegacyVolumeIntegrand);

    std::cout << ",\"regular_equivalence\":{\"reference\":\"frozen "
                 "SlimedLoopLimitSurfaceEvaluator output for the same "
                 "regular one-ring controls\"";
    std::cout << ",\"derivative_mapping\":\"du=d/dv,dv=d/dw,duu=d2/dv2,"
                 "dvv=d2/dw2,duv=d2/dvdw=d2/dwdv\"";
    std::cout << ",\"normal_mapping\":\"cross(du,dv)=cross(d/dv,d/dw)\"";
    std::cout << ",\"area_integrand\":\"norm(cross(du,dv))\"";
    std::cout << ",\"legacy_volume_integrand\":\"position.x*cross(du,dv).x\"";
    std::cout << ",\"sample_max_abs_difference\":" << sampleSummary.maxAbs;
    std::cout << ",\"sample_max_relative_difference\":"
              << sampleSummary.maxRel;
    std::cout << ",\"derived_sample_max_abs_difference\":"
              << derivedSummary.maxAbs;
    std::cout << ",\"derived_sample_max_relative_difference\":"
              << derivedSummary.maxRel;
    std::cout << ",\"passed\":" << (sampleSummary.passed() ? "true" : "false")
              << ",\"derived_passed\":"
              << (derivedSummary.passed() ? "true" : "false")
              << ",\"slimed_reference\":{\"tangent_cross_product\":["
              << expectedCross[0] << "," << expectedCross[1] << ","
              << expectedCross[2] << "],\"unit_normal\":["
              << expectedUnitNormal[0] << "," << expectedUnitNormal[1] << ","
              << expectedUnitNormal[2] << "],\"area_integrand\":"
              << expectedAreaIntegrand << ",\"legacy_volume_integrand\":"
              << expectedLegacyVolumeIntegrand << "}"
              << "}";
}
#endif

#if SLIMED_FORCE_TRANSPOSE_REPORT || SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT || SLIMED_VALENCE4_MAPPING_PROOF_REPORT
static constexpr double kTransposeTolerance = 1.0e-5;

static double deterministic_gradient(int row, int axis) {
    return 0.125 * static_cast<double>(row + 1) -
           0.03125 * static_cast<double>(axis + 2) +
           0.0078125 * static_cast<double>((row + 1) * (axis + 1));
}

static double weighted_component(Point const *points,
                                 Far::LimitStencil const &stencil,
                                 float const *weights,
                                 int axis) {
    double result = 0.0;
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        Point const &point = points[indices[i]];
        double component = axis == 0 ? point.x : (axis == 1 ? point.y : point.z);
        result += static_cast<double>(weights[i]) * component;
    }
    return result;
}

static void add_transpose_row(Far::LimitStencil const &stencil,
                              float const *weights,
                              int row,
                              std::vector<double> &backProjection) {
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        int const vertex = indices[i];
        for (int axis = 0; axis < 3; ++axis) {
            backProjection[3 * vertex + axis] +=
                static_cast<double>(weights[i]) *
                deterministic_gradient(row, axis);
        }
    }
}

static double dot_controls(Point const *points,
                           std::vector<double> const &backProjection) {
    double result = 0.0;
    for (int vertex = 0; vertex < static_cast<int>(backProjection.size() / 3);
         ++vertex) {
        Point const &point = points[vertex];
        result += static_cast<double>(point.x) * backProjection[3 * vertex];
        result += static_cast<double>(point.y) * backProjection[3 * vertex + 1];
        result += static_cast<double>(point.z) * backProjection[3 * vertex + 2];
    }
    return result;
}

static double sample_linear_functional(Point const *points,
                                       Far::LimitStencil const &stencil,
                                       std::vector<float const *> const &rows) {
    double result = 0.0;
    for (int row = 0; row < static_cast<int>(rows.size()); ++row) {
        for (int axis = 0; axis < 3; ++axis) {
            result += deterministic_gradient(row, axis) *
                      weighted_component(points, stencil, rows[row], axis);
        }
    }
    return result;
}

static double max_abs_control_value(std::vector<double> const &values) {
    double result = 0.0;
    for (double value : values) {
        result = std::max(result, std::abs(value));
    }
    return result;
}
#endif

#if SLIMED_FORCE_TRANSPOSE_REPORT
static bool print_force_transpose_report(MeshCase const &mesh,
                                         Far::LimitStencil const &stencil) {
    std::vector<float const *> opensubdivRows = {
        stencil.GetWeights(),
        stencil.GetDuWeights(),
        stencil.GetDvWeights(),
        stencil.GetDuuWeights(),
        stencil.GetDuvWeights(),
        stencil.GetDvvWeights(),
    };
    std::vector<float const *> slimedRows = {
        stencil.GetWeights(),
        stencil.GetDuWeights(),
        stencil.GetDvWeights(),
        stencil.GetDuuWeights(),
        stencil.GetDvvWeights(),
        stencil.GetDuvWeights(),
        stencil.GetDuvWeights(),
    };

    std::vector<double> opensubdivBackProjection(mesh.numVertices * 3, 0.0);
    for (int row = 0; row < static_cast<int>(opensubdivRows.size()); ++row) {
        add_transpose_row(stencil, opensubdivRows[row], row,
                          opensubdivBackProjection);
    }
    double const opensubdivSampleDot =
        sample_linear_functional(mesh.points.data(), stencil, opensubdivRows);
    double const opensubdivControlDot =
        dot_controls(mesh.points.data(), opensubdivBackProjection);
    double const opensubdivAbsDifference =
        std::abs(opensubdivSampleDot - opensubdivControlDot);

    std::vector<double> slimedBackProjection(mesh.numVertices * 3, 0.0);
    for (int row = 0; row < static_cast<int>(slimedRows.size()); ++row) {
        add_transpose_row(stencil, slimedRows[row], row, slimedBackProjection);
    }
    double const slimedSampleDot =
        sample_linear_functional(mesh.points.data(), stencil, slimedRows);
    double const slimedControlDot =
        dot_controls(mesh.points.data(), slimedBackProjection);
    double const slimedAbsDifference =
        std::abs(slimedSampleDot - slimedControlDot);

    std::set<int> sourceIds;
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        sourceIds.insert(indices[i]);
    }

    bool const passed = opensubdivAbsDifference <= kTransposeTolerance &&
                        slimedAbsDifference <= kTransposeTolerance;
    std::cout << ",\"force_transpose_contract\":{";
    std::cout << "\"kind\":\"toy_linear_functional_only\"";
    std::cout << ",\"not_production_force_formula\":true";
    std::cout << ",\"source_ids\":";
    print_int_set(sourceIds);
    std::cout << ",\"source_id_count\":" << sourceIds.size();
    std::cout << ",\"local_control_component_count\":"
              << sourceIds.size() * 3;
    std::cout << ",\"opensubdiv_sample_gradient_component_count\":18";
    std::cout << ",\"slimed_compatible_sample_gradient_component_count\":21";
    std::cout << ",\"opensubdiv_rows\":\"value,du,dv,duu,duv,dvv\"";
    std::cout << ",\"slimed_compatible_rows\":\"position,d/dv,d/dw,"
                 "d2/dv2,d2/dw2,d2/dvdw,d2/dwdv\"";
    std::cout << ",\"mixed_derivative_policy\":\"OpenSubdiv duv is used for "
                 "both SLIMED mixed rows in this toy transpose check\"";
    std::cout << ",\"transpose_identity\":\"g dot (W p) == (W^T g) dot p\"";
    std::cout << ",\"opensubdiv_sample_dot\":" << opensubdivSampleDot;
    std::cout << ",\"opensubdiv_control_dot\":" << opensubdivControlDot;
    std::cout << ",\"opensubdiv_abs_difference\":"
              << opensubdivAbsDifference;
    std::cout << ",\"slimed_compatible_sample_dot\":" << slimedSampleDot;
    std::cout << ",\"slimed_compatible_control_dot\":" << slimedControlDot;
    std::cout << ",\"slimed_compatible_abs_difference\":"
              << slimedAbsDifference;
    std::cout << ",\"max_abs_backprojected_component\":"
              << max_abs_control_value(slimedBackProjection);
    std::cout << ",\"tolerance\":" << kTransposeTolerance;
    std::cout << ",\"passed\":" << (passed ? "true" : "false");
    std::cout << "}";
    return passed;
}
#endif

#if SLIMED_REGULAR_ACTUAL_FORCE_REPORT || SLIMED_REGULAR_ADAPTER_PROOF_REPORT
static constexpr double kActualForceTolerance = 1.0e-8;

struct Vec3d {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Mat3d {
    double v[3][3] = {{0.0, 0.0, 0.0},
                      {0.0, 0.0, 0.0},
                      {0.0, 0.0, 0.0}};
};

struct ActualForceParams {
    double kCurv = 47.5;
    double spontCurv = 0.18;
    double uSurf = 130.0;
    double area0 = 2.75;
    double area = 0.0;
    double uVol = 65.0;
    double vol0 = 0.82;
    double vol = 0.0;
};

struct ActualForceResult {
    double meanCurv = 0.0;
    double eBend = 0.0;
    Vec3d normVector;
    std::vector<double> fBend;
    std::vector<double> fArea;
    std::vector<double> fVolume;
};

static Vec3d make_vec(double x, double y, double z) {
    Vec3d out;
    out.x = x;
    out.y = y;
    out.z = z;
    return out;
}

static double get_axis(Vec3d const &value, int axis) {
    if (axis == 0) {
        return value.x;
    }
    return axis == 1 ? value.y : value.z;
}

static void set_axis(Vec3d &value, int axis, double component) {
    if (axis == 0) {
        value.x = component;
    } else if (axis == 1) {
        value.y = component;
    } else {
        value.z = component;
    }
}

static Vec3d operator+(Vec3d const &lhs, Vec3d const &rhs) {
    return make_vec(lhs.x + rhs.x, lhs.y + rhs.y, lhs.z + rhs.z);
}

static Vec3d operator-(Vec3d const &lhs, Vec3d const &rhs) {
    return make_vec(lhs.x - rhs.x, lhs.y - rhs.y, lhs.z - rhs.z);
}

static Vec3d operator*(Vec3d const &value, double scale) {
    return make_vec(value.x * scale, value.y * scale, value.z * scale);
}

static Vec3d operator*(double scale, Vec3d const &value) {
    return value * scale;
}

static Vec3d &operator+=(Vec3d &lhs, Vec3d const &rhs) {
    lhs.x += rhs.x;
    lhs.y += rhs.y;
    lhs.z += rhs.z;
    return lhs;
}

static double dot(Vec3d const &lhs, Vec3d const &rhs) {
    return lhs.x * rhs.x + lhs.y * rhs.y + lhs.z * rhs.z;
}

static Vec3d cross(Vec3d const &lhs, Vec3d const &rhs) {
    return make_vec(lhs.y * rhs.z - lhs.z * rhs.y,
                    lhs.z * rhs.x - lhs.x * rhs.z,
                    lhs.x * rhs.y - lhs.y * rhs.x);
}

static double norm(Vec3d const &value) {
    return std::sqrt(dot(value, value));
}

static Vec3d normalized(Vec3d const &value) {
    double const length = norm(value);
    if (length == 0.0) {
        return Vec3d();
    }
    return value * (1.0 / length);
}

static Mat3d kron(Vec3d const &lhs, Vec3d const &rhs) {
    Mat3d out;
    for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
            out.v[row][col] = get_axis(lhs, row) * get_axis(rhs, col);
        }
    }
    return out;
}

static Mat3d operator+(Mat3d const &lhs, Mat3d const &rhs) {
    Mat3d out;
    for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
            out.v[row][col] = lhs.v[row][col] + rhs.v[row][col];
        }
    }
    return out;
}

static Mat3d &operator+=(Mat3d &lhs, Mat3d const &rhs) {
    for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
            lhs.v[row][col] += rhs.v[row][col];
        }
    }
    return lhs;
}

static Mat3d operator*(Mat3d const &value, double scale) {
    Mat3d out;
    for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
            out.v[row][col] = value.v[row][col] * scale;
        }
    }
    return out;
}

static Vec3d row_vec_times_matrix(Vec3d const &row, Mat3d const &matrix) {
    Vec3d out;
    for (int col = 0; col < 3; ++col) {
        double value = 0.0;
        for (int axis = 0; axis < 3; ++axis) {
            value += get_axis(row, axis) * matrix.v[axis][col];
        }
        set_axis(out, col, value);
    }
    return out;
}

static Vec3d weighted_vec3(MeshCase const &mesh,
                           Far::LimitStencil const &stencil,
                           float const *weights) {
    Vec3d out;
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        Point const &point = mesh.points[indices[i]];
        out.x += static_cast<double>(weights[i]) * point.x;
        out.y += static_cast<double>(weights[i]) * point.y;
        out.z += static_cast<double>(weights[i]) * point.z;
    }
    return out;
}

static bool finite_vec(Vec3d const &value) {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z);
}

static void add_force(std::vector<double> &target,
                      int vertex,
                      Vec3d const &force,
                      double scale) {
    target[3 * vertex] += scale * force.x;
    target[3 * vertex + 1] += scale * force.y;
    target[3 * vertex + 2] += scale * force.z;
}

static double max_abs_component(std::vector<double> const &values) {
    double out = 0.0;
    for (double value : values) {
        out = std::max(out, std::abs(value));
    }
    return out;
}

static double l1_component_sum(std::vector<double> const &values) {
    double out = 0.0;
    for (double value : values) {
        out += std::abs(value);
    }
    return out;
}

static double max_abs_component_delta(std::vector<double> const &lhs,
                                      std::vector<double> const &rhs) {
    double out = 0.0;
    for (int i = 0; i < static_cast<int>(lhs.size()); ++i) {
        out = std::max(out, std::abs(lhs[i] - rhs[i]));
    }
    return out;
}

static bool all_finite(std::vector<double> const &values) {
    for (double value : values) {
        if (!std::isfinite(value)) {
            return false;
        }
    }
    return true;
}

static void accumulate_area_volume(MeshCase const &mesh,
                                   Far::LimitStencil const &stencil,
                                   double quadratureCoeff,
                                   ActualForceParams &params) {
    Vec3d const x = weighted_vec3(mesh, stencil, stencil.GetWeights());
    Vec3d const a1 = weighted_vec3(mesh, stencil, stencil.GetDuWeights());
    Vec3d const a2 = weighted_vec3(mesh, stencil, stencil.GetDvWeights());
    Vec3d const xa = cross(a1, a2);
    double const sqa = norm(xa);
    params.area += 0.5 * quadratureCoeff * sqa;
    params.vol += (1.0 / 6.0) * quadratureCoeff * dot(x, xa);
}

static bool accumulate_actual_force_sample(MeshCase const &mesh,
                                           Far::LimitStencil const &stencil,
                                           double quadratureCoeff,
                                           ActualForceParams const &params,
                                           ActualForceResult &result,
                                           std::set<int> &forceSourceIds) {
    Vec3d const x = weighted_vec3(mesh, stencil, stencil.GetWeights());
    Vec3d const a_1 = weighted_vec3(mesh, stencil, stencil.GetDuWeights());
    Vec3d const a_2 = weighted_vec3(mesh, stencil, stencil.GetDvWeights());
    Vec3d const a_11 = weighted_vec3(mesh, stencil, stencil.GetDuuWeights());
    Vec3d const a_22 = weighted_vec3(mesh, stencil, stencil.GetDvvWeights());
    Vec3d const a_12 = weighted_vec3(mesh, stencil, stencil.GetDuvWeights());
    Vec3d const a_21 = a_12;

    Vec3d const xa = cross(a_1, a_2);
    double const sqa = norm(xa);
    if (sqa == 0.0) {
        return false;
    }
    double const tmp_sqa_sqrinv = 1.0 / sqa / sqa;

    Vec3d const xa_1 = cross(a_11, a_2) + cross(a_1, a_21);
    Vec3d const xa_2 = cross(a_12, a_2) + cross(a_1, a_22);
    double const sqa_1 = dot(xa, xa_1) / sqa;
    double const sqa_2 = dot(xa, xa_2) / sqa;
    Vec3d const a_3 = xa * (1.0 / sqa);
    Vec3d const a_31 = (xa_1 * sqa - xa * sqa_1) * tmp_sqa_sqrinv;
    Vec3d const a_32 = (xa_2 * sqa - xa * sqa_2) * tmp_sqa_sqrinv;

    Vec3d const tmp_a2x3 = cross(a_2, a_3);
    Vec3d const tmp_a3x1 = cross(a_3, a_1);
    Vec3d const a1 = tmp_a2x3 * (1.0 / sqa);
    Vec3d const a2 = tmp_a3x1 * (1.0 / sqa);
    Vec3d const a11 =
        ((cross(a_21, a_3) + cross(a_2, a_31)) * sqa -
         tmp_a2x3 * sqa_1) *
        tmp_sqa_sqrinv;
    Vec3d const a12 =
        ((cross(a_22, a_3) + cross(a_2, a_32)) * sqa -
         tmp_a2x3 * sqa_2) *
        tmp_sqa_sqrinv;
    Vec3d const a21 =
        ((cross(a_31, a_1) + cross(a_3, a_11)) * sqa -
         tmp_a3x1 * sqa_1) *
        tmp_sqa_sqrinv;
    Vec3d const a22 =
        ((cross(a_32, a_1) + cross(a_3, a_12)) * sqa -
         tmp_a3x1 * sqa_2) *
        tmp_sqa_sqrinv;

    double const H_curv = 0.5 * (dot(a1, a_31) + dot(a2, a_32));
    double const tmp_const_f =
        -params.kCurv * (2.0 * H_curv - params.spontCurv);
    double const tmp_const_l =
        params.kCurv * 0.5 * std::pow(2.0 * H_curv - params.spontCurv, 2.0);
    Vec3d const n1_be =
        (a_31 * dot(a1, a1) + a_32 * dot(a1, a2)) * tmp_const_f +
        a1 * tmp_const_l;
    Vec3d const n2_be =
        (a_31 * dot(a2, a1) + a_32 * dot(a2, a2)) * tmp_const_f +
        a2 * tmp_const_l;
    Vec3d const m1_be = a1 * (-tmp_const_f);
    Vec3d const m2_be = a2 * (-tmp_const_f);

    double const areaScale =
        (params.uSurf == 0.0 || params.area0 == 0.0)
            ? 0.0
            : (params.uSurf / params.area0) * (params.area - params.area0);
    Vec3d const n1_cons = a1 * areaScale;
    Vec3d const n2_cons = a2 * areaScale;

    double const tmp_evol =
        (params.uVol == 0.0 || params.vol0 == 0.0)
            ? 0.0
            : (params.uVol / params.vol0) * (params.vol - params.vol0) / 3.0;
    Vec3d const n1_conv =
        (a1 * dot(x, a_3) - a_3 * dot(x, a1)) * tmp_evol;
    Vec3d const n2_conv =
        (a2 * dot(x, a_3) - a_3 * dot(x, a2)) * tmp_evol;

    double const eBendTmp =
        0.5 * params.kCurv * sqa *
        std::pow(2.0 * H_curv - params.spontCurv, 2.0);
    double const halfCoeff = 0.5 * quadratureCoeff;

    Far::Index const *indices = stencil.GetVertexIndices();
    float const *sf0Weights = stencil.GetWeights();
    float const *sf1Weights = stencil.GetDuWeights();
    float const *sf2Weights = stencil.GetDvWeights();
    float const *sf3Weights = stencil.GetDuuWeights();
    float const *sf4Weights = stencil.GetDvvWeights();
    float const *sf5Weights = stencil.GetDuvWeights();
    float const *sf6Weights = stencil.GetDuvWeights();

    for (int i = 0; i < stencil.GetSize(); ++i) {
        int const vertex = indices[i];
        forceSourceIds.insert(vertex);
        double const sf0 = sf0Weights[i];
        double const sf1 = sf1Weights[i];
        double const sf2 = sf2Weights[i];
        double const sf3 = sf3Weights[i];
        double const sf4 = sf4Weights[i];
        double const sf5 = sf5Weights[i];
        double const sf6 = sf6Weights[i];

        Mat3d da1;
        da1 += kron(a1, a_3) * -sf3;
        da1 += kron(a11, a_3) * -sf1;
        da1 += kron(a1, a_31) * -sf1;
        da1 += kron(a2, a_3) * -sf6;
        da1 += kron(a21, a_3) * -sf2;
        da1 += kron(a2, a_31) * -sf2;

        Mat3d da2;
        da2 += kron(a1, a_3) * -sf5;
        da2 += kron(a12, a_3) * -sf1;
        da2 += kron(a1, a_32) * -sf1;
        da2 += kron(a2, a_3) * -sf4;
        da2 += kron(a22, a_3) * -sf2;
        da2 += kron(a2, a_32) * -sf2;

        Vec3d tempf_be = row_vec_times_matrix(m1_be, da1) +
                         row_vec_times_matrix(m2_be, da2) +
                         n1_be * sf1 + n2_be * sf2;
        tempf_be = tempf_be * -sqa;

        Vec3d tempf_cons = (n1_cons * sf1 + n2_cons * sf2) * -sqa;
        Vec3d tempf_conv =
            (n1_conv * sf1 + n2_conv * sf2 + a_3 * (tmp_evol * sf0)) *
            -sqa;

        add_force(result.fBend, vertex, tempf_be, halfCoeff);
        add_force(result.fArea, vertex, tempf_cons, halfCoeff);
        add_force(result.fVolume, vertex, tempf_conv, halfCoeff);
    }

    result.meanCurv += halfCoeff * H_curv;
    result.eBend += halfCoeff * eBendTmp;
    result.normVector += a_3 * halfCoeff;
    return finite_vec(x) && finite_vec(a_1) && finite_vec(a_2) &&
           finite_vec(a_11) && finite_vec(a_22) && finite_vec(a_12);
}

static bool print_regular_actual_force_report(MeshCase const &mesh,
                                              Far::TopologyRefiner const &refiner) {
    std::cout << ",\"regular_actual_force_formula\":{";
    if (mesh.name != "regular_triangular_lattice") {
        std::cout << "\"available\":false,\"reason\":\"regular_lattice_only\"}";
        return true;
    }

    float s[3] = {1.0f / 6.0f, 1.0f / 6.0f, 4.0f / 6.0f};
    float t[3] = {1.0f / 6.0f, 4.0f / 6.0f, 1.0f / 6.0f};
    double coeff[3] = {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0};

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = mesh.sampleFace;
    location.numLocations = 3;
    location.s = s;
    location.t = t;
    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    Far::LimitStencilTable const *stencils =
        Far::LimitStencilTableFactory::Create(refiner, locations, 0, 0,
                                              stencilOptions);
    if (!stencils) {
        std::cout << "\"available\":false,\"reason\":\"limit_stencil_creation_failed\"}";
        return false;
    }

    ActualForceParams params;
    for (int sample = 0; sample < stencils->GetNumStencils(); ++sample) {
        accumulate_area_volume(mesh, stencils->GetLimitStencil(sample),
                               coeff[sample], params);
    }

    ActualForceResult result;
    result.fBend.assign(mesh.numVertices * 3, 0.0);
    result.fArea.assign(mesh.numVertices * 3, 0.0);
    result.fVolume.assign(mesh.numVertices * 3, 0.0);
    std::set<int> forceSourceIds;
    bool finite = true;
    for (int sample = 0; sample < stencils->GetNumStencils(); ++sample) {
        finite = accumulate_actual_force_sample(
                     mesh, stencils->GetLimitStencil(sample), coeff[sample],
                     params, result, forceSourceIds) &&
                 finite;
    }
    result.normVector = normalized(result.normVector);

    bool const forcesFinite = all_finite(result.fBend) &&
                              all_finite(result.fArea) &&
                              all_finite(result.fVolume) &&
                              std::isfinite(result.eBend) &&
                              std::isfinite(result.meanCurv) &&
                              finite_vec(result.normVector);
    double const bendMax = max_abs_component(result.fBend);
    double const areaMax = max_abs_component(result.fArea);
    double const volumeMax = max_abs_component(result.fVolume);
    bool const nonzeroActualForce = bendMax > kActualForceTolerance &&
                                    areaMax > kActualForceTolerance &&
                                    volumeMax > kActualForceTolerance;
    bool const passed = finite && forcesFinite && nonzeroActualForce;

    std::cout << "\"available\":true";
    std::cout << ",\"kind\":\"opensubdiv_regular_rows_actual_formula_evidence\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"not_irregular_evidence\":true";
    std::cout << ",\"sample_set\":\"SLIMED second-order triangular quadrature\"";
    std::cout << ",\"derivative_mapping\":\"du=d/dv,dv=d/dw,duu=d2/dv2,"
                 "dvv=d2/dw2,duv=d2/dvdw=d2/dwdv\"";
    std::cout << ",\"formula_scope\":\"local copy of current bending, area, "
                 "and volume force sample algebra using OpenSubdiv row weights\"";
    std::cout << ",\"sample_count\":" << stencils->GetNumStencils();
    std::cout << ",\"force_source_ids\":";
    print_int_set(forceSourceIds);
    std::cout << ",\"force_source_count\":" << forceSourceIds.size();
    std::cout << ",\"area\":" << params.area;
    std::cout << ",\"volume\":" << params.vol;
    std::cout << ",\"e_bend\":" << result.eBend;
    std::cout << ",\"mean_curvature\":" << result.meanCurv;
    std::cout << ",\"normal\":[" << result.normVector.x << ","
              << result.normVector.y << "," << result.normVector.z << "]";
    std::cout << ",\"max_abs_f_bend\":" << bendMax;
    std::cout << ",\"max_abs_f_area\":" << areaMax;
    std::cout << ",\"max_abs_f_volume\":" << volumeMax;
    std::cout << ",\"l1_f_bend\":" << l1_component_sum(result.fBend);
    std::cout << ",\"l1_f_area\":" << l1_component_sum(result.fArea);
    std::cout << ",\"l1_f_volume\":" << l1_component_sum(result.fVolume);
    std::cout << ",\"finite\":" << (forcesFinite ? "true" : "false");
    std::cout << ",\"nonzero_actual_force\":"
              << (nonzeroActualForce ? "true" : "false");
    std::cout << ",\"passed\":" << (passed ? "true" : "false");
    std::cout << "}";

    delete stencils;
    return passed;
}

#if SLIMED_REGULAR_ADAPTER_PROOF_REPORT
static std::vector<int> regular_lattice_face_one_ring_source_ids() {
    return {9, 15, 10, 16, 22, 11, 17, 23, 29, 18, 24, 30};
}

static bool same_int_set(std::set<int> const &lhs,
                         std::vector<int> const &rhs) {
    return lhs == std::set<int>(rhs.begin(), rhs.end());
}

static double weight_for_source(Far::LimitStencil const &stencil,
                                float const *weights,
                                int sourceId) {
    double result = 0.0;
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        if (indices[i] == sourceId) {
            result += static_cast<double>(weights[i]);
        }
    }
    return result;
}

static Vec3d weighted_vec3_from_original_ids(
    MeshCase const &mesh,
    std::vector<int> const &sourceIds,
    std::vector<double> const &weights) {
    Vec3d out;
    for (int i = 0; i < static_cast<int>(sourceIds.size()); ++i) {
        Point const &point = mesh.points[sourceIds[i]];
        out.x += weights[i] * point.x;
        out.y += weights[i] * point.y;
        out.z += weights[i] * point.z;
    }
    return out;
}

static double max_abs_delta(Vec3d const &lhs, Vec3d const &rhs) {
    return std::max(std::abs(lhs.x - rhs.x),
                    std::max(std::abs(lhs.y - rhs.y),
                             std::abs(lhs.z - rhs.z)));
}

static double row_weight_by_source(std::vector<double> const &rowWeights,
                                   std::vector<int> const &sourceIds,
                                   int sourceId) {
    double result = 0.0;
    for (int i = 0; i < static_cast<int>(sourceIds.size()); ++i) {
        if (sourceIds[i] == sourceId) {
            result += rowWeights[i];
        }
    }
    return result;
}

static void print_vec3d_values(Vec3d const &values) {
    std::cout << "[" << std::setprecision(9) << values.x << ","
              << values.y << "," << values.z << "]";
}

static bool print_regular_adapter_proof_report(
    MeshCase const &mesh,
    Far::TopologyRefiner const &refiner) {
    std::cout << ",\"regular_adapter_proof\":{";
    if (mesh.name != "regular_triangular_lattice") {
        std::cout << "\"available\":false,\"reason\":\"regular_lattice_only\"}";
        return true;
    }

    float s[3] = {1.0f / 6.0f, 1.0f / 6.0f, 4.0f / 6.0f};
    float t[3] = {1.0f / 6.0f, 4.0f / 6.0f, 1.0f / 6.0f};
    float u[3] = {4.0f / 6.0f, 1.0f / 6.0f, 1.0f / 6.0f};
    double coeff[3] = {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0};

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = mesh.sampleFace;
    location.numLocations = 3;
    location.s = s;
    location.t = t;
    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    Far::LimitStencilTable const *stencils =
        Far::LimitStencilTableFactory::Create(refiner, locations, 0, 0,
                                              stencilOptions);
    if (!stencils) {
        std::cout << "\"available\":false,\"reason\":\"limit_stencil_creation_failed\"}";
        return false;
    }

    std::vector<int> const faceOneRing =
        regular_lattice_face_one_ring_source_ids();
    std::vector<int> duplicateSourceIds = faceOneRing;
    duplicateSourceIds[1] = duplicateSourceIds[0];
    duplicateSourceIds[4] = duplicateSourceIds[3];
    duplicateSourceIds[8] = duplicateSourceIds[7];

    double maxEvaluationDifference = 0.0;
    double maxDuplicateAggregationDifference = 0.0;
    bool allStencilSourcesMatchOneRing = true;
    bool duplicatedMixedRows = true;

    std::cout << "\"available\":true";
    std::cout << ",\"kind\":\"test_only_regular_opensubdiv_adapter_proof\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"contract\":\"LimitSurfaceWeightedSample-style seven rows keyed by original SLIMED source ids\"";
    std::cout << ",\"sample_set\":\"frozen SLIMED second-order triangular quadrature\"";
    std::cout << ",\"coordinate_mapping\":\"s=v,t=w\"";
    std::cout << ",\"row_order\":\"position,d/dv,d/dw,d2/dv2,d2/dw2,d2/dvdw,d2/dwdv\"";
    std::cout << ",\"mixed_derivative_policy\":\"OpenSubdiv duv is duplicated into both SLIMED mixed rows\"";
    std::cout << ",\"face_one_ring_source_ids\":";
    print_int_array(faceOneRing);
    std::cout << ",\"duplicate_aggregation_probe_source_ids\":";
    print_int_array(duplicateSourceIds);
    std::cout << ",\"samples\":[";

    for (int sample = 0; sample < stencils->GetNumStencils(); ++sample) {
        Far::LimitStencil stencil = stencils->GetLimitStencil(sample);
        std::vector<float const *> rowPtrs = {
            stencil.GetWeights(),
            stencil.GetDuWeights(),
            stencil.GetDvWeights(),
            stencil.GetDuuWeights(),
            stencil.GetDvvWeights(),
            stencil.GetDuvWeights(),
            stencil.GetDuvWeights(),
        };

        std::set<int> stencilSources;
        for (int i = 0; i < stencil.GetSize(); ++i) {
            stencilSources.insert(stencil.GetVertexIndices()[i]);
        }
        bool const sampleSourcesMatch =
            same_int_set(stencilSources, faceOneRing);
        allStencilSourcesMatchOneRing =
            allStencilSourcesMatchOneRing && sampleSourcesMatch;

        double sampleMaxEvaluationDifference = 0.0;
        double sampleMaxDuplicateDifference = 0.0;
        for (int row = 0; row < 7; ++row) {
            std::vector<double> faceOrderedWeights(faceOneRing.size(), 0.0);
            for (int col = 0; col < static_cast<int>(faceOneRing.size());
                 ++col) {
                faceOrderedWeights[col] =
                    weight_for_source(stencil, rowPtrs[row], faceOneRing[col]);
            }

            Vec3d const adapterValue = weighted_vec3_from_original_ids(
                mesh, faceOneRing, faceOrderedWeights);
            Vec3d const stencilValue =
                weighted_vec3(mesh, stencil, rowPtrs[row]);
            double const evalDifference =
                max_abs_delta(adapterValue, stencilValue);
            sampleMaxEvaluationDifference =
                std::max(sampleMaxEvaluationDifference, evalDifference);
            maxEvaluationDifference =
                std::max(maxEvaluationDifference, evalDifference);

            double const aggregatedDuplicate =
                row_weight_by_source(faceOrderedWeights,
                                     duplicateSourceIds,
                                     duplicateSourceIds[0]);
            double const expectedDuplicate =
                faceOrderedWeights[0] + faceOrderedWeights[1];
            double const duplicateDifference =
                std::abs(aggregatedDuplicate - expectedDuplicate);
            sampleMaxDuplicateDifference =
                std::max(sampleMaxDuplicateDifference, duplicateDifference);
            maxDuplicateAggregationDifference =
                std::max(maxDuplicateAggregationDifference,
                         duplicateDifference);
        }

        duplicatedMixedRows =
            duplicatedMixedRows &&
            sampleMaxEvaluationDifference <= kRegularEquivalenceAbsTolerance;

        if (sample > 0) {
            std::cout << ",";
        }
        std::cout << "{\"index\":" << sample;
        std::cout << ",\"v\":" << s[sample] << ",\"w\":" << t[sample]
                  << ",\"u\":" << u[sample];
        std::cout << ",\"s\":" << s[sample] << ",\"t\":" << t[sample];
        std::cout << ",\"quadrature_weight\":" << coeff[sample];
        std::cout << ",\"formula_factor\":" << 0.5 * coeff[sample];
        std::cout << ",\"stencil_source_ids\":";
        print_int_set(stencilSources);
        std::cout << ",\"stencil_sources_match_face_one_ring\":"
                  << (sampleSourcesMatch ? "true" : "false");
        std::cout << ",\"adapter_row_count\":7";
        std::cout << ",\"adapter_column_count\":" << faceOneRing.size();
        std::cout << ",\"duplicated_mixed_rows\":true";
        std::cout << ",\"max_adapter_vs_stencil_eval_difference\":"
                  << sampleMaxEvaluationDifference;
        std::cout << ",\"max_duplicate_aggregation_difference\":"
                  << sampleMaxDuplicateDifference;
        std::cout << "}";
    }
    std::cout << "]";

    ActualForceParams params;
    for (int sample = 0; sample < stencils->GetNumStencils(); ++sample) {
        accumulate_area_volume(mesh, stencils->GetLimitStencil(sample),
                               coeff[sample], params);
    }

    ActualForceResult result;
    result.fBend.assign(mesh.numVertices * 3, 0.0);
    result.fArea.assign(mesh.numVertices * 3, 0.0);
    result.fVolume.assign(mesh.numVertices * 3, 0.0);
    std::set<int> forceSourceIds;
    bool finite = true;
    for (int sample = 0; sample < stencils->GetNumStencils(); ++sample) {
        finite = accumulate_actual_force_sample(
                     mesh, stencils->GetLimitStencil(sample), coeff[sample],
                     params, result, forceSourceIds) &&
                 finite;
    }
    result.normVector = normalized(result.normVector);

    bool const forcesFinite = all_finite(result.fBend) &&
                              all_finite(result.fArea) &&
                              all_finite(result.fVolume) &&
                              std::isfinite(result.eBend) &&
                              std::isfinite(result.meanCurv) &&
                              finite_vec(result.normVector);
    double const bendMax = max_abs_component(result.fBend);
    double const areaMax = max_abs_component(result.fArea);
    double const volumeMax = max_abs_component(result.fVolume);
    bool const nonzeroActualForce = bendMax > kActualForceTolerance &&
                                    areaMax > kActualForceTolerance &&
                                    volumeMax > kActualForceTolerance;
    bool const forceSourcesMatchOneRing =
        same_int_set(forceSourceIds, faceOneRing);

    std::vector<double> scatteredBend(mesh.numVertices * 3, 0.0);
    std::vector<double> scatteredArea(mesh.numVertices * 3, 0.0);
    std::vector<double> scatteredVolume(mesh.numVertices * 3, 0.0);
    for (int row = 0; row < static_cast<int>(faceOneRing.size()); ++row) {
        int const sourceId = faceOneRing[row];
        for (int axis = 0; axis < 3; ++axis) {
            scatteredBend[3 * sourceId + axis] =
                result.fBend[3 * sourceId + axis];
            scatteredArea[3 * sourceId + axis] =
                result.fArea[3 * sourceId + axis];
            scatteredVolume[3 * sourceId + axis] =
                result.fVolume[3 * sourceId + axis];
        }
    }
    double const scatterDifference = std::max(
        max_abs_component_delta(scatteredBend, result.fBend),
        std::max(max_abs_component_delta(scatteredArea, result.fArea),
                 max_abs_component_delta(scatteredVolume, result.fVolume)));

    bool const adapterRowsPassed =
        allStencilSourcesMatchOneRing && duplicatedMixedRows &&
        maxEvaluationDifference <= kRegularEquivalenceAbsTolerance &&
        maxDuplicateAggregationDifference == 0.0;
    bool const actualForcesPassed =
        finite && forcesFinite && nonzeroActualForce &&
        forceSourcesMatchOneRing &&
        scatterDifference <= kActualForceTolerance;
    bool const passed = adapterRowsPassed && actualForcesPassed;

    std::cout << ",\"summary\":{";
    std::cout << "\"sample_count\":" << stencils->GetNumStencils();
    std::cout << ",\"all_stencil_sources_match_face_one_ring\":"
              << (allStencilSourcesMatchOneRing ? "true" : "false");
    std::cout << ",\"max_adapter_vs_stencil_eval_difference\":"
              << maxEvaluationDifference;
    std::cout << ",\"max_duplicate_aggregation_difference\":"
              << maxDuplicateAggregationDifference;
    std::cout << ",\"adapter_rows_passed\":"
              << (adapterRowsPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"actual_force_rows\":{";
    std::cout << "\"available\":true";
    std::cout << ",\"formula_scope\":\"local copy of current bending, area, and volume force sample algebra using adapter-remapped OpenSubdiv row weights\"";
    std::cout << ",\"force_source_ids\":";
    print_int_set(forceSourceIds);
    std::cout << ",\"force_sources_match_face_one_ring\":"
              << (forceSourcesMatchOneRing ? "true" : "false");
    std::cout << ",\"face_one_ring_scatter_identity\":"
              << (scatterDifference <= kActualForceTolerance ? "true" : "false");
    std::cout << ",\"scatter_max_abs_difference\":" << scatterDifference;
    std::cout << ",\"area\":" << params.area;
    std::cout << ",\"volume\":" << params.vol;
    std::cout << ",\"e_bend\":" << result.eBend;
    std::cout << ",\"mean_curvature\":" << result.meanCurv;
    std::cout << ",\"normal\":";
    print_vec3d_values(result.normVector);
    std::cout << ",\"max_abs_f_bend\":" << bendMax;
    std::cout << ",\"max_abs_f_area\":" << areaMax;
    std::cout << ",\"max_abs_f_volume\":" << volumeMax;
    std::cout << ",\"finite\":" << (forcesFinite ? "true" : "false");
    std::cout << ",\"nonzero_actual_force\":"
              << (nonzeroActualForce ? "true" : "false");
    std::cout << ",\"rows\":[";
    for (int row = 0; row < static_cast<int>(faceOneRing.size()); ++row) {
        int const sourceId = faceOneRing[row];
        if (row > 0) {
            std::cout << ",";
        }
        std::cout << "{\"local_row\":" << row;
        std::cout << ",\"source_id\":" << sourceId;
        std::cout << ",\"f_bend\":";
        print_vec3d_values(make_vec(result.fBend[3 * sourceId],
                                    result.fBend[3 * sourceId + 1],
                                    result.fBend[3 * sourceId + 2]));
        std::cout << ",\"f_area\":";
        print_vec3d_values(make_vec(result.fArea[3 * sourceId],
                                    result.fArea[3 * sourceId + 1],
                                    result.fArea[3 * sourceId + 2]));
        std::cout << ",\"f_volume\":";
        print_vec3d_values(make_vec(result.fVolume[3 * sourceId],
                                    result.fVolume[3 * sourceId + 1],
                                    result.fVolume[3 * sourceId + 2]));
        std::cout << "}";
    }
    std::cout << "]";
    std::cout << ",\"passed\":" << (actualForcesPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"passed\":" << (passed ? "true" : "false");
    std::cout << "}";

    delete stencils;
    return passed;
}
#endif
#endif

#if SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT
static void merge_limit_row_ids(std::set<int> &dest,
                                Far::LimitStencil const &stencil,
                                float const *weights) {
    merge_ids(dest, limit_weight_source_ids(stencil, weights));
}

static bool print_irregular_transpose_proof_map(
    MeshCase const &mesh,
    Far::TopologyRefiner const &refiner,
    Far::PatchTable const *patchTable,
    Far::StencilTable const *cvStencils) {
    std::cout << ",\"irregular_transpose_proof_map\":{";
    if (mesh.expectedLocalControlIds.empty()) {
        std::cout << "\"available\":false,\"reason\":\"regular_case_has_no_"
                     "11_control_fixture_ids\"}";
        return true;
    }
    if (!patchTable || !cvStencils) {
        std::cout << "\"available\":false,\"reason\":\"patch_table_or_control_"
                     "vertex_stencils_unavailable\"}";
        return false;
    }

    std::vector<AggregateSampleLocation> sampleLocations =
        aggregate_sample_locations();
    const int ptexFaceCount = patchTable->GetNumPtexFaces();
    std::vector<std::vector<float>> sValues(ptexFaceCount);
    std::vector<std::vector<float>> tValues(ptexFaceCount);
    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.reserve(ptexFaceCount);

    for (int ptexFace = 0; ptexFace < ptexFaceCount; ++ptexFace) {
        sValues[ptexFace].reserve(sampleLocations.size());
        tValues[ptexFace].reserve(sampleLocations.size());
        for (AggregateSampleLocation const &sample : sampleLocations) {
            sValues[ptexFace].push_back(sample.v);
            tValues[ptexFace].push_back(sample.w);
        }

        Far::LimitStencilTableFactory::LocationArray location;
        location.ptexIdx = ptexFace;
        location.numLocations = static_cast<int>(sampleLocations.size());
        location.s = sValues[ptexFace].data();
        location.t = tValues[ptexFace].data();
        locations.push_back(location);
    }

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    Far::LimitStencilTable const *stencils =
        Far::LimitStencilTableFactory::Create(
            refiner, locations, cvStencils, patchTable, stencilOptions);
    if (!stencils) {
        std::cout << "\"available\":false,\"reason\":\"limit_stencil_"
                     "creation_failed\"}";
        return false;
    }

    std::set<int> valueIds;
    std::set<int> firstIds;
    std::set<int> secondIds;
    std::set<int> transposeIds;
    std::vector<double> backProjection(mesh.numVertices * 3, 0.0);
    double sampleDot = 0.0;

    for (int stencilIndex = 0; stencilIndex < stencils->GetNumStencils();
         ++stencilIndex) {
        Far::LimitStencil stencil = stencils->GetLimitStencil(stencilIndex);
        std::vector<float const *> slimedRows = {
            stencil.GetWeights(),
            stencil.GetDuWeights(),
            stencil.GetDvWeights(),
            stencil.GetDuuWeights(),
            stencil.GetDvvWeights(),
            stencil.GetDuvWeights(),
            stencil.GetDuvWeights(),
        };

        merge_limit_row_ids(valueIds, stencil, stencil.GetWeights());
        merge_limit_row_ids(firstIds, stencil, stencil.GetDuWeights());
        merge_limit_row_ids(firstIds, stencil, stencil.GetDvWeights());
        merge_limit_row_ids(secondIds, stencil, stencil.GetDuuWeights());
        merge_limit_row_ids(secondIds, stencil, stencil.GetDuvWeights());
        merge_limit_row_ids(secondIds, stencil, stencil.GetDvvWeights());
        for (float const *rowWeights : slimedRows) {
            merge_limit_row_ids(transposeIds, stencil, rowWeights);
        }

        sampleDot +=
            sample_linear_functional(mesh.points.data(), stencil, slimedRows);
        for (int row = 0; row < static_cast<int>(slimedRows.size()); ++row) {
            add_transpose_row(stencil, slimedRows[row], row, backProjection);
        }
    }

    double const controlDot = dot_controls(mesh.points.data(), backProjection);
    double const absDifference = std::abs(sampleDot - controlDot);
    std::vector<int> missing = missing_expected_ids(
        transposeIds, mesh.expectedLocalControlIds);
    bool const identityPassed = absDifference <= kTransposeTolerance;
    bool const fixtureCoveragePassed = missing.empty();
    bool const proofMapPassed = identityPassed && fixtureCoveragePassed;

    std::cout << "\"available\":true";
    std::cout << ",\"kind\":\"observational_all_ptex_grid_toy_transpose\"";
    std::cout << ",\"not_production_force_formula\":true";
    std::cout << ",\"not_production_irregular_routing\":true";
    std::cout << ",\"strategy\":\"all_ptex_faces_x_sample_grid\"";
    std::cout << ",\"derivative_mapping\":\"du=d/dv,dv=d/dw,duu=d2/dv2,"
                 "dvv=d2/dw2,duv=d2/dvdw=d2/dwdv\"";
    std::cout << ",\"transpose_identity\":\"sum_samples g dot (W p) == "
                 "p dot sum_samples (W^T g)\"";
    std::cout << ",\"scatter_contract_observation\":\"backprojected source "
                 "ids are original control ids; production must still map "
                 "approved fixture ids through Face::oneRingVertices order\"";
    std::cout << ",\"ptex_face_count\":" << ptexFaceCount;
    std::cout << ",\"sample_location_count_per_face\":"
              << sampleLocations.size();
    std::cout << ",\"evaluated_sample_count\":"
              << stencils->GetNumStencils();
    std::cout << ",\"slimed_compatible_rows\":\"position,d/dv,d/dw,"
                 "d2/dv2,d2/dw2,d2/dvdw,d2/dwdv\"";
    std::cout << ",\"slimed_compatible_sample_gradient_component_count\":21";
    print_coverage_summary("value", valueIds, mesh.expectedLocalControlIds);
    print_coverage_summary("first_derivative",
                           firstIds,
                           mesh.expectedLocalControlIds);
    print_coverage_summary("second_derivative",
                           secondIds,
                           mesh.expectedLocalControlIds);
    print_coverage_summary("transpose_backprojection",
                           transposeIds,
                           mesh.expectedLocalControlIds);
    std::cout << ",\"expected_local_control_component_count\":"
              << mesh.expectedLocalControlIds.size() * 3;
    std::cout << ",\"transpose_backprojection_component_count\":"
              << transposeIds.size() * 3;
    std::cout << ",\"sample_dot\":" << sampleDot;
    std::cout << ",\"control_dot\":" << controlDot;
    std::cout << ",\"abs_difference\":" << absDifference;
    std::cout << ",\"max_abs_backprojected_component\":"
              << max_abs_control_value(backProjection);
    std::cout << ",\"tolerance\":" << kTransposeTolerance;
    std::cout << ",\"toy_transpose_passed\":"
              << (identityPassed ? "true" : "false");
    std::cout << ",\"fixture_source_coverage_passed\":"
              << (fixtureCoveragePassed ? "true" : "false");
    std::cout << ",\"passed\":" << (proofMapPassed ? "true" : "false");
    std::cout << "}";

    delete stencils;
    return proofMapPassed;
}
#endif

#if SLIMED_VALENCE4_MAPPING_PROOF_REPORT
static char const *kValence4RowNames[7] = {
    "value",
    "du",
    "dv",
    "duu",
    "dvv",
    "duv",
    "duv",
};

static std::map<int, double> aggregate_row_entries(
    std::vector<std::pair<int, double>> const &entries) {
    std::map<int, double> result;
    for (std::pair<int, double> const &entry : entries) {
        result[entry.first] += entry.second;
    }
    return result;
}

static double max_row_difference(std::map<int, double> const &left,
                                 std::map<int, double> const &right) {
    std::set<int> ids;
    for (std::pair<int const, double> const &entry : left) {
        ids.insert(entry.first);
    }
    for (std::pair<int const, double> const &entry : right) {
        ids.insert(entry.first);
    }

    double result = 0.0;
    for (int id : ids) {
        std::map<int, double>::const_iterator lhs = left.find(id);
        std::map<int, double>::const_iterator rhs = right.find(id);
        double const leftValue = lhs == left.end() ? 0.0 : lhs->second;
        double const rightValue = rhs == right.end() ? 0.0 : rhs->second;
        result = std::max(result, std::abs(leftValue - rightValue));
    }
    return result;
}

static bool row_maps_to_fixture(std::map<int, double> const &row,
                                int vertexCount) {
    for (std::pair<int const, double> const &entry : row) {
        if (entry.first < 0 || entry.first >= vertexCount) {
            return false;
        }
    }
    return true;
}

static bool expand_patch_row_to_fixture(
    Far::ConstIndexArray const &patchVertices,
    float const *basisWeights,
    int controlCount,
    Far::StencilTable const *cvStencils,
    int originalVertexCount,
    std::array<double, 6> &denseRow) {
    denseRow.fill(0.0);
    for (int basisIndex = 0; basisIndex < controlCount; ++basisIndex) {
        int const patchVertex = patchVertices[basisIndex];
        double const basisWeight = static_cast<double>(basisWeights[basisIndex]);
        if (patchVertex < 0 || patchVertex >= cvStencils->GetNumStencils()) {
            return false;
        }
        Far::Stencil stencil = cvStencils->GetStencil(patchVertex);
        for (int stencilIndex = 0; stencilIndex < stencil.GetSize();
             ++stencilIndex) {
            int const sourceId = stencil.GetVertexIndices()[stencilIndex];
            if (sourceId < 0 || sourceId >= originalVertexCount) {
                return false;
            }
            denseRow[sourceId] +=
                basisWeight *
                static_cast<double>(stencil.GetWeights()[stencilIndex]);
        }
    }
    return true;
}

static double proof_gradient(int face, int sample, int row, int axis) {
    return 0.071 * static_cast<double>(face + 1) +
           0.037 * static_cast<double>(sample + 1) +
           0.019 * static_cast<double>(row + 1) +
           0.011 * static_cast<double>(axis + 1) +
           0.003 * static_cast<double>((face + 1) * (row + 2)) +
           0.001 * static_cast<double>((sample + 2) * (axis + 3));
}

static double diagnostic_control_component(int sourceId, int axis) {
    return 0.23 + 0.17 * static_cast<double>(sourceId + 1) +
           0.031 * static_cast<double>(axis + 1) +
           0.007 * static_cast<double>((sourceId + 2) * (axis + 1)) +
           0.002 * static_cast<double>((sourceId + 1) * (sourceId + 1));
}

static double diagnostic_control_dot(
    std::vector<double> const &backProjection) {
    double result = 0.0;
    for (int sourceId = 0; sourceId < 6; ++sourceId) {
        for (int axis = 0; axis < 3; ++axis) {
            result += diagnostic_control_component(sourceId, axis) *
                      backProjection[3 * sourceId + axis];
        }
    }
    return result;
}

static bool print_valence4_mapping_proof(MeshCase const &mesh) {
    constexpr double kRowTolerance = 5.0e-6;
    constexpr double kAggregationTolerance = 1.0e-12;
    constexpr double kTransposeRelativeTolerance = 1.0e-12;
    constexpr int kSampleCountPerFace = 3;
    float const s[kSampleCountPerFace] = {
        1.0f / 6.0f,
        1.0f / 6.0f,
        4.0f / 6.0f,
    };
    float const t[kSampleCountPerFace] = {
        1.0f / 6.0f,
        4.0f / 6.0f,
        1.0f / 6.0f,
    };
    float const barycentricU[kSampleCountPerFace] = {
        4.0f / 6.0f,
        1.0f / 6.0f,
        1.0f / 6.0f,
    };
    double const quadratureWeight[kSampleCountPerFace] = {
        1.0 / 3.0,
        1.0 / 3.0,
        1.0 / 3.0,
    };

    bool const fixtureLoaded =
        mesh.numVertices == 6 && mesh.points.size() == 6 &&
        mesh.vertsPerFace.size() == 8 && mesh.vertIndices.size() == 24;
    if (!fixtureLoaded) {
        std::cerr << "failed to load the approved valence-4 fixture\n";
        return false;
    }

    Far::TopologyRefiner *refiner = create_refiner(mesh);
    if (!refiner) {
        std::cerr << "failed to create valence-4 fixture refiner\n";
        return false;
    }

    Far::PatchTableFactory::Options patchOptions(5);
    refiner->RefineAdaptive(patchOptions.GetRefineAdaptiveOptions());
    Far::PatchTable *patchTable =
        Far::PatchTableFactory::Create(*refiner, patchOptions);

    Far::StencilTableFactory::Options cvOptions;
    cvOptions.generateControlVerts = true;
    cvOptions.generateIntermediateLevels = true;
    cvOptions.factorizeIntermediateLevels = true;
    cvOptions.maxLevel = 5;
    Far::StencilTable const *cvStencils =
        Far::StencilTableFactory::Create(*refiner, cvOptions);

    if (!patchTable || !cvStencils) {
        std::cerr << "failed to create valence-4 patch/control tables\n";
        delete cvStencils;
        delete patchTable;
        delete refiner;
        return false;
    }

    int const ptexFaceCount = patchTable->GetNumPtexFaces();
    std::vector<std::vector<float>> sValues(
        ptexFaceCount, std::vector<float>(s, s + kSampleCountPerFace));
    std::vector<std::vector<float>> tValues(
        ptexFaceCount, std::vector<float>(t, t + kSampleCountPerFace));
    Far::LimitStencilTableFactory::LocationArrayVec locations;
    for (int ptexFace = 0; ptexFace < ptexFaceCount; ++ptexFace) {
        Far::LimitStencilTableFactory::LocationArray location;
        location.ptexIdx = ptexFace;
        location.numLocations = kSampleCountPerFace;
        location.s = sValues[ptexFace].data();
        location.t = tValues[ptexFace].data();
        locations.push_back(location);
    }

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    Far::LimitStencilTable const *stencils =
        Far::LimitStencilTableFactory::Create(
            *refiner, locations, cvStencils, patchTable, stencilOptions);
    if (!stencils) {
        std::cerr << "failed to create valence-4 limit stencils\n";
        delete cvStencils;
        delete patchTable;
        delete refiner;
        return false;
    }

    Far::PatchMap patchMap(*patchTable);
    bool faceIdentityPassed = ptexFaceCount == 8;
    bool allRowsFinite = true;
    bool allRowsMapped = true;
    bool rowSumChecksPassed = true;
    bool patchBasisComparisonPassed = true;
    bool duplicateAggregationPassed = true;
    bool permutationOrderStabilityPassed = true;
    double maxRowSumDifference = 0.0;
    double maxPatchBasisDifference = 0.0;
    double maxDuplicateAggregationDifference = 0.0;
    std::set<int> aggregateSourceIds;
    std::set<int> valueSourceIds;
    std::set<int> firstDerivativeSourceIds;
    std::set<int> secondDerivativeSourceIds;
    std::vector<double> stackedBackProjection(mesh.numVertices * 3, 0.0);
    double stackedSampleDot = 0.0;
    bool allSampleTransposePassed = true;

    std::cout << "{\"case\":\"" << mesh.name << "\"";
    std::cout << ",\"approved_fixture\":true";
    std::cout << ",\"scientifically_approved\":false";
    std::cout << ",\"approved_for_mapping_sample_transpose_proof\":true";
    std::cout << ",\"approved_scope\":\"mechanical OpenSubdiv Ptex identity, "
                 "sample ordering, source-row mapping, and linear transpose "
                 "evidence for the serialized octahedron stand-in\"";
    std::cout << ",\"proof_only\":true";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_route_enabled\":false";
    std::cout << ",\"fixture_loaded_from_serialized_csv\":true";
    std::cout << ",\"fixture_vertex_count\":" << mesh.numVertices;
    std::cout << ",\"fixture_face_count\":" << mesh.vertsPerFace.size();
    std::cout << ",\"expected_original_fixture_vertex_ids\":";
    print_int_array(mesh.expectedLocalControlIds);
    std::cout << ",\"coordinate_mapping\":\"s=v,t=w,u=1-v-w\"";
    std::cout << ",\"row_order\":[";
    for (int row = 0; row < 7; ++row) {
        if (row > 0) {
            std::cout << ",";
        }
        std::cout << "\"" << kValence4RowNames[row] << "\"";
    }
    std::cout << "]";
    std::cout << ",\"mixed_derivative_policy\":\"OpenSubdiv duv is duplicated "
                 "into SLIMED mixed rows vw and wv\"";
    std::cout << ",\"sample_ordering\":\"fixture faces.csv row order, then "
                 "sample indices 0,1,2\"";
    std::cout << ",\"per_face_samples\":[";
    for (int sample = 0; sample < kSampleCountPerFace; ++sample) {
        if (sample > 0) {
            std::cout << ",";
        }
        std::cout << "{\"sample_index\":" << sample;
        std::cout << ",\"v\":" << std::setprecision(17) << s[sample];
        std::cout << ",\"w\":" << t[sample];
        std::cout << ",\"u\":" << barycentricU[sample];
        std::cout << ",\"opensubdiv_s\":" << s[sample];
        std::cout << ",\"opensubdiv_t\":" << t[sample];
        std::cout << ",\"quadrature_weight\":"
                  << quadratureWeight[sample];
        std::cout << ",\"formula_factor\":"
                  << 0.5 * quadratureWeight[sample] << "}";
    }
    std::cout << "]";
    std::cout << ",\"ptex_face_count\":" << ptexFaceCount;
    std::cout << ",\"faces\":[";

    for (int face = 0; face < ptexFaceCount; ++face) {
        if (face > 0) {
            std::cout << ",";
        }
        bool currentFaceIdentityPassed = face < 8;
        std::set<int> currentFaceSourceIds;
        std::cout << "{\"fixture_face_index\":" << face;
        std::cout << ",\"oriented_fixture_vertex_ids\":["
                  << mesh.vertIndices[3 * face] << ","
                  << mesh.vertIndices[3 * face + 1] << ","
                  << mesh.vertIndices[3 * face + 2] << "]";
        std::cout << ",\"ptex_face_index\":" << face;
        std::cout << ",\"samples\":[";

        for (int sample = 0; sample < kSampleCountPerFace; ++sample) {
            int const stencilIndex = face * kSampleCountPerFace + sample;
            Far::LimitStencil stencil = stencils->GetLimitStencil(stencilIndex);
            std::vector<float const *> rowPtrs = {
                stencil.GetWeights(),
                stencil.GetDuWeights(),
                stencil.GetDvWeights(),
                stencil.GetDuuWeights(),
                stencil.GetDvvWeights(),
                stencil.GetDuvWeights(),
                stencil.GetDuvWeights(),
            };
            Far::PatchMap::Handle const *handle =
                patchMap.FindPatch(face, s[sample], t[sample]);
            int const patchParamFaceId =
                handle ? patchTable->GetPatchParam(*handle).GetFaceId() : -1;
            bool const sampleFaceIdentityPassed =
                handle && patchParamFaceId == face;
            currentFaceIdentityPassed =
                currentFaceIdentityPassed && sampleFaceIdentityPassed;
            std::array<std::array<double, 6>, 7> denseRows{};
            std::array<std::array<double, 6>, 7> patchRows{};
            bool patchRowsAvailable = false;
            if (handle) {
                Far::PatchDescriptor descriptor =
                    patchTable->GetPatchDescriptor(*handle);
                int const controlCount = descriptor.GetNumControlVertices();
                Far::ConstIndexArray patchVertices =
                    patchTable->GetPatchVertices(*handle);
                std::vector<float> basis(controlCount);
                std::vector<float> du(controlCount);
                std::vector<float> dv(controlCount);
                std::vector<float> duu(controlCount);
                std::vector<float> duv(controlCount);
                std::vector<float> dvv(controlCount);
                patchTable->EvaluateBasis(
                    *handle, s[sample], t[sample], basis.data(), du.data(),
                    dv.data(), duu.data(), duv.data(), dvv.data());
                std::vector<float const *> patchRowPtrs = {
                    basis.data(),
                    du.data(),
                    dv.data(),
                    duu.data(),
                    dvv.data(),
                    duv.data(),
                    duv.data(),
                };
                patchRowsAvailable = true;
                for (int row = 0; row < 7; ++row) {
                    patchRowsAvailable =
                        expand_patch_row_to_fixture(
                            patchVertices, patchRowPtrs[row], controlCount,
                            cvStencils, mesh.numVertices, patchRows[row]) &&
                        patchRowsAvailable;
                }
            }

            if (sample > 0) {
                std::cout << ",";
            }
            std::cout << "{\"sample_index\":" << sample;
            std::cout << ",\"limit_stencil_index\":" << stencilIndex;
            std::cout << ",\"patch_found\":"
                      << (handle ? "true" : "false");
            std::cout << ",\"patch_index\":"
                      << (handle ? handle->patchIndex : -1);
            std::cout << ",\"patch_type\":\""
                      << (handle
                              ? patch_type_name(
                                    patchTable->GetPatchDescriptor(*handle).GetType())
                              : "NONE")
                      << "\"";
            std::cout << ",\"patch_param_face_id\":" << patchParamFaceId;
            std::cout << ",\"ptex_identity_passed\":"
                      << (sampleFaceIdentityPassed ? "true" : "false");
            std::cout << ",\"rows\":[";

            for (int row = 0; row < 7; ++row) {
                std::vector<std::pair<int, double>> directEntries;
                std::vector<std::pair<int, double>> duplicateEntries;
                for (int entry = 0; entry < stencil.GetSize(); ++entry) {
                    int const sourceId = stencil.GetVertexIndices()[entry];
                    double const coefficient =
                        static_cast<double>(rowPtrs[row][entry]);
                    directEntries.push_back({sourceId, coefficient});
                    duplicateEntries.push_back({sourceId, 0.25 * coefficient});
                    duplicateEntries.push_back({sourceId, 0.75 * coefficient});
                }
                std::map<int, double> const aggregated =
                    aggregate_row_entries(directEntries);
                std::reverse(duplicateEntries.begin(), duplicateEntries.end());
                std::map<int, double> const duplicateAggregated =
                    aggregate_row_entries(duplicateEntries);
                double const duplicateDifference =
                    max_row_difference(aggregated, duplicateAggregated);
                bool const rowDuplicatePassed =
                    duplicateDifference <= kAggregationTolerance;

                double rowSum = 0.0;
                bool rowFinite = true;
                for (std::pair<int const, double> const &entry : aggregated) {
                    rowSum += entry.second;
                    rowFinite = rowFinite && std::isfinite(entry.second);
                    if (std::abs(entry.second) > 1.0e-8) {
                        aggregateSourceIds.insert(entry.first);
                        currentFaceSourceIds.insert(entry.first);
                        if (row == 0) {
                            valueSourceIds.insert(entry.first);
                        } else if (row <= 2) {
                            firstDerivativeSourceIds.insert(entry.first);
                        } else {
                            secondDerivativeSourceIds.insert(entry.first);
                        }
                    }
                }
                for (int sourceId = 0; sourceId < mesh.numVertices; ++sourceId) {
                    std::map<int, double>::const_iterator entry =
                        aggregated.find(sourceId);
                    denseRows[row][sourceId] =
                        entry == aggregated.end() ? 0.0 : entry->second;
                }
                double const expectedSum = row == 0 ? 1.0 : 0.0;
                double const rowSumDifference = std::abs(rowSum - expectedSum);
                bool const rowSumPassed =
                    rowSumDifference <= kRowTolerance;
                bool const rowMapped =
                    row_maps_to_fixture(aggregated, mesh.numVertices);
                double rowPatchDifference = 0.0;
                if (patchRowsAvailable) {
                    for (int sourceId = 0; sourceId < mesh.numVertices;
                         ++sourceId) {
                        rowPatchDifference = std::max(
                            rowPatchDifference,
                            std::abs(denseRows[row][sourceId] -
                                     patchRows[row][sourceId]));
                    }
                }
                bool const rowPatchPassed =
                    patchRowsAvailable && rowPatchDifference <= kRowTolerance;
                maxRowSumDifference =
                    std::max(maxRowSumDifference, rowSumDifference);
                maxPatchBasisDifference =
                    std::max(maxPatchBasisDifference, rowPatchDifference);
                maxDuplicateAggregationDifference =
                    std::max(maxDuplicateAggregationDifference,
                             duplicateDifference);
                allRowsFinite = allRowsFinite && rowFinite;
                allRowsMapped = allRowsMapped && rowMapped;
                rowSumChecksPassed = rowSumChecksPassed && rowSumPassed;
                patchBasisComparisonPassed =
                    patchBasisComparisonPassed && rowPatchPassed;
                duplicateAggregationPassed =
                    duplicateAggregationPassed && rowDuplicatePassed;
                permutationOrderStabilityPassed =
                    permutationOrderStabilityPassed && rowDuplicatePassed;

                if (row > 0) {
                    std::cout << ",";
                }
                std::cout << "{\"row_index\":" << row;
                std::cout << ",\"name\":\"" << kValence4RowNames[row]
                          << "\"";
                std::cout << ",\"entries\":[";
                for (int sourceId = 0; sourceId < mesh.numVertices;
                     ++sourceId) {
                    if (sourceId > 0) {
                        std::cout << ",";
                    }
                    std::cout << "{\"source_id\":" << sourceId
                              << ",\"coefficient\":" << std::setprecision(17)
                              << denseRows[row][sourceId] << "}";
                }
                std::cout << "]";
                std::cout << ",\"dense_source_id_order\":[0,1,2,3,4,5]";
                std::cout << ",\"finite_coefficients\":"
                          << (rowFinite ? "true" : "false");
                std::cout << ",\"mapped_to_original_fixture_vertex_ids\":"
                          << (rowMapped ? "true" : "false");
                std::cout << ",\"coefficient_sum\":" << rowSum;
                std::cout << ",\"expected_sum\":" << expectedSum;
                std::cout << ",\"sum_check_mathematically_applicable\":true";
                std::cout << ",\"sum_check_passed\":"
                          << (rowSumPassed ? "true" : "false");
                std::cout << ",\"patch_basis_expansion_available\":"
                          << (patchRowsAvailable ? "true" : "false");
                std::cout << ",\"patch_basis_limit_stencil_max_abs_difference\":"
                          << rowPatchDifference;
                std::cout << ",\"patch_basis_limit_stencil_match_passed\":"
                          << (rowPatchPassed ? "true" : "false");
                std::cout << ",\"duplicate_aggregation_rule\":\"ascending "
                             "original source id with additive coefficient sum\"";
                std::cout << ",\"duplicate_aggregation_probe\":\"split each "
                             "raw entry into 1/4 and 3/4 contributions, reverse "
                             "entry order, aggregate\"";
                std::cout << ",\"duplicate_aggregation_max_abs_difference\":"
                          << duplicateDifference;
                std::cout << ",\"duplicate_aggregation_passed\":"
                          << (rowDuplicatePassed ? "true" : "false");
                std::cout << "}";
            }
            bool const mixedRowsIdentical =
                denseRows[5] == denseRows[6];
            std::vector<double> sampleBackProjection(18, 0.0);
            double sampleRowDot = 0.0;
            for (int row = 0; row < 7; ++row) {
                for (int axis = 0; axis < 3; ++axis) {
                    double rowValue = 0.0;
                    for (int sourceId = 0; sourceId < mesh.numVertices;
                         ++sourceId) {
                        rowValue +=
                            denseRows[row][sourceId] *
                            diagnostic_control_component(sourceId, axis);
                        sampleBackProjection[3 * sourceId + axis] +=
                            quadratureWeight[sample] *
                            denseRows[row][sourceId] *
                            proof_gradient(face, sample, row, axis);
                    }
                    sampleRowDot +=
                        quadratureWeight[sample] *
                        proof_gradient(face, sample, row, axis) * rowValue;
                }
            }
            double const sampleControlDot =
                diagnostic_control_dot(sampleBackProjection);
            double const sampleResidual =
                std::abs(sampleRowDot - sampleControlDot);
            double const sampleScale =
                std::max(1.0,
                         std::max(std::abs(sampleRowDot),
                                  std::abs(sampleControlDot)));
            bool const sampleTransposePassed =
                sampleResidual <= kTransposeRelativeTolerance * sampleScale;
            allSampleTransposePassed =
                allSampleTransposePassed && sampleTransposePassed;
            stackedSampleDot += sampleRowDot;
            for (int component = 0; component < 18; ++component) {
                stackedBackProjection[component] +=
                    sampleBackProjection[component];
            }
            std::cout << "]";
            std::cout << ",\"mixed_rows_identical\":"
                      << (mixedRowsIdentical ? "true" : "false");
            std::cout << ",\"weighted_transpose\":{";
            std::cout << "\"sample_dot\":" << sampleRowDot;
            std::cout << ",\"control_dot\":" << sampleControlDot;
            std::cout << ",\"abs_residual\":" << sampleResidual;
            std::cout << ",\"scale\":" << sampleScale;
            std::cout << ",\"relative_tolerance\":"
                      << kTransposeRelativeTolerance;
            std::cout << ",\"passed\":"
                      << (sampleTransposePassed ? "true" : "false");
            std::cout << "}}";
        }
        faceIdentityPassed =
            faceIdentityPassed && currentFaceIdentityPassed;
        std::cout << "]";
        std::cout << ",\"all_samples_map_to_same_ptex_face_identity\":"
                  << (currentFaceIdentityPassed ? "true" : "false");
        std::cout << ",\"source_coverage_union\":";
        print_int_set(currentFaceSourceIds);
        std::cout << ",\"source_coverage_union_contains_all_six\":"
                  << (currentFaceSourceIds.size() == 6 ? "true" : "false");
        std::cout << "}";
    }
    std::cout << "]";

    double const stackedControlDot =
        diagnostic_control_dot(stackedBackProjection);
    double const stackedTransposeResidual =
        std::abs(stackedSampleDot - stackedControlDot);
    double const stackedTransposeScale =
        std::max(1.0,
                 std::max(std::abs(stackedSampleDot),
                          std::abs(stackedControlDot)));
    bool const stackedTransposePassed =
        stackedTransposeResidual <=
        kTransposeRelativeTolerance * stackedTransposeScale;
    std::set<int> backProjectionSourceIds;
    for (int sourceId = 0; sourceId < mesh.numVertices; ++sourceId) {
        for (int axis = 0; axis < 3; ++axis) {
            if (stackedBackProjection[3 * sourceId + axis] != 0.0) {
                backProjectionSourceIds.insert(sourceId);
            }
        }
    }
    bool const backProjectionSupportPassed =
        stackedBackProjection.size() == 18 &&
        backProjectionSourceIds.size() == 6;
    bool const sourceCoveragePassed =
        aggregateSourceIds.size() == 6 &&
        missing_expected_ids(aggregateSourceIds,
                             mesh.expectedLocalControlIds).empty();
    bool const derivativeCoveragePassed =
        missing_expected_ids(valueSourceIds,
                             mesh.expectedLocalControlIds).empty() &&
        missing_expected_ids(firstDerivativeSourceIds,
                             mesh.expectedLocalControlIds).empty() &&
        missing_expected_ids(secondDerivativeSourceIds,
                             mesh.expectedLocalControlIds).empty();
    bool const stencilCountPassed =
        stencils->GetNumStencils() == 8 * kSampleCountPerFace;
    bool const passed =
        faceIdentityPassed && stencilCountPassed && allRowsFinite &&
        allRowsMapped && rowSumChecksPassed && patchBasisComparisonPassed &&
        duplicateAggregationPassed && permutationOrderStabilityPassed &&
        sourceCoveragePassed && derivativeCoveragePassed &&
        allSampleTransposePassed && stackedTransposePassed &&
        backProjectionSupportPassed;

    std::cout << ",\"mapping_summary\":{";
    std::cout << "\"all_eight_oriented_faces_map_deterministically\":"
              << (faceIdentityPassed ? "true" : "false");
    std::cout << ",\"expected_limit_stencil_count\":24";
    std::cout << ",\"actual_limit_stencil_count\":"
              << stencils->GetNumStencils();
    std::cout << ",\"stencil_count_passed\":"
              << (stencilCountPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"row_checks\":{";
    std::cout << "\"all_coefficients_finite\":"
              << (allRowsFinite ? "true" : "false");
    std::cout << ",\"all_entries_map_to_original_fixture_vertex_ids\":"
              << (allRowsMapped ? "true" : "false");
    std::cout << ",\"position_partition_of_unity_and_derivative_sum_checks_passed\":"
              << (rowSumChecksPassed ? "true" : "false");
    std::cout << ",\"max_abs_row_sum_difference\":" << maxRowSumDifference;
    std::cout << ",\"row_sum_tolerance\":" << kRowTolerance;
    std::cout << ",\"patch_basis_limit_stencil_comparison_passed\":"
              << (patchBasisComparisonPassed ? "true" : "false");
    std::cout << ",\"max_abs_patch_basis_limit_stencil_difference\":"
              << maxPatchBasisDifference;
    std::cout << ",\"patch_basis_limit_stencil_tolerance\":"
              << kRowTolerance;
    std::cout << ",\"duplicate_aggregation_passed\":"
              << (duplicateAggregationPassed ? "true" : "false");
    std::cout << ",\"permutation_order_stability_passed\":"
              << (permutationOrderStabilityPassed ? "true" : "false");
    std::cout << ",\"max_abs_duplicate_aggregation_difference\":"
              << maxDuplicateAggregationDifference;
    std::cout << ",\"duplicate_aggregation_tolerance\":"
              << kAggregationTolerance;
    std::cout << "}";
    std::cout << ",\"aggregate_source_coverage\":{";
    std::cout << "\"original_fixture_vertex_ids\":";
    print_int_set(aggregateSourceIds);
    std::cout << ",\"value_source_ids\":";
    print_int_set(valueSourceIds);
    std::cout << ",\"first_derivative_source_ids\":";
    print_int_set(firstDerivativeSourceIds);
    std::cout << ",\"second_derivative_source_ids\":";
    print_int_set(secondDerivativeSourceIds);
    std::cout << ",\"all_six_fixture_vertices_covered\":"
              << (sourceCoveragePassed ? "true" : "false");
    std::cout << ",\"value_first_second_category_unions_cover_all_six\":"
              << (derivativeCoveragePassed ? "true" : "false");
    std::cout << ",\"no_claim_that_each_individual_row_covers_all_six\":true";
    std::cout << "}";
    std::cout << ",\"transpose_backprojection\":{";
    std::cout << "\"identity\":\"sum_face_samples weight*g dot (W p) == "
                 "p dot sum_face_samples weight*(W^T g)\"";
    std::cout << ",\"diagnostic\":\"asymmetric source/axis scalar controls "
                 "with face/sample/row/axis-dependent gradients\"";
    std::cout << ",\"sample_row_component_count\":"
              << 8 * kSampleCountPerFace * 7 * 3;
    std::cout << ",\"original_source_component_count\":"
              << mesh.numVertices * 3;
    std::cout << ",\"backprojection_component_count\":"
              << stackedBackProjection.size();
    std::cout << ",\"backprojected_original_source_ids\":";
    print_int_set(backProjectionSourceIds);
    std::cout << ",\"all_per_sample_weighted_transposes_passed\":"
              << (allSampleTransposePassed ? "true" : "false");
    std::cout << ",\"stacked_sample_dot\":" << stackedSampleDot;
    std::cout << ",\"stacked_control_dot\":" << stackedControlDot;
    std::cout << ",\"stacked_abs_residual\":"
              << stackedTransposeResidual;
    std::cout << ",\"stacked_scale\":" << stackedTransposeScale;
    std::cout << ",\"relative_tolerance\":"
              << kTransposeRelativeTolerance;
    std::cout << ",\"backprojection_has_exactly_18_components_with_all_six_support\":"
              << (backProjectionSupportPassed ? "true" : "false");
    std::cout << ",\"passed\":"
              << (allSampleTransposePassed && stackedTransposePassed &&
                          backProjectionSupportPassed
                      ? "true"
                      : "false");
    std::cout << "}";
    std::cout << ",\"claims_not_proven\":[";
    std::cout << "\"production geometry\",";
    std::cout << "\"production fBend/fArea/fVolume\",";
    std::cout << "\"production scatter/OpenMP parity\",";
    std::cout << "\"broader-valence production route readiness\"";
    std::cout << "]";
    std::cout << ",\"passed\":" << (passed ? "true" : "false");
    std::cout << "}" << std::endl;

    delete stencils;
    delete cvStencils;
    delete patchTable;
    delete refiner;
    return passed;
}
#endif

static int run_case(MeshCase const &mesh) {
    Far::TopologyRefiner *refiner = create_refiner(mesh);
    if (!refiner) {
        std::cerr << "failed to create refiner for " << mesh.name << "\n";
        return 2;
    }

    Far::PatchTable *patchTable = 0;
    Far::StencilTable const *cvStencils = 0;

#if SLIMED_BACKPROJECTION_REPORT || SLIMED_AGGREGATE_SOURCE_COVERAGE_REPORT || SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT || SLIMED_BROADER_VALENCE_COVERAGE_REPORT
    Far::PatchTableFactory::Options patchOptions(5);
    refiner->RefineAdaptive(patchOptions.GetRefineAdaptiveOptions());
    patchTable = Far::PatchTableFactory::Create(*refiner, patchOptions);

    Far::StencilTableFactory::Options cvOptions;
    cvOptions.generateControlVerts = true;
    cvOptions.generateIntermediateLevels = true;
    cvOptions.factorizeIntermediateLevels = true;
    cvOptions.maxLevel = 5;
    cvStencils = Far::StencilTableFactory::Create(*refiner, cvOptions);
#else
    Far::TopologyRefiner::AdaptiveOptions adaptiveOptions(3);
    refiner->RefineAdaptive(adaptiveOptions);
#endif

    const float slimedV[3] = {1.0f / 3.0f, 0.20f, 0.05f};
    const float slimedW[3] = {1.0f / 3.0f, 0.30f, 0.85f};
    float s[3];
    float t[3];
    for (int i = 0; i < 3; ++i) {
        s[i] = slimedV[i];
        t[i] = slimedW[i];
    }

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = mesh.sampleFace;
    location.numLocations = 3;
    location.s = s;
    location.t = t;

    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;

    Far::LimitStencilTable const *stencils =
        Far::LimitStencilTableFactory::Create(
            *refiner, locations, cvStencils, patchTable, stencilOptions);
    if (!stencils) {
        std::cerr << "failed to create limit stencils for " << mesh.name
                  << "\n";
        delete cvStencils;
        delete patchTable;
        delete refiner;
        return 3;
    }

    std::cout << "{\"case\":\"" << mesh.name << "\",";
    std::cout << "\"control_vertex_count\":" << mesh.numVertices << ",";
    std::cout << "\"face_count\":" << mesh.vertsPerFace.size() << ",";
    std::cout << "\"sample_face\":" << mesh.sampleFace << ",";
    std::cout << "\"slimed_to_opensubdiv_uv\":\"s=v,t=w\",";
    if (mesh.extraordinaryValence > 0) {
        std::cout << "\"observational_case_class\":\"broader_extraordinary_"
                     "valence\",";
        std::cout << "\"extraordinary_valence\":"
                  << mesh.extraordinaryValence << ",";
        std::cout << "\"not_production_support\":true,";
    }
    std::cout << "\"expected_local_control_ids\":";
    print_int_array(mesh.expectedLocalControlIds);
    std::cout << ",";
    std::cout << "\"samples\":[";

#if SLIMED_REGULAR_EQUIVALENCE_REPORT
    DifferenceSummary regularEquivalenceSummary;
    DifferenceSummary regularDerivedEquivalenceSummary;
#endif
#if SLIMED_FORCE_TRANSPOSE_REPORT
    bool forceTransposePassed = true;
#endif
#if SLIMED_REGULAR_ACTUAL_FORCE_REPORT
    bool regularActualForcePassed = true;
#endif
#if SLIMED_REGULAR_ADAPTER_PROOF_REPORT
    bool regularAdapterProofPassed = true;
#endif
#if SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT
    bool irregularTransposeProofMapPassed = true;
#endif

    for (int sample = 0; sample < stencils->GetNumStencils(); ++sample) {
        Far::LimitStencil stencil = stencils->GetLimitStencil(sample);
        if (!stencil.GetDuWeights() || !stencil.GetDvWeights() ||
            !stencil.GetDuuWeights() || !stencil.GetDuvWeights() ||
            !stencil.GetDvvWeights()) {
            std::cerr << "missing derivative weights for " << mesh.name
                      << "\n";
            delete stencils;
            delete cvStencils;
            delete patchTable;
            delete refiner;
            return 4;
        }

        float position[3], du[3], dv[3], duu[3], duv[3], dvv[3];
        accumulate(mesh.points.data(), stencil, stencil.GetWeights(), position);
        accumulate(mesh.points.data(), stencil, stencil.GetDuWeights(), du);
        accumulate(mesh.points.data(), stencil, stencil.GetDvWeights(), dv);
        accumulate(mesh.points.data(), stencil, stencil.GetDuuWeights(), duu);
        accumulate(mesh.points.data(), stencil, stencil.GetDuvWeights(), duv);
        accumulate(mesh.points.data(), stencil, stencil.GetDvvWeights(), dvv);
        if (!finite3(position) || !finite3(du) || !finite3(dv) ||
            !finite3(duu) || !finite3(duv) || !finite3(dvv)) {
            std::cerr << "non-finite evaluated value for " << mesh.name
                      << "\n";
            delete stencils;
            delete cvStencils;
            delete patchTable;
            delete refiner;
            return 5;
        }
        float tangentCross[3];
        float unitNormal[3];
        cross3(du, dv, tangentCross);
        normalize3(tangentCross, unitNormal);
        double areaIntegrand = norm3(tangentCross);
        double legacyVolumeIntegrand =
            static_cast<double>(position[0]) * tangentCross[0];

        std::set<int> sourceIdSet;
        for (int i = 0; i < stencil.GetSize(); ++i) {
            sourceIdSet.insert(stencil.GetVertexIndices()[i]);
        }
        int representedExpected = 0;
        for (int expectedId : mesh.expectedLocalControlIds) {
            if (sourceIdSet.count(expectedId)) {
                ++representedExpected;
            }
        }

        if (sample > 0) {
            std::cout << ",";
        }
        std::cout << "{\"index\":" << sample << ",";
        std::cout << "\"source_ids\":[";
        Far::Index const *indices = stencil.GetVertexIndices();
        for (int i = 0; i < stencil.GetSize(); ++i) {
            if (i > 0) {
                std::cout << ",";
            }
            std::cout << indices[i];
        }
        std::cout << "],\"position_weight_count\":" << stencil.GetSize();
        std::cout << ",\"du_weight_count\":" << stencil.GetSize();
        std::cout << ",\"dv_weight_count\":" << stencil.GetSize();
        std::cout << ",\"duu_weight_count\":" << stencil.GetSize();
        std::cout << ",\"duv_weight_count\":" << stencil.GetSize();
        std::cout << ",\"dvv_weight_count\":" << stencil.GetSize();
        std::cout << ",\"finite_position\":true";
        std::cout << ",\"finite_first_derivatives\":true";
        std::cout << ",\"finite_second_derivatives\":true";
        std::cout << ",\"represented_expected_local_control_count\":"
                  << representedExpected;
        std::cout << ",\"all_expected_local_controls_represented\":"
                  << (representedExpected ==
                              static_cast<int>(mesh.expectedLocalControlIds.size())
                          ? "true"
                          : "false");
        print_vec3("position", position);
        print_vec3("du", du);
        print_vec3("dv", dv);
        print_vec3("duu", duu);
        print_vec3("duv", duv);
        print_vec3("dvv", dvv);
        print_vec3("tangent_cross_product", tangentCross);
        print_vec3("unit_normal", unitNormal);
        std::cout << ",\"area_integrand\":" << areaIntegrand;
        std::cout << ",\"legacy_volume_integrand\":"
                  << legacyVolumeIntegrand;
#if SLIMED_REGULAR_EQUIVALENCE_REPORT
        if (mesh.name == "regular_triangular_lattice") {
            print_regular_equivalence_sample(sample,
                                             position,
                                             du,
                                             dv,
                                             duu,
                                             duv,
                                             dvv,
                                             tangentCross,
                                             unitNormal,
                                             areaIntegrand,
                                             legacyVolumeIntegrand,
                                             regularEquivalenceSummary,
                                             regularDerivedEquivalenceSummary);
        }
#endif
#if SLIMED_FORCE_TRANSPOSE_REPORT
        forceTransposePassed =
            print_force_transpose_report(mesh, stencil) && forceTransposePassed;
#endif
#if SLIMED_BACKPROJECTION_REPORT
        print_patch_table_report(patchTable,
                                 cvStencils,
                                 mesh.expectedLocalControlIds,
                                 mesh.numVertices,
                                 mesh.sampleFace,
                                 s[sample],
                                 t[sample]);
#endif
        std::cout << "}";
    }
    std::cout << "]";
#if SLIMED_REGULAR_EQUIVALENCE_REPORT
    if (mesh.name == "regular_triangular_lattice") {
        std::cout << ",\"regular_equivalence_summary\":{";
        std::cout << "\"sample_count\":" << stencils->GetNumStencils();
        std::cout << ",\"abs_tolerance\":"
                  << kRegularEquivalenceAbsTolerance;
        std::cout << ",\"relative_tolerance\":"
                  << kRegularEquivalenceRelTolerance;
        std::cout << ",\"max_abs_difference\":"
                  << regularEquivalenceSummary.maxAbs;
        std::cout << ",\"max_relative_difference\":"
                  << regularEquivalenceSummary.maxRel;
        std::cout << ",\"derived_max_abs_difference\":"
                  << regularDerivedEquivalenceSummary.maxAbs;
        std::cout << ",\"derived_max_relative_difference\":"
                  << regularDerivedEquivalenceSummary.maxRel;
        std::cout << ",\"passed\":"
                  << (regularEquivalenceSummary.passed() &&
                              regularDerivedEquivalenceSummary.passed()
                          ? "true"
                          : "false")
                  << "}";
    }
#endif
#if SLIMED_AGGREGATE_SOURCE_COVERAGE_REPORT
    print_aggregate_source_coverage(mesh, *refiner, patchTable, cvStencils);
#endif
#if SLIMED_REGULAR_ACTUAL_FORCE_REPORT
    regularActualForcePassed =
        print_regular_actual_force_report(mesh, *refiner);
#endif
#if SLIMED_REGULAR_ADAPTER_PROOF_REPORT
    regularAdapterProofPassed =
        print_regular_adapter_proof_report(mesh, *refiner);
#endif
#if SLIMED_BROADER_VALENCE_COVERAGE_REPORT && !SLIMED_AGGREGATE_SOURCE_COVERAGE_REPORT
    if (mesh.extraordinaryValence > 0) {
        print_aggregate_source_coverage(mesh, *refiner, patchTable, cvStencils);
    }
#endif
#if SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT
    irregularTransposeProofMapPassed =
        print_irregular_transpose_proof_map(mesh, *refiner, patchTable,
                                            cvStencils);
#endif
    std::cout << "}" << std::endl;

    delete stencils;
    delete cvStencils;
    delete patchTable;
    delete refiner;
#if SLIMED_REGULAR_EQUIVALENCE_REPORT
    if (mesh.name == "regular_triangular_lattice" &&
        (!regularEquivalenceSummary.passed() ||
         !regularDerivedEquivalenceSummary.passed())) {
        return 6;
    }
#endif
#if SLIMED_FORCE_TRANSPOSE_REPORT
    if (!forceTransposePassed) {
        return 7;
    }
#endif
#if SLIMED_REGULAR_ACTUAL_FORCE_REPORT
    if (!regularActualForcePassed) {
        return 9;
    }
#endif
#if SLIMED_REGULAR_ADAPTER_PROOF_REPORT
    if (!regularAdapterProofPassed) {
        return 10;
    }
#endif
#if SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT
    if (!irregularTransposeProofMapPassed) {
        return 8;
    }
#endif
    return 0;
}

int main(int argc, char **argv) {
#if SLIMED_VALENCE4_MAPPING_PROOF_REPORT
    if (argc != 3) {
        std::cerr << "valence-4 mapping proof requires vertices.csv and faces.csv\n";
        return 11;
    }
    return print_valence4_mapping_proof(
               load_serialized_valence4_fixture(argv[1], argv[2]))
               ? 0
               : 12;
#else
    int status = run_case(make_regular_lattice_case());
    if (status != 0) {
        return status;
    }
    status = run_case(make_irregular_fixture_case());
    if (status != 0) {
        return status;
    }
#if SLIMED_BACKPROJECTION_REPORT || SLIMED_AGGREGATE_SOURCE_COVERAGE_REPORT || SLIMED_FORCE_TRANSPOSE_REPORT || SLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT
    status = run_case(make_oriented_irregular_fixture_case());
    if (status != 0) {
        return status;
    }
    status = run_case(make_padded_irregular_fixture_case());
    if (status != 0) {
        return status;
    }
#endif
#if SLIMED_BROADER_VALENCE_COVERAGE_REPORT
    status = run_case(make_extraordinary_valence_fan_case(3));
    if (status != 0) {
        return status;
    }
    status = run_case(make_extraordinary_valence_fan_case(5));
    if (status != 0) {
        return status;
    }
    status = run_case(make_extraordinary_valence_fan_case(7));
    if (status != 0) {
        return status;
    }
    status = run_case(make_extraordinary_valence_fan_case(9));
    if (status != 0) {
        return status;
    }
#endif
    return 0;
#endif
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe an optional OpenSubdiv Far install without touching SLIMED builds."
    )
    parser.add_argument(
        "--opensubdiv-root",
        default=os.environ.get("OPENSUBDIV_ROOT"),
        help="OpenSubdiv install prefix. Defaults to OPENSUBDIV_ROOT.",
    )
    parser.add_argument(
        "--require-opensubdiv",
        action="store_true",
        help="Return non-zero instead of skip status when OpenSubdiv is absent.",
    )
    parser.add_argument(
        "--cxx",
        default=os.environ.get("CXX", "c++"),
        help="C++ compiler to use for the temporary probe.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the probe status as JSON.",
    )
    parser.add_argument(
        "--backprojection-report",
        action="store_true",
        help=(
            "Opt into extra patch-table/source-control reporting for force "
            "back-projection investigation."
        ),
    )
    parser.add_argument(
        "--aggregate-source-coverage-report",
        action="store_true",
        help=(
            "Opt into aggregate original-control source coverage across all "
            "ptex faces and a documented sample grid."
        ),
    )
    parser.add_argument(
        "--regular-equivalence-report",
        action="store_true",
        help=(
            "Opt into a regular-face comparison against frozen SLIMED "
            "regular evaluator values."
        ),
    )
    parser.add_argument(
        "--force-transpose-report",
        action="store_true",
        help=(
            "Opt into a toy linear-functional transpose check for OpenSubdiv "
            "value and derivative rows without using production force formulas."
        ),
    )
    parser.add_argument(
        "--regular-actual-force-report",
        action="store_true",
        help=(
            "Opt into an OpenSubdiv regular-row smoke that runs a local copy "
            "of the current bending/area/volume force sample algebra without "
            "changing production routing."
        ),
    )
    parser.add_argument(
        "--regular-adapter-proof-report",
        action="store_true",
        help=(
            "Opt into a test-only regular OpenSubdiv adapter proof report "
            "that remaps rows through original SLIMED source ids, duplicate "
            "aggregation, actual force rows, and Face::oneRingVertices scatter "
            "identity without changing production routing."
        ),
    )
    parser.add_argument(
        "--irregular-transpose-proof-map-report",
        action="store_true",
        help=(
            "Opt into an all-ptex/sample-grid 11-control fixture proof map "
            "for observational source coverage and toy transpose shape."
        ),
    )
    parser.add_argument(
        "--broader-valence-coverage-report",
        action="store_true",
        help=(
            "Opt into report-only aggregate source coverage for synthetic "
            "extraordinary-valence fan topologies beyond SLIMED's current "
            "supported irregular route."
        ),
    )
    parser.add_argument(
        "--valence4-mapping-sample-transpose-report",
        action="store_true",
        help=(
            "Opt into the approved serialized valence-4 octahedron proof-only "
            "Ptex/sample/source-row/transpose report."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["check"],
        help=(
            "Legacy alias for checklist compatibility. "
            "`--mode check` behaves like `--json`."
        ),
    )
    args = parser.parse_args()
    if args.mode == "check":
        args.json = True
    return args


def candidate_roots(explicit_root: str | None) -> list[Path]:
    roots: list[Path] = []
    if explicit_root:
        roots.append(Path(explicit_root))
    roots.extend(
        [
            Path("/opt/homebrew/opt/opensubdiv"),
            Path("/usr/local/opt/opensubdiv"),
            Path("/usr/local"),
            Path("/usr"),
        ]
    )
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def find_install(root: Path) -> tuple[Path, Path] | None:
    include_dir = root / "include"
    header = include_dir / "opensubdiv" / "far" / "topologyDescriptor.h"
    if not header.exists():
        return None

    for lib_dir in (root / "lib", root / "lib64"):
        if glob.glob(str(lib_dir / "libosdCPU.*")):
            return include_dir, lib_dir
    return None


def status_payload(status: str, details: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {"status": status}
    payload.update(details)
    return payload


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(f"status: {payload['status']}")
    for key, value in payload.items():
        if key != "status":
            print(f"{key}: {value}")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    args = parse_args()

    install: tuple[Path, Path] | None = None
    checked_roots = candidate_roots(args.opensubdiv_root)
    for root in checked_roots:
        install = find_install(root)
        if install:
            break

    if not install:
        payload = status_payload(
            "skipped",
            {
                "reason": "OpenSubdiv headers/libs were not found",
                "checked_roots": [str(root) for root in checked_roots],
                "next_step": "Set OPENSUBDIV_ROOT to an install prefix and rerun.",
            },
        )
        emit(payload, args.json)
        return 2 if args.require_opensubdiv else 0

    include_dir, lib_dir = install
    with tempfile.TemporaryDirectory(prefix="slimed-opensubdiv-probe-") as tmp:
        tmp_path = Path(tmp)
        source_path = tmp_path / "opensubdiv_probe.cpp"
        binary_path = tmp_path / "opensubdiv_probe"
        source_path.write_text(textwrap.dedent(PROBE_SOURCE), encoding="utf-8")

        command = [
            args.cxx,
            "-std=c++17",
        ]
        if args.backprojection_report:
            command.append("-DSLIMED_BACKPROJECTION_REPORT=1")
        if args.aggregate_source_coverage_report:
            command.append("-DSLIMED_AGGREGATE_SOURCE_COVERAGE_REPORT=1")
        if args.regular_equivalence_report:
            command.append("-DSLIMED_REGULAR_EQUIVALENCE_REPORT=1")
        if args.force_transpose_report:
            command.append("-DSLIMED_FORCE_TRANSPOSE_REPORT=1")
        if args.regular_actual_force_report:
            command.append("-DSLIMED_REGULAR_ACTUAL_FORCE_REPORT=1")
        if args.regular_adapter_proof_report:
            command.append("-DSLIMED_REGULAR_ADAPTER_PROOF_REPORT=1")
        if args.irregular_transpose_proof_map_report:
            command.append("-DSLIMED_IRREGULAR_TRANSPOSE_PROOF_MAP_REPORT=1")
        if args.broader_valence_coverage_report:
            command.append("-DSLIMED_BROADER_VALENCE_COVERAGE_REPORT=1")
        if args.valence4_mapping_sample_transpose_report:
            command.append("-DSLIMED_VALENCE4_MAPPING_PROOF_REPORT=1")
        command.extend(shlex.split(os.environ.get("OPENSUBDIV_CXXFLAGS", "")))
        command.extend(
            [
                str(source_path),
                "-I",
                str(include_dir),
                "-L",
                str(lib_dir),
                f"-Wl,-rpath,{lib_dir}",
            ]
        )
        command.extend(shlex.split(os.environ.get("OPENSUBDIV_LDFLAGS", "")))
        command.extend(["-losdCPU", "-o", str(binary_path)])

        compile_result = run_command(command)
        if compile_result.returncode != 0:
            payload = status_payload(
                "compile_failed",
                {
                    "command": command,
                    "stdout": compile_result.stdout,
                    "stderr": compile_result.stderr,
                },
            )
            emit(payload, args.json)
            return compile_result.returncode

        run_command_line = [str(binary_path)]
        if args.valence4_mapping_sample_transpose_report:
            fixture_dir = (
                Path(__file__).resolve().parents[1]
                / "data/fixtures/candidates/closed_valence4_octahedron"
            )
            run_command_line.extend(
                [
                    str(fixture_dir / "vertices.csv"),
                    str(fixture_dir / "faces.csv"),
                ]
            )
        run_result = run_command(run_command_line)
        if run_result.returncode != 0:
            payload = status_payload(
                "run_failed",
                {
                    "stdout": run_result.stdout,
                    "stderr": run_result.stderr,
                    "returncode": run_result.returncode,
                },
            )
            emit(payload, args.json)
            return run_result.returncode

        deterministic_repeat_match = None
        if args.valence4_mapping_sample_transpose_report:
            repeat_result = run_command(run_command_line)
            deterministic_repeat_match = (
                repeat_result.returncode == 0
                and repeat_result.stdout == run_result.stdout
                and repeat_result.stderr == run_result.stderr
            )
            if not deterministic_repeat_match:
                payload = status_payload(
                    "run_failed",
                    {
                        "reason": "canonical valence-4 proof JSON changed across identical runs",
                        "first_stdout": run_result.stdout,
                        "repeat_stdout": repeat_result.stdout,
                        "repeat_stderr": repeat_result.stderr,
                    },
                )
                emit(payload, args.json)
                return 1

    details: dict[str, object] = {
        "include_dir": str(include_dir),
        "lib_dir": str(lib_dir),
        "prototype_output": run_result.stdout.strip().splitlines(),
    }
    if args.valence4_mapping_sample_transpose_report:
        details.update(
            {
                "approved_fixture": True,
                "approved_for_mapping_sample_transpose_proof": True,
                "approved_scope": (
                "mechanical OpenSubdiv Ptex identity, sample ordering, "
                "source-row mapping, and linear transpose evidence"
                ),
                "deterministic_repeat_match": deterministic_repeat_match,
                "not_production_routing": True,
                "production_route_enabled": False,
                "proof_only": True,
                "scientifically_approved": False,
            }
        )
    payload = status_payload("passed", details)
    emit(payload, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
