import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_production_kernel_call_proof.py"
)
RUNNER = (
    ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_production_kernel_call_proof",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourProductionKernelCallProofInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_narrow_production_scope(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["production_helper_executed_under_test"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_production_helper_has_no_production_caller(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["production_callers"], [])
        self.assertFalse(report["production_or_default_surfaces_changed"])
        self.assertFalse(report["backend_neutral_helper_has_opensubdiv_leak"])

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
    def test_present_dependency_executes_production_helper(self):
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
        self.assertFalse(report["actual_production_force_path_executed"])
        adapter = report["adapter"]
        self.assertTrue(adapter["production_kernel_call_helper_executed"])
        self.assertTrue(adapter["production_helper_output_owned_by_caller"])
        self.assertTrue(adapter["source_binding_permutation_invariant"])
        self.assertTrue(
            adapter["duplicate_row_entries_aggregated_by_source_id"]
        )
        self.assertEqual(adapter["max_scatter_oracle_delta"], 0)
        self.assertTrue(adapter["negative_gates"]["all_passed"])


if __name__ == "__main__":
    unittest.main()
