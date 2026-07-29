#!/usr/bin/env python3
"""Inventory the proof-only approved valence-5 OpenSubdiv coverage lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROBE_PATH = Path("scripts/probe_opensubdiv_feasibility.py")
WRAPPER_PATH = Path(
    "scripts/run_irregular_valence5_opensubdiv_fixture_coverage.sh"
)
DOC_PATH = Path("docs/irregular_valence5_opensubdiv_fixture_coverage.md")
READINESS_PATH = Path("docs/opensubdiv_routing_readiness_map.md")
FIXTURE_INVENTORY_PATH = Path(
    "scripts/inventory_irregular_valence5_scientific_fixture.py"
)

ANCHORS = {
    PROBE_PATH: (
        "--valence5-fixture-coverage-report",
        "SLIMED_VALENCE5_FIXTURE_COVERAGE_REPORT",
        "load_serialized_valence5_fixture",
        "valence5_fixture_identity_matches",
        "approved_fixture_identity_matches",
        "complete_value_first_second_coverage",
        "all_requested_samples_evaluated",
        "finite_evaluated_sample_count",
        "all_stencil_weights_source_ids_and_results_finite",
        "if (!valence5FixtureCoveragePassed)",
        "return 14;",
        '"not_production_routing": True',
        '"production_route_enabled": False',
        '"production_force_path_executed": False',
    ),
    WRAPPER_PATH: (
        "run_opensubdiv_probe.sh",
        "--valence5-fixture-coverage-report",
    ),
    DOC_PATH: (
        "approved scientific stand-in",
        "all 180 requested samples",
        "rejects any coordinate, face-order, or winding drift",
        "all six value/derivative vectors",
        "aggregate value, first-derivative, and second-derivative coverage",
        "`proof_only:true`",
        "`not_production_routing:true`",
        "`production_route_enabled:false`",
        "`production_force_path_executed:false`",
        "per-face 11-control source order",
        "Production routing is not authorized.",
    ),
    READINESS_PATH: (
        "aggregate Ptex derivative coverage",
        "A single face exposes only nine source IDs",
        "per-face source-order and weighted-transpose contract now passes",
        "Broader-valence production routing remains unsupported",
    ),
    FIXTURE_INVENTORY_PATH: (
        "closed_valence5_icosahedron",
        "vertex_valence_counts",
        "narrow_positive_depth_11_control",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for relative_path, needles in ANCHORS.items():
        path = root / relative_path
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative_path} missing {needle!r}")

    return {
        "status": "passed" if not errors else "failed",
        "approved_fixture": "data/fixtures/closed_valence5",
        "approved_scope": "narrow positive-depth 11-control scientific stand-in",
        "fixture_coverage_proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_force_path_executed": False,
        "next_gate": (
            "counterfactual valence-5 extraordinary mask attribution "
            "diagnostic"
        ),
        "anchors": {"located": located, "expected": expected},
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
        print(f"fixture: {report['approved_fixture']}")
        print(
            f"anchors: {report['anchors']['located']}/"
            f"{report['anchors']['expected']}"
        )
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
