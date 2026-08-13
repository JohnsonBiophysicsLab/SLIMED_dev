#!/usr/bin/env python3
"""Executable B2b result-contract vocabulary for anchored-row qualification.

This module contains no observations and performs no qualification work.  It
spells out the already approved 32-slot evidence contract so the report schema,
standalone sidecar validator, and mutation suite share one closed executable
description while the approved Markdown byte anchor remains independent.
"""

from __future__ import print_function

import copy


SHA256_PATTERN = "^[0-9a-f]{64}$"
BITS64_PATTERN = "^[0-9a-f]{16}$"
HEX_PATTERN = "^(0|[1-9a-f][0-9a-f]*)$"
UINT_PATTERN = "^(0|[1-9][0-9]*)$"
SINT_PATTERN = "^(0|-?[1-9][0-9]*)$"


def ref(name):
    return {"$ref": "#/$defs/{}".format(name)}


def closed(properties, required=None, **keywords):
    result = {
        "type": "object",
        "additionalProperties": False,
        "required": list(required if required is not None else properties),
        "properties": properties,
    }
    result.update(keywords)
    return result


def array(items=None, minimum=0, maximum=None):
    result = {"type": "array", "minItems": minimum}
    if items is not None:
        result["items"] = items
    if maximum is not None:
        result["maxItems"] = maximum
    return result


SHA256 = {"type": "string", "pattern": SHA256_PATTERN}
BITS64 = {"type": "string", "pattern": BITS64_PATTERN}
UINT64 = {"type": "integer", "minimum": 0,
          "maximum": 18446744073709551615}
SIGNED_INTEGER = {"type": "integer"}
NONEMPTY_STRING = {"type": "string", "minLength": 1}
SOURCE_IDS = array(SIGNED_INTEGER, minimum=1)


OBJECT_SCHEMAS = {
    "signed_dyadic_v1": closed({
        "kind": {"const": "signed_dyadic_v1"},
        "sign": {"enum": [-1, 0, 1]},
        "numerator_hex": {"type": "string", "pattern": HEX_PATTERN},
        "denominator_power": {"enum": [1074, 2148]},
    }),
    "absolute_dyadic_v1": closed({
        "kind": {"const": "absolute_dyadic_v1"},
        "numerator_hex": {"type": "string", "pattern": HEX_PATTERN},
        "denominator_power": {"enum": [1074, 2148]},
    }),
    "rational_v1": closed({
        "kind": {"const": "rational_v1"},
        "numerator": {"type": "string", "pattern": SINT_PATTERN},
        "denominator": {"type": "string", "pattern": UINT_PATTERN},
    }),
    "absolute_rational_v1": closed({
        "kind": {"const": "absolute_rational_v1"},
        "numerator": {"type": "string", "pattern": UINT_PATTERN},
        "denominator": {"type": "string", "pattern": UINT_PATTERN},
    }),
    "rational_over_sqrt_v1": closed({
        "kind": {"const": "rational_over_sqrt_v1"},
        "absolute_numerator": {"type": "string", "pattern": UINT_PATTERN},
        "absolute_denominator": {"type": "string", "pattern": UINT_PATTERN},
        "scale_squared_numerator": {"type": "string", "pattern": UINT_PATTERN},
        "scale_squared_denominator": {"type": "string", "pattern": UINT_PATTERN},
    }),
    "binary64_pair_v1": closed({
        "kind": {"const": "binary64_pair_v1"},
        "observed_bits": BITS64,
        "expected_bits": BITS64,
    }),
    "binary64_scalar_v1": closed({
        "kind": {"const": "binary64_scalar_v1"}, "bits": BITS64,
    }),
    "digest_pair_v1": closed({
        "kind": {"const": "digest_pair_v1"},
        "observed_sha256": SHA256, "expected_sha256": SHA256,
    }),
    "interval_rational_v1": closed({
        "kind": {"const": "interval_rational_v1"},
        "lower": ref("rational_v1"), "upper": ref("rational_v1"),
    }),
    "scalar_comparison_v1": closed({
        "kind": {"const": "scalar_comparison_v1"},
        "observed": {"oneOf": [ref("signed_dyadic_v1"), ref("rational_v1")]},
        "expected": {"oneOf": [ref("signed_dyadic_v1"), ref("rational_v1")]},
        "absolute_error": {"oneOf": [ref("absolute_dyadic_v1"),
                                      ref("absolute_rational_v1")]},
    }),
    "exact_zero_l1_target_v1": closed({
        "kind": {"const": "exact_zero_l1_target_v1"},
        "numerator": {"const": "0"}, "denominator": {"const": "1"},
    }),
    "absolute_rational_target_v1": closed({
        "kind": {"const": "absolute_rational_target_v1"},
        "numerator": {"const": "1"},
        "denominator": {"enum": ["200000", "2000000", "400000",
                                  "80000", "40000", "8000"]},
    }),
}


OBJECT_SCHEMAS.update({
    "coefficient_vector_comparison_v1": closed({
        "kind": {"const": "coefficient_vector_comparison_v1"},
        "source_ids": SOURCE_IDS,
        "observed": array(ref("signed_dyadic_v1"), minimum=1),
        "expected": array(ref("signed_dyadic_v1"), minimum=1),
        "absolute_errors": array(ref("absolute_dyadic_v1"), minimum=1),
        "l1": ref("absolute_dyadic_v1"),
    }),
    "exact_coefficient_l1_v1": closed({
        "kind": {"const": "exact_coefficient_l1_v1"},
        "source_ids": SOURCE_IDS,
        "observed": array(ref("signed_dyadic_v1"), minimum=1),
        "expected": array(ref("signed_dyadic_v1"), minimum=1),
        "absolute_errors": array(ref("absolute_dyadic_v1"), minimum=1),
        "l1": ref("absolute_dyadic_v1"),
    }),
    "oracle_coefficient_l1_v1": closed({
        "kind": {"const": "oracle_coefficient_l1_v1"},
        "source_ids": SOURCE_IDS,
        "observed": array(ref("signed_dyadic_v1"), minimum=1),
        "oracle_intervals": array(ref("interval_rational_v1"), minimum=1),
        "absolute_error_uppers": array(ref("absolute_rational_v1"), minimum=1),
        "l1": ref("absolute_rational_v1"),
    }),
    "coefficient_interval_vector_v1": closed({
        "kind": {"const": "coefficient_interval_vector_v1"},
        "source_union_ids": SOURCE_IDS,
        "observed": array(ref("signed_dyadic_v1"), minimum=1),
        "analytic_intervals": array(ref("interval_rational_v1"), minimum=1),
        "absolute_error_uppers": array(ref("absolute_rational_v1"), minimum=1),
        "maximum_error_upper": ref("absolute_rational_v1"),
        "first_maximum_source_id": SIGNED_INTEGER,
    }),
    "normalized_interval_bound_v1": closed({
        "kind": {"const": "normalized_interval_bound_v1"},
        "difference_interval": ref("interval_rational_v1"),
        "distance_upper": ref("absolute_rational_v1"),
        "scale_squared_interval": ref("interval_rational_v1"),
        "scale_lower": ref("rational_v1"),
        "ideal_normalized": ref("rational_over_sqrt_v1"),
        "normalized_upper": ref("absolute_rational_v1"),
    }),
    "geometry_axis_v1": closed({
        "kind": {"const": "geometry_axis_v1"},
        "axis": {"enum": ["x", "y", "z"]},
        "view": {"enum": ["exact_effective", "emitted_binary64"]},
        "observed": {"oneOf": [ref("signed_dyadic_v1"), ref("rational_v1"),
                                ref("binary64_scalar_v1")]},
        "reference_interval": ref("interval_rational_v1"),
        "normalized_bound": ref("normalized_interval_bound_v1"),
    }),
    "integrand_exact_interval_v1": closed({
        "kind": {"const": "integrand_exact_interval_v1"},
        "view": {"const": "exact_effective"},
        "observed_interval": ref("interval_rational_v1"),
        "analytic_interval": ref("interval_rational_v1"),
        "absolute_error_upper": ref("absolute_rational_v1"),
    }),
    "integrand_emitted_interval_v1": closed({
        "kind": {"const": "integrand_emitted_interval_v1"},
        "view": {"const": "emitted_binary64"},
        "observed_bits": BITS64,
        "analytic_interval": ref("interval_rational_v1"),
        "absolute_error_upper": ref("absolute_rational_v1"),
    }),
    "emitted_interval_scalar_v1": closed({
        "kind": {"const": "emitted_interval_scalar_v1"},
        "observed_bits": BITS64,
        "analytic_interval": ref("interval_rational_v1"),
        "absolute_error_upper": ref("absolute_rational_v1"),
    }),
    "basis_value_v1": closed({
        "kind": {"const": "basis_value_v1"},
        "emitted_basis_bits": BITS64,
        "exact_effective": ref("signed_dyadic_v1"),
        "source_error": ref("absolute_dyadic_v1"),
        "group_l1": ref("absolute_dyadic_v1"),
    }),
    "row_signature_pair_v1": closed({
        "kind": {"const": "row_signature_pair_v1"},
        "source_count": UINT64,
        "cache_disabled_sha256": SHA256, "serial_cache_sha256": SHA256,
    }),
})


