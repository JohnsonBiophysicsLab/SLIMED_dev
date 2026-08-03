#!/usr/bin/env python3
"""Inventory the Option B Phase 3 guarded production activation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "86605aa4a1df6bb5a4a72adf34cdc021abdac1a5"
HEADER = Path("include/energy_force/Valence5_opensubdiv_face_loop.hpp")
IMPLEMENTATION = Path("src/energy_force/Valence5_opensubdiv_face_loop.cpp")
DEFAULT_CALLER = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
HARNESS = Path("experiments/irregular_valence5_option_b_phase3_activation.cpp")
RUNNER = Path("scripts/run_irregular_valence5_option_b_phase3_activation.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_phase3_activation.sh")
DOC = Path("docs/irregular_valence5_option_b_phase3_activation.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL_INVENTORY = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")
PHASE2_INVENTORY = Path("scripts/inventory_irregular_valence5_option_b_phase2_face_loop.py")
TEST = Path("tests/test_irregular_valence5_option_b_phase3_activation_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_phase3_activation.py")
ALLOWED_PATHS = {
    HEADER,
    IMPLEMENTATION,
    DEFAULT_CALLER,
    HARNESS,
    RUNNER,
    WRAPPER,
    DOC,
    READINESS,
    GLOBAL_INVENTORY,
    GLOBAL_TEST,
    PHASE2_INVENTORY,
    TEST,
    SELF,
}
ANCHORS = {
    HEADER: (
        "opensubdiv_valence5_production_routing_requested",
        "evaluate_guarded_valence5_production_route",
        "SLIMED_USE_OPENSUBDIV_VALENCE5=1",
        "dependency-disabled build is rejected before mesh mutation",
    ),
    IMPLEMENTATION: (
        '"SLIMED_USE_OPENSUBDIV_VALENCE5"',
        "evaluate_guarded_valence5_face_loop",
        "result.productionRouteEnabled = true",
        "result.defaultEvaluatorCaller = true",
        "result.phase3ActivationAuthorized = true",
    ),
    DEFAULT_CALLER: (
        "opensubdiv_valence5_production_routing_requested",
        "evaluate_guarded_valence5_production_route(*this)",
        "conflicting extraordinary OpenSubdiv production routes",
        "Option B production route, but preflight rejected it ",
        "refresh_energy_force_geometry(*this)",
    ),
    HARNESS: (
        "dependency_absent_request_rejected_atomically",
        "conflicting_route_request_rejected_atomically",
        "default_vs_direct_force_max_abs_difference",
        "checkpoint_roundtrip_exact",
        "production_one_rings_preserved",
    ),
    RUNNER: (
        "PRODUCTION_TOLERANCE = 1.0e-10",
        "PHASE2_EXPECTED_GLOBAL_ENERGY",
        "PHASE2_EXPECTED_FACE_CURVATURE",
        "default_enabled_build_fallback_max_abs_difference",
        '"rollback": "unset SLIMED_USE_OPENSUBDIV_VALENCE5"',
        '"output_and_restart_through_default_caller_passed": True',
    ),
    WRAPPER: (
        "run_irregular_valence5_option_b_phase3_activation.py",
        '"$@"',
    ),
    DOC: (
        "Phase 3 guarded production activation",
        "SLIMED_USE_OPENSUBDIV_VALENCE5=1",
        "complete rollback",
        "Default builds remain OpenSubdiv-free",
        "does not widen any tolerance",
    ),
    READINESS: (
        "Phase 3 guarded production route is activated",
        "`SLIMED_USE_OPENSUBDIV_VALENCE5` restores the unchanged current SLIMED",
    ),
    GLOBAL_INVENTORY: (
        "Option B guarded production route activated",
        "Option B fallback rollback preserved",
    ),
    GLOBAL_TEST: (
        "Option B guarded production route activated",
        "Option B fallback rollback preserved",
    ),
    TEST: (
        "test_phase3_inventory_passes",
        "test_scientific_expectations_remain_fixed",
        "test_enabled_phase3_suite_when_available",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    paths: list[str] = []
    for command in (
        ["git", "-c", f"safe.directory={root}", "diff", "--name-only", BASE],
        ["git", "-c", f"safe.directory={root}", "ls-files", "--others", "--exclude-standard"],
    ):
        result = subprocess.run(
            command,
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode:
            return [], result.stderr.strip() or "git path inventory failed"
        paths.extend(result.stdout.splitlines())
    return sorted(set(paths)), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    expected = 0
    located = 0
    for relative, needles in ANCHORS.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
            expected += len(needles)
            continue
        source = path.read_text(encoding="utf-8")
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative} missing {needle!r}")

    caller_source = (root / DEFAULT_CALLER).read_text(encoding="utf-8")
    caller = caller_source.split("void Mesh::Compute_Energy_And_Force()", 1)[1]
    caller = caller.split("void Mesh::complete_energy_force_after_membrane_accumulation", 1)[0]
    route_position = caller.find("evaluate_guarded_valence5_production_route(*this)")
    fallback_position = caller.find("refresh_energy_force_geometry(*this)")
    if route_position < 0 or fallback_position < 0 or route_position >= fallback_position:
        errors.append("valence-5 route must precede the unchanged fallback in the default evaluator")

    mode = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "ls-files", "--stage", str(WRAPPER)],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    wrapper_mode = mode.stdout.split(maxsplit=1)[0] if mode.stdout.strip() else None
    if wrapper_mode != "100755":
        errors.append(f"{WRAPPER} must have Git mode 100755 (got {wrapper_mode})")

    changed, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    changed_set = set(map(Path, changed))
    unexpected = sorted(changed_set - ALLOWED_PATHS)
    missing = sorted(ALLOWED_PATHS - changed_set)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(map(str, unexpected)))
    if missing:
        errors.append("expected Phase 3 paths are unchanged: " + ", ".join(map(str, missing)))

    return {
        "status": "passed" if not errors else "failed",
        "base": BASE,
        "located_anchors": located,
        "expected_anchors": expected,
        "changed_paths": changed,
        "wrapper_git_mode": wrapper_mode,
        "production_route_enabled": True,
        "default_evaluator_caller": True,
        "phase3_activation_authorized": True,
        "rollback_gate": "SLIMED_USE_OPENSUBDIV_VALENCE5",
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
            f"Option B Phase 3 inventory: {report['status']} "
            f"({report['located_anchors']}/{report['expected_anchors']})"
        )
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
