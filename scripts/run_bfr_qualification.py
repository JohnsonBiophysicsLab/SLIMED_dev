#!/usr/bin/env python3
"""Fail-closed B2 Bfr qualification runner.

The cheap ``--self-test`` path validates only frozen, pre-result inputs.  The
``--require-proof-dependencies`` path additionally audits and executes the two
compiled proof programs.  It never downloads or discovers dependencies.
"""

from __future__ import print_function

import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction


REPO = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json"
MANIFEST_FILE_SHA256 = "bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b"
MANIFEST_CONTRACT_SHA256 = "30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368"
OPENSUBDIV_COMMIT = "9dab8a47bfbb1388ec8388fe61f5f916e6123f38"
GMP_ARCHIVE_SHA256 = "a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898"
MPFR_ARCHIVE_SHA256 = "b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01"
OPENSUBDIV_ARCHIVE_SHA256 = "f843eb49daf20264007d807cbc64516a1fed9cdb1149aaf84ff47691d97491f9"
ROW_ORDER = ["position", "du", "dv", "duu", "duv", "dvv"]
BFR_LEVELS = list(range(2, 9))
FAR_LEVELS = list(range(2, 9))
D10 = {
    "position": 5.0e-6,
    "du": 2.5e-5,
    "dv": 2.5e-5,
    "duu": 1.25e-4,
    "duv": 1.25e-4,
    "dvv": 1.25e-4,
}
D12 = {
    "preparation_median_ms": 1000.0,
    "preparation_single_run_failstop_ms": 10000.0,
    "retained_row_payload_bytes_per_face": 131072,
    "preparation_peak_rss_delta_mib": 64.0,
}
UNQUALIFIED_PLATFORM = "UNQUALIFIED_PLATFORM"
EXPECTED_PLATFORM_FINGERPRINT = {
    "architecture": "arm64",
    "chip": "Apple M5",
    "hw_logicalcpu": 10,
    "hw_memsize_bytes": 25769803776,
    "hw_model": "Mac17,2",
    "hw_ncpu": 10,
    "hw_perflevel0_logicalcpu": 4,
    "hw_perflevel0_physicalcpu": 4,
    "hw_perflevel1_logicalcpu": 6,
    "hw_perflevel1_physicalcpu": 6,
    "hw_physicalcpu": 10,
    "kern_hv_vmm_present": 0,
    "macos_build": "25F80",
    "macos_version": "26.5.1",
}
EXPECTED_COMPILER_PATH = "/Library/Developer/CommandLineTools/usr/bin/clang++"
EXPECTED_COMPILER_VERSION = "Apple clang version 21.0.0 (clang-2100.1.1.101)"
EXPECTED_POWER_API = "IOPSCopyPowerSourcesInfo plus IOPSGetProvidingPowerSourceType"
EXPECTED_POWER_VALUE = "kIOPSACPowerValue"
EXPECTED_THERMAL_API = "NSProcessInfo.thermalState"
EXPECTED_THERMAL_VALUE = "NSProcessInfoThermalStateNominal"
FORBIDDEN_ORACLE_TOKENS = ("opensubdiv", "OpenSubdiv", "Far", "Bfr", "Osd", "Sdc", "Vtr")
ORACLE_SOURCE_PATHS = (
    "experiments/bfr_qualification/stam_oracle.cpp",
    "experiments/bfr_qualification/stam_box_spline.hpp",
    "experiments/bfr_qualification/mpfr_interval.hpp",
    "experiments/bfr_qualification/stam_evaluation.hpp",
    "experiments/bfr_qualification/stam_primary.hpp",
    "experiments/bfr_qualification/stam_fixture.hpp",
    "experiments/bfr_qualification/stam_uniform.hpp",
    "experiments/bfr_qualification/stam_uniform_box_spline.hpp",
)
CANONICAL_CASE_ORDER = [
    "u8_01_regular_closed", "u8_02_tetrahedron", "u8_03_octahedron",
    "u8_04_icosahedron", "u8_05_symmetric_344", "u8_06_asymmetric_344",
    "u8_07_mixed_345", "u8_08_closed_566", "u8_09_nonplatonic",
    "u8_10_coordinate_perturbed", "u8_11_reversed_winding",
    "u8_12_open_boundary", "u8_13_duplicate_face", "u8_14_edge_flip_family",
    "b7_03_adjacent_extraordinary",
]
NEGATIVE_CASES = {
    "u8_11_reversed_winding", "u8_12_open_boundary", "u8_13_duplicate_face"
}
BFR_CRITERIA = [
    "regular_analytic_rows_and_integrands", "row_sum_invariants",
    "original_source_reconstruction", "internal_refinement_convergence",
    "irregular_primary_stam_oracle", "d12_preparation_cost",
    "d12_retained_payload", "d12_peak_rss", "cache_disabled_concurrency",
    "threaded_cache_fully_instrumented_tsan",
]
ALLOWED_PATH_PATTERNS = (
    re.compile(r"^experiments/"), re.compile(r"^tests/"),
    re.compile(r"^scripts/run_bfr_qualification\.py$"),
    re.compile(r"^docs/bfr_qualification_evidence\.md$"),
    re.compile(r"^\.github/workflows/bfr_qualification\.yml$"),
)


class QualificationError(RuntimeError):
    pass


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return sha256_bytes(encoded)


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True).encode("utf-8")


def run(command, cwd=REPO, env=None, check=True, timeout=None):
    try:
        completed = subprocess.run(
            [str(item) for item in command], cwd=str(cwd), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
            timeout=timeout)
    except subprocess.TimeoutExpired:
        raise QualificationError("command timed out after {} seconds: {}".format(
            timeout, " ".join(str(x) for x in command)))
    if check and completed.returncode != 0:
        raise QualificationError("command failed ({}): {}\n{}\n{}".format(
            completed.returncode, " ".join(str(x) for x in command),
            completed.stdout, completed.stderr))
    return completed


