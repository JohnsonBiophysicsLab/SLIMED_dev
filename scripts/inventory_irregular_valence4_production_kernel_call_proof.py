#!/usr/bin/env python3
"""Inventory the guarded valence-4 production kernel-call proof lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "737cb25fcc93e7c8600018c9659b10d3e4b96270"
HEADER = Path("include/energy_force/Source_keyed_kernel_call.hpp")
SOURCE = Path("src/energy_force/Source_keyed_kernel_call.cpp")
CPP_TEST = Path("tests/test_source_keyed_kernel_call.cpp")
PROOF_HEADER = Path(
    "experiments/irregular_valence4_source_keyed_kernel_adapter.hpp"
)
EXPERIMENT = Path(
    "experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"
)
RUNNER = Path(
    "scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"
)
DOC = Path("docs/irregular_valence4_production_kernel_call_proof.md")
PREDECESSOR_DOC = Path(
    "docs/irregular_valence4_source_keyed_kernel_adapter.md"
)
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_kernel_call_proof.py"
)
TEST = Path(
    "tests/test_irregular_valence4_production_kernel_call_proof_inventory.py"
)
PREDECESSOR_INVENTORIES = {
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_representation.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"
    ),
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
}
SUCCESSOR_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_scientific_force_algebra_proof.py"
)
SUCCESSOR_PATHS = {
    Path("include/mesh/Mesh.hpp"),
    Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
    Path("tests/test_variable_cardinality_force_algebra.cpp"),
    Path("docs/irregular_valence4_scientific_force_algebra_proof.md"),
    SUCCESSOR_INVENTORY,
    Path(
        "tests/test_irregular_valence4_scientific_force_algebra_proof_inventory.py"
    ),
    Path("docs/irregular_valence4_face_loop_observable_shadow.md"),
    Path("experiments/irregular_valence4_face_loop_observable_shadow.cpp"),
    Path("scripts/inventory_irregular_valence4_face_loop_observable_shadow.py"),
    Path("scripts/run_irregular_valence4_face_loop_observable_shadow.py"),
    Path("scripts/run_irregular_valence4_face_loop_observable_shadow.sh"),
    Path("tests/test_irregular_valence4_face_loop_observable_shadow_inventory.py"),
}

ALLOWED_PATHS = {
    HEADER,
    SOURCE,
    CPP_TEST,
    PROOF_HEADER,
    EXPERIMENT,
    RUNNER,
    DOC,
    PREDECESSOR_DOC,
    INVENTORY,
    TEST,
} | PREDECESSOR_INVENTORIES

ANCHORS = {
    HEADER: (
        "SourceKeyedKernelCallInput",
        "PreparedSourceKeyedKernelCall",
        "prepare_source_keyed_kernel_call",
        "accumulate_source_keyed_force_contributions",
        "returns a new owned result only after every face",
        "It does not mutate",
        "No production Mesh or OpenMP",
    ),
    SOURCE: (
        "canonical_source_ids",
        "canonicalize_derivative_row",
        "canonicalize_forces",
        "long double sum",
        "requires stable face identity",
        "requires empty production",
        "rejected face orientation drift",
        "rejected mixed-row",
        "incomplete force source",
    ),
    CPP_TEST: (
        "CanonicalizesPermutationAndDuplicateDerivativeRowsWithoutInputMutation",
        "AccumulatesWithAnIndependentFixedIndexForceOracle",
        "RejectsMalformedRequestsBeforeReturningOutput",
        "kind * 3 + axis",
        "std::invalid_argument",
    ),
    PROOF_HEADER: (
        "energy_force/Source_keyed_kernel_call.hpp",
        "prepare_source_keyed_kernel_call",
    ),
    EXPERIMENT: (
        "prepare_source_keyed_kernel_call",
        "accumulate_source_keyed_force_contributions",
        r"\"production_kernel_call_helper_executed\":true",
        r"\"actual_production_force_path_executed\":false",
        "independent_scatter_oracle",
        "permuted_bindings",
        "split_duplicate_rows",
    ),
    RUNNER: (
        "production_kernel_call_helper_executed",
        "production_helper_output_owned_by_caller",
        "source_binding_permutation_invariant",
        "duplicate_row_entries_aggregated_by_source_id",
    ),
    DOC: (
        "actual call to a production helper",
        "not an actual",
        "fixed-index `6 x 9`",
        "throws before returning",
        "scientific force algebra",
        "production mesh face loop does not call this helper",
    ),
    TEST: (
        "test_inventory_passes_with_narrow_production_scope",
        "test_production_helper_has_no_production_caller",
        "test_absent_dependency_skips_cleanly",
        "test_present_dependency_executes_production_helper",
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
    successor_present = (root / SUCCESSOR_INVENTORY).is_file()
    lane_paths = [
        path
        for path in paths
        if not (successor_present and Path(path) in SUCCESSOR_PATHS)
    ]
    unexpected = sorted(
        path for path in lane_paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    forbidden_prefixes = ("EXEs/", ".github/", "data/fixtures/")
    forbidden_files = {
        "Makefile",
        "scripts/verify_pr_ready.sh",
        "include/mesh/Mesh.hpp",
        "include/mesh/Face.hpp",
        "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
        "src/mesh/Mesh.cpp",
        "src/mesh/Mesh_setup_geometry.cpp",
    }
    forbidden_changed = any(
        path.startswith(forbidden_prefixes) or path in forbidden_files
        for path in lane_paths
    )
    if forbidden_changed:
        errors.append("production route/default/fixture surfaces changed")

    helper_name = "prepare_source_keyed_kernel_call"
    production_callers = []
    for path in (
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        Path("src/energy_force/Energy_force_evaluator.cpp"),
        Path("src/mesh/Mesh.cpp"),
        Path("src/mesh/Mesh_setup_geometry.cpp"),
        Path("EXEs/continuum_membrane.cpp"),
        Path("EXEs/membrane_dynamics.cpp"),
    ):
        text = (
            (root / path).read_text(encoding="utf-8")
            if (root / path).is_file()
            else ""
        )
        if helper_name in text:
            production_callers.append(str(path))
    if production_callers:
        errors.append(
            "production helper has route callers: "
            + ", ".join(production_callers)
        )

    source = (root / SOURCE).read_text(encoding="utf-8")
    header = (root / HEADER).read_text(encoding="utf-8")
    opensubdiv_leak = "opensubdiv/" in (source + header).lower()
    if opensubdiv_leak:
        errors.append("backend-neutral production helper leaks OpenSubdiv")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "production_helper_executed_under_test": True,
        "actual_production_force_path_executed": False,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_callers": production_callers,
        "production_or_default_surfaces_changed": forbidden_changed,
        "backend_neutral_helper_has_opensubdiv_leak": opensubdiv_leak,
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
