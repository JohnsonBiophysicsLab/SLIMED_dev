"""Focused topology, correspondence, and reproduction checks for B2p."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "scripts/generate_b2p_loop_fixtures.py"
SPEC = importlib.util.spec_from_file_location("b2p_fixture_generator", GENERATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)

FIXTURE_ROOTS = (
    Path("data/fixtures/candidates/b2p_single_flip_family"),
    Path("data/fixtures/candidates/b2p_valence789"),
    Path("data/fixtures/candidates/b2p_adjacent_extraordinary"),
)


def read_faces(path: Path) -> list[tuple[int, int, int]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return [tuple(int(value) for value in row) for row in csv.reader(stream)]


def read_vertices(path: Path) -> list[tuple[float, float, float]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return [tuple(float(value) for value in row) for row in csv.reader(stream)]


def validate_topology(vertices: list[tuple[float, float, float]],
                      faces: list[tuple[int, int, int]]) -> dict[str, object]:
    vertex_count = len(vertices)
    used: set[int] = set()
    canonical_faces: set[tuple[int, int, int]] = set()
    edges: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    links: list[dict[int, set[int]]] = [defaultdict(set) for _ in vertices]

    for face in faces:
        if len(face) != 3 or len(set(face)) != 3:
            raise AssertionError(f"not a triangle with distinct corners: {face}")
        if min(face) < 0 or max(face) >= vertex_count:
            raise AssertionError(f"triangle index out of range: {face}")
        canonical = tuple(sorted(face))
        if canonical in canonical_faces:
            raise AssertionError(f"duplicate face: {face}")
        canonical_faces.add(canonical)
        used.update(face)
        for index in range(3):
            u, v = face[index], face[(index + 1) % 3]
            edges[tuple(sorted((u, v)))].append((u, v))
        a, b, c = face
        for center, left, right in ((a, b, c), (b, c, a), (c, a, b)):
            links[center][left].add(right)
            links[center][right].add(left)

    if used != set(range(vertex_count)):
        raise AssertionError("not every vertex is used")
    for edge, directions in edges.items():
        if len(directions) != 2:
            raise AssertionError(f"edge {edge} does not have exactly two faces")
        if directions[0] != directions[1][::-1]:
            raise AssertionError(f"edge {edge} directions are not opposite")

    valences: list[int] = []
    for vertex, link in enumerate(links):
        if any(len(opposites) != 2 for opposites in link.values()):
            raise AssertionError(f"vertex {vertex} link is not degree two")
        start = min(link)
        reached = {start}
        pending = deque([start])
        while pending:
            current = pending.popleft()
            for neighbor in link[current]:
                if neighbor not in reached:
                    reached.add(neighbor)
                    pending.append(neighbor)
        if reached != set(link):
            raise AssertionError(f"vertex {vertex} link is disconnected")
        valences.append(len(link))

    return {
        "edge_count": len(edges),
        "face_count": len(faces),
        "valence_by_vertex": valences,
        "vertex_count": vertex_count,
    }


def member_directories() -> list[Path]:
    family = ROOT / FIXTURE_ROOTS[0]
    return [family / "base", family / "flip_000", family / "flip_001",
            family / "flip_002", ROOT / FIXTURE_ROOTS[1], ROOT / FIXTURE_ROOTS[2]]


def vector_subtract(left, right):
    return tuple(a - b for a, b in zip(left, right))


def vector_cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def vector_dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def triangles_intersect(left, right):
    left_edges = [vector_subtract(left[(index + 1) % 3], left[index])
                  for index in range(3)]
    right_edges = [vector_subtract(right[(index + 1) % 3], right[index])
                   for index in range(3)]
    left_normal = vector_cross(left_edges[0], left_edges[1])
    right_normal = vector_cross(right_edges[0], right_edges[1])
    axes = [left_normal, right_normal]
    axes.extend(vector_cross(a, b) for a in left_edges for b in right_edges)
    # These in-plane edge normals make the same SAT test cover coplanar pairs.
    axes.extend(vector_cross(left_normal, edge) for edge in left_edges)
    axes.extend(vector_cross(right_normal, edge) for edge in right_edges)
    for axis in axes:
        if vector_dot(axis, axis) <= 1.0e-28:
            continue
        left_projection = [vector_dot(axis, vertex) for vertex in left]
        right_projection = [vector_dot(axis, vertex) for vertex in right]
        scale = max(1.0, *(abs(value) for value in left_projection + right_projection))
        epsilon = 1.0e-12 * scale
        if max(left_projection) < min(right_projection) - epsilon or \
                max(right_projection) < min(left_projection) - epsilon:
            return False
    return True


def mesh_adjacency(vertices, faces):
    adjacency = [set() for _ in vertices]
    for face in faces:
        for index in range(3):
            left, right = face[index], face[(index + 1) % 3]
            adjacency[left].add(right)
            adjacency[right].add(left)
    return adjacency


def neighborhood_signature(vertices, faces, edge, radius):
    adjacency = mesh_adjacency(vertices, faces)
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
    records = []
    for shell in range(radius + 1):
        shell_records = []
        for vertex in sorted(item for item, distance in distances.items()
                             if distance == shell):
            counts = [sum(distances.get(neighbor) == target
                          for neighbor in adjacency[vertex])
                      for target in range(radius + 1)]
            outside = sum(neighbor not in distances for neighbor in adjacency[vertex])
            shell_records.append([len(adjacency[vertex]), *counts, outside])
        records.append({"distance": shell, "records": sorted(shell_records)})
    edge_counts = {(left, right): 0 for left in range(radius + 1)
                   for right in range(left, radius + 1)}
    for left, neighbors in enumerate(adjacency):
        for right in neighbors:
            if left < right and left in distances and right in distances:
                pair = tuple(sorted((distances[left], distances[right])))
                edge_counts[pair] += 1
    opposites = []
    for face in faces:
        if edge[0] in face and edge[1] in face:
            opposites.append(next(vertex for vertex in face if vertex not in edge))
    return {
        "edge_shell_counts": [
            {"count": edge_counts[pair], "shells": list(pair)}
            for pair in sorted(edge_counts)
        ],
        "endpoint_valences": sorted(len(adjacency[vertex]) for vertex in edge),
        "opposite_valences": sorted(len(adjacency[vertex]) for vertex in opposites),
        "radius": radius,
        "shell_vertex_records": records,
    }


def select_flip_edges(vertices, faces):
    adjacency = mesh_adjacency(vertices, faces)
    incidence = defaultdict(list)
    for face in faces:
        for index in range(3):
            edge = tuple(sorted((face[index], face[(index + 1) % 3])))
            incidence[edge].append(face[(index + 2) % 3])
    accepted = []
    endpoint_pairs = set()
    signatures = {1: set(), 2: set()}
    for edge in sorted(incidence):
        opposites = incidence[edge]
        if len(opposites) != 2 or tuple(sorted(opposites)) in incidence:
            continue
        endpoint_pair = tuple(sorted(len(adjacency[vertex]) for vertex in edge))
        candidates = {
            radius: json.dumps(
                neighborhood_signature(vertices, faces, edge, radius),
                sort_keys=True, separators=(",", ":"))
            for radius in (1, 2)
        }
        if set(edge).intersection(vertex for prior in accepted for vertex in prior):
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
    raise AssertionError("independent selection found fewer than three flips")


class B2pLoopFixturesTest(unittest.TestCase):
    def test_A_all_members_are_closed_oriented_two_manifolds(self) -> None:
        for member in member_directories():
            with self.subTest(member=member.relative_to(ROOT)):
                vertices = read_vertices(member / "vertices.csv")
                faces = read_faces(member / "faces.csv")
                observed = validate_topology(vertices, faces)
                metadata = json.loads((member / "candidate_metadata.json").read_text())
                topology = metadata["topology"]
                self.assertEqual(observed["vertex_count"], topology["vertex_count"])
                self.assertEqual(observed["edge_count"], topology["edge_count"])
                self.assertEqual(observed["face_count"], topology["face_count"])
                self.assertEqual(observed["valence_by_vertex"],
                                 topology["valence_by_vertex"])
                self.assertTrue(topology["all_vertices_referenced"])
                self.assertTrue(topology["closed_two_face_edge_manifold"])
                self.assertTrue(topology["opposite_edge_orientation"])
                self.assertTrue(topology["connected_degree2_vertex_links"])
                self.assertTrue(topology["duplicate_faces_absent"])
                self.assertEqual(metadata["generator"]["id"],
                                 "scripts/generate_b2p_loop_fixtures.py")
                self.assertEqual(metadata["generator"]["version"], 2)
                self.assertTrue(metadata["proof_only"])
                self.assertFalse(metadata["scientifically_approved"])

    def test_B_each_flip_is_legal_and_rewrites_exactly_two_faces(self) -> None:
        family_root = ROOT / FIXTURE_ROOTS[0]
        base_faces = read_faces(family_root / "base/faces.csv")
        family = json.loads((family_root / "family_metadata.json").read_text())
        self.assertEqual(len(family["variants"]), 3)
        self.assertEqual(family["comparison_contract"]["row_changed_tolerance"],
                         1.0e-12)

        base_edges = {
            tuple(sorted((face[index], face[(index + 1) % 3])))
            for face in base_faces for index in range(3)
        }
        for correspondence in family["variants"]:
            member_name = correspondence["member"]
            member_root = family_root / member_name
            member_faces = read_faces(member_root / "faces.csv")
            differing = [index for index, pair in enumerate(zip(base_faces, member_faces))
                         if pair[0] != pair[1]]
            rewritten = correspondence["rewritten"]
            self.assertEqual(differing, rewritten["rewritten_base_rows"])
            self.assertEqual(len(differing), 2)

            old_edge = tuple(rewritten["old_edge"])
            new_edge = tuple(rewritten["new_edge"])
            self.assertIn(old_edge, base_edges)
            self.assertNotIn(new_edge, base_edges)
            member_edges = {
                tuple(sorted((face[index], face[(index + 1) % 3])))
                for face in member_faces for index in range(3)
            }
            self.assertNotIn(old_edge, member_edges)
            self.assertIn(new_edge, member_edges)

            metadata = json.loads(
                (member_root / "candidate_metadata.json").read_text())
            self.assertEqual(metadata["family"]["correspondence"], correspondence)
            unchanged = correspondence["unchanged"]
            self.assertEqual(len(unchanged), len(base_faces) - 2)
            self.assertEqual(correspondence["comparable_face_ids"],
                             [item["face_id"] for item in unchanged])
            for item in unchanged:
                row = item["base_row"]
                self.assertEqual(row, item["member_row"])
                self.assertEqual(base_faces[row], member_faces[row])
                self.assertEqual(list(base_faces[row]), item["oriented_vertices"])
            self.assertTrue(all("rewritten" in face_id
                                for face_id in rewritten["member_face_ids"]))

    def test_C_declared_valence_7_8_9_vertices_are_exact(self) -> None:
        member = ROOT / FIXTURE_ROOTS[1]
        metadata = json.loads((member / "candidate_metadata.json").read_text())
        validation = validate_topology(
            read_vertices(member / "vertices.csv"), read_faces(member / "faces.csv"))
        valences = validation["valence_by_vertex"]
        for expected_text, vertex in metadata["declared_valence_vertices"].items():
            self.assertEqual(valences[vertex], int(expected_text))
        self.assertTrue({7, 8, 9}.issubset(set(valences)))
        self.assertEqual(metadata["topology"]["contains_valences"], [7, 8, 9])

    def test_C2_valence789_geometry_is_finite_embedded_and_well_shaped(self) -> None:
        member = ROOT / FIXTURE_ROOTS[1]
        vertices = read_vertices(member / "vertices.csv")
        faces = read_faces(member / "faces.csv")
        metadata = json.loads((member / "candidate_metadata.json").read_text())
        qualities = []
        triangles = [tuple(vertices[index] for index in face) for face in faces]
        for vertex in vertices:
            self.assertTrue(all(math.isfinite(value) for value in vertex))
        for triangle in triangles:
            edges = [vector_subtract(triangle[(index + 1) % 3], triangle[index])
                     for index in range(3)]
            cross = vector_cross(edges[0], vector_subtract(triangle[2], triangle[0]))
            doubled_area = math.sqrt(vector_dot(cross, cross))
            self.assertGreater(doubled_area, 0.0)
            qualities.append(
                2.0 * math.sqrt(3.0) * doubled_area
                / sum(vector_dot(edge, edge) for edge in edges))
        intersection_count = 0
        for left_index, left_face in enumerate(faces):
            for right_index in range(left_index + 1, len(faces)):
                if set(left_face).isdisjoint(faces[right_index]):
                    intersection_count += triangles_intersect(
                        triangles[left_index], triangles[right_index])
        self.assertEqual(intersection_count, 0)
        self.assertGreaterEqual(min(qualities), 0.24)
        geometry = metadata["geometry"]
        self.assertEqual(geometry["nonadjacent_triangle_intersection_count"], 0)
        self.assertAlmostEqual(geometry["minimum_triangle_quality"], min(qualities))
        self.assertEqual(geometry["minimum_triangle_quality_bound"], 0.24)

    def test_C3_flip_neighborhood_signatures_are_recomputed_and_diverse(self) -> None:
        family_root = ROOT / FIXTURE_ROOTS[0]
        vertices = read_vertices(family_root / "base/vertices.csv")
        faces = read_faces(family_root / "base/faces.csv")
        family = json.loads((family_root / "family_metadata.json").read_text())
        selected = [tuple(edge) for edge in family["selected_flip_edges"]]
        self.assertEqual(selected, [(0, 2), (3, 4), (6, 8)])
        self.assertEqual(selected, select_flip_edges(vertices, faces))
        self.assertEqual(len(set().union(*(set(edge) for edge in selected))), 6)
        endpoint_pairs = []
        observed = {1: set(), 2: set()}
        for edge, variant in zip(selected, family["variants"]):
            self.assertEqual(tuple(variant["rewritten"]["old_edge"]), edge)
            for radius in (1, 2):
                expected = neighborhood_signature(vertices, faces, edge, radius)
                self.assertEqual(
                    variant["neighborhood_signatures"][f"radius_{radius}"], expected)
                observed[radius].add(json.dumps(expected, sort_keys=True))
            endpoint_pairs.append(tuple(
                variant["neighborhood_signatures"]["radius_1"]["endpoint_valences"]))
        self.assertEqual(len(set(endpoint_pairs)), 3)
        self.assertEqual(len(observed[1]), 3)
        self.assertEqual(len(observed[2]), 3)

    def test_C4_locality_sample_manifest_is_exact_complete_and_ordered(self) -> None:
        family = json.loads(
            (ROOT / FIXTURE_ROOTS[0] / "family_metadata.json").read_text())
        manifest = family["locality_sample_manifest"]
        self.assertEqual(manifest["lattice_denominator"], 6)
        self.assertEqual(
            manifest["row_order"],
            ["position", "du", "dv", "duu", "duv", "dvv"])
        expected = []
        for total in range(2, 6):
            for i in range(1, total):
                j = total - i
                expected.append({
                    "barycentric_numerators": [6 - i - j, i, j],
                    "id": f"tri-l6-s{total:02d}-u{i:02d}-v{j:02d}",
                    "u_numerator": i,
                    "v_numerator": j,
                })
        self.assertEqual(manifest["samples"], expected)
        self.assertEqual(len(expected), 10)
        self.assertEqual(len({sample["id"] for sample in expected}), 10)
        self.assertEqual(
            len({(sample["u_numerator"], sample["v_numerator"])
                 for sample in expected}), 10)
        for sample in expected:
            self.assertEqual(sum(sample["barycentric_numerators"]), 6)
            self.assertTrue(all(value > 0
                                for value in sample["barycentric_numerators"]))

    def test_C5_shared_hull_identity_and_coverage_risk_are_explicit(self) -> None:
        family_base = ROOT / FIXTURE_ROOTS[0] / "base"
        valence789 = ROOT / FIXTURE_ROOTS[1]
        for filename in ("vertices.csv", "faces.csv"):
            with self.subTest(filename=filename):
                self.assertEqual(
                    (family_base / filename).read_bytes(),
                    (valence789 / filename).read_bytes())

        topology = validate_topology(
            read_vertices(family_base / "vertices.csv"),
            read_faces(family_base / "faces.csv"))
        self.assertEqual(
            sorted(topology["valence_by_vertex"]),
            [3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 7, 8, 9])
        self.assertNotIn(6, topology["valence_by_vertex"])

        plan = (ROOT / "docs/bfr_loop_backend_plan_macos.md").read_text()
        self.assertIn(
            "must not count the two directory names as independent mesh-level",
            plan)
        self.assertIn(
            "frozen negative-evidence risk to accept explicitly with D10",
            plan)

    def test_D_adjacent_extraordinary_vertices_share_declared_edge(self) -> None:
        member = ROOT / FIXTURE_ROOTS[2]
        metadata = json.loads((member / "candidate_metadata.json").read_text())
        faces = read_faces(member / "faces.csv")
        validation = validate_topology(read_vertices(member / "vertices.csv"), faces)
        declaration = metadata["adjacent_extraordinary"]
        u, v = declaration["shared_edge"]
        self.assertEqual(declaration["vertices"], [u, v])
        self.assertEqual([validation["valence_by_vertex"][u],
                          validation["valence_by_vertex"][v]], [5, 5])
        incidence = sum(
            tuple(sorted((face[index], face[(index + 1) % 3]))) == tuple(sorted((u, v)))
            for face in faces for index in range(3)
        )
        self.assertEqual(incidence, 2)

    def test_E_generator_reproduces_every_checked_in_byte(self) -> None:
        with tempfile.TemporaryDirectory(prefix="slimed-b2p-fixtures-") as temporary:
            generated_root = Path(temporary)
            GENERATOR.generate(generated_root)
            checked_files = sorted(
                path for relative in FIXTURE_ROOTS
                for path in (ROOT / relative).rglob("*") if path.is_file()
            )
            generated_files = sorted(
                path for relative in FIXTURE_ROOTS
                for path in (generated_root / relative).rglob("*") if path.is_file()
            )
            self.assertEqual(
                [path.relative_to(ROOT) for path in checked_files],
                [path.relative_to(generated_root) for path in generated_files],
            )
            for checked, generated in zip(checked_files, generated_files):
                with self.subTest(path=checked.relative_to(ROOT)):
                    self.assertEqual(checked.read_bytes(), generated.read_bytes())
                    self.assertEqual(hashlib.sha256(checked.read_bytes()).digest(),
                                     hashlib.sha256(generated.read_bytes()).digest())

    def test_F_generator_refuses_to_overwrite_checked_in_tree(self) -> None:
        with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
            GENERATOR.generate(ROOT)


if __name__ == "__main__":
    unittest.main()
