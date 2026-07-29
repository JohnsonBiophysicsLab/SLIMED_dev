#!/usr/bin/env python3
"""Inventory the valence-5 OpenSubdiv integration-composition diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PRODUCTION = Path("experiments/irregular_valence5_fixture_parity.cpp")
PROBE = Path("scripts/probe_opensubdiv_feasibility.py")
RUNNER = Path(
    "scripts/run_irregular_valence5_opensubdiv_integration_composition.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence5_opensubdiv_integration_composition.sh"
)
DOC = Path("docs/irregular_valence5_opensubdiv_integration_composition.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
PREDECESSOR = Path(
    "scripts/inventory_irregular_valence5_opensubdiv_force_parity.py"
)

ANCHORS = {
    PRODUCTION: (
        "append_positive_depth_composed_rows",
        "param.subMatrix.irregM1",
        "param.subMatrix.irregM2",
        "param.subMatrix.irregM3",
        "param.subMatrix.irregM4",
        "shapeFunction * childToOriginal",
        "positive_depth_composed_rows",
        "positive_depth_composed_row_shape",
        "positive_depth_extraordinary_vertex_mask",
        "adjacent_face_source_ids",
    ),
    PROBE: (
        "SLIMED_VALENCE5_INTEGRATION_COMPOSITION_REPORT",
        "--valence5-integration-composition-report",
        "print_valence5_integration_composition_proof",
        "depth1_M1_C_corner",
        "depth1_M2_center",
        "depth1_M3_B_corner",
        "depth2_M1_C_corner",
        "depth2_M2_center",
        "depth2_M3_B_corner",
        "orientationPermutations",
        "composed_rows_all_orientations",
        "opensubdivValence5EdgeWeight",
        "opensubdivValence5CenterWeight",
        "production_scatter_executed",
    ),
    RUNNER: (
        "REVIEWED_ROW_TOLERANCE = 5.0e-6",
        "ROW_SHAPE = [20, 6, 3, 7, 12]",
        "ALL_ORIENTATION_ROW_SHAPE = [20, 6, 6, 3, 7, 12]",
        "local_ids.index(source_id)",
        "value_row_domain_residual_matrix",
        "extraordinary_vertex_mask_policy_mismatch",
        "SLIMED and OpenSubdiv use different valence-5",
        "scientific decision on valence-5 extraordinary vertex",
        "production_scatter_executed",
    ),
    WRAPPER: (
        "run_irregular_valence5_opensubdiv_integration_composition.py",
        '"$@"',
    ),
    DOC: (
        "`20 x 6 x 3 x 7 x 12`",
        "`shapeFunction * childToOriginal`",
        "All six orientation permutations",
        "`0.7357563654581705`",
        "`0.02817109760678843`",
        "`0.075`",
        "`0.625`",
        "`0.08409321892578289`",
        "`0.5795339053710855`",
        "scientific decision on valence-5 extraordinary vertex mask",
        "`production_route_enabled:false`",
    ),
    READINESS: (
        "completed integration-domain/composition diagnostic",
        "maximum position-row residual of `0.02817109760678843`",
        "extraordinary smooth-vertex mask",
        "scientific decision on valence-5 extraordinary vertex mask semantics",
    ),
    PREDECESSOR: (
        '"scientific decision on valence-5 extraordinary vertex mask "',
    ),
}

FORBIDDEN_STALE_CLAIMS = {
    RUNNER: (
        'add_argument("--tolerance"',
        "args.tolerance",
    ),
    READINESS: (
        "The next reviewed step is a proof-only\nintegration-domain/composition",
    ),
    PREDECESSOR: (
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
        "composed_row_parity_passed": False,
        "exact_blocker": "valence-5 extraordinary vertex mask policy mismatch",
        "next_gate": (
            "scientific decision on valence-5 extraordinary vertex mask "
            "semantics"
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
