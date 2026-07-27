import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT / "scripts/inventory_irregular_valence4_vertex_force_publication.py"
)
ADAPTER = (
    ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"
)
OPENMP = (
    ROOT / "scripts/run_irregular_valence4_production_openmp_shadow.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_vertex_force_publication", INVENTORY
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourVertexForcePublicationInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_no_real_face_loop_caller(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertTrue(report["vertex_force_publication_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertFalse(report["production_face_loop_caller"])
        self.assertFalse(report["default_dependency_changed"])
        self.assertTrue(report["backend_neutral_opensubdiv_free"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_dependency_absent_proofs_skip_cleanly(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        for wrapper in (ADAPTER, OPENMP):
            result = subprocess.run(
                [str(wrapper), "--json"],
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
        "OPENSUBDIV_ROOT is required for present-dependency proofs",
    )
    def test_present_dependency_publication_proofs_pass(self):
        adapter_result = subprocess.run(
            [str(ADAPTER), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(adapter_result.returncode, 0, adapter_result.stderr)
        adapter = json.loads(adapter_result.stdout)
        self.assertEqual(adapter["status"], "passed")
        composition = adapter["adapter"][
            "guarded_scientific_request_composition"
        ]
        self.assertTrue(
            composition["default_off_vertex_force_publication_rejected"]
        )
        self.assertTrue(composition["vertex_force_publication_executed"])
        self.assertTrue(
            composition["only_membrane_force_families_published"]
        )
        self.assertLessEqual(
            composition["max_published_force_difference"], 1.0e-12
        )

        openmp_result = subprocess.run(
            [str(OPENMP), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(openmp_result.returncode, 0, openmp_result.stderr)
        openmp = json.loads(openmp_result.stdout)
        self.assertEqual(openmp["status"], "passed")
        shadow = openmp["shadow"]
        self.assertTrue(shadow["vertex_force_publication_executed"])
        self.assertTrue(
            shadow[
                "vertex_force_publication_overwrites_only_membrane_families"
            ]
        )
        self.assertTrue(
            all(
                run["vertex_force_publication_executed"]
                and run["max_abs_vertex_force_publication_difference"]
                <= 1.0e-12
                for run in shadow["thread_runs"]
            )
        )


if __name__ == "__main__":
    unittest.main()
