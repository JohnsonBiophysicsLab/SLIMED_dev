#!/usr/bin/env python3
"""Inventory the valence-5 OpenSubdiv custom-scheme feasibility diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RUNNER = Path(
    "scripts/run_irregular_valence5_opensubdiv_custom_scheme_feasibility.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence5_opensubdiv_custom_scheme_feasibility.sh"
)
DOC = Path("docs/irregular_valence5_opensubdiv_custom_scheme_feasibility.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
PREDECESSOR = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_mask_counterfactual.py"
)
TEST = Path(
    "tests/test_irregular_valence5_opensubdiv_custom_scheme_feasibility_inventory.py"
)

BLOCKER = (
    "OpenSubdiv 3.7.0 public Far/Sdc pipeline closes scheme selection over "
    "the fixed SchemeType set and exposes no custom Loop smooth-mask "
    "injection or scheme registration hook"
)
NEXT_BOUNDARY = (
    "separately reviewed custom-scheme or library architecture decision; "
    "production valence-5 routing remains disabled"
)

ANCHORS = {
    RUNNER: (
        "REVIEWED_ROW_TOLERANCE = 5.0e-6",
        'EXPECTED_SCHEME_TYPES = ["SCHEME_BILINEAR", "SCHEME_CATMARK", "SCHEME_LOOP"]',
        "scheme_type_set_matches_reviewed_api",
        "scheme_template_parameter_is_scheme_type",
        "loop_scheme_is_fixed_specialization",
        "topology_refiner_accepts_scheme_type",
        "topology_factory_scheme_type_field",
        "public_scheme_registration_hook_available",
        "public_custom_mask_injection_available",
        "valid_standalone_public_extension_path_exists",
        "custom_scheme_adapter_constructed",
        "evaluator_bound_slimed_mask_rows_generated",
        "post-hoc or JSON-only row substitution is not evaluator-bound evidence",
        "this diagnostic cannot choose scientific mask semantics",
        "this diagnostic cannot patch or vendor OpenSubdiv",
        "false_claim_negative_gates_passed",
        "OpenSubdiv 3.7.0 public Far/Sdc pipeline closes scheme selection over",
        "separately reviewed custom-scheme or library architecture decision;",
    ),
    WRAPPER: (
        "run_irregular_valence5_opensubdiv_custom_scheme_feasibility.py",
        '"$@"',
    ),
    DOC: (
        "approved closed valence-5 icosahedron",
        "fixed non-overrideable `5e-6` policy",
        "`SCHEME_BILINEAR`, `SCHEME_CATMARK`, and",
        "`valid_standalone_public_extension_path_exists:false`",
        "`evaluator_bound_slimed_mask_rows_generated:false`",
        "post-hoc or JSON-only row substitution",
        "does not establish mask causality",
        "`scientifically_approved:false`",
        BLOCKER,
        NEXT_BOUNDARY,
    ),
    READINESS: (
        "completed custom-scheme feasibility diagnostic",
        BLOCKER,
        "public-extension adapter produced evaluator-bound SLIMED-mask rows",
        NEXT_BOUNDARY,
    ),
    PREDECESSOR: (
        '"explicitly reviewed custom OpenSubdiv Loop scheme or library decision"',
    ),
    TEST: (
        "test_false_extension_and_post_hoc_claims_are_binding",
        "test_scientific_choice_and_vendoring_claims_are_binding",
        "test_public_scheme_set_drift_is_binding",
        "test_present_dependency_reports_exact_architecture_blocker",
        "test_wider_tolerance_override_is_rejected",
    ),
}

FORBIDDEN = {
    RUNNER: (
        'add_argument("--tolerance"',
        "args.tolerance",
    ),
    DOC: (
        "custom scheme path is production ready",
        "SLIMED mask is scientifically preferred",
        "standard OpenSubdiv mask is scientifically preferred",
    ),
    READINESS: (
        "The remaining boundary is an\n`explicitly reviewed custom OpenSubdiv Loop scheme or library decision`",
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
        "valid_standalone_public_extension_path_exists": False,
        "evaluator_bound_slimed_mask_rows_generated": False,
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
