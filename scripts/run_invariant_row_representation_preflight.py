#!/usr/bin/env python3
"""Proof-only anchored-difference row-representation preflight.

This program consumes the complete, provenance-bound B2 Release checkpoint and
its 294 gzip case artifacts.  It does not build a provider, normalize a row,
change a tolerance, or select an architecture.  Its only candidate is a
representation of each of the six source-keyed functionals:

* position: ``x_anchor + sum(c_i * (x_i - x_anchor))``;
* derivatives: ``sum(c_i * (x_i - x_anchor))``.

The anchor is the first oriented coarse-face corner and the sums retain every
provider coefficient bit-for-bit.  The anchor term is present and multiplies
the exact zero difference ``x_anchor - x_anchor``.  Consequently constant
fields are reproduced by construction.  Whether the resulting operator
perturbation is scientifically acceptable is deliberately not decided here.
"""

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import pathlib
import re
import struct
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
B2_RUNNER = ROOT / "scripts/run_bfr_qualification.py"
B2_SPEC = importlib.util.spec_from_file_location("run_bfr_qualification", B2_RUNNER)
B2 = importlib.util.module_from_spec(B2_SPEC)
B2_SPEC.loader.exec_module(B2)

SCHEMA_VERSION = 1
REPRESENTATION = "anchored_difference_rows_v1"
ROW_INVARIANT_TOLERANCE = 1.0e-12
ROW_ORDER = ("position", "du", "dv", "duu", "duv", "dvv")
CONSTANT_FIELD_CHALLENGES = (0.0, 1.0, -1.0, 1048576.0, -1048576.0)
EXPECTED_CASE_COUNT = 294
EXPECTED_BFR_CASE_COUNT = 196
EXPECTED_FAR_CASE_COUNT = 98
EXPECTED_D9A_BFR_FAILURE_COUNT = 124
EXPECTED_D9A_BFR_MAX_ERROR = 2.0368522054550406e-11
FROZEN_B2_INPUT_HEAD = "8282549ac2e0d0819edb095772e4b85aa204209d"


class PreflightError(RuntimeError):
    """Fail-closed contract violation."""


def require(condition, message):
    if not condition:
        raise PreflightError(message)


def binary64_bits(value):
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            "binary64 value is not numeric")
    value = float(value)
    require(math.isfinite(value), "binary64 value is nonfinite")
    return struct.pack("<d", value)


def binary64_bits_hex(value):
    return binary64_bits(value).hex()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_git_head():
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    head = completed.stdout.strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None,
            "exact Git head is unavailable")
    return head


def row_target(row_kind):
    require(row_kind in ROW_ORDER, "unknown six-row kind")
    return 1.0 if row_kind == "position" else 0.0


def represent_row(row, oriented_face):
    """Create an audit-complete anchored-difference representation.

    No coefficient is corrected, omitted, or synthesized.  Every evaluation
    term carries one provider coefficient with identical binary64 bits.  The
    anchor coefficient multiplies the exact zero anchor difference.
    """
    require(isinstance(row, dict), "row is not an object")
    row_kind = row.get("row_kind")
    target = row_target(row_kind)
    source_ids = row.get("source_ids")
    coefficients = row.get("coefficients")
    require(isinstance(source_ids, list) and source_ids == sorted(set(source_ids)),
            "source IDs are missing, duplicated, or unordered")
    require(isinstance(coefficients, list) and len(coefficients) == len(source_ids),
            "source/coefficient cardinality mismatch")
    require(isinstance(oriented_face, (list, tuple)) and len(oriented_face) == 3,
            "oriented face is malformed")
    anchor_source_id = oriented_face[0]
    require(anchor_source_id in source_ids,
            "first oriented face corner is absent from the provider row")
    anchor_index = source_ids.index(anchor_source_id)
    difference_terms = []
    for source_id, coefficient in zip(source_ids, coefficients):
        coefficient_bits = binary64_bits_hex(coefficient)
        difference_terms.append({
            "source_id": source_id,
            "coefficient": float(coefficient),
            "coefficient_bits_hex": coefficient_bits,
        })
    return {
        "representation": REPRESENTATION,
        "row_kind": row_kind,
        "target": target,
        "anchor_source_id": anchor_source_id,
        "provider_anchor_coefficient": float(coefficients[anchor_index]),
        "provider_anchor_coefficient_bits_hex": binary64_bits_hex(
            coefficients[anchor_index]),
        "difference_terms": difference_terms,
        "source_ids": list(source_ids),
    }


