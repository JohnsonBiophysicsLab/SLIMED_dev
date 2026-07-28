import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_opensubdiv_row_provider.py"
)
RUNNER = (
    ROOT
    / "scripts/run_irregular_valence4_opensubdiv_row_provider.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_opensubdiv_row_provider",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourOpenSubdivRowProviderInventoryTest(unittest.TestCase):
    def test_inventory_passes_without_route_activation(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(
            report["chosen_prerequisite"],
            "guarded OpenSubdiv valence-4 row provider",
        )
        self.assertTrue(report["provider_smaller_than_duplicate_caller"])
        self.assertTrue(report["backend_neutral_output"])
        self.assertEqual(report["exact_tensor_shape"], "8x3x7x6")
        self.assertTrue(report["failure_atomic_empty_result"])
        self.assertFalse(report["default_dependency_changed"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertEqual(
            report["anchors"]["located"],
            report["anchors"]["expected"],
        )

    def test_dependency_absent_wrapper_skips_cleanly(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(RUNNER), "--json"],
            cwd=ROOT,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is required for row-provider evidence",
    )
    def test_present_dependency_double_rows_match_reviewed_float_proof(self):
        result = subprocess.run(
            [str(RUNNER), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["provider_passed"])
        self.assertEqual(payload["exact_tensor_shape"], "8x3x7x6")
        self.assertTrue(payload["sample_and_face_identity_match"])
        self.assertEqual(payload["provider_row_precision"], "double")
        self.assertEqual(
            payload["comparison_reference"],
            "reviewed float force-proof rows",
        )
        self.assertLessEqual(
            payload["max_abs_difference_vs_reviewed_float_force_proof"],
            payload["comparison_tolerance"],
        )
        self.assertEqual(
            payload["constant_field_invariant_tolerance"],
            1.0e-12,
        )
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(
            payload["actual_production_force_path_executed"]
        )
        self.assertFalse(payload["production_face_loop_executed"])
        self.assertFalse(payload["production_one_rings_populated"])
        self.assertFalse(payload["default_dependency_changed"])


if __name__ == "__main__":
    unittest.main()
