#!/usr/bin/env python3
"""Inventory the proof-only valence-4 production/OpenMP shadow lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "53560800baa7b8a946e833ef63c3578bb3d90a49"
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
}
PROBE = Path("scripts/probe_opensubdiv_feasibility.py")
EXPERIMENT = Path(
    "experiments/irregular_valence4_production_openmp_shadow.cpp"
)
RUNNER = Path("scripts/run_irregular_valence4_production_openmp_shadow.py")
WRAPPER = Path("scripts/run_irregular_valence4_production_openmp_shadow.sh")
DOC = Path("docs/irregular_valence4_production_openmp_shadow.md")
TEST = Path(
    "tests/test_irregular_valence4_production_openmp_shadow_inventory.py"
)

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
    EXPERIMENT,
    RUNNER,
    WRAPPER,
    DOC,
    TEST,
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("docs/irregular_valence4_scatter_openmp_proof.md"),
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
        "print_valence4_face_force_contributions",
        "face_force_contributions",
        "evaluation.faceFBend[face]",
        "evaluation.faceFArea[face]",
        "evaluation.faceFVolume[face]",
    ),
    EXPERIMENT: (
        "mesh.setup_from_vertices_faces",
        "mesh.faces[face].adjacentVertices == facesData[face]",
        "mesh.faces[face].oneRingVertices.empty()",
        "actual_production_force_path_executed",
        "#pragma omp parallel num_threads(requestedThreads)",
        "#pragma omp for schedule(static)",
        "omp_set_dynamic(0)",
        "requested{{1, 2, 3, 4, 8}}",
        "kRepeats = 5",
        "kTolerance = 1.0e-12",
        "long double source-kind-axis before flattening",
        "independent_exact_index_layout_oracle_passed",
        "expectedDestination",
        "run_threads(sentinels, expected, 3)",
        "uncovered_component_slots",
        "single_contribution_component_slots",
        "unexpected_collision_count_component_slots",
        "collisions[index] != kFaceCount",
        "actual_openmp_runtime_parity_passed",
    ),
    RUNNER: (
        "run_irregular_valence4_opensubdiv_force_formula_proof.sh",
        "face_force_contributions",
        'run_env["OMP_DYNAMIC"] = "FALSE"',
        '"production_call_shadow": True',
        '"actual_production_force_path_executed": False',
        'shadow.get("collision_counts") == [8] * 54',
        'shadow.get("unexpected_collision_count_component_slots") == []',
        '"actual_openmp_runtime_parity_passed": True',
    ),
    WRAPPER: (
        "run_irregular_valence4_production_openmp_shadow.py",
    ),
    DOC: (
        "proof_only: true",
        "production_call_shadow: true",
        "actual_production_force_path_executed: false",
        "production `Mesh` topology setup",
        "Requested thread counts `1`, `2`, `3`, `4`, and `8`",
        "absolute `1e-12`",
        "does not call the production valence-4 force path",
    ),
    TEST: (
        "test_inventory_passes_and_scope_is_proof_only",
        "test_production_topology_and_real_openmp_are_binding",
        "test_dependency_absent_wrapper_skips",
        "test_present_dependency_production_openmp_shadow",
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
            "production/OpenMP shadow changed paths outside its allowlist: "
            + ", ".join(unexpected)
        )

    production_paths_changed = any(
        (
            path.startswith(("src/", "include/", "EXEs/", ".github/"))
            or path in {"Makefile", "scripts/verify_pr_ready.sh"}
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
        errors.append("production/default build surfaces must remain unchanged")
    if fixture_csvs_changed:
        errors.append("approved fixture CSVs must remain unchanged")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "production_call_shadow": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
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
