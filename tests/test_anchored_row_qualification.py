import copy
import importlib.util
import json
import math
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_anchored_row_qualification.py"
SPEC = importlib.util.spec_from_file_location("anchored_row_qualification", RUNNER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AnchoredRowQualificationTests(unittest.TestCase):
    def make_incomplete_criteria_fixture(self):
        digest = "a" * 64
        records = []
        for criterion_id in MODULE.CRITERION_IDS:
            expected = MODULE.EXPECTED_CELL_COUNTS[criterion_id]
            if criterion_id in MODULE.INFRASTRUCTURE_CRITERIA:
                records.append(MODULE.criterion_record(
                    criterion_id, "INCOMPLETE", expected=expected))
            elif criterion_id in MODULE.ORACLE_CRITERIA:
                result_digest = "b" * 64
                records.append(MODULE.criterion_record(
                    criterion_id, "UNCOVERED", expected=expected,
                    observed=expected, ledger=digest,
                    result_ledger=result_digest,
                    expectation="EIGENBASIS_CERTIFICATION_FAILED",
                    witness=["EIGENBASIS_CERTIFICATION_FAILED", expected,
                             result_digest]))
            elif criterion_id in MODULE.D12_CRITERIA:
                records.append(MODULE.criterion_record(
                    criterion_id, "INCOMPLETE", expected=expected,
                    ledger=digest))
            else:
                records.append(MODULE.criterion_record(
                    criterion_id, "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                    blocker=MODULE.CRITERION_IDS[0], expected=expected,
                    ledger=digest))
        return records

    def test_self_test_freezes_scope_and_honest_oracle_gap(self):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--self-test", "--json"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual(value["criterion_count"], 32)
        self.assertFalse(value["independent_primary_oracle_available"])
        self.assertFalse(value["qualification_pass_permitted_without_oracle"])

    def test_exact_binary64_common_denominator_covers_extremes(self):
        self.assertEqual(MODULE.exact_binary64_numerator(0.0), 0)
        self.assertEqual(MODULE.exact_binary64_numerator(2.0 ** -1074), 1)
        self.assertEqual(MODULE.exact_binary64_numerator(-(2.0 ** -1074)), -1)
        self.assertEqual(MODULE.exact_binary64_numerator(1.0), 1 << 1074)
        self.assertEqual(MODULE.exact_binary64_numerator(-2.0), -(1 << 1075))
        with self.assertRaises(MODULE.QualificationError):
            MODULE.exact_binary64_numerator(float("inf"))

    def test_effective_row_changes_only_anchor_and_sums_exactly(self):
        row = {"row_kind": "du", "source_ids": [2, 5, 9],
               "coefficients": [1.000000000000002, -0.5, -0.5]}
        raw = [MODULE.exact_binary64_numerator(value) for value in row["coefficients"]]
        effective = MODULE.effective_numerators(row, 5)
        self.assertEqual(effective[2], raw[0])
        self.assertEqual(effective[9], raw[2])
        self.assertNotEqual(effective[5], raw[1])
        self.assertEqual(sum(effective.values()), 0)

    def test_all_anchor_and_relabel_exact_functionals_are_canonical(self):
        row = {"row_kind": "position", "source_ids": [0, 2, 3],
               "coefficients": [0.25, 0.5000000000000001, 0.25]}
        face = [2, 3, 0]
        mappings = MODULE.relabel_maps(4)
        for anchor in face:
            original = MODULE.effective_numerators(row, anchor)
            for mapping in mappings.values():
                relabeled = MODULE.relabel_row(row, mapping)
                observed = MODULE.effective_numerators(relabeled, mapping[anchor])
                inverse = {value: key for key, value in mapping.items()}
                canonical = {inverse[key]: value for key, value in observed.items()}
                self.assertEqual(original, canonical)

    def test_jcs_rejects_negative_zero_and_formats_thresholds(self):
        self.assertEqual(MODULE.jcs_bytes({"b": 1e-7, "a": 1e-6}),
                         b'{"a":0.000001,"b":1e-7}')
        with self.assertRaises(MODULE.QualificationError):
            MODULE.jcs_bytes(-0.0)
        with self.assertRaises(MODULE.QualificationError):
            MODULE.jcs_bytes(float("nan"))

    def test_duplicate_json_keys_fail_closed(self):
        with self.assertRaises(MODULE.QualificationError):
            MODULE.strict_json_bytes(b'{"a":1,"a":2}')

    def test_availability_state_hash_reason_cross_product_is_closed(self):
        present = MODULE.availability("PRESENT", "a" * 64)
        self.assertIsNone(present["reason_code"])
        with self.assertRaises(MODULE.QualificationError):
            MODULE.availability("PRESENT", "0" * 64)
        with self.assertRaises(MODULE.QualificationError):
            MODULE.availability("MISSING", reason_code="TOOL_UNAVAILABLE")
        with self.assertRaises(MODULE.QualificationError):
            MODULE.availability("UNAVAILABLE", "a" * 64,
                                "EXECUTION_UNAVAILABLE")

    def test_schema_rejects_extra_top_level_and_nested_keys(self):
        schema = MODULE.load_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(all(
            definition.get("additionalProperties") is False
            for definition in schema["$defs"].values()
            if definition.get("type") == "object"))
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_schema_instance({"unexpected": True}, schema)

    def test_schema_itself_enforces_availability_conditionals(self):
        schema = MODULE.load_schema()
        availability_schema = schema["$defs"]["availability"]
        MODULE.validate_schema_instance(
            {"state": "UNAVAILABLE", "sha256": None,
             "reason_code": "EXECUTION_UNAVAILABLE"},
            availability_schema, schema)
        for mutation in (
                {"state": "PRESENT", "sha256": "a" * 64,
                 "reason_code": "CONTENT_INVALID"},
                {"state": "MISSING", "sha256": None,
                 "reason_code": "TOOL_UNAVAILABLE"},
                {"state": "INVALID", "sha256": "a" * 64,
                 "reason_code": "HASH_MISMATCH"},
                {"state": "PRESENT", "sha256": "0" * 64,
                 "reason_code": None}):
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_schema_instance(
                    mutation, availability_schema, schema)

    def test_binary_schema_has_complete_dependency_provenance_slots(self):
        schema = MODULE.load_schema()
        binary_required = set(schema["$defs"]["binary"]["required"])
        self.assertTrue({"compiler_command", "compiler_version", "link_map",
                         "dynamic_dependencies", "dependencies"}.issubset(binary_required))
        dependency_required = set(schema["$defs"]["dependency"]["required"])
        self.assertEqual(dependency_required, {
            "version", "source_archive", "build_provenance",
            "install_provenance", "link_map", "dynamic_dependencies"})
        self.assertEqual(set(schema["$defs"]["dependencies"]["required"]),
                         {"gmp", "mpfr", "opensubdiv"})
        with tempfile.TemporaryDirectory() as temporary:
            present = pathlib.Path(temporary) / "evidence"
            present.write_bytes(b"actual provenance bytes")
            self.assertEqual(MODULE.file_availability(present)["state"],
                             "PRESENT")
            self.assertEqual(
                MODULE.file_availability(pathlib.Path(temporary) / "missing")[
                    "reason_code"], "EXPECTED_PATH_MISSING")
            self.assertEqual(MODULE.file_availability(None)["reason_code"],
                             "EXECUTION_UNAVAILABLE")

    def test_criterion_set_is_exact_and_omission_needs_real_blocker(self):
        records = []
        for criterion_id in MODULE.CRITERION_IDS:
            if criterion_id in MODULE.INFRASTRUCTURE_CRITERIA:
                status, blocker = "INCOMPLETE", None
            elif criterion_id in MODULE.ORACLE_CRITERIA:
                status, blocker = "INCOMPLETE", None
            elif criterion_id in MODULE.D12_CRITERIA:
                status, blocker = "INCOMPLETE", None
            else:
                status = "OMITTED_AFTER_INFRASTRUCTURE_FAILURE"
                blocker = MODULE.CRITERION_IDS[0]
            records.append(MODULE.criterion_record(
                criterion_id, status, blocker=blocker,
                expected=MODULE.EXPECTED_CELL_COUNTS[criterion_id]))
        MODULE.validate_criteria(records)
        mutation = copy.deepcopy(records)
        mutation[-1]["criterion_id"] = "invented"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_criteria(mutation)
        with self.assertRaises(MODULE.QualificationError):
            MODULE.criterion_record(MODULE.CRITERION_IDS[1],
                                    "OMITTED_AFTER_INFRASTRUCTURE_FAILURE")

    def test_schema_freezes_every_criterion_slot_and_status_owner(self):
        schema = MODULE.load_schema()
        criteria_schema = schema["properties"]["criteria"]
        records = self.make_incomplete_criteria_fixture()
        MODULE.validate_schema_instance(records, criteria_schema, schema)
        self.assertEqual(len(criteria_schema["prefixItems"]), 32)
        for index, criterion_id in enumerate(MODULE.CRITERION_IDS):
            with self.subTest(index=index, mutation="id"):
                mutation = copy.deepcopy(records)
                mutation[index]["criterion_id"] = criterion_id + "_invented"
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.validate_schema_instance(
                        mutation, criteria_schema, schema)
            with self.subTest(index=index, mutation="count"):
                mutation = copy.deepcopy(records)
                mutation[index]["expected_cell_count"] += 1
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.validate_schema_instance(
                        mutation, criteria_schema, schema)
        swapped = copy.deepcopy(records)
        swapped[3], swapped[4] = swapped[4], swapped[3]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_schema_instance(swapped, criteria_schema, schema)
        illegal_statuses = {0: "FAIL", 10: "FAIL", 14: "UNCOVERED",
                            27: "OMITTED_AFTER_INFRASTRUCTURE_FAILURE"}
        for index, status in illegal_statuses.items():
            with self.subTest(index=index, status=status):
                mutation = copy.deepcopy(records)
                mutation[index]["status"] = status
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.validate_schema_instance(
                        mutation, criteria_schema, schema)
        missing_result = copy.deepcopy(records)
        del missing_result[10]["result_ledger_sha256"]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_schema_instance(
                missing_result, criteria_schema, schema)

    def test_status_causality_rejects_later_or_wrong_class_blockers(self):
        records = self.make_incomplete_criteria_fixture()
        MODULE.validate_criteria(records)
        later = copy.deepcopy(records)
        later[3]["omission_blocker"] = MODULE.CRITERION_IDS[10]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_criteria(later)
        wrong_class = copy.deepcopy(records)
        wrong_class[3]["status"] = "OMITTED_AFTER_CANDIDATE_FAILURE"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_criteria(wrong_class)
        infrastructure_fail = copy.deepcopy(records)
        infrastructure_fail[0]["status"] = "FAIL"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_criteria(infrastructure_fail)

    def test_missing_oracle_binding_is_infrastructure_incomplete(self):
        cases = [{"content_identity_key": "content-{:03d}".format(index),
                  "candidate": "bfr" if index < 196 else "far",
                  "approximation_level": 2 + (index % 7),
                  "applicable_mode": "cache_disabled"}
                 for index in range(294)]
        ledgers = MODULE.make_pre_result_ledgers(
            {"binding": {"git_head": "a" * 40}, "numeric_cases": cases})
        criteria = MODULE.make_criteria(
            MODULE.worktree_observation(True), False, ledgers)
        self.assertEqual(criteria[0]["status"], "INCOMPLETE")
        self.assertEqual(criteria[3]["status"],
                         "OMITTED_AFTER_INFRASTRUCTURE_FAILURE")
        self.assertEqual(criteria[10]["status"], "UNCOVERED")
        self.assertTrue(all(criteria[index]["status"] == "INCOMPLETE"
                            for index in range(27, 32)))

    def test_omitted_result_retains_materialized_pre_result_ledger(self):
        digest = "a" * 64
        ledgers = [{
            "criterion_id": criterion_id,
            "partition": ("oracle_request" if criterion_id ==
                          "oracle_coverage_and_crosscheck" else "all"),
            "expected_count": MODULE.EXPECTED_CELL_COUNTS[criterion_id],
            "observed_count": MODULE.EXPECTED_CELL_COUNTS[criterion_id],
            "key_ledger_sha256": digest,
            "availability": MODULE.availability("PRESENT", digest),
            "omission_blocker": None,
        } for criterion_id in MODULE.CRITERION_IDS]
        criteria = MODULE.make_criteria(
            MODULE.worktree_observation(True), False, ledgers)
        self.assertEqual(criteria[10]["status"], "UNCOVERED")
        self.assertEqual(criteria[10]["observed_cell_count"],
                         MODULE.EXPECTED_CELL_COUNTS[
                             "oracle_coverage_and_crosscheck"])
        self.assertEqual(criteria[10]["key_ledger_sha256"], digest)

    def test_verdict_precedence_never_turns_uncovered_into_pass(self):
        records = [MODULE.criterion_record(identifier, "PASS")
                   for identifier in MODULE.CRITERION_IDS]
        records[10] = MODULE.criterion_record(
            "oracle_coverage_and_crosscheck", "UNCOVERED",
            expectation="EIGENBASIS_CERTIFICATION_FAILED")
        verdict = MODULE.calculate_verdict(records)
        self.assertEqual(verdict["status"], "INCOMPLETE")
        self.assertEqual(verdict["first_decisive_criterion"],
                         "oracle_coverage_and_crosscheck")
        records[3] = MODULE.criterion_record("representation_structure", "FAIL")
        self.assertEqual(MODULE.calculate_verdict(records)["status"], "FAIL")

    def test_verdict_uses_single_frozen_order_for_uncovered_and_incomplete(self):
        records = [MODULE.criterion_record(identifier, "PASS")
                   for identifier in MODULE.CRITERION_IDS]
        records[10] = MODULE.criterion_record(
            "oracle_coverage_and_crosscheck", "UNCOVERED")
        records[27] = MODULE.criterion_record(
            "d12_preparation_cost", "INCOMPLETE")
        self.assertEqual(MODULE.calculate_verdict(records)[
            "first_decisive_criterion"], "oracle_coverage_and_crosscheck")
        records[0] = MODULE.criterion_record(
            "bindings_and_independence", "INCOMPLETE")
        self.assertEqual(MODULE.calculate_verdict(records)[
            "first_decisive_criterion"], "bindings_and_independence")

    def test_serial_only_disposition_is_exactly_race_only(self):
        records = [MODULE.criterion_record(identifier, "PASS")
                   for identifier in MODULE.CRITERION_IDS]
        records[-1] = MODULE.criterion_record(
            "d12_instrumented_tsan", "FAIL")
        key = ["content", 7, "tsan", "threaded_cache", 2, 1, 0,
               None, None, None, None, None, "thread_result", "row_digest"]
        context = {"complete_tsan_tuple_count": 588,
                   "complete_tsan_cell_count": MODULE.EXPECTED_CELL_COUNTS[
                       "d12_instrumented_tsan"],
                   "cache_disabled_tsan_pass": True,
                   "failures": [{"key": key,
                                  "reason": "THREADED_CACHE_RACE"}]}
        verdict = MODULE.calculate_verdict(records, context)
        self.assertTrue(verdict["serial_only_qualification_eligible"])
        self.assertEqual(verdict["serial_only_reason"],
                         "ELIGIBLE_PENDING_EXPLICIT_USER_DECISION")
        self.assertEqual(verdict["threaded_only_failure_ledger_sha256"],
                         MODULE.generic_key_ledger_sha256([key]))
        for mutation in (
                {"complete_tsan_tuple_count": 587},
                {"cache_disabled_tsan_pass": False},
                {"failures": [{"key": key,
                               "reason": "THREADED_CACHE_OUTPUT_MISMATCH"}]},
                {"failures": []}):
            changed = copy.deepcopy(context)
            changed.update(mutation)
            self.assertFalse(MODULE.calculate_verdict(
                records, changed)["serial_only_qualification_eligible"])
        scientific_fail = copy.deepcopy(records)
        scientific_fail[3]["status"] = "FAIL"
        self.assertFalse(MODULE.calculate_verdict(
            scientific_fail, context)["serial_only_qualification_eligible"])

    def test_git_binding_rejects_old_checkpoint_and_midrun_head_change(self):
        head = "a" * 40
        identity = {"state": "PRESENT", "git_commit": head,
                    "reason_code": None}
        clean = {"state": "PRESENT", "clean": True, "reason_code": None}
        MODULE.require_git_binding(identity, copy.deepcopy(identity), clean,
                                   copy.deepcopy(clean), head, head)
        old_checkpoint = "b" * 40
        with self.assertRaises(MODULE.QualificationError):
            MODULE.require_git_binding(identity, copy.deepcopy(identity), clean,
                                       copy.deepcopy(clean), head, old_checkpoint)
        changed_end = {"state": "PRESENT", "git_commit": "c" * 40,
                       "reason_code": None}
        with self.assertRaises(MODULE.QualificationError):
            MODULE.require_git_binding(identity, changed_end, clean,
                                       copy.deepcopy(clean), head, head)

    def test_scientific_ledger_rejects_duplicate_keys(self):
        key = ["content", "cache_disabled", 7, 0, 0, "sample", "du",
               "exact_effective", "v0", "identity", None, "x", None,
               None, None]
        digest = MODULE.ledger_sha256([key])
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        with self.assertRaises(MODULE.QualificationError):
            MODULE.ledger_sha256([key, copy.deepcopy(key)])

    def test_streaming_scientific_ledger_matches_frozen_outer_array_hash(self):
        keys = [
            ["content", "cache_disabled", 7, face, None, "sample", "position",
             "structural", anchor, "identity", None, None, None, None, None]
            for face in (0, 10, 2) for anchor in MODULE.ANCHORS
        ]
        for key in keys:
            MODULE.validate_scientific_cell_key(key, "representation_structure")
        encoded = sorted(MODULE.jcs_bytes(key) for key in keys)
        stream = MODULE.StreamingScientificLedger("representation_structure")
        for item in encoded:
            stream.add_encoded(item)
        self.assertEqual(stream.finish(), MODULE.ledger_sha256(keys))
        duplicate = MODULE.StreamingScientificLedger("representation_structure")
        duplicate.add_encoded(encoded[0])
        with self.assertRaises(MODULE.QualificationError):
            duplicate.add_encoded(encoded[0])

    def test_result_ledger_binds_outcome_value_and_rejects_duplicate_key(self):
        key = ["content", "cache_disabled", 7, 0, None, "sample",
               "position", "structural", "v0", "identity", None, None,
               None, None, None]
        encoded = MODULE.jcs_bytes(key)
        first = MODULE.StreamingResultLedger("first")
        first.add_encoded(encoded, "PASS", "01", "01", None)
        first_digest = first.finish()
        changed = MODULE.StreamingResultLedger("changed")
        changed.add_encoded(encoded, "FAIL", "00", "01", "MISMATCH")
        self.assertNotEqual(first_digest, changed.finish())
        duplicate = MODULE.StreamingResultLedger("duplicate")
        duplicate.add_encoded(encoded, "PASS")
        with self.assertRaises(MODULE.QualificationError):
            duplicate.add_encoded(encoded, "PASS")

    def test_oracle_absence_is_empty_covered_full_uncovered(self):
        request_digest = "c" * 64
        count = MODULE.EXPECTED_CELL_COUNTS[
            "oracle_coverage_and_crosscheck"]
        partitions = MODULE.oracle_absent_partition_ledgers(
            request_digest, count)
        self.assertEqual([item["partition"] for item in partitions],
                         ["covered", "uncovered"])
        self.assertEqual(partitions[0]["observed_count"], 0)
        self.assertEqual(partitions[0]["key_ledger_sha256"],
                         MODULE.sha256_bytes(b"[]"))
        self.assertEqual(partitions[1]["observed_count"], count)
        self.assertEqual(partitions[1]["key_ledger_sha256"], request_digest)
        self.assertTrue(all(item["availability"]["state"] == "PRESENT"
                            for item in partitions))

    def test_numeric_maximum_witness_mutations_fail_closed(self):
        records = self.make_incomplete_criteria_fixture()
        index = MODULE.CRITERION_IDS.index(
            "anchor_sensitivity_exact_coeff")
        key = ["content", "cache_disabled", 7, 0, None, "sample", "du",
               "exact_effective", None, "identity", None, None, "v0_v1",
               None, None]
        digest = "d" * 64
        maximum = 0.25
        records[index] = MODULE.criterion_record(
            "anchor_sensitivity_exact_coeff", "PASS",
            expected=MODULE.EXPECTED_CELL_COUNTS[
                "anchor_sensitivity_exact_coeff"],
            observed=MODULE.EXPECTED_CELL_COUNTS[
                "anchor_sensitivity_exact_coeff"],
            ledger="e" * 64, result_ledger=digest, maximum=maximum,
            witness=[key, {"numerator": 1, "denominator": 4},
                     MODULE.binary64_bits_hex(maximum), digest])
        MODULE.validate_criteria(records)
        for witness_index, replacement in ((0, ["bad"]),
                                           (2, MODULE.binary64_bits_hex(0.5)),
                                           (3, "f" * 64)):
            mutation = copy.deepcopy(records)
            mutation[index]["witness"][witness_index] = replacement
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_criteria(mutation)

    def test_preoracle_suffixes_cover_exact_frozen_dimensions(self):
        suffixes = MODULE._validate_suffix_definitions()
        self.assertEqual(len(suffixes["representation_structure"]), 3)
        self.assertEqual(len(suffixes["constant_field_bits"]), 45)
        self.assertEqual(len(suffixes[
            "relabel_exact_effective_coefficients"]), 6)
        self.assertEqual(len(suffixes["cache_mode_bit_identity"]), 3)
        self.assertEqual(set(MODULE.CANDIDATE_CHALLENGES),
                         set(MODULE.CHALLENGES))
        basis = MODULE._frozen_scientific_suffixes()
        self.assertNotIn("binary64_basis_probe_diagnostic", basis)
        basis_key = ["content", "cache_disabled", 7, 0, None, "sample",
                     "du", "emitted_binary64", "v1", "rank_rotate_1", 9,
                     None, None, None, None]
        MODULE.validate_scientific_cell_key(
            basis_key, "binary64_basis_probe_diagnostic")

    def test_exact_regular_box_spline_rows_and_patch_inventory(self):
        rows = MODULE.regular_box_spline_rows(
            MODULE.Fraction(1, 6), MODULE.Fraction(1, 6))
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(len(row) == 12 for row in rows))
        self.assertEqual(sum(rows[0]), 1)
        self.assertTrue(all(sum(row) == 0 for row in rows[1:]))
        inventory = MODULE.regular_patch_inventory(MODULE.B2.load_manifest())
        self.assertEqual(len(inventory), 14)
        self.assertTrue(any(item["patches"] for item in inventory.values()))

    def test_scientific_nullable_dimensions_are_criterion_specific(self):
        key = ["content", "cache_disabled", 7, 0, 0, "sample", "du",
               "emitted_binary64", "v0", "identity", None, "x", None,
               None, None]
        MODULE.validate_scientific_cell_key(
            key, "binary64_direct_geometry_fidelity")
        for index, replacement in ((11, None), (12, "v0_v1"),
                                   (13, "6_7"), (14, "positive_one")):
            mutation = copy.deepcopy(key)
            mutation[index] = replacement
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_scientific_cell_key(
                    mutation, "binary64_direct_geometry_fidelity")

        integrand = ["content", "serial_cache", 8, 2, None, "sample",
                     "area_integrand", "exact_effective", "v2", "identity",
                     None, None, None, None, None]
        MODULE.validate_scientific_cell_key(
            integrand, "regular_analytic_area_integrand")
        for index, replacement in ((6, "position"), (7, "structural"),
                                   (8, None), (11, "x"), (9, "rank_reverse")):
            mutation = copy.deepcopy(integrand)
            mutation[index] = replacement
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_scientific_cell_key(
                    mutation, "regular_analytic_area_integrand")

        exact_regular_row = [
            "content", "cache_disabled", 7, 0, None, "sample", "position",
            "exact_effective", "v0", "identity", None, None, None, None,
            None]
        MODULE.validate_scientific_cell_key(
            exact_regular_row, "regular_analytic_exact_rows")
        exact_regular_row[11] = "x"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_scientific_cell_key(
                exact_regular_row, "regular_analytic_exact_rows")

        pair = ["content", "cache_disabled", 7, 1, 0, "sample", "du",
                "exact_effective", None, "identity", None, "x", "v0_v1",
                None, None]
        MODULE.validate_scientific_cell_key(
            pair, "anchor_sensitivity_exact_geometry")
        pair[8] = "v0"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_scientific_cell_key(
                pair, "anchor_sensitivity_exact_geometry")

    def test_d12_nullable_dimensions_and_worker_bound_fail_closed(self):
        preparation = ["content", 7, "release", "cache_disabled", None,
                       None, None, "measured", 14, None, None, None, None,
                       "preparation_duration_ns"]
        MODULE.validate_d12_key(preparation, "d12_preparation_cost")
        mutation = copy.deepcopy(preparation)
        mutation[8] = None
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_d12_key(mutation, "d12_preparation_cost")
        threaded = ["content", 7, "tsan", "threaded_cache", 2, 2, 0,
                    None, None, None, None, None, "thread_result", "row_digest"]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_d12_key(threaded, "d12_instrumented_tsan")
        cache_disabled = ["content", 7, "tsan", "cache_disabled", 2, 1, 19,
                          None, None, None, None, None, "thread_result",
                          "row_digest"]
        MODULE.validate_d12_key(
            cache_disabled, "d12_cache_disabled_concurrency")
        wrong_mode = copy.deepcopy(cache_disabled)
        wrong_mode[3] = "threaded_cache"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_d12_key(
                wrong_mode, "d12_cache_disabled_concurrency")
        sanitizer = ["content", 7, "tsan", "threaded_cache", 4, None, None,
                     None, None, None, None, None, "sanitizer_summary",
                     "instrumentation_coverage"]
        MODULE.validate_d12_key(sanitizer, "d12_instrumented_tsan")
        rss = ["content", 7, "release", "serial_cache", None, None, None,
               "warmup", 2, 3, 1, "sample", "after_face_insert",
               "rss_bytes"]
        MODULE.validate_d12_key(rss, "d12_peak_rss")
        regular_rss = copy.deepcopy(rss)
        regular_rss[10] = None
        MODULE.validate_d12_key(regular_rss, "d12_peak_rss")
        rss[8] = 3
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_d12_key(rss, "d12_peak_rss")

    def test_d12_observed_head_probe_and_worktree_are_not_synthesized(self):
        head = "1" * 40
        probe_fingerprint = {"architecture": "observed-test-host",
                             "chip": "not-the-frozen-expected-chip"}
        evidence = {
            "release_checkpoint": {"binding": {"git_head": head}},
            "platform_qualification": {
                "status": "UNQUALIFIED_PLATFORM",
                "git_identity": {"head": head, "head_query_ok": True,
                                 "worktree_empty": True},
                "current_probe": {"fingerprint": probe_fingerprint},
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "d12.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            with mock.patch.object(MODULE.B2, "validate_evidence_document",
                                   return_value=True):
                record, expectation = MODULE.inspect_d12_evidence(path, head)
                self.assertEqual(record["availability"]["state"], "PRESENT")
                self.assertEqual(record["exact_head"], head)
                self.assertEqual(
                    record["physical_fingerprint_sha256"],
                    MODULE.sha256_bytes(MODULE.jcs_bytes(probe_fingerprint)))
                self.assertIn("representation work is not included",
                              expectation)

                old_head, _ = MODULE.inspect_d12_evidence(path, "2" * 40)
                self.assertEqual(old_head["availability"]["state"], "INVALID")
                dirty = copy.deepcopy(evidence)
                dirty["platform_qualification"]["git_identity"][
                    "worktree_empty"] = False
                path.write_text(json.dumps(dirty), encoding="utf-8")
                dirty_record, _ = MODULE.inspect_d12_evidence(path, head)
                self.assertEqual(dirty_record["availability"]["state"],
                                 "INVALID")

    def test_d12_malformed_and_qualified_without_representation_fail_closed(self):
        head = "3" * 40
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "d12.json"
            path.write_text('{"duplicate":1,"duplicate":2}',
                            encoding="utf-8")
            record, _ = MODULE.inspect_d12_evidence(path, head)
            self.assertEqual(record["availability"]["state"], "INVALID")
            qualified = {
                "release_checkpoint": {"binding": {"git_head": head}},
                "platform_qualification": {
                    "status": "QUALIFIED",
                    "git_identity": {"head": head, "head_query_ok": True,
                                     "worktree_empty": True},
                    "current_probe": {"fingerprint": {"chip": "Apple M5"}},
                },
            }
            path.write_text(json.dumps(qualified), encoding="utf-8")
            with mock.patch.object(MODULE.B2, "validate_evidence_document",
                                   return_value=True):
                record, _ = MODULE.inspect_d12_evidence(path, head)
            self.assertEqual(record["availability"]["state"], "INVALID")

    def test_pre_result_ledger_partition_is_never_empty(self):
        cases = []
        for index in range(294):
            cases.append({
                "content_identity_key": "content-{:03d}".format(index),
                "candidate": "bfr" if index < 196 else "far",
                "approximation_level": 2 + (index % 7),
                "applicable_mode": "cache_disabled" if index < 196 else
                                   "not_applicable_uncached",
            })
        checkpoint = {"binding": {"git_head": "a" * 40},
                      "numeric_cases": cases}
        ledgers = MODULE.make_pre_result_ledgers(checkpoint)
        self.assertEqual(len(ledgers), 34)
        self.assertEqual({item["criterion_id"] for item in ledgers},
                         set(MODULE.CRITERION_IDS))
        self.assertTrue(all(
            item["expected_count"] is not None or
            item["partition"] in ("covered", "uncovered")
            for item in ledgers))
        self.assertTrue(all(
            item["expected_count"] is None
            for item in ledgers
            if item["partition"] in ("covered", "uncovered")))
        self.assertEqual(
            [item["partition"] for item in ledgers
             if item["criterion_id"] == "oracle_coverage_and_crosscheck"],
            ["oracle_request", "covered", "uncovered"])
        schema = MODULE.load_schema()
        ledger_schema = schema["$defs"]["matrix"]["properties"]["ledgers"]
        MODULE.validate_schema_instance(ledgers, ledger_schema, schema)
        reordered = copy.deepcopy(ledgers)
        reordered[3], reordered[4] = reordered[4], reordered[3]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_schema_instance(reordered, ledger_schema, schema)

    def test_candidate_cpp_has_observable_round_points_and_executes(self):
        source = ROOT / "experiments/anchored_row_qualification/candidate.cpp"
        text = source.read_text(encoding="utf-8")
        self.assertIn("#pragma STDC FENV_ACCESS ON", text)
        self.assertIn("volatile double", text)
        self.assertNotIn("std::fma", text)
        with tempfile.TemporaryDirectory() as temporary:
            binary = pathlib.Path(temporary) / "candidate"
            compile_result = subprocess.run(
                ["/usr/bin/clang++", "-std=c++17", "-O3", "-fno-fast-math",
                 "-ffp-contract=off", str(source), "-o", str(binary)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            self_test = subprocess.run([str(binary), "--self-test"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            self.assertEqual(self_test.returncode, 0, self_test.stderr)
            request = "position 1 3fe0000000000000,3fd0000000000000,3fd0000000000000 " \
                      "3ff0000000000000,4000000000000000,4008000000000000"
            result = subprocess.run([str(binary), "--evaluate-line", request],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            bits = int(result.stdout.strip(), 16)
            observed = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
            self.assertTrue(math.isfinite(observed))
            integrand = subprocess.run(
                [str(binary), "--integrand-stream"],
                input=("3ff0000000000000,4000000000000000,4008000000000000,"
                       "3ff0000000000000,0000000000000000,0000000000000000,"
                       "0000000000000000,3ff0000000000000,0000000000000000\n"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(integrand.returncode, 0, integrand.stderr)
            self.assertEqual(integrand.stdout.strip(),
                             "3ff0000000000000 0000000000000000")
            audit_input = "\n".join((
                "position 3 0,1,2 0,1,2 "
                "3fd0000000000000,3fe0000000000000,3fd0000000000000",
                "du 3 0,1,2 0,1,2 "
                "3ff0000000000000,bff0000000000000,0000000000000000",
            )) + "\n"
            audit = subprocess.run(
                [str(binary), "--audit-stream"], input=audit_input,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(audit.returncode, 0, audit.stderr)
            value = json.loads(audit.stdout)
            self.assertEqual(value["row_count"], 2)
            self.assertEqual(value["structure_cell_count"], 6)
            self.assertEqual(value["constant_cell_count"], 90)
            self.assertEqual(value["relabel_exact_cell_count"], 12)
            self.assertEqual(value["structure_failure_count"], 0)
            self.assertEqual(value["constant_failure_count"], 0)
            self.assertEqual(value["relabel_exact_failure_count"], 0)
            mutation = subprocess.run(
                [str(binary), "--audit-stream"],
                input="du 3 0,1,2 0,0,2 "
                      "3ff0000000000000,bff0000000000000,0000000000000000\n",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(mutation.returncode, 0)
            self.assertIn("source order", mutation.stderr)

            scale_numerator = 2 * (1 << 2148)
            target_numerator = 5
            boundary1074 = math.isqrt(
                target_numerator * target_numerator * scale_numerator)
            boundary2148 = math.isqrt(
                (target_numerator * target_numerator * scale_numerator)
                << 2148)
            coefficients = ",".join(MODULE.binary64_bits_hex(value)
                                    for value in (0.25, 0.5, 0.25))
            x_values = ",".join(MODULE.binary64_bits_hex(value)
                                for value in (0.0, 1.0, 0.0))
            y_values = ",".join(MODULE.binary64_bits_hex(value)
                                for value in (0.0, 0.0, 1.0))
            z_values = ",".join(MODULE.binary64_bits_hex(0.0)
                                for _ in range(3))
            component_input = (
                "6_7 position 3 0,1,2 0,1,2 {0} 0,1,2 {0} 0,1,2 "
                "{1} {2} {3} {4:x} {5:x} {6:x}\n").format(
                    coefficients, x_values, y_values, z_values,
                    scale_numerator, boundary1074, boundary2148)
            component = subprocess.run(
                [str(binary), "--component-audit-stream"],
                input=component_input, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            self.assertEqual(component.returncode, 0, component.stderr)
            component_value = json.loads(component.stdout)
            self.assertEqual(component_value["row_count"], 1)
            self.assertEqual(component_value["status"], "ok")
            self.assertEqual(component_value["criteria"][
                "binary64_basis_probe_diagnostic"]["cell_count"], 27)
            self.assertEqual(component_value["criteria"][
                "binary64_direct_geometry_fidelity"]["cell_count"], 27)
            bad_coefficients = ",".join(MODULE.binary64_bits_hex(value)
                                        for value in (0.25001, 0.5, 0.25))
            bad_component = subprocess.run(
                [str(binary), "--component-audit-stream"],
                input=component_input.replace(coefficients,
                                              bad_coefficients),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(bad_component.returncode, 0,
                             bad_component.stderr)
            bad_value = json.loads(bad_component.stdout)
            self.assertEqual(bad_value["status"], "candidate_failure")
            self.assertGreater(bad_value["criteria"][
                "anchor_sensitivity_exact_coeff"]["failure_count"], 0)
            self.assertIsNotNone(bad_value["criteria"][
                "anchor_sensitivity_exact_coeff"]["first_failure"])

    def test_boundary_source_freezes_mpfr_directions_and_uncovers_primary(self):
        source = (ROOT / "experiments/anchored_row_qualification/"
                 "exact_dyadic_boundary.cpp").read_text(encoding="utf-8")
        for anchor in ("MPFR_RNDD", "MPFR_RNDU", "mpfr_set_z_2exp",
                       "kPrecision = 544", "EIGENBASIS_CERTIFICATION_FAILED",
                       "uniform_success_substituted_for_primary\\\":false",
                       "regular_integrand_stream", "interval_square_root"):
            self.assertIn(anchor, source)
        for forbidden in MODULE.B2.FORBIDDEN_ORACLE_TOKENS:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
