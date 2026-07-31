#!/usr/bin/env python3
"""Assess the bounded scientific re-baselining work required by Option B."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
POST_GATE_RUNNER = (
    ROOT / "scripts/run_irregular_valence5_post_option_d_architecture_gate.py"
)
PR151_MERGE_COMMIT = "38a745d74880da05f1c50e80798e6bbddcc42c41"
REVIEWED_TOLERANCE = 5.0e-6
EXPECTED_FORCE_MAXIMA = {
    "fBend": 7.108303140663388,
    "fArea": 0.46106761515265404,
    "fVolume": 0.062309089012307695,
}
EXPECTED_ROW_MAXIMUM = 0.7357563654581705
CURRENT_SERIAL_OMP_TOLERANCE = 1.0e-10
EXPECTED_CURRENT_SERIAL_OMP_CHANNELS = (
    "global_energy",
    "face_energy",
    "vertex_forces",
    "face_normals",
    "face_area",
    "face_legacy_volume",
    "face_mean_curvature",
)
FORCE_BLOCKER = (
    "direct whole-Ptex OpenSubdiv rows do not match the existing "
    "positive-depth 11=4+3+4 force composition"
)
ROW_BLOCKER = (
    "composed OpenSubdiv rows do not reproduce the positive-depth SLIMED rows"
)
REMAINING_BOUNDARY = (
    "review and explicitly authorize the proposed stock OpenSubdiv "
    "valence-5 physical re-baselining plan; Option B remains unselected"
)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} did not contain a JSON object")
    return payload


def _close(left: object, right: float) -> bool:
    return (
        isinstance(left, (int, float))
        and math.isfinite(float(left))
        and math.isclose(float(left), right, rel_tol=0.0, abs_tol=1.0e-15)
    )


def evaluate(
    *,
    post_gate: dict[str, object] | None = None,
    force_report: dict[str, object],
    composition_report: dict[str, object],
    current_serial_openmp_report: dict[str, object],
    option_b_selected: bool = False,
    option_b_recommended: bool = False,
    stock_semantics_scientifically_approved: bool = False,
    physical_rebaselining_plan_authorized: bool = False,
    implementation_work_authorized: bool = False,
    production_route_enabled: bool = False,
) -> dict[str, object]:
    if post_gate is None:
        post_gate = _load_module(
            POST_GATE_RUNNER, "valence5_post_option_d_gate"
        ).evaluate()

    errors: list[str] = []
    if post_gate.get("status") != "passed":
        errors.append("PR151 post-Option-D gate did not pass")
    if post_gate.get("decision_selected") is not False:
        errors.append("PR151 no-selection boundary drift")
    if post_gate.get("selected_option") is not None:
        errors.append("PR151 selected-option boundary drift")
    if post_gate.get("scientific_approval_granted") is not False:
        errors.append("PR151 scientific-approval boundary drift")
    if post_gate.get("physical_rebaselining_plan_authorized") is not False:
        errors.append("PR151 re-baselining authorization boundary drift")

    expected_force_fields = {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_force_parity_diagnostic",
        "force_parity_passed": False,
        "relative_tolerance": REVIEWED_TOLERANCE,
        "face_count": 20,
        "source_count": 12,
        "force_component_count": 2160,
        "production_route_enabled": False,
        "production_scatter_executed": False,
    }
    for key, expected in expected_force_fields.items():
        if force_report.get(key) != expected:
            errors.append(f"force predecessor {key} drift")
    if force_report.get("route_blockers") != [FORCE_BLOCKER]:
        errors.append("force predecessor blocker drift")
    maxima = force_report.get("max_abs_force_difference_by_kind")
    if not isinstance(maxima, dict):
        errors.append("force predecessor maxima missing")
    else:
        for key, expected in EXPECTED_FORCE_MAXIMA.items():
            if not _close(maxima.get(key), expected):
                errors.append(f"force predecessor {key} residual drift")
    if not _close(
        force_report.get("max_abs_force_difference"),
        EXPECTED_FORCE_MAXIMA["fBend"],
    ):
        errors.append("force predecessor maximum residual drift")

    expected_composition_fields = {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_integration_composition",
        "composed_row_parity_passed": False,
        "reviewed_absolute_tolerance": REVIEWED_TOLERANCE,
        "row_component_count": 30240,
        "domain_count": 6,
        "positive_depth": 2,
        "extraordinary_vertex_mask_policy_mismatch": True,
        "mask_policy_causal_sufficiency_proven": False,
        "production_route_enabled": False,
        "production_scatter_executed": False,
    }
    for key, expected in expected_composition_fields.items():
        if composition_report.get(key) != expected:
            errors.append(f"composition predecessor {key} drift")
    if composition_report.get("route_blockers") != [ROW_BLOCKER]:
        errors.append("composition predecessor blocker drift")
    if not _close(
        composition_report.get("max_abs_row_difference"),
        EXPECTED_ROW_MAXIMUM,
    ):
        errors.append("composition predecessor maximum residual drift")
    if not _close(
        composition_report.get("production_valence5_vertex_edge_weight"),
        0.075,
    ) or not _close(
        composition_report.get("production_valence5_vertex_center_weight"),
        0.625,
    ):
        errors.append("production valence-5 mask drift")
    if not _close(
        composition_report.get("opensubdiv_valence5_vertex_edge_weight"),
        0.08409321892578289,
    ) or not _close(
        composition_report.get("opensubdiv_valence5_vertex_center_weight"),
        0.5795339053710855,
    ):
        errors.append("stock OpenSubdiv valence-5 mask drift")

    expected_serial_openmp_fields = {
        "status": "passed",
        "proof_kind": "approved_closed_valence5_11_control_serial_openmp_parity",
        "identity_matches": True,
        "within_tolerance": True,
        "scientific_stand_in": True,
        "scientific_stand_in_scope": "narrow_positive_depth_11_control",
        "not_broader_valence_routing": True,
        "tolerance": CURRENT_SERIAL_OMP_TOLERANCE,
    }
    for key, expected in expected_serial_openmp_fields.items():
        if current_serial_openmp_report.get(key) != expected:
            errors.append(f"current SLIMED serial/OpenMP {key} drift")
    channels = current_serial_openmp_report.get("channels")
    if (
        not isinstance(channels, dict)
        or set(channels) != set(EXPECTED_CURRENT_SERIAL_OMP_CHANNELS)
    ):
        errors.append("current SLIMED serial/OpenMP channels missing")
    else:
        channel_values = []
        for key in EXPECTED_CURRENT_SERIAL_OMP_CHANNELS:
            value = channels.get(key)
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0.0
                or float(value) > CURRENT_SERIAL_OMP_TOLERANCE
            ):
                errors.append(
                    f"current SLIMED {key} baseline exceeds reviewed tolerance"
                )
            else:
                channel_values.append(float(value))
        maximum = current_serial_openmp_report.get("max_abs_difference")
        if (
            not isinstance(maximum, (int, float))
            or not math.isfinite(float(maximum))
            or float(maximum) < 0.0
            or float(maximum) > CURRENT_SERIAL_OMP_TOLERANCE
        ):
            errors.append(
                "current SLIMED serial/OpenMP maximum exceeds reviewed tolerance"
            )
        elif channel_values and float(maximum) != max(channel_values):
            errors.append(
                "current SLIMED serial/OpenMP maximum does not bind channel deltas"
            )

    if option_b_selected:
        errors.append("this assessment cannot select Option B")
    if option_b_recommended:
        errors.append("this assessment cannot recommend Option B")
    if stock_semantics_scientifically_approved:
        errors.append("this assessment cannot approve changed scientific semantics")
    if physical_rebaselining_plan_authorized:
        errors.append("this assessment cannot authorize the proposed plan")
    if implementation_work_authorized:
        errors.append("this assessment cannot authorize implementation")
    if production_route_enabled:
        errors.append("this assessment cannot enable production routing")

    channels_plan = [
        {
            "id": "force",
            "state": "characterized_non_parity",
            "acceptance": (
                "scientific review must explicitly accept or reject the "
                "measured stock-semantics force changes"
            ),
        },
        {
            "id": "energy",
            "state": "pending_stock_vs_current_rebaseline",
            "acceptance": "global and per-face energy deltas must be characterized",
        },
        {
            "id": "geometry",
            "state": "pending_stock_vs_current_rebaseline",
            "acceptance": (
                "normals, mean curvature, area, and legacy volume deltas "
                "must be characterized"
            ),
        },
        {
            "id": "output",
            "state": "pending_stock_vs_current_rebaseline",
            "acceptance": (
                "output-visible force and face-observable records must be "
                "compared without changing output semantics"
            ),
        },
        {
            "id": "serial_openmp",
            "state": "pending_stock_semantics_rebaseline",
            "acceptance": (
                "stock-semantics serial/OpenMP accumulation and repeatability "
                "must be characterized independently"
            ),
        },
    ]
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "proof_kind": "valence5_option_b_scientific_rebaseline_assessment",
        "proof_only": True,
        "assessment_authorized": True,
        "assessment_scope": "observational_scientific_rebaseline_planning_only",
        "predecessor_merge_commit": PR151_MERGE_COMMIT,
        "option_b_selected": option_b_selected,
        "option_b_recommended": option_b_recommended,
        "stock_semantics_scientifically_approved": (
            stock_semantics_scientifically_approved
        ),
        "physical_rebaselining_plan_proposed": True,
        "physical_rebaselining_plan_authorized": (
            physical_rebaselining_plan_authorized
        ),
        "implementation_work_authorized": implementation_work_authorized,
        "production_route_enabled": production_route_enabled,
        "valence5_opensubdiv_route_enabled": False,
        "not_production_routing": True,
        "current_slimed_valence5_fallback_preserved": True,
        "known_stock_semantics_change": True,
        "reviewed_tolerance": REVIEWED_TOLERANCE,
        "known_row_residual": EXPECTED_ROW_MAXIMUM,
        "known_force_residuals": dict(EXPECTED_FORCE_MAXIMA),
        "mask_policy_causal_sufficiency_proven": False,
        "current_serial_openmp_baseline_preserved": True,
        "current_serial_openmp_baseline_tolerance": (
            CURRENT_SERIAL_OMP_TOLERANCE
        ),
        "rebaseline_channels": channels_plan,
        "completed_evidence": [
            "topology_and_source_mapping",
            "row_composition_characterization",
            "force_characterization",
            "current_slimed_serial_openmp_baseline",
        ],
        "pending_evidence": [
            "stock_energy",
            "stock_geometry",
            "stock_output",
            "stock_serial_openmp",
        ],
        "decision_ready": False,
        "recommended_next_evidence_lane": (
            "proof-only stock OpenSubdiv valence-5 energy and geometry "
            "observable re-baselining"
        ),
        "route_blockers": [
            "stock OpenSubdiv valence-5 semantics are measurably different "
            "from current SLIMED semantics",
            "stock energy, geometry, output, and serial/OpenMP re-baselining "
            "remain incomplete",
            "Option B remains unselected and scientifically unapproved",
        ],
        "remaining_boundary": REMAINING_BOUNDARY,
    }


def emit(report: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"status: {report['status']}")
    print(f"Option B selected: {report['option_b_selected']}")
    print(f"decision ready: {report['decision_ready']}")
    print(f"remaining boundary: {report['remaining_boundary']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force-report", type=Path, required=True)
    parser.add_argument("--composition-report", type=Path, required=True)
    parser.add_argument("--current-serial-openmp-report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate(
            force_report=_load_json(args.force_report),
            composition_report=_load_json(args.composition_report),
            current_serial_openmp_report=_load_json(
                args.current_serial_openmp_report
            ),
        )
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        report = {"status": "failed", "errors": [str(error)]}
    emit(report, args.json)
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
