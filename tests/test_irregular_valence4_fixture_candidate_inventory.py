import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_irregular_valence4_fixture_candidate.py"
SPEC = importlib.util.spec_from_file_location(
    "inventory_irregular_valence4_fixture_candidate", SCRIPT
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class IrregularValence4FixtureCandidateInventoryTest(unittest.TestCase):
    def test_candidate_topology_orientation_and_analytical_geometry(self):
        report = inventory.collect(ROOT)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["vertex_count"], 6)
        self.assertEqual(report["unique_finite_vertex_count"], 6)
        self.assertEqual(report["edge_count"], 12)
        self.assertEqual(report["face_count"], 8)
        self.assertEqual(report["valid_face_count"], 8)
        self.assertEqual(report["edge_incidence_counts"], {2: 12})
        self.assertEqual(report["vertex_valence_counts"], {4: 6})
        self.assertEqual(report["face_valence_triplet_counts"], {"4/4/4": 8})
        self.assertTrue(report["coherently_oriented_closed_connectivity"])
        self.assertTrue(report["connected"])
        self.assertEqual(report["euler_characteristic"], 2)
        self.assertTrue(report["outward_winding"])
        self.assertTrue(report["all_oriented_face_volume_contributions_positive"])

        self.assertEqual(
            report["geometry_scope"],
            "straight_sided_input_polyhedron_not_slimed_output",
        )
        geometry = report["input_polyhedron_geometry"]
        self.assertAlmostEqual(geometry["circumradius"], 1.0, places=12)
        self.assertAlmostEqual(geometry["edge_length"], math.sqrt(2.0), places=12)
        self.assertAlmostEqual(
            geometry["single_face_area"], math.sqrt(3.0) / 2.0, places=12
        )
        self.assertAlmostEqual(
            geometry["total_polyhedral_surface_area"],
            4.0 * math.sqrt(3.0),
            places=12,
        )
        self.assertAlmostEqual(
            geometry["signed_enclosed_polyhedral_volume"],
            4.0 / 3.0,
            places=12,
        )

    def test_packet_remains_candidate_only_and_unrouted(self):
        report = inventory.collect(ROOT)

        self.assertTrue(report["candidate_only"])
        self.assertFalse(report["scientifically_approved"])
        self.assertTrue(report["scientific_approval_required"])
        self.assertTrue(report["approved_for_mapping_sample_transpose_proof"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertEqual(report["expected_production_one_ring_size_counts"], {"0": 8})
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertIn("membrane force correctness", report["claims_not_made"])
        self.assertIn("OpenSubdiv force correctness", report["claims_not_made"])

    def test_check_mode_emits_passing_json(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--json", "--check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "passed")


if __name__ == "__main__":
    unittest.main()
