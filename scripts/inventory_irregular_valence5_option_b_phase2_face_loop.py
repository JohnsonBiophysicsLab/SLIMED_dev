#!/usr/bin/env python3
"""Inventory the guarded Option B Phase 2 face-loop integration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "324868c5a19c58933c411f324312d4286a802792"
HEADER = Path("include/energy_force/Valence5_opensubdiv_face_loop.hpp")
GENERIC_HEADER = Path("include/energy_force/Guarded_source_keyed_production_face_loop.hpp")
IMPLEMENTATION = Path("src/energy_force/Valence5_opensubdiv_face_loop.cpp")
FACE_LOOP = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
SOURCE_KEYED_HEADER = Path("include/energy_force/Source_keyed_kernel_call.hpp")
SOURCE_KEYED_IMPLEMENTATION = Path("src/energy_force/Source_keyed_kernel_call.cpp")
HARNESS = Path("experiments/irregular_valence5_option_b_phase2_face_loop.cpp")
ORACLE = Path("experiments/irregular_valence5_option_b_energy_geometry_oracle.cpp")
RUNNER = Path("scripts/run_irregular_valence5_option_b_phase2_face_loop.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_phase2_face_loop.sh")
DOC = Path("docs/irregular_valence5_option_b_phase2_face_loop.md")
TEST = Path("tests/test_irregular_valence5_option_b_phase2_face_loop_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_phase2_face_loop.py")
REGULAR_COMPATIBILITY = Path("scripts/inventory_opensubdiv_regular_cpp_adapter_proof.py")
PHASE3_PATHS = {
    Path("docs/irregular_valence5_option_b_phase3_activation.md"),
    Path("docs/opensubdiv_routing_readiness_map.md"),
    Path("experiments/irregular_valence5_option_b_phase3_activation.cpp"),
    Path("scripts/inventory_irregular_valence5_option_b_phase3_activation.py"),
    Path("scripts/inventory_opensubdiv_routing_readiness.py"),
    Path("scripts/run_irregular_valence5_option_b_phase3_activation.py"),
    Path("scripts/run_irregular_valence5_option_b_phase3_activation.sh"),
    Path("tests/test_irregular_valence5_option_b_phase3_activation_inventory.py"),
    Path("tests/test_opensubdiv_routing_readiness_inventory.py"),
}
ALLOWED_PATHS = {
    HEADER, GENERIC_HEADER, IMPLEMENTATION, FACE_LOOP, SOURCE_KEYED_HEADER,
    SOURCE_KEYED_IMPLEMENTATION, HARNESS, RUNNER, WRAPPER, DOC, TEST, SELF,
    REGULAR_COMPATIBILITY,
} | PHASE3_PATHS
ANCHORS = {
    HEADER: (
        "reviewerApprovedExplicitRequest = false",
        "productionRouteEnabled = false",
        "defaultEvaluatorCaller = false",
        "phase3ActivationAuthorized = false",
    ),
    GENERIC_HEADER: (
        "execute_guarded_source_keyed_production_face_loop",
        "validated before the first Mesh write",
        "does not select or enable a default route",
    ),
    IMPLEMENTATION: (
        '"SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2"',
        "kReviewedSampleCount = 3",
        "mapping.originalSourceIds = sourceIds",
        "evaluate_scientific_dry_run",
        "completeTransactionValidatedBeforeMutation = true",
        "actualProductionForcePathExecuted = true",
        "phase3ActivationAuthorized = false",
    ),
    FACE_LOOP: (
        "execute_guarded_source_keyed_production_face_loop",
        "All route inputs and destinations are validated before the first write",
        "execute_guarded_valence4_production_face_loop",
    ),
    SOURCE_KEYED_HEADER: (
        "productionOneRingEmpty = false",
        "productionOneRingBypassed = false",
    ),
    SOURCE_KEYED_IMPLEMENTATION: (
        "production one-ring disposition",
    ),
    HARNESS: (
        "explicit_gate_rejection_atomic",
        "default_caller_remained_fallback",
        "production_one_rings_preserved",
        "checkpoint_membrane_force_max_abs_difference",
        "aggregate_source_forces",
        "long_double_oracle_package_written",
    ),
    ORACLE: (
        '\\"independent_long_double_oracle\\":true',
        '\\"calls_element_energy_force_regular\\":false',
    ),
    RUNNER: (
        "PRODUCTION_TOLERANCE = 1.0e-10",
        "PHASE2_EXPECTED_GLOBAL_ENERGY",
        "PHASE2_EXPECTED_FACE_CURVATURE",
        "EXPECTED_CANONICAL_OBSERVABLE_VECTOR",
        "serial_openmp_force_max_abs_difference",
        "independent_long_double_oracle_max_abs_difference",
        "ORACLE_ABSOLUTE_TOLERANCE",
        "restart_roundtrip_exact",
        '"phase3_activation_authorized": False',
    ),
    WRAPPER: (
        "run_irregular_valence5_option_b_phase2_face_loop.py",
        '"$@"',
    ),
    DOC: (
        "Phase 2 only",
        "default production route",
        "SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2=1",
        "Phase 3 remains separately gated",
    ),
    TEST: (
        "test_phase2_inventory_passes",
        "test_accepted_baseline_has_complete_shape",
        "test_numeric_guards_reject_false_and_nonfinite_values",
        "test_enabled_phase2_suite_when_available",
    ),
    REGULAR_COMPATIBILITY: (
        'Path("include/energy_force/Valence5_opensubdiv_face_loop.hpp")',
        'Path("src/energy_force/Valence5_opensubdiv_face_loop.cpp")',
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
        result = subprocess.run(command, cwd=root, check=False, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

    compute_source = (root / FACE_LOOP).read_text(encoding="utf-8")
    default_caller = compute_source.split("void Mesh::Compute_Energy_And_Force()", 1)[1]
    default_caller = default_caller.split("void Mesh::complete_energy_force_after_membrane_accumulation", 1)[0]
    phase2_default_caller_markers = (
        "SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2",
        "evaluate_guarded_valence5_face_loop(",
    )
    if any(marker in default_caller for marker in phase2_default_caller_markers):
        errors.append("Mesh::Compute_Energy_And_Force unexpectedly selects valence-5 Phase 2")

    mode = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "ls-files", "--stage", str(WRAPPER)],
        cwd=root, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
        errors.append("expected Phase 2 paths are unchanged: " + ", ".join(map(str, missing)))

    return {
        "status": "passed" if not errors else "failed",
        "base": BASE,
        "located_anchors": located,
        "expected_anchors": expected,
        "changed_paths": changed,
        "wrapper_git_mode": wrapper_mode,
        "production_face_loop_exercised": True,
        "production_route_enabled": False,
        "default_evaluator_caller": False,
        "phase3_activation_authorized": False,
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
        print(f"Option B Phase 2 inventory: {report['status']} "
              f"({report['located_anchors']}/{report['expected_anchors']})")
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
