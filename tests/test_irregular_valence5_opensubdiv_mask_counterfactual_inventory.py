import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT
    / "scripts/run_irregular_valence5_opensubdiv_mask_counterfactual.py"
)
WRAPPER = (
    ROOT
    / "scripts/run_irregular_valence5_opensubdiv_mask_counterfactual.sh"
)
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_opensubdiv_mask_counterfactual.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def baseline_payload(runner):
    return {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_integration_composition",
        "row_shape": runner.ROW_SHAPE,
        "row_component_count": runner.ROW_COMPONENT_COUNT,
        "reviewed_absolute_tolerance": runner.REVIEWED_ROW_TOLERANCE,
        "face_orientation_bound_by_source_identity": True,
        "affine_domain_plan_matches_reviewed": True,
        "production_scatter_executed": False,
        "composed_row_parity_passed": False,
        "max_abs_row_difference": runner.BASELINE_MAX_ABS_ROW_DIFFERENCE,
        "production_valence5_vertex_edge_weight": 0.075,
        "production_valence5_vertex_center_weight": 0.625,
        "opensubdiv_valence5_vertex_edge_weight": 0.08409321892578289,
        "opensubdiv_valence5_vertex_center_weight": 0.5795339053710855,
    }


def api_payload(runner):
    return {
        "options_declares_all_supported_scheme_options": True,
        "public_option_setters": runner.EXPECTED_PUBLIC_SETTERS,
        "public_option_setters_match_reviewed_api": True,
        "public_custom_smooth_mask_setters": [],
        "public_custom_smooth_mask_override_available": False,
        "loop_smooth_mask_formula_anchors": {"all": True},
        "loop_smooth_mask_formula_embedded": True,
    }


class ValenceFiveMaskCounterfactualInventoryTest(unittest.TestCase):
    def test_inventory_passes(self):
        report = load_module(INVENTORY, "val5_mask_inventory").collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertEqual(report["forbidden_stale_claims"]["located"], 0)
        self.assertFalse(report["counterfactual_evaluator_bound"])
        self.assertIsNone(report["counterfactual_row_parity_passed"])
        self.assertFalse(report["scientifically_approved"])

    def test_reporting_only_mask_mutation_is_rejected(self):
        runner = load_module(RUNNER, "val5_mask_reporting_mutation")
        report = runner._build_report(
            baseline_payload(runner),
            api_payload(runner),
            reporting_only_mask=runner.SLIMED_MASK,
        )
        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["reporting_only_mask_mutation_requested"])
        self.assertFalse(report["reporting_only_mask_mutation_accepted"])
        self.assertFalse(report["counterfactual"]["evaluator_bound"])
        self.assertEqual(report["counterfactual"]["row_component_count"], 0)
        self.assertIsNone(report["counterfactual"]["row_parity_passed"])
        self.assertIn(
            "reporting-only mask mutation cannot create an evaluator-bound "
            "counterfactual",
            report["errors"],
        )

    def test_public_options_drift_is_binding(self):
        runner = load_module(RUNNER, "val5_mask_public_api")
        options = """
        /// All supported options applying to subdivision scheme.
        class Options {
          void SetVtxBoundaryInterpolation(int);
          void SetFVarLinearInterpolation(int);
          void SetCreasingMethod(int);
          void SetTriangleSubdivision(int);
          void SetSmoothMaskWeights(double, double);
        };
        """
        loop = "\n".join(
            [
                "Scheme<SCHEME_LOOP>::assignSmoothMaskForVertex",
                "double beta = 0.25f * cosTheta + 0.375f;",
                "eWeight = (Weight) ((0.625f - (beta * beta)) * invValence);",
                "vWeight = (Weight) (1.0f - (eWeight * dValence));",
            ]
        )
        api = runner.public_api_evidence(options, loop)
        self.assertTrue(api["public_custom_smooth_mask_override_available"])
        self.assertEqual(
            api["public_custom_smooth_mask_setters"],
            ["SetSmoothMaskWeights"],
        )
        report = runner._build_report(baseline_payload(runner), api)
        self.assertEqual(report["status"], "failed")
        self.assertIn("OpenSubdiv public scheme-options API drift", report["errors"])

    def test_baseline_contract_mutations_are_binding(self):
        runner = load_module(RUNNER, "val5_mask_baseline_contract")
        mutations = [
            ("row_component_count", runner.ROW_COMPONENT_COUNT - 1),
            ("reviewed_absolute_tolerance", 1.0),
            ("face_orientation_bound_by_source_identity", False),
            ("affine_domain_plan_matches_reviewed", False),
            ("production_valence5_vertex_edge_weight", 0.0),
            ("opensubdiv_valence5_vertex_center_weight", 0.0),
            ("max_abs_row_difference", 0.0),
        ]
        for key, value in mutations:
            with self.subTest(key=key):
                baseline = baseline_payload(runner)
                baseline[key] = value
                report = runner._build_report(baseline, api_payload(runner))
                self.assertEqual(report["status"], "failed")
                self.assertTrue(report["errors"])

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
        self.assertNotIn("counterfactual", result.stdout)
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
    def test_present_dependency_reports_exact_api_blocker(self):
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
        self.assertEqual(report["baseline"]["row_component_count"], 30240)
        self.assertFalse(report["baseline"]["composed_row_parity_passed"])
        self.assertEqual(
            report["baseline"]["max_abs_row_difference"],
            0.7357563654581705,
        )
        self.assertEqual(report["reviewed_absolute_tolerance"], 5.0e-6)
        self.assertFalse(report["counterfactual"]["evaluator_bound"])
        self.assertEqual(report["counterfactual"]["row_component_count"], 0)
        self.assertIsNone(report["counterfactual"]["row_parity_passed"])
        self.assertTrue(
            report["reporting_only_mask_mutation_negative_gate_passed"]
        )
        self.assertFalse(report["mask_policy_causal_sufficiency_proven"])
        self.assertFalse(report["scientifically_approved"])
        self.assertEqual(
            report["route_blockers"],
            [runner_blocker()],
        )


def runner_blocker():
    runner = load_module(RUNNER, "val5_mask_blocker")
    return runner.PUBLIC_API_BLOCKER


if __name__ == "__main__":
    unittest.main()
