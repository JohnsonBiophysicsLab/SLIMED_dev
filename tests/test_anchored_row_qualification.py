import copy
import gzip
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
        self.assertFalse(value["independent_primary_oracle_available"])
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
            "029816125619f58f99464e8055170ffa12e957e3")

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

    def test_all_3501_literal_mutations_have_executable_rejections(self):
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
            records.append([["raw", index], "PASS", {
                "raw_invariant_state": "FAIL" if index < 124 else "PASS"},
                None, None])
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
            root = pathlib.Path(temporary)
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
            binaries = {
                "row_provider": {"availability": present},
                "representation_candidate": {"availability": present},
                "exact_dyadic_boundary": {"availability": present},
                "independent_oracle": {"availability": unavailable},
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
                "matrix": {"unexpected_paths": evidence[
                    "complete_artifact_inventory"]["unexpected_paths"]},
            }
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
            one_row = audit_input.splitlines()[0] + "\n"
            for criterion_id, expected_count, expected_kind in (
                    ("representation_structure", 3,
                     "candidate_structure_observation_v1"),
                    ("constant_field_bits", 45,
                     "candidate_binary64_observation_v1"),
                    ("relabel_exact_effective_coefficients", 6,
                     "candidate_dyadic_vector_observation_v1")):
                observations = list(MODULE.iter_candidate_observations(
                    binary, criterion_id, [one_row], expected_count))
                self.assertEqual(len(observations), expected_count)
                self.assertTrue(all(item["kind"] == expected_kind
                                    for item in observations))
                self.assertTrue(all(not ({"outcome", "target", "reason",
                                         "maximum", "digest"} & set(item))
                                    for item in observations))
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
