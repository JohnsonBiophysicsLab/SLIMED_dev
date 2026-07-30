#!/usr/bin/env python3
"""Record the bounded architecture decision state for valence-5 OpenSubdiv."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FEASIBILITY = (
    ROOT / "scripts/run_irregular_valence5_opensubdiv_custom_scheme_feasibility.sh"
)
FORCE_PARITY = ROOT / "scripts/run_irregular_valence5_opensubdiv_force_parity.sh"

EXPECTED_OPENSUBDIV_VERSION_NUMBER = 30700
EXPECTED_OPENSUBDIV_VERSION = "3.7.0"
REVIEWED_ABSOLUTE_TOLERANCE = 5.0e-6
EXPECTED_MAX_ABS_FORCE_DIFFERENCE = 7.108303140663388
PUBLIC_EXTENSION_BLOCKER = (
    "OpenSubdiv 3.7.0 public Far/Sdc pipeline closes scheme selection over "
    "the fixed SchemeType set and exposes no custom Loop smooth-mask "
    "injection or scheme registration hook"
)
FORCE_PARITY_BLOCKER = (
    "direct whole-Ptex OpenSubdiv rows do not match the existing "
    "positive-depth 11=4+3+4 force composition"
)
SELECTION_GATE = (
    "explicit reviewer/user architecture selection; scientific approval and "
    "output re-baselining for changed semantics; dependency, maintenance, "
    "and license review for changed library policy"
)

CANONICAL_OPTIONS = (
    {
        "id": "A",
        "name": "hybrid_preserve_existing_slimed_valence5",
        "status": "unselected",
        "preserves_current_scientific_semantics": True,
        "changes_dependency_policy": False,
        "requires_scientific_approval": False,
        "requires_full_output_rebaseline": False,
        "requires_dependency_maintenance_license_review": False,
        "requires_new_library_feasibility_lane": False,
        "boundary": (
            "preserve the existing dependency-free SLIMED positive-depth "
            "valence-5 evaluator while retaining the separately guarded "
            "OpenSubdiv regular and canonical valence-4 routes"
        ),
    },
    {
        "id": "B",
        "name": "adopt_stock_opensubdiv_extraordinary_semantics",
        "status": "unselected",
        "preserves_current_scientific_semantics": False,
        "changes_dependency_policy": False,
        "requires_scientific_approval": True,
        "requires_full_output_rebaseline": True,
        "requires_dependency_maintenance_license_review": False,
        "requires_new_library_feasibility_lane": False,
        "boundary": (
            "requires a separate scientific mask-policy decision and complete "
            "force, energy, geometry, output, and serial/OpenMP re-baselining"
        ),
    },
    {
        "id": "C",
        "name": "patch_fork_or_vendor_opensubdiv",
        "status": "unselected",
        "preserves_current_scientific_semantics": False,
        "changes_dependency_policy": True,
        "requires_scientific_approval": True,
        "requires_full_output_rebaseline": True,
        "requires_dependency_maintenance_license_review": True,
        "requires_new_library_feasibility_lane": False,
        "boundary": (
            "requires separate dependency-policy, maintenance, license, "
            "scientific, and full output re-baselining reviews"
        ),
    },
    {
        "id": "D",
        "name": "evaluate_alternate_subdivision_library",
        "status": "unselected",
        "preserves_current_scientific_semantics": False,
        "changes_dependency_policy": True,
        "requires_scientific_approval": True,
        "requires_full_output_rebaseline": True,
        "requires_dependency_maintenance_license_review": True,
        "requires_new_library_feasibility_lane": True,
        "boundary": (
            "requires a new library feasibility lane before any scientific, "
            "dependency-policy, or production routing claim"
        ),
    },
)


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


def _validate_options(options: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    expected = [deepcopy(option) for option in CANONICAL_OPTIONS]
    option_ids = [option.get("id") for option in options]
    expected_ids = [option["id"] for option in expected]

    if len(option_ids) != len(set(option_ids)):
        errors.append("architecture option ids must be unique")
    if option_ids != expected_ids:
        errors.append("architecture options must be exactly ordered A, B, C, D")
    if options != expected:
        errors.append("architecture option definitions drifted")
    if any(
        option.get("status") != "unselected"
        or option.get("preferred") is not None
        or option.get("recommended") is not None
        for option in options
    ):
        errors.append("architecture options must remain unselected and unpreferred")
    return errors


def _build_report(
    feasibility: dict[str, object],
    force_parity: dict[str, object],
    *,
    options: list[dict[str, object]] | None = None,
    decision_selected: bool = False,
    selected_option: str | None = None,
    scientifically_approved: bool = False,
    dependency_policy_changed: bool = False,
    library_patch_or_vendoring_performed: bool = False,
    alternate_library_selected: bool = False,
    production_route_enabled: bool = False,
    valence5_opensubdiv_route_enabled: bool = False,
    current_slimed_valence5_route_preserved: bool = True,
    recommendation_language_present: bool = False,
) -> dict[str, object]:
    errors: list[str] = []
    decision_options = (
        [deepcopy(option) for option in CANONICAL_OPTIONS]
        if options is None
        else deepcopy(options)
    )
    errors.extend(_validate_options(decision_options))

    if feasibility.get("status") != "passed":
        errors.append("PR148 custom-scheme feasibility predecessor did not pass")
    if (
        feasibility.get("proof_kind")
        != "valence5_opensubdiv_custom_scheme_feasibility"
    ):
        errors.append("PR148 feasibility proof identity drift")
    api = feasibility.get("public_api_evidence", {})
    if not isinstance(api, dict):
        errors.append("PR148 public API evidence is missing")
        api = {}
    if api.get("detected_opensubdiv_version_number") != (
        EXPECTED_OPENSUBDIV_VERSION_NUMBER
    ):
        errors.append("reviewed OpenSubdiv version number drift")
    if api.get("detected_opensubdiv_version") != EXPECTED_OPENSUBDIV_VERSION:
        errors.append("reviewed OpenSubdiv version string drift")
    if api.get("version_number_matches_reviewed_api") is not True:
        errors.append("reviewed OpenSubdiv version gate failed")
    if api.get("public_scheme_registration_hook_available") is not False:
        errors.append("public scheme-registration API fact drift")
    if api.get("public_custom_mask_injection_available") is not False:
        errors.append("public custom-mask API fact drift")
    if feasibility.get("valid_standalone_public_extension_path_exists") is not False:
        errors.append("public extension-path feasibility fact drift")
    if feasibility.get("evaluator_bound_slimed_mask_rows_generated") is not False:
        errors.append("evaluator-bound custom row fact drift")
    if feasibility.get("evaluator_bound_row_component_count") != 0:
        errors.append("evaluator-bound custom row count drift")
    if feasibility.get("mask_policy_causal_sufficiency_proven") is not False:
        errors.append("mask-policy causal-sufficiency boundary drift")
    if feasibility.get("scientifically_approved") is not False:
        errors.append("PR148 scientific-approval boundary drift")
    if feasibility.get("production_route_enabled") is not False:
        errors.append("PR148 production-route boundary drift")
    if feasibility.get("route_blockers") != [PUBLIC_EXTENSION_BLOCKER]:
        errors.append("PR148 public extension blocker drift")

    if force_parity.get("status") != "passed":
        errors.append("force-parity predecessor did not pass diagnostically")
    if (
        force_parity.get("proof_kind")
        != "valence5_opensubdiv_force_parity_diagnostic"
    ):
        errors.append("force-parity proof identity drift")
    if force_parity.get("force_parity_passed") is not False:
        errors.append("valence-5 force-parity boundary drift")
    if force_parity.get("max_abs_force_difference") != (
        EXPECTED_MAX_ABS_FORCE_DIFFERENCE
    ):
        errors.append("reviewed maximum force residual drift")
    if force_parity.get("relative_tolerance") != REVIEWED_ABSOLUTE_TOLERANCE:
        errors.append("reviewed force-parity tolerance drift")
    if force_parity.get("route_blockers") != [FORCE_PARITY_BLOCKER]:
        errors.append("force-parity blocker drift")
    if force_parity.get("production_route_enabled") is not False:
        errors.append("force-parity route boundary drift")
    if force_parity.get("production_scatter_executed") is not False:
        errors.append("force-parity scatter boundary drift")

    if decision_selected or selected_option is not None:
        errors.append("this proof-only package cannot select an architecture option")
    if scientifically_approved:
        errors.append("this package cannot grant scientific approval")
    if dependency_policy_changed:
        errors.append("this package cannot change dependency policy")
    if library_patch_or_vendoring_performed:
        errors.append("this package cannot patch, fork, or vendor OpenSubdiv")
    if alternate_library_selected:
        errors.append("this package cannot select an alternate library")
    if production_route_enabled or valence5_opensubdiv_route_enabled:
        errors.append("this package cannot enable valence-5 OpenSubdiv routing")
    if not current_slimed_valence5_route_preserved:
        errors.append("the current SLIMED valence-5 route must remain preserved")
    if recommendation_language_present:
        errors.append("this package cannot recommend or implicitly prefer an option")

    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "valence5_opensubdiv_architecture_decision",
        "proof_only": True,
        "not_production_routing": True,
        "approved_fixture": "closed valence-5 icosahedron",
        "reviewed_facts": {
            "detected_opensubdiv_version_number": api.get(
                "detected_opensubdiv_version_number"
            ),
            "detected_opensubdiv_version": api.get("detected_opensubdiv_version"),
            "public_scheme_registration_hook_available": api.get(
                "public_scheme_registration_hook_available"
            ),
            "public_custom_mask_injection_available": api.get(
                "public_custom_mask_injection_available"
            ),
            "valid_standalone_public_extension_path_exists": feasibility.get(
                "valid_standalone_public_extension_path_exists"
            ),
            "evaluator_bound_slimed_mask_rows_generated": feasibility.get(
                "evaluator_bound_slimed_mask_rows_generated"
            ),
            "evaluator_bound_row_component_count": feasibility.get(
                "evaluator_bound_row_component_count"
            ),
            "mask_policy_causal_sufficiency_proven": feasibility.get(
                "mask_policy_causal_sufficiency_proven"
            ),
            "force_parity_passed": force_parity.get("force_parity_passed"),
            "max_abs_force_difference": force_parity.get(
                "max_abs_force_difference"
            ),
            "reviewed_absolute_tolerance": force_parity.get("relative_tolerance"),
        },
        "decision_options": decision_options,
        "decision_option_order": ["A", "B", "C", "D"],
        "decision_selected": decision_selected,
        "selected_option": selected_option,
        "scientifically_approved": scientifically_approved,
        "dependency_policy_changed": dependency_policy_changed,
        "library_patch_or_vendoring_performed": (
            library_patch_or_vendoring_performed
        ),
        "alternate_library_selected": alternate_library_selected,
        "production_route_enabled": production_route_enabled,
        "valence5_opensubdiv_route_enabled": valence5_opensubdiv_route_enabled,
        "current_slimed_valence5_route_preserved": (
            current_slimed_valence5_route_preserved
        ),
        "current_fallback_is_selected_opensubdiv_architecture": False,
        "recommendation_language_present": recommendation_language_present,
        "route_blockers": [PUBLIC_EXTENSION_BLOCKER, FORCE_PARITY_BLOCKER],
        "remaining_boundary": SELECTION_GATE,
        "errors": errors,
    }


def evaluate(
    feasibility: dict[str, object],
    force_parity: dict[str, object],
) -> dict[str, object]:
    report = _build_report(feasibility, force_parity)
    malformed_options = (
        [deepcopy(option) for option in CANONICAL_OPTIONS[:-1]],
        [deepcopy(CANONICAL_OPTIONS[0]), *deepcopy(list(CANONICAL_OPTIONS))],
        [
            *deepcopy(list(CANONICAL_OPTIONS[:-1])),
            {**deepcopy(CANONICAL_OPTIONS[-1]), "id": "E"},
        ],
        [
            deepcopy(CANONICAL_OPTIONS[1]),
            deepcopy(CANONICAL_OPTIONS[0]),
            *deepcopy(list(CANONICAL_OPTIONS[2:])),
        ],
        [
            {**deepcopy(CANONICAL_OPTIONS[0]), "preferred": True},
            *deepcopy(list(CANONICAL_OPTIONS[1:])),
        ],
    )
    false_claims = (
        {"recommendation_language_present": True},
        {"decision_selected": True, "selected_option": "A"},
        {"scientifically_approved": True},
        {"library_patch_or_vendoring_performed": True},
        {"alternate_library_selected": True},
        {"dependency_policy_changed": True},
        {"production_route_enabled": True},
        {"valence5_opensubdiv_route_enabled": True},
        {"current_slimed_valence5_route_preserved": False},
    )
    report["option_contract_negative_gates_passed"] = all(
        _build_report(feasibility, force_parity, options=options)["status"]
        == "failed"
        for options in malformed_options
    )
    report["policy_claim_negative_gates_passed"] = all(
        _build_report(feasibility, force_parity, **claim)["status"] == "failed"
        for claim in false_claims
    )
    if not report["option_contract_negative_gates_passed"]:
        report["errors"].append("option-contract negative gates failed")
    if not report["policy_claim_negative_gates_passed"]:
        report["errors"].append("policy-claim negative gates failed")
    if report["errors"]:
        report["status"] = "failed"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()

    if not os.environ.get("OPENSUBDIV_ROOT"):
        if args.require_opensubdiv:
            print("OPENSUBDIV_ROOT is required", file=os.sys.stderr)
            return 2
        report = {
            "status": "skipped",
            "reason": "OPENSUBDIV_ROOT is not configured",
            "proof_only": True,
            "not_production_routing": True,
            "decision_options": [deepcopy(option) for option in CANONICAL_OPTIONS],
            "decision_option_order": ["A", "B", "C", "D"],
            "decision_selected": False,
            "selected_option": None,
            "scientifically_approved": False,
            "dependency_policy_changed": False,
            "library_patch_or_vendoring_performed": False,
            "production_route_enabled": False,
            "valence5_opensubdiv_route_enabled": False,
            "current_slimed_valence5_route_preserved": True,
            "current_fallback_is_selected_opensubdiv_architecture": False,
        }
    else:
        env = os.environ.copy()
        try:
            feasibility = parse_json(
                run(
                    [str(FEASIBILITY), "--json", "--require-opensubdiv"],
                    env,
                ),
                "PR148 custom-scheme feasibility predecessor",
            )
            force_parity = parse_json(
                run(
                    [str(FORCE_PARITY), "--json", "--require-opensubdiv"],
                    env,
                ),
                "valence-5 force-parity predecessor",
            )
            report = evaluate(feasibility, force_parity)
        except RuntimeError as error:
            report = {
                "status": "failed",
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
                "errors": [str(error)],
            }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        if report["status"] == "passed":
            print("decision selected: false")
            print(f"remaining boundary: {report['remaining_boundary']}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
