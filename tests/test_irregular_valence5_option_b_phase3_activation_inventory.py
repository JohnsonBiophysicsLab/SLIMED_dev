import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "scripts/inventory_irregular_valence5_option_b_phase3_activation.py"
RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_phase3_activation.py"
PHASE2 = ROOT / "scripts/run_irregular_valence5_option_b_phase2_face_loop.py"
WRAPPER = ROOT / "scripts/run_irregular_valence5_option_b_phase3_activation.sh"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OptionBPhase3ActivationInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = load(INVENTORY, "option_b_phase3_inventory")
        cls.runner = load(RUNNER, "option_b_phase3_runner")
        cls.phase2 = load(PHASE2, "option_b_phase3_phase2_contract")

    def test_phase3_inventory_passes(self):
        report = self.inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["production_route_enabled"])
        self.assertTrue(report["default_evaluator_caller"])
        self.assertTrue(report["phase3_activation_authorized"])
        self.assertEqual(report["rollback_gate"], "SLIMED_USE_OPENSUBDIV_VALENCE5")

    def test_scientific_expectations_remain_fixed(self):
        self.assertEqual(self.runner.PRODUCTION_TOLERANCE, 1.0e-10)
        self.assertEqual(len(self.phase2.PHASE2_EXPECTED_GLOBAL_ENERGY), 10)
        self.assertEqual(len(self.phase2.PHASE2_EXPECTED_FACE_CURVATURE), 20)
        self.assertTrue(all(
            math.isfinite(value)
            for value in self.phase2.PHASE2_EXPECTED_GLOBAL_ENERGY
            + self.phase2.PHASE2_EXPECTED_FACE_CURVATURE
        ))

    @unittest.skipUnless(os.environ.get("OPENSUBDIV_ROOT"), "OpenSubdiv not configured")
    def test_enabled_phase3_suite_when_available(self):
        result = subprocess.run(
            [str(WRAPPER), "--check", "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=900,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