def run_observed(command, cwd=REPO, env=None, timeout=None):
    """Run one proof process and retain its closed success provenance."""
    normalized_command = [str(item) for item in command]
    runtime_environment = (dict(env) if env is not None else {
        "LANG": "C", "LC_ALL": "C", "SOURCE_DATE_EPOCH": "0",
        "TZ": "UTC", "ZERO_AR_DATE": "1"})
    started = datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")
    process = subprocess.Popen(
        normalized_command, cwd=str(cwd), env=runtime_environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise QualificationError(
            "command timed out after {} seconds: {}".format(
                timeout, " ".join(normalized_command)))
    ended = datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")
    completed = subprocess.CompletedProcess(
        normalized_command, process.returncode, stdout, stderr)
    if completed.returncode != 0:
        raise QualificationError("command failed ({}): {}\n{}\n{}".format(
            completed.returncode, " ".join(normalized_command),
            stdout, stderr))
    provenance = {
        "pid": process.pid, "start_utc": started, "end_utc": ended,
        "exit_kind": "EXITED", "exit_code": 0, "signal": None,
        "argv_sha256": canonical_digest(normalized_command),
        "environment_sha256": canonical_digest(runtime_environment),
        "stderr_sha256": sha256_bytes(stderr.encode("utf-8")),
    }
    return completed, provenance


def require(condition, message):
    if not condition:
        raise QualificationError(message)


def strict_child_json(text):
    """Decode a subprocess JSON object without lossy key/number handling."""
    def reject_duplicate_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate child JSON key: {}".format(key))
            result[key] = value
        return result

    def reject_nonstandard_constant(value):
        raise ValueError("nonstandard child JSON constant: {}".format(value))

    return json.loads(
        text, object_pairs_hook=reject_duplicate_pairs,
        parse_constant=reject_nonstandard_constant)


def candidate_platform_probe(candidate_binary):
    """Return a non-throwing physical-host/power/thermal observation."""
    failure = {
        "schema_version": 1, "kind": "bfr_platform_probe",
        "status": "query_failed", "finite": True,
        "fingerprint_queries_ok": False, "fingerprint": {},
        "power": {"api": EXPECTED_POWER_API, "query_ok": False,
                  "raw": "", "value": ""},
        "thermal": {"api": EXPECTED_THERMAL_API, "query_ok": False,
                    "raw": -1, "value": ""},
        "process_returncode": None,
    }
    try:
        completed = run([candidate_binary, "--platform-probe"], check=False, timeout=15)
    except QualificationError:
        return failure
    failure["process_returncode"] = completed.returncode
    if completed.returncode != 0:
        return failure
    try:
        observed = strict_child_json(completed.stdout)
    except ValueError:
        return failure
    expected_observed_keys = set(failure) - {"process_returncode"}
    if (not isinstance(observed, dict) or
            set(observed) != expected_observed_keys):
        return failure
    observed["process_returncode"] = completed.returncode
    return observed


def compiler_platform_observation():
    compiler = pathlib.Path(EXPECTED_COMPILER_PATH)
    if not compiler.is_file():
        return {"path": EXPECTED_COMPILER_PATH, "query_ok": False, "version": ""}
    completed = run([compiler, "--version"], check=False, timeout=15)
    lines = completed.stdout.splitlines()
    return {"path": str(compiler), "query_ok": completed.returncode == 0 and bool(lines),
            "version": lines[0] if lines else ""}


def platform_probe_mismatches(probe, expected_fingerprint):
    mismatches = []
    if (probe.get("schema_version") != 1 or
            probe.get("kind") != "bfr_platform_probe" or
            probe.get("status") != "ok"):
        mismatches.append("platform_probe_failed")
    if probe.get("fingerprint_queries_ok") is not True:
        mismatches.append("fingerprint_query_failed")
    if probe.get("fingerprint") != expected_fingerprint:
        mismatches.append("fingerprint_mismatch")
    power = probe.get("power", {})
    if (power.get("api") != EXPECTED_POWER_API or power.get("query_ok") is not True or
            power.get("value") != EXPECTED_POWER_VALUE):
        mismatches.append("power_not_confirmed_ac")
    thermal = probe.get("thermal", {})
    if (thermal.get("api") != EXPECTED_THERMAL_API or
            thermal.get("query_ok") is not True or
            thermal.get("value") != EXPECTED_THERMAL_VALUE):
        mismatches.append("thermal_not_confirmed_nominal")
    return mismatches


def capture_platform_qualification(candidate_binary, manifest, numeric_cases):
    """Assess the frozen D12 platform without invalidating other science."""
    expected = manifest["qualification_platform"]["fingerprint"]
    current_probe = candidate_platform_probe(candidate_binary)
    compiler = compiler_platform_observation()
    mismatches = platform_probe_mismatches(current_probe, expected)
    if (compiler.get("query_ok") is not True or
            compiler.get("path") != EXPECTED_COMPILER_PATH or
            compiler.get("version") != EXPECTED_COMPILER_VERSION):
        mismatches.append("compiler_identity_mismatch")

    expected_boundaries = ["primary_before", "primary_after",
                           "determinism_before", "determinism_after"]
    sample_count = 0
    per_case_complete = len(numeric_cases) == 294
    for case in numeric_cases:
        samples = case.get("platform_boundary_samples")
        if (not isinstance(samples, list) or
                [sample.get("boundary") for sample in samples
                 if isinstance(sample, dict)] != expected_boundaries):
            per_case_complete = False
            continue
        sample_count += len(samples)
        for sample in samples:
            sample_probe = sample.get("probe")
            if not isinstance(sample_probe, dict):
                per_case_complete = False
                continue
            if platform_probe_mismatches(sample_probe, expected):
                per_case_complete = False
    if not per_case_complete or sample_count != 294 * len(expected_boundaries):
        mismatches.append("per_case_power_thermal_sampling_incomplete_or_unqualified")

    runner_environment = os.environ.get("RUNNER_ENVIRONMENT", "")
    github_hosted = (runner_environment == "github-hosted" or
                     (os.environ.get("GITHUB_ACTIONS") == "true" and
                      runner_environment != "self-hosted"))
    if github_hosted:
        mismatches.append("github_hosted_workflow_disallowed_for_d12")

    head_result = run(["git", "rev-parse", "HEAD"], check=False)
    status_result = run(["git", "status", "--porcelain=v1"], check=False)
    git_identity = {
        "head": head_result.stdout.strip() if head_result.returncode == 0 else None,
        "head_query_ok": head_result.returncode == 0,
        "worktree_empty": status_result.returncode == 0 and not status_result.stdout.strip(),
        "review_match": "PENDING_INDEPENDENT_EXACT_SHA_REVIEW",
    }
    unique_mismatches = sorted(set(mismatches))
    return {
        "status": "QUALIFIED" if not unique_mismatches else UNQUALIFIED_PLATFORM,
        "expected_fingerprint": expected,
        "current_probe": current_probe,
        "compiler": compiler,
        "per_case_boundary_protocol": {
            "required_boundaries": expected_boundaries,
            "case_count": len(numeric_cases),
            "sample_count": sample_count,
            "complete_and_qualified": per_case_complete and sample_count == 1176,
        },
        "github_hosted": github_hosted,
        "runner_environment": runner_environment or None,
        "git_identity": git_identity,
        "mismatches": unique_mismatches,
    }


def validate_platform_qualification(value, manifest, numeric_cases):
    require(isinstance(value, dict), "missing D12 platform qualification")
    expected = manifest["qualification_platform"]["fingerprint"]
    require(value.get("expected_fingerprint") == expected,
            "D12 expected platform fingerprint drift")
    probe = value.get("current_probe")
    require(isinstance(probe, dict), "missing current D12 platform probe")
    mismatches = platform_probe_mismatches(probe, expected)
    compiler = value.get("compiler", {})
    if (compiler.get("query_ok") is not True or
            compiler.get("path") != EXPECTED_COMPILER_PATH or
            compiler.get("version") != EXPECTED_COMPILER_VERSION):
        mismatches.append("compiler_identity_mismatch")
    boundaries = ["primary_before", "primary_after",
                  "determinism_before", "determinism_after"]
    sample_count = 0
    per_case_complete = len(numeric_cases) == 294
    for case in numeric_cases:
        samples = case.get("platform_boundary_samples")
        if (not isinstance(samples, list) or
                [sample.get("boundary") for sample in samples
                 if isinstance(sample, dict)] != boundaries):
            per_case_complete = False
            continue
        sample_count += len(samples)
        for sample in samples:
            sample_probe = sample.get("probe")
            if (not isinstance(sample_probe, dict) or
                    platform_probe_mismatches(sample_probe, expected)):
                per_case_complete = False
    if not per_case_complete or sample_count != 1176:
        mismatches.append("per_case_power_thermal_sampling_incomplete_or_unqualified")
    if value.get("github_hosted") is True:
        mismatches.append("github_hosted_workflow_disallowed_for_d12")
    protocol = value.get("per_case_boundary_protocol")
    require(protocol == {
        "required_boundaries": boundaries, "case_count": len(numeric_cases),
        "sample_count": sample_count,
        "complete_and_qualified": per_case_complete and sample_count == 1176},
            "D12 boundary-probe protocol summary drift")
    observed_mismatches = sorted(set(mismatches))
    require(value.get("mismatches") == observed_mismatches,
            "D12 platform mismatch ledger is forged or incomplete")
    expected_status = "QUALIFIED" if not observed_mismatches else UNQUALIFIED_PLATFORM
    require(value.get("status") == expected_status,
            "D12 platform qualification status contradicts its probes")
    return expected_status


def load_manifest():
    raw = MANIFEST.read_bytes()
    require(sha256_bytes(raw) == MANIFEST_FILE_SHA256, "frozen execution-manifest file hash drift")
    value = json.loads(raw.decode("utf-8"))
    require(canonical_digest(value) == MANIFEST_CONTRACT_SHA256, "frozen execution-manifest canonical digest drift")
    return value


def _find_by_id(values, value_id):
    matches = [value for value in values if value.get("id") == value_id]
    require(len(matches) == 1, "expected one manifest object with id {}".format(value_id))
    return matches[0]


def validate_manifest_contract(manifest):
    require(manifest.get("schema_version") == 2, "schema-2 manifest required")
    require(manifest.get("status") == "pending_D12", "immutable pre-decision manifest status drift")
    entries = manifest.get("entries")
    require(isinstance(entries, list) and len(entries) == 17, "manifest must contain exactly 17 ordered entries")
    expected_rows = ["U8-{:02d}".format(i) for i in range(1, 15)] + ["B7-01", "B7-02", "B7-03"]
    require([entry.get("source_matrix_row_id") for entry in entries] == expected_rows, "source-matrix order drift")
    require(manifest.get("row_order", {}).get("rows") == ROW_ORDER, "six-row order drift")
    regular = _find_by_id(manifest.get("sample_policies", []), "regular_interior_l6_10")
    trend = _find_by_id(manifest.get("sample_policies", []), "extraordinary_trend_24_per_corner")
    require(len(regular.get("samples", [])) == 10, "regular sample count drift")
    require(len(trend.get("samples", [])) == 24, "trend sample count drift")
    require([s.get("radius_exponent") for s in trend["samples"]] == [e for e in range(1, 9) for _ in range(3)], "trend-radius order drift")
    weight = manifest.get("sample_field_contract", {}).get("weight", {})
    require(weight.get("bits_hex") == "3ff0000000000000", "sample sentinel bits drift")
    require(struct.unpack(">Q", struct.pack(">d", 1.0))[0] == int(weight["bits_hex"], 16), "host binary64 sentinel mismatch")
    require("forbidden for quadrature" in weight.get("meaning", ""), "sentinel exclusion missing")
    levels = manifest.get("numeric_measurement_protocol", {}).get("levels", {})
    require(levels.get("bfr_approxLevelSmooth") == BFR_LEVELS, "Bfr sweep drift")
    require(levels.get("bfr_approxLevelSharp") == 6, "Bfr sharp level drift")
    require(levels.get("far_isolationLevel") == FAR_LEVELS, "Far sweep drift")
    repeats = manifest.get("numeric_measurement_protocol", {}).get("repeats", {})
    require(repeats == {"measured": 15, "warmup": 3}, "repeat protocol drift")
    threading = manifest.get("threading_protocol", {})
    require(threading.get("workers") == [1, 2, 4], "thread worker matrix drift")
    require(threading.get("rounds") == 20, "thread round count drift")
    require(threading.get("modes") == ["cache_disabled", "SurfaceFactoryCacheThreaded"], "thread cache-mode drift")
    require(threading.get("levels_approxLevelSmooth") == BFR_LEVELS, "thread level drift")
    qualification_platform = manifest.get("qualification_platform", {})
    require(qualification_platform.get("fingerprint") == EXPECTED_PLATFORM_FINGERPRINT,
            "qualification-platform fingerprint drift")
    build = qualification_platform.get("build", {})
    require(build.get("compiler_path") == EXPECTED_COMPILER_PATH and
            build.get("compiler_version") == EXPECTED_COMPILER_VERSION,
            "qualification-platform compiler identity drift")
    require(qualification_platform.get("power") == {
        "api": EXPECTED_POWER_API, "required_value": EXPECTED_POWER_VALUE,
        "sampling": "before and after every full case process"},
            "qualification-platform power protocol drift")
    require(qualification_platform.get("thermal") == {
        "api": EXPECTED_THERMAL_API, "required_value": EXPECTED_THERMAL_VALUE,
        "sampling": "before and after every full case process"},
            "qualification-platform thermal protocol drift")
    require("UNQUALIFIED_PLATFORM" in qualification_platform.get("qualification_failure", "") and
            "cannot satisfy D12 numeric platform gates" in
            qualification_platform.get("workflow_boundary", ""),
            "qualification-platform failure/workflow boundary drift")
    unique_valid = []
    for entry in entries:
        if entry.get("alias_of") is None and entry.get("numeric_gate_applicability", {}).get("threading_bfr_only"):
            entry_input = entry["input"]
            if entry_input.get("kind") == "deterministic_mutation":
                members = [{"content_identity_key": entry_input["output_content_identity_key"]}]
            else:
                members = entry_input.get("members", [entry_input.get("base_member")])
            for member in members:
                if member and member["content_identity_key"] not in unique_valid:
                    unique_valid.append(member["content_identity_key"])
    require(len(unique_valid) == 14, "threading content-identity count must be 14")
    require(len(unique_valid) * 7 * 2 * 3 == 588, "threading matrix must contain 588 tuples")
    aliases = {entry["execution_case_id"]: entry.get("alias_of") for entry in entries if entry.get("alias_of")}
    require(aliases == {"b7_01_single_flip_family": "u8_14_edge_flip_family", "b7_02_valence789": "u8_09_nonplatonic"}, "alias contract drift")
    return {"entry_count": 17, "unique_threading_contents": 14, "threading_tuple_count": 588}


def valid_unique_contents(manifest):
    """Return the frozen 14-content numeric order without counting aliases."""
    ordered = []
    for entry in manifest["entries"]:
        if entry.get("alias_of") is not None:
            continue
        if not entry["numeric_gate_applicability"]["threading_bfr_only"]:
            continue
        fixture = entry["input"]
        if fixture["kind"] == "deterministic_mutation":
            members = [{"content_identity_key": fixture["output_content_identity_key"]}]
        else:
            members = fixture["members"]
        for member in members:
            identity = member["content_identity_key"]
            if identity not in ordered:
                ordered.append(identity)
    require(len(ordered) == 14, "numeric content expansion is not exactly 14")
    return ordered


def expected_numeric_case_identities(manifest):
    expected = []
    for identity in valid_unique_contents(manifest):
        for level in BFR_LEVELS:
            expected.append((identity, "bfr", level, "cache_disabled"))
            expected.append((identity, "bfr", level, "SurfaceFactoryCache_serial"))
        for level in FAR_LEVELS:
            expected.append((identity, "far", level, "not_applicable_uncached"))
    require(len(expected) == 294, "numeric case expansion is not exactly 294")
    return expected


def expected_threading_identities(manifest):
    expected = []
    threading = manifest["threading_protocol"]
    for identity in valid_unique_contents(manifest):
        for level in threading["levels_approxLevelSmooth"]:
            for mode in threading["modes"]:
                for workers in threading["workers"]:
                    expected.append((identity, level, mode, workers))
    require(len(expected) == 588, "threading expansion is not exactly 588")
    return expected


def validate_changed_path_allowlist(paths):
    for path in paths:
        normalized = path.replace(os.sep, "/")
        require(any(pattern.match(normalized) for pattern in ALLOWED_PATH_PATTERNS),
                "forbidden B2 changed path: {}".format(normalized))
    return True


def validate_frozen_approval_anchors():
    plan = (REPO / "docs/bfr_loop_backend_plan_macos.md").read_text(encoding="utf-8")
    adr = (REPO / "docs/adr_unified_loop_backend.md").read_text(encoding="utf-8")
    for text, label in ((plan, "plan"), (adr, "ADR")):
        require("D10" in text and "Approved" in text, "{} lacks recorded D10 approval".format(label))
        require("D12" in text and "Approved" in text, "{} lacks recorded D12 approval".format(label))
        for rendered in ("5.0e-6", "2.5e-5", "1.25e-4", "1.0e-12"):
            require(rendered in text, "{} lacks frozen D10 value {}".format(label, rendered))
    require("Explicit user D10 approval on 2026-08-08" in plan, "D10 approval provenance drift")
    require("explicit user D12 approval followed on 2026-08-10" in plan, "D12 approval provenance drift")


def validate_source_separation():
    proof_dir = REPO / "experiments/bfr_qualification"
    candidate = proof_dir / "candidate.cpp"
    oracle_sources = tuple(REPO / path for path in ORACLE_SOURCE_PATHS)
    for path in (candidate,) + oracle_sources:
        require(path.is_file(), "missing proof source {}".format(path.relative_to(REPO)))
    oracle_text = "".join(path.read_text(encoding="utf-8")
                          for path in oracle_sources)
    for token in FORBIDDEN_ORACLE_TOKENS:
        require(token not in oracle_text, "oracle source contains forbidden dependency token {}".format(token))
    require("MPFR_RNDD" in oracle_text and "MPFR_RNDU" in oracle_text, "directed interval rounding is absent")
    require("mpfr_init2" in oracle_text and "544" in oracle_text, "544-bit MPFR endpoints are absent")
    uniform_text = (proof_dir / "stam_uniform.hpp").read_text(
        encoding="utf-8") + (proof_dir / "stam_uniform_box_spline.hpp").read_text(
            encoding="utf-8")
    require("stam_box_spline.hpp" not in uniform_text and
            "b2stam::" not in uniform_text,
            "uniform oracle route depends on primary Stam implementation")
    candidate_text = candidate.read_text(encoding="utf-8")
    require("OPENSUBDIV_VERSION_NUMBER != 30700" in candidate_text, "candidate exact OpenSubdiv version pin missing")
    require("validation-only sentinel" in candidate_text, "candidate sentinel exclusion anchor missing")
    forbidden_weight_use = re.findall(r"(?:\*|/)\s*(?:sample\.)?weight|(?:sample\.)?weight\s*(?:\*|/)", candidate_text)
    require(not forbidden_weight_use, "sample weight is consumed arithmetically")


def cheap_self_test():
    manifest = load_manifest()
    contract = validate_manifest_contract(manifest)
    validate_frozen_approval_anchors()
    validate_source_separation()
    return {
        "schema_version": 1,
        "kind": "b2_contract_self_test",
        "status": "ok",
        "manifest_file_sha256": MANIFEST_FILE_SHA256,
        "manifest_contract_sha256": MANIFEST_CONTRACT_SHA256,
        "contract": contract,
        "sample_weight": {"value": 1.0, "use": "validation_only_not_quadrature"},
        "candidate_roles": {"bfr": "qualification_target", "far": "regression_comparator_only"},
        "d9a_decided": False,
        "d9b_decided": False,
    }


def require_root(path_text, label):
    require(path_text, "{} is required".format(label))
    root = pathlib.Path(path_text).resolve()
    require(root.is_dir(), "{} does not exist: {}".format(label, root))
    return root


def contained(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def read_nonempty_lines(path, label):
    require(path.is_file() and path.stat().st_size > 0,
            "missing {}".format(label))
    return path.read_text(encoding="utf-8", errors="strict").splitlines()


def replace_build_placeholders(values, source_root, build_root, install_root):
    replacements = {
        "${OPENSUBDIV_SOURCE}": str(source_root),
        "${PROFILE_BUILD_ROOT}": str(build_root),
        "${PROFILE_INSTALL_ROOT}": str(install_root),
    }
    expanded = []
    for value in values:
        for placeholder, replacement in replacements.items():
            value = value.replace(placeholder, replacement)
        expanded.append(value)
    return expanded


def ordered_subsequence(values, expected):
    if not expected:
        return True
    for index in range(len(values) - len(expected) + 1):
        if values[index:index + len(expected)] == expected:
            return True
    return False


def audit_opensubdiv(opensubdiv_root, build_root, source_root,
                     opensubdiv_contract, profile_name):
    header = opensubdiv_root / "include/opensubdiv/version.h"
    archive = opensubdiv_root / "lib/libosdCPU.a"
    require(header.is_file() and archive.is_file(), "{} OpenSubdiv install incomplete".format(profile_name))
    require(contained(header, opensubdiv_root) and contained(archive, opensubdiv_root), "OpenSubdiv dependency escaped declared root")
    header_text = header.read_text(encoding="utf-8", errors="replace")
    require("OPENSUBDIV_VERSION_NUMBER 30700" in header_text, "OpenSubdiv version is not exactly 3.7.0")
    raw_members = run(["/usr/bin/ar", "-t", archive]).stdout.splitlines()
    expected_members = opensubdiv_contract["expected_raw_ar_t_members_in_order"]
    require(raw_members == expected_members, "{} archive member order/scope drift".format(profile_name))
    require(raw_members[1:] == opensubdiv_contract[
                "expected_archive_member_basenames_in_target_order"],
            "{} archive object-member order drift".format(profile_name))
    require(build_root.is_dir() and contained(build_root, build_root),
            "{} OpenSubdiv build root is unavailable".format(profile_name))
    required_artifacts = {
        "cmake_cache": build_root / "CMakeCache.txt",
        "configure_log": build_root / "configure.log",
        "compile_commands": build_root / "compile_commands.json",
        "build_log": build_root / "build.log",
        "link_command": build_root / "opensubdiv/CMakeFiles/osd_static_cpu.dir/link.txt",
        "install_manifest": build_root / "install_manifest.txt",
        "configure_arguments": build_root / "configure.args.txt",
        "build_arguments": build_root / "build.args.txt",
        "install_arguments": build_root / "install.args.txt",
        "build_environment": build_root / "build-environment.txt",
        "install_log": build_root / "install.log",
    }
    for label, path in required_artifacts.items():
        require(path.is_file() and path.stat().st_size > 0,
                "{} profile lacks {} provenance".format(profile_name, label))

    cmake_contract = opensubdiv_contract["cmake"]
    profile = opensubdiv_contract["profiles"][profile_name]
    configure_expected = [cmake_contract["path"], "-S", str(source_root),
                          "-B", str(build_root)] + replace_build_placeholders(
        cmake_contract["common_options_in_exact_order"], source_root,
        build_root, opensubdiv_root) + [
            "-DCMAKE_CXX_FLAGS=",
            "-DCMAKE_CXX_FLAGS_RELEASE={}".format(
                " ".join(profile["compile_flags"]))]
    build_expected = [cmake_contract["path"], "--build", str(build_root),
                      "--config", "Release", "--target", "osd_static_cpu",
                      "--parallel", "1", "--verbose"]
    install_expected = [cmake_contract["path"], "--install", str(build_root),
                        "--config", "Release"]
    require(read_nonempty_lines(required_artifacts["configure_arguments"],
                                "configure argument transcript") == configure_expected and
            read_nonempty_lines(required_artifacts["build_arguments"],
                                "build argument transcript") == build_expected and
            read_nonempty_lines(required_artifacts["install_arguments"],
                                "install argument transcript") == install_expected,
            "{} exact configure/build/install command drift".format(profile_name))
    expected_environment = ["{}={}".format(key, value) for key, value in sorted(
        opensubdiv_contract["build_environment"].items())]
    require(read_nonempty_lines(required_artifacts["build_environment"],
                                "build environment transcript") == expected_environment,
            "{} exact build environment drift".format(profile_name))

    cache_text = required_artifacts["cmake_cache"].read_text(
        encoding="utf-8", errors="strict")
    cache = {}
    for line in cache_text.splitlines():
        match = re.fullmatch(r"([^/#][^:]*):[^=]*=(.*)", line)
        if match:
            cache[match.group(1)] = match.group(2)
    exact_cache = {
        "CMAKE_BUILD_TYPE": "Release", "CMAKE_CXX_FLAGS": "",
        "CMAKE_CXX_FLAGS_RELEASE": " ".join(profile["compile_flags"]),
        "CMAKE_INSTALL_PREFIX": str(opensubdiv_root),
        "CMAKE_GENERATOR": "Unix Makefiles",
        "CMAKE_MAKE_PROGRAM": "/usr/bin/make",
        "CMAKE_OSX_ARCHITECTURES": "arm64",
        "CMAKE_OSX_DEPLOYMENT_TARGET": "26.0",
        "CMAKE_OSX_SYSROOT": "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk",
        "BUILD_SHARED_LIBS": "OFF", "NO_LIB": "OFF", "SIMD": "NONE",
        "OPENSUBDIV_GREGORY_EVAL_TRUE_DERIVATIVES": "OFF",
    }
    for key in ("NO_EXAMPLES", "NO_TUTORIALS", "NO_REGRESSION", "NO_PTEX",
                "NO_DOC", "NO_OMP", "NO_TBB", "NO_CUDA", "NO_OPENCL",
                "NO_CLEW", "NO_OPENGL", "NO_METAL", "NO_DX", "NO_TESTS",
                "NO_GLTESTS", "NO_GLEW", "NO_GLFW", "NO_GLFW_X11",
                "NO_MACOS_FRAMEWORK"):
        exact_cache[key] = "ON"
    require(all(cache.get(key) == value for key, value in exact_cache.items()),
            "{} CMake cache contradicts the frozen configuration".format(profile_name))

    compile_entries = json.loads(required_artifacts["compile_commands"].read_text(
        encoding="utf-8"))
    expected_sources = opensubdiv_contract["translation_units_in_target_order"]
    require(isinstance(compile_entries, list),
            "{} compile-command database is malformed".format(profile_name))
    selected_entries = []
    non_target_entries = []
    for entry in compile_entries:
        source = pathlib.Path(entry.get("file", "")).resolve()
        require(contained(source, source_root),
                "{} compile-command source escaped pinned checkout".format(profile_name))
        relative_source = str(source.relative_to(source_root))
        if relative_source in expected_sources:
            selected_entries.append(entry)
        else:
            non_target_entries.append({
                "source_relative_path": relative_source,
                "compile_command": (shlex.split(entry["command"])
                                    if isinstance(entry.get("command"), str)
                                    else entry.get("arguments")),
            })
    require(len(selected_entries) == len(expected_sources),
            "{} target compile-command TU count drift".format(profile_name))
    ledger = []
    for entry, expected_source, expected_member in zip(
            selected_entries, expected_sources,
            opensubdiv_contract["expected_archive_member_basenames_in_target_order"]):
        source = pathlib.Path(entry.get("file", "")).resolve()
        require(contained(source, source_root) and
                str(source.relative_to(source_root)) == expected_source,
                "{} compile-command TU order/path drift".format(profile_name))
        command = entry.get("command")
        arguments = entry.get("arguments")
        tokens = (shlex.split(command) if isinstance(command, str) else arguments)
        require(isinstance(tokens, list) and tokens and
                ordered_subsequence(tokens, profile["compile_flags"]),
                "{} compile command lacks exact profile flags".format(profile_name))
        optimization = [token for token in tokens if re.fullmatch(r"-O(?:[0-3sz]|fast)", token)]
        expected_optimization = "-O3" if profile_name == "release" else "-O1"
        sanitizers = [token for token in tokens if token.startswith("-fsanitize=")]
        require(set(optimization) == {expected_optimization} and
                (sanitizers == [] if profile_name == "release"
                 else set(sanitizers) == {"-fsanitize=thread"}) and
                "-ffast-math" not in tokens and "-fno-fast-math" in tokens and
                "-ffp-contract=off" in tokens and
                ordered_subsequence(tokens, ["-arch", "arm64"]),
                "{} compile command contains conflicting profile flags".format(profile_name))
        output_index = tokens.index("-o")
        object_path = pathlib.Path(tokens[output_index + 1])
        require(object_path.name == expected_member,
                "{} object/member mapping drift".format(profile_name))
        ledger.append({"source_relative_path": expected_source,
                       "source_sha256": sha256_file(source),
                       "object_member_basename": expected_member,
                       "compile_command": tokens})

    link_lines = read_nonempty_lines(required_artifacts["link_command"],
                                     "OpenSubdiv link command")
    require(len(link_lines) == 2, "{} archive link transcript drift".format(profile_name))
    archive_tokens = shlex.split(link_lines[0])
    require(archive_tokens[:2] == ["/Library/Developer/CommandLineTools/usr/bin/ar", "qc"] and
            [pathlib.Path(value).name for value in archive_tokens[3:]] ==
            opensubdiv_contract["expected_archive_member_basenames_in_target_order"] and
            shlex.split(link_lines[1])[0] ==
            "/Library/Developer/CommandLineTools/usr/bin/ranlib",
            "{} archive link object order/tool drift".format(profile_name))
    artifacts = {label: {"path": str(path), "sha256": sha256_file(path),
                         "size": path.stat().st_size}
                 for label, path in required_artifacts.items()}
    return {"profile": profile_name, "build_root": str(build_root),
            "install_root": str(opensubdiv_root), "archive": str(archive),
            "archive_sha256": sha256_file(archive),
            "archive_size": archive.stat().st_size,
            "raw_archive_members": raw_members,
            "configure_command": configure_expected, "build_command": build_expected,
            "install_command": install_expected,
            "build_environment": dict(opensubdiv_contract["build_environment"]),
            "global_compile_database_entry_count": len(compile_entries),
            "non_target_compile_database_entries": non_target_entries,
            "translation_unit_ledger": ledger,
            "provenance_artifacts": artifacts}


def audit_source_checkout(source_root, manifest):
    require((source_root / ".git").exists(), "OpenSubdiv source must be a git checkout")
    head = run(["git", "rev-parse", "HEAD"], cwd=source_root).stdout.strip()
    require(head == OPENSUBDIV_COMMIT, "OpenSubdiv source commit drift")
    require(not run(["git", "status", "--porcelain=v1"], cwd=source_root).stdout.strip(), "OpenSubdiv source checkout is dirty")
    ledger = []
    for rel in manifest["qualification_platform"]["build"]["opensubdiv"]["translation_units_in_target_order"]:
        path = source_root / rel
        require(path.is_file(), "missing pinned OpenSubdiv translation unit {}".format(rel))
        ledger.append({"path": rel, "sha256": sha256_file(path)})
    return {"head": head, "tree": run(["git", "rev-parse", "HEAD^{tree}"], cwd=source_root).stdout.strip(), "translation_units": ledger}


def audit_autotools_build(build_root, install_root, identity, configure_options):
    required = {
        "configure_arguments": build_root / "configure.args.txt",
        "build_arguments": build_root / "build.args.txt",
        "install_arguments": build_root / "install.args.txt",
        "build_environment": build_root / "build-environment.txt",
        "configure_transcript": build_root / "configure.log",
        "configure_state": build_root / "config.status",
        "configure_internal_log": build_root / "config.log",
        "generated_makefile": build_root / "Makefile",
        "build_transcript": build_root / "build.log",
        "install_transcript": build_root / "install.log",
    }
    for label, path in required.items():
        require(path.is_file() and path.stat().st_size > 0,
                "{} lacks {} provenance".format(identity, label))
    configure_expected = [str(build_root / "configure"),
                          "--prefix={}".format(install_root)] + configure_options
    require(read_nonempty_lines(required["configure_arguments"],
                                "{} configure arguments".format(identity)) ==
            configure_expected and
            read_nonempty_lines(required["build_arguments"],
                                "{} build arguments".format(identity)) ==
            ["/usr/bin/make", "-j1"] and
            read_nonempty_lines(required["install_arguments"],
                                "{} install arguments".format(identity)) ==
            ["/usr/bin/make", "install"],
            "{} configure/build/install command drift".format(identity))
    expected_environment = ["LANG=C", "LC_ALL=C", "SOURCE_DATE_EPOCH=0",
                            "TZ=UTC", "ZERO_AR_DATE=1"]
    require(read_nonempty_lines(required["build_environment"],
                                "{} build environment".format(identity)) ==
            expected_environment,
            "{} build environment drift".format(identity))
    return {"identity": identity, "build_root": str(build_root),
            "install_root": str(install_root),
            "configure_command": configure_expected,
            "build_command": ["/usr/bin/make", "-j1"],
            "install_command": ["/usr/bin/make", "install"],
            "build_environment": dict(line.split("=", 1)
                                      for line in expected_environment),
            "provenance_artifacts": {
                label: {"path": str(path), "sha256": sha256_file(path),
                        "size": path.stat().st_size}
                for label, path in required.items()}}


def audit_mpfr(mpfr_root, gmp_build_root, mpfr_build_root):
    header = mpfr_root / "include/mpfr.h"
    libraries = list((mpfr_root / "lib").glob("libmpfr.*"))
    require(header.is_file() and libraries, "MPFR root is incomplete")
    text = header.read_text(encoding="utf-8", errors="replace")
    require(re.search(r"#define\s+MPFR_VERSION_STRING\s+\"4\.2\.2\"", text), "MPFR compile-time version is not 4.2.2")
    library = sorted(libraries, key=lambda p: (p.suffix != ".dylib", p.name))[0]
    require(contained(library, mpfr_root), "MPFR library escaped declared root")
    gmp_header = mpfr_root / "include/gmp.h"
    gmp_libraries = list((mpfr_root / "lib").glob("libgmp.*"))
    require(gmp_header.is_file() and gmp_libraries,
            "GMP dependency in MPFR root is incomplete")
    gmp_text = gmp_header.read_text(encoding="utf-8", errors="replace")
    require(re.search(r"#define\s+__GNU_MP_VERSION\s+6\b", gmp_text) and
            re.search(r"#define\s+__GNU_MP_VERSION_MINOR\s+3\b", gmp_text) and
            re.search(r"#define\s+__GNU_MP_VERSION_PATCHLEVEL\s+0\b", gmp_text),
            "GMP compile-time version is not 6.3.0")
    gmp_library = sorted(gmp_libraries,
                         key=lambda path: (path.suffix != ".dylib", path.name))[0]
    result = {"root": str(mpfr_root), "mpfr_version": "4.2.2",
            "mpfr_header": str(header), "mpfr_library": str(library),
            "mpfr_library_sha256": sha256_file(library),
            "gmp_version": "6.3.0", "gmp_header": str(gmp_header),
            "gmp_library": str(gmp_library),
            "gmp_library_sha256": sha256_file(gmp_library)}
    result["gmp_build"] = audit_autotools_build(
        gmp_build_root, mpfr_root, "gmp-6.3.0",
        ["--enable-shared", "--disable-static"])
    result["mpfr_build"] = audit_autotools_build(
        mpfr_build_root, mpfr_root, "mpfr-4.2.2",
        ["--with-gmp={}".format(mpfr_root),
         "--enable-shared", "--disable-static"])
    return result


def audit_dependency_archives(args):
    specifications = (
        (args.gmp_archive, "gmp-6.3.0", GMP_ARCHIVE_SHA256),
        (args.mpfr_archive, "mpfr-4.2.2", MPFR_ARCHIVE_SHA256),
        (args.opensubdiv_archive, "opensubdiv-3.7.0", OPENSUBDIV_ARCHIVE_SHA256),
    )
    results = []
    for path_text, identity, expected_hash in specifications:
        require(path_text, "{} source archive is required".format(identity))
        path = pathlib.Path(path_text).resolve()
        require(path.is_file() and sha256_file(path) == expected_hash,
                "{} source archive SHA-256 drift".format(identity))
        results.append({"identity": identity, "path": str(path),
                        "sha256": expected_hash, "size": path.stat().st_size})
    return results


def audit_build_tools(manifest):
    build = manifest["qualification_platform"]["build"]
    opensubdiv = build["opensubdiv"]
    cmake_contract = opensubdiv["cmake"]
    make_contract = opensubdiv["build_tool"]
    cmake = pathlib.Path(cmake_contract["path"])
    make = pathlib.Path(make_contract["path"])
    compiler = pathlib.Path(build["compiler_path"])
    sdk = pathlib.Path(build["macos_sdk_path"])
    require(cmake.is_file() and make.is_file() and compiler.is_file() and sdk.is_dir(),
            "pinned build toolchain path is unavailable")
    cmake_output = run([cmake, "--version"]).stdout.splitlines()
    make_output = run([make, "--version"]).stdout.splitlines()
    compiler_output = run([compiler, "--version"]).stdout.splitlines()
    sdk_output = run(["/usr/bin/xcrun", "--sdk", "macosx",
                      "--show-sdk-version"]).stdout.strip()
    require(cmake_output and cmake_output[0] ==
            "cmake version {}".format(cmake_contract["version"]),
            "pinned CMake version drift")
    require(make_output and make_output[0] == make_contract["version"],
            "pinned make version drift")
    require(compiler_output and compiler_output[0] == build["compiler_version"],
            "pinned compiler version drift")
    require(sdk_output == build["macos_sdk_version"],
            "pinned macOS SDK version drift")
    return {
        "cmake": {"path": str(cmake), "version": cmake_output[0],
                  "full_output": cmake_output},
        "make": {"path": str(make), "version": make_output[0],
                 "full_output": make_output},
        "compiler": {"path": str(compiler), "version": compiler_output[0],
                     "full_output": compiler_output},
        "sdk": {"path": str(sdk), "version": sdk_output},
    }


def compile_proofs(build_dir, mpfr_root, opensubdiv_root, tsan_root,
                   release_build_root, tsan_build_root):
    build = load_manifest()["qualification_platform"]["build"]
    compiler = pathlib.Path(build["compiler_path"])
    require(compiler.is_file(), "pinned Apple clang++ is unavailable")
    build_dir = pathlib.Path(build_dir).resolve()
    release_root = pathlib.Path(release_build_root).resolve()
    tsan_proof_root = pathlib.Path(tsan_build_root).resolve()
    release_root.mkdir(parents=True, exist_ok=True)
    tsan_proof_root.mkdir(parents=True, exist_ok=True)
    source_provider = REPO / "experiments/bfr_qualification/candidate.cpp"
    source_representation = (
        REPO / "experiments/anchored_row_qualification/candidate.cpp")
    environment = {
        "LANG": "C", "LC_ALL": "C", "SOURCE_DATE_EPOCH": "0",
        "TZ": "UTC", "ZERO_AR_DATE": "1"}

    def profile_commands(root, install_root, flags):
        prefix = [str(compiler)] + list(flags)
        provider_object = root / "provider.o"
        representation_object = root / "representation.o"
        compile_commands = [
            prefix + ["-MMD", "-MF", str(root / "provider.d"),
                      "-I" + str(install_root / "include"),
                      str(source_provider), "-c", "-o",
                      str(provider_object)],
            prefix + ["-MMD", "-MF", str(root / "representation.d"),
                      str(source_representation), "-c", "-o",
                      str(representation_object)],
        ]
        link_commands = [
            prefix + [str(provider_object),
                      str(install_root / "lib/libosdCPU.a"),
                      "-framework", "IOKit", "-framework", "Foundation",
                      "-Wl,-map," + str(root / "provider.map"),
                      "-o", str(root / "provider")],
            prefix + [str(representation_object),
                      "-Wl,-map," + str(root / "representation.map"),
                      "-o", str(root / "representation")],
        ]
        for command in compile_commands + link_commands:
            run(command, env=environment)
        compile_path = root / "compile-commands.json"
        link_path = root / "link-commands.json"
        compile_path.write_bytes(canonical_bytes(compile_commands))
        link_path.write_bytes(canonical_bytes(link_commands))
        manifest = {
            "schema_id": "d12-command-profile-manifest-v1",
            "working_directory": str(REPO),
            "environment": environment,
            "compile_commands": {
                "relative_path": compile_path.name,
                "sha256": sha256_file(compile_path)},
            "link_commands": {
                "relative_path": link_path.name,
                "sha256": sha256_file(link_path)},
        }
        manifest_path = root / "command-profile.json"
        manifest_path.write_bytes(canonical_bytes(manifest))
        return {
            "root": root, "provider": root / "provider",
            "representation": root / "representation",
            "provider_dependency": root / "provider.d",
            "representation_dependency": root / "representation.d",
            "provider_map": root / "provider.map",
            "representation_map": root / "representation.map",
            "compile_commands": compile_commands,
            "link_commands": link_commands,
            "command_manifest": manifest_path,
        }

    release = profile_commands(
        release_root, pathlib.Path(opensubdiv_root).resolve(),
        build["common_release_compile_flags"])
    tsan = profile_commands(
        tsan_proof_root, pathlib.Path(tsan_root).resolve(),
        build["thread_sanitizer_compile_flags"])
    candidate = release["provider"]
    candidate_tsan = tsan["provider"]
    oracle = build_dir / "stam_oracle"
    common = [str(compiler)] + list(build["common_release_compile_flags"])
    oracle_cmd = common + ["-MMD", "-MF", str(build_dir / "oracle.d"),
                           "-I" + str(mpfr_root / "include"),
                           "experiments/bfr_qualification/stam_oracle.cpp",
                           "-L" + str(mpfr_root / "lib"),
                           "-Wl,-rpath," + str(mpfr_root / "lib"),
                           "-lmpfr", "-lgmp",
                           "-Wl,-map," + str(build_dir / "oracle.map"),
                           "-o", str(oracle)]
    run(oracle_cmd)
    compatibility = {
        build_dir / "bfr_candidate": candidate,
        build_dir / "bfr_candidate_tsan": candidate_tsan,
        build_dir / "candidate.d": release["provider_dependency"],
        build_dir / "candidate.map": release["provider_map"],
        build_dir / "candidate_tsan.d": tsan["provider_dependency"],
        build_dir / "candidate_tsan.map": tsan["provider_map"],
    }
    for destination, source in compatibility.items():
        shutil.copyfile(source, destination)
        if os.access(source, os.X_OK):
            destination.chmod(source.stat().st_mode)
    artifacts = {
        "release/provider.d": release["provider_dependency"],
        "release/provider.map": release["provider_map"],
        "release/representation.d": release["representation_dependency"],
        "release/representation.map": release["representation_map"],
        "tsan/provider.d": tsan["provider_dependency"],
        "tsan/provider.map": tsan["provider_map"],
        "tsan/representation.d": tsan["representation_dependency"],
        "tsan/representation.map": tsan["representation_map"],
        "oracle.d": build_dir / "oracle.d",
        "oracle.map": build_dir / "oracle.map"}
    for artifact in artifacts.values():
        require(artifact.is_file() and artifact.stat().st_size > 0,
                "missing proof compiler/link audit artifact {}".format(artifact.name))
    oracle_dependencies = (build_dir / "oracle.d").read_text(encoding="utf-8", errors="replace")
    for token in FORBIDDEN_ORACLE_TOKENS:
        require(token not in oracle_dependencies,
                "oracle dependency file contains forbidden token {}".format(token))
    binary_audit = {}
    for role, binary in (
            ("provider_release", candidate),
            ("provider_tsan", candidate_tsan),
            ("representation_release", release["representation"]),
            ("representation_tsan", tsan["representation"]),
            ("stam_oracle", oracle)):
        otool = run(["/usr/bin/otool", "-L", binary]).stdout
        undefined_symbols = run(["/usr/bin/nm", "-u", binary]).stdout
        binary_audit[role] = {
            "path": str(binary), "sha256": sha256_file(binary),
            "size": binary.stat().st_size, "otool_L": otool.splitlines(),
            "undefined_symbols_sha256": sha256_bytes(
                undefined_symbols.encode("utf-8")),
        }
    oracle_symbols = run(["/usr/bin/nm", "-u", oracle]).stdout
    for token in FORBIDDEN_ORACLE_TOKENS:
        require(token not in oracle_symbols, "oracle binary contains forbidden symbol token {}".format(token))
    oracle_links = run(["/usr/bin/otool", "-L", oracle]).stdout
    require("osd" not in oracle_links.lower(), "oracle linked OpenSubdiv")
    return {"candidate": candidate, "candidate_tsan": candidate_tsan,
            "representation": release["representation"],
            "representation_tsan": tsan["representation"],
            "oracle": oracle,
            "candidate_command": release["link_commands"][0],
            "candidate_tsan_command": tsan["link_commands"][0],
            "release_profile": release, "tsan_profile": tsan,
            "oracle_command": oracle_cmd,
            "binary_audit": binary_audit,
            "audit_artifacts": {
                name: sha256_file(artifact)
                for name, artifact in artifacts.items()}}


def validate_compiled_report(value, expected_kind):
    require(value.get("schema_version") == 1, "compiled report schema drift")
    require(value.get("kind") == expected_kind, "compiled report kind drift")
    require(value.get("status") == "ok", "compiled proof self-test failed")
    require(value.get("finite") is True, "compiled proof emitted nonfinite evidence")


def execute_fixture_preflights(candidate, manifest):
    """Exercise every unique schema-2 content before any numeric package exists."""
    valid = []
    negative = []
    seen = set()
    for entry in manifest["entries"]:
        if entry.get("alias_of") is not None:
            continue
        fixture = entry["input"]
        if fixture["kind"] == "deterministic_mutation":
            members = [fixture["base_member"]]
            mutation = fixture["mutation_id"]
            identity = fixture["output_content_identity_key"]
        else:
            members = fixture["members"]
            mutation = "none"
            identity = None
        for member in members:
            content_identity = identity or member["content_identity_key"]
            if content_identity in seen:
                continue
            seen.add(content_identity)
            mesh_path = (REPO / member["path"]).resolve()
            require(contained(mesh_path, REPO / "data/fixtures"),
                    "fixture path escaped frozen data root")
            command = [candidate, "--preflight", mesh_path, mutation]
            first = run(command, check=False)
            second = run(command, check=False)
            require(first.returncode == second.returncode and
                    first.stdout == second.stdout and first.stderr == second.stderr,
                    "fixture preflight is nondeterministic for {}".format(content_identity))
            if entry["numeric_gate_applicability"]["threading_bfr_only"]:
                require(first.returncode == 0, "valid fixture rejected: {}\n{}".format(
                    content_identity, first.stderr))
                report = json.loads(first.stdout)
                validate_compiled_report(report, "bfr_fixture_preflight")
                require(report.get("rows_emitted") == 0 and
                        report.get("candidate_objects_constructed") == 1,
                        "valid preflight lifecycle drift")
                valid.append({"content_identity_key": content_identity,
                              "execution_case_id": entry["execution_case_id"],
                              "member_id": member["member_id"],
                              "mutation": mutation, "report": report})
            else:
                require(first.returncode != 0 and not first.stdout,
                        "negative fixture did not fail before output: {}".format(content_identity))
                require("D2_" in first.stderr,
                        "negative fixture lacks D2 rejection reason")
                negative.append({"content_identity_key": content_identity,
                                 "execution_case_id": entry["execution_case_id"],
                                 "status": "REJECTED_BEFORE_OUTPUT",
                                 "candidate_objects_constructed": 0, "rows_emitted": 0,
                                 "reason": first.stderr.strip()})
    require([item["content_identity_key"] for item in valid] == valid_unique_contents(manifest),
            "valid fixture preflight order/coverage drift")
    require({item["execution_case_id"] for item in negative} == NEGATIVE_CASES,
            "negative fixture preflight coverage drift")
    with tempfile.TemporaryDirectory(prefix="bfr-pinched-vertex-") as temporary:
        pinched = pathlib.Path(temporary)
        (pinched / "vertices.csv").write_text(
            "0,0,0\n1,0,0\n0,1,0\n0,0,1\n-1,0,0\n0,-1,0\n0,0,-1\n",
            encoding="utf-8")
        (pinched / "faces.csv").write_text(
            "0,2,1\n0,1,3\n0,3,2\n1,2,3\n"
            "0,5,4\n0,4,6\n0,6,5\n4,5,6\n",
            encoding="utf-8")
        pinched_command = [candidate, "--preflight", pinched, "none"]
        pinched_first = run(pinched_command, check=False)
        pinched_second = run(pinched_command, check=False)
        require(pinched_first.returncode == pinched_second.returncode and
                pinched_first.stdout == pinched_second.stdout and
                pinched_first.stderr == pinched_second.stderr,
                "adversarial pinched-vertex preflight is nondeterministic")
        require(pinched_first.returncode != 0 and not pinched_first.stdout and
                pinched_first.stderr.strip() == "D2_INVALID_CLOSED_VERTEX_LINK",
                "pinched vertex was not rejected by the exact D2 link-cycle gate")
        pinched_evidence = {
            "content_identity_key": "adversarial_temporary_pinched_vertex",
            "status": "REJECTED_BEFORE_OUTPUT",
            "candidate_objects_constructed": 0, "rows_emitted": 0,
            "reason": pinched_first.stderr.strip(),
            "edge_incidence_and_global_connectivity_control": True,
            "retained_fixture": False,
        }
    identity_group = manifest["byte_identity_groups"][0]
    left = REPO / identity_group["members"][0]
    right = REPO / identity_group["members"][1]
    for filename in identity_group["required_equal_files"]:
        require((left / filename).read_bytes() == (right / filename).read_bytes(),
                "frozen byte-identity group drift: {}".format(filename))
    return {"valid": valid, "negative": negative,
            "adversarial_pinched_vertex": pinched_evidence,
            "deterministic_reruns_equal": True}


def valid_content_jobs(manifest):
    jobs = []
    seen = set()
    for entry in manifest["entries"]:
        if entry.get("alias_of") is not None or not entry["numeric_gate_applicability"]["threading_bfr_only"]:
            continue
        fixture = entry["input"]
        if fixture["kind"] == "deterministic_mutation":
            members = [fixture["base_member"]]
            mutation = fixture["mutation_id"]
            forced_identity = fixture["output_content_identity_key"]
        else:
            members = fixture["members"]
            mutation = "none"
            forced_identity = None
        for member in members:
            identity = forced_identity or member["content_identity_key"]
            if identity in seen:
                continue
            seen.add(identity)
            jobs.append({"content_identity_key": identity,
                         "execution_case_id": entry["execution_case_id"],
                         "member_id": member["member_id"],
                         "mesh_path": str((REPO / member["path"]).resolve()),
                         "mutation": mutation})
    require([job["content_identity_key"] for job in jobs] == valid_unique_contents(manifest),
            "valid execution job expansion drift")
    return jobs


def binary64_bits_hex(value):
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and
            math.isfinite(value), "nonfinite binary64 value")
    return struct.pack(">d", float(value)).hex()


def ordered_binary64_sum(values):
    """Use the frozen left-to-right binary64 order on every supported Python."""
    total = 0.0
    for value in values:
        total += value
    return total


def independent_mesh(job):
    mesh_path = pathlib.Path(job["mesh_path"])
    vertices = []
    faces = []
    with (mesh_path / "vertices.csv").open("r", encoding="utf-8") as stream:
        for line in stream:
            fields = line.rstrip("\n").split(",")
            require(len(fields) == 3, "fixture vertex row is not xyz")
            vertex = tuple(float(value) for value in fields)
            require(all(math.isfinite(value) for value in vertex),
                    "fixture contains nonfinite coordinate")
            vertices.append(vertex)
    with (mesh_path / "faces.csv").open("r", encoding="utf-8") as stream:
        for line in stream:
            fields = line.rstrip("\n").split(",")
            require(len(fields) == 3, "fixture face row is not triangular")
            faces.append(tuple(int(value) for value in fields))
    require(vertices and faces, "fixture is empty")
    if job["mutation"] == "coordinate_perturbation_v1":
        expected = ["3ff2b851eb851eb8", "bfe0cffc0ea99f27", "3fc0a3d70a3d70a4"]
        outputs = ["3ff2c851eb851eb8", "bfe0dffc0ea99f27", "3fc0c3d70a3d70a4"]
        deltas = [float.fromhex("0x1.0p-8"), float.fromhex("-0x1.0p-9"),
                  float.fromhex("0x1.0p-10")]
        require([binary64_bits_hex(value) for value in vertices[1]] == expected,
                "coordinate mutation input bits drift")
        mutated = tuple(vertices[1][axis] + deltas[axis] for axis in range(3))
        require([binary64_bits_hex(value) for value in mutated] == outputs,
                "coordinate mutation output bits drift")
        vertices[1] = mutated
    else:
        require(job["mutation"] == "none", "unexpected valid-case mutation")
    neighbors = [set() for _ in vertices]
    for face in faces:
        require(len(set(face)) == 3 and
                all(0 <= vertex < len(vertices) for vertex in face),
                "invalid valid-case face")
        for corner in range(3):
            a, b = face[corner], face[(corner + 1) % 3]
            neighbors[a].add(b)
            neighbors[b].add(a)
    return vertices, faces, [len(value) for value in neighbors]


def expected_case_samples(manifest, job):
    vertices, faces, valences = independent_mesh(job)
    regular = _find_by_id(manifest["sample_policies"], "regular_interior_l6_10")
    trend = _find_by_id(manifest["sample_policies"], "extraordinary_trend_24_per_corner")
    expected = []
    for face_row, face in enumerate(faces):
        for sample in regular["samples"]:
            expected.append({
                "face_row": face_row, "local_corner_or_none": -1,
                "sample_id": sample["id"],
                "u": float(Fraction(sample["u_numerator"], regular["lattice_denominator"])),
                "v": float(Fraction(sample["v_numerator"], regular["lattice_denominator"])),
            })
        for local_corner, vertex in enumerate(face):
            if valences[vertex] == 6:
                continue
            for sample in trend["samples"]:
                xi = Fraction(sample["xi"])
                eta = Fraction(sample["eta"])
                if local_corner == 0:
                    u, v = xi, eta
                elif local_corner == 1:
                    u, v = 1 - xi - eta, xi
                else:
                    u, v = eta, 1 - xi - eta
                expected.append({
                    "face_row": face_row, "local_corner_or_none": local_corner,
                    "sample_id": sample["id"], "u": float(u), "v": float(v),
                })
    return vertices, faces, expected


def validate_candidate_case(case_report, identity, candidate, level, mode,
                            manifest, job):
    validate_compiled_report(case_report, "bfr_candidate_case")
    require((case_report.get("content_identity_key"), case_report.get("candidate"),
             case_report.get("approximation_level"), case_report.get("applicable_mode")) ==
            (identity, candidate, level, mode), "candidate case identity drift")
    vertices, faces, expected_samples = expected_case_samples(manifest, job)
    rows = case_report.get("rows")
    require(isinstance(rows, list) and len(rows) == len(expected_samples) * len(ROW_ORDER),
            "candidate case row count is incomplete")
    row_keys = {
        "content_identity_key", "candidate", "approximation_level", "applicable_mode",
        "face_row", "local_corner_or_none", "sample_id", "u_binary64",
        "v_binary64", "u_binary64_bits_hex", "v_binary64_bits_hex",
        "weight_bits_hex", "row_kind", "source_ids", "coefficients",
    }
    digest = hashlib.sha256()
    maximum_error = 0.0
    face_source_unions = [set() for _ in faces]
    face_coefficient_counts = [0 for _ in faces]
    face_sample_counts = [0 for _ in faces]
    row_kind_counts = {kind: 0 for kind in ROW_ORDER}
    for row_index, row in enumerate(rows):
        require(isinstance(row, dict) and set(row) == row_keys,
                "candidate row schema contains missing or extra fields")
        sample = expected_samples[row_index // len(ROW_ORDER)]
        row_kind = ROW_ORDER[row_index % len(ROW_ORDER)]
        require((row["content_identity_key"], row["candidate"],
                 row["approximation_level"], row["applicable_mode"],
                 row["face_row"], row["local_corner_or_none"], row["sample_id"],
                 row["row_kind"]) ==
                (identity, candidate, level, mode, sample["face_row"],
                 sample["local_corner_or_none"], sample["sample_id"], row_kind),
                "candidate row identity/order drift")
        require(binary64_bits_hex(row["u_binary64"]) == binary64_bits_hex(sample["u"]) and
                binary64_bits_hex(row["v_binary64"]) == binary64_bits_hex(sample["v"]) and
                row["u_binary64_bits_hex"] == binary64_bits_hex(sample["u"]) and
                row["v_binary64_bits_hex"] == binary64_bits_hex(sample["v"]),
                "candidate row sample coordinate bits drift")
        require(row["weight_bits_hex"] == "3ff0000000000000",
                "candidate sample sentinel bits drift")
        source_ids = row["source_ids"]
        coefficients = row["coefficients"]
        require(isinstance(source_ids, list) and source_ids and
                all(type(value) is int for value in source_ids) and
                source_ids == sorted(set(source_ids)) and
                all(0 <= value < len(vertices) for value in source_ids),
                "candidate original-source IDs are malformed or out of range")
        require(isinstance(coefficients, list) and
                len(coefficients) == len(source_ids) and
                all(isinstance(value, (int, float)) and not isinstance(value, bool) and
                    math.isfinite(value) for value in coefficients),
                "candidate row coefficients are malformed or nonfinite")
        expected_sum = 1.0 if row_kind == "position" else 0.0
        coefficient_sum = ordered_binary64_sum(coefficients)
        maximum_error = max(maximum_error, abs(coefficient_sum - expected_sum))
        face = row["face_row"]
        face_source_unions[face].update(source_ids)
        face_coefficient_counts[face] += len(coefficients)
        row_kind_counts[row_kind] += 1
        if row_kind == "position":
            face_sample_counts[face] += 1
        encoded_sample = row["sample_id"].encode("utf-8")
        digest.update(b"B2ROWV1")
        digest.update(struct.pack("<i", face))
        digest.update(struct.pack("<I", len(encoded_sample)))
        digest.update(encoded_sample)
        digest.update(struct.pack("<I", row_index % len(ROW_ORDER)))
        digest.update(struct.pack("<I", len(source_ids)))
        for source_id, coefficient in zip(source_ids, coefficients):
            digest.update(struct.pack("<i", source_id))
            digest.update(struct.pack("<d", coefficient))
    payloads = [12 + 4 * len(face_source_unions[index]) +
                72 * face_sample_counts[index] +
                12 * face_coefficient_counts[index]
                for index in range(len(faces))]
    maximum_payload = max(payloads)
    row_group_count = len(expected_samples)
    require(case_report.get("row_group_count") == row_group_count and
            case_report.get("row_kind_counts") == row_kind_counts,
            "candidate row-group/kind summary contradicts emitted rows")
    require(case_report.get("source_reconstruction_complete") is True,
            "candidate source reconstruction summary drift")
    require(binary64_bits_hex(case_report.get("max_row_sum_error")) ==
            binary64_bits_hex(maximum_error),
            "candidate row-invariant maximum contradicts emitted rows")
    require(case_report.get("retained_payload_bytes_per_face") == maximum_payload,
            "candidate retained-payload summary contradicts emitted rows")
    require(case_report.get("warmup_count") == 3,
            "candidate case warmup count drift")
    timings = case_report.get("preparation_ns")
    require(isinstance(timings, list) and len(timings) == 15 and
            all(type(value) is int and value >= 0 for value in timings),
            "candidate case lacks 15 integer-nanosecond measurements")
    require(case_report.get("preparation_median_ns") == sorted(timings)[7],
            "candidate case median drift")
    expected_rss_counts = {
        "after_refiner_construction": 18,
        "after_factory_or_cache_construction": 18,
        "after_each_completed_face_row_insertion": 18 * row_group_count,
        "after_immutable_package_publication": 18,
        "after_row_package_destruction": 18,
        "after_factory_or_cache_destruction": 18,
        "after_refiner_destruction": 18,
    }
    expected_rss_sample_count = sum(expected_rss_counts.values())
    require(case_report.get("rss_baseline_sample_count") == 1 and
            case_report.get("rss_named_sample_counts") == expected_rss_counts and
            case_report.get("rss_named_sample_count") == expected_rss_sample_count and
            case_report.get("rss_expected_named_sample_count") == expected_rss_sample_count and
            case_report.get("rss_named_samples_complete") is True,
            "candidate RSS named-boundary coverage is incomplete or forged")
    require(case_report.get("untimed_serialization_replay") is True and
            case_report.get("serialization_replay_rss_sampled") is False,
            "candidate row serialization contaminated D12 timing/RSS")
    peak_rss = case_report.get("peak_rss_delta_bytes")
    require(type(peak_rss) is int and peak_rss >= 0,
            "candidate peak RSS observation is invalid")
    if candidate == "bfr":
        baseline = case_report.get("d12_rss_baseline_bytes")
        payload_observations = case_report.get(
            "d12_retained_payload_bytes_by_face")
        rss_observations = case_report.get("d12_rss_observations")
        require(case_report.get(
                    "d12_representation_workload_included") is True and
                type(baseline) is int and baseline >= 0 and
                payload_observations == payloads and
                isinstance(rss_observations, list) and
                len(rss_observations) == expected_rss_sample_count,
                "B2c D12 representation/RSS observations are incomplete")
        cursor = 0
        for repeat in range(18):
            phase = "warmup" if repeat < 3 else "measured"
            repeat_index = repeat if repeat < 3 else repeat - 3
            expected_observations = [
                ("after_refiner", None, None, None),
                ("after_factory_cache", None, None, None)]
            expected_observations.extend(
                ("after_face_insert", sample["face_row"],
                 (None if sample["local_corner_or_none"] < 0 else
                  sample["local_corner_or_none"]), sample["sample_id"])
                for sample in expected_samples)
            expected_observations.extend([
                ("after_package_publication", None, None, None),
                ("after_package_destruction", None, None, None),
                ("after_factory_cache_destruction", None, None, None),
                ("after_refiner_destruction", None, None, None)])
            for stage, face_id, local_corner, sample_id in \
                    expected_observations:
                observation = rss_observations[cursor]
                require(isinstance(observation, dict) and
                        set(observation) == {
                            "repeat_phase", "repeat_index", "face_id",
                            "local_corner_or_none", "sample_id", "stage",
                            "rss_bytes"} and
                        (observation["repeat_phase"],
                         observation["repeat_index"],
                         observation["stage"], observation["face_id"],
                         observation["local_corner_or_none"],
                         observation["sample_id"]) ==
                        (phase, repeat_index, stage, face_id,
                         local_corner, sample_id) and
                        type(observation["rss_bytes"]) is int and
                        observation["rss_bytes"] >= 0,
                        "B2c D12 RSS observation identity/order drift")
                cursor += 1
        derived_peak = max(
            [0] + [max(0, item["rss_bytes"] - baseline)
                   for item in rss_observations])
        require(cursor == len(rss_observations) and
                peak_rss == derived_peak,
                "B2c D12 RSS maximum differs from raw observations")
    d12_pass = (case_report["preparation_median_ns"] <= 1000000000 and
                max(timings) <= 10000000000 and maximum_payload <= 131072 and
                peak_rss <= 64 * 1048576)
    return {
        "canonical_rows_sha256": digest.hexdigest(),
        "max_row_sum_error": maximum_error,
        "row_group_count": row_group_count,
        "row_kind_counts": row_kind_counts,
        "retained_payload_bytes_per_face": maximum_payload,
        "source_reconstruction_complete": True,
        "rss_named_samples_complete": True,
        "rss_named_sample_count": expected_rss_sample_count,
        "rss_named_sample_counts": expected_rss_counts,
        "d12_within_budgets": d12_pass,
        "row_invariant_pass": maximum_error <= 1.0e-12,
    }


def d12_observation_within_budgets(value):
    timings = value.get("preparation_ns", [])
    return (len(timings) == 15 and
            value.get("preparation_median_ns", 1000000001) <= 1000000000 and
            max(timings) <= 10000000000 and
            value.get("retained_payload_bytes_per_face", 131073) <= 131072 and
            value.get("peak_rss_delta_bytes", 64 * 1048576 + 1) <= 64 * 1048576)


def exact_git_head():
    completed = run(["git", "rev-parse", "HEAD"])
    head = completed.stdout.strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None,
            "exact git head is unavailable")
    return head


def release_checkpoint_binding(candidate_binary):
    candidate = pathlib.Path(candidate_binary).resolve()
    require(candidate.is_file(), "candidate binary is unavailable for checkpoint binding")
    return {
        "manifest_file_sha256": MANIFEST_FILE_SHA256,
        "manifest_contract_sha256": MANIFEST_CONTRACT_SHA256,
        "git_head": exact_git_head(),
        "candidate_binary_sha256": sha256_file(candidate),
    }


def validate_case_summary_against_artifact(summary, report, validated,
                                           identity, candidate, level, mode):
    invariant_pass = validated["row_invariant_pass"]
    expected = {
        "content_identity_key": identity,
        "candidate": candidate,
        "approximation_level": level,
        "applicable_mode": mode,
        "status": "PASS" if invariant_pass else "FAIL",
        "failure_reasons": [] if invariant_pass else ["row_sum_invariant"],
        "d12_budget_observation": ("WITHIN_BUDGETS"
                                   if validated["d12_within_budgets"]
                                   else "EXCEEDS_BUDGETS"),
        "row_group_count": validated["row_group_count"],
        "row_kind_counts": validated["row_kind_counts"],
        "source_reconstruction_complete": True,
        "max_row_sum_error": validated["max_row_sum_error"],
        "warmup_count": 3,
        "preparation_ns": report["preparation_ns"],
        "preparation_median_ns": report["preparation_median_ns"],
        "retained_payload_bytes_per_face": validated["retained_payload_bytes_per_face"],
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
    for key, value in expected.items():
        if key == "max_row_sum_error":
            require(binary64_bits_hex(summary.get(key)) == binary64_bits_hex(value),
                    "checkpoint/artifact row maximum mismatch")
        else:
            require(summary.get(key) == value,
                    "checkpoint/artifact summary mismatch for {}".format(key))
    return True


def validate_case_artifact(artifact_path, summary, manifest, job,
                           identity, candidate, level, mode):
    require(artifact_path.is_file(), "complete case artifact is missing")
    compressed = artifact_path.read_bytes()
    require(sha256_bytes(compressed) == summary.get("complete_json_artifact_sha256"),
            "case artifact compressed SHA-256 mismatch")
    try:
        raw = gzip.decompress(compressed)
    except (OSError, EOFError) as error:
        raise QualificationError("case artifact gzip validation failed: {}".format(error))
    require(sha256_bytes(raw) == summary.get("complete_json_sha256"),
            "case artifact decompressed JSON SHA-256 mismatch")
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise QualificationError("case artifact JSON validation failed: {}".format(error))
    validated = validate_candidate_case(
        report, identity, candidate, level, mode, manifest, job)
    validate_case_summary_against_artifact(
        summary, report, validated, identity, candidate, level, mode)
    round_tripped = json.loads(json.dumps(report, sort_keys=True, allow_nan=False))
    validate_candidate_case(
        round_tripped, identity, candidate, level, mode, manifest, job)
    return report, validated


def validate_artifact_directory_inventory(artifact_root, summaries):
    expected = {item.get("complete_json_artifact") for item in summaries}
    require(None not in expected and len(expected) == len(summaries),
            "case artifact inventory contains missing or duplicate names")
    actual = {path.name for path in artifact_root.iterdir() if path.is_file()}
    require(actual == expected and
            all(not path.is_dir() for path in artifact_root.iterdir()),
            "case artifact directory contains missing, extra, or nested entries")
    return True


def execute_release_matrix(candidate_binary, manifest, artifact_dir=None,
                           progress_callback=None, checkpoint_path=None):
    require(artifact_dir, "full Release matrix requires a complete artifact directory")
    artifact_root = pathlib.Path(artifact_dir).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    checkpoint = pathlib.Path(checkpoint_path).resolve() if checkpoint_path else None
    require(checkpoint is not None, "full Release matrix requires a bound checkpoint")
    binding = release_checkpoint_binding(candidate_binary)
    summaries = []
    expected_identities = expected_numeric_case_identities(manifest)
    jobs_by_identity = {job["content_identity_key"]: job
                        for job in valid_content_jobs(manifest)}
    if checkpoint and checkpoint.is_file():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        require(saved.get("schema_version") == 2 and
                saved.get("kind") == "bfr_release_matrix_checkpoint",
                "Release checkpoint kind drift")
        require(saved.get("binding") == binding,
                "Release checkpoint manifest/head/candidate binding mismatch")
        summaries = saved.get("numeric_cases", [])
        actual_prefix = [(item.get("content_identity_key"), item.get("candidate"),
                          item.get("approximation_level"), item.get("applicable_mode"))
                         for item in summaries]
        require(actual_prefix == expected_identities[:len(actual_prefix)],
                "Release checkpoint identity prefix drift")
        for item, expected in zip(summaries, expected_identities):
            identity, candidate, level, mode = expected
            artifact = item.get("complete_json_artifact")
            expected_name = "{}-{}-{}-{}.json.gz".format(
                identity, candidate, level, mode)
            require(artifact == expected_name and pathlib.Path(artifact).name == artifact,
                    "Release checkpoint artifact name is missing or unsafe")
            validate_case_artifact(
                artifact_root / artifact, item, manifest, jobs_by_identity[identity],
                identity, candidate, level, mode)
        validate_artifact_directory_inventory(artifact_root, summaries)
    for identity, candidate, level, mode in expected_identities[len(summaries):]:
        job = jobs_by_identity[identity]
        command = [candidate_binary, "--execute-case", job["mesh_path"], job["mutation"],
                   candidate, str(level), mode, identity]
        primary_before = candidate_platform_probe(candidate_binary)
        first, primary_process_provenance = run_observed(
            command, timeout=30)
        primary_after = candidate_platform_probe(candidate_binary)
        first_report = json.loads(first.stdout)
        first_validated = validate_candidate_case(
            first_report, identity, candidate, level, mode, manifest, job)
        determinism_before = candidate_platform_probe(candidate_binary)
        second, determinism_process_provenance = run_observed(
            command, timeout=30)
        determinism_after = candidate_platform_probe(candidate_binary)
        second_report = json.loads(second.stdout)
        second_validated = validate_candidate_case(
            second_report, identity, candidate, level, mode, manifest, job)
        require(first_validated["canonical_rows_sha256"] ==
                second_validated["canonical_rows_sha256"],
                "candidate deterministic row rerun mismatch for {}".format((identity, candidate, level, mode)))
        require(first_validated["row_invariant_pass"] ==
                second_validated["row_invariant_pass"],
                "candidate row-invariant state changed across deterministic rerun")
        artifact = "{}-{}-{}-{}.json.gz".format(identity, candidate, level, mode)
        artifact_path = artifact_root / artifact
        raw_json = first.stdout.encode("utf-8")
        with artifact_path.open("wb") as raw_stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_stream, mtime=0) as stream:
                stream.write(raw_json)
        artifact_sha256 = sha256_file(artifact_path)
        summary = {
            "content_identity_key": identity, "candidate": candidate,
            "approximation_level": level, "applicable_mode": mode,
            "status": "PASS" if first_validated["row_invariant_pass"] else "FAIL",
            "failure_reasons": ([] if first_validated["row_invariant_pass"]
                                else ["row_sum_invariant"]),
            "d12_budget_observation": ("WITHIN_BUDGETS"
                                       if first_validated["d12_within_budgets"]
                                       else "EXCEEDS_BUDGETS"),
            "row_group_count": first_validated["row_group_count"],
            "row_kind_counts": first_validated["row_kind_counts"],
            "source_reconstruction_complete": first_validated["source_reconstruction_complete"],
            "max_row_sum_error": first_validated["max_row_sum_error"],
            "warmup_count": 3, "preparation_ns": first_report["preparation_ns"],
            "preparation_median_ns": first_report["preparation_median_ns"],
            "retained_payload_bytes_per_face": first_validated["retained_payload_bytes_per_face"],
            "peak_rss_delta_bytes": first_report["peak_rss_delta_bytes"],
            "rss_baseline_sample_count": first_report["rss_baseline_sample_count"],
            "rss_named_samples_complete": first_validated["rss_named_samples_complete"],
            "rss_named_sample_count": first_validated["rss_named_sample_count"],
            "rss_expected_named_sample_count": first_report[
                "rss_expected_named_sample_count"],
            "rss_named_sample_counts": first_validated["rss_named_sample_counts"],
            "untimed_serialization_replay": first_report[
                "untimed_serialization_replay"],
            "serialization_replay_rss_sampled": first_report[
                "serialization_replay_rss_sampled"],
            "canonical_rows_sha256": first_validated["canonical_rows_sha256"],
            "deterministic_rerun_equal": True,
            "complete_json_artifact": artifact,
            "complete_json_artifact_sha256": artifact_sha256,
            "complete_json_sha256": sha256_bytes(raw_json),
            "platform_boundary_samples": [
                {"boundary": "primary_before", "probe": primary_before},
                {"boundary": "primary_after", "probe": primary_after},
                {"boundary": "determinism_before", "probe": determinism_before},
                {"boundary": "determinism_after", "probe": determinism_after},
            ],
            "d12_primary_process_provenance": primary_process_provenance,
            "d12_determinism_process_provenance":
                determinism_process_provenance,
        }
        validate_case_artifact(
            artifact_path, summary, manifest, job,
            identity, candidate, level, mode)
        summaries.append(summary)
        if progress_callback:
            progress_callback(len(summaries), 294, summaries[-1])
        if checkpoint:
            checkpoint_payload = {"schema_version": 2,
                                  "kind": "bfr_release_matrix_checkpoint",
                                  "binding": binding,
                                  "complete": len(summaries) == 294,
                                  "numeric_cases": summaries}
            temporary = checkpoint.with_name(checkpoint.name + ".tmp")
            temporary.write_text(json.dumps(checkpoint_payload, sort_keys=True,
                                             separators=(",", ":")) + "\n",
                                 encoding="utf-8")
            os.replace(str(temporary), str(checkpoint))
    require(len(summaries) == 294, "Release matrix did not execute exactly 294 cases")
    validate_artifact_directory_inventory(artifact_root, summaries)
    require(all(isinstance(item.get("complete_json_artifact_sha256"), str) and
                len(item["complete_json_artifact_sha256"]) == 64 and
                isinstance(item.get("complete_json_sha256"), str) and
                len(item["complete_json_sha256"]) == 64
                for item in summaries),
            "Release matrix case-artifact set is incomplete")
    return {"case_count": 294, "numeric_cases": summaries,
            "deterministic_reruns_equal": True,
            "complete_case_artifacts": True,
            "binding": binding, "artifact_root": str(artifact_root),
            "all_d12_budgets_pass": all(d12_observation_within_budgets(value)
                                         for value in summaries),
            "all_row_invariants_pass": all("row_sum_invariant" not in value["failure_reasons"]
                                             for value in summaries)}


def validate_thread_case(report, expected):
    validate_compiled_report(report, "bfr_thread_case")
    identity, level, mode, workers = expected
    require((report.get("content_identity_key"), report.get("approxLevelSmooth"),
             report.get("mode"), report.get("worker_count")) == expected,
            "thread-case identity drift")
    require(report.get("rounds") == 20 and report.get("canonical_rows_identical") is True,
            "thread case lacks 20 byte-identical rounds")
    require(report.get("concurrent_factory_mode") == mode,
            "thread case did not exercise the named factory mode")
    require(isinstance(report.get("canonical_byte_count"), int) and
            report["canonical_byte_count"] > 0,
            "thread case emitted no canonical rows")
    return {"content_identity_key": identity, "approxLevelSmooth": level,
            "mode": mode, "worker_count": workers, "rounds": 20,
            "canonical_rows_identical": True,
            "concurrent_factory_mode": mode,
            "canonical_byte_count": report["canonical_byte_count"],
            "status": "PASS"}


def execute_thread_matrix(candidate_binary, manifest, instrumented,
                          progress_callback=None, checkpoint_path=None):
    expected = expected_threading_identities(manifest)
    checkpoint = pathlib.Path(checkpoint_path).resolve() if checkpoint_path else None
    results = []
    kind = "bfr_tsan_matrix_checkpoint" if instrumented else "bfr_release_thread_matrix_checkpoint"
    if checkpoint and checkpoint.is_file():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        require(saved.get("kind") == kind, "thread checkpoint kind/profile drift")
        results = saved.get("tuple_results", [])
        actual_prefix = [(item.get("content_identity_key"), item.get("approxLevelSmooth"),
                          item.get("mode"), item.get("worker_count")) for item in results]
        require(actual_prefix == expected[:len(actual_prefix)],
                "thread checkpoint identity prefix drift")
    jobs = {job["content_identity_key"]: job for job in valid_content_jobs(manifest)}
    environment = dict(os.environ)
    if instrumented:
        environment["TSAN_OPTIONS"] = "halt_on_error=1"
    for thread_identity in expected[len(results):]:
        identity, level, mode, workers = thread_identity
        job = jobs[identity]
        command = [candidate_binary, "--thread-case", job["mesh_path"], job["mutation"],
                   str(level), mode, str(workers), identity]
        completed = run(command, env=environment, timeout=120)
        value = validate_thread_case(json.loads(completed.stdout), thread_identity)
        value["instrumented_profile"] = instrumented
        results.append(value)
        if progress_callback:
            progress_callback(len(results), 588, value)
        if checkpoint:
            payload = {"schema_version": 1, "kind": kind,
                       "complete": len(results) == 588,
                       "instrumented_profile": instrumented,
                       "tuple_results": results}
            temporary = checkpoint.with_name(checkpoint.name + ".tmp")
            temporary.write_text(json.dumps(payload, sort_keys=True,
                                             separators=(",", ":")) + "\n",
                                 encoding="utf-8")
            os.replace(str(temporary), str(checkpoint))
    require(len(results) == 588, "threading matrix did not execute exactly 588 tuples")
    return {"tuple_count": 588, "rounds_per_tuple": 20,
            "instrumented_profile": instrumented,
            "tuple_results": results, "status": "PASS"}


def load_release_checkpoint(path_text, manifest, candidate_binary, artifact_dir):
    checkpoint = require_root(str(pathlib.Path(path_text).resolve().parent),
                              "release checkpoint parent") / pathlib.Path(path_text).name
    require(checkpoint.is_file(), "release checkpoint is unavailable")
    raw = checkpoint.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    binding = release_checkpoint_binding(candidate_binary)
    require(value.get("schema_version") == 2 and
            value.get("kind") == "bfr_release_matrix_checkpoint" and
            value.get("complete") is True, "Release checkpoint is not complete")
    require(value.get("binding") == binding,
            "Release checkpoint manifest/head/candidate binding mismatch")
    cases = value.get("numeric_cases")
    require(isinstance(cases, list) and len(cases) == 294,
            "Release checkpoint must contain exactly 294 cases")
    identities = [(item.get("content_identity_key"), item.get("candidate"),
                   item.get("approximation_level"), item.get("applicable_mode"))
                  for item in cases]
    require(identities == expected_numeric_case_identities(manifest),
            "Release checkpoint case identity drift")
    require(all(item.get("deterministic_rerun_equal") is True for item in cases),
            "Release checkpoint lacks deterministic row reruns")
    require(artifact_dir, "checkpoint finalization requires the complete artifact directory")
    artifact_root = pathlib.Path(artifact_dir).resolve()
    require(artifact_root.is_dir(), "checkpoint artifact directory is unavailable")
    jobs = {job["content_identity_key"]: job for job in valid_content_jobs(manifest)}
    for item, expected in zip(cases, expected_numeric_case_identities(manifest)):
        identity, candidate, level, mode = expected
        expected_name = "{}-{}-{}-{}.json.gz".format(
            identity, candidate, level, mode)
        require(item.get("complete_json_artifact") == expected_name,
                "checkpoint artifact identity drift")
        validate_case_artifact(
            artifact_root / expected_name, item, manifest, jobs[identity],
            identity, candidate, level, mode)
    validate_artifact_directory_inventory(artifact_root, cases)
    return {"path": str(checkpoint), "sha256": sha256_bytes(raw),
            "case_count": 294, "numeric_cases": cases,
            "binding": binding, "artifact_root": str(artifact_root),
            "complete_case_artifacts": True,
            "deterministic_reruns_equal": True,
            "all_d12_budgets_pass": all(d12_observation_within_budgets(item)
                                         for item in cases),
            "all_row_invariants_pass": all("row_sum_invariant" not in item.get("failure_reasons", [])
                                             for item in cases)}


def numeric_summary(values):
    require(values and all(math.isfinite(value) and value >= 0.0 for value in values),
            "spread statistic contains no finite observations")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    median = (ordered[midpoint] if len(ordered) % 2 else
              (ordered[midpoint - 1] + ordered[midpoint]) / 2.0)
    return {"observation_count": len(values), "maximum": max(values),
            "median": median}


def measured_near_vertex_spread(release, manifest):
    """Neutral observed spread at the two candidates' highest frozen settings."""
    artifact_root = pathlib.Path(release["artifact_root"])
    summaries = {(item["content_identity_key"], item["candidate"],
                  item["approximation_level"], item["applicable_mode"]): item
                 for item in release["numeric_cases"]}
    jobs = {job["content_identity_key"]: job for job in valid_content_jobs(manifest)}
    observations = []
    artifact_bindings = []
    for identity in valid_unique_contents(manifest):
        bfr_key = (identity, "bfr", 8, "cache_disabled")
        far_key = (identity, "far", 8, "not_applicable_uncached")
        bfr_summary = summaries[bfr_key]
        far_summary = summaries[far_key]
        bfr_report, _ = validate_case_artifact(
            artifact_root / bfr_summary["complete_json_artifact"], bfr_summary,
            manifest, jobs[identity], *bfr_key)
        far_report, _ = validate_case_artifact(
            artifact_root / far_summary["complete_json_artifact"], far_summary,
            manifest, jobs[identity], *far_key)
        artifact_bindings.extend([
            {"content_identity_key": identity, "candidate": "bfr",
             "artifact_sha256": bfr_summary["complete_json_artifact_sha256"]},
            {"content_identity_key": identity, "candidate": "far",
             "artifact_sha256": far_summary["complete_json_artifact_sha256"]},
        ])
        vertices, _, _ = expected_case_samples(manifest, jobs[identity])
        centroid = [ordered_binary64_sum(vertex[axis] for vertex in vertices) /
                    len(vertices)
                    for axis in range(3)]
        scale = max(abs(vertex[axis] - centroid[axis])
                    for vertex in vertices for axis in range(3))
        require(math.isfinite(scale) and scale > 0.0,
                "spread normalization scale is invalid")
        normalized = [[(vertex[axis] - centroid[axis]) / scale for axis in range(3)]
                      for vertex in vertices]
        bfr_rows = {(row["face_row"], row["local_corner_or_none"],
                     row["sample_id"], row["row_kind"]): row
                    for row in bfr_report["rows"]
                    if row["local_corner_or_none"] != -1}
        far_rows = {(row["face_row"], row["local_corner_or_none"],
                     row["sample_id"], row["row_kind"]): row
                    for row in far_report["rows"]
                    if row["local_corner_or_none"] != -1}
        require(bfr_rows.keys() == far_rows.keys(),
                "near-vertex spread rows are not aligned")
        for key in sorted(bfr_rows):
            face, corner, sample_id, row_kind = key
            radius_match = re.fullmatch(r"trend-r0([1-8])-ray0[0-2]", sample_id)
            require(radius_match is not None, "near-vertex spread sample schedule drift")
            left = dict(zip(bfr_rows[key]["source_ids"], bfr_rows[key]["coefficients"]))
            right = dict(zip(far_rows[key]["source_ids"], far_rows[key]["coefficients"]))
            source_union = sorted(set(left) | set(right))
            difference = {source: left.get(source, 0.0) - right.get(source, 0.0)
                          for source in source_union}
            coefficient_l1 = ordered_binary64_sum(
                abs(value) for value in difference.values())
            geometric_linf = max(abs(ordered_binary64_sum(
                difference[source] * normalized[source][axis]
                for source in source_union))
                                  for axis in range(3))
            observations.append({
                "content_identity_key": identity, "face_row": face,
                "local_corner": corner, "sample_id": sample_id,
                "radius_exponent": int(radius_match.group(1)),
                "row_kind": row_kind, "coefficient_l1": coefficient_l1,
                "normalized_geometric_linf": geometric_linf,
            })
    require(observations, "mandatory near-vertex spread has no observations")
    per_order = {}
    trend = {}
    for row_kind in ROW_ORDER:
        values = [item for item in observations if item["row_kind"] == row_kind]
        require(values, "near-vertex spread omitted {}".format(row_kind))
        coefficient_values = [item["coefficient_l1"] for item in values]
        geometric_values = [item["normalized_geometric_linf"] for item in values]
        maximum_item = max(values, key=lambda item: (
            item["coefficient_l1"], item["normalized_geometric_linf"],
            item["content_identity_key"], item["face_row"], item["local_corner"],
            item["sample_id"]))
        per_order[row_kind] = {
            "coefficient_l1": numeric_summary(coefficient_values),
            "normalized_geometric_linf": numeric_summary(geometric_values),
            "maximum_coefficient_l1_observation": maximum_item,
        }
        trend[row_kind] = {}
        for exponent in range(1, 9):
            radius_values = [item for item in values
                             if item["radius_exponent"] == exponent]
            trend[row_kind][str(exponent)] = {
                "coefficient_l1": numeric_summary(
                    [item["coefficient_l1"] for item in radius_values]),
                "normalized_geometric_linf": numeric_summary(
                    [item["normalized_geometric_linf"] for item in radius_values]),
            }
    return {
        "kind": "observed_inter_method_spread",
        "row_order": list(ROW_ORDER),
        "pairing": {
            "bfr": {"approxLevelSmooth": 8, "approxLevelSharp": 6,
                    "mode": "cache_disabled"},
            "far": {"isolationLevel": 8, "mode": "not_applicable_uncached"},
            "alignment": "same content/face/local-corner/trend-sample/original-source coarse frame",
            "selection_reason": "highest frozen setting for each candidate",
            "approximation_knobs_commensurable": False,
        },
        "normalization": "per-content coordinates centered at their arithmetic centroid and divided by maximum absolute centered coordinate",
        "observation_count": len(observations),
        "per_order": per_order,
        "trend_by_radius_exponent": trend,
        "overall_max_coefficient_l1": max(item["coefficient_l1"] for item in observations),
        "overall_max_normalized_geometric_linf": max(
            item["normalized_geometric_linf"] for item in observations),
        "artifact_bindings": artifact_bindings,
        "is_accuracy_ranking": False, "is_accuracy_floor": False,
        "is_accuracy_bound": False,
    }


def measured_terminal_row_example(release, manifest):
    identity = "closed_valence3_tetrahedron"
    level = 4
    modes = ["cache_disabled", "SurfaceFactoryCache_serial"]
    summaries = {(item["content_identity_key"], item["candidate"],
                  item["approximation_level"], item["applicable_mode"]): item
                 for item in release["numeric_cases"]}
    job = next(job for job in valid_content_jobs(manifest)
               if job["content_identity_key"] == identity)
    selected = []
    artifact_hashes = {}
    for mode in modes:
        key = (identity, "bfr", level, mode)
        summary = summaries[key]
        report, _ = validate_case_artifact(
            pathlib.Path(release["artifact_root"]) /
            summary["complete_json_artifact"], summary, manifest, job, *key)
        matches = [row for row in report["rows"]
                   if row["face_row"] == 0 and
                   row["local_corner_or_none"] == 1 and
                   row["sample_id"] == "trend-r08-ray01" and
                   row["row_kind"] == "dvv"]
        require(len(matches) == 1,
                "terminal row-invariant example is missing or duplicated")
        selected.append(matches[0])
        artifact_hashes[mode] = summary["complete_json_artifact_sha256"]
    require(selected[0]["source_ids"] == selected[1]["source_ids"] and
            [binary64_bits_hex(value) for value in selected[0]["coefficients"]] ==
            [binary64_bits_hex(value) for value in selected[1]["coefficients"]],
            "terminal Bfr cache modes disagree at the cited row")
    observed_sum = ordered_binary64_sum(selected[0]["coefficients"])
    return {"content_identity_key": identity, "candidate": "bfr",
            "approximation_level": level, "modes": modes,
            "row_kind": "dvv", "face_row": 0, "local_corner": 1,
            "sample_id": "trend-r08-ray01", "sum": observed_sum,
            "absolute_error": abs(observed_sum), "cache_modes_equal": True,
            "artifact_sha256_by_mode": artifact_hashes}


def validate_observed_near_vertex_spread(value, manifest):
    """Validate the neutral, paired Far--Bfr observation without ranking it."""
    require(isinstance(value, dict) and
            value.get("kind") == "observed_inter_method_spread",
            "mandatory near-vertex spread observation is missing")
    require(value.get("row_order") == ROW_ORDER,
            "near-vertex spread derivative order drift")
    pairing = value.get("pairing")
    require(pairing == {
        "bfr": {"approxLevelSmooth": 8, "approxLevelSharp": 6,
                "mode": "cache_disabled"},
        "far": {"isolationLevel": 8, "mode": "not_applicable_uncached"},
        "alignment": "same content/face/local-corner/trend-sample/original-source coarse frame",
        "selection_reason": "highest frozen setting for each candidate",
        "approximation_knobs_commensurable": False,
    }, "near-vertex spread pairing/alignment drift")
    require(value.get("normalization") ==
            "per-content coordinates centered at their arithmetic centroid and divided by maximum absolute centered coordinate",
            "near-vertex spread normalization drift")
    require(value.get("is_accuracy_ranking") is False and
            value.get("is_accuracy_floor") is False and
            value.get("is_accuracy_bound") is False,
            "near-vertex spread was promoted to a ranking, floor, or bound")
    require(set(value) == {
        "kind", "row_order", "pairing", "normalization", "observation_count",
        "per_order", "trend_by_radius_exponent",
        "overall_max_coefficient_l1", "overall_max_normalized_geometric_linf",
        "artifact_bindings", "is_accuracy_ranking", "is_accuracy_floor",
        "is_accuracy_bound",
    }, "near-vertex spread schema contains missing or extra fields")

    def validate_statistic(statistic, label):
        require(isinstance(statistic, dict) and
                set(statistic) == {"observation_count", "maximum", "median"},
                "{} statistic schema drift".format(label))
        require(type(statistic.get("observation_count")) is int and
                statistic["observation_count"] > 0,
                "{} statistic has no observations".format(label))
        for key in ("maximum", "median"):
            observed = statistic.get(key)
            require(isinstance(observed, (int, float)) and
                    not isinstance(observed, bool) and math.isfinite(observed) and
                    observed >= 0.0,
                    "{} {} is invalid".format(label, key))
        require(statistic["median"] <= statistic["maximum"],
                "{} median exceeds maximum".format(label))

    per_order = value.get("per_order")
    trends = value.get("trend_by_radius_exponent")
    require(isinstance(per_order, dict) and set(per_order) == set(ROW_ORDER) and
            isinstance(trends, dict) and set(trends) == set(ROW_ORDER),
            "near-vertex spread does not cover all six derivative orders")
    total_observations = 0
    coefficient_maxima = []
    geometric_maxima = []
    expected_radii = {str(value) for value in range(1, 9)}
    observation_keys = {
        "content_identity_key", "face_row", "local_corner", "sample_id",
        "radius_exponent", "row_kind", "coefficient_l1",
        "normalized_geometric_linf",
    }
    for row_kind in ROW_ORDER:
        order = per_order[row_kind]
        require(isinstance(order, dict) and set(order) == {
            "coefficient_l1", "normalized_geometric_linf",
            "maximum_coefficient_l1_observation"},
            "near-vertex per-order schema drift")
        coefficient = order["coefficient_l1"]
        geometry = order["normalized_geometric_linf"]
        validate_statistic(coefficient, "{} coefficient L1".format(row_kind))
        validate_statistic(geometry, "{} normalized geometry Linf".format(row_kind))
        require(coefficient["observation_count"] == geometry["observation_count"],
                "near-vertex per-order metric counts disagree")
        maximum_observation = order["maximum_coefficient_l1_observation"]
        require(isinstance(maximum_observation, dict) and
                set(maximum_observation) == observation_keys and
                maximum_observation.get("row_kind") == row_kind and
                maximum_observation.get("radius_exponent") in range(1, 9) and
                maximum_observation.get("coefficient_l1") == coefficient["maximum"] and
                isinstance(maximum_observation.get("normalized_geometric_linf"),
                           (int, float)) and
                math.isfinite(maximum_observation["normalized_geometric_linf"]) and
                maximum_observation["normalized_geometric_linf"] >= 0.0,
                "near-vertex maximum observation is not reconstructible")
        order_trend = trends[row_kind]
        require(isinstance(order_trend, dict) and set(order_trend) == expected_radii,
                "near-vertex trend lacks radii 1 through 8")
        trend_count = 0
        for exponent in range(1, 9):
            radius = order_trend[str(exponent)]
            require(isinstance(radius, dict) and set(radius) == {
                "coefficient_l1", "normalized_geometric_linf"},
                "near-vertex radius statistic schema drift")
            validate_statistic(radius["coefficient_l1"],
                               "{} radius {} coefficient L1".format(row_kind, exponent))
            validate_statistic(radius["normalized_geometric_linf"],
                               "{} radius {} normalized geometry Linf".format(
                                   row_kind, exponent))
            require(radius["coefficient_l1"]["observation_count"] ==
                    radius["normalized_geometric_linf"]["observation_count"],
                    "near-vertex radius metric counts disagree")
            trend_count += radius["coefficient_l1"]["observation_count"]
        require(trend_count == coefficient["observation_count"],
                "near-vertex radius counts do not reconstruct per-order count")
        total_observations += coefficient["observation_count"]
        coefficient_maxima.append(coefficient["maximum"])
        geometric_maxima.append(geometry["maximum"])
    require(value.get("observation_count") == total_observations and
            value.get("overall_max_coefficient_l1") == max(coefficient_maxima) and
            value.get("overall_max_normalized_geometric_linf") == max(geometric_maxima),
            "near-vertex overall counts/maxima do not reconstruct")
    bindings = value.get("artifact_bindings")
    expected_bindings = [(identity, candidate)
                         for identity in valid_unique_contents(manifest)
                         for candidate in ("bfr", "far")]
    require(isinstance(bindings, list) and len(bindings) == len(expected_bindings),
            "near-vertex spread artifact binding set is incomplete")
    for binding, expected in zip(bindings, expected_bindings):
        require(isinstance(binding, dict) and set(binding) == {
            "content_identity_key", "candidate", "artifact_sha256"} and
            (binding.get("content_identity_key"), binding.get("candidate")) == expected and
            re.fullmatch(r"[0-9a-f]{64}", binding.get("artifact_sha256", "")) is not None,
            "near-vertex spread artifact binding drift")
    return True


def terminal_failure_evidence(release, preflights, platform_qualification,
                              observed_spread,
                              checkpoint_path=None, checkpoint_sha256=None,
                              provenance=None, complete_case_artifacts=False):
    cases = release["numeric_cases"]
    bfr_failures = [item for item in cases
                    if item["candidate"] == "bfr" and
                    "row_sum_invariant" in item.get("failure_reasons", [])]
    far_failures = [item for item in cases
                    if item["candidate"] == "far" and
                    "row_sum_invariant" in item.get("failure_reasons", [])]
    require(len(cases) == 294 and len(bfr_failures) == 124 and len(far_failures) == 62,
            "terminal failure distribution drift")
    bfr_maximum = max(item["max_row_sum_error"] for item in cases if item["candidate"] == "bfr")
    far_maximum = max(item["max_row_sum_error"] for item in cases if item["candidate"] == "far")
    require(bfr_maximum == 2.0368522054550406e-11 and
            far_maximum == 3.356106503815681e-10,
            "terminal failure maxima drift")
    max_median = max(item["preparation_median_ns"] for item in cases)
    max_single = max(max(item["preparation_ns"]) for item in cases)
    max_payload = max(item["retained_payload_bytes_per_face"] for item in cases)
    max_rss = max(item["peak_rss_delta_bytes"] for item in cases)
    exceeded_case_count = sum(
        item["preparation_median_ns"] > 1000000000 or
        max(item["preparation_ns"]) > 10000000000 or
        item["retained_payload_bytes_per_face"] > 131072 or
        item["peak_rss_delta_bytes"] > 64 * 1048576
        for item in cases)
    platform_qualified = platform_qualification.get("status") == "QUALIFIED"
    example = measured_terminal_row_example(release, load_manifest())
    require(example["absolute_error"] == 1.4781509349859334e-12,
            "terminal row-invariant example magnitude drift")
    d12 = {
        "status": ("PASS" if exceeded_case_count == 0 else "FAIL")
        if platform_qualified else UNQUALIFIED_PLATFORM,
        "budget_verdict": ("PASS" if exceeded_case_count == 0 else "FAIL")
        if platform_qualified else "NEITHER_PASS_NOR_FAIL",
        "case_count": 294,
        "exceeded_case_count_observation": exceeded_case_count,
        "max_preparation_median_ns": max_median,
        "max_preparation_single_ns": max_single,
        "max_retained_payload_bytes_per_face": max_payload,
        "max_peak_rss_delta_bytes": max_rss,
        "budgets": {"median_ns": 1000000000, "single_ns": 10000000000,
                    "payload_bytes_per_face": 131072, "peak_rss_delta_bytes": 64 * 1048576},
    }
    bfr_by_level = {str(level): sum(item["approximation_level"] == level
                                    for item in bfr_failures) for level in range(2, 9)}
    far_by_level = {str(level): sum(item["approximation_level"] == level
                                    for item in far_failures) for level in range(2, 9)}
    not_run = "NOT_RUN_TERMINAL_BFR_FAILURE"
    d12_preparation = ("PASS" if max_median <= 1000000000 and
                       max_single <= 10000000000 else "FAIL")
    d12_payload = "PASS" if max_payload <= 131072 else "FAIL"
    d12_rss = "PASS" if max_rss <= 64 * 1048576 else "FAIL"
    if not platform_qualified:
        d12_preparation = UNQUALIFIED_PLATFORM
        d12_payload = UNQUALIFIED_PLATFORM
        d12_rss = UNQUALIFIED_PLATFORM
    criteria = {
        "regular_analytic_rows_and_integrands": not_run,
        "row_sum_invariants": "FAIL",
        "original_source_reconstruction": "PASS",
        "internal_refinement_convergence": not_run,
        "irregular_primary_stam_oracle": not_run,
        "d12_preparation_cost": d12_preparation,
        "d12_retained_payload": d12_payload,
        "d12_peak_rss": d12_rss,
        "cache_disabled_concurrency": not_run,
        "threaded_cache_fully_instrumented_tsan": not_run,
    }
    return {
        "schema_version": 1, "kind": "bfr_qualification_evidence", "status": "ok",
        "proof_execution_status": "COMPLETE_TERMINAL_BFR_FAILURE",
        "manifest_file_sha256": MANIFEST_FILE_SHA256,
        "manifest_contract_sha256": MANIFEST_CONTRACT_SHA256,
        "candidate_roles": {"bfr": "qualification_target", "far": "regression_comparator_only"},
        "sample_weight_use": "validation_only_not_quadrature",
        "sample_weight_bits_hex": "3ff0000000000000", "sample_weight_arithmetic_uses": 0,
        "near_vertex_accuracy_ranking_declined": True,
        "inter_method_spread_is_accuracy_floor": False,
        "observed_near_vertex_inter_method_spread": observed_spread,
        "far_promotion_declined": True, "approximation_knobs_commensurable": False,
        "execution": {"canonical_case_order": CANONICAL_CASE_ORDER,
                      "deterministic_reruns_equal": True,
                      "negative_cases": preflights["negative"],
                      "adversarial_pinched_vertex":
                          preflights["adversarial_pinched_vertex"],
                      "numeric_cases": cases,
                      "complete_case_artifacts": complete_case_artifacts},
        "release_checkpoint": {"path": checkpoint_path, "sha256": checkpoint_sha256,
                               "complete": True, "case_count": 294,
                               "binding": release["binding"]},
        "row_invariant_failure": {
            "criterion": "position sum one and derivative sums zero within 1.0e-12",
            "tolerance": 1.0e-12, "tolerance_changed": False,
            "bfr_failure_count": 124, "bfr_failure_count_by_level": bfr_by_level,
            "bfr_max_error": bfr_maximum,
            "example": example,
            "far_comparator_failure_count": 62,
            "far_failure_count_by_level": far_by_level,
            "far_max_error": far_maximum,
        },
        "d12_summary": d12,
        "platform_qualification": platform_qualification,
        "canonical_determinism": {"status": "PASS", "case_count": 294,
                                  "two_pass_rows_equal": True},
        "negative_preflight": {"status": "PASS", "manifest_case_count": 3,
                               "adversarial_case_count": 1, "case_count": 4,
                               "failure_before_output": True,
                               "pinched_vertex_link_cycle_rejected": True},
        "criterion_order": list(BFR_CRITERIA),
        "bfr_d9a_criteria": criteria, "bfr_verdict": "FAIL",
        "blocking_criterion": "row_sum_invariants",
        "terminal_not_run_reason": "P9: the frozen Bfr row-invariant criterion failed; non-decisive downstream science was not run",
        "oracle_certificates": [], "oracle_coverage_complete": False,
        "threading_tsan_complete": False,
        "review_status": {"verification_agent": "PENDING", "technical_review": "PENDING",
                          "scientific_review": "PENDING", "gatekeeper": "PENDING"},
        "package_review_complete": False,
        "d9a_decided": False, "d9b_decided": False,
        "dependency_provenance": provenance,
    }


def validate_dependency_provenance(value, manifest, checkpoint_binding):
    require(isinstance(value, dict), "dependency provenance is malformed")
    archives = value.get("dependency_source_archives")
    expected_archives = [
        ("gmp-6.3.0", GMP_ARCHIVE_SHA256),
        ("mpfr-4.2.2", MPFR_ARCHIVE_SHA256),
        ("opensubdiv-3.7.0", OPENSUBDIV_ARCHIVE_SHA256),
    ]
    require(isinstance(archives, list) and len(archives) == 3,
            "dependency source-archive provenance is incomplete")
    for archive, expected in zip(archives, expected_archives):
        require(isinstance(archive, dict) and
                archive.get("identity") == expected[0] and
                archive.get("sha256") == expected[1] and
                isinstance(archive.get("path"), str) and archive["path"] and
                type(archive.get("size")) is int and archive["size"] > 0,
                "dependency source-archive provenance drift")
    tools = value.get("build_tools")
    build_contract = manifest["qualification_platform"]["build"]
    require(isinstance(tools, dict) and
            tools.get("cmake", {}).get("path") ==
            build_contract["opensubdiv"]["cmake"]["path"] and
            tools.get("cmake", {}).get("version") == "cmake version 4.4.2" and
            tools.get("make", {}).get("path") == "/usr/bin/make" and
            tools.get("make", {}).get("version") == "GNU Make 3.81" and
            tools.get("compiler", {}).get("path") == EXPECTED_COMPILER_PATH and
            tools.get("compiler", {}).get("version") == EXPECTED_COMPILER_VERSION and
            tools.get("sdk", {}) == {
                "path": build_contract["macos_sdk_path"], "version": "26.5"},
            "build-tool provenance drift")

    mpfr = value.get("mpfr")
    require(isinstance(mpfr, dict) and mpfr.get("mpfr_version") == "4.2.2" and
            mpfr.get("gmp_version") == "6.3.0" and
            all(re.fullmatch(r"[0-9a-f]{64}", mpfr.get(key, "")) is not None
                for key in ("mpfr_library_sha256", "gmp_library_sha256")),
            "MPFR/GMP installed dependency provenance drift")
    for key, identity in (("gmp_build", "gmp-6.3.0"),
                          ("mpfr_build", "mpfr-4.2.2")):
        build = mpfr.get(key)
        require(isinstance(build, dict) and build.get("identity") == identity and
                build.get("build_command") == ["/usr/bin/make", "-j1"] and
                build.get("install_command") == ["/usr/bin/make", "install"] and
                build.get("build_environment") == {
                    "LANG": "C", "LC_ALL": "C", "SOURCE_DATE_EPOCH": "0",
                    "TZ": "UTC", "ZERO_AR_DATE": "1"} and
                isinstance(build.get("provenance_artifacts"), dict) and
                set(build["provenance_artifacts"]) == {
                    "configure_arguments", "build_arguments", "install_arguments",
                    "build_environment", "configure_transcript", "configure_state",
                    "configure_internal_log", "generated_makefile",
                    "build_transcript", "install_transcript"},
                "{} build provenance is incomplete".format(identity))

    opensubdiv_contract = build_contract["opensubdiv"]
    source = value.get("source")
    require(isinstance(source, dict) and source.get("head") == OPENSUBDIV_COMMIT and
            re.fullmatch(r"[0-9a-f]{40}", source.get("tree", "")) is not None,
            "OpenSubdiv source checkout provenance drift")
    source_ledger = source.get("translation_units")
    require(isinstance(source_ledger, list) and
            [item.get("path") for item in source_ledger] ==
            opensubdiv_contract["translation_units_in_target_order"] and
            all(re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) is not None
                for item in source_ledger),
            "OpenSubdiv source translation-unit ledger drift")
    profile_roots = []
    for key, profile_name in (("opensubdiv_release", "release"),
                              ("opensubdiv_tsan", "thread_sanitizer")):
        profile = value.get(key)
        require(isinstance(profile, dict) and profile.get("profile") == profile_name,
                "{} OpenSubdiv profile provenance missing".format(profile_name))
        profile_roots.extend([profile.get("build_root"), profile.get("install_root")])
        require(profile.get("raw_archive_members") ==
                opensubdiv_contract["expected_raw_ar_t_members_in_order"] and
                re.fullmatch(r"[0-9a-f]{64}",
                             profile.get("archive_sha256", "")) is not None and
                type(profile.get("archive_size")) is int and
                profile["archive_size"] > 0 and
                profile.get("build_environment") ==
                opensubdiv_contract["build_environment"],
                "{} OpenSubdiv archive/environment provenance drift".format(
                    profile_name))
        ledger = profile.get("translation_unit_ledger")
        require(isinstance(ledger, list) and
                [item.get("source_relative_path") for item in ledger] ==
                opensubdiv_contract["translation_units_in_target_order"] and
                [item.get("object_member_basename") for item in ledger] ==
                opensubdiv_contract[
                    "expected_archive_member_basenames_in_target_order"] and
                [item.get("source_sha256") for item in ledger] ==
                [item["sha256"] for item in source_ledger] and
                all(isinstance(item.get("compile_command"), list) and
                    item["compile_command"] for item in ledger),
                "{} OpenSubdiv compile ledger drift".format(profile_name))
        artifacts = profile.get("provenance_artifacts")
        require(isinstance(artifacts, dict) and set(artifacts) == {
            "cmake_cache", "configure_log", "compile_commands", "build_log",
            "link_command", "install_manifest", "configure_arguments",
            "build_arguments", "install_arguments", "build_environment",
            "install_log"} and
            all(re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) is not None and
                type(item.get("size")) is int and item["size"] > 0
                for item in artifacts.values()),
                "{} OpenSubdiv provenance artifact ledger drift".format(profile_name))
    require(len(set(profile_roots)) == 4,
            "OpenSubdiv Release/TSan roots are not pairwise disjoint")

    require(value.get("candidate_binary_sha256") ==
            checkpoint_binding["candidate_binary_sha256"],
            "candidate/checkpoint binary identity drift")
    proof_artifacts = value.get("proof_audit_artifacts")
    require(isinstance(proof_artifacts, dict) and set(proof_artifacts) == {
        "release/provider.d", "release/provider.map",
        "release/representation.d", "release/representation.map",
        "tsan/provider.d", "tsan/provider.map",
        "tsan/representation.d", "tsan/representation.map",
        "oracle.d", "oracle.map"} and
        all(re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            for digest in proof_artifacts.values()),
            "proof dependency/map artifact provenance drift")
    binary_audit = value.get("proof_binary_audit")
    expected_binary_hashes = {
        "provider_release": value.get("candidate_binary_sha256"),
        "provider_tsan": value.get("candidate_tsan_binary_sha256"),
        "representation_release": value.get(
            "representation_binary_sha256"),
        "representation_tsan": value.get(
            "representation_tsan_binary_sha256"),
        "stam_oracle": value.get("oracle_binary_sha256"),
    }
    require(isinstance(binary_audit, dict) and
            set(binary_audit) == set(expected_binary_hashes) and
            all(binary_audit[name].get("sha256") == digest and
                isinstance(binary_audit[name].get("otool_L"), list) and
                binary_audit[name]["otool_L"]
                for name, digest in expected_binary_hashes.items()),
            "proof binary/link provenance drift")
    commands = value.get("proof_compile_commands")
    require(isinstance(commands, dict) and set(commands) == {
        "release_compile", "release_link", "thread_sanitizer_compile",
        "thread_sanitizer_link", "oracle"} and
            all(isinstance(command, list) and command and
                (command[0] == EXPECTED_COMPILER_PATH
                 if key == "oracle" else
                 len(command) == 2 and
                 all(isinstance(argv, list) and argv and
                     argv[0] == EXPECTED_COMPILER_PATH for argv in command))
                for key, command in commands.items()),
            "proof compile/link command provenance drift")
    command_manifests = value.get("proof_command_manifests")
    require(isinstance(command_manifests, dict) and
            set(command_manifests) == {"release", "thread_sanitizer"} and
            all(pathlib.Path(path).is_file() for path in
                command_manifests.values()),
            "proof command-manifest provenance drift")
    return True


