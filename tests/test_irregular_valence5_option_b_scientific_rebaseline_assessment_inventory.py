import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT
    / "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.py"
)
WRAPPER = (
    ROOT
    / "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.sh"
)
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_option_b_scientific_rebaseline_assessment.py"
)
GLOBAL_INVENTORY = ROOT / "scripts/inventory_opensubdiv_routing_readiness.py"
POST_GATE_INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_post_option_d_architecture_gate.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical_inputs(runner):
    post_gate = {
        "status": "passed",
        "decision_selected": False,
        "selected_option": None,
        "scientific_approval_granted": False,
        "physical_rebaselining_plan_authorized": False,
    }
    force = {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_force_parity_diagnostic",
        "force_parity_passed": False,
        "relative_tolerance": runner.REVIEWED_TOLERANCE,
        "face_count": 20,
        "source_count": 12,
        "force_component_count": 2160,
        "production_route_enabled": False,
        "production_scatter_executed": False,
        "route_blockers": [runner.FORCE_BLOCKER],
        "max_abs_force_difference": runner.EXPECTED_FORCE_MAXIMA["fBend"],
        "max_abs_force_difference_by_kind": dict(
            runner.EXPECTED_FORCE_MAXIMA
        ),
    }
    composition = {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_integration_composition",
        "composed_row_parity_passed": False,
        "reviewed_absolute_tolerance": runner.REVIEWED_TOLERANCE,
        "row_component_count": 30240,
        "domain_count": 6,
        "positive_depth": 2,
        "extraordinary_vertex_mask_policy_mismatch": True,
        "mask_policy_causal_sufficiency_proven": False,
        "production_route_enabled": False,
        "production_scatter_executed": False,
        "route_blockers": [runner.ROW_BLOCKER],
        "max_abs_row_difference": runner.EXPECTED_ROW_MAXIMUM,
        "production_valence5_vertex_edge_weight": 0.075,
        "production_valence5_vertex_center_weight": 0.625,
        "opensubdiv_valence5_vertex_edge_weight": 0.08409321892578289,
        "opensubdiv_valence5_vertex_center_weight": 0.5795339053710855,
    }
    serial_openmp = {
        "status": "passed",
        "proof_kind": "approved_closed_valence5_11_control_serial_openmp_parity",
        "identity_matches": True,
        "within_tolerance": True,
        "scientific_stand_in": True,
        "scientific_stand_in_scope": "narrow_positive_depth_11_control",
        "not_broader_valence_routing": True,
        "tolerance": runner.CURRENT_SERIAL_OMP_TOLERANCE,
        "channels": {
            key: 0.0 for key in runner.EXPECTED_CURRENT_SERIAL_OMP_CHANNELS
        },
        "max_abs_difference": 0.0,
    }
    return post_gate, force, composition, serial_openmp


