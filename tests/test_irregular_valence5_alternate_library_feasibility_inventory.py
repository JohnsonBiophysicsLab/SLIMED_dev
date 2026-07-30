import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_irregular_valence5_alternate_library_feasibility.py"
WRAPPER = ROOT / "scripts/run_irregular_valence5_alternate_library_feasibility.sh"
INVENTORY = (
    ROOT / "scripts/inventory_irregular_valence5_alternate_library_feasibility.py"
)
GLOBAL_INVENTORY = ROOT / "scripts/inventory_opensubdiv_routing_readiness.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class IrregularValence5AlternateLibraryFeasibilityTest(unittest.TestCase):
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
        self.assertEqual(report["forbidden_claims"]["located"], 0)

    def test_canonical_report_passes_without_selection(self):
        runner = load_module(RUNNER, "altlib_canonical")
        report = runner.evaluate()
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(
            report["candidate_ids"],
            ["cgal", "libigl", "openmesh", "pmp-library"],
        )
        self.assertEqual(report["viable_candidate_ids"], [])
        self.assertEqual(report["architecture_option_authorized_for_investigation"], "D")
        self.assertTrue(report["alternate_library_feasibility_lane_authorized"])
        self.assertEqual(report["authorization_scope"], "observational_feasibility_only")
        self.assertFalse(report["predecessor_decision_selected"])
        self.assertIsNone(report["predecessor_selected_option"])
        self.assertEqual(set(report["predecessor_option_statuses"].values()), {"unselected"})
        self.assertFalse(report["investigation_authorization_is_architecture_selection"])
        self.assertFalse(report["library_selected"])
        self.assertIsNone(report["selected_library"])
        self.assertIsNone(report["preferred_candidate"])
        self.assertTrue(report["installability_not_executed"])
        for candidate in report["candidates"]:
            self.assertNotIn("installable", candidate)
            self.assertEqual(
                candidate["installability_evidence"],
                "official_documentation_and_release_source",
            )
            self.assertFalse(candidate["installability_probe_executed"])
            self.assertFalse(candidate["compile_link_probe_passed"])
        self.assertTrue(report["current_slimed_valence5_fallback_preserved"])

    def test_missing_duplicate_reordered_and_unknown_candidates_fail(self):
        runner = load_module(RUNNER, "altlib_candidate_set")
        canonical = copy.deepcopy(list(runner.CANONICAL_CANDIDATES))
        cases = (
            canonical[:-1],
            [canonical[0], *canonical],
            [canonical[1], canonical[0], *canonical[2:]],
            [*canonical[:-1], {**canonical[-1], "id": "unknown"}],
        )
        for candidates in cases:
            with self.subTest(ids=[candidate["id"] for candidate in candidates]):
                report = runner.evaluate(candidates=candidates)
                self.assertEqual(report["status"], "failed")
                self.assertTrue(report["errors"])

    def test_capability_and_source_metadata_drift_fail(self):
        runner = load_module(RUNNER, "altlib_metadata_drift")
        mutations = (
            ("version", "future"),
            ("release_or_commit", "0" * 40),
            ("release_url", "https://example.invalid/release"),
            ("source_archive_url", "https://example.invalid/source"),
            ("archive_sha256", "0" * 64),
            ("license", "Unknown"),
            ("license_url", "https://example.invalid/license"),
            ("cpp_minimum", "unknown"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                candidates = copy.deepcopy(list(runner.CANONICAL_CANDIDATES))
                candidates[0][key] = value
                report = runner.evaluate(candidates=candidates)
                self.assertEqual(report["status"], "failed")

        candidates = copy.deepcopy(list(runner.CANONICAL_CANDIDATES))
        candidates[0]["api_evidence"][0]["anchor"] = "fabricated capability"
        self.assertEqual(runner.evaluate(candidates=candidates)["status"], "failed")

    def test_refinement_limit_and_derivative_false_greens_fail(self):
        runner = load_module(RUNNER, "altlib_false_green")
        cases = (
            ("exact_limit_surface_evaluation", True),
            ("first_parametric_derivatives", True),
            ("second_parametric_derivatives", True),
            ("public_custom_mask_scheme_evaluator_seam", True),
            ("evaluator_bound_custom_rows", True),
            ("source_identity_order_cardinality_compatible", True),
            ("chain_rule_compatible", True),
            ("post_hoc_row_substitution_required", True),
        )
        for key, value in cases:
            with self.subTest(key=key):
                candidates = copy.deepcopy(list(runner.CANONICAL_CANDIDATES))
                candidates[1]["capabilities"][key] = value
                report = runner.evaluate(candidates=candidates)
                self.assertEqual(report["status"], "failed")

        for claim in (
            {"post_hoc_row_substitution_accepted": True},
            {"normals_or_curvature_accepted_as_parametric_derivatives": True},
        ):
            with self.subTest(claim=claim):
                self.assertEqual(runner.evaluate(**claim)["status"], "failed")

    def test_selection_policy_route_and_fallback_false_claims_fail(self):
        runner = load_module(RUNNER, "altlib_policy_false_claims")
        cases = (
            {"selected_library": "cgal", "library_selected": True},
            {"preferred_candidate": "cgal"},
            {"recommendation_present": True},
            {"dependency_policy_changed": True},
            {"production_route_enabled": True},
            {"scientifically_approved": True},
            {"patch_or_vendoring_performed": True},
            {"current_slimed_valence5_fallback_preserved": False},
        )
        for claim in cases:
            with self.subTest(claim=claim):
                report = runner.evaluate(**claim)
                self.assertEqual(report["status"], "failed")

    def test_pr149_history_and_authorization_scope_are_binding(self):
        runner = load_module(RUNNER, "altlib_authorization")
        cases = (
            {"architecture_option_authorized_for_investigation": "A"},
            {"alternate_library_feasibility_lane_authorized": False},
            {"authorization_scope": "architecture_selection"},
            {"predecessor_decision_selected": True, "predecessor_selected_option": "D"},
            {"predecessor_selected_option": "D"},
            {"predecessor_option_statuses": {"A": "unselected", "B": "unselected", "C": "unselected", "D": "selected"}},
            {"investigation_authorization_is_architecture_selection": True},
        )
        for claim in cases:
            with self.subTest(claim=claim):
                self.assertEqual(runner.evaluate(**claim)["status"], "failed")

    def test_wrapper_is_local_and_deterministic(self):
        results = []
        for _ in range(2):
            result = subprocess.run(
                [str(WRAPPER), "--json", "--check"],
                cwd=ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            results.append(result.stdout)
        self.assertEqual(results[0], results[1])
        report = json.loads(results[0])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["retrieval_date"], "2026-07-30")

    def test_stale_nothing_next_wording_fails_global_readiness(self):
        inventory = load_module(GLOBAL_INVENTORY, "altlib_global_readiness")
        claims = [
            claim
            for claim in inventory.FORBIDDEN_READINESS_CLAIMS
            if claim.name.startswith("post-PR149")
        ]
        self.assertGreaterEqual(len(claims), 2)
        for claim in claims:
            with self.subTest(claim=claim.name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    path = root / claim.path
                    path.parent.mkdir(parents=True)
                    path.write_text(f"{claim.needle}\n", encoding="utf-8")
                    located = inventory.collect_forbidden_claims(root)
                self.assertEqual(len(located), 1)


if __name__ == "__main__":
    unittest.main()
