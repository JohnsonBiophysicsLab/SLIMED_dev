#!/usr/bin/env python3

import argparse
import json
import math
from pathlib import Path


CHANNELS = (
    "global_energy",
    "face_energy",
    "vertex_forces",
    "face_normals",
    "face_area",
    "face_legacy_volume",
    "face_mean_curvature",
)


def load_report(path):
    with Path(path).open(encoding="utf-8") as handle:
        report = json.load(handle)
    required_true = (
        "all_valence_five",
        "all_faces_physical",
        "deterministic_duplicate_aggregation_shape",
        "finite",
        "nonzero_force",
        "not_broader_valence_routing",
    )
    if not all(report.get(key, False) for key in required_true):
        raise ValueError(f"invalid fixture contract in {path}")
    if (
        report.get("fixture") != "closed_valence5_icosahedron"
        or report.get("scientific_stand_in_scope")
        != "narrow_positive_depth_11_control"
        or report.get("vertex_count") != 12
        or report.get("face_count") != 20
        or report.get("eleven_control_face_count") != 20
        or report.get("active_face_ids") != list(range(20))
        or len(report.get("one_ring_source_ids", [])) != 220
    ):
        raise ValueError(f"unexpected fixture shape in {path}")
    return report


def max_delta(left, right):
    if len(left) != len(right):
        raise ValueError(f"shape mismatch: {len(left)} != {len(right)}")
    if not left:
        return 0.0
    return max(abs(float(a) - float(b)) for a, b in zip(left, right))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", required=True)
    parser.add_argument("--openmp", required=True)
    parser.add_argument("--tolerance", type=float, default=1.0e-10)
    args = parser.parse_args()

    serial = load_report(args.serial)
    openmp = load_report(args.openmp)
    identity_matches = (
        serial.get("execution_mode") == "serial"
        and openmp.get("execution_mode") == "openmp"
        and serial["active_face_ids"] == openmp["active_face_ids"]
        and serial["one_ring_source_ids"] == openmp["one_ring_source_ids"]
    )
    deltas = {
        channel: max_delta(serial[channel], openmp[channel])
        for channel in CHANNELS
    }
    maximum = max(deltas.values())
    within_tolerance = math.isfinite(maximum) and maximum <= args.tolerance
    passed = identity_matches and within_tolerance
    summary = {
        "status": "passed" if passed else "failed",
        "proof_kind": "approved_closed_valence5_11_control_serial_openmp_parity",
        "scientific_stand_in": True,
        "scientific_stand_in_scope": "narrow_positive_depth_11_control",
        "not_broader_valence_routing": True,
        "tolerance": args.tolerance,
        "identity_matches": identity_matches,
        "channels": deltas,
        "max_abs_difference": maximum,
        "within_tolerance": within_tolerance,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
