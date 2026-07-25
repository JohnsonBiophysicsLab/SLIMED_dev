import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "scripts/inventory_irregular_valence4_production_call_parity.py"
RUNNER = ROOT / "scripts/run_irregular_valence4_production_call_parity.sh"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_production_call_parity", INVENTORY
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourProductionCallParityInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_proof_only_scope(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])

    def test_default_and_production_surfaces_are_unchanged(self):
        report = load_inventory_module().collect(ROOT)
        self.assertFalse(report["production_or_default_surfaces_changed"])
        self.assertFalse(report["fake_regular_kernel_call"])
        self.assertTrue(report["temporary_one_ring_mutation_gate"])

    def test_absent_dependency_skips_cleanly(self):
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
        "OPENSUBDIV_ROOT is required for the present-dependency proof",
    )
    def test_present_dependency_boundary_passes(self):
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
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["fresh_opensubdiv_row_binding_passed"])
        self.assertTrue(report["production_entry_rejected_loudly"])
        self.assertFalse(report["actual_production_force_path_executed"])


if __name__ == "__main__":
    unittest.main()
