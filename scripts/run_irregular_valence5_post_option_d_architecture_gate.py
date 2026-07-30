#!/usr/bin/env python3
"""Emit the frozen post-Option-D valence-5 architecture decision gate."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PR149_RUNNER = (
    ROOT / "scripts/run_irregular_valence5_opensubdiv_architecture_decision.py"
)
PREDECESSOR_RUNNER = (
    ROOT / "scripts/run_irregular_valence5_alternate_library_feasibility.py"
)
PR149_MERGE_COMMIT = "54fecddb60edd05c0ec4677c87f684ebe5b50301"
PR150_MERGE_COMMIT = "636a6583fea3e76e42e8b6b48699e40bc80f4e4d"
PR149_OPTIONS_SHA256 = (
    "a23f7974b66ee17a0ffbfffe5a102beeed1965393365d5de36ad0228b1ff1b4c"
)
PR150_REPORT_SHA256 = (
    "c773ac3cbc25438325aa5f3b7037b49541a06e7038dd556fa47a320e1b52328f"
)
PR150_CANDIDATE_RECORDS_SHA256 = (
    "dab623d1554ce2face1b7536be95a9f06797707de12f9d78a3df109cf7467123"
)
PR150_RETRIEVAL_DATE = "2026-07-30"
PR150_SLIMED_VALENCE5_MASK = {
    "neighbor_weight": 0.075,
    "center_weight": 0.625,
}
PR150_CAPABILITY_ORDER = (
    "triangular_loop_support",
    "extraordinary_valence_support",
    "exact_limit_surface_evaluation",
    "first_parametric_derivatives",
    "second_parametric_derivatives",
    "public_custom_mask_scheme_evaluator_seam",
    "evaluator_bound_custom_rows",
    "source_identity_order_cardinality_compatible",
    "chain_rule_compatible",
)
PR150_CANDIDATE_IDS = ("cgal", "libigl", "openmesh", "pmp-library")
PR150_CANDIDATE_BINDINGS = (
    ("cgal", "CGAL", "6.2", "cac3e9d75e254928db0e38a3161564216cb01919"),
    (
        "libigl",
        "libigl",
        "2.6.0",
        "40e7900ccbd767f1f360e0eb10f0f1a6432e0993",
    ),
    (
        "openmesh",
        "OpenMesh",
        "11.0",
        "f13a3bf79f8dc91cd453b74baa9dc6f97a5a3062",
    ),
    (
        "pmp-library",
        "pmp-library",
        "3.0.0",
        "f2fb04f4a4188a5c1ab137e83b96e62fa99c639f",
    ),
)
PR150_AUTHORIZATION_STATE = {
    "architecture_option_authorized_for_investigation": "D",
    "alternate_library_feasibility_lane_authorized": True,
    "authorization_scope": "observational_feasibility_only",
    "predecessor_decision_selected": False,
    "predecessor_selected_option": None,
    "investigation_authorization_is_architecture_selection": False,
}
PR150_EXACT_BLOCKER = (
    "no viable candidate in the reviewed finite non-exhaustive set provides "
    "exact extraordinary Loop limit-surface evaluation with first and second "
    "parametric derivatives and a public evaluator-bound custom-mask seam "
    "that preserves the SLIMED valence-5 source and chain-rule contract"
)
OPTION_D_RESULT = "no_viable_candidate_in_reviewed_finite_non_exhaustive_set"
REMAINING_BOUNDARY = (
    "preserve the current fallback/status quo; or separately approve "
    "scientific re-baselining for stock OpenSubdiv extraordinary semantics; "
    "or separately approve patch/fork/vendor dependency, license, and "
    "maintenance investigation; Option D may reopen only with materially new "
    "evidence and explicit authorization"
)

CANONICAL_OPTIONS = (
    {
        "id": "A",
        "name": "preserve_current_slimed_fallback_status_quo",
        "status": "unselected",
        "state": "current_behavior_preserved",
        "selected": False,
        "recommended": False,
        "preferred": False,
        "automatically_next": False,
        "is_architecture_selection": False,
        "implementation_work_required": False,
        "boundary": (
            "preserve the current dependency-free SLIMED positive-depth "
            "valence-5 fallback; no implementation work is required"
        ),
    },
    {
        "id": "B",
        "name": "adopt_stock_opensubdiv_extraordinary_semantics",
        "status": "unselected",
        "state": "awaiting_explicit_user_decision",
        "selected": False,
        "recommended": False,
        "preferred": False,
        "automatically_next": False,
        "is_architecture_selection": True,
        "implementation_work_required": True,
        "required_explicit_user_decision": (
            "explicitly select Option B: adopt stock OpenSubdiv extraordinary "
            "semantics"
        ),
        "prerequisites_before_implementation": [
            "explicit scientific approval",
            "a separate physical re-baselining plan",
        ],
    },
    {
        "id": "C",
        "name": "patch_fork_or_vendor_opensubdiv",
        "status": "unselected",
        "state": "awaiting_explicit_user_decision",
        "selected": False,
        "recommended": False,
        "preferred": False,
        "automatically_next": False,
        "is_architecture_selection": True,
        "implementation_work_required": True,
        "required_explicit_user_decision": (
            "explicitly select Option C: patch, fork, or vendor OpenSubdiv"
        ),
        "prerequisites_before_implementation": [
            "explicit dependency, license, and maintenance approval",
            "scientific validation after dependency approval",
        ],
    },
    {
        "id": "D",
        "name": "evaluate_alternate_subdivision_library",
        "status": "completed",
        "result": OPTION_D_RESULT,
        "state": "completed_no_viable_candidate_in_reviewed_set",
        "selected": False,
        "recommended": False,
        "preferred": False,
        "automatically_next": False,
        "is_architecture_selection": False,
        "implementation_work_required": False,
        "reviewed_candidate_ids": list(PR150_CANDIDATE_IDS),
        "reopen_boundary": (
            "a separate explicit authorization plus materially new upstream "
            "or candidate evidence"
        ),
    },
)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pr149_options() -> list[dict[str, object]]:
    module = _load_module(PR149_RUNNER, "valence5_pr149_architecture_predecessor")
    return [deepcopy(option) for option in module.CANONICAL_OPTIONS]


def _load_predecessor_report() -> dict[str, object]:
    module = _load_module(
        PREDECESSOR_RUNNER, "valence5_alternate_library_predecessor"
    )
    return module.evaluate()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_predecessor(predecessor: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if predecessor.get("status") != "passed":
        errors.append("PR150 predecessor status drift")
    if predecessor.get("proof_kind") != "valence5_alternate_library_feasibility":
        errors.append("PR150 predecessor identity drift")
    if _canonical_sha256(predecessor) != PR150_REPORT_SHA256:
        errors.append("PR150 canonical report digest drift")
    if predecessor.get("retrieval_date") != PR150_RETRIEVAL_DATE:
        errors.append("PR150 retrieval date drift")
    if predecessor.get("slimed_valence5_mask") != PR150_SLIMED_VALENCE5_MASK:
        errors.append("PR150 SLIMED valence-5 mask drift")
    if predecessor.get("required_capabilities") != list(PR150_CAPABILITY_ORDER):
        errors.append("PR150 required capability order drift")
    if predecessor.get("candidate_ids") != list(PR150_CANDIDATE_IDS):
        errors.append("PR150 candidate IDs or ordering drift")

    candidates = predecessor.get("candidates")
    bindings: list[tuple[object, object, object, object]] = []
    if isinstance(candidates, list):
        bindings = [
            (
                candidate.get("id"),
                candidate.get("name"),
                candidate.get("version"),
                candidate.get("release_or_commit"),
            )
            for candidate in candidates
            if isinstance(candidate, dict)
        ]
    if bindings != list(PR150_CANDIDATE_BINDINGS):
        errors.append("PR150 candidate identity, version, or pin drift")
    if _canonical_sha256(candidates) != PR150_CANDIDATE_RECORDS_SHA256:
        errors.append("PR150 full canonical candidate records or order drift")
    if predecessor.get("viable_candidate_ids") != []:
        errors.append("PR150 finite-set no-viable-candidate result drift")
    if predecessor.get("route_blockers") != [PR150_EXACT_BLOCKER]:
        errors.append("PR150 exact blocker drift")
    for key, expected in PR150_AUTHORIZATION_STATE.items():
        if predecessor.get(key) != expected:
            errors.append(f"PR150 authorization state drift: {key}")
    if predecessor.get("installability_not_executed") is not True:
        errors.append("PR150 installability execution state drift")
    if predecessor.get("library_selected") is not False:
        errors.append("PR150 library-selection state drift")
    if predecessor.get("selected_library") is not None:
        errors.append("PR150 selected-library state drift")
    if predecessor.get("preferred_candidate") is not None:
        errors.append("PR150 preferred-candidate state drift")
    if predecessor.get("current_slimed_valence5_fallback_preserved") is not True:
        errors.append("PR150 fallback-preservation state drift")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                errors.append("PR150 candidate record is malformed")
                continue
            if candidate.get("viable") is not False:
                errors.append("PR150 fabricated viable candidate")
            if candidate.get("selected") is not False:
                errors.append("PR150 fabricated selected candidate")
            if candidate.get("recommended") is not False:
                errors.append("PR150 fabricated recommended candidate")
            if candidate.get("installability_probe_executed") is not False:
                errors.append("PR150 candidate installability overclaim")
            if candidate.get("compile_link_probe_passed") is not False:
                errors.append("PR150 candidate compile/link overclaim")
    return errors


def _validate_pr149_options(options: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    if _canonical_sha256(options) != PR149_OPTIONS_SHA256:
        errors.append("PR149 canonical architecture options drift")
    if [option.get("id") for option in options] != ["A", "B", "C", "D"]:
        errors.append("PR149 architecture option order drift")
    if any(option.get("status") != "unselected" for option in options):
        errors.append("PR149 architecture options must remain unselected")
    return errors


def _validate_options(options: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    if options != [deepcopy(option) for option in CANONICAL_OPTIONS]:
        errors.append("post-Option-D option definitions or order drift")
    if any(
        option.get("selected")
        or option.get("recommended")
        or option.get("preferred")
        or option.get("automatically_next")
        for option in options
    ):
        errors.append("no option may be selected, recommended, preferred, or next")
    return errors


def evaluate(
    *,
    pr149_options: list[dict[str, object]] | None = None,
    predecessor_report: dict[str, object] | None = None,
    options: list[dict[str, object]] | None = None,
    decision_selected: bool = False,
    selected_option: str | None = None,
    recommended_option: str | None = None,
    preferred_option: str | None = None,
    automatically_next_option: str | None = None,
    proceed_interpreted_as_option_selection: bool = False,
    scientific_approval_granted: bool = False,
    physical_rebaselining_plan_authorized: bool = False,
    dependency_license_maintenance_approval_granted: bool = False,
    dependency_policy_changed: bool = False,
    patch_or_vendoring_performed: bool = False,
    implementation_work_authorized: bool = False,
    production_route_enabled: bool = False,
    valence5_opensubdiv_route_enabled: bool = False,
    current_slimed_valence5_fallback_preserved: bool = True,
    option_d_reopened: bool = False,
    explicit_option_d_reopen_authorization: bool = False,
    materially_new_upstream_or_candidate_evidence: bool = False,
) -> dict[str, object]:
    predecessor_options = (
        _load_pr149_options()
        if pr149_options is None
        else deepcopy(pr149_options)
    )
    predecessor = (
        _load_predecessor_report()
        if predecessor_report is None
        else deepcopy(predecessor_report)
    )
    decision_options = (
        [deepcopy(option) for option in CANONICAL_OPTIONS]
        if options is None
        else deepcopy(options)
    )
    errors = _validate_pr149_options(predecessor_options)
    errors.extend(_validate_predecessor(predecessor))
    errors.extend(_validate_options(decision_options))

    if decision_selected or selected_option is not None:
        errors.append("this decision gate cannot select an architecture")
    if recommended_option is not None or preferred_option is not None:
        errors.append("this decision gate cannot recommend or prefer an option")
    if automatically_next_option is not None:
        errors.append("this decision gate cannot declare an option next")
    if proceed_interpreted_as_option_selection:
        errors.append("Proceed authorizes only this gate, not Option B or C")
    if scientific_approval_granted:
        errors.append("this decision gate cannot grant scientific approval")
    if physical_rebaselining_plan_authorized:
        errors.append("this decision gate cannot authorize physical re-baselining")
    if dependency_license_maintenance_approval_granted:
        errors.append("this decision gate cannot approve dependency policy")
    if dependency_policy_changed:
        errors.append("this decision gate cannot change dependency policy")
    if patch_or_vendoring_performed:
        errors.append("this decision gate cannot patch, fork, or vendor OpenSubdiv")
    if implementation_work_authorized:
        errors.append("this decision gate cannot authorize implementation")
    if production_route_enabled or valence5_opensubdiv_route_enabled:
        errors.append("this decision gate cannot enable production routing")
    if not current_slimed_valence5_fallback_preserved:
        errors.append("the current SLIMED valence-5 fallback must remain preserved")
    option_d_reopen_requirements_satisfied = (
        explicit_option_d_reopen_authorization
        and materially_new_upstream_or_candidate_evidence
    )
    if option_d_reopened and not option_d_reopen_requirements_satisfied:
        errors.append(
            "Option D reopening requires both explicit authorization and "
            "materially new evidence"
        )
    if (
        option_d_reopened
        or explicit_option_d_reopen_authorization
        or materially_new_upstream_or_candidate_evidence
    ):
        errors.append("this frozen gate cannot reopen Option D")

    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "valence5_post_option_d_architecture_gate",
        "proof_only": True,
        "decision_gate_only": True,
        "predecessor_merge_commits": {
            "pr149": PR149_MERGE_COMMIT,
            "pr150": PR150_MERGE_COMMIT,
        },
        "pr149_predecessor": {
            "pull_request": 149,
            "merge_commit": PR149_MERGE_COMMIT,
            "canonical_options_sha256": _canonical_sha256(predecessor_options),
            "option_order": [option.get("id") for option in predecessor_options],
            "option_statuses": {
                str(option.get("id")): option.get("status")
                for option in predecessor_options
            },
            "decision_selected": False,
            "selected_option": None,
        },
        "pr150_predecessor": {
            "pull_request": 150,
            "merge_commit": PR150_MERGE_COMMIT,
            "proof_kind": predecessor.get("proof_kind"),
            "canonical_report_sha256": _canonical_sha256(predecessor),
            "candidate_ids": predecessor.get("candidate_ids"),
            "candidate_records_sha256": _canonical_sha256(
                predecessor.get("candidates")
            ),
            "viable_candidate_ids": predecessor.get("viable_candidate_ids"),
            "retrieval_date": predecessor.get("retrieval_date"),
            "slimed_valence5_mask": predecessor.get("slimed_valence5_mask"),
            "required_capabilities": predecessor.get("required_capabilities"),
            "route_blockers": predecessor.get("route_blockers"),
            "authorization_state": {
                key: predecessor.get(key) for key in PR150_AUTHORIZATION_STATE
            },
            "installability_not_executed": predecessor.get(
                "installability_not_executed"
            ),
        },
        "options": decision_options,
        "option_order": ["A", "B", "C", "D"],
        "remaining_choices": deepcopy(decision_options[:3]),
        "completed_option_d": next(
            (
                deepcopy(option)
                for option in decision_options
                if option.get("id") == "D"
            ),
            None,
        ),
        "option_d_status": "completed",
        "option_d_result": OPTION_D_RESULT,
        "decision_selected": decision_selected,
        "selected_option": selected_option,
        "recommended_option": recommended_option,
        "preferred_option": preferred_option,
        "automatically_next_option": automatically_next_option,
        "proceed_interpreted_as_option_selection": (
            proceed_interpreted_as_option_selection
        ),
        "scientific_approval_granted": scientific_approval_granted,
        "physical_rebaselining_plan_authorized": (
            physical_rebaselining_plan_authorized
        ),
        "dependency_license_maintenance_approval_granted": (
            dependency_license_maintenance_approval_granted
        ),
        "dependency_policy_changed": dependency_policy_changed,
        "patch_or_vendoring_performed": patch_or_vendoring_performed,
        "implementation_work_authorized": implementation_work_authorized,
        "production_route_enabled": production_route_enabled,
        "valence5_opensubdiv_route_enabled": valence5_opensubdiv_route_enabled,
        "current_slimed_valence5_fallback_preserved": (
            current_slimed_valence5_fallback_preserved
        ),
        "option_d_reopened": option_d_reopened,
        "explicit_option_d_reopen_authorization": (
            explicit_option_d_reopen_authorization
        ),
        "materially_new_upstream_or_candidate_evidence": (
            materially_new_upstream_or_candidate_evidence
        ),
        "option_d_reopen_requires_both_prerequisites": True,
        "option_d_reopen_requirements_satisfied": (
            option_d_reopen_requirements_satisfied
        ),
        "remaining_user_decision_boundary": {
            "B": (
                "explicitly select Option B, grant scientific approval, and "
                "approve a separate physical re-baselining plan before "
                "implementation"
            ),
            "C": (
                "explicitly select Option C, approve dependency, license, and "
                "maintenance policy, then complete scientific validation "
                "before implementation"
            ),
        },
        "remaining_boundary": REMAINING_BOUNDARY,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = evaluate()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print("predecessors: PR #149 and PR #150")
        print("selected option: none")
        for option, boundary in report["remaining_user_decision_boundary"].items():
            print(f"Option {option}: {boundary}")
        print(f"remaining boundary: {report['remaining_boundary']}")
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
