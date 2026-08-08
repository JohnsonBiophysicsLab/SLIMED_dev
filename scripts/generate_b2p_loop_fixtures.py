#!/usr/bin/env python3
"""Generate the deterministic, proof-only B2p Loop fixture corpus.

The generator uses only the Python standard library.  It writes a new output
tree and never reads or rewrites the checked-in fixture tree, which makes a
temporary-directory byte-reproduction check possible.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


GENERATOR_ID = "scripts/generate_b2p_loop_fixtures.py"
GENERATOR_VERSION = 2
GEOMETRY_SEED = 14631
GEOMETRY_VERTEX_COUNT = 13
MIN_TRIANGLE_QUALITY = 0.24


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]


LOCALITY_SAMPLE_MANIFEST = {
    "applicability": "every comparable unchanged face in every listed variant",
    "coordinate_rule": (
        "Use the same oriented face-local (u,v) coordinate in base and member; "
        "do not permute corners and do not duplicate samples per corner."
    ),
    "lattice_denominator": 6,
    "order_rule": (
        "Increasing i+j from 2 through 5, then increasing i; j=(i+j)-i."
    ),
    "row_order": ["position", "du", "dv", "duu", "duv", "dvv"],
    "samples": [
        {
            "barycentric_numerators": [6 - i - j, i, j],
            "id": f"tri-l6-s{i + j:02d}-u{i:02d}-v{j:02d}",
            "u_numerator": i,
            "v_numerator": j,
        }
        for total in range(2, 6)
        for i in range(1, total)
        for j in (total - i,)
    ],
}


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _float_text(value: float) -> str:
    if value == 0.0:
        return "0"
    return format(value, ".17g")


def _csv_text(rows: Iterable[Iterable[Any]], floats: bool = False) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for row in rows:
        writer.writerow([_float_text(value) if floats else str(value)
                         for value in row])
    return stream.getvalue()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Path.write_text() did not accept ``newline`` until Python 3.10.  Use the
    # underlying text stream so the byte contract is identical on the system
    # Python 3.9 profile and the CI-pinned Python 3.14 profile.
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)


def validate_mesh(mesh: Mesh) -> dict[str, Any]:
    vertex_count = len(mesh.vertices)
    if vertex_count < 4:
        raise ValueError("a closed triangular fixture needs at least four vertices")

    face_keys: set[tuple[int, int, int]] = set()
    edge_incidence: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    links: list[dict[int, set[int]]] = [defaultdict(set) for _ in mesh.vertices]
    used: set[int] = set()

    for face in mesh.faces:
        if len(face) != 3 or len(set(face)) != 3:
            raise ValueError(f"invalid triangular face {face}")
        if min(face) < 0 or max(face) >= vertex_count:
            raise ValueError(f"out-of-range triangular face {face}")
        key = tuple(sorted(face))
        if key in face_keys:
            raise ValueError(f"duplicate face {face}")
        face_keys.add(key)
        used.update(face)
        for corner in range(3):
            u = face[corner]
            v = face[(corner + 1) % 3]
            edge_incidence[tuple(sorted((u, v)))].append((u, v))
        a, b, c = face
        links[a][b].add(c)
        links[a][c].add(b)
        links[b][c].add(a)
        links[b][a].add(c)
        links[c][a].add(b)
        links[c][b].add(a)

    if used != set(range(vertex_count)):
        raise ValueError("fixture does not reference every vertex")
    for edge, directed in edge_incidence.items():
        if len(directed) != 2:
            raise ValueError(f"edge {edge} has {len(directed)} incident faces")
        if directed[0] != directed[1][::-1]:
            raise ValueError(f"edge {edge} does not have opposite directions")

    valences: list[int] = []
    for vertex, link in enumerate(links):
        if not link:
            raise ValueError(f"vertex {vertex} has an empty link")
        if any(len(opposites) != 2 for opposites in link.values()):
            raise ValueError(f"vertex {vertex} link is not degree two")
        start = min(link)
        reached = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in link[current]:
                if neighbor not in reached:
                    reached.add(neighbor)
                    queue.append(neighbor)
        if reached != set(link):
            raise ValueError(f"vertex {vertex} link is disconnected")
        valences.append(len(link))

    return {
        "all_vertices_referenced": True,
        "closed_two_face_edge_manifold": True,
        "connected_degree2_vertex_links": True,
        "duplicate_faces_absent": True,
        "edge_count": len(edge_incidence),
        "face_count": len(mesh.faces),
        "opposite_edge_orientation": True,
        "valence_by_vertex": valences,
        "vertex_count": vertex_count,
    }


def _base_metadata(fixture_id: str, mesh: Mesh, source: str,
                   parameters: dict[str, Any]) -> dict[str, Any]:
    validation = validate_mesh(mesh)
    return {
        "fixture_id": fixture_id,
        "generator": {
            "id": GENERATOR_ID,
            "parameters": parameters,
            "version": GENERATOR_VERSION,
        },
        "proof_only": True,
        "schema_version": 1,
        "scientifically_approved": False,
        "source_identity": source,
        "status": "candidate_only",
        "topology": validation,
    }


def _write_member(root: Path, mesh: Mesh, metadata: dict[str, Any]) -> None:
    _write(root / "vertices.csv", _csv_text(mesh.vertices, floats=True))
    _write(root / "faces.csv", _csv_text(mesh.faces))
    _write(root / "candidate_metadata.json", _json_text(metadata))


def _edge_incident_faces(faces: tuple[tuple[int, int, int], ...],
                         edge: tuple[int, int]) -> list[tuple[int, int, int, int]]:
    key = tuple(sorted(edge))
    incident: list[tuple[int, int, int, int]] = []
    for face_index, face in enumerate(faces):
        for corner in range(3):
            u, v = face[corner], face[(corner + 1) % 3]
            if tuple(sorted((u, v))) == key:
                incident.append((face_index, u, v, face[(corner + 2) % 3]))
    return incident


def flip_edge(mesh: Mesh, edge: tuple[int, int]) -> tuple[Mesh, dict[str, Any]]:
    incident = _edge_incident_faces(mesh.faces, edge)
    if len(incident) != 2:
        raise ValueError(f"edge {edge} is not a two-face edge")
    first, second = incident
    if (first[1], first[2]) != (second[2], second[1]):
        raise ValueError(f"edge {edge} has inconsistent orientation")
    row_a, u, v, opposite_a = first
    row_b, _, _, opposite_b = second
    new_edge = tuple(sorted((opposite_a, opposite_b)))
    existing_edges = {
        tuple(sorted((face[i], face[(i + 1) % 3])))
        for face in mesh.faces for i in range(3)
    }
    if opposite_a == opposite_b or new_edge in existing_edges:
        raise ValueError(f"edge {edge} is not legally flippable")

    faces = list(mesh.faces)
    faces[row_a] = (opposite_a, u, opposite_b)
    faces[row_b] = (opposite_a, opposite_b, v)
    flipped = Mesh(mesh.vertices, tuple(faces))
    validate_mesh(flipped)
    return flipped, {
        "old_edge": list(tuple(sorted(edge))),
        "new_edge": list(new_edge),
        "quad_boundary_cycle": [v, opposite_a, u, opposite_b],
        "rewritten_base_rows": sorted([row_a, row_b]),
        "rewritten_member_rows": sorted([row_a, row_b]),
    }


def _fraction_sub(left: tuple[Fraction, Fraction, Fraction],
                  right: tuple[Fraction, Fraction, Fraction]
                  ) -> tuple[Fraction, Fraction, Fraction]:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _fraction_cross(left: tuple[Fraction, Fraction, Fraction],
                    right: tuple[Fraction, Fraction, Fraction]
                    ) -> tuple[Fraction, Fraction, Fraction]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _fraction_dot(left: tuple[Fraction, Fraction, Fraction],
                  right: tuple[Fraction, Fraction, Fraction]) -> Fraction:
    return sum((a * b for a, b in zip(left, right)), Fraction(0))


def _asymmetric_convex_mesh() -> tuple[Mesh, dict[str, Any]]:
    """Return the seeded rational construction and its exact convex hull."""
    generator = random.Random(GEOMETRY_SEED)
    parameters = tuple(
        (generator.randint(-12, 12), generator.randint(-12, 12),
         generator.randint(1, 12))
        for _ in range(GEOMETRY_VERTEX_COUNT)
    )
    exact_vertices: list[tuple[Fraction, Fraction, Fraction]] = []
    for a, b, c in parameters:
        x, y = Fraction(a, c), Fraction(b, c)
        denominator = x * x + y * y + 1
        exact_vertices.append((
            2 * x / denominator,
            2 * y / denominator,
            (x * x + y * y - 1) / denominator,
        ))

    faces: list[tuple[int, int, int]] = []
    strict_side_checks = 0
    for i in range(len(exact_vertices)):
        for j in range(i + 1, len(exact_vertices)):
            for k in range(j + 1, len(exact_vertices)):
                normal = _fraction_cross(
                    _fraction_sub(exact_vertices[j], exact_vertices[i]),
                    _fraction_sub(exact_vertices[k], exact_vertices[i]),
                )
                sides = [
                    _fraction_dot(
                        normal,
                        _fraction_sub(exact_vertices[other], exact_vertices[i]),
                    )
                    for other in range(len(exact_vertices))
                    if other not in (i, j, k)
                ]
                if all(side < 0 for side in sides):
                    faces.append((i, j, k))
                    strict_side_checks += len(sides)
                elif all(side > 0 for side in sides):
                    faces.append((i, k, j))
                    strict_side_checks += len(sides)

    mesh = Mesh(
        tuple(tuple(float(value) for value in vertex)
              for vertex in exact_vertices),  # type: ignore[arg-type]
        tuple(faces),
    )
    topology = validate_mesh(mesh)
    if topology["vertex_count"] != GEOMETRY_VERTEX_COUNT:
        raise ValueError("seeded hull dropped a generated vertex")
    geometry = validate_geometry(mesh)
    if geometry["minimum_triangle_quality"] < MIN_TRIANGLE_QUALITY:
        raise ValueError("seeded hull missed the frozen triangle-quality floor")
    if geometry["nonadjacent_triangle_intersection_count"] != 0:
        raise ValueError("seeded hull is not embedded")
    return mesh, {
        "accepted_stereographic_integer_triples": [list(item) for item in parameters],
        "convex_hull": {
            "algorithm": (
                "enumerate vertex triples in lexicographic order with exact Fraction "
                "arithmetic; retain iff every other vertex lies strictly on one side; "
                "orient retained faces outward"
            ),
            "all_generated_vertices_retained": True,
            "strict_rational_side_checks": strict_side_checks,
        },
        "geometry_validation": geometry,
        "random_draw_contract": (
            "Python random.Random(seed); for each of 13 vertices draw a,b with "
            "randint(-12,12) and c with randint(1,12)"
        ),
        "seed": GEOMETRY_SEED,
        "stereographic_map": (
            "x=a/c, y=b/c; vertex=(2x,2y,x^2+y^2-1)/(x^2+y^2+1)"
        ),
    }


def _vsub(left: tuple[float, float, float], right: tuple[float, float, float]
          ) -> tuple[float, float, float]:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _cross(left: tuple[float, float, float], right: tuple[float, float, float]
           ) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left: tuple[float, float, float],
         right: tuple[float, float, float]) -> float:
    # Python 3.12 changed float summation.  fsum gives both supported profiles
    # the same accurately rounded result and keeps generated metadata stable.
    return math.fsum(a * b for a, b in zip(left, right))


def _segment_triangle_intersects(
        start: tuple[float, float, float], end: tuple[float, float, float],
        triangle: tuple[tuple[float, float, float], ...]) -> bool:
    epsilon = 1.0e-12
    direction = _vsub(end, start)
    edge1 = _vsub(triangle[1], triangle[0])
    edge2 = _vsub(triangle[2], triangle[0])
    pvec = _cross(direction, edge2)
    determinant = _dot(edge1, pvec)
    if abs(determinant) <= epsilon:
        return False
    inverse = 1.0 / determinant
    tvec = _vsub(start, triangle[0])
    u = _dot(tvec, pvec) * inverse
    if u < -epsilon or u > 1.0 + epsilon:
        return False
    qvec = _cross(tvec, edge1)
    v = _dot(direction, qvec) * inverse
    if v < -epsilon or u + v > 1.0 + epsilon:
        return False
    distance = _dot(edge2, qvec) * inverse
    return -epsilon <= distance <= 1.0 + epsilon


def _triangles_intersect(
        left: tuple[tuple[float, float, float], ...],
        right: tuple[tuple[float, float, float], ...]) -> bool:
    # The exact hull construction excludes coplanar disjoint facets.  Testing
    # all six boundary segments therefore covers every possible intersection.
    for triangle, other in ((left, right), (right, left)):
        for index in range(3):
            if _segment_triangle_intersects(
                    triangle[index], triangle[(index + 1) % 3], other):
                return True
    return False


def validate_geometry(mesh: Mesh) -> dict[str, Any]:
    if any(not math.isfinite(value) for vertex in mesh.vertices for value in vertex):
        raise ValueError("fixture has a non-finite coordinate")
    qualities: list[float] = []
    triangles = [tuple(mesh.vertices[index] for index in face)
                 for face in mesh.faces]
    for triangle in triangles:
        edge_vectors = (
            _vsub(triangle[1], triangle[0]),
            _vsub(triangle[2], triangle[1]),
            _vsub(triangle[0], triangle[2]),
        )
        doubled_area = math.sqrt(_dot(_cross(edge_vectors[0],
                                                   _vsub(triangle[2], triangle[0])),
                                           _cross(edge_vectors[0],
                                                  _vsub(triangle[2], triangle[0]))))
        if doubled_area <= 0.0:
            raise ValueError("fixture has a zero-area triangle")
        denominator = math.fsum(_dot(edge, edge) for edge in edge_vectors)
        qualities.append(2.0 * math.sqrt(3.0) * doubled_area / denominator)

    intersections = 0
    for left_index, left_face in enumerate(mesh.faces):
        for right_index in range(left_index + 1, len(mesh.faces)):
            if set(left_face).isdisjoint(mesh.faces[right_index]) and \
                    _triangles_intersect(triangles[left_index], triangles[right_index]):
                intersections += 1
    return {
        "all_coordinates_finite": True,
        "minimum_triangle_quality": min(qualities),
        "minimum_triangle_quality_bound": MIN_TRIANGLE_QUALITY,
        "nonadjacent_triangle_intersection_count": intersections,
        "positive_triangle_areas": True,
        "triangle_quality_definition": "4*sqrt(3)*area/(a^2+b^2+c^2)",
    }


def _mesh_adjacency(mesh: Mesh) -> list[set[int]]:
    adjacency = [set() for _ in mesh.vertices]
    for face in mesh.faces:
        for index in range(3):
            left, right = face[index], face[(index + 1) % 3]
            adjacency[left].add(right)
            adjacency[right].add(left)
    return adjacency


def _neighborhood_signature(mesh: Mesh, edge: tuple[int, int], radius: int
                            ) -> dict[str, Any]:
    adjacency = _mesh_adjacency(mesh)
    distances = {edge[0]: 0, edge[1]: 0}
    pending = deque(edge)
    while pending:
        current = pending.popleft()
        if distances[current] == radius:
            continue
        for neighbor in sorted(adjacency[current]):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                pending.append(neighbor)

    shell_records: list[dict[str, Any]] = []
    for shell in range(radius + 1):
        records = []
        for vertex in sorted(item for item, distance in distances.items()
                             if distance == shell):
            counts = [sum(distances.get(neighbor) == target
                          for neighbor in adjacency[vertex])
                      for target in range(radius + 1)]
            outside = sum(neighbor not in distances for neighbor in adjacency[vertex])
            records.append([len(adjacency[vertex]), *counts, outside])
        shell_records.append({"distance": shell, "records": sorted(records)})

    edge_counts = {(left, right): 0 for left in range(radius + 1)
                   for right in range(left, radius + 1)}
    for left, neighbors in enumerate(adjacency):
        for right in neighbors:
            if left < right and left in distances and right in distances:
                pair = tuple(sorted((distances[left], distances[right])))
                edge_counts[pair] += 1

    incident = _edge_incident_faces(mesh.faces, edge)
    return {
        "edge_shell_counts": [
            {"count": edge_counts[pair], "shells": list(pair)}
            for pair in sorted(edge_counts)
        ],
        "endpoint_valences": sorted(len(adjacency[vertex]) for vertex in edge),
        "opposite_valences": sorted(len(adjacency[item[3]]) for item in incident),
        "radius": radius,
        "shell_vertex_records": shell_records,
    }


def _selected_flip_edges(mesh: Mesh) -> list[tuple[int, int]]:
    adjacency = _mesh_adjacency(mesh)
    edge_set = {
        tuple(sorted((face[index], face[(index + 1) % 3])))
        for face in mesh.faces for index in range(3)
    }
    accepted: list[tuple[int, int]] = []
    endpoint_pairs: set[tuple[int, int]] = set()
    signatures = {1: set(), 2: set()}
    for edge in sorted(edge_set):
        incident = _edge_incident_faces(mesh.faces, edge)
        if len(incident) != 2:
            continue
        new_edge = tuple(sorted((incident[0][3], incident[1][3])))
        if incident[0][3] == incident[1][3] or new_edge in edge_set:
            continue
        endpoint_pair = tuple(sorted(len(adjacency[item]) for item in edge))
        candidates = {
            radius: json.dumps(_neighborhood_signature(mesh, edge, radius),
                               sort_keys=True, separators=(",", ":"))
            for radius in (1, 2)
        }
        if set(edge).intersection(item for accepted_edge in accepted
                                  for item in accepted_edge):
            continue
        if endpoint_pair in endpoint_pairs:
            continue
        if any(candidates[radius] in signatures[radius] for radius in (1, 2)):
            continue
        accepted.append(edge)
        endpoint_pairs.add(endpoint_pair)
        for radius in (1, 2):
            signatures[radius].add(candidates[radius])
        if len(accepted) == 3:
            return accepted
    raise ValueError("seeded hull did not provide three diverse legal flips")


def generate_flip_family(root: Path) -> None:
    family_root = root / "data/fixtures/candidates/b2p_single_flip_family"
    base, construction = _asymmetric_convex_mesh()
    base_face_ids = [f"base-face-{index:04d}" for index in range(len(base.faces))]
    base_metadata = _base_metadata(
        "b2p_single_flip_base", base,
        "seeded exact-rational stereographic convex hull",
        {"construction": construction, "member": "base"},
    )
    base_metadata["geometry"] = construction["geometry_validation"]
    base_metadata["family"] = {
        "face_ids_by_row": base_face_ids,
        "family_id": "b2p_single_flip_family",
        "member": "base",
    }
    _write_member(family_root / "base", base, base_metadata)

    variants: list[dict[str, Any]] = []
    selected_edges = tuple(_selected_flip_edges(base))
    for variant_index, edge in enumerate(selected_edges):
        name = f"flip_{variant_index:03d}"
        variant, flip = flip_edge(base, edge)
        rewritten = flip["rewritten_base_rows"]
        unchanged = [index for index in range(len(base.faces))
                     if index not in rewritten]
        face_ids = list(base_face_ids)
        for local_index, row in enumerate(rewritten):
            face_ids[row] = f"{name}-rewritten-{local_index}"

        correspondence = {
            "base_member": "base",
            "comparable_face_ids": [base_face_ids[row] for row in unchanged],
            "identity_rule": (
                "A face is identical only when its base-face ID, CSV row, and "
                "oriented vertex triple are all unchanged; each of the two "
                "rewritten rows receives a variant-local ID and has no base-face identity."
            ),
            "member": name,
            "neighborhood_signatures": {
                "radius_1": _neighborhood_signature(base, edge, 1),
                "radius_2": _neighborhood_signature(base, edge, 2),
            },
            "rewritten": {
                **flip,
                "base_face_ids": [base_face_ids[row] for row in rewritten],
                "base_oriented_faces": [list(base.faces[row]) for row in rewritten],
                "member_face_ids": [face_ids[row] for row in rewritten],
                "member_oriented_faces": [list(variant.faces[row]) for row in rewritten],
            },
            "unchanged": [
                {
                    "base_row": row,
                    "face_id": base_face_ids[row],
                    "member_row": row,
                    "oriented_vertices": list(base.faces[row]),
                }
                for row in unchanged
            ],
        }
        metadata = _base_metadata(
            f"b2p_single_flip_{name}", variant,
            "one deterministic legal edge flip from b2p_single_flip_base",
            {
                "base_member": "base",
                "base_seed": GEOMETRY_SEED,
                "edge": list(edge),
                "member": name,
                "selection_contract": (
                    "lexicographically scan legal base edges; require endpoint-disjoint "
                    "accepted edges, a new sorted endpoint-valence pair, and new exact "
                    "radius-1 and radius-2 signatures; accept the first three"
                ),
            },
        )
        metadata["family"] = {
            "correspondence": correspondence,
            "face_ids_by_row": face_ids,
            "family_id": "b2p_single_flip_family",
            "member": name,
        }
        _write_member(family_root / name, variant, metadata)
        variants.append(correspondence)

    family_metadata = {
        "base_member": "base",
        "comparison_contract": {
            "coefficient_norm": "linf over the source-ID union, missing coefficient equals zero",
            "derivative_orders": LOCALITY_SAMPLE_MANIFEST["row_order"],
            "row_changed_tolerance": 1.0e-12,
            "sample_identity": (
                "the exact ordered locality_sample_manifest entry, evaluated at the "
                "same oriented face-local (u,v) coordinate"
            ),
        },
        "construction_provenance": construction,
        "family_id": "b2p_single_flip_family",
        "generator": {"id": GENERATOR_ID, "version": GENERATOR_VERSION},
        "identity_rule": (
            "Only unchanged base-face IDs are comparable. The exact two rewritten "
            "rows are recorded but are not assigned a false same-domain identity."
        ),
        "schema_version": 1,
        "locality_sample_manifest": LOCALITY_SAMPLE_MANIFEST,
        "selected_flip_edges": [list(edge) for edge in selected_edges],
        "selection_contract": (
            "lexicographically scan legal base edges; require endpoint-disjoint accepted "
            "edges, a new sorted endpoint-valence pair, and new exact radius-1 and "
            "radius-2 signatures; accept the first three"
        ),
        "variants": variants,
    }
    _write(family_root / "family_metadata.json", _json_text(family_metadata))


def generate_valence789(root: Path) -> None:
    mesh, construction = _asymmetric_convex_mesh()
    validation = validate_mesh(mesh)
    targets = {"7": 2, "8": 4, "9": 0}
    for expected, vertex in targets.items():
        if validation["valence_by_vertex"][vertex] != int(expected):
            raise ValueError(f"target vertex {vertex} did not retain valence {expected}")

    metadata = _base_metadata(
        "b2p_closed_valence789", mesh,
        "seeded exact-rational stereographic convex hull",
        {"construction": construction},
    )
    metadata["declared_valence_vertices"] = targets
    metadata["geometry"] = construction["geometry_validation"]
    metadata["topology"]["contains_valences"] = [7, 8, 9]
    _write_member(root / "data/fixtures/candidates/b2p_valence789", mesh, metadata)


def generate_adjacent_extraordinary(root: Path) -> None:
    vertices = (
        (0.0, 0.0, 1.0), (0.0, 0.0, -1.0),
        (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0),
    )
    faces = (
        (0, 2, 3), (0, 3, 4), (0, 4, 5), (0, 5, 2),
        (1, 3, 2), (1, 4, 3), (1, 5, 4), (1, 2, 5),
    )
    base = Mesh(vertices, faces)
    mesh, flip = flip_edge(base, (0, 2))
    validation = validate_mesh(mesh)
    adjacent = list(flip["new_edge"])
    adjacent_valences = [validation["valence_by_vertex"][vertex]
                         for vertex in adjacent]
    if adjacent_valences != [5, 5]:
        raise ValueError("adjacent extraordinary vertices are not both valence five")
    metadata = _base_metadata(
        "b2p_adjacent_extraordinary", mesh,
        "one legal edge flip of an oriented octahedral sphere",
        {"base": "octahedron", "flipped_edge": [0, 2]},
    )
    metadata["adjacent_extraordinary"] = {
        "shared_edge": adjacent,
        "valences": adjacent_valences,
        "vertices": adjacent,
    }
    metadata["construction_flip"] = flip
    _write_member(
        root / "data/fixtures/candidates/b2p_adjacent_extraordinary",
        mesh, metadata)


def generate(output_root: Path) -> None:
    relative_roots = (
        Path("data/fixtures/candidates/b2p_single_flip_family"),
        Path("data/fixtures/candidates/b2p_valence789"),
        Path("data/fixtures/candidates/b2p_adjacent_extraordinary"),
    )
    existing = [relative for relative in relative_roots
                if (output_root / relative).exists()
                and any(path.is_file() for path in
                        (output_root / relative).rglob("*"))]
    if existing:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            f"refusing to overwrite an existing B2p fixture tree: {joined}")
    generate_flip_family(output_root)
    generate_valence789(output_root)
    generate_adjacent_extraordinary(output_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root", required=True, type=Path,
        help="root under which data/fixtures/candidates is created",
    )
    arguments = parser.parse_args()
    generate(arguments.output_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
