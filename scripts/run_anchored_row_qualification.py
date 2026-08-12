#!/usr/bin/env python3
"""Fail-closed B2c proof runner for ``anchored_difference_rows_v1``.

The runner validates the frozen B2 corpus and the executable representation
boundary.  The repository does not contain the independently certified primary
eigenanalysis plus uniform-refinement oracle required by B2b.  That absence is
reported as ``UNCOVERED`` and forces ``INCOMPLETE``; this program cannot emit a
qualification PASS, reopen D9a, select Far, unblock B3, or authorize production.
"""

from __future__ import print_function

import argparse
import copy
import datetime
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
from decimal import Decimal, localcontext
from fractions import Fraction


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "scripts/anchored_row_qualification_report_v1.schema.json"
B2A_PATH = ROOT / "scripts/run_invariant_row_representation_preflight.py"
B2A_SPEC = importlib.util.spec_from_file_location("b2a_preflight", B2A_PATH)
B2A = importlib.util.module_from_spec(B2A_SPEC)
B2A_SPEC.loader.exec_module(B2A)
B2 = B2A.B2

SCHEMA_ID = "anchored-row-qualification-report-v1"
CANDIDATE = "anchored_difference_rows_v1"
APPROVED_B2B_MERGE = "022df7a8e11bcc4aee4df2254cc994cf4efdeb4f"
ZERO_SHA256 = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
ROW_ORDER = ("position", "du", "dv", "duu", "duv", "dvv")
ANCHORS = ("v0", "v1", "v2")
RELABELS = ("identity", "rank_reverse", "rank_rotate_1")
CHALLENGES = ("negative_2p20", "negative_one", "positive_2p20",
              "positive_one", "positive_zero")
CANDIDATE_CHALLENGES = CHALLENGES
D10 = {"position": 5.0e-6, "first_derivative": 2.5e-5,
       "second_derivative": 1.25e-4}
COMPONENT_TARGETS = {"position": 5.0e-7, "first_derivative": 2.5e-6,
                     "second_derivative": 1.25e-5}
FROZEN_FIXTURE_SHA256 = {
    "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json": "bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b",
    "data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/candidate_metadata.json": "e92b244806eaecd9230a3f3f9977f61ddeff3875ee6550c2dfbdb211a8e05e04",
    "data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/faces.csv": "c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486",
    "data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/vertices.csv": "b275aac1d1b422a131c3703eb7f56fd4d5bf21230b277835774bc27405d10a4e",
    "data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/candidate_metadata.json": "f974fb5bb1d542561672c1e7d2d52bf5220acc09dd3b5510dc14f1d98343b0b5",
    "data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/faces.csv": "d72e02a882c536643e8a3405efe8bb32c745bc034cbc55dcc1af0d5eba11e1b8",
    "data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/vertices.csv": "cb6c618c254b36bbe27ff354f5dc009222e95277188833a3385a4f3c378b0bd6",
    "data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/candidate_metadata.json": "11aba5339fced78cab1056b99d03766ecf3b0a7178e1c04c5376f1af01f2cf1c",
    "data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/faces.csv": "7797a1ded38d99e83707fb85e23a2a193c5857f7425a5f678ceccb1506c67cd0",
    "data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/vertices.csv": "923914e925eaf0f60eb9a087f0150ad37b9e56bf0191ffc52b5d7fbd91b2903c",
    "data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/candidate_metadata.json": "6afd2ec0c0df1cd71a8597fa78889dbf9daea9627d10b97165acec1cd39f9cb0",
    "data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/faces.csv": "c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486",
    "data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/vertices.csv": "bbce1680eb4006622e14dd5d724134df826471bb55e0332c19a208b5e92429a5",
    "data/fixtures/candidates/b2p_adjacent_extraordinary/candidate_metadata.json": "de6bf74052e24f26049c3d194570a081d47bd5dcd278ad9b34c6b1cf39973d1b",
    "data/fixtures/candidates/b2p_adjacent_extraordinary/faces.csv": "1ecbe26328311f99b2e55ccdc7e1d614947099fe1fff124cfca83dc62f5dddbb",
    "data/fixtures/candidates/b2p_adjacent_extraordinary/vertices.csv": "b650ff4c1aed263701d25305d846f520933a2deb457655558f17a855e65c88b7",
    "data/fixtures/candidates/b2p_single_flip_family/base/candidate_metadata.json": "66c9ab55624afb0f7fc8b444e6e5d9479bde356483bb11a73e0d5c6ce3edd35d",
    "data/fixtures/candidates/b2p_single_flip_family/base/faces.csv": "bcc295b8c7e972982676afedb7ead94bbddfd4702f6d638a070630c9f32f7672",
    "data/fixtures/candidates/b2p_single_flip_family/base/vertices.csv": "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_single_flip_family/family_metadata.json": "c8ac7ea89681b72508a29b2bca8f8b97ef2c65acab6aebe19445ae8eb7136fa2",
    "data/fixtures/candidates/b2p_single_flip_family/flip_000/candidate_metadata.json": "226312a46cb6f611efa54866b37787a01b68aa783d614936982b407bf0dc55d9",
    "data/fixtures/candidates/b2p_single_flip_family/flip_000/faces.csv": "744b5a91acbdf6926890eb378dd7410a580155bd84ffb583c49d63a6a56fca76",
    "data/fixtures/candidates/b2p_single_flip_family/flip_000/vertices.csv": "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_single_flip_family/flip_001/candidate_metadata.json": "b0315a513777cad7fb5f5ba9eed395959e3bce6848283c07cf7d7f0fccde974e",
    "data/fixtures/candidates/b2p_single_flip_family/flip_001/faces.csv": "58d78e761bcfb8172eff55084ad99968c14089ba08b2af78f3504ba621c9bc74",
    "data/fixtures/candidates/b2p_single_flip_family/flip_001/vertices.csv": "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_single_flip_family/flip_002/candidate_metadata.json": "a66f2872f64ca861ca6648118aa4981482fc5f247742c5c189ecc906288f934e",
    "data/fixtures/candidates/b2p_single_flip_family/flip_002/faces.csv": "7ee844bfaec6aad97892673d63c7a00522e141db3dc707b6615be6852fd83727",
    "data/fixtures/candidates/b2p_single_flip_family/flip_002/vertices.csv": "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_valence789/candidate_metadata.json": "f6a88b98adec1a90f4d591b9711aa20fd724b14755beadf064e42af8328a381b",
    "data/fixtures/candidates/b2p_valence789/faces.csv": "bcc295b8c7e972982676afedb7ead94bbddfd4702f6d638a070630c9f32f7672",
    "data/fixtures/candidates/b2p_valence789/vertices.csv": "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/closed_mixed_valence345/candidate_metadata.json": "74ae00951e6ea20021722a45a887d0c47530d4d7248cb69f553cb1a66a60f14b",
    "data/fixtures/candidates/closed_mixed_valence345/faces.csv": "bc1db1bf7fb29e4e4bc7b41f93ea9c206fe80a022736f1f02d22063c0b800233",
    "data/fixtures/candidates/closed_mixed_valence345/vertices.csv": "affa93eec68b8de9d5dcd12d31bf1d7222410722b0cca44c58495c558e3d7287",
    "data/fixtures/candidates/closed_valence3_tetrahedron/candidate_metadata.json": "3b2cf28dd5b4b52ea5a999e07fc89527513066ac8f2ef20b52137448fcb52660",
    "data/fixtures/candidates/closed_valence3_tetrahedron/faces.csv": "acfbd18a1922e465052f6badf5aa2567faa282add3edc7867f3bca7493e6e1aa",
    "data/fixtures/candidates/closed_valence3_tetrahedron/vertices.csv": "4a82e312830953d67731970042f5cf7d174e6af9f8844b7cd2b321209e51b898",
    "data/fixtures/candidates/closed_valence4_octahedron/candidate_metadata.json": "2109779d724d924ac416a127fa4a376cf1a72fbe9fa1391223995ebbccb60b74",
    "data/fixtures/candidates/closed_valence4_octahedron/faces.csv": "af9742137b89c25cc29e8b60e137967d8adfcdd80f33d3172fc13f1ed93838e8",
    "data/fixtures/candidates/closed_valence4_octahedron/vertices.csv": "b650ff4c1aed263701d25305d846f520933a2deb457655558f17a855e65c88b7",
    "data/fixtures/closed_valence5/faces.csv": "561b3ec0c4aa6b1e684ef87c2738d8c20a474225bd4960a4a672d306a3e70327",
    "data/fixtures/closed_valence5/vertices.csv": "d0dae733433503f9e2aba4f8eda80fa2d6842d0f5a7b922d7ffce158f505cb45",
}

CRITERION_IDS = (
    "bindings_and_independence",
    "complete_artifact_inventory",
    "raw_bfr_d9a_reproduction",
    "representation_structure",
    "constant_field_bits",
    "relabel_exact_effective_coefficients",
    "regular_analytic_exact_rows",
    "regular_analytic_emitted_geometry",
    "regular_analytic_area_integrand",
    "regular_analytic_legacy_volume_integrand",
    "oracle_coverage_and_crosscheck",
    "exact_effective_d10_coeff",
    "exact_effective_d10_geometry",
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
    "stabilization_7_8_emitted_geometry",
    "cache_mode_bit_identity",
    "d12_preparation_cost",
    "d12_retained_payload",
    "d12_peak_rss",
    "d12_cache_disabled_concurrency",
    "d12_instrumented_tsan",
)

INFRASTRUCTURE_CRITERIA = frozenset(CRITERION_IDS[:3])
ORACLE_CRITERIA = frozenset(("oracle_coverage_and_crosscheck",))
D12_CRITERIA = frozenset(CRITERION_IDS[27:])
CANDIDATE_SCIENTIFIC_CRITERIA = frozenset(CRITERION_IDS[3:27]) - ORACLE_CRITERIA
CATEGORICAL_CRITERIA = frozenset((
    "bindings_and_independence", "complete_artifact_inventory",
    "raw_bfr_d9a_reproduction", "representation_structure",
    "constant_field_bits", "relabel_exact_effective_coefficients",
    "cache_mode_bit_identity",
))

# Exact formula cardinalities that are independent of numerical results.
EXPECTED_CELL_COUNTS = {
    "bindings_and_independence": 1,
    "complete_artifact_inventory": 294,
    "raw_bfr_d9a_reproduction": 196,
    "representation_structure": 4158000,
    "constant_field_bits": 62370000,
    "relabel_exact_effective_coefficients": 8316000,
    "regular_analytic_exact_rows": 152640,
    "regular_analytic_emitted_geometry": 457920,
    "regular_analytic_area_integrand": 50880,
    "regular_analytic_legacy_volume_integrand": 50880,
    "oracle_coverage_and_crosscheck": 1188000,
    "exact_effective_d10_coeff": 1188000,
    "exact_effective_d10_geometry": 3564000,
    "emitted_direct_geometry_d10": 3564000,
    "anchor_sensitivity_exact_coeff": 1188000,
    "anchor_sensitivity_exact_geometry": 3564000,
    "anchor_sensitivity_emitted_geometry": 3564000,
    # One result cell for every source-basis contribution in each frozen
    # anchor/relabel group.  The criterion decision is made on the exact L1
    # sum of those contributions, not on each contribution independently.
    "binary64_basis_probe_diagnostic": 32271264,
    "binary64_direct_geometry_fidelity": 10692000,
    "relabel_emitted_geometry_fidelity": 7128000,
    "stabilization_6_7_exact_coeff": 594000,
    "stabilization_6_7_exact_geometry": 1782000,
    "stabilization_6_7_emitted_geometry": 1782000,
    "stabilization_7_8_exact_coeff": 594000,
    "stabilization_7_8_exact_geometry": 1782000,
    "stabilization_7_8_emitted_geometry": 1782000,
    "cache_mode_bit_identity": 2079000,
    "d12_preparation_cost": 3136,
    "d12_retained_payload": 5964,
    "d12_peak_rss": 4179364,
    "d12_cache_disabled_concurrency": 13720,
    "d12_instrumented_tsan": 14896,
}

STATUSES = {
    "PASS", "FAIL", "INCOMPLETE", "UNCOVERED",
    "OMITTED_AFTER_CANDIDATE_FAILURE",
    "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
}
NON_PRESENT_REASONS = {
    "MISSING": {"EXPECTED_PATH_MISSING"},
    "UNAVAILABLE": {"DEPENDENCY_UNAVAILABLE", "TOOL_UNAVAILABLE",
                    "PLATFORM_UNAVAILABLE", "GIT_IDENTITY_UNAVAILABLE",
                    "EXECUTION_UNAVAILABLE"},
    "INVALID": {"HASH_MISMATCH", "SCHEMA_INVALID", "PROVENANCE_INVALID",
                "CONTENT_INVALID", "WORKTREE_DIRTY",
                "MEASUREMENT_PROTOCOL_INVALID"},
}
ORACLE_UNCOVERED_REASONS = {
    "ORACLE_INDEPENDENCE_AUDIT_FAILED", "MPFR_4_2_2_UNAVAILABLE",
    "MPFR_VERSION_MISMATCH", "DIRECTED_INTERVAL_PRIMITIVE_FAILED",
    "INTERVAL_BRANCH_ORDERING_UNCERTIFIED", "NO_ISOLATION_BY_DEPTH_12",
    "EIGENBASIS_CERTIFICATION_FAILED", "PARAMETRIC_MAP_CHECK_FAILED",
    "REGULAR_SUPPORT_NOT_REACHED_BY_DEPTH_30", "UNIFORM_CROSSCHECK_FAILED",
    "TANGENT_PROJECTION_CHECK_FAILED", "EMPTY_INTERVAL_INTERSECTION",
    "ORACLE_MIDPOINT_NONFINITE", "ORACLE_MIDPOINT_BINARY64_IMPORT_INEXACT",
    "NORMALIZATION_LENGTH_NONPOSITIVE", "ORACLE_UNCERTAINTY_BOUND_EXCEEDED",
    "ORACLE_SERIALIZATION_BOUND_EXCEEDED",
}


class QualificationError(RuntimeError):
    """A fail-closed contract or evidence error."""


def require(condition, message):
    if not condition:
        raise QualificationError(message)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise QualificationError("duplicate JSON key: {}".format(key))
        result[key] = value
    return result


def strict_json_bytes(raw):
    def reject_constant(value):
        raise QualificationError("nonfinite JSON number: {}".format(value))
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=strict_pairs,
                          parse_constant=reject_constant)
    except UnicodeDecodeError as error:
        raise QualificationError("JSON is not UTF-8") from error


def _jcs_number(value):
    require(not isinstance(value, bool), "boolean used as JCS number")
    if isinstance(value, int):
        return str(value)
    require(isinstance(value, float) and math.isfinite(value),
            "JCS number is nonfinite or not numeric")
    require(not (value == 0.0 and math.copysign(1.0, value) < 0.0),
            "negative zero is forbidden")
    if value == 0.0:
        return "0"
    absolute = abs(value)
    rendered = repr(value).lower()
    if 1.0e-6 <= absolute < 1.0e21:
        fixed = format(Decimal(rendered), "f")
        if "." in fixed:
            fixed = fixed.rstrip("0").rstrip(".")
        return fixed
    mantissa, exponent = rendered.split("e") if "e" in rendered else (rendered, "0")
    mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
    exponent_value = int(exponent)
    return "{}e{}{}".format(mantissa, "+" if exponent_value >= 0 else "",
                             exponent_value)


def jcs_bytes(value):
    """Return the RFC-8785 form for this report's I-JSON value domain."""
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _jcs_number(value).encode("ascii")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if isinstance(value, list):
        return b"[" + b",".join(jcs_bytes(item) for item in value) + b"]"
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "JCS object key is not a string")
        ordered = sorted(value, key=lambda key: key.encode("utf-16-be"))
        return b"{" + b",".join(jcs_bytes(key) + b":" + jcs_bytes(value[key])
                                  for key in ordered) + b"}"
    raise QualificationError("unsupported JCS type")


def load_schema():
    schema = strict_json_bytes(SCHEMA_PATH.read_bytes())
    require(schema.get("$id", "").endswith(SCHEMA_ID), "report schema ID drift")
    return schema


def _matches_type(value, expected):
    if expected == "null": return value is None
    if expected == "object": return isinstance(value, dict)
    if expected == "array": return isinstance(value, list)
    if expected == "string": return isinstance(value, str)
    if expected == "boolean": return isinstance(value, bool)
    if expected == "integer": return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number": return (isinstance(value, (int, float)) and
                                      not isinstance(value, bool) and
                                      (not isinstance(value, float) or math.isfinite(value)))
    raise QualificationError("unsupported schema type {}".format(expected))


def validate_schema_instance(value, schema=None, root=None, path="$" ):
    """Small executable validator for every keyword used by the frozen schema."""
    if schema is None:
        schema = load_schema()
    if root is None:
        root = schema
    if "$ref" in schema:
        prefix = "#/$defs/"
        require(schema["$ref"].startswith(prefix), "external schema reference forbidden")
        return validate_schema_instance(value, root["$defs"][schema["$ref"][len(prefix):]], root, path)
    if "not" in schema:
        try:
            validate_schema_instance(value, schema["not"], root, path)
        except QualificationError:
            pass
        else:
            raise QualificationError("{} violates not".format(path))
    for clause in schema.get("allOf", []):
        if "if" not in clause:
            validate_schema_instance(value, clause, root, path)
            continue
        condition_matches = True
        if "if" in clause:
            try:
                validate_schema_instance(value, clause["if"], root, path)
            except QualificationError:
                condition_matches = False
        if condition_matches and "then" in clause:
            validate_schema_instance(value, clause["then"], root, path)
    if "const" in schema:
        require(value == schema["const"], "{} violates const".format(path))
    if "enum" in schema:
        require(value in schema["enum"], "{} violates enum".format(path))
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        require(any(_matches_type(value, item) for item in types),
                "{} has wrong type".format(path))
    if isinstance(value, dict):
        required = schema.get("required", [])
        require(all(key in value for key in required), "{} misses required key".format(path))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            require(set(value).issubset(properties), "{} contains extra key".format(path))
        for key, item in value.items():
            if key in properties:
                validate_schema_instance(item, properties[key], root, path + "." + key)
    if isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0), "{} has too few items".format(path))
        if "maxItems" in schema:
            require(len(value) <= schema["maxItems"], "{} has too many items".format(path))
        prefix_items = schema.get("prefixItems", [])
        for index, item_schema in enumerate(prefix_items):
            if index < len(value):
                validate_schema_instance(value[index], item_schema, root,
                                         "{}[{}]".format(path, index))
        if schema.get("items") is False:
            require(len(value) <= len(prefix_items), "{} has forbidden tail items".format(path))
        elif "items" in schema:
            for index, item in enumerate(value):
                if index >= len(prefix_items):
                    validate_schema_instance(item, schema["items"], root,
                                             "{}[{}]".format(path, index))
    if isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), "{} string too short".format(path))
        if "pattern" in schema:
            require(re.fullmatch(schema["pattern"], value) is not None,
                    "{} violates pattern".format(path))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        require(not isinstance(value, float) or math.isfinite(value), "{} nonfinite".format(path))
        if "minimum" in schema:
            require(value >= schema["minimum"], "{} below minimum".format(path))
        if "maximum" in schema:
            require(value <= schema["maximum"], "{} above maximum".format(path))
    return True


