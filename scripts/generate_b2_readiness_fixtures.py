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
from fractions import Fraction
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


GENERATOR_ID = "scripts/generate_b2_readiness_fixtures.py"
GENERATOR_VERSION = 1
ROOT_NAME = "b2_readiness_v1"
MANIFEST_CONTRACT_SHA256 = (
    "676b03e36b4db9fb618f75bddd80382c79e1a824d47353b1244b75f02f1d2bda")


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


def _member(member_id: str, path: str, content_key: str) -> dict[str, str]:
    return {"content_identity_key": content_key,
            "member_id": member_id, "path": path}


def _fixture_input(*members: dict[str, str]) -> dict[str, Any]:
    return {"kind": "checked_in_fixture", "members": list(members)}


def _mutation_input(mutation_id: str, base: dict[str, str],
                    output_key: str) -> dict[str, Any]:
    return {"base_member": base, "kind": "deterministic_mutation",
            "mutation_id": mutation_id,
            "output_content_identity_key": output_key}


def _check(check_id: str, source_text: str, procedure: str | None = None,
           reason: str | None = None) -> dict[str, str]:
    if (procedure is None) == (reason is None):
        raise ValueError("each source check needs exactly one disposition")
    if procedure is not None:
        return {"b2_applicability": "APPLICABLE", "check_id": check_id,
                "procedure": procedure, "source_text": source_text}
    return {"b2_applicability": "N/A", "check_id": check_id,
            "reason": reason or "", "source_text": source_text}


def _entry(case_id: str, matrix_id: str, row: str, evidence_key: str,
           input_spec: dict[str, Any], sample_policy: str,
           corner_policy: str, checks: list[dict[str, str]],
           numeric: bool = True, alias_of: str | None = None) -> dict[str, Any]:
    return {
        "alias_of": alias_of,
        "candidates": ["bfr", "far"],
        "corner_policy_ref": corner_policy,
        "execution_case_id": case_id,
        "face_policy": {"kind": "all_faces", "order": "ascending_csv_row"},
        "input": input_spec,
        "mesh_evidence_key": evidence_key,
        "numeric_gate_applicability": {
            "peak_rss": numeric,
            "preparation_cost": numeric,
            "retained_row_payload": numeric,
            "threading_bfr_only": numeric,
        },
        "row_order_ref": "six_source_rows_v1",
        "sample_policy_ref": sample_policy,
        "source_matrix_checks": checks,
        "source_matrix_row": row,
        "source_matrix_row_id": matrix_id,
    }


def _regular_samples() -> list[dict[str, Any]]:
    return [
        {"barycentric_numerators": [6 - i - j, i, j],
         "id": f"tri-l6-s{i + j:02d}-u{i:02d}-v{j:02d}",
         "u_numerator": i, "v_numerator": j}
        for total in range(2, 6)
        for i in range(1, total)
        for j in (total - i,)
    ]


def _trend_samples() -> list[dict[str, Any]]:
    rays = ((1, 4, 3, 4), (1, 2, 1, 2), (3, 4, 1, 4))
    samples = []
    for exponent in range(1, 9):
        for ray_index, (xi_n, xi_d, eta_n, eta_d) in enumerate(rays):
            xi = Fraction(xi_n, xi_d * (2 ** exponent))
            eta = Fraction(eta_n, eta_d * (2 ** exponent))
            samples.append({
                "eta": f"{eta.numerator}/{eta.denominator}",
                "id": f"trend-r{exponent:02d}-ray{ray_index:02d}",
                "radius": f"1/{2 ** exponent}",
                "radius_exponent": exponent,
                "ray_index": ray_index,
                "xi": f"{xi.numerator}/{xi.denominator}",
            })
    return samples