def evaluate_provider_row(row, scalar_sources):
    return B2.ordered_binary64_sum(
        float(coefficient) * scalar_sources[source_id]
        for source_id, coefficient in zip(row["source_ids"], row["coefficients"]))


def evaluate_anchored_row(representation, scalar_sources):
    anchor = scalar_sources[representation["anchor_source_id"]]
    terms = [
        term["coefficient"] * (scalar_sources[term["source_id"]] - anchor)
        for term in representation["difference_terms"]
    ]
    difference_sum = B2.ordered_binary64_sum(terms)
    if representation["row_kind"] == "position":
        return anchor + difference_sum
    return difference_sum


def validate_representation_against_row(representation, row):
    require(representation["row_kind"] == row["row_kind"],
            "representation changed a row kind")
    require(representation["source_ids"] == row["source_ids"],
            "representation changed original source identity")
    anchor = representation["anchor_source_id"]
    expected_terms = [(source_id, binary64_bits_hex(coefficient))
                      for source_id, coefficient in
                      zip(row["source_ids"], row["coefficients"])]
    actual_terms = [(term["source_id"], term["coefficient_bits_hex"])
                    for term in representation["difference_terms"]]
    require(actual_terms == expected_terms,
            "representation mutated, omitted, or reordered a coefficient")
    anchor_index = row["source_ids"].index(anchor)
    require(representation["provider_anchor_coefficient_bits_hex"] ==
            binary64_bits_hex(row["coefficients"][anchor_index]),
            "representation lost the provider anchor audit value")
    for constant in CONSTANT_FIELD_CHALLENGES:
        scalar_sources = {source_id: constant for source_id in row["source_ids"]}
        observed = evaluate_anchored_row(representation, scalar_sources)
        expected = constant if row["row_kind"] == "position" else 0.0
        require(binary64_bits_hex(observed) == binary64_bits_hex(expected),
                "anchored representation failed a constant-field identity")


def update_representation_digest(digest, row, representation):
    sample_id = row["sample_id"].encode("utf-8")
    digest.update(b"ANCHDIFF1")
    digest.update(struct.pack("<i", row["face_row"]))
    digest.update(struct.pack("<I", len(sample_id)))
    digest.update(sample_id)
    digest.update(struct.pack("<I", ROW_ORDER.index(row["row_kind"])))
    digest.update(struct.pack("<i", representation["anchor_source_id"]))
    digest.update(bytes.fromhex(
        representation["provider_anchor_coefficient_bits_hex"]))
    digest.update(struct.pack("<I", len(representation["difference_terms"])))
    for term in representation["difference_terms"]:
        digest.update(struct.pack("<i", term["source_id"]))
        digest.update(bytes.fromhex(term["coefficient_bits_hex"]))


