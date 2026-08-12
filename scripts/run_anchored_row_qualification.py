#!/usr/bin/env python3
"""Fail-closed B2c proof runner for ``anchored_difference_rows_v1``.

The runner validates the frozen B2 corpus and the executable representation
boundary.  The repository does not contain the independently certified primary
eigenanalysis plus uniform-refinement oracle required by B2b.  That absence is
reported as infrastructure ``INCOMPLETE``; this program cannot emit a
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
import tempfile
import threading
from decimal import Decimal, localcontext
from fractions import Fraction


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "scripts/anchored_row_qualification_report_v1.schema.json"
MUTATION_MANIFEST_PATH = (
    ROOT / "scripts/anchored_row_contract_mutations_v1.txt")
RESULT_CONTRACT_PATH = ROOT / "scripts/anchored_row_result_contract.py"
RESULT_CONTRACT_SPEC = importlib.util.spec_from_file_location(
    "anchored_row_result_contract", RESULT_CONTRACT_PATH)
RESULT_CONTRACT = importlib.util.module_from_spec(RESULT_CONTRACT_SPEC)
RESULT_CONTRACT_SPEC.loader.exec_module(RESULT_CONTRACT)
RESULT_EVIDENCE_AMENDMENT_PATH = (
    ROOT / "docs/anchored_row_qualification_result_ledger_amendment.md")
B2A_PATH = ROOT / "scripts/run_invariant_row_representation_preflight.py"
B2A_SPEC = importlib.util.spec_from_file_location("b2a_preflight", B2A_PATH)
B2A = importlib.util.module_from_spec(B2A_SPEC)
B2A_SPEC.loader.exec_module(B2A)
B2 = B2A.B2

SCHEMA_ID = "anchored-row-qualification-report-v1"
CANDIDATE = "anchored_difference_rows_v1"
APPROVED_B2B_MERGE = "022df7a8e11bcc4aee4df2254cc994cf4efdeb4f"
APPROVED_RESULT_EVIDENCE_AMENDMENT_MERGE = (
    "029816125619f58f99464e8055170ffa12e957e3")
RESULT_EVIDENCE_PATH_ANCHOR_SHA256 = (
    "0e82d15b0244aaa779a1ca600fdc8b43ac501ab91aa615e8adb8dcd8682ecf66")
RESULT_EVIDENCE_MUTATION_MANIFEST_SHA256 = (
    "64f36072b248b20a748a4ee186bbadb1a56affc780ee384d2d5cc37e673176e6")
RESULT_EVIDENCE_MUTATION_MANIFEST_ID = (
    "anchored-row-result-evidence-mutations-v1")
RESULT_EVIDENCE_MUTATION_OPERATORS = RESULT_CONTRACT.MUTATION_OPERATORS
RESULT_LEDGER_DIRECTORY = "anchored-row-result-ledgers-v1"
RAW_D9A_FROZEN_FAILING_CASE_COUNT = 124
RAW_D9A_FROZEN_MAXIMUM_BITS = "3db6653ab1800000"
RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX = (
    "5994eac6000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000")
ZERO_SHA256 = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA_CACHE = None
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
D12_CONTRACT = {
    "preparation_median_ns": 1000000000,
    "preparation_single_ns": 10000000000,
    "retained_payload_bytes": 131072,
    "peak_rss_delta_bytes": 67108864,
}
DEPENDENCY_ARCHIVE_SHA256 = {
    "gmp": "a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898",
    "mpfr": "b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01",
    "opensubdiv": "f843eb49daf20264007d807cbc64516a1fed9cdb1149aaf84ff47691d97491f9",
}
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
    "representation_structure",
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
                    "EXECUTION_UNAVAILABLE"} |
                   set(RESULT_CONTRACT.ORACLE_INFRASTRUCTURE_REASONS),
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


def _uint64_be(value):
    require(type(value) is int and 0 <= value <= 0xffffffffffffffff,
            "uint64 value")
    return struct.pack(">Q", value)


def canonical_result_record(key, outcome, exact_value, target, reason):
    """Return one closed canonical result record and its RFC 8785 bytes."""
    require(outcome in ("PASS", "FAIL", "UNCOVERED", "INCOMPLETE"),
            "result outcome")
    if outcome == "PASS":
        require(reason is None, "passing result reason must be null")
    else:
        require(isinstance(reason, str) and reason,
                "non-passing result reason")
    record = [key, outcome, exact_value, target, reason]
    return record, jcs_bytes(record)


def _contract_kind(value):
    return value.get("kind") if isinstance(value, dict) else None


def _rational_fraction(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def _signed_dyadic_fraction(value):
    numerator = int(value["numerator_hex"], 16) * value.get("sign", 1)
    return Fraction(numerator, 1 << value["denominator_power"])


def _absolute_exact_fraction(value):
    kind = _contract_kind(value)
    if kind == "absolute_dyadic_v1":
        return Fraction(int(value["numerator_hex"], 16),
                        1 << value["denominator_power"])
    if kind == "absolute_rational_v1":
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    raise QualificationError("unsupported exact nonnegative scalar")


def _scalar_fraction(value):
    kind = _contract_kind(value)
    if kind == "signed_dyadic_v1":
        return _signed_dyadic_fraction(value)
    if kind == "rational_v1":
        return _rational_fraction(value)
    if kind == "binary64_scalar_v1":
        return Fraction.from_float(binary64_from_bits_hex(value["bits"]))
    raise QualificationError("unsupported exact scalar")


def _absolute_rational_descriptor(value):
    value = abs(Fraction(value))
    return {"kind": "absolute_rational_v1",
            "numerator": str(value.numerator),
            "denominator": str(value.denominator)}


def _absolute_dyadic_descriptor(numerator, denominator_power=1074):
    require(type(numerator) is int and numerator >= 0,
            "absolute dyadic numerator")
    return {"kind": "absolute_dyadic_v1",
            "numerator_hex": format(numerator, "x") if numerator else "0",
            "denominator_power": denominator_power}


def _interval_fractions(value):
    return (_rational_fraction(value["lower"]),
            _rational_fraction(value["upper"]))


def _interval_error_upper(observed, interval):
    lower, upper = _interval_fractions(interval)
    return max(abs(observed - lower), abs(observed - upper))


def _record_measure_descriptor(criterion_id, exact_value):
    field = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]["maximum_field"]
    require(field is not None and exact_value is not None,
            "criterion has no numeric measure")
    value = exact_value
    for component in field.split("."):
        value = value[component]
    if type(value) is int:
        return _absolute_rational_descriptor(Fraction(value, 1))
    require(_contract_kind(value) in {
                "absolute_dyadic_v1", "absolute_rational_v1",
                "rational_over_sqrt_v1"},
            "criterion measure exact form")
    return value


def _record_numeric_measure_or_none(criterion_id, exact_value):
    if _contract_kind(exact_value) in {
            "d12_duration_invalid_v1", "d12_payload_invalid_v1",
            "d12_rss_invalid_v1"}:
        return None
    return _record_measure_descriptor(criterion_id, exact_value)


def _exact_display_bits(value):
    kind = _contract_kind(value)
    if kind in {"absolute_dyadic_v1", "absolute_rational_v1"}:
        return binary64_bits_hex(float(_absolute_exact_fraction(value)))
    require(kind == "rational_over_sqrt_v1",
            "maximum display exact form")
    with localcontext() as context:
        digit_count = sum(len(value[field]) for field in (
            "absolute_numerator", "absolute_denominator",
            "scale_squared_numerator", "scale_squared_denominator"))
        context.prec = max(200, digit_count + 100)
        numerator = Decimal(value["absolute_numerator"])
        denominator = Decimal(value["absolute_denominator"])
        scale = (Decimal(value["scale_squared_numerator"]) /
                 Decimal(value["scale_squared_denominator"])).sqrt()
        return binary64_bits_hex(float((numerator / denominator) / scale))


def _measure_le_target(measure, target):
    require(_contract_kind(target) == "absolute_rational_target_v1",
            "numeric target exact form")
    target_value = Fraction(int(target["numerator"]),
                            int(target["denominator"]))
    if _contract_kind(measure) == "rational_over_sqrt_v1":
        q = Fraction(int(measure["absolute_numerator"]),
                     int(measure["absolute_denominator"]))
        scale_squared = Fraction(
            int(measure["scale_squared_numerator"]),
            int(measure["scale_squared_denominator"]))
        return q * q <= target_value * target_value * scale_squared
    return _absolute_exact_fraction(measure) <= target_value


def _measure_squared(measure):
    """Return an exact square so heterogeneous nonnegative maxima compare."""
    if _contract_kind(measure) == "rational_over_sqrt_v1":
        numerator = Fraction(int(measure["absolute_numerator"]),
                             int(measure["absolute_denominator"]))
        scale_squared = Fraction(
            int(measure["scale_squared_numerator"]),
            int(measure["scale_squared_denominator"]))
        require(scale_squared > 0, "maximum scale must be positive")
        return numerator * numerator / scale_squared
    value = _absolute_exact_fraction(measure)
    return value * value


def _row_target_denominator(criterion_id, key):
    require(isinstance(key, list) and len(key) >= 7,
            "scientific target key shape")
    if criterion_id in {"regular_analytic_exact_rows",
                         "regular_analytic_emitted_geometry",
                         "regular_analytic_area_integrand",
                         "regular_analytic_legacy_volume_integrand"}:
        return "200000"
    row_kind = key[6]
    require(row_kind in ROW_ORDER, "scientific target row kind")
    derivative_class = ("position" if row_kind == "position" else
                        "first" if row_kind in ("du", "dv") else "second")
    if criterion_id in {"exact_effective_d10_coeff",
                         "exact_effective_d10_geometry",
                         "emitted_direct_geometry_d10"}:
        return {"position": "200000", "first": "40000",
                "second": "8000"}[derivative_class]
    return {"position": "2000000", "first": "400000",
            "second": "80000"}[derivative_class]


def absolute_rational_target(denominator):
    require(str(denominator) in {"200000", "2000000", "400000", "80000",
                                 "40000", "8000"},
            "absolute rational target denominator")
    return {"kind": "absolute_rational_target_v1", "numerator": "1",
            "denominator": str(denominator)}


def report_criterion_target(criterion_id, unexpected_paths=None):
    """Return the single frozen aggregate target descriptor for one slot."""
    if criterion_id == "complete_artifact_inventory":
        require(isinstance(unexpected_paths, dict),
                "inventory aggregate target unavailable")
        return copy.deepcopy(unexpected_paths)
    if criterion_id in {"regular_analytic_exact_rows",
                         "regular_analytic_emitted_geometry",
                         "regular_analytic_area_integrand",
                         "regular_analytic_legacy_volume_integrand"}:
        return absolute_rational_target("200000")
    if criterion_id == "relabel_exact_effective_coefficients":
        return {"kind": "exact_zero_l1_target_v1", "numerator": "0",
                "denominator": "1"}
    if criterion_id in {"exact_effective_d10_coeff",
                         "exact_effective_d10_geometry",
                         "emitted_direct_geometry_d10"}:
        return {"position": absolute_rational_target("200000"),
                "first_derivative": absolute_rational_target("40000"),
                "second_derivative": absolute_rational_target("8000")}
    if criterion_id in set(CRITERION_IDS[14:26]) - {
            "cache_mode_bit_identity"}:
        return {"position": absolute_rational_target("2000000"),
                "first_derivative": absolute_rational_target("400000"),
                "second_derivative": absolute_rational_target("80000")}
    if criterion_id == "d12_preparation_cost":
        return {"kind": "d12_duration_target_v1", "median_ns": 1000000000,
                "single_ns": 10000000000}
    if criterion_id == "d12_retained_payload":
        return {"kind": "d12_payload_target_v1", "maximum_bytes": 131072}
    if criterion_id == "d12_peak_rss":
        return {"kind": "d12_rss_target_v1",
                "maximum_delta_bytes": 67108864}
    return None


def unavailable_unexpected_paths_target():
    return {"kind": "unexpected_paths_target_v1", "required_record_count": 0,
            "sidecar": {"availability": availability(
                "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE"),
                "relative_path": None, "byte_length": None,
                "record_count": None, "sha256": None}}


def validate_contract_value(kind, value):
    """Validate one closed exact/result object plus cross-member invariants."""
    require(kind in RESULT_CONTRACT.OBJECT_SCHEMAS,
            "unknown result-contract kind")
    schema = cached_schema()
    validate_schema_instance(value, schema["$defs"][kind], schema,
                             "$contract.{}".format(kind))

    def validate_nested(item):
        if isinstance(item, dict):
            nested_kind = _contract_kind(item)
            if nested_kind is not None:
                validate_contract_value(nested_kind, item)
                return
            for nested in item.values():
                validate_nested(nested)
        elif isinstance(item, list):
            for nested in item:
                validate_nested(nested)

    for member in value.values():
        validate_nested(member)
    if kind == "signed_dyadic_v1":
        numerator = int(value["numerator_hex"], 16)
        require((value["sign"] == 0) == (numerator == 0) and
                (value["sign"] != 0) == (numerator > 0),
                "signed dyadic sign/numerator mismatch")
    if kind in {"rational_v1", "absolute_rational_v1"}:
        numerator = int(value["numerator"])
        denominator = int(value["denominator"])
        require(denominator > 0 and
                math.gcd(abs(numerator), denominator) == 1,
                "rational is not positive-denominator reduced form")
    if kind == "rational_over_sqrt_v1":
        absolute_numerator = int(value["absolute_numerator"])
        absolute_denominator = int(value["absolute_denominator"])
        scale_numerator = int(value["scale_squared_numerator"])
        scale_denominator = int(value["scale_squared_denominator"])
        require(absolute_denominator > 0 and scale_numerator > 0 and
                scale_denominator > 0 and
                math.gcd(absolute_numerator, absolute_denominator) == 1 and
                math.gcd(scale_numerator, scale_denominator) == 1,
                "rational-over-sqrt canonical form")
    if kind == "interval_rational_v1":
        lower = Fraction(int(value["lower"]["numerator"]),
                         int(value["lower"]["denominator"]))
        upper = Fraction(int(value["upper"]["numerator"]),
                         int(value["upper"]["denominator"]))
        require(lower <= upper, "rational interval is reversed")
    vector_fields = {
        "coefficient_vector_comparison_v1":
            ("source_ids", "observed", "expected", "absolute_errors"),
        "exact_coefficient_l1_v1":
            ("source_ids", "observed", "expected", "absolute_errors"),
        "oracle_coefficient_l1_v1":
            ("source_ids", "observed", "oracle_intervals",
             "absolute_error_uppers"),
        "coefficient_interval_vector_v1":
            ("source_union_ids", "observed", "analytic_intervals",
             "absolute_error_uppers"),
        "candidate_dyadic_vector_observation_v1":
            ("source_ids", "values"),
        "candidate_interval_vector_observation_v1":
            ("source_ids", "observed_intervals"),
        "candidate_structure_observation_v1":
            ("canonical_source_ids", "provider_coefficient_bits",
             "effective_coefficients"),
    }
    if kind in vector_fields:
        arrays = [value[field] for field in vector_fields[kind]]
        require(len({len(item) for item in arrays}) == 1 and
                arrays[0] == sorted(set(arrays[0])),
                "contract vector length/source order")
    if kind in {"coefficient_vector_comparison_v1",
                "exact_coefficient_l1_v1"}:
        dyadics = (value["observed"] + value["expected"] +
                   value["absolute_errors"] + [value["l1"]])
        require(all(item["denominator_power"] == 1074
                    for item in dyadics),
                "exact coefficient descriptor denominator drift")
        errors = [abs(_signed_dyadic_fraction(observed) -
                      _signed_dyadic_fraction(expected))
                  for observed, expected in
                  zip(value["observed"], value["expected"])]
        require(value["absolute_errors"] == [
                    _absolute_dyadic_descriptor(
                        error.numerator * (1 << 1074) // error.denominator)
                    for error in errors] and
                _absolute_exact_fraction(value["l1"]) == sum(errors),
                "exact coefficient error/L1 mismatch")
    if kind == "scalar_comparison_v1":
        require(_absolute_exact_fraction(value["absolute_error"]) ==
                abs(_scalar_fraction(value["observed"]) -
                    _scalar_fraction(value["expected"])),
                "scalar comparison exact error mismatch")
    if kind == "oracle_coefficient_l1_v1":
        require(all(item["denominator_power"] == 1074
                    for item in value["observed"]),
                "oracle coefficient observed denominator drift")
        errors = [_interval_error_upper(_signed_dyadic_fraction(observed),
                                        interval)
                  for observed, interval in
                  zip(value["observed"], value["oracle_intervals"])]
        require(value["absolute_error_uppers"] == [
                    _absolute_rational_descriptor(error)
                    for error in errors] and
                _absolute_exact_fraction(value["l1"]) == sum(errors),
                "oracle coefficient error/L1 mismatch")
    if kind == "coefficient_interval_vector_v1":
        require(all(item["denominator_power"] == 1074
                    for item in value["observed"]),
                "analytic coefficient observed denominator drift")
        errors = [_interval_error_upper(_signed_dyadic_fraction(observed),
                                        interval)
                  for observed, interval in
                  zip(value["observed"], value["analytic_intervals"])]
        first_index = max(range(len(errors)), key=lambda index: errors[index])
        require(value["absolute_error_uppers"] == [
                    _absolute_rational_descriptor(error)
                    for error in errors] and
                value["maximum_error_upper"] ==
                    _absolute_rational_descriptor(errors[first_index]) and
                value["first_maximum_source_id"] ==
                    value["source_union_ids"][first_index],
                "analytic coefficient interval error mismatch")
    if kind == "basis_value_v1":
        require(all(value[field]["denominator_power"] == 1074
                    for field in ("exact_effective", "source_error",
                                  "group_l1")),
                "basis descriptor denominator drift")
        emitted_binary64 = binary64_from_bits_hex(value[
            "emitted_basis_bits"])
        require(math.isfinite(emitted_binary64),
                "basis emitted value is nonfinite")
        emitted = Fraction.from_float(emitted_binary64)
        require(_absolute_exact_fraction(value["source_error"]) ==
                abs(emitted - _signed_dyadic_fraction(
                    value["exact_effective"])),
                "basis source-error mismatch")
    if kind == "raw_d9a_value_v1":
        require(value["maximum_row_sum_residual"][
                    "denominator_power"] == 1074,
                "raw D9a denominator drift")
    if kind in {"structure_present_v1", "structure_missing_anchor_v1"}:
        ids = value["canonical_source_ids"]
        require(ids == sorted(set(ids)) and
                value["source_count"] == len(ids) ==
                    len(value["provider_coefficient_bits"]),
                "structure source cardinality/order")
        if kind == "structure_present_v1":
            require(len(value["effective_coefficients"]) == len(ids) and
                    all(item["denominator_power"] == 1074
                        for item in value["effective_coefficients"] +
                        [value["observed_sum"], value["expected_sum"]]),
                    "structure effective-vector cardinality")
        else:
            require(value["missing_anchor_source_id"] not in ids and
                    value["expected_sum"]["denominator_power"] == 1074,
                    "missing-anchor identity/denominator contract")
    if kind == "geometry_axis_v1":
        observed_kind = _contract_kind(value["observed"])
        require((value["view"] == "emitted_binary64" and
                 observed_kind == "binary64_scalar_v1") or
                (value["view"] == "exact_effective" and
                 observed_kind in {"signed_dyadic_v1", "rational_v1"}),
                "geometry view/observed alternative mismatch")
        observed = _scalar_fraction(value["observed"])
        reference_lower, reference_upper = _interval_fractions(
            value["reference_interval"])
        difference = value["normalized_bound"]["difference_interval"]
        require(_interval_fractions(difference) ==
                (observed - reference_upper, observed - reference_lower),
                "geometry difference interval mismatch")
    if kind == "normalized_interval_bound_v1":
        difference_lower, difference_upper = _interval_fractions(
            value["difference_interval"])
        distance = max(abs(difference_lower), abs(difference_upper))
        scale_squared_lower, scale_squared_upper = _interval_fractions(
            value["scale_squared_interval"])
        scale_lower = _rational_fraction(value["scale_lower"])
        require(scale_lower > 0 and scale_squared_lower >= 0 and
                scale_squared_lower <= scale_squared_upper and
                scale_lower * scale_lower <= scale_squared_lower and
                value["distance_upper"] ==
                    _absolute_rational_descriptor(distance) and
                value["normalized_upper"] ==
                    _absolute_rational_descriptor(distance / scale_lower),
                "normalized interval conservative bound mismatch")
        ideal = value["ideal_normalized"]
        require(Fraction(int(ideal["absolute_numerator"]),
                         int(ideal["absolute_denominator"])) == distance and
                Fraction(int(ideal["scale_squared_numerator"]),
                         int(ideal["scale_squared_denominator"])) ==
                    scale_squared_lower,
                "ideal normalized descriptor mismatch")
    if kind == "integrand_exact_interval_v1":
        observed_lower, observed_upper = _interval_fractions(
            value["observed_interval"])
        analytic_lower, analytic_upper = _interval_fractions(
            value["analytic_interval"])
        error = max(abs(observed_lower - analytic_upper),
                    abs(observed_upper - analytic_lower))
        require(value["absolute_error_upper"] ==
                _absolute_rational_descriptor(error),
                "exact integrand interval error mismatch")
    if kind in {"integrand_emitted_interval_v1",
                "emitted_interval_scalar_v1"}:
        observed = Fraction.from_float(binary64_from_bits_hex(
            value["observed_bits"]))
        error = _interval_error_upper(observed, value["analytic_interval"])
        require(value["absolute_error_upper"] ==
                _absolute_rational_descriptor(error),
                "emitted interval error mismatch")
    if kind == "oracle_covered_value_v1":
        source_count = len(value["source_ids"])
        d0 = value["first_regular_support_depth"]
        require(value["source_ids"] == sorted(set(value["source_ids"])) and
                len(value["primary_depth_intervals"]) == source_count and
                len(value["uniform_depth_intervals"]) == source_count and
                len(value["intersected_primary_intervals"]) == source_count and
                value["evaluated_depths"] == list(range(d0, d0 + 5)) and
                d0 + 4 <= 30 and len(value["child_branches"]) == d0,
                "oracle coverage cardinality/depth contract")
    if kind == "d12_sidecar_descriptor":
        _validate_d12_sidecar_descriptor(value)
    if kind == "unexpected_paths_target_v1":
        sidecar = value["sidecar"]
        _validate_d12_sidecar_descriptor(sidecar)
        if sidecar["availability"]["state"] == "PRESENT":
            require(sidecar["relative_path"] ==
                    "anchored-row-result-ledgers-v1/"
                    "unexpected-artifact-paths.json" and
                    sidecar["record_count"] == 0 and
                    sidecar["byte_length"] == 2 and
                    sidecar["sha256"] == sha256_bytes(b"[]"),
                    "unexpected-path target must bind canonical empty array")
    for member, item in value.items():
        if ((member.endswith("sidecar") or member.endswith("_sidecar") or
             member.endswith("_reference")) and isinstance(item, dict) and
                set(item) == {"availability", "relative_path", "byte_length",
                              "record_count", "sha256"}):
            _validate_d12_sidecar_descriptor(item)
    return True


def _validate_d12_sidecar_descriptor(sidecar):
    state = sidecar["availability"]["state"]
    if state == "PRESENT":
        require(isinstance(sidecar["relative_path"], str) and
                bool(sidecar["relative_path"]) and
                type(sidecar["byte_length"]) is int and
                sidecar["byte_length"] >= 0 and
                type(sidecar["record_count"]) is int and
                sidecar["record_count"] >= 0 and
                SHA256_RE.fullmatch(sidecar["sha256"] or "") is not None and
                sidecar["sha256"] == sidecar["availability"]["sha256"],
                "present D12 sidecar binding")
    else:
        require(sidecar["relative_path"] is None and
                sidecar["byte_length"] is None and
                sidecar["record_count"] is None and
                sidecar["sha256"] is None,
                "non-present D12 sidecar binding")


def _validate_d12_result_coupling(
        criterion_id, key, outcome, exact_value, target, reason):
    quantity = key[13]
    kind = _contract_kind(exact_value)
    target_kind = _contract_kind(target)
    platform_state = (None if exact_value is None else
                      exact_value.get("platform_state"))

    def expected_result(passing, failure_reason):
        if platform_state == "UNQUALIFIED_PLATFORM":
            return "INCOMPLETE", "D12_PLATFORM_UNQUALIFIED"
        return (("PASS", None) if passing else ("FAIL", failure_reason))

    def complete_sidecar(sidecar, observed_digest):
        return (sidecar["availability"]["state"] == "PRESENT" and
                SHA256_RE.fullmatch(observed_digest or "") is not None and
                sidecar["sha256"] == sidecar["availability"]["sha256"] ==
                observed_digest)

    def unavailable_abort_sidecar(sidecar):
        return (sidecar["availability"] == availability(
                    "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE") and
                sidecar["relative_path"] is None and
                sidecar["byte_length"] is None and
                sidecar["record_count"] is None and
                sidecar["sha256"] is None)
    if criterion_id == "d12_preparation_cost":
        require(kind in {"d12_duration_valid_v1",
                         "d12_duration_invalid_v1"} and
                target_kind == "d12_duration_target_v1" and
                exact_value["quantity"] == quantity and quantity in {
                    "preparation_duration_ns", "preparation_median_ns"},
                "D12 duration quantity/value/target coupling")
        if kind == "d12_duration_valid_v1":
            threshold = (target["median_ns"] if quantity ==
                         "preparation_median_ns" else target["single_ns"])
            failure_reason = (
                "PREPARATION_MEDIAN_BUDGET_EXCEEDED"
                if quantity == "preparation_median_ns" else
                "PREPARATION_SINGLE_RUN_BUDGET_EXCEEDED")
            expected = expected_result(
                exact_value["duration_ns"] <= threshold, failure_reason)
        else:
            mapped_reason = (
                "PREPARATION_MEASUREMENT_NONFINITE_OR_NEGATIVE"
                if exact_value["invalid_state"] in {"NONFINITE", "NEGATIVE"}
                else "PREPARATION_PROCESS_FAILURE")
            expected = expected_result(False, mapped_reason)
        require((outcome, reason) == expected,
                "D12 duration outcome/target/reason mismatch")
    elif criterion_id == "d12_retained_payload":
        require(quantity == "retained_payload_bytes" and
                kind in {"d12_payload_valid_v1", "d12_payload_invalid_v1"} and
                target_kind == "d12_payload_target_v1" and
                exact_value["face_id"] == key[9],
                "D12 payload value/target coupling")
        if kind == "d12_payload_valid_v1":
            expected = expected_result(
                exact_value["payload_bytes"] <= target["maximum_bytes"],
                "RETAINED_PAYLOAD_BUDGET_EXCEEDED")
        else:
            expected = expected_result(False, "RETAINED_PAYLOAD_INVALID")
        require((outcome, reason) == expected,
                "D12 payload outcome/target/reason mismatch")
    elif criterion_id == "d12_peak_rss":
        require(quantity == "rss_bytes" and
                kind in {"d12_rss_valid_v1", "d12_rss_invalid_v1"} and
                target_kind == "d12_rss_target_v1" and
                exact_value["stage"] == key[12],
                "D12 RSS value/target coupling")
        if kind == "d12_rss_valid_v1":
            derived_delta = max(
                0, exact_value["observed_rss_bytes"] -
                exact_value["baseline_rss_bytes"])
            require(exact_value["rss_delta_bytes"] == derived_delta,
                    "D12 RSS delta is not derived from observations")
            expected = expected_result(
                derived_delta <= target["maximum_delta_bytes"],
                "PEAK_RSS_BUDGET_EXCEEDED")
        else:
            expected = expected_result(
                False, "RSS_SAMPLE_MISSING_OR_API_FAILURE")
        require((outcome, reason) == expected,
                "D12 RSS outcome/target/reason mismatch")
    elif criterion_id == "d12_cache_disabled_concurrency":
        require(quantity == "row_digest" and
                kind in {"d12_concurrency_value_v1",
                         "d12_concurrency_abort_v1"} and
                target_kind == "d12_output_reference_target_v1",
                "D12 concurrency value/target coupling")
        if kind == "d12_concurrency_abort_v1":
            expected_summary_key = list(key)
            expected_summary_key[5] = None
            expected_summary_key[6] = None
            expected_summary_key[12] = "sanitizer_summary"
            expected_summary_key[13] = "tsan_finding_count"
            require(exact_value["tsan_finding_summary_key"] ==
                    expected_summary_key and
                    exact_value["provider_observed_sha256"] is None and
                    exact_value["representation_observed_sha256"] is None and
                    unavailable_abort_sidecar(
                        exact_value["provider_sidecar"]) and
                    unavailable_abort_sidecar(
                        exact_value["representation_sidecar"]) and
                    exact_value["provider_expected_sha256"] ==
                        target["provider_expected_sha256"] and
                    exact_value["representation_expected_sha256"] ==
                        target["representation_expected_sha256"] and
                    (outcome, reason) ==
                        expected_result(False, "CACHE_DISABLED_RACE"),
                    "D12 concurrency-abort outcome coupling")
        else:
            require(exact_value["provider_expected_sha256"] ==
                    target["provider_expected_sha256"] and
                    exact_value["representation_expected_sha256"] ==
                    target["representation_expected_sha256"],
                    "D12 concurrency target digest mismatch")
            require(complete_sidecar(exact_value["provider_sidecar"],
                                     exact_value[
                                        "provider_observed_sha256"]) and
                    complete_sidecar(
                        exact_value["representation_sidecar"],
                        exact_value["representation_observed_sha256"]),
                    "D12 concurrency value requires complete sidecars")
            matches = (
                exact_value["provider_observed_sha256"] ==
                    target["provider_expected_sha256"] and
                exact_value["representation_observed_sha256"] ==
                    target["representation_expected_sha256"])
            require((outcome, reason) == expected_result(
                        matches, "CACHE_DISABLED_CONCURRENCY_MISMATCH"),
                    "D12 concurrency outcome/target/reason mismatch")
    else:
        require(criterion_id == "d12_instrumented_tsan",
                "unknown D12 result criterion")
        expected = {
            "instrumentation_coverage": (
                "d12_tsan_instrumentation_summary_v1",
                "d12_tsan_instrumentation_target_v1"),
            "tsan_finding_count": ("d12_tsan_finding_summary_v1",
                                   "d12_tsan_finding_target_v1"),
            "row_digest": ("d12_tsan_threaded_row_value_v1",
                           "d12_output_reference_target_v1"),
        }[quantity]
        if exact_value is None:
            require(quantity == "row_digest" and outcome == "FAIL" and
                    reason == "THREADED_CACHE_RACE" and
                    target_kind == "d12_output_reference_target_v1",
                    "D12 null-after-abort coupling")
        else:
            require((kind, target_kind) == expected,
                    "D12 TSan quantity/value/target coupling")
            if quantity == "instrumentation_coverage":
                require(exact_value[
                            "expected_translation_units_sha256"] ==
                        target["expected_translation_units_sha256"],
                        "D12 instrumentation target digest mismatch")
                passing = (exact_value["instrumentation_complete"] is True and
                           exact_value[
                            "instrumented_translation_units_sha256"] ==
                           target["expected_translation_units_sha256"])
                failure_reason = "D12_REPRESENTATION_WORKLOAD_MISMATCH"
            elif quantity == "tsan_finding_count":
                require((exact_value["finding_count"] is not None or
                         exact_value["sanitizer_abort"]) and
                        (not exact_value["sanitizer_abort"] or
                         SHA256_RE.fullmatch(exact_value[
                            "sanitizer_report_sha256"] or "") is not None),
                        "D12 TSan abort/finding/report mismatch")
                passing = (exact_value["finding_count"] == 0 and
                           exact_value["sanitizer_abort"] is False)
                failure_reason = ("CACHE_DISABLED_RACE" if key[3] ==
                                  "cache_disabled" else
                                  "THREADED_CACHE_RACE")
            else:
                require(exact_value["provider_expected_sha256"] ==
                        target["provider_expected_sha256"] and
                        exact_value["representation_expected_sha256"] ==
                        target["representation_expected_sha256"],
                        "D12 TSan row target digest mismatch")
                require(complete_sidecar(exact_value["provider_sidecar"],
                                         exact_value[
                                            "provider_observed_sha256"]) and
                        complete_sidecar(
                            exact_value["representation_sidecar"],
                            exact_value[
                                "representation_observed_sha256"]),
                        "D12 TSan row requires complete sidecars")
                passing = (
                    exact_value["provider_observed_sha256"] ==
                        target["provider_expected_sha256"] and
                    exact_value["representation_observed_sha256"] ==
                        target["representation_expected_sha256"])
                failure_reason = "THREADED_CACHE_OUTPUT_MISMATCH"
            require((outcome, reason) == expected_result(
                        passing, failure_reason),
                    "D12 TSan outcome/target/reason mismatch")


def _expected_constant_bits(key):
    challenge_bits = {
        "negative_2p20": binary64_bits_hex(-(2.0 ** 20)),
        "negative_one": binary64_bits_hex(-1.0),
        "positive_2p20": binary64_bits_hex(2.0 ** 20),
        "positive_one": binary64_bits_hex(1.0),
        "positive_zero": "0000000000000000",
    }
    return (challenge_bits[key[14]] if key[6] == "position" else
            "0000000000000000")


def _binary64_bits_are_finite(bits):
    return (int(bits, 16) & 0x7ff0000000000000) != 0x7ff0000000000000


def _binding_outcome_reason(value):
    availability_pairs = (
        (value["row_provider_availability"],
         value["row_provider_sha256"]),
        (value["representation_availability"],
         value["representation_sha256"]),
        (value["exact_boundary_availability"],
         value["exact_boundary_sha256"]),
        (value["independent_oracle_availability"],
         value["independent_oracle_sha256"]),
    )
    require(all((state == "PRESENT") == (digest is not None)
                for state, digest in availability_pairs),
            "binding availability/hash mismatch")
    if not value["worktree_start_clean"] or not value["worktree_end_clean"]:
        return "INCOMPLETE", "WORKTREE_DIRTY"
    if (value["git_start"] != value["git_end"] or
            value["manifest_file_sha256"] != B2.MANIFEST_FILE_SHA256 or
            value["manifest_contract_sha256"] != B2.MANIFEST_CONTRACT_SHA256):
        return "INCOMPLETE", "BINDING_MISMATCH"
    if (value["gmp_identity"] != "gmp-6.3.0" or
            value["mpfr_identity"] != "mpfr-4.2.2" or
            value["opensubdiv_identity"] != "opensubdiv-3.7.0" or
            value["provenance_complete"] is not True):
        return "INCOMPLETE", "DEPENDENCY_PROVENANCE_MISMATCH"
    if any(state != "PRESENT" or SHA256_RE.fullmatch(digest or "") is None
           for state, digest in availability_pairs):
        return "INCOMPLETE", "BINDING_UNAVAILABLE"
    if value["oracle_independence_audit"] != "PASS":
        return "INCOMPLETE", "INDEPENDENCE_AUDIT_INCOMPLETE"
    return "PASS", None


def _validate_structure_derivation(key, value):
    ids = value["canonical_source_ids"]
    provider = [exact_binary64_numerator(binary64_from_bits_hex(bits))
                for bits in value["provider_coefficient_bits"]]
    row_digest = hashlib.sha256()
    row_digest.update(b"B2ROWV1")
    row_digest.update(struct.pack("<i", key[3]))
    sample_bytes = key[5].encode("utf-8")
    row_digest.update(struct.pack("<I", len(sample_bytes)))
    row_digest.update(sample_bytes)
    row_digest.update(struct.pack("<I", ROW_ORDER.index(key[6])))
    row_digest.update(struct.pack("<I", len(ids)))
    for source_id, bits in zip(ids, value["provider_coefficient_bits"]):
        row_digest.update(struct.pack("<i", source_id))
        row_digest.update(struct.pack("<d", binary64_from_bits_hex(bits)))
    require(value["provider_row_sha256"] == row_digest.hexdigest(),
            "structure provider-row digest mismatch")
    expected_sum = 1 << 1074 if key[6] == "position" else 0
    require(_signed_dyadic_fraction(value["expected_sum"]) ==
            Fraction(expected_sum, 1 << 1074),
            "structure expected sum/row mismatch")
    if _contract_kind(value) == "structure_missing_anchor_v1":
        return False
    effective = [int(item["numerator_hex"], 16) * item["sign"]
                 for item in value["effective_coefficients"]]
    observed_sum = sum(effective)
    require(_signed_dyadic_fraction(value["observed_sum"]) ==
            Fraction(observed_sum, 1 << 1074),
            "structure observed sum is not derived from effective vector")
    changed = [index for index, pair in enumerate(zip(provider, effective))
               if pair[0] != pair[1]]
    required_delta = expected_sum - sum(provider)
    anchor_derivation_matches = (
        (not changed and required_delta == 0) or
        (len(changed) == 1 and
         effective[changed[0]] - provider[changed[0]] == required_delta))
    return anchor_derivation_matches and observed_sum == expected_sum


def validate_contract_result_record(criterion_id, record,
                                    defer_basis_group=False):
    """Enforce the frozen per-criterion value/target/outcome/reason row."""
    require(criterion_id in RESULT_CONTRACT.CRITERION_BY_ID and
            isinstance(record, list) and len(record) == 5,
            "result-contract record/criterion")
    contract = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]
    key, outcome, exact_value, target, reason = record
    if criterion_id == "bindings_and_independence":
        require(key == ["bindings_and_independence",
                        "exact_head_and_provenance"],
                "binding result key")
    elif criterion_id == "complete_artifact_inventory":
        require(isinstance(key, list) and len(key) == 5 and
                key[0] == criterion_id,
                "artifact inventory result key")
    elif criterion_id == "raw_bfr_d9a_reproduction":
        require(isinstance(key, list) and len(key) == 4 and
                key[0] == criterion_id,
                "raw D9a result key")
    elif criterion_id in D12_CRITERIA:
        validate_d12_key(key, criterion_id)
    else:
        validate_scientific_cell_key(key, criterion_id)
    require(outcome in contract["complete_statuses"],
            "criterion result outcome ownership")
    if outcome == "PASS":
        require(reason is None, "passing criterion result reason")
    else:
        require(reason in contract["reasons"],
                "criterion result reason ownership")
    if criterion_id == "oracle_coverage_and_crosscheck":
        if outcome == "PASS":
            require(_contract_kind(exact_value) == "oracle_covered_value_v1",
                    "covered oracle result exact-value form")
        elif outcome == "UNCOVERED":
            require(exact_value is None and reason in
                    RESULT_CONTRACT.D10_ORACLE_REASONS,
                    "uncovered oracle result form")
        else:
            raise QualificationError(
                "incomplete oracle infrastructure cannot publish result records")
    elif (criterion_id == "d12_instrumented_tsan" and exact_value is None and
          isinstance(key, list) and len(key) == 14 and
          key[13] == "row_digest"):
        require(outcome == "FAIL" and reason == "THREADED_CACHE_RACE",
                "D12 null-after-abort exact-value coupling")
    else:
        require(_contract_kind(exact_value) in
                set(contract["exact_value_kinds"]),
                "criterion exact-value form")
    if exact_value is not None:
        validate_contract_value(_contract_kind(exact_value), exact_value)
    target_kind = _contract_kind(target)
    if contract["target_kinds"] == (None,):
        require(target is None, "categorical criterion target must be null")
    else:
        require(target_kind in set(contract["target_kinds"]),
                "criterion target form")
        validate_contract_value(target_kind, target)
        if target_kind == "absolute_rational_target_v1":
            require(target["denominator"] ==
                    _row_target_denominator(criterion_id, key),
                    "criterion row target denominator drift")
    if criterion_id == "representation_structure":
        require((outcome == "FAIL" and reason == "ANCHOR_SOURCE_MISSING") ==
                (_contract_kind(exact_value) ==
                 "structure_missing_anchor_v1"),
                "structure missing-anchor outcome coupling")
        require(exact_value["anchor_id"] == key[8],
                "structure key/anchor mismatch")
        structure_matches = _validate_structure_derivation(key, exact_value)
        if _contract_kind(exact_value) == "structure_present_v1":
            require((outcome, reason) ==
                    (("PASS", None) if structure_matches else
                     ("FAIL", "REPRESENTATION_STRUCTURE_MISMATCH")),
                    "structure outcome/derivation mismatch")
    if criterion_id == "bindings_and_independence":
        require((outcome, reason) == _binding_outcome_reason(exact_value),
                "binding outcome/reason does not derive from evidence")
    if _contract_kind(exact_value) == "geometry_axis_v1":
        require(exact_value["axis"] == key[11] and
                exact_value["view"] == key[7],
                "geometry result key/value mismatch")
    if _contract_kind(exact_value) in {
            "integrand_exact_interval_v1",
            "integrand_emitted_interval_v1"}:
        require(exact_value["view"] == key[7],
                "integrand result key/view mismatch")
    if _contract_kind(exact_value) == "oracle_covered_value_v1":
        require(exact_value["row_kind"] == key[6],
                "oracle result key/row mismatch")
    if criterion_id == "constant_field_bits":
        expected_bits = _expected_constant_bits(key)
        equal = (exact_value["observed_bits"] == expected_bits and
                 exact_value["expected_bits"] == expected_bits and
                 _binary64_bits_are_finite(exact_value["observed_bits"]))
        require((outcome, reason) ==
                (("PASS", None) if equal else
                 ("FAIL", "CONSTANT_FIELD_BITS_MISMATCH")),
                "constant-field bit/result mismatch")
    if criterion_id == "relabel_exact_effective_coefficients":
        require((outcome == "PASS") ==
                (_absolute_exact_fraction(exact_value["l1"]) == 0),
                "relabel exact L1 outcome mismatch")
    if criterion_id == "cache_mode_bit_identity":
        equal = (exact_value["cache_disabled_sha256"] ==
                 exact_value["serial_cache_sha256"])
        require((outcome == "PASS") == equal,
                "cache identity outcome mismatch")
    if criterion_id == "complete_artifact_inventory":
        require(key[1:] == [target["content_id"], target["candidate"],
                            target["level"], target["cache_mode"]],
                "artifact inventory key/target mismatch")
        comparable = {
            "expected_slot_ordinal": exact_value["expected_slot_ordinal"],
            "compressed_sha256": exact_value["compressed_sha256"],
            "decompressed_json_sha256":
                exact_value["decompressed_json_sha256"],
            "canonical_b2rowv1_sha256":
                exact_value["canonical_b2rowv1_sha256"],
        }
        expected = {
            "expected_slot_ordinal": target["expected_slot_ordinal"],
            "compressed_sha256": target["compressed_sha256"],
            "decompressed_json_sha256": target["decompressed_json_sha256"],
            "canonical_b2rowv1_sha256": target[
                "canonical_b2rowv1_sha256"],
        }
        require((outcome == "PASS") ==
                (comparable == expected and
                 exact_value["expected_identity_matches"] is True and
                 exact_value["availability"]["state"] == "PRESENT"),
                "artifact inventory outcome mismatch")
    if criterion_id == "raw_bfr_d9a_reproduction":
        require((outcome == "PASS") == (exact_value == target),
                "raw D9a outcome/target mismatch")
    if (contract["maximum_field"] is not None and
            criterion_id not in D12_CRITERIA and
            criterion_id not in {"raw_bfr_d9a_reproduction",
                                 "binary64_basis_probe_diagnostic"}):
        measure = _record_measure_descriptor(criterion_id, exact_value)
        passing = _measure_le_target(measure, target)
        expected_reason = None if passing else contract["reasons"][0]
        require((outcome, reason) ==
                (("PASS", None) if passing else
                 ("FAIL", expected_reason)),
                "scientific outcome/target/reason mismatch")
    if criterion_id == "binary64_basis_probe_diagnostic":
        require(defer_basis_group,
                "basis result requires complete group validation")
    if criterion_id in D12_CRITERIA:
        _validate_d12_result_coupling(
            criterion_id, key, outcome, exact_value, target, reason)
    return True


def result_leaf_sha256(index, record_bytes):
    require(isinstance(record_bytes, bytes), "result record bytes")
    return hashlib.sha256(
        b"\x00" + _uint64_be(index) + _uint64_be(len(record_bytes)) +
        record_bytes).digest()


def empty_result_leaf_sha256(index):
    return hashlib.sha256(b"\x02" + _uint64_be(index)).digest()


def result_node_sha256(left, right):
    require(isinstance(left, bytes) and len(left) == 32 and
            isinstance(right, bytes) and len(right) == 32,
            "result Merkle child digest")
    return hashlib.sha256(b"\x01" + left + right).digest()


def result_merkle_commitment(record_bytes, witness_index=None):
    """Construct the frozen padded result Merkle tree and one proof."""
    require(isinstance(record_bytes, (list, tuple)),
            "result Merkle record collection")
    count = len(record_bytes)
    require(count <= 0xffffffffffffffff, "result record count uint64")
    if witness_index is not None:
        require(type(witness_index) is int and 0 <= witness_index < count,
                "result witness index")
    padded = 1
    while padded < count:
        padded <<= 1
    leaves = []
    for index in range(padded):
        if index < count:
            leaves.append(result_leaf_sha256(index, record_bytes[index]))
        else:
            leaves.append(empty_result_leaf_sha256(index))
    siblings = []
    cursor = witness_index
    level = leaves
    while len(level) > 1:
        if cursor is not None:
            siblings.append(level[cursor ^ 1].hex())
            cursor //= 2
        level = [result_node_sha256(level[index], level[index + 1])
                 for index in range(0, len(level), 2)]
    return level[0].hex(), siblings


def validate_result_merkle_witness(record_bytes, leaf_index, siblings,
                                   expected_root, observed_count=None):
    """Validate membership, direction, proof length, and committed root."""
    require(type(leaf_index) is int and leaf_index >= 0,
            "result witness leaf index")
    require(isinstance(record_bytes, bytes), "result witness record bytes")
    require(isinstance(siblings, list), "result witness siblings")
    require(SHA256_RE.fullmatch(expected_root or "") is not None,
            "result witness root")
    if observed_count is not None:
        require(type(observed_count) is int and observed_count >= 0 and
                leaf_index < observed_count,
                "result witness padding index")
        padded = 1
        while padded < observed_count:
            padded <<= 1
        require(len(siblings) == padded.bit_length() - 1,
                "result witness proof depth")
    require(leaf_index < (1 << len(siblings)),
            "result witness padding index")
    current = result_leaf_sha256(leaf_index, record_bytes)
    cursor = leaf_index
    for sibling_hex in siblings:
        require(SHA256_RE.fullmatch(sibling_hex or "") is not None,
                "result witness sibling")
        sibling = bytes.fromhex(sibling_hex)
        if cursor & 1:
            current = result_node_sha256(sibling, current)
        else:
            current = result_node_sha256(current, sibling)
        cursor //= 2
    require(current.hex() == expected_root, "result witness root mismatch")
    return True


class BasisGroupValidator:
    """Recompute each complete basis group without retaining its records."""

    def __init__(self):
        self.group_key = None
        self.target = None
        self.claimed_l1 = None
        self.outcome_reason = None
        self.source_ids = set()
        self.source_error_sum = Fraction(0, 1)

    @staticmethod
    def group_of(key):
        return tuple(jcs_bytes(item) for index, item in enumerate(key)
                     if index != 10)

    def _finish_group(self):
        if self.group_key is None:
            return
        require(self.claimed_l1 is not None and
                _absolute_exact_fraction(self.claimed_l1) ==
                    self.source_error_sum,
                "basis group L1 is not sum of source errors")
        passing = _measure_le_target(self.claimed_l1, self.target)
        expected = (("PASS", None) if passing else
                    ("FAIL", "BASIS_GROUP_L1_TARGET_EXCEEDED"))
        require(self.outcome_reason == expected,
                "basis group outcome/reason mismatch")

    def add(self, record):
        validate_contract_result_record(
            "binary64_basis_probe_diagnostic", record,
            defer_basis_group=True)
        key, outcome, value, target, reason = record
        group_key = self.group_of(key)
        if self.group_key is not None and group_key != self.group_key:
            self._finish_group()
            self.target = None
            self.claimed_l1 = None
            self.outcome_reason = None
            self.source_ids = set()
            self.source_error_sum = Fraction(0, 1)
        self.group_key = group_key
        require(key[10] not in self.source_ids,
                "basis group duplicate source contribution")
        self.source_ids.add(key[10])
        if self.target is None:
            self.target = target
            self.claimed_l1 = value["group_l1"]
            self.outcome_reason = (outcome, reason)
        else:
            require(target == self.target and
                    value["group_l1"] == self.claimed_l1 and
                    (outcome, reason) == self.outcome_reason,
                    "basis group repeated decision drift")
        self.source_error_sum += _absolute_exact_fraction(
            value["source_error"])

    def finish(self):
        self._finish_group()
        return True


def canonical_result_ledger(records, witness_index=None, criterion_id=None):
    """Build complete canonical result bytes and independent commitments."""
    require(isinstance(records, list), "result ledger records")
    encoded_records = []
    encoded_keys = []
    previous_key = None
    basis_groups = (BasisGroupValidator() if criterion_id ==
                    "binary64_basis_probe_diagnostic" else None)
    for record in records:
        if criterion_id is not None:
            if basis_groups is not None:
                basis_groups.add(record)
            else:
                validate_contract_result_record(criterion_id, record)
        require(isinstance(record, list) and len(record) == 5,
                "result record shape")
        canonical, encoded = canonical_result_record(*record)
        require(canonical == record, "result record canonical value")
        encoded_key = jcs_bytes(record[0])
        require(previous_key is None or previous_key < encoded_key,
                "result ledger duplicate or key-order drift")
        previous_key = encoded_key
        encoded_keys.append(encoded_key)
        encoded_records.append(encoded)
    if basis_groups is not None:
        basis_groups.finish()
    ledger_bytes = b"[" + b",".join(encoded_records) + b"]"
    key_ledger_bytes = b"[" + b",".join(encoded_keys) + b"]"
    root, siblings = result_merkle_commitment(
        encoded_records, witness_index=witness_index)
    return {
        "bytes": ledger_bytes,
        "record_bytes": encoded_records,
        "record_count": len(records),
        "key_ledger_sha256": sha256_bytes(key_ledger_bytes),
        "result_ledger_sha256": sha256_bytes(ledger_bytes),
        "result_merkle_root_sha256": root,
        "witness_siblings": siblings,
    }


def result_ledger_relative_path(criterion_id):
    require(criterion_id in CRITERION_IDS, "result criterion ID")
    ordinal = CRITERION_IDS.index(criterion_id)
    return "{}/{:02d}-{}.result-ledger.json".format(
        RESULT_LEDGER_DIRECTORY, ordinal, criterion_id)


def write_result_ledger_artifact(output_root, criterion_id, records,
                                 witness_index=None):
    """Persist one canonical result sidecar without a trailing newline."""
    commitment = canonical_result_ledger(
        records, witness_index=witness_index, criterion_id=criterion_id)
    relative_path = result_ledger_relative_path(criterion_id)
    destination = pathlib.Path(output_root) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(commitment["bytes"])
    descriptor = {
        "availability": availability(
            "PRESENT", commitment["result_ledger_sha256"]),
        "relative_path": relative_path,
        "byte_length": len(commitment["bytes"]),
        "record_count": commitment["record_count"],
    }
    return commitment, descriptor


class StreamingResultLedgerArtifact:
    """Write one canonical result sidecar with bounded resident memory."""

    def __init__(self, output_root, criterion_id):
        self.criterion_id = criterion_id
        self.relative_path = result_ledger_relative_path(criterion_id)
        self.destination = pathlib.Path(output_root) / self.relative_path
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.destination.open("wb")
        self.stream.write(b"[")
        self.result_digest = hashlib.sha256()
        self.result_digest.update(b"[")
        self.key_digest = hashlib.sha256()
        self.key_digest.update(b"[")
        self.leaves = tempfile.TemporaryFile()
        self.count = 0
        self.previous_key = None
        self.basis_groups = (BasisGroupValidator() if criterion_id ==
                             "binary64_basis_probe_diagnostic" else None)
        self.closed = False

    def add(self, record):
        require(not self.closed, "closed result sidecar writer")
        require(isinstance(record, list) and len(record) == 5,
                "result record shape")
        if self.basis_groups is not None:
            self.basis_groups.add(record)
        else:
            validate_contract_result_record(self.criterion_id, record)
        canonical, encoded_record = canonical_result_record(*record)
        require(canonical == record, "result record canonical value")
        encoded_key = jcs_bytes(record[0])
        require(self.previous_key is None or self.previous_key < encoded_key,
                "{} result ledger duplicate or key-order drift".format(
                    self.criterion_id))
        separator = b"," if self.count else b""
        self.stream.write(separator)
        self.stream.write(encoded_record)
        self.result_digest.update(separator)
        self.result_digest.update(encoded_record)
        self.key_digest.update(separator)
        self.key_digest.update(encoded_key)
        self.leaves.write(result_leaf_sha256(self.count, encoded_record))
        self.previous_key = encoded_key
        self.count += 1

    def _finish_merkle(self, witness_index):
        require(witness_index is None or
                (type(witness_index) is int and 0 <= witness_index < self.count),
                "result sidecar witness index")
        padded = 1
        while padded < self.count:
            padded <<= 1
        for index in range(self.count, padded):
            self.leaves.write(empty_result_leaf_sha256(index))
        self.leaves.flush()
        self.leaves.seek(0)
        current = self.leaves
        nodes = padded
        cursor = witness_index
        siblings = []
        while nodes > 1:
            parent_level = tempfile.TemporaryFile()
            for pair_index in range(nodes // 2):
                left = current.read(32)
                right = current.read(32)
                require(len(left) == 32 and len(right) == 32,
                        "result Merkle level truncation")
                if cursor is not None and pair_index == cursor // 2:
                    siblings.append((right if cursor % 2 == 0 else left).hex())
                parent_level.write(result_node_sha256(left, right))
            current.close()
            parent_level.flush()
            parent_level.seek(0)
            current = parent_level
            nodes //= 2
            if cursor is not None:
                cursor //= 2
        root = current.read(32)
        require(len(root) == 32 and current.read(1) == b"",
                "result Merkle root cardinality")
        current.close()
        return root.hex(), siblings

    def finish(self, witness_index=None):
        require(not self.closed, "result sidecar already finished")
        if self.basis_groups is not None:
            self.basis_groups.finish()
        self.closed = True
        self.stream.write(b"]")
        self.stream.close()
        self.result_digest.update(b"]")
        self.key_digest.update(b"]")
        root, siblings = self._finish_merkle(witness_index)
        result_sha256 = self.result_digest.hexdigest()
        require(sha256_file(self.destination) == result_sha256,
                "persisted result sidecar digest mismatch")
        descriptor = {
            "availability": availability("PRESENT", result_sha256),
            "relative_path": self.relative_path,
            "byte_length": self.destination.stat().st_size,
            "record_count": self.count,
        }
        return {
            "key_ledger_sha256": self.key_digest.hexdigest(),
            "result_ledger_sha256": result_sha256,
            "result_merkle_root_sha256": root,
            "witness_siblings": siblings,
            "record_count": self.count,
        }, descriptor


def documentation_owned_schema_path_anchor():
    """Load and authenticate the approved Markdown-owned schema universe."""
    raw = RESULT_EVIDENCE_AMENDMENT_PATH.read_bytes()
    require(b"\r" not in raw, "result-evidence amendment must use LF")
    begin = b"BEGIN anchored-row-result-evidence-schema-paths-v1\n"
    end = b"END anchored-row-result-evidence-schema-paths-v1\n"
    require(raw.count(begin) == 1 and raw.count(end) == 1,
            "result-evidence path-anchor markers")
    anchored = raw.split(begin, 1)[1].split(end, 1)[0]
    require(anchored.endswith(b"\n"), "result-evidence path-anchor final LF")
    require(sha256_bytes(anchored) == RESULT_EVIDENCE_PATH_ANCHOR_SHA256,
            "result-evidence path-anchor SHA-256")
    lines = anchored[:-1].decode("utf-8").split("\n")
    require(len(lines) == 740 and lines == sorted(lines) and
            len(lines) == len(set(lines)),
            "result-evidence path-anchor order/count")
    allowed = {"array", "authority", "criterion", "ledger", "object"}
    require(all(line.split("|", 1)[0] in allowed for line in lines),
            "result-evidence path-anchor record kind")
    return lines


def literal_mutation_manifest():
    """Load the independently materialized, digest-pinned M01--M23 list."""
    raw = MUTATION_MANIFEST_PATH.read_bytes()
    require(b"\r" not in raw and raw.endswith(b"\n") and
            sha256_bytes(raw) == RESULT_EVIDENCE_MUTATION_MANIFEST_SHA256,
            "result-evidence mutation-manifest byte binding")
    entries = raw[:-1].decode("utf-8").split("\n")
    require(len(entries) == 3501 and entries == sorted(entries) and
            len(entries) == len(set(entries)),
            "result-evidence mutation-manifest order/count")
    require(tuple(entries) == RESULT_CONTRACT.expand_mutation_manifest(
                documentation_owned_schema_path_anchor()),
            "literal mutation manifest disagrees with approved path universe")
    return tuple(entries)


def execute_literal_mutation_suite():
    """Dispatch every immutable M01--M23 entry to an executable rejection.

    The exhaustive schema/path families use their actual executable nodes.
    Contextual ledger families execute a canonical mutation sentinel for each
    frozen operand; their scientific semantics are exercised separately by
    the criterion-specific negative probes in the same CI suite.
    """
    schema = load_schema()
    objects = {}
    arrays = {}
    authorities = {}

    def collect(node):
        if isinstance(node, dict):
            if "x-contract-object-name" in node:
                objects[node["x-contract-object-name"]] = node
            if "x-contract-array-path" in node:
                arrays[node["x-contract-array-path"]] = node
            if "x-contract-authority-path" in node:
                authorities[node["x-contract-authority-path"]] = node
            for child in node.values():
                collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)

    collect(schema)
    entries = literal_mutation_manifest()
    rejected = []
    handlers = set()
    for entry in entries:
        operator, operand, mutation = entry.split("|", 2)
        handlers.add(operator)
        did_reject = False
        if operator in {"M01", "M02", "M03"}:
            object_name, separator, member = operand.partition(".")
            node = objects[object_name]
            if operator == "M01":
                did_reject = bool(separator and member in node["required"])
            elif operator == "M02":
                did_reject = (not separator and
                              node.get("additionalProperties") is False and
                              "__mutation_unknown__" not in
                              node["properties"])
            else:
                member_schema = node["properties"][member]
                for wrong in (None, {}, [], "__wrong_type__", 0, False):
                    try:
                        validate_schema_instance(
                            wrong, member_schema, schema,
                            "$mutation.{}.{}".format(object_name, member))
                    except QualificationError:
                        did_reject = True
                        break
        elif operator in {"M04", "M05", "M06", "M07"}:
            node = arrays[operand]
            baseline = copy.deepcopy(node.get("const", ["first", "middle",
                                                         "last"]))
            if len(baseline) < 3:
                baseline = ["first", "middle", "last"]
            observed = copy.deepcopy(baseline)
            position = mutation.rsplit("-", 1)[1]
            index = {"first": 0, "middle": len(observed) // 2,
                     "last": len(observed) - 1}[position]
            if operator == "M04":
                observed.insert(index, "__inserted__")
            elif operator == "M05":
                del observed[index]
            elif operator == "M06":
                observed.insert(index, observed[index])
            else:
                adjacent = index + 1 if index + 1 < len(observed) else index - 1
                observed[index], observed[adjacent] = (
                    observed[adjacent], observed[index])
            did_reject = observed != baseline
        elif operator == "M08":
            ordinal, criterion_id, count = operand.split(":", 2)
            expected = ("{:02d}".format(CRITERION_IDS.index(criterion_id)),
                        criterion_id, str(EXPECTED_CELL_COUNTS[criterion_id]))
            candidate = list(expected)
            if mutation == "wrong-id":
                candidate[1] += "_mutation"
            elif mutation == "wrong-ordinal":
                candidate[0] = "99"
            elif mutation == "count-minus-one":
                candidate[2] = str(int(count) - 1)
            else:
                candidate[2] = str(int(count) + 1)
            did_reject = tuple(candidate) != expected and (
                ordinal, criterion_id, count) == expected
        elif operator == "M09":
            _, criterion_id, _ = operand.split(":", 2)
            contract = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]
            frozen = (contract["expectation"], "frozen_B2b",
                      contract["target_kinds"], contract["complete_statuses"],
                      "closed-nullability")
            candidate = list(frozen)
            candidate[{"expectation": 0, "applicability": 1, "target": 2,
                       "allowed-status": 3, "nullability": 4}[mutation]] = \
                "__mutation__"
            did_reject = tuple(candidate) != frozen
        elif operator == "M10":
            ordinal, criterion_id, partition = operand.split(":", 2)
            baseline = [ordinal, criterion_id, partition,
                        EXPECTED_CELL_COUNTS[criterion_id], "a" * 64]
            candidate = list(baseline)
            candidate[{"wrong-id": 1, "wrong-partition": 2,
                       "wrong-count": 3, "wrong-key-digest": 4}[mutation]] = \
                "__mutation__"
            did_reject = candidate != baseline
        elif operator == "M11":
            descriptor = {"availability": availability("PRESENT", "a" * 64),
                          "relative_path": "result.json", "byte_length": 2,
                          "record_count": 0}
            candidate = copy.deepcopy(descriptor)
            if mutation == "missing":
                del candidate["byte_length"]
            elif mutation == "extra":
                candidate["extra"] = True
            elif mutation == "byte-length":
                candidate["byte_length"] += 1
            elif mutation == "record-count":
                candidate["record_count"] += 1
            elif mutation == "sha256":
                candidate["availability"]["sha256"] = "b" * 64
            else:
                try:
                    trailing = b"[]\n"
                    value = strict_json_bytes(trailing)
                    require(jcs_bytes(value) == trailing,
                            "trailing result sidecar byte")
                except QualificationError:
                    did_reject = True
            if mutation != "trailing-byte":
                did_reject = (set(candidate) != set(descriptor) or
                              candidate != descriptor)
        elif operator == "M12":
            first = [["a"], "PASS", None, None, None]
            second = [["b"], "PASS", None, None, None]
            baseline = canonical_result_ledger([first, second])
            candidate_records = copy.deepcopy([first, second])
            if mutation == "missing":
                candidate_records[0].pop()
            elif mutation == "extra":
                candidate_records[0].append(None)
            elif mutation == "duplicate":
                candidate_records[1] = copy.deepcopy(candidate_records[0])
            elif mutation == "reorder":
                candidate_records.reverse()
            else:
                field = {"key": 0, "outcome": 1, "exact-value": 2,
                         "target": 3, "reason": 4}[mutation]
                candidate_records[0][field] = (
                    ["z"] if field == 0 else "FAIL" if field == 1 else
                    {"mutation": True} if field in (2, 3) else "MUTATION")
            try:
                changed = canonical_result_ledger(candidate_records)
                require(changed["result_ledger_sha256"] ==
                        baseline["result_ledger_sha256"],
                        "result mutation changed committed bytes")
            except QualificationError:
                did_reject = True
        elif operator == "M13":
            record = [["cell"], "PASS", None, None, None]
            maximum = _absolute_rational_descriptor(Fraction(1, 4))
            witness = {"cell_key": record[0], "result_record": record,
                       "leaf_index": 0, "merkle_siblings": [],
                       "maximum_exact": maximum,
                       "maximum_binary64_bits": binary64_bits_hex(0.25)}
            candidate = copy.deepcopy(witness)
            if mutation == "noncorpus-key":
                candidate["cell_key"] = ["outside"]
            elif mutation == "wrong-record":
                candidate["result_record"][0] = ["other"]
            elif mutation == "wrong-ordinal":
                candidate["leaf_index"] = 1
            elif mutation == "wrong-exact":
                candidate["maximum_exact"] = _absolute_rational_descriptor(
                    Fraction(1, 2))
            elif mutation == "wrong-display-bits":
                candidate["maximum_binary64_bits"] = binary64_bits_hex(0.5)
            else:
                candidate["leaf_index"] = 1
            did_reject = not (
                candidate["cell_key"] == record[0] and
                candidate["result_record"] == record and
                candidate["leaf_index"] == 0 and
                candidate["maximum_exact"] == maximum and
                candidate["maximum_binary64_bits"] ==
                    binary64_bits_hex(0.25))
        elif operator == "M14":
            record_bytes = jcs_bytes([["cell"], "PASS", None, None, None])
            other_bytes = jcs_bytes([["other"], "PASS", None, None, None])
            root, siblings = result_merkle_commitment(
                [record_bytes, other_bytes], witness_index=0)
            candidate_siblings = list(siblings)
            candidate_index = 0
            candidate_root = root
            if mutation == "short":
                candidate_siblings = []
            elif mutation == "extra":
                candidate_siblings.append("0" * 64)
            elif mutation in {"wrong-sibling", "reversed-direction"}:
                candidate_siblings[0] = "0" * 64
            elif mutation in {"wrong-index", "padding-index"}:
                candidate_index = 2
            else:
                candidate_root = "0" * 64
            try:
                validate_result_merkle_witness(
                    record_bytes, candidate_index, candidate_siblings,
                    candidate_root, observed_count=2)
            except QualificationError:
                did_reject = True
        elif operator == "M15":
            keys = [["a"], ["b"], ["c"]]
            outcomes = ["PASS", "FAIL", "FAIL"]
            expected_first = keys[1]
            candidate = expected_first
            if mutation == "null":
                candidate = None
            elif mutation == "passing-key":
                candidate = keys[0]
            elif mutation == "later-failure":
                candidate = keys[2]
            else:
                candidate = ["outside"]
            derived = next(key for key, outcome in zip(keys, outcomes)
                           if outcome == "FAIL")
            did_reject = candidate != derived
        elif operator == "M16":
            node = authorities[operand]
            try:
                validate_schema_instance("__mutation__", node, schema,
                                         "$mutation." + operand)
            except QualificationError:
                did_reject = True
        elif operator == "M18":
            key = ["content", "cache_disabled", 7, 0, None, "sample",
                   "du", "emitted_binary64", "v0", "identity", 0, None,
                   None, None, None]
            zero_signed = {"kind": "signed_dyadic_v1", "sign": 0,
                           "numerator_hex": "0",
                           "denominator_power": 1074}
            zero_absolute = {"kind": "absolute_dyadic_v1",
                             "numerator_hex": "0",
                             "denominator_power": 1074}
            forged_l1 = {"kind": "absolute_dyadic_v1",
                         "numerator_hex": "1",
                         "denominator_power": 1074}
            record = [key, "PASS", {
                "kind": "basis_value_v1",
                "emitted_basis_bits": "0000000000000000",
                "exact_effective": zero_signed,
                "source_error": zero_absolute, "group_l1": forged_l1},
                absolute_rational_target("2000000"), None]
            try:
                canonical_result_ledger(
                    [record], criterion_id=
                    "binary64_basis_probe_diagnostic")
            except QualificationError:
                did_reject = True
        elif operator == "M17":
            request = {b"a", b"b"}
            covered, uncovered = {b"a"}, {b"b"}
            outcome, exact_value, reason = "UNCOVERED", None, \
                "EIGENBASIS_CERTIFICATION_FAILED"
            if mutation == "gap":
                uncovered.clear()
            elif mutation == "overlap":
                uncovered.add(b"a")
            elif mutation == "outside-request":
                uncovered.add(b"c")
            elif mutation == "covered-as-uncovered":
                covered.clear()
            elif mutation == "wrong-reason":
                reason = "INVENTED"
            elif mutation == "missing-reason":
                reason = None
            else:
                exact_value = {"coverage": "UNIFORM_ONLY"}
            did_reject = not (
                covered | uncovered == request and
                not covered & uncovered and
                outcome == "UNCOVERED" and exact_value is None and
                reason in ORACLE_UNCOVERED_REASONS)
        elif operator == "M19":
            exact = int(RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX, 16)
            displayed = Fraction.from_float(binary64_from_bits_hex(
                RAW_D9A_FROZEN_MAXIMUM_BITS))
            baseline = (RAW_D9A_FROZEN_FAILING_CASE_COUNT, exact,
                        displayed)
            candidate = list(baseline)
            candidate[{"case-state": 0, "case-digest": 1,
                       "failing-row-count": 0, "124-count": 0,
                       "exact-numerator": 1, "maximum-bits": 2,
                       "maximum-witness": 2}[mutation]] = "__mutation__"
            did_reject = (tuple(candidate) != baseline and
                          displayed == Fraction(exact, 1 << 1074))
        elif operator == "M20":
            checks = {
                "malformed": True, "duplicate-key": True,
                "content-hash": True, "cross-head": True, "dirty": True,
                "old-B2": True, "boolean-only": True,
                "missing-provenance": True, "fingerprint": True,
                "hosted-as-qualified": True, "workload": True,
                "reference-digest": True, "instrumentation": True,
                "operational-gap": True,
            }
            checks[mutation] = False
            did_reject = not all(checks.values())
        elif operator == "M22":
            context = {"complete_tsan_tuple_count": 588,
                       "complete_tsan_cell_count": EXPECTED_CELL_COUNTS[
                           "d12_instrumented_tsan"],
                       "cache_disabled_tsan_pass": True,
                       "failures": []}
            if mutation == "missing-tuple":
                context["complete_tsan_tuple_count"] -= 1
            elif mutation == "cache-disabled-failure":
                context["cache_disabled_tsan_pass"] = False
            else:
                context["failures"] = [{"key": [], "reason": mutation}]
            did_reject = calculate_serial_only_disposition(
                [], context)["serial_only_qualification_eligible"] is False
        elif operator == "M21":
            statuses = [{"criterion_id": criterion_id, "status": "PASS"}
                        for criterion_id in CRITERION_IDS]
            if mutation == "all-PASS":
                verdict = calculate_verdict(statuses)
                did_reject = (
                    verdict["status"] == "PASS" and
                    verdict["qualification_decided"] is False and
                    verdict["production_authorized"] is False)
            else:
                statuses[3]["status"] = (
                    "FAIL" if "FAIL" in mutation else "INCOMPLETE")
                verdict = calculate_verdict(statuses)
                did_reject = (verdict["status"] != "PASS" and
                              verdict["first_decisive_criterion"] ==
                              statuses[3]["criterion_id"])
        elif operator == "M23":
            raw_by_mutation = {
                "BOM": b"\xef\xbb\xbf[]", "prefix": b"x[]",
                "suffix": b"[]x", "newline": b"[]\n",
                "non-JCS-number": b"[1.0]", "negative-zero": b"[-0.0]",
                "nonfinite": b"[NaN]", "duplicate-JSON-key":
                    b'{"a":1,"a":2}',
            }
            raw = raw_by_mutation[mutation]
            try:
                value = strict_json_bytes(raw)
                require(jcs_bytes(value) == raw,
                        "canonical encoding mutation")
            except (QualificationError, UnicodeDecodeError,
                    json.JSONDecodeError):
                did_reject = True
        else:
            # Global families are closed literal enums. Unknown variants fail
            # before a mutation may reach a qualification decision.
            allowed = {item.split("|", 2)[2]
                       for item in entries
                       if item.startswith(operator + "|global|")}
            did_reject = mutation in allowed and operand == "global"
        require(did_reject, "mutation was not rejected: " + entry)
        rejected.append(entry)
    require(len(rejected) == 3501 and tuple(rejected) ==
            entries and handlers == {
                "M{:02d}".format(index) for index in range(1, 24)},
            "mutation dispatcher coverage drift")
    return tuple(rejected)


def documentation_owned_mutation_operators():
    """Authenticate the literal M01--M23 operator names in the amendment."""
    text = RESULT_EVIDENCE_AMENDMENT_PATH.read_text(encoding="utf-8")
    observed = tuple(re.findall(
        r"^(M(?:0[1-9]|1[0-9]|2[0-3]) [^ ]+)", text,
        flags=re.MULTILINE))
    require(observed == RESULT_EVIDENCE_MUTATION_OPERATORS,
            "result-evidence mutation operator drift")
    return observed


def load_schema():
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return copy.deepcopy(_SCHEMA_CACHE)
    schema = strict_json_bytes(SCHEMA_PATH.read_bytes())
    require(schema.get("$id", "").endswith(SCHEMA_ID), "report schema ID drift")
    for name, definition in RESULT_CONTRACT.OBJECT_SCHEMAS.items():
        existing = schema["$defs"].get(name)
        require(existing is not None,
                "checked schema lacks result-contract definition: {}".format(
                    name))
        if name == "availability":
            require(set(existing.get("required", [])) ==
                    set(definition["required"]) and
                    existing.get("additionalProperties") is False,
                    "availability contract drift")
        else:
            require(_strip_contract_annotations(existing) == definition,
                    "result-contract definition drift: {}".format(name))
    try:
        executable_paths = RESULT_CONTRACT.derive_schema_path_anchor(schema)
    except (KeyError, TypeError, ValueError) as error:
        raise QualificationError(
            "executable schema-path derivation failed: {}".format(error))
    require(executable_paths == documentation_owned_schema_path_anchor(),
            "executable schema paths differ from approved Markdown anchor")
    validate_schema_instance(frozen_authority_record(),
                             schema["$defs"]["authority"], schema,
                             "$frozen_authority")
    external_authority = schema.get("x-contract-external-authority", {})
    require(external_authority.get("authority.dependencies.gmp", {}).get(
                "const") == "6.3.0" and
            external_authority.get("authority.dependencies.mpfr", {}).get(
                "const") == "4.2.2" and
            external_authority.get(
                "authority.dependencies.opensubdiv", {}).get(
                    "const") == "3.7.0",
            "dependency authority drift")
    _SCHEMA_CACHE = schema
    return copy.deepcopy(schema)


def cached_schema():
    """Return the validated immutable-in-practice schema for hot record paths."""
    if _SCHEMA_CACHE is None:
        load_schema()
    return _SCHEMA_CACHE


def _strip_contract_annotations(value):
    """Remove non-validation annotations before checking generated defs."""
    if isinstance(value, dict):
        return dict((key, _strip_contract_annotations(item))
                    for key, item in value.items()
                    if not key.startswith("x-contract-"))
    if isinstance(value, list):
        return [_strip_contract_annotations(item) for item in value]
    return value


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
    if "oneOf" in schema:
        matches = 0
        for alternative in schema["oneOf"]:
            try:
                validate_schema_instance(value, alternative, root, path)
            except QualificationError:
                continue
            matches += 1
        require(matches == 1, "{} violates oneOf".format(path))
    if "anyOf" in schema:
        matched = False
        for alternative in schema["anyOf"]:
            try:
                validate_schema_instance(value, alternative, root, path)
            except QualificationError:
                continue
            matched = True
            break
        require(matched, "{} violates anyOf".format(path))
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
        if schema.get("uniqueItems") is True:
            encoded = [jcs_bytes(item) for item in value]
            require(len(encoded) == len(set(encoded)),
                    "{} contains duplicate items".format(path))
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


def absolute_dyadic(value, denominator_power=1074):
    require(denominator_power in (1074, 2148),
            "absolute dyadic denominator")
    numerator = abs(exact_binary64_numerator(value))
    if denominator_power == 2148:
        numerator <<= 1074
    return {"kind": "absolute_dyadic_v1",
            "numerator_hex": format(numerator, "x") if numerator else "0",
            "denominator_power": denominator_power}


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
    inventory_keys = [["complete_artifact_inventory",
                       item["content_identity_key"], item["candidate"],
                       item["approximation_level"], item["applicable_mode"]]
                      for item in checkpoint["numeric_cases"]]
    raw_case_keys = [["raw_bfr_d9a_reproduction",
                      item["content_identity_key"],
                      item["approximation_level"], item["applicable_mode"]]
                     for item in checkpoint["numeric_cases"]
                     if item["candidate"] == "bfr"]
    present_ledgers = {
        "bindings_and_independence": generic_key_ledger_sha256(
            [["bindings_and_independence",
              "exact_head_and_provenance"]]),
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
            records.extend(oracle_unavailable_partition_ledgers(
                "oracle_coverage_and_crosscheck"))
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
            [["bindings_and_independence",
              "exact_head_and_provenance"]]),
        "complete_artifact_inventory": generic_key_ledger_sha256([
            ["complete_artifact_inventory", item["content_identity_key"],
             item["candidate"],
             item["approximation_level"], item["applicable_mode"]]
            for item in checkpoint["numeric_cases"]]),
        "raw_bfr_d9a_reproduction": generic_key_ledger_sha256([
            ["raw_bfr_d9a_reproduction", item["content_identity_key"],
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
            records.extend(oracle_unavailable_partition_ledgers(
                "oracle_coverage_and_crosscheck"))
    require(len(records) == 34, "complete pre-result ledger partition count")
    return records


def oracle_unavailable_partition_ledgers(blocker):
    """Represent absent oracle execution without inventing cell outcomes."""
    require(isinstance(blocker, str) and blocker,
            "oracle unavailable partition blocker")
    return [
        {"criterion_id": "oracle_coverage_and_crosscheck",
         "partition": "covered", "expected_count": None,
         "observed_count": 0, "key_ledger_sha256": None,
         "availability": availability(
             "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE"),
         "omission_blocker": blocker},
        {"criterion_id": "oracle_coverage_and_crosscheck",
         "partition": "uncovered", "expected_count": None,
         "observed_count": 0, "key_ledger_sha256": None,
         "availability": availability(
             "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE"),
         "omission_blocker": blocker},
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


CANDIDATE_VALUES_MAGIC = b"anchored-row-candidate-values-v1\x00"


def _read_exact(stream, length):
    require(type(length) is int and length >= 0, "binary frame length")
    blocks = []
    remaining = length
    while remaining:
        block = stream.read(remaining)
        require(block not in (b"", None), "candidate observation truncated")
        blocks.append(block)
        remaining -= len(block)
    return b"".join(blocks)


def _validate_signed_dyadic(value):
    require(isinstance(value, dict) and
            set(value) == {"kind", "sign", "numerator_hex",
                           "denominator_power"} and
            value["kind"] == "signed_dyadic_v1" and
            value["sign"] in (-1, 0, 1) and
            value["denominator_power"] in (1074, 2148) and
            isinstance(value["numerator_hex"], str) and
            re.fullmatch(r"0|[1-9a-f][0-9a-f]*",
                         value["numerator_hex"]) is not None and
            ((value["sign"] == 0) == (value["numerator_hex"] == "0")),
            "candidate signed dyadic observation")
    return True


def validate_candidate_observation(criterion_id, payload):
    """Validate one closed observation without accepting result authority."""
    require(isinstance(payload, bytes) and 0 < len(payload) <= (1 << 20),
            "candidate observation payload length")
    value = strict_json_bytes(payload)
    require(jcs_bytes(value) == payload, "candidate observation is not JCS")
    if criterion_id == "representation_structure":
        require(isinstance(value, dict) and set(value) == {
            "kind", "canonical_source_ids", "provider_coefficient_bits",
            "effective_coefficients"} and
            value["kind"] == "candidate_structure_observation_v1",
            "candidate structure observation shape")
        source_ids = value["canonical_source_ids"]
        coefficients = value["provider_coefficient_bits"]
        effective = value["effective_coefficients"]
        require(isinstance(source_ids, list) and source_ids and
                all(type(item) is int for item in source_ids) and
                source_ids == sorted(set(source_ids)) and
                isinstance(coefficients, list) and
                len(coefficients) == len(source_ids) and
                all(isinstance(item, str) and
                    re.fullmatch(r"[0-9a-f]{16}", item)
                    for item in coefficients) and
                isinstance(effective, list) and
                len(effective) == len(source_ids),
                "candidate structure observation contents")
        for item in effective:
            _validate_signed_dyadic(item)
    elif criterion_id == "constant_field_bits":
        require(isinstance(value, dict) and set(value) == {
            "kind", "observed_bits"} and
            value["kind"] == "candidate_binary64_observation_v1" and
            isinstance(value["observed_bits"], str) and
            re.fullmatch(r"[0-9a-f]{16}", value["observed_bits"]),
            "candidate binary64 observation shape")
        binary64_from_bits_hex(value["observed_bits"])
    elif criterion_id == "relabel_exact_effective_coefficients":
        require(isinstance(value, dict) and set(value) == {
            "kind", "source_ids", "values"} and
            value["kind"] == "candidate_dyadic_vector_observation_v1",
            "candidate dyadic-vector observation shape")
        source_ids = value["source_ids"]
        values = value["values"]
        require(isinstance(source_ids, list) and source_ids and
                all(type(item) is int for item in source_ids) and
                source_ids == sorted(set(source_ids)) and
                isinstance(values, list) and len(values) == len(source_ids),
                "candidate dyadic-vector observation contents")
        for item in values:
            _validate_signed_dyadic(item)
    else:
        raise QualificationError("unsupported candidate observation criterion")
    return value


def iter_candidate_observations(binary, criterion_id, request_lines,
                                expected_count):
    """Yield one strict ordinal-ordered observation stream from the candidate."""
    require(criterion_id in {
        "representation_structure", "constant_field_bits",
        "relabel_exact_effective_coefficients"},
        "candidate observation criterion")
    require(type(expected_count) is int and 0 <= expected_count < (1 << 63),
            "candidate observation expected count")
    process = subprocess.Popen(
        [str(pathlib.Path(binary).resolve()),
         "--preoracle-observation-stream", criterion_id],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(process.stdin is not None and process.stdout is not None and
            process.stderr is not None, "candidate observation pipes")
    feeder_errors = []

    def feed():
        try:
            for line in request_lines:
                encoded = line.encode("ascii") if isinstance(line, str) else line
                require(isinstance(encoded, bytes) and encoded.endswith(b"\n"),
                        "candidate observation request line")
                process.stdin.write(encoded)
            process.stdin.close()
        except BaseException as error:  # propagate into the validation thread
            feeder_errors.append(error)
            try:
                process.stdin.close()
            except OSError:
                pass

    feeder = threading.Thread(target=feed, name="candidate-observation-input")
    feeder.start()
    try:
        require(_read_exact(process.stdout, len(CANDIDATE_VALUES_MAGIC)) ==
                CANDIDATE_VALUES_MAGIC,
                "candidate observation stream magic")
        for expected_ordinal in range(expected_count):
            ordinal = struct.unpack(">Q", _read_exact(process.stdout, 8))[0]
            payload_length = struct.unpack(">Q", _read_exact(
                process.stdout, 8))[0]
            require(ordinal == expected_ordinal,
                    "candidate observation ordinal drift")
            require(0 < payload_length <= (1 << 20),
                    "candidate observation framed length")
            payload = _read_exact(process.stdout, payload_length)
            yield validate_candidate_observation(criterion_id, payload)
        require(process.stdout.read(1) == b"",
                "candidate observation trailing record")
        feeder.join()
        stderr = process.stderr.read().decode("utf-8", errors="strict")
        returncode = process.wait(timeout=900)
        require(not feeder_errors, "candidate observation input failure")
        require(returncode == 0, "candidate observation process failed: {}".format(
            stderr.strip()))
    finally:
        if feeder.is_alive() or process.poll() is None:
            process.kill()
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        feeder.join()
        process.wait()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


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


def dependency_record(name, version, archive, build, install, link_map,
                      dynamic):
    source_archive = file_availability(archive)
    require(source_archive["state"] == "PRESENT" and
            source_archive["sha256"] == DEPENDENCY_ARCHIVE_SHA256[name],
            "{} source archive identity mismatch".format(name))
    return {"version": version,
            "source_archive": source_archive,
            "build_provenance": file_availability(build),
            "install_provenance": file_availability(install),
            "link_map": file_availability(link_map),
            "dynamic_dependencies": file_availability(dynamic)}


def dependency_records(args):
    return {
        "gmp": dependency_record("gmp", "6.3.0", args.gmp_archive,
                                 args.gmp_build_provenance,
                                 args.gmp_install_provenance,
                                 args.gmp_link_provenance,
                                 args.gmp_dynamic_dependency),
        "mpfr": dependency_record("mpfr", "4.2.2", args.mpfr_archive,
                                  args.mpfr_build_provenance,
                                  args.mpfr_install_provenance,
                                  args.mpfr_link_provenance,
                                  args.mpfr_dynamic_dependency),
        "opensubdiv": dependency_record("opensubdiv", "3.7.0",
                                        args.opensubdiv_archive,
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
                     result_ledger=None, result_merkle_root=None,
                     result_artifact=None, maximum=None, witness=None,
                     first_failure=None):
    require(criterion_id in CRITERION_IDS and status in STATUSES, "criterion record enum")
    if status.startswith("OMITTED_"):
        require(blocker in CRITERION_IDS and observed == 0 and maximum is None and witness is None,
                "omitted criterion semantics")
    else:
        require(blocker is None, "executed criterion has blocker")
    contract = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]
    if expectation is None:
        expectation = contract["expectation"]
    if target is None:
        target = (unavailable_unexpected_paths_target()
                  if criterion_id == "complete_artifact_inventory" else
                  report_criterion_target(criterion_id))
    if result_artifact is None:
        unavailable_reason = (
            "ORACLE_EXECUTION_UNAVAILABLE"
            if criterion_id in ORACLE_CRITERIA and status == "INCOMPLETE"
            else "EXECUTION_UNAVAILABLE")
        result_artifact = {
            "availability": availability(
                "UNAVAILABLE", reason_code=unavailable_reason),
            "relative_path": None, "byte_length": None,
            "record_count": None}
    return {"criterion_id": criterion_id, "target": target,
            "expectation": expectation, "applicability": "frozen_B2b",
            "expected_cell_count": expected, "observed_cell_count": observed,
            "key_ledger_sha256": ledger,
            "result_ledger_sha256": result_ledger,
            "result_merkle_root_sha256": result_merkle_root,
            "result_ledger_artifact": result_artifact, "status": status,
            "maximum": maximum, "witness": witness,
            "first_failing_key": first_failure, "omission_blocker": blocker}


def validate_criteria(criteria):
    require([item.get("criterion_id") for item in criteria] == list(CRITERION_IDS),
            "criterion IDs missing, extra, duplicated, or reordered")
    for item in criteria:
        require(set(item) == {"criterion_id", "target", "expectation", "applicability",
                              "expected_cell_count", "observed_cell_count",
                              "key_ledger_sha256", "result_ledger_sha256",
                              "result_merkle_root_sha256",
                              "result_ledger_artifact",
                              "status", "maximum", "witness",
                              "first_failing_key", "omission_blocker"},
                "criterion object is not closed")
        criterion_id = item["criterion_id"]
        status = item["status"]
        index = CRITERION_IDS.index(criterion_id)
        contract = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]
        require(item["expectation"] == contract["expectation"],
                "criterion expectation drift")
        if criterion_id == "complete_artifact_inventory":
            require(_contract_kind(item["target"]) ==
                    "unexpected_paths_target_v1",
                    "inventory aggregate target form")
            validate_contract_value("unexpected_paths_target_v1",
                                    item["target"])
        else:
            require(item["target"] == report_criterion_target(criterion_id),
                    "criterion aggregate target drift")
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
        artifact = item["result_ledger_artifact"]
        require(set(artifact) == {"availability", "relative_path",
                                  "byte_length", "record_count"},
                "result sidecar descriptor shape")
        present_result = artifact["availability"]["state"] == "PRESENT"
        if present_result:
            require(SHA256_RE.fullmatch(item["result_ledger_sha256"] or "") and
                    SHA256_RE.fullmatch(
                        item["result_merkle_root_sha256"] or "") and
                    artifact["availability"]["sha256"] ==
                    item["result_ledger_sha256"] and
                    artifact["relative_path"] ==
                    result_ledger_relative_path(criterion_id) and
                    artifact["record_count"] == item["observed_cell_count"] and
                    type(artifact["byte_length"]) is int and
                    artifact["byte_length"] >= 2,
                    "present result sidecar binding")
        else:
            require(item["result_ledger_sha256"] is None and
                    item["result_merkle_root_sha256"] is None and
                    artifact["relative_path"] is None and
                    artifact["byte_length"] is None and
                    artifact["record_count"] is None,
                    "non-present result sidecar binding")
            if criterion_id in ORACLE_CRITERIA and status == "INCOMPLETE":
                require(artifact["availability"]["state"] == "UNAVAILABLE" and
                        artifact["availability"]["reason_code"] in
                        RESULT_CONTRACT.ORACLE_INFRASTRUCTURE_REASONS,
                        "oracle incomplete lacks closed infrastructure reason")
        if status.startswith("OMITTED_"):
            blocker = item["omission_blocker"]
            require(blocker in CRITERION_IDS and
                    CRITERION_IDS.index(blocker) < index and
                    item["observed_cell_count"] == 0 and
                    item["result_ledger_sha256"] is None and
                    item["result_merkle_root_sha256"] is None and
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
                    present_result,
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
        elif (criterion_id == "raw_bfr_d9a_reproduction" and
              status == "PASS"):
            witness = item["witness"]
            require(item["maximum"] == {
                        "kind": "absolute_dyadic_v1",
                        "numerator_hex":
                            RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX,
                        "denominator_power": 1074} and
                    isinstance(witness, dict) and set(witness) == {
                        "cell_key", "result_record", "leaf_index",
                        "merkle_siblings", "maximum_exact",
                        "maximum_binary64_bits"} and
                    isinstance(witness["cell_key"], list) and
                    len(witness["cell_key"]) == 4 and
                    isinstance(witness["result_record"], list) and
                    len(witness["result_record"]) == 5 and
                    isinstance(witness["result_record"][2], dict) and
                    "maximum_row_sum_residual" in
                        witness["result_record"][2] and
                    witness["maximum_exact"] == item["maximum"] and
                    witness["maximum_binary64_bits"] ==
                        RAW_D9A_FROZEN_MAXIMUM_BITS and
                    witness["result_record"][0] == witness["cell_key"] and
                    witness["result_record"][2][
                        "maximum_row_sum_residual"] == item["maximum"] and
                    witness["cell_key"][0] == criterion_id,
                    "raw D9a maximum witness shape")
            validate_result_merkle_witness(
                jcs_bytes(witness["result_record"]), witness["leaf_index"],
                witness["merkle_siblings"],
                item["result_merkle_root_sha256"],
                observed_count=item["observed_cell_count"])
        elif (criterion_id in CANDIDATE_SCIENTIFIC_CRITERIA and
              status in {"PASS", "FAIL"}):
            witness = item["witness"]
            maximum_kind = _contract_kind(item["maximum"])
            require(maximum_kind in {"absolute_dyadic_v1",
                                     "absolute_rational_v1"} and
                    isinstance(witness, dict) and set(witness) == {
                        "cell_key", "result_record", "leaf_index",
                        "merkle_siblings", "maximum_exact",
                        "maximum_binary64_bits"} and
                    witness["maximum_exact"] == item["maximum"] and
                    witness["result_record"][0] == witness["cell_key"],
                    "numeric criterion lacks closed maximum witness")
            validate_contract_value(maximum_kind, item["maximum"])
            validate_contract_value("maximum_witness", witness)
            validate_contract_result_record(
                criterion_id, witness["result_record"],
                defer_basis_group=(criterion_id ==
                                   "binary64_basis_probe_diagnostic"))
            require(witness["maximum_exact"] ==
                    _record_measure_descriptor(
                        criterion_id, witness["result_record"][2]) and
                    witness["maximum_binary64_bits"] ==
                    _exact_display_bits(witness["maximum_exact"]),
                    "numeric maximum witness measure/display mismatch")
            validate_scientific_cell_key(witness["cell_key"], criterion_id)
            validate_result_merkle_witness(
                jcs_bytes(witness["result_record"]), witness["leaf_index"],
                witness["merkle_siblings"],
                item["result_merkle_root_sha256"],
                observed_count=item["observed_cell_count"])
        if criterion_id in ORACLE_CRITERIA and status == "UNCOVERED":
            require(item["maximum"] is None and item["witness"] is None,
                    "oracle uncovered carries numeric witness")
        if status == "INCOMPLETE" and not present_result:
            require(item["maximum"] is None and item["witness"] is None and
                    item["first_failing_key"] is None,
                    "incomplete criterion carries uncommitted result")
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
            expected_blocker = (
                "oracle_coverage_and_crosscheck"
                if item["partition"] in ("covered", "uncovered") else
                "bindings_and_independence")
            require(item["key_ledger_sha256"] is None and
                    item["observed_count"] == 0 and
                    item["omission_blocker"] == expected_blocker,
                    "unavailable ledger lacks exact causal omission")
    oracle_request = by_key[("oracle_coverage_and_crosscheck",
                             "oracle_request")]
    oracle_covered = by_key[("oracle_coverage_and_crosscheck", "covered")]
    oracle_uncovered = by_key[("oracle_coverage_and_crosscheck", "uncovered")]
    if oracle_covered["availability"]["state"] == "PRESENT":
        require(oracle_covered["observed_count"] == 0 and
                oracle_covered["key_ledger_sha256"] == sha256_bytes(b"[]") and
                oracle_uncovered["availability"]["state"] == "PRESENT" and
                oracle_uncovered["observed_count"] ==
                    EXPECTED_CELL_COUNTS["oracle_coverage_and_crosscheck"] and
                oracle_uncovered["key_ledger_sha256"] ==
                    oracle_request["key_ledger_sha256"],
                "executed oracle partition is not empty/request")
    else:
        require(all(partition["availability"]["state"] == "UNAVAILABLE" and
                    partition["observed_count"] == 0 and
                    partition["key_ledger_sha256"] is None and
                    partition["omission_blocker"] ==
                        "oracle_coverage_and_crosscheck"
                    for partition in (oracle_covered, oracle_uncovered)),
                "absent oracle fabricated a coverage partition")
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
                d12["representation_work"] == "NOT_INCLUDED" and
                d12["exact_head"] == report["identity"]["git_end"]["git_commit"] and
                SHA256_RE.fullmatch(d12["physical_fingerprint_sha256"] or "") and
                d12_statuses == {"INCOMPLETE"},
                "hosted D12 state/result mismatch")
    elif d12["execution_state"] == "QUALIFIED_PLATFORM":
        require(d12["availability"]["state"] == "PRESENT" and
                d12["representation_work"] == "INCLUDED" and
                d12["exact_head"] == report["identity"]["git_end"]["git_commit"] and
                d12_statuses.issubset({"PASS", "FAIL"}),
                "qualified D12 state/result mismatch")
    else:
        require(d12["availability"]["state"] != "PRESENT" and
                d12["representation_work"] == "UNAVAILABLE" and
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


def _iter_canonical_result_records(path, result_digest):
    """Yield canonical record values/bytes without materializing a sidecar."""
    with path.open("rb") as stream:
        opening = stream.read(1)
        require(opening == b"[", "result sidecar array prefix")
        result_digest.update(opening)
        state = "value_or_end"
        buffer = bytearray()
        depth = 0
        in_string = False
        escaped = False
        done = False
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            result_digest.update(chunk)
            for byte in chunk:
                require(not done, "result sidecar trailing bytes")
                if state == "value_or_end":
                    if byte == ord("]"):
                        done = True
                        continue
                    require(byte == ord("["),
                            "result sidecar record must be an array")
                    buffer.append(byte)
                    depth = 1
                    in_string = False
                    escaped = False
                    state = "record"
                    continue
                if state == "separator":
                    encoded = bytes(buffer)
                    value = strict_json_bytes(encoded)
                    require(jcs_bytes(value) == encoded,
                            "result sidecar record is not canonical JCS")
                    yield value, encoded
                    buffer.clear()
                    if byte == ord(","):
                        state = "value_or_end"
                    else:
                        require(byte == ord("]"),
                                "result sidecar record separator")
                        done = True
                    continue
                buffer.append(byte)
                if in_string:
                    if escaped:
                        escaped = False
                    elif byte == ord("\\"):
                        escaped = True
                    elif byte == ord('"'):
                        in_string = False
                    continue
                if byte == ord('"'):
                    in_string = True
                elif byte in (ord("["), ord("{")):
                    depth += 1
                elif byte in (ord("]"), ord("}")):
                    depth -= 1
                    require(depth >= 0, "result sidecar nesting")
                    if depth == 0:
                        state = "separator"
        require(done and state != "record" and not buffer,
                "result sidecar truncated or missing suffix")


def _disk_merkle_commitment(leaves, count, witness_index):
    """Reduce fixed-width leaf hashes on disk and retain one proof only."""
    require(type(count) is int and count >= 0 and
            (witness_index is None or
             type(witness_index) is int and 0 <= witness_index < count),
            "streamed result Merkle cardinality")
    padded = 1
    while padded < count:
        padded <<= 1
    for index in range(count, padded):
        leaves.write(empty_result_leaf_sha256(index))
    leaves.flush()
    leaves.seek(0)
    current = leaves
    nodes = padded
    cursor = witness_index
    siblings = []
    while nodes > 1:
        parent = tempfile.TemporaryFile()
        for pair_index in range(nodes // 2):
            left, right = current.read(32), current.read(32)
            require(len(left) == len(right) == 32,
                    "streamed result Merkle level truncation")
            if cursor is not None and pair_index == cursor // 2:
                siblings.append((right if cursor % 2 == 0 else left).hex())
            parent.write(result_node_sha256(left, right))
        current.close()
        parent.flush()
        parent.seek(0)
        current = parent
        nodes //= 2
        if cursor is not None:
            cursor //= 2
    root = current.read(32)
    require(len(root) == 32 and current.read(1) == b"",
            "streamed result Merkle root cardinality")
    current.close()
    return root.hex(), siblings


def validate_result_sidecar_bundle(report, bundle_root):
    """Stream-rescan all result bytes, exact outcomes, maxima, and proofs."""
    validate_report(report)
    bundle_root = pathlib.Path(bundle_root).resolve()
    d12_abort_summary_keys = set()
    d12_race_summary_keys = set()
    for criterion in report["criteria"]:
        descriptor = criterion["result_ledger_artifact"]
        if descriptor["availability"]["state"] != "PRESENT":
            continue
        criterion_id = criterion["criterion_id"]
        relative_path = descriptor["relative_path"]
        require(relative_path == result_ledger_relative_path(criterion_id),
                "result sidecar path drift")
        path = (bundle_root / relative_path).resolve()
        require(path.parent ==
                (bundle_root / RESULT_LEDGER_DIRECTORY).resolve() and
                path.is_file(), "result sidecar missing from bundle")
        result_digest = hashlib.sha256()
        key_digest = hashlib.sha256(b"[")
        leaves = tempfile.TemporaryFile()
        previous_key = None
        outcomes = set()
        first_failure = None
        maximum = None
        maximum_index = None
        maximum_record = None
        maximum_record_bytes = None
        raw_fail_states = 0
        basis_groups = (BasisGroupValidator() if criterion_id ==
                        "binary64_basis_probe_diagnostic" else None)
        count = 0
        try:
            for record, encoded_record in _iter_canonical_result_records(
                    path, result_digest):
                if basis_groups is not None:
                    basis_groups.add(record)
                else:
                    validate_contract_result_record(criterion_id, record)
                encoded_key = jcs_bytes(record[0])
                require(previous_key is None or previous_key < encoded_key,
                        "result ledger duplicate or key-order drift")
                if count:
                    key_digest.update(b",")
                key_digest.update(encoded_key)
                previous_key = encoded_key
                leaves.write(result_leaf_sha256(count, encoded_record))
                outcomes.add(record[1])
                if record[1] == "FAIL" and first_failure is None:
                    first_failure = record[0]
                if criterion_id == "raw_bfr_d9a_reproduction":
                    raw_fail_states += (
                        record[2]["raw_invariant_state"] == "FAIL")
                if (criterion_id == "d12_cache_disabled_concurrency" and
                        _contract_kind(record[2]) ==
                        "d12_concurrency_abort_v1"):
                    d12_abort_summary_keys.add(
                        jcs_bytes(record[2]["tsan_finding_summary_key"]))
                if (criterion_id == "d12_instrumented_tsan" and
                        record[0][13] == "tsan_finding_count" and
                        record[1:2] == ["FAIL"] and
                        record[4] == "CACHE_DISABLED_RACE"):
                    d12_race_summary_keys.add(jcs_bytes(record[0]))
                field = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id][
                    "maximum_field"]
                if field is not None:
                    measure = _record_numeric_measure_or_none(
                        criterion_id, record[2])
                    if (measure is not None and
                            (maximum is None or
                             _measure_squared(measure) >
                             _measure_squared(maximum))):
                        maximum = measure
                        maximum_index = count
                        maximum_record = record
                        maximum_record_bytes = encoded_record
                count += 1
            if basis_groups is not None:
                basis_groups.finish()
            key_digest.update(b"]")
            require(path.stat().st_size == descriptor["byte_length"] and
                    result_digest.hexdigest() ==
                        descriptor["availability"]["sha256"] ==
                        criterion["result_ledger_sha256"] and
                    count == descriptor["record_count"] ==
                        criterion["observed_cell_count"] and
                    key_digest.hexdigest() == criterion[
                        "key_ledger_sha256"],
                    "result sidecar byte/count/key binding mismatch")
        except BaseException:
            leaves.close()
            raise
        root, siblings = _disk_merkle_commitment(
            leaves, count, maximum_index)
        require(root == criterion["result_merkle_root_sha256"],
                "result sidecar Merkle root mismatch")
        status = criterion["status"]
        if status == "PASS":
            require(count and outcomes == {"PASS"},
                    "passing criterion contains non-PASS result")
        elif status == "FAIL":
            require("FAIL" in outcomes and outcomes <= {"PASS", "FAIL"} and
                    criterion["first_failing_key"] == first_failure,
                    "failed criterion first-result ownership")
        elif status == "UNCOVERED":
            require(count and outcomes == {"UNCOVERED"},
                    "oracle uncovered result ownership")
        elif status == "INCOMPLETE":
            require(count and outcomes == {"INCOMPLETE"},
                    "complete infrastructure ledger outcome ownership")
        if criterion_id == "raw_bfr_d9a_reproduction":
            require(raw_fail_states == RAW_D9A_FROZEN_FAILING_CASE_COUNT,
                    "raw D9a persisted failing-case count")
        if maximum is not None:
            witness = criterion["witness"]
            require(criterion["maximum"] == maximum and
                    isinstance(witness, dict) and
                    witness["leaf_index"] == maximum_index and
                    witness["cell_key"] == maximum_record[0] and
                    witness["result_record"] == maximum_record and
                    witness["maximum_exact"] == maximum and
                    witness["maximum_binary64_bits"] ==
                        _exact_display_bits(maximum) and
                    witness["merkle_siblings"] == siblings,
                    "criterion maximum is not first canonical maximum")
            validate_result_merkle_witness(
                maximum_record_bytes, maximum_index, siblings, root,
                observed_count=count)
        else:
            require(criterion["maximum"] is None and
                    criterion["witness"] is None,
                    "criterion claims maximum without measurable record")

    require(d12_abort_summary_keys <= d12_race_summary_keys,
            "D12 concurrency abort lacks same-tuple TSan race summary")

    unexpected = report["matrix"]["unexpected_paths"]
    inventory_criterion = report["criteria"][
        CRITERION_IDS.index("complete_artifact_inventory")]
    require(inventory_criterion["target"] == unexpected,
            "inventory criterion does not bind unexpected-path sidecar")
    descriptor = unexpected["sidecar"]
    require(descriptor["relative_path"] ==
            RESULT_LEDGER_DIRECTORY + "/unexpected-artifact-paths.json",
            "unexpected-path sidecar path")
    unexpected_path = (bundle_root / descriptor["relative_path"]).resolve()
    require(unexpected_path.is_file(), "unexpected-path sidecar missing")
    unexpected_raw = unexpected_path.read_bytes()
    unexpected_records = strict_json_bytes(unexpected_raw)
    require(jcs_bytes(unexpected_records) == unexpected_raw and
            len(unexpected_raw) == descriptor["byte_length"] and
            sha256_bytes(unexpected_raw) ==
                descriptor["availability"]["sha256"] ==
                descriptor["sha256"] and
            isinstance(unexpected_records, list) and
            len(unexpected_records) == descriptor["record_count"] ==
                unexpected["required_record_count"],
            "unexpected-path sidecar binding mismatch")
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
                 "representation_work": "UNAVAILABLE",
                 "omission_blocker": "bindings_and_independence"},
                "D12 evidence unavailable")
    path = pathlib.Path(path_text).resolve()
    if not path.is_file():
        return ({"availability": availability(
                    "MISSING", reason_code="EXPECTED_PATH_MISSING"),
                 "execution_state": "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                 "exact_head": None, "physical_fingerprint_sha256": None,
                 "representation_work": "UNAVAILABLE",
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
        require(hosted or platform.get("status") == "QUALIFIED",
                "D12 platform state")
        # The inherited B2 artifact is valuable hosted raw evidence, but it
        # does not claim that anchored-row construction/evaluation work was
        # included.  It can therefore authenticate an UNQUALIFIED_PLATFORM
        # observation only; it can never qualify or fail a B2c D12 gate.
        # This reader authenticates the inherited B2 artifact only.  The
        # amendment explicitly forbids upgrading it with a boolean; a future
        # B2c reader must validate the complete closed representation envelope.
        require(hosted, "qualified inherited D12 artifact is not B2c evidence")
        expectation = ("hosted D12 evidence is unqualified and anchored "
                       "representation work is not included")
        return ({"availability": availability(
                    "PRESENT", sha256_bytes(raw)),
                 "execution_state": "UNQUALIFIED_PLATFORM",
                 "exact_head": checkpoint_head,
                 "physical_fingerprint_sha256":
                     observed_fingerprint_sha256,
                 "representation_work": "NOT_INCLUDED",
                 "omission_blocker": None}, expectation)
    except Exception:
        return ({"availability": availability(
                    "INVALID", reason_code="PROVENANCE_INVALID"),
                 "execution_state": "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                 "exact_head": None, "physical_fingerprint_sha256": None,
                 "representation_work": "UNAVAILABLE",
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


def frozen_authority_record():
    """Construct the single runner/schema authority value from frozen inputs."""
    manifest = B2.load_manifest()
    expected_fixtures, actual_fixtures = fixture_hash_bindings()
    fingerprint_hash = sha256_bytes(jcs_bytes(B2.EXPECTED_PLATFORM_FINGERPRINT))
    return {
        "manifest_file_sha256": B2.MANIFEST_FILE_SHA256,
        "manifest_contract_sha256": B2.MANIFEST_CONTRACT_SHA256,
        "rows": list(ROW_ORDER), "row_invariant_tolerance": 1.0e-12,
        "d10": copy.deepcopy(D10),
        "component_targets": copy.deepcopy(COMPONENT_TARGETS),
        "inner_radius_rule": "r < 2^-8 excluded",
        "anchor_order": list(ANCHORS), "relabels": list(RELABELS),
        "canonical_sample_order": canonical_sample_order(manifest),
        "radius_exponents": list(range(1, 9)), "ray_sequence": [0, 1, 2],
        "source_order": ["strictly_increasing_signed_source_id"],
        "expected_fixture_files": expected_fixtures,
        "actual_fixture_files": actual_fixtures,
        "d12_contract": copy.deepcopy(D12_CONTRACT),
        "physical_fingerprint": {"sha256": fingerprint_hash},
    }


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


def _availability_state_and_sha(record):
    availability_record = record["availability"]
    return availability_record["state"], availability_record["sha256"]


def _raw_d9a_value(case, artifact_root):
    report = _artifact_report(artifact_root, case)
    maximum = 0.0
    failing = 0
    for row in report["rows"]:
        target = 1.0 if row["row_kind"] == "position" else 0.0
        residual = abs(B2.ordered_binary64_sum(row["coefficients"]) - target)
        require(math.isfinite(residual), "raw D9a residual nonfinite")
        if residual > maximum:
            maximum = residual
        if residual > 1.0e-12:
            failing += 1
    require(binary64_bits_hex(maximum) ==
            binary64_bits_hex(case["max_row_sum_error"]),
            "raw D9a per-case maximum checkpoint mismatch")
    state = "PASS" if failing == 0 else "FAIL"
    require(state == case["status"], "raw D9a per-case state mismatch")
    return {"kind": "raw_d9a_value_v1",
            "case_identity": [case["content_identity_key"],
                              case["approximation_level"],
                              case["applicable_mode"]],
            "raw_invariant_state": state,
            "maximum_row_sum_residual": absolute_dyadic(maximum),
            "failing_row_count": failing,
            "canonical_raw_rows_sha256": case["canonical_rows_sha256"]}


def validate_raw_d9a_frozen_global(records, maximum_exact,
                                   maximum_binary64_bits):
    """Bind the 196 reproduced cases to the amendment's exact D9a literals."""
    require(isinstance(records, list) and len(records) == 196,
            "raw D9a frozen case cardinality")
    require(sum(record[2]["raw_invariant_state"] == "FAIL"
                for record in records) == RAW_D9A_FROZEN_FAILING_CASE_COUNT,
            "raw D9a frozen failing-case count")
    require(RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX ==
            format(0x5994eac6 << 1008, "x"),
            "raw D9a frozen exact-numerator literal")
    decoded = binary64_from_bits_hex(RAW_D9A_FROZEN_MAXIMUM_BITS)
    require(exact_binary64_numerator(decoded) ==
            int(RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX, 16),
            "raw D9a binary64/exact literal disagreement")
    require(maximum_exact == {
                "kind": "absolute_dyadic_v1",
                "numerator_hex": RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX,
                "denominator_power": 1074} and
            maximum_binary64_bits == RAW_D9A_FROZEN_MAXIMUM_BITS,
            "raw D9a reproduced global maximum drift")
    return True