def validate_evidence_document(report):
    """Independent schema/semantic validator used by tests and reviewers."""
    manifest = load_manifest()
    validate_manifest_contract(manifest)
    require(report.get("schema_version") == 1, "evidence schema version drift")
    require(report.get("kind") == "bfr_qualification_evidence", "evidence kind drift")
    require(report.get("manifest_file_sha256") == MANIFEST_FILE_SHA256,
            "evidence manifest file identity drift")
    require(report.get("manifest_contract_sha256") == MANIFEST_CONTRACT_SHA256,
            "evidence manifest contract identity drift")
    roles = report.get("candidate_roles")
    require(roles == {"bfr": "qualification_target", "far": "regression_comparator_only"}, "candidate labels/roles were swapped or widened")
    require(report.get("sample_weight_use") == "validation_only_not_quadrature", "sample sentinel was promoted to quadrature")
    require(report.get("sample_weight_bits_hex") == "3ff0000000000000",
            "sample sentinel identity drift")
    require(report.get("sample_weight_arithmetic_uses") == 0,
            "sample sentinel participated in arithmetic")
    require(report.get("near_vertex_accuracy_ranking_declined") is True,
            "near-vertex Bfr/Far ranking was not declined")
    require(report.get("inter_method_spread_is_accuracy_floor") is False,
            "correlated inter-method spread was promoted to an accuracy floor")
    require(report.get("far_promotion_declined") is True,
            "Far comparator was promoted beyond its frozen role")
    require(report.get("approximation_knobs_commensurable") is False,
            "Bfr and Far approximation controls were treated as commensurable")
    validate_observed_near_vertex_spread(
        report.get("observed_near_vertex_inter_method_spread"), manifest)

    execution = report.get("execution")
    require(isinstance(execution, dict), "missing execution coverage")
    require(execution.get("canonical_case_order") == CANONICAL_CASE_ORDER,
            "canonical execution coverage is missing or reordered")
    require(execution.get("deterministic_reruns_equal") is True,
            "deterministic rerun evidence is absent")
    negative = execution.get("negative_cases")
    require(isinstance(negative, list) and len(negative) == 3,
            "negative fixture coverage must contain exactly three cases")
    require({value.get("execution_case_id") for value in negative} == NEGATIVE_CASES,
            "negative fixture identity coverage drift")
    for value in negative:
        require(value.get("status") == "REJECTED_BEFORE_OUTPUT",
                "negative fixture did not fail before output")
        require(value.get("candidate_objects_constructed") == 0 and value.get("rows_emitted") == 0,
                "negative fixture constructed a candidate or emitted rows")
    adversarial = execution.get("adversarial_pinched_vertex")
    require(isinstance(adversarial, dict) and
            adversarial.get("status") == "REJECTED_BEFORE_OUTPUT" and
            adversarial.get("reason") == "D2_INVALID_CLOSED_VERTEX_LINK" and
            adversarial.get("candidate_objects_constructed") == 0 and
            adversarial.get("rows_emitted") == 0 and
            adversarial.get("edge_incidence_and_global_connectivity_control") is True and
            adversarial.get("retained_fixture") is False,
            "adversarial pinched-vertex D2 preflight is absent or incomplete")

    numeric_cases = execution.get("numeric_cases")
    require(isinstance(numeric_cases, list), "missing numeric case results")
    jobs = {job["content_identity_key"]: job for job in valid_content_jobs(manifest)}
    expected_group_counts = {
        identity: len(expected_case_samples(manifest, job)[2])
        for identity, job in jobs.items()
    }
    actual_numeric = []
    for value in numeric_cases:
        identity = (value.get("content_identity_key"), value.get("candidate"),
                    value.get("approximation_level"), value.get("applicable_mode"))
        actual_numeric.append(identity)
        require(value.get("status") in ("PASS", "FAIL"),
                "numeric case has no terminal evidence status")
        require(value.get("row_group_count") == expected_group_counts.get(identity[0]),
                "numeric case row-group count disagrees with the frozen sample schedule")
        row_counts = value.get("row_kind_counts")
        require(isinstance(row_counts, dict) and set(row_counts) == set(ROW_ORDER),
                "numeric case row-kind coverage missing")
        require(len(set(row_counts.values())) == 1 and next(iter(row_counts.values())) > 0,
                "numeric case does not contain all six rows at every group")
        require(value.get("source_reconstruction_complete") is True,
                "numeric case source reconstruction incomplete")
        require(isinstance(value.get("max_row_sum_error"), (int, float)) and
                math.isfinite(value["max_row_sum_error"]),
                "numeric case row invariant metric is nonfinite")
        if value["status"] == "PASS":
            require(value["max_row_sum_error"] <= 1.0e-12,
                    "numeric PASS hides a row invariant failure")
        elif value["max_row_sum_error"] > 1.0e-12:
            require("row_sum_invariant" in value.get("failure_reasons", []),
                    "numeric FAIL omits its row-invariant reason")
        timings = value.get("preparation_ns")
        require(isinstance(timings, list) and len(timings) == 15,
                "D12 requires all 15 measured preparation samples")
        require(value.get("warmup_count") == 3,
                "D12 requires exactly three warmups")
        require(all(isinstance(item, int) and item >= 0 for item in timings),
                "invalid D12 integer-nanosecond preparation sample")
        require(value.get("preparation_median_ns") == sorted(timings)[7],
                "D12 ordinary median is not the eighth sorted value")
        require(isinstance(value.get("retained_payload_bytes_per_face"), int) and
                value["retained_payload_bytes_per_face"] >= 0,
                "invalid D12 retained-payload observation")
        require(isinstance(value.get("peak_rss_delta_bytes"), int) and
                value["peak_rss_delta_bytes"] >= 0,
                "invalid D12 RSS observation")
        require(value.get("rss_named_samples_complete") is True,
                "D12 named RSS lifecycle samples are incomplete")
        expected_rss_counts = {
            "after_refiner_construction": 18,
            "after_factory_or_cache_construction": 18,
            "after_each_completed_face_row_insertion": 18 * value["row_group_count"],
            "after_immutable_package_publication": 18,
            "after_row_package_destruction": 18,
            "after_factory_or_cache_destruction": 18,
            "after_refiner_destruction": 18,
        }
        expected_rss_total = sum(expected_rss_counts.values())
        require(value.get("rss_baseline_sample_count") == 1 and
                value.get("rss_named_sample_counts") == expected_rss_counts and
                value.get("rss_named_sample_count") == expected_rss_total and
                value.get("rss_expected_named_sample_count") == expected_rss_total and
                value.get("untimed_serialization_replay") is True and
                value.get("serialization_replay_rss_sampled") is False,
                "D12 lifecycle/RSS accounting is not the exact 3+15 protocol")
    require(actual_numeric == expected_numeric_case_identities(manifest),
            "numeric execution coverage is incomplete, duplicated, or reordered")
    platform_status = validate_platform_qualification(
        report.get("platform_qualification"), manifest, numeric_cases)
    if execution.get("complete_case_artifacts") is True:
        require(all(isinstance(value.get("complete_json_artifact"), str) and
                    value["complete_json_artifact"] and
                    pathlib.Path(value["complete_json_artifact"]).name ==
                    value["complete_json_artifact"] and
                    isinstance(value.get("complete_json_artifact_sha256"), str) and
                    re.fullmatch(r"[0-9a-f]{64}",
                                 value["complete_json_artifact_sha256"]) is not None and
                    isinstance(value.get("complete_json_sha256"), str) and
                    re.fullmatch(r"[0-9a-f]{64}",
                                 value["complete_json_sha256"]) is not None
                    for value in numeric_cases),
                "complete case-artifact claim lacks names or SHA-256 identities")
        level8_hashes = {
            (value["content_identity_key"], value["candidate"]):
                value["complete_json_artifact_sha256"]
            for value in numeric_cases
            if value["approximation_level"] == 8 and
            ((value["candidate"] == "bfr" and
              value["applicable_mode"] == "cache_disabled") or
             (value["candidate"] == "far" and
              value["applicable_mode"] == "not_applicable_uncached"))
        }
        spread_bindings = report[
            "observed_near_vertex_inter_method_spread"]["artifact_bindings"]
        require(all(level8_hashes.get((binding["content_identity_key"],
                                       binding["candidate"])) ==
                    binding["artifact_sha256"] for binding in spread_bindings),
                "near-vertex spread bindings do not match complete case artifacts")

    if (report.get("proof_execution_status") == "COMPLETE_TERMINAL_BFR_FAILURE"):
        require(report.get("status") == "ok" and report.get("bfr_verdict") == "FAIL",
                "terminal proof execution must be successful with scientific FAIL")
        require(report.get("blocking_criterion") == "row_sum_invariants",
                "terminal Bfr failure lacks the exact blocking criterion")
        failure = report.get("row_invariant_failure")
        require(isinstance(failure, dict) and failure.get("tolerance") == 1.0e-12 and
                failure.get("tolerance_changed") is False,
                "terminal row-invariant tolerance drift")
        require(failure.get("bfr_failure_count") == 124 and
                failure.get("far_comparator_failure_count") == 62 and
                failure.get("bfr_max_error") == 2.0368522054550406e-11 and
                failure.get("far_max_error") == 3.356106503815681e-10,
                "terminal row-invariant counts/maxima drift")
        observed_bfr_failures = [value for value in numeric_cases
                                 if value["candidate"] == "bfr" and
                                 "row_sum_invariant" in value.get("failure_reasons", [])]
        observed_far_failures = [value for value in numeric_cases
                                 if value["candidate"] == "far" and
                                 "row_sum_invariant" in value.get("failure_reasons", [])]
        require(len(observed_bfr_failures) == 124 and len(observed_far_failures) == 62 and
                max(value["max_row_sum_error"] for value in observed_bfr_failures) ==
                failure["bfr_max_error"] and
                max(value["max_row_sum_error"] for value in observed_far_failures) ==
                failure["far_max_error"],
                "terminal summary does not match executed case failures")
        example = failure.get("example")
        require(isinstance(example, dict) and set(example) == {
            "content_identity_key", "candidate", "approximation_level", "modes",
            "row_kind", "face_row", "local_corner", "sample_id", "sum",
            "absolute_error", "cache_modes_equal", "artifact_sha256_by_mode"} and
                (example.get("content_identity_key"), example.get("candidate"),
                 example.get("approximation_level"), example.get("modes"),
                 example.get("row_kind"), example.get("face_row"),
                 example.get("local_corner"), example.get("sample_id")) ==
                ("closed_valence3_tetrahedron", "bfr", 4,
                 ["cache_disabled", "SurfaceFactoryCache_serial"], "dvv", 0, 1,
                 "trend-r08-ray01") and
                example.get("sum") == 1.4781509349859334e-12 and
                example.get("absolute_error") == 1.4781509349859334e-12 and
                example.get("cache_modes_equal") is True and
                isinstance(example.get("artifact_sha256_by_mode"), dict) and
                set(example["artifact_sha256_by_mode"]) == {
                    "cache_disabled", "SurfaceFactoryCache_serial"} and
                all(re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                    for digest in example["artifact_sha256_by_mode"].values()),
                "terminal row-invariant example drift")
        if execution.get("complete_case_artifacts") is True:
            summary_hashes = {
                value["applicable_mode"]: value["complete_json_artifact_sha256"]
                for value in numeric_cases
                if value["content_identity_key"] ==
                "closed_valence3_tetrahedron" and value["candidate"] == "bfr" and
                value["approximation_level"] == 4 and
                value["applicable_mode"] in {
                    "cache_disabled", "SurfaceFactoryCache_serial"}}
            require(example["artifact_sha256_by_mode"] == summary_hashes,
                    "terminal example artifact binding drift")
        d12 = report.get("d12_summary")
        require(isinstance(d12, dict) and d12.get("case_count") == 294,
                "terminal evidence lacks D12 observation summary")
        observed_exceeded = sum(
            value["preparation_median_ns"] > 1000000000 or
            max(value["preparation_ns"]) > 10000000000 or
            value["retained_payload_bytes_per_face"] > 131072 or
            value["peak_rss_delta_bytes"] > 64 * 1048576
            for value in numeric_cases)
        require(d12.get("exceeded_case_count_observation") == observed_exceeded,
                "D12 budget observation count drift")
        require(d12.get("max_preparation_median_ns") ==
                max(value["preparation_median_ns"] for value in numeric_cases) and
                d12.get("max_preparation_single_ns") ==
                max(max(value["preparation_ns"]) for value in numeric_cases) and
                d12.get("max_retained_payload_bytes_per_face") ==
                max(value["retained_payload_bytes_per_face"] for value in numeric_cases) and
                d12.get("max_peak_rss_delta_bytes") ==
                max(value["peak_rss_delta_bytes"] for value in numeric_cases) and
                d12.get("budgets") == {
                    "median_ns": 1000000000, "single_ns": 10000000000,
                    "payload_bytes_per_face": 131072,
                    "peak_rss_delta_bytes": 64 * 1048576},
                "D12 maxima or frozen budgets drift")
        expected_d12_status = (("PASS" if observed_exceeded == 0 else "FAIL")
                               if platform_status == "QUALIFIED"
                               else UNQUALIFIED_PLATFORM)
        expected_budget_verdict = (("PASS" if observed_exceeded == 0 else "FAIL")
                                   if platform_status == "QUALIFIED"
                                   else "NEITHER_PASS_NOR_FAIL")
        require(d12.get("status") == expected_d12_status and
                d12.get("budget_verdict") == expected_budget_verdict,
                "D12 verdict ignores or masquerades platform qualification")
        require(report.get("canonical_determinism") ==
                {"status": "PASS", "case_count": 294, "two_pass_rows_equal": True},
                "terminal evidence lacks canonical determinism PASS")
        require(report.get("negative_preflight") ==
                {"status": "PASS", "manifest_case_count": 3,
                 "adversarial_case_count": 1, "case_count": 4,
                 "failure_before_output": True,
                 "pinched_vertex_link_cycle_rejected": True},
                "terminal evidence lacks negative-preflight PASS")
        checkpoint = report.get("release_checkpoint")
        require(isinstance(checkpoint, dict) and checkpoint.get("complete") is True and
                checkpoint.get("case_count") == 294 and
                isinstance(checkpoint.get("path"), str) and checkpoint["path"] and
                re.fullmatch(r"[0-9a-f]{64}", checkpoint.get("sha256", "")) is not None,
                "terminal evidence lacks a complete checkpoint identity")
        binding = checkpoint.get("binding")
        require(isinstance(binding, dict) and set(binding) == {
            "manifest_file_sha256", "manifest_contract_sha256", "git_head",
            "candidate_binary_sha256"} and
                binding.get("manifest_file_sha256") == MANIFEST_FILE_SHA256 and
                binding.get("manifest_contract_sha256") == MANIFEST_CONTRACT_SHA256 and
                re.fullmatch(r"[0-9a-f]{40}", binding.get("git_head", "")) is not None and
                re.fullmatch(r"[0-9a-f]{64}",
                             binding.get("candidate_binary_sha256", "")) is not None,
                "terminal checkpoint manifest/head/candidate binding drift")
        provenance = report.get("dependency_provenance")
        if provenance is not None:
            validate_dependency_provenance(provenance, manifest, binding)
        criteria = report.get("bfr_d9a_criteria")
        require(report.get("criterion_order") == BFR_CRITERIA and
                isinstance(criteria, dict) and set(criteria) == set(BFR_CRITERIA),
                "terminal criterion identity/order drift")
        if platform_status == "QUALIFIED":
            expected_preparation = ("PASS" if
                max(value["preparation_median_ns"] for value in numeric_cases) <= 1000000000 and
                max(max(value["preparation_ns"]) for value in numeric_cases) <= 10000000000
                else "FAIL")
            expected_payload = ("PASS" if
                max(value["retained_payload_bytes_per_face"] for value in numeric_cases) <= 131072
                else "FAIL")
            expected_rss = ("PASS" if
                max(value["peak_rss_delta_bytes"] for value in numeric_cases) <= 64 * 1048576
                else "FAIL")
        else:
            expected_preparation = UNQUALIFIED_PLATFORM
            expected_payload = UNQUALIFIED_PLATFORM
            expected_rss = UNQUALIFIED_PLATFORM
        require(criteria["row_sum_invariants"] == "FAIL" and
                criteria["original_source_reconstruction"] == "PASS" and
                criteria["d12_preparation_cost"] == expected_preparation and
                criteria["d12_retained_payload"] == expected_payload and
                criteria["d12_peak_rss"] == expected_rss,
                "terminal executed criterion states drift")
        terminal_state = "NOT_RUN_TERMINAL_BFR_FAILURE"
        for criterion in ("regular_analytic_rows_and_integrands",
                          "internal_refinement_convergence",
                          "irregular_primary_stam_oracle",
                          "cache_disabled_concurrency",
                          "threaded_cache_fully_instrumented_tsan"):
            require(criteria[criterion] == terminal_state,
                    "false downstream PASS after terminal Bfr failure")
        require(report.get("oracle_certificates") == [] and
                report.get("oracle_coverage_complete") is False and
                report.get("threading_tsan_complete") is False,
                "terminal-not-run science was falsely labeled complete")
        require(report.get("review_status") == {
            "verification_agent": "PENDING", "technical_review": "PENDING",
            "scientific_review": "PENDING", "gatekeeper": "PENDING"},
                "terminal package falsely claims completed reviews")
        require(report.get("package_review_complete") is False and
                report.get("d9a_decided") is False and report.get("d9b_decided") is False,
                "terminal proof exceeded decision/review authority")
        return True

    rows = report.get("rows")
    require(isinstance(rows, list) and rows, "evidence contains no rows")
    groups = {}
    for row in rows:
        for key in ("execution_case_id", "member_id", "face_row", "sample_id", "candidate", "approximation_level", "row_kind", "coefficients"):
            require(key in row, "evidence row missing {}".format(key))
        require(row["candidate"] in ("bfr", "far"), "unknown candidate label")
        require(row["row_kind"] in ROW_ORDER, "dropped or unknown derivative order")
        require(isinstance(row["coefficients"], list) and row["coefficients"], "missing coefficient row")
        for coefficient in row["coefficients"]:
            require(isinstance(coefficient, (int, float)) and math.isfinite(coefficient), "nonfinite coefficient")
        identity = tuple(row[key] for key in ("execution_case_id", "member_id", "face_row", "sample_id", "candidate", "approximation_level"))
        groups.setdefault(identity, []).append(row["row_kind"])
    for identity, kinds in groups.items():
        require(kinds == ROW_ORDER, "missing, duplicated, or reordered derivative row for {}".format(identity))

    regular = report.get("regular_analytic_gate")
    require(isinstance(regular, dict), "missing analytic regular gate")
    for candidate in ("bfr", "far"):
        value = regular.get(candidate)
        require(isinstance(value, dict), "missing regular gate candidate {}".format(candidate))
        require(value.get("canonical_parameter_map_checks") == 7,
                "regular canonical corner/center/edge map checks incomplete")
        require(value.get("rotated_patch_verified") is True and
                value.get("unrotated_patch_verified") is True,
                "regular rotated/unrotated sub-patch checks incomplete")
        require(value.get("all_six_rows") is True,
                "regular gate omitted derivative rows")
        require(value.get("area_integrand") is True and value.get("legacy_volume_integrand") is True,
                "regular gate omitted required integrand parity")
        require(value.get("max_error", math.inf) <= 5.0e-6,
                "regular analytic tolerance exceeded")

    convergence = report.get("internal_convergence")
    require(isinstance(convergence, dict), "missing independent-setting convergence")
    for candidate in ("bfr", "far"):
        value = convergence.get(candidate)
        require(isinstance(value, dict) and value.get("levels") == list(range(2, 9)),
                "{} convergence sweep missing or reordered".format(candidate))
        require(value.get("own_setting_only") is True and value.get("status") in ("PASS", "FAIL"),
                "{} convergence is confounded or nonterminal".format(candidate))
    require(report.get("approximation_knobs_commensurable") is False,
            "Bfr and Far approximation integers were treated as commensurable")

    certificates = report.get("oracle_certificates")
    require(isinstance(certificates, list) and certificates,
            "missing primary oracle certificates")
    for certificate in certificates:
        require(certificate.get("status") in ("COVERED", "ORACLE_UNCOVERED"),
                "invalid oracle coverage state")
        require(certificate.get("uniform_success_substituted_for_primary") is False,
                "uniform subdivision substituted for primary coverage")
        isolation = certificate.get("first_isolating_depth")
        require(isolation is None or (isinstance(isolation, int) and 0 <= isolation <= 12),
                "invalid isolation-depth evidence")
        if certificate["status"] == "COVERED":
            require(certificate.get("primary_method") == "stam_eigenanalysis",
                    "covered row does not use primary Stam eigenanalysis")
            require(certificate.get("precision_bits") == 544,
                    "primary certificate precision drift")
            require(certificate.get("interval_krawczyk_inclusion") is True,
                    "primary eigenbasis lacks interval Krawczyk inclusion")
            require(certificate.get("spectral_projector_certified") is True,
                    "primary repeated block lacks spectral projector certificate")
            depths = certificate.get("intersection_depths")
            require(isinstance(depths, list) and len(depths) == 5 and
                    depths == list(range(depths[0], depths[0] + 5)) and depths[-1] <= 30,
                    "primary row lacks five consecutive depth intersections")
            require(certificate.get("exact_binary64_midpoint_import") is True and
                    certificate.get("exact_binary64_candidate_import") is True,
                    "oracle coefficient imports are not exact binary64")
            require(certificate.get("uniform_cross_check") is True,
                    "covered primary row lacks independent uniform cross-check")
            require(certificate.get("uncertainty_coeff_le_tenth_target") is True and
                    certificate.get("uncertainty_geom_le_tenth_target") is True,
                    "oracle serialization uncertainty exceeds the frozen allowance")

    threading = report.get("threading")
    require(isinstance(threading, dict), "missing threading evidence")
    require(threading.get("tuple_count") == 588 and threading.get("rounds_per_tuple") == 20,
            "threading evidence is not the frozen 588 x 20 matrix")
    tuple_results = threading.get("tuple_results")
    require(isinstance(tuple_results, list), "missing threading tuple results")
    actual_threading = []
    for value in tuple_results:
        actual_threading.append((value.get("content_identity_key"), value.get("approxLevelSmooth"),
                                 value.get("mode"), value.get("worker_count")))
        require(value.get("rounds") == 20 and value.get("canonical_rows_identical") is True,
                "thread tuple lacks 20 deterministic rounds")
        if value.get("mode") == "cache_disabled":
            require(value.get("concurrent_factory_mode") == "cache_disabled",
                    "cache-disabled concurrency was not exercised")
    require(actual_threading == expected_threading_identities(manifest),
            "threading tuple coverage is incomplete, duplicated, or reordered")
    tsan = threading.get("tsan_profile")
    require(isinstance(tsan, dict) and tsan.get("proof_translation_units_instrumented") is True and
            tsan.get("opensubdiv_translation_units_instrumented") == 47 and
            tsan.get("findings") == 0 and tsan.get("matrix_complete") is True,
            "fully instrumented TSan evidence is incomplete")

    locality = report.get("flip_locality")
    require(isinstance(locality, list) and locality,
            "missing flip-locality evidence")
    for value in locality:
        require(value.get("reusable_faces") == value.get("comparable_faces") - value.get("changed_faces"),
                "flip locality reuse arithmetic is not reconstructible")
        require(value.get("phase2_projection_only") is True,
                "flip locality was promoted to a Phase-1 remeshing benefit")

    criteria = report.get("bfr_d9a_criteria")
    require(report.get("criterion_order") == BFR_CRITERIA and
            isinstance(criteria, dict) and set(criteria) == set(BFR_CRITERIA),
            "missing Bfr criterion identities or explicit order")
    allowed = {"PASS", "FAIL", "PENDING"}
    require(all(value in allowed for value in criteria.values()), "invalid Bfr criterion state")
    overall = report.get("bfr_verdict")
    require(overall in ("PASS", "FAIL", "PENDING"), "invalid Bfr verdict")
    if overall == "PASS":
        require(all(value == "PASS" for value in criteria.values()), "accidental success with incomplete/failing criterion")
        require(report.get("oracle_coverage_complete") is True, "accidental success without complete oracle coverage")
        require(report.get("threading_tsan_complete") is True, "accidental success without complete TSan coverage")
        require(all(value.get("status") == "COVERED" for value in certificates),
                "accidental success with oracle-uncovered evidence")
        require(all(value.get("status") == "PASS" for value in numeric_cases),
                "accidental success with a failed numeric case")
    require(report.get("d9a_decided") is False, "runner must not decide D9a")
    require(report.get("d9b_decided") is False, "runner must not decide D9b")
    return True


