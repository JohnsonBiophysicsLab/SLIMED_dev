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
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


GENERATOR_ID = "scripts/generate_b2p_loop_fixtures.py"
GENERATOR_VERSION = 1


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]


ICOSAHEDRON_VERTICES = (
    (-1.0, 1.6180339887498948482, 0.0),
    (1.0, 1.6180339887498948482, 0.0),
    (-1.0, -1.6180339887498948482, 0.0),
    (1.0, -1.6180339887498948482, 0.0),
    (0.0, -1.0, 1.6180339887498948482),
    (0.0, 1.0, 1.6180339887498948482),
    (0.0, -1.0, -1.6180339887498948482),
    (0.0, 1.0, -1.6180339887498948482),
    (1.6180339887498948482, 0.0, -1.0),
    (1.6180339887498948482, 0.0, 1.0),
    (-1.6180339887498948482, 0.0, -1.0),
    (-1.6180339887498948482, 0.0, 1.0),
)

ICOSAHEDRON_FACES = (
    (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
    (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
    (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
    (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
)


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
    path.write_text(text, encoding="utf-8", newline="")


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


def generate_flip_family(root: Path) -> None:
    family_root = root / "data/fixtures/candidates/b2p_single_flip_family"
    base = Mesh(ICOSAHEDRON_VERTICES, ICOSAHEDRON_FACES)
    base_face_ids = [f"base-face-{index:04d}" for index in range(len(base.faces))]
    base_metadata = _base_metadata(
        "b2p_single_flip_base", base,
        "embedded OpenSubdiv-style oriented icosahedron control topology",
        {"member": "base", "polyhedron": "icosahedron"},
    )
    base_metadata["family"] = {
        "face_ids_by_row": base_face_ids,
        "family_id": "b2p_single_flip_family",
        "member": "base",
    }
    _write_member(family_root / "base", base, base_metadata)

    variants: list[dict[str, Any]] = []
    selected_edges = ((0, 1), (2, 3), (4, 5))
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
            {"base_member": "base", "edge": list(edge), "member": name},
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
            "derivative_orders": ["position", "du", "dv", "duu", "duv", "dvv"],
            "row_changed_tolerance": 1.0e-12,
            "sample_identity": "same approved face-local (u,v) coordinate",
        },
        "family_id": "b2p_single_flip_family",
        "generator": {"id": GENERATOR_ID, "version": GENERATOR_VERSION},
        "identity_rule": (
            "Only unchanged base-face IDs are comparable. The exact two rewritten "
            "rows are recorded but are not assigned a false same-domain identity."
        ),
        "schema_version": 1,
        "variants": variants,
    }
    _write(family_root / "family_metadata.json", _json_text(family_metadata))


def _bipyramid_component(valence: int, connector_face_indices: tuple[int, ...],
                         x_offset: float) -> tuple[Mesh, list[tuple[int, int, int]], int]:
    vertices: list[tuple[float, float, float]] = [
        (x_offset, 0.0, 1.0),
        (x_offset, 0.0, -1.0),
    ]
    # Rational deterministic coordinates are sufficient for this topology-only
    # preflight fixture; B2 normalizes by the checked-in maximum edge length.
    for index in range(valence):
        vertices.append((x_offset + float(index), float(index * index + 1), 0.0))
    faces: list[tuple[int, int, int]] = []
    for index in range(valence):
        current = 2 + index
        following = 2 + ((index + 1) % valence)
        faces.append((0, current, following))
        faces.append((1, following, current))

    connectors: list[tuple[int, int, int]] = []
    for face_index in sorted(connector_face_indices, reverse=True):
        row = 2 * face_index + 1
        a, b, c = faces[row]
        center = len(vertices)
        vertices.append((
            (vertices[a][0] + vertices[b][0] + vertices[c][0]) / 3.0,
            (vertices[a][1] + vertices[b][1] + vertices[c][1]) / 3.0,
            (vertices[a][2] + vertices[b][2] + vertices[c][2]) / 3.0,
        ))
        replacement = [(a, b, center), (b, c, center), (c, a, center)]
        faces[row:row + 1] = replacement
        connectors.append(replacement[1])
    connectors.reverse()
    mesh = Mesh(tuple(vertices), tuple(faces))
    validate_mesh(mesh)
    return mesh, connectors, 0


class _UnionFind:
    def __init__(self, count: int) -> None:
        self.parent = list(range(count))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def generate_valence789(root: Path) -> None:
    specifications = ((7, (0,), 0.0), (8, (0, 4), 20.0), (9, (0,), 50.0))
    components = [_bipyramid_component(*spec) for spec in specifications]
    offsets: list[int] = []
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    connectors: list[list[tuple[int, int, int]]] = []
    target_apexes: list[int] = []
    for mesh, local_connectors, local_target in components:
        offset = len(vertices)
        offsets.append(offset)
        vertices.extend(mesh.vertices)
        faces.extend(tuple(offset + vertex for vertex in face) for face in mesh.faces)
        connectors.append([
            tuple(offset + vertex for vertex in face)
            for face in local_connectors
        ])
        target_apexes.append(offset + local_target)

    union = _UnionFind(len(vertices))
    glue_pairs = ((connectors[0][0], connectors[1][0]),
                  (connectors[1][1], connectors[2][0]))
    removed = {tuple(face) for pair in glue_pairs for face in pair}
    for left, right in glue_pairs:
        for left_vertex, right_vertex in zip(left, (right[0], right[2], right[1])):
            union.union(left_vertex, right_vertex)

    remaining_faces = [face for face in faces if face not in removed]
    roots = sorted({union.find(vertex) for face in remaining_faces for vertex in face})
    root_to_new = {root: index for index, root in enumerate(roots)}
    final_vertices = tuple(vertices[root] for root in roots)
    final_faces = tuple(
        tuple(root_to_new[union.find(vertex)] for vertex in face)
        for face in remaining_faces
    )
    mesh = Mesh(final_vertices, final_faces)
    validation = validate_mesh(mesh)
    targets = {
        str(valence): root_to_new[union.find(apex)]
        for valence, apex in zip((7, 8, 9), target_apexes)
    }
    for expected, vertex in targets.items():
        if validation["valence_by_vertex"][vertex] != int(expected):
            raise ValueError(f"target vertex {vertex} did not retain valence {expected}")

    metadata = _base_metadata(
        "b2p_closed_valence789", mesh,
        "oriented connected sum of deterministic triangular bipyramids",
        {
            "component_valences": [7, 8, 9],
            "connector_faces_per_component": [1, 2, 1],
            "gluing_orientation": "second boundary cycle reversed",
        },
    )
    metadata["declared_valence_vertices"] = targets
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
                if (output_root / relative).exists()]
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
