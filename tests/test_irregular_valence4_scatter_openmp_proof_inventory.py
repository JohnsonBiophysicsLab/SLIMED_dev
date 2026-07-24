import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts/probe_opensubdiv_feasibility.py"
INVENTORY = (
    ROOT / "scripts/inventory_irregular_valence4_scatter_openmp_proof.py"
)
WRAPPER = (
    ROOT / "scripts/run_irregular_valence4_opensubdiv_scatter_openmp_proof.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_scatter_openmp_proof", INVENTORY
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourScatterOpenMpProofInventoryTest(unittest.TestCase):
    def test_inventory_passes_and_scope_is_proof_only(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["scatter_openmp_shape_proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["scientifically_approved"])
        self.assertFalse(report["production_paths_changed"])
        self.assertFalse(report["fixture_csvs_changed"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])

    def test_scatter_openmp_result_is_a_binding_pass_condition(self):
        source = PROBE.read_text(encoding="utf-8")
        start = source.index("static bool print_valence4_force_formula_proof(")
        end = source.index("static int run_case(", start)
        proof_source = source[start:end]
        self.assertIn(
            "invariancePassed && scatterOpenMp.passed;",
            proof_source,
        )
        self.assertIn(
            '\\"passed\\":"\n'
            '              << (scatterOpenMp.passed ? "true" : "false")',
            proof_source,
        )

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
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "skipped")
        self.assertIn("OPENSUBDIV_ROOT is not set", payload["reason"])

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is not configured for this test process",
    )
    def test_present_dependency_scatter_openmp_shape_proof(self):
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
        self.assertTrue(payload["scatter_openmp_shape_passed"])
        self.assertTrue(payload["deterministic_energy_force_repeat_match"])
        self.assertTrue(payload["proof_only"])
        self.assertTrue(payload["scatter_openmp_shape_proof_only"])
        self.assertTrue(payload["not_production_routing"])
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(payload["scientifically_approved"])
        self.assertFalse(payload["actual_face_one_ring_scatter_proven"])
        self.assertFalse(payload["actual_openmp_runtime_proven"])

        proof = payload["proof"]
        self.assertEqual(proof["face_contribution_count"], 8)
        self.assertEqual(proof["source_count"], 6)
        self.assertEqual(proof["force_components_per_source"], 9)
        self.assertEqual(proof["total_force_components"], 54)
        self.assertEqual(proof["sources_with_multi_face_collisions"], 6)
        self.assertTrue(proof["collision_coverage_passed"])
        self.assertTrue(proof["source_order_passed"])
        self.assertTrue(proof["matches_nine_component_scatter_shape"])
        self.assertTrue(
            proof["matches_simulated_serial_openmp_accumulation"]
        )
        self.assertTrue(
            proof["duplicate_aggregation_preserves_scatter"]
        )
        self.assertTrue(proof["passed"])


if __name__ == "__main__":
    unittest.main()
