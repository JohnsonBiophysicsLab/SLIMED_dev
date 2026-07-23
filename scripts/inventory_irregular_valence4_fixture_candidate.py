#!/usr/bin/env python3
"""Check the inert closed valence-4 regular-octahedron candidate packet."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path


FIXTURE_DIR = Path(
    "data/fixtures/candidates/closed_valence4_octahedron"
)
VERTICES_PATH = FIXTURE_DIR / "vertices.csv"
FACES_PATH = FIXTURE_DIR / "faces.csv"
METADATA_PATH = FIXTURE_DIR / "candidate_metadata.json"

ANCHORS = {
    Path("tests/test_surface_geometry_characterization.cpp"): (
        "CandidateClosedValenceFourFixtureRemainsUnsupportedBeforeGeometryMutation",
        "./data/fixtures/candidates/closed_valence4_octahedron/vertices.csv",
        "Broader-valence routing remains disabled",
    ),
    Path("docs/irregular_valence4_fixture_candidate.md"): (
        "Candidate Packet",
        "explicit scientific approval",
        "Broader-valence routing stays disabled",
    ),
    Path("docs/irregular_broader_valence_inventory.md"): (
        "closed_valence4_octahedron",
        "candidate packet",
        "scientific approval",
    ),
    Path("docs/irregular_routing_evidence_gap_map.md"): (
        "closed_valence4_octahedron",
        "candidate, not an approved scientific fixture",
        "routing remains disabled",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_rows(path: Path, cast):
    with path.open(newline="", encoding="utf-8") as handle:
        return tuple(tuple(cast(value) for value in row) for row in csv.reader(handle))


def subtract(left, right):
    return tuple(a - b for a, b in zip(left, right))


def cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def norm(vector):
    return math.sqrt(dot(vector, vector))


def close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12)


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    vertices = read_rows(root / VERTICES_PATH, float)
    faces = read_rows(root / FACES_PATH, int)
    metadata = json.loads((root / METADATA_PATH).read_text(encoding="utf-8"))

    if len(vertices) != 6 or any(len(vertex) != 3 for vertex in vertices):
        errors.append("candidate must contain six three-component vertices")
    if any(not math.isfinite(value) for vertex in vertices for value in vertex):
        errors.append("candidate vertices must contain only finite coordinates")
    if len(set(vertices)) != len(vertices):
        errors.append("candidate vertices must be unique")
    if len(faces) != 8 or any(len(face) != 3 for face in faces):
        errors.append("candidate must contain eight triangular faces")

    neighbors = [set() for _ in vertices]
    undirected_edges: Counter[tuple[int, int]] = Counter()
    directed_edges: Counter[tuple[int, int]] = Counter()
    valid_faces: list[tuple[int, int, int]] = []
    for face_index, face in enumerate(faces):
        if len(set(face)) != 3:
            errors.append(f"face {face_index} repeats a vertex")
            continue
        if any(vertex < 0 or vertex >= len(vertices) for vertex in face):
            errors.append(f"face {face_index} references an invalid vertex")
            continue
        valid_faces.append(face)
        for left, right in zip(face, face[1:] + face[:1]):
            neighbors[left].add(right)
            neighbors[right].add(left)
            undirected_edges[tuple(sorted((left, right)))] += 1
            directed_edges[(left, right)] += 1

    valences = [len(adjacent) for adjacent in neighbors]
    if valences != [4] * 6:
        errors.append(f"expected all vertex valences to be four, got {valences}")
    if len(undirected_edges) != 12 or any(
        count != 2 for count in undirected_edges.values()
    ):
        errors.append("candidate must be closed with twelve two-face edges")

    visited: set[int] = set()
    pending = [0] if vertices else []
    while pending:
        vertex = pending.pop()
        if vertex in visited:
            continue
        visited.add(vertex)
        pending.extend(neighbors[vertex] - visited)
    connected = len(visited) == len(vertices)
    euler_characteristic = len(vertices) - len(undirected_edges) + len(valid_faces)
    if not connected:
        errors.append("candidate vertex-edge graph must be connected")
    if euler_characteristic != 2:
        errors.append(
            f"candidate Euler characteristic must be two, got {euler_characteristic}"
        )

    coherently_oriented = all(
        directed_edges[(left, right)] == 1
        and directed_edges[(right, left)] == 1
        for left, right in undirected_edges
    )
    if not coherently_oriented:
        errors.append("each shared edge must occur once in each direction")

    triplets = Counter(
        "/".join(str(valences[vertex]) for vertex in face)
        for face in valid_faces
    )
    if triplets != {"4/4/4": 8}:
        errors.append(f"expected eight 4/4/4 face triplets, got {dict(triplets)}")

    edge_lengths = [
        norm(subtract(vertices[left], vertices[right]))
        for left, right in undirected_edges
    ]
    face_areas = []
    oriented_volume_contributions = []
    center = tuple(
        sum(vertex[axis] for vertex in vertices) / len(vertices)
        for axis in range(3)
    )
    outward_face_flags = []
    for first, second, third in valid_faces:
        first_edge = subtract(vertices[second], vertices[first])
        second_edge = subtract(vertices[third], vertices[first])
        face_normal = cross(first_edge, second_edge)
        face_areas.append(0.5 * norm(face_normal))
        face_center = tuple(
            (
                vertices[first][axis]
                + vertices[second][axis]
                + vertices[third][axis]
            )
            / 3.0
            for axis in range(3)
        )
        outward_face_flags.append(
            dot(face_normal, subtract(face_center, center)) > 0.0
        )
        oriented_volume_contributions.append(
            dot(vertices[first], cross(vertices[second], vertices[third])) / 6.0
        )

    circumradii = [norm(subtract(vertex, center)) for vertex in vertices]
    expected_circumradius = 1.0
    expected_edge_length = math.sqrt(2.0)
    expected_face_area = math.sqrt(3.0) / 2.0
    expected_total_area = 4.0 * math.sqrt(3.0)
    expected_volume = 4.0 / 3.0
    if not all(close(value, expected_circumradius) for value in circumradii):
        errors.append("serialized vertices do not all have circumradius one")
    if not all(close(value, expected_edge_length) for value in edge_lengths):
        errors.append("serialized edges do not all have length sqrt(2)")
    if not all(close(value, expected_face_area) for value in face_areas):
        errors.append("serialized faces do not all have area sqrt(3)/2")
    if not all(value > 0.0 for value in oriented_volume_contributions):
        errors.append("serialized faces are not all oriented outward")
    if not all(outward_face_flags):
        errors.append("serialized face winding does not point outward")
    total_area = sum(face_areas)
    signed_volume = sum(oriented_volume_contributions)
    if not close(total_area, expected_total_area):
        errors.append("total polyhedral area does not equal 4*sqrt(3)")
    if not close(signed_volume, expected_volume):
        errors.append("signed polyhedral volume does not equal 4/3")

    analytical = metadata.get("input_polyhedron_geometry", {})
    metadata_values = {
        "circumradius": expected_circumradius,
        "edge_length": expected_edge_length,
        "single_face_area": expected_face_area,
        "total_polyhedral_surface_area": expected_total_area,
        "signed_enclosed_polyhedral_volume": expected_volume,
    }
    for key, expected in metadata_values.items():
        entry = analytical.get(key, {})
        if not isinstance(entry, dict) or not close(entry.get("value", math.nan), expected):
            errors.append(f"metadata {key} does not match the serialized geometry")

    expected_topology = {
        "vertex_count": 6,
        "edge_count": 12,
        "face_count": 8,
        "vertex_valence": 4,
        "face_valence_triplet": "4/4/4",
        "closed_two_face_edge_manifold": True,
        "faces_oriented_outward": True,
    }
    if metadata.get("topology") != expected_topology:
        errors.append("metadata topology does not match the serialized candidate")
    if metadata.get("status") != "candidate_only":
        errors.append("metadata must label the fixture candidate_only")
    if metadata.get("scientifically_approved") is not False:
        errors.append("metadata must set scientifically_approved to false")
    if metadata.get("scientific_approval") != "required":
        errors.append("metadata must require scientific approval")
    if metadata.get("production_route_enabled") is not False:
        errors.append("metadata must set production_route_enabled to false")
    if (
        metadata.get("geometry_scope")
        != "straight_sided_input_polyhedron_not_slimed_output"
    ):
        errors.append("metadata must scope analytical values to the input polyhedron")
    expected_production = metadata.get("expected_current_production_contract", {})
    if expected_production.get("one_ring_size_per_face") != 0:
        errors.append("metadata must record an empty production one-ring per face")
    if (
        expected_production.get("geometry_preflight")
        != "runtime_error before area or volume mutation"
    ):
        errors.append("metadata must record the PR114 preflight ordering")
    claims_not_made = set(metadata.get("claims_not_made", []))
    for claim in (
        "scientific fixture approval",
        "broader-valence production routing",
        "membrane force correctness",
        "OpenSubdiv force correctness",
    ):
        if claim not in claims_not_made:
            errors.append(f"metadata must disclaim {claim}")

    located = 0
    expected_anchors = 0
    for relative_path, needles in ANCHORS.items():
        text = (
            (root / relative_path).read_text(encoding="utf-8")
            if (root / relative_path).is_file()
            else ""
        )
        for needle in needles:
            expected_anchors += 1
            if needle in text:
                located += 1
            else:
                errors.append(f"{relative_path} missing {needle!r}")

    return {
        "status": "passed" if not errors else "failed",
        "fixture": metadata.get("fixture_id"),
        "fixture_path": FIXTURE_DIR.as_posix(),
        "candidate_only": metadata.get("status") == "candidate_only",
        "scientifically_approved": metadata.get("scientifically_approved"),
        "scientific_approval_required": (
            metadata.get("scientific_approval") == "required"
        ),
        "production_route_enabled": metadata.get("production_route_enabled"),
        "vertex_count": len(vertices),
        "unique_finite_vertex_count": len(set(vertices))
        if all(math.isfinite(value) for vertex in vertices for value in vertex)
        else 0,
        "edge_count": len(undirected_edges),
        "face_count": len(faces),
        "valid_face_count": len(valid_faces),
        "edge_incidence_counts": dict(
            sorted(Counter(undirected_edges.values()).items())
        ),
        "vertex_valence_counts": dict(sorted(Counter(valences).items())),
        "face_valence_triplet_counts": dict(sorted(triplets.items())),
        "coherently_oriented_closed_connectivity": coherently_oriented,
        "connected": connected,
        "euler_characteristic": euler_characteristic,
        "outward_winding": all(outward_face_flags),
        "all_oriented_face_volume_contributions_positive": all(
            value > 0.0 for value in oriented_volume_contributions
        ),
        "geometry_scope": "straight_sided_input_polyhedron_not_slimed_output",
        "input_polyhedron_geometry": {
            "circumradius": expected_circumradius,
            "edge_length": expected_edge_length,
            "single_face_area": expected_face_area,
            "total_polyhedral_surface_area": total_area,
            "signed_enclosed_polyhedral_volume": signed_volume,
        },
        "expected_production_one_ring_size_counts": {"0": len(faces)},
        "expected_preflight": "runtime_error before area or volume mutation",
        "anchors": {"located": located, "expected": expected_anchors},
        "claims_not_made": sorted(claims_not_made),
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
            "vertices/edges/faces: "
            f"{report['vertex_count']}/{report['edge_count']}/{report['face_count']}"
        )
        print(f"vertex valences: {report['vertex_valence_counts']}")
        print(f"face triplets: {report['face_valence_triplet_counts']}")
        print(f"Euler characteristic: {report['euler_characteristic']}")
        print(f"anchors: {report['anchors']['located']}/{report['anchors']['expected']}")
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
