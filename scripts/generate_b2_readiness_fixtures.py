#!/usr/bin/env python3
"""Generate the deterministic B2-readiness fixtures and execution manifest.

This standard-library-only generator writes a new output tree.  It does not
read the checked-in fixture corpus and it never runs a Bfr or Far candidate.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


GENERATOR_ID = "scripts/generate_b2_readiness_fixtures.py"
GENERATOR_VERSION = 1
ROOT_NAME = "b2_readiness_v1"


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _float(value: float) -> str:
    return "0" if value == 0.0 else format(value, ".17g")


def _csv(rows: Iterable[Iterable[Any]], floats: bool = False) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for row in rows:
        writer.writerow([_float(item) if floats else str(item) for item in row])
    return stream.getvalue()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]
         ) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]
           ) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b))


def _norm(a: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(a, a))


def _normalize(a: tuple[float, float, float]) -> tuple[float, float, float]:
    length = _norm(a)
    if length == 0.0:
        raise ValueError("cannot normalize zero vector")
    return (a[0] / length, a[1] / length, a[2] / length)


def validate_topology(mesh: Mesh) -> dict[str, Any]:
    if len(mesh.vertices) < 4:
        raise ValueError("too few vertices")
    if any(not math.isfinite(x) for vertex in mesh.vertices for x in vertex):
        raise ValueError("nonfinite coordinate")
    face_keys: set[tuple[int, int, int]] = set()
    edges: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    links: list[dict[int, set[int]]] = [defaultdict(set) for _ in mesh.vertices]
    used: set[int] = set()
    for face in mesh.faces:
        if len(set(face)) != 3 or min(face) < 0 or max(face) >= len(mesh.vertices):
            raise ValueError(f"invalid face {face}")
        key = tuple(sorted(face))
        if key in face_keys:
            raise ValueError(f"duplicate face {face}")
        face_keys.add(key)
        used.update(face)
        a, b, c = face
        for u, v in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((u, v)))].append((u, v))
        for center, left, right in ((a, b, c), (b, c, a), (c, a, b)):
            links[center][left].add(right)
            links[center][right].add(left)
    if used != set(range(len(mesh.vertices))):
        raise ValueError("unreferenced vertex")
    for edge, incidence in edges.items():
        if len(incidence) != 2 or incidence[0] != incidence[1][::-1]:
            raise ValueError(f"edge incidence/orientation failure {edge}")
    valences = []
    for vertex, link in enumerate(links):
        if not link or any(len(neighbors) != 2 for neighbors in link.values()):
            raise ValueError(f"non-cycle link at vertex {vertex}")
        reached = {min(link)}
        queue = deque(reached)
        while queue:
            current = queue.popleft()
            for neighbor in link[current]:
                if neighbor not in reached:
                    reached.add(neighbor)
                    queue.append(neighbor)
        if reached != set(link):
            raise ValueError(f"disconnected link at vertex {vertex}")
        valences.append(len(link))
    reached_vertices = {0}
    queue = deque(reached_vertices)
    while queue:
        current = queue.popleft()
        for neighbor in links[current]:
            if neighbor not in reached_vertices:
                reached_vertices.add(neighbor)
                queue.append(neighbor)
    if reached_vertices != set(range(len(mesh.vertices))):
        raise ValueError("disconnected surface")
    return {
        "all_coordinates_finite": True,
        "all_vertices_referenced": True,
        "closed_two_face_edge_manifold": True,
        "connected_surface": True,
        "connected_degree2_vertex_links": True,
        "duplicate_faces_absent": True,
        "edge_count": len(edges),
        "face_count": len(mesh.faces),
        "opposite_edge_orientation": True,
        "valence_by_vertex": valences,
        "vertex_count": len(mesh.vertices),
    }


def _segment_triangle(start: tuple[float, float, float],
                      end: tuple[float, float, float],
                      tri: tuple[tuple[float, float, float], ...]) -> bool:
    epsilon = 1.0e-11
    direction = _sub(end, start)
    edge1, edge2 = _sub(tri[1], tri[0]), _sub(tri[2], tri[0])
    pvec = _cross(direction, edge2)
    determinant = _dot(edge1, pvec)
    if abs(determinant) <= epsilon:
        return False
    inverse = 1.0 / determinant
    tvec = _sub(start, tri[0])
    u = _dot(tvec, pvec) * inverse
    qvec = _cross(tvec, edge1)
    v = _dot(direction, qvec) * inverse
    distance = _dot(edge2, qvec) * inverse
    return (-epsilon <= u <= 1.0 + epsilon and
            -epsilon <= v and u + v <= 1.0 + epsilon and
            -epsilon <= distance <= 1.0 + epsilon)


def validate_geometry(mesh: Mesh) -> dict[str, Any]:
    triangles = [tuple(mesh.vertices[i] for i in face) for face in mesh.faces]
    qualities = []
    for triangle in triangles:
        edge0 = _sub(triangle[1], triangle[0])
        edge1 = _sub(triangle[2], triangle[1])
        edge2 = _sub(triangle[0], triangle[2])
        doubled_area = _norm(_cross(edge0, _sub(triangle[2], triangle[0])))
        if doubled_area <= 0.0:
            raise ValueError("zero-area triangle")
        denominator = math.fsum(_dot(edge, edge) for edge in (edge0, edge1, edge2))
        qualities.append(2.0 * math.sqrt(3.0) * doubled_area / denominator)
    intersections = 0
    for i, left in enumerate(mesh.faces):
        for j in range(i + 1, len(mesh.faces)):
            if not set(left).isdisjoint(mesh.faces[j]):
                continue
            left_tri, right_tri = triangles[i], triangles[j]
            hit = any(_segment_triangle(left_tri[k], left_tri[(k + 1) % 3], right_tri)
                      for k in range(3))
            hit = hit or any(
                _segment_triangle(right_tri[k], right_tri[(k + 1) % 3], left_tri)
                for k in range(3))
            intersections += int(hit)
    if intersections:
        raise ValueError(f"{intersections} nonadjacent triangle intersections")
    return {
        "minimum_triangle_quality": min(qualities),
        "nonadjacent_triangle_intersection_count": 0,
        "positive_triangle_areas": True,
        "triangle_quality_definition": "4*sqrt(3)*area/(a^2+b^2+c^2)",
    }


def _bipyramid(asymmetric: bool) -> Mesh:
    root3 = math.sqrt(3.0)
    vertices = [(-1.0, -root3 / 3.0, 0.0),
                (1.0, -root3 / 3.0, 0.0),
                (0.0, 2.0 * root3 / 3.0, 0.0),
                (0.0, 0.0, 1.5), (0.0, 0.0, -1.5)]
    if asymmetric:
        vertices[1] = (1.17, -0.91 * root3 / 3.0, 0.13)
        vertices[3] = (0.19, -0.11, 1.63)
        vertices[4] = (-0.08, 0.16, -1.41)
    faces = ((3, 0, 1), (3, 1, 2), (3, 2, 0),
             (4, 1, 0), (4, 2, 1), (4, 0, 2))
    return Mesh(tuple(vertices), faces)


def _regular_torus(major_segments: int = 12, minor_segments: int = 8) -> Mesh:
    major_radius, minor_radius = 3.0, 1.0
    vertices = []
    for i in range(major_segments):
        theta = 2.0 * math.pi * i / major_segments
        for j in range(minor_segments):
            phi = 2.0 * math.pi * j / minor_segments
            radial = major_radius + minor_radius * math.cos(phi)
            vertices.append((radial * math.cos(theta), radial * math.sin(theta),
                             minor_radius * math.sin(phi)))
    def index(i: int, j: int) -> int:
        return (i % major_segments) * minor_segments + (j % minor_segments)
    faces = []
    for i in range(major_segments):
        for j in range(minor_segments):
            a, b = index(i, j), index(i + 1, j)
            c, d = index(i + 1, j + 1), index(i, j + 1)
            faces.extend(((a, b, c), (a, c, d)))
    return Mesh(tuple(vertices), tuple(faces))


def _icosahedron() -> Mesh:
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    raw = [(0.0, s1, s2 * phi) for s1 in (-1.0, 1.0) for s2 in (-1.0, 1.0)]
    raw += [(s1, s2 * phi, 0.0) for s1 in (-1.0, 1.0) for s2 in (-1.0, 1.0)]
    raw += [(s2 * phi, 0.0, s1) for s1 in (-1.0, 1.0) for s2 in (-1.0, 1.0)]
    vertices = tuple(_normalize(vertex) for vertex in raw)
    faces = []
    epsilon = 1.0e-12
    for i in range(len(vertices)):
        for j in range(i + 1, len(vertices)):
            for k in range(j + 1, len(vertices)):
                normal = _cross(_sub(vertices[j], vertices[i]),
                                _sub(vertices[k], vertices[i]))
                sides = [_dot(normal, _sub(vertices[n], vertices[i]))
                         for n in range(len(vertices)) if n not in (i, j, k)]
                if all(value < -epsilon for value in sides):
                    faces.append((i, j, k))
                elif all(value > epsilon for value in sides):
                    faces.append((i, k, j))
    return Mesh(vertices, tuple(faces))


def _refined_icosahedron() -> tuple[Mesh, dict[str, Any]]:
    base = _icosahedron()
    midpoint_ids: dict[tuple[int, int], int] = {}
    vertices = list(base.vertices)
    def midpoint(a: int, b: int) -> int:
        edge = tuple(sorted((a, b)))
        if edge not in midpoint_ids:
            summed = tuple(base.vertices[a][axis] + base.vertices[b][axis]
                           for axis in range(3))
            midpoint_ids[edge] = len(vertices)
            vertices.append(_normalize(summed))  # type: ignore[arg-type]
        return midpoint_ids[edge]
    faces = []
    declared = None
    for base_row, (a, b, c) in enumerate(base.faces):
        ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
        children = ((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca))
        if base_row == 0:
            declared = {"face_row": 0, "oriented_vertices": list(children[0]),
                        "valence_pattern": [5, 6, 6],
                        "original_valence5_vertex": a,
                        "edge_midpoint_valence6_vertices": [ab, ca]}
        faces.extend(children)
    assert declared is not None
    return Mesh(tuple(vertices), tuple(faces)), declared


def _metadata(fixture_id: str, mesh: Mesh, construction: dict[str, Any]) -> dict[str, Any]:
    return {
        "construction": construction,
        "fixture_id": fixture_id,
        "generator": {"id": GENERATOR_ID, "version": GENERATOR_VERSION},
        "geometry": validate_geometry(mesh),
        "proof_only": True,
        "schema_version": 1,
        "scientifically_approved": False,
        "status": "candidate_only_pending_D12",
        "topology": validate_topology(mesh),
    }


def _write_fixture(root: Path, name: str, mesh: Mesh,
                   construction: dict[str, Any]) -> None:
    member = root / name
    _write(member / "vertices.csv", _csv(mesh.vertices, floats=True))
    _write(member / "faces.csv", _csv(mesh.faces))
    _write(member / "candidate_metadata.json",
           _json(_metadata(name, mesh, construction)))


def execution_manifest() -> dict[str, Any]:
    rows = [
        ("U8-01", "Regular closed/periodic mesh", "b2_readiness_v1/regular_all6_torus"),
        ("U8-02", "Tetrahedron", "closed_valence3_tetrahedron"),
        ("U8-03", "Octahedron", "closed_valence4_octahedron"),
        ("U8-04", "Icosahedron", "closed_valence5"),
        ("U8-05", "Symmetric 3/4/4 bipyramid", "b2_readiness_v1/symmetric_344_bipyramid"),
        ("U8-06", "Asymmetric 3/4/4 bipyramid", "b2_readiness_v1/asymmetric_344_bipyramid"),
        ("U8-07", "Closed mixed 3/4/5", "closed_mixed_valence345"),
        ("U8-08", "Intended 5/6/6 local patch in a closed mesh", "b2_readiness_v1/closed_566_refined_icosahedron"),
        ("U8-09", "Non-Platonic closed triangulation", "b2p_valence789"),
        ("U8-10", "Coordinate-perturbed variants", "mutation:coordinate_perturbation_v1"),
        ("U8-11", "Reversed/inconsistent winding", "mutation:reverse_face_zero_v1"),
        ("U8-12", "Open boundary mesh", "mutation:delete_face_zero_v1"),
        ("U8-13", "Non-manifold/duplicate edge", "mutation:append_face_zero_v1"),
        ("U8-14", "Topology-mutated/edge-flipped mesh", "b2p_single_flip_family"),
        ("B7-01", "Single-flip pair family", "b2p_single_flip_family"),
        ("B7-02", "Closed mesh containing valence 7, 8, and 9 corners", "b2p_valence789"),
        ("B7-03", "Adjacent extraordinary corners sharing an edge", "b2p_adjacent_extraordinary"),
    ]
    entries = [{"fixture_or_mutation": target, "id": row_id, "row": name}
               for row_id, name, target in rows]
    return {
        "entries": entries,
        "fixture_roots": {
            "b2_readiness_v1": "data/fixtures/candidates/b2_readiness_v1",
            "b2p_adjacent_extraordinary": "data/fixtures/candidates/b2p_adjacent_extraordinary",
            "b2p_single_flip_family": "data/fixtures/candidates/b2p_single_flip_family",
            "b2p_valence789": "data/fixtures/candidates/b2p_valence789",
            "closed_mixed_valence345": "data/fixtures/candidates/closed_mixed_valence345",
            "closed_valence3_tetrahedron": "data/fixtures/candidates/closed_valence3_tetrahedron",
            "closed_valence4_octahedron": "data/fixtures/candidates/closed_valence4_octahedron",
            "closed_valence5": "data/fixtures/closed_valence5",
        },
        "mutation_rules": [
            {"base": "b2_readiness_v1/asymmetric_344_bipyramid", "id": "coordinate_perturbation_v1",
             "operation": "add exact binary64 deltas (+0x1p-8,-0x1p-9,+0x1p-10) to vertex row 1 only; topology unchanged"},
            {"base": "b2_readiness_v1/regular_all6_torus", "id": "reverse_face_zero_v1",
             "operation": "replace face row 0 [a,b,c] with [a,c,b]"},
            {"base": "b2_readiness_v1/regular_all6_torus", "id": "delete_face_zero_v1",
             "operation": "delete face row 0 and preserve every remaining row in order"},
            {"base": "b2_readiness_v1/regular_all6_torus", "id": "append_face_zero_v1",
             "operation": "append an exact duplicate of face row 0 without changing prior rows"},
        ],
        "ordering_contract": "entry checks execute exactly in listed order with no omission, substitution, or reordering; byte-identical fixture content may be loaded once but mesh-level aggregation obeys shared_hull_deduplication",
        "schema_version": 1,
        "shared_hull_deduplication": "b2p_valence789 and b2p_single_flip_family/base share bytes and count once as mesh-level evidence",
        "stable_locality_manifest": "data/fixtures/candidates/b2p_single_flip_family/family_metadata.json#locality_sample_manifest",
        "status": "pending_D12",
    }


def generate(root: Path) -> None:
    symmetric = _bipyramid(False)
    asymmetric = _bipyramid(True)
    torus = _regular_torus()
    refined, declared = _refined_icosahedron()
    _write_fixture(root, "symmetric_344_bipyramid", symmetric, {
        "kind": "triangular_bipyramid", "symmetry": "threefold",
        "declared_face_row": 0, "declared_face_valences": [3, 4, 4]})
    _write_fixture(root, "asymmetric_344_bipyramid", asymmetric, {
        "kind": "triangular_bipyramid", "symmetry": "deliberately_broken",
        "declared_face_row": 0, "declared_face_valences": [3, 4, 4],
        "coordinates": "fixed literals independent of candidate output"})
    _write_fixture(root, "regular_all6_torus", torus, {
        "kind": "embedded_periodic_triangulated_torus", "major_radius": 3,
        "minor_radius": 1, "major_segments": 12, "minor_segments": 8,
        "expected_uniform_valence": 6})
    _write_fixture(root, "closed_566_refined_icosahedron", refined, {
        "kind": "one_midpoint_refinement_of_algorithmic_regular_icosahedron",
        "declared_566_face": declared,
        "midpoints": "each base edge midpoint normalized to the unit sphere"})
    _write(root / "execution_manifest.json", _json(execution_manifest()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output_root.exists() and any(arguments.output_root.iterdir()):
        parser.error("output root must be absent or empty")
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    generate(arguments.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
