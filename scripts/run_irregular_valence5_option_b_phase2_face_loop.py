#!/usr/bin/env python3
"""Build and verify the guarded Option B Phase 2 production face loop."""

from __future__ import annotations

import argparse
import csv
import importlib.util
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
FIXTURE = ROOT / "data/fixtures/closed_valence5"
EXPERIMENT = ROOT / "experiments/irregular_valence5_option_b_phase2_face_loop.cpp"
ORACLE = ROOT / "experiments/irregular_valence5_option_b_energy_geometry_oracle.cpp"
ACCEPTED_BASELINE = (
    ROOT / "scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py"
)
PRODUCTION_TOLERANCE = 1.0e-10
FORCE_CROSS_PLATFORM_ENVELOPE = 5.0e-6
PHASE2_EXPECTED_GLOBAL_ENERGY = (
    1195.2860440949671, 3.6122088504276455, 0.048070817616346115,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1198.9463237630109,
)
PHASE2_EXPECTED_FACE_CURVATURE = (
    59.470863201063196, 59.056966043926508, 58.205818835589852,
    60.335132759250229, 61.078074136244304, 60.022516249811517,
    59.499830874893753, 60.278281932492419, 60.493186895256976,
    60.010577664305359, 59.999543780121812, 61.343410407645976,
    59.493201303304211, 59.553136499380827, 58.840315311788522,
    59.782589911059688, 59.411124644202417, 59.153989722445985,
    60.064208405483463, 59.193275516700062,
)


