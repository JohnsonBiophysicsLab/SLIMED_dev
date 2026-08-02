#!/usr/bin/env python3
"""Characterize stock Option B accumulation with real serial/OpenMP replay."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ENERGY_RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py"
FORCE_HARNESS = ROOT / "experiments/irregular_valence5_opensubdiv_force_parity.cpp"
ACCUMULATION_HARNESS = ROOT / "experiments/irregular_valence5_option_b_serial_openmp.cpp"
SERIAL_OPENMP_ABSOLUTE_TOLERANCE = 1.0e-10
AGGREGATE_FORCE_ABSOLUTE_TOLERANCE = 1.0e-12
FIXED_THREAD_REPEATABILITY_ABSOLUTE_TOLERANCE = 1.0e-10
REQUESTED_THREAD_COUNTS = [1, 2, 4]
REPEATS_PER_THREAD_COUNT = 5


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def finite_list(values: object, count: int, label: str) -> list[float]:
    if (
        not isinstance(values, list)
        or len(values) != count
        or not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in values
        )
    ):
        raise RuntimeError(f"{label} must contain {count} finite numbers")
    return [float(value) for value in values]


def finite_nonnegative(value: object, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise RuntimeError(f"{label} must be a finite nonnegative number")
    return float(value)


def strict_json(text: str, label: str) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"{label} did not emit strict JSON: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must emit a JSON object")
    return value


def parse_last_json(result: subprocess.CompletedProcess[str], label: str) -> dict[str, object]:
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(
            f"{label} emitted no report: " + (result.stderr.strip() or "no stderr")
        )
    return strict_json(lines[-1], label)


def write_package(
    path: Path,
    energy_report: dict[str, object],
    force_candidate: dict[str, object],
) -> None:
    face_energy = finite_list(
        energy_report.get("per_face_energy_stock"), 20 * 10,
        "stock per-face energy",
    )
    face_geometry = finite_list(
        energy_report.get("per_face_geometry_stock"), 20 * 6,
        "stock per-face geometry",
    )
    per_face_forces = finite_list(
        force_candidate.get("per_face_source_forces"), 20 * 12 * 9,
        "stock per-face source forces",
    )
    aggregate_forces = finite_list(
        force_candidate.get("aggregate_source_forces"), 12 * 9,
        "stock aggregate source forces",
    )
    lines = [
        "COUNTS 20 12",
        "FACE_ENERGY " + " ".join(format(value, ".17g") for value in face_energy),
        "FACE_GEOMETRY " + " ".join(
            format(value, ".17g") for value in face_geometry
        ),
        "PER_FACE_SOURCE_FORCES " + " ".join(
            format(value, ".17g") for value in per_face_forces
        ),
        "AGGREGATE_SOURCE_FORCES " + " ".join(
            format(value, ".17g") for value in aggregate_forces
        ),
        "END",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def recompute_aggregate(per_face_forces: list[float]) -> list[float]:
    aggregate = [0.0] * (12 * 9)
    for face in range(20):
        for component in range(12 * 9):
            aggregate[component] += per_face_forces[face * 12 * 9 + component]
    return aggregate


def compare_reports(
    energy_report: dict[str, object],
    force_candidate: dict[str, object],
    force_report: dict[str, object],
    harness: dict[str, object],
) -> dict[str, object]:
    if (
        energy_report.get("status") != "passed"
        or energy_report.get("independent_long_double_oracle_passed") is not True
        or energy_report.get("canonical_observable_vector_tolerance_passed") is not True
        or energy_report.get("energy_geometry_parity_passed") is not False
    ):
        raise RuntimeError("energy/geometry scientific gate drift")
    if (
        force_report.get("status") != "passed"
        or force_report.get("force_parity_passed") is not False
        or force_candidate.get("status") != "passed"
        or force_candidate.get(
            "opensubdiv_rows_evaluated_by_existing_force_algebra"
        ) is not True
    ):
        raise RuntimeError("force scientific gate drift")
    if (
        harness.get("status") != "passed"
        or harness.get("actual_openmp_executed") is not True
        or harness.get("production_shape_replayed") is not True
        or harness.get("finite") is not True
        or harness.get("nonzero_stock_force") is not True
    ):
        raise RuntimeError("serial/OpenMP harness gate drift")
    if harness.get("requested_thread_counts") != REQUESTED_THREAD_COUNTS:
        raise RuntimeError("requested OpenMP thread-count coverage drift")
    if harness.get("actual_thread_counts") != REQUESTED_THREAD_COUNTS:
        raise RuntimeError("actual OpenMP thread-count coverage drift")
    if harness.get("repeats_per_thread_count") != REPEATS_PER_THREAD_COUNT:
        raise RuntimeError("OpenMP repeatability coverage drift")

    bounded_fields = (
        "max_serial_openmp_accumulation_difference",
        "max_curvature_force_difference",
        "max_area_force_difference",
        "max_volume_force_difference",
        "max_curvature_energy_sum_difference",
        "max_regularization_energy_sum_difference",
        "max_area_sum_difference",
        "max_legacy_volume_sum_difference",
    )
    deltas = {
        field: finite_nonnegative(harness.get(field), field)
        for field in bounded_fields
    }
    if any(value > SERIAL_OPENMP_ABSOLUTE_TOLERANCE for value in deltas.values()):
        raise RuntimeError("stock serial/OpenMP accumulation tolerance exceeded")
    repeatability = finite_nonnegative(
        harness.get("max_fixed_thread_repeatability_difference"),
        "fixed-thread repeatability difference",
    )
    if repeatability > FIXED_THREAD_REPEATABILITY_ABSOLUTE_TOLERANCE:
        raise RuntimeError("fixed-thread repeatability drift")
    publication = finite_nonnegative(
        harness.get("max_face_publication_difference"),
        "face publication difference",
    )
    if publication != 0.0:
        raise RuntimeError("face-indexed publication drift")

    per_face_forces = finite_list(
        force_candidate.get("per_face_source_forces"), 20 * 12 * 9,
        "stock per-face source forces",
    )
    expected_aggregate = finite_list(
        force_candidate.get("aggregate_source_forces"), 12 * 9,
        "stock aggregate source forces",
    )
    harness_aggregate = finite_list(
        harness.get("serial_aggregate_source_forces"), 12 * 9,
        "serial aggregate source forces",
    )
    recomputed = recompute_aggregate(per_face_forces)
    aggregate_delta = max(
        abs(left - right)
        for left, right in zip(expected_aggregate, recomputed)
    )
    harness_aggregate_delta = max(
        abs(left - right)
        for left, right in zip(harness_aggregate, recomputed)
    )
    harness_reported_aggregate_delta = finite_nonnegative(
        harness.get("serial_expected_aggregate_force_difference"),
        "serial expected aggregate force difference",
    )
    if max(
        aggregate_delta,
        harness_aggregate_delta,
        harness_reported_aggregate_delta,
    ) > AGGREGATE_FORCE_ABSOLUTE_TOLERANCE:
        raise RuntimeError("stock aggregate source force drift")

    face_energy = finite_list(
        energy_report.get("per_face_energy_stock"), 20 * 10,
        "stock per-face energy",
    )
    face_geometry = finite_list(
        energy_report.get("per_face_geometry_stock"), 20 * 6,
        "stock per-face geometry",
    )
    scalar_expectations = {
        "serial_curvature_energy_sum": sum(face_energy[0::10]),
        "serial_regularization_energy_sum": sum(face_energy[5::10]),
        "serial_area_sum": sum(face_geometry[4::6]),
        "serial_legacy_volume_sum": sum(face_geometry[5::6]),
    }
    scalar_deltas: dict[str, float] = {}
    for field, expected in scalar_expectations.items():
        actual_values = finite_list([harness.get(field)], 1, field)
        scalar_deltas[field] = abs(actual_values[0] - expected)
    if max(scalar_deltas.values()) > AGGREGATE_FORCE_ABSOLUTE_TOLERANCE:
        raise RuntimeError("stock scalar accumulation drift")

    return {
        "status": "passed",
        "proof_kind": "valence5_option_b_stock_serial_openmp_evidence",
        "proof_only": True,
        "assessment_scope": "stock_accumulation_and_repeatability_only",
        "option_b_selected": False,
        "option_b_recommended": False,
        "stock_semantics_scientifically_approved": False,
        "production_route_enabled": False,
        "valence5_opensubdiv_route_enabled": False,
        "output_contract_repair_authorized": False,
        "output_visible_evidence_complete": False,
        "stock_serial_openmp_accumulation_evidence_complete": True,
        "stock_fixed_thread_repeatability_evidence_complete": True,
        "stock_serial_openmp_evidence_pending": False,
        "actual_openmp_executed": True,
        "production_thread_buffer_shape_replayed": True,
        "requested_thread_counts": REQUESTED_THREAD_COUNTS,
        "actual_thread_counts": harness["actual_thread_counts"],
        "repeats_per_thread_count": REPEATS_PER_THREAD_COUNT,
        "serial_openmp_absolute_tolerance": SERIAL_OPENMP_ABSOLUTE_TOLERANCE,
        "fixed_thread_repeatability_absolute_tolerance": (
            FIXED_THREAD_REPEATABILITY_ABSOLUTE_TOLERANCE
        ),
        "max_serial_openmp_accumulation_difference": deltas[
            "max_serial_openmp_accumulation_difference"
        ],
        "max_fixed_thread_repeatability_difference": repeatability,
        "max_face_publication_difference": publication,
        "channel_maximum_differences": deltas,
        "aggregate_source_force_recomputed": True,
        "aggregate_source_force_max_abs_difference": aggregate_delta,
        "harness_aggregate_source_force_max_abs_difference": (
            harness_aggregate_delta
        ),
        "scalar_accumulation_max_abs_difference": max(scalar_deltas.values()),
        "input_energy_geometry_proof_passed": True,
        "input_energy_geometry_parity_passed": False,
        "input_force_characterization_passed": True,
        "input_force_parity_passed": False,
        "remaining_boundary": (
            "review and explicitly authorize an output-contract repair lane; "
            "Option B remains unselected"
        ),
    }


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        print(
            "serial/OpenMP complete: "
            f"{payload.get('stock_serial_openmp_accumulation_evidence_complete')}"
        )
        print(f"remaining boundary: {payload.get('remaining_boundary')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("OPENSUBDIV_ROOT"):
        payload = {
            "status": "skipped",
            "reason": (
                "OPENSUBDIV_ROOT is not set; Option B serial/OpenMP proof "
                "is opt-in only."
            ),
        }
        emit(payload, args.json)
        return 2 if args.require_opensubdiv else 0

    energy = load_module(ENERGY_RUNNER, "option_b_serial_openmp_energy")
    force_runner = energy.load_module(
        energy.FORCE_RUNNER, "option_b_serial_openmp_force"
    )
    env = os.environ.copy()
    try:
        with tempfile.TemporaryDirectory(prefix="slimed-option-b-serial-omp-") as tmp:
            tmp_path = Path(tmp)
            production_binary = tmp_path / "production"
            energy_binary = tmp_path / "energy"
            oracle_binary = tmp_path / "oracle"
            force_binary = tmp_path / "force"
            accumulation_binary = tmp_path / "accumulation"
            energy_package = tmp_path / "energy.txt"
            force_package = tmp_path / "force.txt"
            accumulation_package = tmp_path / "accumulation.txt"

            force_runner.build(production_binary, energy.PRODUCTION_REPORTER, env)
            force_runner.build(energy_binary, energy.CANDIDATE, env)
            force_runner.build(force_binary, FORCE_HARNESS, env)
            oracle_result = force_runner.run([
                force_runner.compiler(), "-std=c++17", str(energy.ORACLE),
                "-o", str(oracle_binary),
            ], env)
            if oracle_result.returncode != 0:
                raise RuntimeError(
                    "independent oracle compile failed: "
                    + (oracle_result.stderr.strip() or oracle_result.stdout.strip())
                )
            accumulation_compile = force_runner.run([
                force_runner.compiler(), "-std=c++17", "-fopenmp",
                str(ACCUMULATION_HARNESS), "-o", str(accumulation_binary),
            ], env)
            if accumulation_compile.returncode != 0:
                raise RuntimeError(
                    "serial/OpenMP harness compile failed: "
                    + (
                        accumulation_compile.stderr.strip()
                        or accumulation_compile.stdout.strip()
                    )
                )

            production = energy.parse_process(
                force_runner.run([str(production_binary)], env),
                "production reporter",
            )
            wrapper = energy.parse_process(force_runner.run([
                str(energy.PROBE), "--json", "--require-opensubdiv",
                "--valence5-source-order-transpose-report",
            ], env), "OpenSubdiv row provider")
            output = wrapper.get("prototype_output")
            if (
                not isinstance(output, list)
                or len(output) != 1
                or not isinstance(output[0], str)
            ):
                raise RuntimeError("OpenSubdiv provider omitted its proof string")
            proof_container = energy.strict_json(
                output[0], "OpenSubdiv proof payload"
            )
            proof = proof_container.get("valence5_source_order_transpose")
            if not isinstance(proof, dict) or proof.get("passed") is not True:
                raise RuntimeError("OpenSubdiv source-order proof did not pass")

            energy.write_package(energy_package, production, proof)
            force_runner.write_package(force_package, production, proof)
            candidate = energy.parse_process(
                force_runner.run([str(energy_binary), str(energy_package)], env),
                "stock energy evaluator",
            )
            oracle = energy.parse_process(
                force_runner.run([str(oracle_binary), str(energy_package)], env),
                "independent energy oracle",
            )
            energy_report = energy.compare_reports(
                production, candidate, oracle, proof
            )
            force_candidate = energy.parse_process(
                force_runner.run([str(force_binary), str(force_package)], env),
                "stock force evaluator",
            )
            force_report = force_runner.compare(production, force_candidate)
            write_package(accumulation_package, energy_report, force_candidate)
            harness_result = force_runner.run(
                [str(accumulation_binary), str(accumulation_package)], env
            )
            harness = parse_last_json(harness_result, "serial/OpenMP harness")
            payload = compare_reports(
                energy_report, force_candidate, force_report, harness
            )
    except (RuntimeError, OSError) as error:
        payload = {"status": "failed", "reason": str(error)}
        emit(payload, args.json)
        return 1

    emit(payload, args.json)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
