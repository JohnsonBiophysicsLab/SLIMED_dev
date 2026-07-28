import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_production_caller_shadow.py"
)
PARITY = (
    ROOT
    / "scripts/run_irregular_valence4_production_call_shadow_parity.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_production_caller_shadow",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourProductionCallerShadowInventoryTest(unittest.TestCase):
    def test_inventory_passes_without_route_activation(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["production_caller_completion_shadow"])
        self.assertTrue(report["shared_production_completion_phase"])
        self.assertTrue(
            report["serial_openmp_total_force_energy_parity_required"]
        )
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertFalse(report["real_production_route_caller"])
        self.assertFalse(report["default_dependency_changed"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_dependency_absent_parity_wrapper_skips_cleanly(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(PARITY), "--json"],
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
        "OPENSUBDIV_ROOT is required for caller-shadow parity",
    )
    def test_present_dependency_caller_shadow_parity_passes(self):
        result = subprocess.run(
            [str(PARITY), "--json", "--require-opensubdiv"],
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
        self.assertTrue(
            payload["production_caller_completion_shadow_executed"]
        )
        self.assertFalse(payload["production_caller_route_enabled"])
        self.assertFalse(
            payload["production_caller_actual_face_loop_executed"]
        )
        self.assertLessEqual(
            payload[
                "max_serial_openmp_production_caller_total_force_delta"
            ],
            1.0e-12,
        )
        self.assertLessEqual(
            payload[
                "serial_openmp_production_caller_total_energy_delta"
            ],
            1.0e-12,
        )


if __name__ == "__main__":
    unittest.main()
