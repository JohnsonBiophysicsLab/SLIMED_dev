#!/usr/bin/env python3
"""Characterize stock OpenSubdiv valence-5 energy and geometry observables."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FORCE_RUNNER = ROOT / "scripts/run_irregular_valence5_opensubdiv_force_parity.py"
SOURCE_ORDER = ROOT / "scripts/compare_irregular_valence5_opensubdiv_source_order_transpose.py"
PRODUCTION_REPORTER = ROOT / "experiments/irregular_valence5_fixture_parity.cpp"
CANDIDATE = ROOT / "experiments/irregular_valence5_option_b_energy_geometry.cpp"
ORACLE = ROOT / "experiments/irregular_valence5_option_b_energy_geometry_oracle.cpp"
PROBE = ROOT / "scripts/run_opensubdiv_probe.sh"
VERTICES = ROOT / "data/fixtures/closed_valence5/vertices.csv"
FACES = ROOT / "data/fixtures/closed_valence5/faces.csv"

VERTICES_SHA256 = "d0dae733433503f9e2aba4f8eda80fa2d6842d0f5a7b922d7ffce158f505cb45"
FACES_SHA256 = "561b3ec0c4aa6b1e684ef87c2738d8c20a474225bd4960a4a672d306a3e70327"
REVIEWED_RELATIVE_TOLERANCE = 5.0e-6
ORACLE_ABSOLUTE_TOLERANCE = 1.0e-10
CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE = {
    "global_energy": 3.0e-5,
    "per_face_energy": 2.0e-6,
    "per_face_geometry": 3.0e-7,
}
CANONICAL_OBSERVABLE_DIGEST_DECIMAL_PLACES = 9
EXPECTED_CANONICAL_OBSERVABLE_DIGEST = (
    "982d0be8559491842125cf5b56d35d06c4e90441c7f8e85214585a140f76622d"
)
EXPECTED_CANONICAL_OBSERVABLE_VECTOR = (
    1195.287406069441, 3.612219054282459, 0.04807107901254862, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 1198.9476962027359,
    59.470929543608904, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    59.470929543608904, 59.05703474041156, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 59.05703474041156, 58.20588492885429, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 58.20588492885429,
    60.33520200347365, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    60.33520200347365, 61.07814318557361, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 61.07814318557361, 60.022585919146366, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 60.022585919146366,
    59.49989757988647, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    59.49989757988647, 60.27834771556096, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 60.27834771556096, 60.49325584264206, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 60.49325584264206,
    60.01064739690943, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    60.01064739690943, 59.99961322005167, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 59.99961322005167, 61.34348053740901, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 61.34348053740901,
    59.493268352802986, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    59.493268352802986, 59.55320659369242, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 59.55320659369242, 58.840383028375165, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 58.840383028375165,
    59.78265894582053, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    59.78265894582053, 59.41118920311885, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 59.41118920311885, 59.15405534022174, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 59.15405534022174,
    60.06427779148267, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    60.06427779148267, 59.19334420039859, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 59.19334420039859,
    -0.5754263785576933, 0.5802618252033538, 0.576351192478727,
    -0.37383661739334767, 1.1198236368692893, 0.1657638383852225,
    -0.00021812729339885703, 0.9351426893448945, 0.35427122799527755,
    -0.3733922368226007, 1.1146736973211073, 0.027421483123508762,
    0.0014553869321248076, 0.9370378238228935, -0.34922485388948743,
    -0.36984434262820054, 1.1197854579863553, 0.027388274841248242,
    -0.5708355016977724, 0.586332633301022, -0.5747702785702667,
    -0.37728741333014104, 1.1153310046883438, 0.16403561511331677,
    -0.9319552363407263, 0.3625723931392343, 0.0008349792749937022,
    -0.3797287639867605, 1.1146219174899525, 0.38886011281828725,
    0.5808171494260145, 0.5764334914312305, 0.5747833234263502,
    -0.3779947040221421, 1.105431869973826, 0.16621688170886156,
    -0.35939493958234403, 0.0022126181456991615, 0.9331829304715902,
    -0.3732604667109776, 1.1238703246384174, 0.08134691968832666,
    -0.9319004697321506, -0.36271399961125744, -0.0002626766113501409,
    -0.37547569750036514, 1.1251556416985833, 0.39192503120921884,
    -0.3520869418362842, -0.003082314869570092, -0.9359622239831146,
    -0.3772587990699683, 1.1185119763005762, 0.0796141040121134,
    0.5764889694454233, 0.5816674982515315, -0.5738670487016644,
    -0.3772759011560625, 1.1094901799694603, 0.1650890443709176,
    0.5865379504820287, -0.5676388975378905, 0.5777190620416721,
    -0.37657441148816584, 1.1132723720404014, 0.1693584116136978,
    0.0013696449016835737, -0.933156489143269, 0.3594677883241438,
    -0.3803014288778475, 1.1161822958834144, 0.028033098531610064,
    0.0019777746332040767, -0.9335942254655769, -0.35832654183695295,
    -0.3728807976035492, 1.1260172713262921, 0.027947064263425078,
    0.5785839176403179, -0.5758320266967925, -0.5776314805117934,
    -0.3742057633477088, 1.1191874427043667, 0.167610098316236,
    0.9368494984322451, -0.34973250792290184, -0.0004361068770576653,
    -0.37263553200073624, 1.115050316399254, 0.3915169919332412,
    0.36154916970493306, 0.0031442765582062465, 0.932347741677213,
    -0.375918740516172, 1.113206379155256, 0.08194548480217517,
    -0.5791650345018016, -0.5743698214410552, 0.5785042532499629,
    -0.37211198070788065, 1.1291120167140503, 0.16753754131824505,
    -0.5710667126074156, -0.5837388269745908, -0.5771757025673274,
    -0.37111715141823004, 1.1302352551281447, 0.16555375821543752,
    0.3577355755925578, -0.0009862000142759105, -0.9338224056880373,
    -0.3764418371600378, 1.1154312128393082, 0.0805231061967143,
    0.9343873537536469, 0.35625871224190503, -5.565066438747544e-05,
    -0.37492994655637873, 1.108096962921183, 0.3875479089417413,
)
SAMPLE_PLAN = ((1.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0),
               (1.0 / 6.0, 4.0 / 6.0, 1.0 / 3.0),
               (4.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0))
ENERGY_CHANNELS = (
    "curvature", "area", "volume", "thickness", "tilt",
    "regularization", "harmonic_bond", "gag_scaffolding",
    "idealized_protein_lattice", "total",
)
GEOMETRY_CHANNELS = (
    "normal_x", "normal_y", "normal_z", "mean_curvature", "area",
    "legacy_volume",
)
REMAINING_BOUNDARY = (
    "scientific review of measured stock energy and geometry changes; "
    "Option B remains unselected and output evidence remains pending"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(text: str, label: str) -> dict[str, object]:
    try:
        payload = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"{label} emitted invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must emit one JSON object")
    return payload


def parse_process(result: subprocess.CompletedProcess[str], label: str) -> dict[str, object]:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit {result.returncode}: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    return strict_json(result.stdout, label)


def require_trailing_token_rejection(
    binary: Path, package: Path, env: dict[str, str], label: str,
    run_process,
) -> None:
    mutated = package.with_name(f"{package.stem}-{label}-trailing.txt")
    mutated.write_text(
        package.read_text(encoding="utf-8") + "TRAILING_NONNUMERIC_TOKEN\n",
        encoding="utf-8",
    )
    result = run_process([str(binary), str(mutated)], env)
    if result.returncode == 0:
        raise RuntimeError(f"{label} accepted trailing nonnumeric package data")


def finite_list(value: object, count: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != count:
        raise RuntimeError(f"{label} must contain exactly {count} values")
    output: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise RuntimeError(f"{label} must contain numeric non-boolean values")
        number = float(item)
        if not math.isfinite(number):
            raise RuntimeError(f"{label} must contain finite values")
        output.append(number)
    return output


def fixture_rows(path: Path, width: int, cast) -> list[list[object]]:
    rows = [
        [cast(token) for token in line.split(",")]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected_count = 12 if cast is float else 20
    if len(rows) != expected_count:
        raise RuntimeError("fixture cardinality drift")
    if any(len(row) != width for row in rows):
        raise RuntimeError("fixture row width drift")
    return rows


def expected_perturbed_coordinates(vertices: list[list[object]]) -> list[float]:
    values: list[float] = []
    for source, row in enumerate(vertices):
        index = float(source + 1)
        x, y, z = (float(item) for item in row)
        values.extend((
            x + 0.017 * math.sin(0.37 * index),
            y - 0.013 * math.cos(0.29 * index),
            z + 0.019 * math.sin(0.41 * index),
        ))
    return values


def validate_identity(
    production: dict[str, object], proof: dict[str, object]
) -> tuple[list[list[int]], list[float], list[dict[str, object]]]:
    if hashlib.sha256(VERTICES.read_bytes()).hexdigest() != VERTICES_SHA256:
        raise RuntimeError("approved valence-5 vertex fixture digest drift")
    if hashlib.sha256(FACES.read_bytes()).hexdigest() != FACES_SHA256:
        raise RuntimeError("approved valence-5 face fixture digest drift")
    vertices = fixture_rows(VERTICES, 3, float)
    faces = fixture_rows(FACES, 3, int)
    source_order = load_module(SOURCE_ORDER, "option_b_source_order")
    expected_rings = [list(row) for row in source_order.EXPECTED_ONE_RINGS]

    required_production = {
        "fixture": "closed_valence5_icosahedron",
        "scientific_stand_in_scope": "narrow_positive_depth_11_control",
        "vertex_count": 12,
        "face_count": 20,
        "eleven_control_face_count": 20,
        "all_valence_five": True,
        "all_faces_physical": True,
        "deterministic_duplicate_aggregation_shape": True,
        "active_face_ids": list(range(20)),
    }
    for key, expected in required_production.items():
        if production.get(key) != expected:
            raise RuntimeError(f"production identity {key} drift")
    rings = production.get("one_ring_source_ids")
    if not isinstance(rings, list) or rings != [source for row in expected_rings for source in row]:
        raise RuntimeError("production 20x11 source order drift")
    for ring in expected_rings:
        counts = Counter(ring)
        if sorted(counts.values()) != [1] * 7 + [2] * 2:
            raise RuntimeError("production duplicate-slot identity drift")

    coordinates = finite_list(
        production.get("scientific_coordinates"), 36,
        "production perturbed coordinates",
    )
    expected_coordinates = expected_perturbed_coordinates(vertices)
    if any(left != right for left, right in zip(coordinates, expected_coordinates)):
        raise RuntimeError("exact perturbed coordinate identity drift")

    required_proof = {
        "passed": True,
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_force_path_executed": False,
        "coordinate_mapping": "s=v,t=w,u=1-v-w",
        "row_order": ["position", "dv", "dw", "dvv", "dww", "dvw", "dwv"],
        "sample_count_per_face": 3,
        "quadrature_weight": 1.0 / 3.0,
    }
    for key, expected in required_proof.items():
        if proof.get(key) != expected:
            raise RuntimeError(f"OpenSubdiv proof identity {key} drift")
    proof_faces = proof.get("faces")
    if not isinstance(proof_faces, list) or len(proof_faces) != 20:
        raise RuntimeError("OpenSubdiv proof must contain twenty ordered faces")
    for face_index, record in enumerate(proof_faces):
        if not isinstance(record, dict):
            raise RuntimeError("OpenSubdiv face record must be an object")
        if record.get("fixture_face_index") != face_index or record.get("ptex_face_index") != face_index:
            raise RuntimeError("fixture/Ptex face order drift")
        if record.get("oriented_fixture_vertex_ids") != faces[face_index]:
            raise RuntimeError("ordered outward face orientation drift")
        if record.get("source_coverage_union") != sorted(set(expected_rings[face_index])):
            raise RuntimeError("per-face original source identity drift")
        samples = record.get("samples")
        if not isinstance(samples, list) or len(samples) != 3:
            raise RuntimeError("ordered sample cardinality drift")
        for sample_index, sample in enumerate(samples):
            if not isinstance(sample, dict) or sample.get("sample") != sample_index:
                raise RuntimeError("ordered sample identity drift")
            rows = sample.get("rows")
            if not isinstance(rows, list) or len(rows) != 7:
                raise RuntimeError("seven-row derivative identity drift")
            for row in rows:
                finite_list(row, 12, "OpenSubdiv source row")
            if rows[5] != rows[6]:
                raise RuntimeError("duplicated mixed-row identity drift")
    return faces, coordinates, proof_faces


def write_package(
    path: Path, production: dict[str, object], proof: dict[str, object]
) -> None:
    faces, coordinates, proof_faces = validate_identity(production, proof)
    parameters = finite_list(production.get("force_formula_parameters"), 8, "formula parameters")
    face_energy = finite_list(production.get("face_energy"), 200, "production face energy")
    regularization = [face_energy[10 * face + 5] for face in range(20)]
    lines = [
        "20 3 7 12",
        "PARAMETERS " + " ".join(format(value, ".17g") for value in parameters),
        "REGULARIZATION " + " ".join(format(value, ".17g") for value in regularization),
        "COORDINATES 12",
    ]
    for source in range(12):
        lines.append(f"{source} " + " ".join(format(coordinates[3 * source + axis], ".17g") for axis in range(3)))
    for face_index, record in enumerate(proof_faces):
        lines.append(f"FACE {face_index} {face_index} " + " ".join(str(value) for value in faces[face_index]))
        samples = record["samples"]
        for sample_index, sample in enumerate(samples):
            v, w, weight = SAMPLE_PLAN[sample_index]
            lines.append(f"SAMPLE {sample_index} {v:.17g} {w:.17g} {weight:.17g}")
            for row_index, row in enumerate(sample["rows"]):
                values = finite_list(row, 12, "OpenSubdiv source row")
                lines.append(f"ROW {row_index} " + " ".join(format(value, ".17g") for value in values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_face_energy(
    curvature: list[float], regularization: list[float],
) -> list[float]:
    face_energy: list[float] = []
    for bend, reg in zip(curvature, regularization):
        values = [bend, 0.0, 0.0, 0.0, 0.0, reg, 0.0, 0.0, 0.0, bend + reg]
        face_energy.extend(values)
    return face_energy


def expand(report: dict[str, object], label: str) -> dict[str, list[float]]:
    if report.get("status") != "passed":
        raise RuntimeError(f"{label} did not pass")
    global_energy = finite_list(
        report.get("global_energy"), 10, f"{label} independently emitted global energy"
    )
    curvature = finite_list(report.get("face_curvature_energy"), 20, f"{label} curvature")
    regularization = finite_list(report.get("face_regularization_energy"), 20, f"{label} regularization")
    normals = finite_list(report.get("face_normals"), 60, f"{label} normals")
    mean = finite_list(report.get("face_mean_curvature"), 20, f"{label} mean curvature")
    area = finite_list(report.get("face_area"), 20, f"{label} area")
    volume = finite_list(report.get("face_legacy_volume"), 20, f"{label} legacy volume")
    face_energy = build_face_energy(curvature, regularization)
    geometry = []
    for face in range(20):
        geometry.extend(normals[3 * face:3 * face + 3])
        geometry.extend((mean[face], area[face], volume[face]))
    return {"global_energy": global_energy, "face_energy": face_energy, "geometry": geometry}


def canonical_observable_vector(values: dict[str, list[float]]) -> list[float]:
    expected_lengths = {"global_energy": 10, "face_energy": 200, "geometry": 120}
    vector: list[float] = []
    for key in ("global_energy", "face_energy", "geometry"):
        current = values.get(key)
        if not isinstance(current, list) or len(current) != expected_lengths[key]:
            raise RuntimeError(f"canonical {key} cardinality drift")
        vector.extend(finite_list(current, expected_lengths[key], f"canonical {key}"))
    return vector


def canonical_observable_digest(values: dict[str, list[float]]) -> str:
    vector = canonical_observable_vector(values)
    encoded = "|".join(
        format(value, f".{CANONICAL_OBSERVABLE_DIGEST_DECIMAL_PLACES}e")
        for value in vector
    )
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def canonical_observable_location(index: int) -> dict[str, object]:
    if index < len(ENERGY_CHANNELS):
        return {"scope": "global_energy", "channel": ENERGY_CHANNELS[index]}
    index -= len(ENERGY_CHANNELS)
    face_energy_count = 20 * len(ENERGY_CHANNELS)
    if index < face_energy_count:
        return {
            "scope": "per_face_energy",
            "face": index // len(ENERGY_CHANNELS),
            "channel": ENERGY_CHANNELS[index % len(ENERGY_CHANNELS)],
        }
    index -= face_energy_count
    return {
        "scope": "per_face_geometry",
        "face": index // len(GEOMETRY_CHANNELS),
        "channel": GEOMETRY_CHANNELS[index % len(GEOMETRY_CHANNELS)],
    }


def validate_expected_canonical_observables(
    values: dict[str, list[float]], label: str,
) -> tuple[float, dict[str, object]]:
    actual = canonical_observable_vector(values)
    expected = finite_list(
        list(EXPECTED_CANONICAL_OBSERVABLE_VECTOR), 330,
        "reviewed expected canonical observable vector",
    )
    deltas = [abs(left - right) for left, right in zip(actual, expected)]
    tolerances = [
        CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE[
            canonical_observable_location(index)["scope"]
        ]
        for index in range(len(deltas))
    ]
    violations = [
        index for index, delta in enumerate(deltas)
        if delta > tolerances[index]
    ]
    if violations:
        index = max(
            violations,
            key=lambda current: deltas[current] / tolerances[current],
        )
    else:
        index = max(range(len(deltas)), key=deltas.__getitem__)
    location = canonical_observable_location(index)
    location.update({
        "expected": expected[index],
        "actual": actual[index],
        "delta": deltas[index],
        "tolerance": tolerances[index],
    })
    if violations:
        raise RuntimeError(
            f"{label} canonical observable drift at "
            f"{location['scope']}"
            + (f" face {location['face']}" if "face" in location else "")
            + f" channel {location['channel']}: expected={expected[index]}, "
            f"actual={actual[index]}, delta={deltas[index]}, "
            f"fixed_cross_platform_absolute_envelope="
            f"{tolerances[index]}"
        )
    return deltas[index], location


def validate_candidate_oracle_observables(
    candidate_values: dict[str, list[float]],
    oracle_values: dict[str, list[float]],
) -> dict[str, object]:
    per_key_deltas = {
        key: max(
            abs(left - right)
            for left, right in zip(candidate_values[key], oracle_values[key])
        )
        for key in ("global_energy", "face_energy", "geometry")
    }
    oracle_delta = max(per_key_deltas.values())
    if oracle_delta > ORACLE_ABSOLUTE_TOLERANCE:
        raise RuntimeError("candidate disagrees with independent long-double oracle")
    candidate_digest = canonical_observable_digest(candidate_values)
    oracle_digest = canonical_observable_digest(oracle_values)
    candidate_expected_delta, candidate_expected_location = (
        validate_expected_canonical_observables(candidate_values, "candidate")
    )
    oracle_expected_delta, oracle_expected_location = (
        validate_expected_canonical_observables(oracle_values, "oracle")
    )
    return {
        "candidate_oracle_max_abs_difference": oracle_delta,
        "candidate_oracle_global_energy_max_abs_difference": (
            per_key_deltas["global_energy"]
        ),
        "candidate_digest": candidate_digest,
        "oracle_digest": oracle_digest,
        "candidate_expected_max_abs_difference": candidate_expected_delta,
        "oracle_expected_max_abs_difference": oracle_expected_delta,
        "candidate_expected_maximum": candidate_expected_location,
        "oracle_expected_maximum": oracle_expected_location,
    }


def differences(current: list[float], stock: list[float], channels: tuple[str, ...], per_face: bool) -> tuple[list[float], dict[str, object], bool]:
    if len(current) != len(stock):
        raise RuntimeError("observable cardinality mismatch")
    deltas = [abs(left - right) for left, right in zip(current, stock)]
    index = max(range(len(deltas)), key=deltas.__getitem__)
    channel_count = len(channels)
    channel = channels[index % channel_count]
    location: dict[str, object] = {
        "channel": channel,
        "current": current[index],
        "stock": stock[index],
        "delta": deltas[index],
    }
    if per_face:
        location["face"] = index // channel_count
    scale = max(1.0, max(abs(value) for value in current))
    parity = max(deltas, default=0.0) <= REVIEWED_RELATIVE_TOLERANCE * scale
    return deltas, location, parity


def compare_reports(
    production: dict[str, object], candidate: dict[str, object],
    oracle: dict[str, object], proof: dict[str, object],
) -> dict[str, object]:
    validate_identity(production, proof)
    finite_list(production.get("force_formula_parameters"), 8, "formula parameters")
    candidate_values = expand(candidate, "candidate")
    oracle_values = expand(oracle, "oracle")
    oracle_validation = validate_candidate_oracle_observables(
        candidate_values, oracle_values
    )
    if oracle.get("independent_long_double_oracle") is not True or oracle.get("calls_element_energy_force_regular") is not False:
        raise RuntimeError("independent oracle boundary drift")
    if candidate.get("existing_slimed_regular_evaluator_executed") is not True:
        raise RuntimeError("candidate did not execute the existing regular evaluator")

    current_global = finite_list(production.get("global_energy"), 10, "current global energy")
    current_faces = finite_list(production.get("face_energy"), 200, "current face energy")
    current_geometry = []
    normals = finite_list(production.get("face_normals"), 60, "current normals")
    mean = finite_list(production.get("face_mean_curvature"), 20, "current mean curvature")
    area = finite_list(production.get("face_area"), 20, "current area")
    volume = finite_list(production.get("face_legacy_volume"), 20, "current legacy volume")
    for face in range(20):
        current_geometry.extend(normals[3 * face:3 * face + 3])
        current_geometry.extend((mean[face], area[face], volume[face]))

    global_deltas, global_location, global_parity = differences(
        current_global, candidate_values["global_energy"], ENERGY_CHANNELS, False)
    face_deltas, face_location, face_parity = differences(
        current_faces, candidate_values["face_energy"], ENERGY_CHANNELS, True)
    geometry_deltas, geometry_location, geometry_parity = differences(
        current_geometry, candidate_values["geometry"], GEOMETRY_CHANNELS, True)
    parity = global_parity and face_parity and geometry_parity
    blockers = [
        "stock OpenSubdiv valence-5 energy and geometry observables differ from current SLIMED semantics"
    ] if not parity else []
    blockers.extend((
        "Option B remains unselected and scientifically unapproved",
        "output-visible evidence and stock serial/OpenMP re-baselining remain pending",
    ))
    return {
        "status": "passed",
        "proof_kind": "valence5_option_b_energy_geometry_rebaseline",
        "proof_only": True,
        "assessment_scope": "observational_energy_geometry_rebaseline_only",
        "option_b_selected": False,
        "option_b_recommended": False,
        "stock_semantics_scientifically_approved": False,
        "implementation_work_authorized": False,
        "production_route_enabled": False,
        "valence5_opensubdiv_route_enabled": False,
        "not_production_routing": True,
        "output_visible_evidence_complete": False,
        "output_evidence_pending": True,
        "stock_serial_openmp_evidence_pending": True,
        "fixture": "closed_valence5_icosahedron",
        "fixture_vertices_sha256": VERTICES_SHA256,
        "fixture_faces_sha256": FACES_SHA256,
        "source_count": 12,
        "face_count": 20,
        "production_one_ring_shape": [20, 11],
        "opensubdiv_row_shape": [20, 3, 7, 12],
        "sample_plan": [list(sample) for sample in SAMPLE_PLAN],
        "coordinate_mapping": "s=v,t=w,u=1-v-w",
        "mixed_rows_duplicated": True,
        "reviewed_relative_tolerance": REVIEWED_RELATIVE_TOLERANCE,
        "oracle_absolute_tolerance": ORACLE_ABSOLUTE_TOLERANCE,
        "canonical_observable_cross_platform_absolute_envelope": (
            CANONICAL_OBSERVABLE_CROSS_PLATFORM_ABSOLUTE_ENVELOPE
        ),
        "canonical_observable_digest_decimal_places": (
            CANONICAL_OBSERVABLE_DIGEST_DECIMAL_PLACES
        ),
        "canonical_observable_component_count": 330,
        "canonical_observable_digest": oracle_validation["candidate_digest"],
        "oracle_canonical_observable_digest": (
            oracle_validation["oracle_digest"]
        ),
        "canonical_observable_digest_reporting_only": True,
        "canonical_observable_vector_tolerance_passed": True,
        "candidate_expected_canonical_max_abs_difference": (
            oracle_validation["candidate_expected_max_abs_difference"]
        ),
        "oracle_expected_canonical_max_abs_difference": (
            oracle_validation["oracle_expected_max_abs_difference"]
        ),
        "candidate_expected_canonical_maximum": (
            oracle_validation["candidate_expected_maximum"]
        ),
        "oracle_expected_canonical_maximum": (
            oracle_validation["oracle_expected_maximum"]
        ),
        "independent_long_double_oracle_passed": True,
        "candidate_oracle_max_abs_difference": (
            oracle_validation["candidate_oracle_max_abs_difference"]
        ),
        "candidate_oracle_global_energy_max_abs_difference": (
            oracle_validation[
                "candidate_oracle_global_energy_max_abs_difference"
            ]
        ),
        "energy_geometry_parity_passed": parity,
        "global_energy_channels": list(ENERGY_CHANNELS),
        "per_face_energy_channels": list(ENERGY_CHANNELS),
        "per_face_energy_semantics": "curvature_plus_regularization_only",
        "area_volume_constraint_energy_scope": "global_only",
        "geometry_channels": list(GEOMETRY_CHANNELS),
        "global_energy_current": current_global,
        "global_energy_stock": candidate_values["global_energy"],
        "global_energy_deltas": global_deltas,
        "global_energy_maximum": global_location,
        "per_face_energy_current": current_faces,
        "per_face_energy_stock": candidate_values["face_energy"],
        "per_face_energy_deltas": face_deltas,
        "per_face_energy_maximum": face_location,
        "per_face_geometry_current": current_geometry,
        "per_face_geometry_stock": candidate_values["geometry"],
        "per_face_geometry_deltas": geometry_deltas,
        "per_face_geometry_maximum": geometry_location,
        "sole_mask_causal_attribution_claimed": False,
        "decision_ready": False,
        "route_blockers": blockers,
        "remaining_boundary": REMAINING_BOUNDARY,
    }


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status: {payload['status']}")
        print(f"parity: {payload.get('energy_geometry_parity_passed')}")
        print(f"remaining boundary: {payload.get('remaining_boundary')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("OPENSUBDIV_ROOT"):
        payload = {"status": "skipped", "reason": "OPENSUBDIV_ROOT is not set; Option B energy/geometry proof is opt-in only."}
        emit(payload, args.json)
        return 2 if args.require_opensubdiv else 0
    force_runner = load_module(FORCE_RUNNER, "option_b_force_runner")
    env = os.environ.copy()
    try:
        with tempfile.TemporaryDirectory(prefix="slimed-option-b-observables-") as tmp:
            tmp_path = Path(tmp)
            production_binary = tmp_path / "production"
            candidate_binary = tmp_path / "candidate"
            oracle_binary = tmp_path / "oracle"
            package = tmp_path / "package.txt"
            force_runner.build(production_binary, PRODUCTION_REPORTER, env)
            force_runner.build(candidate_binary, CANDIDATE, env)
            oracle_result = force_runner.run([
                force_runner.compiler(), "-std=c++17", str(ORACLE), "-o", str(oracle_binary)
            ], env)
            if oracle_result.returncode != 0:
                raise RuntimeError("independent oracle compile failed: " + (oracle_result.stderr.strip() or oracle_result.stdout.strip()))
            production = parse_process(force_runner.run([str(production_binary)], env), "production reporter")
            wrapper = parse_process(force_runner.run([
                str(PROBE), "--json", "--require-opensubdiv", "--valence5-source-order-transpose-report"
            ], env), "OpenSubdiv row provider")
            output = wrapper.get("prototype_output")
            if not isinstance(output, list) or len(output) != 1 or not isinstance(output[0], str):
                raise RuntimeError("OpenSubdiv provider must emit exactly one proof string")
            proof_container = strict_json(output[0], "OpenSubdiv proof payload")
            proof = proof_container.get("valence5_source_order_transpose")
            if not isinstance(proof, dict):
                raise RuntimeError("OpenSubdiv source-order proof missing")
            write_package(package, production, proof)
            require_trailing_token_rejection(
                candidate_binary, package, env, "candidate", force_runner.run
            )
            require_trailing_token_rejection(
                oracle_binary, package, env, "oracle", force_runner.run
            )
            candidate = parse_process(force_runner.run([str(candidate_binary), str(package)], env), "candidate evaluator")
            oracle = parse_process(force_runner.run([str(oracle_binary), str(package)], env), "independent oracle")
            payload = compare_reports(production, candidate, oracle, proof)
            payload["candidate_trailing_token_rejected"] = True
            payload["oracle_trailing_token_rejected"] = True
    except (RuntimeError, OSError) as error:
        payload = {"status": "failed", "reason": str(error)}
        emit(payload, args.json)
        return 1
    emit(payload, args.json)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
