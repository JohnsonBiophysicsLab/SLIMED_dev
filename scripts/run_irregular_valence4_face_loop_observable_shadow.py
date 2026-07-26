#!/usr/bin/env python3
"""Run the proof-only valence-4 face-loop observable shadow."""

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

import run_irregular_valence4_source_keyed_kernel_adapter as source_adapter


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = (
    ROOT / "experiments/irregular_valence4_face_loop_observable_shadow.cpp"
)
FIXTURE = ROOT / "data/fixtures/candidates/closed_valence4_octahedron"
PREDECESSOR = ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"
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
TOLERANCE = 1.0e-12


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
    for key in ("reason", "shadow_passed", "residual_boundary"):
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
            "face-loop observable shadow compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def parse_json(result: subprocess.CompletedProcess[str], label: str) -> dict:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} did not emit JSON: {error}") from error


def add(left: list[float], right: list[float]) -> list[float]:
    return [left[index] + right[index] for index in range(3)]


def subtract(left: list[float], right: list[float]) -> list[float]:
    return [left[index] - right[index] for index in range(3)]


def scale(vector: list[float], factor: float) -> list[float]:
    return [factor * component for component in vector]


def dot(left: list[float], right: list[float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def cross(left: list[float], right: list[float]) -> list[float]:
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def norm(vector: list[float]) -> float:
    return math.sqrt(dot(vector, vector))


def normalized(vector: list[float]) -> list[float]:
    magnitude = norm(vector)
    if magnitude == 0.0:
        raise RuntimeError("independent observable oracle found zero normal")
    return scale(vector, 1.0 / magnitude)


def evaluated_rows(
    rows: list[list[float]], coordinates: list[list[float]]
) -> list[list[float]]:
    return [
        [
            sum(rows[row][source] * coordinates[source][axis] for source in range(6))
            for axis in range(3)
        ]
        for row in range(7)
    ]


def face_observables(
    face: dict[str, object],
    coordinates: list[list[float]],
    k_curv: float,
    spontaneous_curvature: float,
) -> dict[str, object]:
    mean_curvature = 0.0
    bending_energy = 0.0
    weighted_normal = [0.0, 0.0, 0.0]
    area = 0.0
    full_volume = 0.0
    legacy_volume = 0.0
    samples = face.get("samples")
    if not isinstance(samples, list) or len(samples) != 3:
        raise RuntimeError("fresh OpenSubdiv rows omitted a face sample")
    for sample in samples:
        if not isinstance(sample, dict):
            raise RuntimeError("fresh OpenSubdiv sample is malformed")
        rows = sample.get("rows")
        if not isinstance(rows, list) or len(rows) != 7:
            raise RuntimeError("fresh OpenSubdiv sample row count drifted")
        values = evaluated_rows(rows, coordinates)
        x, a_1, a_2, a_11, a_22, a_12, a_21 = values
        xa = cross(a_1, a_2)
        sqa = norm(xa)
        if sqa == 0.0:
            raise RuntimeError("independent observable oracle found zero area")
        xa_1 = add(cross(a_11, a_2), cross(a_1, a_21))
        xa_2 = add(cross(a_12, a_2), cross(a_1, a_22))
        sqa_1 = dot(xa, xa_1) / sqa
        sqa_2 = dot(xa, xa_2) / sqa
        normal = scale(xa, 1.0 / sqa)
        a_31 = scale(
            subtract(scale(xa_1, sqa), scale(xa, sqa_1)),
            1.0 / (sqa * sqa),
        )
        a_32 = scale(
            subtract(scale(xa_2, sqa), scale(xa, sqa_2)),
            1.0 / (sqa * sqa),
        )
        contravariant_1 = scale(cross(a_2, normal), 1.0 / sqa)
        contravariant_2 = scale(cross(normal, a_1), 1.0 / sqa)
        curvature = 0.5 * (
            dot(contravariant_1, a_31) + dot(contravariant_2, a_32)
        )
        quadrature = 1.0 / 3.0
        half_quadrature = 0.5 * quadrature
        mean_curvature += half_quadrature * curvature
        bending_energy += (
            half_quadrature
            * 0.5
            * k_curv
            * sqa
            * (2.0 * curvature - spontaneous_curvature) ** 2
        )
        weighted_normal = add(weighted_normal, scale(normal, half_quadrature))
        area += half_quadrature * sqa
        full_volume += (1.0 / 6.0) * quadrature * dot(x, xa)
        legacy_volume += (1.0 / 6.0) * quadrature * x[0] * xa[0]
    return {
        "mean_curvature": mean_curvature,
        "bending_energy": bending_energy,
        "normal": normalized(weighted_normal),
        "area": area,
        "full_volume": full_volume,
        "legacy_visible_volume": legacy_volume,
    }


def package_observables(proof: dict[str, object]) -> tuple[list[dict], dict]:
    binding = proof.get("fresh_opensubdiv_row_binding")
    coordinate_records = proof.get("proof_coordinates")
    parameters = proof.get("parameters")
    energies = proof.get("energies")
    if (
        not isinstance(binding, dict)
        or not isinstance(coordinate_records, list)
        or not isinstance(parameters, dict)
        or not isinstance(energies, dict)
    ):
        raise RuntimeError("force proof omitted observable oracle inputs")
    faces = binding.get("faces")
    if not isinstance(faces, list) or len(faces) != 8:
        raise RuntimeError("force proof row tensor is not eight faces")
    coordinates = []
    for source, record in enumerate(coordinate_records):
        if (
            not isinstance(record, dict)
            or record.get("source_id") != source
            or not source_adapter.finite_vector(record.get("coordinate"))
        ):
            raise RuntimeError("force proof coordinate mapping drifted")
        coordinates.append([float(value) for value in record["coordinate"]])
    k_curv = float(parameters["kCurv"])
    spontaneous = float(parameters["spontCurv"])
    face_values = [
        face_observables(face, coordinates, k_curv, spontaneous)
        for face in faces
    ]
    global_area = sum(float(face["area"]) for face in face_values)
    global_full_volume = sum(float(face["full_volume"]) for face in face_values)
    global_legacy_volume = sum(
        float(face["legacy_visible_volume"]) for face in face_values
    )
    global_bending = sum(float(face["bending_energy"]) for face in face_values)
    area0 = float(parameters["area0"])
    volume0 = float(parameters["vol0"])
    area_energy = (
        0.0
        if float(parameters["uSurf"]) == 0.0 or area0 == 0.0
        else 0.5
        * (float(parameters["uSurf"]) / area0)
        * (global_area - area0) ** 2
    )
    volume_energy = (
        0.0
        if float(parameters["uVol"]) == 0.0 or volume0 == 0.0
        else 0.5
        * (float(parameters["uVol"]) / volume0)
        * (global_full_volume - volume0) ** 2
    )
    global_values = {
        "bending_energy": global_bending,
        "area": global_area,
        "full_volume": global_full_volume,
        "legacy_visible_volume": global_legacy_volume,
        "area_constraint_energy": area_energy,
        "volume_constraint_energy": volume_energy,
        "total_energy": global_bending + area_energy + volume_energy,
    }
    proof_deltas = {
        "bending_energy": abs(global_bending - float(energies["bending_energy"])),
        "area": abs(global_area - float(energies["area"])),
        "full_volume": abs(global_full_volume - float(energies["signed_volume"])),
        "area_constraint_energy": abs(
            area_energy - float(energies["area_constraint_energy"])
        ),
        "volume_constraint_energy": abs(
            volume_energy - float(energies["volume_constraint_energy"])
        ),
    }
    if max(proof_deltas.values()) > TOLERANCE:
        raise RuntimeError(
            "independent observable oracle drifted from force proof: "
            + json.dumps(proof_deltas, sort_keys=True)
        )
    return face_values, global_values


def write_package(path: Path, proof: dict[str, object]) -> None:
    source_adapter.write_package(path, proof)
    face_values, global_values = package_observables(proof)
    lines = [f"FACE_OBSERVABLES {len(face_values)}"]
    for face, values in enumerate(face_values):
        fields = [
            face,
            values["mean_curvature"],
            values["bending_energy"],
            *values["normal"],
            values["area"],
            values["full_volume"],
            values["legacy_visible_volume"],
        ]
        lines.append(" ".join(format(float(value), ".17g") for value in fields))
    lines.append(
        "GLOBAL_OBSERVABLES "
        + " ".join(
            format(float(global_values[key]), ".17g")
            for key in (
                "bending_energy",
                "area",
                "full_volume",
                "legacy_visible_volume",
                "area_constraint_energy",
                "volume_constraint_energy",
                "total_energy",
            )
        )
    )
    with path.open("a", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")


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
                    "OPENSUBDIV_ROOT is not set; the valence-4 face-loop "
                    "observable shadow is explicit opt-in only."
                ),
                "proof_only": True,
                "not_production_routing": True,
                "production_route_enabled": False,
                "actual_production_force_path_executed": False,
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        predecessor = parse_json(
            run(
                [str(PREDECESSOR), "--json", "--require-opensubdiv"],
                env,
            ),
            "source-keyed predecessor proof",
        )
        adapter = predecessor.get("adapter")
        if (
            predecessor.get("status") != "passed"
            or not isinstance(adapter, dict)
            or not adapter.get("source_binding_permutation_invariant")
            or not adapter.get("duplicate_row_entries_aggregated_by_source_id")
        ):
            raise RuntimeError(
                "source permutation or duplicate-row predecessor gate failed"
            )
        proof = source_adapter.force_report(env)
        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-face-loop-shadow-"
        ) as temporary:
            temp = Path(temporary)
            package = temp / "face_loop_observables.txt"
            binary = temp / "face_loop_observable_shadow"
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
                    "face-loop observable shadow failed: "
                    + (result.stderr.strip() or result.stdout.strip())
                )
            shadow = json.loads(result.stdout)
    except (KeyError, RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    thread_runs = shadow.get("thread_runs")
    requested = [1, 2, 3, 4, 8]
    teams_passed = bool(
        isinstance(thread_runs, list)
        and len(thread_runs) == len(requested)
        and all(
            isinstance(run_report, dict)
            and run_report.get("requested_threads") == expected
            and run_report.get("repeat_count", 0) >= 5
            and run_report.get("actual_threads") == [expected] * 5
            and run_report.get("passed")
            for expected, run_report in zip(requested, thread_runs)
        )
    )
    passed = bool(
        shadow.get("passed")
        and shadow.get("proof_only")
        and shadow.get("production_call_shadow")
        and shadow.get("not_production_routing")
        and not shadow.get("production_route_enabled")
        and not shadow.get("actual_production_force_path_executed")
        and not shadow.get("production_face_loop_executed")
        and shadow.get("actual_openmp_runtime")
        and shadow.get("guarded_topology_source_mapping_consumed")
        and shadow.get("source_keyed_kernel_helper_consumed")
        and shadow.get("scientific_force_algebra")
        == "Mesh::element_energy_force_regular"
        and shadow.get("independent_long_double_nested_force_oracle")
        and shadow.get("independent_raw_destination_formula")
        == "source * 9 + kind * 3 + axis"
        and shadow.get("candidate_slots_compared_raw")
        and shadow.get("candidate_collision_counts_compared_raw")
        and shadow.get("independent_exact_layout_sentinel_passed")
        and shadow.get("all_collision_counts_exactly_eight")
        and shadow.get("expected_collision_count_per_component") == 8
        and shadow.get("serial_oracle_parity_passed")
        and shadow.get("actual_openmp_serial_parity_passed")
        and shadow.get("source_coverage_binding_passed")
        and shadow.get("late_malformed_face_atomic_rejection")
        and shadow.get("late_malformed_complete_shadow_state_atomic")
        and shadow.get("nonfinite_output_negative_regression_passed")
        and shadow.get("all_face_force_and_observable_fields_finite_checked")
        and shadow.get("all_raw_force_slots_finite_checked")
        and shadow.get("all_global_fields_finite_checked")
        and shadow.get("collision_count_negative_regression_passed")
        and shadow.get("flipped_normal_orientation_rejected")
        and not shadow.get("production_one_rings_populated")
        and shadow.get("production_one_rings_empty_before")
        and shadow.get("production_one_rings_empty_after")
        and teams_passed
    )
    payload = {
        "status": "passed" if passed else "failed",
        "proof_only": True,
        "production_call_shadow": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_one_rings_populated": False,
        "source_binding_permutation_invariant": True,
        "duplicate_row_entries_aggregated_by_source_id": True,
        "shadow_passed": passed,
        "actual_openmp_team_contract_passed": teams_passed,
        "shadow": shadow,
        "residual_boundary": shadow.get("residual_boundary"),
    }
    if not passed:
        payload["reason"] = "face-loop observable shadow contract did not pass"
    emit(payload, args.json)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