def availability(state, sha256=None, reason_code=None):
    require(state in {"PRESENT", "MISSING", "UNAVAILABLE", "INVALID"},
            "availability state")
    if state == "PRESENT":
        require(SHA256_RE.fullmatch(sha256 or "") is not None and sha256 != ZERO_SHA256,
                "present availability needs real SHA-256")
        require(reason_code is None, "present availability forbids reason")
    else:
        require(sha256 is None, "non-present availability forbids SHA-256")
        require(reason_code in NON_PRESENT_REASONS[state], "availability reason/state mismatch")
    return {"state": state, "sha256": sha256, "reason_code": reason_code}


def git_identity(state, commit=None, reason_code=None):
    if state == "PRESENT":
        require(GIT_RE.fullmatch(commit or "") is not None, "present Git identity malformed")
        require(reason_code is None, "present Git identity forbids reason")
    else:
        require(commit is None and reason_code in NON_PRESENT_REASONS[state],
                "non-present Git identity mismatch")
    return {"state": state, "git_commit": commit, "reason_code": reason_code}


def worktree_observation(clean):
    if clean:
        return {"state": "PRESENT", "clean": True, "reason_code": None}
    return {"state": "INVALID", "clean": None, "reason_code": "WORKTREE_DIRTY"}


def binary64_bits_hex(value):
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and
            math.isfinite(float(value)), "binary64 value invalid")
    return struct.pack(">d", float(value)).hex()


def binary64_from_bits_hex(label):
    require(isinstance(label, str) and re.fullmatch(r"[0-9a-f]{16}", label),
            "binary64 bit label")
    value = struct.unpack(">d", bytes.fromhex(label))[0]
    require(math.isfinite(value), "nonfinite binary64 bit label")
    return value


def exact_binary64_numerator(value):
    """Decode finite binary64 exactly over the common denominator 2^1074."""
    bits = struct.unpack(">Q", struct.pack(">d", float(value)))[0]
    exponent = (bits >> 52) & 0x7ff
    fraction = bits & ((1 << 52) - 1)
    require(exponent != 0x7ff, "nonfinite exact dyadic")
    numerator = fraction if exponent == 0 else ((1 << 52) | fraction) << (exponent - 1)
    return -numerator if bits >> 63 else numerator


def effective_numerators(row, anchor_source_id):
    source_ids = row["source_ids"]
    coefficients = row["coefficients"]
    require(source_ids == sorted(set(source_ids)) and anchor_source_id in source_ids,
            "effective row source/anchor invalid")
    values = [exact_binary64_numerator(value) for value in coefficients]
    target = (1 << 1074) if row["row_kind"] == "position" else 0
    values[source_ids.index(anchor_source_id)] += target - sum(values)
    require(sum(values) == target, "effective exact sum failed")
    return dict(zip(source_ids, values))


class RationalJet:
    """Exact value, first, and second derivatives in two parameters."""

    def __init__(self, value=0, du=0, dv=0, duu=0, duv=0, dvv=0):
        self.values = tuple(Fraction(item) for item in
                            (value, du, dv, duu, duv, dvv))

    @staticmethod
    def coerce(value):
        return value if isinstance(value, RationalJet) else RationalJet(value)

    def __add__(self, other):
        other = self.coerce(other)
        return RationalJet(*(left + right for left, right in
                             zip(self.values, other.values)))

    __radd__ = __add__

    def __neg__(self):
        return RationalJet(*(-item for item in self.values))

    def __sub__(self, other):
        return self + (-self.coerce(other))

    def __rsub__(self, other):
        return self.coerce(other) - self

    def __mul__(self, other):
        other = self.coerce(other)
        a, au, av, auu, auv, avv = self.values
        b, bu, bv, buu, buv, bvv = other.values
        return RationalJet(
            a * b,
            au * b + a * bu,
            av * b + a * bv,
            auu * b + 2 * au * bu + a * buu,
            auv * b + au * bv + av * bu + a * buv,
            avv * b + 2 * av * bv + a * bvv)

    __rmul__ = __mul__

    def __truediv__(self, other):
        require(not isinstance(other, RationalJet) and Fraction(other) != 0,
                "rational jet divisor")
        return self * (Fraction(1, 1) / Fraction(other))

    def __pow__(self, exponent):
        require(type(exponent) is int and exponent >= 0,
                "rational jet exponent")
        result = RationalJet(1)
        for _ in range(exponent):
            result = result * self
        return result


def regular_box_spline_rows(s, t):
    """Return the exact 6x12 quartic Loop box-spline rows at ``(s,t)``."""
    v = RationalJet(Fraction(s), 1, 0)
    w = RationalJet(Fraction(t), 0, 1)
    u = 1 - v - w
    basis = [
        (u ** 4 + 2 * u ** 3 * v) / 12,
        (u ** 4 + 2 * u ** 3 * w) / 12,
        (u ** 4 + 2 * u ** 3 * w + 6 * u ** 3 * v +
         6 * u ** 2 * v * w + 12 * u ** 2 * v ** 2 +
         6 * u * v ** 2 * w + 6 * u * v ** 3 +
         2 * v ** 3 * w + v ** 4) / 12,
        (6 * u ** 4 + 24 * u ** 3 * w + 24 * u ** 2 * w ** 2 +
         8 * u * w ** 3 + w ** 4 + 24 * u ** 3 * v +
         60 * u ** 2 * v * w + 36 * u * v * w ** 2 +
         6 * v * w ** 3 + 24 * u ** 2 * v ** 2 +
         36 * u * v ** 2 * w + 12 * v ** 2 * w ** 2 +
         8 * u * v ** 3 + 6 * v ** 3 * w + v ** 4) / 12,
        (u ** 4 + 6 * u ** 3 * w + 12 * u ** 2 * w ** 2 +
         6 * u * w ** 3 + w ** 4 + 2 * u ** 3 * v +
         6 * u ** 2 * v * w + 6 * u * v * w ** 2 +
         2 * v * w ** 3) / 12,
        (2 * u * v ** 3 + v ** 4) / 12,
        (u ** 4 + 6 * u ** 3 * w + 12 * u ** 2 * w ** 2 +
         6 * u * w ** 3 + w ** 4 + 8 * u ** 3 * v +
         36 * u ** 2 * v * w + 36 * u * v * w ** 2 +
         8 * v * w ** 3 + 24 * u ** 2 * v ** 2 +
         60 * u * v ** 2 * w + 24 * v ** 2 * w ** 2 +
         24 * u * v ** 3 + 24 * v ** 3 * w + 6 * v ** 4) / 12,
        (u ** 4 + 8 * u ** 3 * w + 24 * u ** 2 * w ** 2 +
         24 * u * w ** 3 + 6 * w ** 4 + 6 * u ** 3 * v +
         36 * u ** 2 * v * w + 60 * u * v * w ** 2 +
         24 * v * w ** 3 + 12 * u ** 2 * v ** 2 +
         36 * u * v ** 2 * w + 24 * v ** 2 * w ** 2 +
         6 * u * v ** 3 + 8 * v ** 3 * w + v ** 4) / 12,
        (2 * u * w ** 3 + w ** 4) / 12,
        (2 * v ** 3 * w + v ** 4) / 12,
        (2 * u * w ** 3 + w ** 4 + 6 * u * v * w ** 2 +
         6 * v * w ** 3 + 6 * u * v ** 2 * w +
         12 * v ** 2 * w ** 2 + 2 * u * v ** 3 +
         6 * v ** 3 * w + v ** 4) / 12,
        (w ** 4 + 2 * v * w ** 3) / 12,
    ]
    rows = [[item.values[index] for item in basis] for index in range(6)]
    require(sum(rows[0]) == 1 and all(sum(row) == 0 for row in rows[1:]),
            "analytic box-spline sum rule")
    return rows


def relabel_maps(vertex_count):
    require(type(vertex_count) is int and vertex_count > 0, "vertex count")
    return {
        "identity": {index: index for index in range(vertex_count)},
        "rank_reverse": {index: vertex_count - 1 - index for index in range(vertex_count)},
        "rank_rotate_1": {index: (index + 1) % vertex_count for index in range(vertex_count)},
    }


def relabel_row(row, mapping):
    entries = sorted((mapping[source], coefficient)
                     for source, coefficient in zip(row["source_ids"], row["coefficients"]))
    result = dict(row)
    result["source_ids"] = [item[0] for item in entries]
    result["coefficients"] = [item[1] for item in entries]
    return result


def canonical_cell_key_bytes(key):
    validate_scientific_cell_key(key)
    return jcs_bytes(key)


def validate_scientific_cell_key(key, criterion_id=None):
    require(isinstance(key, list) and len(key) == 15, "scientific cell key arity")
    validate_schema_instance(key, load_schema()["$defs"]["scientificKey"], load_schema())
    (content_id, cache_mode, level, face_id, local_corner, sample_id, quantity,
     view, anchor, relabel, basis_source_id, axis, anchor_pair, transition,
     challenge) = key
    require(content_id and sample_id and type(level) is int and type(face_id) is int,
            "scientific key identity")
    if criterion_id is None:
        return True
    require(criterion_id in CRITERION_IDS and not criterion_id.startswith("d12_"),
            "scientific criterion ID")
    require(criterion_id not in {"bindings_and_independence",
                                 "complete_artifact_inventory",
                                 "raw_bfr_d9a_reproduction"},
            "infrastructure criterion does not use a scientific key")
    pair_criteria = {"anchor_sensitivity_exact_coeff",
                     "anchor_sensitivity_exact_geometry",
                     "anchor_sensitivity_emitted_geometry"}
    stabilization = {item for item in CRITERION_IDS if item.startswith("stabilization_")}
    require((anchor_pair is not None) == (criterion_id in pair_criteria),
            "anchor-pair nullable dimension")
    require((transition is not None) == (criterion_id in stabilization),
            "transition nullable dimension")
    if criterion_id.startswith("stabilization_6_7"):
        require(transition == "6_7", "6->7 transition key")
    if criterion_id.startswith("stabilization_7_8"):
        require(transition == "7_8", "7->8 transition key")
    require((challenge is not None) == (criterion_id == "constant_field_bits"),
            "constant challenge nullable dimension")
    require((basis_source_id is not None) ==
            (criterion_id == "binary64_basis_probe_diagnostic"),
            "basis-source nullable dimension")
    direct_axis_criteria = {
        "regular_analytic_emitted_geometry",
        "exact_effective_d10_geometry", "emitted_direct_geometry_d10",
        "anchor_sensitivity_exact_geometry", "anchor_sensitivity_emitted_geometry",
        "binary64_direct_geometry_fidelity", "relabel_emitted_geometry_fidelity",
        "stabilization_6_7_exact_geometry", "stabilization_6_7_emitted_geometry",
        "stabilization_7_8_exact_geometry", "stabilization_7_8_emitted_geometry",
    }
    require((axis is not None) == (criterion_id in direct_axis_criteria),
            "axis nullable dimension")
    integrand_criteria = {
        "regular_analytic_area_integrand": "area_integrand",
        "regular_analytic_legacy_volume_integrand":
            "legacy_volume_integrand",
    }
    if criterion_id in integrand_criteria:
        require(quantity == integrand_criteria[criterion_id] and axis is None and
                view in ("exact_effective", "emitted_binary64"),
                "regular integrand quantity/view dimensions")
    else:
        require(quantity in ROW_ORDER, "row criterion quantity")
    if quantity in ("area_integrand", "legacy_volume_integrand"):
        require(axis is None, "scalar integrand axis must be null")
    exact_view = {
        "relabel_exact_effective_coefficients", "regular_analytic_exact_rows",
        "exact_effective_d10_coeff", "exact_effective_d10_geometry",
        "anchor_sensitivity_exact_coeff", "anchor_sensitivity_exact_geometry",
        "stabilization_6_7_exact_coeff", "stabilization_6_7_exact_geometry",
        "stabilization_7_8_exact_coeff", "stabilization_7_8_exact_geometry",
    }
    emitted_view = {
        "constant_field_bits", "regular_analytic_emitted_geometry",
        "emitted_direct_geometry_d10", "anchor_sensitivity_emitted_geometry",
        "binary64_basis_probe_diagnostic", "binary64_direct_geometry_fidelity",
        "relabel_emitted_geometry_fidelity",
        "stabilization_6_7_emitted_geometry",
        "stabilization_7_8_emitted_geometry",
    }
    if criterion_id == "representation_structure":
        require(view == "structural", "representation structure view")
    elif criterion_id in exact_view:
        require(view == "exact_effective", "exact criterion view")
    elif criterion_id in emitted_view:
        require(view == "emitted_binary64", "emitted criterion view")
    elif criterion_id in ("oracle_coverage_and_crosscheck",
                           "cache_mode_bit_identity"):
        require(view is None, "null-view criterion")

    if criterion_id in pair_criteria:
        require(anchor is None, "pairwise criterion uses anchor_pair, not anchor")
    else:
        require(anchor in ANCHORS, "criterion requires frozen anchor")

    if criterion_id == "constant_field_bits":
        require(relabel in RELABELS, "constant relabel coverage")
    elif criterion_id == "binary64_basis_probe_diagnostic":
        require(relabel in RELABELS,
                "basis-probe ledger requires all frozen relabelings")
    elif criterion_id == "binary64_direct_geometry_fidelity":
        require(relabel in RELABELS, "binary64 fidelity relabel coverage")
    elif criterion_id in ("relabel_exact_effective_coefficients",
                           "relabel_emitted_geometry_fidelity"):
        require(relabel in ("rank_reverse", "rank_rotate_1"),
                "relabel criterion excludes identity")
    elif criterion_id == "cache_mode_bit_identity":
        require(relabel is None, "cache-pair relabel must be null")
    else:
        require(relabel == "identity", "identity relabel required")

    if criterion_id == "cache_mode_bit_identity":
        require(cache_mode == "cache_pair", "cache identity mode")
    else:
        require(cache_mode in ("cache_disabled", "serial_cache"),
                "scientific cache mode")

    all_level_criteria = {"representation_structure", "constant_field_bits",
                          "relabel_exact_effective_coefficients",
                          "cache_mode_bit_identity"}
    if criterion_id in all_level_criteria:
        require(2 <= level <= 8, "all-level criterion range")
    elif criterion_id.startswith("stabilization_6_7"):
        require(level == 7, "6->7 key stores high level 7")
    elif criterion_id.startswith("stabilization_7_8"):
        require(level == 8, "7->8 key stores high level 8")
    else:
        require(level in (7, 8), "oracle/accuracy criterion level")
    return True


def validate_d12_key(key, criterion_id):
    require(isinstance(key, list) and len(key) == 14, "D12 key arity")
    schema = load_schema()
    validate_schema_instance(key, schema["$defs"]["d12Key"], schema)
    require(criterion_id in {item for item in CRITERION_IDS if item.startswith("d12_")},
            "D12 criterion ID")
    (content_id, level, profile, cache_mode, worker_count, worker_index, round_index,
     repeat_phase, repeat_index, face_id, local_corner, sample_id, sample_stage,
     quantity) = key
    require(content_id and 2 <= level <= 8, "D12 identity")
    if criterion_id == "d12_preparation_cost":
        require(profile == "release" and cache_mode in ("cache_disabled", "serial_cache") and
                worker_count is None and worker_index is None and round_index is None and
                face_id is None and local_corner is None and sample_id is None and
                sample_stage is None and quantity in
                ("preparation_duration_ns", "preparation_median_ns"),
                "D12 preparation dimensions")
        if quantity == "preparation_duration_ns":
            require(repeat_phase == "measured" and type(repeat_index) is int and
                    0 <= repeat_index <= 14,
                    "D12 measured repeat")
        else:
            require(repeat_phase is None and repeat_index is None,
                    "D12 median repeat dimensions")
    elif criterion_id == "d12_retained_payload":
        require(profile == "release" and cache_mode in ("cache_disabled", "serial_cache") and
                face_id is not None and quantity == "retained_payload_bytes" and
                all(item is None for item in (worker_count, worker_index, round_index,
                                              repeat_phase, repeat_index, local_corner,
                                              sample_id, sample_stage)),
                "D12 retained-payload dimensions")
    elif criterion_id == "d12_peak_rss":
        require(profile == "release" and cache_mode in ("cache_disabled", "serial_cache") and
                quantity == "rss_bytes" and worker_count is None and worker_index is None and
                round_index is None and sample_stage is not None,
                "D12 RSS dimensions")
        if sample_stage == "pre_refiner_baseline":
            require(repeat_phase is None and repeat_index is None and
                    face_id is None and local_corner is None and sample_id is None,
                    "D12 baseline RSS dimensions")
        else:
            require(sample_stage in {
                "after_refiner", "after_factory_cache", "after_face_insert",
                "after_package_publication", "after_package_destruction",
                "after_factory_cache_destruction", "after_refiner_destruction"},
                "D12 RSS stage")
            require(repeat_phase in ("warmup", "measured") and
                    type(repeat_index) is int and
                    0 <= repeat_index <= (2 if repeat_phase == "warmup" else 14),
                    "D12 RSS repeat dimensions")
            if sample_stage == "after_face_insert":
                require(face_id is not None and sample_id is not None,
                        "D12 face-insert identity")
            else:
                require(face_id is None and local_corner is None and sample_id is None,
                        "D12 non-face RSS identity must be null")
    elif criterion_id == "d12_cache_disabled_concurrency":
        require(profile == "tsan" and cache_mode == "cache_disabled" and
                worker_count in (1, 2, 4) and type(worker_index) is int and
                worker_index < worker_count and type(round_index) is int and
                repeat_phase is None and repeat_index is None and face_id is None and
                local_corner is None and sample_id is None and
                sample_stage == "thread_result" and quantity == "row_digest",
                "D12 cache-disabled concurrency dimensions")
    else:
        require(criterion_id == "d12_instrumented_tsan" and profile == "tsan" and
                cache_mode in ("cache_disabled", "threaded_cache") and
                worker_count in (1, 2, 4) and repeat_phase is None and
                repeat_index is None and face_id is None and local_corner is None and
                sample_id is None,
                "D12 instrumented dimensions")
        if sample_stage == "sanitizer_summary":
            require(worker_index is None and round_index is None and
                    quantity in ("instrumentation_coverage", "tsan_finding_count"),
                    "D12 sanitizer-summary dimensions")
        else:
            require(cache_mode == "threaded_cache" and
                    sample_stage == "thread_result" and quantity == "row_digest" and
                    type(worker_index) is int and worker_index < worker_count and
                    type(round_index) is int,
                    "D12 threaded row-digest dimensions")
    return True


def ledger_sha256(keys):
    encoded = sorted({canonical_cell_key_bytes(key) for key in keys})
    require(len(encoded) == len(keys), "duplicate scientific cell key")
    return sha256_bytes(b"[" + b",".join(encoded) + b"]")


def generic_key_ledger_sha256(keys):
    encoded = sorted({jcs_bytes(key) for key in keys})
    require(len(encoded) == len(keys), "duplicate generic ledger key")
    return sha256_bytes(b"[" + b",".join(encoded) + b"]")


class StreamingScientificLedger:
    """Hash one already-canonical, strictly ordered scientific key stream."""

    def __init__(self, criterion_id):
        self.criterion_id = criterion_id
        self.digest = hashlib.sha256()
        self.digest.update(b"[")
        self.count = 0
        self.previous = None

    def add_encoded(self, encoded):
        require(isinstance(encoded, bytes) and encoded.startswith(b"[") and
                encoded.endswith(b"]"), "scientific ledger key encoding")
        require(self.previous is None or self.previous < encoded,
                "{} ledger duplicate or order drift".format(self.criterion_id))
        if self.count:
            self.digest.update(b",")
        self.digest.update(encoded)
        self.previous = encoded
        self.count += 1

    def finish(self):
        require(self.count > 0, "empty executed scientific ledger")
        self.digest.update(b"]")
        return self.digest.hexdigest()


