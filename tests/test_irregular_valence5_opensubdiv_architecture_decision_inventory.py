import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT / "scripts/run_irregular_valence5_opensubdiv_architecture_decision.py"
)
WRAPPER = (
    ROOT / "scripts/run_irregular_valence5_opensubdiv_architecture_decision.sh"
)
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_opensubdiv_architecture_decision.py"
)
GLOBAL_INVENTORY = ROOT / "scripts/inventory_opensubdiv_routing_readiness.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def feasibility_payload(runner):
    return {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_custom_scheme_feasibility",
        "public_api_evidence": {
            "detected_opensubdiv_version_number": 30700,
            "detected_opensubdiv_version": "3.7.0",
            "version_number_matches_reviewed_api": True,
            "public_scheme_registration_hook_available": False,
            "public_custom_mask_injection_available": False,
        },
        "valid_standalone_public_extension_path_exists": False,
        "evaluator_bound_slimed_mask_rows_generated": False,
        "evaluator_bound_row_component_count": 0,
        "mask_policy_causal_sufficiency_proven": False,
        "scientifically_approved": False,
        "production_route_enabled": False,
        "route_blockers": [runner.PUBLIC_EXTENSION_BLOCKER],
    }


def force_payload(runner):
    return {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_force_parity_diagnostic",
        "force_parity_passed": False,
        "max_abs_force_difference": runner.EXPECTED_MAX_ABS_FORCE_DIFFERENCE,
        "relative_tolerance": runner.REVIEWED_ABSOLUTE_TOLERANCE,
        "route_blockers": [runner.FORCE_PARITY_BLOCKER],
        "production_route_enabled": False,
        "production_scatter_executed": False,
    }


