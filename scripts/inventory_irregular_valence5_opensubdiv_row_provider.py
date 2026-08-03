#!/usr/bin/env python3
"""Inventory the guarded stock valence-5 Option B Phase 1 row provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "0b2b6dd425cb47e703c02dce0d32f89e23721b0d"
HEADER = Path("include/mesh/OpenSubdiv_valence5_row_provider.hpp")
IMPLEMENTATION = Path("src/mesh/OpenSubdiv_valence5_row_provider.cpp")
HARNESS = Path("experiments/irregular_valence5_opensubdiv_row_provider.cpp")
RUNNER = Path("scripts/run_irregular_valence5_opensubdiv_row_provider.py")
WRAPPER = Path("scripts/run_irregular_valence5_opensubdiv_row_provider.sh")
DOC = Path("docs/irregular_valence5_opensubdiv_row_provider.md")
TEST = Path("tests/test_irregular_valence5_opensubdiv_row_provider_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_opensubdiv_row_provider.py")
MAKEFILE = Path("Makefile")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")
HISTORICAL_INVENTORIES = {
    Path("scripts/inventory_irregular_valence5_option_b_output_visibility.py"),
    Path("scripts/inventory_irregular_valence5_option_b_scientific_decision.py"),
    Path("scripts/inventory_irregular_valence5_option_b_selection_record.py"),
}
COMPATIBILITY_GUARDS = {
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path("scripts/inventory_irregular_valence4_production_kernel_call_proof.py"),
    Path("scripts/inventory_irregular_valence4_topology_source_representation.py"),
    Path("tests/test_irregular_valence4_topology_source_representation_inventory.py"),
    Path("scripts/inventory_opensubdiv_regular_cpp_adapter_proof.py"),
}
ALLOWED_PATHS = {
    HEADER, IMPLEMENTATION, HARNESS, RUNNER, WRAPPER, DOC, TEST, SELF,
    MAKEFILE, READINESS, GLOBAL, GLOBAL_TEST, *HISTORICAL_INVENTORIES,
    *COMPATIBILITY_GUARDS,
}
ANCHORS = {
    MAKEFILE: (
        "USE_OPENSUBDIV_VALENCE5 ?= 0",
        "-DUSE_OPENSUBDIV_VALENCE5",
        "USE_OPENSUBDIV_VALENCE5=1 requires OPENSUBDIV_ROOT=/path/to/opensubdiv",
    ),
    HEADER: (
        "phase1ProviderExplicitRequest = false",
        "const Mesh &mesh",
        "productionRouteEnabled = false",
        "productionMeshMutated = false",
        "defaultEvaluatorCaller = false",
    ),
    IMPLEMENTATION: (
        "#ifdef USE_OPENSUBDIV_VALENCE5",
        "kApprovedFaceCount = 20",
        "kFaceSourceCount = 9",
        "LimitStencilTableFactoryReal<double>",
        "exact_topology_identity(mesh)",
        "target.sourceIds = sourceIds",
        "result.accepted = true",
    ),
    HARNESS: (
        "snapshot_one_rings",
        "invalid_topology_rejected",
        "production_one_rings_unchanged",
        "production_route_enabled\\\":false",
        "actual_production_force_path_executed\\\":false",
        "production_mesh_mutated\\\":false",
    ),
    RUNNER: (
        "REFERENCE_TOLERANCE = 5.0e-6",
        "TemporaryDirectory(prefix=\"slimed-valence5-phase1-\")",
        "accepted_float_source_order_proof",
        "20x3x7x9_source_keyed",
        "phase2_integration_authorized\": False",
        "first_output == second_output",
    ),
    WRAPPER: (
        "run_irregular_valence5_opensubdiv_row_provider.py",
        '"$@"',
    ),
    DOC: (
        "implements only Phase 1",
        "stock whole-Ptex OpenSubdiv limit",
        "6.568566814357801e-7",
        "production route, face loop, force path, and mesh mutation: all false",
        "Phase 2 remains separately gated",
    ),
    TEST: (
        "test_synthetic_rows_compare_exactly",
        "test_source_mapping_drift_is_visible",
        "test_nonfinite_and_boolean_coefficients_fail",
        "test_phase1_inventory_passes",
        "test_enabled_provider_matches_accepted_proof_when_available",
    ),
    READINESS: (
        "Phase 1 guarded stock row provider is implemented",
        "Phase 2 remains unapproved",
    ),
    GLOBAL: (
        "Option B Phase 1 row provider implemented",
        "Phase 1 provider remains non-production",
    ),
    GLOBAL_TEST: (
        "Option B Phase 1 row provider implemented",
        "Phase 1 provider remains non-production",
    ),
    Path("scripts/inventory_irregular_valence5_option_b_selection_record.py"): (
        "PHASE1_SUCCESSOR_PATHS",
        "inventory_irregular_valence5_opensubdiv_row_provider.py",
    ),
    Path("scripts/inventory_irregular_valence5_option_b_scientific_decision.py"): (
        "PHASE1_SUCCESSOR_PATHS",
        "inventory_irregular_valence5_opensubdiv_row_provider.py",
    ),
    Path("scripts/inventory_irregular_valence5_option_b_output_visibility.py"): (
        "PHASE1_SUCCESSOR_PATHS",
        "inventory_irregular_valence5_opensubdiv_row_provider.py",
    ),
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"): (
        "phase1_makefile_change_is_exact_and_guarded",
        "PHASE1_MAKEFILE_BASE",
    ),
    Path("scripts/inventory_irregular_valence4_production_kernel_call_proof.py"): (
        "phase1_makefile_change_is_exact_and_guarded",
        "PHASE1_MAKEFILE_BASE",
    ),
    Path("scripts/inventory_irregular_valence4_topology_source_representation.py"): (
        "phase1_makefile_change_is_exact_and_guarded",
        "PHASE1_MAKEFILE_BASE",
    ),
    Path("tests/test_irregular_valence4_topology_source_representation_inventory.py"): (
        "phase1_makefile_change_is_exact_and_guarded",
    ),
    Path("scripts/inventory_opensubdiv_regular_cpp_adapter_proof.py"): (
        "OpenSubdiv_valence5_row_provider.hpp",
        "OpenSubdiv_valence5_row_provider.cpp",
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

    mode_result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "ls-files", "--stage", str(WRAPPER)],
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
        errors.append("expected Phase 1 paths are unchanged: " + ", ".join(map(str, missing)))

    return {
        "status": "passed" if not errors else "failed",
        "base": BASE,
        "located_anchors": located,
        "expected_anchors": expected,
        "changed_paths": changed,
        "wrapper_git_mode": wrapper_mode,
        "production_route_enabled": False,
        "phase2_integration_authorized": False,
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
            f"Option B Phase 1 row-provider inventory: {report['status']} "
            f"({report['located_anchors']}/{report['expected_anchors']})"
        )
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
