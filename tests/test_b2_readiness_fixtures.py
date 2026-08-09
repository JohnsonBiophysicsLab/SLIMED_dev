"""Independent validation of the pending D12 B2-readiness corpus."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "data/fixtures/candidates/b2_readiness_v1"
GENERATOR = ROOT / "scripts/generate_b2_readiness_fixtures.py"
MEMBERS = [
    "asymmetric_344_bipyramid",
    "closed_566_refined_icosahedron",
    "regular_all6_torus",
    "symmetric_344_bipyramid",
]
EXPECTED_HASHES = {
    "asymmetric_344_bipyramid/candidate_metadata.json": "e92b244806eaecd9230a3f3f9977f61ddeff3875ee6550c2dfbdb211a8e05e04",
    "asymmetric_344_bipyramid/faces.csv": "c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486",
    "asymmetric_344_bipyramid/vertices.csv": "b275aac1d1b422a131c3703eb7f56fd4d5bf21230b277835774bc27405d10a4e",
    "closed_566_refined_icosahedron/candidate_metadata.json": "f974fb5bb1d542561672c1e7d2d52bf5220acc09dd3b5510dc14f1d98343b0b5",
    "closed_566_refined_icosahedron/faces.csv": "d72e02a882c536643e8a3405efe8bb32c745bc034cbc55dcc1af0d5eba11e1b8",
    "closed_566_refined_icosahedron/vertices.csv": "cb6c618c254b36bbe27ff354f5dc009222e95277188833a3385a4f3c378b0bd6",
    "execution_manifest.json": "f043c51e3274b0b2bb998dadb11357d1e1f091c5f0109506921a212456bbf837",
    "regular_all6_torus/candidate_metadata.json": "11aba5339fced78cab1056b99d03766ecf3b0a7178e1c04c5376f1af01f2cf1c",
    "regular_all6_torus/faces.csv": "7797a1ded38d99e83707fb85e23a2a193c5857f7425a5f678ceccb1506c67cd0",
    "regular_all6_torus/vertices.csv": "923914e925eaf0f60eb9a087f0150ad37b9e56bf0191ffc52b5d7fbd91b2903c",
    "symmetric_344_bipyramid/candidate_metadata.json": "6afd2ec0c0df1cd71a8597fa78889dbf9daea9627d10b97165acec1cd39f9cb0",
    "symmetric_344_bipyramid/faces.csv": "c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486",
    "symmetric_344_bipyramid/vertices.csv": "bbce1680eb4006622e14dd5d724134df826471bb55e0332c19a208b5e92429a5",
}
EXPECTED_ROW_IDS = [f"U8-{index:02d}" for index in range(1, 15)] + [
    "B7-01", "B7-02", "B7-03"]
EXPECTED_FIXTURE_ROOTS = {
    "b2_readiness_v1": "data/fixtures/candidates/b2_readiness_v1",
    "b2p_adjacent_extraordinary":
        "data/fixtures/candidates/b2p_adjacent_extraordinary",
    "b2p_single_flip_family":
        "data/fixtures/candidates/b2p_single_flip_family",
    "b2p_valence789": "data/fixtures/candidates/b2p_valence789",
    "closed_mixed_valence345":
        "data/fixtures/candidates/closed_mixed_valence345",
    "closed_valence3_tetrahedron":
        "data/fixtures/candidates/closed_valence3_tetrahedron",
    "closed_valence4_octahedron":
        "data/fixtures/candidates/closed_valence4_octahedron",
    "closed_valence5": "data/fixtures/closed_valence5",
}


def read_vertices(path: Path) -> list[tuple[float, float, float]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [tuple(float(value) for value in row) for row in csv.reader(stream)]
    if any(len(row) != 3 or any(not math.isfinite(value) for value in row)
           for row in rows):
        raise AssertionError("invalid vertex row")
    return rows  # type: ignore[return-value]


def read_faces(path: Path) -> list[tuple[int, int, int]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [tuple(int(value) for value in row) for row in csv.reader(stream)]
    if any(len(row) != 3 for row in rows):
        raise AssertionError("invalid face row")
    return rows  # type: ignore[return-value]


def validate_topology(vertices, faces) -> list[int]:
    face_keys = set()
    incidence = defaultdict(list)
    links = [defaultdict(set) for _ in vertices]
    used = set()
    for face in faces:
        if len(set(face)) != 3 or min(face) < 0 or max(face) >= len(vertices):
            raise AssertionError("invalid face")
        key = tuple(sorted(face))
        if key in face_keys:
            raise AssertionError("duplicate face")
        face_keys.add(key)
        used.update(face)
        a, b, c = face
        for u, v in ((a, b), (b, c), (c, a)):
            incidence[tuple(sorted((u, v)))].append((u, v))
        for center, left, right in ((a, b, c), (b, c, a), (c, a, b)):
            links[center][left].add(right)
            links[center][right].add(left)
    if used != set(range(len(vertices))):
        raise AssertionError("unreferenced vertex")
    if any(len(items) != 2 or items[0] != items[1][::-1]
           for items in incidence.values()):
        raise AssertionError("not closed and consistently oriented")
    for link in links:
        if any(len(items) != 2 for items in link.values()):
            raise AssertionError("link is not a cycle")
        reached = {min(link)}
        queue = deque(reached)
        while queue:
            for neighbor in link[queue.popleft()]:
                if neighbor not in reached:
                    reached.add(neighbor)
                    queue.append(neighbor)
        if reached != set(link):
            raise AssertionError("link is disconnected")
    reached_vertices = {0}
    queue = deque(reached_vertices)
    while queue:
        for neighbor in links[queue.popleft()]:
            if neighbor not in reached_vertices:
                reached_vertices.add(neighbor)
                queue.append(neighbor)
    if reached_vertices != set(range(len(vertices))):
        raise AssertionError("surface is disconnected")
    return [len(link) for link in links]


def triangle_quality(vertices, face) -> float:
    points = [vertices[index] for index in face]
    edges = [tuple(points[(i + 1) % 3][axis] - points[i][axis]
                   for axis in range(3)) for i in range(3)]
    cross = (edges[0][1] * (-edges[2][2]) - edges[0][2] * (-edges[2][1]),
             edges[0][2] * (-edges[2][0]) - edges[0][0] * (-edges[2][2]),
             edges[0][0] * (-edges[2][1]) - edges[0][1] * (-edges[2][0]))
    doubled_area = math.sqrt(math.fsum(value * value for value in cross))
    denominator = math.fsum(math.fsum(value * value for value in edge)
                            for edge in edges)
    return 2.0 * math.sqrt(3.0) * doubled_area / denominator


def _sub3(left, right):
    return tuple(left[index] - right[index] for index in range(3))


def _dot3(left, right):
    return math.fsum(left[index] * right[index] for index in range(3))


def _cross3(left, right):
    return (left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0])


def _segment_triangle_intersects(start, end, triangle, epsilon=1.0e-10):
    direction = _sub3(end, start)
    edge1 = _sub3(triangle[1], triangle[0])
    edge2 = _sub3(triangle[2], triangle[0])
    pvec = _cross3(direction, edge2)
    determinant = _dot3(edge1, pvec)
    if abs(determinant) <= epsilon:
        return False
    inverse = 1.0 / determinant
    tvec = _sub3(start, triangle[0])
    u = _dot3(tvec, pvec) * inverse
    qvec = _cross3(tvec, edge1)
    v = _dot3(direction, qvec) * inverse
    distance = _dot3(edge2, qvec) * inverse
    return (-epsilon <= u <= 1.0 + epsilon and -epsilon <= v and
            u + v <= 1.0 + epsilon and
            -epsilon <= distance <= 1.0 + epsilon)


def _coplanar_triangles_intersect(left, right, normal, epsilon=1.0e-10):
    dropped = max(range(3), key=lambda index: abs(normal[index]))
    axes = [index for index in range(3) if index != dropped]
    left2 = [tuple(point[index] for index in axes) for point in left]
    right2 = [tuple(point[index] for index in axes) for point in right]

    def orient(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1]) -
                (b[1] - a[1]) * (c[0] - a[0]))

    def on_segment(a, b, point):
        return (min(a[0], b[0]) - epsilon <= point[0] <=
                max(a[0], b[0]) + epsilon and
                min(a[1], b[1]) - epsilon <= point[1] <=
                max(a[1], b[1]) + epsilon and
                abs(orient(a, b, point)) <= epsilon)

    def segments_intersect(a, b, c, d):
        values = (orient(a, b, c), orient(a, b, d),
                  orient(c, d, a), orient(c, d, b))
        if ((values[0] > epsilon and values[1] < -epsilon or
             values[0] < -epsilon and values[1] > epsilon) and
            (values[2] > epsilon and values[3] < -epsilon or
             values[2] < -epsilon and values[3] > epsilon)):
            return True
        return (on_segment(a, b, c) or on_segment(a, b, d) or
                on_segment(c, d, a) or on_segment(c, d, b))

    def contains(triangle, point):
        signs = [orient(triangle[index], triangle[(index + 1) % 3], point)
                 for index in range(3)]
        return (all(value >= -epsilon for value in signs) or
                all(value <= epsilon for value in signs))

    if any(segments_intersect(left2[i], left2[(i + 1) % 3],
                              right2[j], right2[(j + 1) % 3])
           for i in range(3) for j in range(3)):
        return True
    return contains(left2, right2[0]) or contains(right2, left2[0])


def triangles_intersect(left, right, epsilon=1.0e-10):
    left_normal = _cross3(_sub3(left[1], left[0]), _sub3(left[2], left[0]))
    right_normal = _cross3(_sub3(right[1], right[0]), _sub3(right[2], right[0]))
    left_distances = [_dot3(left_normal, _sub3(point, left[0]))
                      for point in right]
    right_distances = [_dot3(right_normal, _sub3(point, right[0]))
                       for point in left]
    if (all(value > epsilon for value in left_distances) or
        all(value < -epsilon for value in left_distances) or
        all(value > epsilon for value in right_distances) or
        all(value < -epsilon for value in right_distances)):
        return False
    normal_cross = _cross3(left_normal, right_normal)
    if _dot3(normal_cross, normal_cross) <= epsilon * epsilon:
        if max(abs(value) for value in left_distances) > epsilon:
            return False
        return _coplanar_triangles_intersect(
            left, right, left_normal, epsilon)
    return any(
        _segment_triangle_intersects(
            triangle[index], triangle[(index + 1) % 3], other, epsilon)
        for triangle, other in ((left, right), (right, left))
        for index in range(3))


class B2ReadinessFixturesTest(unittest.TestCase):
    def test_A_all_members_are_closed_oriented_connected_two_manifolds(self) -> None:
        for member in MEMBERS:
            with self.subTest(member=member):
                root = FIXTURE_ROOT / member
                vertices = read_vertices(root / "vertices.csv")
                faces = read_faces(root / "faces.csv")
                valences = validate_topology(vertices, faces)
                metadata = json.loads((root / "candidate_metadata.json").read_text())
                self.assertEqual(valences, metadata["topology"]["valence_by_vertex"])
                self.assertTrue(metadata["topology"]["closed_two_face_edge_manifold"])
                self.assertTrue(metadata["topology"]["connected_surface"])
                self.assertTrue(metadata["topology"]["opposite_edge_orientation"])
                self.assertTrue(metadata["topology"]["connected_degree2_vertex_links"])
                observed_quality = min(triangle_quality(vertices, face) for face in faces)
                self.assertAlmostEqual(
                    observed_quality, metadata["geometry"]["minimum_triangle_quality"],
                    places=14)
                self.assertGreater(observed_quality, 0.5)
                self.assertEqual(
                    metadata["geometry"]["nonadjacent_triangle_intersection_count"], 0)
                self.assertEqual(metadata["generator"]["id"],
                                 "scripts/generate_b2_readiness_fixtures.py")
                self.assertEqual(metadata["status"], "candidate_only_pending_D12")
                self.assertFalse(metadata["scientifically_approved"])

    def test_B_declared_topology_classes_are_exact(self) -> None:
        for member in ("symmetric_344_bipyramid", "asymmetric_344_bipyramid"):
            root = FIXTURE_ROOT / member
            faces = read_faces(root / "faces.csv")
            valences = validate_topology(read_vertices(root / "vertices.csv"), faces)
            self.assertEqual([valences[index] for index in faces[0]], [3, 4, 4])

        torus = FIXTURE_ROOT / "regular_all6_torus"
        valences = validate_topology(
            read_vertices(torus / "vertices.csv"), read_faces(torus / "faces.csv"))
        self.assertEqual(len(valences), 96)
        self.assertEqual(set(valences), {6})

        refined = FIXTURE_ROOT / "closed_566_refined_icosahedron"
        faces = read_faces(refined / "faces.csv")
        metadata = json.loads((refined / "candidate_metadata.json").read_text())
        valences = validate_topology(read_vertices(refined / "vertices.csv"), faces)
        declaration = metadata["construction"]["declared_566_face"]
        self.assertEqual(faces[declaration["face_row"]],
                         tuple(declaration["oriented_vertices"]))
        self.assertEqual([valences[index] for index in faces[0]], [5, 6, 6])
        self.assertEqual(valences[declaration["original_valence5_vertex"]], 5)
        self.assertTrue(all(valences[index] == 6 for index in
                            declaration["edge_midpoint_valence6_vertices"]))
        self.assertEqual(sorted(set(valences)), [5, 6])

    def test_B2_no_nonadjacent_triangle_intersections(self) -> None:
        for member in MEMBERS:
            with self.subTest(member=member):
                root = FIXTURE_ROOT / member
                vertices = read_vertices(root / "vertices.csv")
                faces = read_faces(root / "faces.csv")
                triangles = [tuple(vertices[index] for index in face)
                             for face in faces]
                for left_index, left_face in enumerate(faces):
                    for right_index in range(left_index + 1, len(faces)):
                        if set(left_face).isdisjoint(faces[right_index]):
                            self.assertFalse(
                                triangles_intersect(
                                    triangles[left_index], triangles[right_index]),
                                (member, left_index, right_index))

    def test_C_hash_ledger_and_cross_python_byte_reproduction(self) -> None:
        observed = {
            str(path.relative_to(FIXTURE_ROOT)):
                hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(FIXTURE_ROOT.rglob("*")) if path.is_file()
        }
        self.assertEqual(observed, EXPECTED_HASHES)
        with tempfile.TemporaryDirectory(prefix="b2-readiness-reproduction-") as tmp:
            generated = Path(tmp) / "corpus"
            subprocess.run(
                [sys.executable, str(GENERATOR), "--output-root", str(generated)],
                check=True, cwd=ROOT)
            expected_paths = sorted(path.relative_to(FIXTURE_ROOT)
                                    for path in FIXTURE_ROOT.rglob("*") if path.is_file())
            generated_paths = sorted(path.relative_to(generated)
                                     for path in generated.rglob("*") if path.is_file())
            self.assertEqual(generated_paths, expected_paths)
            for relative in expected_paths:
                self.assertEqual((generated / relative).read_bytes(),
                                 (FIXTURE_ROOT / relative).read_bytes(), relative)

    def test_D_manifest_is_complete_ordered_and_has_exact_mutations(self) -> None:
        manifest = json.loads((FIXTURE_ROOT / "execution_manifest.json").read_text())
        self.assertEqual([entry["id"] for entry in manifest["entries"]],
                         EXPECTED_ROW_IDS)
        self.assertEqual(len(manifest["entries"]), 17)
        self.assertEqual(manifest["fixture_roots"], EXPECTED_FIXTURE_ROOTS)
        for relative in EXPECTED_FIXTURE_ROOTS.values():
            self.assertTrue((ROOT / relative).is_dir(), relative)
        self.assertEqual([rule["id"] for rule in manifest["mutation_rules"]], [
            "coordinate_perturbation_v1", "reverse_face_zero_v1",
            "delete_face_zero_v1", "append_face_zero_v1"])
        self.assertIn("count once", manifest["shared_hull_deduplication"])
        self.assertIn("mesh-level aggregation obeys shared_hull_deduplication",
                      manifest["ordering_contract"])
        self.assertEqual(
            manifest["stable_locality_manifest"],
            "data/fixtures/candidates/b2p_single_flip_family/"
            "family_metadata.json#locality_sample_manifest")

        torus = FIXTURE_ROOT / "regular_all6_torus"
        vertices, faces = read_vertices(torus / "vertices.csv"), read_faces(torus / "faces.csv")
        reversed_faces = list(faces)
        a, b, c = reversed_faces[0]
        reversed_faces[0] = (a, c, b)
        for invalid in (reversed_faces, faces[1:], faces + [faces[0]]):
            with self.assertRaises(AssertionError):
                validate_topology(vertices, invalid)

        asymmetric = FIXTURE_ROOT / "asymmetric_344_bipyramid"
        perturbed = list(read_vertices(asymmetric / "vertices.csv"))
        x, y, z = perturbed[1]
        perturbed[1] = (x + float.fromhex("0x1p-8"),
                        y - float.fromhex("0x1p-9"),
                        z + float.fromhex("0x1p-10"))
        self.assertEqual(validate_topology(
            perturbed, read_faces(asymmetric / "faces.csv")), [4, 4, 4, 3, 3])


if __name__ == "__main__":
    unittest.main()
