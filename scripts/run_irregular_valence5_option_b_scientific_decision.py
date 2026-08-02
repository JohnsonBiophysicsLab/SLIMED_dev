#!/usr/bin/env python3
"""Emit the non-authorizing Option B scientific decision packet."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_MERGE_COMMIT = "93b18c683a19e3c35b595e8c85ae111b04caa967"
SOURCE_DIGESTS = {
    "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.py":
        "59b1c23deeeb78b81ea1f8a969afd6ac7dcfe770b91a1196889f9c953326f0ac",
    "scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py":
        "bd24cc4446ba2bf3a2e6c2e6e32f416b4db951583c4cf8055b585b6235b7570c",
    "scripts/run_irregular_valence5_option_b_serial_openmp.py":
        "8db235869e940f4c92dcec362eea8c371f955834fc913c1c1ee51b26f306dff7",
    "scripts/run_irregular_valence5_option_b_output_visibility.py":
        "cbb8f7174b2faf5dd8259d844101251e20b3639afed70b0b65429a6c77d64bd6",
}
CANONICAL_EVIDENCE = (
    {
        "lane": "scientific_rebaseline_plan",
        "pull_request": 152,
        "merge_commit": "24cbc8c79259e4ee6dec039b87d816c03ea75560",
        "complete": True,
    },
    {
        "lane": "energy_geometry",
        "pull_request": 153,
        "merge_commit": "5d8ef458f738343df82050e4f02b9647064fd75f",
        "complete": True,
    },
    {
        "lane": "output_characterization",
        "pull_request": 157,
        "merge_commit": "c6569c6fdbcc2de72c10951e7c42699fe9d4a6e6",
        "complete": True,
    },
    {
        "lane": "serial_openmp",
        "pull_request": 160,
        "merge_commit": "73bfbf1e90626eaf829d85c2a77916aaf816076f",
        "complete": True,
    },
    {
        "lane": "output_contract_repair",
        "pull_request": 161,
        "merge_commit": BASE_MERGE_COMMIT,
        "complete": True,
    },
)
MEASURED_CHANGES = {
    "composed_row_max_abs_difference": 0.7357563654581705,
    "force_max_abs_difference_by_kind": {
        "fBend": 7.108303140663388,
        "fArea": 0.46106761515265404,
        "fVolume": 0.062309089012307695,
    },
    "global_curvature_energy_abs_difference": 83.84946348746075,
    "per_face_curvature_energy_max_abs_difference": 4.386320459494776,
    "face_mean_curvature_max_abs_difference": 2.5747867579624395,
    "stock_serial_openmp_max_abs_difference": 2.2737367544323206e-13,
    "stock_serial_openmp_tolerance": 1.0e-10,
    "output_force_group_count": 24,
    "output_force_roundtrip_max_abs_difference": 0.0,
    "output_face_field_roundtrip_max_abs_difference": 0.0,
}
REQUIRED_USER_DECISION = (
    "explicitly accept, reject, or defer Option B stock OpenSubdiv "
    "extraordinary-valence semantics after scientific review of the listed "
    "force, energy, and geometry changes"
)


def _actual_source_digests() -> dict[str, str]:
    return {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in SOURCE_DIGESTS
    }


def evaluate(
    *,
    evidence: list[dict[str, object]] | None = None,
    measured_changes: dict[str, object] | None = None,
    source_digests: dict[str, str] | None = None,
    option_b_selected: bool = False,
    scientific_approval_granted: bool = False,
    implementation_authorized: bool = False,
    production_route_enabled: bool = False,
) -> dict[str, object]:
    evidence = evidence if evidence is not None else deepcopy(list(CANONICAL_EVIDENCE))
    measured_changes = (
        measured_changes
        if measured_changes is not None
        else deepcopy(MEASURED_CHANGES)
    )
    source_digests = source_digests if source_digests is not None else _actual_source_digests()
    errors: list[str] = []

    if evidence != list(CANONICAL_EVIDENCE):
        errors.append("merged Option B evidence identity or completion drift")
    if measured_changes != MEASURED_CHANGES:
        errors.append("reviewed scientific measurement drift")
    if source_digests != SOURCE_DIGESTS:
        errors.append("merged Option B evidence source digest drift")
    if option_b_selected:
        errors.append("this packet cannot select Option B")
    if scientific_approval_granted:
        errors.append("this packet cannot grant scientific approval")
    if implementation_authorized:
        errors.append("this packet cannot authorize implementation")
    if production_route_enabled:
        errors.append("this packet cannot enable production routing")

    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "proof_kind": "valence5_option_b_scientific_decision_packet",
        "base_merge_commit": BASE_MERGE_COMMIT,
        "evidence_complete": True,
        "decision_ready_for_user": True,
        "decision_recorded": False,
        "required_user_decision": REQUIRED_USER_DECISION,
        "option_b_selected": option_b_selected,
        "scientific_approval_granted": scientific_approval_granted,
        "implementation_authorized": implementation_authorized,
        "production_route_enabled": production_route_enabled,
        "current_slimed_valence5_fallback_preserved": True,
        "safe_default_without_explicit_approval": "preserve_current_slimed_fallback",
        "stock_and_current_semantics_are_not_equivalent": True,
        "mask_policy_causal_sufficiency_proven": False,
        "numerical_consistency_is_scientific_acceptance": False,
        "evidence": evidence,
        "measured_changes": measured_changes,
        "decision_responses": {
            "accept": (
                "accept the measured stock-semantic changes as the new physical "
                "baseline and authorize a separate production-routing plan"
            ),
            "reject": "retain the current SLIMED valence-5 fallback and close Option B",
            "defer": (
                "retain the current fallback and identify the additional physical "
                "validation required before a decision"
            ),
        },
        "acceptance_consequences": [
            "rebaseline affected valence-5 scientific expectations",
            "implement routing in a separate reviewed pull request",
            "retain an explicit rollback path to the current fallback",
        ],
        "remaining_boundary": REQUIRED_USER_DECISION,
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
        print(f"Option B scientific decision packet: {report['status']}")
        print(f"Evidence complete: {report['evidence_complete']}")
        print(f"Decision ready for user: {report['decision_ready_for_user']}")
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
