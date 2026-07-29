#!/usr/bin/env python3
"""Inventory the valence-5 OpenSubdiv mask-counterfactual capability proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RUNNER = Path(
    "scripts/run_irregular_valence5_opensubdiv_mask_counterfactual.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence5_opensubdiv_mask_counterfactual.sh"
)
DOC = Path("docs/irregular_valence5_opensubdiv_mask_counterfactual.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
PREDECESSOR = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_integration_composition.py"
)
TEST = Path(
    "tests/test_irregular_valence5_opensubdiv_mask_counterfactual_inventory.py"
)

BLOCKER = (
    "OpenSubdiv public Loop scheme does not expose a custom extraordinary "
    "smooth-mask override"
)
NEXT_BOUNDARY = (
    "explicitly reviewed custom OpenSubdiv Loop scheme or library decision"
)

ANCHORS = {
    RUNNER: (
        "REVIEWED_ROW_TOLERANCE = 5.0e-6",
        "ROW_SHAPE = [20, 6, 3, 7, 12]",
        "ROW_COMPONENT_COUNT = math.prod(ROW_SHAPE)",
        "BASELINE_MAX_ABS_ROW_DIFFERENCE = 0.7357563654581705",
        "production_valence5_vertex_edge_weight",
        "production_valence5_vertex_center_weight",
        "SetVtxBoundaryInterpolation",
        "SetFVarLinearInterpolation",
        "SetCreasingMethod",
        "SetTriangleSubdivision",
        "Scheme<SCHEME_LOOP>::assignSmoothMaskForVertex",
        "loop_smooth_mask_formula_embedded",
        "independent_refiner_constructed",
        "independent_patch_table_constructed",
        "independent_stencil_storage_constructed",
        "independent_row_storage_constructed",
        '"row_parity_passed": None',
        "reporting-only mask mutation cannot create an evaluator-bound",
        "reporting_only_mask_mutation_requested",
        "reporting_only_mask_mutation_accepted",
        "reporting_only_mask_mutation_negative_gate_passed",
        "mask_policy_causal_sufficiency_proven",
        BLOCKER,
        NEXT_BOUNDARY,
    ),
    WRAPPER: (
        "run_irregular_valence5_opensubdiv_mask_counterfactual.py",
        '"$@"',
    ),
    DOC: (
        "`20 x 6 x 3 x 7 x 12`",
        "all 30,240 finite components",
        "fixed non-overrideable `5e-6` policy",
        "`0.075` / `0.625`",
        "`0.08409321892578289` / `0.5795339053710855`",
        "no independent counterfactual refiner",
        "`counterfactual.row_parity_passed:null`",
        "reporting-only replacement",
        BLOCKER,
        "`mask_policy_causal_sufficiency_proven:false`",
        "`scientifically_approved:false`",
        NEXT_BOUNDARY,
    ),
    READINESS: (
        "completed counterfactual capability diagnostic",
        BLOCKER,
        "No evaluator-bound mask-only counterfactual was constructed",
        NEXT_BOUNDARY,
    ),
    PREDECESSOR: (
        f'"{NEXT_BOUNDARY}"',
    ),
    TEST: (
        "test_reporting_only_mask_mutation_is_rejected",
        "test_public_options_drift_is_binding",
        "test_baseline_contract_mutations_are_binding",
        "test_present_dependency_reports_exact_api_blocker",
        "assertIsNone(report[\"counterfactual\"][\"row_parity_passed\"])",
    ),
}

FORBIDDEN = {
    RUNNER: (
        'add_argument("--tolerance"',
        "args.tolerance",
    ),
    DOC: (
        "mask alignment closes all residuals",
        "counterfactual parity passed",
    ),
    READINESS: (
        "The next boundary is a\ncounterfactual valence-5 extraordinary-mask",
        "mask alignment is causally sufficient",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for relative, needles in ANCHORS.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative} missing {needle!r}")

    forbidden_located = 0
    forbidden_expected = 0
    for relative, needles in FORBIDDEN.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            forbidden_expected += 1
            if needle in source:
                forbidden_located += 1
                errors.append(f"{relative} contains stale claim {needle!r}")

    return {
        "status": "passed" if not errors else "failed",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "scientifically_approved": False,
        "counterfactual_evaluator_bound": False,
        "counterfactual_row_parity_passed": None,
        "mask_policy_causal_sufficiency_proven": False,
        "current_route_blocker": BLOCKER,
        "next_gate": NEXT_BOUNDARY,
        "anchors": {"located": located, "expected": expected},
        "forbidden_stale_claims": {
            "located": forbidden_located,
            "expected": forbidden_expected,
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = collect(repo_root())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(
            f"anchors: {report['anchors']['located']}/"
            f"{report['anchors']['expected']}"
        )
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
