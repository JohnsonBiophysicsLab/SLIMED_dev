#!/usr/bin/env python3
"""Fail-closed B2 Bfr qualification runner.

The cheap ``--self-test`` path validates only frozen, pre-result inputs.  The
``--require-proof-dependencies`` path additionally audits and executes the two
compiled proof programs.  It never downloads or discovers dependencies.
"""

from __future__ import print_function

import argparse
import gzip
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile


REPO = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json"
MANIFEST_FILE_SHA256 = "bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b"
MANIFEST_CONTRACT_SHA256 = "30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368"
OPENSUBDIV_COMMIT = "9dab8a47bfbb1388ec8388fe61f5f916e6123f38"
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


def require(condition, message):
    if not condition:
        raise QualificationError(message)


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
        observed = json.loads(completed.stdout)
    except (ValueError, json.JSONDecodeError):
        return failure
    if not isinstance(observed, dict):
        return failure
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
    oracle = proof_dir / "stam_oracle.cpp"
    interval = proof_dir / "mpfr_interval.hpp"
    for path in (candidate, oracle, interval):
        require(path.is_file(), "missing proof source {}".format(path.relative_to(REPO)))
    oracle_text = oracle.read_text(encoding="utf-8") + interval.read_text(encoding="utf-8")
    for token in FORBIDDEN_ORACLE_TOKENS:
        require(token not in oracle_text, "oracle source contains forbidden dependency token {}".format(token))
    require("MPFR_RNDD" in oracle_text and "MPFR_RNDU" in oracle_text, "directed interval rounding is absent")
    require("mpfr_init2" in oracle_text and "544" in oracle_text, "544-bit MPFR endpoints are absent")
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


def audit_opensubdiv(opensubdiv_root, source_root, expected_members, profile_name):
    header = opensubdiv_root / "include/opensubdiv/version.h"
    archive = opensubdiv_root / "lib/libosdCPU.a"
    require(header.is_file() and archive.is_file(), "{} OpenSubdiv install incomplete".format(profile_name))
    require(contained(header, opensubdiv_root) and contained(archive, opensubdiv_root), "OpenSubdiv dependency escaped declared root")
    header_text = header.read_text(encoding="utf-8", errors="replace")
    require("OPENSUBDIV_VERSION_NUMBER 30700" in header_text, "OpenSubdiv version is not exactly 3.7.0")
    raw_members = run(["/usr/bin/ar", "-t", archive]).stdout.splitlines()
    require(raw_members == expected_members, "{} archive member order/scope drift".format(profile_name))
    return {"archive": str(archive), "sha256": sha256_file(archive), "size": archive.stat().st_size, "members": raw_members}


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


def audit_mpfr(mpfr_root):
    header = mpfr_root / "include/mpfr.h"
    libraries = list((mpfr_root / "lib").glob("libmpfr.*"))
    require(header.is_file() and libraries, "MPFR root is incomplete")
    text = header.read_text(encoding="utf-8", errors="replace")
    require(re.search(r"#define\s+MPFR_VERSION_STRING\s+\"4\.2\.2\"", text), "MPFR compile-time version is not 4.2.2")
    library = sorted(libraries, key=lambda p: (p.suffix != ".dylib", p.name))[0]
    require(contained(library, mpfr_root), "MPFR library escaped declared root")
    return {"header": str(header), "library": str(library), "sha256": sha256_file(library)}


