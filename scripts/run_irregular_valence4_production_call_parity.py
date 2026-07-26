#!/usr/bin/env python3
"""Run the proof-only valence-4 production-call boundary package."""

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
FORCE_PROOF = ROOT / "scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh"
EXPERIMENT = ROOT / "experiments/irregular_valence4_production_call_parity.cpp"
FIXTURE = ROOT / "data/fixtures/candidates/closed_valence4_octahedron"


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
        return
    print(f"status: {payload['status']}")
    for key in (
        "reason",
        "fresh_opensubdiv_row_binding_passed",
        "production_entry_rejected_loudly",
    ):
        if key in payload:
            print(f"{key}: {payload[key]}")


def compiler() -> str | None:
    if os.environ.get("CXX"):
        return os.environ["CXX"]
    if platform.system() == "Darwin" and shutil.which("g++-15"):
        return "g++-15"
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


def build_harness(binary: Path, env: dict[str, str]) -> None:
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
        "-DOMP",
        "-fopenmp",
        "-Iinclude",
        "-Iinclude/energy_force",
        "-Iinclude/linalg",
        "-Iinclude/mesh",
        "-Iinclude/model",
        "-Iinclude/parameters",
        *gsl_flags("--cflags"),
        str(EXPERIMENT),
        *(str(source) for source in sources),
        *gsl_flags("--libs"),
        "-o",
        str(binary),
    ]
    result = run(command, env)
    if result.returncode != 0:
        raise RuntimeError(
            "production-call boundary compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def force_report(env: dict[str, str]) -> dict[str, object]:
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
        or not payload.get("proof_passed")
        or not isinstance(proof, dict)
        or not proof.get("passed")
    ):
        raise RuntimeError("valence-4 force proof did not pass")
    return proof


def write_fresh_rows(path: Path, proof: dict[str, object]) -> None:
    binding = proof.get("fresh_opensubdiv_row_binding")
    if not isinstance(binding, dict):
        raise RuntimeError("force proof did not emit fresh row binding")
    if (
        binding.get("generated_in_this_process") is not True
        or binding.get("face_count") != 8
        or binding.get("samples_per_face") != 3
        or binding.get("row_count") != 7
        or binding.get("source_count") != 6
    ):
        raise RuntimeError("fresh row tensor dimensions are not 8x3x7x6")
    faces = binding.get("faces")
    if not isinstance(faces, list) or len(faces) != 8:
        raise RuntimeError("fresh row tensor did not contain eight faces")

    lines = ["8 3 7 6"]
    for face_index, face in enumerate(faces):
        if not isinstance(face, dict) or face.get("face") != face_index:
            raise RuntimeError("fresh rows have invalid face order")
        samples = face.get("samples")
        if not isinstance(samples, list) or len(samples) != 3:
            raise RuntimeError("fresh rows have invalid sample count")
        lines.append(str(face_index))
        for sample_index, sample in enumerate(samples):
            if (
                not isinstance(sample, dict)
                or sample.get("sample") != sample_index
            ):
                raise RuntimeError("fresh rows have invalid sample order")
            rows = sample.get("rows")
            if not isinstance(rows, list) or len(rows) != 7:
                raise RuntimeError("fresh rows have invalid derivative count")
            lines.append(str(sample_index))
            for row in rows:
                if (
                    not isinstance(row, list)
                    or len(row) != 6
                    or not all(
                        isinstance(value, (int, float))
                        and math.isfinite(float(value))
                        for value in row
                    )
                ):
                    raise RuntimeError("fresh row contains invalid coefficients")
                lines.append(" ".join(format(float(value), ".17g") for value in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    if not env.get("OPENSUBDIV_ROOT"):
        emit(
            {
                "status": "skipped",
                "reason": (
                    "OPENSUBDIV_ROOT is not set; the valence-4 production-call "
                    "boundary proof is explicit opt-in only."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        proof = force_report(env)
        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-production-call-parity-"
        ) as temporary:
            temp = Path(temporary)
            rows = temp / "fresh_rows.txt"
            binary = temp / "production_call_parity"
            write_fresh_rows(rows, proof)
            build_harness(binary, env)
            result = run(
                [
                    str(binary),
                    str(FIXTURE / "vertices.csv"),
                    str(FIXTURE / "faces.csv"),
                    str(rows),
                ],
                env,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "production-call boundary proof failed: "
                    + (result.stderr.strip() or result.stdout.strip())
                )
            boundary = json.loads(result.stdout)
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    passed = bool(
        boundary.get("passed")
        and boundary.get("proof_only")
        and boundary.get("not_production_routing")
        and not boundary.get("production_route_enabled")
        and not boundary.get("actual_production_force_path_executed")
        and boundary.get("production_entry_boundary_executed")
        and boundary.get("production_entry_rejected_loudly")
        and boundary.get("production_state_unchanged_after_rejection")
        and boundary.get("guarded_topology_source_representation_used")
        and boundary.get("fresh_opensubdiv_rows_consumed")
        and boundary.get("fresh_row_tensor_shape") == "8x3x7x6"
        and boundary.get("fresh_row_tensor_finite")
        and boundary.get("duplicated_mixed_rows_preserved")
        and boundary.get(
            "independent_canonical_topology_orientation_oracle_passed"
        )
        and boundary.get("independent_fixed_index_6x9_sentinel_oracle_passed")
        and not boundary.get("production_one_rings_populated")
        and boundary.get("source_ids") == list(range(6))
        and boundary.get("orientation_and_one_ring_mutations_rejected")
    )
    payload = {
        "status": "passed" if passed else "failed",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "fresh_opensubdiv_row_binding_passed": passed,
        "production_entry_rejected_loudly": boundary.get(
            "production_entry_rejected_loudly"
        ),
        "force_formula_proof_passed": proof.get("passed"),
        "boundary": boundary,
    }
    if not passed:
        payload["reason"] = "production-call boundary evidence did not pass"
    emit(payload, args.json)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
