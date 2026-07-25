#!/usr/bin/env python3
"""Inventory the proof-only valence-4 topology/source-mapping adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "913378be89ac2f77f99bcb24141ead2b75b21dbc"
EXPERIMENT = Path(
    "experiments/irregular_valence4_topology_source_mapping_adapter.cpp"
)
RUNNER = Path(
    "scripts/run_irregular_valence4_topology_source_mapping_adapter.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence4_topology_source_mapping_adapter.sh"
)
DOC = Path("docs/irregular_valence4_topology_source_mapping_adapter.md")
PREDECESSOR_DOC = Path("docs/irregular_valence4_production_openmp_shadow.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
TEST = Path(
    "tests/test_irregular_valence4_topology_source_mapping_adapter_inventory.py"
)
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"
)

ALLOWED_PATHS = {
    EXPERIMENT,
    RUNNER,
    WRAPPER,
    DOC,
    PREDECESSOR_DOC,
    READINESS,
    TEST,
    INVENTORY,
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
}

ANCHORS = {
    EXPERIMENT: (
        "mesh.setup_from_vertices_faces",
        "derive_source_ids",
        "mesh.vertices[vertex].adjacentVertices",
        "mapping.sourceIds != result.derivedSourceIds[faceIndex]",
        "face.oneRingVertices.empty()",
        "independent_sentinel_scatter_oracle_passed",
        "duplicate_source_rejected",
        "missing_source_rejected",
        "out_of_range_source_rejected",
        "oriented_face_mismatch_rejected",
        "actual_production_force_path_executed",
        "approved octahedron only; no generic valence-4 route",
    ),
    RUNNER: (
        "run_irregular_valence4_opensubdiv_mapping_proof.sh",
        "expected_original_fixture_vertex_ids",
        "source_coverage_union",
        '"per_face_source_ids") == [expected_sources] * 8',
        '"production_route_enabled": False',
        '"actual_production_force_path_executed": False',
    ),
    WRAPPER: (
        "run_irregular_valence4_topology_source_mapping_adapter.py",
    ),
    DOC: (
        "proof_only: true",
        "topology_source_mapping_adapter_design: true",
        "not_production_routing: true",
        "production_route_enabled: false",
        "scientifically_approved: false",
        "Face::oneRingVertices",
        "duplicate, missing, out-of-range, and orientation mutations",
        "approved octahedron only",
    ),
    PREDECESSOR_DOC: (
        "proof-only topology/source-mapping adapter design now",
    ),
    READINESS: (
        "topology/source-mapping adapter design",
    ),
    TEST: (
        "test_inventory_passes_and_scope_is_proof_only",
        "test_mapping_and_mutation_gates_are_binding",
        "test_dependency_absent_wrapper_skips",
        "test_present_dependency_topology_source_mapping_adapter",
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
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append(
            "topology/source-mapping adapter changed paths outside its "
            "allowlist: " + ", ".join(unexpected)
        )

    production_paths_changed = any(
        path.startswith(("src/", "include/", "EXEs/", ".github/"))
        or path in {"Makefile", "scripts/verify_pr_ready.sh"}
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
        "topology_source_mapping_adapter_design": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "scientifically_approved": False,
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
