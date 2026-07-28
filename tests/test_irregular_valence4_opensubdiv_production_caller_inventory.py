import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_opensubdiv_production_caller.py"
)
RUNNER = (
    ROOT
    / "scripts/run_irregular_valence4_opensubdiv_production_caller.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_opensubdiv_production_caller",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourOpenSubdivProductionCallerInventoryTest(
    unittest.TestCase
):
    def test_inventory_passes_without_route_activation(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["provider_fed_production_caller"])
        self.assertTrue(
            report["opensubdiv_rows_feed_reviewed_caller_shadow"]
        )
        self.assertTrue(
            report["serial_openmp_provider_fed_caller_parity_required"]
        )
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertFalse(report["default_evaluator_route_caller"])
        self.assertFalse(report["default_dependency_changed"])
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
        "OPENSUBDIV_ROOT is required for provider-fed caller evidence",
    )
    def test_present_dependency_provider_fed_caller_parity_passes(self):
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
        self.assertTrue(payload["provider_fed_production_caller"])
        self.assertTrue(payload["opensubdiv_row_provider_executed"])
        self.assertTrue(payload["opensubdiv_rows_generated"])
        self.assertTrue(payload["production_caller_shadow_executed"])
        self.assertTrue(
            payload["production_completion_phases_executed"]
        )
        self.assertTrue(
            payload[
                "serial_openmp_provider_fed_caller_parity_passed"
            ]
        )
        self.assertLessEqual(
            payload["max_serial_openmp_provider_fed_force_delta"],
            payload["absolute_tolerance"],
        )
        self.assertLessEqual(
            payload[
                "max_serial_openmp_provider_fed_observable_delta"
            ],
            payload["absolute_tolerance"],
        )
        self.assertLessEqual(
            payload["serial_openmp_provider_fed_energy_delta"],
            payload["absolute_tolerance"],
        )
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(payload["actual_production_force_path_executed"])
        self.assertFalse(payload["production_face_loop_executed"])
        self.assertFalse(payload["production_one_rings_populated"])
        self.assertFalse(payload["default_dependency_changed"])


if __name__ == "__main__":
    unittest.main()
