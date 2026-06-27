#!/usr/bin/env python3
"""Inventory OpenSubdiv production-routing readiness anchors.

This helper is intentionally source-text based. It does not parse C++, run
OpenSubdiv, or execute production force code. It records the regular-first
readiness criteria and the evidence boundaries that must stay visible before a
future PR claims OpenSubdiv-derived samples or rows are production-route ready.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


READINESS_DOC_PATH = Path("docs/opensubdiv_routing_readiness_map.md")
POLICY_DOC_PATH = Path("docs/opensubdiv_backend_interface_policy.md")
MAPPING_DOC_PATH = Path("docs/opensubdiv_mapping_contract.md")
FORCE_EVIDENCE_DOC_PATH = Path("docs/opensubdiv_force_transpose_evidence.md")
FORCE_SCATTER_DOC_PATH = Path("docs/force_formula_scatter_equivalence.md")
IRREGULAR_PROOF_DOC_PATH = Path("docs/irregular_subdivision_transpose_proof_map.md")
PROBE_PATH = Path("scripts/probe_opensubdiv_feasibility.py")
WRAPPER_PATH = Path("scripts/run_opensubdiv_probe.sh")
SURFACE_TEST_PATH = Path("tests/test_surface_geometry_characterization.cpp")
IMPLEMENTATION_PATH = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")


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


REGULAR_READINESS_CRITERIA: tuple[dict[str, str], ...] = (
    {
        "criterion": "OpenSubdiv-derived sample identity",
        "current_status": "regular row/integrand probe evidence",
        "remaining_gap": "freeze routed production samples and quadrature points",
    },
    {
        "criterion": "seven-row derivative mapping",
        "current_status": "mapping contract documents s=v,t=w and mixed-row convention",
        "remaining_gap": "carry explicit convention metadata in any routed backend",
    },
    {
        "criterion": "source-id ordering",
        "current_status": "backend-neutral seam and regular tests cover source ids",
        "remaining_gap": "prove OpenSubdiv-derived ids match Face::oneRingVertices order",
    },
    {
        "criterion": "duplicate aggregation",
        "current_status": "readiness map requires deterministic source-id aggregation",
        "remaining_gap": "compare aggregated OpenSubdiv weights before routing",
    },
    {
        "criterion": "quadrature/sample identity",
        "current_status": "force/scatter contract records current quadrature order",
        "remaining_gap": "prove routed backend uses identical samples or reviewed change",
    },
    {
        "criterion": "actual fBend/fArea/fVolume comparison",
        "current_status": "opt-in regular actual-force probe plus in-tree formula tests",
        "remaining_gap": "compare OpenSubdiv-derived rows through production routing",
    },
    {
        "criterion": "energy/normal/area/volume comparison",
        "current_status": "regular probe and tests cover deterministic evidence",
        "remaining_gap": "compare output-visible production call timing",
    },
    {
        "criterion": "scatter through Face::oneRingVertices",
        "current_status": "regular scatter order test covers current route",
        "remaining_gap": "prove OpenSubdiv-derived rows preserve or review-replace order",
    },
    {
        "criterion": "serial/OpenMP tolerance envelope",
        "current_status": "thread-local buffer and reduction order documented",
        "remaining_gap": "establish routed backend tolerances for outputs",
    },
    {
        "criterion": "fallback diagnostics",
        "current_status": "dependency-absent probe skip and unsupported-route guards",
        "remaining_gap": "review diagnostics for every routed unsupported case",
    },
    {
        "criterion": "default dependency isolation",
        "current_status": "OpenSubdiv remains OPENSUBDIV_ROOT-gated",
        "remaining_gap": "keep default builds and Makefile behavior unchanged",
    },
    {
        "criterion": "reviewer/user gate",
        "current_status": "readiness evidence only",
        "remaining_gap": "separate reviewed PR before production routing",
    },
)


ROUTE_READINESS_MATRIX: tuple[dict[str, str], ...] = (
    {
        "route": "regular 12-control membrane force",
        "current_production_status": "supported by in-tree evaluator",
        "opensubdiv_evidence_status": "opt-in probe evidence only",
        "readiness_result": "not route-ready until gated production comparison",
    },
    {
        "route": "positive-depth 11 = 4+3+4 membrane force",
        "current_production_status": "supported narrowly by subdivision matrices",
        "opensubdiv_evidence_status": "observational aggregate reports only",
        "readiness_result": "keep current route; do not replace in regular lane",
    },
    {
        "route": "zero-depth 11-control and unsupported irregular topologies",
        "current_production_status": "guarded unsupported",
        "opensubdiv_evidence_status": "no production approval",
        "readiness_result": "must continue to fail loudly or use reviewed diagnostics",
    },
    {
        "route": "broader extraordinary valence",
        "current_production_status": "not production supported",
        "opensubdiv_evidence_status": "planning evidence only",
        "readiness_result": "future-only pending fixtures and scientific approval",
    },
)


ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        "readiness map",
        "dedicated readiness map",
        READINESS_DOC_PATH,
        "OpenSubdiv Production-Routing Readiness Map",
        "readiness map",
        "The dedicated routing readiness map is present.",
    ),
    Anchor(
        "readiness map",
        "non-production boundary",
        READINESS_DOC_PATH,
        "This is a docs/scripts-only readiness map.",
        "policy boundary",
        "The map records that production behavior, backend interfaces, and build policy are unchanged.",
    ),
    Anchor(
        "readiness map",
        "PR72 observational boundary",
        READINESS_DOC_PATH,
        "PR #72 probe evidence is observational and non-production.",
        "policy boundary",
        "The map keeps PR #72 evidence out of production routing.",
    ),
    Anchor(
        "readiness map",
        "regular first",
        READINESS_DOC_PATH,
        "Regular 12-control routing first",
        "staged readiness",
        "The map prioritizes the regular route before irregular or broader-valence routing.",
    ),
    Anchor(
        "readiness map",
        "regular not route ready",
        READINESS_DOC_PATH,
        "Not route-ready until OpenSubdiv-derived rows are compared through production routing/scatter",
        "remaining gap",
        "The regular route is not declared production-ready by probe evidence alone.",
    ),
    Anchor(
        "readiness criterion",
        "OpenSubdiv-derived sample identity",
        READINESS_DOC_PATH,
        "OpenSubdiv-derived sample identity",
        "regular criterion",
        "The map requires a fixed routed regular sample identity.",
    ),
    Anchor(
        "readiness criterion",
        "seven-row derivative mapping",
        READINESS_DOC_PATH,
        "Seven-row derivative mapping",
        "regular criterion",
        "The map requires the seven SLIMED row convention before routing.",
    ),
    Anchor(
        "readiness criterion",
        "source-id ordering",
        READINESS_DOC_PATH,
        "Source-id ordering",
        "regular criterion",
        "The map requires original SLIMED source ids to preserve reviewed ordering.",
    ),
    Anchor(
        "readiness criterion",
        "duplicate aggregation",
        READINESS_DOC_PATH,
        "Duplicate aggregation",
        "regular criterion",
        "The map requires deterministic duplicate source-id aggregation.",
    ),
    Anchor(
        "readiness criterion",
        "quadrature/sample identity",
        READINESS_DOC_PATH,
        "Quadrature/sample identity",
        "regular criterion",
        "The map requires the current quadrature/sample identity or reviewed replacement.",
    ),
    Anchor(
        "readiness criterion",
        "actual force rows",
        READINESS_DOC_PATH,
        "Actual `fBend`/`fArea`/`fVolume` comparison",
        "regular criterion",
        "The map requires actual bending, area, and volume force-row comparison.",
    ),
    Anchor(
        "readiness criterion",
        "output-visible geometry",
        READINESS_DOC_PATH,
        "Energy, normal, area, and volume comparison",
        "regular criterion",
        "The map requires output-visible energy and geometry comparison.",
    ),
    Anchor(
        "readiness criterion",
        "one-ring scatter",
        READINESS_DOC_PATH,
        "Scatter through `Face::oneRingVertices`",
        "regular criterion",
        "The map requires scatter through the reviewed one-ring order.",
    ),
    Anchor(
        "readiness criterion",
        "serial OpenMP tolerance",
        READINESS_DOC_PATH,
        "Serial/OpenMP tolerance envelope",
        "regular criterion",
        "The map requires a serial/OpenMP tolerance envelope.",
    ),
    Anchor(
        "readiness criterion",
        "fallback diagnostics",
        READINESS_DOC_PATH,
        "Fallback diagnostics",
        "regular criterion",
        "The map requires explicit fallback diagnostics.",
    ),
    Anchor(
        "readiness criterion",
        "dependency isolation",
        READINESS_DOC_PATH,
        "Default dependency isolation",
        "regular criterion",
        "The map keeps default dependency behavior unchanged.",
    ),
    Anchor(
        "readiness criterion",
        "reviewer user gate",
        READINESS_DOC_PATH,
        "Reviewer/user gate",
        "regular criterion",
        "The map records that a separate reviewed PR is required before routing.",
    ),
    Anchor(
        "future boundary",
        "irregular future only",
        READINESS_DOC_PATH,
        "OpenSubdiv-backed irregular or broader-valence production support remains",
        "future-only",
        "The map keeps irregular and broader-valence OpenSubdiv routing future-only.",
    ),
    Anchor(
        "future boundary",
        "aggregate coverage caveat",
        READINESS_DOC_PATH,
        "Aggregate all-ptex source visibility and toy transpose reports are planning",
        "observational caveat",
        "The map distinguishes aggregate visibility from a production scatter contract.",
    ),
    Anchor(
        "backend policy",
        "readiness map cross-reference",
        POLICY_DOC_PATH,
        "docs/opensubdiv_routing_readiness_map.md",
        "cross-reference",
        "The backend policy points reviewers to the readiness map.",
    ),
    Anchor(
        "mapping contract",
        "original source ids",
        MAPPING_DOC_PATH,
        "Source ids at the public backend boundary must be original SLIMED vertex ids",
        "source-id contract",
        "The mapping contract anchors original SLIMED source ids.",
    ),
    Anchor(
        "mapping contract",
        "seven row contract",
        MAPPING_DOC_PATH,
        "Every backend sample must expose the current seven SLIMED derivative rows",
        "row contract",
        "The mapping contract anchors the seven-row backend-neutral convention.",
    ),
    Anchor(
        "force evidence",
        "regular actual formula smoke",
        FORCE_EVIDENCE_DOC_PATH,
        "kind: opensubdiv_regular_rows_actual_formula_evidence",
        "opt-in evidence",
        "The force evidence map records regular actual-force probe evidence.",
    ),
    Anchor(
        "force evidence",
        "regular actual non-production",
        FORCE_EVIDENCE_DOC_PATH,
        "not production C++ routing",
        "policy boundary",
        "The force evidence map keeps the actual-force smoke non-production.",
    ),
    Anchor(
        "force/scatter contract",
        "force row names",
        FORCE_SCATTER_DOC_PATH,
        "`fBend(j,:)`",
        "production characterization",
        "The force/scatter contract names the bending force-row output.",
    ),
    Anchor(
        "force/scatter contract",
        "area row names",
        FORCE_SCATTER_DOC_PATH,
        "`fArea(j,:)`",
        "production characterization",
        "The force/scatter contract names the area force-row output.",
    ),
    Anchor(
        "force/scatter contract",
        "volume row names",
        FORCE_SCATTER_DOC_PATH,
        "`fVol(j,:)`",
        "production characterization",
        "The force/scatter contract names the volume force-row output.",
    ),
    Anchor(
        "force/scatter contract",
        "quadrature order",
        FORCE_SCATTER_DOC_PATH,
        "0.5 * param.gaussQuadratureCoeff(i, 0)",
        "production characterization",
        "The force/scatter contract records current quadrature weighting.",
    ),
    Anchor(
        "force/scatter contract",
        "one-ring scatter",
        FORCE_SCATTER_DOC_PATH,
        "face.oneRingVertices[j]",
        "scatter contract",
        "The force/scatter contract records local-row scatter order.",
    ),
    Anchor(
        "irregular proof map",
        "observational OpenSubdiv evidence",
        IRREGULAR_PROOF_DOC_PATH,
        "OpenSubdiv evidence remains observational",
        "future boundary",
        "The irregular proof map keeps OpenSubdiv irregular evidence observational.",
    ),
    Anchor(
        "probe",
        "regular equivalence option",
        PROBE_PATH,
        "--regular-equivalence-report",
        "opt-in OpenSubdiv evidence",
        "The probe can emit regular row/integrand equivalence evidence.",
    ),
    Anchor(
        "probe",
        "regular actual force option",
        PROBE_PATH,
        "--regular-actual-force-report",
        "opt-in OpenSubdiv evidence",
        "The probe can emit regular actual-force formula smoke evidence.",
    ),
    Anchor(
        "probe",
        "regular actual force kind",
        PROBE_PATH,
        "opensubdiv_regular_rows_actual_formula_evidence",
        "opt-in OpenSubdiv evidence",
        "The probe labels regular actual-force evidence distinctly.",
    ),
    Anchor(
        "probe",
        "non-production probe caveat",
        PROBE_PATH,
        "not_production_routing",
        "policy boundary",
        "The probe marks actual-force evidence as non-production routing.",
    ),
    Anchor(
        "probe wrapper",
        "absent wrapper skip",
        WRAPPER_PATH,
        '"status": "skipped"',
        "dependency boundary",
        "The wrapper skips cleanly when OPENSUBDIV_ROOT is absent.",
    ),
    Anchor(
        "production test",
        "regular formula comparison",
        SURFACE_TEST_PATH,
        "RegularActualForceBackProjectionMatchesDirectFormulaRows",
        "production characterization",
        "The current regular formula rows are characterized through the in-tree seam.",
    ),
    Anchor(
        "production test",
        "regular scatter comparison",
        SURFACE_TEST_PATH,
        "RegularForceRowsScatterInOneRingOrder",
        "production characterization",
        "The current regular scatter order is characterized.",
    ),
    Anchor(
        "production implementation",
        "one-ring force scatter",
        IMPLEMENTATION_PATH,
        "int iVertex = face.oneRingVertices[j];",
        "scatter contract",
        "Production force rows scatter through Face::oneRingVertices.",
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
        "route_readiness_matrix": list(ROUTE_READINESS_MATRIX),
        "regular_readiness_criteria": list(REGULAR_READINESS_CRITERIA),
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
    print("# OpenSubdiv Production-Routing Readiness Inventory")
    print()
    print("## Route readiness matrix")
    for row in ROUTE_READINESS_MATRIX:
        print(f"- {row['route']}")
        print(f"  current_production_status: {row['current_production_status']}")
        print(f"  opensubdiv_evidence_status: {row['opensubdiv_evidence_status']}")
        print(f"  readiness_result: {row['readiness_result']}")
    print()
    print("## Regular readiness criteria")
    for row in REGULAR_READINESS_CRITERIA:
        print(f"- {row['criterion']}")
        print(f"  current_status: {row['current_status']}")
        print(f"  remaining_gap: {row['remaining_gap']}")
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
        help="Exit nonzero when an expected readiness anchor is not found.",
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
