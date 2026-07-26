import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT / "scripts/inventory_irregular_valence4_production_scatter_buffer.py"
)
ADAPTER = (
    ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"
)
OPENMP = (
    ROOT / "scripts/run_irregular_valence4_production_openmp_shadow.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_production_scatter_buffer", INVENTORY
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourProductionScatterBufferInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_no_production_route_caller(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["production_face_loop_caller"])
        self.assertFalse(report["production_vertex_force_state_mutated"])
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
    def test_present_dependency_scatter_and_openmp_proofs_pass(self):
        payloads = []
        for wrapper in (ADAPTER, OPENMP):
            result = subprocess.run(
                [str(wrapper), "--json", "--require-opensubdiv"],
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
            payloads.append(payload)
        composition = payloads[0]["adapter"][
            "guarded_scientific_request_composition"
        ]
        self.assertTrue(
            composition["production_shaped_source_scatter_executed"]
        )
        self.assertLessEqual(
            composition["max_production_shaped_scatter_difference"],
            1.0e-12,
        )
        shadow = payloads[1]["shadow"]
        self.assertTrue(
            shadow["production_source_keyed_component_helper_executed"]
        )
        self.assertTrue(shadow["actual_openmp_runtime_parity_passed"])


if __name__ == "__main__":
    unittest.main()