def compile_proofs(build_dir, mpfr_root, opensubdiv_root, tsan_root):
    compiler = pathlib.Path("/Library/Developer/CommandLineTools/usr/bin/clang++")
    require(compiler.is_file(), "pinned Apple clang++ is unavailable")
    common = [str(compiler), "-std=c++17", "-O3", "-DNDEBUG", "-fno-fast-math", "-ffp-contract=off", "-fno-omit-frame-pointer", "-isysroot", "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk", "-mmacosx-version-min=26.0", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
    candidate = build_dir / "bfr_candidate"
    candidate_tsan = build_dir / "bfr_candidate_tsan"
    oracle = build_dir / "stam_oracle"
    candidate_cmd = common + ["-MMD", "-MF", str(build_dir / "candidate.d"), "-I" + str(opensubdiv_root / "include"), str(REPO / "experiments/bfr_qualification/candidate.cpp"), str(opensubdiv_root / "lib/libosdCPU.a"), "-framework", "IOKit", "-framework", "Foundation", "-Wl,-map," + str(build_dir / "candidate.map"), "-o", str(candidate)]
    oracle_cmd = common + ["-MMD", "-MF", str(build_dir / "oracle.d"), "-I" + str(mpfr_root / "include"), str(REPO / "experiments/bfr_qualification/stam_oracle.cpp"), "-L" + str(mpfr_root / "lib"), "-Wl,-rpath," + str(mpfr_root / "lib"), "-lmpfr", "-lgmp", "-Wl,-map," + str(build_dir / "oracle.map"), "-o", str(oracle)]
    tsan_common = [str(compiler), "-std=c++17", "-O1", "-g", "-DNDEBUG", "-fno-fast-math", "-ffp-contract=off", "-fno-omit-frame-pointer", "-isysroot", "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk", "-mmacosx-version-min=26.0", "-fsanitize=thread", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
    candidate_tsan_cmd = tsan_common + ["-MMD", "-MF", str(build_dir / "candidate_tsan.d"), "-I" + str(tsan_root / "include"), str(REPO / "experiments/bfr_qualification/candidate.cpp"), "-fsanitize=thread", str(tsan_root / "lib/libosdCPU.a"), "-framework", "IOKit", "-framework", "Foundation", "-Wl,-map," + str(build_dir / "candidate_tsan.map"), "-o", str(candidate_tsan)]
    run(candidate_cmd)
    run(oracle_cmd)
    run(candidate_tsan_cmd)
    for artifact in (build_dir / "candidate.d", build_dir / "candidate.map",
                     build_dir / "candidate_tsan.d", build_dir / "candidate_tsan.map",
                     build_dir / "oracle.d", build_dir / "oracle.map"):
        require(artifact.is_file() and artifact.stat().st_size > 0,
                "missing proof compiler/link audit artifact {}".format(artifact.name))
    oracle_dependencies = (build_dir / "oracle.d").read_text(encoding="utf-8", errors="replace")
    for token in FORBIDDEN_ORACLE_TOKENS:
        require(token not in oracle_dependencies,
                "oracle dependency file contains forbidden token {}".format(token))
    for binary in (candidate, candidate_tsan, oracle):
        run(["/usr/bin/otool", "-L", binary])
        run(["/usr/bin/nm", "-u", binary])
    oracle_symbols = run(["/usr/bin/nm", "-u", oracle]).stdout
    for token in FORBIDDEN_ORACLE_TOKENS:
        require(token not in oracle_symbols, "oracle binary contains forbidden symbol token {}".format(token))
    oracle_links = run(["/usr/bin/otool", "-L", oracle]).stdout
    require("osd" not in oracle_links.lower(), "oracle linked OpenSubdiv")
    return {"candidate": candidate, "candidate_tsan": candidate_tsan,
            "oracle": oracle, "candidate_command": candidate_cmd,
            "candidate_tsan_command": candidate_tsan_cmd,
            "oracle_command": oracle_cmd,
            "audit_artifacts": {artifact.name: sha256_file(artifact) for artifact in (
                build_dir / "candidate.d", build_dir / "candidate.map",
                build_dir / "candidate_tsan.d", build_dir / "candidate_tsan.map",
                build_dir / "oracle.d", build_dir / "oracle.map")}}


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
    identity_group = manifest["byte_identity_groups"][0]
    left = REPO / identity_group["members"][0]
    right = REPO / identity_group["members"][1]
    for filename in identity_group["required_equal_files"]:
        require((left / filename).read_bytes() == (right / filename).read_bytes(),
                "frozen byte-identity group drift: {}".format(filename))
    return {"valid": valid, "negative": negative, "deterministic_reruns_equal": True}


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


def canonical_candidate_rows_digest(case_report):
    digest = hashlib.sha256()
    rows = case_report.get("rows")
    require(isinstance(rows, list) and len(rows) == case_report.get("row_group_count") * 6,
            "candidate case row count is incomplete")
    for index, row in enumerate(rows):
        expected_kind = ROW_ORDER[index % 6]
        require(row.get("row_kind") == expected_kind,
                "candidate row order drift")
        require(row.get("weight_bits_hex") == "3ff0000000000000",
                "candidate sample sentinel bits drift")
        source_ids = row.get("source_ids")
        coefficients = row.get("coefficients")
        require(isinstance(source_ids, list) and isinstance(coefficients, list) and
                len(source_ids) == len(coefficients) and source_ids == sorted(set(source_ids)),
                "candidate row source reconstruction is malformed")
        require(all(isinstance(value, int) and 0 <= value <= 2147483647 for value in source_ids),
                "candidate source ID is outside int32")
        require(all(isinstance(value, (int, float)) and math.isfinite(value) for value in coefficients),
                "candidate row coefficient is nonfinite")
        sample_id = row.get("sample_id")
        require(isinstance(sample_id, str), "candidate sample ID missing")
        encoded_sample = sample_id.encode("utf-8")
        digest.update(b"B2ROWV1")
        digest.update(struct.pack("<i", row.get("face_row")))
        digest.update(struct.pack("<I", len(encoded_sample)))
        digest.update(encoded_sample)
        digest.update(struct.pack("<I", index % 6))
        digest.update(struct.pack("<I", len(source_ids)))
        for source_id, coefficient in zip(source_ids, coefficients):
            digest.update(struct.pack("<i", source_id))
            digest.update(struct.pack("<d", coefficient))
    return digest.hexdigest()


def expected_group_count(mesh_path):
    faces = []
    with (pathlib.Path(mesh_path) / "faces.csv").open("r", encoding="utf-8") as stream:
        for line in stream:
            face = [int(value) for value in line.strip().split(",")]
            require(len(face) == 3, "fixture face ceased to be triangular")
            faces.append(face)
    vertex_count = sum(1 for _ in (pathlib.Path(mesh_path) / "vertices.csv").open("r", encoding="utf-8"))
    neighbors = [set() for _ in range(vertex_count)]
    for face in faces:
        for corner in range(3):
            a, b = face[corner], face[(corner + 1) % 3]
            neighbors[a].add(b)
            neighbors[b].add(a)
    return sum(10 + 24 * sum(len(neighbors[vertex]) != 6 for vertex in face) for face in faces)


def validate_candidate_case(case_report, identity, candidate, level, mode, mesh_path):
    validate_compiled_report(case_report, "bfr_candidate_case")
    require((case_report.get("content_identity_key"), case_report.get("candidate"),
             case_report.get("approximation_level"), case_report.get("applicable_mode")) ==
            (identity, candidate, level, mode), "candidate case identity drift")
    require(case_report.get("warmup_count") == 3, "candidate case warmup count drift")
    timings = case_report.get("preparation_ns")
    require(isinstance(timings, list) and len(timings) == 15 and
            all(isinstance(value, int) and value >= 0 for value in timings),
            "candidate case lacks 15 integer-nanosecond measurements")
    require(case_report.get("preparation_median_ns") == sorted(timings)[7],
            "candidate case median drift")
    require(case_report.get("row_group_count") == expected_group_count(mesh_path),
            "candidate case sample/face/corner execution coverage drift")
    require(case_report.get("row_kind_counts") ==
            {kind: case_report["row_group_count"] for kind in ROW_ORDER},
            "candidate case six-row coverage drift")
    require(case_report.get("source_reconstruction_complete") is True,
            "candidate source reconstruction failed")
    require(isinstance(case_report.get("max_row_sum_error"), (int, float)) and
            math.isfinite(case_report["max_row_sum_error"]),
            "candidate row invariant metric is nonfinite")
    row_digest = canonical_candidate_rows_digest(case_report)
    d12_pass = (case_report["preparation_median_ns"] <= 1000000000 and
                max(timings) <= 10000000000 and
                case_report.get("retained_payload_bytes_per_face", 2 ** 63) <= 131072 and
                case_report.get("peak_rss_delta_bytes", 2 ** 63) <= 64 * 1048576 and
                case_report.get("rss_named_samples_complete") is True)
    return row_digest, d12_pass, case_report["max_row_sum_error"] <= 1.0e-12


def d12_observation_within_budgets(value):
    timings = value.get("preparation_ns", [])
    return (len(timings) == 15 and
            value.get("preparation_median_ns", 1000000001) <= 1000000000 and
            max(timings) <= 10000000000 and
            value.get("retained_payload_bytes_per_face", 131073) <= 131072 and
            value.get("peak_rss_delta_bytes", 64 * 1048576 + 1) <= 64 * 1048576)


def execute_release_matrix(candidate_binary, manifest, artifact_dir=None,
                           progress_callback=None, checkpoint_path=None):
    artifact_root = pathlib.Path(artifact_dir).resolve() if artifact_dir else None
    if artifact_root:
        artifact_root.mkdir(parents=True, exist_ok=True)
    checkpoint = pathlib.Path(checkpoint_path).resolve() if checkpoint_path else None
    summaries = []
    expected_identities = expected_numeric_case_identities(manifest)
    if checkpoint and checkpoint.is_file():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        require(saved.get("kind") == "bfr_release_matrix_checkpoint",
                "Release checkpoint kind drift")
        summaries = saved.get("numeric_cases", [])
        actual_prefix = [(item.get("content_identity_key"), item.get("candidate"),
                          item.get("approximation_level"), item.get("applicable_mode"))
                         for item in summaries]
        require(actual_prefix == expected_identities[:len(actual_prefix)],
                "Release checkpoint identity prefix drift")
        if artifact_root:
            for item in summaries:
                artifact = item.get("complete_json_artifact")
                artifact_sha256 = item.get("complete_json_artifact_sha256")
                require(isinstance(artifact, str) and artifact and
                        pathlib.Path(artifact).name == artifact,
                        "Release checkpoint artifact name is missing or unsafe")
                artifact_path = artifact_root / artifact
                require(artifact_path.is_file() and
                        sha256_file(artifact_path) == artifact_sha256,
                        "Release checkpoint artifact is missing or changed")
    jobs_by_identity = {job["content_identity_key"]: job for job in valid_content_jobs(manifest)}
    for identity, candidate, level, mode in expected_identities[len(summaries):]:
        job = jobs_by_identity[identity]
        command = [candidate_binary, "--execute-case", job["mesh_path"], job["mutation"],
                   candidate, str(level), mode, identity]
        primary_before = candidate_platform_probe(candidate_binary)
        first = run(command, timeout=30)
        primary_after = candidate_platform_probe(candidate_binary)
        first_report = json.loads(first.stdout)
        first_digest, d12_pass, invariant_pass = validate_candidate_case(
            first_report, identity, candidate, level, mode, job["mesh_path"])
        determinism_before = candidate_platform_probe(candidate_binary)
        second = run(command, timeout=30)
        determinism_after = candidate_platform_probe(candidate_binary)
        second_report = json.loads(second.stdout)
        second_digest, second_d12_pass, second_invariant_pass = validate_candidate_case(
            second_report, identity, candidate, level, mode, job["mesh_path"])
        require(first_digest == second_digest,
                "candidate deterministic row rerun mismatch for {}".format((identity, candidate, level, mode)))
        require(invariant_pass == second_invariant_pass,
                "candidate row-invariant state changed across deterministic rerun")
        artifact = None
        if artifact_root:
            artifact = "{}-{}-{}-{}.json.gz".format(identity, candidate, level, mode)
            artifact_path = artifact_root / artifact
            with artifact_path.open("wb") as raw_stream:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_stream, mtime=0) as stream:
                    stream.write(first.stdout.encode("utf-8"))
            artifact_sha256 = sha256_file(artifact_path)
        else:
            artifact_sha256 = None
        summaries.append({
            "content_identity_key": identity, "candidate": candidate,
            "approximation_level": level, "applicable_mode": mode,
            "status": "PASS" if invariant_pass else "FAIL",
            "failure_reasons": ["row_sum_invariant"] if not invariant_pass else [],
            "d12_budget_observation": "WITHIN_BUDGETS" if d12_pass else "EXCEEDS_BUDGETS",
            "row_group_count": first_report["row_group_count"],
            "row_kind_counts": first_report["row_kind_counts"],
            "source_reconstruction_complete": True,
            "max_row_sum_error": first_report["max_row_sum_error"],
            "warmup_count": 3, "preparation_ns": first_report["preparation_ns"],
            "preparation_median_ns": first_report["preparation_median_ns"],
            "retained_payload_bytes_per_face": first_report["retained_payload_bytes_per_face"],
            "peak_rss_delta_bytes": first_report["peak_rss_delta_bytes"],
            "rss_named_samples_complete": first_report["rss_named_samples_complete"],
            "canonical_rows_sha256": first_digest, "deterministic_rerun_equal": True,
            "complete_json_artifact": artifact,
            "complete_json_artifact_sha256": artifact_sha256,
            "platform_boundary_samples": [
                {"boundary": "primary_before", "probe": primary_before},
                {"boundary": "primary_after", "probe": primary_after},
                {"boundary": "determinism_before", "probe": determinism_before},
                {"boundary": "determinism_after", "probe": determinism_after},
            ],
        })
        if progress_callback:
            progress_callback(len(summaries), 294, summaries[-1])
        if checkpoint:
            checkpoint_payload = {"schema_version": 1,
                                  "kind": "bfr_release_matrix_checkpoint",
                                  "complete": len(summaries) == 294,
                                  "numeric_cases": summaries}
            temporary = checkpoint.with_name(checkpoint.name + ".tmp")
            temporary.write_text(json.dumps(checkpoint_payload, sort_keys=True,
                                             separators=(",", ":")) + "\n",
                                 encoding="utf-8")
            os.replace(str(temporary), str(checkpoint))
    require(len(summaries) == 294, "Release matrix did not execute exactly 294 cases")
    if artifact_root:
        require(all(isinstance(item.get("complete_json_artifact_sha256"), str) and
                    len(item["complete_json_artifact_sha256"]) == 64
                    for item in summaries),
                "Release matrix case-artifact set is incomplete")
    return {"case_count": 294, "numeric_cases": summaries,
            "deterministic_reruns_equal": True,
            "complete_case_artifacts": bool(artifact_root),
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


def load_release_checkpoint(path_text, manifest):
    checkpoint = require_root(str(pathlib.Path(path_text).resolve().parent),
                              "release checkpoint parent") / pathlib.Path(path_text).name
    require(checkpoint.is_file(), "release checkpoint is unavailable")
    raw = checkpoint.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    require(value.get("kind") == "bfr_release_matrix_checkpoint" and
            value.get("complete") is True, "Release checkpoint is not complete")
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
    return {"path": str(checkpoint), "sha256": sha256_bytes(raw),
            "case_count": 294, "numeric_cases": cases,
            "deterministic_reruns_equal": True,
            "all_d12_budgets_pass": all(d12_observation_within_budgets(item)
                                         for item in cases),
            "all_row_invariants_pass": all("row_sum_invariant" not in item.get("failure_reasons", [])
                                             for item in cases)}


def terminal_failure_evidence(release, preflights, platform_qualification,
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
        "far_promotion_declined": True, "approximation_knobs_commensurable": False,
        "execution": {"canonical_case_order": CANONICAL_CASE_ORDER,
                      "deterministic_reruns_equal": True,
                      "negative_cases": preflights["negative"],
                      "numeric_cases": cases,
                      "complete_case_artifacts": complete_case_artifacts},
        "release_checkpoint": {"path": checkpoint_path, "sha256": checkpoint_sha256,
                               "complete": True, "case_count": 294},
        "row_invariant_failure": {
            "criterion": "position sum one and derivative sums zero within 1.0e-12",
            "tolerance": 1.0e-12, "tolerance_changed": False,
            "bfr_failure_count": 124, "bfr_failure_count_by_level": bfr_by_level,
            "bfr_max_error": bfr_maximum,
            "example": {"content_identity_key": "closed_valence3_tetrahedron",
                        "candidate": "bfr", "approximation_level": 4,
                        "modes": ["cache_disabled", "SurfaceFactoryCache_serial"],
                        "row_kind": "dvv", "face_row": 0, "local_corner": 1,
                        "sample_id": "trend-r08-ray01",
                        "sum": 1.4781509349859334e-12,
                        "absolute_error": 1.4781509349859334e-12,
                        "cache_modes_equal": True},
            "far_comparator_failure_count": 62,
            "far_failure_count_by_level": far_by_level,
            "far_max_error": far_maximum,
        },
        "d12_summary": d12,
        "platform_qualification": platform_qualification,
        "canonical_determinism": {"status": "PASS", "case_count": 294,
                                  "two_pass_rows_equal": True},
        "negative_preflight": {"status": "PASS", "case_count": 3,
                               "failure_before_output": True},
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

    numeric_cases = execution.get("numeric_cases")
    require(isinstance(numeric_cases, list), "missing numeric case results")
    actual_numeric = []
    for value in numeric_cases:
        identity = (value.get("content_identity_key"), value.get("candidate"),
                    value.get("approximation_level"), value.get("applicable_mode"))
        actual_numeric.append(identity)
        require(value.get("status") in ("PASS", "FAIL"),
                "numeric case has no terminal evidence status")
        require(value.get("row_group_count", 0) > 0,
                "numeric case contains no executed row groups")
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
                    len(value["complete_json_artifact_sha256"]) == 64
                    for value in numeric_cases),
                "complete case-artifact claim lacks names or SHA-256 identities")

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
        require(isinstance(example, dict) and example.get("row_kind") == "dvv" and
                example.get("sample_id") == "trend-r08-ray01" and
                example.get("absolute_error") == 1.4781509349859334e-12 and
                example.get("cache_modes_equal") is True,
                "terminal row-invariant example drift")
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
                {"status": "PASS", "case_count": 3, "failure_before_output": True},
                "terminal evidence lacks negative-preflight PASS")
        criteria = report.get("bfr_d9a_criteria")
        require(isinstance(criteria, dict) and list(criteria) == BFR_CRITERIA,
                "terminal criterion order drift")
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
    require(isinstance(criteria, dict) and list(criteria) == BFR_CRITERIA,
            "missing or reordered Bfr criterion verdicts")
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
    osd_root = require_root(args.opensubdiv_root, "OPENSUBDIV_ROOT")
    tsan_root = require_root(args.opensubdiv_tsan_root, "OPENSUBDIV_TSAN_ROOT")
    source_root = require_root(args.opensubdiv_source, "OPENSUBDIV_SOURCE")
    require(osd_root != tsan_root, "Release and TSan install roots must be disjoint")
    expected_members = manifest["qualification_platform"]["build"]["opensubdiv"]["expected_raw_ar_t_members_in_order"]
    provenance = {
        "mpfr": audit_mpfr(mpfr_root),
        "opensubdiv_release": audit_opensubdiv(osd_root, source_root, expected_members, "release"),
        "opensubdiv_tsan": audit_opensubdiv(tsan_root, source_root, expected_members, "thread_sanitizer"),
        "source": audit_source_checkout(source_root, manifest),
    }
    with tempfile.TemporaryDirectory(prefix="bfr-qualification-build-") as temporary:
        compiled = compile_proofs(pathlib.Path(temporary), mpfr_root, osd_root, tsan_root)
        candidate_report = json.loads(run([compiled["candidate"], "--self-test"]).stdout)
        tsan_env = dict(os.environ)
        tsan_env["TSAN_OPTIONS"] = "halt_on_error=1"
        candidate_tsan_report = json.loads(run(
            [compiled["candidate_tsan"], "--self-test"], env=tsan_env).stdout)
        oracle_report = json.loads(run([compiled["oracle"], "--self-test"]).stdout)
        validate_compiled_report(candidate_report, "bfr_candidate_self_test")
        validate_compiled_report(candidate_tsan_report, "bfr_candidate_self_test")
        validate_compiled_report(oracle_report, "stam_oracle_self_test")
        preflights = execute_fixture_preflights(
            compiled["candidate"], manifest)
        provenance["fixture_preflights"] = preflights
        provenance["candidate_binary_sha256"] = sha256_file(compiled["candidate"])
        provenance["candidate_tsan_binary_sha256"] = sha256_file(compiled["candidate_tsan"])
        provenance["oracle_binary_sha256"] = sha256_file(compiled["oracle"])
        provenance["candidate_self_test"] = candidate_report
        provenance["candidate_tsan_self_test"] = candidate_tsan_report
        provenance["oracle_self_test"] = oracle_report
        provenance["proof_compile_commands"] = {
            "release_candidate": compiled["candidate_command"],
            "thread_sanitizer_candidate": compiled["candidate_tsan_command"],
            "oracle": compiled["oracle_command"],
        }
        provenance["proof_audit_artifacts"] = compiled["audit_artifacts"]
        if args.run_release_matrix:
            require(args.release_checkpoint, "--release-checkpoint is required for full Release replay")
            release = execute_release_matrix(
                compiled["candidate"], manifest, artifact_dir=args.artifact_dir,
                checkpoint_path=args.release_checkpoint)
            platform_qualification = capture_platform_qualification(
                compiled["candidate"], manifest, release["numeric_cases"])
            checkpoint = pathlib.Path(args.release_checkpoint).resolve()
            checkpoint_hash = sha256_file(checkpoint)
            return terminal_failure_evidence(
                release, preflights, platform_qualification,
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
    release = load_release_checkpoint(args.release_checkpoint, manifest)
    platform_qualification = capture_platform_qualification(
        candidate, manifest, release["numeric_cases"])
    return terminal_failure_evidence(
        release, preflights, platform_qualification,
        checkpoint_path=release["path"],
        checkpoint_sha256=release["sha256"], provenance=None,
        complete_case_artifacts=False)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--require-proof-dependencies", action="store_true")
    parser.add_argument("--run-release-matrix", action="store_true")
    parser.add_argument("--finalize-release-checkpoint", action="store_true")
    parser.add_argument("--mpfr-root")
    parser.add_argument("--opensubdiv-root")
    parser.add_argument("--opensubdiv-tsan-root")
    parser.add_argument("--opensubdiv-source")
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
    require(not args.finalize_release_checkpoint or
            (args.release_checkpoint and args.candidate_binary),
            "checkpoint finalization requires --release-checkpoint and --candidate-binary")
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
