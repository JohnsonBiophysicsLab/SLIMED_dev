#!/usr/bin/env python3
"""Inventory the proof-only valence-5 source-order/transpose lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROBE = Path("scripts/probe_opensubdiv_feasibility.py")
WRAPPER = Path(
    "scripts/run_irregular_valence5_opensubdiv_source_order_transpose.sh"
)
COMPARATOR = Path(
    "scripts/compare_irregular_valence5_opensubdiv_source_order_transpose.py"
)
DOC = Path("docs/irregular_valence5_opensubdiv_source_order_transpose.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
FIXTURE_COVERAGE_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_fixture_coverage.py"
)

ANCHORS = {
    PROBE: (
        "--valence5-source-order-transpose-report",
        "SLIMED_VALENCE5_SOURCE_ORDER_TRANSPOSE_REPORT",
        "print_valence5_source_order_transpose_proof",
        "valence5_fixture_identity_matches",
        "kFaceCount = 20",
        "kSourceCount = 12",
        "kSampleCount = 3",
        "kRowCount = 7",
        "allFaceSourceCountsPassed",
        "backprojected_source_components",
        "weighted_transpose_passed",
        "return 17;",
    ),
    WRAPPER: (
        "OPENSUBDIV_ROOT",
        "experiments/irregular_valence5_fixture_parity.cpp",
        "--valence5-source-order-transpose-report",
        "compare_irregular_valence5_opensubdiv_source_order_transpose.py",
    ),
    COMPARATOR: (
        "EXPECTED_ONE_RINGS",
        "len(flattened) != 220",
        "sorted(counts.values()) == [1] * 7 + [2] * 2",
        "fraction = (1.0 / 3.0) if occurrence == 0 else (2.0 / 3.0)",
        "per_face_opensubdiv_source_sets_match",
        "duplicate_slot_rescatter_max_abs_difference",
        "independent_weighted_transpose_max_abs_difference",
        "production_scatter_executed",
        "existing_dependency_free_production_baseline_executed",
        "opensubdiv_production_force_path_executed",
        "actual fBend/fArea/fVolume parity",
    ),
    DOC: (
        "canonical ordered `20 x 11`",
        "exactly two duplicated source IDs",
        "`g dot (W p) == (W^T g) dot p`",
        "asymmetric `1/3,2/3` duplicate split",
        "`proof_only:true`",
        "`not_production_routing:true`",
        "`production_route_enabled:false`",
        "`production_scatter_executed:false`",
        "proof-local scatter-shape evidence",
        "does not invoke production scatter",
        "`opensubdiv_production_force_path_executed:false`",
        "`existing_dependency_free_production_baseline_executed:true`",
        "it does not imply",
        "counterfactual capability diagnostic confirms",
        "custom OpenSubdiv Loop scheme or library decision",
    ),
    READINESS: (
        "per-face source-order and weighted-transpose contract now passes",
        "whole-Ptex OpenSubdiv evaluation does not match",
        "completed integration-domain/composition diagnostic",
        "completed counterfactual capability diagnostic",
        "custom extraordinary smooth-mask override",
        "does not execute production scatter",
        "Broader-valence production routing remains unsupported",
    ),
    FIXTURE_COVERAGE_INVENTORY: (
        '"explicitly reviewed custom OpenSubdiv Loop scheme or library decision"',
    ),
}

FORBIDDEN_STALE_CLAIMS = {
    READINESS: (
        "The next reviewed step is a per-face source-order and weighted-transpose",
    ),
    FIXTURE_COVERAGE_INVENTORY: (
        '"next_gate": "per-face source-order and weighted-transpose contract"',
        '"next_gate": "valence-5 integration-domain/composition diagnostic"',
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
        "existing_dependency_free_production_baseline_executed": True,
        "opensubdiv_production_force_path_executed": False,
        "next_gate": (
            "explicitly reviewed custom OpenSubdiv Loop scheme or library decision"
        ),
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
