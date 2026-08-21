import copy
import gzip
import importlib.util
import json
import math
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_anchored_row_qualification.py"
SPEC = importlib.util.spec_from_file_location("anchored_row_qualification", RUNNER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AnchoredRowQualificationTests(unittest.TestCase):
    def present_result_artifact(self, criterion_id, digest, count):
        ordinal = MODULE.CRITERION_IDS.index(criterion_id)
        return {"availability": MODULE.availability("PRESENT", digest),
                "relative_path":
                    "anchored-row-result-ledgers-v1/{:02d}-{}."
                    "result-ledger.json".format(ordinal, criterion_id),
                "byte_length": 2, "record_count": count}

    def make_incomplete_criteria_fixture(self):
        digest = "a" * 64
        records = []
        for criterion_id in MODULE.CRITERION_IDS:
            expected = MODULE.EXPECTED_CELL_COUNTS[criterion_id]
            if criterion_id in MODULE.INFRASTRUCTURE_CRITERIA:
                target = None
                if criterion_id == "complete_artifact_inventory":
                    target = {
                        "kind": "unexpected_paths_target_v1",
                        "required_record_count": 0,
                        "sidecar": {
                            "availability": MODULE.availability(
                                "PRESENT", MODULE.sha256_bytes(b"[]")),
                            "relative_path":
                                "anchored-row-result-ledgers-v1/"
                                "unexpected-artifact-paths.json",
                            "byte_length": 2, "record_count": 0,
                            "sha256": MODULE.sha256_bytes(b"[]")}}
                records.append(MODULE.criterion_record(
                    criterion_id, "INCOMPLETE", expected=expected,
                    target=target))
            elif criterion_id in MODULE.ORACLE_CRITERIA:
                result_digest = "b" * 64
                records.append(MODULE.criterion_record(
                    criterion_id, "UNCOVERED", expected=expected,
                    observed=expected, ledger=digest,
                    result_ledger=result_digest,
                    result_merkle_root="c" * 64,
                    result_artifact=self.present_result_artifact(
                        criterion_id, result_digest, expected),
                    witness=None))
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
        self.assertTrue(value["independent_primary_oracle_available"])
        self.assertFalse(value["qualification_pass_permitted_without_oracle"])

    def test_documentation_owned_schema_path_anchor_is_immutable(self):
        lines = MODULE.documentation_owned_schema_path_anchor()
        self.assertEqual(len(lines), 740)
        self.assertEqual(len(lines), len(set(lines)))
        self.assertEqual(lines, sorted(lines))
        counts = {}
        for line in lines:
            kind = line.split("|", 1)[0]
            counts[kind] = counts.get(kind, 0) + 1
        self.assertEqual(counts, {
            "array": 71,
            "authority": 26,
            "criterion": 32,
            "ledger": 34,
            "object": 577,
        })
        self.assertEqual(
            MODULE.APPROVED_RESULT_EVIDENCE_AMENDMENT_MERGE,
            "67e5c2c84c907fe79bab257d992fbcbdf0480d48")
        self.assertEqual(
            MODULE.load_schema()["$defs"]["identity"]["properties"][
                "approved_b2b_merge_git_commit"]["const"],
            MODULE.APPROVED_RESULT_EVIDENCE_AMENDMENT_MERGE)

    def test_executable_schema_rederives_anchor_and_full_mutation_manifest(self):
        schema = MODULE.load_schema()
        documentation_paths = MODULE.documentation_owned_schema_path_anchor()
        executable_paths = MODULE.RESULT_CONTRACT.derive_schema_path_anchor(
            schema)
        self.assertEqual(executable_paths, documentation_paths)
        documentation_manifest = MODULE.literal_mutation_manifest()
        executable_manifest = MODULE.RESULT_CONTRACT.expand_mutation_manifest(
            executable_paths)
        self.assertEqual(executable_manifest, documentation_manifest)
        counts = {}
        for mutation in executable_manifest:
            operator = mutation.split("|", 1)[0]
            counts[operator] = counts.get(operator, 0) + 1
        self.assertEqual(set(counts),
                         {"M{:02d}".format(index)
                          for index in range(1, 24)})
        self.assertEqual(counts["M01"], 577)
        self.assertEqual(counts["M02"], 97)
        self.assertEqual(counts["M03"], 577)
        for operator in ("M04", "M05", "M06", "M07"):
            self.assertEqual(counts[operator], 71 * 3)
        self.assertEqual(counts["M08"], 32 * 4)
        self.assertEqual(counts["M09"], 32 * 5)
        self.assertEqual(counts["M10"], 34 * 4)
        self.assertEqual(counts["M11"], 32 * 6)
        self.assertEqual(counts["M12"], 32 * 9)
        self.assertEqual(counts["M16"], 26)

    def test_all_3506_literal_mutations_have_executable_rejections(self):
        rejected = MODULE.execute_literal_mutation_suite()
        self.assertEqual(rejected, MODULE.literal_mutation_manifest())

    def test_report_reachable_references_use_only_reviewed_definitions(self):
        schema = MODULE.load_schema()
        self.assertEqual(schema["$defs"]["binary"]["properties"]["sources"][
            "items"], {"$ref": "#/$defs/source_binding"})
        self.assertEqual(schema["$defs"]["criterion"]["properties"][
            "result_ledger_artifact"],
            {"$ref": "#/$defs/result_ledger_artifact"})
        self.assertEqual(schema["$defs"]["matrix"]["properties"][
            "unexpected_paths"],
            {"$ref": "#/$defs/unexpected_paths_target_v1"})
        self.assertEqual(schema["properties"]["d12_artifact"],
                         {"$ref": "#/$defs/d12_artifact_binding"})

    def test_frozen_actual_fixture_inventory_is_const(self):
        schema = MODULE.load_schema()
        authority = MODULE.frozen_authority_record()
        node = schema["$defs"]["authority"]["properties"][
            "actual_fixture_files"]
        MODULE.validate_schema_instance(
            authority["actual_fixture_files"], node, schema)
        mutation = copy.deepcopy(authority["actual_fixture_files"])
        mutation[0]["sha256"] = "0" * 64
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_schema_instance(mutation, node, schema)

    def test_m01_m02_m03_are_exhaustive_over_closed_schema_objects(self):
        schema = MODULE.load_schema()
        approved = MODULE.documentation_owned_schema_path_anchor()
        objects = []

        def collect(node):
            if isinstance(node, dict):
                if "x-contract-object-name" in node:
                    objects.append(node)
                for value in node.values():
                    collect(value)
            elif isinstance(node, list):
                for value in node:
                    collect(value)

        collect(schema)
        self.assertEqual(len(objects), 97)
        examined_members = 0
        for object_schema in objects:
            self.assertFalse(object_schema["additionalProperties"])
            required = object_schema["required"]
            properties = object_schema["properties"]
            self.assertEqual(set(required), set(properties))
            for index, member in enumerate(tuple(required)):
                examined_members += 1
                removed = required.pop(index)
                self.assertNotEqual(
                    MODULE.RESULT_CONTRACT.derive_schema_path_anchor(schema),
                    approved)
                required.insert(index, removed)
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.validate_schema_instance(
                        (), properties[member], schema,
                        "$wrong_type.{}.{}".format(
                            object_schema["x-contract-object-name"], member))
            required.append("__unexpected_contract_member__")
            properties["__unexpected_contract_member__"] = {}
            self.assertNotEqual(
                MODULE.RESULT_CONTRACT.derive_schema_path_anchor(schema),
                approved)
            required.pop()
            del properties["__unexpected_contract_member__"]
        self.assertEqual(examined_members, 577)

    def test_m09_freezes_every_criterion_expectation_target_and_nullability(self):
        schema = MODULE.load_schema()
        criteria_schema = schema["properties"]["criteria"]
        records = self.make_incomplete_criteria_fixture()
        MODULE.validate_schema_instance(records, criteria_schema, schema)
        for index, record in enumerate(records):
            for field, replacement in (
                    ("expectation", record["expectation"] + "_drift"),
                    ("applicability", "invented"),
                    ("target", {} if record["target"] is None else None),
                    ("status", "INVENTED")):
                with self.subTest(index=index, field=field):
                    mutation = copy.deepcopy(records)
                    mutation[index][field] = replacement
                    with self.assertRaises(MODULE.QualificationError):
                        MODULE.validate_schema_instance(
                            mutation, criteria_schema, schema)
            mutation = copy.deepcopy(records)
            del mutation[index]["witness"]
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_schema_instance(
                    mutation, criteria_schema, schema)

    def test_inventory_target_binds_canonical_empty_sidecar(self):
        digest = MODULE.sha256_bytes(b"[]")
        target = {
            "kind": "unexpected_paths_target_v1",
            "required_record_count": 0,
            "sidecar": {
                "availability": MODULE.availability("PRESENT", digest),
                "relative_path":
                    "anchored-row-result-ledgers-v1/"
                    "unexpected-artifact-paths.json",
                "byte_length": 2, "record_count": 0, "sha256": digest}}
        MODULE.validate_contract_value("unexpected_paths_target_v1", target)
        for field, replacement in (("relative_path", "other.json"),
                                   ("byte_length", 3),
                                   ("record_count", 1),
                                   ("sha256", "0" * 64)):
            mutation = copy.deepcopy(target)
            mutation["sidecar"][field] = replacement
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_contract_value(
                    "unexpected_paths_target_v1", mutation)

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
        self.assertEqual(criteria[10]["status"], "INCOMPLETE")
        self.assertEqual(criteria[10]["observed_cell_count"], 0)
        self.assertIsNone(criteria[10]["result_ledger_sha256"])
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
        self.assertEqual(criteria[10]["status"], "INCOMPLETE")
        self.assertEqual(criteria[10]["observed_cell_count"], 0)
        self.assertIsNone(criteria[10]["result_ledger_sha256"])
        self.assertEqual(criteria[10]["key_ledger_sha256"], digest)

    def test_inventory_evidence_uses_its_explicit_aggregate_target(self):
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
        empty_digest = MODULE.sha256_bytes(b"[]")
        target = {
            "kind": "unexpected_paths_target_v1",
            "required_record_count": 0,
            "sidecar": {
                "availability": MODULE.availability(
                    "PRESENT", empty_digest),
                "relative_path":
                    "anchored-row-result-ledgers-v1/"
                    "unexpected-artifact-paths.json",
                "byte_length": 2,
                "record_count": 0,
                "sha256": empty_digest,
            },
        }
        observed_count = MODULE.EXPECTED_CELL_COUNTS[
            "complete_artifact_inventory"]
        inventory = {
            "status": "PASS",
            "observed_count": observed_count,
            "commitment": {
                "key_ledger_sha256": digest,
                "result_ledger_sha256": "b" * 64,
                "result_merkle_root_sha256": "c" * 64,
            },
            "artifact": {
                "availability": MODULE.availability("PRESENT", "b" * 64),
                "relative_path": MODULE.result_ledger_relative_path(
                    "complete_artifact_inventory"),
                "byte_length": 2,
                "record_count": observed_count,
            },
            "target": target,
            "unexpected_paths": target,
            "maximum": None,
            "witness": None,
            "first_failing_key": None,
        }
        infrastructure = {"complete_artifact_inventory": inventory}
        criteria = MODULE.make_criteria(
            MODULE.worktree_observation(True), False, ledgers,
            infrastructure=infrastructure)
        self.assertEqual(criteria[1]["target"], target)
        MODULE.validate_criteria(criteria)

        for field in ("target", "unexpected_paths"):
            mutation = copy.deepcopy(inventory)
            mutation.pop(field)
            with self.subTest(missing=field):
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.make_criteria(
                        MODULE.worktree_observation(True), False, ledgers,
                        infrastructure={
                            "complete_artifact_inventory": mutation})
            mutation = copy.deepcopy(inventory)
            mutation[field] = None
            with self.subTest(null=field):
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.make_criteria(
                        MODULE.worktree_observation(True), False, ledgers,
                        infrastructure={
                            "complete_artifact_inventory": mutation})

        unavailable = copy.deepcopy(inventory)
        unavailable["target"] = MODULE.unavailable_unexpected_paths_target()
        unavailable["unexpected_paths"] = unavailable["target"]
        criteria = MODULE.make_criteria(
            MODULE.worktree_observation(True), False, ledgers,
            infrastructure={"complete_artifact_inventory": unavailable})
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_criteria(criteria)

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
        failures = [[key, "THREADED_CACHE_RACE"]]
        context = {
            "tuple_count": 588, "all_tuple_keys_sha256": "a" * 64,
            "cache_disabled_concurrency_cell_count": 13720,
            "cache_disabled_concurrency_ledger_sha256": "a" * 64,
            "cache_disabled_concurrency_pass": True,
            "cache_disabled_tsan_summary_cell_count": 588,
            "cache_disabled_tsan_summary_sha256": "a" * 64,
            "cache_disabled_tsan_pass": True,
            "threaded_tsan_summary_cell_count": 588,
            "threaded_tsan_summary_sha256": "a" * 64,
            "threaded_tsan_row_digest_cell_count": 13720,
            "threaded_tsan_row_digest_sha256": "a" * 64,
            "all_tsan_cell_count": 14896,
            "all_tsan_result_ledger_sha256": "a" * 64,
            "failure_records": failures,
            "failure_records_sha256": MODULE.sha256_bytes(
                MODULE.jcs_bytes(failures))}
        verdict = MODULE.calculate_verdict(records, context)
        self.assertTrue(verdict["serial_only_qualification_eligible"])
        self.assertEqual(verdict["serial_only_reason"],
                         "ELIGIBLE_PENDING_EXPLICIT_USER_DECISION")
        self.assertEqual(verdict["threaded_only_failure_ledger_sha256"],
                         MODULE.sha256_bytes(MODULE.jcs_bytes(failures)))
        for mutation in (
                {"tuple_count": 587},
                {"cache_disabled_tsan_pass": False},
                {"failure_records": [
                    [key, "THREADED_CACHE_OUTPUT_MISMATCH"]]},
                {"failure_records": []}):
            changed = copy.deepcopy(context)
            changed.update(mutation)
            if "failure_records" in mutation:
                changed["failure_records_sha256"] = MODULE.sha256_bytes(
                    MODULE.jcs_bytes(changed["failure_records"]))
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

    def test_oracle_uncovered_records_propagate_exactly_to_d10_dependents(self):
        reasons = ("EIGENBASIS_CERTIFICATION_FAILED",
                   "UNIFORM_CROSSCHECK_FAILED")

        def records_by_criterion(mutation=None):
            records = {criterion_id: [] for criterion_id in
                       ("oracle_coverage_and_crosscheck",) + tuple(
                           identifier for identifier in MODULE.CRITERION_IDS
                           if identifier in
                           MODULE.ORACLE_DEPENDENT_CRITERIA)}
            for face_id, reason in zip((0, 1), reasons):
                coeff_key = MODULE._criterion_mutation_key(
                    "exact_effective_d10_coeff")
                coeff_key[3] = face_id
                oracle_key = MODULE.oracle_request_key_for_dependent_key(
                    "exact_effective_d10_coeff", coeff_key)
                records["oracle_coverage_and_crosscheck"].append([
                    oracle_key, "UNCOVERED", None, None, reason])
                for criterion_id in MODULE.ORACLE_DEPENDENT_CRITERIA:
                    axes = (("x", "y", "z") if criterion_id in getattr(
                            MODULE.OracleUncoveredPropagationVerifier,
                            "AXIS_CRITERIA") else (None,))
                    for axis in axes:
                        key = MODULE._criterion_mutation_key(criterion_id)
                        key[3] = face_id
                        key[11] = axis
                        target = MODULE.absolute_rational_target(
                            MODULE._row_target_denominator(criterion_id, key))
                        records[criterion_id].append([
                            key, "UNCOVERED", None, target, reason])
            if mutation == "gap":
                records["exact_effective_d10_coeff"].pop()
            elif mutation == "extra":
                extra = copy.deepcopy(
                    records["exact_effective_d10_coeff"][-1])
                extra[0][3] = 2
                records["exact_effective_d10_coeff"].append(extra)
            elif mutation == "wrong_reason":
                records["exact_effective_d10_coeff"][-1][4] = reasons[0]
            elif mutation == "axis_gap":
                records["exact_effective_d10_geometry"].pop()
            return records

        def verify(records):
            verifier = MODULE.OracleUncoveredPropagationVerifier()
            for criterion_id in ("oracle_coverage_and_crosscheck",) + tuple(
                    identifier for identifier in MODULE.CRITERION_IDS
                    if identifier in MODULE.ORACLE_DEPENDENT_CRITERIA):
                for record in sorted(
                        records[criterion_id],
                        key=lambda item: MODULE.jcs_bytes(item[0])):
                    verifier.add(criterion_id, record)
            return verifier.finish()

        summaries = verify(records_by_criterion())
        expected = summaries["oracle_coverage_and_crosscheck"]
        self.assertEqual(expected[0], 2)
        self.assertTrue(all(summaries[criterion_id] == expected
                            for criterion_id in
                            MODULE.ORACLE_DEPENDENT_CRITERIA))
        for mutation in ("gap", "extra", "wrong_reason", "axis_gap"):
            with self.subTest(mutation=mutation):
                with self.assertRaises(MODULE.QualificationError):
                    verify(records_by_criterion(mutation))

        failure_key = MODULE._criterion_mutation_key(
            "exact_effective_d10_coeff")
        MODULE.validate_criterion_result_outcomes(
            "exact_effective_d10_coeff", "UNCOVERED",
            {"PASS", "UNCOVERED"}, 2, None, None)
        MODULE.validate_criterion_result_outcomes(
            "exact_effective_d10_coeff", "FAIL",
            {"PASS", "FAIL", "UNCOVERED"}, 3,
            failure_key, failure_key)
        for status, outcomes in (
                ("PASS", {"PASS", "UNCOVERED"}),
                ("UNCOVERED", {"PASS", "FAIL", "UNCOVERED"}),
                ("FAIL", {"PASS", "UNCOVERED"})):
            with self.subTest(status=status, outcomes=outcomes):
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.validate_criterion_result_outcomes(
                        "exact_effective_d10_coeff", status, outcomes,
                        len(outcomes), failure_key, failure_key)

    def test_oracle_dependent_uncovered_form_and_aggregate_are_fail_closed(self):
        reason = "UNIFORM_CROSSCHECK_FAILED"
        for criterion_id in MODULE.ORACLE_DEPENDENT_CRITERIA:
            key = MODULE._criterion_mutation_key(criterion_id)
            target = MODULE.absolute_rational_target(
                MODULE._row_target_denominator(criterion_id, key))
            record = [key, "UNCOVERED", None, target, reason]
            MODULE.validate_contract_result_record(criterion_id, record)
            for mutation in (
                    [key, "PASS", None, target, None],
                    [key, "UNCOVERED", {"kind": "geometry_axis_v1"},
                     target, reason],
                    [key, "UNCOVERED", None, None, reason],
                    [key, "UNCOVERED", None, target,
                     "D10_GEOMETRY_TARGET_EXCEEDED"]):
                with self.subTest(criterion=criterion_id,
                                  mutation=mutation[1:]):
                    with self.assertRaises(MODULE.QualificationError):
                        MODULE.validate_contract_result_record(
                            criterion_id, mutation)

        criteria = self.make_incomplete_criteria_fixture()
        for criterion_id in MODULE.ORACLE_DEPENDENT_CRITERIA:
            index = MODULE.CRITERION_IDS.index(criterion_id)
            expected = MODULE.EXPECTED_CELL_COUNTS[criterion_id]
            digest = format(index + 1, "064x")
            criteria[index] = MODULE.criterion_record(
                criterion_id, "UNCOVERED", expected=expected,
                observed=expected, ledger="a" * 64,
                result_ledger=digest, result_merkle_root="c" * 64,
                result_artifact=self.present_result_artifact(
                    criterion_id, digest, expected),
                maximum=None, witness=None)
        MODULE.validate_criteria(criteria)
        verdict = MODULE.calculate_verdict(criteria)
        self.assertEqual(verdict["status"], "INCOMPLETE")
        self.assertEqual(verdict["first_decisive_criterion"],
                         "bindings_and_independence")
        mutation = copy.deepcopy(criteria)
        index = MODULE.CRITERION_IDS.index("exact_effective_d10_coeff")
        mutation[index]["maximum"] = MODULE._absolute_rational_descriptor(
            MODULE.Fraction(0, 1))
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_criteria(mutation)

    def test_persisted_oracle_propagation_binds_numeric_scan_and_partitions(self):
        reason = "EIGENBASIS_CERTIFICATION_FAILED"
        criterion_ids = ("oracle_coverage_and_crosscheck",
                         "exact_effective_d10_coeff",
                         "exact_effective_d10_geometry",
                         "emitted_direct_geometry_d10")

        def covered_records(criterion_id):
            if criterion_id == "oracle_coverage_and_crosscheck":
                return [MODULE._valid_oracle_covered_record()]
            base = MODULE._valid_result_record_for_mutation(criterion_id)
            if criterion_id not in {
                    "exact_effective_d10_geometry",
                    "emitted_direct_geometry_d10"}:
                return [base]
            result = []
            for axis in ("x", "y", "z"):
                record = copy.deepcopy(base)
                record[0][11] = axis
                record[2]["axis"] = axis
                MODULE.validate_contract_result_record(criterion_id, record)
                result.append(record)
            return result

        def uncovered_records(criterion_id):
            if criterion_id == "oracle_coverage_and_crosscheck":
                key = copy.deepcopy(covered_records(criterion_id)[0][0])
                key[3] = 1
                return [[key, "UNCOVERED", None, None, reason]]
            axes = (("x", "y", "z") if criterion_id in {
                    "exact_effective_d10_geometry",
                    "emitted_direct_geometry_d10"} else (None,))
            result = []
            for axis in axes:
                key = MODULE._criterion_mutation_key(criterion_id)
                key[3] = 1
                key[11] = axis
                target = MODULE.absolute_rational_target(
                    MODULE._row_target_denominator(criterion_id, key))
                result.append([key, "UNCOVERED", None, target, reason])
            return result

        records = {}
        for criterion_id in criterion_ids:
            records[criterion_id] = sorted(
                covered_records(criterion_id) +
                uncovered_records(criterion_id),
                key=lambda item: MODULE.jcs_bytes(item[0]))

        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary).resolve()
            criteria = []
            unavailable = MODULE.availability(
                "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE")
            for criterion_id in MODULE.CRITERION_IDS:
                if criterion_id in records:
                    commitment, artifact = (
                        MODULE.write_result_ledger_artifact(
                            output, criterion_id, records[criterion_id],
                            oracle_certification_authority=(
                                MODULE._ORACLE_CERTIFICATION_AUTHORITY
                                if criterion_id ==
                                "oracle_coverage_and_crosscheck" else None)))
                    criteria.append({
                        "criterion_id": criterion_id,
                        "result_ledger_artifact": artifact,
                        "observed_cell_count": len(records[criterion_id]),
                        "key_ledger_sha256": commitment[
                            "key_ledger_sha256"],
                        "result_ledger_sha256": commitment[
                            "result_ledger_sha256"],
                        "result_merkle_root_sha256": commitment[
                            "result_merkle_root_sha256"],
                        "status": "UNCOVERED", "maximum": None,
                        "witness": None, "first_failing_key": None,
                        "target": MODULE.report_criterion_target(
                            criterion_id)})
                else:
                    criteria.append({
                        "criterion_id": criterion_id,
                        "result_ledger_artifact": {
                            "availability": copy.deepcopy(unavailable),
                            "relative_path": None, "byte_length": None,
                            "record_count": None},
                        "observed_cell_count": 0,
                        "key_ledger_sha256": None,
                        "result_ledger_sha256": None,
                        "result_merkle_root_sha256": None,
                        "status": "INCOMPLETE", "maximum": None,
                        "witness": None, "first_failing_key": None,
                        "target": None})

            empty_digest = MODULE.sha256_bytes(b"[]")
            unexpected_target = {
                "kind": "unexpected_paths_target_v1",
                "required_record_count": 0,
                "sidecar": {
                    "availability": MODULE.availability(
                        "PRESENT", empty_digest),
                    "relative_path": MODULE.RESULT_LEDGER_DIRECTORY +
                        "/unexpected-artifact-paths.json",
                    "byte_length": 2, "record_count": 0,
                    "sha256": empty_digest}}
            criteria[1]["target"] = unexpected_target
            unexpected_path = output / unexpected_target["sidecar"][
                "relative_path"]
            unexpected_path.parent.mkdir(parents=True, exist_ok=True)
            unexpected_path.write_bytes(b"[]")

            oracle_records = records["oracle_coverage_and_crosscheck"]
            covered_keys = [record[0] for record in oracle_records
                            if record[1] == "PASS"]
            uncovered_keys = [record[0] for record in oracle_records
                              if record[1] == "UNCOVERED"]

            def partition(name, keys):
                digest = MODULE.generic_key_ledger_sha256(keys)
                return {
                    "criterion_id": "oracle_coverage_and_crosscheck",
                    "partition": name, "expected_count": None,
                    "observed_count": len(keys),
                    "key_ledger_sha256": digest,
                    "availability": MODULE.availability("PRESENT", digest),
                    "omission_blocker": None}

            report = {
                "criteria": criteria,
                "matrix": {
                    "ledgers": [partition("covered", covered_keys),
                                partition("uncovered", uncovered_keys)],
                    "unexpected_paths": unexpected_target}}
            checkpoint = output / "checkpoint.json"
            checkpoint.write_bytes(b"{}")
            runtime_provenance = {"binaries": {"independent_oracle": {
                "dynamic_dependencies": str(output / "dynamic.json")}}}
            with mock.patch.object(MODULE, "validate_report",
                                   return_value=True), \
                    mock.patch.object(MODULE, "_validate_runtime_bindings",
                                      return_value=True), \
                    mock.patch.object(
                        MODULE, "_iter_replayed_oracle_result_records",
                        side_effect=lambda *_: iter(copy.deepcopy(
                            oracle_records))):
                self.assertTrue(MODULE.validate_result_sidecar_bundle(
                    report, output, checkpoint, output,
                    {"independent_oracle": str(pathlib.Path(__file__))},
                    runtime_provenance))
                drift = copy.deepcopy(report)
                drift["matrix"]["ledgers"] = [
                    partition("covered", []),
                    partition("uncovered", covered_keys + uncovered_keys)]
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.validate_result_sidecar_bundle(
                        drift, output, checkpoint, output,
                        {"independent_oracle": str(pathlib.Path(__file__))},
                        runtime_provenance)

    def test_persistent_result_ledger_and_merkle_witness_are_exact(self):
        def key(index):
            return ["content", "cache_disabled", 2, index, None,
                    "sample", "position", "emitted_binary64", "v0",
                    "identity", None, None, None, None, "positive_zero"]

        records = [
            [key(0), "PASS",
             {"kind": "binary64_pair_v1",
              "observed_bits": "0000000000000000",
              "expected_bits": "0000000000000000"},
             None, None],
            [key(1), "FAIL",
             {"kind": "binary64_pair_v1",
              "observed_bits": "3ff0000000000000",
              "expected_bits": "0000000000000000"},
             None, "CONSTANT_FIELD_BITS_MISMATCH"],
            [key(2), "PASS",
             {"kind": "binary64_pair_v1",
              "observed_bits": "0000000000000000",
              "expected_bits": "0000000000000000"},
             None, None],
        ]
        commitment = MODULE.canonical_result_ledger(records, witness_index=1)
        self.assertEqual(commitment["record_count"], 3)
        self.assertEqual(len(commitment["witness_siblings"]), 2)
        self.assertFalse(commitment["bytes"].endswith(b"\n"))
        MODULE.validate_result_merkle_witness(
            commitment["record_bytes"][1], 1,
            commitment["witness_siblings"],
            commitment["result_merkle_root_sha256"], observed_count=3)

        bad_siblings = list(commitment["witness_siblings"])
        bad_siblings[0] = "0" * 64
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_result_merkle_witness(
                commitment["record_bytes"][1], 1, bad_siblings,
                commitment["result_merkle_root_sha256"], observed_count=3)
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_result_merkle_witness(
                commitment["record_bytes"][1], 3,
                commitment["witness_siblings"],
                commitment["result_merkle_root_sha256"], observed_count=3)

        with tempfile.TemporaryDirectory() as temporary:
            persisted, descriptor = MODULE.write_result_ledger_artifact(
                temporary, "constant_field_bits", records, witness_index=1)
            expected_path = (
                "anchored-row-result-ledgers-v1/04-constant_field_bits."
                "result-ledger.json")
            self.assertEqual(descriptor["relative_path"], expected_path)
            artifact = pathlib.Path(temporary) / expected_path
            self.assertEqual(artifact.read_bytes(), persisted["bytes"])
            self.assertEqual(descriptor["byte_length"], artifact.stat().st_size)
            self.assertEqual(descriptor["record_count"], 3)

        with tempfile.TemporaryDirectory() as temporary:
            writer = MODULE.StreamingResultLedgerArtifact(
                temporary, "constant_field_bits")
            for record in records:
                writer.add(record)
            streamed, descriptor = writer.finish(witness_index=1)
            self.assertEqual(streamed["key_ledger_sha256"],
                             commitment["key_ledger_sha256"])
            self.assertEqual(streamed["result_ledger_sha256"],
                             commitment["result_ledger_sha256"])
            self.assertEqual(streamed["result_merkle_root_sha256"],
                             commitment["result_merkle_root_sha256"])
            self.assertEqual(streamed["witness_siblings"],
                             commitment["witness_siblings"])
            self.assertEqual(descriptor["record_count"], 3)

    def test_raw_d9a_global_literals_are_exact_and_mutation_binding(self):
        records = []
        for index in range(196):
            state = "FAIL" if index < 124 else "PASS"
            records.append([["raw", index], "PASS", {
                "kind": "raw_d9a_value_v1",
                "raw_invariant_state": state,
                "failing_row_count": 1 if state == "FAIL" else 0,
                "canonical_raw_rows_sha256": "a" * 64}, None, None])
        maximum = {
            "kind": "absolute_dyadic_v1",
            "numerator_hex": MODULE.RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX,
            "denominator_power": 1074,
        }
        self.assertTrue(MODULE.validate_raw_d9a_frozen_global(
            records, maximum, MODULE.RAW_D9A_FROZEN_MAXIMUM_BITS))
        original_bits = MODULE.RAW_D9A_FROZEN_MAXIMUM_BITS
        original_numerator = MODULE.RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX
        try:
            MODULE.RAW_D9A_FROZEN_MAXIMUM_BITS = "3db6653ab1800001"
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_raw_d9a_frozen_global(
                    records, maximum, original_bits)
            MODULE.RAW_D9A_FROZEN_MAXIMUM_BITS = original_bits
            MODULE.RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX = (
                original_numerator[:-1])
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_raw_d9a_frozen_global(
                    records, maximum, original_bits)
        finally:
            MODULE.RAW_D9A_FROZEN_MAXIMUM_BITS = original_bits
            MODULE.RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX = original_numerator

    def test_infrastructure_sidecars_bind_real_keys_and_raw_maximum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            artifacts = root / "artifacts"
            output = root / "evidence"
            artifacts.mkdir()
            artifact_json = b"{}"
            artifact_bytes = gzip.compress(artifact_json, mtime=0)
            artifact_sha = MODULE.sha256_bytes(artifact_bytes)
            artifact_json_sha = MODULE.sha256_bytes(artifact_json)
            cases = []
            for index in range(294):
                candidate = "bfr" if index < 196 else "far"
                name = "case-{:03d}.json.gz".format(index)
                (artifacts / name).write_bytes(artifact_bytes)
                cases.append({
                    "content_identity_key": "content-{:03d}".format(index),
                    "candidate": candidate,
                    "approximation_level": 2,
                    "applicable_mode": ("cache_disabled" if candidate == "bfr"
                                        else "not_applicable_uncached"),
                    "complete_json_artifact": name,
                    "complete_json_artifact_sha256": artifact_sha,
                    "complete_json_sha256": artifact_json_sha,
                    "canonical_rows_sha256": "2" * 64,
                })
            checkpoint = {"numeric_cases": cases}
            present = MODULE.availability("PRESENT", "3" * 64)
            unavailable = MODULE.availability(
                "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE")
            dependency_versions = {
                "gmp": "6.3.0", "mpfr": "4.2.2",
                "opensubdiv": "3.7.0"}

            def complete_dependencies():
                return {
                    name: {
                        "version": version,
                        "source_archive": copy.deepcopy(present),
                        "build_provenance": copy.deepcopy(present),
                        "install_provenance": copy.deepcopy(present),
                        "link_map": copy.deepcopy(present),
                        "dynamic_dependencies": copy.deepcopy(present),
                    }
                    for name, version in dependency_versions.items()}

            def present_binary():
                return {
                    "availability": copy.deepcopy(present),
                    "sources": [{"path": "source.cpp", "sha256": "5" * 64}],
                    "compiler_command": copy.deepcopy(present),
                    "compiler_version": copy.deepcopy(present),
                    "link_map": copy.deepcopy(present),
                    "dynamic_dependencies": copy.deepcopy(present),
                    "dependencies": complete_dependencies(),
                }

            unavailable_binary = present_binary()
            unavailable_binary.update({
                "availability": copy.deepcopy(unavailable),
                "sources": [],
                "compiler_command": copy.deepcopy(unavailable),
                "compiler_version": copy.deepcopy(unavailable),
                "link_map": copy.deepcopy(unavailable),
                "dynamic_dependencies": copy.deepcopy(unavailable),
            })
            binaries = {
                "row_provider": present_binary(),
                "representation_candidate": present_binary(),
                "exact_dyadic_boundary": present_binary(),
                "independent_oracle": unavailable_binary,
                "oracle_independence_audit": "INCOMPLETE",
            }
            maximum_value = MODULE.binary64_from_bits_hex(
                MODULE.RAW_D9A_FROZEN_MAXIMUM_BITS)

            def raw_value(case, _artifact_root):
                index = int(case["content_identity_key"].split("-")[1])
                return {
                    "kind": "raw_d9a_value_v1",
                    "case_identity": [case["content_identity_key"], 2,
                                      "cache_disabled"],
                    "raw_invariant_state": "FAIL" if index < 124 else "PASS",
                    "maximum_row_sum_residual": MODULE.absolute_dyadic(
                        maximum_value if index == 0 else 0.0),
                    "failing_row_count": 1 if index < 124 else 0,
                    "canonical_raw_rows_sha256": "2" * 64,
                }

            git = {"git_commit": "4" * 40}
            worktree = {"clean": True}
            with mock.patch.object(MODULE, "_raw_d9a_value",
                                   side_effect=raw_value):
                evidence = MODULE.write_infrastructure_result_evidence(
                    output, checkpoint, artifacts, binaries,
                    git, git, worktree, worktree)
            for criterion_id in MODULE.CRITERION_IDS[:3]:
                item = evidence[criterion_id]
                self.assertEqual(
                    item["commitment"]["key_ledger_sha256"],
                    MODULE.generic_key_ledger_sha256([
                        record[0] for record in json.loads(
                            (output / item["artifact"]["relative_path"])
                            .read_text(encoding="utf-8"))]))
            raw = evidence["raw_bfr_d9a_reproduction"]
            self.assertEqual(raw["maximum"]["numerator_hex"],
                             MODULE.RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX)
            self.assertEqual(raw["witness"]["maximum_binary64_bits"],
                             MODULE.RAW_D9A_FROZEN_MAXIMUM_BITS)
            MODULE.validate_result_merkle_witness(
                MODULE.jcs_bytes(raw["witness"]["result_record"]),
                raw["witness"]["leaf_index"],
                raw["witness"]["merkle_siblings"],
                raw["commitment"]["result_merkle_root_sha256"],
                observed_count=196)
            unexpected = output / (
                "anchored-row-result-ledgers-v1/"
                "unexpected-artifact-paths.json")
            self.assertEqual(unexpected.read_bytes(), b"[]")
            criteria = []
            for criterion_id in MODULE.CRITERION_IDS:
                if criterion_id in evidence:
                    item = evidence[criterion_id]
                    criteria.append({
                        "criterion_id": criterion_id,
                        "result_ledger_artifact": item["artifact"],
                        "observed_cell_count": item["observed_count"],
                        "key_ledger_sha256": item["commitment"][
                            "key_ledger_sha256"],
                        "result_ledger_sha256": item["commitment"][
                            "result_ledger_sha256"],
                        "result_merkle_root_sha256": item["commitment"][
                            "result_merkle_root_sha256"],
                        "status": item["status"],
                        "target": item.get("target"),
                        "maximum": item["maximum"],
                        "witness": item["witness"],
                        "first_failing_key": item["first_failing_key"],
                    })
                else:
                    criteria.append({
                        "criterion_id": criterion_id,
                        "result_ledger_artifact": {
                            "availability": unavailable,
                            "relative_path": None, "byte_length": None,
                            "record_count": None},
                        "observed_cell_count": 0,
                        "key_ledger_sha256": None,
                        "result_ledger_sha256": None,
                        "result_merkle_root_sha256": None,
                        "status": "INCOMPLETE", "maximum": None,
                        "target": None,
                        "witness": None, "first_failing_key": None,
                    })
            report = {
                "criteria": criteria,
                "matrix": {
                    "ledgers": MODULE.oracle_unavailable_partition_ledgers(
                        "oracle_coverage_and_crosscheck"),
                    "unexpected_paths": evidence[
                        "complete_artifact_inventory"]["unexpected_paths"]},
            }
            binding_record = json.loads((
                output / evidence["bindings_and_independence"]["artifact"][
                    "relative_path"]).read_text(encoding="utf-8"))[0][2]
            self.assertTrue(binding_record["provenance_complete"])
            self.assertEqual(MODULE._binding_outcome_reason(binding_record),
                             ("INCOMPLETE", "BINDING_UNAVAILABLE"))
            report["identity"] = {
                "git_start": {"git_commit": binding_record["git_start"]},
                "git_end": {"git_commit": binding_record["git_end"]},
                "worktree_start": {
                    "clean": binding_record["worktree_start_clean"]},
                "worktree_end": {
                    "clean": binding_record["worktree_end_clean"]},
                "validator": {"sha256": binding_record["validator_sha256"]},
            }
            report["binaries"] = copy.deepcopy(binaries)
            self.assertTrue(MODULE._validate_binding_against_report(
                binding_record, report))
            with mock.patch.object(MODULE, "validate_report",
                                   return_value=True):
                self.assertTrue(MODULE.validate_result_sidecar_bundle(
                    report, output))
                raw_path = output / raw["artifact"]["relative_path"]
                canonical_raw = raw_path.read_bytes()
                raw_path.write_bytes(canonical_raw + b"\n")
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.validate_result_sidecar_bundle(report, output)
                raw_path.write_bytes(canonical_raw)

    def test_result_ledger_rejects_reorder_duplicate_and_reason_drift(self):
        passing = [["criterion", 0], "PASS", None, None, None]
        failing = [["criterion", 1], "FAIL", None, None, "BROKEN"]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.canonical_result_ledger([failing, passing])
        with self.assertRaises(MODULE.QualificationError):
            MODULE.canonical_result_ledger([passing, passing])
        with self.assertRaises(MODULE.QualificationError):
            MODULE.canonical_result_ledger(
                [[passing[0], "PASS", None, None, "INVENTED_REASON"]])

    def test_oracle_absence_is_incomplete_without_fabricated_partitions(self):
        partitions = MODULE.oracle_unavailable_partition_ledgers(
            "oracle_coverage_and_crosscheck")
        self.assertEqual([item["partition"] for item in partitions],
                         ["covered", "uncovered"])
        self.assertTrue(all(item["observed_count"] == 0 for item in partitions))
        self.assertTrue(all(item["key_ledger_sha256"] is None
                            for item in partitions))
        self.assertTrue(all(item["availability"]["state"] == "UNAVAILABLE"
                            for item in partitions))
        self.assertTrue(all(item["omission_blocker"] ==
                            "oracle_coverage_and_crosscheck"
                            for item in partitions))
        criterion = MODULE.criterion_record(
            "oracle_coverage_and_crosscheck", "INCOMPLETE",
            expected=MODULE.EXPECTED_CELL_COUNTS[
                "oracle_coverage_and_crosscheck"])
        self.assertEqual(criterion["result_ledger_artifact"]["availability"][
            "reason_code"], "ORACLE_EXECUTION_UNAVAILABLE")
        criteria = self.make_incomplete_criteria_fixture()
        criteria[10] = criterion
        MODULE.validate_criteria(criteria)
        criteria[10]["result_ledger_artifact"]["availability"][
            "reason_code"] = "EXECUTION_UNAVAILABLE"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_criteria(criteria)

    def test_oracle_batch_stream_is_ordinal_bound_and_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)

            def make_oracle(name, reverse=False):
                path = root / name
                path.write_text(
                    "#!/usr/bin/env python3\n"
                    "import json, sys\n"
                    "rows = [line.rstrip('\\n').split('\\t') "
                    "for line in sys.stdin]\n"
                    + ("rows.reverse()\n" if reverse else "") +
                    "value = {'schema_version': 1, "
                    "'kind': 'stam_oracle_sample_v1', "
                    "'status': 'uncovered', "
                    "'reason_code': 'NO_ISOLATION_BY_DEPTH_12'}\n"
                    "encoded = json.dumps(value, sort_keys=True, "
                    "separators=(',', ':'))\n"
                    "for row in rows:\n"
                    "    print(row[0] + '\\t' + encoded)\n",
                    encoding="utf-8")
                path.chmod(0o755)
                return path

            identifiers = ["a" * 64, "b" * 64]
            requests = [
                "{}\t/mesh\tnone\t0\t-1\t{}\t{}\n".format(
                    identifier, "0" * 16, "0" * 16)
                for identifier in identifiers]
            observations = list(MODULE.iter_oracle_batch_observations(
                make_oracle("oracle"), requests, identifiers, timeout=10))
            self.assertEqual([item[0] for item in observations], identifiers)
            self.assertTrue(all(item[2]["status"] == "uncovered"
                                for item in observations))

            with self.assertRaises(MODULE.QualificationError):
                list(MODULE.iter_oracle_batch_observations(
                    make_oracle("oracle-reordered", reverse=True),
                    requests, identifiers, timeout=10))

    def test_oracle_batch_timeout_kills_descendant_pipe_holders(self):
        with tempfile.TemporaryDirectory() as temporary:
            oracle = pathlib.Path(temporary) / "stalling-oracle"
            oracle.write_text(
                "#!/bin/sh\n"
                "(sleep 30) &\n"
                "sleep 30\n", encoding="utf-8")
            oracle.chmod(0o755)
            identifier = "a" * 64
            request = "{}\t/mesh\tnone\t0\t-1\t{}\t{}\n".format(
                identifier, "0" * 16, "0" * 16)
            started = time.monotonic()
            with self.assertRaises(MODULE.QualificationError):
                list(MODULE.iter_oracle_batch_observations(
                    oracle, [request], [identifier], timeout=0.2))
            self.assertLess(time.monotonic() - started, 6.0)

    def test_independent_oracle_capability_and_self_test_are_closed(self):
        capability = {
            "schema_version": 1,
            "kind": "independent_primary_capability",
            "status": "implemented",
            "coverage": "AVAILABLE",
            "implementation_state": "PRIMARY_STAM_AND_UNIFORM_AVAILABLE",
            "precision_bits": 544,
            "mpfr_version": "4.2.2",
            "stock_mask_interval_matrix_construction": True,
            "interval_eigenpair_krawczyk_certification": True,
            "repeated_eigenspace_spectral_projector_certification": True,
            "quartic_box_spline_interval_evaluation": True,
            "certified_parametric_branch_mapping": True,
            "independent_uniform_five_depth_intersection": True,
            "uniform_success_substituted_for_primary": False,
        }
        self.assertTrue(MODULE.validate_independent_oracle_capability(
            capability))
        mutated_capability = copy.deepcopy(capability)
        mutated_capability["precision_bits"] = 543
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_independent_oracle_capability(mutated_capability)

        scalar = {
            "schema_version": 1,
            "kind": "stam_oracle_self_test",
            "status": "ok",
            "finite": True,
            "precision_bits": 544,
            "mpfr_compile_version": "4.2.2",
            "mpfr_runtime_version": "4.2.2",
            "directed_rounding": True,
            "single_rounding_direction_mutations_rejected": True,
            "zero_denominator_rejected": True,
            "candidate_dependency_free": True,
            "stock_loop_matrix_constructed_from_masks": True,
            "quartic_box_spline_interval_rows": True,
            "certified_parametric_branch_mapping": True,
            "primary_five_depth_intersection": True,
            "independent_uniform_five_depth_crosscheck": True,
            "primary_eigensystem_certified_valence_min": 3,
            "primary_eigensystem_certified_valence_max": 9,
        }
        boolean_fields = (
            "stock_matrix", "analytic_eigen_residual",
            "interval_krawczyk_inclusion", "verified_inverse_residual",
            "condition_number_bound", "jordan_power_certified",
            "spectral_projectors_certified",
            "source_id_ordered_mgs_certified",
            "tangent_projector_certified")
        scalar["valence_certificates"] = [dict(
            {"valence": valence, "dimension": valence + 6},
            **{field: True for field in boolean_fields})
            for valence in range(3, 10)]
        self.assertTrue(MODULE.validate_independent_oracle_self_test(scalar))
        mutated_self_test = copy.deepcopy(scalar)
        mutated_self_test["valence_certificates"][3][
            "spectral_projectors_certified"] = False
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_independent_oracle_self_test(mutated_self_test)

    def test_oracle_dependent_exact_values_derive_from_bound_intervals(self):
        oracle_value = MODULE._valid_oracle_covered_record()[2]
        one = {"kind": "rational_v1", "numerator": "1",
               "denominator": "1"}
        one_interval = {"kind": "interval_rational_v1",
                        "lower": copy.deepcopy(one),
                        "upper": copy.deepcopy(one)}
        oracle_value["primary_depth_intervals"] = [[
            copy.deepcopy(one_interval) for _ in range(5)]]
        oracle_value["uniform_depth_intervals"] = [[
            copy.deepcopy(one_interval) for _ in range(5)]]
        oracle_value["intersected_primary_intervals"] = [
            copy.deepcopy(one_interval)]
        MODULE.validate_contract_value("oracle_covered_value_v1",
                                       oracle_value)
        row = {"row_kind": "position", "source_ids": [0],
               "coefficients": [1.0]}
        coefficient = MODULE.oracle_coefficient_l1_value(
            row, 0, oracle_value)
        self.assertEqual(coefficient["l1"], {
            "kind": "absolute_rational_v1", "numerator": "0",
            "denominator": "1"})
        coefficient_key = MODULE._criterion_mutation_key(
            "exact_effective_d10_coeff")
        MODULE.validate_contract_result_record(
            "exact_effective_d10_coeff",
            [coefficient_key, "PASS", coefficient,
             MODULE.absolute_rational_target("200000"), None])

        fixture = {"vertices": [(0.0, 0.0, 0.0),
                                (1.0, 0.0, 0.0),
                                (0.0, 1.0, 0.0)],
                   "faces": [(0, 1, 2)]}
        for criterion_id, emitted_bits in (
                ("exact_effective_d10_geometry", None),
                ("emitted_direct_geometry_d10", "0000000000000000")):
            geometry = MODULE.oracle_geometry_axis_value(
                row, 0, oracle_value, fixture, 0, emitted_bits=emitted_bits)
            self.assertEqual(geometry["normalized_bound"][
                "normalized_upper"]["numerator"], "0")
            key = MODULE._criterion_mutation_key(criterion_id)
            MODULE.validate_contract_result_record(
                criterion_id, [key, "PASS", geometry,
                               MODULE.absolute_rational_target("200000"),
                               None])

    def test_oracle_numeric_accumulator_persists_exact_maximum_witness(self):
        row = {"row_kind": "position", "source_ids": [0],
               "coefficients": [1.0]}
        covered = MODULE._valid_oracle_covered_record()[2]
        target = MODULE.absolute_rational_target("200000")
        records = []
        for sample_id, point in (("sample-a", 1), ("sample-b", 0)):
            rational = {"kind": "rational_v1", "numerator": str(point),
                        "denominator": "1"}
            interval = {"kind": "interval_rational_v1",
                        "lower": copy.deepcopy(rational),
                        "upper": copy.deepcopy(rational)}
            value = copy.deepcopy(covered)
            value["primary_depth_intervals"] = [[
                copy.deepcopy(interval) for _ in range(5)]]
            value["uniform_depth_intervals"] = [[
                copy.deepcopy(interval) for _ in range(5)]]
            value["intersected_primary_intervals"] = [
                copy.deepcopy(interval)]
            exact = MODULE.oracle_coefficient_l1_value(row, 0, value)
            key = MODULE._criterion_mutation_key(
                "exact_effective_d10_coeff")
            key[5] = sample_id
            passed = point == 1
            records.append([key, "PASS" if passed else "FAIL", exact,
                            target, None if passed else
                            "D10_COEFFICIENT_TARGET_EXCEEDED"])

        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
                MODULE.EXPECTED_CELL_COUNTS,
                {"exact_effective_d10_coeff": 2}):
            accumulator = MODULE._OracleNumericResultAccumulator(
                temporary, "exact_effective_d10_coeff")
            for record in records:
                accumulator.add(record)
            result = accumulator.finish()
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["failure_count"], 1)
            self.assertEqual(result["maximum"], records[1][2]["l1"])
            self.assertEqual(result["witness"]["result_record"], records[1])
            self.assertEqual(result["witness"]["leaf_index"], 1)
            MODULE.validate_result_merkle_witness(
                MODULE.jcs_bytes(records[1]), 1,
                result["witness"]["merkle_siblings"],
                result["result_merkle_root"], observed_count=2)

    def test_oracle_coverage_executes_emitted_geometry_observations(self):
        case = {"content_identity_key": "content", "candidate": "bfr",
                "approximation_level": 7,
                "applicable_mode": "cache_disabled"}
        row = {"face_row": 0, "local_corner_or_none": -1,
               "sample_id": "sample", "u_binary64_bits_hex": "0" * 16,
               "v_binary64_bits_hex": "0" * 16,
               "row_kind": "position", "source_ids": [0, 1, 2],
               "coefficients": [1.0, 0.0, 0.0]}
        fixture = {"vertices": [(0.0, 0.0, 0.0),
                                (1.0, 0.0, 0.0),
                                (0.0, 1.0, 0.0)],
                   "faces": [(0, 1, 2)], "patches": {}}
        oracle_value = MODULE._valid_oracle_covered_record()[2]
        zero = {"kind": "rational_v1", "numerator": "0",
                "denominator": "1"}
        one = {"kind": "rational_v1", "numerator": "1",
               "denominator": "1"}

        def interval(value):
            return {"kind": "interval_rational_v1",
                    "lower": copy.deepcopy(value),
                    "upper": copy.deepcopy(value)}

        intervals = [interval(one), interval(zero), interval(zero)]
        oracle_value["source_ids"] = [0, 1, 2]
        oracle_value["primary_depth_intervals"] = [
            [copy.deepcopy(item) for _ in range(5)]
            for item in intervals]
        oracle_value["uniform_depth_intervals"] = copy.deepcopy(
            oracle_value["primary_depth_intervals"])
        oracle_value["intersected_primary_intervals"] = copy.deepcopy(
            intervals)
        MODULE.validate_contract_value("oracle_covered_value_v1",
                                       oracle_value)
        oracle_observation = {
            "schema_version": 1, "kind": "stam_oracle_sample_v1",
            "status": "ok",
            "rows": [copy.deepcopy(oracle_value) for _ in MODULE.ROW_ORDER],
        }
        for kind, value in zip(MODULE.ROW_ORDER,
                               oracle_observation["rows"]):
            value["row_kind"] = kind
            if kind != "position":
                derivative_intervals = [interval(zero) for _ in range(3)]
                value["primary_depth_intervals"] = [
                    [copy.deepcopy(item) for _ in range(5)]
                    for item in derivative_intervals]
                value["uniform_depth_intervals"] = copy.deepcopy(
                    value["primary_depth_intervals"])
                value["intersected_primary_intervals"] = copy.deepcopy(
                    derivative_intervals)
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_oracle_sample_observation(oracle_observation)
        MODULE.validate_oracle_sample_observation(
            oracle_observation, MODULE._ORACLE_CERTIFICATION_AUTHORITY)

        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            candidate = root / "candidate.py"
            candidate.write_text(
                "#!/usr/bin/python3\n"
                "import json,struct,sys\n"
                "out=sys.stdout.buffer\n"
                "out.write(b'anchored-row-candidate-values-v1\\x00')\n"
                "for ordinal,line in enumerate(sys.stdin):\n"
                " axis=line.split()[0]\n"
                " value={'axis':axis,'kind':"
                "'candidate_emitted_geometry_observation_v1',"
                "'observed_bits':'0000000000000000'}\n"
                " raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()\n"
                " out.write(struct.pack('>QQ',ordinal,len(raw))+raw)\n",
                encoding="utf-8")
            candidate.chmod(0o755)
            jobs = [{"content_identity_key": "content",
                     "mesh_path": root / "mesh", "mutation": "none"}]
            jobs.extend({"content_identity_key": "unused-{}".format(index),
                         "mesh_path": root / "mesh", "mutation": "none"}
                        for index in range(13))

            def oracle_stream(_binary, _rows, identifiers, timeout=7200,
                              runtime_library_root=None,
                              runtime_library_bindings=None):
                del timeout, runtime_library_root, runtime_library_bindings
                raw = MODULE.jcs_bytes(oracle_observation)
                for identifier in identifiers:
                    yield identifier, raw, oracle_observation

            expected = {
                "oracle_coverage_and_crosscheck": 3,
                "exact_effective_d10_coeff": 3,
                "exact_effective_d10_geometry": 9,
                "emitted_direct_geometry_d10": 9,
            }
            with mock.patch.object(MODULE.B2, "valid_content_jobs",
                                   return_value=jobs), \
                    mock.patch.object(MODULE, "ordered_bfr_cases",
                                      return_value=[case]), \
                    mock.patch.object(MODULE, "_artifact_report",
                                      return_value={"rows": [row]}), \
                    mock.patch.object(MODULE, "regular_patch_inventory",
                                      return_value={"content": fixture}), \
                    mock.patch.object(MODULE,
                                      "iter_oracle_batch_observations",
                                      side_effect=oracle_stream), \
                    mock.patch.object(MODULE,
                                      "ORACLE_EXECUTION_REQUEST_COUNT", 1), \
                    mock.patch.dict(MODULE.EXPECTED_CELL_COUNTS, expected):
                result, partitions, execution_audit = \
                    MODULE.execute_oracle_coverage(
                        {}, root, {}, root / "oracle", candidate, root)
            self.assertEqual(execution_audit["record_count"], 1)
            self.assertEqual(set(result), set(expected))
            self.assertTrue(all(item["status"] == "PASS"
                                for item in result.values()))
            self.assertEqual(result["emitted_direct_geometry_d10"][
                "observed_count"], 9)
            self.assertIsNotNone(result["emitted_direct_geometry_d10"][
                "witness"])
            self.assertEqual([item["observed_count"] for item in partitions],
                             [3, 0])

    def test_preoracle_observations_derive_persisted_categorical_results(self):
        job = MODULE.B2.valid_content_jobs(MODULE.B2.load_manifest())[0]
        vertices, faces, _ = MODULE.B2.independent_mesh(job)
        face = faces[0]
        source_ids = sorted(set(face))
        coefficients = [1.0 if source_id == face[0] else 0.0
                        for source_id in source_ids]
        row = {"face_row": 0, "local_corner_or_none": -1,
               "sample_id": "sample", "row_kind": "position",
               "source_ids": source_ids, "coefficients": coefficients}
        case = {"content_identity_key": job["content_identity_key"],
                "candidate": "bfr", "approximation_level": 7,
                "applicable_mode": "cache_disabled"}
        effective = MODULE.effective_numerators(row, face[0])
        effective_values = [MODULE._signed_dyadic_descriptor(
            effective[source_id]) for source_id in source_ids]
        structure = {
            "kind": "candidate_structure_observation_v1",
            "canonical_source_ids": source_ids,
            "provider_coefficient_bits": [
                MODULE.binary64_bits_hex(value) for value in coefficients],
            "effective_coefficients": effective_values,
        }
        relabel = {
            "kind": "candidate_dyadic_vector_observation_v1",
            "source_ids": source_ids, "values": effective_values,
        }
        challenge_bits = {
            "negative_2p20": MODULE.binary64_bits_hex(-(2.0 ** 20)),
            "negative_one": MODULE.binary64_bits_hex(-1.0),
            "positive_2p20": MODULE.binary64_bits_hex(2.0 ** 20),
            "positive_one": MODULE.binary64_bits_hex(1.0),
            "positive_zero": "0000000000000000",
        }
        constant = [{"kind": "candidate_binary64_observation_v1",
                     "observed_bits": challenge_bits[challenge]}
                    for _anchor in MODULE.ANCHORS
                    for _relabel in MODULE.RELABELS
                    for challenge in MODULE.CHALLENGES]

        def observations(_binary, criterion_id, request_lines,
                         expected_count):
            self.assertEqual(len(list(request_lines)), 1)
            values = {
                "representation_structure": [structure] * 3,
                "constant_field_bits": constant,
                "relabel_exact_effective_coefficients": [relabel] * 6,
            }[criterion_id]
            self.assertEqual(len(values), expected_count)
            return iter(copy.deepcopy(values))

        expected = {"representation_structure": 3,
                    "constant_field_bits": 45,
                    "relabel_exact_effective_coefficients": 6}
        topology = {job["content_identity_key"]: (len(vertices), faces)}
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(MODULE, "ordered_bfr_cases",
                                  return_value=[case]), \
                mock.patch.object(MODULE, "_artifact_report",
                                  return_value={"rows": [row]}), \
                mock.patch.object(MODULE, "fixture_topology",
                                  return_value=topology), \
                mock.patch.object(MODULE, "iter_candidate_observations",
                                  side_effect=observations), \
                mock.patch.dict(MODULE.EXPECTED_CELL_COUNTS, expected):
            result = MODULE.execute_observation_preoracle_criteria(
                "/candidate", {}, pathlib.Path(temporary), {}, temporary)
        self.assertEqual(set(result), set(expected))
        self.assertTrue(all(item["status"] == "PASS"
                            for item in result.values()))
        self.assertTrue(all(item["result_artifact"]["availability"][
            "state"] == "PRESENT" for item in result.values()))

        self.assertEqual(
            MODULE.provider_row_sha256(row),
            MODULE.sha256_bytes(
                MODULE.D12WorkerInventoryVerifier._provider_record_bytes(row)))
        mutated = copy.deepcopy(structure)
        mutated["effective_coefficients"][0] = \
            MODULE._signed_dyadic_descriptor(0)
        _, matches = MODULE.structure_result_value(
            row, "v0", face[0], mutated)
        self.assertFalse(matches)

    def test_regular_observations_derive_persisted_numeric_results(self):
        case = {"content_identity_key": "content", "candidate": "bfr",
                "approximation_level": 7,
                "applicable_mode": "cache_disabled"}
        row = {"face_row": 0, "local_corner_or_none": -1,
               "sample_id": "sample", "row_kind": "position",
               "source_ids": [0, 1, 2],
               "coefficients": [1.0, 0.0, 0.0]}
        fixture = {"vertices": [[0.0, 0.0, 0.0],
                                [1.0, 0.0, 0.0],
                                [0.0, 1.0, 0.0]],
                   "faces": [[0, 1, 2]], "patches": {0: [0, 1, 2]}}
        analytic = [MODULE.Fraction(1), MODULE.Fraction(0),
                    MODULE.Fraction(0)]
        exact = {"kind": "candidate_dyadic_vector_observation_v1",
                 "source_ids": [0, 1, 2],
                 "values": [MODULE._signed_dyadic_descriptor(1 << 1074),
                            MODULE._signed_dyadic_descriptor(0),
                            MODULE._signed_dyadic_descriptor(0)]}
        emitted = [
            {"axis": axis,
             "kind": "candidate_emitted_geometry_observation_v1",
             "observed_bits": "0000000000000000"}
            for _anchor in MODULE.ANCHORS for axis in ("x", "y", "z")]

        def rows(*_args):
            return iter([(case, row, fixture, [0, 1, 2], analytic)])

        def observations(_binary, criterion_id, request_lines,
                         expected_count):
            lines = list(request_lines)
            if criterion_id == "regular_analytic_exact_rows":
                self.assertEqual(len(lines), 1)
                values = [exact] * 3
            else:
                self.assertEqual(len(lines), 9)
                values = emitted
            self.assertEqual(len(values), expected_count)
            return iter(copy.deepcopy(values))

        expected = {"regular_analytic_exact_rows": 3,
                    "regular_analytic_emitted_geometry": 9}
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(MODULE, "_iter_regular_observation_rows",
                                  side_effect=rows), \
                mock.patch.object(MODULE, "iter_candidate_observations",
                                  side_effect=observations), \
                mock.patch.dict(MODULE.EXPECTED_CELL_COUNTS, expected):
            result = MODULE.execute_observation_regular_criteria(
                "/candidate", {}, pathlib.Path(temporary), {}, temporary)
        self.assertEqual(set(result), set(expected))
        for criterion in result.values():
            self.assertEqual(criterion["status"], "PASS")
            self.assertEqual(criterion["failure_count"], 0)
            self.assertEqual(criterion["maximum"],
                             MODULE._absolute_rational_descriptor(
                                 MODULE.Fraction(0)))
            self.assertIsNotNone(criterion["witness"])
            self.assertEqual(criterion["result_artifact"]["availability"][
                "state"], "PRESENT")
        with mock.patch.dict(MODULE.EXPECTED_CELL_COUNTS, expected):
            report_slot = MODULE.executed_criterion_record(
                "regular_analytic_exact_rows",
                result["regular_analytic_exact_rows"])
        self.assertEqual(report_slot["result_ledger_sha256"],
                         result["regular_analytic_exact_rows"][
                             "result_digest"])
        self.assertEqual(report_slot["result_merkle_root_sha256"],
                         result["regular_analytic_exact_rows"][
                             "result_merkle_root"])

    def test_regular_integrand_observations_derive_persisted_results(self):
        zero_interval = MODULE._interval_descriptor(
            MODULE.Fraction(0), MODULE.Fraction(0))
        exact_observation = {
            "kind": "candidate_exact_integrand_observation_v1",
            "observed_interval": zero_interval,
            "view": "exact_effective"}
        emitted_observation = {
            "kind": "candidate_emitted_integrand_observation_v1",
            "observed_bits": "0000000000000000",
            "view": "emitted_binary64"}

        def cells(_checkpoint, _artifact_root, _manifest, criterion_id):
            quantity = ("area_integrand" if criterion_id ==
                        "regular_analytic_area_integrand" else
                        "legacy_volume_integrand")
            result = []
            for view in ("emitted_binary64", "exact_effective"):
                key = ["content", "cache_disabled", 7, 0, None, "sample",
                       quantity, view, "v0", "identity", None, None, None,
                       None, None]
                MODULE.validate_scientific_cell_key(key, criterion_id)
                result.append((key, "B request\n" if view.startswith(
                    "emitted") else "E request\n", zero_interval,
                    zero_interval))
            return iter(result)

        def observations(_binary, _criterion_id, request_lines,
                         expected_count):
            self.assertEqual(len(list(request_lines)), 1)
            self.assertEqual(expected_count, 1)
            return iter(copy.deepcopy([emitted_observation]))

        expected = {"regular_analytic_area_integrand": 2,
                    "regular_analytic_legacy_volume_integrand": 2}
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(
                    MODULE, "_iter_regular_integrand_observation_cells",
                    side_effect=cells), \
                mock.patch.object(MODULE, "iter_candidate_observations",
                                  side_effect=observations), \
                mock.patch.dict(MODULE.EXPECTED_CELL_COUNTS, expected):
            result = MODULE.execute_observation_regular_integrand_criteria(
                "/candidate", {}, pathlib.Path(temporary), {}, temporary)
        self.assertEqual(set(result), set(expected))
        for criterion in result.values():
            self.assertEqual(criterion["status"], "PASS")
            self.assertEqual(criterion["failure_count"], 0)
            self.assertEqual(criterion["maximum"],
                             MODULE._absolute_rational_descriptor(
                                 MODULE.Fraction(0)))
            self.assertIsNotNone(criterion["witness"])
            self.assertEqual(criterion["result_artifact"]["availability"][
                "state"], "PRESENT")

        exact = MODULE._exact_regular_integrands([
            MODULE.Fraction(0), MODULE.Fraction(0), MODULE.Fraction(0),
            MODULE.Fraction(1), MODULE.Fraction(0), MODULE.Fraction(0),
            MODULE.Fraction(0), MODULE.Fraction(1), MODULE.Fraction(0)])
        self.assertEqual(MODULE._interval_fractions(exact[
            "regular_analytic_area_integrand"]),
            (MODULE.Fraction(1), MODULE.Fraction(1)))
        self.assertEqual(MODULE._interval_fractions(exact[
            "regular_analytic_legacy_volume_integrand"]),
            (MODULE.Fraction(0), MODULE.Fraction(0)))

    def test_component_observations_derive_persisted_results(self):
        fixture = {"vertices": [[0.0, 0.0, 0.0],
                                [1.0, 0.0, 0.0],
                                [0.0, 1.0, 0.0]],
                   "faces": [[0, 1, 2]], "patches": {}}

        def row(sample):
            return {"face_row": 0, "local_corner_or_none": -1,
                    "sample_id": sample, "row_kind": "position",
                    "source_ids": [0, 1, 2],
                    "coefficients": [1.0, 0.0, 0.0]}

        low67, high67 = row("sample-67"), row("sample-67")
        low78, high78 = row("sample-78"), row("sample-78")
        case67 = {"content_identity_key": "content", "candidate": "bfr",
                  "approximation_level": 7,
                  "applicable_mode": "cache_disabled"}
        case78 = copy.deepcopy(case67)
        case78["approximation_level"] = 8
        pairs = [
            (case67, low67, case67, high67, fixture, "6_7"),
            (case78, low78, case78, high78, fixture, "7_8")]

        def paired_rows(*_args):
            return iter(pairs)

        expected = {
            "anchor_sensitivity_exact_coeff": 6,
            "anchor_sensitivity_exact_geometry": 18,
            "anchor_sensitivity_emitted_geometry": 18,
            "binary64_basis_probe_diagnostic": 54,
            "binary64_direct_geometry_fidelity": 54,
            "relabel_emitted_geometry_fidelity": 36,
            "stabilization_6_7_exact_coeff": 3,
            "stabilization_6_7_exact_geometry": 9,
            "stabilization_6_7_emitted_geometry": 9,
            "stabilization_7_8_exact_coeff": 3,
            "stabilization_7_8_exact_geometry": 9,
            "stabilization_7_8_emitted_geometry": 9,
        }
        zero = MODULE._signed_dyadic_descriptor(0)

        def requests(_checkpoint, _artifact_root, _manifest, criterion_id):
            return iter(["request\n"] * (1 if criterion_id.startswith(
                "stabilization_") else 2))

        def observations(_binary, criterion_id, request_lines,
                         expected_count):
            list(request_lines)
            cells = list(MODULE._iter_component_observation_cells(
                {}, pathlib.Path("/unused"), {}, criterion_id))
            self.assertEqual(len(cells), expected_count)
            values = []
            for key, _context in cells:
                if criterion_id.endswith("_exact_coeff"):
                    values.append({
                        "kind": "candidate_dyadic_vector_observation_v1",
                        "source_ids": [0, 1, 2],
                        "values": [zero, zero, zero]})
                elif criterion_id in {
                        "anchor_sensitivity_exact_geometry",
                        "stabilization_6_7_exact_geometry",
                        "stabilization_7_8_exact_geometry"}:
                    exact_zero = MODULE._signed_dyadic_descriptor(0, 2148)
                    values.append({
                        "axis": key[11],
                        "kind":
                            "candidate_exact_geometry_observation_v1",
                        "observed": exact_zero})
                elif criterion_id == "binary64_basis_probe_diagnostic":
                    values.append({
                        "emitted_basis_bits": MODULE.binary64_bits_hex(
                            1.0 if key[10] == 0 else 0.0),
                        "kind": "candidate_basis_observation_v1"})
                else:
                    values.append({
                        "axis": key[11],
                        "kind":
                            "candidate_emitted_geometry_observation_v1",
                        "observed_bits": "0000000000000000"})
            return iter(values)

        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(MODULE, "iter_component_row_pairs",
                                  side_effect=paired_rows), \
                mock.patch.object(
                    MODULE, "_component_observation_request_lines",
                    side_effect=requests), \
                mock.patch.object(MODULE, "iter_candidate_observations",
                                  side_effect=observations), \
                mock.patch.dict(MODULE.EXPECTED_CELL_COUNTS, expected):
            result = MODULE.execute_observation_component_criteria(
                "/candidate", {}, pathlib.Path("/unused"), {}, temporary)
        self.assertEqual(set(result), set(expected))
        self.assertTrue(all(item["status"] == "PASS"
                            for item in result.values()))
        self.assertTrue(all(item["result_artifact"]["availability"][
            "state"] == "PRESENT" for item in result.values()))

    def test_cache_observations_derive_persisted_result(self):
        case = {"content_identity_key": "content", "candidate": "bfr",
                "approximation_level": 7,
                "applicable_mode": "cache_disabled"}
        row = {"face_row": 0, "local_corner_or_none": -1,
               "sample_id": "sample", "row_kind": "position",
               "source_ids": [0, 1, 2],
               "coefficients": [1.0, 0.0, 0.0]}
        face = [0, 1, 2]

        def rows(*_args):
            return iter([(case, row, copy.deepcopy(row), face)])

        def observations(_binary, criterion_id, request_lines,
                         expected_count):
            self.assertEqual(criterion_id, "cache_mode_bit_identity")
            self.assertEqual(len(list(request_lines)), 1)
            self.assertEqual(expected_count, 3)
            values = []
            for anchor_source in face:
                entries = MODULE._expected_row_signature_entries(
                    row, anchor_source)
                values.append({
                    "cache_disabled_entries": entries,
                    "kind": "candidate_row_signature_observation_v1",
                    "serial_cache_entries": entries})
            return iter(values)

        expected = {"cache_mode_bit_identity": 3}
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(MODULE, "_iter_cache_observation_rows",
                                  side_effect=rows), \
                mock.patch.object(MODULE, "_cache_observation_request_lines",
                                  return_value=iter(["request\n"])), \
                mock.patch.object(MODULE, "iter_candidate_observations",
                                  side_effect=observations), \
                mock.patch.dict(MODULE.EXPECTED_CELL_COUNTS, expected):
            result = MODULE.execute_observation_cache_criterion(
                "/candidate", {}, pathlib.Path("/unused"), {}, temporary)
        criterion = result["cache_mode_bit_identity"]
        self.assertEqual(criterion["status"], "PASS")
        self.assertEqual(criterion["failure_count"], 0)
        self.assertEqual(criterion["result_artifact"]["availability"][
            "state"], "PRESENT")

    def test_numeric_maximum_witness_mutations_fail_closed(self):
        key = ["content", "cache_disabled", 7, 0, None, "sample", "du",
               "exact_effective", None, "identity", None, None, "v0_v1",
               None, None]
        zero_signed = {"kind": "signed_dyadic_v1", "sign": 0,
                       "numerator_hex": "0", "denominator_power": 1074}
        quarter_signed = {"kind": "signed_dyadic_v1", "sign": 1,
                          "numerator_hex": format(1 << 1072, "x"),
                          "denominator_power": 1074}
        maximum = {"kind": "absolute_dyadic_v1",
                   "numerator_hex": format(1 << 1072, "x"),
                   "denominator_power": 1074}
        exact_value = {
            "kind": "exact_coefficient_l1_v1", "source_ids": [0],
            "observed": [quarter_signed], "expected": [zero_signed],
            "absolute_errors": [maximum],
            "l1": maximum,
        }
        target = MODULE.absolute_rational_target("400000")
        record = [key, "FAIL", exact_value, target,
                  "ANCHOR_SENSITIVITY_TARGET_EXCEEDED"]
        witness = {"cell_key": key, "result_record": record,
                   "leaf_index": 0, "merkle_siblings": [],
                   "maximum_exact": maximum,
                   "maximum_binary64_bits":
                       MODULE.binary64_bits_hex(0.25)}
        MODULE.validate_contract_result_record(
            "anchor_sensitivity_exact_coeff", record)
        MODULE.validate_contract_value("maximum_witness", witness)
        mutations = []
        missing = copy.deepcopy(witness)
        del missing["maximum_exact"]
        mutations.append(missing)
        extra = copy.deepcopy(witness)
        extra["invented"] = 1
        mutations.append(extra)
        wrong_exact = copy.deepcopy(witness)
        wrong_exact["maximum_exact"] = "0.25"
        mutations.append(wrong_exact)
        wrong_record = copy.deepcopy(witness)
        wrong_record["result_record"].append(None)
        mutations.append(wrong_record)
        for mutation in mutations:
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_contract_value("maximum_witness", mutation)

    def test_component_maximum_witness_reconstructs_canonical_key(self):
        case = {"content_identity_key": "content",
                "applicable_mode": "cache_disabled",
                "approximation_level": 7}
        row = {"face_row": 0, "local_corner_or_none": -1,
               "sample_id": "sample", "row_kind": "du"}
        failure = {"anchor_index": 0, "anchor_pair_index": None,
                   "axis_index": None, "basis_source_id": 9,
                   "relabel_index": 2, "row_ordinal": 0}
        component_row = (case, row, case, row, {}, "6_7")
        with mock.patch.object(
                MODULE, "iter_component_row_pairs",
                return_value=iter([component_row])):
            key = MODULE._component_failure_key(
                {}, pathlib.Path("/tmp"), {}, failure,
                "binary64_basis_probe_diagnostic")
        self.assertEqual(
            key,
            ["content", "cache_disabled", 7, 0, None, "sample", "du",
             "emitted_binary64", "v0", "rank_rotate_1", 9, None, None,
             None, None])

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

    def test_candidate_pre_result_ledgers_require_no_candidate_outcomes(self):
        row = {"face_row": 0, "local_corner_or_none": -1,
               "sample_id": "sample", "row_kind": "position"}
        cases = []
        for index in range(98):
            for mode in ("cache_disabled", "SurfaceFactoryCache_serial"):
                cases.append({
                    "content_identity_key": "content-{:03d}".format(index),
                    "approximation_level": 7,
                    "applicable_mode": mode})
        expected = copy.deepcopy(MODULE.EXPECTED_CELL_COUNTS)
        expected.update({
            "representation_structure": 196 * 3,
            "constant_field_bits": 196 * 45,
            "relabel_exact_effective_coefficients": 196 * 6,
            "cache_mode_bit_identity": 98 * 3})
        with mock.patch.object(
                MODULE, "ordered_bfr_cases", return_value=cases), \
                mock.patch.object(
                    MODULE, "_artifact_report",
                    return_value={"rows": [row]}), \
                mock.patch.object(MODULE, "EXPECTED_CELL_COUNTS", expected):
            result = MODULE.make_candidate_pre_result_ledgers(
                {"numeric_cases": cases}, pathlib.Path("/unused"))
        self.assertEqual(set(result), {
            "representation_structure", "constant_field_bits",
            "relabel_exact_effective_coefficients",
            "cache_mode_bit_identity"})
        self.assertEqual(
            {criterion_id: item["count"]
             for criterion_id, item in result.items()},
            {criterion_id: expected[criterion_id]
             for criterion_id in result})
        self.assertTrue(all(
            MODULE.SHA256_RE.fullmatch(item["digest"])
            for item in result.values()))

    def test_complete_pre_result_ledgers_cover_empty_execution(self):
        candidate = {criterion_id: {
            "digest": "a" * 64,
            "count": MODULE.EXPECTED_CELL_COUNTS[criterion_id]}
            for criterion_id in (
                "representation_structure", "constant_field_bits",
                "relabel_exact_effective_coefficients",
                "cache_mode_bit_identity")}
        scientific = {criterion_id: {
            "digest": "b" * 64,
            "count": MODULE.EXPECTED_CELL_COUNTS[criterion_id]}
            for criterion_id in MODULE.CRITERION_IDS[6:26]}
        d12 = {criterion_id: {
            "digest": "c" * 64,
            "count": MODULE.EXPECTED_CELL_COUNTS[criterion_id]}
            for criterion_id in MODULE.CRITERION_IDS[27:]}
        with mock.patch.object(
                MODULE, "make_candidate_pre_result_ledgers",
                return_value=candidate), \
                mock.patch.object(
                    MODULE, "make_d12_pre_result_ledgers",
                    return_value=d12):
            records = MODULE.make_complete_pre_result_ledgers(
                {"numeric_cases": []}, pathlib.Path("/unused"), {}, {},
                scientific=scientific)
        primary_partitions = {record["criterion_id"]: record
                              for record in records
                              if record["partition"] in (
                                  "all", "oracle_request")}
        self.assertEqual(set(primary_partitions), set(MODULE.CRITERION_IDS))
        self.assertEqual(len(records), 34)
        for criterion_id in candidate:
            self.assertEqual(
                primary_partitions[criterion_id]["key_ledger_sha256"],
                candidate[criterion_id]["digest"])

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

    def test_integrand_target_and_oracle_denominator_are_exact(self):
        integrand_key = [
            "content", "serial_cache", 8, 2, None, "sample",
            "area_integrand", "exact_effective", "v2", "identity",
            None, None, None, None, None]
        self.assertEqual(MODULE._row_target_denominator(
            "regular_analytic_area_integrand", integrand_key), "200000")
        invalid_oracle_value = {
            "kind": "oracle_coefficient_l1_v1", "source_ids": [0],
            "observed": [{"kind": "signed_dyadic_v1", "sign": 0,
                          "numerator_hex": "0", "denominator_power": 2148}],
            "oracle_intervals": [{
                "kind": "interval_rational_v1",
                "lower": {"kind": "rational_v1", "numerator": "0",
                          "denominator": "1"},
                "upper": {"kind": "rational_v1", "numerator": "0",
                          "denominator": "1"}}],
            "absolute_error_uppers": [{
                "kind": "absolute_rational_v1", "numerator": "0",
                "denominator": "1"}],
            "l1": {"kind": "absolute_rational_v1", "numerator": "0",
                   "denominator": "1"}}
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_value(
                "oracle_coefficient_l1_v1", invalid_oracle_value)

    def test_runner_derives_binding_structure_constant_and_basis_truth(self):
        binding = {
            "kind": "binding_value_v1", "git_start": "a" * 40,
            "git_end": "a" * 40, "worktree_start_clean": True,
            "worktree_end_clean": True, "validator_sha256": "a" * 64,
            "row_provider_availability": "PRESENT",
            "row_provider_sha256": "b" * 64,
            "representation_availability": "PRESENT",
            "representation_sha256": "c" * 64,
            "exact_boundary_availability": "PRESENT",
            "exact_boundary_sha256": "d" * 64,
            "independent_oracle_availability": "PRESENT",
            "independent_oracle_sha256": "e" * 64,
            "oracle_independence_audit": "PASS",
            "manifest_file_sha256": MODULE.B2.MANIFEST_FILE_SHA256,
            "manifest_contract_sha256": MODULE.B2.MANIFEST_CONTRACT_SHA256,
            "gmp_identity": "gmp-6.3.0", "mpfr_identity": "mpfr-4.2.2",
            "opensubdiv_identity": "opensubdiv-3.7.0",
            "provenance_complete": True}
        record = [["bindings_and_independence",
                   "exact_head_and_provenance"],
                  "PASS", binding, None, None]
        MODULE.validate_contract_result_record(
            "bindings_and_independence", record)
        record[2]["provenance_complete"] = False
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "bindings_and_independence", record)

        structure_key = [
            "content", "cache_disabled", 2, 0, None, "sample", "position",
            "structural", "v0", "identity", None, None, None, None, None]
        one = {"kind": "signed_dyadic_v1", "sign": 1,
               "numerator_hex": format(1 << 1074, "x"),
               "denominator_power": 1074}
        zero = {"kind": "signed_dyadic_v1", "sign": 0,
                "numerator_hex": "0", "denominator_power": 1074}
        structure = {
            "kind": "structure_present_v1", "anchor_id": "v0",
            "anchor_present": True, "canonical_source_ids": [0, 1],
            "provider_coefficient_bits": ["3fe0000000000000",
                                          "3fe0000000000000"],
            "provider_row_sha256": "a" * 64,
            "effective_coefficients": [zero, one],
            "observed_sum": one, "expected_sum": one, "source_count": 2}
        forged = [structure_key, "PASS", structure, None, None]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "representation_structure", forged)

        constant_key = list(structure_key)
        constant_key[7] = "emitted_binary64"
        constant_key[14] = "positive_one"
        fabricated = [constant_key, "PASS", {
            "kind": "binary64_pair_v1", "observed_bits": "0000000000000000",
            "expected_bits": "0000000000000000"}, None, None]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "constant_field_bits", fabricated)

        basis_key = list(structure_key)
        basis_key[7] = "emitted_binary64"
        basis_key[10] = 0
        half = {"kind": "absolute_dyadic_v1", "numerator_hex": "1",
                "denominator_power": 1074}
        basis = {"kind": "basis_value_v1",
                 "emitted_basis_bits": "0000000000000000",
                 "exact_effective": zero, "source_error": {
                     "kind": "absolute_dyadic_v1", "numerator_hex": "0",
                     "denominator_power": 1074}, "group_l1": half}
        basis_record = [basis_key, "PASS", basis,
                        MODULE.absolute_rational_target("2000000"), None]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.canonical_result_ledger(
                [basis_record], criterion_id=
                "binary64_basis_probe_diagnostic")

    def test_structure_rows_bind_to_checkpoint_provider_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            row = {"face_row": 0, "local_corner_or_none": -1,
                   "sample_id": "sample", "row_kind": "position",
                   "source_ids": [0, 1], "coefficients": [0.25, 0.75]}
            raw = MODULE.jcs_bytes({"rows": [row]})
            archive = gzip.compress(raw, mtime=0)
            archive_path = artifacts / "case-000.json.gz"
            archive_path.write_bytes(archive)
            cases = []
            for index in range(196):
                cases.append({
                    "content_identity_key": "content-{:03d}".format(index),
                    "candidate": "bfr", "approximation_level": 2,
                    "applicable_mode": "cache_disabled",
                    "complete_json_artifact":
                        "case-000.json.gz" if index == 0 else
                        "unused-{:03d}.json.gz".format(index),
                    "complete_json_artifact_sha256":
                        MODULE.sha256_bytes(archive),
                    "complete_json_sha256": MODULE.sha256_bytes(raw)})
            checkpoint = {"complete": True,
                          "binding": {"git_head": "a" * 40},
                          "numeric_cases": cases}
            checkpoint_path = root / "checkpoint.json"
            checkpoint_path.write_bytes(MODULE.jcs_bytes(checkpoint))
            report = {"checkpoint": {
                "availability": MODULE.availability(
                    "PRESENT", MODULE.sha256_file(checkpoint_path)),
                "git_head": "a" * 40}}
            provider_binary = root / "provider"
            provider_binary.write_bytes(b"provider")
            checkpoint["binding"]["candidate_binary_sha256"] = \
                MODULE.sha256_file(provider_binary)
            checkpoint_path.write_bytes(MODULE.jcs_bytes(checkpoint))
            report["checkpoint"]["availability"] = MODULE.availability(
                "PRESENT", MODULE.sha256_file(checkpoint_path))
            with mock.patch.object(
                    MODULE.B2A, "validate_checkpoint_and_artifacts",
                    return_value=(None, checkpoint, None,
                                  MODULE.sha256_file(checkpoint_path))):
                verifier = MODULE.ProviderRowVerifier(
                    checkpoint_path, artifacts, provider_binary, report)
            key = ["content-000", "cache_disabled", 2, 0, None,
                   "sample", "position", "structural", "v0", "identity",
                   None, None, None, None, None]
            value = {"canonical_source_ids": [0, 1],
                     "provider_coefficient_bits": [
                         MODULE.binary64_bits_hex(0.25),
                         MODULE.binary64_bits_hex(0.75)]}
            self.assertTrue(verifier.result_record(
                "representation_structure", key, value))
            value["provider_coefficient_bits"][0] = \
                MODULE.binary64_bits_hex(0.5)
            with self.assertRaises(MODULE.QualificationError):
                verifier.result_record("representation_structure", key, value)

    def test_relabel_and_basis_exact_values_are_provider_derived(self):
        row = {"face_row": 0, "local_corner_or_none": -1,
               "sample_id": "sample", "row_kind": "position",
               "source_ids": [0, 1], "coefficients": [0.25, 0.75]}
        verifier = MODULE.ProviderRowVerifier.__new__(
            MODULE.ProviderRowVerifier)
        verifier.faces = {"content": [[0, 1, 2]]}
        verifier._row_for_key = lambda key: row

        relabel = MODULE._valid_result_record_for_mutation(
            "relabel_exact_effective_coefficients")
        relabel[0][0] = "content"
        relabel[2]["source_ids"] = [999]
        relabel[2]["observed"] = [MODULE._signed_dyadic_descriptor(0)]
        relabel[2]["expected"] = [MODULE._signed_dyadic_descriptor(0)]
        relabel[2]["absolute_errors"] = [
            MODULE._absolute_dyadic_descriptor(0)]
        relabel[2]["l1"] = MODULE._absolute_dyadic_descriptor(0)
        MODULE.validate_contract_result_record(
            "relabel_exact_effective_coefficients", relabel)
        with self.assertRaises(MODULE.QualificationError):
            verifier.result_record(
                "relabel_exact_effective_coefficients", relabel[0], relabel[2])

        basis = MODULE._valid_result_record_for_mutation(
            "binary64_basis_probe_diagnostic")
        basis[0][0] = "content"
        basis[0][10] = 999
        MODULE.validate_contract_result_record(
            "binary64_basis_probe_diagnostic", basis,
            defer_basis_group=True)
        with self.assertRaises(MODULE.QualificationError):
            verifier.result_record(
                "binary64_basis_probe_diagnostic", basis[0], basis[2])

    def test_geometry_and_d12_values_are_coupled_to_their_keys(self):
        zero = {"kind": "rational_v1", "numerator": "0",
                "denominator": "1"}
        one = {"kind": "rational_v1", "numerator": "1",
               "denominator": "1"}
        interval_zero = {"kind": "interval_rational_v1",
                         "lower": zero, "upper": zero}
        geometry = {
            "kind": "geometry_axis_v1", "axis": "x",
            "view": "exact_effective",
            "observed": {"kind": "signed_dyadic_v1", "sign": 0,
                         "numerator_hex": "0", "denominator_power": 1074},
            "reference_interval": interval_zero,
            "normalized_bound": {
                "kind": "normalized_interval_bound_v1",
                "difference_interval": interval_zero,
                "distance_upper": {"kind": "absolute_rational_v1",
                                   "numerator": "0", "denominator": "1"},
                "scale_squared_interval": {
                    "kind": "interval_rational_v1", "lower": one,
                    "upper": one},
                "scale_lower": one,
                "ideal_normalized": {
                    "kind": "rational_over_sqrt_v1",
                    "absolute_numerator": "0", "absolute_denominator": "1",
                    "scale_squared_numerator": "1",
                    "scale_squared_denominator": "1"},
                "normalized_upper": {
                    "kind": "absolute_rational_v1", "numerator": "0",
                    "denominator": "1"}}}
        geometry_key = [
            "content", "cache_disabled", 7, 0, 0, "sample", "du",
            "exact_effective", "v0", "identity", None, "x", None,
            None, None]
        geometry_record = [
            geometry_key, "PASS", geometry,
            MODULE.absolute_rational_target("40000"),
            None]
        MODULE.validate_contract_result_record(
            "exact_effective_d10_geometry", geometry_record)
        mismatched = copy.deepcopy(geometry_record)
        mismatched[2]["axis"] = "y"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "exact_effective_d10_geometry", mismatched)

        payload_key = [
            "content", 7, "release", "cache_disabled", None, None, None,
            None, None, 3, None, None, None, "retained_payload_bytes"]
        payload = {
            "kind": "d12_payload_valid_v1", "payload_bytes": 1,
            "face_id": 3, "platform_state": "QUALIFIED_PLATFORM",
            "raw_observation": {
                "kind": "d12_raw_observation_binding_v1",
                "availability": MODULE.availability("PRESENT", "a" * 64),
                "relative_path": "raw.json", "byte_offset": 0,
                "byte_length": 1, "sha256": "a" * 64}}
        payload_record = [
            payload_key, "PASS", payload,
            MODULE.report_criterion_target("d12_retained_payload"), None]
        MODULE.validate_contract_result_record(
            "d12_retained_payload", payload_record)
        payload_record[2]["face_id"] = 4
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "d12_retained_payload", payload_record)

        qualified_overrun = copy.deepcopy(payload_record)
        qualified_overrun[2]["face_id"] = 3
        qualified_overrun[2]["payload_bytes"] = 131073
        qualified_overrun[1] = "FAIL"
        qualified_overrun[4] = "D12_PLATFORM_UNQUALIFIED"
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "d12_retained_payload", qualified_overrun)

        invalid_payload = {
            "kind": "d12_payload_invalid_v1", "payload_bytes": None,
            "face_id": 3, "invalid_state": "MISSING_COUNT",
            "platform_state": "QUALIFIED_PLATFORM",
            "raw_observation": copy.deepcopy(payload["raw_observation"])}
        self.assertIsNone(MODULE._record_numeric_measure_or_none(
            "d12_retained_payload", invalid_payload))

        concurrency_key = [
            "content", 7, "tsan", "cache_disabled", 2, 1, 3, None,
            None, None, None, None, "thread_result", "row_digest"]
        target = {"kind": "d12_output_reference_target_v1",
                  "provider_expected_sha256": "b" * 64,
                  "representation_expected_sha256": "c" * 64}
        unavailable_sidecar = {
            "availability": MODULE.availability(
                "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE"),
            "relative_path": None, "byte_length": None,
            "record_count": None, "sha256": None}
        normal = {
            "kind": "d12_concurrency_value_v1",
            "provider_sidecar": copy.deepcopy(unavailable_sidecar),
            "representation_sidecar": copy.deepcopy(unavailable_sidecar),
            "provider_observed_sha256": None,
            "provider_expected_sha256": "b" * 64,
            "representation_observed_sha256": None,
            "representation_expected_sha256": "c" * 64,
            "platform_state": "QUALIFIED_PLATFORM"}
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "d12_cache_disabled_concurrency",
                [concurrency_key, "FAIL", normal, target,
                 "CACHE_DISABLED_CONCURRENCY_MISMATCH"])
        abort = copy.deepcopy(normal)
        abort["kind"] = "d12_concurrency_abort_v1"
        abort["tsan_finding_summary_key"] = ["arbitrary"]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "d12_cache_disabled_concurrency",
                [concurrency_key, "FAIL", abort, target,
                 "CACHE_DISABLED_RACE"])

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

    def test_d12_unavailable_and_invalid_raw_states_cannot_forge_passes(self):
        unavailable = {
            "kind": "d12_tsan_finding_raw_v1",
            "state": "EXECUTION_UNAVAILABLE", "finding_count_token": None,
            "sanitizer_report_sha256": None}
        forged = {
            "kind": "d12_tsan_finding_summary_v1", "finding_count": 0,
            "sanitizer_abort": False, "sanitizer_report_sha256": None,
            "platform_state": "QUALIFIED_PLATFORM",
            "raw_observation": MODULE._schema_exemplar(
                MODULE.cached_schema()["$defs"][
                    "d12_raw_observation_binding_v1"],
                MODULE.cached_schema())}
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_d12_raw_exact_value(unavailable, forged)
        incomplete = copy.deepcopy(forged)
        incomplete["finding_count"] = None
        self.assertTrue(MODULE.validate_d12_raw_exact_value(
            unavailable, incomplete))
        record = MODULE._valid_result_record_for_mutation(
            "d12_instrumented_tsan")
        record[2] = incomplete
        record[1] = "INCOMPLETE"
        record[4] = "D12_OPERATIONAL_LEDGER_INCOMPLETE"
        MODULE.validate_contract_result_record(
            "d12_instrumented_tsan", record)
        forged_record = copy.deepcopy(record)
        forged_record[1], forged_record[4] = "PASS", None
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "d12_instrumented_tsan", forged_record)

        instrumentation = MODULE._schema_exemplar(
            MODULE.cached_schema()["$defs"][
                "d12_tsan_instrumentation_summary_v1"],
            MODULE.cached_schema())
        instrumentation.update({"instrumentation_complete": False,
                                "instrumented_translation_units_sha256":
                                    None})
        instrumentation_key = copy.deepcopy(record[0])
        instrumentation_key[13] = "instrumentation_coverage"
        instrumentation_target = MODULE._schema_exemplar(
            MODULE.cached_schema()["$defs"][
                "d12_tsan_instrumentation_target_v1"],
            MODULE.cached_schema())
        bad_instrumentation = [
            instrumentation_key, "FAIL", instrumentation,
            instrumentation_target,
            "D12_REPRESENTATION_WORKLOAD_MISMATCH"]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "d12_instrumented_tsan", bad_instrumentation)
        bad_instrumentation[1] = "INCOMPLETE"
        bad_instrumentation[4] = "D12_OPERATIONAL_LEDGER_INCOMPLETE"
        MODULE.validate_contract_result_record(
            "d12_instrumented_tsan", bad_instrumentation)

        audit_digest = "a" * 64
        complete_raw = {
            "kind": "d12_tsan_instrumentation_raw_v1",
            "state": "COMPLETE",
            "instrumented_translation_units_sha256": audit_digest}
        complete_value = copy.deepcopy(instrumentation)
        complete_value.update({
            "instrumentation_complete": True,
            "instrumented_translation_units_sha256": audit_digest})
        MODULE.validate_d12_raw_exact_value(
            complete_raw, complete_value, audit_digest)
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_d12_raw_exact_value(
                complete_raw, complete_value, "b" * 64)

        invalid_rss = {"kind": "d12_rss_raw_v1",
                       "state": "MISSING_OBSERVATION",
                       "baseline_token": "123", "observed_token": None}
        rss_value = MODULE._schema_exemplar(
            MODULE.cached_schema()["$defs"]["d12_rss_invalid_v1"],
            MODULE.cached_schema())
        rss_value.update({"baseline_rss_bytes": 999,
                          "observed_rss_bytes": None,
                          "invalid_state": "MISSING_OBSERVATION"})
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_d12_raw_exact_value(invalid_rss, rss_value)
        rss_value["baseline_rss_bytes"] = 123
        MODULE.validate_d12_raw_exact_value(invalid_rss, rss_value)

    def test_d12_frozen_build_and_boundary_authority_rejects_drift(self):
        envelope = MODULE._d12_envelope_contract_fixture()
        first_observation = envelope["platform"][
            "power_thermal_observations"][0]
        first_boundary = MODULE.strict_json_bytes(
            first_observation["boundary"].encode("utf-8"))
        self.assertEqual(len(first_boundary), 5)
        self.assertEqual(set(first_observation["probe"]), {
            "schema_version", "kind", "status", "finite",
            "fingerprint_queries_ok", "fingerprint", "power", "thermal",
            "process_returncode"})
        for mutate in (
                lambda value: value["build_profiles"]["release"].update(
                    {"flags": ["WRONG"]}),
                lambda value: value["build_profiles"]["release"][
                    "compile_commands"][0].append("-ffast-math"),
                lambda value: value["build_profiles"]["tsan"][
                    "link_commands"][0].append("-fno-sanitize=thread"),
                lambda value: value["build_profiles"]["release"][
                    "compile_commands"][0].append("-mcpu=apple-m1"),
                lambda value: value["build_profiles"]["release"][
                    "compile_commands"][0].append("-Wno-error"),
                lambda value: value["build_profiles"]["release"][
                    "compile_commands"][0].extend(
                        ["-include", "unbound.hpp"]),
                lambda value: value["build_profiles"]["release"][
                    "compile_commands"][0].append("@unbound-flags.rsp"),
                lambda value: value["build_profiles"]["release"][
                    "compile_commands"][0].extend(
                        ["-mllvm", "-enable-unsafe-fp-math"]),
                lambda value: value["platform"][
                    "power_thermal_observations"][0].update(
                        {"boundary": "invented"}),
                lambda value: value["platform"][
                    "power_thermal_observations"][0].update(
                        {"power_api": "invented"})):
            candidate = copy.deepcopy(envelope)
            mutate(candidate)
            candidate["content_sha256"] = MODULE.ZERO_SHA256
            candidate["content_sha256"] = MODULE.sha256_bytes(
                MODULE.jcs_bytes(candidate))
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_d12_envelope_contract(candidate, "a" * 40)

        for coordinated_mutation in (
                "same_phase", "compile_source", "link_object",
                "shared_profile_roots", "traversal_profile_roots",
                "double_slash_roots", "linker_multiplex"):
            candidate = copy.deepcopy(envelope)
            profile = candidate["build_profiles"]["release"]
            if coordinated_mutation == "same_phase":
                profile["link_commands"] = copy.deepcopy(
                    profile["compile_commands"])
            elif coordinated_mutation == "compile_source":
                profile["compile_commands"][0][-4] = str(
                    (MODULE.ROOT / "invented.cpp").resolve())
            elif coordinated_mutation == "link_object":
                prefix_length = 1 + len(profile["flags"])
                profile["link_commands"][0][prefix_length] = "/tmp/invented.o"
            elif coordinated_mutation in {
                    "shared_profile_roots", "traversal_profile_roots",
                    "double_slash_roots"}:
                tsan = candidate["build_profiles"]["tsan"]
                for field in ("compile_commands", "link_commands"):
                    for command_index, command in enumerate(tsan[field]):
                        if coordinated_mutation == "shared_profile_roots":
                            replacements = (
                                ("/tsan-build/", "/release-build/"),
                                ("/tsan-install/", "/release-install/"))
                        elif coordinated_mutation == "traversal_profile_roots":
                            replacements = (
                                ("/tsan-build/",
                                 "/shadow/../release-build/"),
                                ("/tsan-install/",
                                 "/shadow/../release-install/"))
                        else:
                            replacements = (("/d12-proof/", "//d12-proof/"),)
                        rewritten = []
                        for token in command:
                            for old, new in replacements:
                                token = token.replace(old, new)
                            rewritten.append(token)
                        tsan[field][command_index] = rewritten
            else:
                command = profile["link_commands"][0]
                map_index = next(index for index, token in enumerate(command)
                                 if token.startswith("-Wl,-map,"))
                command[map_index] += ",-dead_strip,-order_file,order.map"
            candidate["content_sha256"] = MODULE.ZERO_SHA256
            candidate["content_sha256"] = MODULE.sha256_bytes(
                MODULE.jcs_bytes(candidate))
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_d12_envelope_contract(candidate, "a" * 40)

    def test_d12_command_profile_binds_distinct_compile_and_link_argv(self):
        profile = {
            "working_directory": str(MODULE.ROOT),
            "environment": MODULE._d12_rebuild_environment(),
            "compile_commands": [["clang++", "-O3", "-c", "source.cpp"]],
            "link_commands": [["clang++", "source.o", "-o", "proof"]]}
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            compile_path = root / "compile-commands.json"
            link_path = root / "link-commands.json"
            compile_path.write_bytes(MODULE.jcs_bytes(
                profile["compile_commands"]))
            link_path.write_bytes(MODULE.jcs_bytes(profile["link_commands"]))
            manifest = {
                "schema_id": "d12-command-profile-manifest-v1",
                "working_directory": profile["working_directory"],
                "environment": copy.deepcopy(profile["environment"]),
                "compile_commands": {
                    "relative_path": compile_path.name,
                    "sha256": MODULE.sha256_file(compile_path)},
                "link_commands": {
                    "relative_path": link_path.name,
                    "sha256": MODULE.sha256_file(link_path)}}
            path = root / "commands.manifest.json"
            path.write_bytes(MODULE.jcs_bytes(manifest))
            self.assertEqual(MODULE._read_command_profile(path), profile)
            for mutate in (
                    lambda value: value.update(
                        working_directory=str(root)),
                    lambda value: value["environment"].update(
                        CCC_OVERRIDE_OPTIONS="+-fno-inline"),
                    lambda value: value["environment"].pop("LC_ALL")):
                bad_manifest = copy.deepcopy(manifest)
                mutate(bad_manifest)
                path.write_bytes(MODULE.jcs_bytes(bad_manifest))
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._read_command_profile(path)
            for bad_relative in (
                    "./compile-commands.json",
                    "nested/../compile-commands.json",
                    str(compile_path)):
                bad_manifest = copy.deepcopy(manifest)
                bad_manifest["compile_commands"][
                    "relative_path"] = bad_relative
                path.write_bytes(MODULE.jcs_bytes(bad_manifest))
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._read_command_profile(path)
            path.write_bytes(MODULE.jcs_bytes(manifest))
            actual_compile = root / "actual-compile-commands.json"
            compile_path.rename(actual_compile)
            compile_path.symlink_to(actual_compile)
            with self.assertRaises(MODULE.QualificationError):
                MODULE._read_command_profile(path)
            compile_path.unlink()
            actual_compile.rename(compile_path)
            link_path.write_bytes(MODULE.jcs_bytes(
                profile["compile_commands"]))
            with self.assertRaises(MODULE.QualificationError):
                MODULE._read_command_profile(path)
            link_path.write_bytes(MODULE.jcs_bytes(profile["link_commands"]))
            manifest["link_commands"] = copy.deepcopy(
                manifest["compile_commands"])
            path.write_bytes(MODULE.jcs_bytes(manifest))
            with self.assertRaises(MODULE.QualificationError):
                MODULE._read_command_profile(path)

    def test_d12_opensubdiv_profile_manifest_binds_distinct_libraries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            descriptors = {}
            for profile_name, payload in (
                    ("release", b"release library"),
                    ("tsan", b"tsan library")):
                install_root = root / (profile_name + "-install")
                library = install_root / "lib/libosdCPU.a"
                library.parent.mkdir(parents=True)
                library.write_bytes(payload)
                descriptors[profile_name] = {
                    "root": str(install_root),
                    "artifact_path": str(library),
                    "sha256": MODULE.sha256_file(library)}
            manifest = {
                "schema_id": "d12-opensubdiv-profile-artifacts-v1",
                "field": "installed_library",
                "release": descriptors["release"],
                "tsan": descriptors["tsan"]}
            path = root / "installed-libraries.manifest.json"
            path.write_bytes(MODULE.jcs_bytes(manifest))
            self.assertEqual(
                MODULE._read_d12_opensubdiv_profile_manifest(
                    path, "installed_library"), descriptors)
            manifest["tsan"]["artifact_path"] = \
                manifest["release"]["artifact_path"]
            manifest["tsan"]["sha256"] = manifest["release"]["sha256"]
            path.write_bytes(MODULE.jcs_bytes(manifest))
            with self.assertRaises(MODULE.QualificationError):
                MODULE._read_d12_opensubdiv_profile_manifest(
                    path, "installed_library")

    def test_d12_opensubdiv_audit_derives_instrumentation_digest(self):
        envelope = MODULE._d12_envelope_contract_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            source_root = root / "source"
            source_root.mkdir()
            source_audit = {
                "head": "a" * 40, "tree": "b" * 40,
                "translation_units": []}
            profiles = {field: {} for field in (
                "build_root_provenance", "install_provenance",
                "link_provenance", "installed_library")}
            independent_audits = {}
            independent_object_ledgers = {}
            for profile_name, b2_name in (
                    ("release", "release"),
                    ("tsan", "thread_sanitizer")):
                build_root = root / (profile_name + "-build")
                install_root = root / (profile_name + "-install")
                build_root.mkdir()
                (install_root / "include/opensubdiv").mkdir(parents=True)
                (install_root / "lib").mkdir()
                header = install_root / "include/opensubdiv/version.h"
                header.write_text("version", encoding="utf-8")
                archive = install_root / "lib/libosdCPU.a"
                archive.write_bytes((profile_name + " archive").encode())
                install_manifest = build_root / "install_manifest.txt"
                install_manifest.write_text("installed", encoding="utf-8")
                link_command = build_root / "link.txt"
                link_command.write_text("linked", encoding="utf-8")
                audit = {
                    "profile": b2_name, "build_root": str(build_root),
                    "install_root": str(install_root),
                    "archive": str(archive),
                    "archive_sha256": MODULE.sha256_file(archive),
                    "raw_archive_members": ["__.SYMDEF", "version.cpp.o"],
                    "translation_unit_ledger": [{
                        "source_relative_path": "opensubdiv/version.cpp",
                        "source_sha256": profile_name[0] * 64,
                        "object_member_basename": "version.cpp.o",
                        "compile_command": ["clang++"] +
                            (["-fsanitize=thread"]
                             if profile_name == "tsan" else [])}],
                    "provenance_artifacts": {
                        "install_manifest": {
                            "sha256": MODULE.sha256_file(install_manifest)},
                        "link_command": {
                            "sha256": MODULE.sha256_file(link_command)}}}
                independent_audits[b2_name] = audit
                object_ledger = [{
                    "source_relative_path": "opensubdiv/version.cpp",
                    "source_sha256": ("a" if profile_name == "release"
                                      else "b") * 64,
                    "compile_command": ["clang++"] +
                        (["-fsanitize=thread"]
                         if profile_name == "tsan" else []),
                    "object_path": str(build_root / "version.cpp.o"),
                    "object_member_basename": "version.cpp.o",
                    "object_sha256": ("c" if profile_name == "release"
                                      else "d") * 64,
                    "undefined_symbols_sha256": "e" * 64,
                    "tsan_instrumented": profile_name == "tsan",
                    "archive_member_sha256":
                        ("c" if profile_name == "release" else "d") * 64}]
                independent_object_ledgers[b2_name] = object_ledger

                build_packet = {
                    "schema_id": "d12-opensubdiv-build-audit-v1",
                    "profile": profile_name,
                    "source_root": str(source_root),
                    "source": source_audit, "audit": audit,
                    "object_archive_ledger": object_ledger}
                build_path = build_root / \
                    "d12-opensubdiv-build-audit.json"
                build_path.write_bytes(MODULE.jcs_bytes(build_packet))
                install_value = {
                    "schema_id": "d12-opensubdiv-install-provenance-v1",
                    "profile": profile_name,
                    "install_root": str(install_root),
                    "version_header_sha256": MODULE.sha256_file(header),
                    "install_manifest_sha256":
                        MODULE.sha256_file(install_manifest),
                    "archive_sha256": MODULE.sha256_file(archive)}
                install_path = install_root / \
                    "d12-opensubdiv-install-provenance.json"
                install_path.write_bytes(MODULE.jcs_bytes(install_value))
                link_value = {
                    "schema_id": "d12-opensubdiv-link-provenance-v1",
                    "profile": profile_name, "build_root": str(build_root),
                    "archive_sha256": MODULE.sha256_file(archive),
                    "raw_archive_members": audit["raw_archive_members"],
                    "link_command_sha256": MODULE.sha256_file(link_command)}
                link_path = build_root / \
                    "d12-opensubdiv-link-provenance.json"
                link_path.write_bytes(MODULE.jcs_bytes(link_value))
                for field, path, field_root in (
                        ("build_root_provenance", build_path, build_root),
                        ("install_provenance", install_path, install_root),
                        ("link_provenance", link_path, build_root),
                        ("installed_library", archive, install_root)):
                    profiles[field][profile_name] = {
                        "root": str(field_root),
                        "artifact_path": str(path),
                        "sha256": MODULE.sha256_file(path)}

            def audit_profile(_install, _build, _source, _contract, profile):
                return copy.deepcopy(independent_audits[profile])

            def audit_objects(_source, _build, _install, _contract, profile):
                return copy.deepcopy(independent_object_ledgers[profile])

            def installed_headers(_source, install):
                header = pathlib.Path(
                    install) / "include/opensubdiv/version.h"
                return {str(header.resolve()): {
                    "source_relative_path": "opensubdiv/version.h",
                    "sha256": MODULE.sha256_file(header)}}

            with mock.patch.object(
                    MODULE, "_audit_d12_source_checkout",
                    return_value=copy.deepcopy(source_audit)), \
                    mock.patch.object(
                        MODULE, "_d12_installed_header_bindings",
                        side_effect=installed_headers), \
                    mock.patch.object(
                        MODULE.B2, "audit_opensubdiv",
                        side_effect=audit_profile), \
                    mock.patch.object(
                        MODULE, "_validate_d12_opensubdiv_object_chain",
                        side_effect=audit_objects):
                result = MODULE._validate_d12_opensubdiv_profile_audits(
                    envelope, profiles)
                self.assertRegex(
                    result["instrumented_translation_units_sha256"],
                    r"^[0-9a-f]{64}$")
                mutated_envelope = copy.deepcopy(envelope)
                mutated_envelope["binaries"]["provider_tsan"][
                    "sha256"] = "f" * 64
                mutated = MODULE._validate_d12_opensubdiv_profile_audits(
                    mutated_envelope, profiles)
                self.assertNotEqual(
                    result["instrumented_translation_units_sha256"],
                    mutated["instrumented_translation_units_sha256"])
                build_path = pathlib.Path(profiles[
                    "build_root_provenance"]["tsan"]["artifact_path"])
                packet = MODULE.strict_json_bytes(build_path.read_bytes())
                packet["audit"]["archive_sha256"] = "f" * 64
                build_path.write_bytes(MODULE.jcs_bytes(packet))
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._validate_d12_opensubdiv_profile_audits(
                        envelope, profiles)

    def test_d12_proof_binary_is_independently_rebuilt(self):
        build = MODULE.B2.load_manifest()["qualification_platform"]["build"]
        if not pathlib.Path(build["compiler_path"]).is_file() or not \
                pathlib.Path(build["macos_sdk_path"]).is_dir():
            self.skipTest("pinned macOS proof compiler/SDK unavailable")
        envelope = MODULE._d12_envelope_contract_fixture()
        environment = MODULE._d12_rebuild_environment()
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            built = {}
            for profile_name in ("release", "tsan"):
                profile_root = root / profile_name
                profile_root.mkdir()
                compile_command = copy.deepcopy(envelope["build_profiles"][
                    profile_name]["compile_commands"][1])
                link_command = copy.deepcopy(envelope["build_profiles"][
                    profile_name]["link_commands"][1])
                old_object = MODULE._command_output(compile_command)
                compile_command[compile_command.index("-MF") + 1] = str(
                    profile_root / "representation.d")
                compile_command[compile_command.index("-o") + 1] = str(
                    profile_root / "representation.o")
                link_command[link_command.index(old_object)] = \
                    MODULE._command_output(compile_command)
                map_index = next(
                    index for index, token in enumerate(link_command)
                    if token.startswith("-Wl,-map,"))
                runtime_map = profile_root / "representation.map"
                runtime_binary = profile_root / "representation"
                link_command[map_index] = "-Wl,-map," + str(runtime_map)
                link_command[link_command.index("-o") + 1] = str(
                    runtime_binary)
                subprocess.run(
                    compile_command, check=True, capture_output=True,
                    cwd=str(MODULE.ROOT), env=environment)
                subprocess.run(
                    link_command, check=True, capture_output=True,
                    cwd=str(MODULE.ROOT), env=environment)
                MODULE._rebuild_d12_proof_binary(
                    "representation_" + profile_name,
                    compile_command, link_command, runtime_binary, runtime_map,
                    MODULE.ROOT, environment, {})
                built[profile_name] = (
                    compile_command, link_command, runtime_binary, runtime_map)

            compile_command, link_command, runtime_binary, runtime_map = \
                built["release"]
            expected_dependencies = [
                MODULE.ROOT / relative for relative in
                MODULE.RUNTIME_SOURCE_PATHS["representation_candidate"]]
            dependencies = MODULE._require_reproducible_object(
                compile_command, MODULE._command_output(compile_command),
                MODULE.ROOT, environment, "representation_release",
                dependency_root=MODULE.ROOT,
                expected_dependencies=expected_dependencies)
            self.assertEqual(
                {item["path"] for item in dependencies},
                {str(path.resolve()) for path in expected_dependencies})
            no_dependency_command = list(compile_command)
            dependency_index = no_dependency_command.index("-MMD")
            del no_dependency_command[dependency_index:dependency_index + 3]
            MODULE._require_reproducible_object(
                no_dependency_command,
                MODULE._command_output(compile_command), MODULE.ROOT,
                environment, "representation_release_no_original_depfile",
                dependency_root=MODULE.ROOT,
                expected_dependencies=expected_dependencies)
            with self.assertRaises(MODULE.QualificationError):
                MODULE._require_reproducible_object(
                    compile_command, "/usr/bin/true", MODULE.ROOT, environment,
                    "representation_release")
            contaminated_object = root / "contaminated.o"
            contaminated_dependency = root / "contaminated.d"
            contaminated_command = list(compile_command)
            contaminated_command[contaminated_command.index("-MF") + 1] = str(
                contaminated_dependency)
            contaminated_command[contaminated_command.index("-o") + 1] = str(
                contaminated_object)
            contaminated_environment = dict(
                environment, CCC_OVERRIDE_OPTIONS="+-fno-inline")
            subprocess.run(
                contaminated_command, check=True, capture_output=True,
                cwd=str(MODULE.ROOT), env=contaminated_environment)
            with self.assertRaises(MODULE.QualificationError):
                MODULE._require_reproducible_object(
                    compile_command, contaminated_object, MODULE.ROOT,
                    environment, "representation_release")
            forged_map = root / "forged.map"
            forged_map.write_text("invented map\n", encoding="utf-8")
            with self.assertRaises(MODULE.QualificationError):
                MODULE._rebuild_d12_proof_binary(
                    "representation_release", compile_command, link_command,
                    runtime_binary, forged_map, MODULE.ROOT, environment, {})
            with self.assertRaises(MODULE.QualificationError):
                MODULE._rebuild_d12_proof_binary(
                    "representation_release", compile_command, link_command,
                    "/usr/bin/true", runtime_map,
                    MODULE.ROOT, environment, {})

    def test_d12_dependency_aliases_bind_to_authenticated_headers(self):
        with tempfile.TemporaryDirectory() as temporary:
            working = pathlib.Path(temporary).resolve()
            (working / "src").mkdir()
            (working / "include/sub").mkdir(parents=True)
            source = working / "src/main.cpp"
            header = working / "include/header.hpp"
            spaced = working / "include/space header.hpp"
            for path, value in ((source, "source"), (header, "header"),
                                (spaced, "spaced")):
                path.write_text(value, encoding="utf-8")
            target = working / "proof.o"
            dependency = working / "proof.d"
            dependency.write_text(
                "{}: src/../src/./main.cpp \\\n"
                " include/./header.hpp include/sub/../header.hpp "
                "include/space\\ header.hpp\n".format(target),
                encoding="utf-8")
            observed = MODULE._d12_dependency_inputs(
                dependency, target, working)
            self.assertEqual(
                [item["path"] for item in observed],
                [str(source.resolve()), str(header.resolve()),
                 str(spaced.resolve())])

            provider_root_inputs = [{
                "path": str((MODULE.ROOT / relative).resolve()),
                "sha256": MODULE.sha256_file(MODULE.ROOT / relative)}
                for relative in
                MODULE.RUNTIME_SOURCE_PATHS["row_provider"]]
            installed = {
                str(header.resolve()): {
                    "source_relative_path": "opensubdiv/header.hpp",
                    "sha256": MODULE.sha256_file(header)},
                str(spaced.resolve()): {
                    "source_relative_path": "opensubdiv/space header.hpp",
                    "sha256": MODULE.sha256_file(spaced)}}
            provider_inputs = provider_root_inputs + [
                {"path": path, "sha256": value["sha256"]}
                for path, value in installed.items()]
            for name in ("provider_release", "provider_tsan"):
                self.assertTrue(
                    MODULE._validate_d12_proof_dependency_closure(
                        name, provider_inputs, installed))
            forged = copy.deepcopy(provider_inputs)
            forged[-1]["sha256"] = "f" * 64
            with self.assertRaises(MODULE.QualificationError):
                MODULE._validate_d12_proof_dependency_closure(
                    "provider_release", forged, installed)
            with self.assertRaises(MODULE.QualificationError):
                MODULE._validate_d12_proof_dependency_closure(
                    "provider_tsan", provider_root_inputs, installed)

            representation_inputs = [{
                "path": str((MODULE.ROOT / relative).resolve()),
                "sha256": MODULE.sha256_file(MODULE.ROOT / relative)}
                for relative in MODULE.RUNTIME_SOURCE_PATHS[
                    "representation_candidate"]]
            self.assertTrue(
                MODULE._validate_d12_proof_dependency_closure(
                    "representation_release", representation_inputs, {}))
            with self.assertRaises(MODULE.QualificationError):
                MODULE._validate_d12_proof_dependency_closure(
                    "representation_tsan", representation_inputs + [{
                        "path": str(header.resolve()),
                        "sha256": MODULE.sha256_file(header)}], {})

    def test_d12_installed_headers_bind_to_tracked_source_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            source = root / "source"
            installed = root / "install/include/opensubdiv"
            source_header = source / "opensubdiv/version.h"
            installed_header = installed / "version.h"
            source_header.parent.mkdir(parents=True)
            installed.mkdir(parents=True)
            source_header.write_text("pinned header\n", encoding="utf-8")
            installed_header.write_bytes(source_header.read_bytes())
            subprocess.run(
                ["/usr/bin/git", "init", "-q"], cwd=str(source),
                check=True, capture_output=True)
            subprocess.run(
                ["/usr/bin/git", "add", "opensubdiv/version.h"],
                cwd=str(source), check=True, capture_output=True)
            bindings = MODULE._d12_installed_header_bindings(
                source, root / "install")
            self.assertEqual(bindings, {str(installed_header.resolve()): {
                "source_relative_path": "opensubdiv/version.h",
                "sha256": MODULE.sha256_file(installed_header)}})
            installed_header.write_text("mutated header\n", encoding="utf-8")
            with self.assertRaises(MODULE.QualificationError):
                MODULE._d12_installed_header_bindings(
                    source, root / "install")

    def test_d12_archive_is_independently_rebuilt_byte_exact(self):
        build = MODULE.B2.load_manifest()["qualification_platform"]["build"]
        if not pathlib.Path(build["compiler_path"]).is_file():
            self.skipTest("pinned macOS proof compiler unavailable")
        environment = MODULE._d12_rebuild_environment()
        envelope = MODULE._d12_envelope_contract_fixture()
        compile_command = copy.deepcopy(envelope["build_profiles"][
            "release"]["compile_commands"][1])
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            object_path = root / "member.o"
            dependency_path = root / "member.d"
            command = list(compile_command)
            command[command.index("-MF") + 1] = str(dependency_path)
            command[command.index("-o") + 1] = str(object_path)
            subprocess.run(
                command, check=True, capture_output=True,
                cwd=str(MODULE.ROOT), env=environment)
            ar_command = [
                "/Library/Developer/CommandLineTools/usr/bin/ar", "qc",
                "libproof.a", str(object_path)]
            ranlib_command = [
                "/Library/Developer/CommandLineTools/usr/bin/ranlib",
                "libproof.a"]
            subprocess.run(
                ar_command, check=True, capture_output=True,
                cwd=str(root), env=environment)
            subprocess.run(
                ranlib_command, check=True, capture_output=True,
                cwd=str(root), env=environment)
            archive = root / "libproof.a"
            MODULE._require_reproducible_archive(
                ar_command, ranlib_command, root, archive, environment,
                "release")
            tampered = bytearray(archive.read_bytes())
            self.assertGreater(len(tampered), 25)
            tampered[24] = ord("1") if tampered[24] != ord("1") else ord("2")
            archive.write_bytes(tampered)
            with self.assertRaises(MODULE.QualificationError):
                MODULE._require_reproducible_archive(
                    ar_command, ranlib_command, root, archive, environment,
                    "release")

    def test_d12_qualified_full_probe_fields_are_consequential(self):
        envelope = MODULE._d12_envelope_contract_fixture()
        platform = envelope["platform"]
        fingerprint = copy.deepcopy(platform["expected_fingerprint"])
        platform.update({
            "platform_state": "QUALIFIED_PLATFORM",
            "observed_fingerprint": copy.deepcopy(fingerprint),
            "field_mismatches": [], "github_hosted": False,
            "virtualization_observation": {
                "kern_hv_vmm_present": 0,
                "shared_host_evidence": False}})
        qualified_probe = {
            "schema_version": 1, "kind": "bfr_platform_probe",
            "status": "ok", "finite": True,
            "fingerprint_queries_ok": True,
            "fingerprint": copy.deepcopy(fingerprint),
            "power": {"api": MODULE.B2.EXPECTED_POWER_API,
                      "query_ok": True, "raw": "AC Power",
                      "value": MODULE.B2.EXPECTED_POWER_VALUE},
            "thermal": {"api": MODULE.B2.EXPECTED_THERMAL_API,
                        "query_ok": True, "raw": 0,
                        "value": MODULE.B2.EXPECTED_THERMAL_VALUE},
            "process_returncode": 0}
        platform["power_thermal_observations"] = [
            MODULE._d12_observation_record(identity, boundary,
                                           qualified_probe)
            for identity, boundary in
            MODULE._expected_d12_boundary_identities()]
        for criterion in envelope["criteria"]:
            criterion["status"] = "PASS"
        envelope["content_sha256"] = MODULE.ZERO_SHA256
        envelope["content_sha256"] = MODULE.sha256_bytes(
            MODULE.jcs_bytes(envelope))
        MODULE.validate_d12_envelope_contract(envelope, "a" * 40)
        for field_mutation in ("fingerprint", "process_returncode",
                               "power_raw"):
            candidate = copy.deepcopy(envelope)
            probe = candidate["platform"][
                "power_thermal_observations"][0]["probe"]
            if field_mutation == "fingerprint":
                probe["fingerprint"]["chip"] = "Invented"
            elif field_mutation == "power_raw":
                probe["power"]["raw"] = "INVENTED_RAW_POWER"
            else:
                probe["process_returncode"] = 1
            candidate["content_sha256"] = MODULE.ZERO_SHA256
            candidate["content_sha256"] = MODULE.sha256_bytes(
                MODULE.jcs_bytes(candidate))
            with self.assertRaises(MODULE.QualificationError):
                MODULE.validate_d12_envelope_contract(candidate, "a" * 40)

    def test_runtime_source_sets_include_local_transitive_headers(self):
        self.assertEqual(MODULE.RUNTIME_SOURCE_PATHS["row_provider"], (
            "experiments/bfr_qualification/candidate.cpp",
            "experiments/bfr_qualification/fixture_mesh.hpp",
            "experiments/anchored_row_qualification/anchored_row_evaluator.hpp"))
        self.assertEqual(MODULE.RUNTIME_SOURCE_PATHS[
            "representation_candidate"], (
                "experiments/anchored_row_qualification/candidate.cpp",
                "experiments/anchored_row_qualification/anchored_row_evaluator.hpp"))
        self.assertEqual(MODULE.RUNTIME_SOURCE_PATHS["independent_oracle"], (
            "experiments/bfr_qualification/stam_oracle.cpp",
            "experiments/bfr_qualification/stam_box_spline.hpp",
            "experiments/bfr_qualification/mpfr_interval.hpp",
            "experiments/bfr_qualification/stam_evaluation.hpp",
            "experiments/bfr_qualification/stam_primary.hpp",
            "experiments/bfr_qualification/stam_fixture.hpp",
            "experiments/bfr_qualification/stam_uniform.hpp",
            "experiments/bfr_qualification/stam_uniform_box_spline.hpp",
            ))
        for name, entrypoints in MODULE.RUNTIME_SOURCE_ENTRYPOINTS.items():
            self.assertEqual(MODULE.RUNTIME_SOURCE_PATHS[name],
                             MODULE._repository_source_closure(entrypoints))

    def test_oracle_certificates_are_computed_and_uniform_route_is_separate(self):
        oracle = (ROOT / "experiments/bfr_qualification/stam_oracle.cpp").read_text(
            encoding="utf-8")
        primary = (ROOT / "experiments/bfr_qualification/stam_primary.hpp").read_text(
            encoding="utf-8")
        uniform = (ROOT / "experiments/bfr_qualification/stam_uniform.hpp").read_text(
            encoding="utf-8")
        self.assertNotIn("bool projector_ok = true", primary)
        self.assertIn("certify_frozen_valence", oracle)
        for point in ("{0.25, 0.25}", "{0.5, 0.25}", "{0.25, 0.5}"):
            self.assertIn(point, oracle)
        self.assertIn('"1e-20"', oracle)
        self.assertIn("EIGENBASIS_CERTIFICATION_FAILED", oracle)
        self.assertIn("PARAMETRIC_MAP_CHECK_FAILED", oracle)
        self.assertIn("TANGENT_PROJECTION_CHECK_FAILED", oracle)
        self.assertIn('"DIRECTED_INTERVAL_PRIMITIVE_FAILED"', oracle)
        self.assertIn('"INTERVAL_BRANCH_ORDERING_UNCERTIFIED"', oracle)
        self.assertIn("directed_rounding_mutation_self_test", oracle)
        self.assertNotIn("mpfr_sin", (
            ROOT / "experiments/bfr_qualification/mpfr_interval.hpp"
        ).read_text(encoding="utf-8"))
        self.assertIn("selected_face_distances", oracle)
        self.assertNotIn("for(auto const &face:state.mesh.faces)", oracle)
        self.assertIn("rethrow_exact_or_fallback", oracle)
        self.assertIn("is_exact_interval_reason(error.what())", oracle)
        self.assertNotIn('#include "stam_box_spline.hpp"', uniform)
        self.assertIn('#include "stam_uniform_box_spline.hpp"', uniform)
        self.assertNotIn("b2stam_fixture::local_support(", uniform)
        self.assertIn("complete_mesh_backward_closure", uniform)
        self.assertIn("backward_refine_selected", uniform)
        self.assertIn("backward_dependency_self_test", uniform)
        interval = (ROOT / "experiments/bfr_qualification/mpfr_interval.hpp").read_text(
            encoding="utf-8")
        for mutation in ("AddLower", "SubtractUpper", "MultiplyLower",
                         "DivideUpper", "SquareRootLower", "CosineUpper",
                         "MatrixAccumulatorLower"):
            self.assertIn("ProductionRoundingMutation::" + mutation,
                          interval)
        self.assertTrue(MODULE._audit_oracle_mpfr_calls())
        forged = MODULE._valid_oracle_covered_record()
        with self.assertRaises(MODULE.QualificationError):
            MODULE.canonical_result_ledger(
                [forged], criterion_id="oracle_coverage_and_crosscheck")
        self.assertEqual(MODULE.canonical_result_ledger(
            [forged], criterion_id="oracle_coverage_and_crosscheck",
            oracle_certification_authority=
                MODULE._ORACLE_CERTIFICATION_AUTHORITY)["record_count"], 1)
        zero = {"kind": "interval_rational_v1",
                "lower": {"kind": "rational_v1", "numerator": "0",
                          "denominator": "1"},
                "upper": {"kind": "rational_v1", "numerator": "0",
                          "denominator": "1"}}
        forged[2]["primary_depth_intervals"] = [[
            copy.deepcopy(zero) for _ in range(5)]]
        forged[2]["uniform_depth_intervals"] = [[
            copy.deepcopy(zero) for _ in range(5)]]
        forged[2]["intersected_primary_intervals"] = [copy.deepcopy(zero)]
        with self.assertRaises(MODULE.QualificationError):
            MODULE.validate_contract_result_record(
                "oracle_coverage_and_crosscheck", forged)

    def test_oracle_independence_audit_is_executable_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            binary = root / "stam_oracle"
            dependency = root / "oracle.d"
            link_map = root / "oracle.map"
            dynamic = root / "oracle.otool-L"
            dependency_root = root / "mpfr"
            include_root = dependency_root / "include"
            library_root = dependency_root / "lib"
            include_root.mkdir(parents=True)
            library_root.mkdir(parents=True)
            mpfr_header = include_root / "mpfr.h"
            gmp_header = include_root / "gmp.h"
            mpfr_library = library_root / "libmpfr.6.dylib"
            gmp_library = library_root / "libgmp.10.dylib"
            for path, data in ((mpfr_header, b"mpfr header\n"),
                               (gmp_header, b"gmp header\n"),
                               (mpfr_library, b"mpfr library\n"),
                               (gmp_library, b"gmp library\n")):
                path.write_bytes(data)
            dynamic_bytes = (
                (str(binary) + ":\n\t" + str(mpfr_library) +
                 " (compatibility version 7.0.0, current version 7.2.2)\n" +
                 "\t" + str(gmp_library) +
                 " (compatibility version 11.0.0, current version 11.0.0)\n")
                .encode("utf-8"))
            for path, data in ((binary, b"binary"),
                               (dependency, b"dependency\n"),
                               (link_map, b"# Path: stam_oracle\n"),
                               (dynamic, dynamic_bytes)):
                path.write_bytes(data)
            command = [
                MODULE.B2.EXPECTED_COMPILER_PATH,
                "-std=c++17", "-O3", "-DNDEBUG", "-fno-fast-math",
                "-ffp-contract=off", "-fno-omit-frame-pointer", "-Wall",
                "-Wextra", "-Wpedantic", "-Werror", "-isysroot",
                "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk",
                "-mmacosx-version-min=26.0", "-MMD", "-MF", str(dependency),
                "-I" + str(include_root),
                "experiments/bfr_qualification/stam_oracle.cpp",
                "-L" + str(library_root),
                "-Wl,-rpath," + str(library_root), "-lmpfr", "-lgmp",
                "-Wl,-map," + str(link_map), "-o", str(binary)]
            command_path = root / "oracle.command"
            command_path.write_text("\n".join(command) + "\n", encoding="utf-8")
            dependencies = [{"path": str((ROOT / relative).resolve()),
                             "sha256": MODULE.sha256_file(ROOT / relative)}
                            for relative in MODULE.RUNTIME_SOURCE_PATHS[
                                "independent_oracle"]]
            dependencies.extend({"path": str(path),
                                 "sha256": MODULE.sha256_file(path)}
                                for path in (mpfr_header, gmp_header))
            installed_root = root / "authenticated-install"
            installed_root.mkdir()
            installed_libraries = {
                "gmp": installed_root / "libgmp.10.dylib",
                "mpfr": installed_root / "libmpfr.6.dylib"}
            installed_libraries["gmp"].write_bytes(gmp_library.read_bytes())
            installed_libraries["mpfr"].write_bytes(mpfr_library.read_bytes())

            def completed(argv, **unused):
                output = (dynamic.read_bytes() if argv[1] == "-L" else
                          b"                 U _mpfr_add\n")
                return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

            with mock.patch.object(MODULE.B2, "validate_source_separation"), \
                    mock.patch.object(MODULE, "_d12_dependency_inputs",
                                      return_value=dependencies), \
                    mock.patch.object(MODULE.subprocess, "run",
                                      side_effect=completed):
                sealed = root / "oracle.dynamic-audit.json"
                self.assertEqual(MODULE.audit_oracle_independence(
                    binary, command_path, link_map, dynamic,
                    sealed_output_path=sealed), "PASS")
                runtime_bindings = MODULE._snapshot_oracle_runtime_libraries(
                    sealed, root /
                    "anchored-row-oracle-runtime-libraries-v1")
                self.assertEqual(
                    [item[0].name for item in runtime_bindings],
                    ["libgmp.10.dylib", "libmpfr.6.dylib"])
                self.assertEqual(MODULE.audit_oracle_independence(
                    binary, command_path, link_map, sealed), "PASS")
                with mock.patch.object(
                        MODULE, "ORACLE_EXECUTION_REQUEST_COUNT", 1):
                    raw_value = MODULE.jcs_bytes({
                        "schema_version": 1,
                        "kind": "stam_oracle_sample_v1",
                        "status": "uncovered",
                        "reason_code": "NO_ISOLATION_BY_DEPTH_12"})
                    audit = MODULE.OracleExecutionAuditArtifact(root)
                    audit.add("request\n", "a" * 64, raw_value,
                              MODULE.strict_json_bytes(raw_value))
                    descriptor = audit.finish()
                    execution_packet = root / (
                        "anchored-row-oracle-runtime-execution-audit-v2.json")
                    MODULE._publish_oracle_runtime_execution_packet(
                        sealed, runtime_bindings, descriptor,
                        execution_packet, installed_libraries)
                    self.assertEqual(MODULE.audit_oracle_independence(
                        binary, command_path, link_map,
                        execution_packet,
                        installed_library_paths=installed_libraries), "PASS")
                    with self.assertRaises(MODULE.QualificationError):
                        MODULE.audit_oracle_independence(
                            binary, command_path, link_map,
                            execution_packet)
                    with self.assertRaises(MODULE.QualificationError):
                        MODULE.audit_oracle_independence(
                            binary, command_path, link_map,
                            execution_packet,
                            installed_library_paths={
                                "gmp": runtime_bindings[0][2],
                                "mpfr": runtime_bindings[1][2]})
                    projected = MODULE.strict_json_bytes(
                        execution_packet.read_bytes())
                    projected["libraries"][0]["audited_path"] = str(
                        library_root / "invented-libgmp.10.dylib")
                    execution_packet.write_bytes(MODULE.jcs_bytes(projected))
                    with self.assertRaises(MODULE.QualificationError):
                        MODULE.audit_oracle_independence(
                            binary, command_path, link_map,
                            execution_packet,
                            installed_library_paths=installed_libraries)
                    projected["libraries"][0]["audited_path"] = str(
                        gmp_library)
                    execution_packet.write_bytes(MODULE.jcs_bytes(projected))
                    loaded_gmp = pathlib.Path(runtime_bindings[0][2])
                    canonical_loaded_gmp = loaded_gmp.read_bytes()
                    coordinated = MODULE.strict_json_bytes(
                        execution_packet.read_bytes())
                    loaded_gmp.chmod(0o600)
                    loaded_gmp.write_bytes(b"coordinated substitute gmp\n")
                    coordinated["libraries"][0]["sha256"] = \
                        MODULE.sha256_file(loaded_gmp)
                    execution_packet.write_bytes(
                        MODULE.jcs_bytes(coordinated))
                    with self.assertRaises(MODULE.QualificationError):
                        MODULE.audit_oracle_independence(
                            binary, command_path, link_map,
                            execution_packet,
                            installed_library_paths=installed_libraries)
                    loaded_gmp.write_bytes(canonical_loaded_gmp)
                    loaded_gmp.chmod(0o500)
                    execution_packet.write_bytes(MODULE.jcs_bytes(projected))
                mpfr_library.write_bytes(b"tampered mpfr library\n")
                with self.assertRaises(MODULE.QualificationError):
                    MODULE.audit_oracle_independence(
                        binary, command_path, link_map, sealed)
                with mock.patch.object(
                        MODULE, "ORACLE_EXECUTION_REQUEST_COUNT", 1):
                    self.assertEqual(MODULE.audit_oracle_independence(
                        binary, command_path, link_map,
                        execution_packet,
                        installed_library_paths=installed_libraries), "PASS")
                mpfr_library.write_bytes(b"mpfr library\n")

            for injected in ("@/private/tmp/oracle-extra.rsp", "-include"):
                command_path.write_text(
                    "\n".join(command + [injected]) + "\n", encoding="utf-8")
                with mock.patch.object(MODULE.B2,
                                       "validate_source_separation"), \
                        mock.patch.object(MODULE,
                                          "_d12_dependency_inputs",
                                          return_value=dependencies), \
                        mock.patch.object(MODULE.subprocess, "run",
                                          side_effect=completed), \
                        self.assertRaises(MODULE.QualificationError):
                    MODULE.audit_oracle_independence(
                        binary, command_path, link_map, dynamic)
            command_path.write_text(
                "\n".join(command) + "\n", encoding="utf-8")

            def forbidden(argv, **unused):
                output = (dynamic.read_bytes() if argv[1] == "-L" else
                          b"                 U _Far_poison\n                 U _mpfr_add\n")
                return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

            with mock.patch.object(MODULE.B2, "validate_source_separation"), \
                    mock.patch.object(MODULE, "_d12_dependency_inputs",
                                      return_value=dependencies), \
                    mock.patch.object(MODULE.subprocess, "run",
                                      side_effect=forbidden), \
                    self.assertRaises(MODULE.QualificationError):
                MODULE.audit_oracle_independence(
                    binary, command_path, link_map, dynamic)

    def test_oracle_runtime_execution_packet_binds_snapshots_and_requests(self):
        self.assertEqual(MODULE.ORACLE_EXECUTION_REQUEST_COUNT, 16500)
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            original_root = root / "original"
            original_root.mkdir()
            originals = []
            libraries = []
            for name, payload in (("gmp", b"gmp-proof-bytes\n"),
                                  ("mpfr", b"mpfr-proof-bytes\n")):
                path = original_root / ("lib" + name + ".dylib")
                path.write_bytes(payload)
                originals.append(path)
                libraries.append({"name": name, "path": str(path),
                                  "sha256": MODULE.sha256_file(path)})
            transcript = "proof-oracle:\n"
            sealed = root / "sealed.json"
            sealed.write_bytes(MODULE.jcs_bytes({
                "schema_id": "oracle-runtime-dependency-audit-v1",
                "otool_L_text": transcript,
                "otool_L_sha256": MODULE.sha256_bytes(
                    transcript.encode("utf-8")),
                "libraries": libraries}))
            loaded = MODULE._snapshot_oracle_runtime_libraries(
                sealed,
                root / "anchored-row-oracle-runtime-libraries-v1")
            raw_value = MODULE.jcs_bytes({
                "schema_version": 1, "kind": "stam_oracle_sample_v1",
                "status": "uncovered",
                "reason_code": "NO_ISOLATION_BY_DEPTH_12"})
            with mock.patch.object(MODULE,
                                   "ORACLE_EXECUTION_REQUEST_COUNT", 1):
                audit = MODULE.OracleExecutionAuditArtifact(root)
                audit.add("request\n", "a" * 64, raw_value,
                          MODULE.strict_json_bytes(raw_value))
                descriptor = audit.finish()
                packet = root / "anchored-row-oracle-runtime-execution-audit-v2.json"
                installed_libraries = {
                    item["name"]: pathlib.Path(item["path"])
                    for item in libraries}
                MODULE._publish_oracle_runtime_execution_packet(
                    sealed, loaded, descriptor, packet,
                    installed_libraries)
                self.assertEqual(MODULE._bound_oracle_execution_audit(packet),
                                 descriptor)
                replay = root / "replay"
                rebound = MODULE._snapshot_oracle_runtime_libraries(
                    packet, replay)
                self.assertEqual([item[1] for item in rebound],
                                 [item["sha256"] for item in libraries])
                originals[0].write_bytes(b"changed after execution\n")
                self.assertEqual(MODULE._bound_oracle_execution_audit(packet),
                                 descriptor)
                loaded_path = pathlib.Path(loaded[0][2])
                canonical_loaded = loaded_path.read_bytes()
                loaded_path.chmod(0o600)
                loaded_path.write_bytes(b"changed loaded snapshot\n")
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._bound_oracle_execution_audit(packet)
                loaded_path.write_bytes(canonical_loaded)
                loaded_path.chmod(0o500)
                audit_path = root / MODULE.ORACLE_EXECUTION_AUDIT_PATH
                canonical_audit = audit_path.read_bytes()
                audit_path.write_bytes(canonical_audit + b"\n")
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._bound_oracle_execution_audit(packet)
                audit_path.write_bytes(canonical_audit)

    def test_standalone_d12_uses_distinct_opensubdiv_library_argument(self):
        arguments = MODULE.parse_args([
            "--opensubdiv-dynamic-dependency", "/proof/opensubdiv.otool-L",
            "--opensubdiv-installed-library", "/proof/libosdCPU.a"])
        self.assertEqual(arguments.opensubdiv_dynamic_dependency,
                         "/proof/opensubdiv.otool-L")
        self.assertEqual(arguments.opensubdiv_installed_library,
                         "/proof/libosdCPU.a")
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertIn('"installed_library":\n'
                      '                                args.opensubdiv_installed_library',
                      runner)
        self.assertNotIn('"installed_library":\n'
                         '                                args.opensubdiv_dynamic_dependency',
                         runner)

    def test_d12_provider_reference_preserves_frozen_row_order(self):
        rows = []
        for row_kind in MODULE.ROW_ORDER:
            rows.append({"face_row": 0, "local_corner_or_none": -1,
                         "sample_id": "sample", "row_kind": row_kind,
                         "source_ids": [0, 1, 2],
                         "coefficients": ([1.0, 0.0, 0.0]
                                          if row_kind == "position" else
                                          [0.0, 0.0, 0.0])})
        provider = b"".join(
            MODULE.D12WorkerInventoryVerifier._provider_record_bytes(row)
            for row in rows)
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            raw = MODULE.jcs_bytes({
                "rows": rows,
                "row_kind_counts": {kind: 1 for kind in MODULE.ROW_ORDER}})
            artifact = root / "case.json.gz"
            artifact.write_bytes(gzip.compress(raw, mtime=0))
            case = {"content_identity_key": "content",
                    "approximation_level": 2,
                    "complete_json_artifact": artifact.name,
                    "complete_json_sha256": MODULE.sha256_bytes(raw),
                    "canonical_rows_sha256": MODULE.sha256_bytes(provider)}
            result = MODULE.D12WorkerInventoryVerifier._case_contract(
                case, root, {"vertices": [(0.0, 0.0, 0.0),
                                           (1.0, 0.0, 0.0),
                                           (0.0, 1.0, 0.0)],
                             "faces": [[0, 1, 2]]})
            self.assertEqual(result[1], MODULE.sha256_bytes(provider))

    def test_standalone_validation_binds_actual_git_head_and_cleanliness(self):
        head = "a" * 40
        report = {
            "identity": {
                "git_start": {"git_commit": head},
                "git_end": {"git_commit": head},
                "worktree_start": {"clean": True},
                "worktree_end": {"clean": True},
                "validator": {"sha256": MODULE.sha256_file(
                    pathlib.Path(MODULE.__file__).resolve())}},
            "checkpoint": {"git_head": head}, "binaries": {}}
        actual = ({"state": "PRESENT", "git_commit": head,
                   "reason_code": None},
                  {"state": "PRESENT", "clean": True,
                   "reason_code": None})
        with mock.patch.object(MODULE, "git_observations",
                               return_value=actual):
            MODULE._validate_runtime_bindings(report, {})
            forged = copy.deepcopy(report)
            forged["identity"]["git_end"]["git_commit"] = "b" * 40
            with self.assertRaises(MODULE.QualificationError):
                MODULE._validate_runtime_bindings(forged, {})
            dirty = (actual[0], {"state": "INVALID", "clean": None,
                                 "reason_code": "WORKTREE_DIRTY"})
            with mock.patch.object(MODULE, "git_observations",
                                   return_value=dirty):
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._validate_runtime_bindings(report, {})

    def test_git_probes_ignore_ambient_repository_redirects(self):
        expected = MODULE.git_observations()
        with mock.patch.dict(os.environ, {
                "GIT_DIR": "/nonexistent/redirected.git",
                "GIT_WORK_TREE": "/nonexistent/redirected-worktree",
                "PATH": "/nonexistent/bin"}, clear=False):
            self.assertEqual(MODULE.git_observations(), expected)

        environment = MODULE._d12_rebuild_environment()
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            source = root / "opensubdiv/version.cpp"
            header = root / "opensubdiv/poisonable.h"
            source.parent.mkdir(parents=True)
            source.write_text(
                '#include "poisonable.h"\nint pinned_source = PINNED;\n',
                encoding="utf-8")
            header.write_text("#define PINNED 1\n", encoding="utf-8")
            for command in (
                    ["/usr/bin/git", "init", "-q", str(root)],
                    ["/usr/bin/git", "add", "opensubdiv"],
                    ["/usr/bin/git", "-c", "user.name=D12",
                     "-c", "user.email=d12@example.invalid", "commit", "-qm",
                     "pinned source"]):
                subprocess.run(
                    command, check=True, capture_output=True, cwd=str(root),
                    env=environment)
            head = MODULE._run_d12_closed_git(
                ["rev-parse", "HEAD"], root).stdout.strip()
            manifest = {"qualification_platform": {"build": {
                "opensubdiv": {"translation_units_in_target_order": [
                    "opensubdiv/version.cpp"]}}}}
            with mock.patch.object(MODULE.B2, "OPENSUBDIV_COMMIT", head), \
                    mock.patch.dict(os.environ, {
                        "GIT_DIR": str(MODULE.ROOT / ".git"),
                        "GIT_WORK_TREE": str(MODULE.ROOT)}, clear=False):
                audit = MODULE._audit_d12_source_checkout(root, manifest)
                self.assertEqual(audit["head"], head)
                subprocess.run(
                    ["/usr/bin/git", "update-index", "--skip-worktree",
                     "opensubdiv/poisonable.h"], check=True,
                    capture_output=True, cwd=str(root), env=environment)
                header.write_text("#define PINNED 999\n", encoding="utf-8")
                self.assertEqual(
                    MODULE._run_d12_closed_git(
                        ["status", "--porcelain=v1"], root).stdout, "")
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._audit_d12_source_checkout(root, manifest)
                subprocess.run(
                    ["/usr/bin/git", "update-index", "--no-skip-worktree",
                     "opensubdiv/poisonable.h"], check=True,
                    capture_output=True, cwd=str(root), env=environment)
                header.write_text("#define PINNED 1\n", encoding="utf-8")
                subprocess.run(
                    ["/usr/bin/git", "update-index", "--assume-unchanged",
                     "opensubdiv/poisonable.h"], check=True,
                    capture_output=True, cwd=str(root), env=environment)
                header.write_text("#define PINNED 777\n", encoding="utf-8")
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._audit_d12_source_checkout(root, manifest)
                subprocess.run(
                    ["/usr/bin/git", "update-index", "--no-assume-unchanged",
                     "opensubdiv/poisonable.h"], check=True,
                    capture_output=True, cwd=str(root), env=environment)
                header.write_text("#define PINNED 1\n", encoding="utf-8")
                source.write_text(
                    "int pinned_source = 2;\n", encoding="utf-8")
                with self.assertRaises(MODULE.QualificationError):
                    MODULE._audit_d12_source_checkout(root, manifest)

    def test_streamed_result_record_has_hard_byte_and_nesting_caps(self):
        record = MODULE.jcs_bytes([["cell"], "PASS", None, None, None])
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "result.json"
            path.write_bytes(b"[" + record + b"]")
            with mock.patch.object(MODULE, "MAX_RESULT_RECORD_BYTES",
                                   len(record) - 1):
                with self.assertRaises(MODULE.QualificationError):
                    list(MODULE._iter_canonical_result_records(
                        path, MODULE.hashlib.sha256()))
            nested = b"[" * 66 + b"0" + b"]" * 66
            path.write_bytes(b"[" + nested + b"]")
            with self.assertRaises(MODULE.QualificationError):
                list(MODULE._iter_canonical_result_records(
                    path, MODULE.hashlib.sha256()))

    def test_m12_baselines_are_semantically_valid_before_mutation(self):
        for criterion_id in MODULE.CRITERION_IDS:
            record = MODULE._valid_result_record_for_mutation(criterion_id)
            MODULE.validate_contract_result_record(
                criterion_id, record,
                defer_basis_group=(criterion_id ==
                                   "binary64_basis_probe_diagnostic"))
            secondary_criterion = (
                "constant_field_bits" if criterion_id ==
                "bindings_and_independence" else criterion_id)
            secondary = MODULE._valid_result_record_for_mutation(
                secondary_criterion,
                variant=(0 if criterion_id ==
                         "bindings_and_independence" else 1))
            MODULE.validate_contract_result_record(
                secondary_criterion, secondary,
                defer_basis_group=(secondary_criterion ==
                                   "binary64_basis_probe_diagnostic"))
            MODULE.canonical_result_ledger(sorted(
                [record, secondary], key=lambda item: MODULE.jcs_bytes(item[0])))

    def test_d12_evidence_rescans_enclosing_json_and_b2row_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            key = ["content", 2, "release", "cache_disabled", None,
                   None, None, "measured", 0, None, None, None, None,
                   "preparation_duration_ns"]
            payload = {"kind": "d12_duration_raw_v1",
                       "state": "VALID_UINT64_NS", "token": "1"}
            provenance = {
                "kind": "d12_process_provenance_v1",
                "process_tuple_sha256": MODULE.sha256_bytes(
                    MODULE.jcs_bytes(key[:5])),
                "executable_sha256": "a" * 64,
                "argv_sha256": "b" * 64,
                "environment_sha256": "c" * 64,
                "pid": 1, "start_utc": "2026-08-12T00:00:00Z",
                "end_utc": "2026-08-12T00:00:01Z",
                "exit_kind": "EXITED", "exit_code": 0, "signal": None,
                "stderr_sha256": "d" * 64}
            encoded_record = MODULE.jcs_bytes([key, payload, provenance])
            process_raw = b"[" + encoded_record + b"]"
            process_relative = (
                MODULE.D12EvidenceVerifier.PROCESS_OBSERVATION_PATH)
            process_path = root / process_relative
            process_path.parent.mkdir(parents=True)
            process_path.write_bytes(process_raw)
            process_digest = MODULE.sha256_bytes(process_raw)
            process_descriptor = {
                "availability": MODULE.availability(
                    "PRESENT", process_digest),
                "relative_path": process_relative,
                "byte_length": len(process_raw), "record_count": 1,
                "sha256": process_digest}
            verifier = MODULE.D12EvidenceVerifier(root)
            verifier.sidecar(process_descriptor)
            binding = {
                "availability": MODULE.availability(
                    "PRESENT", MODULE.sha256_bytes(encoded_record)),
                "relative_path": process_relative, "byte_offset": 1,
                "byte_length": len(encoded_record),
                "sha256": MODULE.sha256_bytes(encoded_record)}
            self.assertEqual(verifier.raw_observation(key, binding), payload)
            mismatched_value = {
                "kind": "d12_duration_valid_v1",
                "quantity": "preparation_duration_ns", "duration_ns": 2,
                "platform_state": "QUALIFIED_PLATFORM",
                "raw_observation": copy.deepcopy(binding)}
            with self.assertRaises(MODULE.QualificationError):
                verifier.result_record(key, mismatched_value)
            changed = copy.deepcopy(binding)
            changed["byte_offset"] = 0
            with self.assertRaises(MODULE.QualificationError):
                verifier.raw_observation(key, changed)

            row = b"".join(
                b"B2ROWV1" + struct.pack("<i", 0) +
                struct.pack("<I", 6) + b"sample" +
                struct.pack("<I", ordinal) + struct.pack("<I", 1) +
                struct.pack("<i", 0) + struct.pack("<d", 1.0)
                for ordinal in range(6))
            row_path = root / "provider.b2rowv1"
            row_path.write_bytes(row)
            row_digest = MODULE.sha256_bytes(row)
            self.assertTrue(verifier.sidecar({
                "availability": MODULE.availability("PRESENT", row_digest),
                "relative_path": "provider.b2rowv1",
                "byte_length": len(row), "record_count": 6,
                "sha256": row_digest}))

    def test_d12_sanitizer_abort_binds_two_processes_and_report_bytes(self):
        content_id = "content"
        base_key = [content_id, 2, "tsan", "threaded_cache", 1,
                    None, None, None, None, None, None, None,
                    "sanitizer_summary", None]
        instrumentation_key = copy.deepcopy(base_key)
        instrumentation_key[13] = "instrumentation_coverage"
        finding_key = copy.deepcopy(base_key)
        finding_key[13] = "tsan_finding_count"
        instrumentation_digest = "a" * 64
        report = b"WARNING: ThreadSanitizer: data race\nexact report\n"
        report_digest = MODULE.sha256_bytes(report)
        finding_provenance = {
            "kind": "d12_process_provenance_v1",
            "process_tuple_sha256": MODULE.sha256_bytes(
                MODULE.jcs_bytes(base_key[:5])),
            "executable_sha256": "b" * 64,
            "argv_sha256": "c" * 64,
            "environment_sha256": "d" * 64,
            "pid": 123, "start_utc": "2026-08-16T00:00:00Z",
            "end_utc": "2026-08-16T00:00:01Z",
            "exit_kind": "EXITED", "exit_code": 66, "signal": None,
            "stderr_sha256": report_digest}
        instrumentation_provenance = copy.deepcopy(finding_provenance)
        instrumentation_provenance.update({
            "executable_sha256": "f" * 64,
            "argv_sha256": "e" * 64,
            "pid": 122,
            "exit_code": 0,
            "stderr_sha256": MODULE.sha256_bytes(b"")})
        instrumentation_payload = {
            "kind": "d12_tsan_instrumentation_raw_v1",
            "state": "COMPLETE",
            "instrumented_translation_units_sha256":
                instrumentation_digest}
        finding_payload = {
            "kind": "d12_tsan_finding_raw_v1",
            "state": "SANITIZER_ABORT", "finding_count_token": None,
            "sanitizer_report_sha256": report_digest}
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            report_path = root / MODULE._d12_tsan_report_relative_path(
                finding_key)
            report_path.parent.mkdir(parents=True)
            report_path.write_bytes(report)
            artifact = MODULE.D12ProcessObservationArtifact(
                root, {instrumentation_provenance["executable_sha256"],
                       finding_provenance["executable_sha256"]})
            try:
                artifact.add("d12_instrumented_tsan", [
                    instrumentation_key, instrumentation_payload,
                    copy.deepcopy(instrumentation_provenance)])
                artifact.add("d12_instrumented_tsan", [
                    finding_key, finding_payload,
                    copy.deepcopy(finding_provenance)])
                descriptor = artifact.finish(2)
                verifier = MODULE.D12EvidenceVerifier(
                    root, expected_instrumented_translation_units=
                    instrumentation_digest)
                verifier.sidecar(descriptor)
                bindings = {
                    key[13]: (key, payload, binding)
                    for key, payload, binding in artifact.iter_bindings(
                        "d12_instrumented_tsan")}
                key, payload, binding = bindings[
                    "instrumentation_coverage"]
                instrumentation_value = {
                    "kind": "d12_tsan_instrumentation_summary_v1",
                    "instrumentation_complete": True,
                    "instrumented_translation_units_sha256":
                        instrumentation_digest,
                    "expected_translation_units_sha256":
                        instrumentation_digest,
                    "platform_state": "QUALIFIED_PLATFORM",
                    "raw_observation": binding}
                instrumentation_target = {
                    "kind": "d12_tsan_instrumentation_target_v1",
                    "instrumentation_complete": True,
                    "expected_translation_units_sha256":
                        instrumentation_digest}
                MODULE.validate_contract_result_record(
                    "d12_instrumented_tsan",
                    [key, "PASS", instrumentation_value,
                     instrumentation_target, None])
                verifier.result_record(
                    key, instrumentation_value, instrumentation_target)
                key, payload, binding = bindings["tsan_finding_count"]
                finding_value = {
                    "kind": "d12_tsan_finding_summary_v1",
                    "finding_count": None, "sanitizer_abort": True,
                    "sanitizer_report_sha256": report_digest,
                    "platform_state": "QUALIFIED_PLATFORM",
                    "raw_observation": binding}
                finding_target = {
                    "kind": "d12_tsan_finding_target_v1",
                    "finding_count": 0}
                MODULE.validate_contract_result_record(
                    "d12_instrumented_tsan",
                    [key, "FAIL", finding_value, finding_target,
                     "THREADED_CACHE_RACE"])
                verifier.result_record(key, finding_value, finding_target)
                report_path.write_bytes(report + b"tampered")
                with self.assertRaises(MODULE.QualificationError):
                    verifier.result_record(key, finding_value, finding_target)
            finally:
                artifact.close()

        with tempfile.TemporaryDirectory() as temporary:
            artifact = MODULE.D12ProcessObservationArtifact(
                temporary, {
                    instrumentation_provenance["executable_sha256"],
                    "9" * 64})
            try:
                artifact.add("d12_instrumented_tsan", [
                    instrumentation_key, instrumentation_payload,
                    copy.deepcopy(instrumentation_provenance)])
                artifact.add("d12_instrumented_tsan", [
                    finding_key, finding_payload,
                    copy.deepcopy(finding_provenance)])
                with self.assertRaises(MODULE.QualificationError):
                    artifact.finish(2)
            finally:
                artifact.close()

        with tempfile.TemporaryDirectory() as temporary:
            artifact = MODULE.D12ProcessObservationArtifact(temporary)
            try:
                artifact.add("d12_instrumented_tsan", [
                    instrumentation_key, instrumentation_payload,
                    copy.deepcopy(instrumentation_provenance)])
                changed = copy.deepcopy(finding_provenance)
                changed["executable_sha256"] = \
                    instrumentation_provenance["executable_sha256"]
                artifact.add("d12_instrumented_tsan", [
                    finding_key, finding_payload, changed])
                with self.assertRaises(MODULE.QualificationError):
                    artifact.finish(2)
            finally:
                artifact.close()

        with tempfile.TemporaryDirectory() as temporary:
            artifact = MODULE.D12ProcessObservationArtifact(
                temporary, {
                    instrumentation_provenance["executable_sha256"],
                    finding_provenance["executable_sha256"]})
            try:
                artifact.add("d12_instrumented_tsan", [
                    instrumentation_key, instrumentation_payload,
                    copy.deepcopy(instrumentation_provenance)])
                changed = copy.deepcopy(finding_provenance)
                changed["pid"] = instrumentation_provenance["pid"]
                artifact.add("d12_instrumented_tsan", [
                    finding_key, finding_payload, changed])
                with self.assertRaises(MODULE.QualificationError):
                    artifact.finish(2)
            finally:
                artifact.close()

    def test_d12_race_results_preserve_full_keys_and_omit_only_tuple_bytes(self):
        identities = [
            ("content", 2, "cache_disabled", 1),
            ("content", 2, "SurfaceFactoryCacheThreaded", 1)]
        provider_digest = "a" * 64
        representation_digest = "b" * 64
        instrumentation_digest = "c" * 64
        references = {
            ("content", 2): {
                "provider": provider_digest,
                "representation": representation_digest}}

        def descriptor(relative_path, digest, count):
            return {
                "availability": MODULE.availability("PRESENT", digest),
                "relative_path": relative_path, "byte_length": 1,
                "record_count": count, "sha256": digest}

        def sidecars(abort_mode):
            result = []
            for _, _, mode, workers in identities:
                normalized = ("threaded_cache" if mode ==
                              "SurfaceFactoryCacheThreaded" else mode)
                if normalized == abort_mode:
                    continue
                for round_index in range(20):
                    prefix = (
                        "anchored-row-d12-v1/workers/{}/content/level-2/"
                        "workers-{}/round-{:02d}/worker-0".format(
                            normalized, workers, round_index))
                    result.extend([
                        descriptor(prefix + "-provider.b2rowv1",
                                   provider_digest, 6),
                        descriptor(prefix + "-representation.json",
                                   representation_digest, 48)])
            return sorted(result, key=lambda item: MODULE.jcs_bytes(
                item["relative_path"]))

        def binding(index):
            digest = "{:064x}".format(index + 1)
            return {
                "kind": "d12_raw_observation_binding_v1",
                "availability": MODULE.availability("PRESENT", digest),
                "relative_path":
                    MODULE.D12EvidenceVerifier.PROCESS_OBSERVATION_PATH,
                "byte_offset": index + 1, "byte_length": 1,
                "sha256": digest}

        class RawArtifact:
            def __init__(self, abort_mode):
                self.records = []
                index = 0
                for _, _, mode, workers in identities:
                    normalized = ("threaded_cache" if mode ==
                                  "SurfaceFactoryCacheThreaded" else mode)
                    for quantity in ("instrumentation_coverage",
                                     "tsan_finding_count"):
                        key = [
                            "content", 2, "tsan", normalized, workers,
                            None, None, None, None, None, None, None,
                            "sanitizer_summary", quantity]
                        if quantity == "instrumentation_coverage":
                            payload = {
                                "kind": "d12_tsan_instrumentation_raw_v1",
                                "state": "COMPLETE",
                                "instrumented_translation_units_sha256":
                                    instrumentation_digest}
                        elif normalized == abort_mode:
                            payload = {
                                "kind": "d12_tsan_finding_raw_v1",
                                "state": "SANITIZER_ABORT",
                                "finding_count_token": None,
                                "sanitizer_report_sha256": "d" * 64}
                        else:
                            payload = {
                                "kind": "d12_tsan_finding_raw_v1",
                                "state": "COMPLETE",
                                "finding_count_token": "0",
                                "sanitizer_report_sha256": None}
                        self.records.append((key, payload, binding(index)))
                        index += 1

            def iter_bindings(self, criterion_id):
                self.assert_criterion = criterion_id
                return iter(self.records)

        for abort_mode in ("cache_disabled", "threaded_cache"):
            descriptors = sidecars(abort_mode)
            aborts = {("content", 2, abort_mode, 1): "d" * 64}
            with tempfile.TemporaryDirectory() as temporary, \
                    mock.patch.object(
                        MODULE.B2, "expected_threading_identities",
                        return_value=identities), \
                    mock.patch.dict(
                        MODULE.EXPECTED_CELL_COUNTS,
                        {"d12_cache_disabled_concurrency": 20,
                         "d12_instrumented_tsan": 24}):
                result, context = MODULE.execute_d12_threading_criteria(
                    descriptors, references, RawArtifact(abort_mode),
                    temporary, "QUALIFIED_PLATFORM",
                    instrumentation_digest, aborts)
                self.assertEqual(result[
                    "d12_cache_disabled_concurrency"]["observed_count"], 20)
                self.assertEqual(result[
                    "d12_instrumented_tsan"]["observed_count"], 24)
                self.assertEqual(result[
                    "d12_instrumented_tsan"]["status"], "FAIL")
                threaded_path = pathlib.Path(temporary) / result[
                    "d12_instrumented_tsan"]["result_artifact"][
                        "relative_path"]
                records = json.loads(threaded_path.read_text(
                    encoding="utf-8"))
                aborted_rows = [record for record in records
                                if record[0][3] == abort_mode and
                                record[0][13] == "row_digest"]
                if abort_mode == "threaded_cache":
                    self.assertEqual(len(aborted_rows), 20)
                    self.assertTrue(all(record[2] is None and
                                        record[4] == "THREADED_CACHE_RACE"
                                        for record in aborted_rows))
                else:
                    concurrency_path = pathlib.Path(temporary) / result[
                        "d12_cache_disabled_concurrency"]["result_artifact"][
                            "relative_path"]
                    concurrency = json.loads(concurrency_path.read_text(
                        encoding="utf-8"))
                    self.assertEqual(len(concurrency), 20)
                    self.assertTrue(all(record[2]["kind"] ==
                                        "d12_concurrency_abort_v1" and
                                        record[4] == "CACHE_DISABLED_RACE"
                                        for record in concurrency))
                self.assertFalse(context["threaded_tsan_row_digest_sha256"]
                                 is None)

            expected = {}
            for mode in ("cache_disabled", "threaded_cache"):
                for round_index in range(20):
                    prefix = (
                        "anchored-row-d12-v1/workers/{}/content/level-2/"
                        "workers-1/round-{:02d}/worker-0".format(
                            mode, round_index))
                    expected[prefix + "-provider.b2rowv1"] = (
                        6, provider_digest)
                    expected[prefix + "-representation.json"] = (
                        48, representation_digest)
            inventory = MODULE.D12WorkerInventoryVerifier.__new__(
                MODULE.D12WorkerInventoryVerifier)
            inventory.expected_paths = frozenset(expected)
            inventory.descriptors = MODULE.D12WorkerInventoryVerifier.\
                _bind_descriptor_inventory(expected, descriptors)
            abort_key = ["content", 2, "tsan", abort_mode, 1, 0, 0]
            self.assertTrue(inventory.require_absent_sidecars(abort_key))

    def test_d12_worker_race_discards_partial_tuple_and_continues_contract(self):
        instrumentation_digest = "a" * 64
        identities = [("content", 2, "cache_disabled", 1)]
        jobs = [{"content_identity_key": "content",
                 "mesh_path": "unused", "mutation": "none"}]
        references = {
            ("content", 2): {
                "provider": "b" * 64, "representation": "c" * 64,
                "provider_count": 1, "representation_count": 1}}
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            binary = root / "race-worker"
            binary.write_text(
                "#!/bin/sh\n"
                "printf 'D12WORK1partial-output'\n"
                "printf 'WARNING: ThreadSanitizer: data race\\n' >&2\n"
                "exit 66\n", encoding="utf-8")
            os.chmod(binary, 0o755)
            representation_binary = root / "representation-worker"
            representation_binary.write_text(
                "#!/bin/sh\ncat >/dev/null\nexit 0\n", encoding="utf-8")
            os.chmod(representation_binary, 0o755)
            request = root / "request.tsv"
            request.write_text("request\n", encoding="utf-8")
            references[("content", 2)]["request_path"] = str(request)
            output_root = root / "output"
            output_root.mkdir()
            expected_executables = {
                MODULE.sha256_file(binary),
                MODULE.sha256_file(representation_binary)}
            artifact = MODULE.D12ProcessObservationArtifact(
                output_root, expected_executables)
            try:
                with mock.patch.object(
                        MODULE.B2, "expected_threading_identities",
                        return_value=identities), mock.patch.object(
                            MODULE.B2, "valid_content_jobs",
                            return_value=jobs), mock.patch.object(
                            MODULE, "_d12_rebuild_environment",
                            return_value={
                                "LANG": "C", "LC_ALL": "C",
                                "SOURCE_DATE_EPOCH": "0", "TZ": "UTC",
                                "ZERO_AR_DATE": "1", "TMPDIR": "/tmp"}):
                    sidecars, aborts = MODULE.execute_d12_worker_streams(
                        binary, representation_binary, {}, output_root,
                        references, artifact,
                        instrumentation_digest, timeout_seconds=10)
                self.assertEqual(sidecars, [])
                self.assertEqual(aborts, {
                    ("content", 2, "cache_disabled", 1):
                        MODULE.sha256_bytes(
                            b"WARNING: ThreadSanitizer: data race\n")})
                self.assertFalse((output_root /
                                  "anchored-row-d12-v1/workers").exists())
                descriptor = artifact.finish(2)
                self.assertEqual(descriptor["record_count"], 2)
                finding_key = [
                    "content", 2, "tsan", "cache_disabled", 1,
                    None, None, None, None, None, None, None,
                    "sanitizer_summary", "tsan_finding_count"]
                report_path = output_root / \
                    MODULE._d12_tsan_report_relative_path(finding_key)
                self.assertEqual(
                    report_path.read_bytes(),
                    b"WARNING: ThreadSanitizer: data race\n")
            finally:
                artifact.close()

    def test_d12_worker_success_hashes_every_stream_and_hardlinks_equal_bytes(self):
        provider = b"provider-bytes"
        representation = b"[\"representation\"]"
        instrumentation_digest = "a" * 64
        identities = [("content", 2, "cache_disabled", 1)]
        jobs = [{"content_identity_key": "content",
                 "mesh_path": "unused", "mutation": "none"}]
        references = {
            ("content", 2): {
                "provider": MODULE.sha256_bytes(provider),
                "representation": MODULE.sha256_bytes(representation),
                "provider_count": 1, "representation_count": 1}}
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            provider_binary = root / "successful-provider-worker"
            provider_binary.write_text(
                "#!/usr/bin/python3\n"
                "import struct,sys\n"
                "p=b'provider-bytes'\n"
                "o=sys.stdout.buffer\n"
                "o.write(b'D12PROV1')\n"
                "for i in range(20):\n"
                " o.write(struct.pack('<IIQ',i,0,len(p)))\n"
                " o.write(p)\n",
                encoding="utf-8")
            os.chmod(provider_binary, 0o755)
            representation_binary = root / "successful-representation-worker"
            representation_binary.write_text(
                "#!/usr/bin/python3\n"
                "import struct,sys\n"
                "sys.stdin.buffer.read()\n"
                "r=b'[\\\"representation\\\"]'\n"
                "o=sys.stdout.buffer\n"
                "o.write(b'D12REPR1')\n"
                "for i in range(20):\n"
                " o.write(struct.pack('>QQQ',i,0,len(r)))\n"
                " o.write(r)\n",
                encoding="utf-8")
            os.chmod(representation_binary, 0o755)
            request = root / "request.tsv"
            request.write_text("request\n", encoding="utf-8")
            references[("content", 2)]["request_path"] = str(request)
            output_root = root / "output"
            output_root.mkdir()
            expected_executables = {
                MODULE.sha256_file(provider_binary),
                MODULE.sha256_file(representation_binary)}
            artifact = MODULE.D12ProcessObservationArtifact(
                output_root, expected_executables)
            try:
                with mock.patch.object(
                        MODULE.B2, "expected_threading_identities",
                        return_value=identities), mock.patch.object(
                            MODULE.B2, "valid_content_jobs",
                            return_value=jobs), mock.patch.object(
                            MODULE, "_d12_rebuild_environment",
                            return_value={
                                "LANG": "C", "LC_ALL": "C",
                                "SOURCE_DATE_EPOCH": "0", "TZ": "UTC",
                                "ZERO_AR_DATE": "1", "TMPDIR": "/tmp"}):
                    sidecars, aborts = MODULE.execute_d12_worker_streams(
                        provider_binary, representation_binary, {},
                        output_root, references, artifact,
                        instrumentation_digest, timeout_seconds=10)
                self.assertEqual(aborts, {})
                self.assertEqual(len(sidecars), 40)
                provider_inodes = set()
                representation_inodes = set()
                for descriptor in sidecars:
                    path = output_root / descriptor["relative_path"]
                    self.assertEqual(
                        MODULE.sha256_file(path), descriptor["sha256"])
                    if path.suffix == ".b2rowv1":
                        provider_inodes.add(path.stat().st_ino)
                    else:
                        representation_inodes.add(path.stat().st_ino)
                self.assertEqual(len(provider_inodes), 1)
                self.assertEqual(len(representation_inodes), 1)
                descriptor = artifact.finish(2)
                process_records = json.loads(
                    (output_root / descriptor["relative_path"]).read_text(
                        encoding="utf-8"))
                self.assertEqual(
                    {record[2]["executable_sha256"]
                     for record in process_records},
                    {MODULE.sha256_file(provider_binary),
                     MODULE.sha256_file(representation_binary)})
            finally:
                artifact.close()

    def test_d12_cross_record_statistics_are_recomputed(self):
        validator = MODULE.D12CrossRecordValidator()
        for repeat in range(15):
            key = ["content", 2, "release", "cache_disabled", None,
                   None, None, "measured", repeat, None, None, None, None,
                   "preparation_duration_ns"]
            validator.add("d12_preparation_cost", [
                key, "PASS", {"kind": "d12_duration_valid_v1",
                               "duration_ns": repeat}, None, None])
        median_key = ["content", 2, "release", "cache_disabled", None,
                      None, None, None, None, None, None, None, None,
                      "preparation_median_ns"]
        validator.add("d12_preparation_cost", [
            median_key, "PASS", {"kind": "d12_duration_valid_v1",
                                  "duration_ns": 7}, None, None])
        baseline_key = ["content", 2, "release", "cache_disabled", None,
                        None, None, None, None, None, None, None,
                        "pre_refiner_baseline", "rss_bytes"]
        validator.add("d12_peak_rss", [
            baseline_key, "PASS", {"kind": "d12_rss_valid_v1",
                                    "baseline_rss_bytes": 10,
                                    "observed_rss_bytes": 10,
                                    "rss_delta_bytes": 0}, None, None])
        self.assertTrue(validator.finish())

        null_validator = MODULE.D12CrossRecordValidator()
        row_key = ["content", 2, "tsan", "threaded_cache", 1, 0, 0,
                   None, None, None, None, None, "thread_result",
                   "row_digest"]
        null_validator.add("d12_instrumented_tsan", [
            row_key, "FAIL", None, None, "THREADED_CACHE_RACE"])
        with self.assertRaises(MODULE.QualificationError):
            null_validator.finish()
        summary_key = copy.deepcopy(row_key)
        summary_key[5] = None
        summary_key[6] = None
        summary_key[12] = "sanitizer_summary"
        summary_key[13] = "tsan_finding_count"
        null_validator.add("d12_instrumented_tsan", [
            summary_key, "FAIL",
            {"sanitizer_abort": True,
             "sanitizer_report_sha256": "a" * 64}, None,
            "THREADED_CACHE_RACE"])
        self.assertTrue(null_validator.finish())

        serial_context = MODULE.D12SerialContextVerifier().finish()
        self.assertEqual(serial_context["tuple_count"], 588)
        self.assertEqual(
            serial_context["all_tuple_keys_sha256"],
            "0f978320bc6e1e9e6c8f016040098dc5946e1101a863e6431eb6d4dc8c8ac1de")
        changed = MODULE.D12CrossRecordValidator()
        for repeat in range(15):
            key = ["content", 2, "release", "cache_disabled", None,
                   None, None, "measured", repeat, None, None, None, None,
                   "preparation_duration_ns"]
            changed.add("d12_preparation_cost", [
                key, "PASS", {"kind": "d12_duration_valid_v1",
                               "duration_ns": repeat}, None, None])
        changed.add("d12_preparation_cost", [
            median_key, "PASS", {"kind": "d12_duration_valid_v1",
                                  "duration_ns": 8}, None, None])
        with self.assertRaises(MODULE.QualificationError):
            changed.finish()

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

    def test_closed_d12_envelope_is_imported_without_relabeling_platform(self):
        envelope = MODULE._d12_envelope_contract_fixture()
        head = envelope["git"]["head"]
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "anchored-row-d12.json"
            raw = MODULE.jcs_bytes(envelope)
            path.write_bytes(raw)
            record, expectation = MODULE.inspect_d12_evidence(path, head)
            self.assertEqual(record, {
                "availability": MODULE.availability(
                    "PRESENT", MODULE.sha256_bytes(raw)),
                "execution_state": "UNQUALIFIED_PLATFORM",
                "exact_head": head,
                "physical_fingerprint_sha256": MODULE.sha256_bytes(
                    MODULE.jcs_bytes(envelope["platform"][
                        "observed_fingerprint"])),
                "representation_work": "INCLUDED",
                "omission_blocker": None})
            self.assertIn("representation workload included", expectation)
            executed, context = MODULE.load_d12_execution_evidence(
                path, head)
            self.assertEqual(set(executed), set(MODULE.D12_CRITERIA))
            self.assertEqual(context, envelope["serial_only_context"])
            for criterion in envelope["criteria"]:
                evidence = executed[criterion["criterion_id"]]
                imported = MODULE.executed_criterion_record(
                    criterion["criterion_id"], evidence)
                self.assertEqual(imported, criterion)

            mutated = copy.deepcopy(envelope)
            mutated["git"]["head"] = "b" * 40
            mutated["content_sha256"] = MODULE.ZERO_SHA256
            mutated["content_sha256"] = MODULE.sha256_bytes(
                MODULE.jcs_bytes(mutated))
            path.write_bytes(MODULE.jcs_bytes(mutated))
            record, _ = MODULE.inspect_d12_evidence(path, head)
            self.assertEqual(record["availability"]["state"], "INVALID")
            self.assertEqual(
                MODULE.load_d12_execution_evidence(path, head), ({}, None))
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

    def test_d12_numeric_raw_artifact_owns_exact_result_slices(self):
        case = {
            "candidate": "bfr", "content_identity_key": "content",
            "approximation_level": 2,
            "applicable_mode": "cache_disabled",
            "d12_primary_process_provenance": {
                "pid": 123, "start_utc": "2026-08-16T00:00:00Z",
                "end_utc": "2026-08-16T00:00:01Z",
                "exit_kind": "EXITED", "exit_code": 0, "signal": None,
                "argv_sha256": "a" * 64,
                "environment_sha256": "b" * 64,
                "stderr_sha256": "c" * 64}}
        report = {
            "d12_representation_workload_included": True,
            "preparation_ns": list(range(15)),
            "preparation_median_ns": 7,
            "d12_retained_payload_bytes_by_face": [100],
            "d12_rss_baseline_bytes": 1000,
            "rss_expected_named_sample_count": 1,
            "d12_rss_observations": [{
                "repeat_phase": "warmup", "repeat_index": 0,
                "face_id": None, "local_corner_or_none": None,
                "sample_id": None, "stage": "after_refiner",
                "rss_bytes": 1100}]}
        records = MODULE._d12_numeric_observations_for_case(
            case, report, "d" * 64)
        self.assertEqual(len(records), 19)
        with tempfile.TemporaryDirectory() as temporary:
            artifact = MODULE.D12ProcessObservationArtifact(temporary)
            try:
                for criterion_id, record in reversed(records):
                    artifact.add(criterion_id, record)
                descriptor = artifact.finish(expected_count=19)
                self.assertEqual(descriptor["record_count"], 19)
                raw_path = pathlib.Path(temporary) / descriptor[
                    "relative_path"]
                raw = raw_path.read_bytes()
                for criterion_id in (
                        "d12_preparation_cost", "d12_retained_payload",
                        "d12_peak_rss"):
                    for key, payload, binding in artifact.iter_bindings(
                            criterion_id):
                        observed = raw[binding["byte_offset"]:
                                       binding["byte_offset"] +
                                       binding["byte_length"]]
                        self.assertEqual(
                            MODULE.sha256_bytes(observed), binding["sha256"])
                        record = MODULE._d12_numeric_result_record(
                            criterion_id, key, payload, binding,
                            "UNQUALIFIED_PLATFORM")
                        self.assertEqual(record[1:2] + record[4:],
                                         ["INCOMPLETE",
                                          "D12_PLATFORM_UNQUALIFIED"])
            finally:
                artifact.close()

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

    def test_candidate_observation_timeout_precedes_blocking_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = pathlib.Path(temporary) / "stalled-candidate"
            binary.write_text(
                "#!/bin/sh\n/bin/sleep 5\n", encoding="utf-8")
            os.chmod(binary, 0o755)
            started = time.monotonic()
            with self.assertRaises(MODULE.QualificationError):
                list(MODULE.iter_candidate_observations(
                    binary, "representation_structure",
                    ["position 1 0 0 3ff0000000000000\n"], 1,
                    timeout_seconds=0.1))
            self.assertLess(time.monotonic() - started, 2.0)

    def test_candidate_cpp_has_observable_round_points_and_executes(self):
        source = ROOT / "experiments/anchored_row_qualification/candidate.cpp"
        text = source.read_text(encoding="utf-8")
        evaluator = (ROOT / "experiments/anchored_row_qualification/"
                     "anchored_row_evaluator.hpp").read_text(encoding="utf-8")
        self.assertIn("#pragma STDC FENV_ACCESS ON", text)
        self.assertIn("volatile double", evaluator)
        self.assertNotIn("std::fma", text + evaluator)
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
            d12_request = (
                "content\t2\t0\t-1\tsample\tposition\t0\t"
                "3ff0000000000000\t3ff0000000000000\t"
                "4000000000000000\t4008000000000000\n")
            d12 = subprocess.run(
                [str(binary), "--d12-representation-stream", "1"],
                input=d12_request.encode("ascii"), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            self.assertEqual(d12.returncode, 0,
                             d12.stderr.decode("utf-8", errors="replace"))
            self.assertEqual(d12.stdout[:8], b"D12REPR1")
            offset = 8
            reference = None
            for round_index in range(20):
                observed_round, worker, length = struct.unpack(
                    ">QQQ", d12.stdout[offset:offset + 24])
                offset += 24
                payload = d12.stdout[offset:offset + length]
                offset += length
                self.assertEqual((observed_round, worker), (round_index, 0))
                self.assertEqual(payload, reference if reference is not None
                                 else payload)
                reference = payload
            self.assertEqual(offset, len(d12.stdout))
            records = json.loads(reference)
            self.assertEqual(len(records), 8)
            self.assertEqual([record[6] for record in records], [
                "fixture_x", "fixture_y", "fixture_z", "negative_2p20",
                "negative_one", "positive_2p20", "positive_one",
                "positive_zero"])
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
            one_row = audit_input.splitlines()[0] + "\n"
            for criterion_id, expected_count, expected_kind in (
                    ("representation_structure", 3,
                     "candidate_structure_observation_v1"),
                    ("constant_field_bits", 45,
                     "candidate_binary64_observation_v1"),
                    ("relabel_exact_effective_coefficients", 6,
                     "candidate_dyadic_vector_observation_v1"),
                    ("regular_analytic_exact_rows", 3,
                     "candidate_dyadic_vector_observation_v1")):
                observations = list(MODULE.iter_candidate_observations(
                    binary, criterion_id, [one_row], expected_count))
                self.assertEqual(len(observations), expected_count)
                self.assertTrue(all(item["kind"] == expected_kind
                                    for item in observations))
                self.assertTrue(all(not ({"outcome", "target", "reason",
                                         "maximum", "digest"} & set(item))
                                    for item in observations))
            emitted_request = (
                "x position 1 "
                "3fd0000000000000,3fe0000000000000,3fd0000000000000 "
                "0000000000000000,3ff0000000000000,"
                "0000000000000000\n")
            emitted = list(MODULE.iter_candidate_observations(
                binary, "emitted_direct_geometry_d10",
                [emitted_request], 1))
            self.assertEqual(emitted, [{
                "axis": "x",
                "kind": "candidate_emitted_geometry_observation_v1",
                "observed_bits": "3fe0000000000000",
            }])
            regular_emitted = list(MODULE.iter_candidate_observations(
                binary, "regular_analytic_emitted_geometry",
                [emitted_request], 1))
            self.assertEqual(regular_emitted, emitted)
            integrand_fixture = {
                "vertices": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                             (0.0, 1.0, 0.0)]}
            integrand_group = {
                "position": {"row_kind": "position",
                             "source_ids": [0, 1, 2],
                             "coefficients": [1.0, 0.0, 0.0]},
                "du": {"row_kind": "du", "source_ids": [0, 1, 2],
                       "coefficients": [0.0, 1.0, 0.0]},
                "dv": {"row_kind": "dv", "source_ids": [0, 1, 2],
                       "coefficients": [0.0, 0.0, 1.0]},
            }
            integrand_request = MODULE._candidate_integrand_request(
                integrand_group, integrand_fixture, 0,
                "emitted_binary64")
            integrand = list(MODULE.iter_candidate_observations(
                binary, "regular_analytic_area_integrand",
                [integrand_request], 1))
            self.assertEqual(integrand, [{
                "kind": "candidate_emitted_integrand_observation_v1",
                "observed_bits": "3ff0000000000000",
                "view": "emitted_binary64",
            }])
            generated_request = MODULE.candidate_emitted_geometry_line(
                {"row_kind": "position", "source_ids": [0, 1, 2],
                 "coefficients": [0.25, 0.5, 0.25]}, 1,
                {"vertices": [(0.0, 0.0, 0.0),
                              (1.0, 0.0, 0.0),
                              (0.0, 1.0, 0.0)]}, "x")
            self.assertEqual(generated_request, emitted_request)
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
            component_observation_counts = {
                "anchor_sensitivity_exact_coeff": 3,
                "anchor_sensitivity_exact_geometry": 9,
                "anchor_sensitivity_emitted_geometry": 9,
                "binary64_basis_probe_diagnostic": 27,
                "binary64_direct_geometry_fidelity": 27,
                "relabel_emitted_geometry_fidelity": 18,
                "stabilization_6_7_exact_coeff": 3,
                "stabilization_6_7_exact_geometry": 9,
                "stabilization_6_7_emitted_geometry": 9,
            }
            for criterion_id, count in component_observation_counts.items():
                values = list(MODULE.iter_candidate_observations(
                    binary, criterion_id, [component_input], count))
                self.assertEqual(len(values), count)
                self.assertTrue(all(not ({
                    "outcome", "target", "reason", "maximum", "digest"} &
                    set(value)) for value in values))
            cache_request = (
                "position 3 0,1,2 0,1,2 "
                "3fd0000000000000,3fe0000000000000,3fd0000000000000 "
                "0,1,2 "
                "3fd0000000000000,3fe0000000000000,3fd0000000000000\n")
            cache_values = list(MODULE.iter_candidate_observations(
                binary, "cache_mode_bit_identity", [cache_request], 3))
            self.assertEqual(len(cache_values), 3)
            self.assertTrue(all(value["cache_disabled_entries"] ==
                                value["serial_cache_entries"]
                                for value in cache_values))
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

    def test_boundary_source_freezes_mpfr_and_reports_oracle_unavailable(self):
        source = (ROOT / "experiments/anchored_row_qualification/"
                 "exact_dyadic_boundary.cpp").read_text(encoding="utf-8")
        for anchor in ("MPFR_RNDD", "MPFR_RNDU", "mpfr_set_z_2exp",
                       "kPrecision = 544", "ORACLE_EXECUTION_UNAVAILABLE",
                       "uniform_success_substituted_for_primary\\\":false",
                       "regular_integrand_stream", "interval_square_root"):
            self.assertIn(anchor, source)
        for forbidden in MODULE.B2.FORBIDDEN_ORACLE_TOKENS:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
