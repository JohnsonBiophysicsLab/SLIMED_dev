import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_face_observable_publication.py"
)
ADAPTER = (
    ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_face_observable_publication",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourFaceObservablePublicationInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_no_real_face_loop_caller(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertTrue(report["face_observable_publication_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertFalse(report["production_face_loop_caller"])
        self.assertFalse(report["default_dependency_changed"])
        self.assertTrue(report["backend_neutral_opensubdiv_free"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_dependency_absent_proof_skips_cleanly(self):
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
        "OPENSUBDIV_ROOT is required for present-dependency proof",
    )
    def test_present_dependency_face_publication_proof_passes(self):
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
                "default_off_face_observable_publication_rejected"
            ]
        )
        self.assertTrue(
            composition["face_observable_publication_executed"]
        )
        self.assertTrue(composition["only_face_observables_published"])
        self.assertTrue(composition["route_remained_disabled"])
        self.assertLessEqual(
            composition["max_published_face_observable_difference"],
            1.0e-12,
        )


if __name__ == "__main__":
    unittest.main()
