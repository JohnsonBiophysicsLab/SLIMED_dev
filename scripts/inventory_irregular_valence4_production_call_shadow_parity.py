#!/usr/bin/env python3
"""Inventory the valence-4 production-call serial/OpenMP parity proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "500402cab96ee6e2ed25b24c376fd1db5442d494"
EXPERIMENT = Path(
    "experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"
)
RUNNER = Path(
    "scripts/run_irregular_valence4_production_call_shadow_parity.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence4_production_call_shadow_parity.sh"
)
DOC = Path(
    "docs/irregular_valence4_production_call_shadow_parity.md"
)
ATOMIC_DOC = Path(
    "docs/irregular_valence4_atomic_face_loop_publication.md"
)
READINESS_DOC = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_call_shadow_parity.py"
)
TEST = Path(
    "tests/test_irregular_valence4_production_call_shadow_parity_inventory.py"
)
PREDECESSOR_INVENTORIES = {
    Path("scripts/inventory_irregular_valence4_atomic_face_loop_publication.py"),
    Path("scripts/inventory_irregular_valence4_face_observable_publication.py"),
    Path("scripts/inventory_irregular_valence4_vertex_force_publication.py"),
    Path("scripts/inventory_irregular_valence4_production_scatter_buffer.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path("scripts/inventory_irregular_valence4_production_kernel_call_proof.py"),
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
}
PRODUCTION_GEOMETRY_STAGING_SUCCESSOR_PATHS = {
    Path("include/energy_force/Valence4_face_loop_route_preflight.hpp"),
    Path("src/energy_force/Valence4_face_loop_route_preflight.cpp"),
    Path("tests/test_valence4_face_loop_route_preflight.cpp"),
    Path("experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"),
    Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path(
        "tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py"
    ),
    Path("docs/irregular_valence4_production_geometry_staging.md"),
    Path(
        "scripts/inventory_irregular_valence4_production_geometry_staging.py"
    ),
    Path(
        "tests/test_irregular_valence4_production_geometry_staging_inventory.py"
    ),
}
GEOMETRY_ATOMIC_COMPOSITION_SUCCESSOR_PATHS = {
    Path("docs/irregular_valence4_geometry_atomic_composition.md"),
    Path(
        "scripts/inventory_irregular_valence4_geometry_atomic_composition.py"
    ),
    Path(
        "tests/test_irregular_valence4_geometry_atomic_composition_inventory.py"
    ),
}
PRODUCTION_CALLER_SHADOW_SUCCESSOR_PATHS = {
    Path("include/mesh/Mesh.hpp"),
    Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
    Path("docs/irregular_valence4_production_caller_shadow.md"),
    Path(
        "scripts/inventory_irregular_valence4_production_caller_shadow.py"
    ),
    Path(
        "tests/test_irregular_valence4_production_caller_shadow_inventory.py"
    ),
}
ROW_PROVIDER_SUCCESSOR_PATHS = {
    Path("include/mesh/OpenSubdiv_valence4_row_provider.hpp"),
    Path("src/mesh/OpenSubdiv_valence4_row_provider.cpp"),
    Path("experiments/irregular_valence4_opensubdiv_row_provider.cpp"),
    Path("scripts/run_irregular_valence4_opensubdiv_row_provider.py"),
    Path("scripts/run_irregular_valence4_opensubdiv_row_provider.sh"),
    Path("docs/irregular_valence4_opensubdiv_row_provider.md"),
    Path("scripts/inventory_irregular_valence4_opensubdiv_row_provider.py"),
    Path(
        "tests/test_irregular_valence4_opensubdiv_row_provider_inventory.py"
    ),
    Path("scripts/inventory_opensubdiv_regular_cpp_adapter_proof.py"),
}
OPENSUBDIV_PRODUCTION_CALLER_SUCCESSOR_PATHS = {
    Path("experiments/irregular_valence4_opensubdiv_production_caller.cpp"),
    Path("scripts/run_irregular_valence4_opensubdiv_production_caller.py"),
    Path("scripts/run_irregular_valence4_opensubdiv_production_caller.sh"),
    Path("docs/irregular_valence4_opensubdiv_production_caller.md"),
    Path(
        "scripts/inventory_irregular_valence4_opensubdiv_production_caller.py"
    ),
    Path(
        "tests/test_irregular_valence4_opensubdiv_production_caller_inventory.py"
    ),
}

ALLOWED_PATHS = {
    EXPERIMENT,
    RUNNER,
    WRAPPER,
    DOC,
    ATOMIC_DOC,
    READINESS_DOC,
    INVENTORY,
    TEST,
    *PREDECESSOR_INVENTORIES,
} | PRODUCTION_GEOMETRY_STAGING_SUCCESSOR_PATHS | \
    GEOMETRY_ATOMIC_COMPOSITION_SUCCESSOR_PATHS | \
    PRODUCTION_CALLER_SHADOW_SUCCESSOR_PATHS | \
    ROW_PROVIDER_SUCCESSOR_PATHS | \
    OPENSUBDIV_PRODUCTION_CALLER_SUCCESSOR_PATHS

ANCHORS = {
    EXPERIMENT: (
        "productionCallShadowExecuted",
        "production_call_shadow",
        "serial_openmp_comparison_ready",
        "vertex_forces",
        "face_observables",
        "legacy_volume",
        "productionShapedGeometryEvaluated",
        "shapeFunctions[sample] * controlPoints",
        "kLegacyVolumeQuadratureFactor",
    ),
    RUNNER: (
        "build_harness(serial_binary, env, openmp=False)",
        "build_harness(openmp_binary, env, openmp=True)",
        'run_env["OMP_DYNAMIC"] = "FALSE"',
        'run_env["OMP_NUM_THREADS"] = "4"',
        "validated_output",
        "max_serial_openmp_force_delta",
        "max_serial_openmp_face_observable_delta",
        "serial_openmp_area_delta",
        "serial_openmp_legacy_volume_delta",
        "observable_shadow.package_observables(proof)",
        "PRODUCTION_LEGACY_VOLUME_FACTOR = 0.16666666666",
        "serial_area_oracle_delta",
        "openmp_legacy_volume_oracle_delta",
        "run_irregular_valence4_production_openmp_shadow.sh",
        "actual_openmp_runtime_parity_passed",
    ),
    WRAPPER: (
        "run_irregular_valence4_production_call_shadow_parity.py",
    ),
    DOC: (
        "production_call_shadow: true",
        "serial_openmp_output_parity_passed: true",
        "actual_openmp_runtime_parity_passed: true",
        "all six vertices",
        "all eight faces",
        "legacy visible volume",
        "not copied from the shared force-proof package",
        "independent Python geometry oracle",
        "production legacy-volume factor `0.16666666666`",
        "route activation",
    ),
    TEST: (
        "test_inventory_passes_without_production_route",
        "test_dependency_absent_wrapper_skips_cleanly",
        "test_present_dependency_serial_openmp_parity_passes",
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
        (
            path.startswith(
                ("include/", "src/", "EXEs/", ".github/", "data/fixtures/")
            )
            or path in {"Makefile", "scripts/verify_pr_ready.sh"}
        )
        and Path(path) not in PRODUCTION_GEOMETRY_STAGING_SUCCESSOR_PATHS
        and Path(path) not in PRODUCTION_CALLER_SHADOW_SUCCESSOR_PATHS
        and Path(path) not in ROW_PROVIDER_SUCCESSOR_PATHS
        and Path(path) not in OPENSUBDIV_PRODUCTION_CALLER_SUCCESSOR_PATHS
        for path in paths
    )
    if forbidden:
        errors.append("production/default/fixture surface changed")

    face_loop = (
        root / "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
    ).read_text(encoding="utf-8")
    production_caller = any(
        anchor in face_loop
        for anchor in (
            "publish_valence4_face_loop_scientific_result_atomically",
            "evaluate_guarded_valence4_face_loop_publication",
        )
    )
    if production_caller:
        errors.append("real production face loop calls the guarded transaction")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "production_call_shadow": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "serial_openmp_output_parity_required": True,
        "actual_openmp_runtime_parity_required": True,
        "independent_geometry_oracle_required": True,
        "production_face_loop_caller": production_caller,
        "forbidden_surface_changed": forbidden,
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
