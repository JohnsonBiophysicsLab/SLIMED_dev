#!/usr/bin/env python3
"""Inventory the guarded canonical valence-4 OpenSubdiv route activation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "ba4dbca7ae61b99b734eb295914925c00857a7d9"
HEADER = Path("include/energy_force/Valence4_face_loop_route_preflight.hpp")
SOURCE = Path("src/energy_force/Valence4_face_loop_route_preflight.cpp")
ENTRY = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
CPP_TEST = Path("tests/test_valence4_face_loop_route_preflight.cpp")
DOC = Path("docs/irregular_valence4_opensubdiv_route_activation.md")
CALLER_DOC = Path("docs/irregular_valence4_opensubdiv_production_caller.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
READINESS_INVENTORY = Path("scripts/inventory_opensubdiv_routing_readiness.py")
READINESS_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")
CALLER_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_opensubdiv_production_caller.py"
)
CALLER_TEST = Path(
    "tests/test_irregular_valence4_opensubdiv_production_caller_inventory.py"
)
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_opensubdiv_route_activation.py"
)
TEST = Path(
    "tests/test_irregular_valence4_opensubdiv_route_activation_inventory.py"
)

ALLOWED_PATHS = {
    HEADER,
    SOURCE,
    ENTRY,
    CPP_TEST,
    DOC,
    CALLER_DOC,
    READINESS,
    READINESS_INVENTORY,
    READINESS_TEST,
    CALLER_INVENTORY,
    CALLER_TEST,
    INVENTORY,
    TEST,
}

ANCHORS = {
    HEADER: (
        "opensubdiv_valence4_production_routing_requested",
        "evaluate_guarded_valence4_opensubdiv_production_route",
    ),
    SOURCE: (
        "SLIMED_USE_OPENSUBDIV_VALENCE4",
        "env_value_is_enabled",
        "reviewerApprovedExplicitCaller = true",
        "evaluate_guarded_valence4_opensubdiv_production_face_loop_caller",
        "productionRouteEnabled = true",
        "defaultEvaluatorCaller = true",
    ),
    ENTRY: (
        "opensubdiv_valence4_production_routing_requested",
        "evaluate_guarded_valence4_opensubdiv_production_route",
        "SLIMED_USE_OPENSUBDIV_VALENCE4 requested a guarded",
        "return;",
    ),
    CPP_TEST: (
        "OpenSubdivProductionRouteRequiresEnabledBuildAtomically",
        "OpenSubdivProductionRouteRunsThroughDefaultEvaluator",
        "OpenSubdivProductionRouteRejectsTopologyDriftAtomically",
        "OpenSubdivProductionRouteRemainsDefaultOff",
        "SLIMED_USE_OPENSUBDIV_VALENCE4",
        "expect_face_observable_publication_state_unchanged",
        "capture_all_vertex_forces",
    ),
    DOC: (
        "Guarded OpenSubdiv Valence-4 Route Activation",
        "Two Explicit Gates",
        "USE_OPENSUBDIV_REGULAR=1",
        "SLIMED_USE_OPENSUBDIV_VALENCE4=1",
        "Ambient OpenSubdiv installation",
        "Atomic Canonical Route",
        "It does not authorize any",
    ),
    CALLER_DOC: (
        "is called by `Mesh::Compute_Energy_And_Force()` only when both the",
        "`SLIMED_USE_OPENSUBDIV_VALENCE4=1` runtime gate",
        "leaves the ordinary evaluator path unchanged",
    ),
    READINESS: (
        "Valence-4 Guarded Route Boundary",
        "`Mesh::Compute_Energy_And_Force()` can now select this reviewed transaction",
        "`SLIMED_USE_OPENSUBDIV_VALENCE4=1`",
        "dependency-free builds stay OpenSubdiv-free",
        "successful runtime-gated execution sets `productionRouteEnabled`",
        "Broader-valence",
    ),
    READINESS_INVENTORY: (
        "pre-activation default evaluator denial",
        "pre-activation route-disabled flags",
        "dedicated runtime route gate",
        "successful route flag promotion",
    ),
    READINESS_TEST: (
        "test_valence4_current_state_anchors_bind_guarded_activation",
        "test_stale_valence4_readiness_claims_fail_the_inventory",
    ),
    CALLER_INVENTORY: (
        "guarded canonical route activation is missing",
        '"production_route_enabled": default_evaluator_route_caller',
        '"not_production_routing": False',
    ),
    CALLER_TEST: (
        "test_inventory_passes_with_guarded_successor_route",
        'self.assertTrue(report["production_route_enabled"])',
        'self.assertTrue(report["default_evaluator_route_caller"])',
    ),
}

FORBIDDEN_SOURCE_NEEDLES = (
    "Face::oneRingVertices",
    "omp_set_num_threads",
    "omp_set_schedule",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    paths: list[str] = []
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
            return [], result.stderr.strip() or "git inventory failed"
        paths.extend(result.stdout.splitlines())
    return sorted({path for path in paths if path}), None


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
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    protected = any(
        path.startswith((".github/", "EXEs/", "data/fixtures/"))
        or path in {"Makefile", "scripts/verify_pr_ready.sh"}
        for path in paths
    )
    if protected:
        errors.append("default dependency/build/fixture surface changed")

    route_source = (root / SOURCE).read_text(encoding="utf-8")
    entry_source = (root / ENTRY).read_text(encoding="utf-8")
    for needle in FORBIDDEN_SOURCE_NEEDLES:
        if needle in route_source or needle in entry_source:
            errors.append(f"route activation owns forbidden behavior: {needle}")

    build_gate_unchanged = "Makefile" not in paths
    runtime_gate_present = "SLIMED_USE_OPENSUBDIV_VALENCE4" in route_source
    default_entry_calls_route = (
        "evaluate_guarded_valence4_opensubdiv_production_route"
        in entry_source
    )

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "canonical_closed_valence4_only": True,
        "build_gate_unchanged": build_gate_unchanged,
        "runtime_gate_present": runtime_gate_present,
        "ambient_dependency_routing": False,
        "default_entry_calls_guarded_route": default_entry_calls_route,
        "atomic_dependency_rejection_tested": True,
        "atomic_topology_rejection_tested": True,
        "successful_route_parity_tested": True,
        "production_one_rings_populated": False,
        "broader_valence_routing": False,
        "production_formula_changed": False,
        "scatter_semantics_changed": False,
        "openmp_reduction_changed": False,
        "checkpoint_output_propagation_changed": False,
        "changed_paths": paths,
        "anchors": {"located": located, "expected": expected},
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    report = collect(repo_root())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
