#!/usr/bin/env python3
"""Compare the guarded valence-4 atomic publication in serial and OpenMP builds."""

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

import run_irregular_valence4_face_loop_observable_shadow as observable_shadow
import run_irregular_valence4_source_keyed_kernel_adapter as source_adapter


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = (
    ROOT / "experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"
)
FIXTURE = ROOT / "data/fixtures/candidates/closed_valence4_octahedron"
OPENMP_SHADOW = (
    ROOT / "scripts/run_irregular_valence4_production_openmp_shadow.sh"
)
TOLERANCE = 1.0e-12
PRODUCTION_LEGACY_VOLUME_FACTOR = 0.16666666666
ORACLE_LEGACY_VOLUME_FACTOR = 1.0 / 6.0


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
        "serial_openmp_output_parity_passed",
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


def build_harness(
    binary: Path, env: dict[str, str], *, openmp: bool
) -> None:
    cxx = compiler()
    if not cxx or not shutil.which("gsl-config"):
        raise RuntimeError("a C++ compiler and gsl-config are required")
    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    mode_flags = ["-DOMP", "-fopenmp"] if openmp else []
    command = [
        cxx,
        "-std=c++17",
        *mode_flags,
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
        *mode_flags[-1:],
        "-o",
        str(binary),
    ]
    result = run(command, env)
    if result.returncode != 0:
        mode = "OpenMP" if openmp else "serial"
        raise RuntimeError(
            f"{mode} production-call shadow compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def run_harness(
    binary: Path, package: Path, env: dict[str, str], *, openmp: bool
) -> dict[str, object]:
    run_env = env.copy()
    if openmp:
        run_env["OMP_DYNAMIC"] = "FALSE"
        run_env["OMP_NUM_THREADS"] = "4"
    result = run(
        [
            str(binary),
            str(FIXTURE / "vertices.csv"),
            str(FIXTURE / "faces.csv"),
            str(package),
        ],
        run_env,
    )
    if result.returncode != 0:
        mode = "OpenMP" if openmp else "serial"
        raise RuntimeError(
            f"{mode} production-call shadow failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    payload = json.loads(result.stdout)
    if not payload.get("passed"):
        raise RuntimeError("production-call shadow experiment did not pass")
    return payload


def finite_vector(value: object, size: int) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != size
        or not all(
            isinstance(component, (int, float))
            and math.isfinite(float(component))
            for component in value
        )
    ):
        raise RuntimeError("production-call shadow vector is malformed")
    return [float(component) for component in value]


def validated_output(payload: dict[str, object]) -> dict[str, object]:
    shadow = payload.get("production_call_shadow")
    if not isinstance(shadow, dict):
        raise RuntimeError("production-call shadow output is missing")
    if not (
        shadow.get("executed")
        and shadow.get("atomic_transaction_invoked")
        and shadow.get("serial_openmp_comparison_ready")
        and shadow.get("production_shaped_geometry_evaluated")
        and shadow.get("not_production_routing")
        and not shadow.get("production_route_enabled")
        and not shadow.get("actual_production_force_path_executed")
        and not shadow.get("production_face_loop_executed")
    ):
        raise RuntimeError("production-call shadow boundary flags are invalid")

    area = shadow.get("area")
    volume = shadow.get("legacy_volume")
    if not all(
        isinstance(value, (int, float)) and math.isfinite(float(value))
        for value in (area, volume)
    ):
        raise RuntimeError("production-call area/volume output is malformed")

    force_values: list[float] = []
    forces = shadow.get("vertex_forces")
    if not isinstance(forces, list) or len(forces) != 6:
        raise RuntimeError("production-call force output must contain six sources")
    for source_id, source in enumerate(forces):
        if (
            not isinstance(source, dict)
            or source.get("source_id") != source_id
        ):
            raise RuntimeError("production-call source identity is malformed")
        for key in ("fBend", "fArea", "fVolume"):
            force_values.extend(finite_vector(source.get(key), 3))

    observable_values: list[float] = []
    observables = shadow.get("face_observables")
    if not isinstance(observables, list) or len(observables) != 8:
        raise RuntimeError("production-call output must contain eight faces")
    for face_index, face in enumerate(observables):
        if (
            not isinstance(face, dict)
            or face.get("face") != face_index
            or not isinstance(face.get("mean_curvature"), (int, float))
            or not isinstance(face.get("bending_energy"), (int, float))
        ):
            raise RuntimeError("production-call face identity is malformed")
        scalar_values = [
            float(face["mean_curvature"]),
            float(face["bending_energy"]),
        ]
        if not all(math.isfinite(value) for value in scalar_values):
            raise RuntimeError("production-call face scalar is nonfinite")
        observable_values.extend(scalar_values)
        observable_values.extend(finite_vector(face.get("normal"), 3))

    if max(abs(value) for value in force_values) <= 1.0e-10:
        raise RuntimeError("production-call force output is unexpectedly zero")
    return {
        "area": float(area),
        "legacy_volume": float(volume),
        "forces": force_values,
        "observables": observable_values,
    }


