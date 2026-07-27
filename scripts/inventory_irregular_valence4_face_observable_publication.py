#!/usr/bin/env python3
"""Inventory the guarded valence-4 face-observable publication lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "d6919d00ee97dcd6a274cee3cc0bb4b9c2dbc71f"
ROUTE_HEADER = Path(
    "include/energy_force/Valence4_face_loop_route_preflight.hpp"
)
ROUTE_SOURCE = Path(
    "src/energy_force/Valence4_face_loop_route_preflight.cpp"
)
CPP_TEST = Path("tests/test_valence4_face_loop_route_preflight.cpp")
ADAPTER = Path("experiments/irregular_valence4_source_keyed_kernel_adapter.cpp")
ADAPTER_RUNNER = Path(
    "scripts/run_irregular_valence4_source_keyed_kernel_adapter.py"
)
ADAPTER_TEST = Path(
    "tests/test_irregular_valence4_source_keyed_kernel_adapter_inventory.py"
)
DOC = Path("docs/irregular_valence4_face_observable_publication.md")
VERTEX_DOC = Path("docs/irregular_valence4_vertex_force_publication.md")
ADAPTER_DOC = Path("docs/irregular_valence4_source_keyed_kernel_adapter.md")
READINESS_DOC = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_face_observable_publication.py"
)
TEST = Path(
    "tests/test_irregular_valence4_face_observable_publication_inventory.py"
)

PREDECESSOR_INVENTORIES = {
    Path("scripts/inventory_irregular_valence4_vertex_force_publication.py"),
    Path("scripts/inventory_irregular_valence4_production_scatter_buffer.py"),
    Path("scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"),
    Path("scripts/inventory_irregular_valence4_production_kernel_call_proof.py"),
    Path("scripts/inventory_irregular_valence4_production_openmp_shadow.py"),
}

ALLOWED_PATHS = {
    ROUTE_HEADER,
    ROUTE_SOURCE,
    CPP_TEST,
    ADAPTER,
    ADAPTER_RUNNER,
    ADAPTER_TEST,
    DOC,
    VERTEX_DOC,
    ADAPTER_DOC,
    READINESS_DOC,
    INVENTORY,
    TEST,
    *PREDECESSOR_INVENTORIES,
}

ANCHORS = {
    ROUTE_HEADER: (
        "Valence4FaceObservablePublicationRequest",
        "Valence4FaceObservablePublicationResult",
        "faceObservablePublicationExecuted",
        "publish_valence4_face_scientific_observables_to_faces",
        "evaluate_guarded_valence4_face_observable_publication",
        "overwrites only meanCurvature, energy.energyCurvature",
    ),
    ROUTE_SOURCE: (
        "valence-4 face-observable publication remains default-off",
        "cardinality drift",
        "rejected duplicate",
        "nonfinite normal data",
        "requires empty",
        "Validation and replacement-normal allocation finish before any write",
        "face.meanCurvature =",
        "face.energy.energyCurvature =",
        "std::swap(face.normVector.mat",
    ),
    CPP_TEST: (
        "FaceObservablePublicationRejectsByDefaultWithoutMutation",
        "FaceObservablePublicationOverwritesOnlyCurrentFaceObservables",
        "FaceObservablePublicationRejectsMalformedLateRowWithoutMutation",
        "FaceObservablePublicationPrimitiveRejectsLateDriftAtomically",
        "FaceObservablePublicationPrimitiveUsesFaceIdentityNotInputOrder",
        "expect_only_face_observables_published",
    ),
    ADAPTER: (
        "defaultOffFaceObservablePublicationRejected",
        "faceObservablePublicationExecuted",
        "onlyFaceObservablesPublished",
        "maxPublishedFaceObservableDifference",
        "mesh_matches_face_observable_publication",
    ),
    ADAPTER_RUNNER: (
        "default_off_face_observable_publication_rejected",
        "face_observable_publication_executed",
        "only_face_observables_published",
        "max_published_face_observable_difference",
    ),
    ADAPTER_TEST: (
        "default_off_face_observable_publication_rejected",
        "face_observable_publication_executed",
        "only_face_observables_published",
        "max_published_face_observable_difference",
    ),
    DOC: (
        "Face::meanCurvature",
        "Face::energy.energyCurvature",
        "Face::normVector",
        "Face::elementArea",
        "production_face_loop_executed: false",
        "face_observable_publication_executed: true",
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
        (root / ROUTE_HEADER).read_text(encoding="utf-8")
        + (root / ROUTE_SOURCE).read_text(encoding="utf-8")
    ).lower()
    opensubdiv_leak = "opensubdiv/" in helper_text
    if opensubdiv_leak:
        errors.append("face-observable helpers leak OpenSubdiv types")

    face_loop = (
        root / "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
    ).read_text(encoding="utf-8")
    production_caller = (
        "publish_valence4_face_scientific_observables_to_faces"
        in face_loop
        or "evaluate_guarded_valence4_face_observable_publication"
        in face_loop
    )
    if production_caller:
        errors.append("real production face loop calls publication boundary")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "face_observable_publication_executed": True,
        "production_one_rings_populated": False,
        "default_dependency_changed": False,
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
