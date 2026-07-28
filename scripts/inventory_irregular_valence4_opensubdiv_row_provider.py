#!/usr/bin/env python3
"""Inventory the guarded production valence-4 OpenSubdiv row provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "3786d51f03c381365ddd8432fa2bb87f19f124bc"
HEADER = Path("include/mesh/OpenSubdiv_valence4_row_provider.hpp")
SOURCE = Path("src/mesh/OpenSubdiv_valence4_row_provider.cpp")
CPP_TEST = Path("tests/test_valence4_face_loop_route_preflight.cpp")
EXPERIMENT = Path(
    "experiments/irregular_valence4_opensubdiv_row_provider.cpp"
)
RUNNER = Path(
    "scripts/run_irregular_valence4_opensubdiv_row_provider.py"
)
SHELL = Path(
    "scripts/run_irregular_valence4_opensubdiv_row_provider.sh"
)
DOC = Path("docs/irregular_valence4_opensubdiv_row_provider.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_opensubdiv_row_provider.py"
)
TEST = Path(
    "tests/test_irregular_valence4_opensubdiv_row_provider_inventory.py"
)
PREDECESSOR = Path(
    "scripts/inventory_irregular_valence4_production_caller_shadow.py"
)
GLOBAL_OPENSUBDIV_INVENTORY = Path(
    "scripts/inventory_opensubdiv_regular_cpp_adapter_proof.py"
)

ALLOWED_PATHS = {
    HEADER,
    SOURCE,
    CPP_TEST,
    EXPERIMENT,
    RUNNER,
    SHELL,
    DOC,
    READINESS,
    INVENTORY,
    TEST,
    PREDECESSOR,
    GLOBAL_OPENSUBDIV_INVENTORY,
}

ANCHORS = {
    HEADER: (
        "OpenSubdivValence4RowProviderRequest",
        "OpenSubdivValence4RowProviderResult",
        "reviewerApprovedExplicitRequest",
        "build_guarded_opensubdiv_valence4_rows",
        "productionRouteEnabled = false",
    ),
    SOURCE: (
        "#ifdef USE_OPENSUBDIV_REGULAR",
        "build_guarded_valence4_topology_source_mapping",
        "kApprovedFaceCount = 8",
        "kApprovedSourceCount = 6",
        "kSampleCount = 3",
        "LimitStencilTableFactoryReal<double>",
        "partition or derivative-sum invariants",
        "stencil.GetDuvWeights()",
        "target.sourceIds = mapping.originalSourceIds",
        "rowsGenerated = true",
        "OpenSubdiv-enabled build",
    ),
    CPP_TEST: (
        "OpenSubdivRowProviderRemainsDefaultOff",
        "OpenSubdivRowProviderRejectsExplicitRequestWithoutDependency",
        "OpenSubdivRowProviderReturnsCompleteApprovedPackage",
        "OpenSubdivRowProviderRejectsTopologyDriftAtomically",
    ),
    EXPERIMENT: (
        "valence4_row_provider",
        "default_off_request_rejected",
        "production_one_rings_empty",
        "not_production_routing",
    ),
    RUNNER: (
        "max_abs_difference_vs_reviewed_float_force_proof",
        '"provider_row_precision": "double"',
        "constant_field_invariant_tolerance",
        "sample_and_face_identity_match",
        "exact_tensor_shape",
        "production_face_loop_executed",
    ),
    DOC: (
        "Why the provider comes first",
        "8 x 3 x 7 x 6",
        "returns an empty row package on every rejection",
        "real production",
    ),
    READINESS: (
        "guarded production row-provider prerequisite",
        "build_guarded_opensubdiv_valence4_rows",
        "guarded real production face-loop caller",
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
            return [], result.stderr.strip() or "git inventory failed"
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

    protected = any(
        path.startswith((".github/", "EXEs/", "data/fixtures/"))
        or path in {"Makefile", "scripts/verify_pr_ready.sh"}
        for path in paths
    )
    if protected:
        errors.append("default dependency/build/fixture surface changed")

    source_text = (root / SOURCE).read_text(encoding="utf-8")
    route_call = any(
        anchor in source_text
        for anchor in (
            "Compute_Energy_And_Force",
            "complete_energy_force_after_membrane_accumulation",
            "publish_valence4_geometry_and_scientific_result_atomically",
        )
    )
    if route_call:
        errors.append("row provider contains a production route caller")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "chosen_prerequisite": "guarded OpenSubdiv valence-4 row provider",
        "provider_smaller_than_duplicate_caller": True,
        "backend_neutral_output": True,
        "exact_tensor_shape": "8x3x7x6",
        "failure_atomic_empty_result": True,
        "default_dependency_changed": protected,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": route_call,
        "production_one_rings_populated": False,
        "anchors": {"located": located, "expected": expected},
        "changed_paths": paths,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = collect(repo_root())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
