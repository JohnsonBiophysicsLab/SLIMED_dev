import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inventory_opensubdiv_routing_readiness.py"
)
SPEC = importlib.util.spec_from_file_location("inventory_opensubdiv_routing_readiness", SCRIPT_PATH)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class OpenSubdivRoutingReadinessInventoryTest(unittest.TestCase):
    def test_regular_readiness_criteria_cover_expected_gates(self):
        criteria = {
            row["criterion"]
            for row in inventory.REGULAR_READINESS_CRITERIA
        }

        self.assertEqual(len(criteria), len(inventory.REGULAR_READINESS_CRITERIA))
        self.assertIn("OpenSubdiv-derived sample identity", criteria)
        self.assertIn("seven-row derivative mapping", criteria)
        self.assertIn("source-id ordering", criteria)
        self.assertIn("duplicate aggregation", criteria)
        self.assertIn("quadrature/sample identity", criteria)
        self.assertIn("actual fBend/fArea/fVolume comparison", criteria)
        self.assertIn("energy/normal/area/volume comparison", criteria)
        self.assertIn("scatter through Face::oneRingVertices", criteria)
        self.assertIn("serial/OpenMP tolerance envelope", criteria)
        self.assertIn("fallback diagnostics", criteria)
        self.assertIn("default dependency isolation", criteria)
        self.assertIn("reviewer/user gate", criteria)

    def test_route_matrix_keeps_irregular_routes_future_or_current_only(self):
        matrix = {
            row["route"]: row
            for row in inventory.ROUTE_READINESS_MATRIX
        }

        regular = matrix["regular 12-control membrane force"]
        self.assertIn("not production-routed", regular["readiness_result"])
        self.assertIn("PR #82", regular["opensubdiv_evidence_status"])

        irregular_11 = matrix["positive-depth 11 = 4+3+4 membrane force"]
        self.assertIn("subdivision matrices", irregular_11["current_production_status"])
        self.assertIn("do not replace", irregular_11["readiness_result"])

        broader = matrix["broader extraordinary valence"]
        self.assertIn("future-only", broader["readiness_result"])

    def test_inventory_anchors_are_present(self):
        located, missing = inventory.collect_anchors(inventory.repo_root())

        self.assertFalse(missing)
        self.assertGreaterEqual(len(located), len(inventory.ANCHORS))

    def test_residual_policy_anchors_cover_required_tolerance_metrics(self):
        anchor_names = {anchor.name for anchor in inventory.ANCHORS}

        self.assertIn("current routed residual tolerance", anchor_names)
        self.assertIn("required routed residual absolute tolerance", anchor_names)
        self.assertIn("required routed residual relative tolerance", anchor_names)
        self.assertIn("required routed residual tolerance multiplier", anchor_names)
        self.assertIn("required routed residual tolerance source", anchor_names)
        self.assertIn("required routed residual tolerance source relative value", anchor_names)
        self.assertIn("required routed residual tolerance assertion", anchor_names)
        self.assertIn("required routed residual tolerance source assertion", anchor_names)
        self.assertIn("required tolerance decision metrics wording", anchor_names)
        self.assertIn("required tolerance source wording", anchor_names)


if __name__ == "__main__":
    unittest.main()
