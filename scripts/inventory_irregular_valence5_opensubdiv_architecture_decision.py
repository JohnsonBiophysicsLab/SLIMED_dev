#!/usr/bin/env python3
"""Inventory the valence-5 OpenSubdiv architecture decision package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RUNNER = Path(
    "scripts/run_irregular_valence5_opensubdiv_architecture_decision.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence5_opensubdiv_architecture_decision.sh"
)
DOC = Path("docs/irregular_valence5_opensubdiv_architecture_decision.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
PREDECESSOR = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_custom_scheme_feasibility.py"
)
TEST = Path(
    "tests/test_irregular_valence5_opensubdiv_architecture_decision_inventory.py"
)

ANCHORS = {
    RUNNER: (
        "EXPECTED_OPENSUBDIV_VERSION_NUMBER = 30700",
        'EXPECTED_OPENSUBDIV_VERSION = "3.7.0"',
        "EXPECTED_MAX_ABS_FORCE_DIFFERENCE = 7.108303140663388",
        "CANONICAL_OPTIONS = (",
        '"id": "A"',
        '"id": "B"',
        '"id": "C"',
        '"id": "D"',
        '"status": "unselected"',
        "architecture options must be exactly ordered A, B, C, D",
        "architecture options must remain unselected and unpreferred",
        '"decision_selected": decision_selected',
        '"selected_option": selected_option',
        '"scientifically_approved": scientifically_approved',
        '"dependency_policy_changed": dependency_policy_changed',
        '"library_patch_or_vendoring_performed": (',
        '"production_route_enabled": production_route_enabled',
        '"valence5_opensubdiv_route_enabled": valence5_opensubdiv_route_enabled',
        '"current_slimed_valence5_route_preserved": (',
        '"current_fallback_is_selected_opensubdiv_architecture": False',
        "this package cannot recommend or implicitly prefer an option",
        "option_contract_negative_gates_passed",
        "policy_claim_negative_gates_passed",
        "mask_policy_causal_sufficiency_proven",
        "evaluator_bound_row_component_count",
        "public_scheme_registration_hook_available",
        "public_custom_mask_injection_available",
    ),
    WRAPPER: (
        "run_irregular_valence5_opensubdiv_architecture_decision.py",
        '"$@"',
    ),
    DOC: (
        "approved closed valence-5 icosahedron",
        "`decision_selected:false`",
        "`selected_option:null`",
        "`scientifically_approved:false`",
        "`dependency_policy_changed:false`",
        "`library_patch_or_vendoring_performed:false`",
        "`production_route_enabled:false`",
        "`valence5_opensubdiv_route_enabled:false`",
        "`current_slimed_valence5_route_preserved:true`",
        "`current_fallback_is_selected_opensubdiv_architecture:false`",
        "`OPENSUBDIV_VERSION_NUMBER == 30700`",
        "zero evaluator-bound SLIMED custom-mask rows",
        "`mask_policy_causal_sufficiency_proven:false`",
        "`7.108303140663388`",
        "exactly four options in order `A`, `B`, `C`, `D`",
        "Every\noption has `status:\"unselected\"` and none is preferred",
        "Hybrid preservation",
        "Adopt stock OpenSubdiv extraordinary semantics",
        "Patch, fork, or vendor OpenSubdiv",
        "Evaluate an alternate subdivision library",
        "At the PR #149 merge boundary, no option\nwas approved or automatically next",
        "A later explicit user authorization may open one bounded\ninvestigation",
    ),
    READINESS: (
        "completed valence-5 architecture decision package",
        "architecture options remain explicitly unselected",
        "positive-depth valence-5 route remains preserved behavior",
        "After that historical no-selection decision",
        "Option D only as an observational feasibility investigation",
    ),
    PREDECESSOR: (
        "EXPECTED_OPENSUBDIV_VERSION_NUMBER = 30700",
        "evaluator_bound_slimed_mask_rows_generated",
    ),
    TEST: (
        "test_exact_ordered_unselected_options_pass",
        "test_missing_duplicate_unknown_reordered_and_preferred_options_fail",
        "test_policy_and_route_false_claims_fail",
        "test_pr148_and_force_predecessor_drift_fail",
        "test_dependency_absent_wrapper_skips",
        "test_present_dependency_reproduces_exact_decision",
        "test_stale_decision_claims_fail_global_readiness",
    ),
}

FORBIDDEN = {
    DOC: (
        "option A is approved",
        "option B is approved",
        "option C is approved",
        "option D is approved",
        "hybrid is automatically next",
        "stock OpenSubdiv semantics are automatically next",
    ),
    READINESS: (
        "hybrid valence-5 architecture is approved",
        "stock OpenSubdiv valence-5 semantics are approved",
        "patching OpenSubdiv is approved",
        "an alternate subdivision library is approved",
        "valence-5 OpenSubdiv route activation is automatically next",
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
        "decision_selected": False,
        "selected_option": None,
        "scientifically_approved": False,
        "dependency_policy_changed": False,
        "library_patch_or_vendoring_performed": False,
        "production_route_enabled": False,
        "valence5_opensubdiv_route_enabled": False,
        "current_slimed_valence5_route_preserved": True,
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
