#!/usr/bin/env python3
"""Compare OpenSubdiv child-domain rows with the positive-depth composition."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_REPORTER = ROOT / "experiments/irregular_valence5_fixture_parity.cpp"
PROBE = ROOT / "scripts/run_opensubdiv_probe.sh"
REVIEWED_ROW_TOLERANCE = 5.0e-6
ROW_SHAPE = [20, 6, 3, 7, 12]
ROW_COUNT = math.prod(ROW_SHAPE)
ALL_ORIENTATION_ROW_SHAPE = [20, 6, 6, 3, 7, 12]
ALL_ORIENTATION_ROW_COUNT = math.prod(ALL_ORIENTATION_ROW_SHAPE)
ORIENTATION_PERMUTATIONS = [
    [0, 1, 2],
    [0, 2, 1],
    [1, 0, 2],
    [1, 2, 0],
    [2, 0, 1],
    [2, 1, 0],
]
EXPECTED_DOMAINS = [
    {
        "name": "depth1_M1_C_corner",
        "depth": 1,
        "child": 1,
        "offset": [0.0, 0.5],
        "jacobian": [0.5, 0.0, 0.0, 0.5],
    },
    {
        "name": "depth1_M2_center",
        "depth": 1,
        "child": 2,
        "offset": [0.5, 0.0],
        "jacobian": [0.0, -0.5, 0.5, 0.5],
    },
    {
        "name": "depth1_M3_B_corner",
        "depth": 1,
        "child": 3,
        "offset": [0.5, 0.0],
        "jacobian": [0.5, 0.0, 0.0, 0.5],
    },
    {
        "name": "depth2_M1_C_corner",
        "depth": 2,
        "child": 1,
        "offset": [0.0, 0.25],
        "jacobian": [0.25, 0.0, 0.0, 0.25],
    },
    {
        "name": "depth2_M2_center",
        "depth": 2,
        "child": 2,
        "offset": [0.25, 0.0],
        "jacobian": [0.0, -0.25, 0.25, 0.25],
    },
    {
        "name": "depth2_M3_B_corner",
        "depth": 2,
        "child": 3,
        "offset": [0.25, 0.0],
        "jacobian": [0.25, 0.0, 0.0, 0.25],
    },
]


def run(
    command: list[str], env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def compiler() -> str | None:
    if os.environ.get("CXX"):
        return os.environ["CXX"]
    if platform.system() == "Darwin" and shutil.which("g++-15"):
        return "g++-15"
    return shutil.which("g++") or shutil.which("c++")


def gsl_flags(option: str) -> list[str]:
    result = run(["gsl-config", option], os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gsl-config failed")
    return shlex.split(result.stdout)


def build(binary: Path, env: dict[str, str]) -> None:
    cxx = compiler()
    if not cxx or not shutil.which("gsl-config"):
        raise RuntimeError("a C++ compiler and gsl-config are required")
    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    command = [
        cxx,
        "-std=c++17",
        "-Iinclude",
        "-Iinclude/energy_force",
        "-Iinclude/linalg",
        "-Iinclude/mesh",
        "-Iinclude/model",
        "-Iinclude/parameters",
        *gsl_flags("--cflags"),
        str(PRODUCTION_REPORTER),
        *(str(source) for source in sources),
        *gsl_flags("--libs"),
        "-o",
        str(binary),
    ]
    result = run(command, env)
    if result.returncode != 0:
        raise RuntimeError(
            "production reporter compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def parse_json(
    result: subprocess.CompletedProcess[str], label: str
) -> dict[str, object]:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit {result.returncode}: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} did not emit JSON: {error}") from error


def finite_values(values: object, count: int, label: str) -> list[float]:
    if (
        not isinstance(values, list)
        or len(values) != count
        or not all(
            isinstance(value, (int, float)) and math.isfinite(float(value))
            for value in values
        )
    ):
        raise RuntimeError(f"{label} must contain {count} finite values")
    return [float(value) for value in values]


def compare(
    production: dict[str, object],
    opensubdiv: dict[str, object],
) -> dict[str, object]:
    errors: list[str] = []
    if production.get("positive_depth_composed_row_shape") != ROW_SHAPE:
        errors.append("production composed-row shape drift")
    if (
        opensubdiv.get("row_shape_all_orientations")
        != ALL_ORIENTATION_ROW_SHAPE
    ):
        errors.append("OpenSubdiv all-orientation row shape drift")
    if opensubdiv.get("orientation_permutations") != ORIENTATION_PERMUTATIONS:
        errors.append("OpenSubdiv orientation permutation plan drift")
    if opensubdiv.get("domains") != EXPECTED_DOMAINS:
        errors.append("reviewed child-domain affine plan drift")
    if opensubdiv.get("passed") is not True:
        errors.append("OpenSubdiv child-domain report did not pass")
    production_mask = finite_values(
        production.get("positive_depth_extraordinary_vertex_mask"),
        11,
        "production extraordinary vertex mask",
    )
    expected_production_mask = [
        0.075,
        0.075,
        0.625,
        0.075,
        0.0,
        0.075,
        0.075,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    if production_mask != expected_production_mask:
        errors.append("production valence-5 extraordinary vertex mask drift")
    opensubdiv_edge_weight = opensubdiv.get(
        "opensubdiv_valence5_vertex_edge_weight"
    )
    opensubdiv_center_weight = opensubdiv.get(
        "opensubdiv_valence5_vertex_center_weight"
    )
    if (
        not isinstance(opensubdiv_edge_weight, (int, float))
        or not math.isfinite(float(opensubdiv_edge_weight))
        or not isinstance(opensubdiv_center_weight, (int, float))
        or not math.isfinite(float(opensubdiv_center_weight))
    ):
        raise RuntimeError("OpenSubdiv valence-5 vertex mask is not finite")
    mask_policy_mismatch = (
        abs(float(opensubdiv_edge_weight) - 0.075)
        > REVIEWED_ROW_TOLERANCE
        and abs(float(opensubdiv_center_weight) - 0.625)
        > REVIEWED_ROW_TOLERANCE
    )
    if not mask_policy_mismatch:
        errors.append("expected extraordinary vertex mask mismatch vanished")

    reference = finite_values(
        production.get("positive_depth_composed_rows"),
        ROW_COUNT,
        "production composed rows",
    )
    all_orientation_rows = finite_values(
        opensubdiv.get("composed_rows_all_orientations"),
        ALL_ORIENTATION_ROW_COUNT,
        "OpenSubdiv all-orientation composed rows",
    )
    production_faces = production.get("adjacent_face_source_ids")
    ptex_faces = opensubdiv.get("oriented_fixture_faces")
    if (
        not isinstance(production_faces, list)
        or len(production_faces) != 60
        or not isinstance(ptex_faces, list)
        or len(ptex_faces) != 60
    ):
        raise RuntimeError("production/Ptex oriented face identity shape drift")
    orientation_block = math.prod(ROW_SHAPE[1:])
    face_block = 6 * orientation_block
    actual: list[float] = []
    selected_orientations: list[int] = []
    for face in range(20):
        local_ids = [int(value) for value in production_faces[3 * face:3 * face + 3]]
        ptex_ids = [int(value) for value in ptex_faces[3 * face:3 * face + 3]]
        if sorted(local_ids) != sorted(ptex_ids) or len(set(local_ids)) != 3:
            raise RuntimeError(f"face {face} production/Ptex identity mismatch")
        permutation = [local_ids.index(source_id) for source_id in ptex_ids]
        try:
            orientation = ORIENTATION_PERMUTATIONS.index(permutation)
        except ValueError as error:
            raise RuntimeError(
                f"face {face} has unsupported orientation permutation"
            ) from error
        selected_orientations.append(orientation)
        start = face * face_block + orientation * orientation_block
        actual.extend(all_orientation_rows[start:start + orientation_block])
    if len(actual) != ROW_COUNT:
        raise RuntimeError("selected OpenSubdiv composed-row shape drift")
    value_row_domain_residuals = []
    for production_domain in range(6):
        row = []
        for candidate_domain in range(6):
            row.append(
                max(
                    abs(
                        reference[
                            (((face_index * 6 + production_domain) * 3
                              + sample_index) * 7)
                            * 12
                            + source_index
                        ]
                        - actual[
                            (((face_index * 6 + candidate_domain) * 3
                              + sample_index) * 7)
                            * 12
                            + source_index
                        ]
                    )
                    for face_index in range(20)
                    for sample_index in range(3)
                    for source_index in range(12)
                )
            )
        value_row_domain_residuals.append(row)
    deltas = [abs(left - right) for left, right in zip(reference, actual)]
    max_index = max(range(len(deltas)), key=deltas.__getitem__)
    remainder = max_index
    source = remainder % ROW_SHAPE[4]
    remainder //= ROW_SHAPE[4]
    row = remainder % ROW_SHAPE[3]
    remainder //= ROW_SHAPE[3]
    sample = remainder % ROW_SHAPE[2]
    remainder //= ROW_SHAPE[2]
    domain = remainder % ROW_SHAPE[1]
    face = remainder // ROW_SHAPE[1]
    max_by_row = []
    for row_index in range(ROW_SHAPE[3]):
        max_by_row.append(
            max(
                deltas[
                    (((face_index * 6 + domain_index) * 3 + sample_index)
                     * 7 + row_index)
                    * 12
                    + source_index
                ]
                for face_index in range(20)
                for domain_index in range(6)
                for sample_index in range(3)
                for source_index in range(12)
            )
        )
    max_by_domain = []
    for domain_index in range(ROW_SHAPE[1]):
        max_by_domain.append(
            max(
                deltas[
                    (((face_index * 6 + domain_index) * 3 + sample_index)
                     * 7 + row_index)
                    * 12
                    + source_index
                ]
                for face_index in range(20)
                for sample_index in range(3)
                for row_index in range(7)
                for source_index in range(12)
            )
        )
    max_delta = deltas[max_index]
    row_start = max_index - source
    max_location_reference_row = reference[row_start:row_start + 12]
    max_location_opensubdiv_row = actual[row_start:row_start + 12]
    parity = max_delta <= REVIEWED_ROW_TOLERANCE
    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "valence5_opensubdiv_integration_composition",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_scatter_executed": False,
        "row_shape": ROW_SHAPE,
        "row_component_count": ROW_COUNT,
        "domain_count": 6,
        "positive_depth": 2,
        "child_order": ["M1", "M2", "M3", "M1", "M2", "M3"],
        "affine_domain_plan_matches_reviewed": (
            opensubdiv.get("domains") == EXPECTED_DOMAINS
        ),
        "face_orientation_bound_by_source_identity": True,
        "selected_orientation_indices": selected_orientations,
        "value_row_domain_residual_matrix": value_row_domain_residuals,
        "derivative_chain_rule_applied": True,
        "composed_row_parity_passed": parity,
        "max_abs_row_difference": max_delta,
        "max_abs_row_difference_location": {
            "face": face,
            "domain": domain,
            "sample": sample,
            "row": row,
            "source_id": source,
        },
        "max_difference_reference_row": max_location_reference_row,
        "max_difference_opensubdiv_row": max_location_opensubdiv_row,
        "max_abs_row_difference_by_row": max_by_row,
        "max_abs_row_difference_by_domain": max_by_domain,
        "reviewed_absolute_tolerance": REVIEWED_ROW_TOLERANCE,
        "production_valence5_vertex_edge_weight": 0.075,
        "production_valence5_vertex_center_weight": 0.625,
        "opensubdiv_valence5_vertex_edge_weight": float(
            opensubdiv_edge_weight
        ),
        "opensubdiv_valence5_vertex_center_weight": float(
            opensubdiv_center_weight
        ),
        "extraordinary_vertex_mask_policy_mismatch": mask_policy_mismatch,
        "mask_policy_causal_sufficiency_proven": False,
        "observed_diagnostic_clues": (
            [
                "SLIMED and OpenSubdiv use different valence-5 "
                "extraordinary smooth-vertex masks"
            ]
            if mask_policy_mismatch
            else []
        ),
        "route_blockers": (
            []
            if parity
            else [
                "composed OpenSubdiv rows do not reproduce the "
                "positive-depth SLIMED rows"
            ]
        ),
        "remaining_boundary": (
            "composed OpenSubdiv fBend/fArea/fVolume parity"
            if parity
            else (
                "counterfactual valence-5 extraordinary mask attribution "
                "diagnostic"
                if mask_policy_mismatch
                else "composed row residual attribution diagnostic"
            )
        ),
        "errors": errors,
    }


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    for key in (
        "composed_row_parity_passed",
        "max_abs_row_difference",
        "remaining_boundary",
        "reason",
    ):
        if key in payload:
            print(f"{key}: {payload[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    if not env.get("OPENSUBDIV_ROOT"):
        payload = {
            "status": "skipped",
            "reason": "OPENSUBDIV_ROOT is not set; proof is opt-in only.",
        }
        emit(payload, args.json)
        return 2 if args.require_opensubdiv else 0

    try:
        with tempfile.TemporaryDirectory(prefix="slimed-val5-compose-") as tmp:
            binary = Path(tmp) / "production"
            build(binary, env)
            production = parse_json(
                run([str(binary)], env),
                "positive-depth production reporter",
            )
            wrapper = parse_json(
                run(
                    [
                        str(PROBE),
                        "--json",
                        "--require-opensubdiv",
                        "--valence5-integration-composition-report",
                    ],
                    env,
                ),
                "OpenSubdiv integration-composition report",
            )
            output = wrapper.get("prototype_output")
            if not isinstance(output, list) or len(output) != 1:
                raise RuntimeError("OpenSubdiv probe omitted its report")
            opensubdiv = json.loads(output[0]).get(
                "valence5_integration_composition"
            )
            if not isinstance(opensubdiv, dict):
                raise RuntimeError(
                    "OpenSubdiv probe omitted integration composition"
                )
            payload = compare(production, opensubdiv)
    except (RuntimeError, json.JSONDecodeError, OSError) as error:
        payload = {"status": "failed", "reason": str(error)}
        emit(payload, args.json)
        return 1

    emit(payload, args.json)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
