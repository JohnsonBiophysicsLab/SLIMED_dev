#!/usr/bin/env python3
"""Validate the guarded OpenSubdiv-fed valence-4 production caller."""

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
    ROOT / "experiments/irregular_valence4_opensubdiv_production_caller.cpp"
)
TOLERANCE = 1.0e-12


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
    if "reason" in payload:
        print(f"reason: {payload['reason']}")


def compiler(*, openmp: bool) -> str | None:
    if os.environ.get("CXX"):
        return os.environ["CXX"]
    if platform.system() == "Darwin" and shutil.which("clang++"):
        return "clang++"
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


def libomp_prefix() -> Path | None:
    if platform.system() != "Darwin" or not shutil.which("brew"):
        return None
    result = subprocess.run(
        ["brew", "--prefix", "libomp"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def using_clang(cxx: str) -> bool:
    return "clang" in Path(cxx).name


def openmp_compile_flags(cxx: str, *, openmp: bool) -> list[str]:
    if not openmp:
        return []
    if platform.system() == "Darwin" and using_clang(cxx):
        return ["-DOMP", "-Xpreprocessor", "-fopenmp"]
    return ["-DOMP", "-fopenmp"]


def openmp_link_flags(cxx: str, *, openmp: bool) -> list[str]:
    if not openmp:
        return []
    if platform.system() == "Darwin" and using_clang(cxx):
        prefix = libomp_prefix()
        if prefix is None:
            raise RuntimeError("Homebrew libomp is required for clang OpenMP")
        libdir = prefix / "lib"
        return [f"-L{libdir}", f"-Wl,-rpath,{libdir}", "-lomp"]
    return ["-fopenmp"]


def build_harness(
    binary: Path, prefix: Path, env: dict[str, str], *, openmp: bool
) -> None:
    cxx = compiler(openmp=openmp)
    if not cxx or not shutil.which("gsl-config"):
        raise RuntimeError("a C++ compiler and gsl-config are required")
    if not (
        prefix / "include/opensubdiv/far/topologyDescriptor.h"
    ).is_file():
        raise RuntimeError("OpenSubdiv headers are not discoverable")
    libdir = library_directory(prefix)
    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    mode_flags = openmp_compile_flags(cxx, openmp=openmp)
    command = [
        cxx,
        "-std=c++17",
        "-DUSE_OPENSUBDIV_REGULAR",
        *mode_flags,
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
        *openmp_link_flags(cxx, openmp=openmp),
        "-o",
        str(binary),
    ]
    result = run(command, env)
    if result.returncode != 0:
        mode = "OpenMP" if openmp else "serial"
        raise RuntimeError(
            f"{mode} OpenSubdiv production caller compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def run_harness(
    binary: Path, env: dict[str, str], *, openmp: bool
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
        ],
        run_env,
    )
    if result.returncode != 0:
        mode = "OpenMP" if openmp else "serial"
        raise RuntimeError(
            f"{mode} OpenSubdiv production caller failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    payload = json.loads(result.stdout)
    if not payload.get("passed"):
        raise RuntimeError("OpenSubdiv production caller did not pass")
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
        raise RuntimeError("OpenSubdiv production caller vector is malformed")
    return [float(component) for component in value]


def validate_output(payload: dict[str, object]) -> dict[str, object]:
    required_true = (
        "default_off_caller_rejected",
        "exact_quadrature_sample_plan_validated",
        "exact_quadrature_weights_validated",
        "opensubdiv_row_provider_executed",
        "opensubdiv_rows_generated",
        "row_provider_accepted",
        "row_provider_rows_generated",
        "production_caller_shadow_executed",
        "production_completion_phases_executed",
        "total_force_publication_executed",
        "total_energy_publication_executed",
        "boundary_handling_executed",
        "current_state_cleared",
        "atomic_geometry_scientific_publication_executed",
        "production_caller_shadow_totals_consistent",
        "nonzero_membrane_forces",
        "production_one_rings_empty",
        "not_production_routing",
    )
    required_false = (
        "production_route_enabled",
        "actual_production_force_path_executed",
        "production_face_loop_executed",
        "default_evaluator_caller",
    )
    if not all(payload.get(key) for key in required_true):
        raise RuntimeError("OpenSubdiv production caller flags are invalid")
    if any(payload.get(key) for key in required_false):
        raise RuntimeError("OpenSubdiv production caller enabled routing")

    force_values: list[float] = []
    forces = payload.get("vertex_forces")
    if not isinstance(forces, list) or len(forces) != 6:
        raise RuntimeError("OpenSubdiv production caller forces are malformed")
    for source_id, force in enumerate(forces):
        if (
            not isinstance(force, dict)
            or force.get("source_id") != source_id
        ):
            raise RuntimeError("OpenSubdiv production caller source drifted")
        for key in ("fBend", "fArea", "fVolume", "fTotal"):
            force_values.extend(finite_vector(force.get(key), 3))

    observable_values: list[float] = []
    observables = payload.get("face_observables")
    if not isinstance(observables, list) or len(observables) != 8:
        raise RuntimeError(
            "OpenSubdiv production caller observables are malformed"
        )
    for face_index, face in enumerate(observables):
        if (
            not isinstance(face, dict)
            or face.get("face") != face_index
            or not isinstance(face.get("mean_curvature"), (int, float))
            or not isinstance(face.get("bending_energy"), (int, float))
            or not isinstance(face.get("area"), (int, float))
            or not isinstance(face.get("legacy_volume"), (int, float))
        ):
            raise RuntimeError("OpenSubdiv production caller face drifted")
        observable_values.extend(
            [
                float(face["mean_curvature"]),
                float(face["bending_energy"]),
                float(face["area"]),
                float(face["legacy_volume"]),
            ]
        )
        observable_values.extend(finite_vector(face.get("normal"), 3))

    energy_total = payload.get("energy_total")
    if not isinstance(energy_total, (int, float)) or not math.isfinite(
        float(energy_total)
    ):
        raise RuntimeError("OpenSubdiv production caller energy is malformed")
    return {
        "forces": force_values,
        "observables": observable_values,
        "energy_total": float(energy_total),
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
    root = env.get("OPENSUBDIV_ROOT")
    if not root:
        emit(
            {
                "status": "skipped",
                "reason": (
                    "OPENSUBDIV_ROOT is not set; the guarded valence-4 "
                    "OpenSubdiv production caller is explicit opt-in only."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-opensubdiv-production-caller-"
        ) as temporary:
            temp = Path(temporary)
            serial_binary = temp / "opensubdiv_production_caller_serial"
            openmp_binary = temp / "opensubdiv_production_caller_openmp"
            build_harness(
                serial_binary, Path(root), env, openmp=False
            )
            build_harness(
                openmp_binary, Path(root), env, openmp=True
            )
            serial_payload = run_harness(
                serial_binary, env, openmp=False
            )
            openmp_payload = run_harness(
                openmp_binary, env, openmp=True
            )
        serial = validate_output(serial_payload)
        openmp = validate_output(openmp_payload)
        force_delta = maximum_delta(serial["forces"], openmp["forces"])
        observable_delta = maximum_delta(
            serial["observables"], openmp["observables"]
        )
        energy_delta = abs(
            float(serial["energy_total"]) -
            float(openmp["energy_total"])
        )
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    parity_passed = bool(
        force_delta <= TOLERANCE
        and observable_delta <= TOLERANCE
        and energy_delta <= TOLERANCE
    )
    payload = {
        "status": "passed" if parity_passed else "failed",
        "provider_fed_production_caller": True,
        "exact_quadrature_sample_plan_validated": True,
        "exact_quadrature_weights_validated": True,
        "opensubdiv_row_provider_executed": True,
        "opensubdiv_rows_generated": True,
        "production_caller_shadow_executed": True,
        "production_completion_phases_executed": True,
        "serial_openmp_provider_fed_caller_parity_passed": parity_passed,
        "max_serial_openmp_provider_fed_force_delta": force_delta,
        "max_serial_openmp_provider_fed_observable_delta": observable_delta,
        "serial_openmp_provider_fed_energy_delta": energy_delta,
        "absolute_tolerance": TOLERANCE,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_one_rings_populated": False,
        "default_dependency_changed": False,
        "next_boundary": (
            "route activation remains a separate explicit reviewer/user "
            "decision"
        ),
        "serial_output": serial_payload,
        "openmp_output": openmp_payload,
    }
    emit(payload, args.json)
    return 0 if parity_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