def full_dependency_audit(args):
    manifest = load_manifest()
    validate_manifest_contract(manifest)
    validate_frozen_approval_anchors()
    validate_source_separation()
    mpfr_root = require_root(args.mpfr_root, "MPFR_ROOT")
    gmp_build_root = require_root(args.gmp_build_root, "GMP_BUILD_ROOT")
    mpfr_build_root = require_root(args.mpfr_build_root, "MPFR_BUILD_ROOT")
    osd_root = require_root(args.opensubdiv_root, "OPENSUBDIV_ROOT")
    tsan_root = require_root(args.opensubdiv_tsan_root, "OPENSUBDIV_TSAN_ROOT")
    source_root = require_root(args.opensubdiv_source, "OPENSUBDIV_SOURCE")
    release_build_root = require_root(
        args.opensubdiv_release_build_root, "OPENSUBDIV_RELEASE_BUILD_ROOT")
    tsan_build_root = require_root(
        args.opensubdiv_tsan_build_root, "OPENSUBDIV_TSAN_BUILD_ROOT")
    build_install_roots = [mpfr_root, gmp_build_root, mpfr_build_root,
                           osd_root, tsan_root, release_build_root,
                           tsan_build_root]
    require(len(set(build_install_roots)) == len(build_install_roots),
            "dependency build and install roots must be pairwise disjoint")
    opensubdiv_contract = manifest["qualification_platform"]["build"]["opensubdiv"]
    provenance = {
        "mpfr": audit_mpfr(mpfr_root, gmp_build_root, mpfr_build_root),
        "dependency_source_archives": audit_dependency_archives(args),
        "build_tools": audit_build_tools(manifest),
        "opensubdiv_release": audit_opensubdiv(
            osd_root, release_build_root, source_root,
            opensubdiv_contract, "release"),
        "opensubdiv_tsan": audit_opensubdiv(
            tsan_root, tsan_build_root, source_root,
            opensubdiv_contract, "thread_sanitizer"),
        "source": audit_source_checkout(source_root, manifest),
    }
    require(args.proof_artifact_dir,
            "--proof-artifact-dir is required for persistent proof provenance")
    proof_artifact_root = pathlib.Path(args.proof_artifact_dir).resolve()
    proof_artifact_root.mkdir(parents=True, exist_ok=True)
    compiled = compile_proofs(
        proof_artifact_root, mpfr_root, osd_root, tsan_root,
        release_build_root, tsan_build_root)
    candidate_report = json.loads(run([compiled["candidate"], "--self-test"]).stdout)
    tsan_env = dict(os.environ)
    tsan_env["TSAN_OPTIONS"] = "halt_on_error=1"
    candidate_tsan_report = json.loads(run(
        [compiled["candidate_tsan"], "--self-test"], env=tsan_env).stdout)
    oracle_report = json.loads(run([compiled["oracle"], "--self-test"]).stdout)
    validate_compiled_report(candidate_report, "bfr_candidate_self_test")
    validate_compiled_report(candidate_tsan_report, "bfr_candidate_self_test")
    validate_compiled_report(oracle_report, "stam_oracle_self_test")
    preflights = execute_fixture_preflights(compiled["candidate"], manifest)
    provenance["fixture_preflights"] = preflights
    provenance["candidate_binary_sha256"] = sha256_file(compiled["candidate"])
    provenance["candidate_tsan_binary_sha256"] = sha256_file(compiled["candidate_tsan"])
    provenance["representation_binary_sha256"] = sha256_file(
        compiled["representation"])
    provenance["representation_tsan_binary_sha256"] = sha256_file(
        compiled["representation_tsan"])
    provenance["oracle_binary_sha256"] = sha256_file(compiled["oracle"])
    provenance["candidate_self_test"] = candidate_report
    provenance["candidate_tsan_self_test"] = candidate_tsan_report
    provenance["oracle_self_test"] = oracle_report
    provenance["proof_compile_commands"] = {
        "release_compile": compiled["release_profile"]["compile_commands"],
        "release_link": compiled["release_profile"]["link_commands"],
        "thread_sanitizer_compile":
            compiled["tsan_profile"]["compile_commands"],
        "thread_sanitizer_link": compiled["tsan_profile"]["link_commands"],
        "oracle": compiled["oracle_command"],
    }
    provenance["proof_command_manifests"] = {
        "release": str(compiled["release_profile"]["command_manifest"]),
        "thread_sanitizer":
            str(compiled["tsan_profile"]["command_manifest"]),
    }
    provenance["proof_audit_artifacts"] = compiled["audit_artifacts"]
    provenance["proof_binary_audit"] = compiled["binary_audit"]
    provenance["proof_artifact_root"] = str(proof_artifact_root)
    if args.run_release_matrix:
        require(args.release_checkpoint, "--release-checkpoint is required for full Release replay")
        release = execute_release_matrix(
            compiled["candidate"], manifest, artifact_dir=args.artifact_dir,
            checkpoint_path=args.release_checkpoint)
        platform_qualification = capture_platform_qualification(
            compiled["candidate"], manifest, release["numeric_cases"])
        observed_spread = measured_near_vertex_spread(release, manifest)
        checkpoint = pathlib.Path(args.release_checkpoint).resolve()
        checkpoint_hash = sha256_file(checkpoint)
        return terminal_failure_evidence(
            release, preflights, platform_qualification, observed_spread,
            checkpoint_path=str(checkpoint),
            checkpoint_sha256=checkpoint_hash, provenance=provenance,
            complete_case_artifacts=release["complete_case_artifacts"])
    return {
        "schema_version": 1,
        "kind": "bfr_qualification_dependency_audit",
        "status": "ok",
        "manifest_contract_sha256": MANIFEST_CONTRACT_SHA256,
        "provenance": provenance,
        "qualification_evidence": "pending_exact_head_candidate_and_numeric_replay",
        "bfr_verdict": "PENDING",
        "far_role": "regression_comparator_only",
        "d9a_decided": False,
        "d9b_decided": False,
    }


