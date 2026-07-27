#!/usr/bin/env python3
"""Inventory guarded valence-4 geometry-aware atomic composition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "f09ba4670913581b59eae10b6c1215c15ee28767"
HEADER = Path(
    "include/energy_force/Valence4_face_loop_route_preflight.hpp"
)
SOURCE = Path(
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
DOC = Path("docs/irregular_valence4_geometry_atomic_composition.md")
STAGING_DOC = Path(
    "docs/irregular_valence4_production_geometry_staging.md"
)
READINESS_DOC = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_geometry_atomic_composition.py"
)
TEST = Path(
    "tests/test_irregular_valence4_geometry_atomic_composition_inventory.py"
)

PREDECESSOR_INVENTORIES = {
    Path(
        "scripts/inventory_irregular_valence4_atomic_face_loop_publication.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_production_call_shadow_parity.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_production_geometry_staging.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"
    ),
}

ALLOWED_PATHS = {
    HEADER,
    SOURCE,
    CPP_TEST,
    EXPERIMENT,
    RUNNER,
    ADAPTER_TEST,
    DOC,
    STAGING_DOC,
    READINESS_DOC,
    INVENTORY,
    TEST,
    *PREDECESSOR_INVENTORIES,
}

ANCHORS = {
    HEADER: (
        "Valence4GeometryAwareAtomicCompositionRequest",
        "Valence4GeometryAwareAtomicCompositionResult",
        "stagedGeometryUsedForScientificEvaluation",
        "publish_valence4_geometry_and_scientific_result_atomically",
        "evaluate_guarded_valence4_geometry_aware_atomic_composition",
    ),
    SOURCE: (
        "validate_geometry_aware_publication",
        "geometry-aware atomic composition remains default-off",
        "stagedParam.area = geometryResult.totalArea",
        "stagedParam.vol = geometryResult.totalVolume",
        "Mesh stagedScientificEvaluator(stagedParam)",
        "evaluate_scientific_request_with_evaluator",
        "stagedGeometryUsedForScientificEvaluation",
        "geometryResult.totalArea",
        "geometryResult.totalVolume",
        "publish_valence4_geometry_and_scientific_result_atomically",
        "mesh.faces[faceIndex].elementArea",
        "mesh.faces[faceIndex].elementVolume",
        "mesh.param.area = geometryResult.totalArea",
        "mesh.param.vol = geometryResult.totalVolume",
    ),
    CPP_TEST: (
        "GeometryAwareAtomicCompositionRejectsByDefaultWithoutMutation",
        "GeometryAwareAtomicCompositionUsesStagedGlobalsAndCommitsAllFamilies",
        "GeometryAwareScientificForcesIgnoreStaleMeshGlobals",
        "GeometryAwareScientificEvaluationPreservesNonuniformQuadrature",
        "GeometryAwareCompositionRejectsMalformedLateRowWithoutMutation",
        "GeometryAwarePrimitiveRejectsLateGeometryDriftBeforeAnyWrite",
        "GeometryAwarePrimitiveRejectsLateDestinationDriftBeforeAnyWrite",
    ),
    EXPERIMENT: (
        "defaultOffGeometryAwareCompositionRejected",
        "geometryAwareAtomicCompositionExecuted",
        "stagedGeometryUsedForScientificEvaluation",
        "staleMeshGlobalsIgnored",
        "onlyReviewedGeometryScientificFamiliesPublishedAtomically",
        "maxGeometryAwareForceDifference",
        "maxGeometryAwareFaceObservableDifference",
        "maxGeometryAwareGeometryDifference",
    ),
    RUNNER: (
        "default_off_geometry_aware_composition_rejected",
        "geometry_aware_atomic_composition_executed",
        "staged_geometry_used_for_scientific_evaluation",
        "stale_mesh_globals_ignored",
        "only_reviewed_geometry_scientific_families_published_atomically",
    ),
    ADAPTER_TEST: (
        "default_off_geometry_aware_composition_rejected",
        "geometry_aware_atomic_composition_executed",
        "staged_geometry_used_for_scientific_evaluation",
        "stale_mesh_globals_ignored",
    ),
    DOC: (
        "copied `Param`",
        "nonuniform quadrature plan `{0.8, 0.1, 0.1}`",
        "Before the first write",
        "Param::area` and `Param::vol",
        "stale_mesh_globals_ignored: true",
        "production_route_enabled: false",
        "real-caller shadow/parity lane",
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

    forbidden = any(
        path.startswith((".github/", "EXEs/", "data/fixtures/"))
        or path
        in {
            "Makefile",
            "scripts/verify_pr_ready.sh",
            "include/mesh/Mesh.hpp",
            "include/mesh/Face.hpp",
            "include/mesh/Vertex.hpp",
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
        }
        for path in paths
    )
    if forbidden:
        errors.append("production caller/default/fixture surface changed")

    helper_text = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (HEADER, SOURCE)
    ).lower()
    opensubdiv_leak = "opensubdiv/" in helper_text
    if opensubdiv_leak:
        errors.append("backend-neutral composition leaks OpenSubdiv types")

    face_loop = (
        root / "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
    ).read_text(encoding="utf-8")
    production_caller = any(
        anchor in face_loop
        for anchor in (
            "evaluate_guarded_valence4_geometry_aware_atomic_composition",
            "publish_valence4_geometry_and_scientific_result_atomically",
        )
    )
    if production_caller:
        errors.append("real production face loop calls composition")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "geometry_aware_atomic_composition": True,
        "staged_geometry_used_for_scientific_evaluation": True,
        "atomic_geometry_scientific_publication": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_one_rings_populated": False,
        "default_evaluator_caller": False,
        "production_face_loop_caller": production_caller,
        "default_dependency_changed": forbidden,
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