def maximum_delta(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return math.inf
    return max((abs(a - b) for a, b in zip(left, right)), default=0.0)


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
                    "OPENSUBDIV_ROOT is not set; production-call shadow "
                    "parity is explicit opt-in only."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        proof = source_adapter.force_report(env)
        _, geometry_oracle = observable_shadow.package_observables(proof)
        oracle_area = float(geometry_oracle["area"])
        oracle_legacy_volume = (
            float(geometry_oracle["legacy_visible_volume"])
            * PRODUCTION_LEGACY_VOLUME_FACTOR
            / ORACLE_LEGACY_VOLUME_FACTOR
        )
        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-production-call-shadow-"
        ) as temporary:
            temp = Path(temporary)
            package = temp / "source_keyed_package.txt"
            serial_binary = temp / "production_call_shadow_serial"
            openmp_binary = temp / "production_call_shadow_openmp"
            source_adapter.write_package(package, proof)
            build_harness(serial_binary, env, openmp=False)
            build_harness(openmp_binary, env, openmp=True)
            serial_payload = run_harness(
                serial_binary, package, env, openmp=False
            )
            openmp_payload = run_harness(
                openmp_binary, package, env, openmp=True
            )

        serial = validated_output(serial_payload)
        openmp = validated_output(openmp_payload)
        force_delta = maximum_delta(serial["forces"], openmp["forces"])
        observable_delta = maximum_delta(
            serial["observables"], openmp["observables"]
        )
        area_delta = abs(float(serial["area"]) - float(openmp["area"]))
        volume_delta = abs(
            float(serial["legacy_volume"])
            - float(openmp["legacy_volume"])
        )
        serial_area_oracle_delta = abs(
            float(serial["area"]) - oracle_area
        )
        openmp_area_oracle_delta = abs(
            float(openmp["area"]) - oracle_area
        )
        serial_volume_oracle_delta = abs(
            float(serial["legacy_volume"]) - oracle_legacy_volume
        )
        openmp_volume_oracle_delta = abs(
            float(openmp["legacy_volume"]) - oracle_legacy_volume
        )

        runtime_result = run(
            [str(OPENMP_SHADOW), "--json", "--require-opensubdiv"],
            env,
        )
        if runtime_result.returncode != 0:
            raise RuntimeError(
                "actual OpenMP runtime proof failed: "
                + (
                    runtime_result.stderr.strip()
                    or runtime_result.stdout.strip()
                )
            )
        runtime_payload = json.loads(runtime_result.stdout)
        runtime_shadow = runtime_payload.get("shadow")
        actual_runtime_passed = bool(
            runtime_payload.get("status") == "passed"
            and runtime_payload.get("actual_openmp_runtime_parity_passed")
            and isinstance(runtime_shadow, dict)
            and runtime_shadow.get("actual_openmp_runtime")
            and runtime_shadow.get("actual_openmp_runtime_parity_passed")
        )
        parity_passed = bool(
            force_delta <= TOLERANCE
            and observable_delta <= TOLERANCE
            and area_delta <= TOLERANCE
            and volume_delta <= TOLERANCE
            and serial_area_oracle_delta <= TOLERANCE
            and openmp_area_oracle_delta <= TOLERANCE
            and serial_volume_oracle_delta <= TOLERANCE
            and openmp_volume_oracle_delta <= TOLERANCE
        )
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    passed = parity_passed and actual_runtime_passed
    emit(
        {
            "status": "passed" if passed else "failed",
            "proof_only": True,
            "production_call_shadow": True,
            "not_production_routing": True,
            "production_route_enabled": False,
            "actual_production_force_path_executed": False,
            "production_face_loop_executed": False,
            "atomic_face_loop_publication_executed": True,
            "production_shaped_geometry_evaluated": True,
            "serial_openmp_output_parity_passed": parity_passed,
            "actual_openmp_runtime_parity_passed": actual_runtime_passed,
            "max_serial_openmp_force_delta": force_delta,
            "max_serial_openmp_face_observable_delta": observable_delta,
            "serial_openmp_area_delta": area_delta,
            "serial_openmp_legacy_volume_delta": volume_delta,
            "serial_area_oracle_delta": serial_area_oracle_delta,
            "openmp_area_oracle_delta": openmp_area_oracle_delta,
            "serial_legacy_volume_oracle_delta":
                serial_volume_oracle_delta,
            "openmp_legacy_volume_oracle_delta":
                openmp_volume_oracle_delta,
            "independent_geometry_oracle": {
                "area": oracle_area,
                "legacy_volume": oracle_legacy_volume,
            },
            "absolute_tolerance": TOLERANCE,
            "serial_output": serial,
            "openmp_output": openmp,
            "actual_openmp_runtime": runtime_payload,
            "residual_boundary": (
                "production route activation remains a separate explicit "
                "reviewer/user decision"
            ),
        },
        args.json,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
