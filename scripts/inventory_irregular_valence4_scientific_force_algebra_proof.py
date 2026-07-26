#!/usr/bin/env python3
"""Inventory the valence-4 scientific force-algebra proof lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "eb178076ba5799e527a4ea3b3edfa4ef8454e8e3"
MESH_HEADER = Path("include/mesh/Mesh.hpp")
FORCE_SOURCE = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
CPP_TEST = Path("tests/test_variable_cardinality_force_algebra.cpp")
EXPERIMENT = Path(
    "experiments/irregular_valence4_source_keyed_kernel_adapter.cpp"
)
RUNNER = Path("scripts/run_irregular_valence4_source_keyed_kernel_adapter.py")
DOC = Path("docs/irregular_valence4_scientific_force_algebra_proof.md")
PREDECESSOR_DOC = Path(
    "docs/irregular_valence4_production_kernel_call_proof.md"
)
PREDECESSOR_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_kernel_call_proof.py"
)
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_scientific_force_algebra_proof.py"
)
TEST = Path(
    "tests/test_irregular_valence4_scientific_force_algebra_proof_inventory.py"
)
FACE_LOOP_OBSERVABLE_SUCCESSOR_PATHS = {
    Path("docs/irregular_valence4_face_loop_observable_shadow.md"),
    Path(
        "experiments/irregular_valence4_face_loop_observable_shadow.cpp"
    ),
    Path(
        "scripts/inventory_irregular_valence4_face_loop_observable_shadow.py"
    ),
    Path(
        "scripts/run_irregular_valence4_face_loop_observable_shadow.py"
    ),
    Path(
        "scripts/run_irregular_valence4_face_loop_observable_shadow.sh"
    ),
    Path(
        "tests/test_irregular_valence4_face_loop_observable_shadow_inventory.py"
    ),
    Path("docs/opensubdiv_routing_readiness_map.md"),
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
STALE_SCOPE_INVENTORIES = {
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"
    ),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_representation.py"
    ),
}

ALLOWED_PATHS = {
    MESH_HEADER,
    FORCE_SOURCE,
    CPP_TEST,
    EXPERIMENT,
    RUNNER,
    DOC,
    PREDECESSOR_DOC,
    PREDECESSOR_INVENTORY,
    INVENTORY,
    TEST,
} | STALE_SCOPE_INVENTORIES

ANCHORS = {
    MESH_HEADER: (
        "Providing an",
        "validated variable control-point cardinality",
        "shapeFunctionsOverride",
    ),
    FORCE_SOURCE: (
        "const int controlPointCount",
        "normal output must be 3 x 1",
        "force outputs must match the",
        "variable-cardinality force evaluation requires an explicit",
        "shape-function dimensions",
        "quadrature weights must match",
        "Matrix f_be(controlPointCount, 3)",
        "for (int j = 0; j < controlPointCount; j++)",
    ),
    CPP_TEST: (
        "ExplicitThreeSourceRowsMatchZeroPaddedTwelveSourceEvaluation",
        "RejectsImplicitOrDimensionMismatchedVariableCardinality",
        "triangle_shape_functions(3)",
        "triangle_shape_functions(12)",
    ),
    EXPERIMENT: (
        "invoke_scientific_force_algebra",
        "Mesh::element_energy_force_regular",
        r"\"existing_scientific_force_algebra_invoked\":",
        r"\"actual_production_force_path_executed\":false",
        "max_scientific_force_algebra_difference",
        "production face-loop integration",
    ),
    RUNNER: (
        "proof_coordinates",
        "signed_volume",
        "existing_scientific_force_algebra_invoked",
        "scientific_force_algebra_variable_cardinality",
        "max_scientific_force_algebra_difference",
    ),
    DOC: (
        "existing production scientific",
        "does not copy",
        "Variable cardinality is accepted only when an explicit override",
        "actual_production_force_path_executed: false",
        "real production face loop is unchanged",
        "serial/OpenMP energy, force, normal, area, and",
    ),
    TEST: (
        "test_inventory_passes_with_exact_production_scope",
        "test_formula_body_and_route_remain_unchanged",
        "test_absent_dependency_skips_cleanly",
        "test_present_dependency_invokes_existing_scientific_algebra",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_git(root: Path, *args: str) -> tuple[str, str | None]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return "", result.stderr.strip() or "git command failed"
    return result.stdout, None


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    diff, error = run_git(root, "diff", "--name-only", BASE)
    if error:
        return [], error
    untracked, error = run_git(
        root, "ls-files", "--others", "--exclude-standard"
    )
    if error:
        return [], error
    return sorted(
        {
            line
            for line in (*diff.splitlines(), *untracked.splitlines())
            if line
        }
    ), None


def formula_section(text: str) -> str:
    start = text.index("cross(a_1, a_2, xa)")
    end = text.index("meanCurv += halfGaussQuadratureCoeff", start)
    section = text[start:end]
    section = section.replace(
        "for (int j = 0; j < 12; j++)",
        "FOR_EACH_CONTROL_POINT",
    )
    section = section.replace(
        "for (int j = 0; j < controlPointCount; j++)",
        "FOR_EACH_CONTROL_POINT",
    )
    return section


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
    if (
        root
        / "scripts/inventory_irregular_valence4_face_loop_observable_shadow.py"
    ).is_file():
        paths = [
            path
            for path in paths
            if Path(path) not in FACE_LOOP_OBSERVABLE_SUCCESSOR_PATHS
        ]
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    forbidden_prefixes = ("EXEs/", ".github/", "data/fixtures/")
    forbidden_files = {
        "Makefile",
        "scripts/verify_pr_ready.sh",
        "include/mesh/Face.hpp",
        "src/mesh/Mesh.cpp",
        "src/mesh/Mesh_setup_geometry.cpp",
    }
    forbidden_changed = any(
        path.startswith(forbidden_prefixes) or path in forbidden_files
        for path in paths
    )
    if forbidden_changed:
        errors.append("default, route, fixture, or output surfaces changed")

    current_source = (root / FORCE_SOURCE).read_text(encoding="utf-8")
    base_source, base_error = run_git(root, "show", f"{BASE}:{FORCE_SOURCE}")
    formula_unchanged = False
    if base_error:
        errors.append(base_error)
    else:
        formula_unchanged = (
            formula_section(current_source) == formula_section(base_source)
        )
        if not formula_unchanged:
            errors.append("scientific force formula body changed")

    face_loop_start = current_source.index(
        "void accumulate_membrane_face_energy_and_forces"
    )
    face_loop_end = current_source.index(
        "void Mesh::Compute_Energy_And_Force", face_loop_start
    )
    face_loop = current_source[face_loop_start:face_loop_end]
    route_unchanged = (
        "nOneRingVertices == 6" not in face_loop
        and "source_keyed_kernel" not in face_loop
        and "scientific_force_algebra" not in face_loop
    )
    if not route_unchanged:
        errors.append("production face loop gained a valence-4 route")

    production_text = (
        current_source
        + (root / MESH_HEADER).read_text(encoding="utf-8")
    ).lower()
    opensubdiv_leak = "opensubdiv/" in production_text
    if opensubdiv_leak:
        errors.append("production formula surface gained OpenSubdiv headers")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "existing_scientific_force_algebra_invoked_under_proof": True,
        "actual_production_force_path_executed": False,
        "not_production_routing": True,
        "production_route_enabled": False,
        "scientific_formula_body_unchanged": formula_unchanged,
        "production_face_loop_unchanged": route_unchanged,
        "production_or_default_surfaces_changed": forbidden_changed,
        "production_formula_has_opensubdiv_leak": opensubdiv_leak,
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