AVAILABILITY_STATE = {"enum": ["PRESENT", "MISSING", "UNAVAILABLE", "INVALID"]}
NULLABLE_SHA256 = {"type": ["string", "null"], "pattern": SHA256_PATTERN}
NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_UINT64 = {"type": ["integer", "null"], "minimum": 0,
                   "maximum": 18446744073709551615}
OBJECT_SCHEMAS.update({
    "availability": closed({
        "state": AVAILABILITY_STATE, "sha256": NULLABLE_SHA256,
        "reason_code": NULLABLE_STRING,
    }),
    "binding_value_v1": closed({
        "kind": {"const": "binding_value_v1"},
        "git_start": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
        "git_end": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
        "worktree_start_clean": {"type": "boolean"},
        "worktree_end_clean": {"type": "boolean"},
        "validator_sha256": SHA256,
        "row_provider_availability": AVAILABILITY_STATE,
        "row_provider_sha256": NULLABLE_SHA256,
        "representation_availability": AVAILABILITY_STATE,
        "representation_sha256": NULLABLE_SHA256,
        "exact_boundary_availability": AVAILABILITY_STATE,
        "exact_boundary_sha256": NULLABLE_SHA256,
        "independent_oracle_availability": AVAILABILITY_STATE,
        "independent_oracle_sha256": NULLABLE_SHA256,
        "oracle_independence_audit": {"enum": ["PASS", "INCOMPLETE", "FAIL"]},
        "manifest_file_sha256": SHA256,
        "manifest_contract_sha256": SHA256,
        "gmp_identity": {"const": "gmp-6.3.0"},
        "mpfr_identity": {"const": "mpfr-4.2.2"},
        "opensubdiv_identity": {"const": "opensubdiv-3.7.0"},
        "provenance_complete": {"type": "boolean"},
    }),
    "artifact_value_v1": closed({
        "kind": {"const": "artifact_value_v1"},
        "expected_slot_ordinal": UINT64, "relative_path": NONEMPTY_STRING,
        "availability": ref("availability"), "compressed_sha256": SHA256,
        "decompressed_json_sha256": SHA256,
        "canonical_b2rowv1_sha256": SHA256,
        "expected_identity_matches": {"type": "boolean"},
    }),
    "artifact_slot_target_v1": closed({
        "kind": {"const": "artifact_slot_target_v1"},
        "expected_slot_ordinal": UINT64, "content_id": NONEMPTY_STRING,
        "candidate": {"enum": ["bfr", "far"]}, "level": {"type": "integer",
        "minimum": 2, "maximum": 8}, "cache_mode": NONEMPTY_STRING,
        "compressed_sha256": SHA256, "decompressed_json_sha256": SHA256,
        "canonical_b2rowv1_sha256": SHA256,
    }),
    "result_ledger_artifact": closed({
        "availability": ref("availability"), "relative_path": NULLABLE_STRING,
        "byte_length": NULLABLE_UINT64, "record_count": NULLABLE_UINT64,
    }),
    "d12_sidecar_descriptor": closed({
        "availability": ref("availability"), "relative_path": NULLABLE_STRING,
        "byte_length": NULLABLE_UINT64, "record_count": NULLABLE_UINT64,
        "sha256": NULLABLE_SHA256,
    }),
    "unexpected_paths_target_v1": closed({
        "kind": {"const": "unexpected_paths_target_v1"},
        "sidecar": ref("d12_sidecar_descriptor"),
        "required_record_count": {"const": 0},
    }),
    "maximum_witness": closed({
        "cell_key": {"type": "array"},
        "result_record": {"type": "array", "minItems": 5, "maxItems": 5},
        "leaf_index": UINT64, "merkle_siblings": array(SHA256),
        "maximum_exact": {"type": "object"},
        "maximum_binary64_bits": BITS64,
    }),
    "row_target": closed({
        "position": ref("absolute_rational_target_v1"),
        "first_derivative": ref("absolute_rational_target_v1"),
        "second_derivative": ref("absolute_rational_target_v1"),
    }),
})


PLATFORM_STATE = {"enum": ["QUALIFIED_PLATFORM", "UNQUALIFIED_PLATFORM"]}
RAW_OBSERVATION = ref("d12_raw_observation_binding_v1")
SIDE_CAR = ref("d12_sidecar_descriptor")
OBJECT_SCHEMAS.update({
    "d12_raw_observation_binding_v1": closed({
        "kind": {"const": "d12_raw_observation_binding_v1"},
        "availability": ref("availability"), "relative_path": NULLABLE_STRING,
        "byte_offset": UINT64, "byte_length": UINT64, "sha256": SHA256,
    }),
    "d12_duration_target_v1": closed({
        "kind": {"const": "d12_duration_target_v1"},
        "median_ns": {"const": 1000000000}, "single_ns": {"const": 10000000000},
    }),
    "d12_payload_target_v1": closed({
        "kind": {"const": "d12_payload_target_v1"},
        "maximum_bytes": {"const": 131072},
    }),
    "d12_rss_target_v1": closed({
        "kind": {"const": "d12_rss_target_v1"},
        "maximum_delta_bytes": {"const": 67108864},
    }),
    "d12_duration_valid_v1": closed({
        "kind": {"const": "d12_duration_valid_v1"},
        "quantity": {"enum": ["preparation_duration_ns", "preparation_median_ns"]},
        "duration_ns": UINT64, "platform_state": PLATFORM_STATE,
        "raw_observation": RAW_OBSERVATION,
    }),
    "d12_duration_invalid_v1": closed({
        "kind": {"const": "d12_duration_invalid_v1"},
        "quantity": {"enum": ["preparation_duration_ns", "preparation_median_ns"]},
        "duration_ns": {"const": None},
        "invalid_state": {"enum": ["NONFINITE", "NEGATIVE", "TIMEOUT", "SIGNAL",
                                   "ALLOCATION_FAILURE", "PROCESS_FAILURE"]},
        "platform_state": PLATFORM_STATE, "raw_observation": RAW_OBSERVATION,
    }),
    "d12_payload_valid_v1": closed({
        "kind": {"const": "d12_payload_valid_v1"}, "payload_bytes": UINT64,
        "face_id": UINT64, "platform_state": PLATFORM_STATE,
        "raw_observation": RAW_OBSERVATION,
    }),
    "d12_payload_invalid_v1": closed({
        "kind": {"const": "d12_payload_invalid_v1"}, "payload_bytes": {"const": None},
        "face_id": NULLABLE_UINT64,
        "invalid_state": {"enum": ["MISSING_COUNT", "NON_SIX_ROW_SAMPLE",
                                   "ARITHMETIC_OVERFLOW", "PROCESS_FAILURE"]},
        "platform_state": PLATFORM_STATE, "raw_observation": RAW_OBSERVATION,
    }),
    "d12_rss_valid_v1": closed({
        "kind": {"const": "d12_rss_valid_v1"}, "baseline_rss_bytes": UINT64,
        "observed_rss_bytes": UINT64, "rss_delta_bytes": UINT64,
        "stage": NONEMPTY_STRING, "platform_state": PLATFORM_STATE,
        "raw_observation": RAW_OBSERVATION,
    }),
    "d12_rss_invalid_v1": closed({
        "kind": {"const": "d12_rss_invalid_v1"},
        "baseline_rss_bytes": NULLABLE_UINT64, "observed_rss_bytes": {"const": None},
        "rss_delta_bytes": {"const": None}, "stage": NONEMPTY_STRING,
        "invalid_state": {"enum": ["SAMPLE_MISSING", "API_FAILURE",
                                   "PROCESS_FAILURE"]},
        "platform_state": PLATFORM_STATE, "raw_observation": RAW_OBSERVATION,
    }),
    "d12_output_reference_target_v1": closed({
        "kind": {"const": "d12_output_reference_target_v1"},
        "provider_expected_sha256": SHA256,
        "representation_expected_sha256": SHA256,
    }),
})


def d12_row_value(name, abort=False):
    properties = {
        "kind": {"const": name}, "provider_sidecar": SIDE_CAR,
        "representation_sidecar": SIDE_CAR,
        "provider_observed_sha256": NULLABLE_SHA256,
        "provider_expected_sha256": SHA256,
        "representation_observed_sha256": NULLABLE_SHA256,
        "representation_expected_sha256": SHA256,
        "platform_state": PLATFORM_STATE,
    }
    if abort:
        properties["tsan_finding_summary_key"] = {"type": "array"}
    return closed(properties)


