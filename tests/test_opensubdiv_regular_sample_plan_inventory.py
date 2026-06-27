import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inventory_opensubdiv_regular_sample_plan.py"
)
SPEC = importlib.util.spec_from_file_location("inventory_opensubdiv_regular_sample_plan", SCRIPT_PATH)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class OpenSubdivRegularSamplePlanInventoryTest(unittest.TestCase):
    def test_regular_sample_plan_freezes_default_quadrature_order(self):
        self.assertEqual(len(inventory.REGULAR_SAMPLE_PLAN), 3)
        self.assertEqual(
            [(row["v"], row["w"], row["u"]) for row in inventory.REGULAR_SAMPLE_PLAN],
            [("1/6", "1/6", "4/6"), ("1/6", "4/6", "1/6"), ("4/6", "1/6", "1/6")],
        )
        self.assertEqual(
            {row["quadrature_weight"] for row in inventory.REGULAR_SAMPLE_PLAN},
            {"1/3"},
        )
        self.assertEqual(
            {row["formula_factor"] for row in inventory.REGULAR_SAMPLE_PLAN},
            {"1/6"},
        )

    def test_derivative_rows_cover_slimed_seven_row_contract(self):
        rows = {row["row"]: row for row in inventory.DERIVATIVE_ROWS}

        self.assertEqual(set(rows), set(range(7)))
        self.assertEqual(rows[0]["name"], "position")
        self.assertEqual(rows[1]["name"], "firstDerivativeV")
        self.assertIn("s=v,t=w", rows[1]["opensubdiv_row"])
        self.assertEqual(rows[2]["name"], "firstDerivativeW")
        self.assertIn("s=v,t=w", rows[2]["opensubdiv_row"])
        self.assertEqual(rows[5]["opensubdiv_row"], "duv")
        self.assertEqual(rows[6]["opensubdiv_row"], "duv")

    def test_source_id_rules_cover_order_scatter_and_duplicate_aggregation(self):
        rules = {row["rule"]: row["requirement"] for row in inventory.SOURCE_ID_RULES}

        self.assertIn("regular local source order", rules)
        self.assertIn("Face::oneRingVertices[j]", rules["regular local source order"])
        self.assertIn("force scatter order", rules)
        self.assertIn("face.oneRingVertices[j]", rules["force scatter order"])
        self.assertIn("duplicate source ids", rules)
        self.assertIn("sums every local column", rules["duplicate source ids"])

    def test_inventory_anchors_are_present(self):
        located, missing = inventory.collect_anchors(inventory.repo_root())

        self.assertFalse(missing)
        self.assertGreaterEqual(len(located), len(inventory.ANCHORS))


if __name__ == "__main__":
    unittest.main()
