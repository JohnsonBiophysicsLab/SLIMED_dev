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
