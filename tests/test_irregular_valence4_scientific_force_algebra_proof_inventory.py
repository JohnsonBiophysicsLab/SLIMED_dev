import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_scientific_force_algebra_proof.py"
)
RUNNER = (
    ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_scientific_force_algebra_proof",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourScientificForceAlgebraProofInventoryTest(
    unittest.TestCase
):
    def test_inventory_passes_with_exact_production_scope(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(
            report["existing_scientific_force_algebra_invoked_under_proof"]
        )
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_formula_body_and_route_remain_unchanged(self):
        report = load_inventory_module().collect(ROOT)
        self.assertTrue(report["scientific_formula_body_unchanged"])
        self.assertTrue(report["production_face_loop_unchanged"])
        self.assertFalse(report["production_or_default_surfaces_changed"])
        self.assertFalse(report["production_formula_has_opensubdiv_leak"])

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
    def test_present_dependency_invokes_existing_scientific_algebra(self):
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
        self.assertTrue(adapter["existing_scientific_force_algebra_invoked"])
        self.assertEqual(
            adapter["scientific_force_algebra_function"],
            "Mesh::element_energy_force_regular",
        )
        self.assertEqual(
            adapter["scientific_force_algebra_variable_cardinality"], 6
        )
        self.assertTrue(adapter["scientific_force_algebra_finite"])
        self.assertTrue(adapter["scientific_force_algebra_nonzero"])
        self.assertLessEqual(
            adapter["max_scientific_force_algebra_difference"], 1.0e-12
        )


if __name__ == "__main__":
    unittest.main()
