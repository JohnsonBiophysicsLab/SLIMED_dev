#!/usr/bin/env python3
"""Deterministically update or check the B2c executable report contract."""

from __future__ import print_function

import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "scripts/anchored_row_qualification_report_v1.schema.json"
MUTATION_MANIFEST_PATH = (
    ROOT / "scripts/anchored_row_contract_mutations_v1.txt")
RUNNER_PATH = ROOT / "scripts/run_anchored_row_qualification.py"
BASE_SCHEMA_COMMIT = "b48acbf49ae361ee8f1bd3593800a6993ad82fcf"
BASE_SCHEMA_SHA256 = (
    "3ab27d5b58f6e9c0108c24bfb4357b9396c004d97ab5e3fa66fdd8d06e706933")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_bytes():
    runner = load_module("anchored_row_qualification_schema_update", RUNNER_PATH)
    raw = subprocess.check_output(
        ["git", "show", "{}:{}".format(
            BASE_SCHEMA_COMMIT,
            SCHEMA_PATH.relative_to(ROOT).as_posix())], cwd=str(ROOT))
    if hashlib.sha256(raw).hexdigest() != BASE_SCHEMA_SHA256:
        raise RuntimeError("independent base-schema digest mismatch")
    raw_schema = json.loads(raw.decode("utf-8"))
    authority_values = runner.frozen_authority_record()
    schema = runner.RESULT_CONTRACT.install_report_schema_contract(
        raw_schema, authority_values)
    schema["$defs"]["identity"]["properties"][
        "approved_b2b_merge_git_commit"] = {
            "const": runner.APPROVED_RESULT_EVIDENCE_AMENDMENT_MERGE}
    schema["$defs"]["identity"]["properties"]["implementation_state"] = {
        "const": "PACKAGE2_EXECUTED_PROOF_ONLY_NO_QUALIFICATION_DECISION"}
    return (json.dumps(schema, indent=2, sort_keys=True,
                       ensure_ascii=False) + "\n").encode("utf-8")


def expected_mutation_manifest_bytes():
    runner = load_module("anchored_row_qualification_mutation_update",
                         RUNNER_PATH)
    entries = runner.RESULT_CONTRACT.expand_mutation_manifest(
        runner.documentation_owned_schema_path_anchor())
    return ("\n".join(entries) + "\n").encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    action.add_argument("--write-mutation-manifest", action="store_true")
    args = parser.parse_args(argv)
    expected = expected_bytes()
    expected_manifest = expected_mutation_manifest_bytes()
    if args.check:
        if SCHEMA_PATH.read_bytes() != expected:
            print("anchored-row report schema is not generated exactly",
                  file=sys.stderr)
            return 1
        if MUTATION_MANIFEST_PATH.read_bytes() != expected_manifest:
            print("anchored-row mutation manifest is not generated exactly",
                  file=sys.stderr)
            return 1
        return 0
    if args.write_mutation_manifest:
        MUTATION_MANIFEST_PATH.write_bytes(expected_manifest)
        return 0
    SCHEMA_PATH.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
