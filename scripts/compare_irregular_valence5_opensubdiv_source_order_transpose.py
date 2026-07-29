#!/usr/bin/env python3
"""Compare production valence-5 source order with proof-only OpenSubdiv rows."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path


EXPECTED_ONE_RINGS = (
    (7, 10, 0, 1, 2, 11, 5, 9, 2, 4, 9),
    (10, 11, 0, 7, 4, 5, 1, 8, 4, 9, 8),
    (11, 5, 0, 10, 9, 1, 7, 6, 9, 8, 6),
    (5, 1, 0, 11, 8, 7, 10, 2, 8, 6, 2),
    (1, 7, 0, 5, 6, 10, 11, 4, 6, 2, 4),
    (7, 0, 1, 8, 11, 5, 9, 3, 11, 4, 3),
    (1, 0, 5, 9, 10, 11, 4, 3, 10, 2, 3),
    (5, 0, 11, 4, 7, 10, 2, 3, 7, 6, 3),
    (11, 0, 10, 2, 1, 7, 6, 3, 1, 8, 3),
    (10, 0, 7, 6, 5, 1, 8, 3, 5, 9, 3),
    (6, 8, 3, 2, 1, 9, 4, 11, 1, 5, 11),
    (8, 9, 3, 6, 5, 4, 2, 10, 5, 11, 10),
    (9, 4, 3, 8, 11, 2, 6, 7, 11, 10, 7),
    (4, 2, 3, 9, 10, 6, 8, 1, 10, 7, 1),
    (2, 6, 3, 4, 7, 8, 9, 5, 7, 1, 5),
    (2, 3, 4, 11, 8, 9, 5, 0, 8, 1, 0),
    (6, 3, 2, 10, 9, 4, 11, 0, 9, 5, 0),
    (8, 3, 6, 7, 4, 2, 10, 0, 4, 11, 0),
    (9, 3, 8, 1, 2, 6, 7, 0, 2, 10, 0),
    (4, 3, 9, 5, 6, 8, 1, 0, 6, 7, 0),
)


def load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def split_one_rings(flattened: list[int]) -> list[list[int]]:
    if len(flattened) != 220:
        raise ValueError("production report must contain exactly 220 source slots")
    return [flattened[index : index + 11] for index in range(0, 220, 11)]


def fixture_coordinates(path: Path) -> list[list[float]]:
    coordinates = [
        [float(value) for value in line.split(",")]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(coordinates) != 12 or any(len(row) != 3 for row in coordinates):
        raise ValueError("fixture must contain exactly twelve 3D coordinates")
    return coordinates


def compare_reports(
    production: dict[str, object],
    wrapper: dict[str, object],
    coordinates: list[list[float]],
    transpose_tolerance: float = 5.0e-6,
    scatter_tolerance: float = 1.0e-12,
) -> dict[str, object]:
    errors: list[str] = []
    if production.get("fixture") != "closed_valence5_icosahedron":
        errors.append("unexpected production fixture identity")
    if production.get("active_face_ids") != list(range(20)):
        errors.append("production face identity/order drift")

    production_rings = split_one_rings(production.get("one_ring_source_ids", []))
    exact_order = tuple(tuple(row) for row in production_rings) == EXPECTED_ONE_RINGS
    if not exact_order:
        errors.append("production 20x11 one-ring source order drift")

    if wrapper.get("status") != "passed":
        errors.append("OpenSubdiv wrapper did not pass")
        proof = {}
    else:
        output = wrapper.get("prototype_output", [])
        if len(output) != 1:
            errors.append("OpenSubdiv wrapper must emit exactly one proof report")
            proof = {}
        else:
            proof = json.loads(output[0]).get(
                "valence5_source_order_transpose", {}
            )

    faces = proof.get("faces", [])
    if len(faces) != 20:
        errors.append("OpenSubdiv proof must emit exactly twenty faces")

    source_sets_match = True
    duplicate_shape_passed = True
    all_face_transposes_passed = True
    max_scatter_delta = 0.0
    max_independent_dot_delta = 0.0
    slot_component_count = 0

    for face_index, ring in enumerate(production_rings):
        counts = Counter(ring)
        duplicate_shape_passed &= (
            len(ring) == 11
            and len(counts) == 9
            and sorted(counts.values()) == [1] * 7 + [2] * 2
        )
        if face_index >= len(faces):
            continue
        face = faces[face_index]
        face_sources = face.get("source_coverage_union", [])
        expected_sources = sorted(counts)
        current_source_match = (
            face.get("fixture_face_index") == face_index
            and face.get("ptex_face_index") == face_index
            and face_sources == expected_sources
        )
        source_sets_match &= current_source_match

        source_components = face.get("backprojected_source_components", [])
        if len(source_components) != 36:
            errors.append(
                f"face {face_index} must emit 36 source backprojection components"
            )
            continue

        slot_components: list[float] = []
        rescattered = [0.0] * 36
        occurrence_seen: Counter[int] = Counter()
        for source_id in ring:
            occurrence = occurrence_seen[source_id]
            occurrence_seen[source_id] += 1
            multiplicity = counts[source_id]
            if multiplicity == 1:
                fraction = 1.0
            else:
                fraction = (1.0 / 3.0) if occurrence == 0 else (2.0 / 3.0)
            for axis in range(3):
                component = float(source_components[3 * source_id + axis])
                slot_value = fraction * component
                slot_components.append(slot_value)
                rescattered[3 * source_id + axis] += slot_value
        slot_component_count += len(slot_components)
        scatter_delta = max(
            abs(float(left) - right)
            for left, right in zip(source_components, rescattered)
        )
        max_scatter_delta = max(max_scatter_delta, scatter_delta)

        independent_control_dot = sum(
            coordinates[source_id][axis]
            * float(source_components[3 * source_id + axis])
            for source_id in range(12)
            for axis in range(3)
        )
        control_dot_delta = abs(
            independent_control_dot - float(face.get("weighted_control_dot", math.nan))
        )
        sample_dot_delta = abs(
            independent_control_dot - float(face.get("weighted_sample_dot", math.nan))
        )
        max_independent_dot_delta = max(
            max_independent_dot_delta, control_dot_delta, sample_dot_delta
        )
        all_face_transposes_passed &= bool(
            face.get("weighted_transpose_passed")
        )

    if not source_sets_match:
        errors.append("per-face OpenSubdiv source sets do not match production one-rings")
    if not duplicate_shape_passed:
        errors.append("production duplicate-slot shape drift")
    if max_scatter_delta > scatter_tolerance:
        errors.append("duplicate-slot re-scatter does not preserve source forces")
    if max_independent_dot_delta > transpose_tolerance:
        errors.append("independent weighted-transpose oracle mismatch")
    if not all_face_transposes_passed:
        errors.append("one or more OpenSubdiv face transpose checks failed")

    required_proof_flags = (
        proof.get("passed") is True
        and proof.get("proof_only") is True
        and proof.get("not_production_routing") is True
        and proof.get("production_route_enabled") is False
        and proof.get("production_force_path_executed") is False
    )
    if not required_proof_flags:
        errors.append("proof boundary flags are incomplete or inconsistent")

    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "approved_valence5_per_face_source_order_weighted_transpose",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "existing_dependency_free_production_baseline_executed": True,
        "opensubdiv_production_force_path_executed": False,
        "production_face_count": len(production_rings),
        "production_source_slots_per_face": 11,
        "production_unique_sources_per_face": 9,
        "exact_production_one_ring_order_match": exact_order,
        "per_face_opensubdiv_source_sets_match": source_sets_match,
        "duplicate_slot_shape_passed": duplicate_shape_passed,
        "duplicate_slot_split_rule": "first duplicate occurrence 1/3, second 2/3",
        "slot_backprojection_component_count": slot_component_count,
        "duplicate_slot_rescatter_max_abs_difference": max_scatter_delta,
        "independent_weighted_transpose_max_abs_difference": (
            max_independent_dot_delta
        ),
        "all_face_weighted_transposes_passed": all_face_transposes_passed,
        "independent_transpose_tolerance": transpose_tolerance,
        "duplicate_slot_rescatter_tolerance": scatter_tolerance,
        "remaining_boundary": (
            "actual fBend/fArea/fVolume parity against the positive-depth "
            "subdivision-matrix route"
        ),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--opensubdiv", type=Path, required=True)
    parser.add_argument("--vertices", type=Path, required=True)
    parser.add_argument("--transpose-tolerance", type=float, default=5.0e-6)
    parser.add_argument("--scatter-tolerance", type=float, default=1.0e-12)
    args = parser.parse_args()
    report = compare_reports(
        load_json(args.production),
        load_json(args.opensubdiv),
        fixture_coordinates(args.vertices),
        args.transpose_tolerance,
        args.scatter_tolerance,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