class StreamingJcsLedger:
    """Hash one already-sorted stream of arbitrary frozen JCS keys."""

    def __init__(self, label):
        self.label = label
        self.digest = hashlib.sha256()
        self.digest.update(b"[")
        self.count = 0
        self.previous = None

    def add_encoded(self, encoded):
        require(isinstance(encoded, bytes) and encoded.startswith(b"[") and
                encoded.endswith(b"]"), "generic ledger key encoding")
        require(self.previous is None or self.previous < encoded,
                "{} ledger duplicate or order drift".format(self.label))
        if self.count:
            self.digest.update(b",")
        self.digest.update(encoded)
        self.previous = encoded
        self.count += 1

    def finish(self):
        require(self.count > 0, "empty frozen key ledger")
        self.digest.update(b"]")
        return self.digest.hexdigest()


class StreamingResultLedger:
    """Hash canonical per-cell result records in frozen key order.

    A record is ``[key, outcome, exact_value, target, reason]``.  The exact
    value may be a closed integer/dyadic descriptor or a binary64 bit label;
    categorical and coverage records use null where no numerical value exists.
    """

    def __init__(self, label):
        self.label = label
        self.digest = hashlib.sha256()
        self.digest.update(b"[")
        self.count = 0
        self.previous_key = None

    def add_encoded(self, encoded_key, outcome, exact_value=None, target=None,
                    reason=None):
        require(isinstance(encoded_key, bytes) and
                encoded_key.startswith(b"[") and encoded_key.endswith(b"]"),
                "result-ledger key encoding")
        require(self.previous_key is None or self.previous_key < encoded_key,
                "{} result ledger duplicate or order drift".format(self.label))
        suffix = jcs_bytes([outcome, exact_value, target, reason])
        record = b"[" + encoded_key + b"," + suffix[1:]
        if self.count:
            self.digest.update(b",")
        self.digest.update(record)
        self.previous_key = encoded_key
        self.count += 1

    def finish(self, allow_empty=False):
        require(allow_empty or self.count > 0,
                "empty executed result ledger")
        self.digest.update(b"]")
        return self.digest.hexdigest()


def normalized_cache_mode(value):
    require(value in ("cache_disabled", "SurfaceFactoryCache_serial"),
            "unexpected Bfr cache mode")
    return ("cache_disabled" if value == "cache_disabled" else "serial_cache")


def scientific_base_prefix(case, row, cache_mode=None):
    local_corner = row["local_corner_or_none"]
    require(type(local_corner) is int and local_corner >= -1,
            "row local-corner encoding")
    base = [case["content_identity_key"],
            cache_mode or normalized_cache_mode(case["applicable_mode"]),
            case["approximation_level"], row["face_row"],
            None if local_corner == -1 else local_corner,
            row["sample_id"], row["row_kind"]]
    encoded = jcs_bytes(base)
    return encoded[:-1]


def scientific_suffix(view, anchor, relabel, challenge=None):
    # The base owns fields 0..6.  This is fields 7..14 plus the closing bracket.
    encoded = jcs_bytes([view, anchor, relabel, None, None, None, None, challenge])
    return b"," + encoded[1:]


def scientific_suffix_full(view, anchor, relabel, basis_source_id=None,
                           axis=None, anchor_pair=None, transition=None,
                           challenge=None):
    encoded = jcs_bytes([view, anchor, relabel, basis_source_id, axis,
                         anchor_pair, transition, challenge])
    return b"," + encoded[1:]


def scientific_prefix_for_quantity(case, row, quantity, cache_mode=None):
    local_corner = row["local_corner_or_none"]
    base = [case["content_identity_key"],
            cache_mode or normalized_cache_mode(case["applicable_mode"]),
            case["approximation_level"], row["face_row"],
            None if local_corner == -1 else local_corner,
            row["sample_id"], quantity]
    return jcs_bytes(base)[:-1]


def _artifact_report(artifact_root, case):
    path = pathlib.Path(artifact_root) / case["complete_json_artifact"]
    require(path.is_file(), "validated artifact disappeared before execution")
    try:
        raw = gzip.decompress(path.read_bytes())
    except (OSError, EOFError) as error:
        raise QualificationError("artifact gzip changed during execution") from error
    report = strict_json_bytes(raw)
    require(isinstance(report, dict) and isinstance(report.get("rows"), list),
            "artifact rows unavailable")
    return report


def ordered_bfr_cases(checkpoint):
    cases = [case for case in checkpoint["numeric_cases"]
             if case["candidate"] == "bfr"]
    cases.sort(key=lambda case: jcs_bytes([
        case["content_identity_key"],
        normalized_cache_mode(case["applicable_mode"]),
        case["approximation_level"],
    ]))
    require(len(cases) == 196, "ordered Bfr case count")
    return cases


def ordered_case_rows(report):
    return sorted(report["rows"], key=lambda row: jcs_bytes([
        row["face_row"],
        None if row["local_corner_or_none"] == -1 else
        row["local_corner_or_none"],
        row["sample_id"], row["row_kind"],
    ]))


def fixture_topology(manifest):
    result = {}
    for job in B2.valid_content_jobs(manifest):
        vertices, faces, _ = B2.independent_mesh(job)
        used_ids = sorted({source_id for face in faces for source_id in face})
        require(used_ids == list(range(len(vertices))),
                "fixture vertex IDs are not the frozen ascending contiguous rank list")
        result[job["content_identity_key"]] = (len(vertices), faces)
    require(len(result) == 14, "fixture topology inventory")
    return result


def regular_patch_inventory(manifest):
    """Derive the oriented 12-control regular patch from frozen topology."""
    result = {}
    for job in B2.valid_content_jobs(manifest):
        vertices, faces, valences = B2.independent_mesh(job)
        edge_opposites = {}
        for face in faces:
            for left, right, opposite in (
                    (face[0], face[1], face[2]),
                    (face[1], face[2], face[0]),
                    (face[2], face[0], face[1])):
                edge_opposites.setdefault(tuple(sorted((left, right))),
                                          []).append(opposite)

        def opposite(left, right, excluded):
            values = edge_opposites.get(tuple(sorted((left, right))), [])
            choices = [value for value in values if value != excluded]
            require(len(choices) == 1, "regular patch edge adjacency")
            return choices[0]

        patches = {}
        for face_index, face in enumerate(faces):
            if not all(valences[source_id] == 6 for source_id in face):
                continue
            d4, d7, d8 = face
            d3 = opposite(d4, d7, d8)
            d11 = opposite(d7, d8, d4)
            d5 = opposite(d4, d8, d7)
            patch = [
                opposite(d3, d4, d7),
                opposite(d4, d5, d8),
                d3, d4, d5,
                opposite(d3, d7, d4),
                d7, d8,
                opposite(d8, d5, d4),
                opposite(d7, d11, d8),
                d11,
                opposite(d8, d11, d7),
            ]
            require(len(patch) == 12 and len(set(patch)) == 12,
                    "regular patch source cardinality")
            patches[face_index] = patch
        result[job["content_identity_key"]] = {
            "vertices": vertices, "faces": faces, "patches": patches}
    require(len(result) == 14, "regular patch fixture count")
    return result


def regular_sample_rows(manifest):
    policy = next(item for item in manifest["sample_policies"]
                  if item["id"] == "regular_interior_l6_10")
    denominator = policy["lattice_denominator"]
    result = {
        sample["id"]: regular_box_spline_rows(
            Fraction(sample["u_numerator"], denominator),
            Fraction(sample["v_numerator"], denominator))
        for sample in policy["samples"]}
    require(len(result) == 10, "regular analytic sample count")
    return result


def iter_ordered_bfr_rows(checkpoint, artifact_root):
    for case in ordered_bfr_cases(checkpoint):
        report = _artifact_report(artifact_root, case)
        for row in ordered_case_rows(report):
            yield case, row


def candidate_audit_line(row, vertex_count, face):
    require(len(face) == 3 and all(type(value) is int for value in face),
            "oriented face anchor set")
    coefficients = ",".join(binary64_bits_hex(value)
                            for value in row["coefficients"])
    return "{} {} {} {} {}\n".format(
        row["row_kind"], vertex_count, ",".join(str(value) for value in face),
        ",".join(str(value) for value in row["source_ids"]), coefficients)


def _validate_suffix_definitions():
    definitions = {
        "representation_structure": [
            ("structural", anchor, "identity", None) for anchor in ANCHORS],
        "constant_field_bits": [
            ("emitted_binary64", anchor, relabel, challenge)
            for anchor in ANCHORS for relabel in RELABELS
            for challenge in CHALLENGES],
        "relabel_exact_effective_coefficients": [
            ("exact_effective", anchor, relabel, None)
            for anchor in ANCHORS for relabel in RELABELS[1:]],
        "cache_mode_bit_identity": [
            (None, anchor, None, None) for anchor in ANCHORS],
    }
    result = {}
    for criterion_id, dimensions in definitions.items():
        entries = []
        for view, anchor, relabel, challenge in dimensions:
            key = ["synthetic", ("cache_pair" if criterion_id ==
                                  "cache_mode_bit_identity" else "cache_disabled"),
                   7, 0, None, "sample", "position", view, anchor, relabel,
                   None, None, None, None, challenge]
            validate_scientific_cell_key(key, criterion_id)
            entries.append((scientific_suffix(view, anchor, relabel, challenge),
                            (view, anchor, relabel, challenge)))
        entries.sort(key=lambda item: item[0])
        require(len({item[0] for item in entries}) == len(entries),
                "duplicate criterion suffix definition")
        result[criterion_id] = entries
    return result


def _cache_row_signature(row):
    return (row["content_identity_key"], row["candidate"],
            row["approximation_level"], row["face_row"],
            row["local_corner_or_none"], row["sample_id"],
            row["u_binary64_bits_hex"], row["v_binary64_bits_hex"],
            row["weight_bits_hex"], row["row_kind"],
            tuple(row["source_ids"]),
            tuple(binary64_bits_hex(value) for value in row["coefficients"]))


def _failure_key(checkpoint, artifact_root, failure, criterion_id):
    if failure is None:
        return None
    require(set(failure) == {"anchor_index", "challenge_index", "relabel_index",
                             "row_ordinal"}, "candidate failure descriptor")
    ordinal = failure["row_ordinal"]
    require(type(ordinal) is int and ordinal >= 0, "candidate failure ordinal")
    selected = None
    for index, item in enumerate(iter_ordered_bfr_rows(checkpoint, artifact_root)):
        if index == ordinal:
            selected = item
            break
    require(selected is not None, "candidate failure ordinal outside matrix")
    case, row = selected
    anchor = ANCHORS[failure["anchor_index"]]
    if criterion_id == "representation_structure":
        view, relabel, challenge = "structural", "identity", None
    elif criterion_id == "constant_field_bits":
        view = "emitted_binary64"
        relabel = RELABELS[failure["relabel_index"]]
        challenge = CANDIDATE_CHALLENGES[failure["challenge_index"]]
    else:
        require(criterion_id == "relabel_exact_effective_coefficients",
                "failure criterion")
        view, challenge = "exact_effective", None
        relabel = RELABELS[failure["relabel_index"]]
    key = [case["content_identity_key"],
           normalized_cache_mode(case["applicable_mode"]),
           case["approximation_level"], row["face_row"],
           None if row["local_corner_or_none"] == -1 else
           row["local_corner_or_none"], row["sample_id"], row["row_kind"],
           view, anchor, relabel, None, None, None, None, challenge]
    validate_scientific_cell_key(key, criterion_id)
    return key


def _populate_cache_identity_ledger(checkpoint, artifact_root, topology,
                                    suffixes, ledger):
    """Build the cache pre-result ledger before candidate output is read."""
    results = StreamingResultLedger("cache_mode_bit_identity")
    by_identity = {(case["content_identity_key"], case["approximation_level"],
                    case["applicable_mode"]): case
                   for case in checkpoint["numeric_cases"]
                   if case["candidate"] == "bfr"}
    failure_count = 0
    first_failure = None
    for content_id in sorted(topology, key=lambda value: jcs_bytes(value)):
        for level in range(2, 9):
            disabled_case = by_identity[(content_id, level, "cache_disabled")]
            serial_case = by_identity[(content_id, level,
                                       "SurfaceFactoryCache_serial")]
            disabled_rows = ordered_case_rows(_artifact_report(artifact_root,
                                                                disabled_case))
            serial_rows = ordered_case_rows(_artifact_report(artifact_root,
                                                              serial_case))
            require(len(disabled_rows) == len(serial_rows),
                    "cache-pair row count drift")
            for disabled_row, serial_row in zip(disabled_rows, serial_rows):
                equal = (_cache_row_signature(disabled_row) ==
                         _cache_row_signature(serial_row))
                prefix = scientific_base_prefix(disabled_case, disabled_row,
                                                cache_mode="cache_pair")
                for suffix, dimensions in suffixes:
                    encoded_key = prefix + suffix
                    ledger.add_encoded(encoded_key)
                    results.add_encoded(
                        encoded_key, "PASS" if equal else "FAIL",
                        exact_value="B2ROWV1_BIT_IDENTITY",
                        target="BITWISE_EQUAL",
                        reason=None if equal else "CACHE_MODE_BITS_MISMATCH")
                    if not equal:
                        failure_count += 1
                        if first_failure is None:
                            _, anchor, _, _ = dimensions
                            first_failure = [
                                content_id, "cache_pair", level,
                                disabled_row["face_row"],
                                None if disabled_row["local_corner_or_none"] == -1
                                else disabled_row["local_corner_or_none"],
                                disabled_row["sample_id"], disabled_row["row_kind"],
                                None, anchor, None, None, None, None, None, None]
    return failure_count, first_failure, results.finish()


