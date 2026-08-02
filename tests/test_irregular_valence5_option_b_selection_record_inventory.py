import copy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_selection_record.py"
INVENTORY = ROOT / "scripts/inventory_irregular_valence5_option_b_selection_record.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OptionBSelectionRecordTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load(RUNNER, "option_b_selection_record")

    def test_canonical_record_selects_and_approves_but_does_not_route(self):
        report = self.runner.evaluate()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["decision"], "accept")
        self.assertTrue(report["decision_recorded"])
        self.assertTrue(report["option_b_selected"])
        self.assertFalse(report["option_b_recommended"])
        self.assertTrue(report["stock_semantics_scientifically_approved"])
        self.assertTrue(report["scientific_rebaseline_plan_authorized"])
        self.assertTrue(report["production_routing_plan_authorized"])
        self.assertFalse(report["implementation_authorized"])
        self.assertFalse(report["production_route_enabled"])
        self.assertTrue(report["current_slimed_valence5_fallback_preserved"])

    def test_predecessor_identity_and_non_authorizing_state_are_binding(self):
        predecessor = self.runner._predecessor_report()
        predecessor["decision_recorded"] = True
        report = self.runner.evaluate(predecessor_report=predecessor)
        self.assertEqual(report["status"], "failed")
        self.assertIn("predecessor decision_recorded drift", " ".join(report["errors"]))
        report = self.runner.evaluate(predecessor_sha256="0" * 64)
        self.assertEqual(report["status"], "failed")

        predecessor = self.runner._predecessor_report()
        predecessor["measured_changes"]["composed_row_max_abs_difference"] = 0.0
        report = self.runner.evaluate(predecessor_report=predecessor)
        self.assertEqual(report["status"], "failed")
        self.assertIn("predecessor measurements drift", " ".join(report["errors"]))

        predecessor = self.runner._predecessor_report()
        predecessor["evidence"][0]["pull_request"] = 999
        report = self.runner.evaluate(predecessor_report=predecessor)
        self.assertEqual(report["status"], "failed")
        self.assertIn("predecessor evidence drift", " ".join(report["errors"]))

    def test_selection_and_plan_authorizations_cannot_false_negative(self):
        for key in (
            "decision_recorded",
            "option_b_selected",
            "stock_semantics_scientifically_approved",
            "scientific_rebaseline_plan_authorized",
            "production_routing_plan_authorized",
        ):
            with self.subTest(key=key):
                self.assertEqual(self.runner.evaluate(**{key: False})["status"], "failed")
        self.assertEqual(self.runner.evaluate(decision="defer")["status"], "failed")

    def test_recommendation_implementation_and_route_false_greens_fail(self):
        for key in (
            "option_b_recommended",
            "implementation_authorized",
            "production_route_enabled",
        ):
            with self.subTest(key=key):
                self.assertEqual(self.runner.evaluate(**{key: True})["status"], "failed")

    def test_plan_has_three_separately_gated_phases(self):
        phases = self.runner.evaluate()["implementation_plan"]
        self.assertEqual([phase["phase"] for phase in phases], [1, 2, 3])
        self.assertFalse(phases[0]["production_mutation"])
        self.assertTrue(phases[1]["production_mutation"])
        self.assertIn("user_approval", phases[2]["authorization"])

    def test_wrapper_executable_mode_is_inventory_bound(self):
        inventory = load(INVENTORY, "option_b_selection_record_inventory")
        report = inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["wrapper_git_mode"], "100755")


if __name__ == "__main__":
    unittest.main()
