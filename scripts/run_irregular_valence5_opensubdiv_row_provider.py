#!/usr/bin/env python3
"""Validate the guarded stock valence-5 OpenSubdiv Phase 1 row provider."""

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
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/closed_valence5"
EXPERIMENT = ROOT / "experiments/irregular_valence5_opensubdiv_row_provider.cpp"
PROBE = ROOT / "scripts/run_opensubdiv_probe.sh"
REFERENCE_TOLERANCE = 5.0e-6


def run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        if "reason" in payload:
            print(f"reason: {payload['reason']}")


def compiler() -> str | None:
    if os.environ.get("CXX"):
        return os.environ["CXX"]
    if platform.system() == "Darwin":
        return shutil.which("clang++")
    return shutil.which("g++") or shutil.which("c++")


def gsl_flags(option: str) -> list[str]:
    result = run(["gsl-config", option], os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gsl-config failed")
    return shlex.split(result.stdout)


def library_directory(prefix: Path) -> Path:
    for candidate in (prefix / "lib", prefix / "lib64"):
        if any(candidate.glob("libosdCPU.*")):
            return candidate
    raise RuntimeError("OpenSubdiv osdCPU library is not discoverable")


def build_harness(
    binary: Path,
    env: dict[str, str],
    prefix: Path | None,
) -> None:
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
    ]
    if prefix is not None:
        if not (prefix / "include/opensubdiv/far/topologyDescriptor.h").is_file():
            raise RuntimeError("OpenSubdiv headers are not discoverable")
        libdir = library_directory(prefix)
        command.extend((
            "-DUSE_OPENSUBDIV_VALENCE5",
            f"-I{prefix / 'include'}",
            *shlex.split(env.get("OPENSUBDIV_CXXFLAGS", "")),
        ))
    command.extend((
        str(EXPERIMENT),
        *(str(source) for source in sources),
        *gsl_flags("--libs"),
    ))
    if prefix is not None:
        command.extend((
            f"-L{libdir}",
            f"-Wl,-rpath,{libdir}",
            *shlex.split(env.get("OPENSUBDIV_LDFLAGS", "")),
            "-losdCPU",
        ))
    command.extend(("-o", str(binary)))
    result = run(command, env)
    if result.returncode != 0:
        mode = "enabled" if prefix is not None else "default"
        raise RuntimeError(
            f"valence-5 Phase 1 {mode} compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def run_harness(binary: Path, env: dict[str, str]) -> tuple[str, dict[str, object]]:
    result = run(
        [
            str(binary),
            str(FIXTURE / "vertices.csv"),
            str(FIXTURE / "faces.csv"),
        ],
        env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "valence-5 Phase 1 provider harness failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"provider harness did not emit JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError("provider harness must emit a JSON object")
    return result.stdout, payload


def source_order_proof(env: dict[str, str]) -> dict[str, object]:
    result = run(
        [
            str(PROBE),
            "--json",
            "--require-opensubdiv",
            "--valence5-source-order-transpose-report",
        ],
        env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "accepted valence-5 source-order proof failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    wrapper = json.loads(result.stdout)
    output = wrapper.get("prototype_output")
    if wrapper.get("status") != "passed" or not isinstance(output, list) or len(output) != 1:
        raise RuntimeError("accepted source-order proof wrapper did not pass")
    proof = json.loads(output[0]).get("valence5_source_order_transpose")
    if (
        not isinstance(proof, dict)
        or proof.get("passed") is not True
        or proof.get("proof_only") is not True
        or proof.get("production_route_enabled") is not False
        or proof.get("production_force_path_executed") is not False
    ):
        raise RuntimeError("accepted source-order proof boundary drift")
    return proof


def finite_row(value: object, count: int, label: str) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != count
        or not all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in value
        )
    ):
        raise RuntimeError(f"{label} must contain {count} finite numbers")
    return [float(item) for item in value]


def compare_rows(
    provider: dict[str, object],
    proof: dict[str, object],
) -> tuple[float, bool, bool]:
    provider_faces = provider.get("rows")
    proof_faces = proof.get("faces")
    if (
        not isinstance(provider_faces, list)
        or not isinstance(proof_faces, list)
        or len(provider_faces) != 20
        or len(proof_faces) != 20
    ):
        raise RuntimeError("provider and proof must contain twenty faces")

    maximum = 0.0
    identities_match = True
    source_mappings_match = True
    for face_index, (actual_face, expected_face) in enumerate(
        zip(provider_faces, proof_faces)
    ):
        if not isinstance(actual_face, dict) or not isinstance(expected_face, dict):
            raise RuntimeError("provider face is malformed")
        source_ids = actual_face.get("source_ids")
        expected_sources = expected_face.get("source_coverage_union")
        if (
            not isinstance(source_ids, list)
            or len(source_ids) != 9
            or not all(isinstance(value, int) and not isinstance(value, bool) for value in source_ids)
        ):
            raise RuntimeError("provider face must contain nine integer source IDs")
        source_mappings_match = source_mappings_match and source_ids == expected_sources
        identities_match = identities_match and (
            actual_face.get("face") == face_index
            and expected_face.get("fixture_face_index") == face_index
            and actual_face.get("oriented_face_vertices")
            == expected_face.get("oriented_fixture_vertex_ids")
        )
        actual_samples = actual_face.get("samples")
        expected_samples = expected_face.get("samples")
        if (
            not isinstance(actual_samples, list)
            or not isinstance(expected_samples, list)
            or len(actual_samples) != 3
            or len(expected_samples) != 3
        ):
            raise RuntimeError("provider sample plan is malformed")
        for sample_index, (actual_sample, expected_sample) in enumerate(
            zip(actual_samples, expected_samples)
        ):
            if not isinstance(actual_sample, dict) or not isinstance(expected_sample, dict):
                raise RuntimeError("provider sample is malformed")
            identities_match = identities_match and (
                actual_sample.get("sample") == sample_index
                and expected_sample.get("sample") == sample_index
            )
            actual_rows = actual_sample.get("rows")
            expected_rows = expected_sample.get("rows")
            if (
                not isinstance(actual_rows, list)
                or not isinstance(expected_rows, list)
                or len(actual_rows) != 7
                or len(expected_rows) != 7
            ):
                raise RuntimeError("provider derivative plan is malformed")
            for row_index, (actual_row, expected_row) in enumerate(
                zip(actual_rows, expected_rows)
            ):
                actual = finite_row(actual_row, 9, "provider derivative row")
                expected = finite_row(expected_row, 12, "proof derivative row")
                dense = [0.0] * 12
                for source_id, coefficient in zip(source_ids, actual):
                    if source_id < 0 or source_id >= 12:
                        raise RuntimeError("provider source ID escaped the fixture")
                    dense[source_id] = coefficient
                maximum = max(
                    maximum,
                    max(abs(left - right) for left, right in zip(dense, expected)),
                )
                if row_index == 6 and actual != finite_row(
                    actual_rows[5], 9, "provider mixed derivative row"
                ):
                    raise RuntimeError("provider mixed derivative rows differ")
    return maximum, identities_match, source_mappings_match


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    root = env.get("OPENSUBDIV_ROOT")

    try:
        with tempfile.TemporaryDirectory(prefix="slimed-valence5-phase1-") as temporary:
            temporary_path = Path(temporary)
            default_binary = temporary_path / "provider_default"
            build_harness(default_binary, env, None)
            _, default = run_harness(default_binary, env)
            if (
                default.get("passed") is not True
                or default.get("dependency_disabled_contract_passed") is not True
                or default.get("opensubdiv_compiled") is not False
                or default.get("production_route_enabled") is not False
            ):
                raise RuntimeError("default dependency-disabled provider contract drift")

            if not root:
                payload = {
                    "status": "skipped",
                    "reason": "OPENSUBDIV_ROOT is not set; Phase 1 provider proof is opt-in only.",
                    "default_dependency_disabled_contract_passed": True,
                    "production_route_enabled": False,
                }
                emit(payload, args.json)
                return 2 if args.require_opensubdiv else 0

            prefix = Path(root)
            enabled_binary = temporary_path / "provider_enabled"
            build_harness(enabled_binary, env, prefix)
            first_output, provider = run_harness(enabled_binary, env)
            second_output, repeated = run_harness(enabled_binary, env)
            proof = source_order_proof(env)
            maximum, identities_match, mappings_match = compare_rows(provider, proof)
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    required_flags = (
        "passed",
        "provider_passed",
        "default_off_request_rejected",
        "opensubdiv_compiled",
        "explicit_request_accepted",
        "exact_topology_identity_validated",
        "topology_source_mapping_validated",
        "ptex_face_identity_validated",
        "exact_sample_plan_validated",
        "exact_nine_source_coverage_validated",
        "double_precision_rows_generated",
        "constant_field_invariants_validated",
        "mixed_derivative_rows_duplicated",
        "invalid_topology_rejected",
        "production_one_rings_unchanged",
        "not_production_routing",
    )
    flags_passed = all(provider.get(key) is True for key in required_flags)
    negative_flags_passed = all(
        provider.get(key) is False
        for key in (
            "production_route_enabled",
            "actual_production_force_path_executed",
            "production_face_loop_executed",
            "production_mesh_mutated",
        )
    )
    deterministic = first_output == second_output and provider == repeated
    passed = bool(
        flags_passed
        and negative_flags_passed
        and deterministic
        and identities_match
        and mappings_match
        and maximum <= REFERENCE_TOLERANCE
    )
    payload = {
        "status": "passed" if passed else "failed",
        "proof_kind": "guarded_stock_valence5_phase1_row_provider",
        "provider_passed": passed,
        "exact_tensor_shape": "20x3x7x9_source_keyed",
        "stock_whole_ptex_rows": True,
        "provider_row_precision": "double",
        "comparison_reference": "accepted_float_source_order_proof",
        "max_abs_difference_vs_accepted_float_proof": maximum,
        "comparison_tolerance": REFERENCE_TOLERANCE,
        "sample_face_and_source_identity_match": identities_match and mappings_match,
        "byte_deterministic_repeated_execution": deterministic,
        "default_dependency_disabled_contract_passed": True,
        "invalid_topology_rejected": provider.get("invalid_topology_rejected") is True,
        "production_one_rings_unchanged": provider.get("production_one_rings_unchanged") is True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_mesh_mutated": False,
        "default_dependency_changed": False,
        "implementation_phase": 1,
        "phase2_integration_authorized": False,
        "next_boundary": (
            "dedicated reviewer and user approval of this provider before any "
            "guarded face-loop integration or scientific re-baselining"
        ),
    }
    emit(payload, args.json)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
