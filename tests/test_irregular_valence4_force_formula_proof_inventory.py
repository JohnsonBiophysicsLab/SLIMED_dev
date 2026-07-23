import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "scripts/inventory_irregular_valence4_force_formula_proof.py"
PROBE = ROOT / "scripts/probe_opensubdiv_feasibility.py"
WRAPPER = (
    ROOT / "scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_force_formula_proof", INVENTORY
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourForceFormulaProofInventoryTest(unittest.TestCase):
    def test_inventory_passes_and_scope_is_proof_only(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["approved_for_mapping_sample_transpose_proof"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["force_formula_proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["scientifically_approved"])
        self.assertFalse(report["fixture_csvs_changed"])
        self.assertFalse(report["production_paths_changed"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])

    def test_mapping_mixed_rows_are_a_binding_pass_condition(self):
        source = PROBE.read_text(encoding="utf-8")
        start = source.index("static bool print_valence4_mapping_proof(")
        end = source.index("static bool print_valence4_force_formula_proof(", start)
        mapping_source = source[start:end]
        self.assertIn("bool allMixedRowsIdentical = true;", mapping_source)
        self.assertIn(
            "allMixedRowsIdentical &&\n        sourceCoveragePassed",
            mapping_source,
        )

    def test_scalar_oracle_does_not_call_force_evaluator(self):
        source = PROBE.read_text(encoding="utf-8")
        start = source.index(
            "static Valence4ScalarEnergies evaluate_valence4_scalar_energies("
        )
        end = source.index(
            "static double valence4_energy_component(", start
        )
        oracle_source = source[start:end]
        self.assertNotIn("accumulate_valence4_formula_sample", oracle_source)
        self.assertNotIn("evaluate_valence4_formula(", oracle_source)

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
    def test_present_dependency_force_formula_proof(self):
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
        self.assertTrue(payload["regular_formula_bridge_passed"])
        self.assertTrue(payload["deterministic_energy_force_repeat_match"])
        self.assertTrue(payload["proof_passed"])
        self.assertTrue(payload["proof_only"])
        self.assertTrue(payload["force_formula_proof_only"])
        self.assertTrue(payload["not_production_routing"])
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(payload["scientifically_approved"])

        proof = payload["proof"]
        self.assertEqual(proof["sample_count"], 24)
        self.assertEqual(len(proof["sample_evidence"]), 24)
        self.assertEqual(
            [row["source_id"] for row in proof["source_forces"]],
            list(range(6)),
        )
        self.assertTrue(
            proof["source_force_contract"][
                "every_source_has_nonzero_vector_for_each_force_kind"
            ]
        )
        self.assertTrue(proof["duplicate_aggregation"]["passed"])
        oracle = proof["finite_difference_oracle"]
        self.assertEqual(oracle["unique_source_axis_comparisons"], 54)
        self.assertTrue(oracle["all_54_source_axis_comparisons_passed"])
        for kind in ("bending", "area", "volume"):
            self.assertEqual(len(oracle[kind]["steps"]), 5)
            self.assertTrue(oracle[kind]["plateau_passed"])
            self.assertTrue(oracle[kind]["passed"])
            self.assertTrue(
                proof["rigid_motion_invariance"][kind][
                    "translation_invariance_passed"
                ]
            )
            self.assertTrue(
                proof["rigid_motion_invariance"][kind][
                    "rotation_invariance_passed"
                ]
            )
        self.assertIn(
            "not equivalent to the legacy visible-volume",
            proof["energies"]["volume_output_disclaimer"],
        )


if __name__ == "__main__":
    unittest.main()
