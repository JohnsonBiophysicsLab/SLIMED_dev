#!/usr/bin/env python3
"""Check whether OpenSubdiv can run an evaluator-bound valence-5 mask counterfactual."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BASELINE_WRAPPER = (
    ROOT
    / "scripts/run_irregular_valence5_opensubdiv_integration_composition.sh"
)
REVIEWED_ROW_TOLERANCE = 5.0e-6
ROW_SHAPE = [20, 6, 3, 7, 12]
ROW_COMPONENT_COUNT = math.prod(ROW_SHAPE)
BASELINE_MAX_ABS_ROW_DIFFERENCE = 0.7357563654581705
SLIMED_MASK = {"edge_weight": 0.075, "center_weight": 0.625}
OPENSUBDIV_MASK = {
    "edge_weight": 0.08409321892578289,
    "center_weight": 0.5795339053710855,
}
EXPECTED_PUBLIC_SETTERS = [
    "SetCreasingMethod",
    "SetFVarLinearInterpolation",
    "SetTriangleSubdivision",
    "SetVtxBoundaryInterpolation",
]
PUBLIC_API_BLOCKER = "OpenSubdiv public Loop scheme does not expose a custom extraordinary smooth-mask override"
NEXT_BOUNDARY = "explicitly reviewed custom OpenSubdiv Loop scheme or library decision"


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


def parse_json(result: subprocess.CompletedProcess[str], label: str) -> dict[str, object]:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit {result.returncode}: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} did not emit JSON: {error}") from error


def public_api_evidence(options_source: str, loop_source: str) -> dict[str, object]:
    setters = sorted(set(re.findall(r"\bvoid\s+(Set[A-Za-z0-9_]+)\s*\(", options_source)))
    mask_like_setters = [
        setter
        for setter in setters
        if any(token in setter.lower() for token in ("mask", "weight", "smooth"))
    ]
    formula_needles = [
        "Scheme<SCHEME_LOOP>::assignSmoothMaskForVertex",
        "double beta = 0.25f * cosTheta + 0.375f;",
        "eWeight = (Weight) ((0.625f - (beta * beta)) * invValence);",
        "vWeight = (Weight) (1.0f - (eWeight * dValence));",
    ]
    return {
        "options_declares_all_supported_scheme_options": (
            "All supported options applying to subdivision scheme" in options_source
        ),
        "public_option_setters": setters,
        "public_option_setters_match_reviewed_api": setters == EXPECTED_PUBLIC_SETTERS,
        "public_custom_smooth_mask_setters": mask_like_setters,
        "public_custom_smooth_mask_override_available": bool(mask_like_setters),
        "loop_smooth_mask_formula_anchors": {
            needle: needle in loop_source for needle in formula_needles
        },
        "loop_smooth_mask_formula_embedded": all(
            needle in loop_source for needle in formula_needles
        ),
    }


def _build_report(
    baseline: dict[str, object],
    api: dict[str, object],
    *,
    reporting_only_mask: dict[str, float] | None = None,
) -> dict[str, object]:
    errors: list[str] = []
    if baseline.get("status") != "passed":
        errors.append("integration-composition baseline did not pass its diagnostic")
    if baseline.get("proof_kind") != "valence5_opensubdiv_integration_composition":
        errors.append("integration-composition baseline proof identity drift")
    if baseline.get("row_shape") != ROW_SHAPE:
        errors.append("baseline composed-row shape drift")
    if baseline.get("row_component_count") != ROW_COMPONENT_COUNT:
        errors.append("baseline composed-row cardinality drift")
    if baseline.get("reviewed_absolute_tolerance") != REVIEWED_ROW_TOLERANCE:
        errors.append("baseline reviewed tolerance drift")
    if baseline.get("face_orientation_bound_by_source_identity") is not True:
        errors.append("baseline source/orientation identity is not bound")
    if baseline.get("affine_domain_plan_matches_reviewed") is not True:
        errors.append("baseline child-domain identity is not bound")
    if baseline.get("production_scatter_executed") is not False:
        errors.append("baseline unexpectedly executed production scatter")
    if baseline.get("composed_row_parity_passed") is not False:
        errors.append("baseline composed-row parity result drift")
    if (
        baseline.get("max_abs_row_difference")
        != BASELINE_MAX_ABS_ROW_DIFFERENCE
    ):
        errors.append("baseline maximum composed-row residual drift")

    baseline_slimed_mask = {
        "edge_weight": baseline.get("production_valence5_vertex_edge_weight"),
        "center_weight": baseline.get("production_valence5_vertex_center_weight"),
    }
    baseline_opensubdiv_mask = {
        "edge_weight": baseline.get("opensubdiv_valence5_vertex_edge_weight"),
        "center_weight": baseline.get("opensubdiv_valence5_vertex_center_weight"),
    }
    if baseline_slimed_mask != SLIMED_MASK:
        errors.append("baseline SLIMED valence-5 mask drift")
    if baseline_opensubdiv_mask != OPENSUBDIV_MASK:
        errors.append("baseline OpenSubdiv valence-5 mask drift")

    valence = 5.0
    beta = 0.25 * math.cos(2.0 * math.pi / valence) + 0.375
    embedded_edge = (0.625 - beta * beta) / valence
    embedded_center = 1.0 - embedded_edge * valence
    embedded_mask = {
        "edge_weight": embedded_edge,
        "center_weight": embedded_center,
    }
    if embedded_mask != OPENSUBDIV_MASK:
        errors.append("independent OpenSubdiv Loop mask calculation drift")
    if api.get("options_declares_all_supported_scheme_options") is not True:
        errors.append("OpenSubdiv public options declaration was not verified")
    if api.get("public_option_setters_match_reviewed_api") is not True:
        errors.append("OpenSubdiv public scheme-options API drift")
    if api.get("loop_smooth_mask_formula_embedded") is not True:
        errors.append("OpenSubdiv embedded Loop smooth-mask formula drift")

    reporting_mutation_requested = reporting_only_mask is not None
    if reporting_mutation_requested:
        errors.append(
            "reporting-only mask mutation cannot create an evaluator-bound "
            "counterfactual"
        )

    override_available = bool(
        api.get("public_custom_smooth_mask_override_available")
    )
    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "valence5_opensubdiv_mask_counterfactual_capability",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_scatter_executed": False,
        "scientifically_approved": False,
        "reviewed_absolute_tolerance": REVIEWED_ROW_TOLERANCE,
        "baseline": {
            "evaluator_bound": True,
            "row_shape": baseline.get("row_shape"),
            "row_component_count": baseline.get("row_component_count"),
            "composed_row_parity_passed": baseline.get(
                "composed_row_parity_passed"
            ),
            "max_abs_row_difference": baseline.get("max_abs_row_difference"),
            "source_orientation_identity_bound": baseline.get(
                "face_orientation_bound_by_source_identity"
            ),
            "child_domain_identity_bound": baseline.get(
                "affine_domain_plan_matches_reviewed"
            ),
            "slimed_mask": baseline_slimed_mask,
            "opensubdiv_mask": baseline_opensubdiv_mask,
        },
        "public_api_evidence": api,
        "embedded_loop_mask_recomputed": embedded_mask,
        "counterfactual": {
            "requested_mask": SLIMED_MASK,
            "evaluator_bound": False,
            "independent_refiner_constructed": False,
            "independent_patch_table_constructed": False,
            "independent_stencil_storage_constructed": False,
            "independent_row_storage_constructed": False,
            "row_component_count": 0,
            "row_parity_passed": None,
            "public_override_available": override_available,
        },
        "reporting_only_mask_mutation": reporting_only_mask,
        "reporting_only_mask_mutation_requested": reporting_mutation_requested,
        "reporting_only_mask_mutation_accepted": False,
        "mask_policy_causal_sufficiency_proven": False,
        "route_blockers": [PUBLIC_API_BLOCKER],
        "remaining_boundary": NEXT_BOUNDARY,
        "errors": errors,
    }


def evaluate(
    baseline: dict[str, object],
    api: dict[str, object],
) -> dict[str, object]:
    report = _build_report(baseline, api)
    mutation = _build_report(
        baseline,
        api,
        reporting_only_mask=SLIMED_MASK,
    )
    report["reporting_only_mask_mutation_negative_gate_passed"] = (
        mutation["status"] == "failed"
        and mutation["reporting_only_mask_mutation_requested"] is True
        and mutation["reporting_only_mask_mutation_accepted"] is False
        and mutation["counterfactual"]["evaluator_bound"] is False
        and mutation["counterfactual"]["row_component_count"] == 0
        and "reporting-only mask mutation cannot create an evaluator-bound "
        "counterfactual" in mutation["errors"]
    )
    if not report["reporting_only_mask_mutation_negative_gate_passed"]:
        report["errors"].append("reporting-only mask mutation negative gate failed")
        report["status"] = "failed"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()

    root_value = os.environ.get("OPENSUBDIV_ROOT")
    if not root_value:
        if args.require_opensubdiv:
            print("OPENSUBDIV_ROOT is required", file=os.sys.stderr)
            return 2
        report = {
            "status": "skipped",
            "reason": "OPENSUBDIV_ROOT is not configured",
            "proof_only": True,
            "not_production_routing": True,
        }
    else:
        include = Path(root_value) / "include/opensubdiv"
        options_path = include / "sdc/options.h"
        loop_path = include / "sdc/loopScheme.h"
        try:
            options_source = options_path.read_text(encoding="utf-8")
            loop_source = loop_path.read_text(encoding="utf-8")
            env = os.environ.copy()
            baseline = parse_json(
                run(
                    [
                        str(BASELINE_WRAPPER),
                        "--json",
                        "--require-opensubdiv",
                    ],
                    env,
                ),
                "integration-composition baseline",
            )
            report = evaluate(
                baseline,
                public_api_evidence(options_source, loop_source),
            )
        except (OSError, RuntimeError) as error:
            report = {
                "status": "failed",
                "proof_only": True,
                "not_production_routing": True,
                "production_route_enabled": False,
                "scientifically_approved": False,
                "errors": [str(error)],
            }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        if report["status"] == "passed":
            print(f"route blocker: {report['route_blockers'][0]}")
            print(f"remaining boundary: {report['remaining_boundary']}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
