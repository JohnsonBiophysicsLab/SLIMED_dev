#!/usr/bin/env python3
"""Inventory the proof-only valence-5 OpenSubdiv force diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PRODUCTION = Path("experiments/irregular_valence5_fixture_parity.cpp")
HARNESS = Path("experiments/irregular_valence5_opensubdiv_force_parity.cpp")
PROBE = Path("scripts/probe_opensubdiv_feasibility.py")
RUNNER = Path("scripts/run_irregular_valence5_opensubdiv_force_parity.py")
WRAPPER = Path("scripts/run_irregular_valence5_opensubdiv_force_parity.sh")
DOC = Path("docs/irregular_valence5_opensubdiv_force_parity.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
FIXTURE_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_fixture_coverage.py"
)

ANCHORS = {
    PRODUCTION: (
        "production_irregular_force_path_executed",
        "element_energy_force_irregular_11",
        "perFaceSourceForces",
        "forceFormulaParameters",
    ),
    HARNESS: (
        "element_energy_force_regular",
        "kFaceCount = 20",
        "kSampleCount = 3",
        "kRowCount = 7",
        "kSourceCount = 12",
        "production_scatter_executed",
        "opensubdiv_rows_evaluated_by_existing_force_algebra",
        "per_face_source_forces",
    ),
    PROBE: (
        '\\"samples\\":[',
        '\\"rows\\":[',
        "kSourceCount = 12",
        "kSampleCount = 3",
        "kRowCount = 7",
    ),
    RUNNER: (
        "20 * 12 * 9",
        "max_abs_force_difference_by_kind",
        "max_abs_force_difference_location",
        "direct whole-Ptex OpenSubdiv rows do not match",
        "production_scatter_executed",
        "resolve the measured valence-5 force parity residuals",
    ),
    WRAPPER: (
        "run_irregular_valence5_opensubdiv_force_parity.py",
        '"$@"',
    ),
    DOC: (
        "per-face source-keyed `fBend`, `fArea`, and `fVolume`",
        "`20 x 3 x 7 x 12`",
        "`fBend`: `7.108303140663388`",
        "`fArea`: `0.46106761515265404`",
        "`fVolume`: `0.062309089012307695`",
        "`production_scatter_executed:false`",
        "proof-only integration-domain/composition",
    ),
    READINESS: (
        "whole-Ptex OpenSubdiv evaluation does not match",
        "Maximum per-face source-component differences",
        "valence-5 routing",
    ),
    FIXTURE_INVENTORY: (
        '"next_gate": "valence-5 integration-domain/composition diagnostic"',
    ),
}

FORBIDDEN_STALE_CLAIMS = {
    READINESS: (
        "The next reviewed step is actual valence-5",
    ),
    FIXTURE_INVENTORY: (
        '"next_gate": "actual valence-5 fBend/fArea/fVolume parity"',
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for relative, needles in ANCHORS.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative} missing {needle!r}")

    forbidden_located = 0
    forbidden_expected = 0
    for relative, needles in FORBIDDEN_STALE_CLAIMS.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            forbidden_expected += 1
            if needle in source:
                forbidden_located += 1
                errors.append(f"{relative} contains stale claim {needle!r}")

    return {
        "status": "passed" if not errors else "failed",
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_scatter_executed": False,
        "force_parity_passed": False,
        "next_gate": "valence-5 integration-domain/composition diagnostic",
        "anchors": {"located": located, "expected": expected},
        "forbidden_stale_claims": {
            "located": forbidden_located,
            "expected": forbidden_expected,
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = collect(repo_root())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(
            f"anchors: {report['anchors']['located']}/"
            f"{report['anchors']['expected']}"
        )
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