def execution_manifest() -> dict[str, Any]:
    torus = _member("regular_all6_torus", "data/fixtures/candidates/b2_readiness_v1/regular_all6_torus", "regular_all6_torus")
    tetra = _member("closed_valence3_tetrahedron", "data/fixtures/candidates/closed_valence3_tetrahedron", "closed_valence3_tetrahedron")
    octa = _member("closed_valence4_octahedron", "data/fixtures/candidates/closed_valence4_octahedron", "closed_valence4_octahedron")
    icosa = _member("closed_valence5", "data/fixtures/closed_valence5", "closed_valence5")
    symmetric = _member("symmetric_344_bipyramid", "data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid", "symmetric_344_bipyramid")
    asymmetric = _member("asymmetric_344_bipyramid", "data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid", "asymmetric_344_bipyramid")
    mixed = _member("closed_mixed_valence345", "data/fixtures/candidates/closed_mixed_valence345", "closed_mixed_valence345")
    refined = _member("closed_566_refined_icosahedron", "data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron", "closed_566_refined_icosahedron")
    shared_hull = _member("b2p_valence789", "data/fixtures/candidates/b2p_valence789", "b2p_shared_hull_base")
    flip_members = (
        _member("base", "data/fixtures/candidates/b2p_single_flip_family/base", "b2p_shared_hull_base"),
        _member("flip_000", "data/fixtures/candidates/b2p_single_flip_family/flip_000", "b2p_flip_000"),
        _member("flip_001", "data/fixtures/candidates/b2p_single_flip_family/flip_001", "b2p_flip_001"),
        _member("flip_002", "data/fixtures/candidates/b2p_single_flip_family/flip_002", "b2p_flip_002"),
    )
    adjacent = _member("b2p_adjacent_extraordinary", "data/fixtures/candidates/b2p_adjacent_extraordinary", "b2p_adjacent_extraordinary")

    rows_checks = [_check("rows", "Rows", procedure="Evaluate all six source-keyed rows in the frozen row/sample order; apply the regular analytic or D10 Stam oracle as applicable.")]
    orientation = _check("orientation", "Orientation", procedure="Run the D2 closure/orientation validator before candidate construction and verify canonical face/corner maps for accepted input.")
    full_volume_na = _check("full_volume", "Full volume", reason="N/A in B2: D3/D4 volume semantics remain undecided and B2 is a row-qualification proof.")
    fd_force_na = _check("fd_force", "FD force", reason="N/A in B2: force kernels are WP4/WP6 work and integrated-functional acceptance is deferred to D9b.")
    entries = [
        _entry("u8_01_regular_closed", "U8-01", "Regular closed/periodic mesh", "regular_all6_torus", _fixture_input(torus), "regular_interior_l6_10", "none_regular", [
            *rows_checks,
            _check("geometry", "Geometry", procedure="Compare position/derivative rows plus the area and legacy-volume integrands with the analytic regular evaluator at every regular sample."),
            _check("all_force_families", "All force families", reason="N/A in B2: no production force kernel is authorized; force qualification belongs to WP4/WP6 and D9b."),
            _check("output", "Output", reason="N/A in B2: the proof has no production route or output/checkpoint schema authority."),
            _check("cache", "Cache", procedure="Run the frozen serial-cache numeric protocol and Bfr-only threading matrix; compare canonical row bytes."),
        ]),
        _entry("u8_02_tetrahedron", "U8-02", "Tetrahedron", "closed_valence3_tetrahedron", _fixture_input(tetra), "full_surface_plus_extraordinary_trend", "all_non6_corners", [*rows_checks, orientation, full_volume_na, fd_force_na]),
        _entry("u8_03_octahedron", "U8-03", "Octahedron", "closed_valence4_octahedron", _fixture_input(octa), "full_surface_plus_extraordinary_trend", "all_non6_corners", [*rows_checks, orientation, full_volume_na, fd_force_na]),
        _entry("u8_04_icosahedron", "U8-04", "Icosahedron", "closed_valence5", _fixture_input(icosa), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            *rows_checks, orientation, full_volume_na, fd_force_na,
            _check("legacy_rejection_compatibility", "Legacy rejection/compatibility", reason="N/A in B2: legacy Valence-5 quarantine/compatibility is governed by D5 and no route change is authorized."),
        ]),
        _entry("u8_05_symmetric_344", "U8-05", "Symmetric 3/4/4 bipyramid", "symmetric_344_bipyramid", _fixture_input(symmetric), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("convergence", "Convergence", procedure="Run each candidate's independent fixed approximation sweep and apply its internal row-stabilization criterion."),
            _check("row_invariants", "Row invariants", procedure="Apply position-sum-one and derivative-sum-zero at 1.0e-12 to every emitted row."),
            _check("cache", "Cache", procedure="Run serial-cache numeric and Bfr threading protocols with canonical byte equality."),
        ]),
        _entry("u8_06_asymmetric_344", "U8-06", "Asymmetric 3/4/4 bipyramid", "asymmetric_344_bipyramid", _fixture_input(asymmetric), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("per_source_axis_evidence", "Per-source/axis evidence", procedure="For every row, retain source-ID coefficients and all three geometry-applied Cartesian components in exact face/corner/sample order."),
        ]),
        _entry("u8_07_mixed_345", "U8-07", "Closed mixed 3/4/5", "closed_mixed_valence345", _fixture_input(mixed), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("one_full_mesh_provider", "One full-mesh provider", procedure="Construct each proof candidate from one complete full-mesh TopologyRefiner and require unambiguous original-source reconstruction."),
            _check("transaction", "Transaction", reason="N/A in B2: the production write transaction belongs to B3/WP3.2 and no production caller is authorized."),
        ]),
        _entry("u8_08_closed_566", "U8-08", "Intended 5/6/6 local patch in a closed mesh", "closed_566_refined_icosahedron", _fixture_input(refined), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("exact_classification", "Exact classification", procedure="Verify metadata-declared face row 0 is oriented [0,12,14] with valences [5,6,6] before candidate construction."),
            _check("generic_rows", "Generic rows", procedure="Evaluate all six rows on the complete selected face/sample workload without a per-valence route."),
        ]),
        _entry("u8_09_nonplatonic", "U8-09", "Non-Platonic closed triangulation", "b2p_shared_hull", _fixture_input(shared_hull), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("variable_cardinality", "Variable cardinality", procedure="Record and validate each face-union source count without a fixed-cardinality assumption."),
            _check("mixed_valences", "Mixed valences", procedure="Execute the complete mesh containing valences 3,4,5,7,8,9 and group oracle coverage by exact valence."),
        ]),
        _entry("u8_10_coordinate_perturbed", "U8-10", "Coordinate-perturbed variants", "asymmetric_344_binary64_perturbed", _mutation_input("coordinate_perturbation_v1", asymmetric, "asymmetric_344_binary64_perturbed"), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("finite_differences", "Finite differences", reason="N/A in B2: production energy/force finite differences belong to WP4/WP6 and D9b."),
            _check("convergence", "Convergence", procedure="Repeat the independent candidate approximation sweeps on the exact binary64-mutated coordinates."),
        ]),
        _entry("u8_11_reversed_winding", "U8-11", "Reversed/inconsistent winding", "invalid_reversed_face_zero", _mutation_input("reverse_face_zero_v1", torus, "invalid_reversed_face_zero"), "none_rejection", "none_rejection", [
            _check("atomic_rejection_or_sign", "Atomic rejection or defined sign behavior", procedure="D2 fixes rejection: reverse face row 0 and require fail-before-candidate with no partial row package."),
        ], numeric=False),
        _entry("u8_12_open_boundary", "U8-12", "Open boundary mesh", "invalid_deleted_face_zero", _mutation_input("delete_face_zero_v1", torus, "invalid_deleted_face_zero"), "none_rejection", "none_rejection", [
            _check("fail_before_mutation", "Fail-before-mutation diagnostic", procedure="Delete face row 0 and require the exact D2 open-boundary diagnostic before candidate construction or state mutation."),
        ], numeric=False),
        _entry("u8_13_duplicate_face", "U8-13", "Non-manifold/duplicate edge", "invalid_appended_face_zero", _mutation_input("append_face_zero_v1", torus, "invalid_appended_face_zero"), "none_rejection", "none_rejection", [
            _check("fail_before_mutation", "Fail-before-mutation diagnostic", procedure="Append face row 0 verbatim and require the exact duplicate/non-manifold diagnostic before candidate construction or state mutation."),
        ], numeric=False),
        _entry("u8_14_edge_flip_family", "U8-14", "Topology-mutated/edge-flipped mesh", "b2p_flip_family", _fixture_input(*flip_members), "full_surface_extraordinary_flip_locality", "all_non6_corners", [
            _check("epoch_miss_rebuild", "Epoch miss and rebuild", reason="N/A in B2: cache epoch invalidation is B4 and mutation ownership is WP9; B2 only measures frozen pairwise row locality."),
        ]),
        _entry("b7_01_single_flip_family", "B7-01", "Single-flip pair family", "b2p_flip_family", _fixture_input(*flip_members), "full_surface_extraordinary_flip_locality", "all_non6_corners", [
            _check("rows", "Rows", procedure="Evaluate all six rows for base and each variant in family-metadata order."),
            _check("source_coverage", "Source coverage", procedure="Validate original-source union coverage for every comparable unchanged face."),
            _check("error_oracle", "Error versus oracle", procedure="Apply D10 error bounds at every covered extraordinary trend sample; uncovered items remain uncovered."),
            _check("changed_face_count", "Changed-face count between pair members", procedure="Use the external B2p stable correspondence and ten-point locality manifest; report comparable, changed, and reusable counts separately."),
        ], alias_of="u8_14_edge_flip_family"),
        _entry("b7_02_valence789", "B7-02", "Closed mesh containing valence 7, 8, and 9 corners", "b2p_shared_hull", _fixture_input(shared_hull), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("rows", "Rows", procedure="Evaluate all six rows over the complete shared-hull workload."),
            _check("derivative_sum_rules", "Derivative sum rules", procedure="Require du,dv,duu,duv,dvv coefficient sums zero within 1.0e-12."),
            _check("error_oracle", "Error versus oracle", procedure="Apply D10 bounds only where the frozen isolation/eigenbasis contract establishes coverage."),
            _check("force_conjugacy", "Force conjugacy", reason="N/A in B2: force kernels and integrated-functional conjugacy belong to WP4/WP5 and D9b."),
        ], alias_of="u8_09_nonplatonic"),
        _entry("b7_03_adjacent_extraordinary", "B7-03", "Adjacent extraordinary corners sharing an edge", "b2p_adjacent_extraordinary", _fixture_input(adjacent), "full_surface_plus_extraordinary_trend", "all_non6_corners", [
            _check("rows", "Rows", procedure="Evaluate all six rows at every ordered full-surface/trend sample."),
            _check("oracle_error", "Oracle error", procedure="Report D10 error only for independently covered corners; adjacency never implies depth-zero coverage."),
            _check("quadrature_sensitivity", "Quadrature sensitivity", reason="N/A in B2: quadrature selection is WP5.1/WP5.2 and production activation is D9b."),
        ]),
    ]

    regular_samples = _regular_samples()
    trend_samples = _trend_samples()
    coordinate_components = [
        {"axis": "x", "delta_binary64_hex": "0x1.0000000000000p-8", "delta_bits_hex": "3f70000000000000", "input_binary64_hex": "0x1.2b851eb851eb8p+0", "input_bits_hex": "3ff2b851eb851eb8", "output_binary64_hex": "0x1.2c851eb851eb8p+0", "output_bits_hex": "3ff2c851eb851eb8"},
        {"axis": "y", "delta_binary64_hex": "-0x1.0000000000000p-9", "delta_bits_hex": "bf60000000000000", "input_binary64_hex": "-0x1.0cffc0ea99f27p-1", "input_bits_hex": "bfe0cffc0ea99f27", "output_binary64_hex": "-0x1.0dffc0ea99f27p-1", "output_bits_hex": "bfe0dffc0ea99f27"},
        {"axis": "z", "delta_binary64_hex": "0x1.0000000000000p-10", "delta_bits_hex": "3f50000000000000", "input_binary64_hex": "0x1.0a3d70a3d70a4p-3", "input_bits_hex": "3fc0a3d70a3d70a4", "output_binary64_hex": "0x1.0c3d70a3d70a4p-3", "output_bits_hex": "3fc0c3d70a3d70a4"},
    ]
    return {
        "aggregation_contract": {
            "alias_result_rule": "alias rows reuse the canonical execution bytes but run and report their own ordered source_matrix_checks; aliases never increase execution, fixture, sample, or mesh-evidence counts",
            "canonical_execution_case_order": [entry["execution_case_id"] for entry in entries if entry["alias_of"] is None],
            "case_result_identity": ["execution_case_id", "member_id", "candidate", "approximation_level", "applicable_mode"],
            "check_result_identity": ["source_matrix_row_id", "check_id"],
            "failure_rule": "one missing case/check/sample/row, nonfinite value, forbidden N/A substitution, or FAIL makes the owning criterion FAIL; no passing subset or alias can mask it",
            "row_result_identity": ["execution_case_id", "member_id", "face_row", "local_corner_or_none", "sample_id", "candidate", "approximation_level", "row_kind"],
            "unique_content_identity_order": ["regular_all6_torus", "closed_valence3_tetrahedron", "closed_valence4_octahedron", "closed_valence5", "symmetric_344_bipyramid", "asymmetric_344_bipyramid", "closed_mixed_valence345", "closed_566_refined_icosahedron", "b2p_shared_hull_base", "asymmetric_344_binary64_perturbed", "invalid_reversed_face_zero", "invalid_deleted_face_zero", "invalid_appended_face_zero", "b2p_flip_000", "b2p_flip_001", "b2p_flip_002", "b2p_adjacent_extraordinary"],
        },
        "alias_contracts": [
            {"alias_execution_case_id": "b7_01_single_flip_family", "canonical_execution_case_id": "u8_14_edge_flip_family", "must_equal_fields": ["input", "mesh_evidence_key", "face_policy", "corner_policy_ref", "sample_policy_ref", "row_order_ref", "candidates", "numeric_gate_applicability"], "permitted_differences": ["execution_case_id", "source_matrix_row_id", "source_matrix_row", "source_matrix_checks", "alias_of"]},
            {"alias_execution_case_id": "b7_02_valence789", "canonical_execution_case_id": "u8_09_nonplatonic", "must_equal_fields": ["input", "mesh_evidence_key", "face_policy", "corner_policy_ref", "sample_policy_ref", "row_order_ref", "candidates", "numeric_gate_applicability"], "permitted_differences": ["execution_case_id", "source_matrix_row_id", "source_matrix_row", "source_matrix_checks", "alias_of"]},
        ],
        "byte_identity_groups": [
            {"content_identity_key": "b2p_shared_hull_base", "count_once": True, "members": ["data/fixtures/candidates/b2p_valence789", "data/fixtures/candidates/b2p_single_flip_family/base"], "required_equal_files": ["faces.csv", "vertices.csv"]},
        ],
        "canonical_row_encoding": {
            "endianness": "little", "float": "IEEE-754 binary64 bits; negative zero preserved", "integer": "two's-complement signed int32 source/face IDs and unsigned uint32 counts", "magic_ascii": "B2ROWV1", "order": ["magic", "face_row", "sample_id_utf8_length_and_bytes", "row_kind_ordinal", "coefficient_count", "ascending_source_id_then_binary64_coefficient_bits"], "row_kind_ordinals": {"position": 0, "du": 1, "dv": 2, "duu": 3, "duv": 4, "dvv": 5}, "text": "UTF-8 without NUL; uint32 byte length prefix", "version": 1,
        },
        "corner_policies": [
            {"id": "none_regular", "selection": "none", "order": "none"},
            {"id": "all_non6_corners", "selection": "every selected face local corner whose base-mesh vertex valence != 6", "order": "ascending face_row then local_corner 0,1,2"},
            {"id": "none_rejection", "selection": "none because rejection must occur before candidate/sample construction", "order": "none"},
        ],
        "d9a_rollup": {
            "cache_disabled_concurrency": "mandatory PASS with fully instrumented TSan coverage",
            "decision_authority": "this manifest produces evidence status only and never infers or records D9a",
            "mandatory_numeric_and_rows": "every unique valid content identity must pass cache-disabled and serial SurfaceFactoryCache cost/RSS/payload/row criteria",
            "threaded_cache_tsan_unqualified": "B2/D9a evidence INCOMPLETE; no D9a proposal is permitted",
            "threaded_cache_unsupported_blocking": "threaded mode and any threaded-support claim are BLOCKED; if and only if every mandatory serial/cache-disabled criterion passes, evidence may support an explicitly serial-only D9a proposal subject to reviews and user decision",
        },
        "entries": entries,
        "mutation_rules": [
            {"base_member_path": asymmetric["path"], "components": coordinate_components, "id": "coordinate_perturbation_v1", "operation": "parse the checked-in decimal once to binary64; verify input bits; add the exact delta under FE_TONEAREST; verify output bits; replace vertex row 1 only", "rounding": "IEEE-754 roundTiesToEven (C/C++ FE_TONEAREST), verified before addition; fused or extended-precision arithmetic forbidden"},
            {"base_member_path": torus["path"], "id": "reverse_face_zero_v1", "operation": "replace face row 0 [a,b,c] with [a,c,b]"},
            {"base_member_path": torus["path"], "id": "delete_face_zero_v1", "operation": "delete face row 0 and preserve every remaining row in order"},
            {"base_member_path": torus["path"], "id": "append_face_zero_v1", "operation": "append an exact duplicate of face row 0 without changing prior rows"},
        ],
        "numeric_measurement_protocol": {
            "aggregation": "retain all 15 measured repeats; ordinary median is eighth sorted value; every repeat also obeys the single-run fail-stop",
            "applicable_modes": {"bfr": ["cache_disabled", "SurfaceFactoryCache_serial"], "far": ["not_applicable_uncached"]},
            "case_process_identity": ["candidate", "canonical_execution_case_id", "content_identity_key", "approximation_level", "applicable_mode"],
            "clock": {"api": "mach_continuous_time", "conversion_api": "mach_timebase_info", "unit": "integer nanoseconds with checked uint64 multiplication/division", "failure": "MEASUREMENT_PROTOCOL_FAILURE; B2 evidence incomplete and no numeric PASS"},
            "fresh_process_per_case": True,
            "levels": {"bfr_approxLevelSharp": 6, "bfr_approxLevelSmooth": [2, 3, 4, 5, 6, 7, 8], "far_isolationLevel": [2, 3, 4, 5, 6, 7, 8]},
            "release_build_only": True,
            "repeats": {"measured": 15, "warmup": 3},
            "rss_lifecycle": {"baseline": "once after fixture parsing and before the first refiner", "delta": "max(0, sample-baseline) for each named sample; gate on maximum across all samples in all 18 repeats; never reset or discard", "fresh_objects_each_repeat": ["full_mesh_TopologyRefiner", "candidate_factory_or_cache", "immutable_row_package"], "named_boundaries_per_repeat": ["after_refiner_construction", "after_factory_or_cache_construction", "after_each_completed_face_row_insertion", "after_immutable_package_publication", "after_row_package_destruction", "after_factory_or_cache_destruction", "after_refiner_destruction"], "rss_api": "task_info(mach_task_self(), MACH_TASK_BASIC_INFO, ...) resident_size", "sample_failure": "candidate case FAIL", "teardown": "destroy package, then factory/cache, then refiner before the next repeat"},
        },
        "qualification_platform": {
            "build": {
                "candidate_link_inputs": ["${OPENSUBDIV_ROOT}/lib/libosdCPU.a", "-framework", "IOKit", "-framework", "Foundation"],
                "candidate_proof_binary": "one Release binary containing both Bfr and Far candidates",
                "common_release_compile_flags": ["-std=c++17", "-O3", "-DNDEBUG", "-fno-fast-math", "-ffp-contract=off", "-fno-omit-frame-pointer", "-isysroot", "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk", "-mmacosx-version-min=26.0", "-Wall", "-Wextra", "-Wpedantic", "-Werror"],
                "compiler_path": "/Library/Developer/CommandLineTools/usr/bin/clang++",
                "compiler_version": "Apple clang version 21.0.0 (clang-2100.1.1.101)",
                "macos_sdk_path": "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk",
                "macos_sdk_version": "26.5",
                "mpfr": {"version": "4.2.2"},
                "mpfr_oracle_link_flags": ["-L${MPFR_ROOT}/lib", "-Wl,-rpath,${MPFR_ROOT}/lib", "-lmpfr", "-lgmp"],
                "opensubdiv": {"release_archive": "${OPENSUBDIV_ROOT}/lib/libosdCPU.a", "release_compile_flags": ["-std=c++17", "-O3", "-DNDEBUG", "-fno-fast-math", "-ffp-contract=off", "-fno-omit-frame-pointer", "-isysroot", "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk", "-mmacosx-version-min=26.0"], "tag_commit": "9dab8a47bfbb1388ec8388fe61f5f916e6123f38", "version": "3.7.0"},
                "oracle_separation": "the D10 MPFR oracle remains a separate executable and may not link OpenSubdiv",
                "thread_sanitizer_compile_flags": ["-std=c++17", "-O1", "-g", "-DNDEBUG", "-fno-fast-math", "-ffp-contract=off", "-fno-omit-frame-pointer", "-isysroot", "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk", "-mmacosx-version-min=26.0", "-fsanitize=thread"],
                "thread_sanitizer_link_inputs": ["-fsanitize=thread", "${OPENSUBDIV_TSAN_ROOT}/lib/libosdCPU.a", "-framework", "IOKit", "-framework", "Foundation"],
                "thread_sanitizer_opensubdiv_requirement": "rebuild every linked OpenSubdiv 3.7.0 translation unit from the pinned source with thread_sanitizer_compile_flags into the exact OPENSUBDIV_TSAN_ROOT static archive and link that instrumented archive only",
            },
            "fingerprint": {"architecture": "arm64", "chip": "Apple M5", "hw_logicalcpu": 10, "hw_memsize_bytes": 25769803776, "hw_model": "Mac17,2", "hw_ncpu": 10, "hw_perflevel0_logicalcpu": 4, "hw_perflevel0_physicalcpu": 4, "hw_perflevel1_logicalcpu": 6, "hw_perflevel1_physicalcpu": 6, "hw_physicalcpu": 10, "kern_hv_vmm_present": 0, "macos_build": "25F80", "macos_version": "26.5.1"},
            "git_identity": "local artifact records and exactly equals the reviewed B2 head SHA and has an empty worktree",
            "power": {"api": "IOPSCopyPowerSourcesInfo plus IOPSGetProvidingPowerSourceType", "required_value": "kIOPSACPowerValue"},
            "qualification_failure": "any fingerprint mismatch, API/query failure, non-AC value, virtualization/shared-host evidence, or non-nominal thermal state is UNQUALIFIED_PLATFORM; numeric gates neither pass nor fail and B2 evidence is incomplete; no repeat may be discarded or rerun selectively",
            "thermal": {"api": "NSProcessInfo.thermalState", "required_value": "NSProcessInfoThermalStateNominal", "sampling": "before and after every full case process"},
            "workflow_boundary": "GitHub-hosted macos-26 runs correctness, dependency provisioning, and independence audit only; it cannot satisfy D12 numeric platform gates. Qualified numeric evidence is an exact-head local artifact from this physical fingerprint and receives independent technical and scientific review.",
        },
        "row_order": {"id": "six_source_rows_v1", "rows": ["position", "du", "dv", "duu", "duv", "dvv"]},
        "sample_field_contract": {
            "binary64_rounding": "IEEE-754 roundTiesToEven (C/C++ FE_TONEAREST), verified before conversion",
            "extraordinary_corner_maps": [
                {"barycentric": ["1-xi-eta", "xi", "eta"], "local_corner": 0, "u": "xi", "v": "eta"},
                {"barycentric": ["eta", "1-xi-eta", "xi"], "local_corner": 1, "u": "1-xi-eta", "v": "xi"},
                {"barycentric": ["xi", "eta", "1-xi-eta"], "local_corner": 2, "u": "eta", "v": "1-xi-eta"},
            ],
            "regular_coordinates": "u=u_numerator/6 and v=v_numerator/6, each converted once from the exact rational",
            "retained_fields": ["u_binary64", "v_binary64", "weight_binary64"],
            "trend_coordinates": "xi and eta are exact dyadic rationals; apply extraordinary_corner_maps before binary64 conversion",
            "weight": {"binary64_hex": "0x0.0p+0", "bits_hex": "0000000000000000", "meaning": "proof-only placeholder; not quadrature"},
        },
        "sample_policies": [
            {"count_formula": "S=10 for every selected face", "external_identity_reference": "data/fixtures/candidates/b2p_single_flip_family/family_metadata.json#locality_sample_manifest.samples", "id": "regular_interior_l6_10", "kind": "rational_face_interior", "lattice_denominator": 6, "order": "increasing i+j from 2 through 5, then increasing i; j=(i+j)-i", "samples": regular_samples},
            {"corner_policy_ref": "all_non6_corners", "count_formula": "S=24*K where K is the exact number of selected non-valence-6 corners on that face", "formula": "for radius r=2^-e and ordered ray (a,b), (xi,eta)=r*(a,b)", "id": "extraordinary_trend_24_per_corner", "kind": "extraordinary_corner_trend", "order": "ascending face_row, local_corner, radius_exponent 1..8, ray_index 0..2", "rays": ["(1/4,3/4)", "(1/2,1/2)", "(3/4,1/4)"], "samples": trend_samples},
            {"components": ["regular_interior_l6_10", "extraordinary_trend_24_per_corner"], "count_formula": "S=10+24*K for each selected face; component order is listed and duplicate sample IDs are forbidden", "id": "full_surface_plus_extraordinary_trend", "kind": "ordered_composite"},
            {"components": ["regular_interior_l6_10", "extraordinary_trend_24_per_corner"], "count_formula": "S=10+24*K; the ten regular samples are exactly the external flip-locality samples and are not duplicated", "flip_locality_reference": "data/fixtures/candidates/b2p_single_flip_family/family_metadata.json#locality_sample_manifest", "id": "full_surface_extraordinary_flip_locality", "kind": "ordered_composite"},
            {"count_formula": "S=0", "id": "none_rejection", "kind": "none", "reason": "D2 rejection occurs before face/corner/sample/candidate construction"},
        ],
        "schema_version": 2,
        "status": "pending_D12",
        "threading_protocol": {
            "candidate": "bfr", "case_selection": "every non-alias entry with threading_bfr_only=true, expanded in entry/member order and deduplicated by content_identity_key", "levels_approxLevelSmooth": [2, 3, 4, 5, 6, 7, 8], "modes": ["cache_disabled", "SurfaceFactoryCacheThreaded"], "process_identity": ["content_identity_key", "approxLevelSmooth", "mode", "worker_count"], "rounds": 20, "shared_state_per_process": ["one immutable full-mesh Far::TopologyRefiner", "one shared Bfr::RefinerSurfaceFactory", "for SurfaceFactoryCacheThreaded mode one shared SurfaceFactoryCacheThreaded"], "synchronization": "one start barrier per round; every worker simultaneously requests the same complete ordered face/sample workload", "teardown": "compare canonical bytes, then destroy each per-worker result after that round; shared refiner/factory/cache persists through all 20 rounds", "tsan": "both B2 proof translation units and every linked OpenSubdiv 3.7.0 translation unit use -fsanitize=thread; zero findings required", "workers": [1, 2, 4], "workload_order": "entry member order, ascending face row, sample-policy order, six_source_rows_v1 order, ascending source ID", "row_comparison": "exact canonical_row_encoding byte identity across all workers and rounds; missing output or mismatch is blocking",
        },
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
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--output-root", type=Path)
    output.add_argument("--manifest-only", type=Path)
    arguments = parser.parse_args()
    if arguments.manifest_only is not None:
        _write(arguments.manifest_only, _json(execution_manifest()))
        return 0
    assert arguments.output_root is not None
    if arguments.output_root.exists() and any(arguments.output_root.iterdir()):
        parser.error("output root must be absent or empty")
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    generate(arguments.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
