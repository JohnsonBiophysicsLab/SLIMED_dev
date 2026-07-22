#!/usr/bin/env python3
"""Inventory mesh fixtures for irregular one-ring routing candidates.

This is an inert docs/scripts helper. It reads checked-in CSV mesh fixtures and
small generated topology probes, derives conservative face one-ring route
buckets from triangle connectivity, and reports where ghost/boundary status is
available. It does not parse, compile, or execute production C++.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from math import sqrt
from pathlib import Path
from typing import Sequence


REGULAR_ROUTE = "regular 12-control membrane force"
SUPPORTED_11_ROUTE = "supported positive-depth 11=4+3+4 irregular route"
ZERO_DEPTH_GUARD = "zero-depth 11-control guard applies"
UNSUPPORTED_ROUTE = "unsupported broader valence or incomplete one-ring"
OPENSUBDIV_GAP = "OpenSubdiv-replacement gap candidate"
BOUNDARY_ROUTE = "boundary/ghost excluded from physical irregular route"


ROUTE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "route": REGULAR_ROUTE,
        "inventory_mapping": "interior/non-ghost faces whose three vertices all have valence 6",
        "current_behavior": "supported",
    },
    {
        "route": SUPPORTED_11_ROUTE,
        "inventory_mapping": "interior/non-ghost faces whose three vertices all have valence 5",
        "current_behavior": "supported only when Param::subDivideTimes > 0",
    },
    {
        "route": ZERO_DEPTH_GUARD,
        "inventory_mapping": "same 11-control candidates when subdivision depth is zero",
        "current_behavior": "guarded unsupported",
    },
    {
        "route": UNSUPPORTED_ROUTE,
        "inventory_mapping": "non-boundary faces outside the current regular-12 or 11=4+3+4 predicates",
        "current_behavior": "unsupported; regular fallback remains disabled",
    },
    {
        "route": OPENSUBDIV_GAP,
        "inventory_mapping": "unsupported physical irregular topologies needing a future backend policy",
        "current_behavior": "not production",
    },
)


@dataclass(frozen=True)
class MeshInput:
    label: str
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]
    source: str
    ghost_status: str
    face_ghost_flags: tuple[bool | None, ...]


@dataclass(frozen=True)
class SkippedSource:
    label: str
    path: str
    reason: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_vertices_csv(path: Path) -> tuple[tuple[float, float, float], ...]:
    vertices: list[tuple[float, float, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            values = [cell.strip() for cell in row if cell.strip()]
            if not values:
                continue
            try:
                vertices.append((float(values[0]), float(values[1]), float(values[2])))
            except (IndexError, ValueError):
                if values[:3] == ["x", "y", "z"]:
                    continue
                raise ValueError(f"{path} contains a non-coordinate row: {row!r}")
    return tuple(vertices)


def parse_faces_csv(path: Path) -> tuple[tuple[int, int, int], ...]:
    faces: list[tuple[int, int, int]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            values = [cell.strip() for cell in row if cell.strip()]
            if not values:
                continue
            try:
                faces.append((int(values[0]), int(values[1]), int(values[2])))
            except (IndexError, ValueError):
                lowered = [value.lower() for value in values[:3]]
                if lowered in (["v0", "v1", "v2"], ["vertex0", "vertex1", "vertex2"]):
                    continue
                raise ValueError(f"{path} contains a non-face row: {row!r}")
    return tuple(faces)


def infer_flat_grid_divisions(
    vertex_count: int,
    faces: Sequence[tuple[int, int, int]],
) -> tuple[int, int] | None:
    """Recognize the row-major topology emitted by Mesh::set_vertices_faces_flat."""
    if not faces:
        return None
    first = faces[0]
    if first[2] != 0 or first[1] != first[0] + 1:
        return None
    n_face_x = first[0] - 1
    if n_face_x <= 0 or len(faces) % (2 * n_face_x) != 0:
        return None
    n_face_y = len(faces) // (2 * n_face_x)
    if (n_face_x + 1) * (n_face_y + 1) != vertex_count:
        return None
    return n_face_x, n_face_y


def periodic_ghost_face_flags(n_face_x: int, n_face_y: int) -> tuple[bool, ...]:
    """Mirror Mesh::determine_ghost_vertices_faces for periodic flat faces."""
    flags = [False] * (2 * n_face_x * n_face_y)
    ghost_rows = {0, 1, 2, n_face_y - 3, n_face_y - 2, n_face_y - 1}
    ghost_columns = {0, 1, 2, n_face_x - 3, n_face_x - 2, n_face_x - 1}
    for row in ghost_rows:
        for column in range(n_face_x):
            face = 2 * n_face_x * row + 2 * column
            flags[face] = True
            flags[face + 1] = True
    for column in ghost_columns:
        for row in range(n_face_y):
            face = 2 * n_face_x * row + 2 * column
            flags[face] = True
            flags[face + 1] = True
    return tuple(flags)


def approved_example_ghost_contract(
    root: Path,
    label: str,
    vertex_count: int,
    faces: Sequence[tuple[int, int, int]],
) -> tuple[str, tuple[bool | None, ...]] | None:
    """Return the reviewed production ghost contract for data/example."""
    if label != "data/example":
        return None
    params_path = root / label / "example.params"
    if (
        not params_path.is_file()
        or "boundaryType = Periodic"
        not in params_path.read_text(encoding="utf-8")
    ):
        return None
    divisions = infer_flat_grid_divisions(vertex_count, faces)
    if divisions is None:
        return None
    n_face_x, n_face_y = divisions
    return (
        "production periodic ghost policy from data/example/example.params "
        f"(nFaceX={n_face_x}, nFaceY={n_face_y})",
        periodic_ghost_face_flags(n_face_x, n_face_y),
    )


def checked_in_mesh_inputs(root: Path) -> tuple[list[MeshInput], list[SkippedSource]]:
    meshes: list[MeshInput] = []
    skipped: list[SkippedSource] = []

    for face_path in sorted(root.glob("**/faces*.csv")):
        if any(part.startswith(".") for part in face_path.relative_to(root).parts):
            continue
        vertex_path = face_path.with_name(face_path.name.replace("faces", "vertices", 1))
        if not vertex_path.is_file():
            skipped.append(
                SkippedSource(
                    label=face_path.relative_to(root).as_posix(),
                    path=face_path.relative_to(root).as_posix(),
                    reason="face CSV has no sibling vertices CSV",
                )
            )
            continue
        faces = parse_faces_csv(face_path)
        vertices = parse_vertices_csv(vertex_path)
        label = face_path.parent.relative_to(root).as_posix()
        ghost_contract = approved_example_ghost_contract(
            root, label, len(vertices), faces
        )
        if ghost_contract is None:
            ghost_status = "not serialized in CSV fixture"
            ghost_flags: tuple[bool | None, ...] = tuple(None for _ in faces)
        else:
            ghost_status, ghost_flags = ghost_contract
        meshes.append(
            MeshInput(
                label=label,
                vertices=vertices,
                faces=faces,
                source=f"{vertex_path.relative_to(root).as_posix()} + {face_path.relative_to(root).as_posix()}",
                ghost_status=ghost_status,
                face_ghost_flags=ghost_flags,
            )
        )

    paired_vertex_paths = {
        path.with_name(path.name.replace("faces", "vertices", 1))
        for path in root.glob("**/faces*.csv")
    }
    for csv_path in sorted((root / "data").glob("**/*.csv")):
        if csv_path.name.startswith("faces") or csv_path in paired_vertex_paths:
            continue
        try:
            vertices = parse_vertices_csv(csv_path)
        except ValueError:
            continue
        if vertices:
            skipped.append(
                SkippedSource(
                    label=csv_path.relative_to(root).as_posix(),
                    path=csv_path.relative_to(root).as_posix(),
                    reason="coordinate CSV has no face connectivity",
                )
            )
    return meshes, skipped


def generated_icosahedron() -> MeshInput:
    phi = (1.0 + sqrt(5.0)) / 2.0
    vertices = (
        (-1.0, phi, 0.0),
        (1.0, phi, 0.0),
        (-1.0, -phi, 0.0),
        (1.0, -phi, 0.0),
        (0.0, -1.0, phi),
        (0.0, 1.0, phi),
        (0.0, -1.0, -phi),
        (0.0, 1.0, -phi),
        (phi, 0.0, -1.0),
        (phi, 0.0, 1.0),
        (-phi, 0.0, -1.0),
        (-phi, 0.0, 1.0),
    )
    faces = (
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    )
    return MeshInput(
        label="generated/closed_icosahedron_valence5",
        vertices=vertices,
        faces=faces,
        source="generated topology probe; not checked-in production output",
        ghost_status="available: generated faces are non-ghost",
        face_ghost_flags=tuple(False for _ in faces),
    )


def parse_mesh_arg(value: str) -> tuple[Path, Path, str]:
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError("--mesh expects FACE_CSV:VERTEX_CSV[:LABEL]")
    face_path = Path(parts[0])
    vertex_path = Path(parts[1])
    label = parts[2] if len(parts) == 3 else face_path.stem
    return face_path, vertex_path, label


def load_extra_meshes(mesh_args: Sequence[tuple[Path, Path, str]]) -> list[MeshInput]:
    meshes: list[MeshInput] = []
    for face_path, vertex_path, label in mesh_args:
        faces = parse_faces_csv(face_path)
        vertices = parse_vertices_csv(vertex_path)
        meshes.append(
            MeshInput(
                label=label,
                vertices=vertices,
                faces=faces,
                source=f"{vertex_path} + {face_path}",
                ghost_status="not serialized in CSV fixture",
                face_ghost_flags=tuple(None for _ in faces),
            )
        )
    return meshes


def edge_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def summarize_mesh(mesh: MeshInput, candidate_limit: int) -> dict[str, object]:
    errors: list[str] = []
    vertex_count = len(mesh.vertices)
    face_count = len(mesh.faces)
    vertex_neighbors: list[set[int]] = [set() for _ in range(vertex_count)]
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)

    for face_index, face in enumerate(mesh.faces):
        face_errors: list[str] = []
        if len(set(face)) != 3:
            face_errors.append(f"face {face_index} repeats a vertex: {face}")
            continue
        for vertex in face:
            if vertex < 0 or vertex >= vertex_count:
                face_errors.append(f"face {face_index} references vertex {vertex} outside 0..{vertex_count - 1}")
        if face_errors:
            errors.extend(face_errors)
            continue
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            vertex_neighbors[a].add(b)
            vertex_neighbors[b].add(a)
            edge_faces[edge_key(a, b)].append(face_index)

    route_counts: Counter[str] = Counter()
    one_ring_counts: Counter[str] = Counter()
    valence_triplets: Counter[str] = Counter()
    examples: dict[str, list[dict[str, object]]] = defaultdict(list)
    zero_depth_guard_candidates = 0
    opensubdiv_gap_candidates = 0

    for face_index, face in enumerate(mesh.faces):
        if any(vertex < 0 or vertex >= vertex_count for vertex in face) or len(set(face)) != 3:
            continue
        incident_lengths = [
            len(edge_faces[edge_key(face[0], face[1])]),
            len(edge_faces[edge_key(face[1], face[2])]),
            len(edge_faces[edge_key(face[2], face[0])]),
        ]
        topology_boundary = any(length == 1 for length in incident_lengths)
        nonmanifold = any(length > 2 for length in incident_lengths)
        ghost_flag = mesh.face_ghost_flags[face_index] if face_index < len(mesh.face_ghost_flags) else None
        valences = tuple(len(vertex_neighbors[vertex]) for vertex in face)
        triplet_key = "/".join(str(value) for value in sorted(valences))
        valence_triplets[triplet_key] += 1

        one_ring_size: int | None = None
        route = UNSUPPORTED_ROUTE
        note = "outside current regular-12 and 11=4+3+4 predicates"
        if ghost_flag is True or topology_boundary:
            route = BOUNDARY_ROUTE
            note = "boundary or ghost face is excluded before physical irregular routing"
        elif nonmanifold:
            route = UNSUPPORTED_ROUTE
            note = "nonmanifold edge incidence needs a topology policy"
        elif all(value == 6 for value in valences):
            one_ring_size = 12
            route = REGULAR_ROUTE
            note = "matches current regular one-ring predicate"
        elif all(value == 5 for value in valences):
            one_ring_size = 11
            route = SUPPORTED_11_ROUTE
            note = "matches current 11=4+3+4 positive-depth predicate"
            zero_depth_guard_candidates += 1
        else:
            opensubdiv_gap_candidates += 1

        one_ring_counts[str(one_ring_size) if one_ring_size is not None else "unavailable"] += 1
        route_counts[route] += 1

        if route in {
            SUPPORTED_11_ROUTE,
            UNSUPPORTED_ROUTE,
            BOUNDARY_ROUTE,
            OPENSUBDIV_GAP,
        } and len(examples[route]) < candidate_limit:
            examples[route].append(
                {
                    "face_index": face_index,
                    "vertices": list(face),
                    "vertex_valences": list(valences),
                    "topology_boundary": topology_boundary,
                    "ghost": ghost_flag,
                    "derived_one_ring_size": one_ring_size,
                    "route_note": note,
                }
            )

    if opensubdiv_gap_candidates:
        route_counts[OPENSUBDIV_GAP] = opensubdiv_gap_candidates
    if zero_depth_guard_candidates:
        route_counts[ZERO_DEPTH_GUARD] = zero_depth_guard_candidates

    edge_incidence_counts = Counter(len(faces) for faces in edge_faces.values())
    return {
        "label": mesh.label,
        "source": mesh.source,
        "vertex_count": vertex_count,
        "face_count": face_count,
        "ghost_status": mesh.ghost_status,
        "edge_incidence_counts": dict(sorted(edge_incidence_counts.items())),
        "vertex_valence_counts": dict(sorted(Counter(len(neighbors) for neighbors in vertex_neighbors).items())),
        "face_valence_triplet_counts": dict(sorted(valence_triplets.items())),
        "derived_one_ring_size_counts": dict(sorted(one_ring_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "candidate_examples": {key: value for key, value in sorted(examples.items())},
        "errors": errors,
    }


def collect_inventory(
    root: Path,
    include_checked_in: bool,
    include_generated: bool,
    extra_mesh_args: Sequence[tuple[Path, Path, str]],
    candidate_limit: int,
) -> dict[str, object]:
    meshes: list[MeshInput] = []
    skipped: list[SkippedSource] = []
    if include_checked_in:
        checked_meshes, checked_skipped = checked_in_mesh_inputs(root)
        meshes.extend(checked_meshes)
        skipped.extend(checked_skipped)
    if include_generated:
        meshes.append(generated_icosahedron())
    meshes.extend(load_extra_meshes(extra_mesh_args))

    summaries = [summarize_mesh(mesh, candidate_limit=candidate_limit) for mesh in meshes]
    aggregate_routes: Counter[str] = Counter()
    aggregate_one_rings: Counter[str] = Counter()
    errors: list[str] = []
    for summary in summaries:
        aggregate_routes.update(summary["route_counts"])
        aggregate_one_rings.update(summary["derived_one_ring_size_counts"])
        errors.extend(f"{summary['label']}: {error}" for error in summary["errors"])

    return {
        "status": "passed" if not errors else "failed",
        "route_matrix": list(ROUTE_MATRIX),
        "aggregate_route_counts": dict(sorted(aggregate_routes.items())),
        "aggregate_one_ring_size_counts": dict(sorted(aggregate_one_rings.items())),
        "mesh_summaries": summaries,
        "skipped_sources": [skipped_source.__dict__ for skipped_source in skipped],
        "errors": errors,
    }


def print_counter(counter: dict[object, object], indent: str = "  ") -> None:
    if not counter:
        print(f"{indent}- none")
        return
    for key, value in counter.items():
        print(f"{indent}- {key}: {value}")


def print_text(inventory: dict[str, object]) -> None:
    print("# Irregular Fixture Candidate Inventory")
    print()
    print("This report is inert: it reads fixture topology and does not execute production C++.")
    print()
    print("## Route matrix")
    for row in inventory["route_matrix"]:
        print(f"- {row['route']}")
        print(f"  mapping: {row['inventory_mapping']}")
        print(f"  current_behavior: {row['current_behavior']}")
    print()
    print("## Aggregate route counts")
    print_counter(inventory["aggregate_route_counts"])
    print()
    print("## Aggregate derived one-ring sizes")
    print_counter(inventory["aggregate_one_ring_size_counts"])

    for summary in inventory["mesh_summaries"]:
        print()
        print(f"## {summary['label']}")
        print(f"- source: {summary['source']}")
        print(f"- vertices: {summary['vertex_count']}")
        print(f"- faces: {summary['face_count']}")
        print(f"- ghost status: {summary['ghost_status']}")
        print("- edge incidence counts:")
        print_counter(summary["edge_incidence_counts"], indent="  ")
        print("- vertex valence counts:")
        print_counter(summary["vertex_valence_counts"], indent="  ")
        print("- derived one-ring size counts:")
        print_counter(summary["derived_one_ring_size_counts"], indent="  ")
        print("- route counts:")
        print_counter(summary["route_counts"], indent="  ")
        if summary["candidate_examples"]:
            print("- candidate examples:")
            for route, examples in summary["candidate_examples"].items():
                print(f"  - {route}:")
                for example in examples:
                    print(
                        "    - face {face_index}, vertices {vertices}, valences {vertex_valences}, "
                        "boundary={topology_boundary}, ghost={ghost}, one_ring={derived_one_ring_size}".format(
                            **example
                        )
                    )
        if summary["errors"]:
            print("- errors:")
            for error in summary["errors"]:
                print(f"  - {error}")

    if inventory["skipped_sources"]:
        print()
        print("## Skipped sources")
        for skipped in inventory["skipped_sources"]:
            print(f"- {skipped['label']}: {skipped['reason']}")


def check_inventory(
    inventory: dict[str, object],
    include_checked_in: bool,
    include_generated: bool,
) -> list[str]:
    failures = list(inventory["errors"])
    labels = {summary["label"] for summary in inventory["mesh_summaries"]}
    if include_checked_in and "data/example" not in labels:
        failures.append("expected checked-in data/example face/vertex CSV pair was not inventoried")
    if include_generated and "generated/closed_icosahedron_valence5" not in labels:
        failures.append("expected generated icosahedron probe was not inventoried")
    for summary in inventory["mesh_summaries"]:
        if summary["label"] == "data/example":
            route_counts = summary["route_counts"]
            expected_routes = {BOUNDARY_ROUTE: 960, REGULAR_ROUTE: 2720}
            if route_counts != expected_routes:
                failures.append(
                    "data/example production ghost contract should expose exactly "
                    f"{expected_routes}, got {route_counts}"
                )
            if route_counts.get(SUPPORTED_11_ROUTE, 0) != 0:
                failures.append("data/example should not expose a physical 11-control face")
            if route_counts.get(OPENSUBDIV_GAP, 0) != 0:
                failures.append("data/example mixed-valence faces should all be production ghosts")
        if summary["label"] == "generated/closed_icosahedron_valence5":
            route_counts = summary["route_counts"]
            if route_counts.get(SUPPORTED_11_ROUTE) != 20:
                failures.append("generated icosahedron should expose twenty positive-depth 11-control faces")
            if route_counts.get(ZERO_DEPTH_GUARD) != 20:
                failures.append("generated icosahedron should map all 11-control faces to the zero-depth guard")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--check", action="store_true", help="Exit nonzero on inventory or invariant failures.")
    parser.add_argument(
        "--no-checked-in",
        action="store_true",
        help="Skip automatic checked-in mesh fixture discovery.",
    )
    parser.add_argument(
        "--no-generated",
        action="store_true",
        help="Skip generated topology probes.",
    )
    parser.add_argument(
        "--mesh",
        action="append",
        default=[],
        type=parse_mesh_arg,
        help="Add FACE_CSV:VERTEX_CSV[:LABEL] to the inventory.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=5,
        help="Maximum candidate examples to print per route and mesh.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    include_generated = not args.no_generated
    inventory = collect_inventory(
        root=repo_root(),
        include_checked_in=not args.no_checked_in,
        include_generated=include_generated,
        extra_mesh_args=args.mesh,
        candidate_limit=args.candidate_limit,
    )
    if args.json:
        print(json.dumps(inventory, indent=2, sort_keys=True))
    else:
        print_text(inventory)
    if args.check:
        failures = check_inventory(
            inventory,
            include_checked_in=not args.no_checked_in,
            include_generated=include_generated,
        )
        if failures:
            print()
            print("## Check failures")
            for failure in failures:
                print(f"- {failure}")
            return 1
    return 0 if inventory["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