OBJECT_SCHEMAS.update({
    "d12_concurrency_value_v1": d12_row_value("d12_concurrency_value_v1"),
    "d12_concurrency_abort_v1": d12_row_value("d12_concurrency_abort_v1", True),
    "d12_tsan_threaded_row_value_v1": d12_row_value(
        "d12_tsan_threaded_row_value_v1"),
    "d12_tsan_instrumentation_target_v1": closed({
        "kind": {"const": "d12_tsan_instrumentation_target_v1"},
        "instrumentation_complete": {"const": True},
        "expected_translation_units_sha256": SHA256,
    }),
    "d12_tsan_finding_target_v1": closed({
        "kind": {"const": "d12_tsan_finding_target_v1"},
        "finding_count": {"const": 0},
    }),
    "d12_tsan_instrumentation_summary_v1": closed({
        "kind": {"const": "d12_tsan_instrumentation_summary_v1"},
        "instrumentation_complete": {"type": "boolean"},
        "instrumented_translation_units_sha256": NULLABLE_SHA256,
        "expected_translation_units_sha256": SHA256,
        "platform_state": PLATFORM_STATE, "raw_observation": RAW_OBSERVATION,
    }),
    "d12_tsan_finding_summary_v1": closed({
        "kind": {"const": "d12_tsan_finding_summary_v1"},
        "finding_count": NULLABLE_UINT64, "sanitizer_abort": {"type": "boolean"},
        "sanitizer_report_sha256": NULLABLE_SHA256,
        "platform_state": PLATFORM_STATE, "raw_observation": RAW_OBSERVATION,
    }),
})


OBJECT_SCHEMAS.update({
    "d12_duration_raw_v1": closed({
        "kind": {"const": "d12_duration_raw_v1"},
        "state": {"enum": ["VALID_UINT64_NS", "NONFINITE", "NEGATIVE", "TIMEOUT",
                           "SIGNAL", "ALLOCATION_FAILURE", "PROCESS_FAILURE"]},
        "token": NULLABLE_STRING,
    }),
    "d12_payload_raw_v1": closed({
        "kind": {"const": "d12_payload_raw_v1"},
        "state": {"enum": ["VALID_UINT64_BYTES", "MISSING_COUNT",
                           "NON_SIX_ROW_SAMPLE", "ARITHMETIC_OVERFLOW",
                           "PROCESS_FAILURE"]}, "token": NULLABLE_STRING,
    }),
    "d12_rss_raw_v1": closed({
        "kind": {"const": "d12_rss_raw_v1"},
        "state": {"enum": ["VALID_UINT64_BYTES", "SAMPLE_MISSING", "API_FAILURE",
                           "PROCESS_FAILURE"]}, "baseline_token": NULLABLE_STRING,
        "observed_token": NULLABLE_STRING,
    }),
    "d12_tsan_instrumentation_raw_v1": closed({
        "kind": {"const": "d12_tsan_instrumentation_raw_v1"},
        "state": {"enum": ["COMPLETE", "INCOMPLETE"]},
        "instrumented_translation_units_sha256": NULLABLE_SHA256,
    }),
    "d12_tsan_finding_raw_v1": closed({
        "kind": {"const": "d12_tsan_finding_raw_v1"},
        "state": {"enum": ["COMPLETE", "SANITIZER_ABORT",
                           "EXECUTION_UNAVAILABLE"]},
        "finding_count_token": NULLABLE_STRING,
        "sanitizer_report_sha256": NULLABLE_SHA256,
    }),
    "d12_process_provenance_v1": closed({
        "kind": {"const": "d12_process_provenance_v1"},
        "process_tuple_sha256": SHA256, "executable_sha256": SHA256,
        "argv_sha256": SHA256, "environment_sha256": SHA256,
        "pid": NULLABLE_UINT64, "start_utc": NONEMPTY_STRING,
        "end_utc": NONEMPTY_STRING,
        "exit_kind": {"enum": ["EXITED", "SIGNALED", "TIMEOUT", "NOT_STARTED"]},
        "exit_code": {"type": ["integer", "null"]},
        "signal": {"type": ["integer", "null"]}, "stderr_sha256": SHA256,
    }),
})


OBJECT_SCHEMAS.update({
    "source_binding": closed({"path": NONEMPTY_STRING, "sha256": SHA256}),
    "d12_binary": closed({
        "availability": ref("availability"), "sha256": NULLABLE_SHA256,
        "compiler_command_sha256": NULLABLE_SHA256,
        "link_map_sha256": NULLABLE_SHA256,
        "dynamic_dependency_sha256": NULLABLE_SHA256,
        "source_inventory": array(ref("source_binding")),
    }),
    "d12_dependency": closed({
        "version": NONEMPTY_STRING, "archive_sha256": SHA256,
        "source_identity": NONEMPTY_STRING, "build_root_provenance_sha256": SHA256,
        "install_provenance_sha256": SHA256, "link_provenance_sha256": SHA256,
        "installed_library_sha256": SHA256,
    }),
    "d12_build_profile": closed({
        "compiler_path": NONEMPTY_STRING, "compiler_version": NONEMPTY_STRING,
        "flags": array(NONEMPTY_STRING), "sdk_path": NONEMPTY_STRING,
        "sdk_version": NONEMPTY_STRING, "cmake_path": NONEMPTY_STRING,
        "cmake_version": NONEMPTY_STRING, "make_path": NONEMPTY_STRING,
        "make_version": NONEMPTY_STRING, "compile_commands": array(array(NONEMPTY_STRING)),
        "link_commands": array(array(NONEMPTY_STRING)),
    }),
    "d12_git": closed({
        "head": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
        "head_query_ok": {"const": True}, "worktree_clean": {"const": True},
    }),
    "d12_platform": closed({
        "platform_state": PLATFORM_STATE,
        "expected_fingerprint": closed({
            "architecture": NONEMPTY_STRING, "chip": NONEMPTY_STRING,
            "hw_logicalcpu": UINT64, "hw_memsize_bytes": UINT64,
            "hw_model": NONEMPTY_STRING, "hw_ncpu": UINT64,
            "hw_perflevel0_logicalcpu": UINT64,
            "hw_perflevel0_physicalcpu": UINT64,
            "hw_perflevel1_logicalcpu": UINT64,
            "hw_perflevel1_physicalcpu": UINT64,
            "hw_physicalcpu": UINT64, "kern_hv_vmm_present": UINT64,
            "macos_build": NONEMPTY_STRING, "macos_version": NONEMPTY_STRING,
        }),
        "observed_fingerprint": closed({
            "architecture": NONEMPTY_STRING, "chip": NONEMPTY_STRING,
            "hw_logicalcpu": UINT64, "hw_memsize_bytes": UINT64,
            "hw_model": NONEMPTY_STRING, "hw_ncpu": UINT64,
            "hw_perflevel0_logicalcpu": UINT64,
            "hw_perflevel0_physicalcpu": UINT64,
            "hw_perflevel1_logicalcpu": UINT64,
            "hw_perflevel1_physicalcpu": UINT64,
            "hw_physicalcpu": UINT64, "kern_hv_vmm_present": UINT64,
            "macos_build": NONEMPTY_STRING, "macos_version": NONEMPTY_STRING,
        }),
        "field_mismatches": array(NONEMPTY_STRING),
        "compiler_identity": NONEMPTY_STRING, "github_hosted": {"type": "boolean"},
        "virtualization_observation": closed({
            "kern_hv_vmm_present": UINT64,
            "shared_host_evidence": {"type": "boolean"},
        }),
        "power_thermal_observations": array(closed({
            "boundary": NONEMPTY_STRING,
            "power_api": NONEMPTY_STRING, "power_query_ok": {"type": "boolean"},
            "power_value": NONEMPTY_STRING,
            "thermal_api": NONEMPTY_STRING,
            "thermal_query_ok": {"type": "boolean"},
            "thermal_value": NONEMPTY_STRING,
        })),
    }),
    "d12_workload": closed({
        "workload_id": {"const": "anchored-difference-v1-d12-workload-v1"},
        "construction_and_evaluation_included": {"const": True},
        "input_ids": {"const": ["fixture_x", "fixture_y", "fixture_z",
                                "positive_zero", "positive_one", "negative_one",
                                "positive_2p20", "negative_2p20"]},
        "provider_serial_reference": SIDE_CAR,
        "representation_serial_reference": SIDE_CAR,
        "process_observation_sidecar": SIDE_CAR,
        "sidecars": array(SIDE_CAR),
    }),
    "serial_only_context": closed({
        "tuple_count": {"const": 588}, "all_tuple_keys_sha256": SHA256,
        "cache_disabled_concurrency_cell_count": {"const": 13720},
        "cache_disabled_concurrency_ledger_sha256": SHA256,
        "cache_disabled_concurrency_pass": {"type": "boolean"},
        "cache_disabled_tsan_summary_cell_count": {"const": 588},
        "cache_disabled_tsan_summary_sha256": SHA256,
        "cache_disabled_tsan_pass": {"type": "boolean"},
        "threaded_tsan_summary_cell_count": {"const": 588},
        "threaded_tsan_summary_sha256": SHA256,
        "threaded_tsan_row_digest_cell_count": {"const": 13720},
        "threaded_tsan_row_digest_sha256": SHA256,
        "all_tsan_cell_count": {"const": 14896},
        "all_tsan_result_ledger_sha256": SHA256,
        "failure_records": array({"type": "array", "minItems": 2, "maxItems": 2}),
        "failure_records_sha256": SHA256,
    }),
    "d12_artifact_binding": closed({
        "availability": ref("availability"),
        "execution_state": {"enum": ["QUALIFIED_PLATFORM", "UNQUALIFIED_PLATFORM",
                                     "OMITTED_AFTER_CANDIDATE_FAILURE",
                                     "OMITTED_AFTER_INFRASTRUCTURE_FAILURE"]},
        "exact_head": {"type": ["string", "null"], "pattern": "^[0-9a-f]{40}$"},
        "physical_fingerprint_sha256": NULLABLE_SHA256,
        "representation_work": {"enum": ["INCLUDED", "NOT_INCLUDED", "UNAVAILABLE"]},
        "omission_blocker": NULLABLE_STRING,
    }),
    "anchored_row_representation_d12": closed({
        "schema_id": {"const": "anchored-row-representation-d12-v1"},
        "content_sha256": SHA256,
        "candidate": {"const": "anchored_difference_rows_v1"},
        "git": ref("d12_git"),
        "binaries": closed({
            "provider_release": ref("d12_binary"),
            "provider_tsan": ref("d12_binary"),
            "representation_release": ref("d12_binary"),
            "representation_tsan": ref("d12_binary"),
        }),
        "dependencies": closed({
            "gmp": {"allOf": [ref("d12_dependency"), {
                "properties": {
                    "version": {"const": "6.3.0"},
                    "archive_sha256": {"const":
                        "a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898"},
                }}]},
            "mpfr": {"allOf": [ref("d12_dependency"), {
                "properties": {
                    "version": {"const": "4.2.2"},
                    "archive_sha256": {"const":
                        "b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01"},
                }}]},
            "opensubdiv": {"allOf": [ref("d12_dependency"), {
                "properties": {
                    "version": {"const": "3.7.0"},
                    "archive_sha256": {"const":
                        "f843eb49daf20264007d807cbc64516a1fed9cdb1149aaf84ff47691d97491f9"},
                }}]},
        }),
        "build_profiles": closed({
            "release": ref("d12_build_profile"),
            "tsan": ref("d12_build_profile"),
        }),
        "platform": ref("d12_platform"), "authority": ref("authority"),
        "workload": ref("d12_workload"),
        "criteria": {"type": "array", "minItems": 5, "maxItems": 5,
                     "prefixItems": [ref("criterion_27"),
                                     ref("criterion_28"),
                                     ref("criterion_29"),
                                     ref("criterion_30"),
                                     ref("criterion_31")],
                     "items": False},
        "serial_only_context": ref("serial_only_context"),
    }),
})


