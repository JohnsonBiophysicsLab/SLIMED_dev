#!/usr/bin/env python3
"""Inventory the guarded valence-4 production-shaped scatter-buffer lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "6b168919aeacc9f52900850348c3b3dcce7d4875"
HEADER = Path("include/energy_force/Source_keyed_kernel_call.hpp")
SOURCE = Path("src/energy_force/Source_keyed_kernel_call.cpp")
CPP_TEST = Path("tests/test_source_keyed_kernel_call.cpp")
ADAPTER_HEADER = Path(
    "experiments/irregular_valence4_source_keyed_kernel_adapter.hpp"
)
ADAPTER = Path("experiments/irregular_valence4_source_keyed_kernel_adapter.cpp")
ADAPTER_RUNNER = Path(
    "scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"
)
ADAPTER_TEST = Path(
    "tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py"
)
OPENMP = Path("experiments/irregular_valence4_production_openmp_shadow.cpp")
OPENMP_RUNNER = Path(
    "scripts/run_irregular_valence4_production_openmp_shadow.py"
)
ADAPTER_DOC = Path("docs/irregular_valence4_source_keyed_kernel_adapter.md")
OPENMP_DOC = Path("docs/irregular_valence4_production_openmp_shadow.md")
READINESS_DOC = Path("docs/opensubdiv_routing_readiness_map.md")
DOC = Path("docs/irregular_valence4_production_scatter_buffer.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_scatter_buffer.py"
)
TEST = Path(
    "tests/test_irregular_valence4_production_scatter_buffer_inventory.py"
)
VERTEX_PUBLICATION_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_vertex_force_publication.py"
)
VERTEX_PUBLICATION_SUCCESSOR_PATHS = {
    HEADER,
    SOURCE,
    Path("include/energy_force/Valence4_face_loop_route_preflight.hpp"),
    Path("src/energy_force/Valence4_face_loop_route_preflight.cpp"),
    Path("tests/test_valence4_face_loop_route_preflight.cpp"),
    ADAPTER,
    ADAPTER_RUNNER,
    ADAPTER_TEST,
    OPENMP,
    OPENMP_RUNNER,
    Path("tests/test_irregular_valence4_production_openmp_shadow_inventory.py"),
    ADAPTER_DOC,
    OPENMP_DOC,
    READINESS_DOC,
    Path("docs/irregular_valence4_production_scatter_buffer.md"),
    Path("docs/irregular_valence4_vertex_force_publication.md"),
    VERTEX_PUBLICATION_INVENTORY,
    Path(
        "tests/test_irregular_valence4_vertex_force_publication_inventory.py"
    ),
    Path("docs/irregular_valence4_face_observable_publication.md"),
    Path(
        "scripts/inventory_irregular_valence4_face_observable_publication.py"
    ),
    Path(
        "tests/test_irregular_valence4_face_observable_publication_inventory.py"
    ),
    Path("scripts/inventory_irregular_valence4_production_scatter_buffer.py"),
}

ALLOWED_PATHS = {
    HEADER,
    SOURCE,
    CPP_TEST,
    ADAPTER_HEADER,
    ADAPTER,
    ADAPTER_RUNNER,
    ADAPTER_TEST,
    OPENMP,
    OPENMP_RUNNER,
    ADAPTER_DOC,
    OPENMP_DOC,
    READINESS_DOC,
    DOC,
    INVENTORY,
    TEST,
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
    Path("scripts/inventory_irregular_valence4_production_kernel_call_proof.py"),
    Path(
        "tests/test_irregular_valence4_production_openmp_shadow_inventory.py"
    ),
}

ANCHORS = {
    HEADER: (
        "kForceComponentsPerSource",
        "SourceForceComponentBuffer",
        "scatter_source_keyed_face_forces_to_component_buffer",
        "reduce_source_keyed_force_component_buffers",
        "ascending buffer order",
    ),
    SOURCE: (
        "source-keyed component scatter rejected",
        "std::vector<std::pair<std::size_t, double>> staged",
        "componentBuffer[update.first] = update.second",
        "source-keyed component reduction rejected",
        "for (const SourceForceComponentBuffer &buffer : componentBuffers)",
    ),
    CPP_TEST: (
        "ProductionShapedComponentBuffersMatchIndependentScatterOracle",
        "ComponentScatterRejectsMalformedInputWithoutPartialMutation",
        "EXPECT_EQ(destination, unchanged)",
    ),
    ADAPTER: (
        "productionShapedScatterExecuted",
        "maxProductionShapedScatterDifference",
        r"\"production_shaped_source_scatter_executed\":",
    ),
    ADAPTER_RUNNER: (
        "production_shaped_source_scatter_executed",
        "max_production_shaped_scatter_difference",
    ),
    OPENMP: (
        "scatter_source_keyed_face_forces_to_component_buffer",
        "reduce_source_keyed_force_component_buffers",
        "production_source_keyed_component_helper_executed",
        "independentlyReduced[destination]",
    ),
    OPENMP_RUNNER: (
        "production_source_keyed_component_helper_executed",
    ),
    DOC: (
        "source_id * 9 + force_kind * 3 + axis",
        "staged before publication",
        "production_route_enabled: false",
        "production_vertex_force_state_mutated:",
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
    if (root / VERTEX_PUBLICATION_INVENTORY).is_file():
        paths = [
            path
            for path in paths
            if Path(path) not in VERTEX_PUBLICATION_SUCCESSOR_PATHS
        ]
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    forbidden = any(
        path.startswith(("EXEs/", ".github/", "data/fixtures/"))
        or path
        in {
            "Makefile",
            "scripts/verify_pr_ready.sh",
            "include/mesh/Mesh.hpp",
            "include/mesh/Face.hpp",
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
        }
        for path in paths
    )
    if forbidden:
        errors.append("production route/default/fixture surfaces changed")

    helper_text = (
        (root / HEADER).read_text(encoding="utf-8")
        + (root / SOURCE).read_text(encoding="utf-8")
    ).lower()
    opensubdiv_leak = "opensubdiv/" in helper_text
    if opensubdiv_leak:
        errors.append("backend-neutral scatter helper leaks OpenSubdiv")

    production_face_loop = (
        root / "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
    ).read_text(encoding="utf-8")
    production_caller = (
        "scatter_source_keyed_face_forces_to_component_buffer"
        in production_face_loop
        or "reduce_source_keyed_force_component_buffers"
        in production_face_loop
    )
    if production_caller:
        errors.append("production face loop calls the guarded scatter helper")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_vertex_force_state_mutated": False,
        "backend_neutral_opensubdiv_free": not opensubdiv_leak,
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