def finalize_release_checkpoint(args):
    manifest = load_manifest()
    validate_manifest_contract(manifest)
    validate_frozen_approval_anchors()
    validate_source_separation()
    candidate = pathlib.Path(args.candidate_binary).resolve() if args.candidate_binary else None
    require(candidate and candidate.is_file(), "--candidate-binary is required for negative preflight replay")
    preflights = execute_fixture_preflights(candidate, manifest)
    release = load_release_checkpoint(
        args.release_checkpoint, manifest, candidate, args.artifact_dir)
    platform_qualification = capture_platform_qualification(
        candidate, manifest, release["numeric_cases"])
    observed_spread = measured_near_vertex_spread(release, manifest)
    return terminal_failure_evidence(
        release, preflights, platform_qualification, observed_spread,
        checkpoint_path=release["path"],
        checkpoint_sha256=release["sha256"], provenance=None,
        complete_case_artifacts=release["complete_case_artifacts"])


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--require-proof-dependencies", action="store_true")
    parser.add_argument("--run-release-matrix", action="store_true")
    parser.add_argument("--finalize-release-checkpoint", action="store_true")
    parser.add_argument("--mpfr-root")
    parser.add_argument("--gmp-build-root")
    parser.add_argument("--mpfr-build-root")
    parser.add_argument("--opensubdiv-root")
    parser.add_argument("--opensubdiv-tsan-root")
    parser.add_argument("--opensubdiv-source")
    parser.add_argument("--opensubdiv-release-build-root")
    parser.add_argument("--opensubdiv-tsan-build-root")
    parser.add_argument("--gmp-archive")
    parser.add_argument("--mpfr-archive")
    parser.add_argument("--opensubdiv-archive")
    parser.add_argument("--proof-artifact-dir")
    parser.add_argument("--release-checkpoint")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--candidate-binary")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    mode_count = sum(bool(value) for value in (
        args.self_test, args.require_proof_dependencies,
        args.run_release_matrix, args.finalize_release_checkpoint))
    require(mode_count == 1, "select exactly one execution mode")
    require(not args.run_release_matrix or args.release_checkpoint,
            "--run-release-matrix requires --release-checkpoint")
    require(not args.run_release_matrix or args.artifact_dir,
            "--run-release-matrix requires --artifact-dir")
    require(not args.finalize_release_checkpoint or
            (args.release_checkpoint and args.candidate_binary and args.artifact_dir),
            "checkpoint finalization requires --release-checkpoint, --candidate-binary, and --artifact-dir")
    if args.require_proof_dependencies or args.run_release_matrix:
        required = {
            "--mpfr-root": args.mpfr_root,
            "--gmp-build-root": args.gmp_build_root,
            "--mpfr-build-root": args.mpfr_build_root,
            "--opensubdiv-root": args.opensubdiv_root,
            "--opensubdiv-tsan-root": args.opensubdiv_tsan_root,
            "--opensubdiv-source": args.opensubdiv_source,
            "--opensubdiv-release-build-root": args.opensubdiv_release_build_root,
            "--opensubdiv-tsan-build-root": args.opensubdiv_tsan_build_root,
            "--gmp-archive": args.gmp_archive,
            "--mpfr-archive": args.mpfr_archive,
            "--opensubdiv-archive": args.opensubdiv_archive,
            "--proof-artifact-dir": args.proof_artifact_dir,
        }
        require(all(required.values()),
                "dependency audit requires {}".format(
                    ", ".join(key for key, value in required.items() if not value)))
    return args


def main(argv=None):
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        if args.require_proof_dependencies or args.run_release_matrix:
            report = full_dependency_audit(args)
        elif args.finalize_release_checkpoint:
            report = finalize_release_checkpoint(args)
        else:
            report = cheap_self_test()
        if report.get("kind") == "bfr_qualification_evidence":
            validate_evidence_document(report)
        rendered = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if report.get("kind") == "bfr_qualification_evidence":
            validate_evidence_document(json.loads(rendered))
        if args.output:
            pathlib.Path(args.output).write_text(rendered, encoding="utf-8")
        if args.json or not args.output:
            sys.stdout.write(rendered)
        return 0
    except (QualificationError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        failure = {"schema_version": 1, "kind": "bfr_qualification_runner", "status": "failed", "errors": [str(error)], "bfr_verdict": "PENDING", "d9a_decided": False}
        sys.stdout.write(json.dumps(failure, sort_keys=True, indent=2) + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