def validate_checkpoint_and_artifacts(checkpoint_path, artifact_dir,
                                      expected_binding_head):
    manifest = B2.load_manifest()
    B2.validate_manifest_contract(manifest)
    require(tuple(B2.ROW_ORDER) == ROW_ORDER, "six-row order drift")
    require(B2.MANIFEST_FILE_SHA256 ==
            "bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b",
            "frozen D10/D12 manifest file hash drift")
    require(B2.MANIFEST_CONTRACT_SHA256 ==
            "30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368",
            "frozen D10/D12 manifest contract hash drift")

    checkpoint_path = pathlib.Path(checkpoint_path).resolve()
    artifact_root = pathlib.Path(artifact_dir).resolve()
    require(checkpoint_path.is_file(), "Release checkpoint is unavailable")
    require(artifact_root.is_dir(), "case artifact directory is unavailable")
    checkpoint_raw = checkpoint_path.read_bytes()
    checkpoint = json.loads(checkpoint_raw.decode("utf-8"))
    require(set(checkpoint) == {"schema_version", "kind", "binding", "complete",
                                "numeric_cases"},
            "Release checkpoint schema contains missing or extra fields")
    require(checkpoint["schema_version"] == 2 and
            checkpoint["kind"] == "bfr_release_matrix_checkpoint" and
            checkpoint["complete"] is True,
            "Release checkpoint is not complete schema 2 evidence")
    binding = checkpoint["binding"]
    require(set(binding) == {"candidate_binary_sha256", "git_head",
                             "manifest_contract_sha256", "manifest_file_sha256"},
            "Release checkpoint binding schema drift")
    require(binding["git_head"] == expected_binding_head,
            "Release checkpoint is not bound to the required exact head")
    require(binding["manifest_file_sha256"] == B2.MANIFEST_FILE_SHA256 and
            binding["manifest_contract_sha256"] == B2.MANIFEST_CONTRACT_SHA256,
            "Release checkpoint is not bound to the frozen D10/D12 inputs")
    require(re.fullmatch(r"[0-9a-f]{64}", binding["candidate_binary_sha256"])
            is not None, "candidate binary binding is malformed")

    cases = checkpoint["numeric_cases"]
    require(isinstance(cases, list) and len(cases) == EXPECTED_CASE_COUNT,
            "Release checkpoint must contain exactly 294 cases")
    expected_identities = B2.expected_numeric_case_identities(manifest)
    identities = [(item.get("content_identity_key"), item.get("candidate"),
                   item.get("approximation_level"), item.get("applicable_mode"))
                  for item in cases]
    require(identities == expected_identities,
            "Release checkpoint case identity/order drift")
    require(sum(item[1] == "bfr" for item in identities) == EXPECTED_BFR_CASE_COUNT and
            sum(item[1] == "far" for item in identities) == EXPECTED_FAR_CASE_COUNT,
            "qualification-target/comparator case counts drift")
    jobs = {job["content_identity_key"]: job
            for job in B2.valid_content_jobs(manifest)}
    for item, expected in zip(cases, expected_identities):
        identity, candidate, level, mode = expected
        expected_name = "{}-{}-{}-{}.json.gz".format(
            identity, candidate, level, mode)
        require(item.get("complete_json_artifact") == expected_name,
                "checkpoint artifact identity drift")
        artifact_path = artifact_root / expected_name
        require(sha256_file(artifact_path) ==
                item.get("complete_json_artifact_sha256"),
                "compressed case artifact hash drift")
        B2.validate_case_artifact(
            artifact_path, item, manifest, jobs[identity],
            identity, candidate, level, mode)
    B2.validate_artifact_directory_inventory(artifact_root, cases)
    return manifest, checkpoint, jobs, hashlib.sha256(checkpoint_raw).hexdigest()