def execute_four_preoracle_criteria(candidate_binary, checkpoint, artifact_root,
                                    manifest):
    """Execute and ledger the four candidate-owned, non-analytic criteria."""
    suffixes = _validate_suffix_definitions()
    ledgers = {criterion: StreamingScientificLedger(criterion)
               for criterion in suffixes}
    topology = fixture_topology(manifest)
    binary = pathlib.Path(candidate_binary).resolve()
    require(binary.is_file(), "candidate binary unavailable for exhaustive audit")
    process = subprocess.Popen(
        [str(binary), "--audit-stream"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1024 * 1024)
    require(process.stdin is not None and process.stdout is not None and
            process.stderr is not None, "candidate audit pipes unavailable")
    submitted = 0
    try:
        for case, row in iter_ordered_bfr_rows(checkpoint, artifact_root):
            prefix = scientific_base_prefix(case, row)
            for criterion_id in ("representation_structure", "constant_field_bits",
                                 "relabel_exact_effective_coefficients"):
                for suffix, _ in suffixes[criterion_id]:
                    ledgers[criterion_id].add_encoded(prefix + suffix)
            vertex_count, faces = topology[case["content_identity_key"]]
            face = faces[row["face_row"]]
            process.stdin.write(candidate_audit_line(row, vertex_count, face))
            submitted += 1
        process.stdin.close()
        # All four pre-result ledgers are complete before the candidate's
        # numeric summary is read from stdout.
        cache_failure_count, cache_first_failure, cache_result_digest = \
            _populate_cache_identity_ledger(
            checkpoint, artifact_root, topology,
            suffixes["cache_mode_bit_identity"],
            ledgers["cache_mode_bit_identity"])
        stdout = process.stdout.read()
        stderr = process.stderr.read()
        returncode = process.wait(timeout=900)
    except Exception:
        process.kill()
        process.wait()
        raise
    require(returncode == 0, "candidate exhaustive audit failed: {}".format(stderr.strip()))
    audit = strict_json_bytes(stdout.encode("utf-8"))
    require(set(audit) == {
        "constant_cell_count", "constant_failure_count",
        "constant_result_stream_sha256",
        "first_constant_failure", "first_relabel_exact_failure",
        "first_structure_failure", "kind", "relabel_exact_cell_count",
        "relabel_exact_failure_count", "relabel_exact_result_stream_sha256",
        "row_count", "status", "structure_cell_count",
        "structure_failure_count", "structure_result_stream_sha256",
    } and audit["kind"] == "anchored_row_preoracle_audit" and
            audit["status"] in ("ok", "candidate_failure"),
            "candidate exhaustive audit output schema")
    require(submitted == 1386000 and audit["row_count"] == submitted,
            "candidate exhaustive row count")

    observed = {
        "representation_structure": audit["structure_cell_count"],
        "constant_field_bits": audit["constant_cell_count"],
        "relabel_exact_effective_coefficients": audit["relabel_exact_cell_count"],
        "cache_mode_bit_identity": ledgers["cache_mode_bit_identity"].count,
    }
    failures = {
        "representation_structure": audit["structure_failure_count"],
        "constant_field_bits": audit["constant_failure_count"],
        "relabel_exact_effective_coefficients":
            audit["relabel_exact_failure_count"],
        "cache_mode_bit_identity": cache_failure_count,
    }
    first = {
        "representation_structure": _failure_key(
            checkpoint, artifact_root, audit["first_structure_failure"],
            "representation_structure"),
        "constant_field_bits": _failure_key(
            checkpoint, artifact_root, audit["first_constant_failure"],
            "constant_field_bits"),
        "relabel_exact_effective_coefficients": _failure_key(
            checkpoint, artifact_root, audit["first_relabel_exact_failure"],
            "relabel_exact_effective_coefficients"),
        "cache_mode_bit_identity": cache_first_failure,
    }
    result = {}
    stream_fields = {
        "representation_structure": "structure_result_stream_sha256",
        "constant_field_bits": "constant_result_stream_sha256",
        "relabel_exact_effective_coefficients":
            "relabel_exact_result_stream_sha256",
    }
    for criterion_id in ledgers:
        digest = ledgers[criterion_id].finish()
        require(observed[criterion_id] == EXPECTED_CELL_COUNTS[criterion_id] and
                ledgers[criterion_id].count == observed[criterion_id],
                "{} exhaustive count drift".format(criterion_id))
        if first[criterion_id] is not None:
            validate_scientific_cell_key(first[criterion_id], criterion_id)
        status = "PASS" if failures[criterion_id] == 0 else "FAIL"
        if criterion_id == "cache_mode_bit_identity":
            result_digest = canonical_result_commitment(
                digest, observed[criterion_id], status, cache_result_digest)
        else:
            candidate_stream = audit[stream_fields[criterion_id]]
            require(SHA256_RE.fullmatch(candidate_stream or "") is not None,
                    "candidate preoracle result commitment")
            result_digest = result_commitment(
                digest, observed[criterion_id], status,
                {"candidate_result_stream_encoding":
                     "anchored-row-candidate-outcome-v1",
                 "candidate_result_stream_sha256": candidate_stream})
        result[criterion_id] = {
            "digest": digest, "observed_count": observed[criterion_id],
            "result_digest": result_digest,
            "failure_count": failures[criterion_id],
            "first_failing_key": first[criterion_id],
            "status": status,
        }
    return result


def execute_regular_row_criteria(candidate_binary, checkpoint, artifact_root,
                                 manifest):
    """Execute exact-row and emitted-coordinate regular box-spline gates."""
    analytic_rows = regular_sample_rows(manifest)
    inventory = regular_patch_inventory(manifest)
    exact_ledger = StreamingScientificLedger("regular_analytic_exact_rows")
    emitted_ledger = StreamingScientificLedger(
        "regular_analytic_emitted_geometry")
    exact_results = StreamingResultLedger("regular_analytic_exact_rows")
    emitted_results = StreamingResultLedger(
        "regular_analytic_emitted_geometry")
    target = Fraction(5, 1000000)
    exact_maximum = Fraction(0)
    emitted_maximum = Fraction(0)
    exact_failures = 0
    emitted_failures = 0
    first_exact = None
    first_emitted = None
    maximum_exact_key = None
    maximum_emitted_key = None
    binary = pathlib.Path(candidate_binary).resolve()
    require(binary.is_file(), "candidate binary unavailable for regular audit")

    pending_lines = []
    pending_cells = []

    def flush_pending():
        nonlocal emitted_maximum, emitted_failures, first_emitted
        nonlocal maximum_emitted_key
        if not pending_lines:
            return
        completed = subprocess.run(
            [str(binary), "--stream"], input="".join(pending_lines),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=120)
        require(completed.returncode == 0,
                "candidate regular stream failed: {}".format(
                    completed.stderr.strip()))
        labels = completed.stdout.splitlines()
        require(len(labels) == len(pending_cells),
                "candidate regular stream output cardinality")
        for label, (key, expected) in zip(labels, pending_cells):
            observed = Fraction.from_float(binary64_from_bits_hex(label))
            difference = abs(observed - expected)
            encoded_key = jcs_bytes(key)
            passed = difference <= target
            emitted_results.add_encoded(
                encoded_key, "PASS" if passed else "FAIL",
                exact_value={
                    "absolute_difference": [difference.numerator,
                                            difference.denominator],
                    "observed_binary64_bits": label,
                    "expected": [expected.numerator, expected.denominator],
                }, target=[target.numerator, target.denominator],
                reason=None if passed else "REGULAR_TARGET_EXCEEDED")
            if (difference > emitted_maximum or
                    (difference == emitted_maximum and
                     (maximum_emitted_key is None or
                      encoded_key < jcs_bytes(maximum_emitted_key)))):
                emitted_maximum = difference
                maximum_emitted_key = key
            if not passed:
                emitted_failures += 1
                if first_emitted is None:
                    first_emitted = key
        pending_lines[:] = []
        pending_cells[:] = []

    row_index = {name: index for index, name in enumerate(ROW_ORDER)}
    axes = ("x", "y", "z")
    for case in ordered_bfr_cases(checkpoint):
        if case["approximation_level"] not in (7, 8):
            continue
        fixture = inventory[case["content_identity_key"]]
        report = _artifact_report(artifact_root, case)
        for row in ordered_case_rows(report):
            patch = fixture["patches"].get(row["face_row"])
            if patch is None or row["sample_id"] not in analytic_rows:
                continue
            require(row["source_ids"] == sorted(patch),
                    "regular provider source support differs from analytic patch")
            formula = analytic_rows[row["sample_id"]][row_index[row["row_kind"]]]
            analytic = dict(zip(patch, formula))
            face = fixture["faces"][row["face_row"]]
            coefficient_labels = ",".join(
                binary64_bits_hex(value) for value in row["coefficients"])
            for anchor_name, anchor_source in zip(ANCHORS, face):
                effective = effective_numerators(row, anchor_source)
                coefficient_difference = max(
                    abs(Fraction(effective.get(source_id, 0), 1 << 1074) -
                        analytic.get(source_id, Fraction(0)))
                    for source_id in set(effective).union(analytic))
                exact_key = [
                    case["content_identity_key"],
                    normalized_cache_mode(case["applicable_mode"]),
                    case["approximation_level"], row["face_row"],
                    None if row["local_corner_or_none"] == -1 else
                    row["local_corner_or_none"], row["sample_id"],
                    row["row_kind"], "exact_effective", anchor_name,
                    "identity", None, None, None, None, None]
                validate_scientific_cell_key(
                    exact_key, "regular_analytic_exact_rows")
                exact_ledger.add_encoded(jcs_bytes(exact_key))
                exact_passed = coefficient_difference <= target
                exact_results.add_encoded(
                    jcs_bytes(exact_key),
                    "PASS" if exact_passed else "FAIL",
                    exact_value={
                        "absolute_difference": [
                            coefficient_difference.numerator,
                            coefficient_difference.denominator]},
                    target=[target.numerator, target.denominator],
                    reason=None if exact_passed else
                    "REGULAR_TARGET_EXCEEDED")
                if (coefficient_difference > exact_maximum or
                        (coefficient_difference == exact_maximum and
                         (maximum_exact_key is None or
                          jcs_bytes(exact_key) < jcs_bytes(maximum_exact_key)))):
                    exact_maximum = coefficient_difference
                    maximum_exact_key = exact_key
                if not exact_passed:
                    exact_failures += 1
                    if first_exact is None:
                        first_exact = exact_key

                anchor_index = row["source_ids"].index(anchor_source)
                for axis_index, axis in enumerate(axes):
                    source_labels = ",".join(
                        binary64_bits_hex(
                            fixture["vertices"][source_id][axis_index])
                        for source_id in row["source_ids"])
                    emitted_key = [
                        case["content_identity_key"],
                        normalized_cache_mode(case["applicable_mode"]),
                        case["approximation_level"], row["face_row"],
                        None if row["local_corner_or_none"] == -1 else
                        row["local_corner_or_none"], row["sample_id"],
                        row["row_kind"], "emitted_binary64", anchor_name,
                        "identity", None, axis, None, None, None]
                    validate_scientific_cell_key(
                        emitted_key, "regular_analytic_emitted_geometry")
                    emitted_ledger.add_encoded(jcs_bytes(emitted_key))
                    expected = sum(
                        analytic[source_id] * Fraction.from_float(
                            fixture["vertices"][source_id][axis_index])
                        for source_id in patch)
                    pending_lines.append("{} {} {} {}\n".format(
                        row["row_kind"], anchor_index, coefficient_labels,
                        source_labels))
                    pending_cells.append((emitted_key, expected))
            if len(pending_lines) >= 4500:
                flush_pending()
    flush_pending()

    exact_digest = exact_ledger.finish()
    emitted_digest = emitted_ledger.finish()
    exact_result_digest = canonical_result_commitment(
        exact_digest, exact_ledger.count,
        "PASS" if exact_failures == 0 else "FAIL", exact_results.finish())
    emitted_result_digest = canonical_result_commitment(
        emitted_digest, emitted_ledger.count,
        "PASS" if emitted_failures == 0 else "FAIL", emitted_results.finish())
    require(exact_ledger.count ==
            EXPECTED_CELL_COUNTS["regular_analytic_exact_rows"],
            "regular exact-row execution cardinality")
    require(emitted_ledger.count ==
            EXPECTED_CELL_COUNTS["regular_analytic_emitted_geometry"],
            "regular emitted-geometry execution cardinality")
    return {
        "regular_analytic_exact_rows": {
            "digest": exact_digest, "observed_count": exact_ledger.count,
            "result_digest": exact_result_digest,
            "failure_count": exact_failures,
            "first_failing_key": first_exact,
            "maximum": float(exact_maximum),
            "witness": [maximum_exact_key,
                        {"numerator": exact_maximum.numerator,
                         "denominator": exact_maximum.denominator},
                        binary64_bits_hex(float(exact_maximum)),
                        exact_result_digest],
            "status": "PASS" if exact_failures == 0 else "FAIL",
            "target": 5.0e-6,
            "expectation":
                "maximum source coefficient difference from exact quartic box-spline row",
        },
        "regular_analytic_emitted_geometry": {
            "digest": emitted_digest,
            "result_digest": emitted_result_digest,
            "observed_count": emitted_ledger.count,
            "failure_count": emitted_failures,
            "first_failing_key": first_emitted,
            "maximum": float(emitted_maximum),
            "witness": [maximum_emitted_key,
                        {"numerator": emitted_maximum.numerator,
                         "denominator": emitted_maximum.denominator},
                        binary64_bits_hex(float(emitted_maximum)),
                        emitted_result_digest],
            "status": "PASS" if emitted_failures == 0 else "FAIL",
            "target": 5.0e-6,
            "expectation":
                "absolute direct-coordinate difference from exact quartic box-spline geometry",
        },
    }


def _fraction_tokens(values):
    result = []
    for value in values:
        value = Fraction(value)
        result.extend((str(value.numerator), str(value.denominator)))
    return result


def execute_regular_integrand_criteria(candidate_binary, boundary_binary,
                                       checkpoint, artifact_root, manifest):
    """Execute both frozen regular scalar-integrand views through MPFR."""
    candidate = pathlib.Path(candidate_binary).resolve()
    boundary = pathlib.Path(boundary_binary).resolve()
    require(candidate.is_file() and boundary.is_file(),
            "regular integrand executable unavailable")
    analytic_rows = regular_sample_rows(manifest)
    inventory = regular_patch_inventory(manifest)
    criterion_quantity = {
        "regular_analytic_area_integrand": "area_integrand",
        "regular_analytic_legacy_volume_integrand":
            "legacy_volume_integrand",
    }
    ledgers = {criterion: StreamingScientificLedger(criterion)
               for criterion in criterion_quantity}
    results = {criterion: StreamingResultLedger(criterion)
               for criterion in criterion_quantity}
    failures = {criterion: 0 for criterion in criterion_quantity}
    maxima = {criterion: 0.0 for criterion in criterion_quantity}
    first = {criterion: None for criterion in criterion_quantity}
    maximum_keys = {criterion: None for criterion in criterion_quantity}
    pending = []

    def record_result(batch, criterion_id, key, status, upper_bits):
        value = binary64_from_bits_hex(upper_bits)
        if (value > maxima[criterion_id] or
                (value == maxima[criterion_id] and
                 (maximum_keys[criterion_id] is None or
                  jcs_bytes(key) < jcs_bytes(maximum_keys[criterion_id])))):
            maxima[criterion_id] = value
            maximum_keys[criterion_id] = key
        if status == "FAIL":
            failures[criterion_id] += 1
            if (first[criterion_id] is None or
                    jcs_bytes(key) < jcs_bytes(first[criterion_id])):
                first[criterion_id] = key
        else:
            require(status == "PASS", "integrand comparison status")
        batch[criterion_id].append((jcs_bytes(key), status, upper_bits))

    def flush_pending():
        if not pending:
            return
        evaluation_lines = []
        for item in pending:
            evaluation_lines.extend(item["evaluation_lines"])
        evaluated = subprocess.run(
            [str(candidate), "--stream"], input="".join(evaluation_lines),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=120)
        require(evaluated.returncode == 0,
                "candidate integrand-vector stream failed: {}".format(
                    evaluated.stderr.strip()))
        evaluated_labels = evaluated.stdout.splitlines()
        require(len(evaluated_labels) == len(pending) * 9,
                "candidate integrand-vector output cardinality")

        integrand_lines = []
        for index, item in enumerate(pending):
            vector_labels = evaluated_labels[index * 9:(index + 1) * 9]
            integrand_lines.append(",".join(vector_labels) + "\n")
        integrated = subprocess.run(
            [str(candidate), "--integrand-stream"],
            input="".join(integrand_lines), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=120)
        require(integrated.returncode == 0,
                "candidate emitted-integrand stream failed: {}".format(
                    integrated.stderr.strip()))
        emitted = [line.split(" ") for line in integrated.stdout.splitlines()]
        require(len(emitted) == len(pending) and
                all(len(item) == 2 for item in emitted),
                "candidate emitted-integrand output cardinality")

        boundary_lines = []
        for item, emitted_labels in zip(pending, emitted):
            boundary_lines.append("E {} {}\n".format(
                " ".join(_fraction_tokens(item["exact_vector"])),
                " ".join(_fraction_tokens(item["analytic_vector"]))))
            boundary_lines.append("B {} {} {}\n".format(
                emitted_labels[0], emitted_labels[1],
                " ".join(_fraction_tokens(item["analytic_vector"]))))
        compared = subprocess.run(
            [str(boundary), "--regular-integrand-stream"],
            input="".join(boundary_lines), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=120)
        require(compared.returncode == 0,
                "MPFR regular-integrand stream failed: {}".format(
                    compared.stderr.strip()))
        comparisons = [line.split(" ")
                       for line in compared.stdout.splitlines()]
        require(len(comparisons) == len(pending) * 2 and
                all(len(item) == 4 for item in comparisons),
                "MPFR regular-integrand output cardinality")
        result_batch = {criterion: [] for criterion in criterion_quantity}
        for index, item in enumerate(pending):
            exact_result = comparisons[2 * index]
            emitted_result = comparisons[2 * index + 1]
            record_result(result_batch, "regular_analytic_area_integrand",
                          item["keys"]["area_integrand"]["exact_effective"],
                          exact_result[0], exact_result[2])
            record_result(
                result_batch, "regular_analytic_legacy_volume_integrand",
                item["keys"]["legacy_volume_integrand"]["exact_effective"],
                exact_result[1], exact_result[3])
            record_result(result_batch, "regular_analytic_area_integrand",
                          item["keys"]["area_integrand"]["emitted_binary64"],
                          emitted_result[0], emitted_result[2])
            record_result(
                result_batch, "regular_analytic_legacy_volume_integrand",
                item["keys"]["legacy_volume_integrand"]["emitted_binary64"],
                emitted_result[1], emitted_result[3])
        for criterion_id, records in result_batch.items():
            for encoded_key, status, upper_bits in sorted(
                    records, key=lambda item: item[0]):
                results[criterion_id].add_encoded(
                    encoded_key, status,
                    exact_value={"upper_binary64_bits": upper_bits},
                    target={"upper_binary64_bits":
                            binary64_bits_hex(5.0e-6)},
                    reason=None if status == "PASS" else
                    "REGULAR_INTEGRAND_TARGET_EXCEEDED")
        pending[:] = []

    for case in ordered_bfr_cases(checkpoint):
        if case["approximation_level"] not in (7, 8):
            continue
        fixture = inventory[case["content_identity_key"]]
        rows = ordered_case_rows(_artifact_report(artifact_root, case))
        groups = {}
        for row in rows:
            group_key = (row["face_row"], row["local_corner_or_none"],
                         row["sample_id"])
            groups.setdefault(group_key, {})[row["row_kind"]] = row
        for (face_id, local_corner_raw, sample_id), group in groups.items():
            patch = fixture["patches"].get(face_id)
            if patch is None or sample_id not in analytic_rows:
                continue
            require(set(group) == set(ROW_ORDER),
                    "regular integrand six-row group")
            representative = group["position"]
            local_corner = None if local_corner_raw == -1 else local_corner_raw
            keys = {}
            for criterion_id, quantity in criterion_quantity.items():
                keys[quantity] = {}
                ordered_dimensions = sorted(
                    ((view, anchor) for view in
                     ("exact_effective", "emitted_binary64")
                     for anchor in ANCHORS),
                    key=lambda item: scientific_suffix_full(
                        item[0], item[1], "identity"))
                prefix = scientific_prefix_for_quantity(
                    case, representative, quantity)
                for view, anchor in ordered_dimensions:
                    key = [case["content_identity_key"],
                           normalized_cache_mode(case["applicable_mode"]),
                           case["approximation_level"], face_id, local_corner,
                           sample_id, quantity, view, anchor, "identity", None,
                           None, None, None, None]
                    validate_scientific_cell_key(key, criterion_id)
                    ledgers[criterion_id].add_encoded(jcs_bytes(key))
                    keys[quantity].setdefault(anchor, {})[view] = key

            face = fixture["faces"][face_id]
            for anchor_name, anchor_source in zip(ANCHORS, face):
                exact_vector = []
                analytic_vector = []
                evaluation_lines = []
                for row_kind in ("position", "du", "dv"):
                    row = group[row_kind]
                    require(row["source_ids"] == sorted(patch),
                            "regular integrand source support")
                    formula = analytic_rows[sample_id][ROW_ORDER.index(row_kind)]
                    analytic_coefficients = dict(zip(patch, formula))
                    effective = effective_numerators(row, anchor_source)
                    coefficient_labels = ",".join(
                        binary64_bits_hex(value) for value in row["coefficients"])
                    anchor_index = row["source_ids"].index(anchor_source)
                    for axis in range(3):
                        coordinates = [fixture["vertices"][source_id][axis]
                                       for source_id in row["source_ids"]]
                        exact_vector.append(sum(
                            Fraction(effective[source_id], 1 << 1074) *
                            Fraction.from_float(coordinate)
                            for source_id, coordinate in
                            zip(row["source_ids"], coordinates)))
                        analytic_vector.append(sum(
                            analytic_coefficients[source_id] *
                            Fraction.from_float(
                                fixture["vertices"][source_id][axis])
                            for source_id in patch))
                        evaluation_lines.append("{} {} {} {}\n".format(
                            row_kind, anchor_index, coefficient_labels,
                            ",".join(binary64_bits_hex(value)
                                     for value in coordinates)))
                item_keys = {
                    quantity: {
                        view: keys[quantity][anchor_name][view]
                        for view in ("exact_effective", "emitted_binary64")}
                    for quantity in criterion_quantity.values()}
                pending.append({
                    "exact_vector": exact_vector,
                    "analytic_vector": analytic_vector,
                    "evaluation_lines": evaluation_lines,
                    "keys": item_keys})
                if len(pending) >= 300:
                    flush_pending()
    flush_pending()

    result = {}
    for criterion_id, ledger in ledgers.items():
        digest = ledger.finish()
        status = "PASS" if failures[criterion_id] == 0 else "FAIL"
        result_digest = canonical_result_commitment(
            digest, ledger.count, status, results[criterion_id].finish())
        require(ledger.count == EXPECTED_CELL_COUNTS[criterion_id],
                "{} execution cardinality".format(criterion_id))
        result[criterion_id] = {
            "digest": digest, "observed_count": ledger.count,
            "result_digest": result_digest,
            "failure_count": failures[criterion_id],
            "first_failing_key": first[criterion_id],
            "maximum": maxima[criterion_id],
            "witness": [maximum_keys[criterion_id],
                        {"upper_binary64_bits":
                         binary64_bits_hex(maxima[criterion_id])},
                        binary64_bits_hex(maxima[criterion_id]),
                        result_digest],
            "status": status,
            "target": 5.0e-6,
            "expectation": (
                "absolute 544-bit MPFR-enclosed exact/emitted area-integrand difference"
                if criterion_id == "regular_analytic_area_integrand" else
                "absolute 544-bit MPFR-enclosed exact/emitted legacy-volume-integrand difference"),
        }
    return result


def component_target_fraction(row_kind):
    if row_kind == "position":
        return Fraction(5, 10000000)
    if row_kind in ("du", "dv"):
        return Fraction(25, 10000000)
    require(row_kind in ("duu", "duv", "dvv"), "component target row")
    return Fraction(125, 10000000)


def fixture_edge_scale_squared(fixture):
    maximum = Fraction(0)
    vertices = fixture["vertices"]
    for face in fixture["faces"]:
        for left, right in ((face[0], face[1]), (face[1], face[2]),
                            (face[2], face[0])):
            squared = sum(
                (Fraction.from_float(vertices[left][axis]) -
                 Fraction.from_float(vertices[right][axis])) ** 2
                for axis in range(3))
            maximum = max(maximum, squared)
    require(maximum > 0, "normalization edge scale")
    return maximum


def fixture_edge_scale_numerator(fixture):
    value = fixture_edge_scale_squared(fixture) * (1 << 2148)
    require(value.denominator == 1 and value.numerator > 0,
            "binary64 fixture scale dyadic boundary")
    return value.numerator


def component_integer_boundaries(scale_numerator, row_kind):
    target = component_target_fraction(row_kind)
    scaled_numerator = target * 10000000
    require(scaled_numerator.denominator == 1 and
            scaled_numerator.numerator in (5, 25, 125),
            "frozen component target numerator")
    square = (scaled_numerator.numerator * scaled_numerator.numerator *
              scale_numerator)
    return math.isqrt(square), math.isqrt(square << 2148)


def _component_cases(checkpoint):
    cases = {(case["content_identity_key"],
              normalized_cache_mode(case["applicable_mode"]),
              case["approximation_level"]): case
             for case in checkpoint["numeric_cases"]
             if case["candidate"] == "bfr"}
    modes = sorted({(key[0], key[1]) for key in cases},
                   key=lambda item: jcs_bytes(list(item)))
    require(len(cases) == 196 and len(modes) == 28,
            "component Bfr case inventory")
    return cases, modes


def iter_component_row_pairs(checkpoint, artifact_root, manifest):
    inventory = regular_patch_inventory(manifest)
    cases, modes = _component_cases(checkpoint)
    for content_id, cache_mode in modes:
        fixture = inventory[content_id]
        for low_level, high_level, transition in (
                (6, 7, "6_7"), (7, 8, "7_8")):
            low_case = cases[(content_id, cache_mode, low_level)]
            high_case = cases[(content_id, cache_mode, high_level)]
            low_rows = ordered_case_rows(
                _artifact_report(artifact_root, low_case))
            high_rows = ordered_case_rows(
                _artifact_report(artifact_root, high_case))
            require(len(low_rows) == len(high_rows),
                    "stabilization row count")
            for low_row, high_row in zip(low_rows, high_rows):
                require((low_row["face_row"],
                         low_row["local_corner_or_none"],
                         low_row["sample_id"], low_row["row_kind"]) ==
                        (high_row["face_row"],
                         high_row["local_corner_or_none"],
                         high_row["sample_id"], high_row["row_kind"]),
                        "stabilization row identity")
                yield (low_case, low_row, high_case, high_row, fixture,
                       transition)


def candidate_component_line(low_row, high_row, fixture, transition,
                             scale_numerator):
    union_ids = sorted(set(low_row["source_ids"]).union(
        high_row["source_ids"]))
    face = fixture["faces"][high_row["face_row"]]
    require(len(face) == 3 and
            all(source_id in low_row["source_ids"] and
                source_id in high_row["source_ids"] for source_id in face),
            "component anchor support")
    boundary1074, boundary2148 = component_integer_boundaries(
        scale_numerator, high_row["row_kind"])
    return "{} {} {} {} {} {} {} {} {} {} {} {} {:x} {:x} {:x}\n".format(
        transition, high_row["row_kind"], len(fixture["vertices"]),
        ",".join(str(value) for value in face),
        ",".join(str(value) for value in low_row["source_ids"]),
        ",".join(binary64_bits_hex(value)
                 for value in low_row["coefficients"]),
        ",".join(str(value) for value in high_row["source_ids"]),
        ",".join(binary64_bits_hex(value)
                 for value in high_row["coefficients"]),
        ",".join(str(value) for value in union_ids),
        *(",".join(binary64_bits_hex(
            fixture["vertices"][source_id][axis]) for source_id in union_ids)
          for axis in range(3)),
        scale_numerator, boundary1074, boundary2148)


def _component_failure_key(checkpoint, artifact_root, manifest, failure,
                           criterion_id):
    if failure is None:
        return None
    require(set(failure) == {
        "anchor_index", "anchor_pair_index", "axis_index",
        "basis_source_id", "relabel_index", "row_ordinal",
    }, "component failure descriptor")
    ordinal = failure["row_ordinal"]
    require(type(ordinal) is int and ordinal >= 0,
            "component failure row ordinal")
    selected = None
    for index, item in enumerate(iter_component_row_pairs(
            checkpoint, artifact_root, manifest)):
        if index == ordinal:
            selected = item
            break
    require(selected is not None, "component failure outside matrix")
    _, _, high_case, row, _, transition = selected
    prefix = scientific_base_prefix(high_case, row)
    anchors = (None if failure["anchor_index"] is None else
               ANCHORS[failure["anchor_index"]])
    relabel = (None if failure["relabel_index"] is None else
               RELABELS[failure["relabel_index"]])
    axis = (None if failure["axis_index"] is None else
            ("x", "y", "z")[failure["axis_index"]])
    pair = (None if failure["anchor_pair_index"] is None else
            ("v0_v1", "v0_v2", "v1_v2")[
                failure["anchor_pair_index"]])
    basis = failure["basis_source_id"]
    exact = criterion_id in {
        "anchor_sensitivity_exact_coeff",
        "anchor_sensitivity_exact_geometry",
        "stabilization_6_7_exact_coeff",
        "stabilization_6_7_exact_geometry",
        "stabilization_7_8_exact_coeff",
        "stabilization_7_8_exact_geometry",
    }
    view = "exact_effective" if exact else "emitted_binary64"
    if criterion_id.startswith("anchor_sensitivity_"):
        anchors = None
        relabel = "identity"
        transition_value = None
    elif criterion_id.startswith("stabilization_"):
        relabel = "identity"
        transition_value = transition
    else:
        transition_value = None
    key = strict_json_bytes(prefix + scientific_suffix_full(
        view, anchors, relabel, basis, axis, pair, transition_value, None))
    validate_scientific_cell_key(key, criterion_id)
    return key


def execute_component_criteria(candidate_binary, checkpoint, artifact_root,
                               manifest, scientific_ledgers):
    """Execute compact exact anchor, fidelity, relabel, and stabilization gates."""
    criterion_ids = (
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
        "stabilization_7_8_emitted_geometry",
    )
    require(set(criterion_ids).issubset(scientific_ledgers),
            "component pre-result ledgers unavailable")
    inventory = regular_patch_inventory(manifest)
    scales = {content_id: fixture_edge_scale_numerator(fixture)
              for content_id, fixture in inventory.items()}
    binary = pathlib.Path(candidate_binary).resolve()
    process = subprocess.Popen(
        [str(binary), "--component-audit-stream"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        bufsize=1024 * 1024)
    require(process.stdin is not None and process.stdout is not None and
            process.stderr is not None, "component audit pipes unavailable")
    submitted = 0
    try:
        for _, low_row, high_case, high_row, fixture, transition in \
                iter_component_row_pairs(checkpoint, artifact_root, manifest):
            process.stdin.write(candidate_component_line(
                low_row, high_row, fixture, transition,
                scales[high_case["content_identity_key"]]))
            submitted += 1
        process.stdin.close()
        stdout = process.stdout.read()
        stderr = process.stderr.read()
        returncode = process.wait(timeout=900)
    except Exception:
        process.kill()
        process.wait()
        raise
    require(returncode == 0,
            "candidate component audit failed: {}".format(stderr.strip()))
    audit = strict_json_bytes(stdout.encode("utf-8"))
    require(set(audit) == {"criteria", "kind", "row_count", "status"} and
            audit["kind"] == "anchored_row_component_audit" and
            audit["status"] in ("ok", "candidate_failure") and
            audit["row_count"] == submitted == 396000 and
            set(audit["criteria"]) == set(criterion_ids),
            "candidate component audit output schema")
    result = {}
    for criterion_id in criterion_ids:
        statistic = audit["criteria"][criterion_id]
        require(set(statistic) == {
            "candidate_result_stream_sha256", "cell_count", "failure_count",
            "first_failure", "maximum", "maximum_exact", "maximum_witness",
        } and statistic["cell_count"] ==
                EXPECTED_CELL_COUNTS[criterion_id] and
                type(statistic["failure_count"]) is int and
                0 <= statistic["failure_count"] <= statistic["cell_count"] and
                type(statistic["maximum"]) in (int, float) and
                math.isfinite(statistic["maximum"]) and
                statistic["maximum"] >= 0 and
                SHA256_RE.fullmatch(
                    statistic["candidate_result_stream_sha256"] or "") is not None and
                isinstance(statistic["maximum_exact"], dict) and
                set(statistic["maximum_exact"]) == {
                    "denominator_power", "normalized_by_sqrt_scale",
                    "numerator_hex", "scale_numerator_hex"} and
                statistic["maximum_exact"]["denominator_power"] in (1074, 2148) and
                type(statistic["maximum_exact"][
                    "normalized_by_sqrt_scale"]) is bool and
                re.fullmatch(r"[0-9a-f]+", statistic["maximum_exact"][
                    "numerator_hex"]) is not None and
                re.fullmatch(r"[0-9a-f]+", statistic["maximum_exact"][
                    "scale_numerator_hex"]) is not None and
                ((statistic["first_failure"] is None) ==
                 (statistic["failure_count"] == 0)),
                "{} component summary".format(criterion_id))
        first = _component_failure_key(
            checkpoint, artifact_root, manifest,
            statistic["first_failure"], criterion_id)
        ledger = scientific_ledgers[criterion_id]
        require(ledger["count"] == statistic["cell_count"],
                "{} component ledger count".format(criterion_id))
        maximum_key = _component_failure_key(
            checkpoint, artifact_root, manifest,
            statistic["maximum_witness"], criterion_id)
        require(maximum_key is not None,
                "{} maximum witness missing".format(criterion_id))
        exact_maximum = statistic["maximum_exact"]
        numerator = int(exact_maximum["numerator_hex"], 16)
        scale = int(exact_maximum["scale_numerator_hex"], 16)
        with localcontext() as context:
            context.prec = 100
            if exact_maximum["normalized_by_sqrt_scale"]:
                require(scale > 0 and
                        exact_maximum["denominator_power"] in (1074, 2148),
                        "normalized maximum exact descriptor")
                exact_display = (Decimal(numerator) /
                                 Decimal(scale).sqrt() /
                                 (Decimal(2) **
                                  (exact_maximum["denominator_power"] - 1074)))
            else:
                require(scale == 1 and
                        exact_maximum["denominator_power"] == 1074,
                        "coefficient maximum exact descriptor")
                exact_display = (Decimal(numerator) /
                                 (Decimal(2) ** 1074))
        require(math.isclose(float(exact_display), statistic["maximum"],
                             rel_tol=2.0e-15, abs_tol=0.0) or
                (exact_display == 0 and statistic["maximum"] == 0),
                "component maximum display/exact mismatch")
        result_digest = result_commitment(
            ledger["digest"], statistic["cell_count"],
            "PASS" if statistic["failure_count"] == 0 else "FAIL",
            {"candidate_result_stream_encoding":
                 "anchored-row-candidate-outcome-v1",
             "candidate_result_stream_sha256":
                 statistic["candidate_result_stream_sha256"]})
        result[criterion_id] = {
            "digest": ledger["digest"],
            "result_digest": result_digest,
            "observed_count": statistic["cell_count"],
            "failure_count": statistic["failure_count"],
            "first_failing_key": first,
            "maximum": statistic["maximum"],
            "witness": [maximum_key, statistic["maximum_exact"],
                        binary64_bits_hex(statistic["maximum"]),
                        result_digest],
            "status": ("PASS" if statistic["failure_count"] == 0 else
                       "FAIL"),
            "target": None,
            "expectation": "frozen row-order 0.1 x D10 component target",
        }
    return result


def make_pre_result_ledgers(checkpoint, executed=None):
    executed = executed or {}
    inventory_keys = [[item["content_identity_key"], item["candidate"],
                       item["approximation_level"], item["applicable_mode"]]
                      for item in checkpoint["numeric_cases"]]
    raw_case_keys = [key for key in inventory_keys if key[1] == "bfr"]
    present_ledgers = {
        "bindings_and_independence": generic_key_ledger_sha256(
            [[CANDIDATE, checkpoint["binding"]["git_head"]]]),
        "complete_artifact_inventory": generic_key_ledger_sha256(inventory_keys),
        "raw_bfr_d9a_reproduction": generic_key_ledger_sha256(raw_case_keys),
    }
    records = []
    for criterion_id in CRITERION_IDS:
        if criterion_id in executed:
            item = executed[criterion_id]
            require(item["observed_count"] == EXPECTED_CELL_COUNTS[criterion_id] and
                    SHA256_RE.fullmatch(item["digest"]) is not None,
                    "executed ledger binding")
            records.append({
                "criterion_id": criterion_id, "partition": "all",
                "expected_count": EXPECTED_CELL_COUNTS[criterion_id],
                "observed_count": item["observed_count"],
                "key_ledger_sha256": item["digest"],
                "availability": availability("PRESENT", item["digest"]),
                "omission_blocker": None,
            })
            continue
        if criterion_id in present_ledgers:
            digest = present_ledgers[criterion_id]
            records.append({"criterion_id": criterion_id, "partition": "all",
                            "expected_count": EXPECTED_CELL_COUNTS[criterion_id],
                            "observed_count": EXPECTED_CELL_COUNTS[criterion_id],
                            "key_ledger_sha256": digest,
                            "availability": availability("PRESENT", digest),
                            "omission_blocker": None})
            continue
        records.append({
            "criterion_id": criterion_id,
            "partition": ("oracle_request" if criterion_id ==
                          "oracle_coverage_and_crosscheck" else "all"),
            "expected_count": EXPECTED_CELL_COUNTS[criterion_id],
            "observed_count": 0, "key_ledger_sha256": None,
            "availability": availability(
                "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE"),
            "omission_blocker": "bindings_and_independence",
        })
        if criterion_id == "oracle_coverage_and_crosscheck":
            for partition in ("covered", "uncovered"):
                uncovered = partition == "uncovered"
                digest = (present_ledgers.get(criterion_id) or
                          generic_key_ledger_sha256([[criterion_id, "synthetic"]]))
                partition_digest = digest if uncovered else sha256_bytes(b"[]")
                records.append({
                    "criterion_id": criterion_id, "partition": partition,
                    "expected_count": None,
                    "observed_count": (EXPECTED_CELL_COUNTS[criterion_id]
                                       if uncovered else 0),
                    "key_ledger_sha256": partition_digest,
                    "availability": availability("PRESENT", partition_digest),
                    "omission_blocker": None,
                })
    require(len(records) == 34, "pre-result ledger partition count")
    return records


def _add_sorted_suffixes(ledger, prefix, suffixes):
    for suffix in suffixes:
        ledger.add_encoded(prefix + suffix)


def _frozen_scientific_suffixes():
    pairs = ("v0_v1", "v0_v2", "v1_v2")
    axes = ("x", "y", "z")
    definitions = {
        "regular_analytic_exact_rows": [
            scientific_suffix_full("exact_effective", anchor, "identity")
            for anchor in ANCHORS],
        "regular_analytic_emitted_geometry": [
            scientific_suffix_full("emitted_binary64", anchor, "identity",
                                   axis=axis)
            for anchor in ANCHORS for axis in axes],
        "oracle_coverage_and_crosscheck": [
            scientific_suffix_full(None, anchor, "identity")
            for anchor in ANCHORS],
        "exact_effective_d10_coeff": [
            scientific_suffix_full("exact_effective", anchor, "identity")
            for anchor in ANCHORS],
        "exact_effective_d10_geometry": [
            scientific_suffix_full("exact_effective", anchor, "identity",
                                   axis=axis)
            for anchor in ANCHORS for axis in axes],
        "emitted_direct_geometry_d10": [
            scientific_suffix_full("emitted_binary64", anchor, "identity",
                                   axis=axis)
            for anchor in ANCHORS for axis in axes],
        "anchor_sensitivity_exact_coeff": [
            scientific_suffix_full("exact_effective", None, "identity",
                                   anchor_pair=pair)
            for pair in pairs],
        "anchor_sensitivity_exact_geometry": [
            scientific_suffix_full("exact_effective", None, "identity",
                                   axis=axis, anchor_pair=pair)
            for pair in pairs for axis in axes],
        "anchor_sensitivity_emitted_geometry": [
            scientific_suffix_full("emitted_binary64", None, "identity",
                                   axis=axis, anchor_pair=pair)
            for pair in pairs for axis in axes],
        "binary64_direct_geometry_fidelity": [
            scientific_suffix_full("emitted_binary64", anchor, relabel,
                                   axis=axis)
            for anchor in ANCHORS for relabel in RELABELS for axis in axes],
        "relabel_emitted_geometry_fidelity": [
            scientific_suffix_full("emitted_binary64", anchor, relabel,
                                   axis=axis)
            for anchor in ANCHORS for relabel in RELABELS[1:] for axis in axes],
    }
    for high_level, transition in ((7, "6_7"), (8, "7_8")):
        stem = "stabilization_{}_{}".format(transition, "{}")
        definitions[stem.format("exact_coeff")] = [
            scientific_suffix_full("exact_effective", anchor, "identity",
                                   transition=transition)
            for anchor in ANCHORS]
        definitions[stem.format("exact_geometry")] = [
            scientific_suffix_full("exact_effective", anchor, "identity",
                                   axis=axis, transition=transition)
            for anchor in ANCHORS for axis in axes]
        definitions[stem.format("emitted_geometry")] = [
            scientific_suffix_full("emitted_binary64", anchor, "identity",
                                   axis=axis, transition=transition)
            for anchor in ANCHORS for axis in axes]
    return {key: sorted(value) for key, value in definitions.items()}


def _regular_coverage(manifest):
    regular_faces = {}
    for job in B2.valid_content_jobs(manifest):
        _, faces, valences = B2.independent_mesh(job)
        regular_faces[job["content_identity_key"]] = {
            index for index, face in enumerate(faces)
            if all(valences[source_id] == 6 for source_id in face)}
    regular_samples = {
        sample["id"] for policy in manifest["sample_policies"]
        if policy["id"] == "regular_interior_l6_10"
        for sample in policy["samples"]}
    require(len(regular_faces) == 14 and len(regular_samples) == 10,
            "regular applicability inventory")
    return regular_faces, regular_samples


def make_scientific_pre_result_ledgers(checkpoint, artifact_root, manifest):
    """Materialize every frozen scientific applicability ledger."""
    criterion_ids = CRITERION_IDS[6:26]
    ledgers = {criterion_id: StreamingScientificLedger(criterion_id)
               for criterion_id in criterion_ids}
    oracle_uncovered_results = StreamingResultLedger(
        "oracle_coverage_and_crosscheck:uncovered")
    suffixes = _frozen_scientific_suffixes()
    regular_faces, regular_samples = _regular_coverage(manifest)
    integrands = {
        "regular_analytic_area_integrand": "area_integrand",
        "regular_analytic_legacy_volume_integrand":
            "legacy_volume_integrand",
    }
    for case in ordered_bfr_cases(checkpoint):
        level = case["approximation_level"]
        if level not in (7, 8):
            continue
        report = _artifact_report(artifact_root, case)
        for row in ordered_case_rows(report):
            prefix = scientific_base_prefix(case, row)
            oracle_id = "oracle_coverage_and_crosscheck"
            oracle_suffixes = suffixes[oracle_id]
            for suffix in oracle_suffixes:
                encoded_key = prefix + suffix
                ledgers[oracle_id].add_encoded(encoded_key)
                oracle_uncovered_results.add_encoded(
                    encoded_key, "UNCOVERED", reason=
                    "EIGENBASIS_CERTIFICATION_FAILED")
            for criterion_id in (
                    "exact_effective_d10_coeff",
                    "exact_effective_d10_geometry",
                    "emitted_direct_geometry_d10",
                    "anchor_sensitivity_exact_coeff",
                    "anchor_sensitivity_exact_geometry",
                    "anchor_sensitivity_emitted_geometry",
                    "binary64_direct_geometry_fidelity",
                    "relabel_emitted_geometry_fidelity"):
                _add_sorted_suffixes(ledgers[criterion_id], prefix,
                                     suffixes[criterion_id])

            basis_suffixes = sorted(
                scientific_suffix_full("emitted_binary64", anchor,
                                       relabel, basis_source_id=source_id)
                for anchor in ANCHORS for relabel in RELABELS
                for source_id in row["source_ids"])
            _add_sorted_suffixes(
                ledgers["binary64_basis_probe_diagnostic"], prefix,
                basis_suffixes)

            transition = "6_7" if level == 7 else "7_8"
            for ending in ("exact_coeff", "exact_geometry",
                           "emitted_geometry"):
                criterion_id = "stabilization_{}_{}".format(
                    transition, ending)
                _add_sorted_suffixes(ledgers[criterion_id], prefix,
                                     suffixes[criterion_id])

            is_regular = (row["face_row"] in
                          regular_faces[case["content_identity_key"]] and
                          row["sample_id"] in regular_samples)
            if not is_regular:
                continue
            for criterion_id in ("regular_analytic_exact_rows",
                                 "regular_analytic_emitted_geometry"):
                _add_sorted_suffixes(ledgers[criterion_id], prefix,
                                     suffixes[criterion_id])
            if row["row_kind"] == "position":
                for criterion_id, quantity in integrands.items():
                    integrand_prefix = scientific_prefix_for_quantity(
                        case, row, quantity)
                    integrand_suffixes = sorted(
                        scientific_suffix_full(view, anchor, "identity")
                        for anchor in ANCHORS
                        for view in ("exact_effective", "emitted_binary64"))
                    _add_sorted_suffixes(ledgers[criterion_id],
                                         integrand_prefix,
                                         integrand_suffixes)

    result = {}
    for criterion_id, ledger in ledgers.items():
        digest = ledger.finish()
        require(ledger.count == EXPECTED_CELL_COUNTS[criterion_id],
                "{} pre-result cardinality drift".format(criterion_id))
        result[criterion_id] = {"digest": digest, "count": ledger.count}
    oracle = result["oracle_coverage_and_crosscheck"]
    require(oracle_uncovered_results.count == oracle["count"],
            "oracle uncovered/result cardinality drift")
    oracle["uncovered_result_digest"] = oracle_uncovered_results.finish()
    oracle["covered_result_digest"] = sha256_bytes(b"[]")
    return result


def _ordered_d12_cases(checkpoint):
    cases = [case for case in checkpoint["numeric_cases"]
             if case["candidate"] == "bfr"]
    cases.sort(key=lambda case: jcs_bytes([
        case["content_identity_key"], case["approximation_level"],
        "release", normalized_cache_mode(case["applicable_mode"])]))
    require(len(cases) == 196, "D12 release case count")
    return cases


def make_d12_pre_result_ledgers(checkpoint, artifact_root, manifest):
    """Materialize the five frozen D12 operational applicability ledgers."""
    del manifest
    ledgers = {criterion_id: StreamingJcsLedger(criterion_id)
               for criterion_id in CRITERION_IDS[27:]}
    for case in _ordered_d12_cases(checkpoint):
        content_id = case["content_identity_key"]
        level = case["approximation_level"]
        cache_mode = normalized_cache_mode(case["applicable_mode"])
        report = _artifact_report(artifact_root, case)
        groups = sorted({
            (row["face_row"],
             None if row["local_corner_or_none"] == -1 else
             row["local_corner_or_none"], row["sample_id"])
            for row in report["rows"]}, key=lambda item: jcs_bytes(list(item)))
        require(len(groups) == report["row_group_count"],
                "D12 row-group identity drift")
        face_ids = sorted({row["face_row"] for row in report["rows"]},
                          key=lambda value: jcs_bytes(value))

        preparation = []
        for repeat_index in range(15):
            preparation.append([
                content_id, level, "release", cache_mode, None, None, None,
                "measured", repeat_index, None, None, None, None,
                "preparation_duration_ns"])
        preparation.append([
            content_id, level, "release", cache_mode, None, None, None,
            None, None, None, None, None, None, "preparation_median_ns"])
        for encoded in sorted(jcs_bytes(key) for key in preparation):
            ledgers["d12_preparation_cost"].add_encoded(encoded)

        retained = [[content_id, level, "release", cache_mode, None, None,
                     None, None, None, face_id, None, None, None,
                     "retained_payload_bytes"] for face_id in face_ids]
        for encoded in sorted(jcs_bytes(key) for key in retained):
            ledgers["d12_retained_payload"].add_encoded(encoded)

        rss = [[content_id, level, "release", cache_mode, None, None, None,
                None, None, None, None, None, "pre_refiner_baseline",
                "rss_bytes"]]
        ordinary_stages = (
            "after_refiner", "after_factory_cache",
            "after_package_publication", "after_package_destruction",
            "after_factory_cache_destruction", "after_refiner_destruction")
        for repeat_phase, count in (("warmup", 3), ("measured", 15)):
            for repeat_index in range(count):
                for stage in ordinary_stages:
                    rss.append([
                        content_id, level, "release", cache_mode, None, None,
                        None, repeat_phase, repeat_index, None, None, None,
                        stage, "rss_bytes"])
                for face_id, local_corner, sample_id in groups:
                    rss.append([
                        content_id, level, "release", cache_mode, None, None,
                        None, repeat_phase, repeat_index, face_id,
                        local_corner, sample_id, "after_face_insert",
                        "rss_bytes"])
        require(len(rss) == 1 + case["rss_expected_named_sample_count"],
                "D12 RSS case cardinality drift")
        for encoded in sorted(jcs_bytes(key) for key in rss):
            ledgers["d12_peak_rss"].add_encoded(encoded)

    content_ids = sorted({case["content_identity_key"]
                          for case in _ordered_d12_cases(checkpoint)},
                         key=jcs_bytes)
    require(len(content_ids) == 14, "D12 content identity count")
    for content_id in content_ids:
        for level in range(2, 9):
            cache_disabled = []
            instrumented = []
            for worker_count in (1, 2, 4):
                for round_index in range(20):
                    for worker_index in range(worker_count):
                        cache_disabled.append([
                            content_id, level, "tsan", "cache_disabled",
                            worker_count, worker_index, round_index, None,
                            None, None, None, None, "thread_result",
                            "row_digest"])
                        instrumented.append([
                            content_id, level, "tsan", "threaded_cache",
                            worker_count, worker_index, round_index, None,
                            None, None, None, None, "thread_result",
                            "row_digest"])
                for cache_mode in ("cache_disabled", "threaded_cache"):
                    for quantity in ("instrumentation_coverage",
                                     "tsan_finding_count"):
                        instrumented.append([
                            content_id, level, "tsan", cache_mode,
                            worker_count, None, None, None, None, None, None,
                            None, "sanitizer_summary", quantity])
            for encoded in sorted(jcs_bytes(key) for key in cache_disabled):
                ledgers["d12_cache_disabled_concurrency"].add_encoded(encoded)
            for encoded in sorted(jcs_bytes(key) for key in instrumented):
                ledgers["d12_instrumented_tsan"].add_encoded(encoded)

    result = {}
    for criterion_id, ledger in ledgers.items():
        digest = ledger.finish()
        require(ledger.count == EXPECTED_CELL_COUNTS[criterion_id],
                "{} pre-result cardinality drift".format(criterion_id))
        result[criterion_id] = {"digest": digest, "count": ledger.count}
    return result


def make_complete_pre_result_ledgers(checkpoint, artifact_root, manifest,
                                     executed, scientific=None):
    """Bind every frozen key set without inventing post-oracle partitions."""
    if scientific is None:
        scientific = make_scientific_pre_result_ledgers(
            checkpoint, artifact_root, manifest)
    d12 = make_d12_pre_result_ledgers(
        checkpoint, artifact_root, manifest)
    generated = dict(scientific)
    generated.update(d12)
    present = {
        "bindings_and_independence": generic_key_ledger_sha256(
            [[CANDIDATE, checkpoint["binding"]["git_head"]]]),
        "complete_artifact_inventory": generic_key_ledger_sha256([
            [item["content_identity_key"], item["candidate"],
             item["approximation_level"], item["applicable_mode"]]
            for item in checkpoint["numeric_cases"]]),
        "raw_bfr_d9a_reproduction": generic_key_ledger_sha256([
            [item["content_identity_key"], item["candidate"],
             item["approximation_level"], item["applicable_mode"]]
            for item in checkpoint["numeric_cases"]
            if item["candidate"] == "bfr"]),
    }
    records = []
    for criterion_id in CRITERION_IDS:
        if criterion_id in executed:
            digest = executed[criterion_id]["digest"]
            count = executed[criterion_id]["observed_count"]
        elif criterion_id in generated:
            digest = generated[criterion_id]["digest"]
            count = generated[criterion_id]["count"]
        else:
            digest = present[criterion_id]
            count = EXPECTED_CELL_COUNTS[criterion_id]
        partition = ("oracle_request" if criterion_id ==
                     "oracle_coverage_and_crosscheck" else "all")
        records.append({
            "criterion_id": criterion_id, "partition": partition,
            "expected_count": EXPECTED_CELL_COUNTS[criterion_id],
            "observed_count": count, "key_ledger_sha256": digest,
            "availability": availability("PRESENT", digest),
            "omission_blocker": None})
        if criterion_id == "oracle_coverage_and_crosscheck":
            records.extend(oracle_absent_partition_ledgers(digest, count))
    require(len(records) == 34, "complete pre-result ledger partition count")
    return records


def oracle_absent_partition_ledgers(request_digest, request_count):
    """Return the exact empty-covered/full-uncovered absent-oracle split."""
    require(SHA256_RE.fullmatch(request_digest or "") is not None and
            request_count == EXPECTED_CELL_COUNTS[
                "oracle_coverage_and_crosscheck"],
            "oracle request partition input")
    empty = sha256_bytes(b"[]")
    return [
        {"criterion_id": "oracle_coverage_and_crosscheck",
         "partition": "covered", "expected_count": None,
         "observed_count": 0, "key_ledger_sha256": empty,
         "availability": availability("PRESENT", empty),
         "omission_blocker": None},
        {"criterion_id": "oracle_coverage_and_crosscheck",
         "partition": "uncovered", "expected_count": None,
         "observed_count": request_count,
         "key_ledger_sha256": request_digest,
         "availability": availability("PRESENT", request_digest),
         "omission_blocker": None},
    ]


def run_json(binary, argument, expected_kind):
    path = pathlib.Path(binary).resolve()
    require(path.is_file(), "binary unavailable: {}".format(path))
    completed = subprocess.run([str(path), argument], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, timeout=30)
    require(completed.returncode == 0,
            "binary failed: {}".format(completed.stderr.strip()))
    value = strict_json_bytes(completed.stdout.encode("utf-8"))
    require(value.get("kind") == expected_kind, "binary self-test kind mismatch")
    return value


def git_observations():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=str(ROOT),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    identity = (git_identity("PRESENT", head.stdout.strip())
                if head.returncode == 0 and GIT_RE.fullmatch(head.stdout.strip())
                else git_identity("UNAVAILABLE", reason_code="GIT_IDENTITY_UNAVAILABLE"))
    clean = status.returncode == 0 and not status.stdout.strip()
    return identity, worktree_observation(clean)


def require_git_binding(start_identity, end_identity, start_worktree,
                        end_worktree, expected_head, checkpoint_head):
    require(start_identity["state"] == "PRESENT" and
            end_identity["state"] == "PRESENT", "Git identity unavailable")
    commits = (start_identity["git_commit"], end_identity["git_commit"],
               expected_head, checkpoint_head)
    require(all(GIT_RE.fullmatch(value or "") is not None for value in commits),
            "Git binding contains malformed commit")
    require(len(set(commits)) == 1,
            "start/end/expected/checkpoint Git commits do not match")
    require(start_worktree["state"] == "PRESENT" and
            start_worktree["clean"] is True,
            "worktree was not clean before execution")
    require(end_worktree["state"] == "PRESENT" and
            end_worktree["clean"] is True,
            "worktree was not clean after execution")
    return True


def file_availability(path_text):
    path = pathlib.Path(path_text).resolve() if path_text else None
    if path is None:
        return availability("UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE")
    if not path.is_file():
        return availability("MISSING", reason_code="EXPECTED_PATH_MISSING")
    return availability("PRESENT", sha256_file(path))


def dependency_record(version, archive, build, install, link_map, dynamic):
    return {"version": version,
            "source_archive": file_availability(archive),
            "build_provenance": file_availability(build),
            "install_provenance": file_availability(install),
            "link_map": file_availability(link_map),
            "dynamic_dependencies": file_availability(dynamic)}


def dependency_records(args):
    return {
        "gmp": dependency_record("6.3.0", args.gmp_archive,
                                 args.gmp_build_provenance,
                                 args.gmp_install_provenance,
                                 args.gmp_link_provenance,
                                 args.gmp_dynamic_dependency),
        "mpfr": dependency_record("4.2.2", args.mpfr_archive,
                                  args.mpfr_build_provenance,
                                  args.mpfr_install_provenance,
                                  args.mpfr_link_provenance,
                                  args.mpfr_dynamic_dependency),
        "opensubdiv": dependency_record("3.7.0", args.opensubdiv_archive,
                                        args.opensubdiv_build_provenance,
                                        args.opensubdiv_install_provenance,
                                        args.opensubdiv_link_provenance,
                                        args.opensubdiv_dynamic_dependency),
    }


def binary_record(path, source_paths, capability, dependencies,
                  command=None, version=None, link_map=None, dynamic=None,
                  present=True):
    if not present:
        missing = availability("UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE")
        return {"availability": missing, "sources": [],
                "compiler_command": missing, "compiler_version": missing,
                "link_map": missing, "dynamic_dependencies": missing,
                "dependencies": dependencies,
                "capability": capability}
    path = pathlib.Path(path).resolve()
    record_sources = [{"path": str(item.relative_to(ROOT)), "sha256": sha256_file(item)}
                      for item in source_paths]
    digest = sha256_file(path)
    return {"availability": availability("PRESENT", digest),
            "sources": record_sources,
            "compiler_command": file_availability(command),
            "compiler_version": file_availability(version),
            "link_map": file_availability(link_map),
            "dynamic_dependencies": file_availability(dynamic),
            "dependencies": dependencies,
            "capability": capability}


def criterion_record(criterion_id, status, blocker=None, expectation=None,
                     expected=0, observed=0, ledger=None, target=None,
                     result_ledger=None, maximum=None, witness=None,
                     first_failure=None):
    require(criterion_id in CRITERION_IDS and status in STATUSES, "criterion record enum")
    if status.startswith("OMITTED_"):
        require(blocker in CRITERION_IDS and observed == 0 and maximum is None and witness is None,
                "omitted criterion semantics")
    else:
        require(blocker is None, "executed criterion has blocker")
    return {"criterion_id": criterion_id, "target": target,
            "expectation": expectation, "applicability": "frozen_B2b",
            "expected_cell_count": expected, "observed_cell_count": observed,
            "key_ledger_sha256": ledger,
            "result_ledger_sha256": result_ledger, "status": status,
            "maximum": maximum, "witness": witness,
            "first_failing_key": first_failure, "omission_blocker": blocker}


def validate_criteria(criteria):
    require([item.get("criterion_id") for item in criteria] == list(CRITERION_IDS),
            "criterion IDs missing, extra, duplicated, or reordered")
    for item in criteria:
        require(set(item) == {"criterion_id", "target", "expectation", "applicability",
                              "expected_cell_count", "observed_cell_count",
                              "key_ledger_sha256", "result_ledger_sha256",
                              "status", "maximum", "witness",
                              "first_failing_key", "omission_blocker"},
                "criterion object is not closed")
        criterion_id = item["criterion_id"]
        status = item["status"]
        index = CRITERION_IDS.index(criterion_id)
        require(status in STATUSES, "criterion status")
        if criterion_id in INFRASTRUCTURE_CRITERIA:
            require(status in {"PASS", "INCOMPLETE"},
                    "infrastructure status ownership")
        elif criterion_id in ORACLE_CRITERIA:
            require(status in {"PASS", "UNCOVERED", "INCOMPLETE"},
                    "oracle status ownership")
        elif criterion_id in D12_CRITERIA:
            require(status in {"PASS", "FAIL", "INCOMPLETE",
                               "OMITTED_AFTER_CANDIDATE_FAILURE"},
                    "D12 status ownership")
        else:
            require(status in {"PASS", "FAIL",
                               "OMITTED_AFTER_CANDIDATE_FAILURE",
                               "OMITTED_AFTER_INFRASTRUCTURE_FAILURE"},
                    "candidate-scientific status ownership")
        require(item["expected_cell_count"] ==
                EXPECTED_CELL_COUNTS[criterion_id],
                "criterion expected-count drift")
        if status.startswith("OMITTED_"):
            blocker = item["omission_blocker"]
            require(blocker in CRITERION_IDS and
                    CRITERION_IDS.index(blocker) < index and
                    item["observed_cell_count"] == 0 and
                    item["result_ledger_sha256"] is None and
                    item["maximum"] is None and item["witness"] is None and
                    item["first_failing_key"] is None,
                    "invalid omitted criterion")
            blocker_status = criteria[CRITERION_IDS.index(blocker)]["status"]
            if status == "OMITTED_AFTER_CANDIDATE_FAILURE":
                require(blocker_status == "FAIL" and
                        blocker not in INFRASTRUCTURE_CRITERIA | ORACLE_CRITERIA,
                        "candidate omission lacks earlier candidate failure")
            else:
                require(blocker_status == "INCOMPLETE",
                        "infrastructure omission lacks earlier incomplete blocker")
        else:
            require(item["omission_blocker"] is None,
                    "executed criterion has omission blocker")
        if status in {"PASS", "FAIL", "UNCOVERED"}:
            require(item["observed_cell_count"] == item["expected_cell_count"] and
                    SHA256_RE.fullmatch(item["key_ledger_sha256"] or "") is not None and
                    SHA256_RE.fullmatch(item["result_ledger_sha256"] or "") is not None,
                    "executed criterion lacks complete key/result binding")
        if status == "FAIL":
            require(item["first_failing_key"] is not None,
                    "candidate failure lacks first failing key")
        elif status != "FAIL":
            require(item["first_failing_key"] is None,
                    "non-failure carries first failing key")
        if item["first_failing_key"] is not None:
            if criterion_id in D12_CRITERIA:
                validate_d12_key(item["first_failing_key"], criterion_id)
            else:
                validate_scientific_cell_key(
                    item["first_failing_key"], criterion_id)
        if criterion_id in CATEGORICAL_CRITERIA:
            require(item["maximum"] is None and item["witness"] is None,
                    "categorical criterion carries numeric witness")
        elif (criterion_id in CANDIDATE_SCIENTIFIC_CRITERIA and
              status in {"PASS", "FAIL"}):
            witness = item["witness"]
            require(type(item["maximum"]) in (int, float) and
                    math.isfinite(item["maximum"]) and
                    item["maximum"] >= 0 and
                    isinstance(witness, list) and len(witness) == 4 and
                    isinstance(witness[0], list) and
                    isinstance(witness[1], dict) and
                    binary64_from_bits_hex(witness[2]) == item["maximum"] and
                    witness[3] == item["result_ledger_sha256"],
                    "numeric criterion lacks reconstructible maximum witness")
            validate_scientific_cell_key(witness[0], criterion_id)
        if criterion_id in ORACLE_CRITERIA and status == "UNCOVERED":
            require(item["maximum"] is None and
                    item["witness"] == [
                        "EIGENBASIS_CERTIFICATION_FAILED",
                        EXPECTED_CELL_COUNTS[criterion_id],
                        item["result_ledger_sha256"]],
                    "oracle uncovered reason/result binding")
        if status == "INCOMPLETE":
            require(item["maximum"] is None and item["witness"] is None and
                    item["first_failing_key"] is None,
                    "incomplete criterion carries invented result")
    return True


def calculate_serial_only_disposition(criteria, context=None):
    """Evaluate the closed race-only serial qualification exception."""
    ineligible = {
        "serial_only_qualification_eligible": False,
        "serial_only_reason": "NOT_ELIGIBLE",
        "threaded_only_failure_ledger_sha256": None,
    }
    if context is None:
        return ineligible
    require(set(context) == {"complete_tsan_tuple_count",
                             "complete_tsan_cell_count",
                             "cache_disabled_tsan_pass", "failures"},
            "serial-only context shape")
    if (context["complete_tsan_tuple_count"] != 588 or
            context["complete_tsan_cell_count"] !=
            EXPECTED_CELL_COUNTS["d12_instrumented_tsan"] or
            context["cache_disabled_tsan_pass"] is not True):
        return ineligible
    statuses = {item["criterion_id"]: item["status"] for item in criteria}
    if (statuses.get("d12_instrumented_tsan") != "FAIL" or
            any(statuses[criterion_id] != "PASS"
                for criterion_id in CRITERION_IDS
                if criterion_id != "d12_instrumented_tsan")):
        return ineligible
    failures = context["failures"]
    if not isinstance(failures, list) or not failures:
        return ineligible
    keys = []
    for item in failures:
        if (not isinstance(item, dict) or set(item) != {"key", "reason"} or
                item["reason"] != "THREADED_CACHE_RACE"):
            return ineligible
        try:
            validate_d12_key(item["key"], "d12_instrumented_tsan")
        except QualificationError:
            return ineligible
        if item["key"][3] != "threaded_cache":
            return ineligible
        keys.append(item["key"])
    try:
        failure_digest = generic_key_ledger_sha256(keys)
    except QualificationError:
        return ineligible
    return {
        "serial_only_qualification_eligible": True,
        "serial_only_reason": "ELIGIBLE_PENDING_EXPLICIT_USER_DECISION",
        "threaded_only_failure_ledger_sha256": failure_digest,
    }


def calculate_verdict(criteria, serial_context=None):
    failed = [item["criterion_id"] for item in criteria if item["status"] == "FAIL"]
    incomplete = [item["criterion_id"] for item in criteria if item["status"] == "INCOMPLETE"]
    uncovered = [item["criterion_id"] for item in criteria if item["status"] == "UNCOVERED"]
    omitted = [item["criterion_id"] for item in criteria if item["status"].startswith("OMITTED_")]
    if failed:
        status, decisive = "FAIL", failed[0]
    elif incomplete or uncovered:
        status = "INCOMPLETE"
        decisive = next(item["criterion_id"] for item in criteria
                        if item["status"] in {"INCOMPLETE", "UNCOVERED"})
    else:
        require(all(item["status"] == "PASS" for item in criteria),
                "PASS attempted with non-PASS criterion")
        status, decisive = "PASS", None
    serial = calculate_serial_only_disposition(criteria, serial_context)
    return {"status": status, "first_decisive_criterion": decisive,
            "failed": failed, "incomplete": incomplete, "uncovered": uncovered,
            "omitted": omitted,
            "serial_only_qualification_eligible":
                serial["serial_only_qualification_eligible"],
            "serial_only_reason": serial["serial_only_reason"],
            "threaded_only_failure_ledger_sha256":
                serial["threaded_only_failure_ledger_sha256"],
            "report_content_sha256": ZERO_SHA256,
            "qualification_decided": False, "d9a_reopened": False,
            "b3_unblocked": False, "far_selected": False,
            "production_authorized": False}


def validate_report(report):
    validate_schema_instance(report)
    validate_criteria(report["criteria"])
    for binary_name in ("row_provider", "representation_candidate",
                        "exact_dyadic_boundary"):
        binary = report["binaries"][binary_name]
        require(binary["availability"]["state"] == "PRESENT" and
                binary["sources"] and
                all(binary[field]["state"] == "PRESENT" for field in
                    ("compiler_command", "compiler_version", "link_map",
                     "dynamic_dependencies")),
                "{} compile/link provenance incomplete".format(binary_name))
        for dependency_name, version in (("gmp", "6.3.0"),
                                         ("mpfr", "4.2.2"),
                                         ("opensubdiv", "3.7.0")):
            dependency = binary["dependencies"][dependency_name]
            require(dependency["version"] == version and
                    all(dependency[field]["state"] == "PRESENT" for field in
                        ("source_archive", "build_provenance",
                         "install_provenance", "link_map",
                         "dynamic_dependencies")),
                    "{} {} provenance incomplete".format(
                        binary_name, dependency_name))
    ledgers = report["matrix"]["ledgers"]
    require(len(ledgers) == 34 and
            {item["criterion_id"] for item in ledgers} == set(CRITERION_IDS),
            "matrix criterion-ledger coverage")
    by_key = {(item["criterion_id"], item["partition"]): item
              for item in ledgers}
    require(len(by_key) == len(ledgers), "duplicate criterion ledger partition")
    require([partition for criterion, partition in by_key
             if criterion == "oracle_coverage_and_crosscheck"] ==
            ["oracle_request", "covered", "uncovered"],
            "oracle ledger partitions")
    for item in ledgers:
        criterion_id = item["criterion_id"]
        expected = EXPECTED_CELL_COUNTS[criterion_id]
        if item["partition"] in ("covered", "uncovered"):
            require(item["expected_count"] is None,
                    "post-oracle partition predicted before oracle")
        else:
            require(item["expected_count"] == expected,
                    "pre-result ledger expected-count drift")
        if item["availability"]["state"] == "PRESENT":
            require(item["key_ledger_sha256"] == item["availability"]["sha256"] and
                    item["omission_blocker"] is None,
                    "present ledger binding mismatch")
            if item["partition"] not in ("covered", "uncovered"):
                require(item["observed_count"] == item["expected_count"],
                        "present pre-result ledger count mismatch")
        else:
            require(item["key_ledger_sha256"] is None and
                    item["observed_count"] == 0 and
                    item["omission_blocker"] == "bindings_and_independence",
                    "unavailable ledger lacks exact causal omission")
    oracle_request = by_key[("oracle_coverage_and_crosscheck",
                             "oracle_request")]
    oracle_covered = by_key[("oracle_coverage_and_crosscheck", "covered")]
    oracle_uncovered = by_key[("oracle_coverage_and_crosscheck", "uncovered")]
    require(oracle_covered["availability"]["state"] == "PRESENT" and
            oracle_covered["observed_count"] == 0 and
            oracle_covered["key_ledger_sha256"] == sha256_bytes(b"[]") and
            oracle_uncovered["availability"]["state"] == "PRESENT" and
            oracle_uncovered["observed_count"] ==
                EXPECTED_CELL_COUNTS["oracle_coverage_and_crosscheck"] and
            oracle_uncovered["key_ledger_sha256"] ==
                oracle_request["key_ledger_sha256"],
            "oracle covered/uncovered partition is not empty/request")
    primary_ledgers = {criterion: by_key[(criterion,
                                         "oracle_request" if criterion ==
                                         "oracle_coverage_and_crosscheck" else "all")]
                       for criterion in CRITERION_IDS}
    for criterion in report["criteria"]:
        expected = EXPECTED_CELL_COUNTS[criterion["criterion_id"]]
        require(criterion["expected_cell_count"] == expected,
                "criterion expected-cell count drift")
        ledger = primary_ledgers[criterion["criterion_id"]]
        require(criterion["key_ledger_sha256"] == ledger["key_ledger_sha256"],
                "criterion/matrix ledger digest mismatch")
    d12 = report["d12_artifact"]
    d12_statuses = {item["status"] for item in report["criteria"]
                    if item["criterion_id"] in D12_CRITERIA}
    if d12["execution_state"] == "UNQUALIFIED_PLATFORM":
        require(d12["availability"]["state"] == "PRESENT" and
                d12["exact_head"] == report["identity"]["git_end"]["git_commit"] and
                SHA256_RE.fullmatch(d12["physical_fingerprint_sha256"] or "") and
                d12_statuses == {"INCOMPLETE"},
                "hosted D12 state/result mismatch")
    elif d12["execution_state"] == "QUALIFIED_PLATFORM":
        require(d12["availability"]["state"] == "PRESENT" and
                d12["exact_head"] == report["identity"]["git_end"]["git_commit"] and
                d12_statuses.issubset({"PASS", "FAIL"}),
                "qualified D12 state/result mismatch")
    else:
        require(d12["availability"]["state"] != "PRESENT" and
                d12_statuses == {"INCOMPLETE"},
                "non-present D12 state/result mismatch")
    expected = calculate_verdict(report["criteria"])
    for key in expected:
        if key != "report_content_sha256":
            require(report["verdict"][key] == expected[key],
                    "verdict contradicts criteria: {}".format(key))
    digest_copy = copy.deepcopy(report)
    digest_copy["verdict"]["report_content_sha256"] = ZERO_SHA256
    require(report["verdict"]["report_content_sha256"] ==
            sha256_bytes(jcs_bytes(digest_copy)), "report content digest mismatch")
    require(report["verdict"]["status"] != "PASS",
            "this package lacks the frozen primary oracle and cannot PASS")
    return True


def fixture_hash_bindings():
    expected, actual = [], []
    for relative, frozen_hash in sorted(FROZEN_FIXTURE_SHA256.items()):
        expected.append({"path": relative,
                         "availability": availability("PRESENT", frozen_hash)})
        path = ROOT / relative
        if not path.is_file():
            observed = availability("MISSING", reason_code="EXPECTED_PATH_MISSING")
        else:
            observed_hash = sha256_file(path)
            observed = (availability("PRESENT", observed_hash)
                        if observed_hash == frozen_hash else
                        availability("INVALID", reason_code="HASH_MISMATCH"))
        actual.append({"path": relative, "availability": observed})
    require(expected == actual, "frozen fixture file hash inventory drift")
    return expected, actual


def inspect_d12_evidence(path_text, expected_head):
    """Authenticate observed D12 bytes without synthesizing their bindings."""
    if not path_text:
        return ({"availability": availability(
                    "UNAVAILABLE", reason_code="PLATFORM_UNAVAILABLE"),
                 "execution_state": "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                 "exact_head": None, "physical_fingerprint_sha256": None,
                 "omission_blocker": "bindings_and_independence"},
                "D12 evidence unavailable")
    path = pathlib.Path(path_text).resolve()
    if not path.is_file():
        return ({"availability": availability(
                    "MISSING", reason_code="EXPECTED_PATH_MISSING"),
                 "execution_state": "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                 "exact_head": None, "physical_fingerprint_sha256": None,
                 "omission_blocker": "bindings_and_independence"},
                "D12 evidence path missing")
    try:
        raw = path.read_bytes()
        value = strict_json_bytes(raw)
        require(isinstance(value, dict), "D12 evidence root")
        B2.validate_evidence_document(value)
        checkpoint_head = value["release_checkpoint"]["binding"]["git_head"]
        platform = value["platform_qualification"]
        git_observation = platform["git_identity"]
        require(checkpoint_head == expected_head and
                git_observation.get("head_query_ok") is True and
                git_observation.get("head") == checkpoint_head and
                git_observation.get("worktree_empty") is True,
                "D12 artifact exact-head/worktree binding mismatch")
        probe = platform["current_probe"]
        require(isinstance(probe, dict) and
                isinstance(probe.get("fingerprint"), dict),
                "D12 artifact physical probe missing")
        observed_fingerprint_sha256 = sha256_bytes(
            jcs_bytes(probe["fingerprint"]))
        hosted = platform.get("status") == "UNQUALIFIED_PLATFORM"
        qualified = platform.get("status") == "QUALIFIED"
        require(hosted or qualified, "D12 platform state")
        # The inherited B2 artifact is valuable hosted raw evidence, but it
        # does not claim that anchored-row construction/evaluation work was
        # included.  It can therefore authenticate an UNQUALIFIED_PLATFORM
        # observation only; it can never qualify or fail a B2c D12 gate.
        b2c = value.get("anchored_row_representation_d12")
        representation_included = (
            isinstance(b2c, dict) and
            b2c.get("candidate") == CANDIDATE and
            b2c.get("construction_and_evaluation_work_included") is True)
        require(hosted or representation_included,
                "qualified D12 artifact omits anchored representation work")
        expectation = ("hosted D12 evidence is unqualified and anchored "
                       "representation work is not included"
                       if not representation_included else
                       "hosted D12 evidence is unqualified")
        return ({"availability": availability(
                    "PRESENT", sha256_bytes(raw)),
                 "execution_state": ("UNQUALIFIED_PLATFORM" if hosted else
                                     "QUALIFIED_PLATFORM"),
                 "exact_head": checkpoint_head,
                 "physical_fingerprint_sha256":
                     observed_fingerprint_sha256,
                 "omission_blocker": None}, expectation)
    except Exception:
        return ({"availability": availability(
                    "INVALID", reason_code="PROVENANCE_INVALID"),
                 "execution_state": "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                 "exact_head": None, "physical_fingerprint_sha256": None,
                 "omission_blocker": "bindings_and_independence"},
                "D12 artifact malformed, cross-head, dirty, or invalid provenance")


def canonical_sample_order(manifest):
    result = []
    for policy in manifest["sample_policies"]:
        for sample in policy.get("samples", []):
            if sample["id"] not in result:
                result.append(sample["id"])
    require(len(result) == 34, "canonical sample order must contain 34 unique samples")
    return result


def validate_derived_cardinalities(manifest, checkpoint):
    regular_face_count = 0
    total_face_count = 0
    for job in B2.valid_content_jobs(manifest):
        _, faces, valences = B2.independent_mesh(job)
        total_face_count += len(faces)
        regular_face_count += sum(
            all(valences[source_id] == 6 for source_id in face)
            for face in faces)
    # Ten regular samples, four level/cache combinations, six rows, three
    # anchors; geometry adds three axes and each scalar integrand has two views.
    regular_groups = regular_face_count * 10 * 4
    require(regular_groups * 6 * 3 ==
            EXPECTED_CELL_COUNTS["regular_analytic_exact_rows"],
            "regular exact-row cardinality drift")
    require(regular_groups * 6 * 3 * 3 ==
            EXPECTED_CELL_COUNTS["regular_analytic_emitted_geometry"],
            "regular geometry cardinality drift")
    require(regular_groups * 3 * 2 ==
            EXPECTED_CELL_COUNTS["regular_analytic_area_integrand"] ==
            EXPECTED_CELL_COUNTS["regular_analytic_legacy_volume_integrand"],
            "regular integrand cardinality drift")
    require(total_face_count * 7 * 2 ==
            EXPECTED_CELL_COUNTS["d12_retained_payload"],
            "D12 retained-payload cardinality drift")
    bfr_cases = [item for item in checkpoint["numeric_cases"]
                 if item["candidate"] == "bfr"]
    rss_count = sum(1 + item["rss_expected_named_sample_count"]
                    for item in bfr_cases)
    require(rss_count == EXPECTED_CELL_COUNTS["d12_peak_rss"],
            "D12 RSS cardinality drift")
    return True


def make_artifacts(checkpoint):
    result = []
    for item in checkpoint["numeric_cases"]:
        result.append({"content_id": item["content_identity_key"],
                       "candidate": item["candidate"],
                       "cache_mode": item["applicable_mode"],
                       "level": item["approximation_level"],
                       "availability": availability("PRESENT", item["complete_json_artifact_sha256"]),
                       "compressed_sha256": item["complete_json_artifact_sha256"],
                       "json_sha256": item["complete_json_sha256"],
                       "b2rowv1_sha256": item["canonical_rows_sha256"]})
    return result


def result_commitment(key_ledger_sha256, observed_count, status, details):
    """Bind an execution-owned result stream or closed coverage disposition."""
    require(SHA256_RE.fullmatch(key_ledger_sha256 or "") is not None,
            "result commitment key ledger")
    return sha256_bytes(jcs_bytes({
        "encoding": "anchored-row-result-ledger-v1",
        "key_ledger_sha256": key_ledger_sha256,
        "observed_count": observed_count,
        "status": status,
        "stream_commitment": details,
    }))


def canonical_result_commitment(key_ledger_sha256, observed_count, status,
                                canonical_stream_sha256):
    require(SHA256_RE.fullmatch(canonical_stream_sha256 or "") is not None,
            "canonical result stream digest")
    return result_commitment(
        key_ledger_sha256, observed_count, status,
        {"canonical_result_stream_encoding":
             "rfc8785-key-outcome-exact-target-reason-v1",
         "canonical_result_stream_sha256": canonical_stream_sha256})


def make_criteria(worktree, all_required_bindings_present, ledgers,
                  executed=None, oracle_result_digest=None,
                  d12_expectation="qualified physical B2c D12 evidence unavailable"):
    # This implementation deliberately self-identifies as incomplete until it
    # can construct every pre-result ledger and execute all pre-oracle cells.
    # The missing scientific oracle is separately recorded by its capability;
    # it is not misreported as a candidate failure.
    binding_status = ("PASS" if worktree["state"] == "PRESENT" and
                      all_required_bindings_present else "INCOMPLETE")
    executed = executed or {}
    ledger_by_criterion = {}
    for ledger in ledgers:
        if ledger["partition"] in ("all", "oracle_request"):
            ledger_by_criterion[ledger["criterion_id"]] = ledger
    records = []
    binding_ledger = ledger_by_criterion[
        "bindings_and_independence"]["key_ledger_sha256"]
    records.append(criterion_record(
        "bindings_and_independence", binding_status,
        expectation="all bindings present and independent",
        expected=1, observed=1, ledger=binding_ledger,
        result_ledger=result_commitment(
            binding_ledger, 1, binding_status, "validated_binding_record")))
    inventory_ledger = ledger_by_criterion[
        "complete_artifact_inventory"]["key_ledger_sha256"]
    records.append(criterion_record("complete_artifact_inventory", "PASS",
                                    expectation="exact 294 slots", expected=294, observed=294,
                                    ledger=inventory_ledger,
                                    result_ledger=result_commitment(
                                        inventory_ledger, 294, "PASS",
                                        "validated_artifact_inventory")))
    raw_ledger = ledger_by_criterion[
        "raw_bfr_d9a_reproduction"]["key_ledger_sha256"]
    records.append(criterion_record("raw_bfr_d9a_reproduction", "PASS",
                                    expectation="124 failing Bfr cases and frozen maximum",
                                    expected=196, observed=196,
                                    ledger=raw_ledger,
                                    result_ledger=result_commitment(
                                        raw_ledger, 196, "PASS",
                                        "validated_raw_d9a_reproduction")))
    blocker = "bindings_and_independence"
    for criterion_id in CRITERION_IDS[3:]:
        if criterion_id in executed:
            item = executed[criterion_id]
            default_expectations = {
                "representation_structure":
                    "all three anchors present; retained bits unchanged; exact effective sum is target",
                "constant_field_bits":
                    "five frozen constants reproduce exact position/positive-zero derivative bits",
                "relabel_exact_effective_coefficients":
                    "inverse rank relabeling preserves every exact effective numerator",
                "cache_mode_bit_identity":
                    "cache-disabled and serial-cache rows are bitwise identical",
            }
            key_digest = item["digest"]
            result_digest = item.get("result_digest") or result_commitment(
                key_digest, item["observed_count"], item["status"],
                item.get("stream_commitment", {
                    "failure_count": item["failure_count"],
                    "maximum": item.get("maximum"),
                }))
            categorical = criterion_id in CATEGORICAL_CRITERIA
            maximum = None if categorical else item.get("maximum")
            witness = None if categorical else item.get("witness")
            if not categorical and witness is None:
                witness = [result_digest, maximum,
                           binary64_bits_hex(maximum)]
            records.append(criterion_record(
                criterion_id, item["status"],
                expectation=item.get("expectation",
                                     default_expectations.get(criterion_id)),
                expected=EXPECTED_CELL_COUNTS[criterion_id],
                observed=item["observed_count"], ledger=key_digest,
                result_ledger=result_digest,
                target=item.get("target", 0.0),
                maximum=maximum, witness=witness,
                first_failure=item["first_failing_key"]))
            continue
        if criterion_id == "oracle_coverage_and_crosscheck":
            key_digest = ledger_by_criterion[criterion_id]["key_ledger_sha256"]
            if key_digest is None:
                key_digest = next(
                    item["key_ledger_sha256"] for item in ledgers
                    if item["criterion_id"] == criterion_id and
                    item["partition"] == "uncovered")
            result_digest = (canonical_result_commitment(
                key_digest, EXPECTED_CELL_COUNTS[criterion_id], "UNCOVERED",
                oracle_result_digest) if oracle_result_digest else
                result_commitment(
                    key_digest, EXPECTED_CELL_COUNTS[criterion_id],
                    "UNCOVERED", "EIGENBASIS_CERTIFICATION_FAILED"))
            records.append(criterion_record(
                criterion_id, "UNCOVERED",
                expectation="EIGENBASIS_CERTIFICATION_FAILED",
                expected=EXPECTED_CELL_COUNTS[criterion_id],
                observed=EXPECTED_CELL_COUNTS[criterion_id],
                ledger=key_digest, result_ledger=result_digest,
                witness=["EIGENBASIS_CERTIFICATION_FAILED",
                         EXPECTED_CELL_COUNTS[criterion_id], result_digest]))
            continue
        if criterion_id in D12_CRITERIA:
            records.append(criterion_record(
                criterion_id, "INCOMPLETE", expectation=d12_expectation,
                expected=EXPECTED_CELL_COUNTS[criterion_id], observed=0,
                ledger=ledger_by_criterion[criterion_id]["key_ledger_sha256"]))
            continue
        records.append(criterion_record(criterion_id,
                                        "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                                        blocker=blocker,
                                        expectation=
                                            "requires complete frozen proof infrastructure",
                                        expected=EXPECTED_CELL_COUNTS[criterion_id],
                                        observed=0,
                                        ledger=ledger_by_criterion[
                                            criterion_id]["key_ledger_sha256"]))
    require(len(records) == 32, "criterion record count")
    return records


def iso_utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def execute(args):
    started = iso_utc_now()
    git_start, worktree_start = git_observations()
    checkpoint_path = pathlib.Path(args.checkpoint).resolve()
    require(checkpoint_path.is_file(), "checkpoint path missing before execution")
    checkpoint = strict_json_bytes(checkpoint_path.read_bytes())
    require(isinstance(checkpoint, dict) and
            checkpoint.get("schema_version") == 2 and
            checkpoint.get("kind") == "bfr_release_matrix_checkpoint" and
            checkpoint.get("complete") is True,
            "checkpoint is not complete schema-2 evidence")
    expected_head = args.expected_binding_head or (
        git_start["git_commit"] if git_start["state"] == "PRESENT" else None)
    # Reject an arbitrary old or unrelated checkpoint before any proof binary
    # or numerical replay is executed.
    require(git_start["state"] == "PRESENT" and
            GIT_RE.fullmatch(expected_head or "") is not None and
            checkpoint.get("binding", {}).get("git_head") == expected_head and
            git_start["git_commit"] == expected_head,
            "pre-execution Git/checkpoint binding mismatch")
    require(worktree_start["state"] == "PRESENT" and
            worktree_start["clean"] is True,
            "worktree must be clean before execution")
    candidate_self_test = run_json(args.candidate_binary, "--self-test",
                                   "anchored_row_candidate_self_test")
    require(candidate_self_test.get("status") == "ok" and
            candidate_self_test.get("rounding_mode") == "FE_TONEAREST" and
            candidate_self_test.get("fma_contraction_permitted") is False,
            "candidate self-test incomplete")
    boundary_self_test = run_json(args.exact_dyadic_boundary_binary, "--self-test",
                                  "exact_dyadic_boundary_self_test")
    require(boundary_self_test.get("status") == "ok" and
            boundary_self_test.get("precision_bits") == 544 and
            boundary_self_test.get("directed_rounding") is True,
            "exact dyadic boundary self-test incomplete")
    capability = run_json(args.exact_dyadic_boundary_binary, "--capability",
                          "independent_primary_capability")
    require(capability == {"coverage": "UNCOVERED",
                           "implementation_state": "INCOMPLETE",
                           "kind": "independent_primary_capability",
                           "missing_algorithms": [
                               "stock_mask_interval_matrix_construction",
                               "interval_eigenpair_krawczyk_certification",
                               "repeated_eigenspace_spectral_projector_certification",
                               "quartic_box_spline_interval_evaluation",
                               "certified_parametric_branch_mapping",
                               "independent_uniform_five_depth_intersection",
                           ],
                           "reason_code": "EIGENBASIS_CERTIFICATION_FAILED",
                           "status": "honest_incomplete",
                           "uniform_success_substituted_for_primary": False},
            "oracle capability must be the frozen honest uncovered state")

    preflight = B2A.analyze(args.checkpoint, args.artifact_dir,
                            args.provider_binary, expected_head)
    observations = preflight["observations"]
    require(observations["bfr_six_rows_examined"] == 1386000 and
            observations["bfr_coefficient_terms_examined"] == 12549936 and
            observations["raw_bfr_failing_case_count"] == 124 and
            B2A.binary64_bits_hex(observations["raw_bfr_max_ordered_sum_residual"]) ==
            B2A.binary64_bits_hex(2.0368522054550406e-11),
            "raw Bfr reproduction drift")
    manifest = B2.load_manifest()
    validate_derived_cardinalities(manifest, checkpoint)
    expected_fixtures, actual_fixtures = fixture_hash_bindings()
    scientific_ledgers = make_scientific_pre_result_ledgers(
        checkpoint, pathlib.Path(args.artifact_dir).resolve(), manifest)
    executed = execute_four_preoracle_criteria(
        args.candidate_binary, checkpoint, pathlib.Path(args.artifact_dir).resolve(),
        manifest)
    executed.update(execute_regular_row_criteria(
        args.candidate_binary, checkpoint,
        pathlib.Path(args.artifact_dir).resolve(), manifest))
    executed.update(execute_regular_integrand_criteria(
        args.candidate_binary, args.exact_dyadic_boundary_binary, checkpoint,
        pathlib.Path(args.artifact_dir).resolve(), manifest))
    executed.update(execute_component_criteria(
        args.candidate_binary, checkpoint,
        pathlib.Path(args.artifact_dir).resolve(), manifest,
        scientific_ledgers))
    git_end, worktree_end = git_observations()
    require_git_binding(git_start, git_end, worktree_start, worktree_end,
                        expected_head, checkpoint["binding"]["git_head"])

    candidate_source = ROOT / "experiments/anchored_row_qualification/candidate.cpp"
    boundary_source = ROOT / "experiments/anchored_row_qualification/exact_dyadic_boundary.cpp"
    provider_source = ROOT / "experiments/bfr_qualification/candidate.cpp"
    oracle_present = bool(args.independent_oracle_binary)
    dependencies = dependency_records(args)
    independent_record = binary_record(
        args.independent_oracle_binary, [], "primary_stam_plus_uniform_crosscheck",
        dependencies,
        present=oracle_present) if oracle_present else binary_record(
            "", [], "primary_stam_plus_uniform_crosscheck_absent", dependencies,
            present=False)
    binaries = {
        "row_provider": binary_record(
            args.provider_binary, [provider_source], "frozen_B2ROWV1_provider",
            dependencies, args.provider_command_file, args.compiler_version_file,
            args.provider_link_map, args.provider_dynamic_dependencies),
        "representation_candidate": binary_record(
            args.candidate_binary, [candidate_source], "anchored_difference_rows_v1",
            dependencies, args.candidate_command_file, args.compiler_version_file,
            args.candidate_link_map, args.candidate_dynamic_dependencies),
        "independent_oracle": independent_record,
        "exact_dyadic_boundary": binary_record(
            args.exact_dyadic_boundary_binary, [boundary_source],
            "exact_integer_over_2p1074_outward_MPFR_import", dependencies,
            args.boundary_command_file, args.compiler_version_file,
            args.boundary_link_map, args.boundary_dynamic_dependencies),
        "oracle_independence_audit": "INCOMPLETE",
    }
    ledgers = make_complete_pre_result_ledgers(
        checkpoint, pathlib.Path(args.artifact_dir).resolve(), manifest,
        executed, scientific_ledgers)
    d12_record, d12_expectation = inspect_d12_evidence(
        args.d12_evidence, expected_head)
    criteria = make_criteria(
        worktree_end, oracle_present, ledgers, executed,
        oracle_result_digest=scientific_ledgers[
            "oracle_coverage_and_crosscheck"]["uncovered_result_digest"],
        d12_expectation=d12_expectation)
    fingerprint_hash = sha256_bytes(jcs_bytes(B2.EXPECTED_PLATFORM_FINGERPRINT))
    report = {
        "identity": {"schema_id": SCHEMA_ID, "candidate": CANDIDATE,
                     "implementation_state":
                         "INCOMPLETE_MISSING_ORACLE_DEPENDENT_CELL_EXECUTION_D12_EXECUTION_AND_PRIMARY_STAM_UNIFORM_ORACLES",
                     "git_start": git_start, "git_end": git_end,
                     "worktree_start": worktree_start,
                     "worktree_end": worktree_end,
                     "base_merge_git_commit": APPROVED_B2B_MERGE,
                     "approved_b2b_merge_git_commit": APPROVED_B2B_MERGE,
                     "start_utc": started, "end_utc": iso_utc_now(),
                     "validator": availability(
                         "PRESENT", sha256_file(pathlib.Path(__file__).resolve()))},
        "binaries": binaries,
        "authority": {"manifest_file_sha256": B2.MANIFEST_FILE_SHA256,
                      "manifest_contract_sha256": B2.MANIFEST_CONTRACT_SHA256,
                      "rows": list(ROW_ORDER), "row_invariant_tolerance": 1.0e-12,
                      "d10": D10, "component_targets": COMPONENT_TARGETS,
                      "inner_radius_rule": "r < 2^-8 excluded",
                      "anchor_order": list(ANCHORS), "relabels": list(RELABELS),
                      "canonical_sample_order": canonical_sample_order(manifest),
                      "radius_exponents": list(range(1, 9)),
                      "ray_sequence": [0, 1, 2],
                      "source_order": "strictly_increasing_signed_source_id",
                      "expected_fixture_files": expected_fixtures,
                      "actual_fixture_files": actual_fixtures,
                      "d12_contract": B2.D12,
                      "physical_fingerprint": {"sha256": fingerprint_hash}},
        "checkpoint": {"availability": availability("PRESENT", sha256_file(checkpoint_path)),
                       "git_head": checkpoint["binding"]["git_head"],
                       "row_provider_binary_sha256": checkpoint["binding"]["candidate_binary_sha256"],
                       "release_complete": checkpoint["complete"]},
        "artifacts": make_artifacts(checkpoint),
        "matrix": {"expected_artifacts": 294, "observed_artifacts": 294,
                   "expected_bfr_cases": 196, "observed_bfr_cases": 196,
                   "expected_far_cases": 98, "observed_far_cases": 98,
                   "expected_cache_pairs": 98, "observed_cache_pairs": observations["cache_mode_bitwise_equal_pair_count"],
                   "expected_raw_bfr_rows": 1386000, "observed_raw_bfr_rows": observations["bfr_six_rows_examined"],
                   "expected_anchor_rows": 4158000, "observed_anchor_rows": observations["bfr_six_rows_examined"] * 3,
                   "expected_provider_terms": 12549936, "observed_provider_terms": observations["bfr_coefficient_terms_examined"],
                   "expected_anchor_terms": 37649808, "observed_anchor_terms": observations["bfr_coefficient_terms_examined"] * 3,
                   "ledgers": ledgers, "unexpected_paths": []},
        "criteria": criteria,
        "d12_artifact": d12_record,
        "verdict": calculate_verdict(criteria),
    }
    digest_copy = copy.deepcopy(report)
    digest_copy["verdict"]["report_content_sha256"] = ZERO_SHA256
    report["verdict"]["report_content_sha256"] = sha256_bytes(jcs_bytes(digest_copy))
    validate_report(report)
    return report


def self_test_report():
    schema = load_schema()
    require(schema["additionalProperties"] is False, "top-level schema not closed")
    require(len(CRITERION_IDS) == 32 and len(set(CRITERION_IDS)) == 32,
            "criterion set cardinality")
    criteria_schema = schema["properties"]["criteria"]
    require(criteria_schema.get("items") is False and
            len(criteria_schema.get("prefixItems", [])) == len(CRITERION_IDS),
            "schema criterion slots are not frozen")
    schema_ids = []
    for slot in criteria_schema["prefixItems"]:
        definition = schema["$defs"][slot["$ref"].split("/")[-1]]
        schema_ids.append(definition["allOf"][1]["properties"][
            "criterion_id"]["const"])
    require(schema_ids == list(CRITERION_IDS),
            "schema criterion order differs from executable order")
    ledger_schema = schema["$defs"]["matrix"]["properties"]["ledgers"]
    require(ledger_schema.get("items") is False and
            len(ledger_schema.get("prefixItems", [])) == 34,
            "schema ledger slots are not frozen")
    require(exact_binary64_numerator(1.0) == 1 << 1074, "exact dyadic 1.0")
    require(exact_binary64_numerator(2.0 ** -1074) == 1, "exact dyadic minimum subnormal")
    synthetic = {"row_kind": "position", "source_ids": [2, 5, 9],
                 "coefficients": [0.5, 0.25, 0.2500000000000001]}
    for anchor in synthetic["source_ids"]:
        values = effective_numerators(synthetic, anchor)
        require(sum(values.values()) == 1 << 1074, "effective exact invariant")
    require(jcs_bytes({"b": 1.0e-7, "a": 1.0e-6}) == b'{"a":0.000001,"b":1e-7}',
            "JCS numeric boundary")
    return {"candidate": CANDIDATE, "criterion_count": len(CRITERION_IDS),
            "exact_dyadic_common_denominator_exponent": -1074,
            "implementation_state":
                "INCOMPLETE_MISSING_ORACLE_DEPENDENT_CELL_EXECUTION_D12_EXECUTION_AND_PRIMARY_STAM_UNIFORM_ORACLES",
            "independent_primary_oracle_available": False,
            "kind": "anchored_row_qualification_self_test",
            "qualification_pass_permitted_without_oracle": False,
            "report_schema": SCHEMA_ID, "status": "ok"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--checkpoint")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--provider-binary")
    parser.add_argument("--candidate-binary")
    parser.add_argument("--exact-dyadic-boundary-binary")
    parser.add_argument("--independent-oracle-binary")
    parser.add_argument("--compiler-version-file")
    parser.add_argument("--provider-command-file")
    parser.add_argument("--provider-link-map")
    parser.add_argument("--provider-dynamic-dependencies")
    parser.add_argument("--candidate-command-file")
    parser.add_argument("--candidate-link-map")
    parser.add_argument("--candidate-dynamic-dependencies")
    parser.add_argument("--boundary-command-file")
    parser.add_argument("--boundary-link-map")
    parser.add_argument("--boundary-dynamic-dependencies")
    parser.add_argument("--gmp-archive")
    parser.add_argument("--gmp-build-provenance")
    parser.add_argument("--gmp-install-provenance")
    parser.add_argument("--gmp-link-provenance")
    parser.add_argument("--gmp-dynamic-dependency")
    parser.add_argument("--mpfr-archive")
    parser.add_argument("--mpfr-build-provenance")
    parser.add_argument("--mpfr-install-provenance")
    parser.add_argument("--mpfr-link-provenance")
    parser.add_argument("--mpfr-dynamic-dependency")
    parser.add_argument("--opensubdiv-archive")
    parser.add_argument("--opensubdiv-build-provenance")
    parser.add_argument("--opensubdiv-install-provenance")
    parser.add_argument("--opensubdiv-link-provenance")
    parser.add_argument("--opensubdiv-dynamic-dependency")
    parser.add_argument("--d12-evidence")
    parser.add_argument("--expected-binding-head")
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.self_test:
            supplied = [value for key, value in vars(args).items()
                        if key not in ("self_test", "json")]
            require(not any(supplied), "self-test accepts no evidence inputs")
            value = self_test_report()
            encoded = jcs_bytes(value) + b"\n"
        else:
            require(args.checkpoint and args.artifact_dir and args.provider_binary and
                    args.candidate_binary and args.exact_dyadic_boundary_binary,
                    "execution requires checkpoint, artifacts, provider, candidate, and exact boundary")
            provenance_arguments = [
                args.compiler_version_file, args.provider_command_file,
                args.provider_link_map, args.provider_dynamic_dependencies,
                args.candidate_command_file, args.candidate_link_map,
                args.candidate_dynamic_dependencies, args.boundary_command_file,
                args.boundary_link_map, args.boundary_dynamic_dependencies,
                args.gmp_archive, args.gmp_build_provenance,
                args.gmp_install_provenance, args.gmp_link_provenance,
                args.gmp_dynamic_dependency, args.mpfr_archive,
                args.mpfr_build_provenance, args.mpfr_install_provenance,
                args.mpfr_link_provenance, args.mpfr_dynamic_dependency,
                args.opensubdiv_archive, args.opensubdiv_build_provenance,
                args.opensubdiv_install_provenance,
                args.opensubdiv_link_provenance,
                args.opensubdiv_dynamic_dependency,
            ]
            require(all(provenance_arguments),
                    "execution requires every frozen compile/link/dependency provenance path")
            value = execute(args)
            encoded = jcs_bytes(value)
            if args.output:
                pathlib.Path(args.output).write_bytes(encoded)
        if args.json or not args.output:
            sys.stdout.buffer.write(encoded)
        return 0
    except (QualificationError, B2A.PreflightError, B2.QualificationError,
            OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        failure = {"error": str(error), "kind": "anchored_row_qualification",
                   "status": "failed"}
        sys.stderr.buffer.write(jcs_bytes(failure) + b"\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
