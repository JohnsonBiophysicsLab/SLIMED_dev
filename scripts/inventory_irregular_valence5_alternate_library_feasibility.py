#!/usr/bin/env python3
"""Inventory the valence-5 alternate-library feasibility package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RUNNER = Path("scripts/run_irregular_valence5_alternate_library_feasibility.py")
WRAPPER = Path("scripts/run_irregular_valence5_alternate_library_feasibility.sh")
DOC = Path("docs/irregular_valence5_alternate_library_feasibility.md")
ARCHITECTURE_DOC = Path(
    "docs/irregular_valence5_opensubdiv_architecture_decision.md"
)
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
PREDECESSOR = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_architecture_decision.py"
)
GLOBAL_INVENTORY = Path("scripts/inventory_opensubdiv_routing_readiness.py")
TEST = Path(
    "tests/test_irregular_valence5_alternate_library_feasibility_inventory.py"
)

ANCHORS = {
    RUNNER: (
        'RETRIEVAL_DATE = "2026-07-30"',
        "SLIMED_VALENCE5_NEIGHBOR_WEIGHT = 0.075",
        "SLIMED_VALENCE5_CENTER_WEIGHT = 0.625",
        '"exact_limit_surface_evaluation"',
        '"first_parametric_derivatives"',
        '"second_parametric_derivatives"',
        '"public_custom_mask_scheme_evaluator_seam"',
        '"evaluator_bound_custom_rows"',
        '"source_identity_order_cardinality_compatible"',
        '"chain_rule_compatible"',
        '"cgal", "libigl", "openmesh", "pmp-library"',
        '"release_or_commit": "cac3e9d75e254928db0e38a3161564216cb01919"',
        '"release_or_commit": "40e7900ccbd767f1f360e0eb10f0f1a6432e0993"',
        '"release_or_commit": "f13a3bf79f8dc91cd453b74baa9dc6f97a5a3062"',
        '"release_or_commit": "f2fb04f4a4188a5c1ab137e83b96e62fa99c639f"',
        '"public_custom_refinement_mask": public_custom_refinement_mask',
        '"limit_vertex_position_weights": limit_vertex_position_weights',
        '"limit_vertex_tangent_weights": limit_vertex_tangent_weights',
        "cannot infer exact limit evaluation ",
        "post-hoc row substitution is not a legitimate evaluator seam",
        "architecture_option_authorized_for_investigation: str = \"D\"",
        'authorization_scope: str = "observational_feasibility_only"',
        "PR149 predecessor history must remain no-option-selected",
        "all four PR149 architecture options must remain historically unselected",
        "this observational package cannot select a library",
        "this observational package cannot prefer a candidate",
        "this observational package cannot recommend or prefer a library",
        "normals or curvature cannot substitute for parametric derivatives",
        '"selected_library": selected_library',
        '"library_selected": library_selected',
        '"preferred_candidate": preferred_candidate',
        '"dependency_policy_changed": dependency_policy_changed',
        '"production_route_enabled": production_route_enabled',
        '"scientifically_approved": scientifically_approved',
        '"patch_or_vendoring_performed": patch_or_vendoring_performed',
        '"installability_not_executed": True',
        "no viable candidate in the reviewed finite non-exhaustive set",
    ),
    WRAPPER: (
        "run_irregular_valence5_alternate_library_feasibility.py",
        '"$@"',
    ),
    DOC: (
        "observational, proof-only package",
        '`architecture_option_authorized_for_investigation:"D"`',
        "`alternate_library_feasibility_lane_authorized:true`",
        '`authorization_scope:"observational_feasibility_only"`',
        "`selected_library:null`",
        "`library_selected:false`",
        "`preferred_candidate:null`",
        "`dependency_policy_changed:false`",
        "`production_route_enabled:false`",
        "`scientifically_approved:false`",
        "`patch_or_vendoring_performed:false`",
        "`post_hoc_row_substitution_accepted:false`",
        "`current_slimed_valence5_fallback_preserved:true`",
        "`neighbor_weight:0.075`, `center_weight:0.625`",
        "CGAL 6.2",
        "libigl 2.6.0",
        "OpenMesh 11.0",
        "pmp-library 3.0.0",
        "finite non-exhaustive set",
        "`installability_not_executed:true`",
        "current dependency-free",
    ),
    ARCHITECTURE_DOC: (
        "At the PR #149 merge boundary, no option",
        "PR #150 subsequently completed the bounded Option D observational",
    ),
    READINESS: (
        "Option D observational survey is complete",
        "no viable candidate in the reviewed finite non-exhaustive set",
        "valence-5 fallback remains preserved",
        "post-Option-D gate records the remaining neutral boundary",
    ),
    PREDECESSOR: (
        "architecture options must be exactly ordered A, B, C, D",
        "architecture options must remain unselected and unpreferred",
    ),
    GLOBAL_INVENTORY: (
        "Option D observational feasibility completed",
        "alternate-library finite-set result",
        "alternate-library selection remains false",
        "alternate-library fallback preserved",
        "post-Option-D neutral gate",
    ),
    TEST: (
        "test_canonical_report_passes_without_selection",
        'self.assertNotIn("installable", candidate)',
        'self.assertFalse(candidate["installability_probe_executed"])',
        'self.assertFalse(candidate["compile_link_probe_passed"])',
        "test_missing_duplicate_reordered_and_unknown_candidates_fail",
        "test_capability_and_source_metadata_drift_fail",
        "test_refinement_limit_and_derivative_false_greens_fail",
        "test_selection_policy_route_and_fallback_false_claims_fail",
        "test_pr149_history_and_authorization_scope_are_binding",
        "test_wrapper_is_local_and_deterministic",
        "test_stale_nothing_next_wording_fails_global_readiness",
    ),
}

FORBIDDEN = {
    DOC: (
        "CGAL is recommended",
        "libigl is recommended",
        "OpenMesh is recommended",
        "pmp-library is recommended",
        "an alternate library was selected",
        "finite refinement is exact limit evaluation",
        "normals are first derivatives",
        "curvature is a second derivative",
    ),
    ARCHITECTURE_DOC: (
        "No option is approved or automatically next",
    ),
    READINESS: (
        "an alternate subdivision library is selected",
        "Option D selects an alternate library",
        "alternate-library production routing is enabled",
        "Option D is now authorized only for this observational feasibility lane",
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
                errors.append(f"{relative} contains forbidden claim {needle!r}")

    return {
        "status": "passed" if not errors else "failed",
        "proof_only": True,
        "observational_only": True,
        "architecture_option_authorized_for_investigation": "D",
        "authorization_scope": "observational_feasibility_only",
        "library_selected": False,
        "selected_library": None,
        "preferred_candidate": None,
        "dependency_policy_changed": False,
        "production_route_enabled": False,
        "scientifically_approved": False,
        "patch_or_vendoring_performed": False,
        "current_slimed_valence5_fallback_preserved": True,
        "anchors": {"located": located, "expected": expected},
        "forbidden_claims": {
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
