#!/usr/bin/env python3
"""Inventory the guarded valence-4 production caller completion shadow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "06f728787b3925e333166363790c78ef40e97ecc"
MESH_HEADER = Path("include/mesh/Mesh.hpp")
PREFLIGHT_HEADER = Path(
    "include/energy_force/Valence4_face_loop_route_preflight.hpp"
)
PRODUCTION_SOURCE = Path(
    "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
)
PREFLIGHT_SOURCE = Path(
    "src/energy_force/Valence4_face_loop_route_preflight.cpp"
)
CPP_TEST = Path("tests/test_valence4_face_loop_route_preflight.cpp")
EXPERIMENT = Path(
    "experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"
)
ADAPTER_RUNNER = Path(
    "scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"
)
PARITY_RUNNER = Path(
    "scripts/run_irregular_valence4_production_call_shadow_parity.py"
)
ADAPTER_TEST = Path(
    "tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py"
)
PARITY_TEST = Path(
    "tests/test_irregular_valence4_production_call_shadow_parity_inventory.py"
)
DOC = Path("docs/irregular_valence4_production_caller_shadow.md")
READINESS_DOC = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_caller_shadow.py"
)
TEST = Path(
    "tests/test_irregular_valence4_production_caller_shadow_inventory.py"
)
PREDECESSOR_INVENTORIES = {
    Path(
        "scripts/inventory_irregular_valence4_geometry_atomic_composition.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_production_call_shadow_parity.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"
    ),
}

ALLOWED_PATHS = {
    MESH_HEADER,
    PREFLIGHT_HEADER,
    PRODUCTION_SOURCE,
    PREFLIGHT_SOURCE,
    CPP_TEST,
    EXPERIMENT,
    ADAPTER_RUNNER,
    PARITY_RUNNER,
    ADAPTER_TEST,
    PARITY_TEST,
    DOC,
    READINESS_DOC,
    INVENTORY,
    TEST,
    *PREDECESSOR_INVENTORIES,
}

ANCHORS = {
    MESH_HEADER: (
        "complete_energy_force_after_membrane_accumulation",
        "regularization, total-force",
    ),
    PRODUCTION_SOURCE: (
        "accumulate_membrane_face_energy_and_forces(*this);",
        "complete_energy_force_after_membrane_accumulation();",
        "void Mesh::complete_energy_force_after_membrane_accumulation()",
        "energy_force_regularization();",
        "vertex.force.calculate_total_force();",
        "manage_force_for_boundary_ghost_vertex();",
    ),
    PREFLIGHT_HEADER: (
        "Valence4ProductionCallerShadowRequest",
        "Valence4ProductionCallerShadowResult",
        "evaluate_guarded_valence4_production_caller_shadow",
        "productionCompletionPhasesExecuted",
    ),
    PREFLIGHT_SOURCE: (
        "prepare_geometry_aware_composition",
        "validate_production_caller_shadow_destinations",
        "&vertex.force.forceRegularization",
        "vertex.coordRef.mat == nullptr",
        "!std::isfinite(vertex.coordRef.get(axis, 0))",
        "production caller shadow remains default-off",
        "mesh.clear_force_on_vertices_and_energy_on_faces();",
        "publish_valence4_geometry_and_scientific_result_atomically",
        "mesh.complete_energy_force_after_membrane_accumulation();",
    ),
    CPP_TEST: (
        "ProductionCallerShadowRejectsBeforeClearingCurrentState",
        "ProductionCallerShadowRejectsMalformedCompletionDestinationBeforeClear",
        "ProductionCallerShadowRejectsMalformedReferenceShapeBeforeClear",
        "ProductionCallerShadowRejectsNonfiniteReferenceBeforeClear",
        "ProductionCallerShadowRunsExactCompletionPhasesWithRouteDisabled",
        "vertex.coordRef = vertex.coord",
    ),
    EXPERIMENT: (
        "defaultOffProductionCallerShadowRejected",
        "productionCallerCompletionShadowExecuted",
        "productionCallerShadowClearedStaleState",
        "productionCallerShadowTotalsConsistent",
        "productionCallerShadowRouteRemainedDisabled",
        "productionCallerTotalForces",
        "productionCallerEnergyTotal",
    ),
    PARITY_RUNNER: (
        "production_caller_completion_shadow_executed",
        "max_serial_openmp_production_caller_total_force_delta",
        "serial_openmp_production_caller_total_energy_delta",
    ),
    DOC: (
        "post-membrane timing boundary",
        "Malformed input is rejected before clearing current state",
        "production_caller_completion_shadow_executed: true",
        "production_route_enabled: false",
        "production_face_loop_executed: false",
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
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    protected_change = any(
        path.startswith((".github/", "EXEs/", "data/fixtures/"))
        or path in {"Makefile", "scripts/verify_pr_ready.sh"}
        for path in paths
    )
    if protected_change:
        errors.append("default dependency/build/fixture surface changed")

    production_text = (root / PRODUCTION_SOURCE).read_text(encoding="utf-8")
    route_caller = any(
        anchor in production_text
        for anchor in (
            "evaluate_guarded_valence4_production_caller_shadow",
            "evaluate_guarded_valence4_geometry_aware_atomic_composition",
            "publish_valence4_geometry_and_scientific_result_atomically",
        )
    )
    if route_caller:
        errors.append("real production face loop calls guarded valence-4 route")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "production_caller_completion_shadow": True,
        "shared_production_completion_phase": True,
        "serial_openmp_total_force_energy_parity_required": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_one_rings_populated": False,
        "real_production_route_caller": route_caller,
        "default_dependency_changed": protected_change,
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
        print(
            "anchors: "
            f"{report['anchors']['located']}/{report['anchors']['expected']}"
        )
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
