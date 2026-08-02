import copy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_scientific_decision.py"
INVENTORY = ROOT / "scripts/inventory_irregular_valence5_option_b_scientific_decision.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load decision runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OptionBScientificDecisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load(RUNNER, "option_b_scientific_decision")

    def test_canonical_packet_is_decision_ready_but_authorizes_nothing(self):
        report = self.runner.evaluate()
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["evidence_complete"])
        self.assertTrue(report["decision_ready_for_user"])
        self.assertFalse(report["decision_recorded"])
        self.assertFalse(report["option_b_selected"])
        self.assertFalse(report["option_b_recommended"])
        self.assertFalse(report["scientific_approval_granted"])
        self.assertFalse(report["implementation_authorized"])
        self.assertFalse(report["production_route_enabled"])
        self.assertTrue(report["current_slimed_valence5_fallback_preserved"])
        self.assertFalse(report["numerical_consistency_is_scientific_acceptance"])

    def test_evidence_identity_measurements_and_source_digests_are_binding(self):
        evidence = copy.deepcopy(list(self.runner.CANONICAL_EVIDENCE))
        evidence[1]["pull_request"] = 999
        self.assertEqual(self.runner.evaluate(evidence=evidence)["status"], "failed")

        measurements = copy.deepcopy(self.runner.MEASURED_CHANGES)
        measurements["global_curvature_energy_abs_difference"] = 0.0
        self.assertEqual(
            self.runner.evaluate(measured_changes=measurements)["status"], "failed"
        )

        digests = copy.deepcopy(self.runner.SOURCE_DIGESTS)
        first = next(iter(digests))
        digests[first] = "0" * 64
        self.assertEqual(self.runner.evaluate(source_digests=digests)["status"], "failed")

    def test_selection_approval_implementation_and_route_false_greens_fail(self):
        for key in (
            "option_b_selected",
            "option_b_recommended",
            "scientific_approval_granted",
            "implementation_authorized",
            "production_route_enabled",
        ):
            with self.subTest(key=key):
                self.assertEqual(self.runner.evaluate(**{key: True})["status"], "failed")

    def test_wrapper_executable_mode_is_inventory_bound(self):
        inventory = load(INVENTORY, "option_b_scientific_decision_inventory")
        report = inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["wrapper_git_mode"], "100755")

    def test_decision_responses_keep_defer_and_reject_on_current_fallback(self):
        report = self.runner.evaluate()
        self.assertIn("current SLIMED", report["decision_responses"]["reject"])
        self.assertIn("current fallback", report["decision_responses"]["defer"])
        self.assertIn("separate", report["decision_responses"]["accept"])


if __name__ == "__main__":
    unittest.main()
