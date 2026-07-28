#!/usr/bin/env python3
"""Validate the guarded production valence-4 OpenSubdiv row provider."""

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
FIXTURE = ROOT / "data/fixtures/candidates/closed_valence4_octahedron"
EXPERIMENT = (
    ROOT / "experiments/irregular_valence4_opensubdiv_row_provider.cpp"
)
FORCE_PROOF = (
    ROOT / "scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh"
)


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
    result = subprocess.run(
        ["gsl-config", option],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gsl-config failed")
    return shlex.split(result.stdout)


def library_directory(prefix: Path) -> Path:
    for candidate in (prefix / "lib", prefix / "lib64"):
        if any(candidate.glob("libosdCPU.*")):
            return candidate
    raise RuntimeError("OpenSubdiv osdCPU library is not discoverable")


def platform_include_flags() -> list[str]:
    if platform.system() != "Darwin" or not shutil.which("brew"):
        return []
    result = subprocess.run(
        ["brew", "--prefix", "libomp"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return []
    return [f"-I{Path(result.stdout.strip()) / 'include'}"]


def build_harness(
    binary: Path, prefix: Path, env: dict[str, str]
) -> None:
    cxx = compiler()
    if not cxx or not shutil.which("gsl-config"):
        raise RuntimeError("a C++ compiler and gsl-config are required")
    if not (
        prefix
        / "include/opensubdiv/far/topologyDescriptor.h"
    ).is_file():
        raise RuntimeError("OpenSubdiv headers are not discoverable")
    libdir = library_directory(prefix)
    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    command = [
        cxx,
        "-std=c++17",
        "-DUSE_OPENSUBDIV_REGULAR",
        "-Iinclude",
        "-Iinclude/energy_force",
        "-Iinclude/linalg",
        "-Iinclude/mesh",
        "-Iinclude/model",
        "-Iinclude/parameters",
        f"-I{prefix / 'include'}",
        *platform_include_flags(),
        *shlex.split(env.get("OPENSUBDIV_CXXFLAGS", "")),
        *gsl_flags("--cflags"),
        str(EXPERIMENT),
        *(str(source) for source in sources),
        *gsl_flags("--libs"),
        f"-L{libdir}",
        f"-Wl,-rpath,{libdir}",
        *shlex.split(env.get("OPENSUBDIV_LDFLAGS", "")),
        "-losdCPU",
        "-o",
        str(binary),
    ]
    result = run(command, env)
    if result.returncode != 0:
        raise RuntimeError(
            "valence-4 row-provider compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def force_proof(env: dict[str, str]) -> dict[str, object]:
    result = run(
        [str(FORCE_PROOF), "--json", "--require-opensubdiv"],
        env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "valence-4 force proof failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    payload = json.loads(result.stdout)
    proof = payload.get("proof")
    if (
        payload.get("status") != "passed"
        or not isinstance(proof, dict)
        or not proof.get("passed")
    ):
        raise RuntimeError("valence-4 force proof did not pass")
    return proof


def compare_rows(
    provider: dict[str, object], proof: dict[str, object]
) -> tuple[float, bool]:
    binding = proof.get("fresh_opensubdiv_row_binding")
    provider_faces = provider.get("rows")
    if not isinstance(binding, dict):
        raise RuntimeError("force proof omitted fresh row binding")
    proof_faces = binding.get("faces")
    if (
        not isinstance(provider_faces, list)
        or not isinstance(proof_faces, list)
        or len(provider_faces) != 8
        or len(proof_faces) != 8
    ):
        raise RuntimeError("row providers did not emit eight faces")

    maximum = 0.0
    identities_match = True
    for face_index, (actual_face, expected_face) in enumerate(
        zip(provider_faces, proof_faces)
    ):
        if not isinstance(actual_face, dict) or not isinstance(
            expected_face, dict
        ):
            raise RuntimeError("row provider face is malformed")
        identities_match = identities_match and (
            actual_face.get("face") == face_index
            and expected_face.get("face") == face_index
        )
        actual_samples = actual_face.get("samples")
        expected_samples = expected_face.get("samples")
        if (
            not isinstance(actual_samples, list)
            or not isinstance(expected_samples, list)
            or len(actual_samples) != 3
            or len(expected_samples) != 3
        ):
            raise RuntimeError("row provider sample plan is malformed")
        for sample_index, (actual_sample, expected_sample) in enumerate(
            zip(actual_samples, expected_samples)
        ):
            if not isinstance(actual_sample, dict) or not isinstance(
                expected_sample, dict
            ):
                raise RuntimeError("row provider sample is malformed")
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
                raise RuntimeError("row provider derivative plan is malformed")
            for actual_row, expected_row in zip(
                actual_rows, expected_rows
            ):
                if (
                    not isinstance(actual_row, list)
                    or not isinstance(expected_row, list)
                    or len(actual_row) != 6
                    or len(expected_row) != 6
                ):
                    raise RuntimeError("row provider source plan is malformed")
                for actual, expected in zip(actual_row, expected_row):
                    if not isinstance(actual, (int, float)) or not isinstance(
                        expected, (int, float)
                    ):
                        raise RuntimeError("row provider coefficient is invalid")
                    if not math.isfinite(float(actual)) or not math.isfinite(
                        float(expected)
                    ):
                        raise RuntimeError("row provider coefficient is nonfinite")
                    maximum = max(
                        maximum, abs(float(actual) - float(expected))
                    )
    return maximum, identities_match


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    root = env.get("OPENSUBDIV_ROOT")
    if not root:
        emit(
            {
                "status": "skipped",
                "reason": (
                    "OPENSUBDIV_ROOT is not set; the production valence-4 "
                    "row provider is explicit opt-in only."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        proof = force_proof(env)
        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-row-provider-"
        ) as temporary:
            binary = Path(temporary) / "row_provider"
            build_harness(binary, Path(root), env)
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
                    "valence-4 row provider failed: "
                    + (result.stderr.strip() or result.stdout.strip())
                )
            provider = json.loads(result.stdout)
        max_difference, identity_match = compare_rows(provider, proof)
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    passed = bool(
        provider.get("passed")
        and provider.get("provider_passed")
        and provider.get("default_off_request_rejected")
        and provider.get("opensubdiv_compiled")
        and provider.get("explicit_request_accepted")
        and provider.get("topology_source_mapping_validated")
        and provider.get("ptex_face_identity_validated")
        and provider.get("exact_sample_plan_validated")
        and provider.get("exact_source_coverage_validated")
        and provider.get("double_precision_rows_generated")
        and provider.get("constant_field_invariants_validated")
        and provider.get("mixed_derivative_rows_duplicated")
        and provider.get("production_one_rings_empty")
        and provider.get("not_production_routing")
        and not provider.get("production_route_enabled")
        and not provider.get("actual_production_force_path_executed")
        and not provider.get("production_face_loop_executed")
        and identity_match
        and max_difference <= 5.0e-6
    )
    payload = {
        "status": "passed" if passed else "failed",
        "provider_passed": passed,
        "exact_tensor_shape": "8x3x7x6",
        "sample_and_face_identity_match": identity_match,
        "provider_row_precision": "double",
        "comparison_reference": "reviewed float force-proof rows",
        "max_abs_difference_vs_reviewed_float_force_proof": max_difference,
        "comparison_tolerance": 5.0e-6,
        "constant_field_invariant_tolerance": 1.0e-12,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_one_rings_populated": False,
        "default_dependency_changed": False,
        "next_boundary": (
            "separate reviewer-gated real production face-loop caller using "
            "this provider; route activation remains unapproved"
        ),
    }
    emit(payload, args.json)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
