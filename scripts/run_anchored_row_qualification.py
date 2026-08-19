#!/usr/bin/env python3
"""Fail-closed B2c proof runner for ``anchored_difference_rows_v1``.

The runner executes and validates the frozen B2 corpus, independent primary
oracle, representation boundary, and D12 evidence contract.  It publishes a
proof-only qualification packet; it cannot reopen D9a, select Far, unblock B3,
or authorize production, regardless of the observed qualification verdict.
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
import os
import pathlib
import re
import shutil
import shlex
import signal
import sqlite3
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
    "67e5c2c84c907fe79bab257d992fbcbdf0480d48")
RESULT_EVIDENCE_PATH_ANCHOR_SHA256 = (
    "0e82d15b0244aaa779a1ca600fdc8b43ac501ab91aa615e8adb8dcd8682ecf66")
RESULT_EVIDENCE_MUTATION_MANIFEST_SHA256 = (
    "7916c8175984863086da48ebcf57d0943d983da069dcc000603c315741dca01d")
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
_FACE_ANCHOR_CACHE = None
_D12_FIXTURE_CACHE = None
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
RUNTIME_SOURCE_PATHS = {
    "row_provider": (
        "experiments/bfr_qualification/candidate.cpp",
        "experiments/bfr_qualification/fixture_mesh.hpp",
        "experiments/anchored_row_qualification/anchored_row_evaluator.hpp"),
    "representation_candidate": (
        "experiments/anchored_row_qualification/candidate.cpp",
        "experiments/anchored_row_qualification/anchored_row_evaluator.hpp"),
    "exact_dyadic_boundary": (
        "experiments/anchored_row_qualification/exact_dyadic_boundary.cpp",),
    "independent_oracle": (
        "experiments/bfr_qualification/stam_oracle.cpp",
        "experiments/bfr_qualification/stam_box_spline.hpp",
        "experiments/bfr_qualification/mpfr_interval.hpp",
        "experiments/bfr_qualification/stam_evaluation.hpp",
        "experiments/bfr_qualification/stam_primary.hpp",
        "experiments/bfr_qualification/stam_fixture.hpp",
        "experiments/bfr_qualification/stam_uniform.hpp",
        "experiments/bfr_qualification/stam_uniform_box_spline.hpp",
        ),
}
RUNTIME_SOURCE_ENTRYPOINTS = {
    "row_provider": ("experiments/bfr_qualification/candidate.cpp",),
    "representation_candidate": (
        "experiments/anchored_row_qualification/candidate.cpp",),
    "exact_dyadic_boundary": (
        "experiments/anchored_row_qualification/exact_dyadic_boundary.cpp",),
    "independent_oracle": (
        "experiments/bfr_qualification/stam_oracle.cpp",),
}
MAX_RESULT_RECORD_BYTES = 16 * 1024 * 1024
MAX_RESULT_RECORD_NESTING = 64
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
ORACLE_DEPENDENT_CRITERIA = frozenset((
    "exact_effective_d10_coeff", "exact_effective_d10_geometry",
    "emitted_direct_geometry_d10",
))
_ORACLE_CERTIFICATION_AUTHORITY = object()
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


def _signed_dyadic_descriptor(numerator, denominator_power=1074):
    require(type(numerator) is int,
            "signed dyadic numerator")
    return {"kind": "signed_dyadic_v1",
            "sign": 0 if numerator == 0 else (1 if numerator > 0 else -1),
            "numerator_hex": (format(abs(numerator), "x")
                              if numerator else "0"),
            "denominator_power": denominator_power}


def _interval_fractions(value):
    return (_rational_fraction(value["lower"]),
            _rational_fraction(value["upper"]))


def _interval_error_upper(observed, interval):
    lower, upper = _interval_fractions(interval)
    return max(abs(observed - lower), abs(observed - upper))


def _interval_error_upper_between(observed, reference):
    observed_lower, observed_upper = _interval_fractions(observed)
    reference_lower, reference_upper = _interval_fractions(reference)
    return max(abs(observed_lower - reference_upper),
               abs(observed_upper - reference_lower))


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
            if nested_kind in RESULT_CONTRACT.OBJECT_SCHEMAS:
                validate_contract_value(nested_kind, item)
                return
            if nested_kind == "bfr_platform_probe":
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
        partition_target = Fraction(
            1 if value["row_kind"] == "position" else 0)
        require(value["source_ids"] == sorted(set(value["source_ids"])) and
                len(value["primary_depth_intervals"]) == source_count and
                len(value["uniform_depth_intervals"]) == source_count and
                len(value["intersected_primary_intervals"]) == source_count and
                value["evaluated_depths"] == list(range(d0, d0 + 5)) and
                d0 + 4 <= 30 and len(value["child_branches"]) == d0,
                "oracle coverage cardinality/depth contract")
        primary_sums = [[Fraction(0), Fraction(0)] for _ in range(5)]
        uniform_sums = [[Fraction(0), Fraction(0)] for _ in range(5)]
        intersection_sum = [Fraction(0), Fraction(0)]
        for source_index in range(source_count):
            primary = value["primary_depth_intervals"][source_index]
            uniform = value["uniform_depth_intervals"][source_index]
            intersection_lower = None
            intersection_upper = None
            for depth in range(5):
                primary_lower, primary_upper = _interval_fractions(
                    primary[depth])
                uniform_lower, uniform_upper = _interval_fractions(
                    uniform[depth])
                primary_sums[depth][0] += primary_lower
                primary_sums[depth][1] += primary_upper
                uniform_sums[depth][0] += uniform_lower
                uniform_sums[depth][1] += uniform_upper
                require(primary_lower <= uniform_upper and
                        uniform_lower <= primary_upper,
                        "primary/uniform oracle interval separation")
                intersection_lower = (primary_lower if
                    intersection_lower is None else
                    max(intersection_lower, primary_lower))
                intersection_upper = (primary_upper if
                    intersection_upper is None else
                    min(intersection_upper, primary_upper))
            observed_intersection = _interval_fractions(value[
                "intersected_primary_intervals"][source_index])
            intersection_sum[0] += observed_intersection[0]
            intersection_sum[1] += observed_intersection[1]
            require(intersection_lower <= intersection_upper and
                    observed_intersection ==
                        (intersection_lower, intersection_upper),
                    "oracle primary five-depth intersection mismatch")
        require(all(lower <= partition_target <= upper
                    for lower, upper in primary_sums + uniform_sums) and
                intersection_sum[0] <= partition_target <=
                    intersection_sum[1],
                "oracle covered rows do not certify partition/derivative sum")
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

    def incomplete_result():
        if platform_state == "UNQUALIFIED_PLATFORM":
            return "INCOMPLETE", "D12_PLATFORM_UNQUALIFIED"
        return "INCOMPLETE", "D12_OPERATIONAL_LEDGER_INCOMPLETE"

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
            require(quantity == "row_digest" and
                    (outcome, reason) in {
                        ("FAIL", "THREADED_CACHE_RACE"),
                        ("INCOMPLETE", "D12_PLATFORM_UNQUALIFIED")} and
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
                if exact_value["instrumentation_complete"] is not True:
                    require(exact_value[
                                "instrumented_translation_units_sha256"]
                            is None and
                            (outcome, reason) == incomplete_result(),
                            "missing D12 instrumentation is incomplete evidence")
                    return
                passing = (exact_value[
                    "instrumented_translation_units_sha256"] ==
                    target["expected_translation_units_sha256"])
                failure_reason = "D12_REPRESENTATION_WORKLOAD_MISMATCH"
            elif quantity == "tsan_finding_count":
                if (exact_value["finding_count"] is None and
                        exact_value["sanitizer_abort"] is False):
                    require(exact_value["sanitizer_report_sha256"] is None and
                            (outcome, reason) == incomplete_result(),
                            "unavailable D12 TSan execution is incomplete evidence")
                    return
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


def _validate_binding_against_report(value, report):
    identity = report["identity"]
    binaries = report["binaries"]
    authority = report.get("authority", {
        "manifest_file_sha256": B2.MANIFEST_FILE_SHA256,
        "manifest_contract_sha256": B2.MANIFEST_CONTRACT_SHA256})

    def dependency_version(binary_name, dependency_name, fallback):
        return binaries[binary_name].get("dependencies", {}).get(
            dependency_name, {}).get("version", fallback)

    expected = {
        "git_start": identity["git_start"]["git_commit"],
        "git_end": identity["git_end"]["git_commit"],
        "worktree_start_clean": identity["worktree_start"]["clean"],
        "worktree_end_clean": identity["worktree_end"]["clean"],
        "validator_sha256": identity["validator"]["sha256"],
        "oracle_independence_audit": binaries[
            "oracle_independence_audit"],
        "manifest_file_sha256": authority[
            "manifest_file_sha256"],
        "manifest_contract_sha256": authority[
            "manifest_contract_sha256"],
        "gmp_identity": "gmp-" + dependency_version(
            "row_provider", "gmp", "6.3.0"),
        "mpfr_identity": "mpfr-" + dependency_version(
            "row_provider", "mpfr", "4.2.2"),
        "opensubdiv_identity": "opensubdiv-" + binaries[
            "row_provider"].get("dependencies", {}).get(
                "opensubdiv", {}).get("version", "3.7.0"),
    }
    for prefix, binary_name in (
            ("row_provider", "row_provider"),
            ("representation", "representation_candidate"),
            ("exact_boundary", "exact_dyadic_boundary"),
            ("independent_oracle", "independent_oracle")):
        availability_record = binaries[binary_name]["availability"]
        expected[prefix + "_availability"] = availability_record["state"]
        expected[prefix + "_sha256"] = availability_record["sha256"]
    provenance_binaries = [
        binary for binary in (
            binaries["row_provider"],
            binaries["representation_candidate"],
            binaries["exact_dyadic_boundary"],
            binaries["independent_oracle"])
        if binary["availability"]["state"] == "PRESENT"]
    expected["provenance_complete"] = all(
        binary.get("sources") and
        all(binary.get(field, {}).get("state") == "PRESENT" for field in
            ("compiler_command", "compiler_version", "link_map",
             "dynamic_dependencies")) and
        all(dependency.get(field, {}).get("state") == "PRESENT"
            for dependency in binary.get("dependencies", {}).values()
            for field in ("source_archive", "build_provenance",
                          "install_provenance", "link_map",
                          "dynamic_dependencies"))
        for binary in provenance_binaries)
    require(all(value[key] == expected_value
                for key, expected_value in expected.items()),
            "binding result does not match report/runtime bindings")
    return True


def _validate_runtime_bindings(report, runtime_binaries,
                               runtime_provenance=None):
    actual_git, actual_worktree = git_observations()
    actual_head = actual_git.get("git_commit")
    require(actual_git == {"state": "PRESENT", "git_commit": actual_head,
                           "reason_code": None} and
            GIT_RE.fullmatch(actual_head or "") is not None and
            actual_worktree == {"state": "PRESENT", "clean": True,
                                "reason_code": None} and
            report["identity"]["git_start"]["git_commit"] == actual_head ==
                report["identity"]["git_end"]["git_commit"] ==
                report["checkpoint"]["git_head"] and
            report["identity"]["worktree_start"]["clean"] is True and
            report["identity"]["worktree_end"]["clean"] is True,
            "report/checkpoint identity differs from actual clean Git HEAD")
    require(report["identity"]["validator"]["sha256"] ==
            sha256_file(pathlib.Path(__file__).resolve()),
            "report validator digest does not match executing validator")
    for binary_name, path_text in runtime_binaries.items():
        binding = report["binaries"][binary_name]["availability"]
        require(RUNTIME_SOURCE_PATHS[binary_name] ==
                _repository_source_closure(
                    RUNTIME_SOURCE_ENTRYPOINTS[binary_name]),
                "frozen runtime source set omits a local include: " +
                binary_name)
        expected_sources = ([] if binding["state"] != "PRESENT" else [{
            "path": relative_path,
            "sha256": sha256_file(ROOT / relative_path)}
            for relative_path in RUNTIME_SOURCE_PATHS[binary_name]])
        require(report["binaries"][binary_name]["sources"] ==
                expected_sources,
                "runtime binary source inventory is not the frozen complete set: " +
                binary_name)
        if binding["state"] == "PRESENT":
            require(path_text is not None and
                    pathlib.Path(path_text).resolve().is_file() and
                    sha256_file(pathlib.Path(path_text).resolve()) ==
                        binding["sha256"],
                    "runtime binary differs from report binding: " +
                    binary_name)
        else:
            require(path_text is None,
                    "non-present report binary supplied at validation: " +
                    binary_name)
        for source in report["binaries"][binary_name]["sources"]:
            source_path = (ROOT / source["path"]).resolve()
            require(source_path.is_relative_to(ROOT) and
                    source_path.is_file() and
                    sha256_file(source_path) == source["sha256"],
                    "binary source inventory differs from repository")
    if runtime_provenance is not None:
        for binary_name, files in runtime_provenance["binaries"].items():
            binary = report["binaries"][binary_name]
            if binary["availability"]["state"] != "PRESENT":
                require(all(path is None for path in files.values()),
                        "unavailable binary supplied provenance files")
                continue
            for field, path_text in files.items():
                require(path_text is not None and
                        binary[field]["state"] == "PRESENT" and
                        sha256_file(pathlib.Path(path_text).resolve()) ==
                            binary[field]["sha256"],
                        "runtime binary provenance differs from report: " +
                        binary_name + "." + field)
        for dependency_name, files in runtime_provenance[
                "dependencies"].items():
            for binary_name, binary in report["binaries"].items():
                if (binary_name == "oracle_independence_audit" or
                        binary["availability"]["state"] != "PRESENT"):
                    continue
                dependency = binary["dependencies"][dependency_name]
                for field, path_text in files.items():
                    require(path_text is not None and
                            dependency[field]["state"] == "PRESENT" and
                            sha256_file(pathlib.Path(path_text).resolve()) ==
                                dependency[field]["sha256"],
                            "runtime dependency provenance differs from "
                            "report: " + dependency_name + "." + field)
        oracle_binding = report["binaries"]["independent_oracle"][
            "availability"]
        if oracle_binding["state"] == "PRESENT":
            oracle_files = runtime_provenance["binaries"][
                "independent_oracle"]
            require(report["binaries"]["oracle_independence_audit"] ==
                        audit_oracle_independence(
                            runtime_binaries["independent_oracle"],
                            oracle_files["compiler_command"],
                            oracle_files["link_map"],
                            oracle_files["dynamic_dependencies"]),
                    "oracle independence audit differs from runtime evidence")
    return True


def _repository_source_closure(entrypoints):
    """Derive the ordered repository-local quoted-include closure."""
    result = []
    visited = set()
    visiting = set()

    def visit(relative_path):
        if relative_path in visited:
            return
        require(relative_path not in visiting,
                "runtime source include cycle: " + relative_path)
        visiting.add(relative_path)
        result.append(relative_path)
        path = (ROOT / relative_path).resolve()
        require(path.is_relative_to(ROOT) and path.is_file(),
                "runtime source entry missing: " + relative_path)
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r'^\s*#\s*include\s+"([^"]+)"\s*$', line)
            if match is None:
                continue
            included = (path.parent / match.group(1)).resolve()
            if included.is_relative_to(ROOT) and included.is_file():
                visit(str(included.relative_to(ROOT)))
        visiting.remove(relative_path)
        visited.add(relative_path)

    for entrypoint in entrypoints:
        visit(entrypoint)
    return tuple(result)


def _validate_structure_derivation(key, value):
    ids = value["canonical_source_ids"]
    provider = [exact_binary64_numerator(binary64_from_bits_hex(bits))
                for bits in value["provider_coefficient_bits"]]
    effective_values = value.get("effective_coefficients")
    require(value["source_count"] == len(ids) == len(provider) and
            (effective_values is None or len(effective_values) == len(ids)) and
            ids == sorted(ids) and len(ids) == len(set(ids)),
            "structure source-vector cardinality/order mismatch")
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
    global _FACE_ANCHOR_CACHE
    if _FACE_ANCHOR_CACHE is None:
        _FACE_ANCHOR_CACHE = {}
        for job in B2.valid_content_jobs(B2.load_manifest()):
            _, faces, _ = B2.independent_mesh(job)
            _FACE_ANCHOR_CACHE[job["content_identity_key"]] = faces
    faces = _FACE_ANCHOR_CACHE.get(key[0])
    require(faces is not None and 0 <= key[3] < len(faces),
            "structure key has no frozen oriented face")
    face = faces[key[3]]
    anchor_source_id = face[ANCHORS.index(key[8])]
    require(_signed_dyadic_fraction(value["expected_sum"]) ==
            Fraction(expected_sum, 1 << 1074),
            "structure expected sum/row mismatch")
    if _contract_kind(value) == "structure_missing_anchor_v1":
        require(value["missing_anchor_source_id"] == anchor_source_id,
                "structure missing source is not oriented-face anchor")
        return False
    effective = [int(item["numerator_hex"], 16) * item["sign"]
                 for item in effective_values]
    observed_sum = sum(effective)
    require(_signed_dyadic_fraction(value["observed_sum"]) ==
            Fraction(observed_sum, 1 << 1074),
            "structure observed sum is not derived from effective vector")
    changed = [index for index, pair in enumerate(zip(provider, effective))
               if pair[0] != pair[1]]
    required_delta = expected_sum - sum(provider)
    anchor_derivation_matches = (
        (not changed and required_delta == 0) or
        (len(changed) == 1 and ids[changed[0]] == anchor_source_id and
         effective[changed[0]] - provider[changed[0]] == required_delta))
    return anchor_derivation_matches and observed_sum == expected_sum


def validate_result_record_envelope(criterion_id, record):
    """Validate the criterion-owned key/status/reason five-field envelope."""
    require(criterion_id in RESULT_CONTRACT.CRITERION_BY_ID and
            isinstance(record, list) and len(record) == 5,
            "result-contract record/criterion")
    contract = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]
    key, outcome, _, _, reason = record
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
    return True


def validate_contract_result_record(
        criterion_id, record, defer_basis_group=False,
        oracle_certification_authority=None):
    """Enforce the frozen per-criterion value/target/outcome/reason row."""
    validate_result_record_envelope(criterion_id, record)
    contract = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]
    key, outcome, exact_value, target, reason = record
    if criterion_id == "oracle_coverage_and_crosscheck":
        if outcome == "PASS":
            require(oracle_certification_authority is
                    _ORACLE_CERTIFICATION_AUTHORITY,
                    "covered oracle result lacks authenticated certificate "
                    "execution context")
            require(_contract_kind(exact_value) == "oracle_covered_value_v1",
                    "covered oracle result exact-value form")
            require(isinstance(key, list) and len(key) == 15 and
                    exact_value["row_kind"] == key[6],
                    "covered oracle row/key quantity drift")
        elif outcome == "UNCOVERED":
            require(exact_value is None and reason in
                    RESULT_CONTRACT.D10_ORACLE_REASONS,
                    "uncovered oracle result form")
        else:
            raise QualificationError(
                "incomplete oracle infrastructure cannot publish result records")
    elif (criterion_id in ORACLE_DEPENDENT_CRITERIA and
          outcome == "UNCOVERED"):
        require(exact_value is None and reason in
                RESULT_CONTRACT.D10_ORACLE_REASONS,
                "oracle-dependent uncovered result form")
    elif (criterion_id == "d12_instrumented_tsan" and exact_value is None and
          isinstance(key, list) and len(key) == 14 and
          key[13] == "row_digest"):
        require((outcome, reason) in {
                    ("FAIL", "THREADED_CACHE_RACE"),
                    ("INCOMPLETE", "D12_PLATFORM_UNQUALIFIED")},
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
        finite = _binary64_bits_are_finite(exact_value["observed_bits"])
        equal = (finite and exact_value["observed_bits"] == expected_bits and
                 exact_value["expected_bits"] == expected_bits)
        expected = (("PASS", None) if equal else
                    ("FAIL", "CANDIDATE_NONFINITE") if not finite else
                    ("FAIL", "CONSTANT_FIELD_BITS_MISMATCH"))
        require((outcome, reason) == expected,
                "constant-field bit/result mismatch")
    if criterion_id == "relabel_exact_effective_coefficients":
        passing = _absolute_exact_fraction(exact_value["l1"]) == 0
        require((outcome, reason) ==
                (("PASS", None) if passing else
                 ("FAIL", "RELABEL_EXACT_MISMATCH")),
                "relabel exact L1 outcome/reason mismatch")
    if criterion_id == "cache_mode_bit_identity":
        equal = (exact_value["cache_disabled_sha256"] ==
                 exact_value["serial_cache_sha256"])
        require((outcome, reason) ==
                (("PASS", None) if equal else
                 ("FAIL", "CACHE_MODE_BITS_MISMATCH")),
                "cache identity outcome/reason mismatch")
    if criterion_id == "complete_artifact_inventory":
        require(key[1:] == [target["content_id"], target["candidate"],
                            target["level"], target["cache_mode"]],
                "artifact inventory key/target mismatch")
        if exact_value["availability"]["state"] != "PRESENT":
            expected_result = "INCOMPLETE", "ARTIFACT_MISSING"
        elif (exact_value["compressed_sha256"] !=
              target["compressed_sha256"]):
            expected_result = "INCOMPLETE", "ARTIFACT_HASH_MISMATCH"
        elif (exact_value["decompressed_json_sha256"] !=
              target["decompressed_json_sha256"] or
              exact_value["canonical_b2rowv1_sha256"] !=
              target["canonical_b2rowv1_sha256"]):
            expected_result = "INCOMPLETE", "ARTIFACT_CONTENT_MISMATCH"
        elif (exact_value["expected_slot_ordinal"] !=
              target["expected_slot_ordinal"] or
              exact_value["expected_identity_matches"] is not True):
            expected_result = "INCOMPLETE", "ARTIFACT_IDENTITY_MISMATCH"
        else:
            expected_result = "PASS", None
        require((outcome, reason) == expected_result,
                "artifact inventory outcome/reason mismatch")
    if criterion_id == "raw_bfr_d9a_reproduction":
        require((outcome == "PASS") == (exact_value == target),
                "raw D9a outcome/target mismatch")
    if (contract["maximum_field"] is not None and
            outcome != "UNCOVERED" and
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


def validate_maximum_witness_binding(witness, maximum, record, record_bytes,
                                     index, siblings, root, count):
    require(isinstance(witness, dict) and
            witness["leaf_index"] == index and
            witness["cell_key"] == record[0] and
            witness["result_record"] == record and
            witness["maximum_exact"] == maximum and
            witness["maximum_binary64_bits"] ==
                _exact_display_bits(maximum) and
            witness["merkle_siblings"] == siblings,
            "criterion maximum is not first canonical maximum")
    validate_result_merkle_witness(
        record_bytes, index, siblings, root, observed_count=count)
    return True


def validate_first_failure_binding(records, claimed_key):
    expected = next((record[0] for record in records
                     if record[1] == "FAIL"), None)
    require(claimed_key == expected,
            "criterion first-failure key is not first canonical failure")
    return True


def validate_oracle_partition(request, covered, uncovered, outcome,
                              exact_value, reason):
    require(covered | uncovered == request and
            not covered & uncovered and
            outcome == "UNCOVERED" and exact_value is None and
            reason in ORACLE_UNCOVERED_REASONS,
            "oracle request/covered/uncovered partition mismatch")
    return True


def oracle_request_key_for_dependent_key(criterion_id, key):
    """Project one D10 candidate key onto its exact oracle request key."""
    require(criterion_id in ORACLE_DEPENDENT_CRITERIA,
            "oracle-dependent propagation criterion")
    validate_scientific_cell_key(key, criterion_id)
    oracle_key = copy.deepcopy(key)
    oracle_key[7] = None
    oracle_key[9] = "identity"
    oracle_key[10] = None
    oracle_key[11] = None
    oracle_key[12] = None
    oracle_key[13] = None
    oracle_key[14] = None
    validate_scientific_cell_key(
        oracle_key, "oracle_coverage_and_crosscheck")
    return oracle_key


class _CanonicalOracleSignatureStream:
    """Bounded-memory RFC 8785 digest of ordered [oracle-key, reason] rows."""

    def __init__(self):
        self.digest = hashlib.sha256(b"[")
        self.previous = None
        self.count = 0

    def add(self, oracle_key, reason):
        validate_scientific_cell_key(
            oracle_key, "oracle_coverage_and_crosscheck")
        require(reason in RESULT_CONTRACT.D10_ORACLE_REASONS,
                "oracle propagation reason")
        encoded = jcs_bytes([oracle_key, reason])
        require(self.previous is None or self.previous < encoded,
                "oracle propagation duplicate/order drift")
        if self.count:
            self.digest.update(b",")
        self.digest.update(encoded)
        self.previous = encoded
        self.count += 1

    def finish(self):
        self.digest.update(b"]")
        return self.count, self.digest.hexdigest()


class _CanonicalOracleKeyStream:
    """Bounded-memory RFC 8785 digest of one ordered oracle-key partition."""

    def __init__(self, label):
        self.label = label
        self.digest = hashlib.sha256(b"[")
        self.previous = None
        self.count = 0

    def add(self, oracle_key):
        validate_scientific_cell_key(
            oracle_key, "oracle_coverage_and_crosscheck")
        encoded = jcs_bytes(oracle_key)
        require(self.previous is None or self.previous < encoded,
                self.label + " oracle partition duplicate/order drift")
        if self.count:
            self.digest.update(b",")
        self.digest.update(encoded)
        self.previous = encoded
        self.count += 1

    def finish(self):
        self.digest.update(b"]")
        return self.count, self.digest.hexdigest()


class OracleUncoveredPropagationVerifier:
    """Bind criteria 11--13 UNCOVERED rows to criterion 10 exactly."""

    AXIS_CRITERIA = frozenset((
        "exact_effective_d10_geometry", "emitted_direct_geometry_d10"))

    def __init__(self):
        criterion_ids = ("oracle_coverage_and_crosscheck",) + tuple(
            criterion_id for criterion_id in CRITERION_IDS
            if criterion_id in ORACLE_DEPENDENT_CRITERIA)
        self.streams = dict(
            (criterion_id, _CanonicalOracleSignatureStream())
            for criterion_id in criterion_ids)
        self.axis_groups = dict(
            (criterion_id, None) for criterion_id in self.AXIS_CRITERIA)
        self.partition_streams = {
            "covered": _CanonicalOracleKeyStream("covered"),
            "uncovered": _CanonicalOracleKeyStream("uncovered")}

    def _flush_axis_group(self, criterion_id):
        group = self.axis_groups[criterion_id]
        if group is None:
            return
        require(group["axes"] == ["x", "y", "z"],
                "oracle propagation axis set drift")
        self.streams[criterion_id].add(
            group["oracle_key"], group["reason"])
        self.axis_groups[criterion_id] = None

    def add(self, criterion_id, record):
        require(criterion_id in self.streams,
                "oracle propagation criterion")
        require(isinstance(record, list) and len(record) == 5,
                "oracle propagation result record")
        if criterion_id == "oracle_coverage_and_crosscheck":
            if record[1] == "PASS":
                self.partition_streams["covered"].add(record[0])
                return True
            if record[1] == "UNCOVERED":
                self.partition_streams["uncovered"].add(record[0])
            else:
                return True
        if record[1] != "UNCOVERED":
            return True
        key, _, _, _, reason = record
        if criterion_id == "oracle_coverage_and_crosscheck":
            self.streams[criterion_id].add(key, reason)
            return True
        oracle_key = oracle_request_key_for_dependent_key(
            criterion_id, key)
        if criterion_id not in self.AXIS_CRITERIA:
            self.streams[criterion_id].add(oracle_key, reason)
            return True
        group = self.axis_groups[criterion_id]
        encoded_key = jcs_bytes(oracle_key)
        if group is not None and group["encoded_key"] != encoded_key:
            self._flush_axis_group(criterion_id)
            group = None
        if group is None:
            group = {"oracle_key": oracle_key, "encoded_key": encoded_key,
                     "reason": reason, "axes": []}
            self.axis_groups[criterion_id] = group
        require(group["reason"] == reason and key[11] not in group["axes"],
                "oracle propagation axis/reason drift")
        group["axes"].append(key[11])
        return True

    def finish(self, criteria=None, oracle_partitions=None):
        for criterion_id in self.AXIS_CRITERIA:
            self._flush_axis_group(criterion_id)
        summaries = dict((criterion_id, stream.finish())
                         for criterion_id, stream in self.streams.items())
        expected = summaries["oracle_coverage_and_crosscheck"]
        require(all(summaries[criterion_id] == expected
                    for criterion_id in ORACLE_DEPENDENT_CRITERIA),
                "oracle-dependent UNCOVERED propagation drift")
        partition_summaries = dict(
            (name, stream.finish()) for name, stream in
            self.partition_streams.items())
        if criteria is not None:
            statuses = dict((item["criterion_id"], item["status"])
                            for item in criteria)
            if statuses["oracle_coverage_and_crosscheck"] == "UNCOVERED":
                require(expected[0] > 0 and
                        all(statuses[criterion_id] in {"FAIL", "UNCOVERED"}
                            for criterion_id in ORACLE_DEPENDENT_CRITERIA),
                        "oracle-uncovered dependent criterion disposition")
            else:
                require(expected[0] == 0,
                        "non-UNCOVERED oracle carries uncovered records")
            if oracle_partitions is not None:
                require(set(oracle_partitions) == {"covered", "uncovered"},
                        "oracle result partition inventory")
                for name, summary in partition_summaries.items():
                    partition = oracle_partitions[name]
                    if statuses["oracle_coverage_and_crosscheck"] in {
                            "PASS", "UNCOVERED"}:
                        require(partition["availability"]["state"] ==
                                    "PRESENT" and
                                partition["observed_count"] == summary[0] and
                                partition["key_ledger_sha256"] == summary[1] and
                                partition["availability"]["sha256"] ==
                                    summary[1] and
                                partition["omission_blocker"] is None,
                                "criterion-10 result/{} partition drift".format(
                                    name))
                    else:
                        require(summary[0] == 0 and
                                partition["availability"]["state"] ==
                                    "UNAVAILABLE" and
                                partition["observed_count"] == 0 and
                                partition["key_ledger_sha256"] is None and
                                partition["omission_blocker"] ==
                                    "oracle_coverage_and_crosscheck",
                                "incomplete oracle {} partition drift".format(
                                    name))
        return summaries


def validate_criterion_result_outcomes(criterion_id, status, outcomes,
                                       count, first_failure, claimed_failure):
    """Derive one aggregate status from its complete per-cell outcomes."""
    if status == "PASS":
        require(count and outcomes == {"PASS"},
                "passing criterion contains non-PASS result")
    elif status == "FAIL":
        allowed = ({"PASS", "FAIL", "UNCOVERED"}
                   if criterion_id in ORACLE_DEPENDENT_CRITERIA else
                   {"PASS", "FAIL"})
        require("FAIL" in outcomes and outcomes <= allowed and
                claimed_failure == first_failure,
                "failed criterion first-result ownership")
    elif status == "UNCOVERED":
        require((criterion_id in ORACLE_CRITERIA or
                 criterion_id in ORACLE_DEPENDENT_CRITERIA) and
                count and "UNCOVERED" in outcomes and
                outcomes <= {"PASS", "UNCOVERED"},
                "uncovered result ownership")
    elif status == "INCOMPLETE":
        require(count and outcomes == {"INCOMPLETE"},
                "complete infrastructure ledger outcome ownership")
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


class BasisRelabelValidator:
    """Validate all three inverse-mapped relabel views of each basis group."""

    def __init__(self):
        self.outer_key = None
        self.validators = {}
        self.exact_by_relabel = {}

    @staticmethod
    def outer_group_of(key):
        return tuple(jcs_bytes(item) for index, item in enumerate(key)
                     if index not in (9, 10))

    def _finish_outer_group(self):
        if self.outer_key is None:
            return
        require(set(self.validators) == set(RELABELS),
                "basis group lacks one or more frozen relabels")
        for validator in self.validators.values():
            validator.finish()
        identity_map = self.exact_by_relabel["identity"]
        require(all(source_map == identity_map for source_map in
                    self.exact_by_relabel.values()),
                "basis relabel inverse map differs from canonical sources")

    def add(self, record):
        key = record[0]
        outer_key = self.outer_group_of(key)
        if self.outer_key is not None and outer_key != self.outer_key:
            self._finish_outer_group()
            self.validators = {}
            self.exact_by_relabel = {}
        self.outer_key = outer_key
        relabel = key[9]
        require(relabel in RELABELS,
                "basis group unknown relabel")
        validator = self.validators.setdefault(relabel,
                                               BasisGroupValidator())
        validator.add(record)
        source_map = self.exact_by_relabel.setdefault(relabel, {})
        require(key[10] not in source_map,
                "basis relabel duplicate inverse-mapped source")
        source_map[key[10]] = _signed_dyadic_fraction(
            record[2]["exact_effective"])

    def finish(self):
        self._finish_outer_group()
        return True


def canonical_result_ledger(records, witness_index=None, criterion_id=None,
                            oracle_certification_authority=None):
    """Build complete canonical result bytes and independent commitments."""
    require(isinstance(records, list), "result ledger records")
    encoded_records = []
    encoded_keys = []
    previous_key = None
    basis_groups = (BasisRelabelValidator() if criterion_id ==
                    "binary64_basis_probe_diagnostic" else None)
    for record in records:
        if criterion_id is not None:
            if basis_groups is not None:
                basis_groups.add(record)
            else:
                validate_contract_result_record(
                    criterion_id, record,
                    oracle_certification_authority=
                        oracle_certification_authority)
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
                                 witness_index=None,
                                 oracle_certification_authority=None):
    """Persist one canonical result sidecar without a trailing newline."""
    commitment = canonical_result_ledger(
        records, witness_index=witness_index, criterion_id=criterion_id,
        oracle_certification_authority=oracle_certification_authority)
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

    def __init__(self, output_root, criterion_id,
                 oracle_certification_authority=None):
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
        self.basis_groups = (BasisRelabelValidator() if criterion_id ==
                             "binary64_basis_probe_diagnostic" else None)
        self.oracle_certification_authority = oracle_certification_authority
        self.closed = False

    def add(self, record):
        require(not self.closed, "closed result sidecar writer")
        require(isinstance(record, list) and len(record) == 5,
                "result record shape")
        if self.basis_groups is not None:
            self.basis_groups.add(record)
        else:
            validate_contract_result_record(
                self.criterion_id, record,
                oracle_certification_authority=
                    self.oracle_certification_authority)
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
    require(len(entries) == 3506 and entries == sorted(entries) and
            len(entries) == len(set(entries)),
            "result-evidence mutation-manifest order/count")
    require(tuple(entries) == RESULT_CONTRACT.expand_mutation_manifest(
                documentation_owned_schema_path_anchor()),
            "literal mutation manifest disagrees with approved path universe")
    return tuple(entries)


def _schema_exemplar(node, root, path="$exemplar"):
    """Construct and validate a deterministic witness for a schema node."""
    if "$ref" in node:
        require(node["$ref"].startswith("#/$defs/"),
                "exemplar local reference")
        return _schema_exemplar(
            root["$defs"][node["$ref"].split("/")[-1]], root, path)
    if "allOf" in node and "type" not in node:
        value = {}
        for clause in node["allOf"]:
            if "$ref" in clause:
                fragment = _schema_exemplar(clause, root, path)
                if isinstance(fragment, dict):
                    value.update(fragment)
            for member, member_schema in clause.get(
                    "properties", {}).items():
                value[member] = _schema_exemplar(
                    member_schema, root, path + "." + member)
        validate_schema_instance(value, node, root, path)
        return value
    if "const" in node:
        return copy.deepcopy(node["const"])
    if "oneOf" in node:
        errors = []
        for branch in node["oneOf"]:
            try:
                value = _schema_exemplar(branch, root, path)
                validate_schema_instance(value, node, root, path)
                return value
            except QualificationError as error:
                errors.append(str(error))
        raise QualificationError("no exemplar for {}: {}".format(
            path, "; ".join(errors)))
    semantic_kind = node.get("properties", {}).get("kind", {}).get("const")
    semantic_zeroes = {
        "signed_dyadic_v1": {
            "kind": "signed_dyadic_v1", "sign": 0,
            "numerator_hex": "0", "denominator_power": 1074},
        "absolute_dyadic_v1": {
            "kind": "absolute_dyadic_v1", "numerator_hex": "0",
            "denominator_power": 1074},
        "rational_v1": {"kind": "rational_v1", "numerator": "0",
                        "denominator": "1"},
        "absolute_rational_v1": {
            "kind": "absolute_rational_v1", "numerator": "0",
            "denominator": "1"},
        "rational_over_sqrt_v1": {
            "kind": "rational_over_sqrt_v1", "absolute_numerator": "0",
            "absolute_denominator": "1", "scale_squared_numerator": "1",
            "scale_squared_denominator": "1"},
    }
    if semantic_kind in semantic_zeroes:
        value = copy.deepcopy(semantic_zeroes[semantic_kind])
        validate_schema_instance(value, node, root, path)
        return value
    object_name = node.get("x-contract-object-name")
    if object_name == "availability":
        return availability("PRESENT", "a" * 64)
    if object_name == "git_identity":
        return {"state": "PRESENT", "git_commit": "a" * 40,
                "reason_code": None}
    if object_name == "worktree_observation":
        return {"state": "PRESENT", "clean": True,
                "reason_code": None}
    declared = node.get("type")
    types = declared if isinstance(declared, list) else [declared]
    types = [kind for kind in types if kind is not None]
    if "object" in types or "properties" in node:
        value = {}
        for member in node.get("required", []):
            value[member] = _schema_exemplar(
                node["properties"][member], root, path + "." + member)
    elif "array" in types or "items" in node or "prefixItems" in node:
        value = [_schema_exemplar(child, root, path + "[]")
                 for child in node.get("prefixItems", [])]
        minimum = node.get("minItems", 0)
        item_schema = node.get("items", {})
        while len(value) < minimum:
            value.append(_schema_exemplar(item_schema, root, path + "[]"))
    elif "string" in types:
        candidates = ["a", "0", "1", "a" * 16, "a" * 40, "a" * 64,
                      "0000000000000000", "1970-01-01T00:00:00Z"]
        if path.rsplit(".", 1)[-1] in {
                "denominator", "absolute_denominator",
                "scale_squared_numerator", "scale_squared_denominator"}:
            candidates = ["1"] + candidates
        if "enum" in node:
            candidates = list(node["enum"])
        value = None
        for candidate in candidates:
            try:
                validate_schema_instance(candidate, node, root, path)
                value = candidate
                break
            except QualificationError:
                pass
        require(value is not None, "string exemplar unavailable: " + path)
    elif "integer" in types:
        value = max(0, node.get("minimum", 0))
    elif "number" in types:
        value = float(max(0, node.get("minimum", 0)))
    elif "boolean" in types:
        value = True
    elif "null" in types:
        value = None
    elif "enum" in node:
        value = copy.deepcopy(node["enum"][0])
    else:
        value = {}
    validate_schema_instance(value, node, root, path)
    return value


def _wrong_schema_type(value):
    candidates = [None, {}, [], "__wrong_type__", 0, True]
    return next(candidate for candidate in candidates
                if type(candidate) is not type(value))


def _valid_oracle_covered_record(key=None):
    """Build one semantically valid covered-oracle record for mutation probes."""
    key = (copy.deepcopy(_criterion_mutation_key(
        "oracle_coverage_and_crosscheck")) if key is None else
        copy.deepcopy(key))
    rational = {"kind": "rational_v1",
                "numerator": "1" if key[6] == "position" else "0",
                "denominator": "1"}
    interval = {"kind": "interval_rational_v1",
                "lower": copy.deepcopy(rational),
                "upper": copy.deepcopy(rational)}
    certification = {"kind": "oracle_certification_v1"}
    certification.update(dict(
        (field, "CERTIFIED")
        for field in RESULT_CONTRACT.ORACLE_CERTIFICATION_FIELDS))
    value = {
        "kind": "oracle_covered_value_v1", "coverage": "COVERED",
        "row_kind": key[6], "source_ids": [0],
        "primary_depth_intervals": [[copy.deepcopy(interval)
                                      for _ in range(5)]],
        "uniform_depth_intervals": [[copy.deepcopy(interval)
                                      for _ in range(5)]],
        "intersected_primary_intervals": [copy.deepcopy(interval)],
        "first_isolating_depth": 0, "first_regular_support_depth": 0,
        "evaluated_depths": [0, 1, 2, 3, 4], "child_branches": [],
        "certification": certification}
    record = [key, "PASS", value, None, None]
    validate_contract_result_record(
        "oracle_coverage_and_crosscheck", record,
        oracle_certification_authority=_ORACLE_CERTIFICATION_AUTHORITY)
    return record


def _valid_result_record_for_mutation(criterion_id, variant=0):
    """Build one semantically valid complete record before mutating M12."""
    require(variant in {0, 1}, "M12 baseline variant")
    key = _criterion_mutation_key(criterion_id)
    if variant:
        if criterion_id == "complete_artifact_inventory":
            pass  # target-owned content identity is changed below
        elif criterion_id == "raw_bfr_d9a_reproduction":
            key[1] = "content-z"
        elif criterion_id in D12_CRITERIA:
            key[0] = "content-z"
        elif criterion_id != "bindings_and_independence":
            key[5] = "sample-z"
    contract = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]
    if criterion_id == "oracle_coverage_and_crosscheck":
        record = [key, "UNCOVERED", None, None,
                  "EIGENBASIS_CERTIFICATION_FAILED"]
        validate_contract_result_record(criterion_id, record)
        return record
    schema = cached_schema()
    exact_kind = next(kind for kind in contract["exact_value_kinds"]
                      if kind is not None)
    if criterion_id == "d12_instrumented_tsan":
        exact_kind = "d12_tsan_finding_summary_v1"
    target_kind = next((kind for kind in contract["target_kinds"]
                        if kind is not None), None)
    value = _schema_exemplar(schema["$defs"][exact_kind], schema,
                             "$mutation.valid.value")
    target = (None if target_kind is None else
              _schema_exemplar(schema["$defs"][target_kind], schema,
                               "$mutation.valid.target"))
    outcome, reason = "PASS", None
    zero_rational = {"kind": "rational_v1", "numerator": "0",
                     "denominator": "1"}
    zero_absolute = {"kind": "absolute_rational_v1", "numerator": "0",
                     "denominator": "1"}
    if criterion_id == "bindings_and_independence":
        value["manifest_file_sha256"] = B2.MANIFEST_FILE_SHA256
        value["manifest_contract_sha256"] = B2.MANIFEST_CONTRACT_SHA256
    elif criterion_id == "complete_artifact_inventory":
        if variant:
            target["content_id"] = "content-z"
        key[1:] = [target["content_id"], target["candidate"],
                   target["level"], target["cache_mode"]]
        value.update({
            "expected_slot_ordinal": target["expected_slot_ordinal"],
            "compressed_sha256": target["compressed_sha256"],
            "decompressed_json_sha256":
                target["decompressed_json_sha256"],
            "canonical_b2rowv1_sha256":
                target["canonical_b2rowv1_sha256"],
            "expected_identity_matches": True})
    elif criterion_id == "representation_structure":
        job = B2.valid_content_jobs(B2.load_manifest())[0]
        _, faces, _ = B2.independent_mesh(job)
        key[0] = job["content_identity_key"]
        key[3] = 0
        source_ids = sorted(set(faces[0]))
        anchor_source = faces[0][0]
        coefficients = [1.0 if source_id == anchor_source else 0.0
                        for source_id in source_ids]
        row = {"face_row": 0, "sample_id": key[5],
               "row_kind": key[6], "source_ids": source_ids,
               "coefficients": coefficients}
        digest = hashlib.sha256()
        digest.update(b"B2ROWV1")
        digest.update(struct.pack("<i", key[3]))
        sample_bytes = key[5].encode("utf-8")
        digest.update(struct.pack("<I", len(sample_bytes)))
        digest.update(sample_bytes)
        digest.update(struct.pack("<I", ROW_ORDER.index(key[6])))
        digest.update(struct.pack("<I", len(source_ids)))
        for source_id, coefficient in zip(source_ids, coefficients):
            digest.update(struct.pack("<i", source_id))
            digest.update(struct.pack("<d", coefficient))
        effective = effective_numerators(row, anchor_source)
        value = {
            "kind": "structure_present_v1", "anchor_id": "v0",
            "anchor_present": True, "canonical_source_ids": source_ids,
            "provider_coefficient_bits": [
                binary64_bits_hex(item) for item in coefficients],
            "provider_row_sha256": digest.hexdigest(),
            "effective_coefficients": [
                _signed_dyadic_descriptor(effective[source_id])
                for source_id in source_ids],
            "observed_sum": _signed_dyadic_descriptor(1 << 1074),
            "expected_sum": _signed_dyadic_descriptor(1 << 1074),
            "source_count": len(source_ids)}
    elif criterion_id == "constant_field_bits":
        bits = _expected_constant_bits(key)
        value["observed_bits"] = bits
        value["expected_bits"] = bits
    elif exact_kind == "emitted_interval_scalar_v1":
        value["observed_bits"] = "0000000000000000"
        value["analytic_interval"] = {
            "kind": "interval_rational_v1",
            "lower": copy.deepcopy(zero_rational),
            "upper": copy.deepcopy(zero_rational)}
        value["absolute_error_upper"] = copy.deepcopy(zero_absolute)
    elif exact_kind == "geometry_axis_v1":
        value["axis"] = key[11]
        value["view"] = key[7]
        value["observed"] = (
            {"kind": "binary64_scalar_v1",
             "bits": "0000000000000000"}
            if key[7] == "emitted_binary64" else
            _signed_dyadic_descriptor(0))
        value["reference_interval"] = {
            "kind": "interval_rational_v1",
            "lower": copy.deepcopy(zero_rational),
            "upper": copy.deepcopy(zero_rational)}
        one = {"kind": "rational_v1", "numerator": "1",
               "denominator": "1"}
        value["normalized_bound"] = {
            "kind": "normalized_interval_bound_v1",
            "difference_interval": {
                "kind": "interval_rational_v1",
                "lower": copy.deepcopy(zero_rational),
                "upper": copy.deepcopy(zero_rational)},
            "distance_upper": copy.deepcopy(zero_absolute),
            "scale_squared_interval": {
                "kind": "interval_rational_v1", "lower": copy.deepcopy(one),
                "upper": copy.deepcopy(one)},
            "scale_lower": copy.deepcopy(one),
            "ideal_normalized": {
                "kind": "rational_over_sqrt_v1",
                "absolute_numerator": "0", "absolute_denominator": "1",
                "scale_squared_numerator": "1",
                "scale_squared_denominator": "1"},
            "normalized_upper": copy.deepcopy(zero_absolute)}
    elif exact_kind == "basis_value_v1":
        value["emitted_basis_bits"] = "0000000000000000"
        value["exact_effective"] = _signed_dyadic_descriptor(0)
        value["source_error"] = _absolute_dyadic_descriptor(0)
        value["group_l1"] = _absolute_dyadic_descriptor(0)
    if target_kind == "absolute_rational_target_v1":
        target = absolute_rational_target(
            _row_target_denominator(criterion_id, key))
    if criterion_id == "d12_peak_rss":
        value["stage"] = key[12]
    if criterion_id == "d12_instrumented_tsan":
        value.update({"finding_count": 0, "sanitizer_abort": False,
                      "sanitizer_report_sha256": None})
        target = {"kind": "d12_tsan_finding_target_v1",
                  "finding_count": 0}
    record = [key, outcome, value, target, reason]
    validate_contract_result_record(
        criterion_id, record,
        defer_basis_group=(criterion_id ==
                           "binary64_basis_probe_diagnostic"))
    return record


def validate_bound_jcs_array(raw, descriptor):
    """Validate one closed JCS array against its byte/count commitment."""
    value = strict_json_bytes(raw)
    require(isinstance(value, list) and jcs_bytes(value) == raw and
            len(raw) == descriptor["byte_length"] and
            len(value) == descriptor["record_count"] and
            sha256_bytes(raw) == descriptor["sha256"] ==
            descriptor["availability"]["sha256"],
            "JCS array differs from bound byte/count/hash commitment")
    return value


def _criteria_contract_fixture():
    """Return one schema/semantic-valid closed 32-slot criterion vector."""
    digest = "a" * 64
    result = []
    for criterion_id in CRITERION_IDS:
        expected = EXPECTED_CELL_COUNTS[criterion_id]
        if criterion_id in INFRASTRUCTURE_CRITERIA:
            target = None
            if criterion_id == "complete_artifact_inventory":
                empty_digest = sha256_bytes(b"[]")
                target = {
                    "kind": "unexpected_paths_target_v1",
                    "required_record_count": 0,
                    "sidecar": {
                        "availability": availability(
                            "PRESENT", empty_digest),
                        "relative_path": RESULT_LEDGER_DIRECTORY +
                            "/unexpected-artifact-paths.json",
                        "byte_length": 2, "record_count": 0,
                        "sha256": empty_digest}}
            result.append(criterion_record(
                criterion_id, "INCOMPLETE", expected=expected,
                target=target))
        elif criterion_id in ORACLE_CRITERIA:
            result_digest = "b" * 64
            result.append(criterion_record(
                criterion_id, "UNCOVERED", expected=expected,
                observed=expected, ledger=digest,
                result_ledger=result_digest,
                result_merkle_root="c" * 64,
                result_artifact={
                    "availability": availability("PRESENT", result_digest),
                    "relative_path": result_ledger_relative_path(
                        criterion_id),
                    "byte_length": 2, "record_count": expected},
                witness=None))
        elif criterion_id in D12_CRITERIA:
            result.append(criterion_record(
                criterion_id, "INCOMPLETE", expected=expected,
                ledger=digest))
        else:
            result.append(criterion_record(
                criterion_id, "OMITTED_AFTER_INFRASTRUCTURE_FAILURE",
                blocker=CRITERION_IDS[0], expected=expected,
                ledger=digest))
    validate_criteria(result)
    return result


def _pre_result_ledger_contract_fixture():
    result = []
    schema = cached_schema()
    slots = schema["$defs"]["matrix"]["properties"]["ledgers"][
        "prefixItems"]
    for slot in slots:
        fixed = schema["$defs"][slot["$ref"].split("/")[-1]]["allOf"][1][
            "properties"]
        criterion_id = fixed["criterion_id"]["const"]
        partition = fixed["partition"]["const"]
        expected = EXPECTED_CELL_COUNTS[criterion_id]
        if partition in {"covered", "uncovered"}:
            item = {
                "criterion_id": criterion_id, "partition": partition,
                "expected_count": None, "observed_count": 0,
                "key_ledger_sha256": None,
                "availability": availability(
                    "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE"),
                "omission_blocker": "oracle_coverage_and_crosscheck"}
        else:
            item = {
                "criterion_id": criterion_id, "partition": partition,
                "expected_count": expected, "observed_count": expected,
                "key_ledger_sha256": "a" * 64,
                "availability": availability("PRESENT", "a" * 64),
                "omission_blocker": None}
        result.append(item)
    _validate_pre_result_ledgers(result)
    return result


def _criterion_mutation_key(criterion_id):
    if criterion_id == "bindings_and_independence":
        return [criterion_id, "exact_head_and_provenance"]
    if criterion_id == "complete_artifact_inventory":
        return [criterion_id, "content", "bfr", 2, "cache_disabled"]
    if criterion_id == "raw_bfr_d9a_reproduction":
        return [criterion_id, "content", 2, "cache_disabled"]
    if criterion_id == "d12_preparation_cost":
        return ["content", 2, "release", "cache_disabled", None, None,
                None, "measured", 0, None, None, None, None,
                "preparation_duration_ns"]
    if criterion_id == "d12_retained_payload":
        return ["content", 2, "release", "cache_disabled", None, None,
                None, None, None, 0, None, None, None,
                "retained_payload_bytes"]
    if criterion_id == "d12_peak_rss":
        return ["content", 2, "release", "cache_disabled", None, None,
                None, None, None, None, None, None,
                "pre_refiner_baseline", "rss_bytes"]
    if criterion_id == "d12_cache_disabled_concurrency":
        return ["content", 2, "tsan", "cache_disabled", 1, 0, 0,
                None, None, None, None, None, "thread_result",
                "row_digest"]
    if criterion_id == "d12_instrumented_tsan":
        return ["content", 2, "tsan", "threaded_cache", 1, None, None,
                None, None, None, None, None, "sanitizer_summary",
                "tsan_finding_count"]
    pair_criteria = {
        "anchor_sensitivity_exact_coeff",
        "anchor_sensitivity_exact_geometry",
        "anchor_sensitivity_emitted_geometry"}
    stabilization = criterion_id.startswith("stabilization_")
    axis_criteria = {
        "regular_analytic_emitted_geometry",
        "exact_effective_d10_geometry", "emitted_direct_geometry_d10",
        "anchor_sensitivity_exact_geometry",
        "anchor_sensitivity_emitted_geometry",
        "binary64_direct_geometry_fidelity",
        "relabel_emitted_geometry_fidelity",
        "stabilization_6_7_exact_geometry",
        "stabilization_6_7_emitted_geometry",
        "stabilization_7_8_exact_geometry",
        "stabilization_7_8_emitted_geometry"}
    exact_view = {
        "relabel_exact_effective_coefficients",
        "regular_analytic_exact_rows", "exact_effective_d10_coeff",
        "exact_effective_d10_geometry", "anchor_sensitivity_exact_coeff",
        "anchor_sensitivity_exact_geometry",
        "stabilization_6_7_exact_coeff",
        "stabilization_6_7_exact_geometry",
        "stabilization_7_8_exact_coeff",
        "stabilization_7_8_exact_geometry"}
    emitted_view = {
        "constant_field_bits", "regular_analytic_emitted_geometry",
        "emitted_direct_geometry_d10",
        "anchor_sensitivity_emitted_geometry",
        "binary64_basis_probe_diagnostic",
        "binary64_direct_geometry_fidelity",
        "relabel_emitted_geometry_fidelity",
        "stabilization_6_7_emitted_geometry",
        "stabilization_7_8_emitted_geometry"}
    quantity = "position"
    view = ("structural" if criterion_id == "representation_structure" else
            "exact_effective" if criterion_id in exact_view else
            "emitted_binary64" if criterion_id in emitted_view else None)
    if criterion_id == "regular_analytic_area_integrand":
        quantity, view = "area_integrand", "exact_effective"
    elif criterion_id == "regular_analytic_legacy_volume_integrand":
        quantity, view = "legacy_volume_integrand", "exact_effective"
    anchor = None if criterion_id in pair_criteria else "v0"
    relabel = (None if criterion_id == "cache_mode_bit_identity" else
               "rank_reverse" if criterion_id in {
                    "relabel_exact_effective_coefficients",
                    "relabel_emitted_geometry_fidelity"} else "identity")
    if criterion_id == "constant_field_bits":
        relabel = "identity"
    level = (7 if criterion_id.startswith("stabilization_6_7") else
             8 if criterion_id.startswith("stabilization_7_8") else
             2 if criterion_id in {
                "representation_structure", "constant_field_bits",
                "relabel_exact_effective_coefficients",
                "cache_mode_bit_identity"} else 7)
    key = ["content",
           "cache_pair" if criterion_id == "cache_mode_bit_identity" else
           "cache_disabled",
           level, 0, None, "sample", quantity, view, anchor, relabel,
           0 if criterion_id == "binary64_basis_probe_diagnostic" else None,
           "x" if criterion_id in axis_criteria else None,
           "v0_v1" if criterion_id in pair_criteria else None,
           ("6_7" if criterion_id.startswith("stabilization_6_7") else
            "7_8" if criterion_id.startswith("stabilization_7_8") else
            None),
           "positive_zero" if criterion_id == "constant_field_bits" else
           None]
    validate_scientific_cell_key(key, criterion_id)
    return key


def _d12_envelope_contract_fixture():
    global _D12_FIXTURE_CACHE
    if _D12_FIXTURE_CACHE is not None:
        return copy.deepcopy(_D12_FIXTURE_CACHE)
    schema = cached_schema()
    value = _schema_exemplar(
        schema["$defs"]["anchored_row_representation_d12"], schema,
        "$mutation.d12")
    value["git"] = {"head": "a" * 40, "head_query_ok": True,
                    "worktree_clean": True}
    source_role = {
        "provider_release": "row_provider",
        "provider_tsan": "row_provider",
        "representation_release": "representation_candidate",
        "representation_tsan": "representation_candidate",
    }
    for binary_name, binary in value["binaries"].items():
        binary["source_inventory"] = [{
            "path": path, "sha256": sha256_file(ROOT / path)}
            for path in RUNTIME_SOURCE_PATHS[source_role[binary_name]]]
    build = B2.load_manifest()["qualification_platform"]["build"]
    for name, flags in (
            ("release", build["common_release_compile_flags"]),
            ("tsan", build["thread_sanitizer_compile_flags"])):
        profile = value["build_profiles"][name]
        commands = _d12_build_command_fixture(name, flags)
        profile.update({
            "compiler_path": build["compiler_path"],
            "compiler_version": build["compiler_version"],
            "flags": copy.deepcopy(flags),
            "sdk_path": build["macos_sdk_path"],
            "sdk_version": build["macos_sdk_version"],
            "cmake_path": build["opensubdiv"]["cmake"]["path"],
            "cmake_version": build["opensubdiv"]["cmake"]["version"],
            "make_path": build["opensubdiv"]["build_tool"]["path"],
            "make_version": build["opensubdiv"]["build_tool"]["version"],
            "compile_commands": commands["compile_commands"],
            "link_commands": commands["link_commands"],
        })
    for name, dependency in value["dependencies"].items():
        dependency["source_identity"] = {
            "gmp": "6.3.0", "mpfr": "4.2.2",
            "opensubdiv": "3.7.0"}[name]
    value["platform"] = {
        "platform_state": "UNQUALIFIED_PLATFORM",
        "expected_fingerprint": copy.deepcopy(
            B2.load_manifest()["qualification_platform"]["fingerprint"]),
        "observed_fingerprint": dict(
            B2.load_manifest()["qualification_platform"]["fingerprint"],
            chip="Hosted Mac", kern_hv_vmm_present=1),
        "field_mismatches": ["chip", "kern_hv_vmm_present"],
        "compiler_identity": B2.load_manifest()["qualification_platform"][
            "build"]["compiler_version"], "github_hosted": True,
        "virtualization_observation": {
            "kern_hv_vmm_present": 1, "shared_host_evidence": True},
        "power_thermal_observations": [
            _d12_observation_record(identity, boundary,
                                    _d12_unavailable_probe())
            for identity, boundary in _expected_d12_boundary_identities()]}
    value["authority"] = frozen_authority_record()

    def sidecar(path, count, digest):
        return {"availability": availability("PRESENT", digest),
                "relative_path": path, "byte_length": 2,
                "record_count": count, "sha256": digest}

    value["workload"]["provider_serial_reference"] = sidecar(
        "anchored-row-d12-v1/serial/provider-rows.b2rowv1",
        693000, "b" * 64)
    value["workload"]["representation_serial_reference"] = sidecar(
        "anchored-row-d12-v1/serial/representation-outputs.json",
        5544000, "c" * 64)
    value["workload"]["process_observation_sidecar"] = sidecar(
        "anchored-row-d12-v1/process/process-observations.json",
        4189640, "d" * 64)
    value["workload"]["sidecars"] = [sidecar(
        "anchored-row-d12-v1/workers/cache_disabled/content/level-2/"
        "workers-1/round-00/worker-0-provider.b2rowv1", 1, "e" * 64)]
    full_criteria = _criteria_contract_fixture()
    for criterion_id in D12_CRITERIA:
        index = CRITERION_IDS.index(criterion_id)
        expected = EXPECTED_CELL_COUNTS[criterion_id]
        result_digest = format(index + 1, "064x")
        full_criteria[index] = criterion_record(
            criterion_id, "INCOMPLETE", expected=expected,
            observed=expected, ledger="a" * 64,
            result_ledger=result_digest, result_merkle_root="f" * 64,
            result_artifact={
                "availability": availability("PRESENT", result_digest),
                "relative_path": result_ledger_relative_path(criterion_id),
                "byte_length": 2, "record_count": expected})
    validate_criteria(full_criteria)
    value["criteria"] = full_criteria[-5:]
    value["serial_only_context"]["failure_records_sha256"] = sha256_bytes(
        jcs_bytes(value["serial_only_context"]["failure_records"]))
    value["content_sha256"] = ZERO_SHA256
    value["content_sha256"] = sha256_bytes(jcs_bytes(value))
    validate_d12_envelope_contract(value, "a" * 40)
    _D12_FIXTURE_CACHE = copy.deepcopy(value)
    return copy.deepcopy(value)


def _expected_d12_boundary_identities():
    boundaries = ("primary_before", "primary_after",
                  "determinism_before", "determinism_after")
    return [(identity, boundary)
            for identity in B2.expected_numeric_case_identities(
                B2.load_manifest())
            for boundary in boundaries]


def _d12_unavailable_probe():
    return {
        "schema_version": 1, "kind": "bfr_platform_probe",
        "status": "query_failed", "finite": True,
        "fingerprint_queries_ok": False, "fingerprint": {},
        "power": {"api": B2.EXPECTED_POWER_API, "query_ok": False,
                  "raw": "", "value": ""},
        "thermal": {"api": B2.EXPECTED_THERMAL_API, "query_ok": False,
                    "raw": -1, "value": ""},
        "process_returncode": None}


def _d12_build_command_fixture(profile_name, flags):
    build = B2.load_manifest()["qualification_platform"]["build"]
    root = "/d12-proof/" + profile_name + "-build"
    install_root = "/d12-proof/" + profile_name + "-install"
    provider_source = str((ROOT / RUNTIME_SOURCE_ENTRYPOINTS[
        "row_provider"][0]).resolve())
    representation_source = str((ROOT / RUNTIME_SOURCE_ENTRYPOINTS[
        "representation_candidate"][0]).resolve())
    provider_object = root + "/provider.o"
    representation_object = root + "/representation.o"
    prefix = [build["compiler_path"]] + copy.deepcopy(flags)
    return {
        "compile_commands": [
            prefix + ["-MMD", "-MF", root + "/provider.d",
                      "-I" + install_root + "/include",
                      provider_source, "-c", "-o", provider_object],
            prefix + ["-MMD", "-MF", root + "/representation.d",
                      representation_source, "-c", "-o",
                      representation_object],
        ],
        "link_commands": [
            prefix + [provider_object,
                      install_root + "/lib/libosdCPU.a",
                      "-framework", "IOKit", "-framework", "Foundation",
                      "-Wl,-map," + root + "/provider.map",
                      "-o", root + "/provider"],
            prefix + [representation_object,
                      "-Wl,-map," + root + "/representation.map",
                      "-o", root + "/representation"],
        ],
    }


def _d12_rebuild_environment():
    observed = B2.load_manifest()["qualification_platform"]["build"][
        "opensubdiv"]["build_environment"]
    expected = {
        "LANG": "C", "LC_ALL": "C", "SOURCE_DATE_EPOCH": "0",
        "TZ": "UTC", "ZERO_AR_DATE": "1"}
    require(observed == expected,
            "D12 frozen closed build environment drift")
    return copy.deepcopy(expected)


def _run_d12_closed_git(arguments, working_directory, text=True):
    directory = pathlib.Path(working_directory).resolve()
    require(directory.is_dir(), "D12 Git working directory is unavailable")
    return subprocess.run(
        ["/usr/bin/git"] + list(arguments), check=False, cwd=str(directory),
        env=_d12_rebuild_environment(), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=text)


def _d12_git_path(raw, label):
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise QualificationError(label + " path is not UTF-8") from error
    path = pathlib.PurePosixPath(value)
    require(value and not path.is_absolute() and ".." not in path.parts and
            value == path.as_posix(), label + " path is not canonical")
    return value


def _d12_z_records(raw, label):
    require(raw.endswith(b"\0"), label + " is not NUL terminated")
    records = raw[:-1].split(b"\0")
    require(records and all(records), label + " contains an empty record")
    return records


def _audit_d12_git_worktree(root_path, expected_head=None):
    """Byte-authenticate every tracked path to a normal pinned Git index."""
    root = pathlib.Path(root_path).resolve()
    git_metadata = root / ".git"
    require(root == root_path and git_metadata.is_dir() and
            git_metadata.resolve() == git_metadata,
            "D12 source must be a canonical standalone Git checkout")
    head = _run_d12_closed_git(["rev-parse", "HEAD"], root)
    tree = _run_d12_closed_git(["rev-parse", "HEAD^{tree}"], root)
    status = _run_d12_closed_git(
        ["status", "--porcelain=v1", "--untracked-files=all"], root)
    toplevel = _run_d12_closed_git(["rev-parse", "--show-toplevel"], root)
    git_dir = _run_d12_closed_git(
        ["rev-parse", "--absolute-git-dir"], root)
    object_format = _run_d12_closed_git(
        ["rev-parse", "--show-object-format"], root)
    observed_head = head.stdout.strip()
    require(head.returncode == 0 and
            GIT_RE.fullmatch(observed_head) is not None and
            (expected_head is None or observed_head == expected_head) and
            tree.returncode == 0 and
            GIT_RE.fullmatch(tree.stdout.strip()) is not None and
            status.returncode == 0 and not status.stdout.strip() and
            toplevel.returncode == 0 and
            pathlib.Path(toplevel.stdout.strip()).resolve() == root and
            git_dir.returncode == 0 and
            pathlib.Path(git_dir.stdout.strip()).resolve() == git_metadata and
            object_format.returncode == 0 and
            object_format.stdout.strip() == "sha1",
            "D12 Git head/tree/root/cleanliness/object-format drift")

    flags = _run_d12_closed_git(["ls-files", "-v", "-z"], root, text=False)
    index = _run_d12_closed_git(
        ["ls-files", "--stage", "-z"], root, text=False)
    committed = _run_d12_closed_git(
        ["ls-tree", "-r", "-z", observed_head], root, text=False)
    require(flags.returncode == index.returncode == committed.returncode == 0,
            "D12 Git index/tree enumeration failed")

    flag_paths = []
    for record in _d12_z_records(flags.stdout, "D12 Git index flags"):
        require(len(record) > 2 and record[:2] == b"H ",
                "D12 Git index contains non-normal tracked flags")
        flag_paths.append(_d12_git_path(record[2:], "D12 Git index flag"))
    index_entries = []
    for record in _d12_z_records(index.stdout, "D12 Git index"):
        require(b"\t" in record, "D12 Git index record shape drift")
        metadata, raw_path = record.split(b"\t", 1)
        fields = metadata.decode("ascii", errors="strict").split(" ")
        require(len(fields) == 3 and fields[2] == "0" and
                re.fullmatch(r"[0-9a-f]{40}", fields[1]) is not None,
                "D12 Git index metadata drift")
        index_entries.append((fields[0], fields[1],
                              _d12_git_path(raw_path, "D12 Git index")))
    tree_entries = []
    for record in _d12_z_records(committed.stdout, "D12 Git tree"):
        require(b"\t" in record, "D12 Git tree record shape drift")
        metadata, raw_path = record.split(b"\t", 1)
        fields = metadata.decode("ascii", errors="strict").split(" ")
        require(len(fields) == 3 and fields[1] == "blob" and
                fields[0] in {"100644", "100755"} and
                re.fullmatch(r"[0-9a-f]{40}", fields[2]) is not None,
                "D12 Git tree contains unsupported entry metadata")
        tree_entries.append((fields[0], fields[2],
                             _d12_git_path(raw_path, "D12 Git tree")))
    require(index_entries == tree_entries and
            flag_paths == [entry[2] for entry in tree_entries],
            "D12 Git index differs from the committed tracked tree")

    ledger = []
    for mode, oid, relative in tree_entries:
        path = root / relative
        require(path.is_file() and not path.is_symlink() and
                path.resolve().is_relative_to(root),
                "D12 tracked worktree path is unavailable or aliased: " +
                relative)
        raw = path.read_bytes()
        observed_oid = hashlib.sha1(
            b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        ).hexdigest()
        executable = bool(path.stat().st_mode & 0o111)
        require(observed_oid == oid and
                executable == (mode == "100755"),
                "D12 tracked worktree bytes/mode differ from Git: " + relative)
        ledger.append({"path": relative, "git_blob": oid,
                       "sha256": sha256_bytes(raw), "mode": mode})
    return {"head": observed_head, "tree": tree.stdout.strip(),
            "tracked_files": ledger}


def _audit_d12_source_checkout(source_root, manifest):
    """Authenticate the pinned checkout with no ambient Git authority."""
    root = pathlib.Path(source_root).resolve()
    audit = _audit_d12_git_worktree(root, B2.OPENSUBDIV_COMMIT)
    tracked = {item["path"]: item for item in audit["tracked_files"]}
    ledger = []
    for relative in manifest["qualification_platform"]["build"][
            "opensubdiv"]["translation_units_in_target_order"]:
        path = root / relative
        require(relative in tracked and path.is_file() and
                sha256_file(path) == tracked[relative]["sha256"],
                "OpenSubdiv worktree translation unit differs from Git blob: " +
                relative)
        ledger.append({"path": relative, "sha256": sha256_file(path)})
    return {"head": audit["head"], "tree": audit["tree"],
            "translation_units": ledger}


def _d12_installed_header_bindings(source_root, install_root):
    """Bind every installed OpenSubdiv header to its pinned source blob."""
    source = pathlib.Path(source_root).resolve()
    include = (pathlib.Path(install_root).resolve() / "include").resolve()
    require(include.is_dir() and include.is_relative_to(
                pathlib.Path(install_root).resolve()),
            "D12 OpenSubdiv installed include root unavailable")
    tracked_query = _run_d12_closed_git(
        ["ls-files", "-z"], source, text=False)
    require(tracked_query.returncode == 0,
            "D12 OpenSubdiv tracked header enumeration failed")
    tracked = {
        _d12_git_path(record, "D12 OpenSubdiv tracked header")
        for record in _d12_z_records(
            tracked_query.stdout, "D12 OpenSubdiv tracked header list")}
    bindings = {}
    for installed in sorted(include.rglob("*")):
        if installed.is_dir():
            continue
        require(installed.is_file() and not installed.is_symlink() and
                installed.resolve().is_relative_to(include),
                "D12 OpenSubdiv installed header is unavailable/aliased")
        relative = installed.relative_to(include).as_posix()
        source_header = source / relative
        require(relative in tracked and source_header.is_file() and
                not source_header.is_symlink() and
                installed.read_bytes() == source_header.read_bytes(),
                "D12 OpenSubdiv installed header differs from pinned source: " +
                relative)
        bindings[str(installed.resolve())] = {
            "source_relative_path": relative,
            "sha256": sha256_file(installed)}
    require(bindings, "D12 OpenSubdiv installed header set is empty")
    return bindings


def _validate_d12_full_probe(probe):
    expected_keys = {
        "schema_version", "kind", "status", "finite",
        "fingerprint_queries_ok", "fingerprint", "power", "thermal",
        "process_returncode"}
    expected_fingerprint = B2.load_manifest()["qualification_platform"][
        "fingerprint"]
    fingerprint = probe.get("fingerprint") if isinstance(probe, dict) else None
    require(isinstance(probe, dict) and set(probe) == expected_keys and
            probe["schema_version"] == 1 and
            probe["kind"] == "bfr_platform_probe" and
            probe["status"] in {"ok", "query_failed"} and
            probe["finite"] is True and
            type(probe["fingerprint_queries_ok"]) is bool and
            isinstance(fingerprint, dict) and
            (fingerprint == {} or
             set(fingerprint) == set(expected_fingerprint) and
             all(type(fingerprint[key]) is type(expected_fingerprint[key])
                 for key in expected_fingerprint)) and
            set(probe["power"]) == {"api", "query_ok", "raw", "value"} and
            probe["power"]["api"] == B2.EXPECTED_POWER_API and
            type(probe["power"]["query_ok"]) is bool and
            isinstance(probe["power"]["raw"], str) and
            isinstance(probe["power"]["value"], str) and
            set(probe["thermal"]) == {"api", "query_ok", "raw", "value"} and
            probe["thermal"]["api"] == B2.EXPECTED_THERMAL_API and
            type(probe["thermal"]["query_ok"]) is bool and
            type(probe["thermal"]["raw"]) is int and
            isinstance(probe["thermal"]["value"], str) and
            (probe["process_returncode"] is None or
             type(probe["process_returncode"]) is int) and
            ((probe["status"] == "ok" and
              probe["process_returncode"] == 0) or
             (probe["status"] == "query_failed" and
              probe["process_returncode"] != 0)) and
            ((probe["fingerprint_queries_ok"] is True and
              set(fingerprint) == set(expected_fingerprint)) or
             (probe["fingerprint_queries_ok"] is False)) and
            ((probe["power"]["query_ok"] is True and
              probe["power"]["raw"] and
              probe["power"]["value"] == {
                  "AC Power": B2.EXPECTED_POWER_VALUE,
                  "Battery Power": "kIOPSBatteryPowerValue",
                  "Off Line": "kIOPSOffLineValue",
              }.get(probe["power"]["raw"], "UNKNOWN_POWER_VALUE")) or
             (probe["power"]["query_ok"] is False and
              probe["power"]["raw"] == "" and
              probe["power"]["value"] == "")) and
            ((probe["thermal"]["query_ok"] is True and
              probe["thermal"]["raw"] in {0, 1, 2, 3} and
              probe["thermal"]["value"] == (
                "NSProcessInfoThermalStateNominal",
                "NSProcessInfoThermalStateFair",
                "NSProcessInfoThermalStateSerious",
                "NSProcessInfoThermalStateCritical")[
                    probe["thermal"]["raw"]]) or
             (probe["thermal"]["query_ok"] is False and
              probe["thermal"]["raw"] == -1 and
              probe["thermal"]["value"] == "")),
            "D12 full process-boundary probe is malformed or lossy")
    return probe


def _d12_observation_record(identity, boundary, probe):
    probe = copy.deepcopy(_validate_d12_full_probe(probe))
    return {
        "boundary": jcs_bytes(list(identity) + [boundary]).decode("utf-8"),
        "power_api": probe["power"]["api"],
        "power_query_ok": probe["power"]["query_ok"],
        "power_value": probe["power"]["value"] or "UNKNOWN",
        "thermal_api": probe["thermal"]["api"],
        "thermal_query_ok": probe["thermal"]["query_ok"],
        "thermal_value": probe["thermal"]["value"] or "UNKNOWN",
        "probe": probe}


def _decode_d12_observation(item, expected_identity, expected_boundary):
    raw = item["boundary"].encode("utf-8")
    try:
        value = strict_json_bytes(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QualificationError(
            "D12 process-boundary probe is not canonical JSON") from error
    require(jcs_bytes(value) == raw and
            value == list(expected_identity) + [expected_boundary],
            "D12 process-boundary identity/probe encoding drift")
    probe = _validate_d12_full_probe(item["probe"])
    require(item == _d12_observation_record(
                expected_identity, expected_boundary, probe),
            "D12 flattened boundary observation differs from full probe")
    return probe


def _absolute_command_path(token, suffix, message):
    path = pathlib.Path(token)
    resolved = path.resolve()
    require(path.is_absolute() and token == str(resolved) and
            resolved.name and "," not in token and token.endswith(suffix),
            message)
    return token


def _validate_d12_compile_command(command, expected_flags, source_path,
                                  provider_role):
    build = B2.load_manifest()["qualification_platform"]["build"]
    prefix = [build["compiler_path"]] + expected_flags
    require(command[:len(prefix)] == prefix,
            "D12 compile command profile flags/order drift")
    suffix = command[len(prefix):]
    expected_source = str((ROOT / source_path).resolve())
    expected_length = 8 if provider_role else 7
    require(len(suffix) == expected_length and
            suffix[:2] == ["-MMD", "-MF"] and
            suffix[-4:] == [expected_source, "-c", "-o", suffix[-1]],
            "D12 compile command is not the exact frozen role grammar")
    dependency_path = _absolute_command_path(
        suffix[2], ".d", "D12 compile dependency path drift")
    if provider_role:
        require(suffix[3].startswith("-I") and len(suffix[3]) > 2,
                "D12 provider include root drift")
        include_root = _absolute_command_path(
            suffix[3][2:], "/include", "D12 provider include root drift")
        source_index = 4
    else:
        include_root = None
        source_index = 3
    require(suffix[source_index] == expected_source and
            suffix[source_index + 1:source_index + 3] == ["-c", "-o"] and
            source_index + 3 == len(suffix) - 1,
            "D12 compile source/output role drift")
    object_path = _absolute_command_path(
        suffix[-1], ".o", "D12 compile object path drift")
    return {"dependency": dependency_path, "include": include_root,
            "object": object_path}


def _validate_d12_link_command(command, expected_flags, compile_record,
                               provider_role):
    build = B2.load_manifest()["qualification_platform"]["build"]
    prefix = [build["compiler_path"]] + expected_flags
    require(command[:len(prefix)] == prefix,
            "D12 link command profile flags/order drift")
    suffix = command[len(prefix):]
    if provider_role:
        require(len(suffix) == 9 and
                suffix[0] == compile_record["object"] and
                suffix[1].endswith("/lib/libosdCPU.a") and
                suffix[2:6] == ["-framework", "IOKit",
                                "-framework", "Foundation"] and
                suffix[6].startswith("-Wl,-map,") and
                suffix[7:9] == ["-o", suffix[8]],
                "D12 provider link command is not the exact frozen grammar")
        library = _absolute_command_path(
            suffix[1], "/lib/libosdCPU.a",
            "D12 provider library input drift")
        require(compile_record["include"][:-len("/include")] ==
                library[:-len("/lib/libosdCPU.a")],
                "D12 provider include/library roots differ")
        map_token = suffix[6]
        output_token = suffix[8]
    else:
        require(len(suffix) == 4 and
                suffix[0] == compile_record["object"] and
                suffix[1].startswith("-Wl,-map,") and
                suffix[2] == "-o",
                "D12 representation link command is not the exact frozen grammar")
        library = None
        map_token = suffix[1]
        output_token = suffix[3]
    map_path = _absolute_command_path(
        map_token[len("-Wl,-map,"):], ".map", "D12 link-map path drift")
    output_path = _absolute_command_path(
        output_token, "", "D12 binary output path drift")
    return {"library": library, "map": map_path, "output": output_path}


def _validate_d12_build_profile_commands(value):
    role_sources = (
        ("row_provider", True),
        ("representation_candidate", False),
    )
    build = B2.load_manifest()["qualification_platform"]["build"]
    all_paths = []
    profile_roots = []
    roots_by_profile = {}
    for profile_name, expected_flags in (
            ("release", build["common_release_compile_flags"]),
            ("tsan", build["thread_sanitizer_compile_flags"])):
        profile = value["build_profiles"][profile_name]
        require(len(profile["compile_commands"]) == len(role_sources) and
                len(profile["link_commands"]) == len(role_sources),
                "D12 profile must contain exact provider/representation commands")
        profile_artifact_roots = set()
        provider_install_root = None
        for index, (role, provider_role) in enumerate(role_sources):
            compile_record = _validate_d12_compile_command(
                profile["compile_commands"][index], expected_flags,
                RUNTIME_SOURCE_ENTRYPOINTS[role][0], provider_role)
            link_record = _validate_d12_link_command(
                profile["link_commands"][index], expected_flags,
                compile_record, provider_role)
            all_paths.extend(value for value in (
                compile_record["dependency"], compile_record["object"],
                compile_record["include"], link_record["library"],
                link_record["map"], link_record["output"])
                if value is not None)
            profile_artifact_roots.update(
                str(pathlib.PurePosixPath(path).parent) for path in (
                    compile_record["dependency"], compile_record["object"],
                    link_record["map"], link_record["output"]))
            if provider_role:
                provider_install_root = str(pathlib.PurePosixPath(
                    compile_record["include"]).parent)
        require(len(profile_artifact_roots) == 1 and
                provider_install_root is not None,
                "D12 profile build/proof artifact root drift")
        build_root = next(iter(profile_artifact_roots))
        roots_by_profile[profile_name] = {
            "build_root": build_root,
            "install_root": provider_install_root}
        profile_roots.extend((build_root, provider_install_root))
    require(len(all_paths) == len(set(all_paths)),
            "D12 Release/TSan build/output roots are not disjoint")
    require(all(not pathlib.PurePosixPath(left).is_relative_to(
                        pathlib.PurePosixPath(right)) and
                not pathlib.PurePosixPath(right).is_relative_to(
                        pathlib.PurePosixPath(left))
                for index, left in enumerate(profile_roots)
                for right in profile_roots[index + 1:]),
            "D12 Release/TSan build/install roots are not pairwise disjoint")
    return roots_by_profile


def validate_d12_envelope_contract(value, expected_head):
    validate_contract_value("anchored_row_representation_d12", value)
    digest_copy = copy.deepcopy(value)
    digest_copy["content_sha256"] = ZERO_SHA256
    require(value["content_sha256"] == sha256_bytes(jcs_bytes(digest_copy)),
            "D12 envelope content digest mismatch")
    require(value["git"] == {"head": expected_head,
                              "head_query_ok": True,
                              "worktree_clean": True},
            "D12 envelope exact-head/worktree mismatch")
    for binary in value["binaries"].values():
        require(binary["availability"]["state"] == "PRESENT" and
                binary["sha256"] == binary["availability"]["sha256"] and
                all(SHA256_RE.fullmatch(binary[field] or "") is not None
                    for field in ("compiler_command_sha256",
                                  "link_map_sha256",
                                  "dynamic_dependency_sha256")) and
                binary["source_inventory"],
                "D12 binary provenance incomplete")
    binary_sources = {
        "provider_release": "row_provider",
        "provider_tsan": "row_provider",
        "representation_release": "representation_candidate",
        "representation_tsan": "representation_candidate",
    }
    for binary_name, role in binary_sources.items():
        require(value["binaries"][binary_name]["source_inventory"] == [{
                    "path": path, "sha256": sha256_file(ROOT / path)}
                    for path in RUNTIME_SOURCE_PATHS[role]],
                "D12 binary source inventory is not the exact repository closure")
    build = B2.load_manifest()["qualification_platform"]["build"]
    for profile_name, expected_flags in (
            ("release", build["common_release_compile_flags"]),
            ("tsan", build["thread_sanitizer_compile_flags"])):
        profile = value["build_profiles"][profile_name]
        require(profile["compiler_path"] == build["compiler_path"] and
                profile["compiler_version"] == build["compiler_version"] and
                profile["flags"] == expected_flags and
                profile["sdk_path"] == build["macos_sdk_path"] and
                profile["sdk_version"] == build["macos_sdk_version"] and
                profile["cmake_path"] ==
                    build["opensubdiv"]["cmake"]["path"] and
                profile["cmake_version"] ==
                    build["opensubdiv"]["cmake"]["version"] and
                profile["make_path"] ==
                    build["opensubdiv"]["build_tool"]["path"] and
                profile["make_version"] ==
                    build["opensubdiv"]["build_tool"]["version"] and
                profile["compile_commands"] and profile["link_commands"],
                "D12 build profile differs from frozen exact authority")
    _validate_d12_build_profile_commands(value)
    for name, dependency in value["dependencies"].items():
        require(dependency["source_identity"] == {
                    "gmp": "6.3.0", "mpfr": "4.2.2",
                    "opensubdiv": "3.7.0"}[name],
                "D12 dependency source identity drift")
    platform = value["platform"]
    qualification_platform = B2.load_manifest()["qualification_platform"]
    require(platform["expected_fingerprint"] ==
            qualification_platform["fingerprint"] and
            platform["compiler_identity"] ==
            qualification_platform["build"]["compiler_version"],
            "D12 platform authority/compiler identity drift")
    exact_mismatches = sorted(
        key for key, expected in platform["expected_fingerprint"].items()
        if platform["observed_fingerprint"][key] != expected)
    require(platform["field_mismatches"] == exact_mismatches,
            "D12 fingerprint mismatch ledger is inconsistent")
    observations = platform["power_thermal_observations"]
    expected_boundaries = _expected_d12_boundary_identities()
    require(len(observations) == len(expected_boundaries) and
            platform["virtualization_observation"][
                "kern_hv_vmm_present"] ==
                platform["observed_fingerprint"]["kern_hv_vmm_present"],
            "D12 process-boundary platform observations are not frozen")
    probes = [_decode_d12_observation(item, identity, boundary)
              for item, (identity, boundary) in
              zip(observations, expected_boundaries)]
    qualified = (platform["github_hosted"] is False and
                 platform["expected_fingerprint"] ==
                    platform["observed_fingerprint"] and
                 platform["field_mismatches"] == [] and
                 platform["virtualization_observation"] == {
                    "kern_hv_vmm_present": 0,
                    "shared_host_evidence": False} and
                 all(probe["status"] == "ok" and
                     probe["finite"] is True and
                     probe["fingerprint_queries_ok"] is True and
                     probe["fingerprint"] ==
                        platform["expected_fingerprint"] and
                     probe["power"]["query_ok"] is True and
                     probe["power"]["value"] == B2.EXPECTED_POWER_VALUE and
                     probe["thermal"]["query_ok"] is True and
                     probe["thermal"]["value"] ==
                        B2.EXPECTED_THERMAL_VALUE and
                     probe["process_returncode"] == 0
                     for probe in probes))
    require((platform["platform_state"] == "QUALIFIED_PLATFORM") == qualified,
            "D12 platform state contradicts frozen observations")
    require(value["authority"] == frozen_authority_record(),
            "D12 envelope authority differs from frozen authority")
    workload = value["workload"]
    expected_references = (
        ("provider_serial_reference",
         "anchored-row-d12-v1/serial/provider-rows.b2rowv1", 693000),
        ("representation_serial_reference",
         "anchored-row-d12-v1/serial/representation-outputs.json", 5544000),
        ("process_observation_sidecar",
         "anchored-row-d12-v1/process/process-observations.json", 4189640))
    for member, path, count in expected_references:
        sidecar = workload[member]
        require(sidecar["availability"]["state"] == "PRESENT" and
                sidecar["relative_path"] == path and
                sidecar["record_count"] == count and
                sidecar["sha256"] == sidecar["availability"]["sha256"],
                "D12 serial/process reference binding mismatch")
    worker_paths = [sidecar["relative_path"]
                    for sidecar in workload["sidecars"]]
    require(worker_paths == sorted(set(worker_paths), key=jcs_bytes) and
            all(sidecar["availability"]["state"] == "PRESENT"
                for sidecar in workload["sidecars"]),
            "D12 worker sidecar inventory duplicate/reordered/non-present")
    combined = _criteria_contract_fixture()[:27] + value["criteria"]
    validate_criteria(combined)
    statuses = {item["status"] for item in value["criteria"]}
    require((platform["platform_state"] == "QUALIFIED_PLATFORM" and
             statuses <= {"PASS", "FAIL"}) or
            (platform["platform_state"] == "UNQUALIFIED_PLATFORM" and
             statuses == {"INCOMPLETE"}),
            "D12 platform/result status mismatch")
    context = value["serial_only_context"]
    require(context["failure_records_sha256"] ==
            sha256_bytes(jcs_bytes(context["failure_records"])),
            "D12 failure-record digest mismatch")
    return True


def execute_literal_mutation_suite():
    """Dispatch every immutable M01--M23 entry to an executable rejection.

    Object/criterion/ledger mutations reach their production validators;
    array/sidecar/record mutations reach canonical byte/count/hash bindings;
    and scientific/global mutations reach their owning derivation validators.
    No manifest entry is accepted by membership or changed-value comparison.
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
    object_exemplars = {
        name: _schema_exemplar(node, schema, "$mutation." + name)
        for name, node in objects.items()}
    criteria_fixture = _criteria_contract_fixture()
    ledger_fixture = _pre_result_ledger_contract_fixture()
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
            candidate = copy.deepcopy(object_exemplars[object_name])
            if operator == "M01":
                require(separator and member in candidate,
                        "M01 operand is not a required exemplar member")
                del candidate[member]
            elif operator == "M02":
                require(not separator, "M02 operand must name one object")
                candidate["__mutation_unknown__"] = True
            else:
                require(separator and member in candidate,
                        "M03 operand is not a required exemplar member")
                original = candidate[member]
                for wrong in (None, {}, [], "__wrong_type__", 0, True):
                    if wrong == original and type(wrong) is type(original):
                        continue
                    candidate[member] = wrong
                    try:
                        validate_schema_instance(
                            candidate, node, schema,
                            "$mutation.{}".format(object_name))
                    except QualificationError:
                        did_reject = True
                        break
            if operator != "M03":
                try:
                    validate_schema_instance(
                        candidate, node, schema,
                        "$mutation.{}".format(object_name))
                except QualificationError:
                    did_reject = True
        elif operator in {"M04", "M05", "M06", "M07"}:
            node = arrays[operand]
            baseline = _schema_exemplar(node, schema,
                                        "$mutation.array." + operand)
            if len(baseline) < 3:
                item_schema = node.get("items", {})
                sample = (_schema_exemplar(item_schema, schema,
                                            "$mutation.array.item")
                          if item_schema is not False else None)
                while len(baseline) < 3:
                    carrier = copy.deepcopy(sample)
                    if carrier in baseline:
                        carrier = {"anchored_array_path": operand,
                                   "representative_ordinal": len(baseline)}
                    baseline.append(carrier)
            seen_carriers = set()
            for carrier_index, carrier in enumerate(baseline):
                encoded_carrier = jcs_bytes(carrier)
                if encoded_carrier in seen_carriers:
                    baseline[carrier_index] = {
                        "anchored_array_path": operand,
                        "representative_ordinal": carrier_index}
                    encoded_carrier = jcs_bytes(baseline[carrier_index])
                seen_carriers.add(encoded_carrier)
            baseline_raw = jcs_bytes(baseline)
            descriptor = {
                "availability": availability(
                    "PRESENT", sha256_bytes(baseline_raw)),
                "byte_length": len(baseline_raw),
                "record_count": len(baseline),
                "sha256": sha256_bytes(baseline_raw)}
            validate_bound_jcs_array(baseline_raw, descriptor)
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
            try:
                validate_bound_jcs_array(jcs_bytes(observed), descriptor)
            except QualificationError:
                did_reject = True
        elif operator == "M08":
            ordinal, criterion_id, count = operand.split(":", 2)
            index = int(ordinal)
            require(CRITERION_IDS[index] == criterion_id and
                    EXPECTED_CELL_COUNTS[criterion_id] == int(count),
                    "M08 operand differs from frozen criterion slot")
            candidate = copy.deepcopy(criteria_fixture)
            if mutation == "wrong-id":
                candidate[index]["criterion_id"] += "_mutation"
            elif mutation == "wrong-ordinal":
                other = (index + 1) % len(candidate)
                candidate[index], candidate[other] = (
                    candidate[other], candidate[index])
            elif mutation == "count-minus-one":
                candidate[index]["expected_cell_count"] -= 1
            else:
                candidate[index]["expected_cell_count"] += 1
            try:
                validate_criteria(candidate)
            except QualificationError:
                did_reject = True
        elif operator == "M09":
            ordinal, criterion_id, _ = operand.split(":", 2)
            index = int(ordinal)
            require(CRITERION_IDS[index] == criterion_id,
                    "M09 operand differs from frozen criterion slot")
            candidate = copy.deepcopy(criteria_fixture)
            item = candidate[index]
            if mutation == "expectation":
                item["expectation"] += "_mutation"
            elif mutation == "applicability":
                item["applicability"] = "invented"
            elif mutation == "target":
                item["target"] = {} if item["target"] is None else None
            elif mutation == "allowed-status":
                item["status"] = "INVENTED"
            else:
                del item["witness"]
            try:
                validate_schema_instance(
                    candidate, schema["properties"]["criteria"], schema,
                    "$mutation.criteria")
                validate_criteria(candidate)
            except QualificationError:
                did_reject = True
        elif operator == "M10":
            _, criterion_id, partition = operand.split(":", 2)
            candidate = copy.deepcopy(ledger_fixture)
            index = next(index for index, item in enumerate(candidate)
                         if item["criterion_id"] == criterion_id and
                         item["partition"] == partition)
            item = candidate[index]
            if mutation == "wrong-id":
                item["criterion_id"] += "_mutation"
            elif mutation == "wrong-partition":
                item["partition"] += "_mutation"
            elif mutation == "wrong-count":
                item["observed_count"] += 1
            else:
                item["key_ledger_sha256"] = "b" * 64
            try:
                _validate_pre_result_ledgers(candidate)
            except QualificationError:
                did_reject = True
        elif operator == "M11":
            empty_digest = sha256_bytes(b"[]")
            descriptor = {
                "availability": availability("PRESENT", empty_digest),
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
                    validate_bound_jcs_array(
                        b"[]\n", {"availability": availability(
                            "PRESENT", empty_digest), "byte_length": 2,
                            "record_count": 0, "sha256": empty_digest})
                except QualificationError:
                    did_reject = True
            if mutation != "trailing-byte":
                try:
                    validate_schema_instance(
                        candidate, schema["$defs"][
                            "result_ledger_artifact"], schema,
                        "$mutation.result_sidecar")
                    validate_bound_jcs_array(
                        b"[]", {"availability": candidate["availability"],
                                "byte_length": candidate["byte_length"],
                                "record_count": candidate["record_count"],
                                "sha256": candidate["availability"][
                                    "sha256"]})
                except (QualificationError, KeyError):
                    did_reject = True
        elif operator == "M12":
            _, criterion_id, _ = operand.split(":", 2)
            first = _valid_result_record_for_mutation(criterion_id)
            secondary_criterion = (
                "constant_field_bits" if criterion_id ==
                "bindings_and_independence" else criterion_id)
            second = _valid_result_record_for_mutation(
                secondary_criterion,
                variant=(0 if criterion_id ==
                         "bindings_and_independence" else 1))
            baseline_records = sorted([first, second],
                                      key=lambda item: jcs_bytes(item[0]))
            candidate_records = copy.deepcopy(baseline_records)
            record_index = next(index for index, item in
                                enumerate(candidate_records)
                                if item[0] == first[0])
            if mutation == "missing":
                candidate_records[record_index].pop()
            elif mutation == "extra":
                candidate_records[record_index].append(None)
            elif mutation == "duplicate":
                candidate_records[1] = copy.deepcopy(candidate_records[0])
            elif mutation == "reorder":
                candidate_records.reverse()
            else:
                field = {"key": 0, "outcome": 1, "exact-value": 2,
                         "target": 3, "reason": 4}[mutation]
                candidate_records[record_index][field] = (
                    ["z"] if field == 0 else "INVENTED" if field == 1 else
                    {"kind": "mutation_v1"} if field in (2, 3) else
                    "MUTATION")
            try:
                if mutation in {"duplicate", "reorder"}:
                    canonical_result_ledger(candidate_records)
                else:
                    validate_contract_result_record(
                        criterion_id, candidate_records[record_index],
                        defer_basis_group=(criterion_id ==
                                           "binary64_basis_probe_diagnostic"))
            except QualificationError:
                did_reject = True
        elif operator == "M13":
            record = [["cell"], "PASS", None, None, None]
            tied_record = [["other"], "PASS", None, None, None]
            maximum = _absolute_rational_descriptor(Fraction(1, 4))
            encoded_records = [jcs_bytes(record), jcs_bytes(tied_record)]
            root, siblings = result_merkle_commitment(
                encoded_records, witness_index=0)
            witness = {"cell_key": record[0], "result_record": record,
                       "leaf_index": 0, "merkle_siblings": siblings,
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
                candidate["cell_key"] = tied_record[0]
                candidate["result_record"] = tied_record
                _, candidate["merkle_siblings"] = result_merkle_commitment(
                    encoded_records, witness_index=1)
            try:
                validate_maximum_witness_binding(
                    candidate, maximum, record, encoded_records[0], 0,
                    siblings, root, 2)
            except QualificationError:
                did_reject = True
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
            try:
                validate_first_failure_binding(
                    [[key, outcome, None, None,
                      None if outcome == "PASS" else "FAILURE"]
                     for key, outcome in zip(keys, outcomes)], candidate)
            except QualificationError:
                did_reject = True
        elif operator == "M16":
            node = authorities[operand]
            try:
                validate_schema_instance("__mutation__", node, schema,
                                         "$mutation." + operand)
            except QualificationError:
                did_reject = True
        elif operator == "M18":
            base_key = _criterion_mutation_key(
                "binary64_basis_probe_diagnostic")
            zero_signed = {"kind": "signed_dyadic_v1", "sign": 0,
                           "numerator_hex": "0",
                           "denominator_power": 1074}
            zero_absolute = {"kind": "absolute_dyadic_v1",
                             "numerator_hex": "0",
                             "denominator_power": 1074}
            records = []
            for relabel in RELABELS:
                key = copy.deepcopy(base_key)
                key[9] = relabel
                records.append([key, "PASS", {
                    "kind": "basis_value_v1",
                    "emitted_basis_bits": "0000000000000000",
                    "exact_effective": copy.deepcopy(zero_signed),
                    "source_error": copy.deepcopy(zero_absolute),
                    "group_l1": copy.deepcopy(zero_absolute)},
                    absolute_rational_target("2000000"), None])
            by_relabel = {record[0][9]: record for record in records}
            if mutation in {"identity-only-failure", "reverse-only-failure",
                            "rotate-only-failure"}:
                record = by_relabel[{
                    "identity-only-failure": "identity",
                    "reverse-only-failure": "rank_reverse",
                    "rotate-only-failure": "rank_rotate_1"}[mutation]]
                record[2]["source_error"] = {
                    "kind": "absolute_dyadic_v1", "numerator_hex": "1",
                    "denominator_power": 1074}
                record[2]["group_l1"] = {
                    "kind": "absolute_dyadic_v1", "numerator_hex": "1",
                    "denominator_power": 1074}
            elif mutation == "distributed-per-source-error":
                record = by_relabel["identity"]
                record[2]["source_error"] = {
                    "kind": "absolute_dyadic_v1", "numerator_hex": "1",
                    "denominator_power": 1074}
            elif mutation == "signed-coefficient":
                record = by_relabel["identity"]
                record[2]["exact_effective"] = {
                    "kind": "signed_dyadic_v1", "sign": 1,
                    "numerator_hex": "1", "denominator_power": 1074}
            elif mutation == "wrong-inverse-map":
                record = by_relabel["rank_reverse"]
                record[2]["emitted_basis_bits"] = "3ff0000000000000"
                record[2]["exact_effective"] = {
                    "kind": "signed_dyadic_v1", "sign": 1,
                    "numerator_hex": format(1 << 1074, "x"),
                    "denominator_power": 1074}
            else:
                record = by_relabel["identity"]
                record[2]["group_l1"] = {
                    "kind": "absolute_dyadic_v1", "numerator_hex": "1",
                    "denominator_power": 1074}
            try:
                canonical_result_ledger(
                    sorted(records, key=lambda item: jcs_bytes(item[0])),
                    criterion_id=
                    "binary64_basis_probe_diagnostic")
            except QualificationError:
                did_reject = True
        elif operator == "M17":
            if mutation.startswith("propagation-"):
                verifier = OracleUncoveredPropagationVerifier()
                reasons = ("EIGENBASIS_CERTIFICATION_FAILED",
                           "UNIFORM_CROSSCHECK_FAILED")
                oracle_keys = []
                for face_id in (0, 1):
                    dependent_key = _criterion_mutation_key(
                        "exact_effective_d10_coeff")
                    dependent_key[3] = face_id
                    oracle_keys.append(oracle_request_key_for_dependent_key(
                        "exact_effective_d10_coeff", dependent_key))
                partition_drift = (mutation ==
                                   "propagation-covered-partition-drift")
                for index, (oracle_key, reason) in enumerate(zip(
                        oracle_keys, reasons)):
                    if partition_drift and index == 0:
                        record = _valid_oracle_covered_record(oracle_key)
                    else:
                        record = [oracle_key, "UNCOVERED", None, None,
                                  reason]
                    verifier.add("oracle_coverage_and_crosscheck", record)
                for criterion_id in ORACLE_DEPENDENT_CRITERIA:
                    keys = []
                    axes = (("x", "y", "z") if criterion_id in
                            OracleUncoveredPropagationVerifier.AXIS_CRITERIA
                            else (None,))
                    for face_id, reason in zip((0, 1), reasons):
                        for axis in axes:
                            key = _criterion_mutation_key(criterion_id)
                            key[3] = face_id
                            key[11] = axis
                            keys.append([key, reason])
                    if partition_drift:
                        keys = [item for item in keys if item[0][3] != 0]
                    if (mutation == "propagation-gap" and criterion_id ==
                            "exact_effective_d10_coeff"):
                        keys.pop()
                    elif (mutation == "propagation-extra" and criterion_id ==
                          "exact_effective_d10_coeff"):
                        extra = copy.deepcopy(keys[-1])
                        extra[0][3] = 2
                        keys.append(extra)
                    elif (mutation == "propagation-wrong-reason" and
                          criterion_id == "exact_effective_d10_coeff"):
                        keys[-1][1] = reasons[0]
                    elif (mutation == "propagation-axis-gap" and criterion_id ==
                          "exact_effective_d10_geometry"):
                        keys.pop()
                    for key, reason in sorted(
                            keys, key=lambda item: jcs_bytes(item[0])):
                        target = absolute_rational_target(
                            _row_target_denominator(criterion_id, key))
                        verifier.add(criterion_id, [
                            key, "UNCOVERED", None, target, reason])
                try:
                    if partition_drift:
                        empty_digest = sha256_bytes(b"[]")
                        request_digest = generic_key_ledger_sha256(oracle_keys)
                        partitions = {
                            "covered": {
                                "availability": availability(
                                    "PRESENT", empty_digest),
                                "observed_count": 0,
                                "key_ledger_sha256": empty_digest,
                                "omission_blocker": None},
                            "uncovered": {
                                "availability": availability(
                                    "PRESENT", request_digest),
                                "observed_count": 2,
                                "key_ledger_sha256": request_digest,
                                "omission_blocker": None}}
                        statuses = [{"criterion_id": criterion_id,
                                     "status": "UNCOVERED"}
                                    for criterion_id in (
                                        "oracle_coverage_and_crosscheck",
                                    ) + tuple(
                                        item for item in CRITERION_IDS
                                        if item in
                                        ORACLE_DEPENDENT_CRITERIA)]
                        verifier.finish(statuses, partitions)
                    else:
                        verifier.finish()
                except QualificationError:
                    did_reject = True
                require(did_reject, "mutation was not rejected: " + entry)
                rejected.append(entry)
                continue
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
            try:
                validate_oracle_partition(
                    request, covered, uncovered, outcome, exact_value,
                    reason)
            except QualificationError:
                did_reject = True
        elif operator == "M19":
            maximum = {
                "kind": "absolute_dyadic_v1",
                "numerator_hex": RAW_D9A_FROZEN_MAXIMUM_NUMERATOR_HEX,
                "denominator_power": 1074}
            records = []
            for index in range(196):
                state = ("FAIL" if index <
                         RAW_D9A_FROZEN_FAILING_CASE_COUNT else "PASS")
                value = {
                    "kind": "raw_d9a_value_v1",
                    "case_identity": ["content-{:03d}".format(index), 2,
                                      "cache_disabled"],
                    "raw_invariant_state": state,
                    "maximum_row_sum_residual":
                        copy.deepcopy(maximum if index == 0 else
                                      {"kind": "absolute_dyadic_v1",
                                       "numerator_hex": "0",
                                       "denominator_power": 1074}),
                    "failing_row_count": 1 if state == "FAIL" else 0,
                    "canonical_raw_rows_sha256": "a" * 64}
                records.append([["raw_bfr_d9a_reproduction",
                                 "content-{:03d}".format(index), 2,
                                 "cache_disabled"], "PASS", value,
                                copy.deepcopy(value), None])
            validate_raw_d9a_frozen_global(
                records, maximum, RAW_D9A_FROZEN_MAXIMUM_BITS)
            baseline_raw = jcs_bytes(records)
            descriptor = {
                "availability": availability(
                    "PRESENT", sha256_bytes(baseline_raw)),
                "byte_length": len(baseline_raw), "record_count": 196,
                "sha256": sha256_bytes(baseline_raw)}
            candidate_records = copy.deepcopy(records)
            candidate_maximum = copy.deepcopy(maximum)
            candidate_bits = RAW_D9A_FROZEN_MAXIMUM_BITS
            if mutation in {"case-state", "124-count"}:
                candidate_records[0][2]["raw_invariant_state"] = "PASS"
            elif mutation == "case-digest":
                candidate_records[0][2]["canonical_raw_rows_sha256"] = \
                    "b" * 64
            elif mutation == "failing-row-count":
                candidate_records[0][2]["failing_row_count"] = 0
            elif mutation == "exact-numerator":
                candidate_maximum["numerator_hex"] = "1"
            elif mutation == "maximum-bits":
                candidate_bits = "0000000000000000"
            else:
                candidate_records[0][2]["maximum_row_sum_residual"] = {
                    "kind": "absolute_dyadic_v1", "numerator_hex": "1",
                    "denominator_power": 1074}
            try:
                validate_raw_d9a_frozen_global(
                    candidate_records, candidate_maximum, candidate_bits)
                validate_bound_jcs_array(
                    jcs_bytes(candidate_records), descriptor)
            except QualificationError:
                did_reject = True
        elif operator == "M20":
            envelope = _d12_envelope_contract_fixture()
            candidate = copy.deepcopy(envelope)
            raw_override = None
            if mutation == "malformed":
                raw_override = b"{"
            elif mutation == "duplicate-key":
                raw_override = b'{"schema_id":"a","schema_id":"b"}'
            elif mutation == "content-hash":
                candidate["content_sha256"] = "a" * 64
            elif mutation == "cross-head":
                candidate["git"]["head"] = "b" * 40
            elif mutation == "dirty":
                candidate["git"]["worktree_clean"] = False
            elif mutation == "old-B2":
                candidate["authority"]["manifest_file_sha256"] = "b" * 64
            elif mutation == "boolean-only":
                candidate = {"representation_work": True}
            elif mutation == "missing-provenance":
                candidate["binaries"]["provider_release"][
                    "source_inventory"] = []
            elif mutation == "fingerprint":
                candidate["platform"]["field_mismatches"] = []
            elif mutation == "hosted-as-qualified":
                candidate["platform"]["platform_state"] = \
                    "QUALIFIED_PLATFORM"
            elif mutation == "workload":
                pass
            elif mutation == "reference-digest":
                candidate["workload"]["provider_serial_reference"][
                    "sha256"] = "f" * 64
                candidate["workload"]["provider_serial_reference"][
                    "availability"]["sha256"] = "f" * 64
            elif mutation == "instrumentation":
                candidate["build_profiles"]["tsan"]["flags"] = ["-O1"]
            elif mutation == "operational-gap":
                pass
            else:
                candidate["criteria"][0]["observed_cell_count"] -= 1
            if (raw_override is None and mutation != "content-hash" and
                    isinstance(candidate, dict) and
                    "content_sha256" in candidate):
                candidate["content_sha256"] = ZERO_SHA256
                candidate["content_sha256"] = sha256_bytes(
                    jcs_bytes(candidate))
            try:
                if raw_override is not None:
                    candidate = strict_json_bytes(raw_override)
                validate_d12_envelope_contract(candidate, "a" * 40)
                if mutation == "workload":
                    key = _criterion_mutation_key(
                        "d12_cache_disabled_concurrency")
                    provider_path, representation_path = \
                        D12WorkerInventoryVerifier._paths_for_key(key)
                    provider_descriptor = {
                        "availability": availability("PRESENT", "a" * 64),
                        "relative_path": provider_path, "byte_length": 1,
                        "record_count": 1, "sha256": "a" * 64}
                    representation_descriptor = {
                        "availability": availability("PRESENT", "b" * 64),
                        "relative_path": representation_path,
                        "byte_length": 1, "record_count": 1,
                        "sha256": "b" * 64}
                    expected = {
                        provider_path: (1, "a" * 64),
                        representation_path: (1, "b" * 64)}
                    inventory = D12WorkerInventoryVerifier.__new__(
                        D12WorkerInventoryVerifier)
                    inventory.expected_paths = frozenset(expected)
                    inventory.descriptors = D12WorkerInventoryVerifier.\
                        _bind_descriptor_inventory(
                            expected, [provider_descriptor])
                    inventory.require_result_sidecars(key, {
                        "provider_sidecar": provider_descriptor,
                        "representation_sidecar":
                            representation_descriptor})
                elif mutation == "operational-gap":
                    validator = D12CrossRecordValidator()
                    key = _criterion_mutation_key(
                        "d12_instrumented_tsan")
                    key[5] = 0
                    key[6] = 0
                    key[12] = "thread_result"
                    key[13] = "row_digest"
                    validator.add("d12_instrumented_tsan", [
                        key, "FAIL", None,
                        {"kind": "d12_output_reference_target_v1",
                         "provider_expected_sha256": "b" * 64,
                         "representation_expected_sha256": "c" * 64},
                        "THREADED_CACHE_RACE"])
                    validator.finish()
                elif mutation == "reference-digest":
                    key = _criterion_mutation_key(
                        "d12_instrumented_tsan")
                    key[5] = 0
                    key[6] = 0
                    key[12] = "thread_result"
                    key[13] = "row_digest"
                    inventory = D12WorkerInventoryVerifier.__new__(
                        D12WorkerInventoryVerifier)
                    inventory.case_references = {
                        (key[0], key[1]): {
                            "provider": "b" * 64,
                            "representation": "c" * 64}}
                    valid_target = {
                        "kind": "d12_output_reference_target_v1",
                        "provider_expected_sha256": envelope["workload"][
                            "provider_serial_reference"]["sha256"],
                        "representation_expected_sha256": envelope["workload"][
                            "representation_serial_reference"]["sha256"]}
                    inventory.require_target(key, valid_target)
                    mutated_target = copy.deepcopy(valid_target)
                    mutated_target["provider_expected_sha256"] = candidate[
                        "workload"]["provider_serial_reference"]["sha256"]
                    inventory.require_target(key, mutated_target)
            except (QualificationError, UnicodeDecodeError,
                    json.JSONDecodeError):
                did_reject = True
        elif operator == "M22":
            race_key = _criterion_mutation_key(
                "d12_instrumented_tsan")
            race_key[5] = 0
            race_key[6] = 0
            race_key[12] = "thread_result"
            race_key[13] = "row_digest"
            statuses = [
                {"criterion_id": criterion_id,
                 "status": ("FAIL" if criterion_id ==
                            "d12_instrumented_tsan" else "PASS")}
                for criterion_id in CRITERION_IDS]
            failures = [[race_key, "THREADED_CACHE_RACE"]]
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
                "failure_records_sha256": sha256_bytes(
                    jcs_bytes(failures))}
            if mutation == "missing-tuple":
                context["tuple_count"] -= 1
            elif mutation == "cache-disabled-failure":
                context["cache_disabled_concurrency_pass"] = False
            elif mutation == "output-mismatch":
                context["failure_records"][0][1] = \
                    "THREADED_CACHE_OUTPUT_MISMATCH"
            elif mutation == "nonrace-failure":
                statuses[3]["status"] = "FAIL"
            elif mutation == "incomplete-evidence":
                context["all_tsan_cell_count"] -= 1
            if mutation not in {"missing-tuple", "cache-disabled-failure",
                                "nonrace-failure",
                                "exact-race-only-eligibility"}:
                context["failure_records_sha256"] = sha256_bytes(
                    jcs_bytes(context["failure_records"]))
            eligible = calculate_serial_only_disposition(
                statuses, context)["serial_only_qualification_eligible"]
            did_reject = (eligible if mutation ==
                          "exact-race-only-eligibility" else not eligible)
        elif operator == "M21":
            statuses = [{"criterion_id": criterion_id, "status": "PASS"}
                        for criterion_id in CRITERION_IDS]
            if mutation == "all-PASS":
                verdict = calculate_verdict(statuses)
                did_reject = (
                    verdict["status"] == "PASS" and
                    verdict["qualification_decided"] is False and
                    verdict["production_authorized"] is False)
            elif mutation == "FAIL-precedence":
                statuses[1]["status"] = "INCOMPLETE"
                statuses[20]["status"] = "FAIL"
                verdict = calculate_verdict(statuses)
                did_reject = (verdict["status"] == "FAIL" and
                              verdict["first_decisive_criterion"] ==
                              statuses[20]["criterion_id"])
            elif mutation == "ordered-INCOMPLETE":
                statuses[2]["status"] = "INCOMPLETE"
                statuses[27]["status"] = "INCOMPLETE"
                verdict = calculate_verdict(statuses)
                did_reject = (verdict["status"] == "INCOMPLETE" and
                              verdict["first_decisive_criterion"] ==
                              statuses[2]["criterion_id"])
            elif mutation == "ordered-UNCOVERED":
                statuses[10]["status"] = "UNCOVERED"
                statuses[27]["status"] = "INCOMPLETE"
                verdict = calculate_verdict(statuses)
                did_reject = (verdict["status"] == "INCOMPLETE" and
                              verdict["first_decisive_criterion"] ==
                              statuses[10]["criterion_id"])
            elif mutation in {"legal-group-status", "earlier-blocker"}:
                candidate = _criteria_contract_fixture()
                try:
                    validate_criteria(candidate)
                    did_reject = True
                except QualificationError:
                    did_reject = False
            elif mutation == "illegal-group-status":
                candidate = _criteria_contract_fixture()
                candidate[10]["status"] = "FAIL"
                try:
                    validate_criteria(candidate)
                except QualificationError:
                    did_reject = True
            elif mutation == "later-blocker":
                candidate = _criteria_contract_fixture()
                candidate[3]["omission_blocker"] = CRITERION_IDS[4]
                try:
                    validate_criteria(candidate)
                except QualificationError:
                    did_reject = True
            else:
                raise QualificationError("unknown M21 mutation")
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
            raise QualificationError(
                "mutation operator lacks executable handler: " + operator)
        require(did_reject, "mutation was not rejected: " + entry)
        rejected.append(entry)
    require(len(rejected) == 3506 and tuple(rejected) ==
            entries and handlers == {
                "M{:02d}".format(index) for index in range(1, 24)},
            "mutation dispatcher coverage drift: rejected={} entries={} "
            "handlers={}".format(len(rejected), len(entries),
                                 sorted(handlers)))
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
    require(sha256_bytes(raw) == case["complete_json_sha256"] and
            isinstance(report, dict) and isinstance(report.get("rows"), list),
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


def regular_coefficient_interval_value(row, observation, analytic_row,
                                       patch):
    require(observation["source_ids"] == row["source_ids"] ==
            sorted(patch) and
            all(item["denominator_power"] == 1074
                for item in observation["values"]),
            "regular exact observation support")
    analytic_by_source = dict(zip(patch, analytic_row))
    intervals = [_interval_descriptor(
        analytic_by_source[source_id], analytic_by_source[source_id])
        for source_id in row["source_ids"]]
    observed = copy.deepcopy(observation["values"])
    errors = [_interval_error_upper(
        _signed_dyadic_fraction(value), interval)
        for value, interval in zip(observed, intervals)]
    maximum_index = max(range(len(errors)), key=lambda index: errors[index])
    result = {
        "kind": "coefficient_interval_vector_v1",
        "source_union_ids": list(row["source_ids"]),
        "observed": observed,
        "analytic_intervals": intervals,
        "absolute_error_uppers": [
            _absolute_rational_descriptor(error) for error in errors],
        "maximum_error_upper": _absolute_rational_descriptor(
            errors[maximum_index]),
        "first_maximum_source_id": row["source_ids"][maximum_index],
    }
    validate_contract_value("coefficient_interval_vector_v1", result)
    return result


def regular_emitted_interval_value(observation, analytic_value):
    interval = _interval_descriptor(analytic_value, analytic_value)
    error = _interval_error_upper(Fraction.from_float(
        binary64_from_bits_hex(observation["observed_bits"])), interval)
    result = {
        "kind": "emitted_interval_scalar_v1",
        "observed_bits": observation["observed_bits"],
        "analytic_interval": interval,
        "absolute_error_upper": _absolute_rational_descriptor(error),
    }
    validate_contract_value("emitted_interval_scalar_v1", result)
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


def provider_row_sha256(row):
    """Return the canonical B2ROWV1 digest for one authenticated row."""
    encoded = bytearray(b"B2ROWV1")
    encoded.extend(struct.pack("<i", row["face_row"]))
    sample = row["sample_id"].encode("utf-8")
    encoded.extend(struct.pack("<I", len(sample)))
    encoded.extend(sample)
    encoded.extend(struct.pack("<I", ROW_ORDER.index(row["row_kind"])))
    encoded.extend(struct.pack("<I", len(row["source_ids"])))
    require(len(row["source_ids"]) == len(row["coefficients"]),
            "provider row digest cardinality")
    for source_id, coefficient in zip(row["source_ids"],
                                      row["coefficients"]):
        encoded.extend(struct.pack("<i", source_id))
        encoded.extend(struct.pack("<d", coefficient))
    return sha256_bytes(bytes(encoded))


def structure_result_value(row, anchor_name, anchor_source, observation):
    """Derive criterion-03 exact truth from provider and raw candidate bytes."""
    require(observation["canonical_source_ids"] == row["source_ids"] and
            observation["provider_coefficient_bits"] == [
                binary64_bits_hex(value) for value in row["coefficients"]],
            "candidate structure observation differs from provider row")
    effective = copy.deepcopy(observation["effective_coefficients"])
    require(all(item["denominator_power"] == 1074 for item in effective),
            "candidate structure dyadic denominator")
    observed_numerators = [
        item["sign"] * int(item["numerator_hex"], 16)
        for item in effective]
    expected_sum = (1 << 1074) if row["row_kind"] == "position" else 0
    value = {
        "kind": "structure_present_v1",
        "anchor_id": anchor_name,
        "anchor_present": True,
        "canonical_source_ids": list(row["source_ids"]),
        "provider_coefficient_bits": [
            binary64_bits_hex(item) for item in row["coefficients"]],
        "provider_row_sha256": provider_row_sha256(row),
        "effective_coefficients": effective,
        "observed_sum": _signed_dyadic_descriptor(
            sum(observed_numerators)),
        "expected_sum": _signed_dyadic_descriptor(expected_sum),
        "source_count": len(row["source_ids"]),
    }
    validate_contract_value("structure_present_v1", value)
    # The provider source/bit identity above is a process-boundary check;
    # this exact vector comparison owns the scientific PASS/FAIL decision.
    expected = effective_numerators(row, anchor_source)
    matches = (observed_numerators == [
        expected[source_id] for source_id in row["source_ids"]])
    return value, matches


def relabel_result_value(row, anchor_source, observation):
    """Derive criterion-05 exact vector comparison and L1."""
    require(observation["source_ids"] == row["source_ids"] and
            all(item["denominator_power"] == 1074
                for item in observation["values"]),
            "candidate relabel observation differs from provider support")
    expected_by_source = effective_numerators(row, anchor_source)
    expected = [_signed_dyadic_descriptor(
        expected_by_source[source_id]) for source_id in row["source_ids"]]
    observed = copy.deepcopy(observation["values"])
    observed_numerators = [
        item["sign"] * int(item["numerator_hex"], 16)
        for item in observed]
    expected_numerators = [expected_by_source[source_id]
                           for source_id in row["source_ids"]]
    errors = [abs(left - right) for left, right in
              zip(observed_numerators, expected_numerators)]
    value = {
        "kind": "coefficient_vector_comparison_v1",
        "source_ids": list(row["source_ids"]),
        "observed": observed,
        "expected": expected,
        "absolute_errors": [_absolute_dyadic_descriptor(error)
                            for error in errors],
        "l1": _absolute_dyadic_descriptor(sum(errors)),
    }
    validate_contract_value("coefficient_vector_comparison_v1", value)
    return value, not any(errors)


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


class _CategoricalResultAccumulator:
    """Persist one categorical criterion and derive its aggregate."""

    def __init__(self, output_root, criterion_id):
        require(criterion_id in RESULT_CONTRACT.CRITERION_BY_ID and
                RESULT_CONTRACT.CRITERION_BY_ID[criterion_id][
                    "maximum_field"] is None,
                "categorical result accumulator criterion")
        self.criterion_id = criterion_id
        self.writer = StreamingResultLedgerArtifact(output_root, criterion_id)
        self.failure_count = 0
        self.incomplete_count = 0
        self.first_failure = None

    def add(self, record):
        if record[1] == "FAIL":
            self.failure_count += 1
            if self.first_failure is None:
                self.first_failure = copy.deepcopy(record[0])
        elif record[1] == "INCOMPLETE":
            self.incomplete_count += 1
        self.writer.add(record)

    def finish(self):
        expected = EXPECTED_CELL_COUNTS[self.criterion_id]
        require(self.writer.count == expected,
                "{} result cardinality".format(self.criterion_id))
        commitment, artifact = self.writer.finish()
        return {
            "digest": commitment["key_ledger_sha256"],
            "result_digest": commitment["result_ledger_sha256"],
            "result_merkle_root": commitment[
                "result_merkle_root_sha256"],
            "result_artifact": artifact,
            "observed_count": expected,
            "failure_count": self.failure_count,
            "first_failing_key": self.first_failure,
            "maximum": None, "witness": None,
            "status": ("FAIL" if self.failure_count else
                       "INCOMPLETE" if self.incomplete_count else "PASS"),
            "target": report_criterion_target(self.criterion_id),
            "expectation": RESULT_CONTRACT.CRITERION_BY_ID[
                self.criterion_id]["expectation"],
        }


def _iter_preoracle_observation_cells(checkpoint, artifact_root, manifest,
                                      criterion_id):
    suffixes = _validate_suffix_definitions()[criterion_id]
    topology = fixture_topology(manifest)
    for case, row in iter_ordered_bfr_rows(checkpoint, artifact_root):
        _, faces = topology[case["content_identity_key"]]
        face = faces[row["face_row"]]
        prefix = scientific_base_prefix(case, row)
        for suffix, dimensions in suffixes:
            key = strict_json_bytes(prefix + suffix)
            _, anchor_name, _, _ = dimensions
            anchor_source = face[ANCHORS.index(anchor_name)]
            require(anchor_source in row["source_ids"],
                    "provider row omits oriented-face anchor")
            yield row, key, anchor_source


def _preoracle_observation_request_lines(checkpoint, artifact_root, manifest):
    topology = fixture_topology(manifest)
    for case, row in iter_ordered_bfr_rows(checkpoint, artifact_root):
        vertex_count, faces = topology[case["content_identity_key"]]
        yield candidate_audit_line(
            row, vertex_count, faces[row["face_row"]])


def execute_observation_preoracle_criteria(candidate_binary, checkpoint,
                                           artifact_root, manifest,
                                           output_root):
    """Execute criteria 03--05 through raw framed candidate observations."""
    result = {}
    zero_target = {"kind": "exact_zero_l1_target_v1",
                   "numerator": "0", "denominator": "1"}
    for criterion_id in (
            "representation_structure", "constant_field_bits",
            "relabel_exact_effective_coefficients"):
        accumulator = _CategoricalResultAccumulator(
            output_root, criterion_id)
        observations = iter_candidate_observations(
            candidate_binary, criterion_id,
            _preoracle_observation_request_lines(
                checkpoint, artifact_root, manifest),
            EXPECTED_CELL_COUNTS[criterion_id])
        for (row, key, anchor_source), observation in zip(
                _iter_preoracle_observation_cells(
                    checkpoint, artifact_root, manifest, criterion_id),
                observations):
            if criterion_id == "representation_structure":
                value, passed = structure_result_value(
                    row, key[8], anchor_source, observation)
                target = None
                reason = None if passed else \
                    "REPRESENTATION_STRUCTURE_MISMATCH"
            elif criterion_id == "constant_field_bits":
                expected_bits = _expected_constant_bits(key)
                value = {"kind": "binary64_pair_v1",
                         "observed_bits": observation["observed_bits"],
                         "expected_bits": expected_bits}
                validate_contract_value("binary64_pair_v1", value)
                passed = observation["observed_bits"] == expected_bits
                target = None
                reason = None if passed else \
                    "CONSTANT_FIELD_BITS_MISMATCH"
            else:
                value, passed = relabel_result_value(
                    row, anchor_source, observation)
                target = zero_target
                reason = None if passed else "RELABEL_EXACT_MISMATCH"
            accumulator.add([
                key, "PASS" if passed else "FAIL", value,
                copy.deepcopy(target), reason])
        exhausted = object()
        require(next(observations, exhausted) is exhausted,
                "candidate preoracle observation overflow")
        result[criterion_id] = accumulator.finish()
    return result


def _iter_regular_observation_rows(checkpoint, artifact_root, manifest):
    analytic_rows = regular_sample_rows(manifest)
    inventory = regular_patch_inventory(manifest)
    for case in ordered_bfr_cases(checkpoint):
        if case["approximation_level"] not in (7, 8):
            continue
        fixture = inventory[case["content_identity_key"]]
        for row in ordered_case_rows(_artifact_report(artifact_root, case)):
            patch = fixture["patches"].get(row["face_row"])
            analytic = analytic_rows.get(row["sample_id"])
            if patch is None or analytic is None:
                continue
            require(row["source_ids"] == sorted(patch),
                    "regular observation provider support")
            yield (case, row, fixture, patch,
                   analytic[ROW_ORDER.index(row["row_kind"])])


def _regular_exact_request_lines(checkpoint, artifact_root, manifest):
    for _, row, fixture, _, _ in _iter_regular_observation_rows(
            checkpoint, artifact_root, manifest):
        yield candidate_audit_line(
            row, len(fixture["vertices"]),
            fixture["faces"][row["face_row"]])


def _regular_emitted_request_lines(checkpoint, artifact_root, manifest):
    for _, row, fixture, _, _ in _iter_regular_observation_rows(
            checkpoint, artifact_root, manifest):
        face = fixture["faces"][row["face_row"]]
        for anchor_source in face:
            for axis in ("x", "y", "z"):
                yield candidate_emitted_geometry_line(
                    row, anchor_source, fixture, axis)


def execute_observation_regular_criteria(candidate_binary, checkpoint,
                                         artifact_root, manifest,
                                         output_root):
    """Execute regular criteria 06--07 from observation-only streams."""
    target = absolute_rational_target("200000")
    result = {}
    exact_accumulator = _NumericResultAccumulator(
        output_root, "regular_analytic_exact_rows")
    exact_observations = iter_candidate_observations(
        candidate_binary, "regular_analytic_exact_rows",
        _regular_exact_request_lines(checkpoint, artifact_root, manifest),
        EXPECTED_CELL_COUNTS["regular_analytic_exact_rows"])
    for case, row, fixture, patch, analytic_row in \
            _iter_regular_observation_rows(
                checkpoint, artifact_root, manifest):
        for anchor_name in ANCHORS:
            observation = next(exact_observations)
            key = [case["content_identity_key"],
                   normalized_cache_mode(case["applicable_mode"]),
                   case["approximation_level"], row["face_row"],
                   None if row["local_corner_or_none"] == -1 else
                   row["local_corner_or_none"], row["sample_id"],
                   row["row_kind"], "exact_effective", anchor_name,
                   "identity", None, None, None, None, None]
            validate_scientific_cell_key(
                key, "regular_analytic_exact_rows")
            value = regular_coefficient_interval_value(
                row, observation, analytic_row, patch)
            measure = value["maximum_error_upper"]
            passed = _measure_le_target(measure, target)
            exact_accumulator.add([
                key, "PASS" if passed else "FAIL", value,
                copy.deepcopy(target), None if passed else
                "REGULAR_ANALYTIC_TARGET_EXCEEDED"])
    exhausted = object()
    require(next(exact_observations, exhausted) is exhausted,
            "regular exact observation overflow")
    result["regular_analytic_exact_rows"] = exact_accumulator.finish()

    emitted_accumulator = _NumericResultAccumulator(
        output_root, "regular_analytic_emitted_geometry")
    emitted_observations = iter_candidate_observations(
        candidate_binary, "regular_analytic_emitted_geometry",
        _regular_emitted_request_lines(checkpoint, artifact_root, manifest),
        EXPECTED_CELL_COUNTS["regular_analytic_emitted_geometry"])
    for case, row, fixture, patch, analytic_row in \
            _iter_regular_observation_rows(
                checkpoint, artifact_root, manifest):
        analytic_by_source = dict(zip(patch, analytic_row))
        face = fixture["faces"][row["face_row"]]
        for anchor_name, _anchor_source in zip(ANCHORS, face):
            for axis_index, axis in enumerate(("x", "y", "z")):
                observation = next(emitted_observations)
                require(observation["axis"] == axis,
                        "regular emitted observation axis drift")
                key = [case["content_identity_key"],
                       normalized_cache_mode(case["applicable_mode"]),
                       case["approximation_level"], row["face_row"],
                       None if row["local_corner_or_none"] == -1 else
                       row["local_corner_or_none"], row["sample_id"],
                       row["row_kind"], "emitted_binary64", anchor_name,
                       "identity", None, axis, None, None, None]
                validate_scientific_cell_key(
                    key, "regular_analytic_emitted_geometry")
                analytic_value = sum((
                    analytic_by_source[source_id] * Fraction.from_float(
                        fixture["vertices"][source_id][axis_index])
                    for source_id in patch), Fraction(0))
                value = regular_emitted_interval_value(
                    observation, analytic_value)
                measure = value["absolute_error_upper"]
                passed = _measure_le_target(measure, target)
                emitted_accumulator.add([
                    key, "PASS" if passed else "FAIL", value,
                    copy.deepcopy(target), None if passed else
                    "REGULAR_ANALYTIC_TARGET_EXCEEDED"])
    require(next(emitted_observations, exhausted) is exhausted,
            "regular emitted observation overflow")
    result["regular_analytic_emitted_geometry"] = \
        emitted_accumulator.finish()
    return result


def _exact_regular_integrands(values):
    """Return rigorous 544-fraction-bit area and exact legacy volume."""
    require(isinstance(values, (list, tuple)) and len(values) == 9 and
            all(isinstance(value, Fraction) for value in values),
            "regular integrand exact vector")
    cx = values[4] * values[8] - values[5] * values[7]
    cy = values[5] * values[6] - values[3] * values[8]
    cz = values[3] * values[7] - values[4] * values[6]
    radicand = cx * cx + cy * cy + cz * cz
    require(radicand >= 0, "regular integrand exact radicand")
    scaled_numerator = radicand.numerator << 1088
    scaled_floor = scaled_numerator // radicand.denominator
    root = math.isqrt(scaled_floor)
    require(root * root * radicand.denominator <= scaled_numerator and
            (root + 1) * (root + 1) * radicand.denominator >
                scaled_numerator,
            "regular integrand square-root enclosure")
    exact = root * root * radicand.denominator == scaled_numerator
    area = _interval_descriptor(
        Fraction(root, 1 << 544),
        Fraction(root if exact else root + 1, 1 << 544))
    volume = _interval_descriptor(values[0] * cx, values[0] * cx)
    return {"regular_analytic_area_integrand": area,
            "regular_analytic_legacy_volume_integrand": volume}


def _regular_integrand_vector(group, fixture, anchor_source,
                              analytic_rows=None, patch=None):
    result = []
    for row_kind in ("position", "du", "dv"):
        row = group[row_kind]
        if analytic_rows is None:
            coefficients = {
                source_id: Fraction(numerator, 1 << 1074)
                for source_id, numerator in
                effective_numerators(row, anchor_source).items()}
            source_ids = row["source_ids"]
        else:
            formula = analytic_rows[row["sample_id"]][
                ROW_ORDER.index(row_kind)]
            coefficients = dict(zip(patch, formula))
            source_ids = patch
        for axis in range(3):
            result.append(sum((
                coefficients[source_id] * Fraction.from_float(
                    fixture["vertices"][source_id][axis])
                for source_id in source_ids), Fraction(0)))
    return result


def _candidate_integrand_request(group, fixture, anchor_source, view):
    fields = ["E" if view == "exact_effective" else "B"]
    for row_kind in ("position", "du", "dv"):
        row = group[row_kind]
        require(anchor_source in row["source_ids"],
                "regular integrand anchor support")
        fields.extend((
            row_kind, str(row["source_ids"].index(anchor_source)),
            ",".join(binary64_bits_hex(value)
                     for value in row["coefficients"])))
        for axis in range(3):
            fields.append(",".join(binary64_bits_hex(
                fixture["vertices"][source_id][axis])
                for source_id in row["source_ids"]))
    require(len(fields) == 19, "regular integrand request arity")
    return " ".join(fields) + "\n"


def _iter_regular_integrand_observation_cells(
        checkpoint, artifact_root, manifest, criterion_id):
    require(criterion_id in {
                "regular_analytic_area_integrand",
                "regular_analytic_legacy_volume_integrand"},
            "regular integrand criterion")
    quantity = ("area_integrand" if criterion_id ==
                "regular_analytic_area_integrand" else
                "legacy_volume_integrand")
    analytic_rows = regular_sample_rows(manifest)
    inventory = regular_patch_inventory(manifest)
    for case in ordered_bfr_cases(checkpoint):
        if case["approximation_level"] not in (7, 8):
            continue
        fixture = inventory[case["content_identity_key"]]
        groups = {}
        for row in ordered_case_rows(_artifact_report(artifact_root, case)):
            identity = (row["face_row"], row["local_corner_or_none"],
                        row["sample_id"])
            groups.setdefault(identity, {})[row["row_kind"]] = row
        for (face_id, local_corner_raw, sample_id), group in groups.items():
            patch = fixture["patches"].get(face_id)
            if patch is None or sample_id not in analytic_rows:
                continue
            require(set(group) == set(ROW_ORDER),
                    "regular integrand six-row group")
            face = fixture["faces"][face_id]
            cells = []
            for anchor_name, anchor_source in zip(ANCHORS, face):
                analytic_vector = _regular_integrand_vector(
                    group, fixture, anchor_source, analytic_rows, patch)
                analytic_interval = _exact_regular_integrands(
                    analytic_vector)[criterion_id]
                candidate_interval = _exact_regular_integrands(
                    _regular_integrand_vector(
                        group, fixture, anchor_source))[criterion_id]
                for view in ("exact_effective", "emitted_binary64"):
                    key = [case["content_identity_key"],
                           normalized_cache_mode(case["applicable_mode"]),
                           case["approximation_level"], face_id,
                           None if local_corner_raw == -1 else
                           local_corner_raw, sample_id, quantity, view,
                           anchor_name, "identity", None, None, None, None,
                           None]
                    validate_scientific_cell_key(key, criterion_id)
                    cells.append((jcs_bytes(key), key,
                                  _candidate_integrand_request(
                                      group, fixture, anchor_source, view),
                                  analytic_interval, candidate_interval))
            for _, key, request, analytic_interval, candidate_interval in \
                    sorted(cells, key=lambda item: item[0]):
                yield key, request, analytic_interval, candidate_interval


def _regular_integrand_request_lines(checkpoint, artifact_root, manifest,
                                     criterion_id):
    for key, request, _, _ in _iter_regular_integrand_observation_cells(
            checkpoint, artifact_root, manifest, criterion_id):
        if key[7] == "emitted_binary64":
            yield request


def execute_observation_regular_integrand_criteria(
        candidate_binary, checkpoint, artifact_root, manifest, output_root):
    """Derive exact integrands and consume only emitted candidate values."""
    result = {}
    target = absolute_rational_target("200000")
    for criterion_id in (
            "regular_analytic_area_integrand",
            "regular_analytic_legacy_volume_integrand"):
        accumulator = _NumericResultAccumulator(output_root, criterion_id)
        observations = iter_candidate_observations(
            candidate_binary, criterion_id,
            _regular_integrand_request_lines(
                checkpoint, artifact_root, manifest, criterion_id),
            EXPECTED_CELL_COUNTS[criterion_id] // 2)
        for (key, _, analytic_interval,
             expected_candidate_interval) in \
                _iter_regular_integrand_observation_cells(
                    checkpoint, artifact_root, manifest, criterion_id):
            if key[7] == "exact_effective":
                observed_interval = copy.deepcopy(
                    expected_candidate_interval)
                error = _interval_error_upper_between(
                    observed_interval, analytic_interval)
                value = {"kind": "integrand_exact_interval_v1",
                         "view": "exact_effective",
                         "observed_interval": observed_interval,
                         "analytic_interval": copy.deepcopy(
                             analytic_interval),
                         "absolute_error_upper":
                             _absolute_rational_descriptor(error)}
            else:
                observation = next(observations, None)
                require(isinstance(observation, dict) and
                        observation["view"] == "emitted_binary64",
                        "candidate emitted integrand view")
                error = _interval_error_upper(
                    Fraction.from_float(binary64_from_bits_hex(
                        observation["observed_bits"])), analytic_interval)
                value = {"kind": "integrand_emitted_interval_v1",
                         "view": "emitted_binary64",
                         "observed_bits": observation["observed_bits"],
                         "analytic_interval": copy.deepcopy(
                             analytic_interval),
                         "absolute_error_upper":
                             _absolute_rational_descriptor(error)}
            validate_contract_value(value["kind"], value)
            measure = value["absolute_error_upper"]
            passed = _measure_le_target(measure, target)
            accumulator.add([
                key, "PASS" if passed else "FAIL", value,
                copy.deepcopy(target), None if passed else
                "REGULAR_INTEGRAND_TARGET_EXCEEDED"])
        exhausted = object()
        require(next(observations, exhausted) is exhausted,
                "regular integrand observation overflow")
        result[criterion_id] = accumulator.finish()
    return result


def _iter_cache_observation_rows(checkpoint, artifact_root, manifest):
    cases = ordered_bfr_cases(checkpoint)
    by_identity = {(case["content_identity_key"],
                    case["approximation_level"],
                    case["applicable_mode"]): case for case in cases}
    topology = fixture_topology(manifest)
    identities = sorted({(case["content_identity_key"],
                          case["approximation_level"])
                         for case in cases}, key=lambda item: jcs_bytes(
                             list(item)))
    require(len(identities) == 98, "cache observation pair inventory")
    for content_id, level in identities:
        disabled_case = by_identity[(content_id, level, "cache_disabled")]
        serial_case = by_identity[
            (content_id, level, "SurfaceFactoryCache_serial")]
        disabled_rows = ordered_case_rows(
            _artifact_report(artifact_root, disabled_case))
        serial_rows = ordered_case_rows(
            _artifact_report(artifact_root, serial_case))
        require(len(disabled_rows) == len(serial_rows),
                "cache observation row cardinality")
        _, faces = topology[content_id]
        for disabled, serial in zip(disabled_rows, serial_rows):
            identity = lambda row: (
                row["face_row"], row["local_corner_or_none"],
                row["sample_id"], row["row_kind"])
            require(identity(disabled) == identity(serial),
                    "cache observation row identity")
            yield disabled_case, disabled, serial, faces[disabled["face_row"]]


def _cache_observation_request_lines(checkpoint, artifact_root, manifest):
    topology = fixture_topology(manifest)
    for case, disabled, serial, face in _iter_cache_observation_rows(
            checkpoint, artifact_root, manifest):
        vertex_count, _ = topology[case["content_identity_key"]]
        yield "{} {} {} {} {} {} {}\n".format(
            disabled["row_kind"], vertex_count,
            ",".join(str(value) for value in face),
            ",".join(str(value) for value in disabled["source_ids"]),
            ",".join(binary64_bits_hex(value)
                     for value in disabled["coefficients"]),
            ",".join(str(value) for value in serial["source_ids"]),
            ",".join(binary64_bits_hex(value)
                     for value in serial["coefficients"]))


def _iter_cache_observation_cells(checkpoint, artifact_root, manifest):
    for case, disabled, serial, face in _iter_cache_observation_rows(
            checkpoint, artifact_root, manifest):
        prefix = scientific_base_prefix(
            case, disabled, cache_mode="cache_pair")
        for anchor_name, anchor_source in zip(ANCHORS, face):
            key = strict_json_bytes(prefix + scientific_suffix_full(
                None, anchor_name, None))
            validate_scientific_cell_key(key, "cache_mode_bit_identity")
            yield key, disabled, serial, anchor_source


def _expected_row_signature_entries(row, anchor_source):
    effective = effective_numerators(row, anchor_source)
    return [[source_id, binary64_bits_hex(coefficient),
             _signed_dyadic_descriptor(effective[source_id])]
            for source_id, coefficient in zip(
                row["source_ids"], row["coefficients"])]


def execute_observation_cache_criterion(candidate_binary, checkpoint,
                                        artifact_root, manifest,
                                        output_root):
    """Execute criterion 26 from paired raw cache-mode row signatures."""
    criterion_id = "cache_mode_bit_identity"
    accumulator = _CategoricalResultAccumulator(output_root, criterion_id)
    observations = iter_candidate_observations(
        candidate_binary, criterion_id,
        _cache_observation_request_lines(
            checkpoint, artifact_root, manifest),
        EXPECTED_CELL_COUNTS[criterion_id])
    for (key, disabled, serial, anchor_source), observation in zip(
            _iter_cache_observation_cells(
                checkpoint, artifact_root, manifest), observations):
        disabled_entries = _expected_row_signature_entries(
            disabled, anchor_source)
        serial_entries = _expected_row_signature_entries(
            serial, anchor_source)
        require(observation["cache_disabled_entries"] == disabled_entries and
                observation["serial_cache_entries"] == serial_entries,
                "candidate cache signature differs from provider rows")
        disabled_digest = sha256_bytes(jcs_bytes(disabled_entries))
        serial_digest = sha256_bytes(jcs_bytes(serial_entries))
        value = {"kind": "row_signature_pair_v1",
                 "source_count": len(disabled_entries),
                 "cache_disabled_sha256": disabled_digest,
                 "serial_cache_sha256": serial_digest}
        validate_contract_value("row_signature_pair_v1", value)
        passed = disabled_entries == serial_entries
        accumulator.add([
            key, "PASS" if passed else "FAIL", value, None,
            None if passed else "CACHE_MODE_BITS_MISMATCH"])
    exhausted = object()
    require(next(observations, exhausted) is exhausted,
            "cache observation overflow")
    return {criterion_id: accumulator.finish()}


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


def _rational_descriptor(value):
    value = Fraction(value)
    return {"kind": "rational_v1", "numerator": str(value.numerator),
            "denominator": str(value.denominator)}


def _interval_descriptor(lower, upper):
    lower = Fraction(lower)
    upper = Fraction(upper)
    require(lower <= upper, "constructed interval is reversed")
    return {"kind": "interval_rational_v1",
            "lower": _rational_descriptor(lower),
            "upper": _rational_descriptor(upper)}


def _positive_sqrt_lower(value, denominator_power=1074):
    """Return a positive dyadic lower bound on sqrt(value)."""
    value = Fraction(value)
    require(value > 0 and type(denominator_power) is int and
            denominator_power > 0, "positive scale-square input")
    scaled_square = ((value.numerator << (2 * denominator_power)) //
                     value.denominator)
    numerator = math.isqrt(scaled_square)
    result = Fraction(numerator, 1 << denominator_power)
    require(result > 0 and result * result <= value,
            "scale square-root lower bound")
    return result


def oracle_coefficient_l1_value(row, anchor_source, oracle_value):
    """Derive a criterion-11 exact descriptor from provider/oracle truth."""
    require(_contract_kind(oracle_value) == "oracle_covered_value_v1" and
            oracle_value["row_kind"] == row["row_kind"],
            "oracle coefficient row binding")
    source_ids = oracle_value["source_ids"]
    require(set(row["source_ids"]).issubset(source_ids),
            "covered oracle omits a provider source")
    effective = effective_numerators(row, anchor_source)
    observed_fractions = [
        Fraction(effective.get(source_id, 0), 1 << 1074)
        for source_id in source_ids]
    intervals = copy.deepcopy(
        oracle_value["intersected_primary_intervals"])
    errors = [_interval_error_upper(observed, interval)
              for observed, interval in zip(observed_fractions, intervals)]
    result = {
        "kind": "oracle_coefficient_l1_v1",
        "source_ids": list(source_ids),
        "observed": [_signed_dyadic_descriptor(
            effective.get(source_id, 0)) for source_id in source_ids],
        "oracle_intervals": intervals,
        "absolute_error_uppers": [
            _absolute_rational_descriptor(error) for error in errors],
        "l1": _absolute_rational_descriptor(sum(errors, Fraction(0))),
    }
    validate_contract_value("oracle_coefficient_l1_v1", result)
    return result


def _oracle_geometry_reference(oracle_value, fixture, axis):
    vertices = fixture["vertices"]
    lower = Fraction(0)
    upper = Fraction(0)
    for source_id, interval in zip(
            oracle_value["source_ids"],
            oracle_value["intersected_primary_intervals"]):
        coordinate = Fraction.from_float(vertices[source_id][axis])
        coefficient_lower, coefficient_upper = _interval_fractions(interval)
        products = (coordinate * coefficient_lower,
                    coordinate * coefficient_upper)
        lower += min(products)
        upper += max(products)
    return lower, upper


def oracle_geometry_axis_value(row, anchor_source, oracle_value, fixture,
                               axis, emitted_bits=None):
    """Derive criterion 12/13 geometry and conservative normalization."""
    require(type(axis) is int and 0 <= axis < 3 and
            _contract_kind(oracle_value) == "oracle_covered_value_v1" and
            oracle_value["row_kind"] == row["row_kind"],
            "oracle geometry row/axis binding")
    require(set(row["source_ids"]).issubset(oracle_value["source_ids"]),
            "covered oracle omits a provider geometry source")
    reference_lower, reference_upper = _oracle_geometry_reference(
        oracle_value, fixture, axis)
    if emitted_bits is None:
        effective = effective_numerators(row, anchor_source)
        observed = sum((
            Fraction(numerator, 1 << 1074) *
            Fraction.from_float(fixture["vertices"][source_id][axis])
            for source_id, numerator in effective.items()), Fraction(0))
        observed_descriptor = _rational_descriptor(observed)
        view = "exact_effective"
    else:
        emitted = binary64_from_bits_hex(emitted_bits)
        require(math.isfinite(emitted), "candidate emitted geometry nonfinite")
        observed = Fraction.from_float(emitted)
        observed_descriptor = {"kind": "binary64_scalar_v1",
                               "bits": emitted_bits}
        view = "emitted_binary64"
    difference_lower = observed - reference_upper
    difference_upper = observed - reference_lower
    distance = max(abs(difference_lower), abs(difference_upper))
    scale_squared = fixture_edge_scale_squared(fixture)
    scale_lower = _positive_sqrt_lower(scale_squared)
    result = {
        "kind": "geometry_axis_v1",
        "axis": ("x", "y", "z")[axis],
        "view": view,
        "observed": observed_descriptor,
        "reference_interval": _interval_descriptor(
            reference_lower, reference_upper),
        "normalized_bound": {
            "kind": "normalized_interval_bound_v1",
            "difference_interval": _interval_descriptor(
                difference_lower, difference_upper),
            "distance_upper": _absolute_rational_descriptor(distance),
            "scale_squared_interval": _interval_descriptor(
                scale_squared, scale_squared),
            "scale_lower": _rational_descriptor(scale_lower),
            "ideal_normalized": {
                "kind": "rational_over_sqrt_v1",
                "absolute_numerator": str(distance.numerator),
                "absolute_denominator": str(distance.denominator),
                "scale_squared_numerator": str(scale_squared.numerator),
                "scale_squared_denominator": str(scale_squared.denominator),
            },
            "normalized_upper": _absolute_rational_descriptor(
                distance / scale_lower),
        },
    }
    validate_contract_value("geometry_axis_v1", result)
    return result


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


def _iter_component_observation_rows(checkpoint, artifact_root, manifest,
                                     criterion_id):
    transition = ("6_7" if criterion_id.startswith("stabilization_6_7")
                  else "7_8" if criterion_id.startswith(
                      "stabilization_7_8") else None)
    for item in iter_component_row_pairs(
            checkpoint, artifact_root, manifest):
        if transition is None or item[5] == transition:
            yield item


def _component_observation_request_lines(checkpoint, artifact_root, manifest,
                                         criterion_id):
    scales = {content_id: fixture_edge_scale_numerator(fixture)
              for content_id, fixture in
              regular_patch_inventory(manifest).items()}
    for _, low_row, high_case, high_row, fixture, transition in \
            _iter_component_observation_rows(
                checkpoint, artifact_root, manifest, criterion_id):
        yield candidate_component_line(
            low_row, high_row, fixture, transition,
            scales[high_case["content_identity_key"]])


def _iter_component_observation_cells(checkpoint, artifact_root, manifest,
                                      criterion_id):
    pairs = ("v0_v1", "v0_v2", "v1_v2")
    for low_case, low_row, high_case, high_row, fixture, transition in \
            _iter_component_observation_rows(
                checkpoint, artifact_root, manifest, criterion_id):
        del low_case
        prefix = scientific_base_prefix(high_case, high_row)
        face = fixture["faces"][high_row["face_row"]]

        def key(view, anchor, relabel="identity", basis=None, axis=None,
                pair=None, transition_value=None):
            value = strict_json_bytes(prefix + scientific_suffix_full(
                view, anchor, relabel, basis, axis, pair,
                transition_value, None))
            validate_scientific_cell_key(value, criterion_id)
            return value

        if criterion_id == "anchor_sensitivity_exact_coeff":
            for pair in pairs:
                yield key("exact_effective", None, pair=pair), {
                    "low": low_row, "high": high_row, "fixture": fixture}
        elif criterion_id in {
                "anchor_sensitivity_exact_geometry",
                "anchor_sensitivity_emitted_geometry"}:
            view = ("exact_effective" if "_exact_" in criterion_id else
                    "emitted_binary64")
            for axis in ("x", "y", "z"):
                for pair in pairs:
                    yield key(view, None, axis=axis, pair=pair), {
                        "low": low_row, "high": high_row,
                        "fixture": fixture}
        elif criterion_id == "binary64_basis_probe_diagnostic":
            for anchor_name, anchor_source in zip(ANCHORS, face):
                for relabel in RELABELS:
                    for source_id in sorted(
                            high_row["source_ids"], key=jcs_bytes):
                        yield key("emitted_binary64", anchor_name, relabel,
                                  basis=source_id), {
                            "low": low_row, "high": high_row,
                            "fixture": fixture,
                            "anchor_source": anchor_source}
        elif criterion_id in {
                "binary64_direct_geometry_fidelity",
                "relabel_emitted_geometry_fidelity"}:
            relabels = (RELABELS if criterion_id ==
                        "binary64_direct_geometry_fidelity" else RELABELS[1:])
            for anchor_name, anchor_source in zip(ANCHORS, face):
                for relabel in relabels:
                    for axis in ("x", "y", "z"):
                        yield key("emitted_binary64", anchor_name, relabel,
                                  axis=axis), {
                            "low": low_row, "high": high_row,
                            "fixture": fixture,
                            "anchor_source": anchor_source}
        else:
            view = ("exact_effective" if "_exact_" in criterion_id else
                    "emitted_binary64")
            coefficient = criterion_id.endswith("_exact_coeff")
            for anchor_name, anchor_source in zip(ANCHORS, face):
                if coefficient:
                    yield key(view, anchor_name,
                              transition_value=transition), {
                        "low": low_row, "high": high_row,
                        "fixture": fixture,
                        "anchor_source": anchor_source}
                else:
                    for axis in ("x", "y", "z"):
                        yield key(view, anchor_name, axis=axis,
                                  transition_value=transition), {
                            "low": low_row, "high": high_row,
                            "fixture": fixture,
                            "anchor_source": anchor_source}


def _exact_coefficient_difference_value(observation):
    observed = copy.deepcopy(observation["values"])
    error_numerators = [abs(value["sign"] *
                            int(value["numerator_hex"], 16))
                        for value in observed]
    errors = [_absolute_dyadic_descriptor(value)
              for value in error_numerators]
    result = {
        "kind": "exact_coefficient_l1_v1",
        "source_ids": list(observation["source_ids"]),
        "observed": observed,
        "expected": [_signed_dyadic_descriptor(0)
                     for _ in observed],
        "absolute_errors": errors,
        "l1": _absolute_dyadic_descriptor(sum(error_numerators)),
    }
    validate_contract_value("exact_coefficient_l1_v1", result)
    return result


def _exact_geometry_fraction(row, anchor_source, fixture, axis_index):
    effective = effective_numerators(row, anchor_source)
    return sum((Fraction(value, 1 << 1074) * Fraction.from_float(
        fixture["vertices"][source_id][axis_index])
        for source_id, value in effective.items()), Fraction(0))


def _component_geometry_value(key, observation, fixture, reference=Fraction(0)):
    axis_index = ("x", "y", "z").index(key[11])
    require(observation["axis"] == key[11],
            "component observation axis drift")
    if key[7] == "exact_effective":
        observed = _signed_dyadic_fraction(observation["observed"])
        observed_descriptor = copy.deepcopy(observation["observed"])
    else:
        observed = Fraction.from_float(binary64_from_bits_hex(
            observation["observed_bits"]))
        observed_descriptor = {"kind": "binary64_scalar_v1",
                               "bits": observation["observed_bits"]}
    difference = observed - reference
    distance = abs(difference)
    scale_squared = fixture_edge_scale_squared(fixture)
    scale_lower = _positive_sqrt_lower(scale_squared)
    result = {
        "kind": "geometry_axis_v1", "axis": key[11], "view": key[7],
        "observed": observed_descriptor,
        "reference_interval": _interval_descriptor(reference, reference),
        "normalized_bound": {
            "kind": "normalized_interval_bound_v1",
            "difference_interval": _interval_descriptor(
                difference, difference),
            "distance_upper": _absolute_rational_descriptor(distance),
            "scale_squared_interval": _interval_descriptor(
                scale_squared, scale_squared),
            "scale_lower": _rational_descriptor(scale_lower),
            "ideal_normalized": {
                "kind": "rational_over_sqrt_v1",
                "absolute_numerator": str(distance.numerator),
                "absolute_denominator": str(distance.denominator),
                "scale_squared_numerator": str(scale_squared.numerator),
                "scale_squared_denominator": str(scale_squared.denominator),
            },
            "normalized_upper": _absolute_rational_descriptor(
                distance / scale_lower),
        },
    }
    del axis_index
    validate_contract_value("geometry_axis_v1", result)
    return result


class _BasisObservationAccumulator:
    def __init__(self, output_root):
        self.accumulator = _NumericResultAccumulator(
            output_root, "binary64_basis_probe_diagnostic")
        self.group = None
        self.entries = []

    @staticmethod
    def _group(key):
        return tuple(jcs_bytes(item) for index, item in enumerate(key)
                     if index != 10)

    def _flush(self):
        if not self.entries:
            return
        l1_numerator = sum(item[3] for item in self.entries)
        group_l1 = _absolute_dyadic_descriptor(l1_numerator)
        target = absolute_rational_target(
            _row_target_denominator(
                "binary64_basis_probe_diagnostic", self.entries[0][0]))
        passed = _measure_le_target(group_l1, target)
        for key, observation, exact, error in self.entries:
            value = {"kind": "basis_value_v1",
                     "emitted_basis_bits": observation[
                         "emitted_basis_bits"],
                     "exact_effective": _signed_dyadic_descriptor(exact),
                     "source_error": _absolute_dyadic_descriptor(error),
                     "group_l1": group_l1}
            validate_contract_value("basis_value_v1", value)
            self.accumulator.add([
                key, "PASS" if passed else "FAIL", value,
                copy.deepcopy(target), None if passed else
                "BASIS_GROUP_L1_TARGET_EXCEEDED"])
        self.entries = []

    def add(self, key, observation, context):
        group = self._group(key)
        if self.group is not None and group != self.group:
            self._flush()
        self.group = group
        effective = effective_numerators(
            context["high"], context["anchor_source"])
        exact = effective[key[10]]
        emitted = exact_binary64_numerator(binary64_from_bits_hex(
            observation["emitted_basis_bits"]))
        self.entries.append((key, observation, exact,
                             abs(emitted - exact)))

    def finish(self):
        self._flush()
        return self.accumulator.finish()


def execute_observation_component_criteria(candidate_binary, checkpoint,
                                           artifact_root, manifest,
                                           output_root):
    """Execute criteria 14--25 from exhaustive raw component observations."""
    result = {}
    for criterion_id in CRITERION_IDS[14:26]:
        accumulator = (_BasisObservationAccumulator(output_root)
                       if criterion_id ==
                       "binary64_basis_probe_diagnostic" else
                       _NumericResultAccumulator(output_root, criterion_id))
        observations = iter_candidate_observations(
            candidate_binary, criterion_id,
            _component_observation_request_lines(
                checkpoint, artifact_root, manifest, criterion_id),
            EXPECTED_CELL_COUNTS[criterion_id])
        for (key, context), observation in zip(
                _iter_component_observation_cells(
                    checkpoint, artifact_root, manifest, criterion_id),
                observations):
            if criterion_id == "binary64_basis_probe_diagnostic":
                accumulator.add(key, observation, context)
                continue
            target = absolute_rational_target(
                _row_target_denominator(criterion_id, key))
            if criterion_id.endswith("_exact_coeff"):
                value = _exact_coefficient_difference_value(observation)
            else:
                reference = Fraction(0)
                if criterion_id == "binary64_direct_geometry_fidelity":
                    reference = _exact_geometry_fraction(
                        context["high"], context["anchor_source"],
                        context["fixture"],
                        ("x", "y", "z").index(key[11]))
                value = _component_geometry_value(
                    key, observation, context["fixture"], reference)
            measure = _record_measure_descriptor(criterion_id, value)
            passed = _measure_le_target(measure, target)
            accumulator.add([
                key, "PASS" if passed else "FAIL", value,
                copy.deepcopy(target), None if passed else
                RESULT_CONTRACT.CRITERION_BY_ID[criterion_id]["reasons"][0]])
        exhausted = object()
        require(next(observations, exhausted) is exhausted,
                "component observation overflow")
        result[criterion_id] = accumulator.finish()
    return result


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


def make_candidate_pre_result_ledgers(checkpoint, artifact_root):
    """Materialize the four candidate applicability sets without outcomes."""
    suffixes = _validate_suffix_definitions()
    criterion_ids = (
        "representation_structure", "constant_field_bits",
        "relabel_exact_effective_coefficients", "cache_mode_bit_identity")
    ledgers = {criterion_id: StreamingScientificLedger(criterion_id)
               for criterion_id in criterion_ids}
    ledger_suffixes = {
        criterion_id: [item[0] for item in suffixes[criterion_id]]
        for criterion_id in criterion_ids}
    cases = ordered_bfr_cases(checkpoint)
    by_identity = {
        (case["content_identity_key"], case["approximation_level"],
         case["applicable_mode"]): case for case in cases}

    for case in cases:
        report = _artifact_report(artifact_root, case)
        for row in ordered_case_rows(report):
            prefix = scientific_base_prefix(case, row)
            for criterion_id in criterion_ids[:3]:
                _add_sorted_suffixes(
                    ledgers[criterion_id], prefix,
                    ledger_suffixes[criterion_id])

    pair_identities = sorted({
        (case["content_identity_key"], case["approximation_level"])
        for case in cases}, key=lambda item: jcs_bytes(list(item)))
    require(len(pair_identities) == 98,
            "cache-pair applicability inventory drift")

    def row_identity(row):
        return (row["face_row"], row["local_corner_or_none"],
                row["sample_id"], row["row_kind"])

    for content_id, level in pair_identities:
        disabled_case = by_identity.get(
            (content_id, level, "cache_disabled"))
        serial_case = by_identity.get(
            (content_id, level, "SurfaceFactoryCache_serial"))
        require(disabled_case is not None and serial_case is not None,
                "cache-pair applicability case missing")
        disabled_rows = ordered_case_rows(
            _artifact_report(artifact_root, disabled_case))
        serial_rows = ordered_case_rows(
            _artifact_report(artifact_root, serial_case))
        require(len(disabled_rows) == len(serial_rows),
                "cache-pair applicability row count drift")
        for disabled_row, serial_row in zip(disabled_rows, serial_rows):
            require(row_identity(disabled_row) == row_identity(serial_row),
                    "cache-pair applicability row identity drift")
            prefix = scientific_base_prefix(
                disabled_case, disabled_row, cache_mode="cache_pair")
            _add_sorted_suffixes(
                ledgers["cache_mode_bit_identity"], prefix,
                ledger_suffixes["cache_mode_bit_identity"])

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


def _d12_process_provenance(key, process, executable_sha256):
    require(isinstance(process, dict) and set(process) == {
                "pid", "start_utc", "end_utc", "exit_kind", "exit_code",
                "signal", "argv_sha256", "environment_sha256",
                "stderr_sha256"} and process["pid"] is not None and
            ((process["exit_kind"] == "EXITED" and
              type(process["exit_code"]) is int and
              process["signal"] is None) or
             (process["exit_kind"] == "SIGNALED" and
              process["exit_code"] is None and
              type(process["signal"]) is int and process["signal"] > 0)) and
            SHA256_RE.fullmatch(executable_sha256 or "") is not None,
            "D12 source process provenance is incomplete")
    return {
        "kind": "d12_process_provenance_v1",
        "process_tuple_sha256": sha256_bytes(jcs_bytes(key[:5])),
        "executable_sha256": executable_sha256,
        "argv_sha256": process["argv_sha256"],
        "environment_sha256": process["environment_sha256"],
        "pid": process["pid"], "start_utc": process["start_utc"],
        "end_utc": process["end_utc"],
        "exit_kind": process["exit_kind"],
        "exit_code": process["exit_code"], "signal": process["signal"],
        "stderr_sha256": process["stderr_sha256"],
    }


def _d12_numeric_observations_for_case(case, report,
                                       executable_sha256):
    """Derive all exact D12 numeric raw records from one process artifact."""
    require(case["candidate"] == "bfr" and
            report.get("d12_representation_workload_included") is True,
            "D12 numeric artifact omitted representation work")
    content_id = case["content_identity_key"]
    level = case["approximation_level"]
    cache_mode = normalized_cache_mode(case["applicable_mode"])
    process = case.get("d12_primary_process_provenance")
    records = []

    def add(criterion_id, key, payload):
        provenance = _d12_process_provenance(
            key, process, executable_sha256)
        record = [key, payload, provenance]
        validate_d12_process_observation(record)
        records.append((criterion_id, record))

    durations = report.get("preparation_ns")
    require(isinstance(durations, list) and len(durations) == 15 and
            all(type(value) is int and value >= 0 for value in durations) and
            report.get("preparation_median_ns") == sorted(durations)[7],
            "D12 numeric duration observations incomplete")
    for repeat_index, duration in enumerate(durations):
        key = [content_id, level, "release", cache_mode, None, None, None,
               "measured", repeat_index, None, None, None, None,
               "preparation_duration_ns"]
        add("d12_preparation_cost", key, {
            "kind": "d12_duration_raw_v1", "state": "VALID_UINT64_NS",
            "token": str(duration)})
    median_key = [content_id, level, "release", cache_mode, None, None,
                  None, None, None, None, None, None, None,
                  "preparation_median_ns"]
    add("d12_preparation_cost", median_key, {
        "kind": "d12_duration_raw_v1", "state": "VALID_UINT64_NS",
        "token": str(report["preparation_median_ns"])})

    payloads = report.get("d12_retained_payload_bytes_by_face")
    require(isinstance(payloads, list) and payloads and
            all(type(value) is int and value >= 0 for value in payloads),
            "D12 retained-payload observations incomplete")
    for face_id, payload_bytes in enumerate(payloads):
        key = [content_id, level, "release", cache_mode, None, None, None,
               None, None, face_id, None, None, None,
               "retained_payload_bytes"]
        add("d12_retained_payload", key, {
            "kind": "d12_payload_raw_v1",
            "state": "VALID_UINT64_BYTES", "token": str(payload_bytes)})

    baseline = report.get("d12_rss_baseline_bytes")
    observations = report.get("d12_rss_observations")
    require(type(baseline) is int and baseline >= 0 and
            isinstance(observations, list) and
            len(observations) == report.get("rss_expected_named_sample_count"),
            "D12 RSS raw observation coverage")
    baseline_key = [content_id, level, "release", cache_mode, None, None,
                    None, None, None, None, None, None,
                    "pre_refiner_baseline", "rss_bytes"]
    add("d12_peak_rss", baseline_key, {
        "kind": "d12_rss_raw_v1", "state": "VALID_UINT64_BYTES",
        "baseline_token": str(baseline), "observed_token": str(baseline)})
    for observation in observations:
        require(isinstance(observation, dict) and set(observation) == {
                    "repeat_phase", "repeat_index", "face_id",
                    "local_corner_or_none", "sample_id", "stage",
                    "rss_bytes"} and
                type(observation["rss_bytes"]) is int and
                observation["rss_bytes"] >= 0,
                "D12 RSS raw observation shape")
        key = [content_id, level, "release", cache_mode, None, None, None,
               observation["repeat_phase"], observation["repeat_index"],
               observation["face_id"],
               observation["local_corner_or_none"],
               observation["sample_id"], observation["stage"], "rss_bytes"]
        add("d12_peak_rss", key, {
            "kind": "d12_rss_raw_v1", "state": "VALID_UINT64_BYTES",
            "baseline_token": str(baseline),
            "observed_token": str(observation["rss_bytes"])})
    records.sort(key=lambda item: jcs_bytes(item[1][0]))
    require(len({jcs_bytes(item[1][0]) for item in records}) == len(records),
            "D12 numeric raw observation duplicate key")
    return records


def iter_d12_numeric_observations(checkpoint, artifact_root):
    executable_sha256 = checkpoint["binding"]["candidate_binary_sha256"]
    for case in _ordered_d12_cases(checkpoint):
        report = _artifact_report(artifact_root, case)
        for criterion_id, record in _d12_numeric_observations_for_case(
                case, report, executable_sha256):
            yield criterion_id, record


class D12ProcessObservationArtifact:
    """Externally sort raw process records and retain exact slice bindings."""

    RELATIVE_PATH = (
        "anchored-row-d12-v1/process/process-observations.json")

    def __init__(self, output_root, expected_tsan_executables=None):
        self.output_root = pathlib.Path(output_root).resolve()
        self.destination = self.output_root / self.RELATIVE_PATH
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            prefix="anchored-row-d12-process-", suffix=".sqlite3",
            delete=False)
        handle.close()
        self.database_path = pathlib.Path(handle.name)
        self.connection = sqlite3.connect(str(self.database_path))
        self.connection.execute("PRAGMA journal_mode=OFF")
        self.connection.execute("PRAGMA synchronous=OFF")
        self.connection.execute(
            "CREATE TABLE records (key BLOB PRIMARY KEY, criterion TEXT "
            "NOT NULL, payload BLOB NOT NULL, record BLOB NOT NULL)")
        self.connection.execute(
            "CREATE TABLE bindings (key BLOB PRIMARY KEY, criterion TEXT "
            "NOT NULL, payload BLOB NOT NULL, byte_offset INTEGER NOT NULL, "
            "byte_length INTEGER NOT NULL, sha256 TEXT NOT NULL)")
        self.tsan_processes = {}
        self.expected_tsan_executables = (
            None if expected_tsan_executables is None else
            frozenset(expected_tsan_executables))
        require(self.expected_tsan_executables is None or
                len(self.expected_tsan_executables) == 2 and
                all(SHA256_RE.fullmatch(value or "") is not None
                    for value in self.expected_tsan_executables),
                "D12 process artifact expected TSan executables")
        self.count = 0
        self.finished = False

    def add(self, criterion_id, record):
        require(not self.finished and criterion_id in D12_CRITERIA and
                criterion_id != "d12_cache_disabled_concurrency",
                "D12 raw process observation owner")
        key, payload, provenance = validate_d12_process_observation(record)
        if criterion_id == "d12_instrumented_tsan":
            tuple_key = jcs_bytes(key[:5])
            summaries = self.tsan_processes.setdefault(tuple_key, {})
            require(key[13] not in summaries,
                    "D12 TSan process duplicates a raw summary")
            summaries[key[13]] = (copy.deepcopy(payload),
                                  copy.deepcopy(provenance))
        encoded_key = jcs_bytes(key)
        encoded_payload = jcs_bytes(payload)
        encoded_record = jcs_bytes(record)
        try:
            self.connection.execute(
                "INSERT INTO records(key,criterion,payload,record) "
                "VALUES(?,?,?,?)",
                (sqlite3.Binary(encoded_key), criterion_id,
                 sqlite3.Binary(encoded_payload),
                 sqlite3.Binary(encoded_record)))
        except sqlite3.IntegrityError as error:
            raise QualificationError(
                "D12 raw process observation duplicate key") from error
        self.count += 1

    def finish(self, expected_count=None):
        require(not self.finished and
                (expected_count is None or self.count == expected_count),
                "D12 process observation cardinality")
        require(all(_validate_d12_tsan_process_pair(
                        records, self.expected_tsan_executables)
                    for records in self.tsan_processes.values()),
                "D12 TSan process-pair validation")
        self.connection.commit()
        digest = hashlib.sha256()
        offset = 0
        with self.destination.open("wb") as stream:
            stream.write(b"[")
            digest.update(b"[")
            offset = 1
            batch = []
            previous = None
            for key, criterion_id, payload, record in self.connection.execute(
                    "SELECT key,criterion,payload,record FROM records "
                    "ORDER BY key"):
                key = bytes(key)
                payload = bytes(payload)
                record = bytes(record)
                require(previous is None or previous < key,
                        "D12 process observation key order")
                if previous is not None:
                    stream.write(b",")
                    digest.update(b",")
                    offset += 1
                stream.write(record)
                digest.update(record)
                batch.append((sqlite3.Binary(key), criterion_id,
                              sqlite3.Binary(payload), offset, len(record),
                              sha256_bytes(record)))
                if len(batch) == 4096:
                    self.connection.executemany(
                        "INSERT INTO bindings VALUES(?,?,?,?,?,?)", batch)
                    batch = []
                offset += len(record)
                previous = key
            if batch:
                self.connection.executemany(
                    "INSERT INTO bindings VALUES(?,?,?,?,?,?)", batch)
            stream.write(b"]")
            digest.update(b"]")
        self.connection.commit()
        self.finished = True
        descriptor = {
            "availability": availability("PRESENT", digest.hexdigest()),
            "relative_path": self.RELATIVE_PATH,
            "byte_length": self.destination.stat().st_size,
            "record_count": self.count, "sha256": digest.hexdigest()}
        validate_contract_value("d12_sidecar_descriptor", descriptor)
        return descriptor

    def iter_bindings(self, criterion_id):
        require(self.finished and criterion_id in D12_CRITERIA,
                "D12 process binding iteration state")
        for key, payload, byte_offset, byte_length, digest in \
                self.connection.execute(
                    "SELECT key,payload,byte_offset,byte_length,sha256 "
                    "FROM bindings WHERE criterion=? ORDER BY key",
                    (criterion_id,)):
            binding = {
                "kind": "d12_raw_observation_binding_v1",
                "availability": availability("PRESENT", digest),
                "relative_path": self.RELATIVE_PATH,
                "byte_offset": byte_offset, "byte_length": byte_length,
                "sha256": digest}
            validate_contract_value(
                "d12_raw_observation_binding_v1", binding)
            yield (strict_json_bytes(bytes(key)),
                   strict_json_bytes(bytes(payload)), binding)

    def close(self):
        try:
            self.connection.close()
        finally:
            try:
                self.database_path.unlink()
            except FileNotFoundError:
                pass


def _d12_numeric_result_record(criterion_id, key, payload, raw_binding,
                               platform_state):
    require(criterion_id in {
                "d12_preparation_cost", "d12_retained_payload",
                "d12_peak_rss"} and
            platform_state in {"QUALIFIED_PLATFORM",
                               "UNQUALIFIED_PLATFORM"},
            "D12 numeric result derivation inputs")
    if criterion_id == "d12_preparation_cost":
        duration = _canonical_uint64_token(payload["token"])
        value = {
            "kind": "d12_duration_valid_v1", "quantity": key[13],
            "duration_ns": duration, "platform_state": platform_state,
            "raw_observation": raw_binding}
        target = report_criterion_target(criterion_id)
        threshold = (target["median_ns"] if key[13] ==
                     "preparation_median_ns" else target["single_ns"])
        reason = ("PREPARATION_MEDIAN_BUDGET_EXCEEDED" if key[13] ==
                  "preparation_median_ns" else
                  "PREPARATION_SINGLE_RUN_BUDGET_EXCEEDED")
        passed = duration <= threshold
    elif criterion_id == "d12_retained_payload":
        payload_bytes = _canonical_uint64_token(payload["token"])
        value = {
            "kind": "d12_payload_valid_v1",
            "payload_bytes": payload_bytes, "face_id": key[9],
            "platform_state": platform_state,
            "raw_observation": raw_binding}
        target = report_criterion_target(criterion_id)
        passed = payload_bytes <= target["maximum_bytes"]
        reason = "RETAINED_PAYLOAD_BUDGET_EXCEEDED"
    else:
        baseline = _canonical_uint64_token(payload["baseline_token"])
        observed = _canonical_uint64_token(payload["observed_token"])
        delta = max(0, observed - baseline)
        value = {
            "kind": "d12_rss_valid_v1",
            "baseline_rss_bytes": baseline,
            "observed_rss_bytes": observed,
            "rss_delta_bytes": delta, "stage": key[12],
            "platform_state": platform_state,
            "raw_observation": raw_binding}
        target = report_criterion_target(criterion_id)
        passed = delta <= target["maximum_delta_bytes"]
        reason = "PEAK_RSS_BUDGET_EXCEEDED"
    if platform_state == "UNQUALIFIED_PLATFORM":
        outcome, reason = "INCOMPLETE", "D12_PLATFORM_UNQUALIFIED"
    elif passed:
        outcome, reason = "PASS", None
    else:
        outcome = "FAIL"
    record = [key, outcome, value, target, reason]
    validate_contract_result_record(criterion_id, record)
    validate_d12_raw_exact_value(payload, value)
    return record


def execute_d12_numeric_criteria(process_artifact, output_root,
                                  platform_state):
    """Persist criteria 27--29 solely from the runner-owned raw sidecar."""
    result = {}
    for criterion_id in (
            "d12_preparation_cost", "d12_retained_payload",
            "d12_peak_rss"):
        accumulator = _NumericResultAccumulator(output_root, criterion_id)
        for key, payload, binding in process_artifact.iter_bindings(
                criterion_id):
            accumulator.add(_d12_numeric_result_record(
                criterion_id, key, payload, binding, platform_state))
        result[criterion_id] = accumulator.finish()
    return result


def write_d12_serial_references(checkpoint, artifact_root, output_root):
    """Independently publish the exact 98-case serial reference bytes."""
    output_root = pathlib.Path(output_root).resolve()
    provider_relative = (
        "anchored-row-d12-v1/serial/provider-rows.b2rowv1")
    representation_relative = (
        "anchored-row-d12-v1/serial/representation-outputs.json")
    provider_path = output_root / provider_relative
    representation_path = output_root / representation_relative
    request_root = output_root / "anchored-row-d12-v1/requests"
    provider_path.parent.mkdir(parents=True, exist_ok=True)
    request_root.mkdir(parents=True, exist_ok=True)
    fixtures = {}
    for job in B2.valid_content_jobs(B2.load_manifest()):
        vertices, faces, _ = B2.independent_mesh(job)
        fixtures[job["content_identity_key"]] = {
            "vertices": vertices, "faces": faces}
    execution_inputs = (
        ("fixture_x", 0), ("fixture_y", 1), ("fixture_z", 2),
        ("positive_zero", 0.0), ("positive_one", 1.0),
        ("negative_one", -1.0), ("positive_2p20", 2.0 ** 20),
        ("negative_2p20", -(2.0 ** 20)))
    output_inputs = sorted(execution_inputs,
                           key=lambda item: jcs_bytes(item[0]))
    provider_digest = hashlib.sha256()
    representation_digest = hashlib.sha256(b"[")
    provider_count = 0
    representation_count = 0
    references = {}
    with provider_path.open("wb") as provider_stream, \
            representation_path.open("wb") as representation_stream:
        representation_stream.write(b"[")
        for case in _ordered_d12_cases(checkpoint):
            if normalized_cache_mode(case["applicable_mode"]) != \
                    "cache_disabled":
                continue
            report = _artifact_report(artifact_root, case)
            fixture = fixtures[case["content_identity_key"]]
            case_provider = hashlib.sha256()
            case_representation = hashlib.sha256(b"[")
            case_provider_count = 0
            case_representation_count = 0
            request_name = sha256_bytes(jcs_bytes([
                case["content_identity_key"],
                case["approximation_level"]])) + ".tsv"
            request_path = request_root / request_name
            with request_path.open("wb") as request_stream:
                for row in report["rows"]:
                    provider_record = D12WorkerInventoryVerifier.\
                        _provider_record_bytes(row)
                    provider_stream.write(provider_record)
                    provider_digest.update(provider_record)
                    case_provider.update(provider_record)
                    provider_count += 1
                    case_provider_count += 1
                    anchor_source = fixture["faces"][row["face_row"]][0]
                    require(anchor_source in row["source_ids"],
                            "D12 serial reference lacks oriented v0 anchor")
                    anchor_index = row["source_ids"].index(anchor_source)
                    request_fields = [
                        case["content_identity_key"],
                        str(case["approximation_level"]),
                        str(row["face_row"]),
                        str(row["local_corner_or_none"]), row["sample_id"],
                        row["row_kind"], str(anchor_index),
                        ",".join(B2A.binary64_bits_hex(value)
                                 for value in row["coefficients"])]
                    for axis in range(3):
                        request_fields.append(",".join(
                            B2A.binary64_bits_hex(
                                fixture["vertices"][source_id][axis])
                            for source_id in row["source_ids"]))
                    require(all("\t" not in field and "\n" not in field
                                for field in request_fields),
                            "D12 representation request delimiter collision")
                    request_stream.write(
                        ("\t".join(request_fields) + "\n").encode("utf-8"))
                    observed_results = {}
                    for input_id, input_value in execution_inputs:
                        if isinstance(input_value, int):
                            sources = [fixture["vertices"][source_id][input_value]
                                       for source_id in row["source_ids"]]
                        else:
                            sources = [input_value] * len(row["source_ids"])
                        observed_results[input_id] = \
                            D12WorkerInventoryVerifier._anchored_evaluate(
                                row, anchor_source, sources)
                    require(len(observed_results) == 8,
                            "D12 serial representation input coverage")
                    for input_id, _ in output_inputs:
                        record = [
                            case["content_identity_key"],
                            case["approximation_level"], row["face_row"],
                            None if row["local_corner_or_none"] == -1 else
                            row["local_corner_or_none"], row["sample_id"],
                            row["row_kind"], input_id,
                            observed_results[input_id]]
                        encoded = jcs_bytes(record)
                        separator = b"," if representation_count else b""
                        representation_stream.write(separator)
                        representation_stream.write(encoded)
                        representation_digest.update(separator)
                        representation_digest.update(encoded)
                        if case_representation_count:
                            case_representation.update(b",")
                        case_representation.update(encoded)
                        representation_count += 1
                        case_representation_count += 1
            case_representation.update(b"]")
            require(case_provider_count > 0 and
                    case_representation_count == case_provider_count * 8 and
                    case_provider.hexdigest() ==
                        case["canonical_rows_sha256"],
                    "D12 serial case reference derivation drift")
            references[(case["content_identity_key"],
                        case["approximation_level"])] = {
                "provider": case_provider.hexdigest(),
                "representation": case_representation.hexdigest(),
                "provider_count": case_provider_count,
                "representation_count": case_representation_count,
                "request_path": str(request_path),
                "request_sha256": sha256_file(request_path)}
        representation_stream.write(b"]")
        representation_digest.update(b"]")
    require(len(references) == 98 and provider_count == 693000 and
            representation_count == 5544000,
            "D12 serial reference cardinality")

    def descriptor(relative_path, path, count, digest):
        value = {
            "availability": availability("PRESENT", digest),
            "relative_path": relative_path,
            "byte_length": path.stat().st_size,
            "record_count": count, "sha256": digest}
        validate_contract_value("d12_sidecar_descriptor", value)
        return value

    return ({
        "provider_serial_reference": descriptor(
            provider_relative, provider_path, provider_count,
            provider_digest.hexdigest()),
        "representation_serial_reference": descriptor(
            representation_relative, representation_path,
            representation_count, representation_digest.hexdigest())},
        references)


def _copy_d12_stream_bytes(source, destination, byte_count):
    digest = hashlib.sha256()
    remaining = byte_count
    while remaining:
        block = source.read(min(1024 * 1024, remaining))
        require(block, "D12 worker stream truncated")
        if destination is not None:
            destination.write(block)
        digest.update(block)
        remaining -= len(block)
    return digest.hexdigest()


def execute_d12_worker_streams(provider_tsan_binary,
                               representation_tsan_binary, checkpoint,
                               output_root, references,
                               process_artifact,
                               instrumentation_digest,
                               timeout_seconds=3600):
    """Execute every frozen tuple, atomically publishing only complete bytes."""
    provider_binary = pathlib.Path(provider_tsan_binary).resolve()
    representation_binary = pathlib.Path(
        representation_tsan_binary).resolve()
    require(provider_binary.is_file() and representation_binary.is_file() and
            SHA256_RE.fullmatch(instrumentation_digest or "") is not None,
            "D12 TSan worker executables/instrumentation unavailable")
    provider_sha256 = sha256_file(provider_binary)
    representation_sha256 = sha256_file(representation_binary)
    jobs = {job["content_identity_key"]: job
            for job in B2.valid_content_jobs(B2.load_manifest())}
    environment = _d12_rebuild_environment()
    descriptors = {}
    aborts = {}
    published_content_files = {}
    tuple_count = 0
    tuple_identities = B2.expected_threading_identities(B2.load_manifest())
    expected_descriptor_count = sum(
        40 * worker_count for _, _, _, worker_count in tuple_identities)
    for content_id, level, mode, worker_count in tuple_identities:
        cache_mode = ("threaded_cache" if mode ==
                      "SurfaceFactoryCacheThreaded" else mode)
        require(cache_mode in {"cache_disabled", "threaded_cache"} and
                (content_id, level) in references,
                "D12 worker tuple/reference identity")
        job = jobs[content_id]
        provider_command = [
            str(provider_binary), "--d12-thread-stream", job["mesh_path"],
            job["mutation"], str(level), mode, str(worker_count), content_id]
        representation_command = [
            str(representation_binary), "--d12-representation-stream",
            str(worker_count)]

        def run_worker(command, input_path=None):
            stdout = tempfile.TemporaryFile()
            stderr_file = tempfile.TemporaryFile()
            input_stream = (pathlib.Path(input_path).open("rb")
                            if input_path is not None else None)
            started = iso_utc_now()
            process = subprocess.Popen(
                command, cwd=str(ROOT), env=environment,
                stdin=input_stream, stdout=stdout, stderr=stderr_file,
                start_new_session=True)
            expired = []

            def expire():
                expired.append(True)
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass

            timer = threading.Timer(timeout_seconds, expire)
            timer.start()
            try:
                returncode = process.wait()
            finally:
                timer.cancel()
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        pass
                    process.wait()
                if input_stream is not None:
                    input_stream.close()
            ended = iso_utc_now()
            stderr_file.seek(0)
            stderr = stderr_file.read()
            stderr_file.close()
            require(not expired, "D12 TSan worker process timed out")
            lower_stderr = stderr.lower()
            race = (returncode != 0 and
                    b"threadsanitizer: data race" in lower_stderr)
            require(returncode == 0 or race,
                    "D12 TSan worker failed without a sanitizer data-race "
                    "report")
            stdout.seek(0)
            return {"stdout": stdout, "stderr": stderr, "race": race,
                    "returncode": returncode, "process": process,
                    "command": command, "started": started, "ended": ended}

        provider_run = run_worker(provider_command)
        representation_run = run_worker(
            representation_command,
            references[(content_id, level)]["request_path"])
        try:
            race = provider_run["race"] or representation_run["race"]
            require(not (provider_run["race"] and
                         representation_run["race"]),
                    "D12 two-process tuple has multiple sanitizer reports")
            for run in (provider_run, representation_run):
                if run["returncode"] == 0:
                    require(run["stderr"] == b"",
                            "D12 successful TSan worker emitted stderr")
            if not race:
                provider_stream = provider_run["stdout"]
                representation_stream = representation_run["stdout"]
                tuple_relative_root = (
                    "anchored-row-d12-v1/workers/{}/{}/level-{}/workers-{}"
                    .format(cache_mode, content_id, level, worker_count))
                final_tuple_root = (pathlib.Path(output_root) /
                                    tuple_relative_root)
                require(not final_tuple_root.exists(),
                        "D12 worker tuple output already exists")
                with tempfile.TemporaryDirectory(
                        prefix="anchored-row-d12-tuple-",
                        dir=str(pathlib.Path(output_root))) as temporary:
                    temporary_root = pathlib.Path(temporary)
                    staged_tuple_root = temporary_root / tuple_relative_root
                    tuple_descriptors = {}
                    tuple_masters = {}
                    new_master_paths = {}
                    provider_magic = provider_stream.read(8)
                    representation_magic = representation_stream.read(8)
                    require(provider_magic == b"D12PROV1" and
                            representation_magic == b"D12REPR1",
                            "D12 provider/representation worker stream magic: " +
                            repr((provider_magic, representation_magic)))
                    for round_index in range(20):
                        for worker_index in range(worker_count):
                            provider_header = provider_stream.read(16)
                            representation_header = \
                                representation_stream.read(24)
                            require(len(provider_header) == 16 and
                                    len(representation_header) == 24,
                                    "D12 worker stream header truncation")
                            provider_round, provider_worker, provider_length = \
                                struct.unpack("<IIQ", provider_header)
                            representation_round, representation_worker, \
                                representation_length = struct.unpack(
                                    ">QQQ", representation_header)
                            require((provider_round, provider_worker) ==
                                        (round_index, worker_index) and
                                    (representation_round,
                                     representation_worker) ==
                                        (round_index, worker_index) and
                                    provider_length > 0 and
                                    representation_length > 0,
                                    "D12 worker stream identity/length drift")
                            prefix = tuple_relative_root + \
                                "/round-{:02d}/worker-{}".format(
                                    round_index, worker_index)
                            expected = references[(content_id, level)]
                            for suffix, source_stream, length, expected_count, \
                                    expected_digest in (
                                        ("-provider.b2rowv1",
                                         provider_stream,
                                         provider_length,
                                         expected["provider_count"],
                                         expected["provider"]),
                                        ("-representation.json",
                                         representation_stream,
                                         representation_length,
                                         expected["representation_count"],
                                         expected["representation"])):
                                relative_path = prefix + suffix
                                destination = temporary_root / relative_path
                                destination.parent.mkdir(
                                    parents=True, exist_ok=True)
                                content_file_key = (content_id, level, suffix)
                                master = published_content_files.get(
                                    content_file_key,
                                    tuple_masters.get(content_file_key))
                                if master is None:
                                    stream = destination.open("wb")
                                else:
                                    stream = None
                                try:
                                    observed_digest = _copy_d12_stream_bytes(
                                        source_stream, stream, length)
                                finally:
                                    if stream is not None:
                                        stream.close()
                                require(observed_digest == expected_digest,
                                        "D12 worker output differs from serial "
                                        "reference: " + relative_path)
                                if master is None:
                                    tuple_masters[content_file_key] = destination
                                    new_master_paths[content_file_key] = \
                                        relative_path
                                else:
                                    os.link(str(master), str(destination),
                                            follow_symlinks=False)
                                descriptor = {
                                    "availability": availability(
                                        "PRESENT", observed_digest),
                                    "relative_path": relative_path,
                                    "byte_length": length,
                                    "record_count": expected_count,
                                    "sha256": observed_digest}
                                validate_contract_value(
                                    "d12_sidecar_descriptor", descriptor)
                                require(relative_path not in descriptors and
                                        relative_path not in tuple_descriptors,
                                        "D12 worker sidecar path collision")
                                tuple_descriptors[relative_path] = descriptor
                    require(provider_stream.read(1) == b"" and
                            representation_stream.read(1) == b"",
                            "D12 worker stream trailing bytes")
                    final_tuple_root.parent.mkdir(parents=True, exist_ok=True)
                    staged_tuple_root.replace(final_tuple_root)
                    descriptors.update(tuple_descriptors)
                    for content_file_key, relative_path in \
                            new_master_paths.items():
                        published_content_files[content_file_key] = \
                            pathlib.Path(output_root) / relative_path
            # The frozen tuple has exactly two summary records.  Bind one to
            # each fresh TSan process so successful zero-finding evidence
            # cannot silently discard either executed translation unit.
            if provider_run["race"]:
                instrumentation_run = representation_run
                instrumentation_sha256 = representation_sha256
                finding_run = provider_run
                finding_executable_sha256 = provider_sha256
            else:
                instrumentation_run = provider_run
                instrumentation_sha256 = provider_sha256
                finding_run = representation_run
                finding_executable_sha256 = representation_sha256

            def process_base(run):
                returncode = run["returncode"]
                return {
                    "pid": run["process"].pid,
                    "start_utc": run["started"],
                    "end_utc": run["ended"],
                    "exit_kind": ("SIGNALED" if returncode < 0 else
                                  "EXITED"),
                    "exit_code": None if returncode < 0 else returncode,
                    "signal": -returncode if returncode < 0 else None,
                    "argv_sha256": sha256_bytes(jcs_bytes(run["command"])),
                    "environment_sha256": sha256_bytes(
                        jcs_bytes(environment)),
                    "stderr_sha256": sha256_bytes(run["stderr"])}

            finding_process = process_base(finding_run)
            instrumentation_process = process_base(instrumentation_run)
            finding_key = [
                content_id, level, "tsan", cache_mode, worker_count,
                None, None, None, None, None, None, None,
                "sanitizer_summary", "tsan_finding_count"]
            if race:
                report_digest = sha256_bytes(finding_run["stderr"])
                report_path = pathlib.Path(output_root) / \
                    _d12_tsan_report_relative_path(finding_key)
                require(finding_run["stderr"] and not report_path.exists(),
                        "D12 sanitizer abort report is empty or duplicated")
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_bytes(finding_run["stderr"])
                aborts[(content_id, level, cache_mode,
                        worker_count)] = report_digest
            else:
                report_digest = None
                report_path = pathlib.Path(output_root) / \
                    _d12_tsan_report_relative_path(finding_key)
                require(not report_path.exists(),
                        "D12 successful tuple has a stale sanitizer report")
        finally:
            provider_run["stdout"].close()
            representation_run["stdout"].close()
        for quantity, payload, provenance_process, executable_sha256 in (
                ("instrumentation_coverage", {
                    "kind": "d12_tsan_instrumentation_raw_v1",
                    "state": "COMPLETE",
                    "instrumented_translation_units_sha256":
                        instrumentation_digest}, instrumentation_process,
                 instrumentation_sha256),
                ("tsan_finding_count", {
                    "kind": "d12_tsan_finding_raw_v1",
                    "state": "SANITIZER_ABORT" if race else "COMPLETE",
                    "finding_count_token": None if race else "0",
                    "sanitizer_report_sha256": report_digest},
                 finding_process, finding_executable_sha256)):
            key = [content_id, level, "tsan", cache_mode, worker_count,
                   None, None, None, None, None, None, None,
                   "sanitizer_summary", quantity]
            process_artifact.add(
                "d12_instrumented_tsan",
                [key, payload, _d12_process_provenance(
                    key, provenance_process, executable_sha256)])
        tuple_count += 1
    missing_descriptors = sum(40 * tuple_key[3] for tuple_key in aborts)
    require(tuple_count == len(tuple_identities) and
            len(descriptors) ==
                expected_descriptor_count - missing_descriptors,
            "D12 worker tuple/sidecar coverage")
    return ([descriptors[path]
             for path in sorted(descriptors, key=jcs_bytes)], aborts)


def execute_d12_threading_criteria(worker_sidecars, references,
                                   process_artifact, output_root,
                                   platform_state,
                                   instrumentation_digest,
                                   aborted_tuples=None):
    """Derive criteria 30--31 from rescannable worker and process bytes."""
    descriptors = {item["relative_path"]: item for item in worker_sidecars}
    require(len(descriptors) == len(worker_sidecars),
            "D12 threading descriptor inventory")
    aborted_tuples = {} if aborted_tuples is None else aborted_tuples
    tuple_identities = B2.expected_threading_identities(B2.load_manifest())
    raw_summaries = {}
    for key, payload, binding in process_artifact.iter_bindings(
            "d12_instrumented_tsan"):
        raw_summaries[jcs_bytes(key)] = (payload, binding)
    require(len(raw_summaries) == len(tuple_identities) * 2,
            "D12 TSan summary raw coverage")

    def disposition(passing=True, failure_reason=None):
        if platform_state == "UNQUALIFIED_PLATFORM":
            return "INCOMPLETE", "D12_PLATFORM_UNQUALIFIED"
        return (("PASS", None) if passing else ("FAIL", failure_reason))

    def operational_incomplete():
        return (("INCOMPLETE", "D12_PLATFORM_UNQUALIFIED")
                if platform_state == "UNQUALIFIED_PLATFORM" else
                ("INCOMPLETE", "D12_OPERATIONAL_LEDGER_INCOMPLETE"))

    def unavailable_sidecar():
        return {
            "availability": availability(
                "UNAVAILABLE", reason_code="EXECUTION_UNAVAILABLE"),
            "relative_path": None, "byte_length": None,
            "record_count": None, "sha256": None}

    concurrency_records = []
    tsan_records = []
    expected_concurrency_count = 0
    expected_tsan_count = len(tuple_identities) * 2
    for content_id, level, mode, worker_count in tuple_identities:
        cache_mode = ("threaded_cache" if mode ==
                      "SurfaceFactoryCacheThreaded" else mode)
        tuple_key = (content_id, level, cache_mode, worker_count)
        reference = references[(content_id, level)]
        target = {
            "kind": "d12_output_reference_target_v1",
            "provider_expected_sha256": reference["provider"],
            "representation_expected_sha256":
                reference["representation"]}
        summaries = {}
        for quantity in ("instrumentation_coverage",
                         "tsan_finding_count"):
            summary_key = [
                content_id, level, "tsan", cache_mode, worker_count,
                None, None, None, None, None, None, None,
                "sanitizer_summary", quantity]
            summaries[quantity] = raw_summaries.pop(jcs_bytes(summary_key))
        finding_payload = summaries["tsan_finding_count"][0]
        aborted = finding_payload["state"] == "SANITIZER_ABORT"
        require(aborted == (tuple_key in aborted_tuples) and
                (not aborted or aborted_tuples[tuple_key] ==
                 finding_payload["sanitizer_report_sha256"]),
                "D12 worker abort inventory/raw summary drift")
        if cache_mode == "cache_disabled":
            expected_concurrency_count += 20 * worker_count
        else:
            expected_tsan_count += 20 * worker_count
        for round_index in range(20):
            for worker_index in range(worker_count):
                prefix = (
                    "anchored-row-d12-v1/workers/{}/{}/level-{}/"
                    "workers-{}/round-{:02d}/worker-{}".format(
                        cache_mode, content_id, level, worker_count,
                        round_index, worker_index))
                key = [content_id, level, "tsan", cache_mode, worker_count,
                       worker_index, round_index, None, None, None, None,
                       None, "thread_result", "row_digest"]
                if aborted:
                    if cache_mode == "cache_disabled":
                        finding_key = list(key)
                        finding_key[5] = None
                        finding_key[6] = None
                        finding_key[12] = "sanitizer_summary"
                        finding_key[13] = "tsan_finding_count"
                        value = {
                            "kind": "d12_concurrency_abort_v1",
                            "provider_sidecar": unavailable_sidecar(),
                            "representation_sidecar": unavailable_sidecar(),
                            "provider_observed_sha256": None,
                            "provider_expected_sha256": reference["provider"],
                            "representation_observed_sha256": None,
                            "representation_expected_sha256":
                                reference["representation"],
                            "tsan_finding_summary_key": finding_key,
                            "platform_state": platform_state}
                        outcome, reason = disposition(
                            False, "CACHE_DISABLED_RACE")
                    else:
                        value = None
                        outcome, reason = disposition(
                            False, "THREADED_CACHE_RACE")
                else:
                    provider = descriptors[prefix + "-provider.b2rowv1"]
                    representation = descriptors[
                        prefix + "-representation.json"]
                    kind = ("d12_concurrency_value_v1" if cache_mode ==
                            "cache_disabled" else
                            "d12_tsan_threaded_row_value_v1")
                    value = {
                        "kind": kind,
                        "provider_sidecar": copy.deepcopy(provider),
                        "representation_sidecar":
                            copy.deepcopy(representation),
                        "provider_observed_sha256": provider["sha256"],
                        "provider_expected_sha256": reference["provider"],
                        "representation_observed_sha256":
                            representation["sha256"],
                        "representation_expected_sha256":
                            reference["representation"],
                        "platform_state": platform_state}
                    matches = (provider["sha256"] == reference["provider"] and
                               representation["sha256"] ==
                               reference["representation"])
                    outcome, reason = disposition(
                        matches,
                        "CACHE_DISABLED_CONCURRENCY_MISMATCH" if
                        cache_mode == "cache_disabled" else
                        "THREADED_CACHE_OUTPUT_MISMATCH")
                record = [key, outcome, value, copy.deepcopy(target), reason]
                criterion_id = (
                    "d12_cache_disabled_concurrency" if cache_mode ==
                    "cache_disabled" else "d12_instrumented_tsan")
                validate_contract_result_record(criterion_id, record)
                (concurrency_records if cache_mode == "cache_disabled" else
                 tsan_records).append(record)
        for quantity in ("instrumentation_coverage",
                         "tsan_finding_count"):
            key = [content_id, level, "tsan", cache_mode, worker_count,
                   None, None, None, None, None, None, None,
                   "sanitizer_summary", quantity]
            payload, binding = summaries[quantity]
            if quantity == "instrumentation_coverage":
                instrumentation_complete = payload["state"] == "COMPLETE"
                value = {
                    "kind": "d12_tsan_instrumentation_summary_v1",
                    "instrumentation_complete": instrumentation_complete,
                    "instrumented_translation_units_sha256":
                        (instrumentation_digest if instrumentation_complete
                         else None),
                    "expected_translation_units_sha256":
                        instrumentation_digest,
                    "platform_state": platform_state,
                    "raw_observation": binding}
                target_value = {
                    "kind": "d12_tsan_instrumentation_target_v1",
                    "instrumentation_complete": True,
                    "expected_translation_units_sha256":
                        instrumentation_digest}
                outcome, reason = (
                    disposition(True) if instrumentation_complete else
                    operational_incomplete())
            else:
                if payload["state"] == "COMPLETE":
                    finding_count = _canonical_uint64_token(
                        payload["finding_count_token"])
                    sanitizer_abort = False
                    report_digest = None
                    outcome, reason = disposition(
                        finding_count == 0,
                        "CACHE_DISABLED_RACE" if cache_mode ==
                        "cache_disabled" else "THREADED_CACHE_RACE")
                elif payload["state"] == "SANITIZER_ABORT":
                    finding_count = None
                    sanitizer_abort = True
                    report_digest = payload["sanitizer_report_sha256"]
                    outcome, reason = disposition(
                        False, "CACHE_DISABLED_RACE" if cache_mode ==
                        "cache_disabled" else "THREADED_CACHE_RACE")
                else:
                    require(payload["state"] == "EXECUTION_UNAVAILABLE",
                            "D12 finding raw state")
                    finding_count = None
                    sanitizer_abort = False
                    report_digest = None
                    outcome, reason = operational_incomplete()
                value = {
                    "kind": "d12_tsan_finding_summary_v1",
                    "finding_count": finding_count,
                    "sanitizer_abort": sanitizer_abort,
                    "sanitizer_report_sha256": report_digest,
                    "platform_state": platform_state,
                    "raw_observation": binding}
                target_value = {
                    "kind": "d12_tsan_finding_target_v1",
                    "finding_count": 0}
            validate_d12_raw_exact_value(
                payload, value, instrumentation_digest)
            record = [key, outcome, value, target_value, reason]
            validate_contract_result_record(
                "d12_instrumented_tsan", record)
            tsan_records.append(record)
    require(not raw_summaries and
            len(concurrency_records) == expected_concurrency_count and
            len(tsan_records) == expected_tsan_count,
            "D12 threading result coverage")
    result = {}
    serial_context = D12SerialContextVerifier()
    for criterion_id, records in (
            ("d12_cache_disabled_concurrency", concurrency_records),
            ("d12_instrumented_tsan", tsan_records)):
        records.sort(key=lambda record: jcs_bytes(record[0]))
        accumulator = _CategoricalResultAccumulator(
            output_root, criterion_id)
        for record in records:
            accumulator.add(record)
            serial_context.add(criterion_id, record, jcs_bytes(record))
        result[criterion_id] = accumulator.finish()
    return result, serial_context.finish()


def write_d12_opensubdiv_provenance(
        source_root, release_build_root, release_install_root,
        tsan_build_root, tsan_install_root, output_root):
    """Publish the four profile-paired OpenSubdiv provenance manifests."""
    source_root = pathlib.Path(source_root).resolve()
    output_root = pathlib.Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = B2.load_manifest()
    contract = manifest["qualification_platform"]["build"]["opensubdiv"]
    profiles = {}
    for profile_name, b2_profile, build_text, install_text in (
            ("release", "release", release_build_root,
             release_install_root),
            ("tsan", "thread_sanitizer", tsan_build_root,
             tsan_install_root)):
        build_root = pathlib.Path(build_text).resolve()
        install_root = pathlib.Path(install_text).resolve()
        source = _audit_d12_source_checkout(source_root, manifest)
        audit = B2.audit_opensubdiv(
            install_root, build_root, source_root, contract, b2_profile)
        object_ledger = _validate_d12_opensubdiv_object_chain(
            source_root, build_root, install_root, contract, b2_profile)
        header_bindings = _d12_installed_header_bindings(
            source_root, install_root)
        build_packet = {
            "schema_id": "d12-opensubdiv-build-audit-v1",
            "profile": profile_name, "source_root": str(source_root),
            "source": source, "audit": audit,
            "object_archive_ledger": object_ledger}
        build_packet_path = build_root / \
            "d12-opensubdiv-build-audit.json"
        build_packet_path.write_bytes(jcs_bytes(build_packet))
        install_packet = {
            "schema_id": "d12-opensubdiv-install-provenance-v1",
            "profile": profile_name, "install_root": str(install_root),
            "version_header_sha256": sha256_file(
                install_root / "include/opensubdiv/version.h"),
            "install_manifest_sha256": audit["provenance_artifacts"][
                "install_manifest"]["sha256"],
            "archive_sha256": audit["archive_sha256"]}
        install_packet_path = install_root / \
            "d12-opensubdiv-install-provenance.json"
        install_packet_path.write_bytes(jcs_bytes(install_packet))
        link_packet = {
            "schema_id": "d12-opensubdiv-link-provenance-v1",
            "profile": profile_name, "build_root": str(build_root),
            "archive_sha256": audit["archive_sha256"],
            "raw_archive_members": audit["raw_archive_members"],
            "link_command_sha256": audit["provenance_artifacts"][
                "link_command"]["sha256"]}
        link_packet_path = build_root / \
            "d12-opensubdiv-link-provenance.json"
        link_packet_path.write_bytes(jcs_bytes(link_packet))
        profiles[profile_name] = {
            "build_root": str(build_root),
            "install_root": str(install_root),
            "build_root_provenance": str(build_packet_path),
            "install_provenance": str(install_packet_path),
            "link_provenance": str(link_packet_path),
            "installed_library": str(
                install_root / "lib/libosdCPU.a"),
            "object_ledger": object_ledger,
            "installed_header_bindings": header_bindings}

    field_roots = {
        "build_root_provenance": "build_root",
        "install_provenance": "install_root",
        "link_provenance": "build_root",
        "installed_library": "install_root"}
    manifests = {}
    for field, root_field in field_roots.items():
        value = {
            "schema_id": "d12-opensubdiv-profile-artifacts-v1",
            "field": field}
        for profile_name in ("release", "tsan"):
            artifact_path = pathlib.Path(
                profiles[profile_name][field]).resolve()
            value[profile_name] = {
                "root": profiles[profile_name][root_field],
                "artifact_path": str(artifact_path),
                "sha256": sha256_file(artifact_path)}
        path = output_root / (
            "d12-opensubdiv-{}-profiles.json".format(
                field.replace("_", "-")))
        path.write_bytes(jcs_bytes(value))
        manifests[field] = str(path)

    release_projection = {
        (item["source_relative_path"], item["sha256"])
        for item in profiles["release"]["installed_header_bindings"].values()}
    tsan_projection = {
        (item["source_relative_path"], item["sha256"])
        for item in profiles["tsan"]["installed_header_bindings"].values()}
    require(release_projection == tsan_projection,
            "D12 generated OpenSubdiv installed-header profiles differ")
    return {"profiles": profiles, "manifests": manifests}


def d12_platform_from_b2_evidence(value):
    """Derive the closed D12 platform object from validated B2 probes."""
    B2.validate_evidence_document(value)
    manifest = B2.load_manifest()
    expected = manifest["qualification_platform"]["fingerprint"]
    qualification = value["platform_qualification"]
    probe = qualification["current_probe"]
    observed = probe.get("fingerprint")
    require(isinstance(observed, dict) and set(observed) == set(expected),
            "D12 observed platform fingerprint is incomplete")
    numeric_cases = value["execution"]["numeric_cases"]
    expected_identities = B2.expected_numeric_case_identities(manifest)
    require(len(numeric_cases) == len(expected_identities),
            "D12 platform case coverage")
    observations = []
    for case, identity in zip(numeric_cases, expected_identities):
        require((case["content_identity_key"], case["candidate"],
                 case["approximation_level"], case["applicable_mode"]) ==
                identity,
                "D12 platform case identity/order drift")
        samples = case.get("platform_boundary_samples")
        require(isinstance(samples, list) and len(samples) == 4,
                "D12 platform boundary sample coverage")
        for sample, boundary in zip(samples, (
                "primary_before", "primary_after",
                "determinism_before", "determinism_after")):
            require(sample.get("boundary") == boundary,
                    "D12 platform boundary order drift")
            observations.append(_d12_observation_record(
                identity, boundary, sample["probe"]))
    github_hosted = qualification["github_hosted"] is True
    platform = {
        "platform_state": (
            "QUALIFIED_PLATFORM" if qualification["status"] == "QUALIFIED"
            else "UNQUALIFIED_PLATFORM"),
        "expected_fingerprint": copy.deepcopy(expected),
        "observed_fingerprint": copy.deepcopy(observed),
        "field_mismatches": sorted(
            key for key in expected if observed[key] != expected[key]),
        "compiler_identity": manifest["qualification_platform"]["build"][
            "compiler_version"],
        "github_hosted": github_hosted,
        "virtualization_observation": {
            "kern_hv_vmm_present": observed["kern_hv_vmm_present"],
            "shared_host_evidence": github_hosted or
                observed["kern_hv_vmm_present"] != 0},
        "power_thermal_observations": observations}
    validate_contract_value("d12_platform", platform)
    return platform


def _d12_binary_evidence(binary_path, command_path, link_map_path,
                         dynamic_path, source_role):
    binary = pathlib.Path(binary_path).resolve()
    command = pathlib.Path(command_path).resolve()
    link_map = pathlib.Path(link_map_path).resolve()
    dynamic = pathlib.Path(dynamic_path).resolve()
    require(all(path.is_file() for path in (
                binary, command, link_map, dynamic)),
            "D12 binary/provenance path is unavailable")
    digest = sha256_file(binary)
    value = {
        "availability": availability("PRESENT", digest),
        "sha256": digest,
        "compiler_command_sha256": sha256_file(command),
        "link_map_sha256": sha256_file(link_map),
        "dynamic_dependency_sha256": sha256_file(dynamic),
        "source_inventory": sorted(({
            "path": path, "sha256": sha256_file(ROOT / path)}
            for path in RUNTIME_SOURCE_PATHS[source_role]),
            key=jcs_bytes)}
    validate_contract_value("d12_binary", value)
    return value


def _d12_dependency_evidence(version, archive_path, build_path,
                             install_path, link_path, library_path):
    paths = [pathlib.Path(path).resolve() for path in (
        archive_path, build_path, install_path, link_path, library_path)]
    require(all(path.is_file() for path in paths),
            "D12 dependency provenance path is unavailable")
    return {
        "version": version, "archive_sha256": sha256_file(paths[0]),
        "source_identity": version,
        "build_root_provenance_sha256": sha256_file(paths[1]),
        "install_provenance_sha256": sha256_file(paths[2]),
        "link_provenance_sha256": sha256_file(paths[3]),
        "installed_library_sha256": sha256_file(paths[4])}


def _d12_build_profile(profile_name, command_manifest_path):
    build = B2.load_manifest()["qualification_platform"]["build"]
    commands = _read_command_profile(command_manifest_path)
    flags = (build["common_release_compile_flags"]
             if profile_name == "release" else
             build["thread_sanitizer_compile_flags"])
    value = {
        "compiler_path": build["compiler_path"],
        "compiler_version": build["compiler_version"],
        "flags": copy.deepcopy(flags),
        "sdk_path": build["macos_sdk_path"],
        "sdk_version": build["macos_sdk_version"],
        "cmake_path": build["opensubdiv"]["cmake"]["path"],
        "cmake_version": build["opensubdiv"]["cmake"]["version"],
        "make_path": build["opensubdiv"]["build_tool"]["path"],
        "make_version": build["opensubdiv"]["build_tool"]["version"],
        "compile_commands": commands["compile_commands"],
        "link_commands": commands["link_commands"]}
    validate_contract_value("d12_build_profile", value)
    return value


def _d12_instrumentation_digest(binaries, build_profiles,
                                opensubdiv_provenance):
    proof_units = []
    for index, binary_name in enumerate((
            "provider_tsan", "representation_tsan")):
        source = next(item for item in binaries[binary_name][
            "source_inventory"] if item["path"].endswith(".cpp"))
        proof_units.append({
            "binary": binary_name, "source": source,
            "binary_sha256": binaries[binary_name]["sha256"],
            "compile_command": build_profiles["tsan"][
                "compile_commands"][index]})
    ledger = {
        "schema_id": "d12-instrumented-translation-unit-ledger-v1",
        "proof_translation_units": proof_units,
        "opensubdiv_translation_units": opensubdiv_provenance[
            "profiles"]["tsan"]["object_ledger"],
        "opensubdiv_installed_headers": opensubdiv_provenance[
            "profiles"]["tsan"]["installed_header_bindings"]}
    return sha256_bytes(jcs_bytes(ledger))


def produce_d12_evidence(args):
    """Execute and publish the complete closed Package-2 D12 envelope."""
    git_start, worktree_start = git_observations()
    expected_head = args.expected_binding_head or git_start.get("git_commit")
    require(git_start.get("state") == "PRESENT" and
            git_start.get("git_commit") == expected_head and
            worktree_start == {"state": "PRESENT", "clean": True},
            "D12 production requires exact clean Git HEAD")
    checkpoint_path = pathlib.Path(args.checkpoint).resolve()
    artifact_root = pathlib.Path(args.artifact_dir).resolve()
    checkpoint = strict_json_bytes(checkpoint_path.read_bytes())
    require(checkpoint.get("schema_version") == 2 and
            checkpoint.get("kind") == "bfr_release_matrix_checkpoint" and
            checkpoint.get("complete") is True and
            checkpoint.get("binding", {}).get("git_head") == expected_head,
            "D12 production checkpoint/head binding")
    b2_evidence = strict_json_bytes(
        pathlib.Path(args.b2_evidence).resolve().read_bytes())
    platform = d12_platform_from_b2_evidence(b2_evidence)
    require(b2_evidence["execution"]["numeric_cases"] ==
            checkpoint["numeric_cases"],
            "D12 B2 evidence/checkpoint case drift")
    output_path = pathlib.Path(args.output).resolve()
    output_root = output_path.parent
    output_root.mkdir(parents=True, exist_ok=True)

    opensubdiv = write_d12_opensubdiv_provenance(
        args.opensubdiv_source_root,
        args.opensubdiv_release_build_root,
        args.opensubdiv_release_install_root,
        args.opensubdiv_tsan_build_root,
        args.opensubdiv_tsan_install_root,
        output_root / "d12-provenance")
    build_profiles = {
        "release": _d12_build_profile(
            "release", args.provider_command_file),
        "tsan": _d12_build_profile(
            "tsan", args.provider_tsan_command_file)}
    require(_read_command_profile(args.candidate_command_file) ==
                _read_command_profile(args.provider_command_file) and
            _read_command_profile(args.representation_tsan_command_file) ==
                _read_command_profile(args.provider_tsan_command_file),
            "D12 binary roles do not share exact profile command authority")
    binaries = {
        "provider_release": _d12_binary_evidence(
            args.provider_binary, args.provider_command_file,
            args.provider_link_map, args.provider_dynamic_dependencies,
            "row_provider"),
        "provider_tsan": _d12_binary_evidence(
            args.provider_tsan_binary, args.provider_tsan_command_file,
            args.provider_tsan_link_map,
            args.provider_tsan_dynamic_dependencies, "row_provider"),
        "representation_release": _d12_binary_evidence(
            args.candidate_binary, args.candidate_command_file,
            args.candidate_link_map, args.candidate_dynamic_dependencies,
            "representation_candidate"),
        "representation_tsan": _d12_binary_evidence(
            args.representation_tsan_binary,
            args.representation_tsan_command_file,
            args.representation_tsan_link_map,
            args.representation_tsan_dynamic_dependencies,
            "representation_candidate")}
    dependencies = {
        "gmp": _d12_dependency_evidence(
            "6.3.0", args.gmp_archive, args.gmp_build_provenance,
            args.gmp_install_provenance, args.gmp_link_provenance,
            args.gmp_installed_library),
        "mpfr": _d12_dependency_evidence(
            "4.2.2", args.mpfr_archive, args.mpfr_build_provenance,
            args.mpfr_install_provenance, args.mpfr_link_provenance,
            args.mpfr_installed_library),
        "opensubdiv": _d12_dependency_evidence(
            "3.7.0", args.opensubdiv_archive,
            opensubdiv["manifests"]["build_root_provenance"],
            opensubdiv["manifests"]["install_provenance"],
            opensubdiv["manifests"]["link_provenance"],
            opensubdiv["manifests"]["installed_library"])}
    instrumentation_digest = _d12_instrumentation_digest(
        binaries, build_profiles, opensubdiv)

    process_artifact = D12ProcessObservationArtifact(
        output_root, {
            binaries["provider_tsan"]["sha256"],
            binaries["representation_tsan"]["sha256"]})
    try:
        for criterion_id, record in iter_d12_numeric_observations(
                checkpoint, artifact_root):
            process_artifact.add(criterion_id, record)
        references_descriptors, references = write_d12_serial_references(
            checkpoint, artifact_root, output_root)
        with tempfile.TemporaryDirectory(
                prefix="anchored-row-d12-runtime-snapshot-") as snapshot:
            worker_paths = {}
            for role, original_text in (
                    ("provider_tsan", args.provider_tsan_binary),
                    ("representation_tsan", args.representation_tsan_binary)):
                original = pathlib.Path(original_text).resolve()
                destination = pathlib.Path(snapshot) / role
                digest = sha256_file(original)
                shutil.copyfile(str(original), str(destination))
                destination.chmod(0o500)
                require(sha256_file(original) == digest ==
                            sha256_file(destination) == binaries[role]["sha256"],
                        "D12 runtime executable changed while snapshotting")
                worker_paths[role] = str(destination)
            worker_sidecars, worker_aborts = execute_d12_worker_streams(
                worker_paths["provider_tsan"],
                worker_paths["representation_tsan"], checkpoint,
                output_root, references, process_artifact,
                instrumentation_digest)
            require(sha256_file(pathlib.Path(
                        args.provider_tsan_binary).resolve()) ==
                        binaries["provider_tsan"]["sha256"] and
                    sha256_file(pathlib.Path(
                        args.representation_tsan_binary).resolve()) ==
                        binaries["representation_tsan"]["sha256"],
                    "D12 runtime executable identity changed during execution")
        request_paths = {
            pathlib.Path(reference["request_path"]).resolve()
            for reference in references.values()}
        require(len(request_paths) == 98 and all(
                    path.parent == output_root /
                        "anchored-row-d12-v1/requests"
                    for path in request_paths),
                "D12 representation request inventory drift")
        for path in request_paths:
            path.unlink()
        (output_root / "anchored-row-d12-v1/requests").rmdir()
        process_descriptor = process_artifact.finish(4189640)
        executed = execute_d12_numeric_criteria(
            process_artifact, output_root, platform["platform_state"])
        threading, serial_context = execute_d12_threading_criteria(
            worker_sidecars, references, process_artifact, output_root,
            platform["platform_state"], instrumentation_digest,
            worker_aborts)
        executed.update(threading)
    finally:
        process_artifact.close()
    expected_ledgers = make_d12_pre_result_ledgers(
        checkpoint, artifact_root, B2.load_manifest())
    require(set(executed) == set(D12_CRITERIA) and
            all(executed[criterion_id]["observed_count"] ==
                    expected_ledgers[criterion_id]["count"] and
                executed[criterion_id]["digest"] ==
                    expected_ledgers[criterion_id]["digest"]
                for criterion_id in D12_CRITERIA),
            "D12 executed result/pre-result universe drift")
    criteria = [executed_criterion_record(criterion_id,
                                          executed[criterion_id])
                for criterion_id in D12_CRITERIA]
    envelope = {
        "schema_id": "anchored-row-representation-d12-v1",
        "content_sha256": ZERO_SHA256,
        "candidate": CANDIDATE,
        "git": {"head": expected_head, "head_query_ok": True,
                "worktree_clean": True},
        "binaries": binaries, "dependencies": dependencies,
        "build_profiles": build_profiles, "platform": platform,
        "authority": frozen_authority_record(),
        "workload": {
            "workload_id": "anchored-difference-v1-d12-workload-v1",
            "construction_and_evaluation_included": True,
            "input_ids": ["fixture_x", "fixture_y", "fixture_z",
                          "positive_zero", "positive_one", "negative_one",
                          "positive_2p20", "negative_2p20"],
            "provider_serial_reference": references_descriptors[
                "provider_serial_reference"],
            "representation_serial_reference": references_descriptors[
                "representation_serial_reference"],
            "process_observation_sidecar": process_descriptor,
            "sidecars": worker_sidecars},
        "criteria": criteria, "serial_only_context": serial_context}
    envelope["content_sha256"] = sha256_bytes(jcs_bytes(envelope))
    validate_d12_envelope_contract(envelope, expected_head)
    runtime_provenance = {
        "binaries": {
            "provider_release": {
                "compiler_command": args.provider_command_file,
                "link_map": args.provider_link_map,
                "dynamic_dependencies": args.provider_dynamic_dependencies},
            "provider_tsan": {
                "compiler_command": args.provider_tsan_command_file,
                "link_map": args.provider_tsan_link_map,
                "dynamic_dependencies":
                    args.provider_tsan_dynamic_dependencies},
            "representation_release": {
                "compiler_command": args.candidate_command_file,
                "link_map": args.candidate_link_map,
                "dynamic_dependencies": args.candidate_dynamic_dependencies},
            "representation_tsan": {
                "compiler_command": args.representation_tsan_command_file,
                "link_map": args.representation_tsan_link_map,
                "dynamic_dependencies":
                    args.representation_tsan_dynamic_dependencies}},
        "dependencies": {
            "gmp": {"archive": args.gmp_archive,
                    "build_root_provenance": args.gmp_build_provenance,
                    "install_provenance": args.gmp_install_provenance,
                    "link_provenance": args.gmp_link_provenance,
                    "installed_library": args.gmp_installed_library},
            "mpfr": {"archive": args.mpfr_archive,
                     "build_root_provenance": args.mpfr_build_provenance,
                     "install_provenance": args.mpfr_install_provenance,
                     "link_provenance": args.mpfr_link_provenance,
                     "installed_library": args.mpfr_installed_library},
            "opensubdiv": {
                "archive": args.opensubdiv_archive,
                "build_root_provenance": opensubdiv["manifests"][
                    "build_root_provenance"],
                "install_provenance": opensubdiv["manifests"][
                    "install_provenance"],
                "link_provenance": opensubdiv["manifests"][
                    "link_provenance"],
                "installed_library": opensubdiv["manifests"][
                    "installed_library"]}}}
    audit = _validate_d12_runtime_provenance(
        envelope, {"binaries": {
            "row_provider": {"sources": binaries[
                "provider_release"]["source_inventory"]},
            "representation_candidate": {"sources": binaries[
                "representation_release"]["source_inventory"]}}},
        runtime_provenance, {
            "provider_release": args.provider_binary,
            "provider_tsan": args.provider_tsan_binary,
            "representation_release": args.candidate_binary,
            "representation_tsan": args.representation_tsan_binary})
    require(audit["instrumented_translation_units_sha256"] ==
            instrumentation_digest,
            "D12 runtime instrumentation audit drift")
    git_end, worktree_end = git_observations()
    require_git_binding(git_start, git_end, worktree_start, worktree_end,
                        expected_head, expected_head)
    output_path.write_bytes(jcs_bytes(envelope))
    return envelope


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
                                     executed, scientific=None,
                                     oracle_partitions=None):
    """Bind every frozen key set without inventing post-oracle partitions."""
    candidate = make_candidate_pre_result_ledgers(
        checkpoint, artifact_root)
    if scientific is None:
        scientific = make_scientific_pre_result_ledgers(
            checkpoint, artifact_root, manifest)
    d12 = make_d12_pre_result_ledgers(
        checkpoint, artifact_root, manifest)
    generated = dict(candidate)
    generated.update(scientific)
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
            records.extend(oracle_partitions or
                           oracle_unavailable_partition_ledgers(
                               "oracle_coverage_and_crosscheck"))
    require(len(records) == 34, "complete pre-result ledger partition count")
    return records


def validate_oracle_sample_observation(
        value, oracle_certification_authority=None):
    """Validate one independent-oracle batch value before persistence."""
    require(isinstance(value, dict) and
            value.get("kind") == "stam_oracle_sample_v1" and
            value.get("status") in {"ok", "uncovered"},
            "oracle batch observation shape")
    if value["status"] == "ok":
        require(oracle_certification_authority is
                _ORACLE_CERTIFICATION_AUTHORITY,
                "covered oracle observation lacks authenticated certificate "
                "execution context")
        require(set(value) == {"schema_version", "kind", "status", "rows"} and
                value["schema_version"] == 1 and
                [item.get("row_kind") for item in value["rows"]] ==
                    list(ROW_ORDER),
                "covered oracle sample shape")
        for exact_value in value["rows"]:
            require(_contract_kind(exact_value) ==
                    "oracle_covered_value_v1",
                    "covered oracle exact-value kind")
            validate_contract_value("oracle_covered_value_v1", exact_value)
    else:
        require(set(value) == {"schema_version", "kind", "status",
                               "reason_code"} and
                value["schema_version"] == 1 and
                value["reason_code"] in ORACLE_UNCOVERED_REASONS,
                "uncovered oracle sample shape")
    return value


ORACLE_EXECUTION_AUDIT_PATH = \
    "anchored-row-oracle-execution-audit-v1.json"
ORACLE_EXECUTION_REQUEST_COUNT = 16500


def _oracle_execution_audit_record(request, request_id, raw_value, value):
    encoded_request = (request.encode("utf-8")
                       if isinstance(request, str) else request)
    require(isinstance(encoded_request, bytes) and
            encoded_request.endswith(b"\n"),
            "oracle execution audit request framing")
    return [request_id, sha256_bytes(encoded_request), value["status"],
            None if value["status"] == "ok" else value["reason_code"],
            sha256_bytes(raw_value)]


class OracleExecutionAuditArtifact:
    """Persist the exact unique-request framing/outcome stream."""

    def __init__(self, output_root=None):
        self.destination = (None if output_root is None else
                            pathlib.Path(output_root) /
                            ORACLE_EXECUTION_AUDIT_PATH)
        self.stream = (None if self.destination is None else
                       self.destination.open("wb"))
        self.digest = hashlib.sha256()
        self.byte_length = 0
        self.count = 0
        self._append(b"[")

    def _append(self, value):
        self.digest.update(value)
        self.byte_length += len(value)
        if self.stream is not None:
            self.stream.write(value)

    def add(self, request, request_id, raw_value, value):
        require(self.count < ORACLE_EXECUTION_REQUEST_COUNT,
                "oracle execution audit exceeds frozen request count")
        encoded = jcs_bytes(_oracle_execution_audit_record(
            request, request_id, raw_value, value))
        if self.count:
            self._append(b",")
        self._append(encoded)
        self.count += 1

    def finish(self):
        self._append(b"]")
        require(self.count == ORACLE_EXECUTION_REQUEST_COUNT,
                "oracle execution audit request count drift")
        if self.stream is not None:
            self.stream.close()
            require(self.destination.is_file() and
                    self.destination.stat().st_size == self.byte_length and
                    sha256_file(self.destination) == self.digest.hexdigest(),
                    "oracle execution audit persisted bytes drift")
        return {"relative_path": ORACLE_EXECUTION_AUDIT_PATH,
                "record_count": self.count,
                "byte_length": self.byte_length,
                "sha256": self.digest.hexdigest()}


def iter_oracle_batch_observations(oracle_binary, request_rows,
                                   expected_request_ids, timeout=7200,
                                   runtime_library_root=None,
                                   runtime_library_bindings=None):
    """Stream strict, ordinal-bound oracle values without a second spool."""
    require(isinstance(request_rows, (list, tuple)) and
            isinstance(expected_request_ids, (list, tuple)) and
            len(request_rows) == len(expected_request_ids) and
            len(set(expected_request_ids)) == len(expected_request_ids),
            "oracle batch request inventory")
    stderr_file = tempfile.TemporaryFile()
    environment = _d12_rebuild_environment()
    if runtime_library_root is not None:
        library_root = pathlib.Path(runtime_library_root).resolve()
        require(library_root.is_dir(),
                "oracle runtime library snapshot unavailable")
        environment["DYLD_LIBRARY_PATH"] = str(library_root)
    runtime_library_bindings = runtime_library_bindings or ()

    def require_runtime_libraries():
        require(all(pathlib.Path(path).resolve().is_file() and
                    sha256_file(pathlib.Path(path).resolve()) == digest
                    for path, digest in runtime_library_bindings),
                "oracle runtime dependency identity changed at process "
                "boundary")

    require_runtime_libraries()
    process = subprocess.Popen(
        [str(pathlib.Path(oracle_binary).resolve()), "--batch"],
        cwd=str(ROOT), env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr_file,
        start_new_session=True)
    require_runtime_libraries()
    require(process.stdin is not None and process.stdout is not None,
            "oracle batch pipes unavailable")
    feeder_errors = []
    timed_out = []

    def feed():
        try:
            for request in request_rows:
                encoded = (request.encode("utf-8") if
                           isinstance(request, str) else request)
                require(isinstance(encoded, bytes) and
                        encoded.endswith(b"\n") and
                        encoded.count(b"\t") == 6,
                        "oracle batch request framing")
                process.stdin.write(encoded)
            process.stdin.close()
        except BaseException as error:
            feeder_errors.append(error)
            try:
                process.stdin.close()
            except OSError:
                pass

    def expire():
        timed_out.append(True)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass

    feeder = threading.Thread(target=feed, name="oracle-batch-input")
    timer = threading.Timer(timeout, expire)
    feeder.start()
    timer.start()
    try:
        for expected_request_id in expected_request_ids:
            raw_line = process.stdout.readline(MAX_RESULT_RECORD_BYTES + 2)
            require(raw_line.endswith(b"\n") and
                    len(raw_line) <= MAX_RESULT_RECORD_BYTES + 1 and
                    raw_line.count(b"\t") == 1,
                    "oracle batch output framing")
            request_id_bytes, raw_value = raw_line[:-1].split(b"\t", 1)
            try:
                request_id = request_id_bytes.decode("ascii")
            except UnicodeDecodeError as error:
                raise QualificationError(
                    "oracle batch output identity encoding") from error
            require(request_id == expected_request_id,
                    "oracle batch output ordinal/identity drift")
            value = validate_oracle_sample_observation(
                strict_json_bytes(raw_value),
                _ORACLE_CERTIFICATION_AUTHORITY)
            # The oracle owns only observations, not authoritative result
            # bytes.  Canonicalize the already closed/validated value before
            # it enters the runner-owned persistence boundary.
            yield request_id, jcs_bytes(value), value
        require(process.stdout.read(1) == b"",
                "oracle batch output trailing record")
        feeder.join(timeout=5)
        require(not feeder.is_alive(), "oracle batch input timed out")
        returncode = process.wait(timeout=5)
        stderr_file.seek(0)
        stderr = stderr_file.read().decode("utf-8", errors="replace")
        require(not timed_out, "oracle batch execution timed out")
        require(not feeder_errors,
                "oracle batch input failure: {}".format(
                    feeder_errors[0] if feeder_errors else ""))
        require(returncode == 0,
                "oracle batch failed: {}".format(stderr.strip()))
    finally:
        timer.cancel()
        if feeder.is_alive() or process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        if process.stdin is not None and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
        feeder.join(timeout=5)
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise QualificationError(
                "oracle batch process group did not terminate") from error
        process.stdout.close()
        stderr_file.close()
        require_runtime_libraries()


def oracle_dependent_key(criterion_id, oracle_key, axis=None):
    require(criterion_id in ORACLE_DEPENDENT_CRITERIA and
            isinstance(oracle_key, list) and len(oracle_key) == 15,
            "oracle-dependent key projection")
    expected_axis = criterion_id in {
        "exact_effective_d10_geometry", "emitted_direct_geometry_d10"}
    require((axis is not None) == expected_axis and
            (axis is None or axis in ("x", "y", "z")),
            "oracle-dependent key axis")
    view = ("emitted_binary64" if criterion_id ==
            "emitted_direct_geometry_d10" else "exact_effective")
    key = list(oracle_key[:7]) + [view, oracle_key[8], "identity", None,
                                  axis, None, None, None]
    validate_scientific_cell_key(key, criterion_id)
    require(oracle_request_key_for_dependent_key(criterion_id, key) ==
            oracle_key,
            "oracle-dependent inverse key projection")
    return key


class _NumericResultAccumulator:
    """Persist one numeric criterion with an exact maximum witness."""

    def __init__(self, output_root, criterion_id):
        require(criterion_id in RESULT_CONTRACT.CRITERION_BY_ID and
                RESULT_CONTRACT.CRITERION_BY_ID[criterion_id][
                    "maximum_field"] is not None,
                "numeric result accumulator criterion")
        self.criterion_id = criterion_id
        self.writer = StreamingResultLedgerArtifact(output_root, criterion_id)
        self.failure_count = 0
        self.first_failure = None
        self.maximum = None
        self.maximum_record = None
        self.maximum_index = None
        self.uncovered_count = 0
        self.incomplete_count = 0

    def add(self, record):
        outcome = record[1]
        if outcome == "FAIL":
            self.failure_count += 1
            if self.first_failure is None:
                self.first_failure = copy.deepcopy(record[0])
        if outcome == "UNCOVERED":
            self.uncovered_count += 1
        else:
            if outcome == "INCOMPLETE":
                self.incomplete_count += 1
            measure = _record_measure_descriptor(
                self.criterion_id, record[2])
            if (self.maximum is None or
                    _measure_squared(measure) >
                    _measure_squared(self.maximum)):
                self.maximum = copy.deepcopy(measure)
                self.maximum_record = copy.deepcopy(record)
                self.maximum_index = self.writer.count
        self.writer.add(record)

    def finish(self):
        expected = EXPECTED_CELL_COUNTS[self.criterion_id]
        require(self.writer.count == expected,
                "{} result cardinality".format(self.criterion_id))
        commitment, artifact = self.writer.finish(
            witness_index=self.maximum_index)
        status = ("FAIL" if self.failure_count else
                  "INCOMPLETE" if self.incomplete_count else
                  "UNCOVERED" if self.uncovered_count else "PASS")
        witness = None
        if self.maximum is not None:
            witness = {
                "cell_key": self.maximum_record[0],
                "result_record": self.maximum_record,
                "leaf_index": self.maximum_index,
                "merkle_siblings": commitment["witness_siblings"],
                "maximum_exact": self.maximum,
                "maximum_binary64_bits": _exact_display_bits(self.maximum),
            }
            validate_contract_value("maximum_witness", witness)
            validate_result_merkle_witness(
                jcs_bytes(self.maximum_record), self.maximum_index,
                commitment["witness_siblings"],
                commitment["result_merkle_root_sha256"],
                observed_count=expected)
        return {
            "digest": commitment["key_ledger_sha256"],
            "result_digest": commitment["result_ledger_sha256"],
            "result_merkle_root": commitment[
                "result_merkle_root_sha256"],
            "result_artifact": artifact,
            "observed_count": expected,
            "failure_count": self.failure_count,
            "first_failing_key": self.first_failure,
            "maximum": self.maximum,
            "witness": witness,
            "status": status,
            "target": report_criterion_target(self.criterion_id),
            "expectation": RESULT_CONTRACT.CRITERION_BY_ID[
                self.criterion_id]["expectation"],
        }


# Compatibility name retained for the focused oracle-boundary probes.
_OracleNumericResultAccumulator = _NumericResultAccumulator


def candidate_emitted_geometry_line(row, anchor_source, fixture, axis):
    """Encode one observation-only direct-geometry candidate request."""
    require(axis in ("x", "y", "z") and
            anchor_source in row["source_ids"],
            "candidate emitted-geometry request identity")
    axis_index = ("x", "y", "z").index(axis)
    source_ids = row["source_ids"]
    coefficients = row["coefficients"]
    require(len(coefficients) == len(source_ids) and source_ids,
            "candidate emitted-geometry request cardinality")
    return "{} {} {} {} {}\n".format(
        axis, row["row_kind"], source_ids.index(anchor_source),
        ",".join(binary64_bits_hex(value) for value in coefficients),
        ",".join(binary64_bits_hex(
            fixture["vertices"][source_id][axis_index])
                 for source_id in source_ids))


def _iter_oracle_geometry_cells(cases, artifact_root, fixtures,
                                request_ids, database_path):
    """Replay exact criterion-13 order from the persisted oracle spool."""
    connection = sqlite3.connect(str(database_path))
    try:
        suffixes = _frozen_scientific_suffixes()[
            "oracle_coverage_and_crosscheck"]
        cached_request_id = None
        cached_value = None
        for case in cases:
            report = _artifact_report(artifact_root, case)
            fixture = fixtures[case["content_identity_key"]]
            for row in ordered_case_rows(report):
                sample_key = (case["content_identity_key"], row["face_row"],
                              row["local_corner_or_none"], row["sample_id"],
                              row["u_binary64_bits_hex"],
                              row["v_binary64_bits_hex"])
                request_id = request_ids[sample_key]
                if request_id != cached_request_id:
                    fetched = connection.execute(
                        "SELECT value FROM observations WHERE request_id=?",
                        (request_id,)).fetchone()
                    require(fetched is not None,
                            "oracle geometry observation lookup")
                    cached_value = strict_json_bytes(bytes(fetched[0]))
                    cached_request_id = request_id
                exact_value = (cached_value["rows"][
                    ROW_ORDER.index(row["row_kind"])]
                    if cached_value["status"] == "ok" else None)
                reason = (None if exact_value is not None else
                          cached_value["reason_code"])
                prefix = scientific_base_prefix(case, row)
                for suffix in suffixes:
                    oracle_key = strict_json_bytes(prefix + suffix)
                    anchor_name = oracle_key[8]
                    anchor_source = fixture["faces"][row["face_row"]][
                        ANCHORS.index(anchor_name)]
                    for axis_index, axis in enumerate(("x", "y", "z")):
                        yield (row, fixture, oracle_key, anchor_source,
                               exact_value, reason, axis_index, axis)
    finally:
        connection.close()


def _oracle_execution_inventory(checkpoint, artifact_root, manifest):
    """Derive the one-per-sample oracle batch and repeated result ordering."""
    jobs = {job["content_identity_key"]: job
            for job in B2.valid_content_jobs(manifest)}
    require(len(jobs) == 14, "oracle fixture job inventory")
    samples = {}
    cases = [case for case in ordered_bfr_cases(checkpoint)
             if case["approximation_level"] in (7, 8)]
    for case in cases:
        report = _artifact_report(artifact_root, case)
        for row in ordered_case_rows(report):
            sample_key = (case["content_identity_key"], row["face_row"],
                          row["local_corner_or_none"], row["sample_id"],
                          row["u_binary64_bits_hex"],
                          row["v_binary64_bits_hex"])
            samples.setdefault(sample_key, None)
    ordered_samples = sorted(samples, key=lambda item: jcs_bytes(list(item)))
    require(len(ordered_samples) == ORACLE_EXECUTION_REQUEST_COUNT,
            "oracle unique frozen request cardinality drift")
    request_rows = []
    expected_request_ids = []
    request_ids = {}
    for sample_key in ordered_samples:
        content_id, face, corner, _, u_bits, v_bits = sample_key
        job = jobs[content_id]
        fields = [sha256_bytes(jcs_bytes(list(sample_key))),
                  str(pathlib.Path(job["mesh_path"]).resolve()),
                  job["mutation"], str(face), str(corner), u_bits, v_bits]
        require(all("\t" not in field and "\n" not in field
                    for field in fields), "oracle batch field delimiter")
        request_ids[sample_key] = fields[0]
        expected_request_ids.append(fields[0])
        request_rows.append("\t".join(fields) + "\n")
    return (cases, request_rows, expected_request_ids, request_ids)


def _iter_replayed_oracle_result_records(
        checkpoint, artifact_root, manifest, oracle_binary,
        dynamic_dependencies_path):
    """Re-execute the authenticated oracle and derive criterion-10 records.

    Standalone result validation uses this path before granting covered-row
    certification authority.  A self-consistent result sidecar therefore
    cannot substitute literal CERTIFIED strings for executable evidence.
    """
    cases, request_rows, expected_ids, request_ids = \
        _oracle_execution_inventory(checkpoint, artifact_root, manifest)
    database_file = tempfile.NamedTemporaryFile(
        prefix="anchored-oracle-replay-", suffix=".sqlite3", delete=False)
    database_path = pathlib.Path(database_file.name)
    database_file.close()
    library_snapshot = tempfile.TemporaryDirectory(
        prefix="anchored-oracle-replay-libraries-")
    library_root = pathlib.Path(library_snapshot.name) / "lib"
    connection = None
    expected_execution_audit = _bound_oracle_execution_audit(
        dynamic_dependencies_path)
    replayed_execution_audit = OracleExecutionAuditArtifact()
    try:
        runtime_bindings = _snapshot_oracle_runtime_libraries(
            dynamic_dependencies_path, library_root)
        connection = sqlite3.connect(str(database_path))
        connection.execute("CREATE TABLE observations "
                           "(request_id TEXT PRIMARY KEY, value BLOB NOT NULL)")
        observed = 0
        for request_id, raw_value, value in iter_oracle_batch_observations(
                oracle_binary, request_rows, expected_ids,
                runtime_library_root=library_root,
                runtime_library_bindings=[
                    (destination, digest)
                    for _, digest, destination in runtime_bindings]):
            replayed_execution_audit.add(
                request_rows[observed],request_id,raw_value,value)
            connection.execute("INSERT INTO observations VALUES (?, ?)",
                               (request_id, raw_value))
            observed += 1
        connection.commit()
        require(observed == len(expected_ids),
                "oracle replay output cardinality")
        require(replayed_execution_audit.finish() == expected_execution_audit,
                "oracle executable replay differs from execution audit")
        suffixes = _frozen_scientific_suffixes()[
            "oracle_coverage_and_crosscheck"]
        cached_request_id = None
        cached_value = None
        for case in cases:
            report = _artifact_report(artifact_root, case)
            for row in ordered_case_rows(report):
                sample_key = (case["content_identity_key"], row["face_row"],
                              row["local_corner_or_none"], row["sample_id"],
                              row["u_binary64_bits_hex"],
                              row["v_binary64_bits_hex"])
                request_id = request_ids[sample_key]
                if request_id != cached_request_id:
                    fetched = connection.execute(
                        "SELECT value FROM observations WHERE request_id=?",
                        (request_id,)).fetchone()
                    require(fetched is not None,
                            "oracle replay observation lookup")
                    cached_value = strict_json_bytes(bytes(fetched[0]))
                    cached_request_id = request_id
                exact_value = (cached_value["rows"][
                    ROW_ORDER.index(row["row_kind"])]
                    if cached_value["status"] == "ok" else None)
                outcome = "PASS" if exact_value is not None else "UNCOVERED"
                reason = (None if exact_value is not None else
                          cached_value["reason_code"])
                prefix = scientific_base_prefix(case, row)
                for suffix in suffixes:
                    yield [strict_json_bytes(prefix + suffix), outcome,
                           exact_value, None, reason]
    finally:
        if connection is not None:
            connection.close()
        try:
            database_path.unlink()
        except FileNotFoundError:
            pass
        library_snapshot.cleanup()


def execute_oracle_coverage(checkpoint, artifact_root, manifest,
                            oracle_binary, candidate_binary, output_root,
                            oracle_runtime_library_root=None,
                            oracle_runtime_library_bindings=None):
    """Run one independent oracle observation per unique frozen sample.

    The complete result sidecar still repeats the observation at every frozen
    case/anchor applicability key.  A temporary SQLite index avoids retaining
    the potentially multi-gigabyte interval corpus in resident memory.
    """
    cases, request_rows, expected_request_ids, request_ids = \
        _oracle_execution_inventory(checkpoint, artifact_root, manifest)
    database_file = tempfile.NamedTemporaryFile(
        prefix="anchored-oracle-", suffix=".sqlite3", delete=False)
    database_path = pathlib.Path(database_file.name)
    database_file.close()
    connection = None
    execution_audit = OracleExecutionAuditArtifact(output_root)
    try:
        connection = sqlite3.connect(str(database_path))
        connection.execute("CREATE TABLE observations "
                           "(request_id TEXT PRIMARY KEY, value BLOB NOT NULL)")
        observed_count = 0
        for request_id, raw_value, _ in iter_oracle_batch_observations(
                oracle_binary, request_rows, expected_request_ids,
                runtime_library_root=oracle_runtime_library_root,
                runtime_library_bindings=
                    oracle_runtime_library_bindings):
            value = strict_json_bytes(raw_value)
            execution_audit.add(
                request_rows[observed_count],request_id,raw_value,value)
            connection.execute("INSERT INTO observations VALUES (?, ?)",
                               (request_id, raw_value))
            observed_count += 1
        connection.commit()
        require(observed_count == len(expected_request_ids),
                "oracle batch output cardinality")
        execution_audit_descriptor = execution_audit.finish()

        writer = StreamingResultLedgerArtifact(
            output_root, "oracle_coverage_and_crosscheck",
            oracle_certification_authority=
                _ORACLE_CERTIFICATION_AUTHORITY)
        dependent = {
            criterion_id: _NumericResultAccumulator(
                output_root, criterion_id)
            for criterion_id in (
                "exact_effective_d10_coeff",
                "exact_effective_d10_geometry",
                "emitted_direct_geometry_d10")}
        fixtures = regular_patch_inventory(manifest)
        covered = StreamingScientificLedger("oracle-covered")
        uncovered = StreamingScientificLedger("oracle-uncovered")
        uncovered_count = 0
        suffixes = _frozen_scientific_suffixes()[
            "oracle_coverage_and_crosscheck"]
        cached_request_id = None
        cached_value = None
        for case in cases:
            report = _artifact_report(artifact_root, case)
            fixture = fixtures[case["content_identity_key"]]
            for row in ordered_case_rows(report):
                sample_key = (case["content_identity_key"], row["face_row"],
                              row["local_corner_or_none"], row["sample_id"],
                              row["u_binary64_bits_hex"],
                              row["v_binary64_bits_hex"])
                request_id = request_ids[sample_key]
                if request_id != cached_request_id:
                    fetched = connection.execute(
                        "SELECT value FROM observations WHERE request_id=?",
                        (request_id,)).fetchone()
                    require(fetched is not None, "oracle observation lookup")
                    cached_value = strict_json_bytes(bytes(fetched[0]))
                    cached_request_id = request_id
                if cached_value["status"] == "ok":
                    exact_value = cached_value["rows"][
                        ROW_ORDER.index(row["row_kind"])]
                    outcome, reason = "PASS", None
                else:
                    exact_value = None
                    outcome, reason = "UNCOVERED", cached_value["reason_code"]
                prefix = scientific_base_prefix(case, row)
                for suffix in suffixes:
                    encoded_key = prefix + suffix
                    key = strict_json_bytes(encoded_key)
                    writer.add([key, outcome, exact_value, None, reason])
                    (covered if outcome == "PASS" else uncovered).add_encoded(
                        encoded_key)
                    uncovered_count += outcome == "UNCOVERED"
                    anchor_name = key[8]
                    anchor_source = fixture["faces"][row["face_row"]][
                        ANCHORS.index(anchor_name)]
                    coefficient_key = oracle_dependent_key(
                        "exact_effective_d10_coeff", key)
                    coefficient_target = absolute_rational_target(
                        _row_target_denominator(
                            "exact_effective_d10_coeff", coefficient_key))
                    if outcome == "UNCOVERED":
                        dependent["exact_effective_d10_coeff"].add([
                            coefficient_key, "UNCOVERED", None,
                            coefficient_target, reason])
                    else:
                        coefficient_value = oracle_coefficient_l1_value(
                            row, anchor_source, exact_value)
                        coefficient_passed = _measure_le_target(
                            coefficient_value["l1"], coefficient_target)
                        dependent["exact_effective_d10_coeff"].add([
                            coefficient_key,
                            "PASS" if coefficient_passed else "FAIL",
                            coefficient_value, coefficient_target,
                            None if coefficient_passed else
                            "D10_COEFFICIENT_TARGET_EXCEEDED"])

                    for axis_index, axis in enumerate(("x", "y", "z")):
                        geometry_key = oracle_dependent_key(
                            "exact_effective_d10_geometry", key, axis=axis)
                        geometry_target = absolute_rational_target(
                            _row_target_denominator(
                                "exact_effective_d10_geometry", geometry_key))
                        if outcome == "UNCOVERED":
                            dependent["exact_effective_d10_geometry"].add([
                                geometry_key, "UNCOVERED", None,
                                geometry_target, reason])
                            continue
                        geometry_value = oracle_geometry_axis_value(
                            row, anchor_source, exact_value, fixture,
                            axis_index)
                        geometry_measure = geometry_value[
                            "normalized_bound"]["normalized_upper"]
                        geometry_passed = _measure_le_target(
                            geometry_measure, geometry_target)
                        dependent["exact_effective_d10_geometry"].add([
                            geometry_key,
                            "PASS" if geometry_passed else "FAIL",
                            geometry_value, geometry_target,
                            None if geometry_passed else
                            "D10_GEOMETRY_TARGET_EXCEEDED"])

        def emitted_request_lines():
            for (row, fixture, _, anchor_source, exact_value, _, _, axis) in (
                    _iter_oracle_geometry_cells(
                        cases, artifact_root, fixtures, request_ids,
                        database_path)):
                if exact_value is not None:
                    yield candidate_emitted_geometry_line(
                        row, anchor_source, fixture, axis)

        emitted_observations = iter_candidate_observations(
            candidate_binary, "emitted_direct_geometry_d10",
            emitted_request_lines(), covered.count * 3)
        exhausted = object()
        for (row, fixture, oracle_key, anchor_source, exact_value, reason,
             axis_index, axis) in _iter_oracle_geometry_cells(
                 cases, artifact_root, fixtures, request_ids, database_path):
            emitted_key = oracle_dependent_key(
                "emitted_direct_geometry_d10", oracle_key, axis=axis)
            emitted_target = absolute_rational_target(
                _row_target_denominator(
                    "emitted_direct_geometry_d10", emitted_key))
            if exact_value is None:
                dependent["emitted_direct_geometry_d10"].add([
                    emitted_key, "UNCOVERED", None,
                    emitted_target, reason])
                continue
            observation = next(emitted_observations)
            require(observation["axis"] == axis,
                    "candidate emitted-geometry axis drift")
            emitted_value = oracle_geometry_axis_value(
                row, anchor_source, exact_value, fixture, axis_index,
                emitted_bits=observation["observed_bits"])
            emitted_measure = emitted_value[
                "normalized_bound"]["normalized_upper"]
            emitted_passed = _measure_le_target(
                emitted_measure, emitted_target)
            dependent["emitted_direct_geometry_d10"].add([
                emitted_key, "PASS" if emitted_passed else "FAIL",
                emitted_value, emitted_target,
                None if emitted_passed else
                "D10_EMITTED_GEOMETRY_TARGET_EXCEEDED"])
        require(next(emitted_observations, exhausted) is exhausted,
                "candidate emitted-geometry observation overflow")
        commitment, artifact = writer.finish()
        expected = EXPECTED_CELL_COUNTS["oracle_coverage_and_crosscheck"]
        require(commitment["record_count"] == expected,
                "oracle result ledger cardinality")
        covered_digest = (covered.finish() if covered.count else
                          sha256_bytes(b"[]"))
        uncovered_digest = (uncovered.finish() if uncovered.count else
                            sha256_bytes(b"[]"))
        partitions = [
            {"criterion_id": "oracle_coverage_and_crosscheck",
             "partition": "covered", "expected_count": None,
             "observed_count": covered.count,
             "key_ledger_sha256": covered_digest,
             "availability": availability("PRESENT", covered_digest),
             "omission_blocker": None},
            {"criterion_id": "oracle_coverage_and_crosscheck",
             "partition": "uncovered", "expected_count": None,
             "observed_count": uncovered.count,
             "key_ledger_sha256": uncovered_digest,
             "availability": availability("PRESENT", uncovered_digest),
             "omission_blocker": None},
        ]
        result = {
            "oracle_coverage_and_crosscheck": {
                "digest": commitment["key_ledger_sha256"],
                "result_digest": commitment["result_ledger_sha256"],
                "result_merkle_root":
                    commitment["result_merkle_root_sha256"],
                "result_artifact": artifact,
                "observed_count": expected,
                "failure_count": 0,
                "first_failing_key": None,
                "maximum": None, "witness": None,
                "status": "UNCOVERED" if uncovered_count else "PASS",
                "target": None,
                "expectation": RESULT_CONTRACT.CRITERION_BY_ID[
                    "oracle_coverage_and_crosscheck"]["expectation"],
            },
            "exact_effective_d10_coeff": dependent[
                "exact_effective_d10_coeff"].finish(),
            "exact_effective_d10_geometry": dependent[
                "exact_effective_d10_geometry"].finish(),
            "emitted_direct_geometry_d10": dependent[
                "emitted_direct_geometry_d10"].finish(),
        }
        return result, partitions, execution_audit_descriptor
    finally:
        if execution_audit.stream is not None and not execution_audit.stream.closed:
            execution_audit.stream.close()
        if connection is not None:
            connection.close()
        try:
            database_path.unlink()
        except FileNotFoundError:
            pass


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


def run_json(binary, argument, expected_kind, runtime_library_root=None):
    path = pathlib.Path(binary).resolve()
    require(path.is_file(), "binary unavailable: {}".format(path))
    environment = _d12_rebuild_environment()
    if runtime_library_root is not None:
        library_root = pathlib.Path(runtime_library_root).resolve()
        require(library_root.is_dir(),
                "JSON probe runtime library snapshot unavailable")
        environment["DYLD_LIBRARY_PATH"] = str(library_root)
    completed = subprocess.run(
        [str(path), argument], cwd=str(ROOT), env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
    require(completed.returncode == 0,
            "binary failed: {}".format(completed.stderr.strip()))
    value = strict_json_bytes(completed.stdout.encode("utf-8"))
    require(value.get("kind") == expected_kind, "binary self-test kind mismatch")
    return value


def validate_independent_oracle_capability(value):
    expected = {
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
    require(value == expected,
            "independent oracle capability differs from frozen package-2 form")
    return True


def validate_independent_oracle_self_test(value):
    scalar_fields = {
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
    require(set(value) == set(scalar_fields) | {"valence_certificates"} and
            all(value[field] == expected
                for field, expected in scalar_fields.items()),
            "independent oracle self-test scalar contract")
    certificates = value["valence_certificates"]
    boolean_fields = {
        "stock_matrix", "analytic_eigen_residual",
        "interval_krawczyk_inclusion", "verified_inverse_residual",
        "condition_number_bound", "jordan_power_certified",
        "spectral_projectors_certified",
        "source_id_ordered_mgs_certified",
        "tangent_projector_certified",
    }
    require(isinstance(certificates, list) and
            [item.get("valence") for item in certificates] ==
                list(range(3, 10)),
            "independent oracle valence certificate inventory")
    for certificate in certificates:
        require(set(certificate) == {"valence", "dimension"} |
                    boolean_fields and
                certificate["dimension"] == certificate["valence"] + 6 and
                all(certificate[field] is True for field in boolean_fields),
                "independent oracle valence certificate")
    return True


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
    elif criterion_id in {
            "relabel_exact_effective_coefficients",
            "regular_analytic_exact_rows",
            "anchor_sensitivity_exact_coeff",
            "stabilization_6_7_exact_coeff",
            "stabilization_7_8_exact_coeff"}:
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
    elif criterion_id in {
            "regular_analytic_emitted_geometry",
            "emitted_direct_geometry_d10",
            "anchor_sensitivity_emitted_geometry",
            "binary64_direct_geometry_fidelity",
            "relabel_emitted_geometry_fidelity",
            "stabilization_6_7_emitted_geometry",
            "stabilization_7_8_emitted_geometry"}:
        require(isinstance(value, dict) and set(value) == {
            "axis", "kind", "observed_bits"} and
            value["kind"] ==
                "candidate_emitted_geometry_observation_v1" and
            value["axis"] in ("x", "y", "z") and
            isinstance(value["observed_bits"], str) and
            re.fullmatch(r"[0-9a-f]{16}", value["observed_bits"]),
            "candidate emitted-geometry observation shape")
        binary64_from_bits_hex(value["observed_bits"])
    elif criterion_id in {
            "anchor_sensitivity_exact_geometry",
            "stabilization_6_7_exact_geometry",
            "stabilization_7_8_exact_geometry"}:
        require(isinstance(value, dict) and set(value) == {
                    "axis", "kind", "observed"} and
                value["kind"] ==
                    "candidate_exact_geometry_observation_v1" and
                value["axis"] in ("x", "y", "z"),
                "candidate exact-geometry observation shape")
        _validate_signed_dyadic(value["observed"])
        require(value["observed"]["denominator_power"] == 2148,
                "candidate exact-geometry denominator")
    elif criterion_id == "binary64_basis_probe_diagnostic":
        require(isinstance(value, dict) and set(value) == {
                    "emitted_basis_bits", "kind"} and
                value["kind"] == "candidate_basis_observation_v1" and
                isinstance(value["emitted_basis_bits"], str) and
                re.fullmatch(r"[0-9a-f]{16}",
                             value["emitted_basis_bits"]),
                "candidate basis observation shape")
        binary64_from_bits_hex(value["emitted_basis_bits"])
    elif criterion_id == "cache_mode_bit_identity":
        require(isinstance(value, dict) and set(value) == {
                    "cache_disabled_entries", "kind",
                    "serial_cache_entries"} and
                value["kind"] ==
                    "candidate_row_signature_observation_v1",
                "candidate row-signature observation shape")
        for field in ("cache_disabled_entries", "serial_cache_entries"):
            entries = value[field]
            require(isinstance(entries, list) and entries and
                    all(isinstance(item, list) and len(item) == 3 and
                        type(item[0]) is int and
                        isinstance(item[1], str) and
                        re.fullmatch(r"[0-9a-f]{16}", item[1])
                        for item in entries) and
                    [item[0] for item in entries] ==
                        sorted(set(item[0] for item in entries)),
                    "candidate row-signature entries")
            for item in entries:
                binary64_from_bits_hex(item[1])
                _validate_signed_dyadic(item[2])
                require(item[2]["denominator_power"] == 1074,
                        "candidate row-signature dyadic denominator")
    elif criterion_id in {
            "regular_analytic_area_integrand",
            "regular_analytic_legacy_volume_integrand"}:
        require(isinstance(value, dict) and value.get("view") in {
                    "exact_effective", "emitted_binary64"},
                "candidate integrand observation view")
        if value["view"] == "exact_effective":
            require(set(value) == {"kind", "observed_interval", "view"} and
                    value["kind"] ==
                        "candidate_exact_integrand_observation_v1",
                    "candidate exact-integrand observation shape")
            validate_contract_value(
                "interval_rational_v1", value["observed_interval"])
        else:
            require(set(value) == {"kind", "observed_bits", "view"} and
                    value["kind"] ==
                        "candidate_emitted_integrand_observation_v1" and
                    isinstance(value["observed_bits"], str) and
                    re.fullmatch(r"[0-9a-f]{16}", value["observed_bits"]),
                    "candidate emitted-integrand observation shape")
            binary64_from_bits_hex(value["observed_bits"])
    else:
        raise QualificationError("unsupported candidate observation criterion")
    return value


def iter_candidate_observations(binary, criterion_id, request_lines,
                                expected_count, timeout_seconds=900):
    """Yield one strict ordinal-ordered observation stream from the candidate."""
    require(criterion_id in {
        "representation_structure", "constant_field_bits",
        "relabel_exact_effective_coefficients",
        "regular_analytic_exact_rows",
        "regular_analytic_emitted_geometry",
        "regular_analytic_area_integrand",
        "regular_analytic_legacy_volume_integrand",
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
        "cache_mode_bit_identity"},
        "candidate observation criterion")
    require(type(expected_count) is int and 0 <= expected_count < (1 << 63),
            "candidate observation expected count")
    if criterion_id in {
            "regular_analytic_area_integrand",
            "regular_analytic_legacy_volume_integrand"}:
        observation_mode = "--integrand-observation-stream"
    elif criterion_id in CRITERION_IDS[14:26]:
        observation_mode = "--component-observation-stream"
    elif criterion_id == "cache_mode_bit_identity":
        observation_mode = "--cache-observation-stream"
    else:
        observation_mode = "--preoracle-observation-stream"
    command = [str(pathlib.Path(binary).resolve()), observation_mode]
    if criterion_id != "cache_mode_bit_identity":
        command.append(criterion_id)
    process = subprocess.Popen(
        command, cwd=str(ROOT), env=_d12_rebuild_environment(),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True)
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
    expired = []

    def expire():
        expired.append(True)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass

    timer = threading.Timer(timeout_seconds, expire)
    timer.start()
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
        feeder.join(timeout_seconds)
        require(not feeder.is_alive(), "candidate observation input timed out")
        stderr = process.stderr.read().decode("utf-8", errors="strict")
        returncode = process.wait()
        require(not expired, "candidate observation process timed out")
        require(not feeder_errors, "candidate observation input failure")
        require(returncode == 0, "candidate observation process failed: {}".format(
            stderr.strip()))
    finally:
        timer.cancel()
        if feeder.is_alive() or process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        feeder.join(timeout=5)
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


def git_observations():
    try:
        audit = _audit_d12_git_worktree(ROOT)
    except QualificationError:
        return (git_identity(
                    "UNAVAILABLE", reason_code="GIT_IDENTITY_UNAVAILABLE"),
                worktree_observation(False))
    return (git_identity("PRESENT", audit["head"]),
            worktree_observation(True))


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


def _oracle_dynamic_dependency_packet(actual_dynamic, library_root):
    """Bind the exact loaded MPFR/GMP dylib paths and bytes."""
    try:
        dynamic_text = actual_dynamic.decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise QualificationError(
            "oracle dynamic-dependency transcript is not UTF-8") from error
    libraries = []
    for name in ("gmp", "mpfr"):
        matches = []
        pattern = re.compile(r"^\s*(/[^\s]+/lib" + name +
                             r"(?:\.[0-9]+)*\.dylib)\s+\(")
        for line in dynamic_text.splitlines()[1:]:
            matched = pattern.match(line)
            if matched is not None:
                matches.append(matched.group(1))
        require(len(matches) == 1,
                "oracle dynamic dependency lacks one exact lib" + name)
        raw_path = matches[0]
        path = pathlib.Path(raw_path).resolve()
        require(raw_path == str(path) and path.is_file() and
                path.is_relative_to(library_root) and
                path.parent == library_root,
                "oracle linked lib{} escapes the declared canonical root".
                format(name))
        libraries.append({"name": name, "path": str(path),
                          "sha256": sha256_file(path)})
    return {
        "schema_id": "oracle-runtime-dependency-audit-v1",
        "otool_L_sha256": sha256_bytes(actual_dynamic),
        "otool_L_text": dynamic_text,
        "libraries": libraries}


def _snapshot_oracle_runtime_libraries(dynamic_packet_path, destination_root):
    """Copy the two audited proof dylibs and return immutable bindings."""
    packet_path = pathlib.Path(dynamic_packet_path).resolve()
    destination_root = pathlib.Path(destination_root).resolve()
    packet = strict_json_bytes(packet_path.read_bytes())
    require(packet.get("schema_id") in {
                "oracle-runtime-dependency-audit-v1",
                "oracle-runtime-execution-audit-v2"} and
            isinstance(packet.get("otool_L_text"), str) and
            sha256_bytes(packet["otool_L_text"].encode("utf-8")) ==
                packet.get("otool_L_sha256") and
            [item.get("name") for item in packet.get("libraries", [])] ==
                ["gmp", "mpfr"],
            "oracle runtime dependency packet shape")
    destination_root.mkdir(parents=True, exist_ok=False)
    bindings = []
    for item in packet["libraries"]:
        expected_keys = ({"name", "path", "sha256"}
                         if packet["schema_id"] ==
                            "oracle-runtime-dependency-audit-v1" else
                         {"name", "audited_path", "relative_path", "sha256"})
        require(set(item) == expected_keys and
                SHA256_RE.fullmatch(item.get("sha256") or "") is not None,
                "oracle runtime dependency binding shape")
        source_value = item.get("relative_path", item.get("path"))
        require(isinstance(source_value, str) and source_value,
                "oracle runtime dependency packet path")
        source = pathlib.Path(source_value)
        if not source.is_absolute():
            source = packet_path.parent / source
        source = source.resolve()
        require(source.is_file() and sha256_file(source) == item["sha256"],
                "oracle runtime dependency changed before snapshot: " +
                item["name"])
        destination = destination_root / source.name
        require(not destination.exists(),
                "oracle runtime dependency basename collision")
        shutil.copyfile(str(source), str(destination))
        destination.chmod(0o500)
        require(sha256_file(source) == item["sha256"] ==
                    sha256_file(destination),
                "oracle runtime dependency changed while snapshotting: " +
                item["name"])
        bindings.append((source, item["sha256"], destination))
    return bindings


def _publish_oracle_runtime_execution_packet(
        sealed_audit_path, runtime_bindings, execution_audit, destination):
    """Bind the actually loaded immutable dylibs and unique-request audit."""
    sealed_path = pathlib.Path(sealed_audit_path).resolve()
    destination = pathlib.Path(destination).resolve()
    packet = strict_json_bytes(sealed_path.read_bytes())
    require(packet.get("schema_id") ==
                "oracle-runtime-dependency-audit-v1" and
            [item.get("name") for item in packet.get("libraries", [])] ==
                ["gmp", "mpfr"] and
            len(runtime_bindings) == 2,
            "oracle sealed dependency packet shape")
    require(set(execution_audit) == {
                "relative_path", "record_count", "byte_length", "sha256"} and
            execution_audit["relative_path"] ==
                ORACLE_EXECUTION_AUDIT_PATH and
            execution_audit["record_count"] ==
                ORACLE_EXECUTION_REQUEST_COUNT and
            SHA256_RE.fullmatch(execution_audit["sha256"] or "") is not None,
            "oracle execution audit descriptor shape")
    audit_artifact = (destination.parent /
                      execution_audit["relative_path"]).resolve()
    require(audit_artifact.parent == destination.parent and
            audit_artifact.is_file() and
            audit_artifact.stat().st_size == execution_audit["byte_length"] and
            sha256_file(audit_artifact) == execution_audit["sha256"],
            "oracle execution audit artifact binding")
    libraries = []
    for original_item, (original, digest, loaded) in zip(
            packet["libraries"], runtime_bindings):
        loaded = pathlib.Path(loaded).resolve()
        require(pathlib.Path(original_item["path"]).resolve() ==
                    pathlib.Path(original).resolve() and
                original_item["sha256"] == digest == sha256_file(loaded) and
                loaded.is_relative_to(destination.parent),
                "oracle loaded runtime dependency differs from audit")
        libraries.append({
            "name": original_item["name"],
            "audited_path": original_item["path"],
            "relative_path": loaded.relative_to(destination.parent).as_posix(),
            "sha256": digest})
    final_packet = {
        "schema_id": "oracle-runtime-execution-audit-v2",
        "otool_L_text": packet["otool_L_text"],
        "otool_L_sha256": packet["otool_L_sha256"],
        "libraries": libraries,
        "execution_audit": copy.deepcopy(execution_audit)}
    require(not destination.exists(),
            "oracle runtime execution packet already exists")
    destination.write_bytes(jcs_bytes(final_packet))
    return final_packet


def _bound_oracle_execution_audit(dynamic_packet_path):
    packet_path = pathlib.Path(dynamic_packet_path).resolve()
    packet = strict_json_bytes(packet_path.read_bytes())
    require(packet.get("schema_id") ==
                "oracle-runtime-execution-audit-v2" and
            set(packet) == {"schema_id", "otool_L_text", "otool_L_sha256",
                            "libraries", "execution_audit"},
            "oracle standalone replay lacks execution audit packet")
    require(isinstance(packet["otool_L_text"], str) and
            sha256_bytes(packet["otool_L_text"].encode("utf-8")) ==
                packet["otool_L_sha256"] and
            [item.get("name") for item in packet.get("libraries", [])] ==
                ["gmp", "mpfr"],
            "oracle runtime execution packet transcript drift")
    bound_library_paths = []
    bound_library_digests = []
    for item in packet["libraries"]:
        require(set(item) == {"name", "audited_path", "relative_path",
                              "sha256"} and
                pathlib.Path(item["audited_path"]).is_absolute() and
                str(pathlib.Path(item["audited_path"]).resolve()) ==
                    item["audited_path"] and
                isinstance(item["relative_path"], str) and
                bool(item["relative_path"]) and
                not pathlib.PurePosixPath(item["relative_path"]).is_absolute() and
                pathlib.PurePosixPath(item["relative_path"]).as_posix() ==
                    item["relative_path"] and
                pathlib.PurePosixPath(item["relative_path"]).parts[0] ==
                    "anchored-row-oracle-runtime-libraries-v1" and
                len(pathlib.PurePosixPath(item["relative_path"]).parts) == 2 and
                SHA256_RE.fullmatch(item["sha256"] or "") is not None,
                "oracle loaded runtime dependency binding drift")
        loaded = (packet_path.parent / item["relative_path"]).resolve()
        require(loaded.is_relative_to(packet_path.parent) and
                loaded.is_file() and sha256_file(loaded) == item["sha256"],
                "oracle loaded runtime dependency bytes drift")
        bound_library_paths.append(loaded)
        bound_library_digests.append(item["sha256"])
    require(len(set(bound_library_paths)) == 2 and
            len(set(bound_library_digests)) == 2,
            "oracle loaded runtime dependency role collapse")
    descriptor = packet["execution_audit"]
    require(set(descriptor) == {
                "relative_path", "record_count", "byte_length", "sha256"} and
            descriptor["relative_path"] == ORACLE_EXECUTION_AUDIT_PATH and
            descriptor["record_count"] == ORACLE_EXECUTION_REQUEST_COUNT and
            type(descriptor["byte_length"]) is int and
            descriptor["byte_length"] >= 2 and
            SHA256_RE.fullmatch(descriptor["sha256"] or "") is not None,
            "oracle execution audit descriptor drift")
    artifact = (packet_path.parent / descriptor["relative_path"]).resolve()
    require(artifact.parent == packet_path.parent and artifact.is_file() and
            artifact.stat().st_size == descriptor["byte_length"] and
            sha256_file(artifact) == descriptor["sha256"],
            "oracle execution audit sidecar bytes drift")
    return descriptor


def _audit_oracle_mpfr_calls():
    """Reject an unrounded or unapproved MPFR arithmetic proof call."""
    directed_arithmetic = {
        "abs", "add", "const_pi", "cos", "div", "div_2ui", "div_ui",
        "mul", "mul_ui", "neg", "sqrt", "sub", "ui_div"}
    explicit_rounding = directed_arithmetic | {
        "get_d", "set", "set_d", "set_si", "set_str", "set_ui",
        "set_ui_2exp"}
    non_arithmetic = {
        "clear", "clear_flags", "divby0_p", "equal_p", "erangeflag_p",
        "get_version", "get_z_2exp", "greater_p", "greaterequal_p",
        "init2", "less_p", "lessequal_p", "nanflag_p", "number_p",
        "overflow_p", "set_zero", "sgn", "snprintf", "underflow_p",
        "zero_p"}
    for relative in RUNTIME_SOURCE_PATHS["independent_oracle"]:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8", errors="strict")
        require("mpfr_sin" not in text,
                "oracle proof surface uses an unapproved transcendental")
        if relative.endswith("mpfr_interval.hpp"):
            require(all(fragment in text for fragment in (
                        "ProductionRoundingMutation::AddLower",
                        "ProductionRoundingMutation::AddUpper",
                        "ProductionRoundingMutation::SubtractLower",
                        "ProductionRoundingMutation::SubtractUpper",
                        "ProductionRoundingMutation::MultiplyLower",
                        "ProductionRoundingMutation::MultiplyUpper",
                        "ProductionRoundingMutation::DivideLower",
                        "ProductionRoundingMutation::DivideUpper",
                        "ProductionRoundingMutation::SquareRootLower",
                        "ProductionRoundingMutation::SquareRootUpper",
                        "ProductionRoundingMutation::CosineLower",
                        "ProductionRoundingMutation::CosineUpper",
                        "ProductionRoundingMutation::MatrixAccumulatorLower",
                        "ProductionRoundingMutation::MatrixAccumulatorUpper",
                        "proof_endpoint_rounding(",
                        "directed_rounding_mutation_self_test()",
                        "return matrix_accumulate(add_a,add_b)")),
                    "oracle production rounding mutation wiring drift")
        for matched in re.finditer(r"\bmpfr_([A-Za-z0-9_]+)\s*\(", text):
            name = matched.group(1)
            require(name in explicit_rounding | non_arithmetic,
                    "oracle source uses an unaudited MPFR call: " + name)
            if name not in explicit_rounding:
                continue
            cursor = matched.end()
            depth = 1
            while cursor < len(text) and depth:
                if text[cursor] == "(":
                    depth += 1
                elif text[cursor] == ")":
                    depth -= 1
                cursor += 1
            require(depth == 0, "oracle MPFR call is not lexically closed")
            call = text[matched.start():cursor]
            variable_mode = (name == "mul" and
                             ("downward_mode" in call or
                              "upward_mode" in call))
            require(variable_mode or any(rounding in call for rounding in (
                        "MPFR_RNDD", "MPFR_RNDU", "MPFR_RNDN")),
                    "oracle MPFR arithmetic call lacks literal rounding: " +
                    name)
            if name in directed_arithmetic:
                normalized_call = re.sub(r"\s+", "", call)
                diagnostic_midpoint_calls = {
                    "mpfr_add(value,lo_,hi_,MPFR_RNDN)",
                    "mpfr_div_2ui(value,value,1,MPFR_RNDN)",
                    "mpfr_add(midpoint,value.lo(),value.hi(),MPFR_RNDN)",
                    "mpfr_div_2ui(midpoint,midpoint,1,MPFR_RNDN)",
                    "mpfr_add(reference,a,b,MPFR_RNDN)",
                    "mpfr_add(a,a,b,MPFR_RNDN)",
                    "mpfr_sub(reference,a,b,MPFR_RNDN)",
                    "mpfr_mul(reference,a,b,MPFR_RNDN)",
                    "mpfr_mul(reference,a,a,MPFR_RNDN)",
                    "mpfr_div(reference,a,b,MPFR_RNDN)",
                    "mpfr_sqrt(reference,a,MPFR_RNDN)",
                    "mpfr_cos(reference,a,MPFR_RNDN)",
                    "mpfr_const_pi(reference,MPFR_RNDN)",
                    "mpfr_mul_ui(reference,reference,2,MPFR_RNDN)",
                    "mpfr_div_ui(reference,reference,5,MPFR_RNDN)",
                }
                require(variable_mode or "MPFR_RNDD" in call or
                        "MPFR_RNDU" in call or
                        normalized_call in diagnostic_midpoint_calls,
                        "oracle interval arithmetic uses nearest rounding: " +
                        name)
    return True


def audit_oracle_independence(binary_path, command_path, link_map_path,
                              dynamic_dependencies_path,
                              sealed_output_path=None,
                              dependency_evidence_path=None):
    """Recompute the frozen primary-oracle independence proof."""
    B2.validate_source_separation()
    _audit_oracle_mpfr_calls()
    binary = pathlib.Path(binary_path).resolve()
    command_file = pathlib.Path(command_path).resolve()
    link_map = pathlib.Path(link_map_path).resolve()
    dynamic_file = pathlib.Path(dynamic_dependencies_path).resolve()
    require(all(path.is_file() for path in (
                binary, command_file, link_map, dynamic_file)),
            "oracle independence audit artifact unavailable")
    command = command_file.read_text(encoding="utf-8").splitlines()
    require(command and all(command) and len(command) == len(set(command)) and
            command[0] == B2.EXPECTED_COMPILER_PATH and
            command.count("-MMD") == 1 and command.count("-MF") == 1 and
            command.count("-o") == 1,
            "oracle compile command is not exact/closed")
    fixed_flags = [
        "-std=c++17", "-O3", "-DNDEBUG", "-fno-fast-math",
        "-ffp-contract=off", "-fno-omit-frame-pointer", "-Wall",
        "-Wextra", "-Wpedantic", "-Werror", "-isysroot",
        "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk",
        "-mmacosx-version-min=26.0"]
    require(command[1:1 + len(fixed_flags)] == fixed_flags,
            "oracle compile profile flags drift")
    tail = command[1 + len(fixed_flags):]
    require(len(tail) == 12 and tail[0:2] == ["-MMD", "-MF"] and
            tail[3].startswith("-I") and len(tail[3]) > 2 and
            tail[4] == "experiments/bfr_qualification/stam_oracle.cpp" and
            tail[5].startswith("-L") and len(tail[5]) > 2 and
            tail[6].startswith("-Wl,-rpath,") and
            tail[7:9] == ["-lmpfr", "-lgmp"] and
            tail[9].startswith("-Wl,-map,") and tail[10] == "-o" and
            pathlib.Path(tail[11]).resolve() == binary,
            "oracle command source/output/dependency grammar drift")
    dependency_path = pathlib.Path(tail[2]).resolve()
    dependency_evidence = (dependency_path if dependency_evidence_path is None
                           else pathlib.Path(
                               dependency_evidence_path).resolve())
    include_root = pathlib.Path(tail[3][2:]).resolve()
    library_root = pathlib.Path(tail[5][2:]).resolve()
    rpath_root = pathlib.Path(tail[6][len("-Wl,-rpath,"):]).resolve()
    command_map = pathlib.Path(tail[9][len("-Wl,-map,"):]).resolve()
    require(str(dependency_path) == tail[2] and
            str(include_root) == tail[3][2:] and
            str(library_root) == tail[5][2:] and
            str(rpath_root) == tail[6][len("-Wl,-rpath,"):] and
            library_root == rpath_root and
            include_root.parent == library_root.parent and
            command_map == link_map and
            str(command_map) == tail[9][len("-Wl,-map,"):] and
            str(binary) == tail[11],
            "oracle command artifact roots are not canonical/distinct")
    require(dependency_evidence.is_file() and
            (dependency_evidence_path is None or
             dependency_evidence.read_bytes() == dependency_path.read_bytes()),
            "oracle dependency evidence differs from compiler depfile")
    dependency_inputs = _d12_dependency_inputs(
        dependency_evidence, binary, ROOT)
    expected_dependencies = {
        str((ROOT / relative).resolve())
        for relative in RUNTIME_SOURCE_PATHS["independent_oracle"]}
    expected_dependencies.update({
        str((include_root / "mpfr.h").resolve()),
        str((include_root / "gmp.h").resolve())})
    require(all(pathlib.Path(path).is_file() and
                (pathlib.Path(path).is_relative_to(ROOT) or
                 pathlib.Path(path).parent == include_root)
                for path in expected_dependencies),
            "oracle frozen source/header dependency unavailable")
    require({item["path"] for item in dependency_inputs} ==
                expected_dependencies and
            all(item["sha256"] == sha256_file(pathlib.Path(item["path"]))
                for item in dependency_inputs),
            "oracle dependency closure differs from frozen independent sources")
    environment = _d12_rebuild_environment()

    def checked_output(command_line):
        completed = subprocess.run(
            command_line, cwd=str(ROOT), env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        require(completed.returncode == 0 and completed.stdout,
                "oracle binary audit command failed")
        return completed.stdout

    actual_dynamic = checked_output(["/usr/bin/otool", "-L", str(binary)])
    dynamic_packet = _oracle_dynamic_dependency_packet(
        actual_dynamic, library_root)
    supplied_dynamic = dynamic_file.read_bytes()
    if supplied_dynamic == actual_dynamic:
        require(sealed_output_path is not None,
                "raw oracle dynamic transcript is not a sealed audit packet")
    else:
        supplied_packet = strict_json_bytes(supplied_dynamic)
        require(supplied_packet == dynamic_packet and
                supplied_dynamic == jcs_bytes(dynamic_packet),
                "oracle dynamic-dependency audit packet drift")
    if sealed_output_path is not None:
        sealed_path = pathlib.Path(sealed_output_path).resolve()
        require(not sealed_path.exists(),
                "oracle dynamic-dependency sealed output already exists")
        sealed_path.write_bytes(jcs_bytes(dynamic_packet))
    undefined_symbols = checked_output(["/usr/bin/nm", "-u", str(binary)])
    forbidden = B2.FORBIDDEN_ORACLE_TOKENS
    dynamic_text = actual_dynamic.decode("utf-8", errors="strict")
    symbol_text = undefined_symbols.decode("utf-8", errors="strict")
    approved_mpfr_symbols = {
        "add", "clear", "clear_flags", "const_pi", "cos", "div",
        "div_2ui", "div_ui", "divby0_p", "equal_p", "erangeflag_p",
        "get_d", "get_version", "get_z_2exp", "greater_p",
        "greaterequal_p", "init2", "less_p", "lessequal_p", "mul",
        "nanflag_p", "neg", "number_p", "overflow_p", "set4", "set_d",
        "set_erangeflag", "set_si", "set_str", "set_ui", "set_ui_2exp",
        "set_zero", "snprintf", "sqrt", "sub", "ui_div",
        "underflow_p"}
    approved_gmp_symbols = {
        "get_memory_functions", "z_clear", "z_divexact_ui", "z_get_str",
        "z_init", "z_init_set_ui", "z_mul_2exp"}
    for line in symbol_text.splitlines():
        symbol = line.split()[-1].lstrip("_") if line.split() else ""
        if symbol.startswith("mpfr_"):
            require(symbol[len("mpfr_"):] in approved_mpfr_symbols,
                    "oracle binary imports an unaudited MPFR symbol: " +
                    symbol)
        elif symbol.startswith("gmp_"):
            require(symbol[len("gmp_"):] in approved_gmp_symbols,
                    "oracle binary imports an unaudited GMP symbol: " +
                    symbol)
        elif symbol.startswith("gmpz_"):
            require(("z_" + symbol[len("gmpz_"):]) in
                    approved_gmp_symbols,
                    "oracle binary imports an unaudited GMP integer symbol: " +
                    symbol)
    require(not any(token in dynamic_text for token in forbidden) and
            "osd" not in dynamic_text.lower() and
            not any(token in symbol_text for token in forbidden) and
            b"mpfr_" in undefined_symbols.lower(),
            "oracle binary links or imports a forbidden/non-MPFR route")
    map_text = link_map.read_text(encoding="utf-8", errors="strict")
    require(map_text and not any(token in map_text
                                 for token in forbidden) and
            ("stam_oracle" in map_text or "stam_oracle.cpp" in map_text),
            "oracle link map does not bind the independent translation unit")
    return "PASS"


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


def executed_criterion_record(criterion_id, evidence):
    """Construct one report slot only from a persisted runner-owned ledger."""
    permitted_statuses = {"PASS", "FAIL", "UNCOVERED"}
    if criterion_id in D12_CRITERIA:
        # A complete hosted/unqualified D12 run retains every observed result
        # record but owns an aggregate INCOMPLETE disposition.  This is
        # materially different from a missing operational ledger.
        permitted_statuses.add("INCOMPLETE")
    require(isinstance(evidence, dict) and
            evidence.get("observed_count") ==
                EXPECTED_CELL_COUNTS[criterion_id] and
            evidence.get("status") in permitted_statuses and
            SHA256_RE.fullmatch(evidence.get("digest", "")) is not None and
            SHA256_RE.fullmatch(
                evidence.get("result_digest", "")) is not None and
            SHA256_RE.fullmatch(
                evidence.get("result_merkle_root", "")) is not None and
            isinstance(evidence.get("result_artifact"), dict),
            "executed criterion lacks persistent result evidence")
    categorical = criterion_id in CATEGORICAL_CRITERIA
    uncovered = evidence["status"] == "UNCOVERED"
    maximum = None if categorical or uncovered else evidence.get("maximum")
    witness = None if categorical or uncovered else evidence.get("witness")
    return criterion_record(
        criterion_id, evidence["status"],
        expectation=evidence.get("expectation"),
        expected=EXPECTED_CELL_COUNTS[criterion_id],
        observed=evidence["observed_count"], ledger=evidence["digest"],
        result_ledger=evidence["result_digest"],
        result_merkle_root=evidence["result_merkle_root"],
        result_artifact=evidence["result_artifact"],
        target=evidence.get("target") or
            report_criterion_target(criterion_id),
        maximum=maximum, witness=witness,
        first_failure=evidence.get("first_failing_key"))


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
            if status == "PASS":
                require(item["target"]["sidecar"]["availability"]["state"] ==
                        "PRESENT",
                        "inventory PASS lacks present aggregate target")
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
        elif criterion_id in ORACLE_DEPENDENT_CRITERIA:
            require(status in {"PASS", "FAIL", "UNCOVERED",
                               "OMITTED_AFTER_CANDIDATE_FAILURE",
                               "OMITTED_AFTER_INFRASTRUCTURE_FAILURE"},
                    "oracle-dependent status ownership")
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
            require(item["observed_cell_count"] ==
                    item["expected_cell_count"],
                    "present result sidecar is not a complete expected set")
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
        if (criterion_id in ORACLE_CRITERIA | ORACLE_DEPENDENT_CRITERIA and
                status == "UNCOVERED"):
            require(item["maximum"] is None and item["witness"] is None,
                    "uncovered criterion carries numeric witness")
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
    try:
        validate_contract_value("serial_only_context", context)
    except QualificationError:
        return ineligible
    if (context["cache_disabled_concurrency_pass"] is not True or
            context["cache_disabled_tsan_pass"] is not True):
        return ineligible
    statuses = {item["criterion_id"]: item["status"] for item in criteria}
    if (statuses.get("d12_instrumented_tsan") != "FAIL" or
            any(statuses[criterion_id] != "PASS"
                for criterion_id in CRITERION_IDS
                if criterion_id != "d12_instrumented_tsan")):
        return ineligible
    failures = context["failure_records"]
    if not isinstance(failures, list) or not failures:
        return ineligible
    for item in failures:
        if (not isinstance(item, list) or len(item) != 2 or
                item[1] != "THREADED_CACHE_RACE"):
            return ineligible
        try:
            validate_d12_key(item[0], "d12_instrumented_tsan")
        except QualificationError:
            return ineligible
        if item[0][3] != "threaded_cache":
            return ineligible
    failure_digest = sha256_bytes(jcs_bytes(failures))
    if context["failure_records_sha256"] != failure_digest:
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


def _validate_pre_result_ledgers(ledgers):
    schema = cached_schema()
    validate_schema_instance(
        ledgers, schema["$defs"]["matrix"]["properties"]["ledgers"],
        schema, "$matrix.ledgers")
    require(len(ledgers) == 34 and
            {item["criterion_id"] for item in ledgers} == set(CRITERION_IDS),
            "matrix criterion-ledger coverage")
    by_key = {(item["criterion_id"], item["partition"]): item
              for item in ledgers}
    require(len(by_key) == len(ledgers),
            "duplicate criterion ledger partition")
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
            require(item["key_ledger_sha256"] ==
                    item["availability"]["sha256"] and
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
    return by_key


def validate_report(report, serial_context=None):
    validate_schema_instance(report)
    validate_criteria(report["criteria"])
    checkpoint = report["checkpoint"]
    require(checkpoint["availability"]["state"] == "PRESENT" and
            checkpoint["release_complete"] is True and
            checkpoint["git_head"] ==
                report["identity"]["git_end"]["git_commit"] and
            checkpoint["row_provider_binary_sha256"] ==
                report["binaries"]["row_provider"]["availability"][
                    "sha256"],
            "report checkpoint/head/provider binding mismatch")
    for binary_name in ("row_provider", "representation_candidate",
                        "exact_dyadic_boundary", "independent_oracle"):
        binary = report["binaries"][binary_name]
        if (binary_name == "independent_oracle" and
                binary["availability"]["state"] != "PRESENT"):
            continue
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
    by_key = _validate_pre_result_ledgers(ledgers)
    oracle_request = by_key[("oracle_coverage_and_crosscheck",
                             "oracle_request")]
    oracle_covered = by_key[("oracle_coverage_and_crosscheck", "covered")]
    oracle_uncovered = by_key[("oracle_coverage_and_crosscheck", "uncovered")]
    if oracle_covered["availability"]["state"] == "PRESENT":
        covered_count = oracle_covered["observed_count"]
        uncovered_count = oracle_uncovered["observed_count"]
        oracle_status = report["criteria"][CRITERION_IDS.index(
            "oracle_coverage_and_crosscheck")]["status"]
        require(oracle_uncovered["availability"]["state"] == "PRESENT" and
                covered_count + uncovered_count ==
                    EXPECTED_CELL_COUNTS["oracle_coverage_and_crosscheck"] and
                (covered_count != 0 or oracle_covered[
                    "key_ledger_sha256"] == sha256_bytes(b"[]")) and
                (uncovered_count != 0 or oracle_uncovered[
                    "key_ledger_sha256"] == sha256_bytes(b"[]")) and
                oracle_status == ("UNCOVERED" if uncovered_count else "PASS"),
                "executed oracle partition count/status drift")
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
                d12["exact_head"] == report["identity"]["git_end"]["git_commit"] and
                SHA256_RE.fullmatch(d12["physical_fingerprint_sha256"] or "") and
                d12_statuses == {"INCOMPLETE"} and
                d12["representation_work"] in {"INCLUDED", "NOT_INCLUDED"},
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
    expected = calculate_verdict(report["criteria"], serial_context)
    for key in expected:
        if key != "report_content_sha256":
            require(report["verdict"][key] == expected[key],
                    "verdict contradicts criteria: {}".format(key))
    digest_copy = copy.deepcopy(report)
    digest_copy["verdict"]["report_content_sha256"] = ZERO_SHA256
    require(report["verdict"]["report_content_sha256"] ==
            sha256_bytes(jcs_bytes(digest_copy)), "report content digest mismatch")
    require(all(report["verdict"][field] is False for field in (
                "qualification_decided", "d9a_reopened", "b3_unblocked",
                "far_selected", "production_authorized")),
            "proof verdict attempted an unauthorized decision/activation")
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
                    require(len(buffer) <= MAX_RESULT_RECORD_BYTES,
                            "result sidecar record exceeds byte limit")
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
                require(len(buffer) <= MAX_RESULT_RECORD_BYTES,
                        "result sidecar record exceeds byte limit")
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
                    require(depth <= MAX_RESULT_RECORD_NESTING,
                            "result sidecar record exceeds nesting limit")
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


def _canonical_uint64_token(token):
    require(isinstance(token, str) and
            re.fullmatch(r"0|[1-9][0-9]*", token) is not None and
            int(token) <= 0xffffffffffffffff,
            "D12 raw integer token is not canonical uint64")
    return int(token)


def validate_d12_process_observation(record):
    require(isinstance(record, list) and len(record) == 3,
            "D12 process observation record shape")
    key, payload, provenance = record
    quantity = key[13] if isinstance(key, list) and len(key) == 14 else None
    criterion = {
        "preparation_duration_ns": "d12_preparation_cost",
        "preparation_median_ns": "d12_preparation_cost",
        "retained_payload_bytes": "d12_retained_payload",
        "rss_bytes": "d12_peak_rss",
        "instrumentation_coverage": "d12_instrumented_tsan",
        "tsan_finding_count": "d12_instrumented_tsan",
    }.get(quantity)
    require(criterion is not None, "D12 process observation quantity")
    validate_d12_key(key, criterion)
    expected_kind = {
        "preparation_duration_ns": "d12_duration_raw_v1",
        "preparation_median_ns": "d12_duration_raw_v1",
        "retained_payload_bytes": "d12_payload_raw_v1",
        "rss_bytes": "d12_rss_raw_v1",
        "instrumentation_coverage": "d12_tsan_instrumentation_raw_v1",
        "tsan_finding_count": "d12_tsan_finding_raw_v1",
    }[quantity]
    require(_contract_kind(payload) == expected_kind,
            "D12 process observation payload kind")
    validate_contract_value(expected_kind, payload)
    validate_contract_value("d12_process_provenance_v1", provenance)
    require(provenance["process_tuple_sha256"] == sha256_bytes(
                jcs_bytes(key[:5])),
            "D12 process provenance does not bind the operational tuple")
    state = payload["state"]
    if expected_kind == "d12_duration_raw_v1":
        if state == "VALID_UINT64_NS":
            _canonical_uint64_token(payload["token"])
        elif state == "NEGATIVE":
            require(re.fullmatch(r"-[1-9][0-9]*", payload["token"] or "") is
                    not None, "D12 negative duration token")
        elif state == "NONFINITE":
            require(payload["token"] in {"nan", "+inf", "-inf"},
                    "D12 nonfinite duration token")
        else:
            require(payload["token"] is None,
                    "D12 failed duration carries a token")
    elif expected_kind == "d12_payload_raw_v1":
        if state == "VALID_UINT64_BYTES":
            _canonical_uint64_token(payload["token"])
        else:
            require(payload["token"] is None,
                    "D12 invalid payload carries a token")
    elif expected_kind == "d12_rss_raw_v1":
        if state == "VALID_UINT64_BYTES":
            _canonical_uint64_token(payload["baseline_token"])
            _canonical_uint64_token(payload["observed_token"])
        else:
            require(payload["observed_token"] is None and
                    (payload["baseline_token"] is None or
                     _canonical_uint64_token(payload["baseline_token"]) >= 0),
                    "D12 invalid RSS token state")
    elif expected_kind == "d12_tsan_instrumentation_raw_v1":
        require((state == "COMPLETE") ==
                (SHA256_RE.fullmatch(payload[
                    "instrumented_translation_units_sha256"] or "") is not
                 None), "D12 instrumentation raw digest/state")
    else:
        if state == "COMPLETE":
            _canonical_uint64_token(payload["finding_count_token"])
            require(payload["sanitizer_report_sha256"] is None,
                    "complete TSan count carries abort report")
        elif state == "SANITIZER_ABORT":
            require(payload["finding_count_token"] is None and
                    SHA256_RE.fullmatch(
                        payload["sanitizer_report_sha256"] or ""),
                    "D12 sanitizer-abort raw payload")
        else:
            require(payload["finding_count_token"] is None and
                    payload["sanitizer_report_sha256"] is None,
                    "unavailable TSan execution carries result evidence")

    exit_kind = provenance["exit_kind"]
    if exit_kind == "EXITED":
        require(provenance["pid"] is not None and
                type(provenance["exit_code"]) is int and
                provenance["signal"] is None,
                "D12 exited-process provenance shape")
    elif exit_kind == "SIGNALED":
        require(provenance["pid"] is not None and
                provenance["exit_code"] is None and
                type(provenance["signal"]) is int and
                provenance["signal"] > 0,
                "D12 signaled-process provenance shape")
    elif exit_kind == "TIMEOUT":
        require(provenance["pid"] is not None and
                provenance["exit_code"] is None and
                provenance["signal"] is None,
                "D12 timeout-process provenance shape")
    else:
        require(exit_kind == "NOT_STARTED" and provenance["pid"] is None and
                provenance["exit_code"] is None and
                provenance["signal"] is None,
                "D12 not-started process provenance shape")

    ordinary_exit_states = {
        "VALID_UINT64_NS", "VALID_UINT64_BYTES", "COMPLETE", "NONFINITE",
        "NEGATIVE", "MISSING_COUNT", "NON_SIX_ROW_SAMPLE",
        "ARITHMETIC_OVERFLOW", "SAMPLE_MISSING", "API_FAILURE",
        "INCOMPLETE"}
    if state in ordinary_exit_states:
        instrumentation_abort = (
            expected_kind == "d12_tsan_instrumentation_raw_v1" and
            state == "COMPLETE" and
            (exit_kind == "SIGNALED" or
             (exit_kind == "EXITED" and provenance["exit_code"] != 0)))
        require((exit_kind == "EXITED" and provenance["exit_code"] == 0) or
                instrumentation_abort,
                "D12 observation/process success-state mismatch")
    elif state == "TIMEOUT":
        require(exit_kind == "TIMEOUT",
                "D12 timeout/process provenance mismatch")
    elif state == "SIGNAL":
        require(exit_kind == "SIGNALED",
                "D12 signal/process provenance mismatch")
    elif state == "EXECUTION_UNAVAILABLE":
        require(exit_kind == "NOT_STARTED",
                "D12 unavailable/process provenance mismatch")
    else:
        require(state in {"ALLOCATION_FAILURE", "PROCESS_FAILURE",
                          "SANITIZER_ABORT"} and
                (exit_kind == "SIGNALED" or
                 (exit_kind == "EXITED" and
                  provenance["exit_code"] != 0)),
                "D12 failed payload has successful process provenance")
    return key, payload, provenance


def validate_d12_raw_exact_value(
        payload, exact_value, expected_instrumented_translation_units=None):
    kind = _contract_kind(exact_value)
    raw_kind = _contract_kind(payload)
    if raw_kind == "d12_duration_raw_v1":
        if payload["state"] == "VALID_UINT64_NS":
            require(kind == "d12_duration_valid_v1" and
                    exact_value["duration_ns"] ==
                        _canonical_uint64_token(payload["token"]),
                    "D12 duration result differs from raw token")
        else:
            require(kind == "d12_duration_invalid_v1" and
                    exact_value["invalid_state"] == payload["state"],
                    "D12 duration invalid state differs from raw payload")
    elif raw_kind == "d12_payload_raw_v1":
        if payload["state"] == "VALID_UINT64_BYTES":
            require(kind == "d12_payload_valid_v1" and
                    exact_value["payload_bytes"] ==
                        _canonical_uint64_token(payload["token"]),
                    "D12 payload result differs from raw token")
        else:
            require(kind == "d12_payload_invalid_v1" and
                    exact_value["invalid_state"] == payload["state"],
                    "D12 payload invalid state differs from raw payload")
    elif raw_kind == "d12_rss_raw_v1":
        if payload["state"] == "VALID_UINT64_BYTES":
            require(kind == "d12_rss_valid_v1" and
                    exact_value["baseline_rss_bytes"] ==
                        _canonical_uint64_token(payload["baseline_token"]) and
                    exact_value["observed_rss_bytes"] ==
                        _canonical_uint64_token(payload["observed_token"]),
                    "D12 RSS result differs from raw tokens")
        else:
            require(kind == "d12_rss_invalid_v1" and
                    exact_value["invalid_state"] == payload["state"] and
                    exact_value["baseline_rss_bytes"] ==
                        (None if payload["baseline_token"] is None else
                         _canonical_uint64_token(
                            payload["baseline_token"])) and
                    exact_value["observed_rss_bytes"] ==
                        (None if payload["observed_token"] is None else
                         _canonical_uint64_token(
                            payload["observed_token"])),
                    "D12 RSS invalid state differs from raw payload")
    elif raw_kind == "d12_tsan_instrumentation_raw_v1":
        require(kind == "d12_tsan_instrumentation_summary_v1" and
                exact_value["instrumentation_complete"] ==
                    (payload["state"] == "COMPLETE") and
                exact_value["instrumented_translation_units_sha256"] ==
                    payload["instrumented_translation_units_sha256"],
                "D12 instrumentation result differs from raw payload")
        if payload["state"] == "COMPLETE" and \
                expected_instrumented_translation_units is not None:
            require(payload["instrumented_translation_units_sha256"] ==
                    expected_instrumented_translation_units,
                    "D12 instrumentation digest differs from authenticated audit")
    else:
        require(raw_kind == "d12_tsan_finding_raw_v1" and
                kind == "d12_tsan_finding_summary_v1",
                "D12 finding raw/result kind")
        if payload["state"] == "COMPLETE":
            require(exact_value["finding_count"] ==
                    _canonical_uint64_token(payload[
                        "finding_count_token"]) and
                    exact_value["sanitizer_abort"] is False and
                    exact_value["sanitizer_report_sha256"] is None,
                    "D12 finding result differs from raw count")
        elif payload["state"] == "SANITIZER_ABORT":
            require(exact_value["finding_count"] is None and
                    exact_value["sanitizer_abort"] is True and
                    exact_value["sanitizer_report_sha256"] ==
                        payload["sanitizer_report_sha256"],
                    "D12 finding result differs from raw abort")
        else:
            require(payload["state"] == "EXECUTION_UNAVAILABLE" and
                    exact_value["finding_count"] is None and
                    exact_value["sanitizer_abort"] is False and
                    exact_value["sanitizer_report_sha256"] is None,
                    "D12 unavailable finding execution must remain incomplete")
    return True


def _d12_tsan_report_relative_path(key):
    validate_d12_key(key, "d12_instrumented_tsan")
    require(key[13] == "tsan_finding_count",
            "D12 sanitizer report key quantity")
    tuple_digest = sha256_bytes(jcs_bytes(key[:5]))
    return ("anchored-row-d12-v1/process/tsan-reports/" +
            tuple_digest + ".stderr")


def _validate_d12_tsan_process_pair(records, expected_executables=None):
    require(set(records) == {
                "instrumentation_coverage", "tsan_finding_count"},
            "D12 TSan process lacks its exact two raw summaries")
    instrumentation, instrumentation_provenance = records[
        "instrumentation_coverage"]
    finding, finding_provenance = records["tsan_finding_count"]
    require(instrumentation_provenance != finding_provenance and
            instrumentation_provenance["pid"] != finding_provenance["pid"] and
            instrumentation_provenance["process_tuple_sha256"] ==
                finding_provenance["process_tuple_sha256"],
            "D12 TSan summaries do not bind two fresh tuple processes")
    observed_executables = {
        instrumentation_provenance["executable_sha256"],
        finding_provenance["executable_sha256"]}
    require(len(observed_executables) == 2 and
            (expected_executables is None or
             observed_executables == set(expected_executables)),
            "D12 TSan summaries do not cover both authenticated executables")
    empty_stderr = sha256_bytes(b"")
    instrumentation_failed = (
        instrumentation_provenance["exit_kind"] == "SIGNALED" or
        (instrumentation_provenance["exit_kind"] == "EXITED" and
         instrumentation_provenance["exit_code"] != 0))
    finding_failed = (finding_provenance["exit_kind"] == "SIGNALED" or
              (finding_provenance["exit_kind"] == "EXITED" and
               finding_provenance["exit_code"] != 0))
    require(not instrumentation_failed and
            instrumentation_provenance["exit_kind"] == "EXITED" and
            instrumentation_provenance["exit_code"] == 0 and
            instrumentation_provenance["stderr_sha256"] == empty_stderr and
            instrumentation["state"] == "COMPLETE",
            "D12 instrumentation summary lacks its successful process")
    if finding_failed:
        require(
                finding["state"] == "SANITIZER_ABORT",
                "D12 failed TSan process is not an exact sanitizer abort")
    else:
        require(finding_provenance["exit_kind"] == "EXITED" and
                finding_provenance["exit_code"] == 0 and
                finding_provenance["stderr_sha256"] == empty_stderr and
                finding["state"] == "COMPLETE",
                "D12 successful TSan process lacks a complete finding count")
    return True


class D12WorkerInventoryVerifier:
    """Derive the complete frozen worker-sidecar universe from B2 evidence."""

    @staticmethod
    def _provider_record_bytes(row):
        sample = row["sample_id"].encode("utf-8")
        encoded = bytearray(b"B2ROWV1")
        encoded.extend(struct.pack("<i", row["face_row"]))
        encoded.extend(struct.pack("<I", len(sample)))
        encoded.extend(sample)
        encoded.extend(struct.pack("<I", ROW_ORDER.index(row["row_kind"])))
        encoded.extend(struct.pack("<I", len(row["source_ids"])))
        for source_id, coefficient in zip(row["source_ids"],
                                          row["coefficients"]):
            encoded.extend(struct.pack("<i", source_id))
            encoded.extend(struct.pack("<d", coefficient))
        return bytes(encoded)

    @staticmethod
    def _bind_descriptor_inventory(expected, descriptors):
        actual_paths = [item["relative_path"] for item in descriptors]
        require(actual_paths == sorted(set(actual_paths), key=jcs_bytes) and
                set(actual_paths) <= set(expected),
                "D12 worker sidecar inventory extra/duplicate/reordered")
        bound = {}
        for descriptor in descriptors:
            path = descriptor["relative_path"]
            require(path not in bound and
                    descriptor["availability"]["state"] == "PRESENT" and
                    descriptor["record_count"] == expected[path][0] and
                    descriptor["byte_length"] > 0 and
                    descriptor["sha256"] ==
                        descriptor["availability"]["sha256"] and
                    (expected[path][1] is None or
                     descriptor["sha256"] == expected[path][1]),
                    "D12 worker descriptor/count binding drift")
            bound[path] = descriptor
        return bound

    @staticmethod
    def _anchored_evaluate(row, anchor_source_id, sources):
        anchor_index = row["source_ids"].index(anchor_source_id)
        anchor_value = sources[anchor_index]
        accumulator = 0.0
        for coefficient, source in zip(row["coefficients"], sources):
            delta = float(source - anchor_value)
            term = float(coefficient * delta)
            accumulator = float(accumulator + term)
            require(math.isfinite(delta) and math.isfinite(term) and
                    math.isfinite(accumulator),
                    "D12 representation evaluation nonfinite intermediate")
        result = accumulator
        if row["row_kind"] == "position":
            result = float(anchor_value + result)
        require(math.isfinite(result),
                "D12 representation evaluation nonfinite result")
        return binary64_bits_hex(result)

    @classmethod
    def _case_contract(cls, case, artifact_root, fixture,
                       global_provider_digest=None,
                       global_representation_digest=None,
                       global_representation_count=None):
        report = _artifact_report(artifact_root, case)
        provider_digest = hashlib.sha256()
        representation_digest = hashlib.sha256(b"[")
        representation_count = 0
        inputs = (
            ("fixture_x", 0), ("fixture_y", 1), ("fixture_z", 2),
            ("positive_zero", 0.0), ("positive_one", 1.0),
            ("negative_one", -1.0), ("positive_2p20", 2.0 ** 20),
            ("negative_2p20", -(2.0 ** 20)))
        inputs = sorted(inputs, key=lambda item: jcs_bytes(item[0]))
        # B2 authenticates this artifact in emitted sample-major order, with
        # ROW_ORDER inside every sample.  JCS-sorting row_kind changes the
        # frozen B2ROWV1 stream and is only appropriate for result-ledger keys.
        for row in report["rows"]:
            provider_bytes = cls._provider_record_bytes(row)
            provider_digest.update(provider_bytes)
            if global_provider_digest is not None:
                global_provider_digest.update(provider_bytes)
            anchor_source_id = fixture["faces"][row["face_row"]][0]
            require(anchor_source_id in row["source_ids"],
                    "D12 oriented v0 anchor absent from provider row")
            for input_id, input_value in inputs:
                if isinstance(input_value, int):
                    sources = [fixture["vertices"][source_id][input_value]
                               for source_id in row["source_ids"]]
                else:
                    sources = [input_value] * len(row["source_ids"])
                record = [
                    case["content_identity_key"],
                    case["approximation_level"], row["face_row"],
                    None if row["local_corner_or_none"] == -1 else
                    row["local_corner_or_none"], row["sample_id"],
                    row["row_kind"], input_id,
                    cls._anchored_evaluate(row, anchor_source_id, sources)]
                encoded_record = jcs_bytes(record)
                if representation_count:
                    representation_digest.update(b",")
                representation_digest.update(encoded_record)
                representation_count += 1
                if global_representation_digest is not None:
                    if global_representation_count[0]:
                        global_representation_digest.update(b",")
                    global_representation_digest.update(encoded_record)
                    global_representation_count[0] += 1
        representation_digest.update(b"]")
        provider_count = sum(report["row_kind_counts"].values())
        require(representation_count == provider_count * 8 and
                provider_digest.hexdigest() ==
                    case["canonical_rows_sha256"],
                "D12 independent case reference derivation drift")
        return (provider_count, provider_digest.hexdigest(),
                representation_count, representation_digest.hexdigest())

    def __init__(self, envelope, checkpoint_cases, artifact_root):
        workload = envelope["workload"]
        row_contracts = {}
        global_provider_digest = hashlib.sha256()
        global_representation_digest = hashlib.sha256(b"[")
        global_representation_count = [0]
        fixture_inventory = {}
        for job in B2.valid_content_jobs(B2.load_manifest()):
            vertices, faces, _ = B2.independent_mesh(job)
            fixture_inventory[job["content_identity_key"]] = {
                "vertices": vertices, "faces": faces}
        for case in checkpoint_cases.values():
            if normalized_cache_mode(case["applicable_mode"]) != \
                    "cache_disabled":
                continue
            key = (case["content_identity_key"],
                   case["approximation_level"])
            contract = self._case_contract(
                case, artifact_root,
                fixture_inventory[case["content_identity_key"]],
                global_provider_digest, global_representation_digest,
                global_representation_count)
            count, provider_sha256, representation_count, \
                representation_sha256 = contract
            require(key not in row_contracts and count > 0,
                    "D12 checkpoint row-count universe drift")
            row_contracts[key] = (
                count, provider_sha256, representation_count,
                representation_sha256)
        require(len(row_contracts) == 98 and
                sum(item[0] for item in row_contracts.values()) == 693000,
                "D12 serial provider cardinality differs from checkpoint")
        global_representation_digest.update(b"]")
        require(workload["provider_serial_reference"]["record_count"] ==
                    693000 and
                workload["provider_serial_reference"]["sha256"] ==
                    global_provider_digest.hexdigest() and
                workload["representation_serial_reference"][
                    "record_count"] == global_representation_count[0] ==
                    5544000 and
                workload["representation_serial_reference"]["sha256"] ==
                    global_representation_digest.hexdigest(),
                "D12 serial references differ from independent derivation")
        self.case_references = {
            key: {"provider": value[1], "representation": value[3]}
            for key, value in row_contracts.items()}

        expected = {}
        provider_total = {"cache_disabled": 0, "threaded_cache": 0}
        representation_total = {
            "cache_disabled": 0, "threaded_cache": 0}
        for content_id, level, mode, worker_count in \
                B2.expected_threading_identities(B2.load_manifest()):
            cache_mode = ("threaded_cache" if mode ==
                          "SurfaceFactoryCacheThreaded" else mode)
            require(cache_mode in provider_total,
                    "D12 threading mode normalization drift")
            (record_count, provider_sha256, representation_count,
             representation_sha256) = row_contracts[(content_id, level)]
            for round_index in range(20):
                for worker_index in range(worker_count):
                    prefix = (
                        "anchored-row-d12-v1/workers/{}/{}/level-{}/"
                        "workers-{}/round-{:02d}/worker-{}".format(
                            cache_mode, content_id, level, worker_count,
                            round_index, worker_index))
                    provider_path = prefix + "-provider.b2rowv1"
                    representation_path = prefix + "-representation.json"
                    require(provider_path not in expected and
                            representation_path not in expected,
                            "D12 expected worker path collision")
                    expected[provider_path] = (record_count,
                                               provider_sha256)
                    expected[representation_path] = (
                        representation_count, representation_sha256)
                    provider_total[cache_mode] += record_count
                    representation_total[cache_mode] += record_count * 8
        require(len(expected) == 54880 and
                provider_total == {
                    "cache_disabled": 97020000,
                    "threaded_cache": 97020000} and
                representation_total == {
                    "cache_disabled": 776160000,
                    "threaded_cache": 776160000},
                "D12 worker inventory frozen cardinality drift")

        self.expected_paths = frozenset(expected)
        self.descriptors = self._bind_descriptor_inventory(
            expected, workload["sidecars"])

    @staticmethod
    def _paths_for_key(key):
        content_id, level, _, cache_mode, worker_count, worker_index, \
            round_index = key[:7]
        prefix = (
            "anchored-row-d12-v1/workers/{}/{}/level-{}/workers-{}/"
            "round-{:02d}/worker-{}".format(
                cache_mode, content_id, level, worker_count, round_index,
                worker_index))
        return prefix + "-provider.b2rowv1", \
            prefix + "-representation.json"

    def require_target(self, key, target, exact_value=None):
        reference = self.case_references[(key[0], key[1])]
        require(target["provider_expected_sha256"] ==
                    reference["provider"] and
                target["representation_expected_sha256"] ==
                    reference["representation"],
                "D12 result target differs from serial-reference slice")
        if exact_value is not None:
            require(exact_value["provider_expected_sha256"] ==
                        reference["provider"] and
                    exact_value["representation_expected_sha256"] ==
                        reference["representation"],
                    "D12 result value differs from serial-reference slice")
        return True

    def require_result_sidecars(self, key, exact_value):
        provider_path, representation_path = self._paths_for_key(key)
        require(exact_value["provider_sidecar"] ==
                    self.descriptors.get(provider_path) and
                exact_value["representation_sidecar"] ==
                    self.descriptors.get(representation_path),
                "D12 result sidecar is not its inventory-owned worker cell")
        return True

    def require_absent_sidecars(self, key):
        provider_path, representation_path = self._paths_for_key(key)
        require(provider_path in self.expected_paths and
                representation_path in self.expected_paths and
                provider_path not in self.descriptors and
                representation_path not in self.descriptors,
                "D12 aborted result retained a worker sidecar")
        return True


class D12EvidenceVerifier:
    """Authenticate D12 worker artifacts and raw observation slices."""

    PROCESS_OBSERVATION_PATH = (
        "anchored-row-d12-v1/process/process-observations.json")
    REPRESENTATION_INPUTS = frozenset({
        "fixture_x", "fixture_y", "fixture_z", "positive_zero",
        "positive_one", "negative_one", "positive_2p20", "negative_2p20"})

    def __init__(self, bundle_root, envelope=None, worker_inventory=None,
                 expected_instrumented_translation_units=None):
        self.bundle_root = pathlib.Path(bundle_root).resolve()
        self.file_bindings = {}
        self.descriptor_bindings = {}
        self.top_level_slices = {}
        self.envelope = envelope
        self.worker_inventory = worker_inventory
        self.expected_instrumented_translation_units = \
            expected_instrumented_translation_units

    def close(self):
        for table, _ in self.top_level_slices.values():
            table.close()
        self.top_level_slices.clear()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _path(self, relative_path):
        require(isinstance(relative_path, str) and relative_path and
                not pathlib.PurePosixPath(relative_path).is_absolute(),
                "D12 evidence relative path")
        path = (self.bundle_root / relative_path).resolve()
        require(path.is_relative_to(self.bundle_root) and path.is_file(),
                "D12 evidence path missing/outside bundle")
        return path

    def sidecar(self, descriptor):
        require(descriptor["availability"]["state"] == "PRESENT" and
                type(descriptor["byte_length"]) is int and
                descriptor["byte_length"] > 0 and
                type(descriptor["record_count"]) is int and
                descriptor["record_count"] > 0,
                "D12 complete sidecar must contain records")
        path = self._path(descriptor["relative_path"])
        descriptor_binding = (
            descriptor["byte_length"], descriptor["record_count"],
            descriptor["sha256"], descriptor["availability"]["sha256"])
        previous_descriptor = self.descriptor_bindings.get(path)
        if previous_descriptor is not None:
            require(previous_descriptor == descriptor_binding,
                    "D12 path is claimed by inconsistent descriptors")
            return True
        observed = self.file_bindings.get(path)
        if observed is None:
            observed = (path.stat().st_size, sha256_file(path))
            self.file_bindings[path] = observed
        require(observed == (descriptor["byte_length"],
                             descriptor["sha256"]) and
                descriptor["availability"]["sha256"] ==
                descriptor["sha256"],
                "D12 sidecar byte/hash binding mismatch")
        if path.suffix == ".json":
            digest = hashlib.sha256()
            count = 0
            previous_key = None
            next_offset = 1
            representation_group = None
            representation_inputs = set()
            tsan_processes = {}
            worker_match = re.fullmatch(
                r"anchored-row-d12-v1/workers/(?:cache_disabled|"
                r"threaded_cache)/([^/]+)/level-([2-8])/workers-[124]/"
                r"round-[0-1][0-9]/worker-[0-3]-representation\.json",
                descriptor["relative_path"])
            slice_table = (tempfile.TemporaryFile()
                           if descriptor["relative_path"] ==
                           self.PROCESS_OBSERVATION_PATH else None)
            for record, encoded in _iter_canonical_result_records(
                    path, digest):
                if slice_table is not None:
                    key, payload, provenance = validate_d12_process_observation(
                        record)
                    if self.envelope is not None:
                        expected_binaries = ({
                            self.envelope["binaries"][
                                "provider_tsan"]["sha256"],
                            self.envelope["binaries"][
                                "representation_tsan"]["sha256"]}
                            if key[2] == "tsan" else {
                                self.envelope["binaries"][
                                    "provider_release"]["sha256"]})
                        require(provenance["executable_sha256"] in
                                expected_binaries,
                                "D12 raw observation executable drift")
                    if key[2] == "tsan":
                        tuple_key = jcs_bytes(key[:5])
                        summaries = tsan_processes.setdefault(tuple_key, {})
                        require(key[13] not in summaries,
                                "D12 persisted TSan summary duplicate")
                        summaries[key[13]] = (payload, provenance)
                    encoded_key = jcs_bytes(key)
                    require(previous_key is None or
                            previous_key < encoded_key,
                            "D12 process observation duplicate/key-order drift")
                    previous_key = encoded_key
                    slice_table.write(struct.pack(">QQ", next_offset,
                                                  len(encoded)))
                    next_offset += len(encoded) + 1
                else:
                    require(isinstance(record, list) and len(record) == 8,
                            "D12 representation record shape")
                    (content_id, level, face_id, local_corner, sample_id,
                     row_kind, input_id, output_bits) = record
                    require(isinstance(content_id, str) and content_id and
                            type(level) is int and 2 <= level <= 8 and
                            type(face_id) is int and face_id >= 0 and
                            (local_corner is None or
                             type(local_corner) is int and
                             local_corner >= 0) and
                            isinstance(sample_id, str) and sample_id and
                            row_kind in ROW_ORDER and
                            input_id in self.REPRESENTATION_INPUTS and
                            re.fullmatch(r"[0-9a-f]{16}", output_bits or ""),
                            "D12 representation record value")
                    if worker_match is not None:
                        require(content_id == worker_match.group(1) and
                                level == int(worker_match.group(2)),
                                "D12 representation record/path ownership")
                    group = tuple(record[:6])
                    if (representation_group is not None and
                            group != representation_group):
                        require(representation_inputs ==
                                self.REPRESENTATION_INPUTS,
                                "D12 representation row lacks eight inputs")
                        representation_inputs = set()
                    representation_group = group
                    require(input_id not in representation_inputs,
                            "D12 representation row duplicates an input")
                    representation_inputs.add(input_id)
                    encoded_key = jcs_bytes(record[:-1])
                    require(previous_key is None or
                            previous_key < encoded_key,
                            "D12 representation duplicate/key-order drift")
                    previous_key = encoded_key
                count += 1
            if slice_table is None:
                require(representation_group is not None and
                        representation_inputs == self.REPRESENTATION_INPUTS,
                        "D12 representation final row lacks eight inputs")
            else:
                expected_tsan_binaries = (None if self.envelope is None else {
                    self.envelope["binaries"]["provider_tsan"]["sha256"],
                    self.envelope["binaries"][
                        "representation_tsan"]["sha256"]})
                require(all(_validate_d12_tsan_process_pair(
                                records, expected_tsan_binaries)
                            for records in tsan_processes.values()),
                        "D12 persisted TSan process-pair validation")
            require(count == descriptor["record_count"] and
                    digest.hexdigest() == descriptor["sha256"],
                    "D12 JSON sidecar canonical record-count mismatch")
            if slice_table is not None:
                slice_table.flush()
                self.top_level_slices[path] = (slice_table, count)
        elif path.suffix == ".b2rowv1":
            count = 0
            previous_row_key = None
            provider_group = None
            provider_ordinals = set()
            with path.open("rb") as stream:
                while stream.tell() < observed[0]:
                    require(stream.read(7) == b"B2ROWV1",
                            "D12 provider sidecar row magic")
                    raw_face = stream.read(4)
                    require(len(raw_face) == 4,
                            "D12 provider sidecar face-row truncation")
                    face_id = struct.unpack("<i", raw_face)[0]
                    require(face_id >= 0,
                            "D12 provider sidecar negative face row")
                    raw_length = stream.read(4)
                    require(len(raw_length) == 4,
                            "D12 provider sample-length truncation")
                    sample_length = struct.unpack("<I", raw_length)[0]
                    sample = stream.read(sample_length)
                    require(len(sample) == sample_length and b"\0" not in
                            sample, "D12 provider sample-id truncation/NUL")
                    sample.decode("utf-8", errors="strict")
                    raw_ordinal = stream.read(4)
                    raw_terms = stream.read(4)
                    require(len(raw_ordinal) == len(raw_terms) == 4,
                            "D12 provider row header truncation")
                    row_ordinal = struct.unpack("<I", raw_ordinal)[0]
                    require(row_ordinal < len(ROW_ORDER),
                            "D12 provider row-kind ordinal")
                    term_count = struct.unpack("<I", raw_terms)[0]
                    require(term_count > 0,
                            "D12 provider row has no coefficients")
                    previous_source = None
                    for _ in range(term_count):
                        raw_source = stream.read(4)
                        raw_bits = stream.read(8)
                        require(len(raw_source) == 4 and len(raw_bits) == 8,
                                "D12 provider coefficient truncation")
                        source = struct.unpack("<i", raw_source)[0]
                        coefficient = struct.unpack("<d", raw_bits)[0]
                        require((previous_source is None or
                                 previous_source < source) and
                                math.isfinite(coefficient),
                                "D12 provider source order/nonfinite")
                        previous_source = source
                    row_key = (face_id, sample, row_ordinal)
                    require(previous_row_key is None or
                            previous_row_key < row_key,
                            "D12 provider duplicate/row-order drift")
                    group = (face_id, sample)
                    if provider_group is not None and group != provider_group:
                        require(provider_ordinals == set(range(len(ROW_ORDER))),
                                "D12 provider sample lacks six rows")
                        provider_ordinals = set()
                    provider_group = group
                    require(row_ordinal not in provider_ordinals,
                            "D12 provider sample duplicates row kind")
                    provider_ordinals.add(row_ordinal)
                    previous_row_key = row_key
                    count += 1
                final_position = stream.tell()
            require(provider_group is not None and
                    provider_ordinals == set(range(len(ROW_ORDER))) and
                    count == descriptor["record_count"] and
                    final_position == observed[0],
                    "D12 provider sidecar record-count mismatch")
        else:
            raise QualificationError("unknown D12 sidecar extension")
        self.descriptor_bindings[path] = descriptor_binding
        return True

    def raw_observation(self, key, binding):
        require(binding["availability"]["state"] == "PRESENT" and
                binding["availability"]["sha256"] == binding["sha256"] and
                type(binding["byte_offset"]) is int and
                type(binding["byte_length"]) is int and
                binding["byte_length"] > 0,
                "D12 raw observation must be a present nonempty slice")
        path = self._path(binding["relative_path"])
        require(binding["relative_path"] == self.PROCESS_OBSERVATION_PATH,
                "D12 raw slice path drift")
        require(path in self.file_bindings,
                "D12 raw slice lacks a rescanned enclosing sidecar")
        require(binding["byte_offset"] + binding["byte_length"] <=
                path.stat().st_size,
                "D12 raw observation slice outside artifact")
        table, count = self.top_level_slices.get(path, (None, 0))
        require(table is not None,
                "D12 raw slice lacks process-record boundary index")
        low, high = 0, count
        matched_length = None
        while low < high:
            middle = (low + high) // 2
            table.seek(middle * 16)
            raw_entry = table.read(16)
            require(len(raw_entry) == 16,
                    "D12 process-record boundary index truncated")
            offset, length = struct.unpack(">QQ", raw_entry)
            if offset < binding["byte_offset"]:
                low = middle + 1
            else:
                high = middle
                if offset == binding["byte_offset"]:
                    matched_length = length
        if low < count:
            table.seek(low * 16)
            offset, length = struct.unpack(">QQ", table.read(16))
            if offset == binding["byte_offset"]:
                matched_length = length
        require(matched_length == binding["byte_length"],
                "D12 raw slice is not one complete top-level record")
        with path.open("rb") as stream:
            stream.seek(binding["byte_offset"])
            raw = stream.read(binding["byte_length"])
        require(len(raw) == binding["byte_length"] and
                sha256_bytes(raw) == binding["sha256"],
                "D12 raw observation slice hash mismatch")
        record = strict_json_bytes(raw)
        require(jcs_bytes(record) == raw,
                "D12 raw observation slice is not canonical")
        observed_key, payload, _ = validate_d12_process_observation(record)
        require(observed_key == key,
                "D12 raw observation does not own result key")
        if key[13] == "tsan_finding_count":
            report_relative = _d12_tsan_report_relative_path(key)
            report_candidate = self.bundle_root / report_relative
            report_path = report_candidate.resolve()
            require(report_path.is_relative_to(self.bundle_root),
                    "D12 sanitizer report path escapes bundle")
            if payload["state"] == "SANITIZER_ABORT":
                require(report_candidate.is_file() and
                        not report_candidate.is_symlink() and
                        sha256_file(report_candidate) ==
                        payload["sanitizer_report_sha256"],
                        "D12 sanitizer report bytes/digest mismatch")
            else:
                require(not report_candidate.exists(),
                        "D12 non-abort tuple published a sanitizer report")
        return payload

    def result_record(self, key, exact_value, target=None):
        if self.envelope is not None and key[13] == "row_digest":
            require(self.worker_inventory is not None,
                    "D12 row target lacks derived reference inventory")
            self.worker_inventory.require_target(
                key, target, exact_value)
        if exact_value is None:
            if key[13] == "row_digest" and self.worker_inventory is not None:
                self.worker_inventory.require_absent_sidecars(key)
            return True
        kind = _contract_kind(exact_value)
        if key[13] == "instrumentation_coverage":
            require(self.expected_instrumented_translation_units is not None and
                    target["expected_translation_units_sha256"] ==
                        self.expected_instrumented_translation_units and
                    exact_value["expected_translation_units_sha256"] ==
                        self.expected_instrumented_translation_units,
                    "D12 instrumentation target is not audit-derived")
        raw = exact_value.get("raw_observation")
        if raw is not None:
            payload = self.raw_observation(key, raw)
            validate_d12_raw_exact_value(
                payload, exact_value,
                self.expected_instrumented_translation_units)
        if kind in {"d12_concurrency_value_v1",
                    "d12_tsan_threaded_row_value_v1"}:
            if self.worker_inventory is not None:
                self.worker_inventory.require_result_sidecars(
                    key, exact_value)
            self.sidecar(exact_value["provider_sidecar"])
            self.sidecar(exact_value["representation_sidecar"])
        elif kind == "d12_concurrency_abort_v1":
            require(self.worker_inventory is not None,
                    "D12 concurrency abort lacks worker inventory")
            self.worker_inventory.require_absent_sidecars(key)
        return True


class D12CrossRecordValidator:
    """Enforce D12 statistics whose truth spans canonical result records."""

    def __init__(self):
        self.preparation = {}
        self.rss = {}
        self.abort_summary_keys = set()
        self.threaded_null_summary_keys = set()
        self.race_summary_keys = set()

    @staticmethod
    def case_key(key):
        return tuple(key[:4])

    def add(self, criterion_id, record):
        key, outcome, value, target, reason = record
        kind = _contract_kind(value)
        if criterion_id == "d12_preparation_cost":
            group = self.preparation.setdefault(
                self.case_key(key), {"measured": {}, "median": None})
            if kind == "d12_duration_valid_v1":
                if key[13] == "preparation_duration_ns":
                    require(key[8] not in group["measured"],
                            "D12 duplicate preparation repeat")
                    group["measured"][key[8]] = value["duration_ns"]
                else:
                    require(group["median"] is None,
                            "D12 duplicate preparation median")
                    group["median"] = value["duration_ns"]
        elif criterion_id == "d12_peak_rss":
            group = self.rss.setdefault(
                self.case_key(key), {"baseline": None, "saw_baseline": False})
            claimed = value.get("baseline_rss_bytes") if value else None
            if claimed is not None:
                if group["baseline"] is None:
                    group["baseline"] = claimed
                require(claimed == group["baseline"],
                        "D12 RSS record changed frozen case baseline")
            if key[12] == "pre_refiner_baseline":
                require(not group["saw_baseline"] and
                        kind == "d12_rss_valid_v1" and
                        value["observed_rss_bytes"] == claimed and
                        value["rss_delta_bytes"] == 0,
                        "D12 RSS frozen baseline record mismatch")
                group["saw_baseline"] = True
        elif (criterion_id == "d12_cache_disabled_concurrency" and
              kind == "d12_concurrency_abort_v1"):
            self.abort_summary_keys.add(jcs_bytes(
                value["tsan_finding_summary_key"]))
        elif (criterion_id == "d12_instrumented_tsan" and
              key[3] == "threaded_cache" and key[13] == "row_digest" and
              value is None):
            summary_key = list(key)
            summary_key[5] = None
            summary_key[6] = None
            summary_key[12] = "sanitizer_summary"
            summary_key[13] = "tsan_finding_count"
            self.threaded_null_summary_keys.add(jcs_bytes(summary_key))
        elif (criterion_id == "d12_instrumented_tsan" and
              key[13] == "tsan_finding_count" and value is not None and
              value.get("sanitizer_abort") is True and
              SHA256_RE.fullmatch(value.get(
                  "sanitizer_report_sha256") or "") is not None):
            self.race_summary_keys.add(jcs_bytes(key))

    def finish(self):
        for group in self.preparation.values():
            if group["median"] is not None:
                require(sorted(group["measured"]) == list(range(15)) and
                        group["median"] == sorted(
                            group["measured"].values())[7],
                        "D12 preparation median is not eighth sorted repeat")
        require(all(group["saw_baseline"] and group["baseline"] is not None
                    for group in self.rss.values()),
                "D12 RSS case lacks one frozen baseline")
        require(self.abort_summary_keys <= self.race_summary_keys,
                "D12 concurrency abort lacks same-tuple TSan abort report")
        require(self.threaded_null_summary_keys <= self.race_summary_keys,
                "D12 threaded null row lacks same-tuple TSan abort report")
        return True


class FilteredJcsLedger:
    """Hash a selected canonical-record subsequence as one JCS array."""

    def __init__(self):
        self.digest = hashlib.sha256(b"[")
        self.count = 0

    def add(self, encoded):
        if self.count:
            self.digest.update(b",")
        self.digest.update(encoded)
        self.count += 1

    def finish(self):
        value = self.digest.copy()
        value.update(b"]")
        return value.hexdigest()


class D12SerialContextVerifier:
    """Recompute every serial-only-context field from result ledgers."""

    def __init__(self):
        self.cache_concurrency = FilteredJcsLedger()
        self.cache_tsan_summary = FilteredJcsLedger()
        self.threaded_tsan_summary = FilteredJcsLedger()
        self.threaded_tsan_rows = FilteredJcsLedger()
        self.all_tsan = FilteredJcsLedger()
        self.failure_records = []
        self.failure_ledger = FilteredJcsLedger()
        expected = [[content_id, level,
                     ("threaded_cache" if mode ==
                      "SurfaceFactoryCacheThreaded" else mode), workers]
                    for content_id, level, mode, workers in
                    B2.expected_threading_identities(B2.load_manifest())]
        self.tuple_keys = tuple(sorted((jcs_bytes(key) for key in expected)))
        self.expected_tuple_key_set = set(self.tuple_keys)
        self.observed_summary_tuples = set()
        self.cache_concurrency_pass = True
        self.cache_tsan_pass = True

    def add(self, criterion_id, record, encoded_record):
        key, outcome, _, _, reason = record
        if criterion_id == "d12_cache_disabled_concurrency":
            self.cache_concurrency.add(encoded_record)
            self.cache_concurrency_pass &= outcome == "PASS"
            return
        if criterion_id != "d12_instrumented_tsan":
            return
        self.all_tsan.add(encoded_record)
        mode, quantity = key[3], key[13]
        if quantity in {"instrumentation_coverage", "tsan_finding_count"}:
            tuple_key = jcs_bytes([key[0], key[1], mode, key[4]])
            require(tuple_key in self.expected_tuple_key_set,
                    "D12 TSan summary tuple outside frozen universe")
            self.observed_summary_tuples.add(tuple_key)
            if mode == "cache_disabled":
                self.cache_tsan_summary.add(encoded_record)
                self.cache_tsan_pass &= outcome == "PASS"
            else:
                self.threaded_tsan_summary.add(encoded_record)
        elif mode == "threaded_cache" and quantity == "row_digest":
            self.threaded_tsan_rows.add(encoded_record)
        if mode == "threaded_cache" and outcome == "FAIL":
            failure = [key, reason]
            self.failure_records.append(failure)
            self.failure_ledger.add(jcs_bytes(failure))

    def finish(self):
        require(self.observed_summary_tuples in (
                    set(), self.expected_tuple_key_set),
                "D12 serial context tuple universe incomplete")
        tuple_keys = [strict_json_bytes(value) for value in self.tuple_keys]
        return {
            "tuple_count": 588,
            "all_tuple_keys_sha256": sha256_bytes(jcs_bytes(tuple_keys)),
            "cache_disabled_concurrency_cell_count":
                self.cache_concurrency.count,
            "cache_disabled_concurrency_ledger_sha256":
                self.cache_concurrency.finish(),
            "cache_disabled_concurrency_pass":
                self.cache_concurrency_pass,
            "cache_disabled_tsan_summary_cell_count":
                self.cache_tsan_summary.count,
            "cache_disabled_tsan_summary_sha256":
                self.cache_tsan_summary.finish(),
            "cache_disabled_tsan_pass": self.cache_tsan_pass,
            "threaded_tsan_summary_cell_count":
                self.threaded_tsan_summary.count,
            "threaded_tsan_summary_sha256":
                self.threaded_tsan_summary.finish(),
            "threaded_tsan_row_digest_cell_count":
                self.threaded_tsan_rows.count,
            "threaded_tsan_row_digest_sha256":
                self.threaded_tsan_rows.finish(),
            "all_tsan_cell_count": self.all_tsan.count,
            "all_tsan_result_ledger_sha256": self.all_tsan.finish(),
            "failure_records": self.failure_records,
            "failure_records_sha256": self.failure_ledger.finish(),
        }


def _bound_d12_envelope(report, bundle_root):
    """Load a complete included D12 envelope by its report-bound digest."""
    binding = report.get("d12_artifact")
    if binding is None:
        return None
    if binding["representation_work"] != "INCLUDED":
        return None
    expected_sha256 = binding["availability"]["sha256"]
    matches = []
    for path in pathlib.Path(bundle_root).glob("*.json"):
        if path.is_file() and sha256_file(path) == expected_sha256:
            matches.append(path)
    require(len(matches) == 1,
            "included D12 envelope is not uniquely present in bundle")
    raw = matches[0].read_bytes()
    root = strict_json_bytes(raw)
    require(jcs_bytes(root) == raw,
            "included D12 artifact bytes are not canonical JCS")
    envelope = (root.get("anchored_row_representation_d12")
                if isinstance(root, dict) else None)
    if envelope is None and isinstance(root, dict) and root.get(
            "schema_id") == "anchored-row-representation-d12-v1":
        envelope = root
    require(isinstance(envelope, dict),
            "included D12 envelope missing from bound artifact")
    validate_d12_envelope_contract(
        envelope, report["identity"]["git_end"]["git_commit"])
    require(envelope["binaries"]["provider_release"]["sha256"] ==
                report["binaries"]["row_provider"]["availability"][
                    "sha256"] and
            envelope["binaries"]["representation_release"]["sha256"] ==
                report["binaries"]["representation_candidate"][
                    "availability"]["sha256"],
            "D12 release binaries differ from report runtime bindings")
    require(envelope["platform"]["platform_state"] ==
                binding["execution_state"],
            "D12 envelope platform state differs from report binding")
    for binary in envelope["binaries"].values():
        previous = None
        for source in binary["source_inventory"]:
            encoded = jcs_bytes(source)
            require(previous is None or previous < encoded,
                    "D12 binary source inventory duplicate/order drift")
            previous = encoded
            source_path = (ROOT / source["path"]).resolve()
            require(source_path.is_relative_to(ROOT) and
                    source_path.is_file() and
                    sha256_file(source_path) == source["sha256"],
                    "D12 binary source differs from exact-head repository")
    return envelope


class ProviderRowVerifier:
    """Bind structure rows to the authenticated checkpoint artifacts."""

    def __init__(self, checkpoint_path, artifact_root, provider_binary,
                 report):
        require(checkpoint_path is not None and artifact_root is not None and
                provider_binary is not None,
                "structure validation requires checkpoint and provider artifacts")
        self.checkpoint_path = pathlib.Path(checkpoint_path).resolve()
        self.artifact_root = pathlib.Path(artifact_root).resolve()
        require(self.checkpoint_path.is_file() and self.artifact_root.is_dir(),
                "structure checkpoint/provider artifact path missing")
        require(sha256_file(self.checkpoint_path) ==
                report["checkpoint"]["availability"]["sha256"],
                "structure checkpoint does not match report binding")
        _, checkpoint, _, validated_checkpoint_sha256 = \
            B2A.validate_checkpoint_and_artifacts(
                self.checkpoint_path, self.artifact_root, provider_binary,
                report["checkpoint"]["git_head"])
        require(validated_checkpoint_sha256 ==
                report["checkpoint"]["availability"]["sha256"],
                "structure checkpoint full validation digest mismatch")
        self.checkpoint = checkpoint
        self.faces = {}
        for job in B2.valid_content_jobs(B2.load_manifest()):
            _, faces, _ = B2.independent_mesh(job)
            self.faces[job["content_identity_key"]] = faces
        self.cases = {}
        for case in ordered_bfr_cases(checkpoint):
            case_key = (case["content_identity_key"],
                        normalized_cache_mode(case["applicable_mode"]),
                        case["approximation_level"])
            require(case_key not in self.cases,
                    "structure checkpoint duplicate case")
            self.cases[case_key] = case
        self.loaded_case_key = None
        self.rows = None

    def _row_for_key(self, key):
        case_key = tuple(key[:3])
        case = self.cases.get(case_key)
        require(case is not None, "structure row has no checkpoint case")
        if case_key != self.loaded_case_key:
            artifact_path = self.artifact_root / case["complete_json_artifact"]
            require(sha256_file(artifact_path) ==
                    case["complete_json_artifact_sha256"],
                    "structure provider artifact archive hash mismatch")
            artifact = _artifact_report(self.artifact_root, case)
            self.rows = {}
            for row in artifact["rows"]:
                row_key = (row["face_row"],
                           None if row["local_corner_or_none"] == -1 else
                           row["local_corner_or_none"],
                           row["sample_id"], row["row_kind"])
                require(row_key not in self.rows,
                        "structure provider artifact duplicate row")
                self.rows[row_key] = row
            self.loaded_case_key = case_key
        row_key = (key[3], key[4], key[5], key[6])
        row = self.rows.get(row_key)
        require(row is not None, "structure provider row missing")
        return row

    def result_record(self, criterion_id, key, exact_value):
        row = self._row_for_key(key)
        if criterion_id == "relabel_exact_effective_coefficients":
            anchor_source = self.faces[key[0]][key[3]][ANCHORS.index(key[8])]
            expected = effective_numerators(row, anchor_source)
            require(exact_value["source_ids"] == row["source_ids"] and
                    exact_value["expected"] == [
                        _signed_dyadic_descriptor(expected[source_id])
                        for source_id in row["source_ids"]],
                    "relabel result differs from provider-derived exact row")
            return True
        if criterion_id == "binary64_basis_probe_diagnostic":
            anchor_source = self.faces[key[0]][key[3]][ANCHORS.index(key[8])]
            expected = effective_numerators(row, anchor_source)
            require(key[10] in expected and exact_value["exact_effective"] ==
                    _signed_dyadic_descriptor(expected[key[10]]),
                    "basis result differs from provider-derived exact row")
            return True
        require(criterion_id == "representation_structure",
                "provider row verifier criterion")
        require(exact_value["canonical_source_ids"] == row["source_ids"] and
                exact_value["provider_coefficient_bits"] == [
                    binary64_bits_hex(coefficient)
                    for coefficient in row["coefficients"]],
                "structure result differs from authenticated provider row")
        return True


def _read_command_profile(path_text):
    manifest_path = pathlib.Path(path_text).resolve()
    require(str(path_text) == str(manifest_path),
            "D12 command profile manifest path is not canonical")
    raw = manifest_path.read_bytes()
    manifest = strict_json_bytes(raw)
    require(jcs_bytes(manifest) == raw and isinstance(manifest, dict) and
            set(manifest) == {
                "schema_id", "working_directory", "environment",
                "compile_commands", "link_commands"} and
            manifest["schema_id"] == "d12-command-profile-manifest-v1" and
            manifest["working_directory"] == str(ROOT) and
            manifest["environment"] == _d12_rebuild_environment(),
            "D12 command profile manifest is not canonical/closed")
    result = {
        "working_directory": manifest["working_directory"],
        "environment": copy.deepcopy(manifest["environment"])}
    expected_sidecar_names = {
        "compile_commands": "compile-commands.json",
        "link_commands": "link-commands.json"}
    for field in ("compile_commands", "link_commands"):
        descriptor = manifest[field]
        require(isinstance(descriptor, dict) and
                set(descriptor) == {"relative_path", "sha256"} and
                isinstance(descriptor["relative_path"], str) and
                descriptor["relative_path"] == expected_sidecar_names[field] and
                SHA256_RE.fullmatch(descriptor["sha256"] or "") is not None,
                "D12 command sidecar descriptor is malformed: " + field)
        relative = pathlib.PurePosixPath(descriptor["relative_path"])
        path = manifest_path.parent / pathlib.Path(*relative.parts)
        require(not relative.is_absolute() and ".." not in relative.parts and
                descriptor["relative_path"] == relative.as_posix() and
                path == path.resolve() and path.parent == manifest_path.parent and
                path.is_file() and
                sha256_file(path) == descriptor["sha256"],
                "D12 command sidecar bytes/path differ: " + field)
        sidecar_raw = path.read_bytes()
        commands = strict_json_bytes(sidecar_raw)
        require(jcs_bytes(commands) == sidecar_raw and
                isinstance(commands, list) and commands and
                all(isinstance(command, list) and command and
                    all(isinstance(token, str) and token for token in command)
                    for command in commands),
                "D12 command sidecar is not canonical argv evidence: " + field)
        result[field] = commands
    require(manifest["compile_commands"]["relative_path"] !=
            manifest["link_commands"]["relative_path"],
            "D12 compile/link command sidecars are not distinct")
    return result


def _read_d12_opensubdiv_profile_manifest(path_text, field):
    manifest_path = pathlib.Path(path_text).resolve()
    require(str(path_text) == str(manifest_path),
            "D12 OpenSubdiv profile manifest path is not canonical: " + field)
    raw = manifest_path.read_bytes()
    manifest = strict_json_bytes(raw)
    require(jcs_bytes(manifest) == raw and isinstance(manifest, dict) and
            set(manifest) == {"schema_id", "field", "release", "tsan"} and
            manifest["schema_id"] ==
                "d12-opensubdiv-profile-artifacts-v1" and
            manifest["field"] == field,
            "D12 OpenSubdiv profile manifest is not canonical/closed: " +
            field)
    result = {}
    for profile_name in ("release", "tsan"):
        descriptor = manifest[profile_name]
        require(isinstance(descriptor, dict) and
                set(descriptor) == {"root", "artifact_path", "sha256"} and
                isinstance(descriptor.get("root"), str) and
                descriptor["root"] and
                isinstance(descriptor.get("artifact_path"), str) and
                descriptor["artifact_path"] and
                SHA256_RE.fullmatch(descriptor.get("sha256", "")) is not None,
                "D12 OpenSubdiv profile descriptor is malformed: " + field)
        root_text = _absolute_command_path(
            descriptor.get("root"), "",
            "D12 OpenSubdiv profile root is not canonical: " + field)
        artifact_text = _absolute_command_path(
            descriptor.get("artifact_path"),
            "/lib/libosdCPU.a" if field == "installed_library" else "",
            "D12 OpenSubdiv artifact path is not canonical: " + field)
        root = pathlib.Path(root_text)
        artifact = pathlib.Path(artifact_text)
        expected_artifact = root / {
            "build_root_provenance": "d12-opensubdiv-build-audit.json",
            "install_provenance": "d12-opensubdiv-install-provenance.json",
            "link_provenance": "d12-opensubdiv-link-provenance.json",
            "installed_library": "lib/libosdCPU.a",
        }[field]
        require(root.is_dir() and artifact.is_file() and
                artifact.is_relative_to(root) and
                sha256_file(artifact) == descriptor["sha256"] and
                artifact == expected_artifact,
                "D12 OpenSubdiv profile artifact bytes/root differ: " + field)
        result[profile_name] = {
            "root": str(root), "artifact_path": str(artifact),
            "sha256": descriptor["sha256"]}
    release_root = pathlib.Path(result["release"]["root"])
    tsan_root = pathlib.Path(result["tsan"]["root"])
    require(not release_root.is_relative_to(tsan_root) and
            not tsan_root.is_relative_to(release_root) and
            result["release"]["sha256"] != result["tsan"]["sha256"],
            "D12 OpenSubdiv Release/TSan profile artifacts are not distinct: " +
            field)
    return result


def _read_canonical_json_object(path, label):
    raw = pathlib.Path(path).read_bytes()
    value = strict_json_bytes(raw)
    require(jcs_bytes(value) == raw and isinstance(value, dict),
            label + " is not a canonical JSON object")
    return value


def _command_output(command):
    require(command.count("-o") == 1 and
            command.index("-o") + 1 < len(command),
            "compile/link command output grammar drift")
    return command[command.index("-o") + 1]


def _d12_dependency_inputs(path, expected_target, working_directory):
    try:
        raw = pathlib.Path(path).read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise QualificationError(
            "D12 compiler dependency output is not UTF-8") from error
    require(raw.endswith(b"\n") and b"\r" not in raw,
            "D12 compiler dependency output framing drift")
    flattened = text.replace("\\\n", " ").strip()
    target = str(pathlib.Path(expected_target).resolve())
    prefix = target + ":"
    require(flattened.startswith(prefix) and
            (len(flattened) == len(prefix) or
             flattened[len(prefix)].isspace()),
            "D12 compiler dependency target/shape drift")
    dependency_text = flattened[len(prefix):]
    dependencies = []
    token = []
    index = 0
    while index < len(dependency_text):
        character = dependency_text[index]
        if character == "\\":
            index += 1
            require(index < len(dependency_text) and
                    dependency_text[index] in
                    {" ", "\t", "#", ":", "$", "\\"},
                    "D12 compiler dependency escaping drift")
            token.append(dependency_text[index])
        elif character.isspace():
            if token:
                dependencies.append("".join(token))
                token = []
        else:
            token.append(character)
        index += 1
    if token:
        dependencies.append("".join(token))
    require(dependencies, "D12 compiler dependency set is empty")
    directory = pathlib.Path(working_directory).resolve()
    require(directory.is_dir(),
            "D12 compiler dependency working directory unavailable")
    result = []
    resolved_paths = set()
    for token in dependencies:
        path_token = pathlib.Path(token)
        dependency = ((directory / path_token).resolve()
                      if not path_token.is_absolute() else path_token.resolve())
        require(dependency.is_file(),
                "D12 compiler dependency path is unavailable")
        if str(dependency) in resolved_paths:
            continue
        resolved_paths.add(str(dependency))
        result.append({"path": str(dependency),
                       "sha256": sha256_file(dependency)})
    return result


def _validate_d12_proof_dependency_closure(
        name, dependency_inputs, installed_header_bindings):
    """Bind proof MMD inputs to reviewed ROOT and pinned installed headers."""
    provider_role = name.startswith("provider_")
    role = "row_provider" if provider_role else "representation_candidate"
    expected_root = {
        str((ROOT / relative).resolve())
        for relative in RUNTIME_SOURCE_PATHS[role]}
    require(isinstance(dependency_inputs, list) and
            all(isinstance(item, dict) and
                set(item) == {"path", "sha256"} and
                isinstance(item["path"], str) and
                isinstance(item["sha256"], str) and
                item["path"] == str(pathlib.Path(item["path"]).resolve()) and
                pathlib.Path(item["path"]).is_file() and
                item["sha256"] == sha256_file(item["path"]) and
                re.fullmatch(r"[0-9a-f]{64}", item["sha256"] or "")
                for item in dependency_inputs),
            "D12 proof dependency ledger shape drift: " + name)
    observed = {item["path"]: item["sha256"] for item in dependency_inputs}
    require(len(observed) == len(dependency_inputs) and
            expected_root.issubset(observed),
            "D12 proof ROOT dependency closure drift: " + name)
    if not provider_role:
        require(set(observed) == expected_root and
                installed_header_bindings == {},
                "D12 representation dependency closure drift: " + name)
        return True

    require(isinstance(installed_header_bindings, dict) and
            installed_header_bindings,
            "D12 provider installed-header authority is absent: " + name)
    for path, binding in installed_header_bindings.items():
        relative = pathlib.PurePosixPath(
            binding.get("source_relative_path", "")
            if isinstance(binding, dict) else "")
        require(isinstance(path, str) and
                path == str(pathlib.Path(path).resolve()) and
                pathlib.Path(path).is_file() and
                isinstance(binding, dict) and
                set(binding) == {"source_relative_path", "sha256"} and
                isinstance(binding["source_relative_path"], str) and
                isinstance(binding["sha256"], str) and
                not relative.is_absolute() and
                relative.as_posix() == binding["source_relative_path"] and
                all(part not in {"", ".", ".."} for part in relative.parts) and
                binding["sha256"] == sha256_file(path) and
                re.fullmatch(r"[0-9a-f]{64}", binding["sha256"] or ""),
                "D12 provider installed-header binding shape drift: " + name)
    require(len({item["source_relative_path"] for item in
                 installed_header_bindings.values()}) ==
            len(installed_header_bindings),
            "D12 provider installed-header source mapping is not unique: " +
            name)
    external = set(observed) - expected_root
    require(external and external.issubset(installed_header_bindings) and
            all(observed[path] == installed_header_bindings[path]["sha256"]
                for path in external),
            "D12 provider installed-header dependency closure drift: " + name)
    return True


def _require_reproducible_object(
        command, observed_object, working_directory, environment, label,
        dependency_root=None, expected_dependencies=None):
    """Re-run one exact compile argv and require identical object bytes."""
    observed = pathlib.Path(observed_object).resolve()
    with tempfile.TemporaryDirectory(
            prefix="d12-object-rebuild-") as temporary:
        rebuilt = pathlib.Path(temporary).resolve() / observed.name
        replay = list(command)
        output = _command_output(replay)
        require(replay.count(output) == 1,
                "D12 object compile output ownership drift: " + label)
        replay[replay.index(output)] = str(rebuilt)
        dependency = rebuilt.with_suffix(".d")
        if "-MF" in replay:
            require(replay.count("-MF") == 1 and
                    replay.index("-MF") + 1 < len(replay),
                    "D12 object dependency-output grammar drift: " + label)
            replay[replay.index("-MF") + 1] = str(dependency)
        else:
            output_index = replay.index("-o")
            replay[output_index:output_index] = [
                "-MMD", "-MF", str(dependency)]
        _run_d12_rebuild_command(
            replay, label + ".object", working_directory, environment)
        dependency_inputs = _d12_dependency_inputs(
            dependency, rebuilt, working_directory)
        dependency_paths = [item["path"] for item in dependency_inputs]
        if dependency_root is not None:
            root = pathlib.Path(dependency_root).resolve()
            require(all(pathlib.Path(path).is_relative_to(root)
                        for path in dependency_paths),
                    "D12 object dependency escaped authenticated source root: " +
                    label)
        if expected_dependencies is not None:
            expected = {str(pathlib.Path(path).resolve())
                        for path in expected_dependencies}
            require(set(dependency_paths) == expected,
                    "D12 object dependency closure drift: " + label)
        require(rebuilt.is_file() and
                sha256_file(rebuilt) == sha256_file(observed),
                "D12 object differs from independent exact-command rebuild: " +
                label)
    return dependency_inputs


def _require_reproducible_archive(
        ar_command, ranlib_command, working_directory, observed_archive,
        environment, label):
    """Re-run exact archive construction and require all container bytes."""
    observed = pathlib.Path(observed_archive).resolve()
    with tempfile.TemporaryDirectory(
            prefix="d12-archive-rebuild-") as temporary:
        rebuilt = pathlib.Path(temporary).resolve() / observed.name
        ar_replay = list(ar_command)
        ranlib_replay = list(ranlib_command)
        require(len(ar_replay) >= 4 and len(ranlib_replay) == 2 and
                ar_replay[2] == ranlib_replay[1],
                "D12 archive output ownership drift: " + label)
        ar_replay[2] = str(rebuilt)
        ranlib_replay[1] = str(rebuilt)
        _run_d12_rebuild_command(
            ar_replay, label + ".ar", working_directory, environment)
        _run_d12_rebuild_command(
            ranlib_replay, label + ".ranlib", working_directory, environment)
        require(rebuilt.is_file() and
                sha256_file(rebuilt) == sha256_file(observed),
                "D12 archive differs from independent exact-command rebuild: " +
                label)
    return True


def _validate_d12_opensubdiv_object_chain(
        source_root, build_root, install_root, contract, profile_name):
    """Bind exact TU argv to object bytes and exact archive member bytes."""
    compile_path = build_root / "compile_commands.json"
    try:
        compile_entries = strict_json_bytes(compile_path.read_bytes())
    except (QualificationError, json.JSONDecodeError) as error:
        raise QualificationError(
            "D12 OpenSubdiv compile database is malformed") from error
    expected_sources = contract["translation_units_in_target_order"]
    expected_non_target = (
        "regression/common/arg_utils.cpp",
        "regression/common/shape_utils.cpp",
        "regression/common/far_utils.cpp",
    )
    require(isinstance(compile_entries, list),
            "D12 OpenSubdiv compile database shape drift")
    entries = {}
    ordered_relative_sources = []
    for entry in compile_entries:
        require(isinstance(entry, dict) and
                set(entry) == {"directory", "command", "file", "output"} and
                all(isinstance(entry.get(field), str) and entry[field]
                    for field in ("directory", "command", "file", "output")),
                "D12 OpenSubdiv compile entry shape drift")
        directory_token = pathlib.Path(entry["directory"])
        directory = directory_token.resolve()
        file_token = pathlib.Path(entry["file"])
        source = ((directory / file_token).resolve()
                  if not file_token.is_absolute() else file_token.resolve())
        require(entry["directory"] == str(directory) and
                directory.is_dir() and directory.is_relative_to(build_root) and
                entry["file"] == str(source) and
                source.is_file() and source.is_relative_to(source_root),
                "D12 OpenSubdiv compile source escaped checkout")
        relative = str(source.relative_to(source_root))
        require(relative not in entries,
                "D12 OpenSubdiv compile source duplicated")
        entries[relative] = (entry, directory, source)
        ordered_relative_sources.append(relative)
    require(tuple(ordered_relative_sources) ==
                tuple(expected_sources) + expected_non_target,
            "D12 OpenSubdiv compile database target/non-target set drift")
    tracked_query = _run_d12_closed_git(
        ["ls-files", "-z"], source_root, text=False)
    require(tracked_query.returncode == 0,
            "D12 OpenSubdiv tracked source enumeration failed")
    tracked_source_paths = {
        str((source_root / _d12_git_path(
            record, "D12 OpenSubdiv tracked source")).resolve())
        for record in _d12_z_records(
            tracked_query.stdout, "D12 OpenSubdiv tracked source list")}

    profile = contract["profiles"][profile_name]
    compiler = B2.EXPECTED_COMPILER_PATH
    sdk = B2.load_manifest()["qualification_platform"]["build"][
        "macos_sdk_path"]
    environment = _d12_rebuild_environment()
    common_suffix = [
        "-std=c++17", "-arch", "arm64", "-isysroot", sdk,
        "-mmacosx-version-min=26.0", "-Wall", "-Wextra",
        "-Wno-invalid-offsetof", "-Wno-strict-aliasing",
        "-Wno-overloaded-virtual"]
    non_target_specs = (
        ("regression/common/arg_utils.cpp", "regression_common_obj"),
        ("regression/common/shape_utils.cpp", "regression_common_obj"),
        ("regression/common/far_utils.cpp", "regression_far_utils_obj"),
    )
    for relative, target_name in non_target_specs:
        entry, directory, source = entries[relative]
        object_token = "CMakeFiles/{}.dir/{}.o".format(
            target_name, source.name)
        expected_tokens = [
            compiler, '-DOPENSUBDIV_VERSION_STRING="3.7.0"',
            "-I" + str(source_root)
        ] + profile["compile_flags"] + common_suffix + [
            "-o", object_token, "-c", str(source)]
        require(directory == build_root / "regression/common" and
                entry["output"] == "regression/common/" + object_token and
                shlex.split(entry["command"]) == expected_tokens,
                "D12 OpenSubdiv non-target compile entry is not exact: " +
                relative)
    ledger = []
    for relative, expected_member in zip(
            expected_sources,
            contract["expected_archive_member_basenames_in_target_order"]):
        entry, directory, source = entries[relative]
        require(entry["file"] == str(source) and
                entry["directory"] == str(directory) and
                directory.is_relative_to(build_root) and directory.is_dir(),
                "D12 OpenSubdiv compile entry path is not canonical")
        tokens = shlex.split(entry["command"])
        generated_include = []
        component = relative.split("/")[1]
        if component in {"sdc", "vtr", "bfr", "osd"}:
            generated_include = ["-I" + str(
                build_root / "opensubdiv" / component)]
        object_token = _command_output(tokens)
        expected_tokens = [
            compiler, '-DOPENSUBDIV_VERSION_STRING="3.7.0"',
            "-I" + str(source_root / "opensubdiv")
        ] + generated_include + profile["compile_flags"] + common_suffix + [
            "-fPIC", "-o", object_token,
            "-c", str(source)]
        require(tokens == expected_tokens,
                "D12 OpenSubdiv TU compiler argv is not exact")
        object_path = (directory / object_token).resolve()
        output_path = (build_root / entry.get("output", "")).resolve()
        require(object_path == output_path and
                entry["output"] == str(object_path.relative_to(build_root)) and
                object_token == os.path.relpath(object_path, directory) and
                object_path.is_relative_to(build_root) and
                object_path.is_file() and object_path.name == expected_member,
                "D12 OpenSubdiv compile output object path drift")
        dependency_inputs = _require_reproducible_object(
            tokens, object_path, directory, environment, relative,
            dependency_root=source_root)
        require({item["path"] for item in dependency_inputs}.issubset(
                    tracked_source_paths),
                "D12 OpenSubdiv dependency closure contains untracked input: " +
                relative)
        nm = subprocess.run(
            ["/usr/bin/nm", "-u", str(object_path)], check=False,
            cwd=str(directory), env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(nm.returncode == 0,
                "D12 OpenSubdiv object is not an auditable Mach-O object")
        undefined = nm.stdout.decode("utf-8", errors="strict")
        has_tsan = "tsan" in undefined
        require(has_tsan == (profile_name == "thread_sanitizer"),
                "D12 OpenSubdiv object instrumentation differs from profile")
        ledger.append({
            "source_relative_path": relative,
            "source_sha256": sha256_file(source),
            "compile_command": tokens,
            "object_path": str(object_path),
            "object_member_basename": expected_member,
            "object_sha256": sha256_file(object_path),
            "undefined_symbols_sha256": sha256_bytes(nm.stdout),
            "tsan_instrumented": has_tsan,
            "dependency_inputs": dependency_inputs,
        })

    link_path = build_root / \
        "opensubdiv/CMakeFiles/osd_static_cpu.dir/link.txt"
    link_lines = link_path.read_text(
        encoding="utf-8", errors="strict").splitlines()
    require(len(link_lines) == 2,
            "D12 OpenSubdiv archive link script line count drift")
    link_directory = build_root / "opensubdiv"
    build_archive = build_root / "lib/libosdCPU.a"
    archive_relative = os.path.relpath(build_archive, link_directory)
    expected_objects = [os.path.relpath(
        item["object_path"], link_directory) for item in ledger]
    ar_command = shlex.split(link_lines[0])
    ranlib_command = shlex.split(link_lines[1])
    require(ar_command == [
                "/Library/Developer/CommandLineTools/usr/bin/ar", "qc",
                archive_relative] + expected_objects and
            ranlib_command == [
                "/Library/Developer/CommandLineTools/usr/bin/ranlib",
                archive_relative] and
            build_archive.is_file() and
            sha256_file(build_archive) == sha256_file(
                install_root / "lib/libosdCPU.a"),
            "D12 OpenSubdiv exact ar/ranlib/archive-output chain drift")
    _require_reproducible_archive(
        ar_command, ranlib_command, link_directory, build_archive,
        environment, profile_name)

    installed_archive = install_root / "lib/libosdCPU.a"
    for item in ledger:
        extracted = subprocess.run(
            ["/usr/bin/ar", "-p", str(installed_archive),
             item["object_member_basename"]], check=False,
            cwd=str(link_directory), env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(extracted.returncode == 0 and
                sha256_bytes(extracted.stdout) == item["object_sha256"],
                "D12 OpenSubdiv archive member bytes differ from object: " +
                item["object_member_basename"])
        item["archive_member_sha256"] = sha256_bytes(extracted.stdout)
    return ledger


def _validate_d12_opensubdiv_profile_audits(envelope, profiles):
    """Re-run the frozen B2 OpenSubdiv audit and derive TSan TU truth."""
    manifest = B2.load_manifest()
    contract = manifest["qualification_platform"]["build"]["opensubdiv"]
    audited = {}
    object_ledgers = {}
    installed_header_bindings = {}
    source_roots = []
    for profile_name, b2_profile_name in (
            ("release", "release"), ("tsan", "thread_sanitizer")):
        build_root = pathlib.Path(profiles[
            "build_root_provenance"][profile_name]["root"])
        install_root = pathlib.Path(profiles[
            "install_provenance"][profile_name]["root"])
        build_packet_path = pathlib.Path(profiles[
            "build_root_provenance"][profile_name]["artifact_path"])
        build_packet = _read_canonical_json_object(
            build_packet_path, "D12 OpenSubdiv build audit")
        require(set(build_packet) == {
                    "schema_id", "profile", "source_root", "source", "audit",
                    "object_archive_ledger"} and
                build_packet["schema_id"] ==
                    "d12-opensubdiv-build-audit-v1" and
                build_packet["profile"] == profile_name,
                "D12 OpenSubdiv build audit identity/shape drift")
        source_root_text = _absolute_command_path(
            build_packet["source_root"], "",
            "D12 OpenSubdiv source root is not canonical")
        source_root = pathlib.Path(source_root_text)
        require(source_root.is_dir(),
                "D12 OpenSubdiv source root is unavailable")
        independent_source = _audit_d12_source_checkout(
            source_root, manifest)
        header_bindings = _d12_installed_header_bindings(
            source_root, install_root)
        independent_audit = B2.audit_opensubdiv(
            install_root, build_root, source_root, contract, b2_profile_name)
        object_ledger = _validate_d12_opensubdiv_object_chain(
            source_root, build_root, install_root, contract, b2_profile_name)
        require(build_packet["source"] == independent_source and
                build_packet["audit"] == independent_audit and
                build_packet["object_archive_ledger"] == object_ledger,
                "D12 OpenSubdiv build audit differs from actual frozen audit")
        source_roots.append(str(source_root))

        header = install_root / "include/opensubdiv/version.h"
        install_expected = {
            "schema_id": "d12-opensubdiv-install-provenance-v1",
            "profile": profile_name,
            "install_root": str(install_root),
            "version_header_sha256": sha256_file(header),
            "install_manifest_sha256": independent_audit[
                "provenance_artifacts"]["install_manifest"]["sha256"],
            "archive_sha256": independent_audit["archive_sha256"],
        }
        install_observed = _read_canonical_json_object(
            profiles["install_provenance"][profile_name]["artifact_path"],
            "D12 OpenSubdiv install provenance")
        require(install_observed == install_expected,
                "D12 OpenSubdiv install provenance differs from audit")

        link_expected = {
            "schema_id": "d12-opensubdiv-link-provenance-v1",
            "profile": profile_name,
            "build_root": str(build_root),
            "archive_sha256": independent_audit["archive_sha256"],
            "raw_archive_members": independent_audit["raw_archive_members"],
            "link_command_sha256": independent_audit[
                "provenance_artifacts"]["link_command"]["sha256"],
        }
        link_observed = _read_canonical_json_object(
            profiles["link_provenance"][profile_name]["artifact_path"],
            "D12 OpenSubdiv link provenance")
        require(link_observed == link_expected,
                "D12 OpenSubdiv link provenance differs from audit")
        require(pathlib.Path(independent_audit["archive"]) == pathlib.Path(
                    profiles["installed_library"][profile_name][
                        "artifact_path"]) and
                independent_audit["archive_sha256"] == profiles[
                    "installed_library"][profile_name]["sha256"],
                "D12 OpenSubdiv installed archive differs from actual audit")
        audited[profile_name] = independent_audit
        object_ledgers[profile_name] = object_ledger
        installed_header_bindings[profile_name] = header_bindings
    require(len(set(source_roots)) == 1 and
            audited["release"]["archive_sha256"] !=
                audited["tsan"]["archive_sha256"],
            "D12 OpenSubdiv profiles do not share one source/distinct archives")
    header_projections = [{
        (item["source_relative_path"], item["sha256"])
        for item in installed_header_bindings[profile_name].values()}
        for profile_name in ("release", "tsan")]
    require(header_projections[0] == header_projections[1],
            "D12 OpenSubdiv Release/TSan installed header sets differ")

    proof_units = []
    tsan_profile = envelope["build_profiles"]["tsan"]
    for index, binary_name in enumerate(
            ("provider_tsan", "representation_tsan")):
        source = next(item for item in envelope["binaries"][binary_name][
            "source_inventory"] if item["path"].endswith(".cpp"))
        proof_units.append({
            "binary": binary_name, "source": source,
            "binary_sha256": envelope["binaries"][binary_name]["sha256"],
            "compile_command": tsan_profile["compile_commands"][index]})
    instrumentation_ledger = {
        "schema_id": "d12-instrumented-translation-unit-ledger-v1",
        "proof_translation_units": proof_units,
        "opensubdiv_translation_units": object_ledgers["tsan"],
        "opensubdiv_installed_headers":
            installed_header_bindings["tsan"],
    }
    return {
        "profiles": audited,
        "object_archive_ledgers": object_ledgers,
        "installed_header_bindings": installed_header_bindings,
        "instrumented_translation_units_sha256": sha256_bytes(
            jcs_bytes(instrumentation_ledger))}


def _run_d12_rebuild_command(
        command, label, working_directory, environment):
    directory = pathlib.Path(working_directory).resolve()
    require(str(working_directory) == str(directory) and directory.is_dir() and
            environment == _d12_rebuild_environment(),
            "D12 rebuild cwd/environment is not exact: " + label)
    completed = subprocess.run(
        command, check=False, cwd=str(directory), env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(completed.returncode == 0,
            "D12 independent proof rebuild failed: " + label + "\n" +
            completed.stderr.decode("utf-8", errors="replace"))


def _rebuild_d12_proof_binary(
        name, compile_command, link_command, runtime_binary,
        runtime_link_map, working_directory, environment,
        installed_header_bindings):
    with tempfile.TemporaryDirectory(prefix="d12-proof-rebuild-") as temporary:
        root = pathlib.Path(temporary).resolve()
        runtime_path = pathlib.Path(runtime_binary).resolve()
        rebuilt_object = root / (name + ".o")
        rebuilt_dependency = root / (name + ".d")
        rebuilt_map = root / (name + ".map")
        # ld's ad-hoc arm64 code signature derives its identifier from the
        # output basename. Preserve that basename so exact-command replay is
        # byte-reproducible while all outputs remain isolated.
        rebuilt_binary = root / runtime_path.name
        compile_replay = list(compile_command)
        require(compile_replay.count("-MF") == 1,
                "D12 compile dependency-output grammar drift")
        compile_replay[compile_replay.index("-MF") + 1] = str(
            rebuilt_dependency)
        compile_replay[compile_replay.index("-o") + 1] = str(rebuilt_object)
        _run_d12_rebuild_command(
            compile_replay, name + ".compile",
            working_directory, environment)
        dependency_inputs = _d12_dependency_inputs(
            rebuilt_dependency, rebuilt_object, working_directory)
        _validate_d12_proof_dependency_closure(
            name, dependency_inputs, installed_header_bindings)

        link_replay = list(link_command)
        original_object = _command_output(compile_command)
        original_object_path = pathlib.Path(original_object).resolve()
        require(original_object == str(original_object_path) and
                original_object_path.is_file() and
                link_replay.count(original_object) == 1 and
                sha256_file(rebuilt_object) ==
                    sha256_file(original_object_path),
                "D12 link object is not the independently rebuilt object")
        map_indexes = [index for index, token in enumerate(link_replay)
                       if token.startswith("-Wl,-map,")]
        require(len(map_indexes) == 1,
                "D12 link-map output grammar drift")
        link_replay[map_indexes[0]] = "-Wl,-map," + str(rebuilt_map)
        link_replay[link_replay.index("-o") + 1] = str(rebuilt_binary)
        _run_d12_rebuild_command(
            link_replay, name + ".link",
            working_directory, environment)
        try:
            rebuilt_map_text = rebuilt_map.read_text(
                encoding="utf-8", errors="strict")
            observed_map_text = pathlib.Path(runtime_link_map).read_text(
                encoding="utf-8", errors="strict")
        except UnicodeError as error:
            raise QualificationError(
                "D12 proof rebuild map is not strict UTF-8: " + name
            ) from error
        binary_placeholder = "${D12_REBUILT_BINARY}"
        require(binary_placeholder not in rebuilt_map_text,
                "D12 rebuilt map contains reserved normalization token")
        canonical_rebuilt_map = rebuilt_map_text.replace(
            str(rebuilt_binary), binary_placeholder).replace(
                binary_placeholder, str(runtime_path))
        require(rebuilt_object.is_file() and rebuilt_dependency.is_file() and
                rebuilt_map.is_file() and rebuilt_binary.is_file() and
                sha256_file(rebuilt_binary) == sha256_file(
                    runtime_path) and
                canonical_rebuilt_map == observed_map_text,
                "D12 proof binary differs from independent exact-command rebuild: " +
                name)
    return True


def _validate_d12_runtime_binary_audit(
        name, runtime_binary, link_map_path, dynamic_path, provider_role,
        profile_name, opensubdiv_audit, compile_command, link_command,
        working_directory, environment, audited_library):
    try:
        observed_dynamic = pathlib.Path(dynamic_path).read_text(
            encoding="utf-8", errors="strict")
        observed_map = pathlib.Path(link_map_path).read_text(
            encoding="utf-8", errors="strict")
    except UnicodeError as error:
        raise QualificationError(
            "D12 binary audit artifact is not strict UTF-8: " + name) from error
    actual_dynamic = B2.run(
        ["/usr/bin/otool", "-L", str(pathlib.Path(runtime_binary).resolve())]
    ).stdout
    tsan_runtime = "libclang_rt.tsan" in actual_dynamic
    require(observed_dynamic == actual_dynamic and
            bool(observed_map.strip()) and
            (tsan_runtime == (profile_name == "tsan")),
            "D12 binary dynamic/TSan audit differs from executable: " + name)
    if provider_role:
        expected_members = {
            item["object_member_basename"] for item in
            opensubdiv_audit["object_archive_ledgers"][profile_name]}
        require(str(pathlib.Path(audited_library).resolve()) in observed_map and
                any(member in observed_map for member in expected_members),
                "D12 provider link map does not use audited OpenSubdiv archive: " +
                name)
    else:
        require("libosdCPU.a" not in observed_map,
                "D12 representation binary unexpectedly links OpenSubdiv: " +
                name)
    return _rebuild_d12_proof_binary(
        name, compile_command, link_command, runtime_binary, link_map_path,
        working_directory, environment,
        (opensubdiv_audit["installed_header_bindings"][profile_name]
         if provider_role else {}))


def _validate_d12_runtime_provenance(envelope, report, provenance,
                                     runtime_binaries):
    """Hash every nested D12 claim against caller-supplied artifact bytes."""
    require(isinstance(provenance, dict) and
            set(provenance.get("binaries", {})) == set(envelope["binaries"]) and
            set(provenance.get("dependencies", {})) ==
                set(envelope["dependencies"]),
            "qualified D12 validation lacks complete nested provenance")
    expected_sources = {
        "provider_release": report["binaries"]["row_provider"]["sources"],
        "provider_tsan": report["binaries"]["row_provider"]["sources"],
        "representation_release": report["binaries"][
            "representation_candidate"]["sources"],
        "representation_tsan": report["binaries"][
            "representation_candidate"]["sources"],
    }
    profile_for_binary = {
        "provider_release": "release", "representation_release": "release",
        "provider_tsan": "tsan", "representation_tsan": "tsan"}
    command_index_for_binary = {
        "provider_release": 0, "provider_tsan": 0,
        "representation_release": 1, "representation_tsan": 1}
    opensubdiv = envelope["dependencies"]["opensubdiv"]
    opensubdiv_files = provenance["dependencies"]["opensubdiv"]
    opensubdiv_profiles = {}
    opensubdiv_manifest_paths = []
    for field, digest_field in (
            ("build_root_provenance", "build_root_provenance_sha256"),
            ("install_provenance", "install_provenance_sha256"),
            ("link_provenance", "link_provenance_sha256"),
            ("installed_library", "installed_library_sha256")):
        manifest_path = pathlib.Path(opensubdiv_files[field]).resolve()
        require(manifest_path.is_file() and
                sha256_file(manifest_path) == opensubdiv[digest_field],
                "D12 OpenSubdiv profile manifest bytes differ: " + field)
        opensubdiv_manifest_paths.append(str(manifest_path))
        opensubdiv_profiles[field] = \
            _read_d12_opensubdiv_profile_manifest(manifest_path, field)
    artifact_paths = [
        opensubdiv_profiles[field][profile_name]["artifact_path"]
        for field in opensubdiv_profiles
        for profile_name in ("release", "tsan")]
    artifact_hashes = [
        opensubdiv_profiles[field][profile_name]["sha256"]
        for field in opensubdiv_profiles
        for profile_name in ("release", "tsan")]
    require(len(set(opensubdiv_manifest_paths)) == 4 and
            len(set(artifact_paths)) == 8 and len(set(artifact_hashes)) == 8,
            "D12 OpenSubdiv manifest/artifact roles are not distinct")
    command_roots = _validate_d12_build_profile_commands(envelope)
    for profile_name in ("release", "tsan"):
        require(opensubdiv_profiles["build_root_provenance"][profile_name][
                    "root"] == command_roots[profile_name]["build_root"] and
                opensubdiv_profiles["link_provenance"][profile_name][
                    "root"] == command_roots[profile_name]["build_root"] and
                opensubdiv_profiles["install_provenance"][profile_name][
                    "root"] == command_roots[profile_name]["install_root"] and
                opensubdiv_profiles["installed_library"][profile_name][
                    "root"] == command_roots[profile_name]["install_root"],
                "D12 OpenSubdiv profile provenance root differs from commands: " +
                profile_name)
    opensubdiv_audit = _validate_d12_opensubdiv_profile_audits(
        envelope, opensubdiv_profiles)
    binary_fields = {
        "compiler_command": "compiler_command_sha256",
        "link_map": "link_map_sha256",
        "dynamic_dependencies": "dynamic_dependency_sha256"}
    for name, files in provenance["binaries"].items():
        binary = envelope["binaries"][name]
        require(binary["source_inventory"] == expected_sources[name] and
                set(files) == set(binary_fields),
                "D12 binary source/provenance inventory is not complete: " +
                name)
        for field, digest_field in binary_fields.items():
            path = pathlib.Path(files[field]).resolve()
            require(path.is_file() and sha256_file(path) ==
                    binary[digest_field],
                    "D12 binary provenance bytes differ: " + name + "." +
                    field)
        command_profile = _read_command_profile(files["compiler_command"])
        profile = envelope["build_profiles"][profile_for_binary[name]]
        require(command_profile == {
                    "working_directory": str(ROOT),
                    "environment": _d12_rebuild_environment(),
                    "compile_commands": profile["compile_commands"],
                    "link_commands": profile["link_commands"]},
                "D12 compile/link command bytes differ from exact build profile")
        command_index = command_index_for_binary[name]
        provider_role = command_index == 0
        role = ("row_provider" if provider_role else
                "representation_candidate")
        compile_record = _validate_d12_compile_command(
            command_profile["compile_commands"][command_index],
            profile["flags"], RUNTIME_SOURCE_ENTRYPOINTS[role][0],
            provider_role)
        link_record = _validate_d12_link_command(
            command_profile["link_commands"][command_index],
            profile["flags"], compile_record, provider_role)
        require(pathlib.Path(link_record["output"]).resolve() ==
                    pathlib.Path(runtime_binaries[name]).resolve() and
                pathlib.Path(link_record["map"]).resolve() ==
                    pathlib.Path(files["link_map"]).resolve() and
                (not provider_role or
                 pathlib.Path(link_record["library"]).resolve() ==
                    pathlib.Path(opensubdiv_profiles[
                        "installed_library"][profile_for_binary[name]][
                            "artifact_path"])),
                "D12 command output/link-map/library differs from supplied artifacts: " +
                name)
        _validate_d12_runtime_binary_audit(
            name, runtime_binaries[name], files["link_map"],
            files["dynamic_dependencies"], provider_role,
            profile_for_binary[name], opensubdiv_audit,
            command_profile["compile_commands"][command_index],
            command_profile["link_commands"][command_index],
            command_profile["working_directory"],
            command_profile["environment"],
            None if not provider_role else opensubdiv_profiles[
                "installed_library"][profile_for_binary[name]][
                    "artifact_path"])
    dependency_fields = {
        "archive": "archive_sha256",
        "build_root_provenance": "build_root_provenance_sha256",
        "install_provenance": "install_provenance_sha256",
        "link_provenance": "link_provenance_sha256",
        "installed_library": "installed_library_sha256"}
    for name, files in provenance["dependencies"].items():
        dependency = envelope["dependencies"][name]
        require(set(files) == set(dependency_fields),
                "D12 dependency provenance inventory is incomplete: " + name)
        for field, digest_field in dependency_fields.items():
            path = pathlib.Path(files[field]).resolve()
            require(path.is_file() and sha256_file(path) ==
                    dependency[digest_field],
                    "D12 dependency provenance bytes differ: " + name + "." +
                    field)
    return opensubdiv_audit


def validate_result_sidecar_bundle(report, bundle_root, checkpoint_path=None,
                                   artifact_root=None,
                                   runtime_binaries=None,
                                   runtime_provenance=None,
                                   d12_runtime_binaries=None,
                                   d12_runtime_provenance=None):
    """Stream-rescan all result bytes, exact outcomes, maxima, and proofs."""
    bundle_root = pathlib.Path(bundle_root).resolve()
    d12_envelope = _bound_d12_envelope(report, bundle_root)
    serial_context = (None if d12_envelope is None else
                      d12_envelope["serial_only_context"])
    validate_report(report, serial_context)
    runtime_binaries = runtime_binaries or {}
    if report.get("identity", {}).get("schema_id") == SCHEMA_ID:
        require(set(runtime_binaries) == {
                    "row_provider", "representation_candidate",
                    "exact_dyadic_boundary", "independent_oracle"} and
                runtime_provenance is not None,
                "standalone report validation lacks runtime source truth")
    if runtime_binaries:
        _validate_runtime_bindings(
            report, runtime_binaries, runtime_provenance)
    provider_rows = None
    worker_inventory = None
    d12_runtime_audit = None
    if d12_envelope is not None:
        d12_runtime_binaries = d12_runtime_binaries or {}
        require(set(d12_runtime_binaries) == set(
                    d12_envelope["binaries"]) and
                all(d12_runtime_binaries.values()),
                "qualified D12 validation lacks all runtime binaries")
        for name, binary in d12_envelope["binaries"].items():
            path = pathlib.Path(d12_runtime_binaries[name]).resolve()
            require(path.is_file() and sha256_file(path) == binary["sha256"],
                    "D12 runtime binary differs from envelope: " + name)
        d12_runtime_audit = _validate_d12_runtime_provenance(
            d12_envelope, report, d12_runtime_provenance,
            d12_runtime_binaries)
        provider_rows = ProviderRowVerifier(
            checkpoint_path, artifact_root,
            runtime_binaries.get("row_provider"), report)
        worker_inventory = D12WorkerInventoryVerifier(
            d12_envelope, provider_rows.cases, artifact_root)
        expected_d12_ledgers = make_d12_pre_result_ledgers(
            provider_rows.checkpoint, artifact_root, B2.load_manifest())
        observed_ledgers = {
            item["criterion_id"]: item for item in report["matrix"]["ledgers"]
            if item["partition"] == "all" and
            item["criterion_id"] in D12_CRITERIA}
        require(set(observed_ledgers) == set(D12_CRITERIA),
                "D12 pre-result ledger slots missing")
        for criterion_id, expected in expected_d12_ledgers.items():
            observed = observed_ledgers[criterion_id]
            require(observed["expected_count"] == expected["count"] ==
                        observed["observed_count"] and
                    observed["key_ledger_sha256"] == expected["digest"] and
                    observed["availability"] == availability(
                        "PRESENT", expected["digest"]),
                    "D12 pre-result ledger differs from checkpoint universe")
    d12_evidence = D12EvidenceVerifier(
        bundle_root, d12_envelope, worker_inventory,
        None if d12_runtime_audit is None else d12_runtime_audit[
            "instrumented_translation_units_sha256"])
    if d12_envelope is not None:
        workload = d12_envelope["workload"]
        d12_evidence.sidecar(workload["provider_serial_reference"])
        d12_evidence.sidecar(workload["representation_serial_reference"])
        d12_evidence.sidecar(workload["process_observation_sidecar"])
        for sidecar in workload["sidecars"]:
            d12_evidence.sidecar(sidecar)
    d12_cross_records = D12CrossRecordValidator()
    d12_serial_context = D12SerialContextVerifier()
    oracle_propagation = OracleUncoveredPropagationVerifier()
    oracle_replay = None
    oracle_slot = report["criteria"][CRITERION_IDS.index(
        "oracle_coverage_and_crosscheck")]
    if oracle_slot["result_ledger_artifact"]["availability"]["state"] == \
            "PRESENT":
        require(checkpoint_path is not None and artifact_root is not None and
                runtime_binaries.get("independent_oracle"),
                "complete oracle result validation lacks executable replay "
                "inputs")
        replay_checkpoint_path = pathlib.Path(checkpoint_path).resolve()
        replay_artifact_root = pathlib.Path(artifact_root).resolve()
        require(replay_checkpoint_path.is_file() and
                replay_artifact_root.is_dir(),
                "oracle executable replay corpus unavailable")
        oracle_replay = iter(_iter_replayed_oracle_result_records(
            strict_json_bytes(replay_checkpoint_path.read_bytes()),
            replay_artifact_root, B2.load_manifest(),
            runtime_binaries["independent_oracle"],
            runtime_provenance["binaries"]["independent_oracle"][
                "dynamic_dependencies"]))
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
        basis_groups = (BasisRelabelValidator() if criterion_id ==
                        "binary64_basis_probe_diagnostic" else None)
        count = 0
        try:
            for record, encoded_record in _iter_canonical_result_records(
                    path, result_digest):
                if basis_groups is not None:
                    basis_groups.add(record)
                else:
                    oracle_authority = None
                    if criterion_id == "oracle_coverage_and_crosscheck":
                        require(oracle_replay is not None,
                                "oracle replay verifier unavailable")
                        try:
                            replayed_record = next(oracle_replay)
                        except StopIteration as error:
                            raise QualificationError(
                                "oracle result ledger exceeds executable "
                                "replay") from error
                        require(record == replayed_record,
                                "oracle result record differs from exact "
                                "executable replay")
                        oracle_authority = _ORACLE_CERTIFICATION_AUTHORITY
                    validate_contract_result_record(
                        criterion_id, record,
                        oracle_certification_authority=oracle_authority)
                if (criterion_id in ORACLE_CRITERIA or
                        criterion_id in ORACLE_DEPENDENT_CRITERIA):
                    oracle_propagation.add(criterion_id, record)
                if criterion_id in {
                        "representation_structure",
                        "relabel_exact_effective_coefficients",
                        "binary64_basis_probe_diagnostic"}:
                    if provider_rows is None:
                        provider_rows = ProviderRowVerifier(
                            checkpoint_path, artifact_root,
                            runtime_binaries.get("row_provider"), report)
                    provider_rows.result_record(
                        criterion_id, record[0], record[2])
                if criterion_id == "bindings_and_independence":
                    _validate_binding_against_report(record[2], report)
                elif criterion_id in D12_CRITERIA:
                    d12_evidence.result_record(
                        record[0], record[2], record[3])
                    d12_cross_records.add(criterion_id, record)
                    d12_serial_context.add(
                        criterion_id, record, encoded_record)
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
                field = RESULT_CONTRACT.CRITERION_BY_ID[criterion_id][
                    "maximum_field"]
                if field is not None and record[1] != "UNCOVERED":
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
            if criterion_id == "oracle_coverage_and_crosscheck":
                try:
                    next(oracle_replay)
                except StopIteration:
                    pass
                else:
                    raise QualificationError(
                        "oracle result ledger is shorter than executable "
                        "replay")
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
        validate_criterion_result_outcomes(
            criterion_id, status, outcomes, count, first_failure,
            criterion["first_failing_key"])
        if criterion_id == "raw_bfr_d9a_reproduction":
            require(raw_fail_states == RAW_D9A_FROZEN_FAILING_CASE_COUNT,
                    "raw D9a persisted failing-case count")
        if status == "UNCOVERED":
            require(criterion["maximum"] is None and
                    criterion["witness"] is None,
                    "uncovered criterion carries covered-cell maximum")
        elif maximum is not None:
            witness = criterion["witness"]
            require(criterion["maximum"] == maximum and
                    criterion["maximum"] == witness["maximum_exact"],
                    "criterion maximum differs from witness")
            validate_maximum_witness_binding(
                witness, maximum, maximum_record, maximum_record_bytes,
                maximum_index, siblings, root, count)
        else:
            require(criterion["maximum"] is None and
                    criterion["witness"] is None,
                    "criterion claims maximum without measurable record")

    oracle_partitions = {
        item["partition"]: item for item in report["matrix"]["ledgers"]
        if item["criterion_id"] == "oracle_coverage_and_crosscheck" and
        item["partition"] in {"covered", "uncovered"}}
    oracle_propagation.finish(report["criteria"], oracle_partitions)
    d12_cross_records.finish()
    computed_serial_context = d12_serial_context.finish()
    if serial_context is not None:
        require(computed_serial_context == serial_context,
                "D12 serial-only context differs from complete result ledgers")

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
    d12_evidence.close()
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
        if value.get("schema_id") == \
                "anchored-row-representation-d12-v1":
            require(jcs_bytes(value) == raw,
                    "closed D12 envelope bytes are not canonical JCS")
            validate_d12_envelope_contract(value, expected_head)
            platform = value["platform"]
            expectation = (
                "closed qualified D12 representation workload included"
                if platform["platform_state"] == "QUALIFIED_PLATFORM" else
                "closed hosted/unqualified D12 representation workload "
                "included; numeric D12 criteria remain incomplete")
            return ({
                "availability": availability(
                    "PRESENT", sha256_bytes(raw)),
                "execution_state": platform["platform_state"],
                "exact_head": value["git"]["head"],
                "physical_fingerprint_sha256": sha256_bytes(
                    jcs_bytes(platform["observed_fingerprint"])),
                "representation_work": "INCLUDED",
                "omission_blocker": None}, expectation)
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


def load_d12_execution_evidence(path_text, expected_head):
    """Import only complete result commitments from one closed D12 envelope."""
    if not path_text:
        return {}, None
    path = pathlib.Path(path_text).resolve()
    if not path.is_file():
        return {}, None
    raw = path.read_bytes()
    try:
        value = strict_json_bytes(raw)
        if not isinstance(value, dict) or value.get("schema_id") != \
                "anchored-row-representation-d12-v1":
            return {}, None
        require(jcs_bytes(value) == raw,
                "closed D12 envelope bytes are not canonical JCS")
        validate_d12_envelope_contract(value, expected_head)
        result = {}
        for criterion in value["criteria"]:
            criterion_id = criterion["criterion_id"]
            require(criterion_id in D12_CRITERIA and
                    criterion["observed_cell_count"] ==
                        EXPECTED_CELL_COUNTS[criterion_id] and
                    criterion["result_ledger_artifact"]["availability"][
                        "state"] == "PRESENT",
                    "closed D12 criterion lacks complete result evidence")
            result[criterion_id] = {
                "status": criterion["status"],
                "observed_count": criterion["observed_cell_count"],
                "digest": criterion["key_ledger_sha256"],
                "result_digest": criterion["result_ledger_sha256"],
                "result_merkle_root": criterion[
                    "result_merkle_root_sha256"],
                "result_artifact": copy.deepcopy(
                    criterion["result_ledger_artifact"]),
                "target": copy.deepcopy(criterion["target"]),
                "maximum": copy.deepcopy(criterion["maximum"]),
                "witness": copy.deepcopy(criterion["witness"]),
                "first_failing_key": copy.deepcopy(
                    criterion["first_failing_key"]),
            }
        require(set(result) == set(D12_CRITERIA),
                "closed D12 criterion coverage")
        return result, copy.deepcopy(value["serial_only_context"])
    except (QualificationError, OSError, ValueError, KeyError,
            json.JSONDecodeError, UnicodeDecodeError):
        return {}, None


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
    for record in records:
        require(isinstance(record, list) and len(record) == 5 and
                _contract_kind(record[2]) == "raw_d9a_value_v1" and
                (record[2]["raw_invariant_state"] == "FAIL") ==
                    (record[2]["failing_row_count"] > 0) and
                SHA256_RE.fullmatch(
                    record[2]["canonical_raw_rows_sha256"] or "") is not
                    None,
                "raw D9a case state/count/digest coupling")
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
    provenance_binaries = [
        binaries[binary_name] for binary_name in (
            "row_provider", "representation_candidate",
            "exact_dyadic_boundary", "independent_oracle")
        if binaries[binary_name]["availability"]["state"] == "PRESENT"]
    provenance_complete = all(
        binary.get("sources") and
        all(binary.get(field, {}).get("state") == "PRESENT" for field in
            ("compiler_command", "compiler_version", "link_map",
             "dynamic_dependencies")) and
        all(dependency.get(field, {}).get("state") == "PRESENT"
            for dependency in binary.get("dependencies", {}).values()
            for field in ("source_archive", "build_provenance",
                          "install_provenance", "link_map",
                          "dynamic_dependencies"))
        for binary in provenance_binaries)
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
        "provenance_complete": provenance_complete,
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
    del worktree, all_required_bindings_present
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
        if criterion_id == "complete_artifact_inventory":
            aggregate_target = evidence.get("target")
            require(aggregate_target is not None,
                    "inventory aggregate target unavailable")
            require(evidence.get("unexpected_paths") == aggregate_target,
                    "inventory aggregate target/evidence drift")
        else:
            aggregate_target = evidence.get("target")
            if aggregate_target is None:
                aggregate_target = report_criterion_target(criterion_id)
        records.append(criterion_record(
            criterion_id, evidence["status"],
            expectation=expectations[criterion_id],
            expected=EXPECTED_CELL_COUNTS[criterion_id],
            observed=evidence["observed_count"],
            ledger=commitment["key_ledger_sha256"],
            result_ledger=commitment["result_ledger_sha256"],
            result_merkle_root=commitment["result_merkle_root_sha256"],
            result_artifact=evidence["artifact"],
            target=aggregate_target,
            maximum=evidence["maximum"], witness=evidence["witness"],
            first_failure=evidence["first_failing_key"]))
    infrastructure_ready = all(
        item["status"] == "PASS" for item in records)
    blocker = next((item["criterion_id"] for item in records
                    if item["status"] == "INCOMPLETE"),
                   "bindings_and_independence")
    for criterion_id in CRITERION_IDS[3:]:
        if criterion_id in executed and infrastructure_ready:
            records.append(executed_criterion_record(
                criterion_id, executed[criterion_id]))
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
    original_args = args
    args = copy.copy(args)
    evidence_root = pathlib.Path(args.output).resolve().parent
    require(evidence_root.is_dir(),
            "qualification evidence output directory unavailable")
    snapshot_directory = tempfile.TemporaryDirectory(
        prefix="anchored-row-runtime-snapshot-")
    snapshot_root = pathlib.Path(snapshot_directory.name)
    original_checkpoint_digest = sha256_file(checkpoint_path)
    snapshot_checkpoint = snapshot_root / "checkpoint.json"
    shutil.copyfile(str(checkpoint_path), str(snapshot_checkpoint))
    require(sha256_file(checkpoint_path) == original_checkpoint_digest ==
                sha256_file(snapshot_checkpoint),
            "checkpoint changed while snapshotting")
    original_artifact_root = pathlib.Path(original_args.artifact_dir).resolve()
    require(original_artifact_root.is_dir(),
            "artifact root unavailable before snapshot")
    snapshot_artifact_root = snapshot_root / "artifacts"
    artifact_originals = []
    artifact_relative_paths = sorted({
        case["complete_json_artifact"] for case in checkpoint["numeric_cases"]},
        key=jcs_bytes)
    require(len(artifact_relative_paths) == 294,
            "checkpoint artifact snapshot cardinality")
    for relative_path in artifact_relative_paths:
        source = (original_artifact_root / relative_path).resolve()
        require(source.is_relative_to(original_artifact_root) and
                source.is_file(),
                "artifact unavailable before snapshot: " + relative_path)
        digest = sha256_file(source)
        destination = snapshot_artifact_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
        require(sha256_file(source) == digest == sha256_file(destination),
                "artifact changed while snapshotting: " + relative_path)
        artifact_originals.append((source, digest))
    args.checkpoint = str(snapshot_checkpoint)
    args.artifact_dir = str(snapshot_artifact_root)
    checkpoint_path = snapshot_checkpoint
    original_runtime = {}
    snapshot_runtime = {}
    for attribute in (
            "provider_binary", "candidate_binary",
            "exact_dyadic_boundary_binary", "independent_oracle_binary"):
        original = pathlib.Path(getattr(original_args, attribute)).resolve()
        require(original.is_file(), "runtime executable unavailable: " + attribute)
        digest = sha256_file(original)
        destination = snapshot_root / attribute
        shutil.copyfile(str(original), str(destination))
        destination.chmod(0o500)
        require(sha256_file(original) == digest and
                sha256_file(destination) == digest,
                "runtime executable changed while snapshotting: " + attribute)
        original_runtime[attribute] = (original, digest)
        snapshot_runtime[attribute] = destination
        setattr(args, attribute, str(destination))
    original_oracle_provenance = {}
    for attribute in ("oracle_command_file", "oracle_link_map",
                      "oracle_dynamic_dependencies"):
        original = pathlib.Path(getattr(original_args, attribute)).resolve()
        require(original.is_file(),
                "oracle provenance unavailable: " + attribute)
        digest = sha256_file(original)
        destination = snapshot_root / attribute
        shutil.copyfile(str(original), str(destination))
        require(sha256_file(original) == digest == sha256_file(destination),
                "oracle provenance changed while snapshotting: " + attribute)
        original_oracle_provenance[attribute] = (original, digest)
        setattr(args, attribute, str(destination))
    oracle_command_lines = original_oracle_provenance[
        "oracle_command_file"][0].read_text(encoding="utf-8").splitlines()
    require(oracle_command_lines.count("-MF") == 1,
            "oracle command lacks one dependency output")
    oracle_dependency_original = pathlib.Path(oracle_command_lines[
        oracle_command_lines.index("-MF") + 1]).resolve()
    require(oracle_dependency_original.is_file(),
            "oracle compiler depfile unavailable before snapshot")
    oracle_dependency_digest = sha256_file(oracle_dependency_original)
    oracle_dependency_snapshot = snapshot_root / "oracle_dependency_file"
    shutil.copyfile(str(oracle_dependency_original),
                    str(oracle_dependency_snapshot))
    require(sha256_file(oracle_dependency_original) ==
                oracle_dependency_digest ==
                sha256_file(oracle_dependency_snapshot),
            "oracle compiler depfile changed while snapshotting")
    original_oracle_provenance["oracle_dependency_file"] = (
        oracle_dependency_original, oracle_dependency_digest)
    sealed_oracle_dynamic = (snapshot_root /
                             "oracle_dynamic_audit.jcs.json")
    published_oracle_dynamic = (
        pathlib.Path(args.output).resolve().parent /
        "anchored-row-oracle-runtime-execution-audit-v2.json")
    oracle_independence_audit = audit_oracle_independence(
        original_runtime["independent_oracle_binary"][0],
        original_oracle_provenance["oracle_command_file"][0],
        original_oracle_provenance["oracle_link_map"][0],
        original_oracle_provenance["oracle_dynamic_dependencies"][0],
        sealed_output_path=sealed_oracle_dynamic,
        dependency_evidence_path=oracle_dependency_snapshot)
    oracle_runtime_library_root = (evidence_root /
                                   "anchored-row-oracle-runtime-libraries-v1")
    oracle_runtime_libraries = _snapshot_oracle_runtime_libraries(
        sealed_oracle_dynamic, oracle_runtime_library_root)
    args.oracle_dynamic_dependencies = str(sealed_oracle_dynamic)
    require(all(path.is_file() and sha256_file(path) == digest and
                sha256_file(snapshot_runtime[attribute]) == digest
                for attribute, (path, digest) in original_runtime.items()),
            "runtime executable identity changed during pre-execution audit")
    require(all(path.is_file() and sha256_file(path) == digest
                for path, digest in original_oracle_provenance.values()),
            "oracle provenance identity changed during pre-execution audit")
    candidate_self_test = run_json(args.candidate_binary, "--self-test",
                                   "anchored_row_candidate_self_test")
    require(candidate_self_test.get("status") == "ok" and
            candidate_self_test.get("rounding_mode") == "FE_TONEAREST" and
            candidate_self_test.get("fma_contraction_permitted") is False and
            candidate_self_test.get("integrand_exact_observation") is False,
            "candidate self-test incomplete")
    boundary_self_test = run_json(args.exact_dyadic_boundary_binary, "--self-test",
                                  "exact_dyadic_boundary_self_test")
    require(boundary_self_test.get("status") == "ok" and
            boundary_self_test.get("precision_bits") == 544 and
            boundary_self_test.get("directed_rounding") is True,
            "exact dyadic boundary self-test incomplete")
    validate_independent_oracle_self_test(run_json(
        args.independent_oracle_binary, "--self-test",
        "stam_oracle_self_test",oracle_runtime_library_root))
    validate_independent_oracle_capability(run_json(
        args.independent_oracle_binary, "--capability",
        "independent_primary_capability",oracle_runtime_library_root))

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
    candidate_ledgers = make_candidate_pre_result_ledgers(
        checkpoint, pathlib.Path(args.artifact_dir).resolve())
    artifact_root = pathlib.Path(args.artifact_dir).resolve()
    if args.d12_evidence:
        require(pathlib.Path(args.d12_evidence).resolve().parent ==
                evidence_root,
                "D12 envelope and qualification report must share one bundle root")
    # The candidate crosses only closed raw observation boundaries.  Every
    # key, expected/reference value, target, outcome, reason, maximum, witness,
    # result digest, and persisted sidecar is constructed in this runner.
    executed = {}
    executed.update(execute_observation_preoracle_criteria(
        args.candidate_binary, checkpoint, artifact_root, manifest,
        evidence_root))
    executed.update(execute_observation_regular_criteria(
        args.candidate_binary, checkpoint, artifact_root, manifest,
        evidence_root))
    executed.update(execute_observation_regular_integrand_criteria(
        args.candidate_binary, checkpoint, artifact_root, manifest,
        evidence_root))
    (oracle_results, oracle_partitions,
     oracle_execution_audit) = execute_oracle_coverage(
        checkpoint, artifact_root, manifest, args.independent_oracle_binary,
        args.candidate_binary, evidence_root,
        oracle_runtime_library_root=oracle_runtime_library_root,
        oracle_runtime_library_bindings=[
            (destination, digest) for _, digest, destination in
            oracle_runtime_libraries])
    executed.update(oracle_results)
    executed.update(execute_observation_component_criteria(
        args.candidate_binary, checkpoint, artifact_root, manifest,
        evidence_root))
    executed.update(execute_observation_cache_criterion(
        args.candidate_binary, checkpoint, artifact_root, manifest,
        evidence_root))
    d12_executed, d12_serial_context = load_d12_execution_evidence(
        args.d12_evidence, expected_head)
    executed.update(d12_executed)
    require(set(executed) == set(CRITERION_IDS[3:27]) | set(d12_executed),
            "scientific execution criterion coverage")
    for criterion_id in CRITERION_IDS[3:27]:
        expected_ledger = (candidate_ledgers[criterion_id]
                           if criterion_id in candidate_ledgers else
                           scientific_ledgers[criterion_id])
        require(executed[criterion_id]["observed_count"] ==
                    expected_ledger["count"] and
                executed[criterion_id]["digest"] ==
                    expected_ledger["digest"],
                "{} result keys differ from pre-result universe".format(
                    criterion_id))
    if d12_executed:
        expected_d12_ledgers = make_d12_pre_result_ledgers(
            checkpoint, artifact_root, manifest)
        for criterion_id in D12_CRITERIA:
            require(d12_executed[criterion_id]["observed_count"] ==
                        expected_d12_ledgers[criterion_id]["count"] and
                    d12_executed[criterion_id]["digest"] ==
                        expected_d12_ledgers[criterion_id]["digest"],
                    "{} result keys differ from D12 pre-result universe".
                    format(criterion_id))
    git_end, worktree_end = git_observations()
    require(all(path.is_file() and sha256_file(path) == digest and
                snapshot_runtime[attribute].is_file() and
                sha256_file(snapshot_runtime[attribute]) == digest
                for attribute, (path, digest) in original_runtime.items()),
            "runtime executable identity changed during scientific execution")
    require(all(path.is_file() and sha256_file(path) == digest
                for path, digest in original_oracle_provenance.values()) and
            sealed_oracle_dynamic.is_file() and
            pathlib.Path(original_args.checkpoint).resolve().is_file() and
            sha256_file(pathlib.Path(original_args.checkpoint).resolve()) ==
                original_checkpoint_digest and
            all(path.is_file() and sha256_file(path) == digest
                for path, digest in artifact_originals),
            "scientific input/provenance identity changed during execution")
    require(all(source.is_file() and destination.is_file() and
                sha256_file(source) == digest == sha256_file(destination)
                for source, digest, destination in oracle_runtime_libraries),
            "oracle runtime dependency identity changed during execution")
    require_git_binding(git_start, git_end, worktree_start, worktree_end,
                        expected_head, checkpoint["binding"]["git_head"])
    _publish_oracle_runtime_execution_packet(
        sealed_oracle_dynamic,oracle_runtime_libraries,
        oracle_execution_audit,published_oracle_dynamic)
    args.oracle_dynamic_dependencies = str(published_oracle_dynamic)

    candidate_source = ROOT / "experiments/anchored_row_qualification/candidate.cpp"
    boundary_source = ROOT / "experiments/anchored_row_qualification/exact_dyadic_boundary.cpp"
    dependencies = dependency_records(args)
    independent_record = binary_record(
        args.independent_oracle_binary,
        [ROOT / path for path in RUNTIME_SOURCE_PATHS["independent_oracle"]],
        "primary_stam_plus_uniform_crosscheck", dependencies,
        args.oracle_command_file, args.compiler_version_file,
        args.oracle_link_map, args.oracle_dynamic_dependencies)
    binaries = {
        "row_provider": binary_record(
            args.provider_binary,
            [ROOT / path for path in RUNTIME_SOURCE_PATHS["row_provider"]],
            "frozen_B2ROWV1_provider",
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
        "oracle_independence_audit": oracle_independence_audit,
    }
    ledgers = make_complete_pre_result_ledgers(
        checkpoint, artifact_root, manifest, executed, scientific_ledgers,
        oracle_partitions=oracle_partitions)
    infrastructure = write_infrastructure_result_evidence(
        evidence_root, checkpoint,
        artifact_root, binaries,
        git_start, git_end, worktree_start, worktree_end)
    d12_record, d12_expectation = inspect_d12_evidence(
        args.d12_evidence, expected_head)
    criteria = make_criteria(
        worktree_end, True, ledgers, executed,
        infrastructure=infrastructure,
        d12_expectation=d12_expectation)
    report = {
        "identity": {"schema_id": SCHEMA_ID, "candidate": CANDIDATE,
                     "implementation_state":
                         "PACKAGE2_EXECUTED_PROOF_ONLY_NO_QUALIFICATION_DECISION",
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
        "verdict": calculate_verdict(criteria, d12_serial_context),
    }
    digest_copy = copy.deepcopy(report)
    digest_copy["verdict"]["report_content_sha256"] = ZERO_SHA256
    report["verdict"]["report_content_sha256"] = sha256_bytes(jcs_bytes(digest_copy))
    validate_report(report, d12_serial_context)
    snapshot_directory.cleanup()
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
                "PACKAGE2_IMPLEMENTED_EXECUTION_REQUIRED",
            "independent_primary_oracle_available": True,
            "kind": "anchored_row_qualification_self_test",
            "qualification_pass_permitted_without_oracle": False,
            "report_schema": SCHEMA_ID, "status": "ok"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--produce-d12-evidence", action="store_true")
    parser.add_argument("--validate-report")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--checkpoint")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--provider-binary")
    parser.add_argument("--candidate-binary")
    parser.add_argument("--exact-dyadic-boundary-binary")
    parser.add_argument("--independent-oracle-binary")
    parser.add_argument("--provider-tsan-binary")
    parser.add_argument("--representation-tsan-binary")
    parser.add_argument("--provider-tsan-command-file")
    parser.add_argument("--provider-tsan-link-map")
    parser.add_argument("--provider-tsan-dynamic-dependencies")
    parser.add_argument("--representation-tsan-command-file")
    parser.add_argument("--representation-tsan-link-map")
    parser.add_argument("--representation-tsan-dynamic-dependencies")
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
    parser.add_argument("--oracle-command-file")
    parser.add_argument("--oracle-link-map")
    parser.add_argument("--oracle-dynamic-dependencies")
    parser.add_argument("--gmp-archive")
    parser.add_argument("--gmp-build-provenance")
    parser.add_argument("--gmp-install-provenance")
    parser.add_argument("--gmp-link-provenance")
    parser.add_argument("--gmp-dynamic-dependency")
    parser.add_argument("--gmp-installed-library")
    parser.add_argument("--mpfr-archive")
    parser.add_argument("--mpfr-build-provenance")
    parser.add_argument("--mpfr-install-provenance")
    parser.add_argument("--mpfr-link-provenance")
    parser.add_argument("--mpfr-dynamic-dependency")
    parser.add_argument("--mpfr-installed-library")
    parser.add_argument("--opensubdiv-archive")
    parser.add_argument("--opensubdiv-build-provenance")
    parser.add_argument("--opensubdiv-install-provenance")
    parser.add_argument("--opensubdiv-link-provenance")
    parser.add_argument("--opensubdiv-dynamic-dependency")
    parser.add_argument("--opensubdiv-installed-library")
    parser.add_argument("--d12-evidence")
    parser.add_argument("--b2-evidence")
    parser.add_argument("--opensubdiv-source-root")
    parser.add_argument("--opensubdiv-release-build-root")
    parser.add_argument("--opensubdiv-release-install-root")
    parser.add_argument("--opensubdiv-tsan-build-root")
    parser.add_argument("--opensubdiv-tsan-install-root")
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
        elif args.produce_d12_evidence:
            accepted = {
                "produce_d12_evidence", "json", "checkpoint",
                "artifact_dir", "provider_binary", "candidate_binary",
                "provider_tsan_binary", "representation_tsan_binary",
                "provider_command_file", "provider_link_map",
                "provider_dynamic_dependencies",
                "provider_tsan_command_file", "provider_tsan_link_map",
                "provider_tsan_dynamic_dependencies",
                "candidate_command_file", "candidate_link_map",
                "candidate_dynamic_dependencies",
                "representation_tsan_command_file",
                "representation_tsan_link_map",
                "representation_tsan_dynamic_dependencies",
                "gmp_archive", "gmp_build_provenance",
                "gmp_install_provenance", "gmp_link_provenance",
                "gmp_installed_library", "mpfr_archive",
                "mpfr_build_provenance", "mpfr_install_provenance",
                "mpfr_link_provenance", "mpfr_installed_library",
                "opensubdiv_archive", "b2_evidence",
                "opensubdiv_source_root",
                "opensubdiv_release_build_root",
                "opensubdiv_release_install_root",
                "opensubdiv_tsan_build_root",
                "opensubdiv_tsan_install_root", "expected_binding_head",
                "output"}
            supplied = [value for key, value in vars(args).items()
                        if key not in accepted]
            require(not any(supplied),
                    "D12 production received unrelated arguments")
            required = [getattr(args, key) for key in accepted
                        if key not in {"produce_d12_evidence", "json",
                                      "expected_binding_head"}]
            require(all(required),
                    "D12 production requires every runtime/provenance input")
            value = produce_d12_evidence(args)
            encoded = jcs_bytes(value)
        elif args.validate_report:
            accepted = {
                "validate_report", "json", "checkpoint", "artifact_dir",
                "provider_binary", "candidate_binary",
                "exact_dyadic_boundary_binary", "independent_oracle_binary",
                "provider_tsan_binary", "representation_tsan_binary",
                "provider_tsan_command_file", "provider_tsan_link_map",
                "provider_tsan_dynamic_dependencies",
                "representation_tsan_command_file",
                "representation_tsan_link_map",
                "representation_tsan_dynamic_dependencies",
                "compiler_version_file", "provider_command_file",
                "provider_link_map", "provider_dynamic_dependencies",
                "candidate_command_file", "candidate_link_map",
                "candidate_dynamic_dependencies", "boundary_command_file",
                "boundary_link_map", "boundary_dynamic_dependencies",
                "oracle_command_file", "oracle_link_map",
                "oracle_dynamic_dependencies", "gmp_archive",
                "gmp_build_provenance", "gmp_install_provenance",
                "gmp_link_provenance", "gmp_dynamic_dependency",
                "gmp_installed_library",
                "mpfr_archive", "mpfr_build_provenance",
                "mpfr_install_provenance", "mpfr_link_provenance",
                "mpfr_dynamic_dependency", "mpfr_installed_library",
                "opensubdiv_archive",
                "opensubdiv_build_provenance",
                "opensubdiv_install_provenance",
                "opensubdiv_link_provenance",
                "opensubdiv_dynamic_dependency",
                "opensubdiv_installed_library"}
            supplied = [value for key, value in vars(args).items()
                        if key not in accepted]
            require(not any(supplied),
                    "report validation received execution-only arguments")
            require(all((args.checkpoint, args.artifact_dir,
                         args.provider_binary, args.candidate_binary,
                         args.exact_dyadic_boundary_binary)),
                    "report validation requires bound provider inputs/binaries")
            required_provenance = [
                args.compiler_version_file, args.provider_command_file,
                args.provider_link_map, args.provider_dynamic_dependencies,
                args.candidate_command_file, args.candidate_link_map,
                args.candidate_dynamic_dependencies,
                args.boundary_command_file, args.boundary_link_map,
                args.boundary_dynamic_dependencies, args.gmp_archive,
                args.gmp_build_provenance, args.gmp_install_provenance,
                args.gmp_link_provenance, args.gmp_dynamic_dependency,
                args.mpfr_archive, args.mpfr_build_provenance,
                args.mpfr_install_provenance, args.mpfr_link_provenance,
                args.mpfr_dynamic_dependency, args.opensubdiv_archive,
                args.opensubdiv_build_provenance,
                args.opensubdiv_install_provenance,
                args.opensubdiv_link_provenance,
                args.opensubdiv_dynamic_dependency,
                args.opensubdiv_installed_library]
            require(all(required_provenance),
                    "report validation requires every provenance input")
            report_path = pathlib.Path(args.validate_report).resolve()
            raw = report_path.read_bytes()
            value = strict_json_bytes(raw)
            require(jcs_bytes(value) == raw,
                    "qualification report bytes are not canonical JCS")
            if value["binaries"]["independent_oracle"][
                    "availability"]["state"] == "PRESENT":
                require(all((args.independent_oracle_binary,
                             args.oracle_command_file,
                             args.oracle_link_map,
                             args.oracle_dynamic_dependencies)),
                        "present oracle requires runtime provenance inputs")
            runtime_provenance = {
                "binaries": {
                    "row_provider": {
                        "compiler_command": args.provider_command_file,
                        "compiler_version": args.compiler_version_file,
                        "link_map": args.provider_link_map,
                        "dynamic_dependencies":
                            args.provider_dynamic_dependencies},
                    "representation_candidate": {
                        "compiler_command": args.candidate_command_file,
                        "compiler_version": args.compiler_version_file,
                        "link_map": args.candidate_link_map,
                        "dynamic_dependencies":
                            args.candidate_dynamic_dependencies},
                    "exact_dyadic_boundary": {
                        "compiler_command": args.boundary_command_file,
                        "compiler_version": args.compiler_version_file,
                        "link_map": args.boundary_link_map,
                        "dynamic_dependencies":
                            args.boundary_dynamic_dependencies},
                    "independent_oracle": {
                        "compiler_command": args.oracle_command_file,
                        "compiler_version": (args.compiler_version_file
                                             if args.oracle_command_file
                                             else None),
                        "link_map": args.oracle_link_map,
                        "dynamic_dependencies":
                            args.oracle_dynamic_dependencies}},
                "dependencies": {
                    "gmp": {
                        "source_archive": args.gmp_archive,
                        "build_provenance": args.gmp_build_provenance,
                        "install_provenance": args.gmp_install_provenance,
                        "link_map": args.gmp_link_provenance,
                        "dynamic_dependencies":
                            args.gmp_dynamic_dependency},
                    "mpfr": {
                        "source_archive": args.mpfr_archive,
                        "build_provenance": args.mpfr_build_provenance,
                        "install_provenance": args.mpfr_install_provenance,
                        "link_map": args.mpfr_link_provenance,
                        "dynamic_dependencies":
                            args.mpfr_dynamic_dependency},
                    "opensubdiv": {
                        "source_archive": args.opensubdiv_archive,
                        "build_provenance":
                            args.opensubdiv_build_provenance,
                        "install_provenance":
                            args.opensubdiv_install_provenance,
                        "link_map": args.opensubdiv_link_provenance,
                        "dynamic_dependencies":
                            args.opensubdiv_dynamic_dependency}}}
            validate_result_sidecar_bundle(
                value, report_path.parent, args.checkpoint,
                args.artifact_dir, {
                    "row_provider": args.provider_binary,
                    "representation_candidate": args.candidate_binary,
                    "exact_dyadic_boundary":
                        args.exact_dyadic_boundary_binary,
                    "independent_oracle": args.independent_oracle_binary},
                runtime_provenance, {
                    "provider_release": args.provider_binary,
                    "provider_tsan": args.provider_tsan_binary,
                    "representation_release": args.candidate_binary,
                    "representation_tsan":
                        args.representation_tsan_binary}, {
                    "binaries": {
                        "provider_release": {
                            "compiler_command": args.provider_command_file,
                            "link_map": args.provider_link_map,
                            "dynamic_dependencies":
                                args.provider_dynamic_dependencies},
                        "provider_tsan": {
                            "compiler_command":
                                args.provider_tsan_command_file,
                            "link_map": args.provider_tsan_link_map,
                            "dynamic_dependencies":
                                args.provider_tsan_dynamic_dependencies},
                        "representation_release": {
                            "compiler_command": args.candidate_command_file,
                            "link_map": args.candidate_link_map,
                            "dynamic_dependencies":
                                args.candidate_dynamic_dependencies},
                        "representation_tsan": {
                            "compiler_command":
                                args.representation_tsan_command_file,
                            "link_map": args.representation_tsan_link_map,
                            "dynamic_dependencies":
                                args.representation_tsan_dynamic_dependencies}},
                    "dependencies": {
                        "gmp": {
                            "archive": args.gmp_archive,
                            "build_root_provenance":
                                args.gmp_build_provenance,
                            "install_provenance":
                                args.gmp_install_provenance,
                            "link_provenance": args.gmp_link_provenance,
                            "installed_library":
                                args.gmp_installed_library},
                        "mpfr": {
                            "archive": args.mpfr_archive,
                            "build_root_provenance":
                                args.mpfr_build_provenance,
                            "install_provenance":
                                args.mpfr_install_provenance,
                            "link_provenance": args.mpfr_link_provenance,
                            "installed_library":
                                args.mpfr_installed_library},
                        "opensubdiv": {
                            "archive": args.opensubdiv_archive,
                            "build_root_provenance":
                                args.opensubdiv_build_provenance,
                            "install_provenance":
                                args.opensubdiv_install_provenance,
                            "link_provenance":
                                args.opensubdiv_link_provenance,
                            "installed_library":
                                args.opensubdiv_installed_library}}})
            encoded = jcs_bytes({
                "kind": "anchored_row_qualification_bundle_validation",
                "report_sha256": sha256_bytes(raw), "status": "ok"}) + b"\n"
        else:
            require(args.checkpoint and args.artifact_dir and
                    args.provider_binary and args.candidate_binary and
                    args.exact_dyadic_boundary_binary and
                    args.independent_oracle_binary and args.output,
                    "execution requires checkpoint, artifacts, provider, "
                    "candidate, exact boundary, independent oracle, and output")
            provenance_arguments = [
                args.compiler_version_file, args.provider_command_file,
                args.provider_link_map, args.provider_dynamic_dependencies,
                args.candidate_command_file, args.candidate_link_map,
                args.candidate_dynamic_dependencies, args.boundary_command_file,
                args.boundary_link_map, args.boundary_dynamic_dependencies,
                args.oracle_command_file, args.oracle_link_map,
                args.oracle_dynamic_dependencies,
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
