#!/usr/bin/env python3
"""Assess public custom-scheme feasibility for the approved valence-5 fixture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = (
    ROOT / "scripts/run_irregular_valence5_opensubdiv_mask_counterfactual.sh"
)
REVIEWED_ROW_TOLERANCE = 5.0e-6
EXPECTED_SCHEME_TYPES = ["SCHEME_BILINEAR", "SCHEME_CATMARK", "SCHEME_LOOP"]
PUBLIC_EXTENSION_BLOCKER = (
    "OpenSubdiv 3.7.0 public Far/Sdc pipeline closes scheme selection over "
    "the fixed SchemeType set and exposes no custom Loop smooth-mask "
    "injection or scheme registration hook"
)
NEXT_BOUNDARY = (
    "separately reviewed custom-scheme or library architecture decision; "
    "production valence-5 routing remains disabled"
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


def _scheme_types(types_source: str) -> list[str]:
    match = re.search(r"enum\s+SchemeType\s*\{([^}]*)\}", types_source, re.DOTALL)
    if match is None:
        return []
    return re.findall(r"\bSCHEME_[A-Z0-9_]+\b", match.group(1))


def public_extension_evidence(
    types_source: str,
    options_source: str,
    scheme_source: str,
    loop_source: str,
    topology_refiner_source: str,
    topology_factory_source: str,
) -> dict[str, object]:
    combined = "\n".join(
        (
            types_source,
            options_source,
            scheme_source,
            loop_source,
            topology_refiner_source,
            topology_factory_source,
        )
    )
    scheme_types = _scheme_types(types_source)
    registration_tokens = sorted(
        set(
            re.findall(
                r"\b(?:Register|Set|Create)(?:Custom)?Scheme[A-Za-z0-9_]*\b",
                combined,
            )
        )
    )
    mask_setters = sorted(
        set(
            re.findall(
                r"\bSet[A-Za-z0-9_]*(?:Mask|Weight|Smooth)[A-Za-z0-9_]*\b",
                options_source,
            )
        )
    )
    return {
        "scheme_type_values": scheme_types,
        "scheme_type_set_matches_reviewed_api": scheme_types == EXPECTED_SCHEME_TYPES,
        "scheme_template_parameter_is_scheme_type": (
            "template <SchemeType SCHEME_TYPE>" in scheme_source
        ),
        "loop_scheme_is_fixed_specialization": (
            "Scheme<SCHEME_LOOP>::assignSmoothMaskForVertex" in loop_source
        ),
        "topology_refiner_accepts_scheme_type": (
            "TopologyRefiner(Sdc::SchemeType type" in topology_refiner_source
        ),
        "topology_factory_scheme_type_field": (
            "Sdc::SchemeType schemeType" in topology_factory_source
        ),
        "public_scheme_registration_tokens": registration_tokens,
        "public_scheme_registration_hook_available": bool(registration_tokens),
        "public_custom_mask_setters": mask_setters,
        "public_custom_mask_injection_available": bool(mask_setters),
    }


def _build_report(
    predecessor: dict[str, object],
    api: dict[str, object],
    *,
    asserted_public_extension: bool = False,
    post_hoc_rows_supplied: bool = False,
    scientific_mask_selected: bool = False,
    library_patch_or_vendor_requested: bool = False,
) -> dict[str, object]:
    errors: list[str] = []
    if predecessor.get("status") != "passed":
        errors.append("mask-counterfactual predecessor did not pass")
    if (
        predecessor.get("proof_kind")
        != "valence5_opensubdiv_mask_counterfactual_capability"
    ):
        errors.append("mask-counterfactual predecessor identity drift")
    if predecessor.get("reviewed_absolute_tolerance") != REVIEWED_ROW_TOLERANCE:
        errors.append("reviewed tolerance drift")
    if predecessor.get("mask_policy_causal_sufficiency_proven") is not False:
        errors.append("predecessor causal-sufficiency boundary drift")
    if predecessor.get("scientifically_approved") is not False:
        errors.append("predecessor scientific-approval boundary drift")
    if predecessor.get("production_route_enabled") is not False:
        errors.append("predecessor route boundary drift")
    if predecessor.get("counterfactual", {}).get("evaluator_bound") is not False:
        errors.append("predecessor unexpectedly produced evaluator-bound rows")
    if predecessor.get("counterfactual", {}).get("row_component_count") != 0:
        errors.append("predecessor counterfactual row cardinality drift")

    required_api_truths = (
        "scheme_type_set_matches_reviewed_api",
        "scheme_template_parameter_is_scheme_type",
        "loop_scheme_is_fixed_specialization",
        "topology_refiner_accepts_scheme_type",
        "topology_factory_scheme_type_field",
    )
    for key in required_api_truths:
        if api.get(key) is not True:
            errors.append(f"OpenSubdiv public API evidence drift: {key}")
    if api.get("public_scheme_registration_hook_available") is not False:
        errors.append("OpenSubdiv public scheme-registration surface changed")
    if api.get("public_custom_mask_injection_available") is not False:
        errors.append("OpenSubdiv public mask-injection surface changed")

    if asserted_public_extension:
        errors.append(
            "public extension cannot be asserted without an installed public "
            "registration or mask-injection hook"
        )
    if post_hoc_rows_supplied:
        errors.append(
            "post-hoc or JSON-only row substitution is not evaluator-bound evidence"
        )
    if scientific_mask_selected:
        errors.append("this diagnostic cannot choose scientific mask semantics")
    if library_patch_or_vendor_requested:
        errors.append("this diagnostic cannot patch or vendor OpenSubdiv")

    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "valence5_opensubdiv_custom_scheme_feasibility",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_scatter_executed": False,
        "scientifically_approved": False,
        "reviewed_absolute_tolerance": REVIEWED_ROW_TOLERANCE,
        "approved_fixture": "closed valence-5 icosahedron",
        "public_api_evidence": api,
        "valid_standalone_public_extension_path_exists": False,
        "custom_scheme_adapter_constructed": False,
        "evaluator_bound_slimed_mask_rows_generated": False,
        "evaluator_bound_row_component_count": 0,
        "post_hoc_or_json_row_substitution_accepted": False,
        "mask_policy_causal_sufficiency_proven": False,
        "scientific_mask_choice_made": False,
        "library_patch_or_vendoring_performed": False,
        "decision_options": [
            {
                "option": "public non-production OpenSubdiv extension adapter",
                "status": "blocked",
                "reason": PUBLIC_EXTENSION_BLOCKER,
            },
            {
                "option": "standalone custom evaluator outside OpenSubdiv",
                "status": "requires separate architecture and scientific review",
                "reason": (
                    "would not be an OpenSubdiv evaluator-bound public-extension "
                    "counterfactual"
                ),
            },
            {
                "option": "fork, patch, or vendor OpenSubdiv",
                "status": "outside approved dependency policy",
                "reason": "prohibited by this proof-only lane",
            },
            {
                "option": "adopt the standard OpenSubdiv valence-5 mask",
                "status": "requires scientific decision",
                "reason": "this diagnostic does not choose mask semantics",
            },
            {
                "option": "keep valence-5 production route disabled",
                "status": "current truthful state",
                "reason": "no reviewed evaluator-bound custom-mask path exists",
            },
        ],
        "route_blockers": [PUBLIC_EXTENSION_BLOCKER],
        "remaining_boundary": NEXT_BOUNDARY,
        "asserted_public_extension": asserted_public_extension,
        "post_hoc_rows_supplied": post_hoc_rows_supplied,
        "scientific_mask_selected": scientific_mask_selected,
        "library_patch_or_vendor_requested": library_patch_or_vendor_requested,
        "errors": errors,
    }


def evaluate(
    predecessor: dict[str, object],
    api: dict[str, object],
) -> dict[str, object]:
    report = _build_report(predecessor, api)
    adversarial_cases = (
        {"asserted_public_extension": True},
        {"post_hoc_rows_supplied": True},
        {"scientific_mask_selected": True},
        {"library_patch_or_vendor_requested": True},
    )
    report["false_claim_negative_gates_passed"] = all(
        _build_report(predecessor, api, **case)["status"] == "failed"
        for case in adversarial_cases
    )
    if not report["false_claim_negative_gates_passed"]:
        report["errors"].append("false-claim negative gates failed")
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
        paths = {
            "types": include / "sdc/types.h",
            "options": include / "sdc/options.h",
            "scheme": include / "sdc/scheme.h",
            "loop": include / "sdc/loopScheme.h",
            "topology_refiner": include / "far/topologyRefiner.h",
            "topology_factory": include / "far/topologyRefinerFactory.h",
        }
        try:
            sources = {
                key: path.read_text(encoding="utf-8") for key, path in paths.items()
            }
            predecessor = parse_json(
                run(
                    [str(PREDECESSOR), "--json", "--require-opensubdiv"],
                    os.environ.copy(),
                ),
                "mask-counterfactual predecessor",
            )
            report = evaluate(
                predecessor,
                public_extension_evidence(
                    sources["types"],
                    sources["options"],
                    sources["scheme"],
                    sources["loop"],
                    sources["topology_refiner"],
                    sources["topology_factory"],
                ),
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
