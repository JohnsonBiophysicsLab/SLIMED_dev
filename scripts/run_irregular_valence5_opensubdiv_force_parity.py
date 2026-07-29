#!/usr/bin/env python3
"""Compare valence-5 OpenSubdiv force rows with the positive-depth route."""

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
FORCE_HARNESS = (
    ROOT / "experiments/irregular_valence5_opensubdiv_force_parity.cpp"
)
PROBE = ROOT / "scripts/run_opensubdiv_probe.sh"
REVIEWED_RELATIVE_TOLERANCE = 5.0e-6


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


def build(binary: Path, experiment: Path, env: dict[str, str]) -> None:
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
        str(experiment),
        *(str(source) for source in sources),
        *gsl_flags("--libs"),
        "-o",
        str(binary),
    ]
    result = run(command, env)
    if result.returncode != 0:
        raise RuntimeError(
            f"{experiment.name} compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def parse_process_json(
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


def write_package(
    path: Path,
    production: dict[str, object],
    proof: dict[str, object],
) -> None:
    parameters = finite_values(
        production.get("force_formula_parameters"),
        8,
        "production force parameters",
    )
    coordinates = finite_values(
        production.get("scientific_coordinates"),
        36,
        "production scientific coordinates",
    )
    faces = proof.get("faces")
    if not isinstance(faces, list) or len(faces) != 20:
        raise RuntimeError("OpenSubdiv proof must contain twenty faces")

    lines = [
        "20 3 7 12",
        "PARAMETERS "
        + " ".join(format(value, ".17g") for value in parameters),
        "COORDINATES 12",
    ]
    for source in range(12):
        lines.append(
            f"{source} "
            + " ".join(
                format(coordinates[3 * source + axis], ".17g")
                for axis in range(3)
            )
        )

    for face_index, face in enumerate(faces):
        if not isinstance(face, dict):
            raise RuntimeError("OpenSubdiv face record must be an object")
        oriented = face.get("oriented_fixture_vertex_ids")
        samples = face.get("samples")
        if (
            face.get("fixture_face_index") != face_index
            or not isinstance(oriented, list)
            or len(oriented) != 3
            or not isinstance(samples, list)
            or len(samples) != 3
        ):
            raise RuntimeError("OpenSubdiv face identity or sample shape drift")
        lines.append(
            f"{face_index} " + " ".join(str(int(value)) for value in oriented)
        )
        for sample_index, sample in enumerate(samples):
            if (
                not isinstance(sample, dict)
                or sample.get("sample") != sample_index
                or not isinstance(sample.get("rows"), list)
                or len(sample["rows"]) != 7
            ):
                raise RuntimeError("OpenSubdiv sample identity or row shape drift")
            lines.append(str(sample_index))
            for row in sample["rows"]:
                values = finite_values(row, 12, "OpenSubdiv derivative row")
                lines.append(
                    " ".join(format(value, ".17g") for value in values)
                )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compare(
    production: dict[str, object],
    candidate: dict[str, object],
) -> dict[str, object]:
    reference = finite_values(
        production.get("per_face_source_forces"),
        20 * 12 * 9,
        "production per-face source forces",
    )
    actual = finite_values(
        candidate.get("per_face_source_forces"),
        20 * 12 * 9,
        "OpenSubdiv per-face source forces",
    )
    component_deltas = [
        abs(left - right) for left, right in zip(reference, actual)
    ]
    max_component = max(range(len(component_deltas)), key=component_deltas.__getitem__)
    face_index, within_face = divmod(max_component, 12 * 9)
    source_id, within_source = divmod(within_face, 9)
    force_kind, axis = divmod(within_source, 3)
    force_names = ("fBend", "fArea", "fVolume")
    kind_maxima = []
    for kind in range(3):
        kind_maxima.append(
            max(
                component_deltas[
                    face * 108 + source * 9 + kind * 3 + axis
                ]
                for face in range(20)
                for source in range(12)
                for axis in range(3)
            )
        )
    max_delta = max(component_deltas)
    reference_scale = max(1.0, max(abs(value) for value in reference))
    scaled_tolerance = REVIEWED_RELATIVE_TOLERANCE * reference_scale
    parity = max_delta <= scaled_tolerance
    errors = []
    if production.get("production_irregular_force_path_executed") is not True:
        errors.append("positive-depth production force baseline did not execute")
    if candidate.get("opensubdiv_rows_evaluated_by_existing_force_algebra") is not True:
        errors.append("OpenSubdiv rows did not execute existing force algebra")
    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "valence5_opensubdiv_force_parity_diagnostic",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_scatter_executed": False,
        "positive_depth_production_force_path_executed": True,
        "opensubdiv_rows_evaluated_by_existing_force_algebra": True,
        "face_count": 20,
        "source_count": 12,
        "force_component_count": len(component_deltas),
        "force_parity_passed": parity,
        "max_abs_force_difference": max_delta,
        "max_abs_force_difference_location": {
            "face": face_index,
            "source_id": source_id,
            "force_kind": force_names[force_kind],
            "axis": axis,
        },
        "max_abs_force_difference_by_kind": {
            "fBend": kind_maxima[0],
            "fArea": kind_maxima[1],
            "fVolume": kind_maxima[2],
        },
        "relative_tolerance": REVIEWED_RELATIVE_TOLERANCE,
        "reference_force_scale": reference_scale,
        "scaled_absolute_tolerance": scaled_tolerance,
        "remaining_boundary": (
            "guarded opt-in valence-5 route activation"
            if parity
            else "resolve the measured valence-5 force parity residuals"
        ),
        "route_blockers": (
            []
            if parity
            else [
                "direct whole-Ptex OpenSubdiv rows do not match the existing "
                "positive-depth 11=4+3+4 force composition"
            ]
        ),
        "errors": errors,
    }


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    for key in (
        "force_parity_passed",
        "max_abs_force_difference",
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
        with tempfile.TemporaryDirectory(prefix="slimed-val5-force-") as tmp:
            tmp_path = Path(tmp)
            production_binary = tmp_path / "production"
            candidate_binary = tmp_path / "candidate"
            package_path = tmp_path / "package.txt"
            build(production_binary, PRODUCTION_REPORTER, env)
            build(candidate_binary, FORCE_HARNESS, env)
            production = parse_process_json(
                run([str(production_binary)], env),
                "positive-depth production reporter",
            )
            wrapper = parse_process_json(
                run(
                    [
                        str(PROBE),
                        "--json",
                        "--require-opensubdiv",
                        "--valence5-source-order-transpose-report",
                    ],
                    env,
                ),
                "OpenSubdiv row provider",
            )
            output = wrapper.get("prototype_output")
            if not isinstance(output, list) or len(output) != 1:
                raise RuntimeError("OpenSubdiv row provider omitted its report")
            proof = json.loads(output[0]).get("valence5_source_order_transpose")
            if not isinstance(proof, dict) or proof.get("passed") is not True:
                raise RuntimeError("OpenSubdiv row provider did not pass")
            write_package(package_path, production, proof)
            candidate = parse_process_json(
                run([str(candidate_binary), str(package_path)], env),
                "OpenSubdiv force harness",
            )
            payload = compare(production, candidate)
    except (RuntimeError, json.JSONDecodeError, OSError) as error:
        payload = {"status": "failed", "reason": str(error)}
        emit(payload, args.json)
        return 1

    emit(payload, args.json)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
