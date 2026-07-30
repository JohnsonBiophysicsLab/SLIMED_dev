import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT / "scripts/run_irregular_valence5_post_option_d_architecture_gate.py"
)
WRAPPER = (
    ROOT / "scripts/run_irregular_valence5_post_option_d_architecture_gate.sh"
)
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_post_option_d_architecture_gate.py"
)
GLOBAL_INVENTORY = ROOT / "scripts/inventory_opensubdiv_routing_readiness.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class IrregularValence5PostOptionDArchitectureGateTest(unittest.TestCase):
    def test_canonical_report_binds_pr150_and_selects_nothing(self):
        runner = load_module(RUNNER, "post_d_canonical")
        report = runner.evaluate()
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(
            report["predecessor_merge_commits"],
            {
                "pr149": "54fecddb60edd05c0ec4677c87f684ebe5b50301",
                "pr150": "636a6583fea3e76e42e8b6b48699e40bc80f4e4d",
            },
        )
        self.assertEqual(
            report["pr149_predecessor"]["canonical_options_sha256"],
            runner.PR149_OPTIONS_SHA256,
        )
        self.assertEqual(
            report["pr149_predecessor"]["option_statuses"],
            {"A": "unselected", "B": "unselected", "C": "unselected", "D": "unselected"},
        )
        self.assertEqual(
            report["pr150_predecessor"]["merge_commit"],
            "636a6583fea3e76e42e8b6b48699e40bc80f4e4d",
        )
        self.assertEqual(
            report["pr150_predecessor"]["canonical_report_sha256"],
            runner.PR150_REPORT_SHA256,
        )
        self.assertEqual(
            report["pr150_predecessor"]["candidate_records_sha256"],
            runner.PR150_CANDIDATE_RECORDS_SHA256,
        )
        self.assertEqual(
            report["pr150_predecessor"]["candidate_ids"],
            ["cgal", "libigl", "openmesh", "pmp-library"],
        )
        self.assertEqual(report["pr150_predecessor"]["viable_candidate_ids"], [])
        self.assertEqual(
            report["pr150_predecessor"]["route_blockers"],
            [runner.PR150_EXACT_BLOCKER],
        )
        self.assertEqual(
            report["pr150_predecessor"]["authorization_state"],
            runner.PR150_AUTHORIZATION_STATE,
        )
        self.assertEqual(
            report["pr150_predecessor"]["required_capabilities"],
            list(runner.PR150_CAPABILITY_ORDER),
        )
        self.assertEqual(
            report["pr150_predecessor"]["slimed_valence5_mask"],
            {"neighbor_weight": 0.075, "center_weight": 0.625},
        )
        self.assertEqual(
            report["pr150_predecessor"]["retrieval_date"], "2026-07-30"
        )
        self.assertTrue(report["pr150_predecessor"]["installability_not_executed"])
        self.assertEqual(report["option_order"], ["A", "B", "C", "D"])
        self.assertEqual(
            [option["status"] for option in report["remaining_choices"]],
            ["unselected", "unselected", "unselected"],
        )
        self.assertEqual(report["completed_option_d"]["status"], "completed")
        self.assertEqual(
            report["completed_option_d"]["result"],
            "no_viable_candidate_in_reviewed_finite_non_exhaustive_set",
        )
        self.assertFalse(report["decision_selected"])
        self.assertIsNone(report["selected_option"])
        self.assertIsNone(report["recommended_option"])
        self.assertIsNone(report["preferred_option"])
        self.assertIsNone(report["automatically_next_option"])
        self.assertFalse(report["proceed_interpreted_as_option_selection"])
        option_a = report["options"][0]
        self.assertEqual(option_a["state"], "current_behavior_preserved")
        self.assertFalse(option_a["is_architecture_selection"])
        self.assertFalse(option_a["implementation_work_required"])
        self.assertTrue(report["current_slimed_valence5_fallback_preserved"])
        self.assertEqual(report["remaining_boundary"], runner.REMAINING_BOUNDARY)

    def test_pr149_canonical_options_and_no_selection_are_binding(self):
        runner = load_module(RUNNER, "post_d_pr149")
        canonical = runner._load_pr149_options()
        mutations = (
            canonical[:-1],
            [canonical[1], canonical[0], *canonical[2:]],
            [{**canonical[0], "status": "selected"}, *canonical[1:]],
            [{**canonical[0], "name": "fabricated"}, *canonical[1:]],
        )
        for options in mutations:
            with self.subTest(ids=[option["id"] for option in options]):
                self.assertEqual(
                    runner.evaluate(pr149_options=options)["status"], "failed"
                )

    def test_predecessor_candidate_result_blocker_and_authorization_drift_fail(self):
        runner = load_module(RUNNER, "post_d_predecessor_drift")
        canonical = runner._load_predecessor_report()
        mutations = (
            ("status", "failed"),
            ("proof_kind", "fabricated"),
            ("retrieval_date", "future"),
            ("slimed_valence5_mask", {"neighbor_weight": 0.1, "center_weight": 0.5}),
            ("required_capabilities", ["triangular_loop_support"]),
            ("candidate_ids", ["cgal"]),
            ("viable_candidate_ids", ["cgal"]),
            ("route_blockers", ["fabricated blocker"]),
            ("architecture_option_authorized_for_investigation", "B"),
            ("alternate_library_feasibility_lane_authorized", False),
            ("authorization_scope", "architecture_selection"),
            ("predecessor_decision_selected", True),
            ("predecessor_selected_option", "D"),
            ("investigation_authorization_is_architecture_selection", True),
            ("installability_not_executed", False),
            ("library_selected", True),
            ("selected_library", "cgal"),
            ("preferred_candidate", "cgal"),
            ("current_slimed_valence5_fallback_preserved", False),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                predecessor = copy.deepcopy(canonical)
                predecessor[key] = value
                self.assertEqual(
                    runner.evaluate(predecessor_report=predecessor)["status"],
                    "failed",
                )

        predecessor = copy.deepcopy(canonical)
        predecessor["candidates"] = list(reversed(predecessor["candidates"]))
        self.assertEqual(
            runner.evaluate(predecessor_report=predecessor)["status"], "failed"
        )

    def test_fabricated_viability_and_installability_overclaim_fail(self):
        runner = load_module(RUNNER, "post_d_false_candidate")
        canonical = runner._load_predecessor_report()
        mutations = (
            ("viable", True),
            ("selected", True),
            ("recommended", True),
            ("installability_probe_executed", True),
            ("compile_link_probe_passed", True),
            ("version", "future"),
            ("release_or_commit", "0" * 40),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                predecessor = copy.deepcopy(canonical)
                predecessor["candidates"][0][key] = value
                self.assertEqual(
                    runner.evaluate(predecessor_report=predecessor)["status"],
                    "failed",
                )

    def test_option_set_drift_selection_recommendation_preference_and_next_fail(self):
        runner = load_module(RUNNER, "post_d_options")
        canonical = [copy.deepcopy(option) for option in runner.CANONICAL_OPTIONS]
        option_mutations = (
            canonical[:-1],
            [canonical[1], canonical[0], *canonical[2:]],
            [{**canonical[0], "selected": True}, *canonical[1:]],
            [{**canonical[0], "recommended": True}, *canonical[1:]],
            [{**canonical[0], "preferred": True}, *canonical[1:]],
            [{**canonical[0], "automatically_next": True}, *canonical[1:]],
        )
        for options in option_mutations:
            with self.subTest(ids=[option["id"] for option in options]):
                self.assertEqual(runner.evaluate(options=options)["status"], "failed")

        claims = (
            {"decision_selected": True, "selected_option": "B"},
            {"selected_option": "C"},
            {"recommended_option": "B"},
            {"preferred_option": "C"},
            {"automatically_next_option": "B"},
        )
        for claim in claims:
            with self.subTest(claim=claim):
                self.assertEqual(runner.evaluate(**claim)["status"], "failed")

    def test_proceed_cannot_select_b_or_c(self):
        runner = load_module(RUNNER, "post_d_proceed")
        for option in ("B", "C"):
            with self.subTest(option=option):
                report = runner.evaluate(
                    proceed_interpreted_as_option_selection=True,
                    decision_selected=True,
                    selected_option=option,
                )
                self.assertEqual(report["status"], "failed")
                self.assertIn(
                    "Proceed authorizes only this gate, not Option B or C",
                    report["errors"],
                )

    def test_status_quo_cannot_be_reported_as_selected_architecture(self):
        runner = load_module(RUNNER, "post_d_status_quo")
        report = runner.evaluate(decision_selected=True, selected_option="A")
        self.assertEqual(report["status"], "failed")
        options = [copy.deepcopy(option) for option in runner.CANONICAL_OPTIONS]
        options[0]["selected"] = True
        self.assertEqual(runner.evaluate(options=options)["status"], "failed")

    def test_scientific_dependency_patch_route_and_fallback_false_greens_fail(self):
        runner = load_module(RUNNER, "post_d_policy")
        claims = (
            {"scientific_approval_granted": True},
            {"physical_rebaselining_plan_authorized": True},
            {"dependency_license_maintenance_approval_granted": True},
            {"dependency_policy_changed": True},
            {"patch_or_vendoring_performed": True},
            {"implementation_work_authorized": True},
            {"production_route_enabled": True},
            {"valence5_opensubdiv_route_enabled": True},
            {"current_slimed_valence5_fallback_preserved": False},
        )
        for claim in claims:
            with self.subTest(claim=claim):
                self.assertEqual(runner.evaluate(**claim)["status"], "failed")

    def test_option_d_cannot_be_reopened_by_this_gate(self):
        runner = load_module(RUNNER, "post_d_reopen")
        claims = (
            {
                "option_d_reopened": True,
                "explicit_option_d_reopen_authorization": True,
            },
            {
                "option_d_reopened": True,
                "materially_new_upstream_or_candidate_evidence": True,
            },
            {
                "option_d_reopened": True,
                "explicit_option_d_reopen_authorization": True,
                "materially_new_upstream_or_candidate_evidence": True,
            },
        )
        for claim in claims:
            with self.subTest(claim=claim):
                report = runner.evaluate(**claim)
                self.assertEqual(report["status"], "failed")
                if not (
                    claim.get("explicit_option_d_reopen_authorization")
                    and claim.get("materially_new_upstream_or_candidate_evidence")
                ):
                    self.assertIn(
                        "Option D reopening requires both explicit authorization "
                        "and materially new evidence",
                        report["errors"],
                    )

    def test_wrapper_is_local_and_deterministic(self):
        outputs = []
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
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(json.loads(outputs[0])["status"], "passed")

    def test_inventory_passes_and_protected_scope_is_unchanged(self):
        inventory = load_module(INVENTORY, "post_d_inventory")
        report = inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["exact_base"], inventory.BASE)
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )
        self.assertEqual(report["forbidden_claims"]["located"], 0)
        self.assertFalse(report["protected_surfaces_changed"])
        self.assertEqual(report["protected_surface_leaks"], [])
        self.assertEqual(
            report["changed_paths"],
            sorted(path.as_posix() for path in inventory.ALLOWED_PATHS),
        )

    def test_stale_post_pr150_wording_fails_global_readiness(self):
        inventory = load_module(GLOBAL_INVENTORY, "post_d_global_readiness")
        claims = [
            claim
            for claim in inventory.FORBIDDEN_READINESS_CLAIMS
            if claim.name.startswith("post-PR150")
        ]
        self.assertGreaterEqual(len(claims), 4)
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
