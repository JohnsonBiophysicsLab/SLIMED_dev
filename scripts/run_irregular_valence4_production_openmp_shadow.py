#!/usr/bin/env python3
"""Run the proof-only valence-4 production-topology/OpenMP shadow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FORCE_PROOF = (
    ROOT / "scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh"
)
EXPERIMENT = (
    ROOT / "experiments/irregular_valence4_production_openmp_shadow.cpp"
)
FIXTURE = ROOT / "data/fixtures/candidates/closed_valence4_octahedron"


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
        return
    print(f"status: {payload['status']}")
    for key in (
        "reason",
        "production_topology_identity_passed",
        "actual_openmp_runtime_parity_passed",
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


def write_contributions(path: Path, proof: dict[str, object]) -> None:
    faces = proof.get("face_force_contributions")
    if not isinstance(faces, list) or len(faces) != 8:
        raise RuntimeError(
            "force proof did not expose eight face-force contributions"
        )
    lines = [str(len(faces))]
    for expected_face, face in enumerate(faces):
        if not isinstance(face, dict) or face.get("face") != expected_face:
            raise RuntimeError("face-force contributions are not ordered 0..7")
        sources = face.get("source_forces")
        if not isinstance(sources, list) or len(sources) != 6:
            raise RuntimeError(
                f"face {expected_face} lacks six source-force rows"
            )
        values: list[str] = [str(expected_face)]
        for force_kind in ("fBend", "fArea", "fVolume"):
            for expected_source, source in enumerate(sources):
                if (
                    not isinstance(source, dict)
                    or source.get("source_id") != expected_source
                ):
                    raise RuntimeError(
                        f"face {expected_face} source order is not 0..5"
                    )
                vector = source.get(force_kind)
                if not isinstance(vector, list) or len(vector) != 3:
                    raise RuntimeError(
                        f"face {expected_face} {force_kind} is incomplete"
                    )
                values.extend(format(float(value), ".17g") for value in vector)
        lines.append(" ".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_harness(binary: Path, env: dict[str, str]) -> None:
    cxx = compiler()
    if not cxx:
        raise RuntimeError("no C++ compiler was found")
    if not shutil.which("gsl-config"):
        raise RuntimeError("gsl-config is required to build the shadow harness")

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
            "production-topology/OpenMP shadow compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


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
                    "OPENSUBDIV_ROOT is not set; the valence-4 "
                    "production/OpenMP shadow is explicit opt-in only."
                ),
                "next_step": (
                    "Set OPENSUBDIV_ROOT to an OpenSubdiv install prefix "
                    "and rerun."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        force_result = run(
            [str(FORCE_PROOF), "--json", "--require-opensubdiv"], env
        )
        if force_result.returncode != 0:
            raise RuntimeError(
                "prerequisite force proof failed: "
                + (force_result.stderr.strip() or force_result.stdout.strip())
            )
        force_payload = json.loads(force_result.stdout)
        proof = force_payload.get("proof")
        if (
            force_payload.get("status") != "passed"
            or not force_payload.get("proof_passed")
            or not isinstance(proof, dict)
            or not proof.get("passed")
        ):
            raise RuntimeError("prerequisite force proof did not pass")

        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-production-openmp-shadow-"
        ) as temporary:
            temp = Path(temporary)
            contributions = temp / "face_force_contributions.txt"
            binary = temp / "irregular_valence4_production_openmp_shadow"
            write_contributions(contributions, proof)
            build_harness(binary, env)
            run_env = env.copy()
            run_env["OMP_DYNAMIC"] = "FALSE"
            result = run(
                [
                    str(binary),
                    str(FIXTURE / "vertices.csv"),
                    str(FIXTURE / "faces.csv"),
                    str(contributions),
                ],
                run_env,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "production-topology/OpenMP shadow failed: "
                    + (result.stderr.strip() or result.stdout.strip())
                )
            shadow = json.loads(result.stdout)
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    passed = bool(
        shadow.get("passed")
        and shadow.get("proof_only")
        and shadow.get("production_call_shadow")
        and shadow.get("not_production_routing")
        and not shadow.get("production_route_enabled")
        and not shadow.get("actual_production_force_path_executed")
        and shadow.get("actual_openmp_runtime")
        and shadow.get("production_topology_identity_passed")
        and shadow.get("production_one_rings_expected_empty")
        and not shadow.get("production_one_rings_populated")
        and shadow.get("independent_exact_index_layout_oracle_passed")
        and shadow.get("nonzero_face_contribution_count") == 8
        and shadow.get("all_face_contributions_finite")
        and shadow.get("expected_collision_count_per_component") == 8
        and shadow.get("collision_counts") == [8] * 54
        and shadow.get("collision_coverage_passed")
        and shadow.get("uncovered_component_slots") == []
        and shadow.get("single_contribution_component_slots") == []
        and shadow.get("unexpected_collision_count_component_slots") == []
        and shadow.get("actual_openmp_runtime_parity_passed")
        and shadow.get("absolute_tolerance") == 1.0e-12
    )
    if not passed:
        emit(
            {
                "status": "failed",
                "reason": "production/OpenMP shadow evidence did not pass",
                "shadow": shadow,
            },
            args.json,
        )
        return 1

    emit(
        {
            "status": "passed",
            "proof_only": True,
            "production_call_shadow": True,
            "not_production_routing": True,
            "production_route_enabled": False,
            "actual_production_force_path_executed": False,
            "production_topology_identity_passed": True,
            "actual_openmp_runtime_parity_passed": True,
            "prerequisite_force_proof_passed": True,
            "shadow": shadow,
        },
        args.json,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
