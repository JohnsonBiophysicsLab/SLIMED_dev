#!/usr/bin/env python3
"""Diagnose boundary-support point splitting from SLIMED vertex type CSV files."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


TYPE_NAMES = {
    0: "Real",
    1: "FixedBoundary",
    2: "PeriodicBoundary",
    3: "PeriodicReflectiveBoundary",
    4: "Ghost",
}

SUPPORT_TYPES = {1, 2, 3}
GHOST_TYPES = {4}
REFLECTIVE_EXPECTED_TYPES = {3, 4}
BOUNDARY_LIKE_TYPES = SUPPORT_TYPES | GHOST_TYPES

FIELDNAMES = [
    "record_type",
    "severity",
    "metric",
    "count",
    "vertex_index",
    "x",
    "y",
    "z",
    "type",
    "type_name",
    "type_family",
    "reflective_vertex_index",
    "reference_index",
    "reference_type",
    "reference_type_name",
    "reference_family",
    "dx",
    "dy",
    "dz",
    "distance",
    "group_id",
    "group_size",
    "group_families",
    "face_index",
    "face_vertices",
    "note",
]


@dataclass(frozen=True)
class VertexRow:
    index: int
    x: float
    y: float
    z: float
    type_id: int
    reflective_index: int

    @property
    def coord(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def type_name(self) -> str:
        return TYPE_NAMES.get(self.type_id, f"Unknown({self.type_id})")

    @property
    def type_family(self) -> str:
        return type_family(self.type_id)


@dataclass(frozen=True)
class FaceRow:
    index: int
    vertices: Tuple[int, int, int]


def type_family(type_id: int) -> str:
    if type_id == 0:
        return "real"
    if type_id in SUPPORT_TYPES:
        return "support"
    if type_id in GHOST_TYPES:
        return "ghost"
    return "unknown"


def split_csv_fields(line: str) -> List[str]:
    fields = [field.strip() for field in line.split(",")]
    while fields and fields[-1] == "":
        fields.pop()
    return fields


def has_alpha(fields: Sequence[str]) -> bool:
    return any(any(ch.isalpha() for ch in field) for field in fields)


def parse_int_field(value: str, *, line_number: int, field_name: str) -> int:
    try:
        return int(value)
    except ValueError:
        try:
            as_float = float(value)
        except ValueError as exc:
            raise ValueError(
                f"line {line_number}: invalid {field_name}: {value!r}"
            ) from exc
        if not as_float.is_integer():
            raise ValueError(
                f"line {line_number}: invalid {field_name}: {value!r}"
            )
        return int(as_float)


def parse_vertex_csv(path: Path) -> Tuple[List[VertexRow], int]:
    vertices: List[VertexRow] = []
    skipped_headers = 0

    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue

        fields = split_csv_fields(raw_line)
        if len(fields) < 5:
            if line_number == 1 and has_alpha(fields):
                skipped_headers += 1
                continue
            raise ValueError(
                f"line {line_number}: expected at least 5 columns "
                "(x,y,z,type,reflectiveVertexIndex)"
            )

        try:
            x = float(fields[0])
            y = float(fields[1])
            z = float(fields[2])
            type_id = parse_int_field(fields[3], line_number=line_number, field_name="type")
            reflective_index = parse_int_field(
                fields[4], line_number=line_number, field_name="reflectiveVertexIndex"
            )
        except ValueError:
            if line_number == 1 and has_alpha(fields):
                skipped_headers += 1
                continue
            raise

        vertices.append(
            VertexRow(
                index=len(vertices),
                x=x,
                y=y,
                z=z,
                type_id=type_id,
                reflective_index=reflective_index,
            )
        )

    return vertices, skipped_headers


def parse_face_csv(path: Path, *, index_base: int = 0) -> Tuple[List[FaceRow], int]:
    faces: List[FaceRow] = []
    skipped_headers = 0

    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue

        fields = split_csv_fields(raw_line)
        if len(fields) < 3:
            if line_number == 1 and has_alpha(fields):
                skipped_headers += 1
                continue
            raise ValueError(f"line {line_number}: expected at least 3 face columns")

        try:
            vertices = tuple(
                parse_int_field(field, line_number=line_number, field_name="face vertex")
                - index_base
                for field in fields[:3]
            )
        except ValueError:
            if line_number == 1 and has_alpha(fields):
                skipped_headers += 1
                continue
            raise

        faces.append(FaceRow(index=len(faces), vertices=vertices))

    return faces, skipped_headers


def format_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.17g}"


def distance(a: VertexRow, b: VertexRow) -> float:
    return math.dist(a.coord, b.coord)


def displacement(a: VertexRow, b: VertexRow) -> Tuple[float, float, float, float]:
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return dx, dy, dz, math.sqrt(dx * dx + dy * dy + dz * dz)


def coordinate_key(vertex: VertexRow, tolerance: float) -> Tuple[int, int, int]:
    if tolerance <= 0.0:
        return hash(vertex.x), hash(vertex.y), hash(vertex.z)
    return (
        int(round(vertex.x / tolerance)),
        int(round(vertex.y / tolerance)),
        int(round(vertex.z / tolerance)),
    )


def base_row(record_type: str, severity: str = "info", **values: object) -> Dict[str, str]:
    row = {field: "" for field in FIELDNAMES}
    row["record_type"] = record_type
    row["severity"] = severity
    for key, value in values.items():
        if key not in row:
            raise KeyError(f"unknown diagnostic field: {key}")
        if value is None:
            row[key] = ""
        elif isinstance(value, float):
            row[key] = format_float(value)
        else:
            row[key] = str(value)
    return row


def vertex_fields(vertex: VertexRow) -> Dict[str, object]:
    return {
        "vertex_index": vertex.index,
        "x": vertex.x,
        "y": vertex.y,
        "z": vertex.z,
        "type": vertex.type_id,
        "type_name": vertex.type_name,
        "type_family": vertex.type_family,
        "reflective_vertex_index": vertex.reflective_index,
    }


def reference_fields(vertex: VertexRow) -> Dict[str, object]:
    return {
        "reference_index": vertex.index,
        "reference_type": vertex.type_id,
        "reference_type_name": vertex.type_name,
        "reference_family": vertex.type_family,
    }


def family_summary(vertices: Iterable[VertexRow]) -> str:
    counts = Counter(vertex.type_family for vertex in vertices)
    return ";".join(f"{family}={counts[family]}" for family in sorted(counts))


def add_summary(rows: List[Dict[str, str]], summary: Dict[str, int], metric: str, count: int,
                *, severity: str = "info", note: str = "") -> None:
    summary[metric] = count
    rows.append(
        base_row(
            "summary",
            severity,
            metric=metric,
            count=count,
            note=note,
        )
    )


def diagnose_vertices(
    vertices: Sequence[VertexRow],
    *,
    baseline_vertices: Optional[Sequence[VertexRow]] = None,
    faces: Optional[Sequence[FaceRow]] = None,
    duplicate_tolerance: float = 1e-9,
    split_tolerance: float = 1e-5,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    rows: List[Dict[str, str]] = []
    summary: Dict[str, int] = {}

    add_summary(rows, summary, "vertex_count", len(vertices))
    add_summary(rows, summary, "duplicate_tolerance", 0, note=format_float(duplicate_tolerance))
    add_summary(rows, summary, "split_tolerance", 0, note=format_float(split_tolerance))

    type_counts = Counter(vertex.type_id for vertex in vertices)
    for type_id in sorted(type_counts):
        type_name = TYPE_NAMES.get(type_id, f"Unknown({type_id})")
        add_summary(
            rows,
            summary,
            f"type_count:{type_name}",
            type_counts[type_id],
            severity="warning" if type_id not in TYPE_NAMES else "info",
        )

    duplicate_groups_by_key: Dict[Tuple[int, int, int], List[VertexRow]] = defaultdict(list)
    for vertex in vertices:
        duplicate_groups_by_key[coordinate_key(vertex, duplicate_tolerance)].append(vertex)

    duplicate_groups = [
        group for group in duplicate_groups_by_key.values() if len(group) > 1
    ]
    add_summary(rows, summary, "duplicate_coordinate_group_count", len(duplicate_groups))

    duplicate_group_counts = Counter(family_summary(group) for group in duplicate_groups)
    mixed_duplicate_groups = 0
    for group_families, count in sorted(duplicate_group_counts.items()):
        if ";" in group_families:
            mixed_duplicate_groups += count
        add_summary(
            rows,
            summary,
            f"duplicate_coordinate_group_count:{group_families}",
            count,
            note="Coordinate groups are rounded by duplicate_tolerance.",
        )
    add_summary(rows, summary, "duplicate_coordinate_group_count:mixed_family", mixed_duplicate_groups)

    for group_id, group in enumerate(duplicate_groups, start=1):
        group_families = family_summary(group)
        note = "Duplicate coordinates within one type family."
        if ";" in group_families:
            note = (
                "Duplicate coordinates span real/support/ghost families. Plotting all "
                "families can make support points look like membrane points."
            )
        rows.append(
            base_row(
                "duplicate_coordinate_group",
                "info",
                group_id=group_id,
                group_size=len(group),
                group_families=group_families,
                note=note,
            )
        )
        for vertex in group:
            rows.append(
                base_row(
                    "duplicate_coordinate_member",
                    "info",
                    **vertex_fields(vertex),
                    group_id=group_id,
                    group_size=len(group),
                    group_families=group_families,
                    note=note,
                )
            )

    invalid_reflective_count = 0
    missing_reflective_count = 0
    reflective_pair_count = 0
    suspected_split_count = 0

    for vertex in vertices:
        reflective_index = vertex.reflective_index

        if reflective_index < 0:
            if vertex.type_id in REFLECTIVE_EXPECTED_TYPES:
                missing_reflective_count += 1
                rows.append(
                    base_row(
                        "missing_reflective_index",
                        "warning",
                        **vertex_fields(vertex),
                        note=(
                            "Ghost and periodic reflective rows usually need a reflective "
                            "index after periodic post-processing. A begin-state file may "
                            "legitimately have -1 before post-processing."
                        ),
                    )
                )
            continue

        if reflective_index >= len(vertices):
            invalid_reflective_count += 1
            rows.append(
                base_row(
                    "invalid_reflective_index",
                    "error",
                    **vertex_fields(vertex),
                    reference_index=reflective_index,
                    note="reflectiveVertexIndex is outside the vertex row range.",
                )
            )
            continue

        reference = vertices[reflective_index]
        dx, dy, dz, dist = displacement(vertex, reference)
        reflective_pair_count += 1
        rows.append(
            base_row(
                "reflective_pair_displacement",
                "info",
                **vertex_fields(vertex),
                **reference_fields(reference),
                dx=dx,
                dy=dy,
                dz=dz,
                distance=dist,
                note=(
                    "Large distances may be normal for unwrapped periodic or ghost "
                    "support coordinates. Small nonzero distances can indicate a split."
                ),
            )
        )

        if (
            vertex.type_id in BOUNDARY_LIKE_TYPES
            and duplicate_tolerance < dist <= split_tolerance
        ):
            suspected_split_count += 1
            rows.append(
                base_row(
                    "suspected_split_near_boundary",
                    "warning",
                    **vertex_fields(vertex),
                    **reference_fields(reference),
                    dx=dx,
                    dy=dy,
                    dz=dz,
                    distance=dist,
                    note=(
                        "Reflective pair is close but not coincident at the configured "
                        "split_tolerance. This points to geometry/output drift near the "
                        "boundary rather than a pure plotting artifact."
                    ),
                )
            )

    for vertex in vertices:
        if vertex.type_id not in BOUNDARY_LIKE_TYPES:
            continue

        nearest: Optional[Tuple[VertexRow, float]] = None
        for candidate in vertices:
            if candidate.index == vertex.index:
                continue
            if candidate.type_family == vertex.type_family:
                continue
            dist = distance(vertex, candidate)
            if nearest is None or dist < nearest[1]:
                nearest = (candidate, dist)

        if nearest is None:
            continue
        reference, dist = nearest
        if duplicate_tolerance < dist <= split_tolerance:
            dx, dy, dz, _ = displacement(vertex, reference)
            suspected_split_count += 1
            rows.append(
                base_row(
                    "suspected_split_near_boundary",
                    "warning",
                    **vertex_fields(vertex),
                    **reference_fields(reference),
                    dx=dx,
                    dy=dy,
                    dz=dz,
                    distance=dist,
                    note=(
                        "Boundary/support row is near a different vertex family but not "
                        "coincident. This can separate geometry drift from duplicate "
                        "support-point visualization."
                    ),
                )
            )

    add_summary(rows, summary, "reflective_pair_count", reflective_pair_count)
    add_summary(
        rows,
        summary,
        "invalid_reflective_index_count",
        invalid_reflective_count,
        severity="error" if invalid_reflective_count else "info",
    )
    add_summary(
        rows,
        summary,
        "missing_reflective_index_count",
        missing_reflective_count,
        severity="warning" if missing_reflective_count else "info",
    )
    add_summary(
        rows,
        summary,
        "suspected_split_near_boundary_count",
        suspected_split_count,
        severity="warning" if suspected_split_count else "info",
    )

    if faces is not None:
        add_face_diagnostics(rows, summary, vertices, faces)

    if baseline_vertices is not None:
        add_baseline_displacement_diagnostics(
            rows,
            summary,
            vertices,
            baseline_vertices,
            duplicate_tolerance=duplicate_tolerance,
            split_tolerance=split_tolerance,
        )

    add_interpretation(rows, summary)
    return rows, summary


def add_baseline_displacement_diagnostics(
    rows: List[Dict[str, str]],
    summary: Dict[str, int],
    vertices: Sequence[VertexRow],
    baseline_vertices: Sequence[VertexRow],
    *,
    duplicate_tolerance: float,
    split_tolerance: float,
) -> None:
    if len(vertices) != len(baseline_vertices):
        raise ValueError(
            "--baseline-vertices row count must match --vertices "
            f"({len(baseline_vertices)} != {len(vertices)})"
        )

    checked_count = 0
    mismatch_count = 0

    for vertex in vertices:
        reflective_index = vertex.reflective_index
        if reflective_index < 0 or reflective_index >= len(vertices):
            continue

        baseline_vertex = baseline_vertices[vertex.index]
        reference = vertices[reflective_index]
        baseline_reference = baseline_vertices[reflective_index]

        delta_x = (vertex.x - baseline_vertex.x) - (reference.x - baseline_reference.x)
        delta_y = (vertex.y - baseline_vertex.y) - (reference.y - baseline_reference.y)
        delta_z = (vertex.z - baseline_vertex.z) - (reference.z - baseline_reference.z)
        delta_distance = math.sqrt(delta_x * delta_x + delta_y * delta_y + delta_z * delta_z)
        checked_count += 1

        rows.append(
            base_row(
                "reflective_displacement_delta",
                "info",
                **vertex_fields(vertex),
                **reference_fields(reference),
                dx=delta_x,
                dy=delta_y,
                dz=delta_z,
                distance=delta_distance,
                note=(
                    "Compares current-minus-baseline displacement against the "
                    "reflective vertex displacement. Periodic post-processing is "
                    "expected to keep this near zero."
                ),
            )
        )

        if delta_distance > split_tolerance:
            mismatch_count += 1
            rows.append(
                base_row(
                    "reflective_displacement_mismatch",
                    "warning",
                    **vertex_fields(vertex),
                    **reference_fields(reference),
                    dx=delta_x,
                    dy=delta_y,
                    dz=delta_z,
                    distance=delta_distance,
                    note=(
                        "Reflective pair displacement changed differently between "
                        "baseline and current files. This points to geometry, "
                        "postprocess, or output-sync drift rather than ordinary "
                        "unwrapped periodic separation."
                    ),
                )
            )
        elif duplicate_tolerance < delta_distance <= split_tolerance:
            rows.append(
                base_row(
                    "reflective_displacement_mismatch",
                    "info",
                    **vertex_fields(vertex),
                    **reference_fields(reference),
                    dx=delta_x,
                    dy=delta_y,
                    dz=delta_z,
                    distance=delta_distance,
                    note=(
                        "Reflective pair displacement mismatch is nonzero but within "
                        "split_tolerance."
                    ),
                )
            )

    add_summary(rows, summary, "reflective_displacement_delta_count", checked_count)
    add_summary(
        rows,
        summary,
        "reflective_displacement_mismatch_count",
        mismatch_count,
        severity="warning" if mismatch_count else "info",
    )


def add_face_diagnostics(
    rows: List[Dict[str, str]],
    summary: Dict[str, int],
    vertices: Sequence[VertexRow],
    faces: Sequence[FaceRow],
) -> None:
    add_summary(rows, summary, "face_count", len(faces))

    adjacency_counts = Counter()
    invalid_face_count = 0
    mixed_family_face_count = 0

    for face in faces:
        invalid_indices = [
            index for index in face.vertices if index < 0 or index >= len(vertices)
        ]
        if invalid_indices:
            invalid_face_count += 1
            rows.append(
                base_row(
                    "invalid_face_indices",
                    "error",
                    face_index=face.index,
                    face_vertices=";".join(str(index) for index in face.vertices),
                    note="Face references vertices outside the vertex row range.",
                )
            )
            continue

        face_vertices = [vertices[index] for index in face.vertices]
        for vertex in face_vertices:
            adjacency_counts[vertex.index] += 1

        families = family_summary(face_vertices)
        if ";" in families:
            mixed_family_face_count += 1
            rows.append(
                base_row(
                    "mixed_family_face",
                    "info",
                    face_index=face.index,
                    face_vertices=";".join(str(index) for index in face.vertices),
                    group_families=families,
                    note=(
                        "Face spans real/support/ghost families. Plotting all faces can "
                        "show ghost or support geometry that is not the physical membrane."
                    ),
                )
            )

    zero_adjacency_count = 0
    for vertex in vertices:
        if adjacency_counts[vertex.index] != 0:
            continue
        zero_adjacency_count += 1
        rows.append(
            base_row(
                "zero_face_adjacency",
                "warning" if vertex.type_family == "real" else "info",
                **vertex_fields(vertex),
                note="Vertex is not referenced by any provided face row.",
            )
        )

    add_summary(
        rows,
        summary,
        "invalid_face_indices_count",
        invalid_face_count,
        severity="error" if invalid_face_count else "info",
    )
    add_summary(rows, summary, "mixed_family_face_count", mixed_family_face_count)
    add_summary(
        rows,
        summary,
        "zero_face_adjacency_count",
        zero_adjacency_count,
        severity="warning" if zero_adjacency_count else "info",
    )


def add_interpretation(rows: List[Dict[str, str]], summary: Dict[str, int]) -> None:
    invalid_reflective = summary.get("invalid_reflective_index_count", 0)
    displacement_mismatch = summary.get("reflective_displacement_mismatch_count", 0)
    suspected_split = summary.get("suspected_split_near_boundary_count", 0)
    mixed_duplicates = summary.get("duplicate_coordinate_group_count:mixed_family", 0)
    mixed_faces = summary.get("mixed_family_face_count", 0)

    if invalid_reflective:
        note = (
            "Invalid reflectiveVertexIndex rows are present. Investigate reflective "
            "indexing before treating the split as a plotting issue."
        )
        rows.append(base_row("interpretation", "error", metric="likely_reflective_indexing", count=invalid_reflective, note=note))
        return

    if displacement_mismatch:
        note = (
            "Reflective pair displacement differs between baseline and current files. "
            "That points to geometry, periodic postprocess, or output-sync drift."
        )
        rows.append(base_row("interpretation", "warning", metric="likely_reflective_displacement_mismatch", count=displacement_mismatch, note=note))
        return

    if suspected_split:
        note = (
            "Close-but-not-coincident boundary/support rows were found. This is the "
            "strongest signal for geometry or output drift near the boundary."
        )
        rows.append(base_row("interpretation", "warning", metric="likely_geometry_or_output_split", count=suspected_split, note=note))
        return

    if mixed_duplicates or mixed_faces:
        note = (
            "No close split was found, but duplicate or face rows span real/support/ghost "
            "families. If the screenshot shows extra boundary points, the likely cause is "
            "plotting support or ghost geometry together with physical membrane rows."
        )
        rows.append(base_row("interpretation", "info", metric="likely_support_visualization", count=mixed_duplicates + mixed_faces, note=note))
        return

    note = (
        "No reflective-index, close-split, duplicate-family, or face-mixing signal was "
        "found with the configured tolerances. If an artifact remains visible, inspect "
        "the plotting pipeline and tolerance settings."
    )
    rows.append(base_row("interpretation", "info", metric="no_split_signal", count=0, note=note))


def write_diagnostics_csv(rows: Sequence[Dict[str, str]], output: Path) -> None:
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose boundary splitting from vertex_type_begin.csv or "
            "vertex_type_final.csv without modifying SLIMED simulation outputs."
        )
    )
    parser.add_argument(
        "--vertices",
        required=True,
        type=Path,
        help="Path to vertex_type_begin.csv or vertex_type_final.csv.",
    )
    parser.add_argument(
        "--baseline-vertices",
        type=Path,
        help=(
            "Optional baseline vertex_type CSV, usually vertex_type_begin.csv, used "
            "to check reflective displacement equality against --vertices."
        ),
    )
    parser.add_argument(
        "--faces",
        type=Path,
        help="Optional face.csv path for face adjacency and mixed-family face checks.",
    )
    parser.add_argument(
        "--face-index-base",
        type=int,
        default=0,
        choices=(0, 1),
        help="Index base for --faces. SLIMED face.csv is 0-based. Default: 0.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("boundary_split_diagnostics.csv"),
        help="Diagnostic CSV output path. Default: boundary_split_diagnostics.csv.",
    )
    parser.add_argument(
        "--duplicate-tolerance",
        type=float,
        default=1e-9,
        help="Coordinate tolerance for duplicate groups. Default: 1e-9.",
    )
    parser.add_argument(
        "--split-tolerance",
        type=float,
        default=1e-5,
        help="Close-but-not-coincident distance threshold for split suspicion. Default: 1e-5.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.duplicate_tolerance < 0.0:
        parser.error("--duplicate-tolerance must be non-negative")
    if args.split_tolerance < args.duplicate_tolerance:
        parser.error("--split-tolerance must be greater than or equal to --duplicate-tolerance")

    vertices, skipped_vertex_headers = parse_vertex_csv(args.vertices)
    baseline_vertices = None
    skipped_baseline_headers = 0
    if args.baseline_vertices is not None:
        baseline_vertices, skipped_baseline_headers = parse_vertex_csv(args.baseline_vertices)
    faces = None
    skipped_face_headers = 0
    if args.faces is not None:
        faces, skipped_face_headers = parse_face_csv(
            args.faces, index_base=args.face_index_base
        )

    rows, summary = diagnose_vertices(
        vertices,
        baseline_vertices=baseline_vertices,
        faces=faces,
        duplicate_tolerance=args.duplicate_tolerance,
        split_tolerance=args.split_tolerance,
    )
    write_diagnostics_csv(rows, args.output)

    print(f"wrote {args.output}")
    print(f"vertices: {summary.get('vertex_count', 0)}")
    print(f"diagnostic rows: {len(rows)}")
    if skipped_vertex_headers:
        print(f"skipped vertex header rows: {skipped_vertex_headers}")
    if skipped_baseline_headers:
        print(f"skipped baseline header rows: {skipped_baseline_headers}")
    if skipped_face_headers:
        print(f"skipped face header rows: {skipped_face_headers}")
    for metric in (
        "duplicate_coordinate_group_count",
        "invalid_reflective_index_count",
        "missing_reflective_index_count",
        "reflective_pair_count",
        "reflective_displacement_mismatch_count",
        "suspected_split_near_boundary_count",
        "invalid_face_indices_count",
        "mixed_family_face_count",
    ):
        if metric in summary:
            print(f"{metric}: {summary[metric]}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
