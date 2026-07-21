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
    if not report.get("finite", False):
        raise ValueError(f"non-finite snapshot: {path}")
    if report.get("vertex_count", 0) <= 0 or not report.get("active_face_ids"):
        raise ValueError(f"empty executable snapshot: {path}")
    return report


def max_delta(left, right):
    if len(left) != len(right):
        raise ValueError(f"shape mismatch: {len(left)} != {len(right)}")
    if not left:
        return 0.0
    return max(abs(float(a) - float(b)) for a, b in zip(left, right))


def compare(left, right, tolerance):
    if left["vertex_count"] != right["vertex_count"]:
        raise ValueError("vertex count mismatch")
    if left["active_face_ids"] != right["active_face_ids"]:
        raise ValueError("active face identity mismatch")
    deltas = {channel: max_delta(left[channel], right[channel]) for channel in CHANNELS}
    maximum = max(deltas.values())
    return {
        "channels": deltas,
        "max_abs_difference": maximum,
        "within_tolerance": math.isfinite(maximum) and maximum <= tolerance,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial-direct", required=True)
    parser.add_argument("--serial-candidate", required=True)
    parser.add_argument("--openmp-direct", required=True)
    parser.add_argument("--openmp-candidate", required=True)
    parser.add_argument("--tolerance", type=float, default=5.0e-6)
    args = parser.parse_args()

    reports = {
        "serial_direct": load_report(args.serial_direct),
        "serial_candidate": load_report(args.serial_candidate),
        "openmp_direct": load_report(args.openmp_direct),
        "openmp_candidate": load_report(args.openmp_candidate),
    }
    expected_modes = {
        "serial_direct": ("serial", False, False),
        "serial_candidate": ("serial", True, True),
        "openmp_direct": ("openmp", False, False),
        "openmp_candidate": ("openmp", True, True),
    }
    mode_checks = {}
    for name, (execution_mode, requested, installed) in expected_modes.items():
        report = reports[name]
        expected_candidate_faces = len(report["active_face_ids"]) if requested else 0
        mode_checks[name] = (
            report.get("execution_mode") == execution_mode
            and report.get("candidate_rows_requested") is requested
            and report.get("candidate_rows_installed_in_diagnostic_build") is installed
            and report.get("candidate_shape_face_count") == expected_candidate_faces
            and report.get("not_production_routing") is True
        )

    comparisons = {
        "serial_direct_vs_candidate": compare(
            reports["serial_direct"], reports["serial_candidate"], args.tolerance
        ),
        "openmp_direct_vs_candidate": compare(
            reports["openmp_direct"], reports["openmp_candidate"], args.tolerance
        ),
        "direct_serial_vs_openmp": compare(
            reports["serial_direct"], reports["openmp_direct"], args.tolerance
        ),
        "candidate_serial_vs_openmp": compare(
            reports["serial_candidate"], reports["openmp_candidate"], args.tolerance
        ),
    }
    passed = all(mode_checks.values()) and all(
        item["within_tolerance"] for item in comparisons.values()
    )
    summary = {
        "status": "passed" if passed else "failed",
        "proof_kind": "disabled_double_row_serial_openmp_executable_output_parity",
        "not_production_routing": True,
        "route_activation_allowed": False,
        "tolerance": args.tolerance,
        "mode_checks": mode_checks,
        "comparisons": comparisons,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
