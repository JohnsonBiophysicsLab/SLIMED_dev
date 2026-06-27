#!/usr/bin/env python3
"""Inventory the frozen regular 12-control OpenSubdiv sample-plan anchors.

This helper is intentionally source-text based. It does not parse C++, run
OpenSubdiv, or execute production force code. It records the current regular
sample identity that a future OpenSubdiv production-routing PR must match or
explicitly review-replace.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


SAMPLE_PLAN_DOC_PATH = Path("docs/opensubdiv_regular_sample_plan.md")
READINESS_DOC_PATH = Path("docs/opensubdiv_routing_readiness_map.md")
MAPPING_DOC_PATH = Path("docs/opensubdiv_mapping_contract.md")
FORCE_EVIDENCE_DOC_PATH = Path("docs/opensubdiv_force_transpose_evidence.md")
GAUSS_PATH = Path("src/mesh/Gauss_quadrature.cpp")
MESH_PATH = Path("src/mesh/Mesh.cpp")
FORCE_PATH = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
LIMIT_SURFACE_IMPL_PATH = Path("src/mesh/Limit_surface_evaluator.cpp")
SURFACE_TEST_PATH = Path("tests/test_surface_geometry_characterization.cpp")


@dataclass(frozen=True)
class Anchor:
    category: str
    name: str
    path: Path
    needle: str
    status: str
    detail: str


@dataclass(frozen=True)
class LocatedAnchor:
    anchor: Anchor
    line_number: int
    line: str


REGULAR_SAMPLE_PLAN: tuple[dict[str, object], ...] = (
    {
        "sample": 0,
        "v": "1/6",
        "w": "1/6",
        "u": "4/6",
        "quadrature_weight": "1/3",
        "formula_factor": "1/6",
    },
    {
        "sample": 1,
        "v": "1/6",
        "w": "4/6",
        "u": "1/6",
        "quadrature_weight": "1/3",
        "formula_factor": "1/6",
    },
    {
        "sample": 2,
        "v": "4/6",
        "w": "1/6",
        "u": "1/6",
        "quadrature_weight": "1/3",
        "formula_factor": "1/6",
    },
)


DERIVATIVE_ROWS: tuple[dict[str, object], ...] = (
    {"row": 0, "name": "position", "meaning": "limit position", "opensubdiv_row": "value"},
    {"row": 1, "name": "firstDerivativeV", "meaning": "d/dv", "opensubdiv_row": "du under s=v,t=w"},
    {"row": 2, "name": "firstDerivativeW", "meaning": "d/dw", "opensubdiv_row": "dv under s=v,t=w"},
    {"row": 3, "name": "secondDerivativeVV", "meaning": "d2/dv2", "opensubdiv_row": "duu"},
    {"row": 4, "name": "secondDerivativeWW", "meaning": "d2/dw2", "opensubdiv_row": "dvv"},
    {"row": 5, "name": "mixedDerivativeVW", "meaning": "d2/dvdw", "opensubdiv_row": "duv"},
    {"row": 6, "name": "mixedDerivativeWV", "meaning": "d2/dwdv", "opensubdiv_row": "duv"},
)


SOURCE_ID_RULES: tuple[dict[str, str], ...] = (
    {
        "rule": "regular local source order",
        "requirement": "shape-function column j addresses Face::oneRingVertices[j]",
    },
    {
        "rule": "force scatter order",
        "requirement": "local regular force row j scatters to face.oneRingVertices[j]",
    },
    {
        "rule": "duplicate source ids",
        "requirement": "row_weight sums every local column with the requested source id",
    },
)


ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        "sample plan doc",
        "dedicated sample plan",
        SAMPLE_PLAN_DOC_PATH,
        "OpenSubdiv Regular 12-Control Sample Plan",
        "sample plan",
        "The dedicated regular sample-plan document is present.",
    ),
    Anchor(
        "sample plan doc",
        "docs scripts tests boundary",
        SAMPLE_PLAN_DOC_PATH,
        "This is a docs/scripts/tests-only characterization lane.",
        "policy boundary",
        "The sample plan records that production behavior and routing are unchanged.",
    ),
    Anchor(
        "sample plan doc",
        "quadrature n2",
        SAMPLE_PLAN_DOC_PATH,
        "The current default `Param::gaussQuadratureN` is `2`.",
        "quadrature identity",
        "The sample plan freezes the current default quadrature order.",
    ),
    Anchor(
        "sample plan doc",
        "first sample",
        SAMPLE_PLAN_DOC_PATH,
        "| 0 | `1/6` | `1/6` | `4/6` | `1/3` | `1/6` |",
        "quadrature identity",
        "The first regular sample row is documented.",
    ),
    Anchor(
        "sample plan doc",
        "second sample",
        SAMPLE_PLAN_DOC_PATH,
        "| 1 | `1/6` | `4/6` | `1/6` | `1/3` | `1/6` |",
        "quadrature identity",
        "The second regular sample row is documented.",
    ),
    Anchor(
        "sample plan doc",
        "third sample",
        SAMPLE_PLAN_DOC_PATH,
        "| 2 | `4/6` | `1/6` | `1/6` | `1/3` | `1/6` |",
        "quadrature identity",
        "The third regular sample row is documented.",
    ),
    Anchor(
        "sample plan doc",
        "s equals v t equals w",
        SAMPLE_PLAN_DOC_PATH,
        "The regular comparison convention is `s=v,t=w`.",
        "derivative convention",
        "The sample plan freezes the OpenSubdiv comparison convention.",
    ),
    Anchor(
        "sample plan doc",
        "orientation",
        SAMPLE_PLAN_DOC_PATH,
        "normal numerator = firstDerivativeV x firstDerivativeW",
        "orientation",
        "The sample plan freezes the tangent-cross orientation.",
    ),
    Anchor(
        "sample plan doc",
        "seven row table",
        SAMPLE_PLAN_DOC_PATH,
        "Each regular sample produces a `7 x 12` matrix.",
        "row contract",
        "The sample plan records the seven-row regular shape contract.",
    ),
    Anchor(
        "sample plan doc",
        "duplicated mixed row",
        SAMPLE_PLAN_DOC_PATH,
        "Rows 5 and 6 currently duplicate the mixed derivative",
        "row contract",
        "The sample plan records the duplicated mixed-row convention.",
    ),
    Anchor(
        "sample plan doc",
        "source order",
        SAMPLE_PLAN_DOC_PATH,
        "local shape-function column `j` addresses",
        "source-id order",
        "The sample plan records the Face::oneRingVertices source order.",
    ),
    Anchor(
        "sample plan doc",
        "duplicate aggregation",
        SAMPLE_PLAN_DOC_PATH,
        "sums every matching local",
        "source-id aggregation",
        "The sample plan records duplicate source-id aggregation semantics.",
    ),
    Anchor(
        "sample plan doc",
        "comparison boundary",
        SAMPLE_PLAN_DOC_PATH,
        "A future production-routing PR can use this sample plan only after proving",
        "routing boundary",
        "The sample plan states what must match before production routing changes.",
    ),
    Anchor(
        "readiness map",
        "sample plan cross reference",
        READINESS_DOC_PATH,
        "docs/opensubdiv_regular_sample_plan.md",
        "cross-reference",
        "The routing readiness map points to the dedicated regular sample plan.",
    ),
    Anchor(
        "mapping contract",
        "sample plan cross reference",
        MAPPING_DOC_PATH,
        "docs/opensubdiv_regular_sample_plan.md",
        "cross-reference",
        "The mapping contract points to the dedicated regular sample plan.",
    ),
    Anchor(
        "force evidence",
        "sample plan cross reference",
        FORCE_EVIDENCE_DOC_PATH,
        "docs/opensubdiv_regular_sample_plan.md",
        "cross-reference",
        "The force evidence map points to the dedicated regular sample plan.",
    ),
    Anchor(
        "production quadrature",
        "default order values",
        GAUSS_PATH,
        "{{1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0}",
        "source anchor",
        "The in-tree quadrature implementation contains the first frozen N=2 row.",
    ),
    Anchor(
        "production quadrature",
        "default weights",
        GAUSS_PATH,
        "vwuCoeff = {1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0};",
        "source anchor",
        "The in-tree quadrature implementation contains the frozen N=2 weights.",
    ),
    Anchor(
        "production cache",
        "shape function cache",
        MESH_PATH,
        "get_shapefunction_vector(param.VWU, param.shapeFunctions);",
        "source anchor",
        "Mesh construction caches shape functions in quadrature order.",
    ),
    Anchor(
        "production formula",
        "half quadrature factor",
        FORCE_PATH,
        "halfGaussQuadratureCoeff = 0.5 * param.gaussQuadratureCoeff(i, 0);",
        "source anchor",
        "The regular force formula uses the frozen half-weight factor.",
    ),
    Anchor(
        "source-id seam",
        "duplicate aggregation implementation",
        LIMIT_SURFACE_IMPL_PATH,
        "weight += rowWeights.get(rowIndex, sourceIndex);",
        "source anchor",
        "The implementation aggregates duplicate source-id row weights.",
    ),
    Anchor(
        "production test",
        "sample plan characterization",
        SURFACE_TEST_PATH,
        "RegularProductionSamplePlanMatchesFrozenDefaultQuadrature",
        "test anchor",
        "The focused C++ test characterizes the frozen regular sample plan.",
    ),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def locate_anchor(root: Path, anchor: Anchor) -> LocatedAnchor | None:
    path = root / anchor.path
    if not path.is_file():
        return None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if anchor.needle in line:
            return LocatedAnchor(anchor=anchor, line_number=line_number, line=line.strip())
    return None


def collect_anchors(root: Path) -> tuple[list[LocatedAnchor], list[Anchor]]:
    located: list[LocatedAnchor] = []
    missing: list[Anchor] = []
    for anchor in ANCHORS:
        match = locate_anchor(root, anchor)
        if match is None:
            missing.append(anchor)
        else:
            located.append(match)
    return located, missing


def as_dicts(located: Sequence[LocatedAnchor], missing: Sequence[Anchor]) -> dict[str, object]:
    return {
        "status": "passed" if not missing else "failed",
        "regular_sample_plan": list(REGULAR_SAMPLE_PLAN),
        "derivative_rows": list(DERIVATIVE_ROWS),
        "source_id_rules": list(SOURCE_ID_RULES),
        "located": [
            {
                "category": item.anchor.category,
                "name": item.anchor.name,
                "path": item.anchor.path.as_posix(),
                "line": item.line_number,
                "source": item.line,
                "status": item.anchor.status,
                "detail": item.anchor.detail,
            }
            for item in located
        ],
        "missing": [
            {
                "category": item.category,
                "name": item.name,
                "path": item.path.as_posix(),
                "needle": item.needle,
                "status": item.status,
                "detail": item.detail,
            }
            for item in missing
        ],
    }


def print_text(located: Sequence[LocatedAnchor], missing: Sequence[Anchor]) -> None:
    print("# OpenSubdiv Regular 12-Control Sample Plan Inventory")
    print()
    print("## Frozen regular sample plan")
    for row in REGULAR_SAMPLE_PLAN:
        print(f"- sample {row['sample']}: v={row['v']} w={row['w']} u={row['u']}")
        print(f"  quadrature_weight: {row['quadrature_weight']}")
        print(f"  formula_factor: {row['formula_factor']}")
    print()
    print("## Seven derivative rows")
    for row in DERIVATIVE_ROWS:
        print(f"- row {row['row']}: {row['name']}")
        print(f"  meaning: {row['meaning']}")
        print(f"  opensubdiv_row: {row['opensubdiv_row']}")
    print()
    print("## Source-id rules")
    for row in SOURCE_ID_RULES:
        print(f"- {row['rule']}: {row['requirement']}")
    print()
    print("## Located anchors")
    for item in located:
        print(f"- [{item.anchor.category}] {item.anchor.name}")
        print(f"  source: {item.anchor.path}:{item.line_number} `{item.line}`")
        print(f"  status: {item.anchor.status}")
        print(f"  detail: {item.anchor.detail}")
    if missing:
        print()
        print("## Missing anchors")
        for item in missing:
            print(f"- [{item.category}] {item.name}: {item.path} missing `{item.needle}`")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit nonzero when an expected sample-plan anchor is not found.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Alias for --fail-on-missing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    located, missing = collect_anchors(repo_root())
    if args.json:
        print(json.dumps(as_dicts(located, missing), indent=2, sort_keys=True))
    else:
        print_text(located, missing)
    return 1 if missing and (args.fail_on_missing or args.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