OBJECT_SCHEMAS.update({
    "structure_present_v1": closed({
        "kind": {"const": "structure_present_v1"},
        "anchor_id": {"enum": ["v0", "v1", "v2"]},
        "anchor_present": {"const": True},
        "canonical_source_ids": SOURCE_IDS,
        "provider_coefficient_bits": array(BITS64, minimum=1),
        "provider_row_sha256": SHA256,
        "effective_coefficients": array(ref("signed_dyadic_v1"), minimum=1),
        "observed_sum": ref("signed_dyadic_v1"),
        "expected_sum": ref("signed_dyadic_v1"),
        "source_count": UINT64,
    }),
    "structure_missing_anchor_v1": closed({
        "kind": {"const": "structure_missing_anchor_v1"},
        "anchor_id": {"enum": ["v0", "v1", "v2"]},
        "anchor_present": {"const": False},
        "canonical_source_ids": SOURCE_IDS,
        "provider_coefficient_bits": array(BITS64, minimum=1),
        "provider_row_sha256": SHA256,
        "missing_anchor_source_id": SIGNED_INTEGER,
        "effective_coefficients": {"const": None},
        "observed_sum": {"const": None},
        "expected_sum": ref("signed_dyadic_v1"),
        "source_count": UINT64,
    }),
    "raw_d9a_value_v1": closed({
        "kind": {"const": "raw_d9a_value_v1"},
        "case_identity": {"type": "array", "minItems": 3, "maxItems": 3,
                          "prefixItems": [NONEMPTY_STRING, UINT64,
                                          NONEMPTY_STRING], "items": False},
        "raw_invariant_state": {"enum": ["PASS", "FAIL"]},
        "maximum_row_sum_residual": ref("absolute_dyadic_v1"),
        "failing_row_count": UINT64,
        "canonical_raw_rows_sha256": SHA256,
    }),
})


OBJECT_SCHEMAS.update({
    "candidate_structure_observation_v1": closed({
        "kind": {"const": "candidate_structure_observation_v1"},
        "canonical_source_ids": SOURCE_IDS,
        "provider_coefficient_bits": array(BITS64, minimum=1),
        "effective_coefficients": array(ref("signed_dyadic_v1"), minimum=1),
    }),
    "candidate_binary64_observation_v1": closed({
        "kind": {"const": "candidate_binary64_observation_v1"},
        "observed_bits": BITS64,
    }),
    "candidate_dyadic_vector_observation_v1": closed({
        "kind": {"const": "candidate_dyadic_vector_observation_v1"},
        "source_ids": SOURCE_IDS,
        "values": array(ref("signed_dyadic_v1"), minimum=1),
    }),
    "candidate_interval_vector_observation_v1": closed({
        "kind": {"const": "candidate_interval_vector_observation_v1"},
        "source_ids": SOURCE_IDS,
        "observed_intervals": array(ref("interval_rational_v1"), minimum=1),
    }),
    "candidate_exact_geometry_observation_v1": closed({
        "kind": {"const": "candidate_exact_geometry_observation_v1"},
        "axis": {"enum": ["x", "y", "z"]},
        "observed": {"oneOf": [ref("signed_dyadic_v1"), ref("rational_v1")]},
    }),
    "candidate_emitted_geometry_observation_v1": closed({
        "kind": {"const": "candidate_emitted_geometry_observation_v1"},
        "axis": {"enum": ["x", "y", "z"]}, "observed_bits": BITS64,
    }),
    "candidate_exact_integrand_observation_v1": closed({
        "kind": {"const": "candidate_exact_integrand_observation_v1"},
        "view": {"const": "exact_effective"},
        "observed_interval": ref("interval_rational_v1"),
    }),
    "candidate_emitted_integrand_observation_v1": closed({
        "kind": {"const": "candidate_emitted_integrand_observation_v1"},
        "view": {"const": "emitted_binary64"}, "observed_bits": BITS64,
    }),
    "candidate_basis_observation_v1": closed({
        "kind": {"const": "candidate_basis_observation_v1"},
        "emitted_basis_bits": BITS64,
    }),
    "candidate_row_signature_observation_v1": closed({
        "kind": {"const": "candidate_row_signature_observation_v1"},
        "cache_disabled_entries": array({}, minimum=1),
        "serial_cache_entries": array({}, minimum=1),
    }),
})


ORACLE_CERTIFICATION_FIELDS = (
    "eigenbasis", "parametric_map", "regular_support",
    "interval_intersection", "uniform_source_overlap", "vertex_limit",
    "tangent_projection", "uncertainty_bound", "midpoint_serialization",
)
OBJECT_SCHEMAS["oracle_certification_v1"] = closed(dict(
    [("kind", {"const": "oracle_certification_v1"})] +
    [(field, {"const": "CERTIFIED"})
     for field in ORACLE_CERTIFICATION_FIELDS]))
OBJECT_SCHEMAS["oracle_covered_value_v1"] = closed({
    "kind": {"const": "oracle_covered_value_v1"},
    "coverage": {"const": "COVERED"},
    "row_kind": {"enum": ["position", "du", "dv", "duu", "duv", "dvv"]},
    "source_ids": SOURCE_IDS,
    "primary_depth_intervals": array(array(ref("interval_rational_v1"),
                                             minimum=5, maximum=5), minimum=1),
    "uniform_depth_intervals": array(array(ref("interval_rational_v1"),
                                             minimum=5, maximum=5), minimum=1),
    "intersected_primary_intervals": array(ref("interval_rational_v1"),
                                             minimum=1),
    "first_isolating_depth": {"type": "integer", "minimum": 0, "maximum": 12},
    "first_regular_support_depth": {"type": "integer", "minimum": 0,
                                    "maximum": 26},
    "evaluated_depths": array({"type": "integer", "minimum": 0,
                               "maximum": 30}, minimum=5, maximum=5),
    "child_branches": array({"enum": ["T0", "T1", "T2", "Tc"]}),
    "certification": ref("oracle_certification_v1"),
})


