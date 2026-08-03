#!/usr/bin/env python3
"""Build and verify Option B Phase 3 production-route activation."""

from __future__ import annotations

import argparse
import importlib.util
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
FIXTURE = ROOT / "data/fixtures/closed_valence5"
EXPERIMENT = ROOT / "experiments/irregular_valence5_option_b_phase3_activation.cpp"
PHASE2_RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_phase2_face_loop.py"
BASELINE_RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py"
PRODUCTION_TOLERANCE = 1.0e-10


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(command: list[str], env: dict[str, str], cwd: Path = ROOT):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def compiler() -> str | None:
    if os.environ.get("CXX"):
        return shutil.which(os.environ["CXX"])
    if platform.system() == "Darwin":
        return shutil.which("clang++")
    return shutil.which("g++") or shutil.which("c++")


def gsl_flags(option: str, env: dict[str, str]) -> list[str]:
    result = run(["gsl-config", option], env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "gsl-config failed")
    return shlex.split(result.stdout)


def library_directory(prefix: Path) -> Path:
    for candidate in (prefix / "lib", prefix / "lib64"):
        if any(candidate.glob("libosdCPU.*")):
            return candidate
    raise RuntimeError("OpenSubdiv osdCPU library is not discoverable")


def build(binary: Path, env: dict[str, str], prefix: Path | None, omp: bool) -> None:
    cxx = compiler()
    if not cxx or not shutil.which("gsl-config"):
        raise RuntimeError("a C++17 compiler and gsl-config are required")
    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    command = [
        cxx,
        "-std=c++17",
        "-O2",
        "-Iinclude",
        "-Iinclude/energy_force",
        "-Iinclude/linalg",
        "-Iinclude/mesh",
        "-Iinclude/model",
        "-Iinclude/parameters",
        *gsl_flags("--cflags", env),
    ]
    if omp:
        command.extend(("-DOMP", "-fopenmp"))
    if prefix is not None:
        header = prefix / "include/opensubdiv/far/topologyDescriptor.h"
        if not header.is_file():
            raise RuntimeError("OpenSubdiv headers are not discoverable")
        command.extend(("-DUSE_OPENSUBDIV_VALENCE5", f"-I{prefix / 'include'}"))
    command.extend((
        str(EXPERIMENT),
        *(str(source) for source in sources),
        *gsl_flags("--libs", env),
    ))
    if prefix is not None:
        libdir = library_directory(prefix)
        command.extend((f"-L{libdir}", f"-Wl,-rpath,{libdir}", "-losdCPU"))
    if omp:
        command.append("-fopenmp")
    command.extend(("-o", str(binary)))
    result = run(command, env)
    if result.returncode:
        raise RuntimeError(
            "Phase 3 compile failed: " +
            (result.stderr.strip() or result.stdout.strip())
        )


def strict_payload(text: str, label: str) -> dict[str, object]:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(text, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"{label} emitted invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must emit one JSON object")
    return payload


def run_harness(
    binary: Path,
    env: dict[str, str],
    directory: Path,
    *,
    valence5: bool,
    valence4: bool = False,
) -> tuple[str, dict[str, object]]:
    directory.mkdir(parents=True)
    routed_env = env.copy()
    routed_env.pop("SLIMED_USE_OPENSUBDIV_VALENCE5", None)
    routed_env.pop("SLIMED_USE_OPENSUBDIV_VALENCE4", None)
    routed_env.pop("SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2", None)
    if valence5:
        routed_env["SLIMED_USE_OPENSUBDIV_VALENCE5"] = "1"
    if valence4:
        routed_env["SLIMED_USE_OPENSUBDIV_VALENCE4"] = "1"
    result = run(
        [
            str(binary),
            str(FIXTURE / "vertices.csv"),
            str(FIXTURE / "faces.csv"),
            str(directory / "EnergyForce.csv"),
            str(directory / "restart.chk"),
        ],
        routed_env,
        directory,
    )
    if result.returncode:
        raise RuntimeError(
            f"Phase 3 harness failed with exit {result.returncode}: " +
            (result.stderr.strip() or result.stdout.strip())
        )
    return result.stdout, strict_payload(result.stdout, "Phase 3 harness")


