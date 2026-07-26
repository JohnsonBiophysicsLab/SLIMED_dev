#!/usr/bin/env python3
"""Run the proof-only valence-4 source-keyed kernel adapter package."""

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
EXPERIMENT = ROOT / "experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"
FIXTURE = ROOT / "data/fixtures/candidates/closed_valence4_octahedron"
ORIENTED_FACES = (
    (0, 2, 3),
    (0, 3, 4),
    (0, 4, 5),
    (0, 5, 2),
    (1, 3, 2),
    (1, 4, 3),
    (1, 5, 4),
    (1, 2, 5),
)


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
    for key in ("reason", "adapter_passed", "residual_boundary"):
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
            "source-keyed adapter compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def force_report(env: dict[str, str]) -> dict[str, object]:
    result = run([str(FORCE_PROOF), "--json", "--require-opensubdiv"], env)
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


def finite_vector(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(
            isinstance(component, (int, float))
            and math.isfinite(float(component))
            for component in value
        )
    )


def write_package(path: Path, proof: dict[str, object]) -> None:
    binding = proof.get("fresh_opensubdiv_row_binding")
    contributions = proof.get("face_force_contributions")
    if not isinstance(binding, dict) or not isinstance(contributions, list):
        raise RuntimeError("force proof omitted rows or face-force contributions")
    if (
        binding.get("generated_in_this_process") is not True
        or binding.get("face_count") != 8
        or binding.get("samples_per_face") != 3
        or binding.get("row_count") != 7
        or binding.get("source_count") != 6
    ):
        raise RuntimeError("fresh row tensor dimensions are not 8x3x7x6")
    faces = binding.get("faces")
    if not isinstance(faces, list) or len(faces) != 8 or len(contributions) != 8:
        raise RuntimeError("proof package must contain eight faces")

    lines = ["8 3 7 6"]
    for face_index, (face, contribution) in enumerate(zip(faces, contributions)):
        if (
            not isinstance(face, dict)
            or face.get("face") != face_index
            or not isinstance(contribution, dict)
            or contribution.get("face") != face_index
        ):
            raise RuntimeError("proof package has invalid face identity")
        lines.append(
            f"{face_index} " + " ".join(str(value) for value in ORIENTED_FACES[face_index])
        )
        samples = face.get("samples")
        if not isinstance(samples, list) or len(samples) != 3:
            raise RuntimeError("fresh rows have invalid sample count")
        for sample_index, sample in enumerate(samples):
            if not isinstance(sample, dict) or sample.get("sample") != sample_index:
                raise RuntimeError("fresh rows have invalid sample order")
            lines.append(str(sample_index))
            rows = sample.get("rows")
            if not isinstance(rows, list) or len(rows) != 7:
                raise RuntimeError("fresh rows have invalid derivative count")
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
                lines.append(
                    " ".join(
                        f"{source} {format(float(value), '.17g')}"
                        for source, value in enumerate(row)
                    )
                )

        source_forces = contribution.get("source_forces")
        if not isinstance(source_forces, list) or len(source_forces) != 6:
            raise RuntimeError("face-force contribution cardinality is not six")
        for source, source_force in enumerate(source_forces):
            if (
                not isinstance(source_force, dict)
                or source_force.get("source_id") != source
                or not all(
                    finite_vector(source_force.get(kind))
                    for kind in ("fBend", "fArea", "fVolume")
                )
            ):
                raise RuntimeError("face-force source mapping is malformed")
            values = [
                component
                for kind in ("fBend", "fArea", "fVolume")
                for component in source_force[kind]
            ]
            lines.append(
                f"{source} "
                + " ".join(format(float(value), ".17g") for value in values)
            )
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
                    "OPENSUBDIV_ROOT is not set; the valence-4 source-keyed "
                    "kernel adapter proof is explicit opt-in only."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        proof = force_report(env)
        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-source-keyed-adapter-"
        ) as temporary:
            temp = Path(temporary)
            package = temp / "source_keyed_package.txt"
            binary = temp / "source_keyed_adapter"
            write_package(package, proof)
            build_harness(binary, env)
            result = run(
                [
                    str(binary),
                    str(FIXTURE / "vertices.csv"),
                    str(FIXTURE / "faces.csv"),
                    str(package),
                ],
                env,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "source-keyed adapter proof failed: "
                    + (result.stderr.strip() or result.stdout.strip())
                )
            adapter = json.loads(result.stdout)
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    passed = bool(
        adapter.get("passed")
        and adapter.get("proof_only")
        and adapter.get("not_production_routing")
        and not adapter.get("production_route_enabled")
        and not adapter.get("actual_production_force_path_executed")
        and adapter.get("backend_neutral_adapter_api")
        and adapter.get("guarded_topology_source_mapping_consumed")
        and adapter.get("proof_provided_opensubdiv_rows_consumed")
        and adapter.get("existing_force_algebra_contributions_consumed")
        and adapter.get("variable_cardinality_source_keyed")
        and adapter.get("canonicalized_by_original_source_id")
        and adapter.get("independent_fixed_source_layout_oracle_passed")
        and adapter.get("source_binding_permutation_invariant")
        and adapter.get("permuted_row_columns_canonicalized")
        and adapter.get("permuted_force_columns_canonicalized")
        and adapter.get("independent_permuted_scatter_oracle_passed")
        and adapter.get("duplicate_row_entries_aggregated_by_source_id")
        and adapter.get("production_one_rings_empty")
        and not adapter.get("production_one_rings_mutated")
        and isinstance(adapter.get("negative_gates"), dict)
        and adapter["negative_gates"].get("all_passed")
    )
    payload = {
        "status": "passed" if passed else "failed",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "adapter_passed": passed,
        "force_formula_proof_passed": proof.get("passed"),
        "adapter": adapter,
        "residual_boundary": adapter.get("residual_boundary"),
    }
    if not passed:
        payload["reason"] = "source-keyed adapter evidence did not pass"
    emit(payload, args.json)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
