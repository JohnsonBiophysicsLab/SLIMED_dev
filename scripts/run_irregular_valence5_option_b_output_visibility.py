#!/usr/bin/env python3
"""Characterize real output visibility for stock Option B observables."""

from __future__ import annotations

import argparse
import csv
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
OUTPUT_HARNESS = ROOT / "experiments/irregular_valence5_option_b_output_visibility.cpp"
FORCE_HARNESS = ROOT / "experiments/irregular_valence5_opensubdiv_force_parity.cpp"
OUTPUT_FORCE_ROUNDTRIP_ABSOLUTE_TOLERANCE = 0.0
OUTPUT_RECORD_ENERGY_ROUNDTRIP_ABSOLUTE_TOLERANCE = 0.0


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


def parse_process(result: subprocess.CompletedProcess[str], label: str) -> dict[str, object]:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit {result.returncode}: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{label} emitted no output")
    return strict_json(lines[-1], label)


def run_in(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_output_package(
    path: Path,
    production: dict[str, object],
    proof: dict[str, object],
    stock: dict[str, list[float]],
    force_candidate: dict[str, object],
) -> None:
    coordinates = finite_list(
        production.get("scientific_coordinates"), 36, "scientific coordinates"
    )
    aggregate_forces = finite_list(
        force_candidate.get("aggregate_source_forces"),
        12 * 3 * 3,
        "stock aggregate source forces",
    )
    faces = proof.get("faces")
    if not isinstance(faces, list) or len(faces) != 20:
        raise RuntimeError("OpenSubdiv proof must contain twenty faces")

    lines = [
        "COUNTS 12 20",
        "COORDINATES " + " ".join(format(value, ".17g") for value in coordinates),
        "FACES",
    ]
    for face_index, face in enumerate(faces):
        if not isinstance(face, dict):
            raise RuntimeError("OpenSubdiv face record must be an object")
        oriented = face.get("oriented_fixture_vertex_ids")
        if (
            face.get("fixture_face_index") != face_index
            or not isinstance(oriented, list)
            or len(oriented) != 3
            or not all(isinstance(value, int) and not isinstance(value, bool) for value in oriented)
        ):
            raise RuntimeError("OpenSubdiv output face identity drift")
        lines.append(f"{face_index} " + " ".join(str(value) for value in oriented))
    lines.extend((
        "GLOBAL_ENERGY "
        + " ".join(format(value, ".17g") for value in stock["global_energy"]),
        "FACE_ENERGY "
        + " ".join(format(value, ".17g") for value in stock["face_energy"]),
        "FACE_GEOMETRY "
        + " ".join(format(value, ".17g") for value in stock["geometry"]),
        "AGGREGATE_FORCES "
        + " ".join(format(value, ".17g") for value in aggregate_forces),
        "END",
    ))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_csv(path: Path, label: str) -> list[list[str]]:
    if not path.is_file():
        raise RuntimeError(f"{label} was not written")
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [[field.strip() for field in row] for row in csv.reader(stream)]
    if not rows:
        raise RuntimeError(f"{label} is empty")
    return rows


def expected_mean_force(aggregate: list[float]) -> float:
    magnitudes = []
    for vertex in range(12):
        components = [
            sum(aggregate[vertex * 9 + kind * 3 + axis] for kind in range(3))
            for axis in range(3)
        ]
        magnitudes.append(math.sqrt(sum(value * value for value in components)))
    return sum(magnitudes) / len(magnitudes)


def compare_output_artifacts(
    energy_report: dict[str, object],
    force_candidate: dict[str, object],
    force_report: dict[str, object],
    harness: dict[str, object],
    energy_rows: list[list[str]],
    face_rows: list[list[str]],
) -> dict[str, object]:
    if energy_report.get("status") != "passed":
        raise RuntimeError("energy/geometry input proof did not pass")
    if force_report.get("status") != "passed":
        raise RuntimeError("force input proof did not pass")
    required_harness_flags = (
        "energy_force_writer_executed",
        "element_face_energy_writer_executed",
        "checkpoint_writer_executed",
        "checkpoint_loader_executed",
    )
    if harness.get("status") != "passed" or any(
        harness.get(key) is not True for key in required_harness_flags
    ):
        raise RuntimeError("real output writer harness did not pass")
    force_roundtrip = float(
        harness.get("checkpoint_total_force_roundtrip_max_abs_difference", math.inf)
    )
    energy_roundtrip = float(
        harness.get("checkpoint_record_energy_roundtrip_max_abs_difference", math.inf)
    )
    if force_roundtrip > OUTPUT_FORCE_ROUNDTRIP_ABSOLUTE_TOLERANCE:
        raise RuntimeError("checkpoint total-force roundtrip drift")
    if energy_roundtrip > OUTPUT_RECORD_ENERGY_ROUNDTRIP_ABSOLUTE_TOLERANCE:
        raise RuntimeError("checkpoint energy-record roundtrip drift")
    if harness.get("checkpoint_face_observables_preserved") is not False:
        raise RuntimeError("checkpoint face-observable coverage claim drift")

    global_stock = finite_list(
        energy_report.get("global_energy_stock"), 10, "stock global energy"
    )
    aggregate = finite_list(
        force_candidate.get("aggregate_source_forces"), 108,
        "stock aggregate source forces",
    )
    expected_energy_header = [
        "E_Curvature", "E_Area", "E_Regularization", "E_HarmonicBond",
        "E_GagScaffolding", "E_IdealizedProteinLattice",
        "E_Total ((pN.nm))", "Mean Force (pN)",
    ]
    if len(energy_rows) != 2 or energy_rows[0] != expected_energy_header:
        raise RuntimeError("EnergyForce.csv schema drift")
    energy_values = finite_list(
        [float(value) for value in energy_rows[1]], 8, "EnergyForce.csv row"
    )
    expected_energy_values = [
        global_stock[0], global_stock[1], global_stock[5], global_stock[6],
        global_stock[7], global_stock[8], global_stock[9],
        expected_mean_force(aggregate),
    ]
    energy_csv_delta = max(
        abs(left - right)
        for left, right in zip(energy_values, expected_energy_values)
    )

    expected_face_header = [
        "Face_index", "E_Curvature", "E_Area", "E_Regularization", "E_Total"
    ]
    if len(face_rows) != 21 or face_rows[0] != expected_face_header:
        raise RuntimeError("ElementFaceEnergy.csv header or row count drift")
    row_widths = sorted({len(row) for row in face_rows[1:]})
    if row_widths != [4]:
        raise RuntimeError("ElementFaceEnergy.csv legacy row width drift")
    face_stock = finite_list(
        energy_report.get("per_face_energy_stock"), 200, "stock face energy"
    )
    face_csv_delta = 0.0
    total_written_in_fourth_column = True
    for face, row in enumerate(face_rows[1:]):
        values = [float(value) for value in row]
        if int(values[0]) != face:
            raise RuntimeError("ElementFaceEnergy.csv face order drift")
        expected = [float(face), face_stock[face * 10],
                    face_stock[face * 10 + 1], face_stock[face * 10 + 9]]
        face_csv_delta = max(
            face_csv_delta,
            max(abs(left - right) for left, right in zip(values, expected)),
        )
        total_written_in_fourth_column = total_written_in_fourth_column and (
            abs(values[3] - expected[3]) <= 1.0e-3
        )
    if not total_written_in_fourth_column:
        raise RuntimeError("ElementFaceEnergy.csv fourth-column behavior drift")

    blockers = [
        "EnergyForce.csv omits global volume, thickness, and tilt channels and rounds stock values at default stream precision",
        "ElementFaceEnergy.csv declares five columns but emits four; regularization is omitted and total occupies the fourth column",
        "restart checkpoints preserve total vertex force but not separate bending, area, and volume force families",
        "no production output writer serializes face normals, mean curvature, area, or legacy volume",
    ]
    return {
        "status": "passed",
        "proof_kind": "valence5_option_b_output_visibility_characterization",
        "proof_only": True,
        "assessment_scope": "observational_output_visibility_only",
        "option_b_selected": False,
        "option_b_recommended": False,
        "stock_semantics_scientifically_approved": False,
        "production_route_enabled": False,
        "valence5_opensubdiv_route_enabled": False,
        "output_writers_executed_and_parsed": True,
        "output_characterization_complete": True,
        "output_visible_evidence_complete": False,
        "output_contract_repair_authorized": False,
        "stock_serial_openmp_evidence_pending": True,
        "energy_force_csv_header": energy_rows[0],
        "energy_force_csv_energy_channel_count": 7,
        "energy_force_csv_max_abs_serialization_difference": energy_csv_delta,
        "energy_force_csv_default_precision_loss_observed": energy_csv_delta > 1.0e-12,
        "energy_force_csv_omitted_global_channels": ["volume", "thickness", "tilt"],
        "element_face_energy_csv_header": face_rows[0],
        "element_face_energy_csv_header_width": 5,
        "element_face_energy_csv_data_row_width": 4,
        "element_face_energy_csv_schema_matches": False,
        "element_face_energy_csv_regularization_serialized": False,
        "element_face_energy_csv_total_in_unlabelled_fourth_value": True,
        "element_face_energy_csv_max_abs_serialization_difference": face_csv_delta,
        "checkpoint_total_force_roundtrip_passed": True,
        "checkpoint_total_force_roundtrip_max_abs_difference": force_roundtrip,
        "checkpoint_record_energy_roundtrip_passed": True,
        "checkpoint_record_energy_roundtrip_max_abs_difference": energy_roundtrip,
        "checkpoint_force_family_components_serialized": False,
        "checkpoint_face_observables_preserved": False,
        "face_normals_output_visible": False,
        "face_mean_curvature_output_visible": False,
        "face_area_output_visible": False,
        "face_legacy_volume_output_visible": False,
        "input_energy_geometry_proof_passed": True,
        "input_force_characterization_passed": True,
        "input_force_parity_passed": force_report.get("force_parity_passed"),
        "writer_blockers": blockers,
        "remaining_boundary": (
            "review and explicitly authorize an output-contract repair lane; "
            "Option B remains unselected and stock serial/OpenMP evidence remains pending"
        ),
    }


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        print(f"output complete: {payload.get('output_visible_evidence_complete')}")
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
            "reason": "OPENSUBDIV_ROOT is not set; Option B output proof is opt-in only.",
        }
        emit(payload, args.json)
        return 2 if args.require_opensubdiv else 0

    energy = load_module(ENERGY_RUNNER, "option_b_energy_output_input")
    force_runner = energy.load_module(energy.FORCE_RUNNER, "option_b_output_force_runner")
    env = os.environ.copy()
    try:
        with tempfile.TemporaryDirectory(prefix="slimed-option-b-output-") as tmp:
            tmp_path = Path(tmp)
            production_binary = tmp_path / "production"
            energy_binary = tmp_path / "energy"
            oracle_binary = tmp_path / "oracle"
            force_binary = tmp_path / "force"
            output_binary = tmp_path / "output"
            energy_row_package = tmp_path / "energy-rows.txt"
            force_row_package = tmp_path / "force-rows.txt"
            output_package = tmp_path / "output.txt"
            energy_csv = tmp_path / "EnergyForce.csv"
            checkpoint = tmp_path / "restart.chk"
            face_csv = tmp_path / "ElementFaceEnergy.csv"

            force_runner.build(production_binary, energy.PRODUCTION_REPORTER, env)
            force_runner.build(energy_binary, energy.CANDIDATE, env)
            force_runner.build(force_binary, FORCE_HARNESS, env)
            force_runner.build(output_binary, OUTPUT_HARNESS, env)
            oracle_result = force_runner.run([
                force_runner.compiler(), "-std=c++17", str(energy.ORACLE),
                "-o", str(oracle_binary),
            ], env)
            if oracle_result.returncode != 0:
                raise RuntimeError(
                    "independent oracle compile failed: "
                    + (oracle_result.stderr.strip() or oracle_result.stdout.strip())
                )

            production = energy.parse_process(
                force_runner.run([str(production_binary)], env), "production reporter"
            )
            wrapper = energy.parse_process(force_runner.run([
                str(energy.PROBE), "--json", "--require-opensubdiv",
                "--valence5-source-order-transpose-report",
            ], env), "OpenSubdiv row provider")
            output = wrapper.get("prototype_output")
            if not isinstance(output, list) or len(output) != 1 or not isinstance(output[0], str):
                raise RuntimeError("OpenSubdiv provider must emit exactly one proof string")
            proof_container = energy.strict_json(output[0], "OpenSubdiv proof payload")
            proof = proof_container.get("valence5_source_order_transpose")
            if not isinstance(proof, dict):
                raise RuntimeError("OpenSubdiv source-order proof missing")
            energy.write_package(energy_row_package, production, proof)
            force_runner.write_package(force_row_package, production, proof)
            candidate = energy.parse_process(
                force_runner.run([str(energy_binary), str(energy_row_package)], env),
                "stock energy evaluator",
            )
            oracle = energy.parse_process(
                force_runner.run([str(oracle_binary), str(energy_row_package)], env),
                "independent energy oracle",
            )
            energy_report = energy.compare_reports(production, candidate, oracle, proof)
            force_candidate = energy.parse_process(
                force_runner.run([str(force_binary), str(force_row_package)], env),
                "stock force evaluator",
            )
            force_report = force_runner.compare(production, force_candidate)
            stock = energy.expand(candidate, "stock output input")
            write_output_package(
                output_package, production, proof, stock, force_candidate
            )
            harness_result = run_in(
                [str(output_binary), str(output_package), str(energy_csv), str(checkpoint)],
                tmp_path,
                env,
            )
            harness = parse_process(harness_result, "real output writer harness")
            payload = compare_output_artifacts(
                energy_report,
                force_candidate,
                force_report,
                harness,
                read_csv(energy_csv, "EnergyForce.csv"),
                read_csv(face_csv, "ElementFaceEnergy.csv"),
            )
    except (RuntimeError, OSError, ValueError) as error:
        payload = {"status": "failed", "reason": str(error)}
        emit(payload, args.json)
        return 1
    emit(payload, args.json)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
