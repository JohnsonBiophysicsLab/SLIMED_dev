import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inventory_cuda_end_to_end_plan.py"
)
SPEC = importlib.util.spec_from_file_location(
    "inventory_cuda_end_to_end_plan", SCRIPT_PATH
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class CudaEndToEndPlanInventoryTest(unittest.TestCase):
    def test_plan_has_thirteen_ordered_pr_steps(self):
        self.assertEqual(
            [step.number for step in inventory.PLAN_STEPS],
            list(range(13)),
        )
        self.assertEqual(inventory.PLAN_STEPS[0].title, "Plan and protected contract")
        self.assertEqual(
            inventory.PLAN_STEPS[-1].title,
            "Explicit opt-in route activation",
        )

    def test_each_step_names_required_evidence(self):
        for step in inventory.PLAN_STEPS:
            with self.subTest(step=step.number):
                self.assertTrue(step.required_evidence)
                self.assertTrue(all(step.required_evidence))

    def test_all_protected_contract_categories_are_present(self):
        located, missing = inventory.locate_anchors(inventory.repo_root())

        self.assertFalse(missing)
        self.assertEqual(
            {item.anchor.category for item in located},
            {
                "scope",
                "architecture",
                "state",
                "formula",
                "scatter",
                "correctness",
                "compatibility",
                "fallback",
                "optimizer",
                "performance",
                "review",
                "prompts",
            },
        )

    def test_markdown_contains_ordered_steps_and_required_evidence(self):
        located, issues = inventory.locate_plan_steps(inventory.repo_root())

        self.assertFalse(issues)
        self.assertEqual([item.step.number for item in located], list(range(13)))
        self.assertEqual(
            [item.line_number for item in located],
            sorted(item.line_number for item in located),
        )

    def test_missing_or_reordered_step_heading_fails_validation(self):
        text = (inventory.repo_root() / inventory.PLAN_PATH).read_text(
            encoding="utf-8"
        )
        step_five = inventory.PLAN_STEPS[5]
        step_six = inventory.PLAN_STEPS[6]

        missing_text = text.replace(step_six.heading, "### Removed step", 1)
        _, missing_issues = inventory.validate_plan_text(missing_text)
        self.assertTrue(any(issue.step.number == 6 for issue in missing_issues))

        reordered_text = text.replace(step_five.heading, "### Step placeholder", 1)
        reordered_text = reordered_text.replace(step_six.heading, step_five.heading, 1)
        reordered_text = reordered_text.replace("### Step placeholder", step_six.heading, 1)
        _, reordered_issues = inventory.validate_plan_text(reordered_text)
        self.assertTrue(any(issue.step.number in {5, 6} for issue in reordered_issues))

    def test_missing_step_evidence_fails_validation(self):
        text = (inventory.repo_root() / inventory.PLAN_PATH).read_text(
            encoding="utf-8"
        )
        evidence = inventory.PLAN_STEPS[9].required_evidence[0]
        drifted = text.replace(evidence, "Removed scalar-only contract", 1)

        _, issues = inventory.validate_plan_text(drifted)

        self.assertTrue(
            any(
                issue.step.number == 9 and "missing required evidence" in issue.detail
                for issue in issues
            )
        )

    def test_inventory_report_is_dependency_free_and_complete(self):
        located, missing = inventory.locate_anchors(inventory.repo_root())
        located_steps, step_issues = inventory.locate_plan_steps(inventory.repo_root())
        report = inventory.as_dicts(located, missing, located_steps, step_issues)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["plan_steps"]), 13)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["step_issues"], [])


if __name__ == "__main__":
    unittest.main()
