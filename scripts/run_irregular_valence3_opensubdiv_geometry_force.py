#!/usr/bin/env python3
"""Build and run the proof-only Valence-3 OpenSubdiv science harness."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/irregular_valence3_opensubdiv_geometry_force.cpp"
TETRA = ROOT / "data/fixtures/candidates/closed_valence3_tetrahedron"
MIXED = ROOT / "data/fixtures/candidates/closed_mixed_valence345"


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


def gsl_flags(option: str, env: dict[str, str]) -> list[str]:
    result = run(["gsl-config", option], env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "gsl-config failed")
    return shlex.split(result.stdout)


def build(binary: Path, env: dict[str, str], enabled: bool) -> None:
    compiler = env.get("CXX") or shutil.which("g++") or shutil.which("c++")
    if not compiler or not shutil.which("gsl-config"):
        raise RuntimeError("a C++17 compiler and gsl-config are required")
    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    command = [
        compiler,
        "-std=c++17",
        "-Iinclude",
        "-Iinclude/energy_force",
        "-Iinclude/linalg",
        "-Iinclude/mesh",
        "-Iinclude/model",
        "-Iinclude/parameters",
        *gsl_flags("--cflags", env),
    ]
    if enabled:
        root = env.get("OPENSUBDIV_ROOT")
        if not root:
            raise RuntimeError("OPENSUBDIV_ROOT is required for the enabled proof")
        command.extend(
            [
                "-DUSE_OPENSUBDIV_VALENCE3",
                f"-I{root}/include",
            ]
        )
    command.extend([str(EXPERIMENT), *(str(source) for source in sources)])
    command.extend(gsl_flags("--libs", env))
    if enabled:
        root = env["OPENSUBDIV_ROOT"]
        command.extend(
            [
                f"-L{root}/lib",
                f"-L{root}/lib64",
                f"-Wl,-rpath,{root}/lib",
                f"-Wl,-rpath,{root}/lib64",
                "-losdCPU",
            ]
        )
    command.extend(["-o", str(binary)])
    result = run(command, env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def execute(binary: Path, env: dict[str, str]) -> dict[str, object]:
    result = run(
        [
            str(binary),
            str(TETRA / "vertices.csv"),
            str(TETRA / "faces.csv"),
            str(MIXED / "vertices.csv"),
            str(MIXED / "faces.csv"),
        ],
        env,
    )
    if result.returncode:
        raise RuntimeError(
            f"harness exited {result.returncode}: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    return json.loads(result.stdout)


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    if "default_off_contract" in payload:
        print(f"default_off_contract: {payload['default_off_contract']}")
    if "reason" in payload:
        print(f"reason: {payload['reason']}")
    for fixture in payload.get("fixtures", []):
        print(
            f"{fixture['name']}: area={fixture['area']:.17g}, "
            f"volume={fixture['full_divergence_volume']:.17g}, "
            f"max_abs_force={fixture['max_abs_force']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    try:
        with tempfile.TemporaryDirectory(prefix="slimed-valence3-") as temp:
            temp_path = Path(temp)
            default_binary = temp_path / "valence3-default"
            build(default_binary, env, enabled=False)
            default_payload = execute(default_binary, env)
            default_passed = (
                default_payload.get("status") == "passed"
                and default_payload.get("dependency_disabled_contract_passed")
                is True
            )
            if not env.get("OPENSUBDIV_ROOT"):
                payload = {
                    "status": "passed" if default_passed else "failed",
                    "default_off_contract": default_passed,
                    "enabled_status": "skipped",
                    "reason": (
                        "OPENSUBDIV_ROOT is not set; the default-off contract "
                        "ran, while the enabled proof remains opt-in."
                    ),
                }
                emit(payload, args.json)
                if args.require_opensubdiv:
                    return 2
                return 0 if default_passed else 1

            enabled_binary = temp_path / "valence3-enabled"
            build(enabled_binary, env, enabled=True)
            enabled_payload = execute(enabled_binary, env)
        passed = enabled_payload.get("status") == "passed" and default_passed
        enabled_payload["default_off_contract"] = default_passed
        enabled_payload["status"] = "passed" if passed else "failed"
        emit(enabled_payload, args.json)
        return 0 if passed else 1
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
