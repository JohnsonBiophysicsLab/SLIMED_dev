#!/usr/bin/env python3
"""Inventory the proof-only valence-4 production-call boundary lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "a9d63e10903aa6a7308acef14bdfe037b43c6ec5"
EXPERIMENT = Path("experiments/irregular_valence4_production_call_parity.cpp")
RUNNER = Path("scripts/run_irregular_valence4_production_call_parity.py")
SHELL = Path("scripts/run_irregular_valence4_production_call_parity.sh")
PROBE = Path("scripts/probe_opensubdiv_feasibility.py")
DOC = Path("docs/irregular_valence4_production_call_parity.md")
REPRESENTATION_DOC = Path("docs/irregular_valence4_topology_source_representation.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path("scripts/inventory_irregular_valence4_production_call_parity.py")
TEST = Path("tests/test_irregular_valence4_production_call_parity_inventory.py")

PRODUCTION_KERNEL_CALL_PROOF_PATHS = {
    Path("docs/irregular_valence4_production_kernel_call_proof.md"),
    Path("include/energy_force/Source_keyed_kernel_call.hpp"),
    Path("src/energy_force/Source_keyed_kernel_call.cpp"),
    Path(
        "scripts/inventory_irregular_valence4_production_kernel_call_proof.py"
    ),
    Path(
        "tests/test_irregular_valence4_production_kernel_call_proof_inventory.py"
    ),
    Path("tests/test_source_keyed_kernel_call.cpp"),
}

ALLOWED_PATHS = {
    EXPERIMENT,
    RUNNER,
    SHELL,
    PROBE,
    DOC,
    REPRESENTATION_DOC,
    READINESS,
    INVENTORY,
    TEST,
    Path("scripts/inventory_irregular_valence4_topology_source_representation.py"),
    Path("scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"),
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path("docs/irregular_valence4_source_keyed_kernel_adapter.md"),
    Path("experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"),
    Path("experiments/irregular_valence4_source_keyed_kernel_adapter.hpp"),
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"),
    Path("tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py"),
} | PRODUCTION_KERNEL_CALL_PROOF_PATHS

ANCHORS = {
    EXPERIMENT: (
        "build_guarded_valence4_topology_source_mapping",
        "independent_topology_orientation_oracle",
        "independent_fixed_index_sentinel_oracle",
        "read_fresh_row_binding",
        "production_rejects_before_mutation",
        r"\"fresh_row_tensor_shape\":\"8x3x7x6\"",
        r"\"actual_production_force_path_executed\":false",
        r"\"variable-cardinality source-keyed production-kernel ",
        "oneRingVertices = {0}",
        "oneRingVertices.clear()",
    ),
    RUNNER: (
        "run_irregular_valence4_opensubdiv_force_formula_proof.sh",
        "generated_in_this_process",
        "fresh row tensor dimensions are not 8x3x7x6",
        "production_entry_rejected_loudly",
        "actual_production_force_path_executed",
    ),
    SHELL: ("set -Eeuo pipefail",),
    PROBE: (
        r"\"fresh_opensubdiv_row_binding\":{",
        r"\"tensor_shape\":\"8 faces x 3 samples x 7 rows x 6 sources\"",
    ),
    DOC: (
        "binding negative result",
        "`actual_production_force_path_executed:false`",
        "variable-cardinality",
        "not production valence-4 force execution",
    ),
    REPRESENTATION_DOC: ("production-call boundary proof",),
    READINESS: (
        "Valence-4 Production-Call Boundary",
        "variable-cardinality source-keyed kernel adapter",
    ),
    TEST: (
        "test_inventory_passes_with_proof_only_scope",
        "test_absent_dependency_skips_cleanly",
        "test_present_dependency_boundary_passes",
        "test_default_and_production_surfaces_are_unchanged",
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
    unexpected = sorted(path for path in paths if Path(path) not in ALLOWED_PATHS)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    forbidden = {
        "Makefile",
        "scripts/verify_pr_ready.sh",
        "include/mesh/Mesh.hpp",
        "include/mesh/Face.hpp",
        "src/mesh/Mesh.cpp",
        "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
    }
    production_changed = any(
        path in forbidden
        or path.startswith(("EXEs/", ".github/"))
        or path.endswith("/vertices.csv")
        or path.endswith("/faces.csv")
        for path in paths
    )
    if production_changed:
        errors.append("production/default/fixture surfaces changed")

    experiment = (root / EXPERIMENT).read_text(encoding="utf-8")
    fake_regular_call = "element_energy_force_regular(" in experiment
    one_ring_mutation_gate = (
        "oneRingVertices = {0}" in experiment
        and "oneRingVertices.clear()" in experiment
        and "orientation_and_one_ring_mutations_rejected" in experiment
    )
    if fake_regular_call:
        errors.append("proof must not call the 12-control regular kernel")
    if not one_ring_mutation_gate:
        errors.append("proof must reject and clear its temporary one-ring mutation")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_or_default_surfaces_changed": production_changed,
        "fake_regular_kernel_call": fake_regular_call,
        "temporary_one_ring_mutation_gate": one_ring_mutation_gate,
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