D10_ORACLE_REASONS = (
    "ORACLE_INDEPENDENCE_AUDIT_FAILED", "MPFR_4_2_2_UNAVAILABLE",
    "MPFR_VERSION_MISMATCH", "DIRECTED_INTERVAL_PRIMITIVE_FAILED",
    "INTERVAL_BRANCH_ORDERING_UNCERTIFIED", "NO_ISOLATION_BY_DEPTH_12",
    "EIGENBASIS_CERTIFICATION_FAILED", "PARAMETRIC_MAP_CHECK_FAILED",
    "REGULAR_SUPPORT_NOT_REACHED_BY_DEPTH_30", "UNIFORM_CROSSCHECK_FAILED",
    "TANGENT_PROJECTION_CHECK_FAILED", "EMPTY_INTERVAL_INTERSECTION",
    "ORACLE_MIDPOINT_NONFINITE", "ORACLE_MIDPOINT_BINARY64_IMPORT_INEXACT",
    "NORMALIZATION_LENGTH_NONPOSITIVE", "ORACLE_UNCERTAINTY_BOUND_EXCEEDED",
    "ORACLE_SERIALIZATION_BOUND_EXCEEDED",
)
ORACLE_INFRASTRUCTURE_REASONS = (
    "ORACLE_REQUEST_LEDGER_UNAVAILABLE", "ORACLE_REQUEST_LEDGER_INVALID",
    "ORACLE_EXECUTION_UNAVAILABLE", "ORACLE_RESULT_LEDGER_INCOMPLETE",
    "ORACLE_RESULT_LEDGER_INVALID",
)


