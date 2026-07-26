#!/usr/bin/env python3
"""Inventory the proof-only valence-4 source-keyed kernel adapter lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "e28d32ce211a5db0889e437be9b043255e8eca1b"
SCIENTIFIC_FORCE_ALGEBRA_SUCCESSOR_PATHS = {
    Path("include/mesh/Mesh.hpp"),
    Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
    Path("tests/test_variable_cardinality_force_algebra.cpp"),
    Path("docs/irregular_valence4_scientific_force_algebra_proof.md"),
    Path(
        "scripts/inventory_irregular_valence4_scientific_force_algebra_proof.py"
    ),
    Path(
        "tests/test_irregular_valence4_scientific_force_algebra_proof_inventory.py"
    ),
    Path("docs/irregular_valence4_face_loop_observable_shadow.md"),
    Path("experiments/irregular_valence4_face_loop_observable_shadow.cpp"),
    Path("scripts/inventory_irregular_valence4_face_loop_observable_shadow.py"),
    Path("scripts/run_irregular_valence4_face_loop_observable_shadow.py"),
    Path("scripts/run_irregular_valence4_face_loop_observable_shadow.sh"),
    Path("tests/test_irregular_valence4_face_loop_observable_shadow_inventory.py"),
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
HEADER = Path("experiments/irregular_valence4_source_keyed_kernel_adapter.hpp")
EXPERIMENT = Path("experiments/irregular_valence4_source_keyed_kernel_adapter.cpp")
RUNNER = Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.py")
SHELL = Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh")
DOC = Path("docs/irregular_valence4_source_keyed_kernel_adapter.md")
INVENTORY = Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py")
TEST = Path("tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py")
PRODUCTION_HEADER = Path(
    "include/energy_force/Source_keyed_kernel_call.hpp"
)
PRODUCTION_SOURCE = Path(
    "src/energy_force/Source_keyed_kernel_call.cpp"
)

PRODUCTION_KERNEL_CALL_PROOF_PATHS = {
    PRODUCTION_HEADER,
    PRODUCTION_SOURCE,
    Path("docs/irregular_valence4_production_kernel_call_proof.md"),
    Path(
        "scripts/inventory_irregular_valence4_production_kernel_call_proof.py"
    ),
    Path(
        "tests/test_irregular_valence4_production_kernel_call_proof_inventory.py"
    ),
    Path("tests/test_source_keyed_kernel_call.cpp"),
}

PREDECESSOR_INVENTORIES = {
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path("scripts/inventory_irregular_valence4_topology_source_representation.py"),
    Path("scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"),
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
}

ALLOWED_PATHS = {
    HEADER,
    EXPERIMENT,
    RUNNER,
    SHELL,
    DOC,
    INVENTORY,
    TEST,
} | PREDECESSOR_INVENTORIES | PRODUCTION_KERNEL_CALL_PROOF_PATHS

ANCHORS = {
    HEADER: (
        "energy_force/Source_keyed_kernel_call.hpp",
        "SourceMappingView",
        "SourceKeyedRow",
        "PreparedSourceKeyedKernelCall",
        "prepare_source_keyed_kernel_call",
        "accumulate_source_keyed_force_contributions",
    ),
    PRODUCTION_HEADER: (
        "SourceKeyedKernelCallInput",
        "PreparedSourceKeyedKernelCall",
        "prepare_source_keyed_kernel_call",
        "accumulate_source_keyed_force_contributions",
        "does not mutate the",
    ),
    PRODUCTION_SOURCE: (
        "canonical_source_ids",
        "canonicalize_derivative_row",
        "canonicalize_forces",
        "accumulate_source_keyed_force_contributions",
        "contains a duplicate original source id",
        "row mapping/cardinality",
        "rejected nonfinite row data",
        "rejected face orientation drift",
        "requires empty production",
    ),
    EXPERIMENT: (
        "energy_force/Valence4_face_loop_route_preflight.hpp",
        "build_guarded_valence4_topology_source_mapping",
        "independent_scatter_oracle",
        "compare_with_independent_oracle",
        "outOfRangeRejected",
        "cardinalityRejected",
        "incompleteRowCoverageRejected",
        "forceDuplicateRejected",
        "nonfiniteRowRejected",
        "nonfiniteForceRejected",
        "orientationRejected",
        "mappingDriftRejected",
        "nonemptyOneRingRejected",
        "mixedRowRejected",
        "permuted_bindings",
        "split_duplicate_rows",
        "compare_adapted_inputs",
        "invoke_guarded_scientific_request",
        "evaluate_guarded_valence4_face_loop_scientific_request",
        "defaultOffRejected",
        "meshStateUnchanged",
        r"\"guarded_scientific_request_composition\":{",
        r"\"source_binding_permutation_invariant\":",
        r"\"duplicate_row_entries_aggregated_by_source_id\":",
        r"\"actual_production_force_path_executed\":false",
        r"\"production_one_rings_mutated\":false",
    ),
    RUNNER: (
        "run_irregular_valence4_opensubdiv_force_formula_proof.sh",
        "fresh row tensor dimensions are not 8x3x7x6",
        "face_force_contributions",
        "source-keyed adapter evidence did not pass",
        "actual_production_force_path_executed",
        "guarded_scientific_request_composition",
        "fresh_opensubdiv_rows_consumed",
        "default_off_request_rejected",
        "max_observable_difference",
        "max_source_force_difference",
        "source_binding_permutation_invariant",
        "duplicate_row_entries_aggregated_by_source_id",
    ),
    SHELL: ("set -Eeuo pipefail",),
    DOC: (
        "backend-neutral",
        "variable-cardinality",
        "Input row and force column order",
        "split and\nreversed duplicates",
        "Independent Oracle",
        "production_route_enabled: false",
        "Production valence-4 route activation remains unapproved.",
    ),
    TEST: (
        "test_inventory_passes_with_proof_only_scope",
        "test_default_and_production_surfaces_are_unchanged",
        "test_absent_dependency_skips_cleanly",
        "test_present_dependency_adapter_passes",
        "source_binding_permutation_invariant",
        "duplicate_row_entries_aggregated_by_source_id",
        "guarded_scientific_request_composition",
        "default_off_request_rejected",
        "mesh_state_unchanged",
        "route_remained_disabled",
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
    for path, needles in ANCHORS.items():
        text = (root / path).read_text(encoding="utf-8") if (root / path).is_file() else ""
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
        / "scripts/inventory_irregular_valence4_scientific_force_algebra_proof.py"
    ).is_file():
        paths = [
            path
            for path in paths
            if Path(path) not in SCIENTIFIC_FORCE_ALGEBRA_SUCCESSOR_PATHS
        ]
    unexpected = sorted(path for path in paths if Path(path) not in ALLOWED_PATHS)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    production_prefixes = (
        "include/",
        "src/",
        "EXEs/",
        ".github/",
        "data/fixtures/",
    )
    production_files = {"Makefile", "scripts/verify_pr_ready.sh"}
    production_changed = any(
        (
            path.startswith(production_prefixes)
            or path in production_files
        )
        and Path(path) not in PRODUCTION_KERNEL_CALL_PROOF_PATHS
        for path in paths
    )
    if production_changed:
        errors.append("production/default/fixture surfaces changed")

    header = (root / HEADER).read_text(encoding="utf-8")
    experiment = (root / EXPERIMENT).read_text(encoding="utf-8")
    production_helper = (
        (root / PRODUCTION_HEADER).read_text(encoding="utf-8")
        + (root / PRODUCTION_SOURCE).read_text(encoding="utf-8")
    )
    opensubdiv_leak = (
        "opensubdiv/" in header.lower()
        or "opensubdiv/" in experiment.lower()
        or "opensubdiv/" in production_helper.lower()
    )
    one_ring_mutation = (
        "oneRingVertices =" in experiment
        or "oneRingVertices.push" in experiment
        or "oneRingVertices.clear" in experiment
    )
    if opensubdiv_leak:
        errors.append("backend-neutral adapter contains an OpenSubdiv type/include")
    if one_ring_mutation:
        errors.append("proof mutates production Face::oneRingVertices")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_or_default_surfaces_changed": production_changed,
        "backend_neutral_adapter_has_opensubdiv_leak": opensubdiv_leak,
        "production_one_ring_mutation": one_ring_mutation,
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
        print(f"anchors: {report['anchors']['located']}/{report['anchors']['expected']}")
        print(f"changed paths: {len(report['changed_paths'])}")
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
