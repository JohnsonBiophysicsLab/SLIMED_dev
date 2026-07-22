import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inventory_irregular_fixture_candidates.py"
)
SPEC = importlib.util.spec_from_file_location("inventory_irregular_fixture_candidates", SCRIPT_PATH)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class IrregularFixtureInventoryTest(unittest.TestCase):
    def test_approved_example_mesh_uses_production_periodic_ghost_contract(self):
        meshes, _ = inventory.checked_in_mesh_inputs(inventory.repo_root())
        mesh = next(mesh for mesh in meshes if mesh.label == "data/example")
        summary = inventory.summarize_mesh(mesh, candidate_limit=2)

        self.assertIn("production periodic ghost policy", summary["ghost_status"])
        self.assertEqual(sum(flag is True for flag in mesh.face_ghost_flags), 960)
        self.assertEqual(
            summary["route_counts"],
            {
                inventory.BOUNDARY_ROUTE: 960,
                inventory.REGULAR_ROUTE: 2720,
            },
        )
        self.assertNotIn(inventory.SUPPORTED_11_ROUTE, summary["route_counts"])
        self.assertNotIn(inventory.OPENSUBDIV_GAP, summary["route_counts"])

    def test_flat_grid_and_periodic_ghost_policy_match_fixture_shape(self):
        root = inventory.repo_root()
        faces = inventory.parse_faces_csv(root / "data/example/faces_flat.csv")
        vertices = inventory.parse_vertices_csv(root / "data/example/vertices_flat.csv")

        self.assertEqual(
            inventory.infer_flat_grid_divisions(len(vertices), faces),
            (40, 46),
        )
        flags = inventory.periodic_ghost_face_flags(40, 46)
        self.assertEqual(len(flags), 3680)
        self.assertEqual(sum(flags), 960)

    def test_generated_icosahedron_maps_to_supported_11_route(self):
        mesh = inventory.generated_icosahedron()
        summary = inventory.summarize_mesh(mesh, candidate_limit=2)

        self.assertEqual(summary["vertex_count"], 12)
        self.assertEqual(summary["face_count"], 20)
        self.assertEqual(summary["derived_one_ring_size_counts"], {"11": 20})
        self.assertEqual(
            summary["route_counts"][inventory.SUPPORTED_11_ROUTE],
            20,
        )
        self.assertEqual(summary["route_counts"][inventory.ZERO_DEPTH_GUARD], 20)
        self.assertEqual(summary["errors"], [])

    def test_boundary_faces_are_not_physical_irregular_candidates(self):
        mesh = inventory.MeshInput(
            label="single_triangle",
            vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            faces=((0, 1, 2),),
            source="test",
            ghost_status="not serialized in CSV fixture",
            face_ghost_flags=(None,),
        )
        summary = inventory.summarize_mesh(mesh, candidate_limit=2)

        self.assertEqual(
            summary["route_counts"],
            {inventory.BOUNDARY_ROUTE: 1},
        )
        self.assertEqual(summary["derived_one_ring_size_counts"], {"unavailable": 1})
        example = summary["candidate_examples"][inventory.BOUNDARY_ROUTE][0]
        self.assertTrue(example["topology_boundary"])
        self.assertIsNone(example["ghost"])


if __name__ == "__main__":
    unittest.main()