CRITERION_ROWS = (
    ("bindings_and_independence", 1,
     "exact_head_provenance_and_oracle_independence", ("binding_value_v1",),
     (None,), ("PASS", "INCOMPLETE"),
     ("BINDING_UNAVAILABLE", "BINDING_MISMATCH", "WORKTREE_DIRTY",
      "DEPENDENCY_PROVENANCE_MISMATCH", "INDEPENDENCE_AUDIT_INCOMPLETE"), None),
    ("complete_artifact_inventory", 294,
     "exact_schema2_artifact_inventory_no_unexpected_paths", ("artifact_value_v1",),
     ("artifact_slot_target_v1",), ("PASS", "INCOMPLETE"),
     ("ARTIFACT_MISSING", "ARTIFACT_HASH_MISMATCH", "ARTIFACT_CONTENT_MISMATCH",
      "ARTIFACT_IDENTITY_MISMATCH", "UNEXPECTED_ARTIFACT_PATH"), None),
    ("raw_bfr_d9a_reproduction", 196,
     "exact_B2_raw_D9a_reproduction_124_cases", ("raw_d9a_value_v1",),
     ("raw_d9a_value_v1",), ("PASS", "INCOMPLETE"),
     ("RAW_D9A_REPRODUCTION_MISMATCH",), "maximum_row_sum_residual"),
    ("representation_structure", 4158000,
     "exact_anchor_derivation_vector_binding_sum_one_position_zero_derivatives",
     ("structure_present_v1", "structure_missing_anchor_v1"), (None,),
     ("PASS", "FAIL"),
     ("ANCHOR_SOURCE_MISSING", "REPRESENTATION_STRUCTURE_MISMATCH",
      "CANDIDATE_NONFINITE"), None),
    ("constant_field_bits", 62370000,
     "five_challenges_exact_position_identity_zero_derivatives",
     ("binary64_pair_v1",), (None,), ("PASS", "FAIL"),
     ("CONSTANT_FIELD_BITS_MISMATCH", "CANDIDATE_NONFINITE"), None),
    ("relabel_exact_effective_coefficients", 8316000,
     "exact_inverse_relabel_coefficient_vector_identity",
     ("coefficient_vector_comparison_v1",), ("exact_zero_l1_target_v1",),
     ("PASS", "FAIL"), ("RELABEL_EXACT_MISMATCH", "CANDIDATE_NONFINITE"), None),
    ("regular_analytic_exact_rows", 152640,
     "regular_box_spline_exact_source_union_row", ("coefficient_interval_vector_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("REGULAR_ANALYTIC_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "maximum_error_upper"),
    ("regular_analytic_emitted_geometry", 457920,
     "regular_box_spline_emitted_axis", ("emitted_interval_scalar_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("REGULAR_ANALYTIC_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "absolute_error_upper"),
    ("regular_analytic_area_integrand", 50880,
     "regular_area_integrand_exact_and_emitted",
     ("integrand_exact_interval_v1", "integrand_emitted_interval_v1"),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("REGULAR_INTEGRAND_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "absolute_error_upper"),
    ("regular_analytic_legacy_volume_integrand", 50880,
     "regular_legacy_volume_integrand_exact_and_emitted",
     ("integrand_exact_interval_v1", "integrand_emitted_interval_v1"),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("REGULAR_INTEGRAND_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "absolute_error_upper"),
    ("oracle_coverage_and_crosscheck", 1188000,
     "primary_Stam_plus_uniform_coverage", ("oracle_covered_value_v1", None),
     (None,), ("PASS", "UNCOVERED", "INCOMPLETE"),
     D10_ORACLE_REASONS + ORACLE_INFRASTRUCTURE_REASONS, None),
    ("exact_effective_d10_coeff", 1188000,
     "covered_primary_oracle_coefficient_l1", ("oracle_coefficient_l1_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("D10_COEFFICIENT_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"), "l1"),
    ("exact_effective_d10_geometry", 3564000,
     "covered_primary_oracle_exact_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("D10_GEOMETRY_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("emitted_direct_geometry_d10", 3564000,
     "covered_primary_oracle_emitted_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("D10_EMITTED_GEOMETRY_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("anchor_sensitivity_exact_coeff", 1188000,
     "all_three_anchor_pairs_exact_coefficient_l1", ("exact_coefficient_l1_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("ANCHOR_SENSITIVITY_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"), "l1"),
    ("anchor_sensitivity_exact_geometry", 3564000,
     "all_three_anchor_pairs_exact_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("ANCHOR_SENSITIVITY_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("anchor_sensitivity_emitted_geometry", 3564000,
     "all_three_anchor_pairs_emitted_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("ANCHOR_SENSITIVITY_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("binary64_basis_probe_diagnostic", 32271264,
     "exact_group_l1_all_anchors_all_relabels", ("basis_value_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("BASIS_GROUP_L1_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"), "group_l1"),
    ("binary64_direct_geometry_fidelity", 10692000,
     "emitted_vs_exact_direct_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("BINARY64_FIDELITY_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("relabel_emitted_geometry_fidelity", 7128000,
     "inverse_relabel_emitted_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("RELABEL_FIDELITY_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("stabilization_6_7_exact_coeff", 594000,
     "level_6_to_7_exact_coefficient_l1", ("exact_coefficient_l1_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("STABILIZATION_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"), "l1"),
    ("stabilization_6_7_exact_geometry", 1782000,
     "level_6_to_7_exact_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("STABILIZATION_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("stabilization_6_7_emitted_geometry", 1782000,
     "level_6_to_7_emitted_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("STABILIZATION_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("stabilization_7_8_exact_coeff", 594000,
     "level_7_to_8_exact_coefficient_l1", ("exact_coefficient_l1_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("STABILIZATION_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"), "l1"),
    ("stabilization_7_8_exact_geometry", 1782000,
     "level_7_to_8_exact_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("STABILIZATION_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("stabilization_7_8_emitted_geometry", 1782000,
     "level_7_to_8_emitted_geometry_axis", ("geometry_axis_v1",),
     ("absolute_rational_target_v1",), ("PASS", "FAIL"),
     ("STABILIZATION_TARGET_EXCEEDED", "CANDIDATE_NONFINITE"),
     "normalized_bound.normalized_upper"),
    ("cache_mode_bit_identity", 2079000,
     "complete_cache_disabled_equals_serial_cache_row_signature",
     ("row_signature_pair_v1",), (None,), ("PASS", "FAIL"),
     ("CACHE_MODE_BITS_MISMATCH", "CANDIDATE_NONFINITE"), None),
)


D12_ROWS = (
    ("d12_preparation_cost", 3136,
     "unchanged_D12_total_representation_preparation",
     ("d12_duration_valid_v1", "d12_duration_invalid_v1"),
     ("d12_duration_target_v1",), ("PASS", "FAIL", "INCOMPLETE"),
     ("PREPARATION_MEDIAN_BUDGET_EXCEEDED",
      "PREPARATION_SINGLE_RUN_BUDGET_EXCEEDED",
      "PREPARATION_MEASUREMENT_NONFINITE_OR_NEGATIVE",
      "PREPARATION_PROCESS_FAILURE", "D12_PLATFORM_UNQUALIFIED",
      "D12_PROVENANCE_INVALID", "D12_OPERATIONAL_LEDGER_INCOMPLETE"),
     "duration_ns"),
    ("d12_retained_payload", 5964,
     "unchanged_D12_retained_representation_payload",
     ("d12_payload_valid_v1", "d12_payload_invalid_v1"),
     ("d12_payload_target_v1",), ("PASS", "FAIL", "INCOMPLETE"),
     ("RETAINED_PAYLOAD_BUDGET_EXCEEDED", "RETAINED_PAYLOAD_INVALID",
      "D12_PLATFORM_UNQUALIFIED", "D12_PROVENANCE_INVALID",
      "D12_OPERATIONAL_LEDGER_INCOMPLETE"), "payload_bytes"),
    ("d12_peak_rss", 4179364, "unchanged_D12_representation_peak_RSS",
     ("d12_rss_valid_v1", "d12_rss_invalid_v1"),
     ("d12_rss_target_v1",), ("PASS", "FAIL", "INCOMPLETE"),
     ("PEAK_RSS_BUDGET_EXCEEDED", "RSS_SAMPLE_MISSING_OR_API_FAILURE",
      "D12_PLATFORM_UNQUALIFIED", "D12_PROVENANCE_INVALID",
      "D12_OPERATIONAL_LEDGER_INCOMPLETE"), "rss_delta_bytes"),
    ("d12_cache_disabled_concurrency", 13720,
     "cache_disabled_representation_output_reference_identity",
     ("d12_concurrency_value_v1", "d12_concurrency_abort_v1"),
     ("d12_output_reference_target_v1",), ("PASS", "FAIL", "INCOMPLETE"),
     ("CACHE_DISABLED_CONCURRENCY_MISMATCH", "CACHE_DISABLED_RACE",
      "D12_REPRESENTATION_WORKLOAD_MISMATCH", "D12_PLATFORM_UNQUALIFIED",
      "D12_PROVENANCE_INVALID", "D12_OPERATIONAL_LEDGER_INCOMPLETE"), None),
    ("d12_instrumented_tsan", 14896,
     "instrumented_provider_and_representation_TSan",
     ("d12_tsan_instrumentation_summary_v1", "d12_tsan_finding_summary_v1",
      "d12_tsan_threaded_row_value_v1", None),
     ("d12_tsan_instrumentation_target_v1", "d12_tsan_finding_target_v1",
      "d12_output_reference_target_v1"), ("PASS", "FAIL", "INCOMPLETE"),
     ("CACHE_DISABLED_RACE", "THREADED_CACHE_RACE",
      "THREADED_CACHE_OUTPUT_MISMATCH", "D12_REPRESENTATION_WORKLOAD_MISMATCH",
      "D12_PLATFORM_UNQUALIFIED", "D12_PROVENANCE_INVALID",
      "D12_OPERATIONAL_LEDGER_INCOMPLETE"), None),
)


CRITERION_ROWS = CRITERION_ROWS + D12_ROWS
CRITERION_CONTRACTS = tuple({
    "ordinal": ordinal, "criterion_id": row[0], "count": row[1],
    "expectation": row[2], "exact_value_kinds": row[3],
    "target_kinds": row[4], "complete_statuses": row[5],
    "reasons": row[6], "maximum_field": row[7],
} for ordinal, row in enumerate(CRITERION_ROWS))
CRITERION_BY_ID = dict((item["criterion_id"], item)
                       for item in CRITERION_CONTRACTS)


# A witness is categorical only through its owning criterion.  Its embedded
# maximum is nevertheless limited to the three exact nonnegative scalar forms
# used by the frozen scientific and operational criteria.
MAXIMUM_EXACT_SCHEMAS = (
    ref("absolute_dyadic_v1"), ref("absolute_rational_v1"),
    ref("rational_over_sqrt_v1"),
)
OBJECT_SCHEMAS["maximum_witness"] = closed({
    "cell_key": array({}, minimum=1),
    "result_record": {
        "type": "array", "minItems": 5, "maxItems": 5,
        "prefixItems": [array({}, minimum=1),
                        {"enum": ["PASS", "FAIL", "UNCOVERED",
                                  "INCOMPLETE"]},
                        {}, {}, {"type": ["string", "null"]}],
        "items": False,
    },
    "leaf_index": UINT64,
    "merkle_siblings": array(SHA256),
    "maximum_exact": {"oneOf": list(MAXIMUM_EXACT_SCHEMAS)},
    "maximum_binary64_bits": BITS64,
})


MUTATION_OPERATORS = (
    "M01 delete-required-object-member", "M02 add-unknown-object-member",
    "M03 replace-required-type", "M04 insert-array-item",
    "M05 delete-array-item", "M06 duplicate-array-item",
    "M07 swap-adjacent-array-items", "M08 criterion-id-position-count",
    "M09 criterion-authority", "M10 ledger-slot", "M11 result-sidecar",
    "M12 result-record", "M13 maximum-witness", "M14 merkle-proof",
    "M15 first-failure", "M16 authority-value", "M17 oracle-partition",
    "M18 basis-aggregation", "M19 raw-D9a", "M20 D12-envelope",
    "M21 causality-verdict", "M22 serial-only", "M23 canonical-encoding",
)


# Locations whose required-member sets form the approved ``object`` universe.
# Aliases retain the report schema's original public definition names while
# assigning one normative result-contract name to each object.
OBJECT_SCHEMA_ALIASES = {
    "artifact": "artifact", "authority": "authority",
    "binaries": "binaries", "binary_binding": "binary",
    "checkpoint": "checkpoint", "criterion": "criterion",
    "dependencies": "dependencies", "dependency_binding": "dependency",
    "git_identity": "gitIdentity", "hash_binding": "hashBinding",
    "identity": "identity", "matrix": "matrix",
    "pre_result_ledger": "ledger", "verdict": "verdict",
    "worktree_observation": "worktree",
}


ARRAY_PATHS = (
    "authority.actual_fixture_files", "authority.anchor_order",
    "authority.canonical_sample_order", "authority.expected_fixture_files",
    "authority.radius_exponents", "authority.ray_sequence",
    "authority.relabels", "authority.rows", "authority.source_order",
    "binary_binding.sources",
    "candidate_dyadic_vector_observation_v1.source_ids",
    "candidate_dyadic_vector_observation_v1.values",
    "candidate_interval_vector_observation_v1.observed_intervals",
    "candidate_interval_vector_observation_v1.source_ids",
    "candidate_row_signature_observation_v1.cache_disabled_entries",
    "candidate_row_signature_observation_v1.serial_cache_entries",
    "candidate_structure_observation_v1.canonical_source_ids",
    "candidate_structure_observation_v1.effective_coefficients",
    "candidate_structure_observation_v1.provider_coefficient_bits",
    "coefficient_interval_vector_v1.absolute_error_uppers",
    "coefficient_interval_vector_v1.analytic_intervals",
    "coefficient_interval_vector_v1.observed",
    "coefficient_interval_vector_v1.source_union_ids",
    "coefficient_vector_comparison_v1.absolute_errors",
    "coefficient_vector_comparison_v1.expected",
    "coefficient_vector_comparison_v1.observed",
    "coefficient_vector_comparison_v1.source_ids",
    "d12.criteria", "d12.process_observations", "d12.tuple_keys",
    "d12_binary.source_inventory", "d12_build_profile.compile_commands",
    "d12_build_profile.flags", "d12_build_profile.link_commands",
    "d12_concurrency_abort_v1.tsan_finding_summary_key",
    "d12_platform.field_mismatches",
    "d12_platform.power_thermal_observations",
    "d12_process_observation_record_v1", "d12_workload.input_ids",
    "d12_workload.sidecars", "exact_coefficient_l1_v1.absolute_errors",
    "exact_coefficient_l1_v1.expected", "exact_coefficient_l1_v1.observed",
    "exact_coefficient_l1_v1.source_ids", "matrix.ledgers",
    "matrix.unexpected_paths", "maximum_witness.merkle_siblings",
    "oracle.covered_keys", "oracle.request_keys", "oracle.uncovered_keys",
    "oracle_coefficient_l1_v1.absolute_error_uppers",
    "oracle_coefficient_l1_v1.observed",
    "oracle_coefficient_l1_v1.oracle_intervals",
    "oracle_coefficient_l1_v1.source_ids",
    "oracle_covered_value_v1.child_branches",
    "oracle_covered_value_v1.evaluated_depths",
    "oracle_covered_value_v1.intersected_primary_intervals",
    "oracle_covered_value_v1.primary_depth_intervals",
    "oracle_covered_value_v1.primary_depth_intervals[]",
    "oracle_covered_value_v1.source_ids",
    "oracle_covered_value_v1.uniform_depth_intervals",
    "oracle_covered_value_v1.uniform_depth_intervals[]",
    "report.artifacts", "report.criteria", "result_ledger.outer_records",
    "serial_only_context.failure_records",
    "structure_missing_anchor_v1.canonical_source_ids",
    "structure_missing_anchor_v1.provider_coefficient_bits",
    "structure_present_v1.canonical_source_ids",
    "structure_present_v1.effective_coefficients",
    "structure_present_v1.provider_coefficient_bits",
)


AUTHORITY_PATHS = (
    "authority.anchor_order", "authority.canonical_sample_order",
    "authority.component_targets.first_derivative",
    "authority.component_targets.position",
    "authority.component_targets.second_derivative",
    "authority.d10.first_derivative", "authority.d10.position",
    "authority.d10.second_derivative",
    "authority.d12_contract.peak_rss_delta_bytes",
    "authority.d12_contract.preparation_median_ns",
    "authority.d12_contract.preparation_single_ns",
    "authority.d12_contract.retained_payload_bytes",
    "authority.dependencies.gmp", "authority.dependencies.mpfr",
    "authority.dependencies.opensubdiv", "authority.expected_fixture_files",
    "authority.inner_radius_rule", "authority.manifest_contract_sha256",
    "authority.manifest_file_sha256", "authority.physical_fingerprint",
    "authority.radius_exponents", "authority.ray_sequence",
    "authority.relabels", "authority.row_invariant_tolerance",
    "authority.rows", "authority.source_order",
)


EXTERNAL_ARRAY_PATHS = {
    "d12.process_observations": array(ref("d12_process_provenance_v1")),
    "d12.tuple_keys": array({"type": "array"}),
    "d12_process_observation_record_v1": array({}, minimum=1),
    "matrix.unexpected_paths": array({"type": "array"}),
    "oracle.covered_keys": array({"type": "array"}),
    "oracle.request_keys": array({"type": "array"}),
    "oracle.uncovered_keys": array({"type": "array"}),
    "result_ledger.outer_records": array(
        {"type": "array", "minItems": 5, "maxItems": 5}),
}


def _criterion_report_target_schema(criterion_id):
    """Return the closed aggregate target schema for one report slot."""
    def exact_target(denominator):
        return closed({
            "kind": {"const": "absolute_rational_target_v1"},
            "numerator": {"const": "1"},
            "denominator": {"const": denominator},
        })

    def exact_row_target(position, first_derivative, second_derivative):
        return closed({
            "position": exact_target(position),
            "first_derivative": exact_target(first_derivative),
            "second_derivative": exact_target(second_derivative),
        })

    if criterion_id == "complete_artifact_inventory":
        return ref("unexpected_paths_target_v1")
    if criterion_id == "relabel_exact_effective_coefficients":
        return ref("exact_zero_l1_target_v1")
    if criterion_id in {
            "regular_analytic_exact_rows",
            "regular_analytic_emitted_geometry",
            "regular_analytic_area_integrand",
            "regular_analytic_legacy_volume_integrand"}:
        return exact_target("200000")
    if criterion_id in {
            "exact_effective_d10_coeff", "exact_effective_d10_geometry",
            "emitted_direct_geometry_d10",
            "anchor_sensitivity_exact_coeff",
            "anchor_sensitivity_exact_geometry",
            "anchor_sensitivity_emitted_geometry",
            "binary64_basis_probe_diagnostic",
            "binary64_direct_geometry_fidelity",
            "relabel_emitted_geometry_fidelity",
            "stabilization_6_7_exact_coeff",
            "stabilization_6_7_exact_geometry",
            "stabilization_6_7_emitted_geometry",
            "stabilization_7_8_exact_coeff",
            "stabilization_7_8_exact_geometry",
            "stabilization_7_8_emitted_geometry"}:
        if criterion_id in {
                "exact_effective_d10_coeff", "exact_effective_d10_geometry",
                "emitted_direct_geometry_d10"}:
            return exact_row_target("200000", "40000", "8000")
        return exact_row_target("2000000", "400000", "80000")
    if criterion_id == "d12_preparation_cost":
        return ref("d12_duration_target_v1")
    if criterion_id == "d12_retained_payload":
        return ref("d12_payload_target_v1")
    if criterion_id == "d12_peak_rss":
        return ref("d12_rss_target_v1")
    return {"const": None}


def _criterion_maximum_schema(criterion_id):
    contract = CRITERION_BY_ID[criterion_id]
    if contract["maximum_field"] is None:
        return {"const": None}, {"const": None}
    if criterion_id in {
            "raw_bfr_d9a_reproduction", "anchor_sensitivity_exact_coeff",
            "binary64_basis_probe_diagnostic",
            "stabilization_6_7_exact_coeff",
            "stabilization_7_8_exact_coeff"}:
        exact = ref("absolute_dyadic_v1")
    else:
        exact = ref("absolute_rational_v1")
    return ({"oneOf": [exact, {"type": "null"}]},
            {"oneOf": [ref("maximum_witness"), {"type": "null"}]})


def _schema_location(schema, object_name):
    if object_name == "report":
        return schema
    if object_name in OBJECT_SCHEMAS:
        return schema["$defs"][object_name]
    return schema["$defs"][OBJECT_SCHEMA_ALIASES[object_name]]


def _authority_schema(authority):
    exact_object_names = {"d10", "component_targets", "d12_contract"}
    properties = {}
    for name, value in authority.items():
        if name in exact_object_names:
            properties[name] = closed(dict(
                (member, {"const": member_value})
                for member, member_value in value.items()))
        else:
            properties[name] = {"const": copy.deepcopy(value)}
    return closed(properties)


def _base_criterion_schema():
    nullable_sha = {"type": ["string", "null"], "pattern": SHA256_PATTERN}
    nullable_key = {"type": ["array", "null"]}
    return closed({
        "criterion_id": NONEMPTY_STRING,
        "target": {"type": ["object", "null"]},
        "expectation": NONEMPTY_STRING,
        "applicability": {"const": "frozen_B2b"},
        "expected_cell_count": UINT64,
        "observed_cell_count": UINT64,
        "key_ledger_sha256": nullable_sha,
        "result_ledger_sha256": nullable_sha,
        "result_merkle_root_sha256": nullable_sha,
        "result_ledger_artifact": ref("result_ledger_artifact"),
        "status": {"enum": ["PASS", "FAIL", "INCOMPLETE", "UNCOVERED",
                            "OMITTED_AFTER_CANDIDATE_FAILURE",
                            "OMITTED_AFTER_INFRASTRUCTURE_FAILURE"]},
        "maximum": {"type": ["object", "null"]},
        "witness": {"type": ["object", "null"]},
        "first_failing_key": nullable_key,
        "omission_blocker": {"type": ["string", "null"]},
    })


def _property_schema(schema, dotted_path):
    """Resolve an anchored path to the schema node that owns its value."""
    name, separator, suffix = dotted_path.partition(".")
    if not separator:
        raise KeyError(dotted_path)
    node = (schema["$defs"]["anchored_row_representation_d12"]
            if name == "d12" else _schema_location(schema, name))
    for component in suffix.split("."):
        if component.endswith("[]"):
            component = component[:-2]
            node = node["properties"][component]["items"]
        else:
            node = node["properties"][component]
    return node


def install_report_schema_contract(schema, authority_values):
    """Install the reviewed closed contract into a report-schema value."""
    schema = copy.deepcopy(schema)

    def remove_annotations(node):
        if isinstance(node, dict):
            for key in tuple(node):
                if key.startswith("x-contract-"):
                    del node[key]
                else:
                    remove_annotations(node[key])
        elif isinstance(node, list):
            for value in node:
                remove_annotations(value)

    remove_annotations(schema)
    definitions = schema["$defs"]
    for name, definition in OBJECT_SCHEMAS.items():
        if name != "availability":
            definitions[name] = copy.deepcopy(definition)
    definitions["authority"] = _authority_schema(authority_values)
    definitions["criterion"] = _base_criterion_schema()
    availability_schema = definitions["availability"]
    availability_schema["properties"]["reason_code"]["enum"] = sorted(
        set(availability_schema["properties"]["reason_code"]["enum"]) |
        set(ORACLE_INFRASTRUCTURE_REASONS),
        key=lambda value: "" if value is None else value)
    for conditional in availability_schema["allOf"]:
        if conditional["if"]["properties"]["state"].get("const") == \
                "UNAVAILABLE":
            conditional["then"]["properties"]["reason_code"]["enum"] = \
                sorted(set(conditional["then"]["properties"][
                    "reason_code"]["enum"]) |
                       set(ORACLE_INFRASTRUCTURE_REASONS))

    # Rebind every report-reachable legacy reference to the reviewed closed
    # definitions.  The original schema used camelCase clones at these four
    # boundaries; leaving even one clone reachable would make the 740-path
    # derivation describe a different contract from the one reports execute.
    definitions["binary"]["properties"]["sources"]["items"] = ref(
        "source_binding")
    definitions["matrix"]["properties"]["unexpected_paths"] = ref(
        "unexpected_paths_target_v1")
    schema["properties"]["d12_artifact"] = ref("d12_artifact_binding")

    schema["x-contract-object-name"] = "report"
    for name in sorted(set(OBJECT_SCHEMAS) | set(OBJECT_SCHEMA_ALIASES)):
        _schema_location(schema, name)["x-contract-object-name"] = name

    schema["x-contract-external-arrays"] = copy.deepcopy(
        EXTERNAL_ARRAY_PATHS)
    for path, node in schema["x-contract-external-arrays"].items():
        node["x-contract-array-path"] = path
    for path in ARRAY_PATHS:
        if path not in EXTERNAL_ARRAY_PATHS:
            _property_schema(schema, path)["x-contract-array-path"] = path

    schema["x-contract-external-authority"] = {
        "authority.dependencies.gmp": {"const": "6.3.0"},
        "authority.dependencies.mpfr": {"const": "4.2.2"},
        "authority.dependencies.opensubdiv": {"const": "3.7.0"},
    }
    for path in AUTHORITY_PATHS:
        node = schema["x-contract-external-authority"].get(path)
        if node is None:
            node = _property_schema(schema, path)
        node["x-contract-authority-path"] = path

    for contract in CRITERION_CONTRACTS:
        name = "criterion_{:02d}".format(contract["ordinal"])
        slot = definitions[name]
        overlay = slot["allOf"][1]["properties"]
        overlay["expectation"] = {"const": contract["expectation"]}
        overlay["applicability"] = {"const": "frozen_B2b"}
        overlay["status"] = {"enum": list(contract["complete_statuses"]) +
                             (["OMITTED_AFTER_CANDIDATE_FAILURE"]
                              if contract["ordinal"] >= 27 else
                              ["OMITTED_AFTER_CANDIDATE_FAILURE",
                               "OMITTED_AFTER_INFRASTRUCTURE_FAILURE"]
                              if 3 <= contract["ordinal"] <= 26 and
                              contract["ordinal"] != 10 else [])}
        overlay["target"] = _criterion_report_target_schema(
            contract["criterion_id"])
        maximum_schema, witness_schema = _criterion_maximum_schema(
            contract["criterion_id"])
        overlay["maximum"] = maximum_schema
        overlay["witness"] = witness_schema
        slot["x-contract-criterion-ordinal"] = contract["ordinal"]
    ledger_slots = definitions["matrix"]["properties"]["ledgers"][
        "prefixItems"]
    for ordinal, slot_ref in enumerate(ledger_slots):
        definition = definitions[slot_ref["$ref"].split("/")[-1]]
        definition["x-contract-ledger-ordinal"] = ordinal
    return schema


def derive_schema_path_anchor(schema):
    """Derive all approved path lines solely from the executable schema."""
    lines = []

    def visit(node):
        if isinstance(node, dict):
            object_name = node.get("x-contract-object-name")
            if object_name is not None:
                required = node.get("required")
                if not isinstance(required, list):
                    raise ValueError("contract object lacks required members")
                lines.extend("object|{}|{}".format(object_name, member)
                             for member in required)
            array_path = node.get("x-contract-array-path")
            if array_path is not None:
                if not (node.get("type") == "array" or
                        isinstance(node.get("const"), list)):
                    raise ValueError("contract array annotation is not array")
                lines.append("array|{}".format(array_path))
            authority_path = node.get("x-contract-authority-path")
            if authority_path is not None:
                if "const" not in node:
                    raise ValueError("contract authority annotation lacks const")
                lines.append("authority|{}".format(authority_path))
            if "x-contract-criterion-ordinal" in node:
                properties = node["allOf"][1]["properties"]
                lines.append("criterion|{:02d}|{}|{}".format(
                    node["x-contract-criterion-ordinal"],
                    properties["criterion_id"]["const"],
                    properties["expected_cell_count"]["const"]))
            if "x-contract-ledger-ordinal" in node:
                properties = node["allOf"][1]["properties"]
                criterion_id = properties["criterion_id"]["const"]
                lines.append("ledger|{:02d}|{}|{}".format(
                    CRITERION_BY_ID[criterion_id]["ordinal"], criterion_id,
                    properties["partition"]["const"]))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    if len(lines) != len(set(lines)):
        raise ValueError("duplicate executable contract path annotation")
    return sorted(lines)


def expand_mutation_manifest(schema_paths):
    """Expand the literal M01--M23 operands over one authenticated universe."""
    objects = {}
    arrays = []
    authorities = []
    criteria = []
    ledgers = []
    for line in schema_paths:
        fields = line.split("|")
        if fields[0] == "object":
            objects.setdefault(fields[1], []).append(fields[2])
        elif fields[0] == "array":
            arrays.append(fields[1])
        elif fields[0] == "authority":
            authorities.append(fields[1])
        elif fields[0] == "criterion":
            criteria.append(tuple(fields[1:]))
        elif fields[0] == "ledger":
            ledgers.append(tuple(fields[1:]))
        else:
            raise ValueError("unknown schema-path kind")

    manifest = []

    def add(operator, operand, mutations):
        for mutation in mutations:
            manifest.append("{}|{}|{}".format(operator, operand, mutation))

    for object_name in sorted(objects):
        for member in sorted(objects[object_name]):
            operand = "{}.{}".format(object_name, member)
            add("M01", operand, ("delete",))
            add("M03", operand, ("replace-required-type",))
        add("M02", object_name, ("add-unknown-member",))
    for path in sorted(arrays):
        for operator, mutation in (
                ("M04", "insert"), ("M05", "delete"),
                ("M06", "duplicate"), ("M07", "swap-adjacent")):
            add(operator, path,
                (mutation + "-first", mutation + "-middle",
                 mutation + "-last"))
    for ordinal, criterion_id, count in sorted(criteria):
        operand = "{}:{}:{}".format(ordinal, criterion_id, count)
        add("M08", operand, ("wrong-id", "wrong-ordinal", "count-minus-one",
                             "count-plus-one"))
        add("M09", operand, ("expectation", "applicability", "target",
                             "allowed-status", "nullability"))
        add("M11", operand, ("missing", "extra", "byte-length",
                             "record-count", "sha256", "trailing-byte"))
        add("M12", operand, ("missing", "extra", "duplicate", "reorder",
                             "key", "outcome", "exact-value", "target",
                             "reason"))
    for ordinal, criterion_id, partition in sorted(ledgers):
        operand = "{}:{}:{}".format(ordinal, criterion_id, partition)
        add("M10", operand, ("wrong-id", "wrong-partition", "wrong-count",
                             "wrong-key-digest"))
    for contract in CRITERION_CONTRACTS:
        operand = "{:02d}:{}".format(
            contract["ordinal"], contract["criterion_id"])
        if contract["maximum_field"] is not None:
            add("M13", operand, ("noncorpus-key", "wrong-record",
                                 "wrong-ordinal", "wrong-exact",
                                 "wrong-display-bits", "nonfirst-tie"))
            add("M14", operand, ("short", "extra", "wrong-sibling",
                                 "reversed-direction", "wrong-index",
                                 "padding-index", "wrong-root"))
        if "FAIL" in contract["complete_statuses"]:
            add("M15", operand, ("null", "passing-key", "later-failure",
                                 "noncorpus-key"))
    for path in sorted(authorities):
        add("M16", path, ("replace-frozen-value",))
    fixed = {
        "M17": ("gap", "overlap", "outside-request",
                 "covered-as-uncovered", "wrong-reason", "missing-reason",
                 "uniform-as-primary"),
        "M18": ("distributed-per-source-error", "identity-only-failure",
                 "reverse-only-failure", "rotate-only-failure",
                 "signed-coefficient", "wrong-inverse-map", "wrong-group-l1"),
        "M19": ("case-state", "case-digest", "failing-row-count",
                 "124-count", "exact-numerator", "maximum-bits",
                 "maximum-witness"),
        "M20": ("malformed", "duplicate-key", "content-hash", "cross-head",
                 "dirty", "old-B2", "boolean-only", "missing-provenance",
                 "fingerprint", "hosted-as-qualified", "workload",
                 "reference-digest", "instrumentation", "operational-gap"),
        "M21": ("legal-group-status", "illegal-group-status",
                 "earlier-blocker", "later-blocker", "FAIL-precedence",
                 "ordered-INCOMPLETE", "ordered-UNCOVERED", "all-PASS"),
        "M22": ("missing-tuple", "cache-disabled-failure",
                 "output-mismatch", "nonrace-failure", "incomplete-evidence",
                 "exact-race-only-eligibility"),
        "M23": ("BOM", "prefix", "suffix", "newline", "non-JCS-number",
                 "negative-zero", "nonfinite", "duplicate-JSON-key"),
    }
    for operator in sorted(fixed):
        add(operator, "global", fixed[operator])
    if len(manifest) != len(set(manifest)):
        raise ValueError("duplicate expanded mutation manifest entry")
    return tuple(sorted(manifest))