class IrregularValence5OptionBScientificRebaselineAssessmentTest(
    unittest.TestCase
):
    def test_canonical_assessment_binds_known_deltas_and_selects_nothing(self):
        runner = load_module(RUNNER, "option_b_canonical")
        report = runner.evaluate(
            post_gate=canonical_inputs(runner)[0],
            force_report=canonical_inputs(runner)[1],
            composition_report=canonical_inputs(runner)[2],
            current_serial_openmp_report=canonical_inputs(runner)[3],
        )
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["assessment_authorized"])
        self.assertFalse(report["option_b_selected"])
        self.assertFalse(report["stock_semantics_scientifically_approved"])
        self.assertTrue(report["physical_rebaselining_plan_proposed"])
        self.assertFalse(report["physical_rebaselining_plan_authorized"])
        self.assertFalse(report["decision_ready"])
        self.assertEqual(
            report["pending_evidence"],
            [
                "stock_energy",
                "stock_geometry",
                "stock_output",
                "stock_serial_openmp",
            ],
        )
        self.assertEqual(
            report["known_force_residuals"], runner.EXPECTED_FORCE_MAXIMA
        )
        self.assertEqual(
            report["known_row_residual"], runner.EXPECTED_ROW_MAXIMUM
        )
        self.assertEqual(report["remaining_boundary"], runner.REMAINING_BOUNDARY)

    def test_predecessor_residual_and_tolerance_drift_fail(self):
        runner = load_module(RUNNER, "option_b_drift")
        post_gate, force, composition, serial_openmp = canonical_inputs(runner)
        mutations = (
            ("force", "relative_tolerance", 1.0),
            ("force", "force_parity_passed", True),
            ("force", "max_abs_force_difference", 0.0),
            ("composition", "reviewed_absolute_tolerance", 1.0),
            ("composition", "composed_row_parity_passed", True),
            ("composition", "max_abs_row_difference", 0.0),
            ("composition", "mask_policy_causal_sufficiency_proven", True),
            ("serial", "within_tolerance", False),
            ("serial", "proof_kind", "fabricated"),
            ("serial", "tolerance", 1.0),
            ("serial", "scientific_stand_in_scope", "broader"),
        )
        for target, key, value in mutations:
            with self.subTest(target=target, key=key):
                test_force = copy.deepcopy(force)
                test_composition = copy.deepcopy(composition)
                test_serial = copy.deepcopy(serial_openmp)
                {"force": test_force, "composition": test_composition, "serial": test_serial}[
                    target
                ][key] = value
                report = runner.evaluate(
                    post_gate=post_gate,
                    force_report=test_force,
                    composition_report=test_composition,
                    current_serial_openmp_report=test_serial,
                )
                self.assertEqual(report["status"], "failed")

        for mutation in ("missing_channel", "oversized_delta", "wrong_maximum"):
            with self.subTest(mutation=mutation):
                test_serial = copy.deepcopy(serial_openmp)
                if mutation == "missing_channel":
                    test_serial["channels"].pop("face_area")
                elif mutation == "oversized_delta":
                    test_serial["channels"]["face_area"] = 2.0e-10
                    test_serial["max_abs_difference"] = 2.0e-10
                else:
                    test_serial["channels"]["face_area"] = 1.0e-14
                    test_serial["max_abs_difference"] = 0.0
                report = runner.evaluate(
                    post_gate=post_gate,
                    force_report=force,
                    composition_report=composition,
                    current_serial_openmp_report=test_serial,
                )
                self.assertEqual(report["status"], "failed")

    def test_selection_approval_implementation_and_route_false_greens_fail(self):
        runner = load_module(RUNNER, "option_b_false_green")
        post_gate, force, composition, serial_openmp = canonical_inputs(runner)
        claims = (
            {"option_b_selected": True},
            {"option_b_recommended": True},
            {"stock_semantics_scientifically_approved": True},
            {"physical_rebaselining_plan_authorized": True},
            {"implementation_work_authorized": True},
            {"production_route_enabled": True},
        )
        for claim in claims:
            with self.subTest(claim=claim):
                report = runner.evaluate(
                    post_gate=post_gate,
                    force_report=force,
                    composition_report=composition,
                    current_serial_openmp_report=serial_openmp,
                    **claim,
                )
                self.assertEqual(report["status"], "failed")

    def test_absent_wrapper_skips_cleanly(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(WRAPPER), "--json", "--check"],
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
        "OPENSUBDIV_ROOT is required for the present assessment",
    )
    def test_present_wrapper_reproduces_assessment(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--check", "--require-opensubdiv"],
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
        self.assertFalse(report["option_b_selected"])
        self.assertFalse(report["decision_ready"])

    def test_inventory_and_global_readiness_pass(self):
        for script in (INVENTORY, GLOBAL_INVENTORY, POST_GATE_INVENTORY):
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [sys.executable, str(script), "--check"],
                    cwd=ROOT,
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    result.stderr or result.stdout,
                )


if __name__ == "__main__":
    unittest.main()