def load_baseline():
    spec = importlib.util.spec_from_file_location("option_b_phase2_baseline", ACCEPTED_BASELINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the accepted Option B baseline")
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
        mode = "OpenMP" if omp else "serial"
        dependency = "enabled" if prefix is not None else "disabled"
        raise RuntimeError(
            f"Phase 2 {dependency} {mode} compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
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


def run_harness(binary: Path, env: dict[str, str], directory: Path):
    directory.mkdir(parents=True)
    energy_csv = directory / "EnergyForce.csv"
    checkpoint = directory / "restart.chk"
    oracle_package = directory / "oracle_package.txt"
    result = run(
        [
            str(binary),
            str(FIXTURE / "vertices.csv"),
            str(FIXTURE / "faces.csv"),
            str(energy_csv),
            str(checkpoint),
            str(oracle_package),
        ],
        env,
        directory,
    )
    if result.returncode:
        raise RuntimeError(
            f"Phase 2 harness failed with exit {result.returncode}: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    return (
        result.stdout,
        strict_payload(result.stdout, "Phase 2 harness"),
        energy_csv,
        oracle_package,
    )


def build_oracle(binary: Path, env: dict[str, str]) -> None:
    cxx = compiler()
    if not cxx:
        raise RuntimeError("a C++17 compiler is required for the independent oracle")
    result = run([cxx, "-std=c++17", "-O2", str(ORACLE), "-o", str(binary)], env)
    if result.returncode:
        raise RuntimeError(
            "independent long-double oracle compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def run_oracle(binary: Path, package: Path, env: dict[str, str]) -> dict[str, object]:
    result = run([str(binary), str(package)], env)
    if result.returncode:
        raise RuntimeError(
            "independent long-double oracle failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    payload = strict_payload(result.stdout, "independent long-double oracle")
    if (
        payload.get("status") != "passed"
        or payload.get("independent_long_double_oracle") is not True
        or payload.get("calls_element_energy_force_regular") is not False
    ):
        raise RuntimeError("independent long-double oracle boundary drift")
    return payload


def finite_list(value: object, count: int, label: str) -> list[float]:
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
        raise RuntimeError(f"{label} must contain {count} finite values")
    return [float(item) for item in value]


def maximum_difference(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise RuntimeError("observable cardinality drift")
    return max((abs(a - b) for a, b in zip(left, right)), default=0.0)


def read_csv_values(path: Path, expected_rows: int, label: str) -> list[list[float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if len(rows) != expected_rows + 1:
        raise RuntimeError(f"{label} row-count drift")
    result = []
    for row in rows[1:]:
        try:
            values = [float(item) for item in row]
        except ValueError as error:
            raise RuntimeError(f"{label} contains nonnumeric output") from error
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"{label} contains nonfinite output")
        result.append(values)
    return result


def validate_output_csvs(directory: Path, payload: dict[str, object]) -> tuple[float, float]:
    global_energy = finite_list(payload.get("global_energy"), 10, "global energy")
    face_energy = finite_list(payload.get("face_energy"), 200, "face energy")
    energy_rows = read_csv_values(directory / "EnergyForce.csv", 1, "EnergyForce.csv")
    face_rows = read_csv_values(directory / "ElementFaceEnergy.csv", 20, "ElementFaceEnergy.csv")
    if len(energy_rows[0]) != 11:
        raise RuntimeError("EnergyForce.csv column-count drift")
    global_difference = maximum_difference(energy_rows[0][:10], global_energy)
    serialized_faces = []
    for face_index, row in enumerate(face_rows):
        if len(row) != 11 or row[0] != float(face_index):
            raise RuntimeError("ElementFaceEnergy.csv schema/order drift")
        serialized_faces.extend(row[1:])
    face_difference = maximum_difference(serialized_faces, face_energy)
    return global_difference, face_difference


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
        with tempfile.TemporaryDirectory(prefix="slimed-valence5-phase2-") as temporary:
            temporary_path = Path(temporary)
            default_binary = temporary_path / "phase2_default"
            build(default_binary, env, None, False)
            _, default, _, _ = run_harness(default_binary, env, temporary_path / "default")
            if (
                default.get("status") != "passed"
                or default.get("dependency_disabled_contract_passed") is not True
                or default.get("production_route_enabled") is not False
            ):
                raise RuntimeError("dependency-disabled Phase 2 contract drift")

            if not root:
                payload = {
                    "status": "skipped",
                    "reason": "OPENSUBDIV_ROOT is not set; Phase 2 remains opt-in.",
                    "dependency_disabled_contract_passed": True,
                    "production_route_enabled": False,
                    "phase3_activation_authorized": False,
                }
                emit(payload, args.json)
                return 2 if args.require_opensubdiv else 0

            prefix = Path(root)
            serial_binary = temporary_path / "phase2_serial"
            omp_binary = temporary_path / "phase2_omp"
            build(serial_binary, env, prefix, False)
            build(omp_binary, env, prefix, True)
            serial_text, serial, _, oracle_package = run_harness(
                serial_binary, env, temporary_path / "serial1"
            )
            repeated_text, repeated, _, _ = run_harness(
                serial_binary, env, temporary_path / "serial2"
            )
            _, omp, _, _ = run_harness(omp_binary, env, temporary_path / "omp")

            for label, report in (("serial", serial), ("repeat", repeated), ("OpenMP", omp)):
                if report.get("status") != "passed":
                    raise RuntimeError(f"{label} Phase 2 report did not pass")
                for key in (
                    "explicit_gate_rejection_atomic",
                    "dependency_compiled",
                    "runtime_opt_in_requested",
                    "production_force_path_executed",
                    "production_face_loop_executed",
                    "production_one_rings_preserved",
                    "default_caller_remained_fallback",
                    "output_state_finite",
                    "long_double_oracle_package_written",
                    "energy_force_writer_executed",
                    "element_face_energy_writer_executed",
                    "checkpoint_writer_executed",
                    "checkpoint_loader_executed",
                ):
                    if report.get(key) is not True:
                        raise RuntimeError(f"{label} Phase 2 gate {key} drifted")
                for key in (
                    "production_route_enabled",
                    "default_evaluator_caller",
                    "phase3_activation_authorized",
                ):
                    if report.get(key) is not False:
                        raise RuntimeError(f"{label} unexpectedly enabled {key}")

            baseline = load_baseline()
            oracle_binary = temporary_path / "phase2_long_double_oracle"
            build_oracle(oracle_binary, env)
            oracle = run_oracle(oracle_binary, oracle_package, env)
            oracle_values = baseline.expand(oracle, "Phase 2 double-row oracle")
            accepted = list(baseline.EXPECTED_CANONICAL_OBSERVABLE_VECTOR)
            expected_global = list(PHASE2_EXPECTED_GLOBAL_ENERGY)
            expected_faces = []
            for curvature in PHASE2_EXPECTED_FACE_CURVATURE:
                expected_faces.extend((
                    curvature, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, curvature,
                ))
            expected_geometry = accepted[210:330]
            serial_global = finite_list(serial.get("global_energy"), 10, "serial global energy")
            serial_faces = finite_list(serial.get("face_energy"), 200, "serial face energy")
            serial_geometry = finite_list(serial.get("face_geometry"), 120, "serial geometry")
            serial_forces = finite_list(serial.get("aggregate_source_forces"), 108, "serial forces")
            omp_forces = finite_list(omp.get("aggregate_source_forces"), 108, "OpenMP forces")
            omp_global = finite_list(omp.get("global_energy"), 10, "OpenMP global energy")
            omp_faces = finite_list(omp.get("face_energy"), 200, "OpenMP face energy")
            omp_geometry = finite_list(omp.get("face_geometry"), 120, "OpenMP geometry")

            global_rebaseline = maximum_difference(serial_global, expected_global)
            face_rebaseline = maximum_difference(serial_faces, expected_faces)
            geometry_rebaseline = maximum_difference(serial_geometry, expected_geometry)
            provider_precision_global_delta = maximum_difference(
                serial_global, accepted[:10]
            )
            provider_precision_face_delta = maximum_difference(
                serial_faces, accepted[10:210]
            )
            serial_omp_force = maximum_difference(serial_forces, omp_forces)
            serial_omp_observables = max(
                maximum_difference(serial_global, omp_global),
                maximum_difference(serial_faces, omp_faces),
                maximum_difference(serial_geometry, omp_geometry),
            )
            oracle_maximum = max(
                maximum_difference(serial_global, oracle_values["global_energy"]),
                maximum_difference(serial_faces, oracle_values["face_energy"]),
                maximum_difference(serial_geometry, oracle_values["geometry"]),
            )
            csv_global, csv_faces = validate_output_csvs(temporary_path / "serial1", serial)
            deterministic = serial_text == repeated_text and serial == repeated
            restart_keys = (
                "checkpoint_global_energy_max_abs_difference",
                "checkpoint_face_energy_max_abs_difference",
                "checkpoint_geometry_max_abs_difference",
                "checkpoint_membrane_force_max_abs_difference",
            )
            restart_exact = all(serial.get(key) == 0.0 for key in restart_keys)
            passed = (
                deterministic
                and global_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["global_energy"]
                and face_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["per_face_energy"]
                and geometry_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["per_face_geometry"]
                and serial_omp_force <= PRODUCTION_TOLERANCE
                and serial_omp_observables <= PRODUCTION_TOLERANCE
                and oracle_maximum <= baseline.ORACLE_ABSOLUTE_TOLERANCE
                and float(serial["face_observable_dry_run_max_abs_difference"]) <= PRODUCTION_TOLERANCE
                and float(serial["source_force_dry_run_max_abs_difference"]) <= PRODUCTION_TOLERANCE
                and csv_global <= FORCE_CROSS_PLATFORM_ENVELOPE
                and csv_faces <= FORCE_CROSS_PLATFORM_ENVELOPE
                and restart_exact
            )
            payload = {
                "status": "passed" if passed else "failed",
                "proof_kind": "guarded_option_b_phase2_production_face_loop",
                "dependency_disabled_contract_passed": True,
                "explicit_and_runtime_gates_passed": True,
                "atomic_rejection_passed": True,
                "actual_production_force_path_executed": True,
                "accepted_energy_geometry_rebaseline_passed": (
                    global_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["global_energy"]
                    and face_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["per_face_energy"]
                    and geometry_rebaseline <= baseline.CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE["per_face_geometry"]
                ),
                "global_energy_rebaseline_max_abs_difference": global_rebaseline,
                "per_face_energy_rebaseline_max_abs_difference": face_rebaseline,
                "geometry_rebaseline_max_abs_difference": geometry_rebaseline,
                "phase1_double_provider_vs_accepted_float_global_max_abs_difference": provider_precision_global_delta,
                "phase1_double_provider_vs_accepted_float_face_max_abs_difference": provider_precision_face_delta,
                "serial_openmp_force_max_abs_difference": serial_omp_force,
                "serial_openmp_observable_max_abs_difference": serial_omp_observables,
                "independent_long_double_oracle_max_abs_difference": oracle_maximum,
                "independent_long_double_oracle_passed": (
                    oracle_maximum <= baseline.ORACLE_ABSOLUTE_TOLERANCE
                ),
                "production_tolerance": PRODUCTION_TOLERANCE,
                "repeatability_exact": deterministic,
                "output_csv_global_max_abs_difference": csv_global,
                "output_csv_face_max_abs_difference": csv_faces,
                "restart_roundtrip_exact": restart_exact,
                "production_route_enabled": False,
                "default_evaluator_caller": False,
                "phase3_activation_authorized": False,
                "current_fallback_preserved": True,
            }
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1
    emit(payload, args.json)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
