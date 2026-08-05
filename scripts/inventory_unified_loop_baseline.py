#!/usr/bin/env python3
"""Fail-closed inventory for the unified irregular Loop architecture ADR.

This script is deliberately read-only.  It describes current main separately
from the unmerged PR 182 stack and rejects source, fixture, policy, or ADR drift
before later work packages rely on the baseline.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a"
PR182_SHA = "9587e3dce4509029e611e2937bac570b410193c3"
PR182_MERGE_BASE = "6d9213e260c90c74c72e831deab1a2ec2d67e1d3"

EXPECTED_BUILD_FLAGS = [
    "USE_OPENSUBDIV_REGULAR",
    "USE_OPENSUBDIV_VALENCE3",
    "USE_OPENSUBDIV_VALENCE5",
]
EXPECTED_RUNTIME_FLAGS = [
    "SLIMED_USE_OPENSUBDIV_REGULAR",
    "SLIMED_USE_OPENSUBDIV_VALENCE4",
    "SLIMED_USE_OPENSUBDIV_VALENCE5",
    "SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2",
]
EXPECTED_VOLUME_FACTOR_NAMES = ["kLegacyVolumeQuadratureFactor"]
EXPECTED_VOLUME_FUNCTIONAL_TOKENS: list[str] = []
EXPECTED_VALENCE5_FACE_SOURCE_MAPPING_SHA256 = (
    "9f5fe4e76a9815a806970164d4a5e02771c4350a6c1047ceb7ce3e86cd2acd1a")

EXPECTED_FACES = {
    "valence3_tetrahedron": [
        [0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]
    ],
    "valence4_octahedron": [
        [0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 2],
        [1, 3, 2], [1, 4, 3], [1, 5, 4], [1, 2, 5],
    ],
    "valence5_icosahedron": [
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ],
}

EXPECTED_FIXTURE_HASHES = {
    "data/fixtures/candidates/closed_valence3_tetrahedron/candidate_metadata.json":
        "3b2cf28dd5b4b52ea5a999e07fc89527513066ac8f2ef20b52137448fcb52660",
    "data/fixtures/candidates/closed_valence3_tetrahedron/faces.csv":
        "acfbd18a1922e465052f6badf5aa2567faa282add3edc7867f3bca7493e6e1aa",
    "data/fixtures/candidates/closed_valence3_tetrahedron/vertices.csv":
        "4a82e312830953d67731970042f5cf7d174e6af9f8844b7cd2b321209e51b898",
    "data/fixtures/candidates/closed_valence4_octahedron/candidate_metadata.json":
        "2109779d724d924ac416a127fa4a376cf1a72fbe9fa1391223995ebbccb60b74",
    "data/fixtures/candidates/closed_valence4_octahedron/faces.csv":
        "af9742137b89c25cc29e8b60e137967d8adfcdd80f33d3172fc13f1ed93838e8",
    "data/fixtures/candidates/closed_valence4_octahedron/vertices.csv":
        "b650ff4c1aed263701d25305d846f520933a2deb457655558f17a855e65c88b7",
    "data/fixtures/candidates/closed_mixed_valence345/candidate_metadata.json":
        "74ae00951e6ea20021722a45a887d0c47530d4d7248cb69f553cb1a66a60f14b",
    "data/fixtures/candidates/closed_mixed_valence345/faces.csv":
        "bc1db1bf7fb29e4e4bc7b41f93ea9c206fe80a022736f1f02d22063c0b800233",
    "data/fixtures/candidates/closed_mixed_valence345/vertices.csv":
        "affa93eec68b8de9d5dcd12d31bf1d7222410722b0cca44c58495c558e3d7287",
    "data/fixtures/closed_valence5/faces.csv":
        "561b3ec0c4aa6b1e684ef87c2738d8c20a474225bd4960a4a672d306a3e70327",
    "data/fixtures/closed_valence5/vertices.csv":
        "d0dae733433503f9e2aba4f8eda80fa2d6842d0f5a7b922d7ffce158f505cb45",
}

EXPECTED_DECISIONS = {
    "D0": "Proposed - pending explicit user disposition",
    "D1": "Proposed - pending explicit user scientific approval",
    "D2": "Proposed - pending explicit user/maintainer approval",
    "D3": "Pending post-WP2.1 oracle, scientific review, and user decision",
    "D4": "Pending post-WP2.1 characterization and user/maintainer decision",
    "D5": "Proposed - pending explicit user approval",
    "D6": "Accepted existing policy",
    "D7": "Accepted existing user instruction",
}

EXPECTED_TOLERANCES = {
    "regular_row_and_route_parity": {
        "value": 5.0e-6,
        "source": "src/mesh/OpenSubdiv_regular_evaluator.cpp",
        "owner": "existing regular OpenSubdiv proof/route",
    },
    "regular_residual_scale_floor": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_regular_evaluator.cpp",
        "owner": "existing regular OpenSubdiv residual metric",
    },
    "valence3_row_invariants": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_valence3_row_provider.cpp",
        "owner": "existing Valence-3 proof provider",
    },
    "valence4_row_invariants": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_valence4_row_provider.cpp",
        "owner": "existing Valence-4 exact route",
    },
    "valence5_row_invariants": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_valence5_row_provider.cpp",
        "owner": "existing Valence-5 exact route",
    },
    "valence5_reviewed_production_parity": {
        "value": 1.0e-10,
        "source": "include/energy_force/Valence5_opensubdiv_face_loop.hpp",
        "owner": "existing Valence-5 Phase-3 activation",
    },
    "irregular_serial_openmp_envelope": {
        "value": 1.0e-10,
        "source": "docs/irregular_serial_omp_tolerance_characterization.md",
        "owner": "existing irregular reduction characterization",
    },
}


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def _csv_int_rows(relative: str) -> list[list[int]]:
    with (ROOT / relative).open(newline="", encoding="utf-8") as stream:
        return [[int(value) for value in row] for row in csv.reader(stream)]


def _source_corpus() -> str:
    chunks: list[str] = []
    for base in (ROOT / "src", ROOT / "include"):
        for path in sorted(base.rglob("*")):
            if path.suffix in {".cpp", ".cu", ".cuh", ".hpp", ".h"}:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def _initializer_rows(text: str, marker: str, columns: int) -> list[list[int]]:
    start = text.index(marker)
    block = text[start:text.index("}};", start) + 3]
    number = r"(-?\d+)"
    pattern = r"\{\{\s*" + r"\s*,\s*".join([number] * columns) + r"\s*\}\}"
    return [[int(value) for value in match]
            for match in re.findall(pattern, block)]


def _rows_sha256(rows: list[list[int]]) -> str:
    encoded = json.dumps(rows, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _all_present(text: str, anchors: list[str]) -> bool:
    return all(anchor in text for anchor in anchors)


def _git_output(*arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *arguments], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def collect_inventory() -> dict[str, Any]:
    makefile = _text("Makefile")
    compute = _text("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
    regular = _text("src/mesh/OpenSubdiv_regular_evaluator.cpp")
    v3 = _text("src/mesh/OpenSubdiv_valence3_row_provider.cpp")
    v4 = _text("src/mesh/OpenSubdiv_valence4_row_provider.cpp")
    v4_topology = _text("src/mesh/Valence4_topology_source_mapping.cpp")
    v4_loop = _text("src/energy_force/Valence4_face_loop_route_preflight.cpp")
    v5 = _text("src/mesh/OpenSubdiv_valence5_row_provider.cpp")
    v5_loop = _text("src/energy_force/Valence5_opensubdiv_face_loop.cpp")
    geometry = _text("src/mesh/Mesh.cpp")
    legacy_topology = _text("src/mesh/Mesh_setup_geometry.cpp")
    legacy_matrix = _text("src/mesh/Gauss_quadrature.cpp")
    source_keyed_hpp = _text("include/energy_force/Source_keyed_kernel_call.hpp")
    source_keyed_cpp = _text("src/energy_force/Source_keyed_kernel_call.cpp")
    output = _text("src/io/output.cpp")
    cuda_cpu = _text("src/cuda/Cuda_regular_geometry_cpu.cpp")
    cuda_device = _text("src/cuda/Cuda_mesh_state.cu")
    adaptive = _text("include/mesh/Adaptive_edge_flip_quality.hpp")
    corpus = _source_corpus()

    build_flags = sorted(set(re.findall(
        r"^(USE_OPENSUBDIV_[A-Z0-9_]+)\s*\?=", makefile, re.MULTILINE)))
    runtime_flags = sorted(set(re.findall(
        r'"(SLIMED_USE_OPENSUBDIV_[A-Z0-9_]+)"', corpus)))
    volume_factor_names = sorted(set(re.findall(
        r"\b(k[A-Za-z0-9_]*Volume[A-Za-z0-9_]*(?:Factor|Functional|Mode))\b",
        corpus)))
    volume_functional_tokens = sorted(set(match.lower() for match in re.findall(
        r"\b(?:legacy[_-]?x[_-]?volume|full[_-]?divergence[_-]?volume|"
        r"volume[_-]?functional|volume[_-]?mode)\b", corpus,
        flags=re.IGNORECASE)))
    pr182_face_loop = _git_output(
        "show", f"{PR182_SHA}:src/energy_force/Valence3_opensubdiv_face_loop.cpp")

    fixtures = {path: _sha256(path) for path in EXPECTED_FIXTURE_HASHES}
    topology = {
        "valence3_tetrahedron": {
            "vertices": 4, "faces": 4, "valence": 3,
            "oriented_faces": _csv_int_rows(
                "data/fixtures/candidates/closed_valence3_tetrahedron/faces.csv"),
            "source_guard_present": _all_present(v3, [
                "kApprovedFaceCount = 4", "kApprovedSourceCount = 4",
                "vertex.adjacentVertices.size() != 3u",
                "!actual.oneRingVertices.empty()",
            ]),
            "source_faces_match_fixture":
                _initializer_rows(v3, "kApprovedFaces", 3) ==
                EXPECTED_FACES["valence3_tetrahedron"],
        },
        "valence4_octahedron": {
            "vertices": 6, "faces": 8, "valence": 4,
            "oriented_faces": _csv_int_rows(
                "data/fixtures/candidates/closed_valence4_octahedron/faces.csv"),
            "source_guard_present": _all_present(v4_topology, [
                "kApprovedVertexCount = 6", "kApprovedFaceCount = 8",
                "vertex.adjacentVertices.size() != 4u",
                "!face.oneRingVertices.empty()",
            ]),
            "source_faces_match_fixture":
                _initializer_rows(v4_topology, "kApprovedOrientedFaces", 3) ==
                EXPECTED_FACES["valence4_octahedron"],
        },
        "valence5_icosahedron": {
            "vertices": 12, "faces": 20, "valence": 5,
            "oriented_faces": _csv_int_rows("data/fixtures/closed_valence5/faces.csv"),
            "source_guard_present": _all_present(v5, [
                "kApprovedFaceCount = 20", "kApprovedSourceCount = 12",
                "vertex.adjacentVertices.size() != 5u",
                "actual.adjacentVertices.size() != 3u",
            ]),
            "source_faces_match_fixture":
                _initializer_rows(v5, "kApprovedFaces", 3) ==
                EXPECTED_FACES["valence5_icosahedron"],
            "face_source_mapping_sha256": _rows_sha256(
                _initializer_rows(v5, "kApprovedFaceSources", 9)),
        },
        "legacy_11_control_predicate": {
            "admitted_corner_valences": [5, 5, 5],
            "matrix_intended_corner_valences": [5, 6, 6],
            "defect_confirmed": _all_present(legacy_topology, [
                "vertices[node0].adjacentVertices.size() == 5",
                "vertices[node1].adjacentVertices.size() == 5",
                "vertices[node2].adjacentVertices.size() == 5",
                "int d4, d7, d8;",
            ]) and _all_present(legacy_matrix, [
                "const int N = 6;", "const int N1 = 5;",
                "std::vector<std::vector<double>> SM4(11",
            ]),
        },
    }

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "pending",
        "baseline": {
            "authoritative_current_main": BASE_SHA,
            "observed_head": _git_output("rev-parse", "HEAD"),
            "pr182_stack_head": PR182_SHA,
            "pr182_merge_base": PR182_MERGE_BASE,
            "observed_pr182_merge_base": _git_output("merge-base", PR182_SHA, BASE_SHA),
            "pr182_object_available": pr182_face_loop != "unavailable",
            "pr182_full_divergence_anchor":
                "kFullDivergenceVolumeQuadratureFactor" in pr182_face_loop
                and "dot(evaluated[0], areaVector)" in pr182_face_loop,
            "pr182_classification": "unmerged stacked negative convergence evidence",
            "pr182_current_main_production": False,
            "current_main_valence3_runtime_route": False,
        },
        "decisions": copy.deepcopy(EXPECTED_DECISIONS),
        "A_build_dependency": {
            "build_flags": build_flags,
            "dependency_root": "OPENSUBDIV_ROOT",
            "dependency_root_required_for_each_flag":
                all(f"{flag}=1 requires OPENSUBDIV_ROOT=" in makefile
                    for flag in EXPECTED_BUILD_FLAGS),
            "valence4_compile_macro": "USE_OPENSUBDIV_REGULAR",
            "valence4_macro_coupling_present": "#ifdef USE_OPENSUBDIV_REGULAR" in v4,
            "default_opensubdiv_free": all(
                re.search(rf"^{flag}\s*\?=\s*0\s*$", makefile, re.MULTILINE)
                for flag in EXPECTED_BUILD_FLAGS),
        },
        "B_runtime_routes": {
            "runtime_flags": runtime_flags,
            "regular_token_semantics": "truthy except empty, 0, false/FALSE, off/OFF",
            "regular_semantics_present": _all_present(regular, [
                'text != "0"', 'text != "false"', 'text != "FALSE"',
                'text != "off"', 'text != "OFF"']),
            "valence4_token_semantics": "exact string 1",
            "valence4_semantics_present":
                'std::string(value) == "1"' in v4_loop,
            "valence5_token_semantics": "exact string 1",
            "valence5_semantics_present":
                v5_loop.count('std::string(value) == "1"') >= 2,
            "v4_v5_conflict_rejected":
                "if (valence4RouteRequested && valence5RouteRequested)" in compute,
            "whole_mesh_early_returns":
                compute.count("return;") >= 2,
        },
        "C_valence3_ancestry": {
            "current_main": "proof-only row provider; no runtime production selector",
            "pr182": "separate stacked V3 production/convergence evidence",
            "runtime_selector_absent_on_current_main":
                "SLIMED_USE_OPENSUBDIV_VALENCE3" not in runtime_flags,
        },
        "D_topology_guards": topology,
        "E_provider_policy": {
            "scheme": "stock OpenSubdiv Sdc::SCHEME_LOOP",
            "vertex_boundary": "VTX_BOUNDARY_EDGE_ONLY",
            "all_three_providers_bind_scheme_boundary": all(
                _all_present(text, ["Sdc::SCHEME_LOOP", "VTX_BOUNDARY_EDGE_ONLY"])
                for text in (v3, v4, v5)),
            "compile_version_pin": {"valence3": 30700, "valence4": None, "valence5": None},
            "only_valence3_pin_present":
                "OPENSUBDIV_VERSION_NUMBER != 30700" in v3
                and "OPENSUBDIV_VERSION_NUMBER" not in v4
                and "OPENSUBDIV_VERSION_NUMBER" not in v5,
            "ambient_version_qualified": False,
        },
        "F_regular_cache": {
            "schema_version": 1,
            "key_fields": [
                "OpenSubdiv version", "Loop scheme", "EDGE_ONLY boundary",
                "adaptive depth 3", "first derivatives", "second derivatives",
                "sizeof(double)", "row tolerance", "vertex/face cardinality",
                "face identity/boundary/ghost/connectivity/one-ring",
                "VWU", "quadrature coefficients", "shape functions",
            ],
            "coordinates_excluded": "coord" not in regular[
                regular.index("RegularCacheKey regular_limit_surface_cache_key"):
                regular.index("struct RefinerDeleter")],
            "mutex_guarded": "std::lock_guard<std::mutex> lock(cache.mutex_)" in regular,
            "invalidations": [
                "Mesh::setup_from_vertices_faces", "Mesh::setup_flat"],
            "only_reviewed_invalidations_present":
                _text("src/mesh/Mesh.cpp").count("regularLimitSurfaceRowCache_.invalidate()") == 1
                and _text("src/mesh/Mesh_setup_flat.cpp").count(
                    "regularLimitSurfaceRowCache_.invalidate()") == 1,
        },
        "G_volume_functionals": {
            "enumerated_factor_names": volume_factor_names,
            "geometry": {
                "regular_mesh": "legacy x-only 1/6",
                "valence4": "legacy x-only 1/6",
                "valence5": "legacy x-only 1/6",
                "cuda_cpu": "legacy x-only 1/6",
                "cuda_device": "legacy x-only 1/6",
            },
            "x_only_anchors_present": all([
                "evaluation.position.get(0, 0) * a_3.get(0, 0)" in geometry,
                "evaluated[0][0] * areaVector[0]" in v4_loop,
                "evaluated[0][0] * areaVector[0]" in v5_loop,
                "rows[0][0] * cross[0]" in cuda_cpu,
                "rows[0][0] * cross[0]" in cuda_device,
            ]),
            "global_volume_energy": "0.5 * param.uVol / param.vol0 * pow(param.vol - param.vol0, 2.0)" if
                "0.5 * param.uVol / param.vol0 * pow(param.vol - param.vol0, 2.0)" in compute else "missing",
            "force": "full-vector analytic derivative with /3",
            "force_anchor_present": "tmp_evol = uVol * (vol - vol0) / 3.0" in compute,
            "one_functional_claim_valid": False,
        },
        "H_source_keyed_seam": {
            "variable_original_source_ids":
                "std::vector<int> originalSourceIds" in source_keyed_hpp,
            "derivative_row_count": 7,
            "mixed_rows": [5, 6],
            "mixed_rows_must_match_exactly":
                "canonicalSample.rows[5].coefficients[source] !=" in source_keyed_cpp
                and "canonicalSample.rows[6].coefficients[source]" in source_keyed_cpp,
            "source_validation_present": _all_present(source_keyed_cpp, [
                "require_unique_source_ids", "duplicate original source id",
                "out-of-range or unmapped", "nonfinite row data"]),
            "guarded_transaction": _all_present(compute, [
                "validate_guarded_source_keyed_production_face_loop(",
                "execute_guarded_source_keyed_production_face_loop("]),
        },
        "I_tolerances_fixtures": {
            "tolerances": copy.deepcopy(EXPECTED_TOLERANCES),
            "source_anchors_present": all([
                "kOpenSubdivRegularRowTolerance = 5.0e-6" in regular,
                "kOpenSubdivRegularResidualScaleFloor = 1.0e-12" in regular,
                "kInvariantTolerance = 1.0e-12" in v3,
                "std::abs(coefficientSum - expectedSum) > 1.0e-12" in v4,
                "kInvariantTolerance = 1.0e-12" in v5,
                "kReviewedProductionTolerance = 1.0e-10" in
                    _text("include/energy_force/Valence5_opensubdiv_face_loop.hpp"),
                "The tolerance envelope is `1.0e-10` absolute" in
                    _text("docs/irregular_serial_omp_tolerance_characterization.md"),
            ]),
            "fixture_sha256": fixtures,
            "expected_values_policy":
                "fixture regressions are locks, not independent scientific oracles",
        },
        "J_output_checkpoint": {
            "energy_csv_fields": [
                "energyCurvature", "energyArea", "energyVolume", "energyThickness",
                "energyTilt", "energyRegularization", "energyHarmonicBond",
                "energyGagScaffolding", "energyIdealizedProteinLattice", "energyTotal",
            ],
            "energy_force_csv_appends": "meanForce",
            "precision": 17,
            "checkpoint_tag": "SLIMED_RESTART_V2",
            "checkpoint_atomic_temp_suffix": ".tmp",
            "checkpoint_atomic_rename": "std::rename(tempFilepath.c_str(), filepath.c_str())" in output,
            "field_order_anchor_present": _all_present(output, [
                "energy.energyCurvature << ','", "energy.energyArea << ','",
                "energy.energyVolume << ','", "energy.energyTotal",
                "outfile << std::setprecision(17)", 'outfile << "SLIMED_RESTART_V2\\n"',
            ]),
            "backend_or_functional_metadata_present": any(token in output for token in [
                "subdivisionBackend", "volumeFunctional", "legacy-x-volume",
                "full-divergence-volume"]),
        },
        "K_deferred_lanes": {
            "adaptive_edge_flip": "proof-only quality predicate",
            "adaptive_header_namespace":
                "namespace slimed::adaptive_edge_flip_proof" in adaptive,
            "adaptive_production_call_count": corpus.count("evaluate_edge_flip_quality(") - 1,
            "adaptive_runtime_flag_present": bool(re.search(
                r'SLIMED_[A-Z0-9_]*(?:EDGE_FLIP|FLIP_EDGE)', corpus)),
            "cuda_policy": "frozen through WP0-WP7",
            "cuda_changed_from_exact_base": bool(_git_output(
                "diff", "--name-only", BASE_SHA, "--", "src/cuda", "include/cuda")),
        },
        "L_fail_closed": {
            "allowed_build_flags": EXPECTED_BUILD_FLAGS,
            "allowed_runtime_flags": EXPECTED_RUNTIME_FLAGS,
            "allowed_volume_factor_names": EXPECTED_VOLUME_FACTOR_NAMES,
            "allowed_volume_functional_tokens": EXPECTED_VOLUME_FUNCTIONAL_TOKENS,
            "observed_volume_functional_tokens": volume_functional_tokens,
        },
    }
    return report


def validate_inventory(report: dict[str, Any], check_adr: bool = True) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    try:
        require(report["schema_version"] == 1, "schema version drift")
        baseline = report["baseline"]
        require(baseline["authoritative_current_main"] == BASE_SHA, "base SHA drift")
        require(baseline["pr182_stack_head"] == PR182_SHA, "PR 182 SHA drift")
        require(baseline["observed_pr182_merge_base"] == PR182_MERGE_BASE,
                "PR 182 ancestry drift")
        require(baseline["pr182_object_available"] and
                baseline["pr182_full_divergence_anchor"],
                "PR 182 evidence object/functional anchor missing")
        require(not baseline["pr182_current_main_production"], "PR 182 ancestry conflated")
        require(not baseline["current_main_valence3_runtime_route"], "false V3 runtime claim")
        require(report["decisions"] == EXPECTED_DECISIONS, "decision authority/status drift")

        a = report["A_build_dependency"]
        require(a["build_flags"] == EXPECTED_BUILD_FLAGS, "unlisted/missing build backend flag")
        require(a["dependency_root"] == "OPENSUBDIV_ROOT", "dependency root drift")
        require(a["dependency_root_required_for_each_flag"], "dependency root guard missing")
        require(a["valence4_compile_macro"] == "USE_OPENSUBDIV_REGULAR", "V4 macro coupling drift")
        require(a["valence4_macro_coupling_present"], "V4 macro coupling anchor missing")
        require(a["default_opensubdiv_free"], "default OpenSubdiv-free build drift")

        b = report["B_runtime_routes"]
        require(b["runtime_flags"] == EXPECTED_RUNTIME_FLAGS, "unlisted/missing runtime backend flag")
        require(b["regular_token_semantics"] ==
                "truthy except empty, 0, false/FALSE, off/OFF",
                "regular runtime token contract drift")
        require(b["valence4_token_semantics"] == "exact string 1" and
                b["valence5_token_semantics"] == "exact string 1",
                "V4/V5 runtime token contract drift")
        require(b["regular_semantics_present"], "regular truthy semantics drift")
        require(b["valence4_semantics_present"] and b["valence5_semantics_present"],
                "V4/V5 exact-1 semantics drift")
        require(b["v4_v5_conflict_rejected"] and b["whole_mesh_early_returns"],
                "extraordinary route conflict/early-return drift")

        c = report["C_valence3_ancestry"]
        require(c["runtime_selector_absent_on_current_main"], "V3 current-main route appeared")

        d = report["D_topology_guards"]
        for name, expected_faces in EXPECTED_FACES.items():
            require(d[name]["oriented_faces"] == expected_faces,
                    f"{name} orientation/count/order drift")
            require(d[name]["source_guard_present"], f"{name} topology source guard drift")
            require(d[name]["source_faces_match_fixture"],
                    f"{name} source/fixture face identity drift")
        require((d["valence3_tetrahedron"]["vertices"],
                 d["valence3_tetrahedron"]["faces"],
                 d["valence3_tetrahedron"]["valence"]) == (4, 4, 3),
                "valence3 topology summary drift")
        require((d["valence4_octahedron"]["vertices"],
                 d["valence4_octahedron"]["faces"],
                 d["valence4_octahedron"]["valence"]) == (6, 8, 4),
                "valence4 topology summary drift")
        require((d["valence5_icosahedron"]["vertices"],
                 d["valence5_icosahedron"]["faces"],
                 d["valence5_icosahedron"]["valence"]) == (12, 20, 5),
                "valence5 topology summary drift")
        require(d["legacy_11_control_predicate"]["admitted_corner_valences"] == [5, 5, 5],
                "legacy predicate classification drift")
        require(d["legacy_11_control_predicate"]["matrix_intended_corner_valences"] == [5, 6, 6],
                "legacy matrix classification drift")
        require(d["legacy_11_control_predicate"]["defect_confirmed"],
                "legacy 11-control defect anchor missing")
        require(d["valence5_icosahedron"]["face_source_mapping_sha256"] ==
                EXPECTED_VALENCE5_FACE_SOURCE_MAPPING_SHA256,
                "valence5 exact face-source mapping drift")

        e = report["E_provider_policy"]
        require(e["all_three_providers_bind_scheme_boundary"], "scheme/boundary drift")
        require(e["compile_version_pin"] == {"valence3": 30700, "valence4": None, "valence5": None},
                "provider version policy drift")
        require(e["only_valence3_pin_present"], "version-pin anchor drift")
        require(not e["ambient_version_qualified"], "ambient version falsely qualified")

        f = report["F_regular_cache"]
        require(f["schema_version"] == 1 and len(f["key_fields"]) == 13,
                "regular cache schema/key drift")
        require(f["coordinates_excluded"], "coordinates entered regular cache key")
        require(f["mutex_guarded"], "regular cache mutex drift")
        require(f["invalidations"] == ["Mesh::setup_from_vertices_faces", "Mesh::setup_flat"],
                "regular cache invalidation list drift")
        require(f["only_reviewed_invalidations_present"], "regular cache invalidation anchor drift")

        g = report["G_volume_functionals"]
        require(g["enumerated_factor_names"] == EXPECTED_VOLUME_FACTOR_NAMES,
                "unlisted/missing volume functional factor")
        require(g["x_only_anchors_present"], "legacy x-only geometry anchor drift")
        require(g["global_volume_energy"] != "missing", "global volume energy anchor missing")
        require(g["force_anchor_present"], "full-vector /3 force anchor missing")
        require(not g["one_functional_claim_valid"], "false one-functional claim")

        h = report["H_source_keyed_seam"]
        require(h["variable_original_source_ids"] and h["source_validation_present"],
                "source-keyed identity validation drift")
        require(h["derivative_row_count"] == 7 and h["mixed_rows"] == [5, 6],
                "seven-row compatibility schema drift")
        require(h["mixed_rows_must_match_exactly"], "mixed-row duplication contract drift")
        require(h["guarded_transaction"], "guarded transaction anchor drift")

        i = report["I_tolerances_fixtures"]
        require(i["tolerances"] == EXPECTED_TOLERANCES, "named tolerance ledger drift")
        require(i["source_anchors_present"], "named tolerance source anchor drift")
        require(i["fixture_sha256"] == EXPECTED_FIXTURE_HASHES, "fixture SHA256 drift")

        j = report["J_output_checkpoint"]
        require(len(j["energy_csv_fields"]) == 10, "energy CSV width drift")
        require(j["energy_csv_fields"][-1] == "energyTotal", "energy CSV field order drift")
        require(j["energy_force_csv_appends"] == "meanForce", "EnergyForce CSV suffix drift")
        require(j["precision"] == 17 and j["checkpoint_tag"] == "SLIMED_RESTART_V2",
                "output precision/checkpoint tag drift")
        require(j["checkpoint_atomic_temp_suffix"] == ".tmp" and j["checkpoint_atomic_rename"],
                "checkpoint atomic replacement drift")
        require(j["field_order_anchor_present"], "output/checkpoint source anchor drift")
        require(not j["backend_or_functional_metadata_present"],
                "false output backend/functional metadata claim")

        k = report["K_deferred_lanes"]
        require(k["adaptive_edge_flip"] == "proof-only quality predicate",
                "edge-flip status drift")
        require(k["adaptive_header_namespace"] and k["adaptive_production_call_count"] == 0,
                "edge-flip production call appeared")
        require(not k["adaptive_runtime_flag_present"], "edge-flip runtime flag appeared")
        require(k["cuda_policy"] == "frozen through WP0-WP7", "CUDA freeze drift")
        require(not k["cuda_changed_from_exact_base"], "CUDA changed in WP0.1")

        l = report["L_fail_closed"]
        require(l["allowed_build_flags"] == EXPECTED_BUILD_FLAGS, "build allowlist drift")
        require(l["allowed_runtime_flags"] == EXPECTED_RUNTIME_FLAGS, "runtime allowlist drift")
        require(l["allowed_volume_factor_names"] == EXPECTED_VOLUME_FACTOR_NAMES,
                "functional allowlist drift")
        require(l["allowed_volume_functional_tokens"] ==
                EXPECTED_VOLUME_FUNCTIONAL_TOKENS,
                "functional-token allowlist drift")
        require(l["observed_volume_functional_tokens"] ==
                EXPECTED_VOLUME_FUNCTIONAL_TOKENS,
                "unlisted volume functional token")
    except (KeyError, TypeError, IndexError) as error:
        errors.append(f"inventory schema incomplete: {error}")

    if check_adr:
        adr_path = ROOT / "docs/adr_unified_loop_backend.md"
        if not adr_path.is_file():
            errors.append("ADR missing")
        else:
            adr = adr_path.read_text(encoding="utf-8")
            for decision, status in EXPECTED_DECISIONS.items():
                if f"| {decision} | {status} |" not in adr:
                    errors.append(f"ADR/inventory disagreement for {decision}")
            for anchor in (BASE_SHA, PR182_SHA, "D3 and D4 remain pending post-WP2.1"):
                if anchor not in adr:
                    errors.append(f"ADR anchor missing: {anchor}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail on inventory drift")
    parser.add_argument("--json", action="store_true", help="emit complete JSON")
    arguments = parser.parse_args()

    report = collect_inventory()
    errors = validate_inventory(report)
    report["status"] = "passed" if not errors else "failed"
    report["errors"] = errors

    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Unified Loop baseline inventory: {report['status']}")
        for error in errors:
            print(f"- {error}")
    return 1 if arguments.check and errors else 0


if __name__ == "__main__":
    sys.exit(main())
