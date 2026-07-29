import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_opensubdiv_force_parity.py"
)
RUNNER = ROOT / "scripts/run_irregular_valence5_opensubdiv_force_parity.py"
WRAPPER = ROOT / "scripts/run_irregular_valence5_opensubdiv_force_parity.sh"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFiveOpenSubdivForceParityInventoryTest(unittest.TestCase):
    def test_inventory_passes(self):
        report = load_module(INVENTORY, "val5_force_inventory").collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertEqual(report["forbidden_stale_claims"]["located"], 0)
        self.assertFalse(report["force_parity_passed"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["production_scatter_executed"])

    def test_per_face_component_mutation_is_binding(self):
        runner = load_module(RUNNER, "val5_force_runner")
        production = {
            "production_irregular_force_path_executed": True,
            "per_face_source_forces": [0.0] * (20 * 12 * 9),
        }
        candidate = {
            "opensubdiv_rows_evaluated_by_existing_force_algebra": True,
            "per_face_source_forces": [0.0] * (20 * 12 * 9),
        }
        passing = runner.compare(production, candidate)
        self.assertTrue(passing["force_parity_passed"])
        self.assertEqual(
            passing["relative_tolerance"],
            runner.REVIEWED_RELATIVE_TOLERANCE,
        )

        component = 7 * 108 + 4 * 9 + 2 * 3 + 1
        candidate["per_face_source_forces"][component] = 1.0
        rejected = runner.compare(production, candidate)
        self.assertFalse(rejected["force_parity_passed"])
        self.assertEqual(
            rejected["max_abs_force_difference_location"],
            {
                "face": 7,
                "source_id": 4,
                "force_kind": "fVolume",
                "axis": 1,
            },
        )
        self.assertTrue(rejected["route_blockers"])

    def test_wider_tolerance_override_is_rejected(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--tolerance", "1"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("force_parity_passed", result.stdout)
        self.assertIn("unrecognized arguments: --tolerance 1", result.stderr)

    def test_dependency_absent_wrapper_skips(self):
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
        "OPENSUBDIV_ROOT is not configured for this test process",
    )
    def test_present_dependency_reports_exact_force_blocker(self):
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
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertFalse(report["force_parity_passed"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["production_scatter_executed"])
        self.assertEqual(report["force_component_count"], 2160)
        self.assertGreater(
            report["max_abs_force_difference"],
            report["scaled_absolute_tolerance"],
        )
        self.assertTrue(report["route_blockers"])


if __name__ == "__main__":
    unittest.main()
