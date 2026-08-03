#!/usr/bin/env python3
"""Inventory the accepted-but-unrouted Option B selection record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "a25a13906a314a40f5442f6068a3bde8bd0e8142"
RUNNER = Path("scripts/run_irregular_valence5_option_b_selection_record.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_selection_record.sh")
DOC = Path("docs/irregular_valence5_option_b_selection_record.md")
TEST = Path("tests/test_irregular_valence5_option_b_selection_record_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_selection_record.py")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")
PREDECESSOR_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_option_b_scientific_decision.py"
)
OUTPUT_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_option_b_output_visibility.py"
)
ALLOWED_PATHS = {
    RUNNER, WRAPPER, DOC, TEST, SELF, READINESS, GLOBAL, GLOBAL_TEST,
    PREDECESSOR_INVENTORY, OUTPUT_INVENTORY,
}
PHASE1_SUCCESSOR_PATHS = {
    Path("Makefile"),
    Path("include/mesh/OpenSubdiv_valence5_row_provider.hpp"),
    Path("src/mesh/OpenSubdiv_valence5_row_provider.cpp"),
    Path("experiments/irregular_valence5_opensubdiv_row_provider.cpp"),
    Path("scripts/run_irregular_valence5_opensubdiv_row_provider.py"),
    Path("scripts/run_irregular_valence5_opensubdiv_row_provider.sh"),
    Path("scripts/inventory_irregular_valence5_opensubdiv_row_provider.py"),
    Path("tests/test_irregular_valence5_opensubdiv_row_provider_inventory.py"),
    Path("docs/irregular_valence5_opensubdiv_row_provider.md"),
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path("scripts/inventory_irregular_valence4_production_kernel_call_proof.py"),
    Path("scripts/inventory_irregular_valence4_topology_source_representation.py"),
    Path("tests/test_irregular_valence4_topology_source_representation_inventory.py"),
    Path("scripts/inventory_opensubdiv_regular_cpp_adapter_proof.py"),
}
ALLOWED_PATHS |= PHASE1_SUCCESSOR_PATHS
ANCHORS = {
    RUNNER: (
        'PREDECESSOR_MERGE_COMMIT = "023db1ea053f90e895175cf89e88ed437dad4b93"',
        'DECISION = "accept"',
        'DECISION_DATE = "2026-08-02"',
        'DECISION_SOURCE = "explicit_user_instruction"',
        'DECISION_TEXT = "Accept Option B."',
        "CANONICAL_PHASE_BINDINGS = (",
        '(1, "guarded_stock_valence5_row_provider", "requires_separate_implementation_approval", False)',
        '(2, "guarded_face_loop_integration_and_rebaseline", "requires_separate_reviewed_pr", True)',
        '(3, "explicit_route_activation", "requires_separate_reviewer_and_user_approval", True)',
        "for phase, name, authorization, production_mutation in CANONICAL_PHASE_BINDINGS",
        '"decision_recorded": decision_recorded',
        '"option_b_selected": option_b_selected',
        '"option_b_recommended": option_b_recommended',
        '"stock_semantics_scientifically_approved":',
        '"scientific_rebaseline_plan_authorized":',
        '"production_routing_plan_authorized": production_routing_plan_authorized',
        '"implementation_authorized": implementation_authorized',
        '"production_route_enabled": production_route_enabled',
        "this selection record cannot authorize implementation",
        "this selection record cannot enable production routing",
        "scientific decision predecessor evidence drift",
        "scientific decision predecessor measurements drift",
        "the recorded decision must remain an explicit user instruction",
        "the separately gated three-phase implementation plan drifted",
    ),
    WRAPPER: ("run_irregular_valence5_option_b_selection_record.py", '"$@"'),
    DOC: (
        "Accept Option B.",
        "`option_b_selected:true`",
        "`stock_semantics_scientifically_approved:true`",
        "`implementation_authorized:false`",
        "`production_route_enabled:false`",
        "Phase 1 — guarded stock valence-5 row provider",
        "Phase 2 — guarded face-loop integration and scientific re-baseline",
        "Phase 3 — explicit activation",
        "Default builds remain OpenSubdiv-free",
        "fallback cannot be removed",
    ),
    TEST: (
        "test_canonical_record_selects_and_approves_but_does_not_route",
        "test_predecessor_identity_and_non_authorizing_state_are_binding",
        "test_selection_and_plan_authorizations_cannot_false_negative",
        "test_explicit_user_decision_provenance_is_binding",
        "test_recommendation_implementation_and_route_false_greens_fail",
        "test_wrapper_executable_mode_is_inventory_bound",
    ),
    READINESS: (
        "Option B is selected and stock semantics are scientifically approved",
        "implementation and production routing remain disabled",
        "fallback remains active",
    ),
    GLOBAL: (
        "Option B accepted selection recorded",
        "Option B accepted but remains unrouted",
    ),
    GLOBAL_TEST: (
        "Option B accepted selection recorded",
        "Option B accepted but remains unrouted",
    ),
    PREDECESSOR_INVENTORY: (
        "SELECTION_RUNNER",
        "SELECTION_INVENTORY",
        "CUDA_PLAN_DOC",
    ),
    OUTPUT_INVENTORY: (
        "SELECTION_RUNNER",
        "SELECTION_INVENTORY",
        "CUDA_PLAN_DOC",
    ),
}
FORBIDDEN = {
    RUNNER: (
        '"option_b_recommended": True',
        '"implementation_authorized": True',
        '"production_route_enabled": True',
    ),
    DOC: (
        "implementation is authorized",
        "production routing is enabled",
        "fallback is removed",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    paths: list[str] = []
    for command in (
        ["git", "-c", f"safe.directory={root}", "diff", "--name-only", BASE],
        [
            "git", "-c", f"safe.directory={root}", "ls-files", "--others",
            "--exclude-standard",
        ],
    ):
        result = subprocess.run(
            command, cwd=root, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return [], result.stderr.strip() or "git path inventory failed"
        paths.extend(result.stdout.splitlines())
    return sorted(set(paths)), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    expected = 0
    located = 0
    for relative, needles in ANCHORS.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative} missing {needle!r}")
    for relative, needles in FORBIDDEN.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            if needle in source:
                errors.append(f"{relative} contains forbidden {needle!r}")
    mode_result = subprocess.run(
        [
            "git", "-c", f"safe.directory={root}", "ls-files", "--stage",
            str(WRAPPER),
        ],
        cwd=root, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    wrapper_mode = (
        mode_result.stdout.split(maxsplit=1)[0]
        if mode_result.returncode == 0 and mode_result.stdout.strip()
        else None
    )
    if wrapper_mode != "100755":
        errors.append(
            f"{WRAPPER} must be executable in Git (mode 100755, got {wrapper_mode})"
        )
    changed, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    changed_set = set(map(Path, changed))
    unexpected = sorted(changed_set - ALLOWED_PATHS)
    missing = sorted(path for path in ALLOWED_PATHS if path not in changed_set)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(map(str, unexpected)))
    if missing:
        errors.append("expected selection paths are unchanged: " + ", ".join(map(str, missing)))
    return {
        "status": "passed" if not errors else "failed",
        "base": BASE,
        "located_anchors": located,
        "expected_anchors": expected,
        "changed_paths": changed,
        "wrapper_git_mode": wrapper_mode,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = collect(repo_root())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"Option B selection record inventory: {report['status']} "
            f"({report['located_anchors']}/{report['expected_anchors']})"
        )
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
