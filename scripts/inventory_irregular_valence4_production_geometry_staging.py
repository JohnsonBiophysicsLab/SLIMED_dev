#!/usr/bin/env python3
"""Inventory the guarded valence-4 production geometry-staging lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "fd092b768a58cd22c4d1390413258239470d4528"
ROUTE_HEADER = Path(
    "include/energy_force/Valence4_face_loop_route_preflight.hpp"
)
ROUTE_SOURCE = Path(
    "src/energy_force/Valence4_face_loop_route_preflight.cpp"
)
CPP_TEST = Path("tests/test_valence4_face_loop_route_preflight.cpp")
EXPERIMENT = Path(
    "experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"
)
RUNNER = Path(
    "scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"
)
ADAPTER_TEST = Path(
    "tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py"
)
DOC = Path("docs/irregular_valence4_production_geometry_staging.md")
SHADOW_DOC = Path(
    "docs/irregular_valence4_production_call_shadow_parity.md"
)
READINESS_DOC = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_geometry_staging.py"
)
TEST = Path(
    "tests/test_irregular_valence4_production_geometry_staging_inventory.py"
)
GEOMETRY_ATOMIC_COMPOSITION_SUCCESSOR_PATHS = {
    Path("docs/irregular_valence4_geometry_atomic_composition.md"),
    Path(
        "scripts/inventory_irregular_valence4_atomic_face_loop_publication.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_production_geometry_staging.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_geometry_atomic_composition.py"
    ),
    Path(
        "tests/test_irregular_valence4_geometry_atomic_composition_inventory.py"
    ),
}

ALLOWED_PATHS = {
    ROUTE_HEADER,
    ROUTE_SOURCE,
    CPP_TEST,
    EXPERIMENT,
    RUNNER,
    ADAPTER_TEST,
    DOC,
    SHADOW_DOC,
    READINESS_DOC,
    Path(
        "scripts/inventory_irregular_valence4_production_call_shadow_parity.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"
    ),
    INVENTORY,
    TEST,
} | GEOMETRY_ATOMIC_COMPOSITION_SUCCESSOR_PATHS

ANCHORS = {
    ROUTE_HEADER: (
        "Valence4FaceGeometry",
        "Valence4FaceGeometryStagingRequest",
        "Valence4FaceGeometryStagingResult",
        "stage_guarded_valence4_face_geometry",
        "productionGeometryEvaluated",
    ),
    ROUTE_SOURCE: (
        "kLegacyVolumeQuadratureFactor = 0.16666666666",
        "valence-4 geometry staging remains default-off",
        "geometry staging requires exactly three ",
        "geometry staging quadrature weights must match ",
        "produced invalid output",
        "evaluated[0][0] * areaVector[0]",
    ),
    CPP_TEST: (
        "GeometryStagingRejectsByDefaultWithoutMutation",
        "GeometryStagingMatchesIndependentOrientedTriangleOracle",
        "GeometryStagingRejectsLateNonfiniteRowWithoutPartialOutput",
        "0.16666666666 * weightSum",
    ),
    EXPERIMENT: (
        "defaultOffGeometryStagingRejected",
        "geometryStagingExecuted",
        "geometryStagingMeshStateUnchanged",
        "maxGeometryDifference",
        "stage_guarded_valence4_face_geometry",
    ),
    RUNNER: (
        "default_off_geometry_staging_rejected",
        "geometry_staging_executed",
        "geometry_staging_mesh_state_unchanged",
        "max_geometry_staging_difference",
    ),
    ADAPTER_TEST: (
        "default_off_geometry_staging_rejected",
        "geometry_staging_executed",
        "geometry_staging_mesh_state_unchanged",
        "max_geometry_staging_difference",
    ),
    DOC: (
        "production_geometry_staging: true",
        "geometry_publication_executed: false",
        "0.16666666666",
        "does not write",
        "production caller be considered",
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

    forbidden_default_surface = any(
        path.startswith((".github/", "EXEs/", "data/fixtures/"))
        or path in {"Makefile", "scripts/verify_pr_ready.sh"}
        for path in paths
    )
    if forbidden_default_surface:
        errors.append("default build, CI, executable, or fixture surface changed")

    face_loop = (
        root / "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
    ).read_text(encoding="utf-8")
    production_caller = (
        "stage_guarded_valence4_face_geometry" in face_loop
    )
    if production_caller:
        errors.append("real production face loop calls geometry staging")

    production_text = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (ROUTE_HEADER, ROUTE_SOURCE)
    )
    opensubdiv_leak = "opensubdiv/" in production_text.lower()
    if opensubdiv_leak:
        errors.append("backend-neutral geometry staging leaks OpenSubdiv types")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "production_geometry_staging": True,
        "production_geometry_evaluated": True,
        "geometry_publication_executed": False,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_one_rings_populated": False,
        "production_face_loop_caller": production_caller,
        "default_dependency_changed": forbidden_default_surface,
        "backend_neutral_opensubdiv_free": not opensubdiv_leak,
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
