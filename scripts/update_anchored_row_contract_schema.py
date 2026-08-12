#!/usr/bin/env python3
"""Deterministically update or check the B2c executable report contract."""

from __future__ import print_function

import argparse
import importlib.util
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "scripts/anchored_row_qualification_report_v1.schema.json"
RUNNER_PATH = ROOT / "scripts/run_anchored_row_qualification.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_bytes():
    runner = load_module("anchored_row_qualification_schema_update", RUNNER_PATH)
    raw_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    authority_values = runner.frozen_authority_record()
    schema = runner.RESULT_CONTRACT.install_report_schema_contract(
        raw_schema, authority_values)
    return (json.dumps(schema, indent=2, sort_keys=True,
                       ensure_ascii=False) + "\n").encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    expected = expected_bytes()
    if args.check:
        if SCHEMA_PATH.read_bytes() != expected:
            print("anchored-row report schema is not generated exactly",
                  file=sys.stderr)
            return 1
        return 0
    SCHEMA_PATH.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
