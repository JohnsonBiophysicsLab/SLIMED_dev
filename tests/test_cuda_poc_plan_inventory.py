import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "inventory_cuda_poc_plan.py"
)
SPEC = importlib.util.spec_from_file_location("inventory_cuda_poc_plan", SCRIPT_PATH)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class CudaPocPlanInventoryTest(unittest.TestCase):
    def test_plan_has_five_ordered_pr_steps(self):
        self.assertEqual(
            [step.number for step in inventory.PLAN_STEPS],
            [1, 2, 3, 4, 5],
        )
        self.assertEqual(inventory.PLAN_STEPS[0].title, "Plan and validation contract")
        self.assertEqual(
            inventory.PLAN_STEPS[-1].title,
            "Opt-in SLIMED adapter experiment",
        )

    def test_each_step_names_required_evidence(self):
        for step in inventory.PLAN_STEPS:
            with self.subTest(step=step.number):
                self.assertTrue(step.required_evidence)
                self.assertTrue(all(step.required_evidence))

    def test_scope_correctness_performance_and_review_gates_are_present(self):
        located, missing = inventory.locate_anchors(inventory.repo_root())

        self.assertFalse(missing)
        categories = {item.anchor.category for item in located}
        self.assertEqual(
            categories,
            {"scope", "kernel", "environment", "compatibility", "correctness", "performance", "review"},
        )

    def test_inventory_report_is_dependency_free_and_complete(self):
        located, missing = inventory.locate_anchors(inventory.repo_root())
        report = inventory.as_dicts(located, missing)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["plan_steps"]), 5)
        self.assertEqual(report["missing"], [])


if __name__ == "__main__":
    unittest.main()
