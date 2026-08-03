#!/usr/bin/env python3
"""Inventory the guarded valence-4 topology/source representation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "0d6f209d3a67ef07962796a84d075499e31d82d0"
PHASE1_MAKEFILE_BASE = "0b2b6dd425cb47e703c02dce0d32f89e23721b0d"
PHASE1_MAKEFILE_BLOCK = """USE_OPENSUBDIV_VALENCE5 ?= 0
ifeq ($(USE_OPENSUBDIV_VALENCE5),1)
\tifeq ($(OPENSUBDIV_ROOT),)
\t\t$(error "USE_OPENSUBDIV_VALENCE5=1 requires OPENSUBDIV_ROOT=/path/to/opensubdiv")
\tendif
\tDEFS += -DUSE_OPENSUBDIV_VALENCE5
\tINCS += -I$(OPENSUBDIV_ROOT)/include
\tLIBS += -L$(OPENSUBDIV_ROOT)/lib -L$(OPENSUBDIV_ROOT)/lib64 -Wl,-rpath,$(OPENSUBDIV_ROOT)/lib -Wl,-rpath,$(OPENSUBDIV_ROOT)/lib64 -losdCPU
endif

"""
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
HEADER = Path("include/mesh/Valence4_topology_source_mapping.hpp")
SOURCE = Path("src/mesh/Valence4_topology_source_mapping.cpp")
CPP_TEST = Path("tests/test_surface_geometry_characterization.cpp")
DOC = Path("docs/irregular_valence4_topology_source_representation.md")
PREDECESSOR_DOC = Path(
    "docs/irregular_valence4_topology_source_mapping_adapter.md"
)
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
TEST = Path(
    "tests/test_irregular_valence4_topology_source_representation_inventory.py"
)
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_topology_source_representation.py"
)

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
    HEADER,
    SOURCE,
    CPP_TEST,
    DOC,
    PREDECESSOR_DOC,
    READINESS,
    TEST,
    INVENTORY,
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_irregular_valence4_scatter_openmp_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path(
        "scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"
    ),
    Path("docs/irregular_valence4_production_call_parity.md"),
    Path("experiments/irregular_valence4_production_call_parity.cpp"),
    Path("scripts/inventory_irregular_valence4_production_call_parity.py"),
    Path("scripts/probe_opensubdiv_feasibility.py"),
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
} | PRODUCTION_KERNEL_CALL_PROOF_PATHS

ANCHORS = {
    HEADER: (
        "Valence4FaceTopologySourceMapping",
        "Valence4TopologySourceMappingResult",
        "build_guarded_valence4_topology_source_mapping",
        "does not populate Face::oneRingVertices",
        "production force route",
    ),
    SOURCE: (
        "kApprovedVertexCount = 6",
        "kApprovedFaceCount = 8",
        "kApprovedOrientedFaces",
        "vertex.index != sourceId",
        "vertex.adjacentVertices.size() != 4u",
        "face.isGhost || face.isBoundary",
        "!face.oneRingVertices.empty()",
        "mapping.originalSourceIds != expectedSourceIds",
        "result.supported = true",
    ),
    CPP_TEST: (
        "ApprovedOctahedronBuildsFaceIndexedOriginalSourceRepresentation",
        "RejectsIdentityValenceBoundaryAndOneRingContractDrift",
        "EXPECT_THROW(mesh.calculate_element_area_volume()",
        'find("canonical face orientation")',
        'find("11/12-control")',
    ),
    DOC: (
        "backend-neutral representation",
        "not consulted by the production energy/force path",
        "Any mismatch returns `supported=false`",
        "valence-4 route activation remains unapproved.",
    ),
    PREDECESSOR_DOC: (
        "guarded,",
        "backend-neutral topology/source representation",
    ),
    READINESS: (
        "guarded backend-neutral production representation",
        "remaining unused by the force path",
        "Future-only until production-call parity",
    ),
    TEST: (
        "test_inventory_passes_and_scope_is_guarded",
        "test_representation_is_not_called_by_production_paths",
        "test_fixture_files_and_default_build_policy_are_unchanged",
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


def phase1_makefile_change_is_exact_and_guarded(root: Path) -> bool:
    current = (root / "Makefile").read_text(encoding="utf-8")
    if current.count(PHASE1_MAKEFILE_BLOCK) != 1:
        return False
    baseline = subprocess.run(
        [
            "git", "-c", f"safe.directory={root}", "show",
            f"{PHASE1_MAKEFILE_BASE}:Makefile",
        ],
        cwd=root, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return (
        baseline.returncode == 0
        and current.replace(PHASE1_MAKEFILE_BLOCK, "") == baseline.stdout
    )


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
            "valence-4 topology/source representation changed paths outside "
            "its allowlist: " + ", ".join(unexpected)
        )

    forbidden_changed = any(
        (
            path.startswith(("src/energy_force/", "EXEs/", ".github/"))
        or path
        in {
            "scripts/verify_pr_ready.sh",
            "include/mesh/Mesh.hpp",
            "include/mesh/Face.hpp",
        }
        )
        and Path(path) not in PRODUCTION_KERNEL_CALL_PROOF_PATHS
        for path in paths
    )
    if "Makefile" in paths and not phase1_makefile_change_is_exact_and_guarded(root):
        forbidden_changed = True
    fixture_csvs_changed = any(
        path.endswith("/vertices.csv") or path.endswith("/faces.csv")
        for path in paths
    )
    if forbidden_changed:
        errors.append(
            "force/default-build/public mesh ownership surfaces must remain "
            "unchanged"
        )
    if fixture_csvs_changed:
        errors.append("approved fixture CSVs must remain unchanged")

    production_callers = (
        Path("src/mesh/Mesh.cpp"),
        Path("src/mesh/Mesh_setup_geometry.cpp"),
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
    )
    route_installed = any(
        "build_guarded_valence4_topology_source_mapping"
        in (root / path).read_text(encoding="utf-8")
        for path in production_callers
    )
    if route_installed:
        errors.append(
            "guarded valence-4 mapping must remain unused by production paths"
        )

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "guarded_production_representation": True,
        "backend_neutral": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_callers_changed": forbidden_changed,
        "route_installed_in_production": route_installed,
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
