import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT
    / "scripts/run_irregular_valence5_opensubdiv_custom_scheme_feasibility.py"
)
WRAPPER = (
    ROOT
    / "scripts/run_irregular_valence5_opensubdiv_custom_scheme_feasibility.sh"
)
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_opensubdiv_custom_scheme_feasibility.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def predecessor_payload(runner):
    return {
        "status": "passed",
        "proof_kind": "valence5_opensubdiv_mask_counterfactual_capability",
        "reviewed_absolute_tolerance": runner.REVIEWED_ROW_TOLERANCE,
        "mask_policy_causal_sufficiency_proven": False,
        "scientifically_approved": False,
        "production_route_enabled": False,
        "counterfactual": {
            "evaluator_bound": False,
            "row_component_count": 0,
        },
    }


def api_payload(runner):
    return {
        "detected_opensubdiv_version_number": (
            runner.EXPECTED_OPENSUBDIV_VERSION_NUMBER
        ),
        "detected_opensubdiv_version": runner.EXPECTED_OPENSUBDIV_VERSION,
        "version_number_matches_reviewed_api": True,
        "scheme_type_values": runner.EXPECTED_SCHEME_TYPES,
        "scheme_type_set_matches_reviewed_api": True,
        "scheme_template_parameter_is_scheme_type": True,
        "loop_scheme_is_fixed_specialization": True,
        "topology_refiner_accepts_scheme_type": True,
        "topology_factory_scheme_type_field": True,
        "public_scheme_registration_tokens": [],
        "public_scheme_registration_hook_available": False,
        "public_custom_mask_setters": [],
        "public_custom_mask_injection_available": False,
    }


def api_sources(runner):
    return {
        "version_source": (
            "#define OPENSUBDIV_VERSION_NUMBER "
            f"{runner.EXPECTED_OPENSUBDIV_VERSION_NUMBER}\n"
        ),
        "types_source": (
            "enum SchemeType { SCHEME_BILINEAR, SCHEME_CATMARK, SCHEME_LOOP };\n"
        ),
        "options_source": "class Options { public: void SetCreasingMethod(); };\n",
        "scheme_source": "template <SchemeType SCHEME_TYPE>\nclass Scheme {};\n",
        "loop_source": (
            "void Scheme<SCHEME_LOOP>::assignSmoothMaskForVertex() {}\n"
        ),
        "topology_refiner_source": (
            "class TopologyRefiner {\n"
            " public:\n"
            "  TopologyRefiner(Sdc::SchemeType type);\n"
            "};\n"
        ),
        "topology_factory_source": (
            "struct Options { Sdc::SchemeType schemeType; };\n"
        ),
    }


