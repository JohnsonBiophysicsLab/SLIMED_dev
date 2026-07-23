#!/usr/bin/env python3
"""Inventory the approved proof-only valence-4 OpenSubdiv mapping lane."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIXTURE_DIR = Path("data/fixtures/candidates/closed_valence4_octahedron")
METADATA_PATH = FIXTURE_DIR / "candidate_metadata.json"
PROBE_PATH = Path("scripts/probe_opensubdiv_feasibility.py")
WRAPPER_PATH = Path("scripts/run_irregular_valence4_opensubdiv_mapping_proof.sh")
DOC_PATH = Path("docs/irregular_valence4_opensubdiv_mapping_proof.md")

ANCHORS = {
    PROBE_PATH: (
        "--valence4-mapping-sample-transpose-report",
        "load_serialized_valence4_fixture",
        "approved_for_mapping_sample_transpose_proof",
        "scientifically_approved",
        "patch_basis_limit_stencil_match_passed",
        "backprojection_has_exactly_18_components_with_all_six_support",
        "return proofMapPassed;",
    ),
    WRAPPER_PATH: (
        "run_opensubdiv_probe.sh",
        "--valence4-mapping-sample-transpose-report",
    ),
    DOC_PATH: (
        "approved_for_mapping_sample_transpose_proof: true",
        "scientifically_approved: false",
        "production_route_enabled: false",
        "production fBend/fArea/fVolume",
        "scatter/OpenMP parity",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_rows(path: Path, cast):
    with path.open(newline="", encoding="utf-8") as handle:
        return tuple(tuple(cast(value) for value in row) for row in csv.reader(handle))


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    vertices = read_rows(root / FIXTURE_DIR / "vertices.csv", float)
    faces = read_rows(root / FIXTURE_DIR / "faces.csv", int)
    metadata = json.loads((root / METADATA_PATH).read_text(encoding="utf-8"))

    if len(vertices) != 6 or any(len(vertex) != 3 for vertex in vertices):
        errors.append("proof fixture must retain six three-component vertices")
    if len(faces) != 8 or any(len(face) != 3 for face in faces):
        errors.append("proof fixture must retain eight oriented triangular faces")
    if metadata.get("scientifically_approved") is not False:
        errors.append("generic scientifically_approved must remain false")
    if metadata.get("approved_for_mapping_sample_transpose_proof") is not True:
        errors.append("narrow mapping/sample/transpose approval must be recorded")
    if not metadata.get("approved_scope"):
        errors.append("the narrow approved scope must be explicit")
    if metadata.get("proof_only") is not True:
        errors.append("metadata must label the lane proof_only")
    if metadata.get("not_production_routing") is not True:
        errors.append("metadata must label the lane not_production_routing")
    if metadata.get("production_route_enabled") is not False:
        errors.append("production routing must remain disabled")

    located = 0
    expected = 0
    for relative_path, needles in ANCHORS.items():
        source = (
            (root / relative_path).read_text(encoding="utf-8")
            if (root / relative_path).is_file()
            else ""
        )
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative_path} missing {needle!r}")

    return {
        "status": "passed" if not errors else "failed",
        "fixture_path": FIXTURE_DIR.as_posix(),
        "fixture_vertex_count": len(vertices),
        "fixture_face_count": len(faces),
        "approved_for_mapping_sample_transpose_proof": metadata.get(
            "approved_for_mapping_sample_transpose_proof"
        ),
        "approved_scope": metadata.get("approved_scope"),
        "scientifically_approved": metadata.get("scientifically_approved"),
        "proof_only": metadata.get("proof_only"),
        "not_production_routing": metadata.get("not_production_routing"),
        "production_route_enabled": metadata.get("production_route_enabled"),
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
        print(f"fixture: {report['fixture_path']}")
        print(
            "vertices/faces: "
            f"{report['fixture_vertex_count']}/{report['fixture_face_count']}"
        )
        print(
            "approval: "
            f"{report['approved_for_mapping_sample_transpose_proof']}"
        )
        print(
            f"anchors: {report['anchors']['located']}/{report['anchors']['expected']}"
        )
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