class IrregularValence5OpenSubdivArchitectureDecisionTest(unittest.TestCase):
    def test_inventory_passes(self):
        result = subprocess.run(
            [str(INVENTORY), "--json", "--check"],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertEqual(report["forbidden_stale_claims"]["located"], 0)

    def test_exact_ordered_unselected_options_pass(self):
        runner = load_module(RUNNER, "val5_architecture_canonical")
        report = runner.evaluate(
            feasibility_payload(runner),
            force_payload(runner),
        )
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(
            [option["id"] for option in report["decision_options"]],
            ["A", "B", "C", "D"],
        )
        self.assertTrue(
            all(
                option["status"] == "unselected"
                for option in report["decision_options"]
            )
        )
        self.assertFalse(report["decision_selected"])
        self.assertIsNone(report["selected_option"])
        self.assertFalse(report["scientifically_approved"])
        self.assertFalse(report["dependency_policy_changed"])
        self.assertFalse(report["library_patch_or_vendoring_performed"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["valence5_opensubdiv_route_enabled"])
        self.assertTrue(report["current_slimed_valence5_route_preserved"])
        self.assertFalse(
            report["current_fallback_is_selected_opensubdiv_architecture"]
        )
        self.assertTrue(report["option_contract_negative_gates_passed"])
        self.assertTrue(report["policy_claim_negative_gates_passed"])

    def test_missing_duplicate_unknown_reordered_and_preferred_options_fail(self):
        runner = load_module(RUNNER, "val5_architecture_option_drift")
        canonical = [dict(option) for option in runner.CANONICAL_OPTIONS]
        cases = (
            canonical[:-1],
            [canonical[0], *canonical],
            [*canonical[:-1], {**canonical[-1], "id": "E"}],
            [canonical[1], canonical[0], *canonical[2:]],
            [{**canonical[0], "preferred": True}, *canonical[1:]],
        )
        for options in cases:
            with self.subTest(options=[option["id"] for option in options]):
                report = runner._build_report(
                    feasibility_payload(runner),
                    force_payload(runner),
                    options=options,
                )
                self.assertEqual(report["status"], "failed")
                self.assertTrue(report["errors"])

    def test_policy_and_route_false_claims_fail(self):
        runner = load_module(RUNNER, "val5_architecture_false_claims")
        cases = (
            {"recommendation_language_present": True},
            {"decision_selected": True, "selected_option": "A"},
            {"scientifically_approved": True},
            {"library_patch_or_vendoring_performed": True},
            {"alternate_library_selected": True},
            {"dependency_policy_changed": True},
            {"production_route_enabled": True},
            {"valence5_opensubdiv_route_enabled": True},
            {"current_slimed_valence5_route_preserved": False},
        )
        for claim in cases:
            with self.subTest(claim=claim):
                report = runner._build_report(
                    feasibility_payload(runner),
                    force_payload(runner),
                    **claim,
                )
                self.assertEqual(report["status"], "failed")
                self.assertTrue(report["errors"])

    def test_pr148_and_force_predecessor_drift_fail(self):
        runner = load_module(RUNNER, "val5_architecture_predecessor_drift")
        feasibility_cases = (
            ("detected_opensubdiv_version_number", 30701, "api"),
            ("public_scheme_registration_hook_available", True, "api"),
            ("public_custom_mask_injection_available", True, "api"),
            ("evaluator_bound_row_component_count", 1, "root"),
            ("mask_policy_causal_sufficiency_proven", True, "root"),
            ("production_route_enabled", True, "root"),
        )
        for key, value, location in feasibility_cases:
            with self.subTest(feasibility_key=key):
                feasibility = feasibility_payload(runner)
                if location == "api":
                    feasibility["public_api_evidence"][key] = value
                else:
                    feasibility[key] = value
                report = runner._build_report(
                    feasibility,
                    force_payload(runner),
                )
                self.assertEqual(report["status"], "failed")

        force_cases = (
            ("force_parity_passed", True),
            ("max_abs_force_difference", 0.0),
            ("relative_tolerance", 1.0),
            ("production_route_enabled", True),
            ("production_scatter_executed", True),
        )
        for key, value in force_cases:
            with self.subTest(force_key=key):
                force = force_payload(runner)
                force[key] = value
                report = runner._build_report(
                    feasibility_payload(runner),
                    force,
                )
                self.assertEqual(report["status"], "failed")

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
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "skipped")
        self.assertEqual(
            [option["id"] for option in report["decision_options"]],
            ["A", "B", "C", "D"],
        )
        self.assertTrue(
            all(
                option["status"] == "unselected"
                for option in report["decision_options"]
            )
        )
        self.assertFalse(report["decision_selected"])
        self.assertIsNone(report["selected_option"])
        self.assertFalse(report["scientifically_approved"])
        self.assertFalse(report["dependency_policy_changed"])
        self.assertFalse(report["library_patch_or_vendoring_performed"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["valence5_opensubdiv_route_enabled"])
        self.assertTrue(report["current_slimed_valence5_route_preserved"])

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is not configured for this test process",
    )
    def test_present_dependency_reproduces_exact_decision(self):
        runner = load_module(RUNNER, "val5_architecture_present")
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
        facts = report["reviewed_facts"]
        self.assertEqual(facts["detected_opensubdiv_version_number"], 30700)
        self.assertEqual(facts["detected_opensubdiv_version"], "3.7.0")
        self.assertFalse(facts["public_scheme_registration_hook_available"])
        self.assertFalse(facts["public_custom_mask_injection_available"])
        self.assertEqual(facts["evaluator_bound_row_component_count"], 0)
        self.assertFalse(facts["mask_policy_causal_sufficiency_proven"])
        self.assertFalse(facts["force_parity_passed"])
        self.assertEqual(
            facts["max_abs_force_difference"],
            runner.EXPECTED_MAX_ABS_FORCE_DIFFERENCE,
        )
        self.assertFalse(report["decision_selected"])
        self.assertIsNone(report["selected_option"])
        self.assertTrue(report["current_slimed_valence5_route_preserved"])

    def test_stale_decision_claims_fail_global_readiness(self):
        global_inventory = load_module(
            GLOBAL_INVENTORY,
            "val5_architecture_global_readiness",
        )
        claims = [
            claim
            for claim in global_inventory.FORBIDDEN_READINESS_CLAIMS
            if claim.name.startswith("valence-5 architecture")
        ]
        self.assertGreaterEqual(len(claims), 5)
        for claim in claims:
            with self.subTest(claim=claim.name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    path = root / claim.path
                    path.parent.mkdir(parents=True)
                    path.write_text(f"{claim.needle}\n", encoding="utf-8")
                    located = global_inventory.collect_forbidden_claims(root)
                self.assertEqual(len(located), 1)
                self.assertEqual(located[0].claim.name, claim.name)


if __name__ == "__main__":
    unittest.main()
