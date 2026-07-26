import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_face_loop_observable_shadow.py"
)
RUNNER = (
    ROOT / "scripts/run_irregular_valence4_face_loop_observable_shadow.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_face_loop_observable_shadow",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourFaceLoopObservableShadowInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_proof_only_scope(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["production_call_shadow"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertFalse(
            report["independent_oracle_reuses_candidate_helper"]
        )
        self.assertTrue(report["nonfinite_binding_present"])
        self.assertTrue(report["complete_atomicity_binding_present"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_production_and_default_surfaces_are_untouched(self):
        report = load_inventory_module().collect(ROOT)
        self.assertFalse(report["production_or_default_surfaces_changed"])
        self.assertFalse(report["production_face_loop_called"])
        self.assertFalse(report["production_one_rings_mutated"])
        self.assertEqual(report["production_default_leaks"], [])

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
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "skipped")
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is required for the present-dependency proof",
    )
    def test_present_dependency_proves_serial_openmp_observables(self):
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
        self.assertTrue(report["source_binding_permutation_invariant"])
        self.assertTrue(
            report["duplicate_row_entries_aggregated_by_source_id"]
        )
        self.assertTrue(report["actual_openmp_team_contract_passed"])
        shadow = report["shadow"]
        self.assertTrue(shadow["serial_oracle_parity_passed"])
        self.assertTrue(shadow["actual_openmp_serial_parity_passed"])
        self.assertTrue(shadow["independent_exact_layout_sentinel_passed"])
        self.assertEqual(
            shadow["independent_raw_destination_formula"],
            "source * 9 + kind * 3 + axis",
        )
        self.assertTrue(shadow["candidate_slots_compared_raw"])
        self.assertTrue(
            shadow["candidate_collision_counts_compared_raw"]
        )
        self.assertTrue(shadow["all_collision_counts_exactly_eight"])
        self.assertEqual(
            shadow["expected_collision_count_per_component"], 8
        )
        self.assertTrue(shadow["late_malformed_face_atomic_rejection"])
        self.assertTrue(
            shadow["late_malformed_complete_shadow_state_atomic"]
        )
        self.assertTrue(
            shadow["nonfinite_output_negative_regression_passed"]
        )
        self.assertTrue(
            shadow["all_face_force_and_observable_fields_finite_checked"]
        )
        self.assertTrue(shadow["all_raw_force_slots_finite_checked"])
        self.assertTrue(shadow["all_global_fields_finite_checked"])
        self.assertTrue(
            shadow["collision_count_negative_regression_passed"]
        )
        self.assertTrue(shadow["flipped_normal_orientation_rejected"])
        self.assertFalse(shadow["production_one_rings_populated"])
        self.assertFalse(shadow["actual_production_force_path_executed"])


if __name__ == "__main__":
    unittest.main()