def maximum_difference(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise RuntimeError("observable cardinality drift")
    return max((abs(a - b) for a, b in zip(left, right)), default=0.0)


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        if "reason" in payload:
            print(f"reason: {payload['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    root = env.get("OPENSUBDIV_ROOT")
    try:
        phase2 = load_module(PHASE2_RUNNER, "phase3_phase2_contract")
        baseline = load_module(BASELINE_RUNNER, "phase3_accepted_baseline")
        with tempfile.TemporaryDirectory(prefix="slimed-valence5-phase3-") as temporary:
            temporary_path = Path(temporary)
            default_binary = temporary_path / "phase3_default"
            build(default_binary, env, None, False)
            _, default_fallback = run_harness(
                default_binary, env, temporary_path / "default-fallback", valence5=False
            )
            _, default_rejection = run_harness(
                default_binary, env, temporary_path / "default-request", valence5=True
            )
            if (
                default_fallback.get("status") != "passed"
                or default_fallback.get("fallback_preserved") is not True
                or default_rejection.get("status") != "passed"
                or default_rejection.get("dependency_absent_request_rejected_atomically") is not True
            ):
                raise RuntimeError("dependency-free activation/rollback contract drift")

            if not root:
                payload = {
                    "status": "skipped",
                    "reason": "OPENSUBDIV_ROOT is not set; production activation remains unavailable.",
                    "dependency_absent_request_rejected_atomically": True,
                    "fallback_preserved": True,
                    "production_route_enabled": False,
                }
                emit(payload, args.json)
                return 2 if args.require_opensubdiv else 0

            prefix = Path(root)
            serial_binary = temporary_path / "phase3_serial"
            omp_binary = temporary_path / "phase3_omp"
            build(serial_binary, env, prefix, False)
            build(omp_binary, env, prefix, True)
            _, enabled_fallback = run_harness(
                serial_binary, env, temporary_path / "enabled-fallback", valence5=False
            )
            serial_text, serial = run_harness(
                serial_binary, env, temporary_path / "serial1", valence5=True
            )
            repeated_text, repeated = run_harness(
                serial_binary, env, temporary_path / "serial2", valence5=True
            )
            _, omp = run_harness(
                omp_binary, env, temporary_path / "omp", valence5=True
            )
            _, conflict = run_harness(
                serial_binary,
                env,
                temporary_path / "conflict",
                valence5=True,
                valence4=True,
            )

            if (
                enabled_fallback.get("status") != "passed"
                or enabled_fallback.get("fallback_preserved") is not True
                or conflict.get("status") != "passed"
                or conflict.get("conflicting_route_request_rejected_atomically") is not True
            ):
                raise RuntimeError("enabled rollback or route-conflict contract drift")

            for label, report in (("serial", serial), ("repeat", repeated), ("OpenMP", omp)):
                if report.get("status") != "passed":
                    raise RuntimeError(f"{label} production activation did not pass")
                for key in (
                    "production_route_enabled",
                    "default_evaluator_caller",
                    "phase3_activation_authorized",
                    "production_force_path_executed",
                    "production_one_rings_preserved",
                    "energy_force_writer_executed",
                    "element_face_energy_writer_executed",
                    "checkpoint_roundtrip_exact",
                ):
                    if report.get(key) is not True:
                        raise RuntimeError(f"{label} activation flag {key} drifted")
                for key in (
                    "default_vs_direct_global_max_abs_difference",
                    "default_vs_direct_face_max_abs_difference",
                    "default_vs_direct_geometry_max_abs_difference",
                    "default_vs_direct_force_max_abs_difference",
                ):
                    if float(report[key]) > PRODUCTION_TOLERANCE:
                        raise RuntimeError(f"{label} default-caller comparison {key} drifted")

            serial_global = phase2.finite_list(serial.get("global_energy"), 10, "serial global")
            serial_faces = phase2.finite_list(serial.get("face_energy"), 200, "serial faces")
            serial_geometry = phase2.finite_list(serial.get("face_geometry"), 120, "serial geometry")
            serial_forces = phase2.finite_list(serial.get("aggregate_source_forces"), 108, "serial forces")
            omp_global = phase2.finite_list(omp.get("global_energy"), 10, "OpenMP global")
            omp_faces = phase2.finite_list(omp.get("face_energy"), 200, "OpenMP faces")
            omp_geometry = phase2.finite_list(omp.get("face_geometry"), 120, "OpenMP geometry")
            omp_forces = phase2.finite_list(omp.get("aggregate_source_forces"), 108, "OpenMP forces")
            default_fallback_vector = (
                phase2.finite_list(default_fallback.get("global_energy"), 10, "default fallback global")
                + phase2.finite_list(default_fallback.get("face_energy"), 200, "default fallback faces")
                + phase2.finite_list(default_fallback.get("face_geometry"), 120, "default fallback geometry")
                + phase2.finite_list(default_fallback.get("aggregate_source_forces"), 108, "default fallback forces")
            )
            enabled_fallback_vector = (
                phase2.finite_list(enabled_fallback.get("global_energy"), 10, "enabled fallback global")
                + phase2.finite_list(enabled_fallback.get("face_energy"), 200, "enabled fallback faces")
                + phase2.finite_list(enabled_fallback.get("face_geometry"), 120, "enabled fallback geometry")
                + phase2.finite_list(enabled_fallback.get("aggregate_source_forces"), 108, "enabled fallback forces")
            )

            expected_faces: list[float] = []
            for curvature in phase2.PHASE2_EXPECTED_FACE_CURVATURE:
                expected_faces.extend((
                    curvature, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, curvature,
                ))
            expected_geometry = list(baseline.EXPECTED_CANONICAL_OBSERVABLE_VECTOR[210:330])
            global_rebaseline = maximum_difference(
                serial_global, list(phase2.PHASE2_EXPECTED_GLOBAL_ENERGY)
            )
            face_rebaseline = maximum_difference(serial_faces, expected_faces)
            geometry_rebaseline = maximum_difference(serial_geometry, expected_geometry)
            serial_omp_force = maximum_difference(serial_forces, omp_forces)
            serial_omp_observables = max(
                maximum_difference(serial_global, omp_global),
                maximum_difference(serial_faces, omp_faces),
                maximum_difference(serial_geometry, omp_geometry),
            )
            fallback_build_difference = maximum_difference(
                default_fallback_vector, enabled_fallback_vector
            )
            deterministic = serial_text == repeated_text and serial == repeated
            passed = (
                deterministic
                and global_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["global_energy"]
                and face_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["per_face_energy"]
                and geometry_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["per_face_geometry"]
                and serial_omp_force <= PRODUCTION_TOLERANCE
                and serial_omp_observables <= PRODUCTION_TOLERANCE
                and fallback_build_difference <= PRODUCTION_TOLERANCE
            )
            payload = {
                "status": "passed" if passed else "failed",
                "proof_kind": "option_b_phase3_default_production_activation",
                "dependency_absent_request_rejected_atomically": True,
                "dependency_present_activation_passed": True,
                "runtime_gate_absent_fallback_preserved": True,
                "conflicting_route_request_rejected_atomically": True,
                "production_route_enabled": True,
                "default_evaluator_caller": True,
                "phase3_activation_authorized": True,
                "rollback": "unset SLIMED_USE_OPENSUBDIV_VALENCE5",
                "default_enabled_build_fallback_max_abs_difference": fallback_build_difference,
                "global_energy_rebaseline_max_abs_difference": global_rebaseline,
                "per_face_energy_rebaseline_max_abs_difference": face_rebaseline,
                "geometry_rebaseline_max_abs_difference": geometry_rebaseline,
                "serial_openmp_force_max_abs_difference": serial_omp_force,
                "serial_openmp_observable_max_abs_difference": serial_omp_observables,
                "repeatability_exact": deterministic,
                "output_and_restart_through_default_caller_passed": True,
                "production_tolerance": PRODUCTION_TOLERANCE,
            }
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1
    emit(payload, args.json)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
