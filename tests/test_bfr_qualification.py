import copy
import gzip
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
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

    def _spread_evidence(self, manifest):
        statistic = {"observation_count": 8, "maximum": 0.1, "median": 0.1}
        radius_statistic = {"observation_count": 1, "maximum": 0.1,
                            "median": 0.1}
        per_order = {}
        trends = {}
        for row_kind in MODULE.ROW_ORDER:
            per_order[row_kind] = {
                "coefficient_l1": copy.deepcopy(statistic),
                "normalized_geometric_linf": {
                    "observation_count": 8, "maximum": 0.01, "median": 0.01},
                "maximum_coefficient_l1_observation": {
                    "content_identity_key": MODULE.valid_unique_contents(manifest)[0],
                    "face_row": 0, "local_corner": 0,
                    "sample_id": "trend-r01-ray00", "radius_exponent": 1,
                    "row_kind": row_kind, "coefficient_l1": 0.1,
                    "normalized_geometric_linf": 0.01,
                },
            }
            trends[row_kind] = {
                str(exponent): {
                    "coefficient_l1": copy.deepcopy(radius_statistic),
                    "normalized_geometric_linf": {
                        "observation_count": 1, "maximum": 0.01,
                        "median": 0.01},
                }
                for exponent in range(1, 9)
            }
        return {
            "kind": "observed_inter_method_spread",
            "row_order": list(MODULE.ROW_ORDER),
            "pairing": {
                "bfr": {"approxLevelSmooth": 8, "approxLevelSharp": 6,
                        "mode": "cache_disabled"},
                "far": {"isolationLevel": 8,
                        "mode": "not_applicable_uncached"},
                "alignment": "same content/face/local-corner/trend-sample/original-source coarse frame",
                "selection_reason": "highest frozen setting for each candidate",
                "approximation_knobs_commensurable": False,
            },
            "normalization": "per-content coordinates centered at their arithmetic centroid and divided by maximum absolute centered coordinate",
            "observation_count": 48,
            "per_order": per_order,
            "trend_by_radius_exponent": trends,
            "overall_max_coefficient_l1": 0.1,
            "overall_max_normalized_geometric_linf": 0.01,
            "artifact_bindings": [
                {"content_identity_key": identity, "candidate": candidate,
                 "artifact_sha256": "a" * 64}
                for identity in MODULE.valid_unique_contents(manifest)
                for candidate in ("bfr", "far")
            ],
            "is_accuracy_ranking": False, "is_accuracy_floor": False,
            "is_accuracy_bound": False,
        }

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
        group_counts = {
            job["content_identity_key"]:
                len(MODULE.expected_case_samples(manifest, job)[2])
            for job in MODULE.valid_content_jobs(manifest)
        }

        def numeric_case(identity, candidate, level, mode):
            group_count = group_counts[identity]
            rss_counts = {
                "after_refiner_construction": 18,
                "after_factory_or_cache_construction": 18,
                "after_each_completed_face_row_insertion": 18 * group_count,
                "after_immutable_package_publication": 18,
                "after_row_package_destruction": 18,
                "after_factory_or_cache_destruction": 18,
                "after_refiner_destruction": 18,
            }
            rss_total = sum(rss_counts.values())
            return {
                "content_identity_key": identity, "candidate": candidate,
                "approximation_level": level, "applicable_mode": mode,
                "status": "PASS", "row_group_count": group_count,
                "row_kind_counts": {kind: group_count for kind in MODULE.ROW_ORDER},
                "source_reconstruction_complete": True, "max_row_sum_error": 0.0,
                "warmup_count": 3, "preparation_ns": list(range(15)),
                "preparation_median_ns": 7, "retained_payload_bytes_per_face": 100,
                "peak_rss_delta_bytes": 100, "rss_baseline_sample_count": 1,
                "rss_named_samples_complete": True,
                "rss_named_sample_count": rss_total,
                "rss_expected_named_sample_count": rss_total,
                "rss_named_sample_counts": rss_counts,
                "untimed_serialization_replay": True,
                "serialization_replay_rss_sampled": False,
                "platform_boundary_samples": [
                    {"boundary": boundary, "probe": copy.deepcopy(probe)}
                    for boundary in boundaries],
            }
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
            "observed_near_vertex_inter_method_spread":
                self._spread_evidence(manifest),
            "far_promotion_declined": True,
            "approximation_knobs_commensurable": False,
            "execution": {
                "canonical_case_order": MODULE.CANONICAL_CASE_ORDER,
                "deterministic_reruns_equal": True,
                "negative_cases": [
                    {"execution_case_id": case_id, "status": "REJECTED_BEFORE_OUTPUT",
                     "candidate_objects_constructed": 0, "rows_emitted": 0}
                    for case_id in sorted(MODULE.NEGATIVE_CASES)
                ],
                "adversarial_pinched_vertex": {
                    "content_identity_key": "adversarial_temporary_pinched_vertex",
                    "status": "REJECTED_BEFORE_OUTPUT",
                    "candidate_objects_constructed": 0, "rows_emitted": 0,
                    "reason": "D2_INVALID_CLOSED_VERTEX_LINK",
                    "edge_incidence_and_global_connectivity_control": True,
                    "retained_fixture": False,
                },
                "numeric_cases": [
                    numeric_case(identity, candidate, level, mode)
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
            "criterion_order": list(MODULE.BFR_CRITERIA),
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
                "example": {
                            "content_identity_key": "closed_valence3_tetrahedron",
                            "candidate": "bfr", "approximation_level": 4,
                            "modes": ["cache_disabled", "SurfaceFactoryCache_serial"],
                            "row_kind": "dvv", "face_row": 0, "local_corner": 1,
                            "sample_id": "trend-r08-ray01",
                            "sum": 1.4781509349859334e-12,
                            "absolute_error": 1.4781509349859334e-12,
                            "cache_modes_equal": True,
                            "artifact_sha256_by_mode": {
                                "cache_disabled": "e" * 64,
                                "SurfaceFactoryCache_serial": "f" * 64}},
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
            "negative_preflight": {
                "status": "PASS", "manifest_case_count": 3,
                "adversarial_case_count": 1, "case_count": 4,
                "failure_before_output": True,
                "pinched_vertex_link_cycle_rejected": True},
            "release_checkpoint": {
                "path": "/tmp/checkpoint", "sha256": "b" * 64,
                "complete": True, "case_count": 294,
                "binding": {
                    "manifest_file_sha256": MODULE.MANIFEST_FILE_SHA256,
                    "manifest_contract_sha256": MODULE.MANIFEST_CONTRACT_SHA256,
                    "git_head": "c" * 40,
                    "candidate_binary_sha256": "d" * 64,
                },
            },
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

    def _synthetic_candidate_case(self):
        manifest = MODULE.load_manifest()
        job = next(job for job in MODULE.valid_content_jobs(manifest)
                   if job["content_identity_key"] == "closed_valence3_tetrahedron")
        identity = job["content_identity_key"]
        candidate, level, mode = "bfr", 2, "cache_disabled"
        _, faces, samples = MODULE.expected_case_samples(manifest, job)
        rows = []
        face_sample_counts = [0 for _ in faces]
        for sample in samples:
            face_sample_counts[sample["face_row"]] += 1
            for row_kind in MODULE.ROW_ORDER:
                rows.append({
                    "content_identity_key": identity, "candidate": candidate,
                    "approximation_level": level, "applicable_mode": mode,
                    "face_row": sample["face_row"],
                    "local_corner_or_none": sample["local_corner_or_none"],
                    "sample_id": sample["sample_id"],
                    "u_binary64": sample["u"], "v_binary64": sample["v"],
                    "u_binary64_bits_hex": MODULE.binary64_bits_hex(sample["u"]),
                    "v_binary64_bits_hex": MODULE.binary64_bits_hex(sample["v"]),
                    "weight_bits_hex": "3ff0000000000000", "row_kind": row_kind,
                    "source_ids": [0],
                    "coefficients": [1.0 if row_kind == "position" else 0.0],
                })
        group_count = len(samples)
        rss_counts = {
            "after_refiner_construction": 18,
            "after_factory_or_cache_construction": 18,
            "after_each_completed_face_row_insertion": 18 * group_count,
            "after_immutable_package_publication": 18,
            "after_row_package_destruction": 18,
            "after_factory_or_cache_destruction": 18,
            "after_refiner_destruction": 18,
        }
        retained_payloads = [
            12 + 4 + 72 * count + 12 * 6 * count
            for count in face_sample_counts]
        rss_observations = []
        for repeat in range(18):
            phase = "warmup" if repeat < 3 else "measured"
            repeat_index = repeat if repeat < 3 else repeat - 3
            stages = [
                ("after_refiner", None, None, None),
                ("after_factory_cache", None, None, None)]
            stages.extend((
                "after_face_insert", sample["face_row"],
                (None if sample["local_corner_or_none"] < 0 else
                 sample["local_corner_or_none"]), sample["sample_id"])
                for sample in samples)
            stages.extend([
                ("after_package_publication", None, None, None),
                ("after_package_destruction", None, None, None),
                ("after_factory_cache_destruction", None, None, None),
                ("after_refiner_destruction", None, None, None)])
            rss_observations.extend({
                "repeat_phase": phase, "repeat_index": repeat_index,
                "face_id": face_id, "local_corner_or_none": local_corner,
                "sample_id": sample_id, "stage": stage,
                "rss_bytes": 1100}
                for stage, face_id, local_corner, sample_id in stages)
        report = {
            "schema_version": 1, "kind": "bfr_candidate_case", "status": "ok",
            "finite": True, "content_identity_key": identity,
            "candidate": candidate, "approximation_level": level,
            "applicable_mode": mode, "rows": rows,
            "row_group_count": group_count,
            "row_kind_counts": {kind: group_count for kind in MODULE.ROW_ORDER},
            "source_reconstruction_complete": True, "max_row_sum_error": 0.0,
            "retained_payload_bytes_per_face": max(retained_payloads),
            "d12_representation_workload_included": True,
            "d12_retained_payload_bytes_by_face": retained_payloads,
            "d12_rss_baseline_bytes": 1000,
            "d12_rss_observations": rss_observations,
            "warmup_count": 3, "preparation_ns": list(range(15)),
            "preparation_median_ns": 7, "peak_rss_delta_bytes": 100,
            "rss_baseline_sample_count": 1,
            "rss_named_sample_counts": rss_counts,
            "rss_named_sample_count": sum(rss_counts.values()),
            "rss_expected_named_sample_count": sum(rss_counts.values()),
            "rss_named_samples_complete": True,
            "untimed_serialization_replay": True,
            "serialization_replay_rss_sampled": False,
        }
        return manifest, job, (identity, candidate, level, mode), report

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

    def test_sorted_json_round_trip_uses_explicit_criterion_order(self):
        valid = self._terminal_failure_evidence()
        round_tripped = json.loads(json.dumps(valid, sort_keys=True, allow_nan=False))
        self.assertNotEqual(list(round_tripped["bfr_d9a_criteria"]),
                            MODULE.BFR_CRITERIA)
        self.assertTrue(MODULE.validate_evidence_document(round_tripped))
        reordered = copy.deepcopy(valid)
        reordered["bfr_d9a_criteria"] = dict(reversed(
            list(reordered["bfr_d9a_criteria"].items())))
        self.assertTrue(MODULE.validate_evidence_document(reordered))
        wrong_order = copy.deepcopy(round_tripped)
        wrong_order["criterion_order"][0:2] = reversed(
            wrong_order["criterion_order"][0:2])
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_evidence_document(wrong_order)

    def test_scientific_accumulation_order_is_python_version_independent(self):
        self.assertEqual(MODULE.ordered_binary64_sum([1.0e16, 1.0, -1.0e16]),
                         0.0)

    def test_spread_and_lifecycle_mutations_fail_closed(self):
        valid = self._terminal_failure_evidence()
        mutations = []
        missing_order = copy.deepcopy(valid)
        del missing_order["observed_near_vertex_inter_method_spread"][
            "per_order"]["dvv"]
        mutations.append(missing_order)
        promoted_floor = copy.deepcopy(valid)
        promoted_floor["observed_near_vertex_inter_method_spread"][
            "is_accuracy_floor"] = True
        mutations.append(promoted_floor)
        bad_trend_count = copy.deepcopy(valid)
        bad_trend_count["observed_near_vertex_inter_method_spread"][
            "trend_by_radius_exponent"]["du"]["8"]["coefficient_l1"][
                "observation_count"] = 2
        mutations.append(bad_trend_count)
        bad_rss = copy.deepcopy(valid)
        bad_rss["execution"]["numeric_cases"][0]["rss_named_sample_count"] += 1
        mutations.append(bad_rss)
        bad_group_count = copy.deepcopy(valid)
        bad_group_count["execution"]["numeric_cases"][0]["row_group_count"] -= 1
        mutations.append(bad_group_count)
        for mutation in mutations:
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_evidence_document(mutation)

    def test_candidate_rows_and_gzip_artifact_are_independently_revalidated(self):
        manifest, job, identity_tuple, report = self._synthetic_candidate_case()
        validated = MODULE.validate_candidate_case(
            report, *identity_tuple, manifest, job)
        self.assertEqual(validated["row_group_count"], report["row_group_count"])
        self.assertTrue(any(
            item["stage"] == "after_face_insert" and
            item["local_corner_or_none"] is None
            for item in report["d12_rss_observations"]))
        self.assertTrue(MODULE.validate_candidate_case(
            json.loads(json.dumps(report, sort_keys=True, allow_nan=False)),
            *identity_tuple, manifest, job))
        mutations = []
        changed_coordinate = copy.deepcopy(report)
        changed_coordinate["rows"][0]["u_binary64"] = 0.125
        mutations.append(changed_coordinate)
        changed_source = copy.deepcopy(report)
        changed_source["rows"][0]["source_ids"] = [1000000]
        mutations.append(changed_source)
        forged_maximum = copy.deepcopy(report)
        forged_maximum["max_row_sum_error"] = 1.0
        mutations.append(forged_maximum)
        forged_rss = copy.deepcopy(report)
        forged_rss["rss_named_sample_counts"][
            "after_each_completed_face_row_insertion"] -= 1
        mutations.append(forged_rss)
        for mutation in mutations:
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_candidate_case(
                    mutation, *identity_tuple, manifest, job)

        identity, candidate, level, mode = identity_tuple
        summary = {
            "content_identity_key": identity, "candidate": candidate,
            "approximation_level": level, "applicable_mode": mode,
            "status": "PASS", "failure_reasons": [],
            "d12_budget_observation": "WITHIN_BUDGETS",
            "row_group_count": validated["row_group_count"],
            "row_kind_counts": validated["row_kind_counts"],
            "source_reconstruction_complete": True,
            "max_row_sum_error": validated["max_row_sum_error"],
            "warmup_count": 3, "preparation_ns": report["preparation_ns"],
            "preparation_median_ns": report["preparation_median_ns"],
            "retained_payload_bytes_per_face":
                validated["retained_payload_bytes_per_face"],
            "peak_rss_delta_bytes": report["peak_rss_delta_bytes"],
            "rss_baseline_sample_count": 1,
            "rss_named_samples_complete": True,
            "rss_named_sample_count": validated["rss_named_sample_count"],
            "rss_expected_named_sample_count": validated["rss_named_sample_count"],
            "rss_named_sample_counts": validated["rss_named_sample_counts"],
            "untimed_serialization_replay": True,
            "serialization_replay_rss_sampled": False,
            "canonical_rows_sha256": validated["canonical_rows_sha256"],
            "deterministic_rerun_equal": True,
        }
        with tempfile.TemporaryDirectory() as temporary:
            artifact = pathlib.Path(temporary) / "case.json.gz"
            raw = (json.dumps(report, sort_keys=True, allow_nan=False) + "\n").encode()
            artifact.write_bytes(gzip.compress(raw, mtime=0))
            summary["complete_json_artifact_sha256"] = MODULE.sha256_file(artifact)
            summary["complete_json_sha256"] = MODULE.sha256_bytes(raw)
            summary["complete_json_artifact"] = artifact.name
            MODULE.validate_case_artifact(
                artifact, summary, manifest, job, *identity_tuple)
            self.assertTrue(MODULE.validate_artifact_directory_inventory(
                artifact.parent, [summary]))
            (artifact.parent / "extra.json.gz").write_bytes(b"extra")
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_artifact_directory_inventory(
                    artifact.parent, [summary])
            (artifact.parent / "extra.json.gz").unlink()
            corrupted = copy.deepcopy(report)
            corrupted["rows"][0]["source_ids"] = [1000000]
            corrupted_raw = (json.dumps(corrupted, sort_keys=True,
                                        allow_nan=False) + "\n").encode()
            artifact.write_bytes(gzip.compress(corrupted_raw, mtime=0))
            corrupt_summary = copy.deepcopy(summary)
            corrupt_summary["complete_json_artifact_sha256"] = (
                MODULE.sha256_file(artifact))
            corrupt_summary["complete_json_sha256"] = MODULE.sha256_bytes(
                corrupted_raw)
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_case_artifact(
                    artifact, corrupt_summary, manifest, job, *identity_tuple)

    def test_scientific_fail_exits_zero_but_infrastructure_failure_is_nonzero(self):
        evidence = self._terminal_failure_evidence()
        stdout = io.StringIO()
        with mock.patch.object(MODULE, "finalize_release_checkpoint", return_value=evidence):
            with mock.patch("sys.stdout", stdout):
                result = MODULE.main([
                    "--finalize-release-checkpoint", "--release-checkpoint", "/tmp/checkpoint",
                    "--candidate-binary", "/tmp/candidate",
                    "--artifact-dir", "/tmp/artifacts", "--json"])
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
