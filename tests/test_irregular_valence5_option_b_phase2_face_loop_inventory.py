import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "scripts/inventory_irregular_valence5_option_b_phase2_face_loop.py"
RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_phase2_face_loop.py"
BASELINE = ROOT / "scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py"
WRAPPER = ROOT / "scripts/run_irregular_valence5_option_b_phase2_face_loop.sh"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OptionBPhase2FaceLoopInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = load(INVENTORY, "option_b_phase2_inventory")
        cls.runner = load(RUNNER, "option_b_phase2_runner")
        cls.baseline = load(BASELINE, "option_b_phase2_accepted_baseline")

    def test_phase2_inventory_passes(self):
        report = self.inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["production_face_loop_exercised"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["default_evaluator_caller"])
        self.assertFalse(report["phase3_activation_authorized"])

    def test_accepted_baseline_has_complete_shape(self):
        vector = list(self.baseline.EXPECTED_CANONICAL_OBSERVABLE_VECTOR)
        self.assertEqual(len(vector), 330)
        self.assertTrue(all(math.isfinite(value) for value in vector))
        self.assertEqual(len(vector[:10]), 10)
        self.assertEqual(len(vector[10:210]), 200)
        self.assertEqual(len(vector[210:]), 120)
        self.assertEqual(len(self.runner.PHASE2_EXPECTED_GLOBAL_ENERGY), 10)
        self.assertEqual(len(self.runner.PHASE2_EXPECTED_FACE_CURVATURE), 20)
        self.assertTrue(all(
            math.isfinite(value)
            for value in self.runner.PHASE2_EXPECTED_GLOBAL_ENERGY
            + self.runner.PHASE2_EXPECTED_FACE_CURVATURE
        ))

    def test_numeric_guards_reject_false_and_nonfinite_values(self):
        for invalid in (False, math.nan, math.inf):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                self.runner.finite_list([invalid], 1, "synthetic")
        self.assertEqual(self.runner.maximum_difference([1.0], [1.25]), 0.25)
        with self.assertRaises(RuntimeError):
            self.runner.maximum_difference([1.0], [1.0, 2.0])

    def test_independent_oracle_boundary_is_fixed(self):
        self.assertEqual(
            self.runner.ORACLE,
            ROOT / "experiments/irregular_valence5_option_b_energy_geometry_oracle.cpp",
        )
        self.assertEqual(self.baseline.ORACLE_ABSOLUTE_TOLERANCE, 1.0e-10)

    @unittest.skipUnless(os.environ.get("OPENSUBDIV_ROOT"), "OpenSubdiv not configured")
    def test_enabled_phase2_suite_when_available(self):
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
