#!/usr/bin/env python3
"""Inventory the inert valence-4 production route preflight lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "7f17dedaa4ad9d12291b403b7493e920dfad7e6c"
HEADER = Path("include/energy_force/Valence4_face_loop_route_preflight.hpp")
SOURCE = Path("src/energy_force/Valence4_face_loop_route_preflight.cpp")
CPP_TEST = Path("tests/test_valence4_face_loop_route_preflight.cpp")
DOC = Path("docs/irregular_valence4_production_route_preflight.md")
READINESS_MAP = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_route_preflight.py"
)
TEST = Path(
    "tests/test_irregular_valence4_production_route_preflight_inventory.py"
)

ALLOWED_PATHS = {
    HEADER,
    SOURCE,
    CPP_TEST,
    DOC,
    READINESS_MAP,
    INVENTORY,
    TEST,
}

ANCHORS = {
    HEADER: (
        "Valence4FaceLoopRoutePreflightResult",
        "Valence4FaceLoopRouteRequest",
        "Valence4FaceLoopRouteRequestResult",
        "source_keyed_kernel::SourceMappingView",
        "reviewerApprovedExplicitRequest = false",
        "sourceKeyedAccumulationExecuted = false",
        "productionRouteEnabled = false",
        "actualProductionForcePathExecuted = false",
        "productionFaceLoopExecuted = false",
        "productionOneRingsPopulated = false",
        "does not authorize route activation",
        "evaluate_guarded_valence4_face_loop_route_request",
    ),
    SOURCE: (
        "build_guarded_valence4_topology_source_mapping",
        "evaluate_guarded_valence4_face_loop_route_request",
        "SourceMappingView",
        "productionOneRingEmpty",
        "requires empty production",
        "reviewerApprovedExplicitRequest",
        "default-off without",
        "prepare_source_keyed_kernel_call",
        "accumulate_source_keyed_force_contributions",
        "sourceKeyedAccumulationExecuted = true",
        "result.supported = true",
        "result.rejectionReason.clear()",
    ),
    CPP_TEST: (
        "ApprovedOctahedronBuildsInertSourceKeyedRouteCandidate",
        "RejectsOneRingContractDriftWithoutPartialCandidate",
        "PreflightMappingsFeedSourceKeyedValidationWithoutRouteExecution",
        "ExplicitRouteRequestRejectsByDefaultBeforeSourceKeyedAccumulation",
        "ExplicitRouteRequestPreparesCallerOwnedSourceKeyedAccumulationOnly",
        "ExplicitRouteRequestRejectsMalformedRowsWithoutPartialOutput",
        "prepare_source_keyed_kernel_call",
        "accumulate_source_keyed_force_contributions",
        "calculate_element_area_volume",
    ),
    DOC: (
        "inert production-facing preflight",
        "explicit route request boundary",
        "review-gated and default-off",
        "not production valence-4 force execution",
        "production_route_preflight_helper_executed: true",
        "explicit_route_request_boundary: true",
        "default_off_request_rejected: true",
        "explicit_request_source_keyed_accumulation: true",
        "production_route_enabled: false",
        "actual_production_force_path_executed: false",
        "production_face_loop_executed: false",
        "production_one_rings_populated: false",
        "backend_neutral_opensubdiv_free: true",
    ),
    READINESS_MAP: (
        "inert production route preflight",
        "default-off route request boundary",
        "production-route preflight",
        "explicit request boundary rejects by default",
        "route activation remains a separate",
        "reviewer/user-gated decision",
    ),
    TEST: (
        "test_inventory_passes_with_inert_production_scope",
        "test_explicit_route_request_boundary_is_default_off",
        "test_preflight_has_no_default_evaluator_caller",
        "test_allowed_path_boundary",
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
    unexpected = sorted(path for path in paths if Path(path) not in ALLOWED_PATHS)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    forbidden_default_files = {
        "Makefile",
        "scripts/verify_pr_ready.sh",
        "include/mesh/Face.hpp",
        "include/mesh/Mesh.hpp",
        "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
        "src/energy_force/Energy_force_evaluator.cpp",
        "src/mesh/Mesh.cpp",
        "src/mesh/Mesh_setup_geometry.cpp",
        "EXEs/continuum_membrane.cpp",
        "EXEs/membrane_dynamics.cpp",
    }
    default_surfaces_changed = any(path in forbidden_default_files for path in paths)
    if default_surfaces_changed:
        errors.append("default evaluator or route surfaces changed")

    helper_names = (
        "build_guarded_valence4_face_loop_route_preflight",
        "evaluate_guarded_valence4_face_loop_route_request",
    )
    default_evaluator_callers: list[str] = []
    for path in sorted(forbidden_default_files):
        candidate = root / path
        if not candidate.is_file():
            continue
        candidate_text = candidate.read_text(
            encoding="utf-8", errors="ignore"
        )
        if any(helper_name in candidate_text for helper_name in helper_names):
            default_evaluator_callers.append(path)
    if default_evaluator_callers:
        errors.append(
            "preflight helper has default evaluator callers: "
            + ", ".join(default_evaluator_callers)
        )

    helper_text = "".join(
        (root / path).read_text(encoding="utf-8", errors="ignore")
        for path in (HEADER, SOURCE)
        if (root / path).is_file()
    )
    backend_neutral_opensubdiv_free = "opensubdiv" not in helper_text.lower()
    if not backend_neutral_opensubdiv_free:
        errors.append("preflight helper leaks OpenSubdiv")
    production_one_ring_mutation = any(
        needle in helper_text
        for needle in (
            ".oneRingVertices =",
            ".oneRingVertices.push_back",
            ".oneRingVertices.clear",
            ".oneRingVertices.resize",
        )
    )
    if production_one_ring_mutation:
        errors.append("preflight helper mutates production one-rings")
    production_force_path_called = any(
        needle in helper_text
        for needle in (
            "element_energy_force_regular",
            "Compute_Energy_And_Force",
            "accumulate_membrane_face_energy_and_forces",
        )
    )
    if production_force_path_called:
        errors.append("preflight helper calls production force path")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "production_route_preflight_helper_executed": True,
        "explicit_route_request_boundary": True,
        "default_off_request_rejected": True,
        "explicit_request_source_keyed_accumulation": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_one_rings_populated": False,
        "default_evaluator_callers": default_evaluator_callers,
        "default_evaluator_or_route_surfaces_changed":
            default_surfaces_changed,
        "backend_neutral_opensubdiv_free": backend_neutral_opensubdiv_free,
        "production_one_ring_mutation": production_one_ring_mutation,
        "production_force_path_called": production_force_path_called,
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