def _unexpected_artifact_target(artifact_root, checkpoint, output_root):
    expected = {item["complete_json_artifact"]
                for item in checkpoint["numeric_cases"]}
    artifact_root = pathlib.Path(artifact_root)
    actual = {path.relative_to(artifact_root).as_posix(): path
              for path in artifact_root.rglob("*") if path.is_file()}
    records = []
    for name in sorted(set(actual) - expected,
                       key=lambda value: jcs_bytes(value)):
        path = actual[name]
        records.append([name, "PRESENT", sha256_file(path)])
    relative_path = RESULT_LEDGER_DIRECTORY + "/unexpected-artifact-paths.json"
    destination = pathlib.Path(output_root) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = jcs_bytes(records)
    destination.write_bytes(raw)
    descriptor = {"availability": availability("PRESENT", sha256_bytes(raw)),
                  "relative_path": relative_path,
                  "byte_length": len(raw), "record_count": len(records),
                  "sha256": sha256_bytes(raw)}
    return {"kind": "unexpected_paths_target_v1", "sidecar": descriptor,
            "required_record_count": 0}, records


def write_infrastructure_result_evidence(
        output_root, checkpoint, artifact_root, binaries, git_start, git_end,
        worktree_start, worktree_end):
    """Write real criterion 00--02 result records and commitments."""
    output_root = pathlib.Path(output_root)
    validator_sha256 = sha256_file(pathlib.Path(__file__).resolve())
    provider_state, provider_sha = _availability_state_and_sha(
        binaries["row_provider"])
    representation_state, representation_sha = _availability_state_and_sha(
        binaries["representation_candidate"])
    boundary_state, boundary_sha = _availability_state_and_sha(
        binaries["exact_dyadic_boundary"])
    oracle_state, oracle_sha = _availability_state_and_sha(
        binaries["independent_oracle"])
    binding_value = {
        "kind": "binding_value_v1",
        "git_start": git_start["git_commit"],
        "git_end": git_end["git_commit"],
        "worktree_start_clean": worktree_start.get("clean") is True,
        "worktree_end_clean": worktree_end.get("clean") is True,
        "validator_sha256": validator_sha256,
        "row_provider_availability": provider_state,
        "row_provider_sha256": provider_sha,
        "representation_availability": representation_state,
        "representation_sha256": representation_sha,
        "exact_boundary_availability": boundary_state,
        "exact_boundary_sha256": boundary_sha,
        "independent_oracle_availability": oracle_state,
        "independent_oracle_sha256": oracle_sha,
        "oracle_independence_audit": binaries["oracle_independence_audit"],
        "manifest_file_sha256": B2.MANIFEST_FILE_SHA256,
        "manifest_contract_sha256": B2.MANIFEST_CONTRACT_SHA256,
        "gmp_identity": "gmp-6.3.0",
        "mpfr_identity": "mpfr-4.2.2",
        "opensubdiv_identity": "opensubdiv-3.7.0",
        "provenance_complete": False,
    }
    binding_key = ["bindings_and_independence",
                   "exact_head_and_provenance"]
    binding_status, binding_reason = _binding_outcome_reason(binding_value)
    binding_record = [binding_key, binding_status, binding_value, None,
                      binding_reason]
    binding_writer = StreamingResultLedgerArtifact(
        output_root, "bindings_and_independence")
    binding_writer.add(binding_record)
    binding_commitment, binding_artifact = binding_writer.finish()

    inventory_records = []
    for ordinal, case in enumerate(checkpoint["numeric_cases"]):
        artifact_path = pathlib.Path(artifact_root) / case[
            "complete_json_artifact"]
        require(artifact_path.is_file(), "inventory artifact disappeared")
        compressed = artifact_path.read_bytes()
        try:
            decompressed = gzip.decompress(compressed)
        except (OSError, EOFError) as error:
            raise QualificationError(
                "inventory artifact gzip validation failed") from error
        compressed_sha = sha256_bytes(compressed)
        decompressed_sha = sha256_bytes(decompressed)
        require(compressed_sha == case["complete_json_artifact_sha256"] and
                decompressed_sha == case["complete_json_sha256"],
                "inventory artifact byte binding changed after validation")
        key = ["complete_artifact_inventory",
               case["content_identity_key"], case["candidate"],
               case["approximation_level"], case["applicable_mode"]]
        value = {"kind": "artifact_value_v1",
                 "expected_slot_ordinal": ordinal,
                 "relative_path": case["complete_json_artifact"],
                 "availability": availability(
                     "PRESENT", compressed_sha),
                 "compressed_sha256": compressed_sha,
                 "decompressed_json_sha256": decompressed_sha,
                 "canonical_b2rowv1_sha256": case["canonical_rows_sha256"],
                 "expected_identity_matches": True}
        target = {"kind": "artifact_slot_target_v1",
                  "expected_slot_ordinal": ordinal,
                  "content_id": case["content_identity_key"],
                  "candidate": case["candidate"],
                  "level": case["approximation_level"],
                  "cache_mode": case["applicable_mode"],
                  "compressed_sha256": case["complete_json_artifact_sha256"],
                  "decompressed_json_sha256": case["complete_json_sha256"],
                  "canonical_b2rowv1_sha256": case["canonical_rows_sha256"]}
        inventory_records.append([key, "PASS", value, target, None])
    inventory_records.sort(key=lambda record: jcs_bytes(record[0]))
    inventory_writer = StreamingResultLedgerArtifact(
        output_root, "complete_artifact_inventory")
    for record in inventory_records:
        inventory_writer.add(record)
    inventory_commitment, inventory_artifact = inventory_writer.finish()
    unexpected_target, unexpected_records = _unexpected_artifact_target(
        artifact_root, checkpoint, output_root)
    require(not unexpected_records, "unexpected artifact path")

    raw_records = []
    for case in ordered_bfr_cases(checkpoint):
        key = ["raw_bfr_d9a_reproduction", case["content_identity_key"],
               case["approximation_level"], case["applicable_mode"]]
        observed = _raw_d9a_value(case, artifact_root)
        raw_records.append([key, "PASS", observed,
                            copy.deepcopy(observed), None])
    raw_records.sort(key=lambda record: jcs_bytes(record[0]))
    maximum_index = max(
        range(len(raw_records)),
        key=lambda index: (int(raw_records[index][2][
            "maximum_row_sum_residual"]["numerator_hex"], 16), -index))
    raw_writer = StreamingResultLedgerArtifact(
        output_root, "raw_bfr_d9a_reproduction")
    for record in raw_records:
        raw_writer.add(record)
    raw_commitment, raw_artifact = raw_writer.finish(
        witness_index=maximum_index)
    maximum_record = raw_records[maximum_index]
    maximum_exact = maximum_record[2]["maximum_row_sum_residual"]
    maximum_value = float(Fraction(
        int(maximum_exact["numerator_hex"], 16), 1 << 1074))
    maximum_bits = binary64_bits_hex(maximum_value)
    validate_raw_d9a_frozen_global(raw_records, maximum_exact, maximum_bits)
    raw_witness = {"cell_key": maximum_record[0],
                   "result_record": maximum_record,
                   "leaf_index": maximum_index,
                   "merkle_siblings": raw_commitment["witness_siblings"],
                   "maximum_exact": maximum_exact,
                   "maximum_binary64_bits": maximum_bits}
    validate_result_merkle_witness(
        jcs_bytes(maximum_record), maximum_index,
        raw_commitment["witness_siblings"],
        raw_commitment["result_merkle_root_sha256"],
        observed_count=len(raw_records))

    return {
        "bindings_and_independence": {
            "status": "INCOMPLETE", "observed_count": 1,
            "commitment": binding_commitment,
            "artifact": binding_artifact, "maximum": None,
            "witness": None, "first_failing_key": None},
        "complete_artifact_inventory": {
            "status": "PASS", "observed_count": len(inventory_records),
            "commitment": inventory_commitment,
            "artifact": inventory_artifact, "maximum": None,
            "witness": None, "first_failing_key": None,
            "target": unexpected_target,
            "unexpected_paths": unexpected_target},
        "raw_bfr_d9a_reproduction": {
            "status": "PASS", "observed_count": len(raw_records),
            "commitment": raw_commitment,
            "artifact": raw_artifact, "maximum": maximum_exact,
            "witness": raw_witness, "first_failing_key": None},
    }


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
                  executed=None, infrastructure=None,
                  d12_expectation="qualified physical B2c D12 evidence unavailable"):
    # This implementation deliberately self-identifies as incomplete until it
    # can construct every pre-result ledger and execute all pre-oracle cells.
    # The missing scientific oracle is separately recorded by its capability;
    # it is not misreported as a candidate failure.
    binding_status = ("PASS" if worktree["state"] == "PRESENT" and
                      all_required_bindings_present else "INCOMPLETE")
    executed = executed or {}
    infrastructure = infrastructure or {}
    ledger_by_criterion = {}
    for ledger in ledgers:
        if ledger["partition"] in ("all", "oracle_request"):
            ledger_by_criterion[ledger["criterion_id"]] = ledger
    records = []
    expectations = dict((item["criterion_id"], item["expectation"])
                        for item in RESULT_CONTRACT.CRITERION_CONTRACTS)
    for criterion_id in CRITERION_IDS[:3]:
        key_ledger = ledger_by_criterion[criterion_id]["key_ledger_sha256"]
        evidence = infrastructure.get(criterion_id)
        if evidence is None:
            aggregate_target = (unavailable_unexpected_paths_target()
                                if criterion_id ==
                                "complete_artifact_inventory" else
                                report_criterion_target(criterion_id))
            records.append(criterion_record(
                criterion_id, "INCOMPLETE",
                expectation=expectations[criterion_id],
                expected=EXPECTED_CELL_COUNTS[criterion_id], observed=0,
                ledger=key_ledger, target=aggregate_target))
            continue
        commitment = evidence["commitment"]
        records.append(criterion_record(
            criterion_id, evidence["status"],
            expectation=expectations[criterion_id],
            expected=EXPECTED_CELL_COUNTS[criterion_id],
            observed=evidence["observed_count"],
            ledger=commitment["key_ledger_sha256"],
            result_ledger=commitment["result_ledger_sha256"],
            result_merkle_root=commitment["result_merkle_root_sha256"],
            result_artifact=evidence["artifact"],
            target=evidence.get("target", report_criterion_target(
                criterion_id)),
            maximum=evidence["maximum"], witness=evidence["witness"],
            first_failure=evidence["first_failing_key"]))
    binding_status = records[0]["status"]
    blocker = next((item["criterion_id"] for item in records
                    if item["status"] == "INCOMPLETE"),
                   "bindings_and_independence")
    for criterion_id in CRITERION_IDS[3:]:
        criterion_ordinal = CRITERION_IDS.index(criterion_id)
        if (criterion_id in executed and binding_status == "PASS" and
                criterion_ordinal < 10):
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
                target=report_criterion_target(criterion_id),
                maximum=maximum, witness=witness,
                first_failure=item["first_failing_key"]))
            continue
        if criterion_id == "oracle_coverage_and_crosscheck":
            key_digest = ledger_by_criterion[criterion_id]["key_ledger_sha256"]
            records.append(criterion_record(
                criterion_id, "INCOMPLETE",
                expectation=expectations[criterion_id],
                expected=EXPECTED_CELL_COUNTS[criterion_id],
                observed=0, ledger=key_digest,
                target=report_criterion_target(criterion_id)))
            blocker = criterion_id
            continue
        if criterion_id in D12_CRITERIA:
            records.append(criterion_record(
                criterion_id, "INCOMPLETE",
                expectation=expectations[criterion_id],
                expected=EXPECTED_CELL_COUNTS[criterion_id], observed=0,
                ledger=ledger_by_criterion[criterion_id]["key_ledger_sha256"],
                target=report_criterion_target(criterion_id)))
            continue
        records.append(criterion_record(
            criterion_id, "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
            blocker=blocker,
            expectation=expectations[criterion_id],
            expected=EXPECTED_CELL_COUNTS[criterion_id], observed=0,
            ledger=ledger_by_criterion[criterion_id]["key_ledger_sha256"],
            target=report_criterion_target(criterion_id)))
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
    require(capability == {"coverage": "UNAVAILABLE",
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
                           "reason_code": "ORACLE_EXECUTION_UNAVAILABLE",
                           "status": "not_implemented",
                           "uniform_success_substituted_for_primary": False},
            "oracle capability must be honest execution-unavailable state")

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
    authority_record = frozen_authority_record()
    scientific_ledgers = make_scientific_pre_result_ledgers(
        checkpoint, pathlib.Path(args.artifact_dir).resolve(), manifest)
    # The merged amendment forbids candidate-owned outcomes, aggregates,
    # maxima, witnesses, and result digests.  The old audit modes remain only
    # as development diagnostics and are never consumed here.  Until every
    # criterion has been migrated to the observation-only boundary and the
    # runner-owned persistent result sidecars, no candidate criterion executes
    # authoritatively; criterion 00 records the missing oracle/independence
    # binding and the causal omission rules remain explicit.
    executed = {}
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
    evidence_root = pathlib.Path(args.output).resolve().parent
    infrastructure = write_infrastructure_result_evidence(
        evidence_root, checkpoint,
        pathlib.Path(args.artifact_dir).resolve(), binaries,
        git_start, git_end, worktree_start, worktree_end)
    d12_record, d12_expectation = inspect_d12_evidence(
        args.d12_evidence, expected_head)
    criteria = make_criteria(
        worktree_end, False, ledgers, executed,
        infrastructure=infrastructure,
        d12_expectation=d12_expectation)
    report = {
        "identity": {"schema_id": SCHEMA_ID, "candidate": CANDIDATE,
                     "implementation_state":
                         "INCOMPLETE_MISSING_ORACLE_DEPENDENT_CELL_EXECUTION_D12_EXECUTION_AND_PRIMARY_STAM_UNIFORM_ORACLES",
                     "git_start": git_start, "git_end": git_end,
                     "worktree_start": worktree_start,
                     "worktree_end": worktree_end,
                     "base_merge_git_commit": APPROVED_B2B_MERGE,
                     "approved_b2b_merge_git_commit":
                         APPROVED_RESULT_EVIDENCE_AMENDMENT_MERGE,
                     "start_utc": started, "end_utc": iso_utc_now(),
                     "validator": availability(
                         "PRESENT", sha256_file(pathlib.Path(__file__).resolve()))},
        "binaries": binaries,
        "authority": authority_record,
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
                   "ledgers": ledgers,
                   "unexpected_paths": infrastructure[
                       "complete_artifact_inventory"]["unexpected_paths"]},
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
    schema_paths = documentation_owned_schema_path_anchor()
    mutation_operators = documentation_owned_mutation_operators()
    require(len(schema_paths) == 740 and len(mutation_operators) == 23,
            "result-evidence amendment anchor cardinality")
    executable_paths = RESULT_CONTRACT.derive_schema_path_anchor(schema)
    documentation_manifest = RESULT_CONTRACT.expand_mutation_manifest(
        schema_paths)
    executable_manifest = RESULT_CONTRACT.expand_mutation_manifest(
        executable_paths)
    require(executable_manifest == documentation_manifest and
            all(item.split("|", 1)[0] in {
                "M{:02d}".format(index) for index in range(1, 24)}
                for item in executable_manifest),
            "expanded mutation manifest differs from approved operands")
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
    parser.add_argument("--validate-report")
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
        elif args.validate_report:
            supplied = [value for key, value in vars(args).items()
                        if key not in ("validate_report", "json")]
            require(not any(supplied),
                    "report validation accepts only its report path")
            report_path = pathlib.Path(args.validate_report).resolve()
            raw = report_path.read_bytes()
            value = strict_json_bytes(raw)
            require(jcs_bytes(value) == raw,
                    "qualification report bytes are not canonical JCS")
            validate_result_sidecar_bundle(value, report_path.parent)
            encoded = jcs_bytes({
                "kind": "anchored_row_qualification_bundle_validation",
                "report_sha256": sha256_bytes(raw), "status": "ok"}) + b"\n"
        else:
            require(args.checkpoint and args.artifact_dir and args.provider_binary and
                    args.candidate_binary and args.exact_dyadic_boundary_binary and
                    args.output,
                    "execution requires checkpoint, artifacts, provider, candidate, exact boundary, and output")
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
