#!/usr/bin/env python3
"""Emit the accepted-but-unrouted Option B scientific selection record."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = ROOT / "scripts/run_irregular_valence5_option_b_scientific_decision.py"
PREDECESSOR_MERGE_COMMIT = "023db1ea053f90e895175cf89e88ed437dad4b93"
PREDECESSOR_SHA256 = "648b030e51ecab8056c6ddd9d50cf9445648014418d6bac8349d69d54f260460"
DECISION = "accept"
DECISION_DATE = "2026-08-02"
DECISION_SOURCE = "explicit_user_instruction"
DECISION_TEXT = "Accept Option B."


def _load_predecessor():
    spec = importlib.util.spec_from_file_location("option_b_decision_predecessor", PREDECESSOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Option B decision predecessor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _predecessor_report() -> dict[str, object]:
    return _load_predecessor().evaluate()


def _validate_predecessor(report: dict[str, object], source_sha256: str) -> list[str]:
    errors: list[str] = []
    expected = {
        "status": "passed",
        "proof_kind": "valence5_option_b_scientific_decision_packet",
        "evidence_complete": True,
        "decision_ready_for_user": True,
        "decision_recorded": False,
        "option_b_selected": False,
        "option_b_recommended": False,
        "scientific_approval_granted": False,
        "implementation_authorized": False,
        "production_route_enabled": False,
        "current_slimed_valence5_fallback_preserved": True,
        "stock_and_current_semantics_are_not_equivalent": True,
        "mask_policy_causal_sufficiency_proven": False,
        "numerical_consistency_is_scientific_acceptance": False,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            errors.append(f"scientific decision predecessor {key} drift")
    if report.get("errors") != []:
        errors.append("scientific decision predecessor error state drift")
    if source_sha256 != PREDECESSOR_SHA256:
        errors.append("scientific decision predecessor source digest drift")
    else:
        predecessor = _load_predecessor()
        if report.get("evidence") != list(predecessor.CANONICAL_EVIDENCE):
            errors.append("scientific decision predecessor evidence drift")
        if report.get("measured_changes") != predecessor.MEASURED_CHANGES:
            errors.append("scientific decision predecessor measurements drift")
    return errors


def evaluate(
    *,
    predecessor_report: dict[str, object] | None = None,
    predecessor_sha256: str | None = None,
    decision: str = DECISION,
    decision_recorded: bool = True,
    option_b_selected: bool = True,
    option_b_recommended: bool = False,
    stock_semantics_scientifically_approved: bool = True,
    scientific_rebaseline_plan_authorized: bool = True,
    production_routing_plan_authorized: bool = True,
    implementation_authorized: bool = False,
    production_route_enabled: bool = False,
) -> dict[str, object]:
    predecessor_report = (
        predecessor_report if predecessor_report is not None else _predecessor_report()
    )
    predecessor_sha256 = (
        predecessor_sha256
        if predecessor_sha256 is not None
        else hashlib.sha256(PREDECESSOR.read_bytes()).hexdigest()
    )
    errors = _validate_predecessor(predecessor_report, predecessor_sha256)
    if decision != DECISION:
        errors.append("the recorded user decision must remain accept")
    if not decision_recorded:
        errors.append("the explicit Option B decision must remain recorded")
    if not option_b_selected:
        errors.append("the accepted Option B selection cannot be cleared")
    if option_b_recommended:
        errors.append("selection is not a recommendation claim")
    if not stock_semantics_scientifically_approved:
        errors.append("accepted stock semantics cannot be reported unapproved")
    if not scientific_rebaseline_plan_authorized:
        errors.append("the accepted scientific re-baseline plan cannot be cleared")
    if not production_routing_plan_authorized:
        errors.append("the accepted production-routing plan cannot be cleared")
    if implementation_authorized:
        errors.append("this selection record cannot authorize implementation")
    if production_route_enabled:
        errors.append("this selection record cannot enable production routing")

    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "proof_kind": "valence5_option_b_scientific_selection_record",
        "predecessor_merge_commit": PREDECESSOR_MERGE_COMMIT,
        "predecessor_source_sha256": predecessor_sha256,
        "decision": decision,
        "decision_date": DECISION_DATE,
        "decision_source": DECISION_SOURCE,
        "decision_text": DECISION_TEXT,
        "decision_recorded": decision_recorded,
        "option_b_selected": option_b_selected,
        "option_b_recommended": option_b_recommended,
        "stock_semantics_scientifically_approved": (
            stock_semantics_scientifically_approved
        ),
        "scientific_rebaseline_plan_authorized": (
            scientific_rebaseline_plan_authorized
        ),
        "production_routing_plan_authorized": production_routing_plan_authorized,
        "implementation_authorized": implementation_authorized,
        "production_route_enabled": production_route_enabled,
        "current_slimed_valence5_fallback_preserved": True,
        "fallback_preservation_boundary": (
            "preserve the current SLIMED valence-5 fallback until a separate "
            "reviewed implementation and activation PR is approved"
        ),
        "accepted_scientific_changes": deepcopy(
            predecessor_report.get("measured_changes")
        ),
        "implementation_plan": [
            {
                "phase": 1,
                "name": "guarded_stock_valence5_row_provider",
                "authorization": "requires_separate_implementation_approval",
                "production_mutation": False,
            },
            {
                "phase": 2,
                "name": "guarded_face_loop_integration_and_rebaseline",
                "authorization": "requires_separate_reviewed_pr",
                "production_mutation": True,
            },
            {
                "phase": 3,
                "name": "explicit_route_activation",
                "authorization": "requires_separate_reviewer_and_user_approval",
                "production_mutation": True,
            },
        ],
        "remaining_boundary": (
            "review and merge this selection record, then explicitly authorize "
            "the first guarded implementation PR; production routing remains disabled"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Option B scientific selection record: {report['status']}")
        print(f"Decision: {report['decision']}")
        print(f"Production route enabled: {report['production_route_enabled']}")
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