def analyze(checkpoint_path, artifact_dir, expected_binding_head):
    manifest, checkpoint, jobs, checkpoint_sha256 = \
        validate_checkpoint_and_artifacts(
            checkpoint_path, artifact_dir, expected_binding_head)
    artifact_root = pathlib.Path(artifact_dir).resolve()
    representation_digest = hashlib.sha256()
    representation_digest.update(REPRESENTATION.encode("ascii"))
    representation_digest.update(bytes.fromhex(B2.MANIFEST_CONTRACT_SHA256))

    row_count = 0
    coefficient_term_count = 0
    raw_failing_row_count = 0
    raw_failing_case_count = 0
    max_raw_ordered_residual = 0.0
    max_fsum_residual = 0.0
    max_actual_coordinate_delta = 0.0
    max_centered_normalized_delta = 0.0
    max_delta_observation = None
    case_digests = {}

    for case in checkpoint["numeric_cases"]:
        if case["candidate"] != "bfr":
            continue
        identity = case["content_identity_key"]
        artifact_path = artifact_root / case["complete_json_artifact"]
        with gzip.open(artifact_path, "rt", encoding="utf-8") as stream:
            report = json.load(stream)
        vertices, faces, _ = B2.expected_case_samples(manifest, jobs[identity])
        centroid = [B2.ordered_binary64_sum(vertex[axis] for vertex in vertices) /
                    len(vertices) for axis in range(3)]
        scale = max(abs(vertex[axis] - centroid[axis])
                    for vertex in vertices for axis in range(3))
        require(math.isfinite(scale) and scale > 0.0,
                "fixture normalization scale is invalid")
        normalized_vertices = [tuple((value - centroid[axis]) / scale
                                     for axis, value in enumerate(vertex))
                               for vertex in vertices]
        case_digest = hashlib.sha256()
        case_failed = False
        for row in report["rows"]:
            row_count += 1
            face = faces[row["face_row"]]
            representation = represent_row(row, face)
            validate_representation_against_row(representation, row)
            coefficient_term_count += len(representation["difference_terms"])
            update_representation_digest(representation_digest, row, representation)
            update_representation_digest(case_digest, row, representation)

            expected = row_target(row["row_kind"])
            ordered_residual = abs(
                B2.ordered_binary64_sum(row["coefficients"]) - expected)
            fsum_residual = abs(math.fsum(row["coefficients"]) - expected)
            max_raw_ordered_residual = max(
                max_raw_ordered_residual, ordered_residual)
            max_fsum_residual = max(max_fsum_residual, fsum_residual)
            if ordered_residual > ROW_INVARIANT_TOLERANCE:
                raw_failing_row_count += 1
                case_failed = True

            for axis in range(3):
                actual_sources = {index: vertex[axis]
                                  for index, vertex in enumerate(vertices)}
                normalized_sources = {index: vertex[axis]
                                      for index, vertex in
                                      enumerate(normalized_vertices)}
                raw_actual = evaluate_provider_row(row, actual_sources)
                represented_actual = evaluate_anchored_row(
                    representation, actual_sources)
                actual_delta = abs(represented_actual - raw_actual)
                raw_normalized = evaluate_provider_row(row, normalized_sources)
                represented_normalized = evaluate_anchored_row(
                    representation, normalized_sources)
                normalized_delta = abs(
                    represented_normalized - raw_normalized)
                max_actual_coordinate_delta = max(
                    max_actual_coordinate_delta, actual_delta)
                if normalized_delta > max_centered_normalized_delta:
                    max_centered_normalized_delta = normalized_delta
                    max_delta_observation = {
                        "content_identity_key": identity,
                        "approximation_level": case["approximation_level"],
                        "applicable_mode": case["applicable_mode"],
                        "face_row": row["face_row"],
                        "sample_id": row["sample_id"],
                        "row_kind": row["row_kind"],
                        "axis": axis,
                        "anchor_source_id": representation["anchor_source_id"],
                        "raw_ordered_sum_residual": ordered_residual,
                        "centered_normalized_operator_delta": normalized_delta,
                    }
        if case_failed:
            raw_failing_case_count += 1
        case_digests[(identity, case["approximation_level"],
                      case["applicable_mode"])] = case_digest.hexdigest()

    require(raw_failing_case_count == EXPECTED_D9A_BFR_FAILURE_COUNT,
            "preflight did not reproduce the recorded 124-case Bfr failure")
    require(binary64_bits_hex(max_raw_ordered_residual) ==
            binary64_bits_hex(EXPECTED_D9A_BFR_MAX_ERROR),
            "preflight did not reproduce the recorded Bfr maximum residual")
    cache_pair_count = 0
    for identity in B2.valid_unique_contents(manifest):
        for level in range(2, 9):
            disabled = case_digests[(identity, level, "cache_disabled")]
            serial = case_digests[(identity, level, "SurfaceFactoryCache_serial")]
            require(disabled == serial,
                    "anchored representation changed across Bfr cache modes")
            cache_pair_count += 1
    require(cache_pair_count == EXPECTED_FAR_CASE_COUNT,
            "Bfr cache-mode pair coverage drift")
    require(max_delta_observation is not None,
            "operator perturbation evidence is empty")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "invariant_row_representation_preflight",
        "status": "EVIDENCE_COMPLETE",
        "preflight_disposition": "REPRESENTATION_FEASIBLE_NOT_QUALIFIED",
        "representation": {
            "name": REPRESENTATION,
            "anchor_policy": "first_oriented_coarse_face_corner",
            "position_semantics":
                "x_anchor + ordered_sum(c_i * (x_i - x_anchor)) for all i",
            "derivative_semantics":
                "ordered_sum(c_i * (x_i - x_anchor)) for all i",
            "provider_anchor_coefficient":
                "retained_and_multiplied_by_exact_zero_anchor_difference",
            "all_coefficients": "provider_binary64_bits_unchanged",
            "six_row_order": list(ROW_ORDER),
        },
        "frozen_authority": {
            "row_invariant_tolerance": ROW_INVARIANT_TOLERANCE,
            "manifest_file_sha256": B2.MANIFEST_FILE_SHA256,
            "manifest_contract_sha256": B2.MANIFEST_CONTRACT_SHA256,
            "checkpoint_sha256": checkpoint_sha256,
            "checkpoint_binding": checkpoint["binding"],
            "input_case_count": EXPECTED_CASE_COUNT,
            "bfr_case_count": EXPECTED_BFR_CASE_COUNT,
            "far_comparator_case_count": EXPECTED_FAR_CASE_COUNT,
        },
        "observations": {
            "bfr_six_rows_examined": row_count,
            "bfr_coefficient_terms_examined": coefficient_term_count,
            "retained_coefficient_mutation_or_omission_count": 0,
            "missing_or_changed_source_id_count": 0,
            "missing_anchor_count": 0,
            "constant_field_challenges": list(CONSTANT_FIELD_CHALLENGES),
            "constant_field_failure_count": 0,
            "structural_invariant_residual": 0.0,
            "raw_bfr_failing_case_count": raw_failing_case_count,
            "raw_bfr_failing_row_count": raw_failing_row_count,
            "raw_bfr_max_ordered_sum_residual": max_raw_ordered_residual,
            "raw_bfr_max_fsum_residual": max_fsum_residual,
            "maximum_actual_coordinate_operator_delta":
                max_actual_coordinate_delta,
            "maximum_centered_normalized_operator_delta":
                max_centered_normalized_delta,
            "maximum_delta_observation": max_delta_observation,
            "cache_mode_bitwise_equal_pair_count": cache_pair_count,
            "canonical_representation_sha256":
                representation_digest.hexdigest(),
        },
        "prohibitions": {
            "post_hoc_normalization_applied": False,
            "row_or_force_tolerance_changed": False,
            "d10_input_changed": False,
            "six_row_contract_changed": False,
            "far_selected_or_promoted": False,
            "b3_implemented": False,
            "production_route_added_or_activated": False,
        },
        "decisions": {
            "architecture_selected": False,
            "scientific_adequacy_decided": False,
            "d9a_reopened": False,
            "d9b_decided": False,
            "required_next_gate":
                "exact-SHA technical, scientific, and gatekeeper review, then explicit user architecture decision",
        },
    }


