#!/usr/bin/env python3
"""Check the approved closed valence-5 narrow 11-control fixture contract."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


VERTICES_PATH = Path("data/fixtures/closed_valence5/vertices.csv")
FACES_PATH = Path("data/fixtures/closed_valence5/faces.csv")

ANCHORS = {
    Path("experiments/irregular_valence5_fixture_parity.cpp"): (
        "scientific_stand_in_scope",
        "deterministic_duplicate_aggregation_shape",
        "evaluate_energy_force(mesh);",
    ),
    Path("scripts/run_irregular_valence5_fixture_parity.sh"): (
        "-DOMP -fopenmp",
        "OMP_NUM_THREADS",
        "compare_irregular_valence5_fixture_parity.py",
    ),
    Path("scripts/compare_irregular_valence5_fixture_parity.py"): (
        'default=1.0e-10',
        "one_ring_source_ids",
        "not_broader_valence_routing",
    ),
    Path("tests/test_surface_geometry_characterization.cpp"): (
        "ApprovedClosedValenceFiveFixtureExercisesAllPositiveDepthElevenControlFaces",
        "direct_irregular_patch_energy_force(mesh, face)",
        "expectedForceComponents",
    ),
    Path("docs/irregular_valence5_scientific_fixture.md"): (
        "approved scientific stand-in",
        "unique original vertex IDs",
        "1.4210854715202004e-14",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_rows(path: Path, cast):
    with path.open(newline="", encoding="utf-8") as handle:
        return tuple(tuple(cast(value) for value in row) for row in csv.reader(handle))


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    vertices = read_rows(root / VERTICES_PATH, float)
    faces = read_rows(root / FACES_PATH, int)
    if len(vertices) != 12 or any(len(vertex) != 3 for vertex in vertices):
        errors.append("fixture must contain twelve three-component vertices")
    if len(faces) != 20 or any(len(face) != 3 for face in faces):
        errors.append("fixture must contain twenty triangular faces")

    neighbors: dict[int, set[int]] = defaultdict(set)
    edge_counts: Counter[tuple[int, int]] = Counter()
    for face in faces:
        for vertex in face:
            if vertex < 0 or vertex >= len(vertices):
                errors.append(f"face references invalid vertex {vertex}")
        for left, right in zip(face, face[1:] + face[:1]):
            neighbors[left].add(right)
            neighbors[right].add(left)
            edge_counts[tuple(sorted((left, right)))] += 1
    valences = [len(neighbors[index]) for index in range(len(vertices))]
    if valences != [5] * 12:
        errors.append(f"expected all vertex valences to be five, got {valences}")
    if len(edge_counts) != 30 or any(count != 2 for count in edge_counts.values()):
        errors.append("fixture must be closed with thirty two-face edges")

    located = 0
    expected = 0
    for relative_path, needles in ANCHORS.items():
        path = root / relative_path
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        for needle in needles:
            expected += 1
            if needle in text:
                located += 1
            else:
                errors.append(f"{relative_path} missing {needle!r}")

    return {
        "status": "passed" if not errors else "failed",
        "fixture": "closed_valence5_icosahedron",
        "scientific_stand_in_scope": "narrow_positive_depth_11_control",
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "vertex_valence_counts": dict(sorted(Counter(valences).items())),
        "edge_incidence_counts": dict(sorted(Counter(edge_counts.values()).items())),
        "anchors": {"located": located, "expected": expected},
        "not_broader_valence_routing": True,
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
        print(f"vertices: {report['vertex_count']}")
        print(f"faces: {report['face_count']}")
        print(f"anchors: {report['anchors']['located']}/{report['anchors']['expected']}")
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
