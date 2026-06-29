import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inventory_opensubdiv_regular_adapter_readiness.py"
)
SPEC = importlib.util.spec_from_file_location("inventory_opensubdiv_regular_adapter_readiness", SCRIPT_PATH)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class OpenSubdivRegularAdapterReadinessInventoryTest(unittest.TestCase):
    def test_evidence_lineage_tracks_pr68_through_current_proof(self):
        lanes = {row["lane"] for row in inventory.EVIDENCE_LINEAGE}

        self.assertEqual(len(lanes), len(inventory.EVIDENCE_LINEAGE))
        self.assertIn("PR #68 weighted-sample seam", lanes)
        self.assertIn("PR #69 mapping contract", lanes)
        self.assertIn("PR #72 regular actual-force evidence", lanes)
        self.assertIn("PR #73 routing readiness map", lanes)
        self.assertIn("PR #74 regular sample plan", lanes)
        self.assertIn("PR #75 regular backend readiness", lanes)
        self.assertIn("current regular adapter proof", lanes)

    def test_adapter_checklist_covers_regular_backend_gates(self):
        gates = {row["gate"]: row for row in inventory.ADAPTER_READINESS_CHECKLIST}

        self.assertIn("regular sample coordinates and quadrature order", gates)
        self.assertIn("coordinate and derivative convention", gates)
        self.assertIn("original source-id order", gates)
        self.assertIn("deterministic duplicate aggregation", gates)
        self.assertIn("actual force rows", gates)
        self.assertIn("regular production helper dry run", gates)
        self.assertIn("output-visible state", gates)
        self.assertIn("scatter and reduction", gates)
        self.assertIn("dependency-present behavior", gates)
        self.assertIn("dependency-absent behavior", gates)
        self.assertIn("non-production review gate", gates)
        self.assertIn("fBend", gates["actual force rows"]["must_prove"])
        self.assertIn("Mesh::element_energy_force_regular", gates["regular production helper dry run"]["must_prove"])
        self.assertIn("Face::oneRingVertices", gates["scatter and reduction"]["must_prove"])
        self.assertIn("OpenSubdiv-derived rows", gates["non-production review gate"]["must_prove"])
        self.assertIn("test-only adapter proof", gates["actual force rows"]["current_status"])

    def test_inventory_anchors_are_present(self):
        located, missing = inventory.collect_anchors(inventory.repo_root())

        self.assertFalse(missing)
        self.assertGreaterEqual(len(located), len(inventory.ANCHORS))


if __name__ == "__main__":
    unittest.main()
