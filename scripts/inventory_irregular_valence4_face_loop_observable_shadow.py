#!/usr/bin/env python3
"""Inventory the proof-only valence-4 face-loop observable shadow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "c0fd8fb4b9bb4dc3d7ac2e5237ac349cd85613a1"
EXPERIMENT = Path(
    "experiments/irregular_valence4_face_loop_observable_shadow.cpp"
)
RUNNER = Path(
    "scripts/run_irregular_valence4_face_loop_observable_shadow.py"
)
SHELL = Path(
    "scripts/run_irregular_valence4_face_loop_observable_shadow.sh"
)
DOC = Path("docs/irregular_valence4_face_loop_observable_shadow.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_face_loop_observable_shadow.py"
)
TEST = Path(
    "tests/test_irregular_valence4_face_loop_observable_shadow_inventory.py"
)
PREDECESSOR_DOC = Path(
    "docs/irregular_valence4_scientific_force_algebra_proof.md"
)
PREDECESSOR_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_scientific_force_algebra_proof.py"
)
HISTORICAL_INVENTORIES = {
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path(
        "scripts/inventory_irregular_valence4_production_kernel_call_proof.py"
    ),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_representation.py"
    ),
}

PRODUCTION_ROUTE_PREFLIGHT_SUCCESSOR_PATHS = {
    Path("docs/opensubdiv_routing_readiness_map.md"),
    Path("docs/irregular_valence4_production_route_preflight.md"),
    Path("include/energy_force/Valence4_face_loop_route_preflight.hpp"),
    Path("src/energy_force/Valence4_face_loop_route_preflight.cpp"),
    Path(
        "scripts/inventory_irregular_valence4_production_route_preflight.py"
    ),
    Path(
        "tests/test_irregular_valence4_production_route_preflight_inventory.py"
    ),
    Path("tests/test_valence4_face_loop_route_preflight.cpp"),
}

ALLOWED_PATHS = {
    EXPERIMENT,
    RUNNER,
    SHELL,
    DOC,
    INVENTORY,
    TEST,
    PREDECESSOR_DOC,
    PREDECESSOR_INVENTORY,
} | HISTORICAL_INVENTORIES

ANCHORS = {
    EXPERIMENT: (
        "build_guarded_valence4_topology_source_mapping",
        "prepare_source_keyed_kernel_call",
        "Mesh::element_energy_force_regular",
        "#pragma omp parallel num_threads(requestedThreads)",
        "#pragma omp for schedule(static)",
        "NestedForceOracle",
        "RawForceOracle",
        "source * 9 + kind * 3 + axis",
        "candidate.vertexForces[destination]",
        "candidate.collisionCounts[destination]",
        "independent_layout_sentinel_passed",
        "expected_collision_count_per_component",
        "late_malformed_face_atomic_rejection",
        "late_malformed_complete_shadow_state_atomic",
        "nonfinite_output_negative_regression_passed",
        "collision_count_negative_regression_passed",
        "shadow_outputs_exactly_equal",
        "fully_seeded_shadow_output",
        "flipped_normal_orientation_rejected",
        r"\"proof_only\":true",
        r"\"production_call_shadow\":true",
        r"\"not_production_routing\":true",
        r"\"production_route_enabled\":false",
        r"\"actual_production_force_path_executed\":false",
        r"\"production_one_rings_populated\":false",
    ),
    RUNNER: (
        "source_binding_permutation_invariant",
        "duplicate_row_entries_aggregated_by_source_id",
        "package_observables",
        "actual_openmp_team_contract_passed",
        "[1, 2, 3, 4, 8]",
        "[expected] * 5",
        "late_malformed_face_atomic_rejection",
        "late_malformed_complete_shadow_state_atomic",
        "nonfinite_output_negative_regression_passed",
        "collision_count_negative_regression_passed",
        "candidate_slots_compared_raw",
        "production_one_rings_populated",
    ),
    SHELL: (
        "set -euo pipefail",
        "run_irregular_valence4_face_loop_observable_shadow.py",
    ),
    DOC: (
        "standalone shadow",
        "OpenMP teams of 1, 2, 3, 4, and 8",
        "independent long-double nested",
        "independent raw destination formula",
        "nonfinite",
        "complete `ShadowOutput`",
        "exact eight-face collision coverage",
        "atomic rejection",
        "production_one_rings_populated: false",
        "production face loop",
    ),
    TEST: (
        "test_inventory_passes_with_proof_only_scope",
        "test_production_and_default_surfaces_are_untouched",
        "test_absent_dependency_skips_cleanly",
        "test_present_dependency_proves_serial_openmp_observables",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_git(root: Path, *args: str) -> tuple[str, str | None]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return "", result.stderr.strip() or "git command failed"
    return result.stdout, None


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    diff, error = run_git(root, "diff", "--name-only", BASE)
    if error:
        return [], error
    untracked, error = run_git(
        root, "ls-files", "--others", "--exclude-standard"
    )
    if error:
        return [], error
    return sorted(
        {
            line
            for line in (*diff.splitlines(), *untracked.splitlines())
            if line
        }
    ), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for path, needles in ANCHORS.items():
        text = (
            (root / path).read_text(encoding="utf-8")
            if (root / path).is_file()
            else ""
        )
        for needle in needles:
            expected += 1
            if needle in text:
                located += 1
            else:
                errors.append(f"{path} missing {needle!r}")

    paths, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    if (
        root
        / "scripts/inventory_irregular_valence4_production_route_preflight.py"
    ).is_file():
        paths = [
            path
            for path in paths
            if Path(path) not in PRODUCTION_ROUTE_PREFLIGHT_SUCCESSOR_PATHS
        ]
    unexpected = sorted(path for path in paths if Path(path) not in ALLOWED_PATHS)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    production_prefixes = ("include/", "src/", "EXEs/", ".github/")
    production_files = {
        "Makefile",
        "scripts/verify_pr_ready.sh",
    }
    production_changed = any(
        path.startswith(production_prefixes) or path in production_files
        for path in paths
    )
    if production_changed:
        errors.append("production or default build surfaces changed")

    experiment = (root / EXPERIMENT).read_text(encoding="utf-8")
    raw_oracle_body = experiment.partition(
        "RawForceOracle independent_raw_force_oracle"
    )[2].partition("std::array<double, 3> canonical_face_normal")[0]
    comparison_body = experiment.partition(
        "Comparison compare_output"
    )[2].partition("double output_delta")[0]
    sentinel_reduction_body = experiment.partition(
        "if (actualThreads != 3)"
    )[2].partition("bool shadow_outputs_exactly_equal")[0]
    independent_oracle_reuses_candidate_helper = bool(
        not raw_oracle_body
        or "force_index(" in raw_oracle_body
        or not comparison_body
        or "force_index(" in comparison_body
        or not sentinel_reduction_body
        or "force_index(" in sentinel_reduction_body
    )
    if independent_oracle_reuses_candidate_helper:
        errors.append(
            "independent raw-slot oracle/comparison reuses force_index"
        )
    nonfinite_binding_present = all(
        anchor in experiment
        for anchor in (
            "record_checked_delta",
            "std::numeric_limits<double>::quiet_NaN()",
            "nonfinite_output_negative_regression_passed",
            "all_face_force_and_observable_fields_finite_checked",
            "all_raw_force_slots_finite_checked",
            "all_global_fields_finite_checked",
        )
    )
    if not nonfinite_binding_present:
        errors.append("nonfinite rejection binding is incomplete")
    complete_atomicity_binding_present = all(
        anchor in experiment
        for anchor in (
            "shadow_outputs_exactly_equal",
            "fully_seeded_shadow_output",
            "late_malformed_complete_shadow_state_atomic",
            "productionOneRingsPopulated",
            "requestedThreads",
            "actualThreads",
        )
    )
    if not complete_atomicity_binding_present:
        errors.append("complete ShadowOutput atomicity binding is incomplete")
    production_face_loop_called = (
        "Compute_Energy_And_Force(" in experiment
        or "accumulate_membrane_face_energy_and_forces" in experiment
    )
    if production_face_loop_called:
        errors.append("standalone proof calls the production face loop")
    one_ring_mutated = (
        ".oneRingVertices.push_back" in experiment
        or ".oneRingVertices =" in experiment
    )
    if one_ring_mutated:
        errors.append("standalone proof mutates production one-rings")

    production_paths = [
        root / "include",
        root / "src",
        root / "EXEs",
        root / "Makefile",
        root / ".github",
        root / "scripts/verify_pr_ready.sh",
    ]
    leak_needle = "irregular_valence4_face_loop_observable_shadow"
    production_leaks: list[str] = []
    for path in production_paths:
        if path.is_file():
            if leak_needle in path.read_text(encoding="utf-8", errors="ignore"):
                production_leaks.append(str(path.relative_to(root)))
        elif path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and leak_needle in candidate.read_text(
                    encoding="utf-8", errors="ignore"
                ):
                    production_leaks.append(str(candidate.relative_to(root)))
    if production_leaks:
        errors.append(
            "proof lane leaked into production/default surfaces: "
            + ", ".join(production_leaks)
        )

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "production_call_shadow": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_one_rings_populated": False,
        "independent_oracle_reuses_candidate_helper":
            independent_oracle_reuses_candidate_helper,
        "nonfinite_binding_present": nonfinite_binding_present,
        "complete_atomicity_binding_present":
            complete_atomicity_binding_present,
        "production_or_default_surfaces_changed": production_changed,
        "production_face_loop_called": production_face_loop_called,
        "production_one_rings_mutated": one_ring_mutated,
        "production_default_leaks": production_leaks,
        "changed_paths": paths,
        "anchors": {"located": located, "expected": expected},
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