class ValenceFiveCustomSchemeFeasibilityInventoryTest(unittest.TestCase):
    def test_inventory_passes(self):
        report = load_module(INVENTORY, "val5_custom_inventory").collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertEqual(report["forbidden_stale_claims"]["located"], 0)
        self.assertFalse(report["valid_standalone_public_extension_path_exists"])
        self.assertFalse(report["evaluator_bound_slimed_mask_rows_generated"])

    def test_false_extension_and_post_hoc_claims_are_binding(self):
        runner = load_module(RUNNER, "val5_custom_false_claims")
        for claim in (
            {"asserted_public_extension": True},
            {"post_hoc_rows_supplied": True},
        ):
            with self.subTest(claim=claim):
                report = runner._build_report(
                    predecessor_payload(runner),
                    api_payload(runner),
                    **claim,
                )
                self.assertEqual(report["status"], "failed")
                self.assertFalse(
                    report["valid_standalone_public_extension_path_exists"]
                )
                self.assertFalse(report["evaluator_bound_slimed_mask_rows_generated"])

    def test_scientific_choice_and_vendoring_claims_are_binding(self):
        runner = load_module(RUNNER, "val5_custom_policy_claims")
        for claim in (
            {"scientific_mask_selected": True},
            {"library_patch_or_vendor_requested": True},
        ):
            with self.subTest(claim=claim):
                report = runner._build_report(
                    predecessor_payload(runner),
                    api_payload(runner),
                    **claim,
                )
                self.assertEqual(report["status"], "failed")
                self.assertFalse(report["scientifically_approved"])
                self.assertFalse(report["library_patch_or_vendoring_performed"])

    def test_public_scheme_set_drift_is_binding(self):
        runner = load_module(RUNNER, "val5_custom_api_drift")
        api = api_payload(runner)
        api["scheme_type_values"] = runner.EXPECTED_SCHEME_TYPES + ["SCHEME_CUSTOM"]
        api["scheme_type_set_matches_reviewed_api"] = False
        report = runner._build_report(predecessor_payload(runner), api)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["errors"])

    def test_public_mask_hooks_outside_options_are_binding(self):
        runner = load_module(RUNNER, "val5_custom_cross_surface_hooks")
        for surface in (
            "scheme_source",
            "topology_refiner_source",
            "topology_factory_source",
        ):
            with self.subTest(surface=surface):
                sources = api_sources(runner)
                sources[surface] += "\npublic: void SetSmoothMaskWeights();\n"
                api = runner.public_extension_evidence(**sources)
                self.assertTrue(api["public_custom_mask_injection_available"])
                self.assertIn(
                    "SetSmoothMaskWeights",
                    api["public_custom_mask_setters"],
                )
                report = runner._build_report(predecessor_payload(runner), api)
                self.assertEqual(report["status"], "failed")
                self.assertIn(
                    "OpenSubdiv public mask-injection surface changed",
                    report["errors"],
                )

    def test_version_drift_and_missing_version_are_binding(self):
        runner = load_module(RUNNER, "val5_custom_version_drift")
        for version_source in (
            "#define OPENSUBDIV_VERSION_NUMBER 30701\n",
            "#define OPENSUBDIV_VERSION_MAJOR 3\n",
        ):
            with self.subTest(version_source=version_source):
                sources = api_sources(runner)
                sources["version_source"] = version_source
                api = runner.public_extension_evidence(**sources)
                self.assertFalse(api["version_number_matches_reviewed_api"])
                report = runner._build_report(predecessor_payload(runner), api)
                self.assertEqual(report["status"], "failed")
                self.assertTrue(
                    any("version_number_matches_reviewed_api" in error for error in report["errors"])
                )

    def test_predecessor_contract_drift_is_binding(self):
        runner = load_module(RUNNER, "val5_custom_predecessor_drift")
        for key, value in (
            ("reviewed_absolute_tolerance", 1.0),
            ("mask_policy_causal_sufficiency_proven", True),
            ("scientifically_approved", True),
            ("production_route_enabled", True),
        ):
            with self.subTest(key=key):
                predecessor = predecessor_payload(runner)
                predecessor[key] = value
                report = runner._build_report(
                    predecessor,
                    api_payload(runner),
                )
                self.assertEqual(report["status"], "failed")

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
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "skipped")
        self.assertTrue(report["not_production_routing"])

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is not configured for this test process",
    )
    def test_present_dependency_reports_exact_architecture_blocker(self):
        runner = load_module(RUNNER, "val5_custom_present")
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
        self.assertEqual(
            report["public_api_evidence"][
                "detected_opensubdiv_version_number"
            ],
            runner.EXPECTED_OPENSUBDIV_VERSION_NUMBER,
        )
        self.assertEqual(
            report["public_api_evidence"]["detected_opensubdiv_version"],
            runner.EXPECTED_OPENSUBDIV_VERSION,
        )
        self.assertTrue(
            report["public_api_evidence"]["version_number_matches_reviewed_api"]
        )
        self.assertEqual(
            report["public_api_evidence"]["scheme_type_values"],
            runner.EXPECTED_SCHEME_TYPES,
        )
        self.assertFalse(
            report["public_api_evidence"][
                "public_scheme_registration_hook_available"
            ]
        )
        self.assertFalse(
            report["public_api_evidence"]["public_custom_mask_injection_available"]
        )
        self.assertFalse(report["valid_standalone_public_extension_path_exists"])
        self.assertFalse(report["custom_scheme_adapter_constructed"])
        self.assertFalse(report["evaluator_bound_slimed_mask_rows_generated"])
        self.assertEqual(report["evaluator_bound_row_component_count"], 0)
        self.assertTrue(report["false_claim_negative_gates_passed"])
        self.assertFalse(report["mask_policy_causal_sufficiency_proven"])
        self.assertFalse(report["scientifically_approved"])
        self.assertEqual(report["route_blockers"], [runner.PUBLIC_EXTENSION_BLOCKER])


if __name__ == "__main__":
    unittest.main()
