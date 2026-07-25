import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = (
    ROOT / "experiments/irregular_valence4_production_openmp_shadow.cpp"
)
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_production_openmp_shadow.py"
)
WRAPPER = (
    ROOT / "scripts/run_irregular_valence4_production_openmp_shadow.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_production_openmp_shadow", INVENTORY
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourProductionOpenMpShadowInventoryTest(unittest.TestCase):
    def test_inventory_passes_and_scope_is_proof_only(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["production_call_shadow"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_paths_changed"])
        self.assertFalse(report["fixture_csvs_changed"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_production_topology_and_real_openmp_are_binding(self):
        source = EXPERIMENT.read_text(encoding="utf-8")
        passed_start = source.index("const bool passed =")
        output_start = source.index("std::cout << std::setprecision", passed_start)
        passed_source = source[passed_start:output_start]
        self.assertIn("topologyIdentity", passed_source)
        self.assertIn("productionOneRingsEmpty", passed_source)
        self.assertIn("layoutOraclePassed", passed_source)
        self.assertIn("collisionCoverage", passed_source)
        self.assertIn("openMpPassed", passed_source)
        oracle_start = source.index("bool exact_layout_oracle_passed()")
        oracle_end = source.index("void print_int_array", oracle_start)
        oracle_source = source[oracle_start:oracle_end]
        self.assertIn("run_threads(sentinels, expected, 3)", oracle_source)
        self.assertIn("expectedDestination", oracle_source)
        self.assertNotIn("expected[flat_index(", oracle_source)
        self.assertIn("collisions[index] != kFaceCount", source)
        self.assertIn("#pragma omp parallel num_threads(requestedThreads)", source)
        self.assertIn("#pragma omp for schedule(static)", source)
        self.assertIn("omp_set_dynamic(0)", source)
        self.assertIn("requested{{1, 2, 3, 4, 8}}", source)
        self.assertIn("kRepeats = 5", source)

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
    def test_present_dependency_production_openmp_shadow(self):
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
        self.assertTrue(payload["proof_only"])
        self.assertTrue(payload["production_call_shadow"])
        self.assertTrue(payload["not_production_routing"])
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(payload["actual_production_force_path_executed"])
        self.assertTrue(payload["production_topology_identity_passed"])
        self.assertTrue(payload["actual_openmp_runtime_parity_passed"])

        shadow = payload["shadow"]
        self.assertFalse(shadow["production_one_rings_populated"])
        self.assertTrue(shadow["production_one_rings_expected_empty"])
        self.assertTrue(shadow["independent_exact_index_layout_oracle_passed"])
        self.assertEqual(shadow["nonzero_face_contribution_count"], 8)
        self.assertEqual(shadow["expected_collision_count_per_component"], 8)
        self.assertEqual(shadow["collision_counts"], [8] * 54)
        self.assertEqual(shadow["uncovered_component_slots"], [])
        self.assertEqual(shadow["single_contribution_component_slots"], [])
        self.assertEqual(
            shadow["unexpected_collision_count_component_slots"], []
        )
        self.assertEqual(
            [run["requested_threads"] for run in shadow["thread_runs"]],
            [1, 2, 3, 4, 8],
        )
        self.assertTrue(all(run["repeat_count"] == 5 for run in shadow["thread_runs"]))
        self.assertTrue(all(run["passed"] for run in shadow["thread_runs"]))
        self.assertTrue(shadow["passed"])


if __name__ == "__main__":
    unittest.main()
