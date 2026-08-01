#!/usr/bin/env python3
"""Inventory the proof-only post-Option-D valence-5 architecture gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "636a6583fea3e76e42e8b6b48699e40bc80f4e4d"
RUNNER = Path(
    "scripts/run_irregular_valence5_post_option_d_architecture_gate.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence5_post_option_d_architecture_gate.sh"
)
DOC = Path("docs/irregular_valence5_post_option_d_architecture_gate.md")
ARCHITECTURE_DOC = Path(
    "docs/irregular_valence5_opensubdiv_architecture_decision.md"
)
ALTERNATE_LIBRARY_DOC = Path(
    "docs/irregular_valence5_alternate_library_feasibility.md"
)
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
PREDECESSOR_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_alternate_library_feasibility.py"
)
ARCHITECTURE_PREDECESSOR_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_architecture_decision.py"
)
GLOBAL_INVENTORY = Path("scripts/inventory_opensubdiv_routing_readiness.py")
TEST = Path(
    "tests/test_irregular_valence5_post_option_d_architecture_gate_inventory.py"
)
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")

ALLOWED_PATHS = {
    RUNNER,
    WRAPPER,
    DOC,
    ARCHITECTURE_DOC,
    ALTERNATE_LIBRARY_DOC,
    READINESS,
    PREDECESSOR_INVENTORY,
    ARCHITECTURE_PREDECESSOR_INVENTORY,
    GLOBAL_INVENTORY,
    TEST,
    GLOBAL_TEST,
    Path("scripts/inventory_irregular_valence5_post_option_d_architecture_gate.py"),
    Path("docs/irregular_valence5_option_b_scientific_rebaseline_assessment.md"),
    Path(
        "scripts/inventory_irregular_valence5_option_b_scientific_rebaseline_assessment.py"
    ),
    Path(
        "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.py"
    ),
    Path(
        "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.sh"
    ),
    Path(
        "tests/test_irregular_valence5_option_b_scientific_rebaseline_assessment_inventory.py"
    ),
    Path("experiments/irregular_valence5_option_b_energy_geometry.cpp"),
    Path("experiments/irregular_valence5_option_b_energy_geometry_oracle.cpp"),
    Path("scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py"),
    Path("scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.sh"),
    Path("scripts/inventory_irregular_valence5_option_b_energy_geometry_rebaseline.py"),
    Path("tests/test_irregular_valence5_option_b_energy_geometry_rebaseline_inventory.py"),
    Path("docs/irregular_valence5_option_b_energy_geometry_rebaseline.md"),
}

ANCHORS = {
    RUNNER: (
        'PR149_MERGE_COMMIT = "54fecddb60edd05c0ec4677c87f684ebe5b50301"',
        'PR150_MERGE_COMMIT = "636a6583fea3e76e42e8b6b48699e40bc80f4e4d"',
        '"a23f7974b66ee17a0ffbfffe5a102beeed1965393365d5de36ad0228b1ff1b4c"',
        '"c773ac3cbc25438325aa5f3b7037b49541a06e7038dd556fa47a320e1b52328f"',
        '"dab623d1554ce2face1b7536be95a9f06797707de12f9d78a3df109cf7467123"',
        'PR150_RETRIEVAL_DATE = "2026-07-30"',
        '"neighbor_weight": 0.075',
        '"center_weight": 0.625',
        "PR150_CAPABILITY_ORDER = (",
        'PR150_CANDIDATE_IDS = ("cgal", "libigl", "openmesh", "pmp-library")',
        '"6.2", "cac3e9d75e254928db0e38a3161564216cb01919"',
        '"40e7900ccbd767f1f360e0eb10f0f1a6432e0993"',
        '"f13a3bf79f8dc91cd453b74baa9dc6f97a5a3062"',
        '"f2fb04f4a4188a5c1ab137e83b96e62fa99c639f"',
        "PR150_EXACT_BLOCKER = (",
        '"architecture_option_authorized_for_investigation": "D"',
        '"authorization_scope": "observational_feasibility_only"',
        '"state": "current_behavior_preserved"',
        '"implementation_work_required": False',
        '"explicitly select Option B',
        '"a separate physical re-baselining plan"',
        '"explicitly select Option C',
        '"explicit dependency, license, and maintenance approval"',
        '"state": "completed_no_viable_candidate_in_reviewed_set"',
        '"a separate explicit authorization plus materially new upstream "',
        "PR150 canonical report digest drift",
        "PR149 canonical architecture options drift",
        "PR150 retrieval date drift",
        "PR150 SLIMED valence-5 mask drift",
        "PR150 required capability order drift",
        "PR150 full canonical candidate records or order drift",
        "PR150 fabricated viable candidate",
        "PR150 candidate installability overclaim",
        "no option may be selected, recommended, preferred, or next",
        "Proceed authorizes only this gate, not Option B or C",
        "this decision gate cannot grant scientific approval",
        "this decision gate cannot change dependency policy",
        "this decision gate cannot patch, fork, or vendor OpenSubdiv",
        "this decision gate cannot enable production routing",
        "the current SLIMED valence-5 fallback must remain preserved",
        "this frozen gate cannot reopen Option D",
        "Option D reopening requires both explicit authorization and ",
        "REMAINING_BOUNDARY = (",
    ),
    WRAPPER: (
        "run_irregular_valence5_post_option_d_architecture_gate.py",
        '"$@"',
    ),
    DOC: (
        "proof-only decision gate",
        "`54fecddb60edd05c0ec4677c87f684ebe5b50301`",
        "`decision_selected:false`",
        "`selected_option:null`",
        "`recommended_option:null`",
        "`preferred_option:null`",
        "`automatically_next_option:null`",
        "`proceed_interpreted_as_option_selection:false`",
        "`current_slimed_valence5_fallback_preserved:true`",
        "No option is selected, recommended, preferred, or automatically next",
        "no viable candidate in the reviewed finite non-exhaustive set",
        "No implementation work is required",
        "explicitly select Option B",
        "separate physical re-baselining plan",
        "explicitly select Option C",
        "maintenance policy. Scientific validation follows",
        "Scientific validation follows that approval",
        "materially new upstream or candidate",
        "Both prerequisites are required",
        "no_viable_candidate_in_reviewed_finite_non_exhaustive_set",
        "preserve the current fallback/status quo; or separately approve",
    ),
    ARCHITECTURE_DOC: (
        "PR #150 subsequently completed the bounded Option D observational",
        "No architecture option is selected",
    ),
    ALTERNATE_LIBRARY_DOC: (
        "PR #150 completed this observational survey",
        "post-Option-D decision gate",
        "Option D may be reopened only with",
    ),
    READINESS: (
        "Option D observational survey is complete",
        "No architecture option is selected",
        "Option B requires an explicit user selection",
        "Option C requires an explicit user selection",
        "reopened only with separate explicit authorization and materially new",
    ),
    PREDECESSOR_INVENTORY: (
        "Option D observational survey is complete",
        "post-Option-D gate records the remaining neutral boundary",
    ),
    ARCHITECTURE_PREDECESSOR_INVENTORY: (
        "PR #150 subsequently completed the bounded Option D observational",
        "No architecture option is selected",
    ),
    GLOBAL_INVENTORY: (
        "Option D observational feasibility completed",
        "post-Option-D neutral gate",
        "B explicit user decision boundary",
        "C explicit user decision boundary",
        "Option D reopen boundary",
    ),
    TEST: (
        "test_canonical_report_binds_pr150_and_selects_nothing",
        "test_pr149_canonical_options_and_no_selection_are_binding",
        "test_predecessor_candidate_result_blocker_and_authorization_drift_fail",
        "test_fabricated_viability_and_installability_overclaim_fail",
        "test_option_set_drift_selection_recommendation_preference_and_next_fail",
        "test_proceed_cannot_select_b_or_c",
        "test_status_quo_cannot_be_reported_as_selected_architecture",
        "test_scientific_dependency_patch_route_and_fallback_false_greens_fail",
        "test_option_d_cannot_be_reopened_by_this_gate",
        "test_wrapper_is_local_and_deterministic",
        "test_inventory_passes_and_protected_scope_is_unchanged",
        "test_stale_post_pr150_wording_fails_global_readiness",
    ),
    GLOBAL_TEST: (
        "Option D observational feasibility completed",
        "post-Option-D neutral gate",
        "B explicit user decision boundary",
        "C explicit user decision boundary",
        "Option D reopen boundary",
    ),
}

FORBIDDEN = {
    DOC: (
        "Option B is selected",
        "Option C is selected",
        "Option B is recommended",
        "Option C is preferred",
        "Option B is next",
        "Option C is next",
        "Option D is pending",
        "installability was validated",
    ),
    READINESS: (
        "Option D is now authorized only for this observational feasibility lane",
        "Option D feasibility is pending",
        "Option B is next",
        "Option C is next",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    outputs: list[str] = []
    for command in (
        ["git", "diff", "--name-only", BASE],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        result = subprocess.run(
            command,
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return [], result.stderr.strip() or "git path inventory failed"
        outputs.extend(result.stdout.splitlines())
    return sorted({line for line in outputs if line}), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for relative, needles in ANCHORS.items():
        path = root / relative
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative} missing {needle!r}")

    forbidden_located = 0
    forbidden_expected = 0
    for relative, needles in FORBIDDEN.items():
        path = root / relative
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        for needle in needles:
            forbidden_expected += 1
            if needle in source:
                forbidden_located += 1
                errors.append(f"{relative} contains forbidden claim {needle!r}")

    paths, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    unexpected = sorted(path for path in paths if Path(path) not in ALLOWED_PATHS)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    production_prefixes = ("include/", "src/", "EXEs/", ".github/", "data/")
    production_files = {"Makefile", "scripts/verify_pr_ready.sh"}
    protected_surfaces_changed = any(
        path.startswith(production_prefixes) or path in production_files
        for path in paths
    )
    if protected_surfaces_changed:
        errors.append("protected production or default surfaces changed")

    lane_needle = "post_option_d_architecture_gate"
    protected_roots = (
        root / "include",
        root / "src",
        root / "EXEs",
        root / ".github",
        root / "data",
        root / "Makefile",
        root / "scripts/verify_pr_ready.sh",
    )
    production_leaks: list[str] = []
    for protected in protected_roots:
        if protected.is_file():
            if lane_needle in protected.read_text(encoding="utf-8", errors="ignore"):
                production_leaks.append(str(protected.relative_to(root)))
        elif protected.is_dir():
            for candidate in protected.rglob("*"):
                if candidate.is_file() and lane_needle in candidate.read_text(
                    encoding="utf-8", errors="ignore"
                ):
                    production_leaks.append(str(candidate.relative_to(root)))
    if production_leaks:
        errors.append(
            "decision gate leaked into protected surfaces: "
            + ", ".join(production_leaks)
        )

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "decision_gate_only": True,
        "decision_selected": False,
        "selected_option": None,
        "recommended_option": None,
        "preferred_option": None,
        "automatically_next_option": None,
        "scientific_approval_granted": False,
        "dependency_policy_changed": False,
        "patch_or_vendoring_performed": False,
        "production_route_enabled": False,
        "current_slimed_valence5_fallback_preserved": True,
        "protected_surfaces_changed": protected_surfaces_changed,
        "protected_surface_leaks": production_leaks,
        "changed_paths": paths,
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
        print(f"exact base: {report['exact_base']}")
        print(
            f"anchors: {report['anchors']['located']}/"
            f"{report['anchors']['expected']}"
        )
        print(f"changed paths: {len(report['changed_paths'])}")
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
