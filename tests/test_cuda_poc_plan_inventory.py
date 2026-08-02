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

    def test_markdown_contains_ordered_steps_and_required_evidence(self):
        located, issues = inventory.locate_plan_steps(inventory.repo_root())

        self.assertFalse(issues)
        self.assertEqual([item.step.number for item in located], [1, 2, 3, 4, 5])
        self.assertEqual(
            [item.line_number for item in located],
            sorted(item.line_number for item in located),
        )

    def test_missing_or_reordered_step_heading_fails_validation(self):
        text = (inventory.repo_root() / inventory.PLAN_PATH).read_text(encoding="utf-8")
        step_two = inventory.PLAN_STEPS[1]
        step_three = inventory.PLAN_STEPS[2]

        missing_text = text.replace(step_three.heading, "### Removed step", 1)
        _, missing_issues = inventory.validate_plan_text(missing_text)
        self.assertTrue(any(issue.step.number == 3 for issue in missing_issues))

        reordered_text = text.replace(step_two.heading, "### Step placeholder", 1)
        reordered_text = reordered_text.replace(step_three.heading, step_two.heading, 1)
        reordered_text = reordered_text.replace("### Step placeholder", step_three.heading, 1)
        _, reordered_issues = inventory.validate_plan_text(reordered_text)
        self.assertTrue(any(issue.step.number in {2, 3} for issue in reordered_issues))

    def test_missing_step_evidence_fails_validation(self):
        text = (inventory.repo_root() / inventory.PLAN_PATH).read_text(encoding="utf-8")
        evidence = inventory.PLAN_STEPS[3].required_evidence[0]
        drifted = text.replace(evidence, "Removed benchmark evidence", 1)

        _, issues = inventory.validate_plan_text(drifted)

        self.assertTrue(
            any(
                issue.step.number == 4 and "missing required evidence" in issue.detail
                for issue in issues
            )
        )

    def test_inventory_report_is_dependency_free_and_complete(self):
        located, missing = inventory.locate_anchors(inventory.repo_root())
        located_steps, step_issues = inventory.locate_plan_steps(inventory.repo_root())
        report = inventory.as_dicts(located, missing, located_steps, step_issues)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["plan_steps"]), 5)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["step_issues"], [])


if __name__ == "__main__":
    unittest.main()
