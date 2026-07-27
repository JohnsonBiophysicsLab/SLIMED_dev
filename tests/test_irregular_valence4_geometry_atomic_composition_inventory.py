import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_geometry_atomic_composition.py"
)
ADAPTER = (
    ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_geometry_atomic_composition",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourGeometryAtomicCompositionInventoryTest(
    unittest.TestCase
):
    def test_inventory_passes_without_caller_or_route(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["geometry_aware_atomic_composition"])
        self.assertTrue(
            report["staged_geometry_used_for_scientific_evaluation"]
        )
        self.assertTrue(report["atomic_geometry_scientific_publication"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertFalse(report["default_evaluator_caller"])
        self.assertFalse(report["production_face_loop_caller"])
        self.assertFalse(report["default_dependency_changed"])
        self.assertTrue(report["backend_neutral_opensubdiv_free"])
        self.assertEqual(
            report["anchors"]["located"],
            report["anchors"]["expected"],
        )

    def test_dependency_absent_adapter_skips_cleanly(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(ADAPTER), "--json"],
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
        "OPENSUBDIV_ROOT is required for present-dependency composition proof",
    )
    def test_present_dependency_rows_pass_atomic_composition(self):
        result = subprocess.run(
            [str(ADAPTER), "--json", "--require-opensubdiv"],
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
        composition = payload["adapter"][
            "guarded_scientific_request_composition"
        ]
        self.assertTrue(
            composition[
                "default_off_geometry_aware_composition_rejected"
            ]
        )
        self.assertTrue(
            composition["geometry_aware_atomic_composition_executed"]
        )
        self.assertTrue(
            composition[
                "staged_geometry_used_for_scientific_evaluation"
            ]
        )
        self.assertTrue(composition["stale_mesh_globals_ignored"])
        self.assertTrue(
            composition[
                "only_reviewed_geometry_scientific_families_published_atomically"
            ]
        )
        self.assertLessEqual(
            composition["max_geometry_aware_force_difference"],
            1.0e-12,
        )
        self.assertLessEqual(
            composition[
                "max_geometry_aware_face_observable_difference"
            ],
            1.0e-12,
        )
        self.assertLessEqual(
            composition["max_geometry_aware_geometry_difference"],
            1.0e-12,
        )
        self.assertTrue(composition["route_remained_disabled"])


if __name__ == "__main__":
    unittest.main()
