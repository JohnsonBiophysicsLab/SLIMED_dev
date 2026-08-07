"""Focused topology, correspondence, and reproduction checks for B2p."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
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
                self.assertEqual(metadata["generator"]["version"], 1)
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
