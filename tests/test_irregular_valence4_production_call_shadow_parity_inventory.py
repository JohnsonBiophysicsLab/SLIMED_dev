import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_production_call_shadow_parity.py"
)
WRAPPER = (
    ROOT
    / "scripts/run_irregular_valence4_production_call_shadow_parity.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_production_call_shadow_parity",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourProductionCallShadowParityInventoryTest(
    unittest.TestCase
):
    def test_inventory_passes_without_production_route(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["production_call_shadow"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertTrue(report["serial_openmp_output_parity_required"])
        self.assertTrue(report["actual_openmp_runtime_parity_required"])
        self.assertTrue(report["independent_geometry_oracle_required"])
        self.assertFalse(report["production_face_loop_caller"])
        self.assertFalse(report["forbidden_surface_changed"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_dependency_absent_wrapper_skips_cleanly(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(WRAPPER), "--json"],
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
        "OPENSUBDIV_ROOT is required for present-dependency proof",
    )
    def test_present_dependency_serial_openmp_parity_passes(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--require-opensubdiv"],
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
        self.assertTrue(payload["production_call_shadow"])
        self.assertTrue(payload["serial_openmp_output_parity_passed"])
        self.assertTrue(
            payload["production_caller_completion_shadow_executed"]
        )
        self.assertFalse(payload["production_caller_route_enabled"])
        self.assertFalse(
            payload["production_caller_actual_face_loop_executed"]
        )
        self.assertTrue(payload["actual_openmp_runtime_parity_passed"])
        self.assertTrue(payload["production_shaped_geometry_evaluated"])
        self.assertTrue(
            payload["serial_output"]["area"] > 0.0
        )
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(payload["actual_production_force_path_executed"])
        self.assertFalse(payload["production_face_loop_executed"])
        self.assertLessEqual(
            payload["max_serial_openmp_force_delta"], 1.0e-12
        )
        self.assertLessEqual(
            payload["max_serial_openmp_face_observable_delta"], 1.0e-12
        )
        self.assertLessEqual(payload["serial_openmp_area_delta"], 1.0e-12)
        self.assertLessEqual(
            payload["serial_openmp_legacy_volume_delta"], 1.0e-12
        )
        self.assertLessEqual(
            payload["serial_area_oracle_delta"], 1.0e-12
        )
        self.assertLessEqual(
            payload["openmp_area_oracle_delta"], 1.0e-12
        )
        self.assertLessEqual(
            payload["serial_legacy_volume_oracle_delta"], 1.0e-12
        )
        self.assertLessEqual(
            payload["openmp_legacy_volume_oracle_delta"], 1.0e-12
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
        self.assertEqual(
            payload["serial_output"]["forces"],
            payload["openmp_output"]["forces"],
        )
        self.assertEqual(
            payload["serial_output"]["observables"],
            payload["openmp_output"]["observables"],
        )


if __name__ == "__main__":
    unittest.main()
