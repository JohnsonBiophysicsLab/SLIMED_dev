#!/usr/bin/env python3
"""Inventory the proof-only valence-4 scatter/OpenMP shape lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "ee5b3b34005f4dea9ec50ac738421479cf3b2b9e"
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
PROBE = Path("scripts/probe_opensubdiv_feasibility.py")
RUNNER = Path(
    "scripts/run_irregular_valence4_opensubdiv_scatter_openmp_proof.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence4_opensubdiv_scatter_openmp_proof.sh"
)
DOC = Path("docs/irregular_valence4_scatter_openmp_proof.md")
TEST = Path("tests/test_irregular_valence4_scatter_openmp_proof_inventory.py")

GUARDED_REPRESENTATION_PATHS = {
    Path("docs/irregular_valence4_topology_source_representation.md"),
    Path("include/mesh/Valence4_topology_source_mapping.hpp"),
    Path("src/mesh/Valence4_topology_source_mapping.cpp"),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_representation.py"
    ),
    Path(
        "tests/test_irregular_valence4_topology_source_representation_inventory.py"
    ),
    Path("tests/test_surface_geometry_characterization.cpp"),
}

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
    PROBE,
    RUNNER,
    WRAPPER,
    DOC,
    TEST,
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("docs/irregular_valence4_force_formula_proof.md"),
    Path("docs/opensubdiv_force_transpose_evidence.md"),
    Path("scripts/inventory_opensubdiv_force_transpose_evidence.py"),
    Path("docs/irregular_valence4_production_openmp_shadow.md"),
    Path("experiments/irregular_valence4_production_openmp_shadow.cpp"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path("scripts/run_irregular_valence4_production_openmp_shadow.py"),
    Path("scripts/run_irregular_valence4_production_openmp_shadow.sh"),
    Path("tests/test_irregular_valence4_production_openmp_shadow_inventory.py"),
    Path("docs/irregular_valence4_topology_source_mapping_adapter.md"),
    Path("docs/opensubdiv_routing_readiness_map.md"),
    Path("experiments/irregular_valence4_topology_source_mapping_adapter.cpp"),
    Path("scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"),
    Path("scripts/run_irregular_valence4_topology_source_mapping_adapter.py"),
    Path("scripts/run_irregular_valence4_topology_source_mapping_adapter.sh"),
    Path("tests/test_irregular_valence4_topology_source_mapping_adapter_inventory.py"),
    Path("docs/irregular_valence4_production_call_parity.md"),
    Path("experiments/irregular_valence4_production_call_parity.cpp"),
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path("scripts/run_irregular_valence4_production_call_parity.py"),
    Path("scripts/run_irregular_valence4_production_call_parity.sh"),
    Path("tests/test_irregular_valence4_production_call_parity_inventory.py"),
    Path("docs/irregular_valence4_source_keyed_kernel_adapter.md"),
    Path("experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"),
    Path("experiments/irregular_valence4_source_keyed_kernel_adapter.hpp"),
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"),
    Path("tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py"),
} | GUARDED_REPRESENTATION_PATHS | PRODUCTION_KERNEL_CALL_PROOF_PATHS

ANCHORS = {
    PROBE: (
        "Valence4ScatterOpenMpSummary",
        "valence4_scatter_openmp_summary",
        "production_scatter_openmp_shape_proof",
        "valence4_scatter_layout_oracle_passed",
        "independent_layout_oracle_passed",
        "nonzero_face_contribution_count",
        "all_eight_faces_contribute",
        "sources_with_multi_face_collisions",
        "matches_nine_component_scatter_shape",
        "matches_simulated_serial_openmp_accumulation",
        "production_topology_one_rings_populated",
        "real OpenMP runtime or executable parity",
    ),
    RUNNER: (
        "run_irregular_valence4_opensubdiv_force_formula_proof.sh",
        "scatter_openmp_shape_proof_only",
        "actual_face_one_ring_scatter_proven",
        "actual_openmp_runtime_proven",
        "max_serial_simulated_openmp_difference",
    ),
    WRAPPER: (
        "run_irregular_valence4_opensubdiv_scatter_openmp_proof.py",
    ),
    DOC: (
        "proof_only: true",
        "scatter_openmp_shape_proof_only: true",
        "production_route_enabled: false",
        "scientifically_approved: false",
        "source_id * 9",
        "absolute `1e-12` tolerance",
        "does not invoke an OpenMP runtime",
    ),
    TEST: (
        "test_dependency_absent_wrapper_skips",
        "test_present_dependency_scatter_openmp_shape_proof",
        "sources_with_multi_face_collisions",
        "independent_layout_oracle_passed",
        "all_eight_faces_contribute",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", BASE],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if tracked.returncode != 0:
        return [], tracked.stderr.strip() or "git diff failed"
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if untracked.returncode != 0:
        return [], untracked.stderr.strip() or "git ls-files failed"
    return sorted(
        {
            line
            for output in (tracked.stdout, untracked.stdout)
            for line in output.splitlines()
            if line
        }
    ), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for path, needles in ANCHORS.items():
        source = (
            (root / path).read_text(encoding="utf-8")
            if (root / path).is_file()
            else ""
        )
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{path} missing {needle!r}")

    paths, diff_error = changed_paths(root)
    if diff_error:
        errors.append(diff_error)
    if (
        root
        / "scripts/inventory_irregular_valence4_scientific_force_algebra_proof.py"
    ).is_file():
        paths = [
            path
            for path in paths
            if Path(path) not in SCIENTIFIC_FORCE_ALGEBRA_SUCCESSOR_PATHS
        ]
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append(
            "scatter/OpenMP lane changed paths outside its allowlist: "
            + ", ".join(unexpected)
        )

    production_paths_changed = any(
        (
            path.startswith(("src/", "include/", "EXEs/", ".github/"))
            or path == "Makefile"
        )
        and Path(path)
        not in GUARDED_REPRESENTATION_PATHS
        | PRODUCTION_KERNEL_CALL_PROOF_PATHS
        for path in paths
    )
    fixture_csvs_changed = any(
        path.endswith("/vertices.csv") or path.endswith("/faces.csv")
        for path in paths
    )
    if production_paths_changed:
        errors.append("production/build/runtime paths must remain unchanged")
    if fixture_csvs_changed:
        errors.append("fixture CSVs must remain unchanged")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "scatter_openmp_shape_proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "scientifically_approved": False,
        "production_paths_changed": production_paths_changed,
        "fixture_csvs_changed": fixture_csvs_changed,
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
