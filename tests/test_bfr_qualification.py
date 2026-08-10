import copy
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_bfr_qualification.py"
SPEC = importlib.util.spec_from_file_location("run_bfr_qualification", str(RUNNER))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BfrQualificationContractTests(unittest.TestCase):
    def test_self_test_is_fail_closed_and_decides_neither_d9_gate(self):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--self-test", "--json"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["contract"]["threading_tuple_count"], 588)
        self.assertEqual(report["candidate_roles"]["bfr"], "qualification_target")
        self.assertEqual(report["candidate_roles"]["far"], "regression_comparator_only")
        self.assertFalse(report["d9a_decided"])
        self.assertFalse(report["d9b_decided"])

    def test_manifest_mutations_fail(self):
        manifest = MODULE.load_manifest()
        mutations = []
        missing_entry = copy.deepcopy(manifest)
        missing_entry["entries"].pop()
        mutations.append(missing_entry)
        swapped_rows = copy.deepcopy(manifest)
        swapped_rows["row_order"]["rows"][1:3] = reversed(swapped_rows["row_order"]["rows"][1:3])
        mutations.append(swapped_rows)
        widened_threading = copy.deepcopy(manifest)
        widened_threading["threading_protocol"]["workers"] = [1, 2]
        mutations.append(widened_threading)
        changed_weight = copy.deepcopy(manifest)
        changed_weight["sample_field_contract"]["weight"]["bits_hex"] = "0000000000000000"
        mutations.append(changed_weight)
        changed_platform = copy.deepcopy(manifest)
        changed_platform["qualification_platform"]["fingerprint"]["hw_model"] = "Mac17,3"
        mutations.append(changed_platform)
        changed_compiler = copy.deepcopy(manifest)
        changed_compiler["qualification_platform"]["build"]["compiler_version"] = "forged"
        mutations.append(changed_compiler)
        for mutation in mutations:
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_manifest_contract(mutation)

    def _valid_evidence(self):
        manifest = MODULE.load_manifest()
        probe = {
            "schema_version": 1, "kind": "bfr_platform_probe", "status": "ok",
            "finite": True, "fingerprint_queries_ok": True,
            "fingerprint": copy.deepcopy(MODULE.EXPECTED_PLATFORM_FINGERPRINT),
            "power": {"api": MODULE.EXPECTED_POWER_API, "query_ok": True,
                      "raw": "AC Power", "value": MODULE.EXPECTED_POWER_VALUE},
            "thermal": {"api": MODULE.EXPECTED_THERMAL_API, "query_ok": True,
                        "raw": 0, "value": MODULE.EXPECTED_THERMAL_VALUE},
        }
        boundaries = ["primary_before", "primary_after",
                      "determinism_before", "determinism_after"]
        rows = []
        for candidate in ("bfr", "far"):
            for kind in MODULE.ROW_ORDER:
                rows.append({
                    "execution_case_id": "u8_01_regular_closed",
                    "member_id": "regular_all6_torus",
                    "face_row": 0,
                    "sample_id": "tri-l6-s02-u01-v01",
                    "candidate": candidate,
                    "approximation_level": 8,
                    "row_kind": kind,
                    "coefficients": [1.0 if kind == "position" else 0.0],
                })
        return {
            "schema_version": 1,
            "kind": "bfr_qualification_evidence",
            "manifest_file_sha256": MODULE.MANIFEST_FILE_SHA256,
            "manifest_contract_sha256": MODULE.MANIFEST_CONTRACT_SHA256,
            "candidate_roles": {"bfr": "qualification_target", "far": "regression_comparator_only"},
            "sample_weight_use": "validation_only_not_quadrature",
            "sample_weight_bits_hex": "3ff0000000000000",
            "sample_weight_arithmetic_uses": 0,
            "near_vertex_accuracy_ranking_declined": True,
            "inter_method_spread_is_accuracy_floor": False,
            "execution": {
                "canonical_case_order": MODULE.CANONICAL_CASE_ORDER,
                "deterministic_reruns_equal": True,
                "negative_cases": [
                    {"execution_case_id": case_id, "status": "REJECTED_BEFORE_OUTPUT",
                     "candidate_objects_constructed": 0, "rows_emitted": 0}
                    for case_id in sorted(MODULE.NEGATIVE_CASES)
                ],
                "numeric_cases": [
                    {"content_identity_key": identity, "candidate": candidate,
                     "approximation_level": level, "applicable_mode": mode,
                     "status": "PASS", "row_group_count": 1,
                     "row_kind_counts": {kind: 1 for kind in MODULE.ROW_ORDER},
                     "source_reconstruction_complete": True, "max_row_sum_error": 0.0,
                     "warmup_count": 3, "preparation_ns": [index for index in range(15)],
                     "preparation_median_ns": 7, "retained_payload_bytes_per_face": 100,
                     "peak_rss_delta_bytes": 100, "rss_named_samples_complete": True,
                     "platform_boundary_samples": [
                         {"boundary": boundary, "probe": copy.deepcopy(probe)}
                         for boundary in boundaries]}
                    for identity, candidate, level, mode in
                    MODULE.expected_numeric_case_identities(manifest)
                ],
            },
            "platform_qualification": {
                "status": "QUALIFIED",
                "expected_fingerprint": copy.deepcopy(MODULE.EXPECTED_PLATFORM_FINGERPRINT),
                "current_probe": copy.deepcopy(probe),
                "compiler": {"path": MODULE.EXPECTED_COMPILER_PATH,
                             "query_ok": True,
                             "version": MODULE.EXPECTED_COMPILER_VERSION},
                "per_case_boundary_protocol": {
                    "required_boundaries": boundaries, "case_count": 294,
                    "sample_count": 1176, "complete_and_qualified": True},
                "github_hosted": False, "runner_environment": None,
                "git_identity": {"head": "exact", "head_query_ok": True,
                                 "worktree_empty": True,
                                 "review_match": "PENDING_INDEPENDENT_EXACT_SHA_REVIEW"},
                "mismatches": [],
            },
            "rows": rows,
            "regular_analytic_gate": {
                candidate: {"canonical_parameter_map_checks": 7,
                            "rotated_patch_verified": True, "unrotated_patch_verified": True,
                            "all_six_rows": True, "area_integrand": True,
                            "legacy_volume_integrand": True, "max_error": 0.0}
                for candidate in ("bfr", "far")
            },
            "internal_convergence": {
                candidate: {"levels": list(range(2, 9)), "own_setting_only": True,
                            "status": "PASS"}
                for candidate in ("bfr", "far")
            },
            "approximation_knobs_commensurable": False,
            "oracle_certificates": [{
                "status": "COVERED", "uniform_success_substituted_for_primary": False,
                "first_isolating_depth": 1, "primary_method": "stam_eigenanalysis",
                "precision_bits": 544, "interval_krawczyk_inclusion": True,
                "spectral_projector_certified": True,
                "intersection_depths": [1, 2, 3, 4, 5],
                "exact_binary64_midpoint_import": True,
                "exact_binary64_candidate_import": True,
                "uniform_cross_check": True,
                "uncertainty_coeff_le_tenth_target": True,
                "uncertainty_geom_le_tenth_target": True,
            }],
            "threading": {
                "tuple_count": 588, "rounds_per_tuple": 20,
                "tuple_results": [
                    {"content_identity_key": identity, "approxLevelSmooth": level,
                     "mode": mode, "worker_count": workers, "rounds": 20,
                     "canonical_rows_identical": True,
                     "concurrent_factory_mode": mode if mode == "cache_disabled" else None}
                    for identity, level, mode, workers in
                    MODULE.expected_threading_identities(manifest)
                ],
                "tsan_profile": {"proof_translation_units_instrumented": True,
                                 "opensubdiv_translation_units_instrumented": 47,
                                 "findings": 0, "matrix_complete": True},
            },
            "flip_locality": [{"comparable_faces": 10, "changed_faces": 2,
                               "reusable_faces": 8, "phase2_projection_only": True}],
            "bfr_d9a_criteria": {criterion: "PASS" for criterion in MODULE.BFR_CRITERIA},
            "bfr_verdict": "PASS",
            "oracle_coverage_complete": True,
            "threading_tsan_complete": True,
            "d9a_decided": False,
            "d9b_decided": False,
        }

    def _terminal_failure_evidence(self):
        report = self._valid_evidence()
        bfr_failures = 0
        far_failures = 0
        for value in report["execution"]["numeric_cases"]:
            should_fail = ((value["candidate"] == "bfr" and bfr_failures < 124) or
                           (value["candidate"] == "far" and far_failures < 62))
            value["failure_reasons"] = []
            if should_fail:
                value["status"] = "FAIL"
                value["failure_reasons"] = ["row_sum_invariant"]
                value["max_row_sum_error"] = 2.0e-12
                if value["candidate"] == "bfr":
                    bfr_failures += 1
                else:
                    far_failures += 1
        bfr_values = [value for value in report["execution"]["numeric_cases"]
                      if value["candidate"] == "bfr" and value["status"] == "FAIL"]
        far_values = [value for value in report["execution"]["numeric_cases"]
                      if value["candidate"] == "far" and value["status"] == "FAIL"]
        bfr_values[-1]["max_row_sum_error"] = 2.0368522054550406e-11
        far_values[-1]["max_row_sum_error"] = 3.356106503815681e-10
        terminal = "NOT_RUN_TERMINAL_BFR_FAILURE"
        report.update({
            "status": "ok", "proof_execution_status": "COMPLETE_TERMINAL_BFR_FAILURE",
            "bfr_verdict": "FAIL", "blocking_criterion": "row_sum_invariants",
            "row_invariant_failure": {
                "tolerance": 1.0e-12, "tolerance_changed": False,
                "bfr_failure_count": 124, "far_comparator_failure_count": 62,
                "bfr_max_error": 2.0368522054550406e-11,
                "far_max_error": 3.356106503815681e-10,
                "example": {"row_kind": "dvv", "sample_id": "trend-r08-ray01",
                            "absolute_error": 1.4781509349859334e-12,
                            "cache_modes_equal": True},
            },
            "d12_summary": {
                "status": "PASS", "budget_verdict": "PASS", "case_count": 294,
                "exceeded_case_count_observation": 0,
                "max_preparation_median_ns": 7, "max_preparation_single_ns": 14,
                "max_retained_payload_bytes_per_face": 100,
                "max_peak_rss_delta_bytes": 100,
                "budgets": {"median_ns": 1000000000, "single_ns": 10000000000,
                            "payload_bytes_per_face": 131072,
                            "peak_rss_delta_bytes": 64 * 1048576}},
            "canonical_determinism": {"status": "PASS", "case_count": 294,
                                      "two_pass_rows_equal": True},
            "negative_preflight": {"status": "PASS", "case_count": 3,
                                   "failure_before_output": True},
            "bfr_d9a_criteria": {
                "regular_analytic_rows_and_integrands": terminal,
                "row_sum_invariants": "FAIL",
                "original_source_reconstruction": "PASS",
                "internal_refinement_convergence": terminal,
                "irregular_primary_stam_oracle": terminal,
                "d12_preparation_cost": "PASS",
                "d12_retained_payload": "PASS",
                "d12_peak_rss": "PASS",
                "cache_disabled_concurrency": terminal,
                "threaded_cache_fully_instrumented_tsan": terminal,
            },
            "oracle_certificates": [], "oracle_coverage_complete": False,
            "threading_tsan_complete": False,
            "review_status": {"verification_agent": "PENDING",
                              "technical_review": "PENDING",
                              "scientific_review": "PENDING", "gatekeeper": "PENDING"},
            "package_review_complete": False,
        })
        return report

    def test_terminal_scientific_failure_schema_is_complete_and_fail_closed(self):
        valid = self._terminal_failure_evidence()
        self.assertTrue(MODULE.validate_evidence_document(valid))
        mutations = []
        changed_tolerance = copy.deepcopy(valid)
        changed_tolerance["row_invariant_failure"]["tolerance"] = 2.0e-12
        mutations.append(changed_tolerance)
        false_downstream_pass = copy.deepcopy(valid)
        false_downstream_pass["bfr_d9a_criteria"]["irregular_primary_stam_oracle"] = "PASS"
        mutations.append(false_downstream_pass)
        fake_count = copy.deepcopy(valid)
        fake_count["row_invariant_failure"]["bfr_failure_count"] = 123
        mutations.append(fake_count)
        fake_maximum = copy.deepcopy(valid)
        fake_maximum["row_invariant_failure"]["bfr_max_error"] = 1.0e-12
        mutations.append(fake_maximum)
        fake_decision = copy.deepcopy(valid)
        fake_decision["d9a_decided"] = True
        mutations.append(fake_decision)
        false_artifact_claim = copy.deepcopy(valid)
        false_artifact_claim["execution"]["complete_case_artifacts"] = True
        mutations.append(false_artifact_claim)
        for mutation in mutations:
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_evidence_document(mutation)

    def test_scientific_fail_exits_zero_but_infrastructure_failure_is_nonzero(self):
        evidence = self._terminal_failure_evidence()
        stdout = io.StringIO()
        with mock.patch.object(MODULE, "finalize_release_checkpoint", return_value=evidence):
            with mock.patch("sys.stdout", stdout):
                result = MODULE.main([
                    "--finalize-release-checkpoint", "--release-checkpoint", "/tmp/checkpoint",
                    "--candidate-binary", "/tmp/candidate", "--json"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["bfr_verdict"], "FAIL")
        with mock.patch("sys.stdout", io.StringIO()):
            infrastructure_result = MODULE.main(["--require-proof-dependencies", "--json"])
        self.assertNotEqual(infrastructure_result, 0)

    def test_unqualified_platform_never_masquerades_as_d12_pass(self):
        unqualified = self._terminal_failure_evidence()
        for case in unqualified["execution"]["numeric_cases"]:
            case.pop("platform_boundary_samples")
        platform = unqualified["platform_qualification"]
        platform["status"] = MODULE.UNQUALIFIED_PLATFORM
        platform["per_case_boundary_protocol"] = {
            "required_boundaries": ["primary_before", "primary_after",
                                    "determinism_before", "determinism_after"],
            "case_count": 294, "sample_count": 0,
            "complete_and_qualified": False,
        }
        platform["mismatches"] = [
            "per_case_power_thermal_sampling_incomplete_or_unqualified"]
        unqualified["d12_summary"]["status"] = MODULE.UNQUALIFIED_PLATFORM
        unqualified["d12_summary"]["budget_verdict"] = "NEITHER_PASS_NOR_FAIL"
        for criterion in ("d12_preparation_cost", "d12_retained_payload",
                          "d12_peak_rss"):
            unqualified["bfr_d9a_criteria"][criterion] = MODULE.UNQUALIFIED_PLATFORM
        self.assertTrue(MODULE.validate_evidence_document(unqualified))

        forged_pass = copy.deepcopy(unqualified)
        forged_pass["d12_summary"]["status"] = "PASS"
        forged_pass["d12_summary"]["budget_verdict"] = "PASS"
        for criterion in ("d12_preparation_cost", "d12_retained_payload",
                          "d12_peak_rss"):
            forged_pass["bfr_d9a_criteria"][criterion] = "PASS"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_evidence_document(forged_pass)

        forged_fingerprint = self._terminal_failure_evidence()
        forged_fingerprint["platform_qualification"]["current_probe"][
            "fingerprint"]["hw_model"] = "Mac17,3"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_evidence_document(forged_fingerprint)

        forged_hosted = self._terminal_failure_evidence()
        forged_hosted["platform_qualification"]["github_hosted"] = True
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_evidence_document(forged_hosted)

    def test_evidence_mutations_fail(self):
        valid = self._valid_evidence()
        self.assertTrue(MODULE.validate_evidence_document(valid))
        mutations = []
        missing_row = copy.deepcopy(valid)
        missing_row["rows"].pop(3)
        mutations.append(missing_row)
        nonfinite = copy.deepcopy(valid)
        nonfinite["rows"][0]["coefficients"] = [float("nan")]
        mutations.append(nonfinite)
        dropped_order = copy.deepcopy(valid)
        dropped_order["rows"][5]["row_kind"] = "duv"
        mutations.append(dropped_order)
        swapped_labels = copy.deepcopy(valid)
        swapped_labels["candidate_roles"] = {"bfr": "regression_comparator_only", "far": "qualification_target"}
        mutations.append(swapped_labels)
        accidental_success = copy.deepcopy(valid)
        accidental_success["bfr_d9a_criteria"]["irregular_primary_stam_oracle"] = "PENDING"
        mutations.append(accidental_success)
        missing_execution = copy.deepcopy(valid)
        missing_execution["execution"]["numeric_cases"].pop()
        mutations.append(missing_execution)
        missing_five_depths = copy.deepcopy(valid)
        missing_five_depths["oracle_certificates"][0]["intersection_depths"].pop()
        mutations.append(missing_five_depths)
        missing_d12_sample = copy.deepcopy(valid)
        missing_d12_sample["execution"]["numeric_cases"][0]["preparation_ns"].pop()
        mutations.append(missing_d12_sample)
        incomplete_threading = copy.deepcopy(valid)
        incomplete_threading["threading"]["tuple_results"].pop()
        mutations.append(incomplete_threading)
        sentinel_arithmetic = copy.deepcopy(valid)
        sentinel_arithmetic["sample_weight_arithmetic_uses"] = 1
        mutations.append(sentinel_arithmetic)
        for mutation in mutations:
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_evidence_document(mutation)

    def test_changed_path_allowlist_rejects_frozen_and_production_paths(self):
        self.assertTrue(MODULE.validate_changed_path_allowlist([
            "experiments/bfr_qualification/candidate.cpp",
            "scripts/run_bfr_qualification.py",
            "tests/test_bfr_qualification.py",
            "docs/bfr_qualification_evidence.md",
            ".github/workflows/bfr_qualification.yml",
        ]))
        for forbidden in (
                "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
                "docs/bfr_loop_backend_plan_macos.md",
                "src/mesh/Limit_surface_evaluator.cpp", "Makefile"):
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_changed_path_allowlist([forbidden])

    def test_oracle_source_is_candidate_dependency_free(self):
        MODULE.validate_source_separation()

    def test_missing_roots_fail_in_required_mode(self):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--require-proof-dependencies", "--json"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True)
        self.assertNotEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["bfr_verdict"], "PENDING")


if __name__ == "__main__":
    unittest.main()