def self_test_report():
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "invariant_row_representation_preflight_self_test",
        "status": "ok",
        "representation": REPRESENTATION,
        "row_invariant_tolerance": ROW_INVARIANT_TOLERANCE,
        "six_row_order": list(ROW_ORDER),
        "expected_case_count": EXPECTED_CASE_COUNT,
        "expected_bfr_case_count": EXPECTED_BFR_CASE_COUNT,
        "expected_far_comparator_case_count": EXPECTED_FAR_CASE_COUNT,
        "post_hoc_normalization_permitted": False,
        "architecture_selection_permitted": False,
        "production_activation_permitted": False,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--checkpoint")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--expected-binding-head")
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.self_test:
            require(not args.checkpoint and not args.artifact_dir and
                    not args.expected_binding_head and not args.output,
                    "self-test does not accept evidence inputs")
            report = self_test_report()
        else:
            require(args.checkpoint and args.artifact_dir,
                    "analysis requires checkpoint and artifact directory")
            expected_head = args.expected_binding_head or exact_git_head()
            require(re.fullmatch(r"[0-9a-f]{40}", expected_head) is not None,
                    "expected binding head is malformed")
            report = analyze(args.checkpoint, args.artifact_dir, expected_head)
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
        if args.output:
            pathlib.Path(args.output).write_text(encoded, encoding="utf-8")
        if args.json or not args.output:
            sys.stdout.write(encoded)
        return 0
    except (PreflightError, B2.QualificationError, OSError, ValueError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        failure = {"schema_version": SCHEMA_VERSION,
                   "kind": "invariant_row_representation_preflight",
                   "status": "failed", "error": str(error)}
        sys.stderr.write(json.dumps(failure, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
