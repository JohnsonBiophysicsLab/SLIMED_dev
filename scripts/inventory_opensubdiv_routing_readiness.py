#!/usr/bin/env python3
"""Inventory OpenSubdiv production-routing readiness anchors.

This helper is intentionally source-text based. It does not parse C++, run
OpenSubdiv, or execute production force code. It records the regular-first
readiness criteria and the evidence boundaries that must stay visible before a
    guarded PR claims broader OpenSubdiv-derived samples or rows are production-route ready.
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
OPENSUBDIV_EVALUATOR_PATH = Path("src/mesh/OpenSubdiv_regular_evaluator.cpp")


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
        "current_status": "regular row/integrand probe, C++ proof evidence, and guarded route tests",
        "remaining_gap": "keep installed route on frozen samples and quadrature points",
    },
    {
        "criterion": "seven-row derivative mapping",
        "current_status": "mapping contract documents s=v,t=w and mixed-row convention",
        "remaining_gap": "carry explicit convention metadata in any routed backend",
    },
    {
        "criterion": "source-id ordering",
        "current_status": "backend-neutral seam, regular tests, and proof harness cover source ids",
        "remaining_gap": "prove installed route matches Face::oneRingVertices order",
    },
    {
        "criterion": "duplicate aggregation",
        "current_status": "proof harness covers deterministic source-id aggregation",
        "remaining_gap": "keep aggregation at the production route boundary",
    },
    {
        "criterion": "quadrature/sample identity",
        "current_status": "force/scatter contract records current quadrature order",
        "remaining_gap": "prove routed backend uses identical samples or reviewed change",
    },
    {
        "criterion": "actual fBend/fArea/fVolume comparison",
        "current_status": "opt-in regular actual-force probe, C++ proof rows, production-helper dry run, guarded helper route test, and diagnostic production-call parity recheck exposing remaining fArea/fVolume deltas, residual locations, and row-error budget location",
        "remaining_gap": "keep route disabled until reviewers approve installing rows",
    },
    {
        "criterion": "energy/normal/area/volume comparison",
        "current_status": "regular probe, tests, visible-observable dry run, guarded route area/helper evidence, and diagnostic production-call parity recheck",
        "remaining_gap": "promote diagnostic evidence only through an explicit activation PR",
    },
    {
        "criterion": "scatter through Face::oneRingVertices",
        "current_status": "regular scatter order test, C++ proof harness, and diagnostic production-call parity recheck cover order while exposing remaining scatter deltas and residual locations",
        "remaining_gap": "prove installed route preserves or review-replaces order",
    },
    {
        "criterion": "serial/OpenMP tolerance envelope",
        "current_status": "thread-local buffer/reduction order documented; proof-local serial/OpenMP-style accumulation parity and diagnostic serial scatter deltas exist",
        "remaining_gap": "establish full serial and OpenMP executable tolerances before activation",
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
        "current_status": "regular seam reviewer/user gate installed; routed rows disabled",
        "remaining_gap": "fix direct-vs-routed semantics before installing rows",
    },
)


ROUTE_READINESS_MATRIX: tuple[dict[str, str], ...] = (
    {
        "route": "regular 12-control membrane force",
        "current_production_status": "supported by in-tree evaluator; guarded OpenSubdiv seam falls back to direct route",
        "opensubdiv_evidence_status": "PR #82 proof evidence, PR #85 row diagnostics, diagnostic parity recheck, and guarded fallback smoke",
        "readiness_result": "OpenSubdiv-derived rows are not production-routed until direct-vs-routed semantics match",
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
        "guarded production boundary",
        READINESS_DOC_PATH,
        "first narrowly guarded production regular-routing",
        "policy boundary",
        "The map records the guarded regular production seam and unchanged defaults.",
    ),
    Anchor(
        "readiness map",
        "PR72 through PR82 observational boundary",
        READINESS_DOC_PATH,
        "PR #72 probe evidence and PR #76 through PR #82 proof evidence are",
        "policy boundary",
        "The map keeps the proof evidence package out of production routing.",
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
        "guarded regular route disabled",
        READINESS_DOC_PATH,
        "No OpenSubdiv-derived rows are production-routed yet",
        "guarded route",
        "The regular route remains disabled until direct-vs-routed semantics match.",
    ),
    Anchor(
        "readiness map",
        "production route boundary",
        READINESS_DOC_PATH,
        "a tiny production route selection boundary",
        "remaining gate",
        "The map names the smallest reviewed production routing boundary.",
    ),
    Anchor(
        "readiness map",
        "proof lineage through PR82",
        READINESS_DOC_PATH,
        "PR #76 through PR #82 proof evidence",
        "evidence lineage",
        "The map records the proof-lane evidence through PR #82.",
    ),
    Anchor(
        "readiness map",
        "diagnostic production-call recheck",
        READINESS_DOC_PATH,
        "diagnose_opensubdiv_regular_production_call_parity",
        "diagnostic gate",
        "The map records the diagnostic-only production-call parity recheck.",
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
        "production test",
        "regular production-call parity recheck",
        SURFACE_TEST_PATH,
        "OptInProductionCallParityRecheckReportsRemainingForceDeltaAndKeepsRouteDisabled",
        "diagnostic test",
        "The OpenSubdiv-enabled focused test records the remaining force/scatter delta without route activation.",
    ),
    Anchor(
        "production diagnostic",
        "regular production-call parity helper",
        OPENSUBDIV_EVALUATOR_PATH,
        "diagnose_opensubdiv_regular_production_call_parity",
        "diagnostic helper",
        "The helper compares would-be routed OpenSubdiv rows against direct regular production helper semantics.",
    ),
    Anchor(
        "production diagnostic",
        "route remains disabled",
        OPENSUBDIV_EVALUATOR_PATH,
        "routeInstalledInProduction = false",
        "guarded route",
        "The diagnostic records that it does not install routed rows in production.",
    ),
    Anchor(
        "production diagnostic",
        "signed area residual",
        OPENSUBDIV_EVALUATOR_PATH,
        "maxFAreaDifferenceSignedDelta",
        "force residual diagnostic",
        "The diagnostic records the signed direct-vs-routed area-force residual.",
    ),
    Anchor(
        "production diagnostic",
        "signed volume residual",
        OPENSUBDIV_EVALUATOR_PATH,
        "maxFVolumeDifferenceSignedDelta",
        "force residual diagnostic",
        "The diagnostic records the signed direct-vs-routed volume-force residual.",
    ),
    Anchor(
        "production diagnostic",
        "signed scatter residual",
        OPENSUBDIV_EVALUATOR_PATH,
        "maxScatterDifferenceSignedDelta",
        "scatter residual diagnostic",
        "The diagnostic records the signed direct-vs-routed scatter residual.",
    ),
    Anchor(
        "production diagnostic",
        "routed row weight residual budget",
        OPENSUBDIV_EVALUATOR_PATH,
        "maxRoutedRowWeightDifferenceVsSlimedRows",
        "row residual diagnostic",
        "The parity recheck records the row-weight drift behind the remaining force residuals.",
    ),
    Anchor(
        "production diagnostic",
        "routed row weight residual location",
        OPENSUBDIV_EVALUATOR_PATH,
        "maxRoutedRowWeightDifferenceSourceColumn",
        "row residual diagnostic",
        "The parity recheck records where the largest row-weight drift occurs.",
    ),
    Anchor(
        "production diagnostic",
        "signed routed row weight residual",
        OPENSUBDIV_EVALUATOR_PATH,
        "maxRoutedRowWeightDifferenceSignedDelta",
        "row residual diagnostic",
        "The parity recheck records the signed direct-vs-routed row-weight residual.",
    ),
    Anchor(
        "production test",
        "routed row weight residual budget assertion",
        SURFACE_TEST_PATH,
        "maxRoutedRowWeightDifferenceVsSlimedRows",
        "row residual diagnostic",
        "The focused OpenSubdiv test asserts the routed row-weight drift remains bounded.",
    ),
    Anchor(
        "production test",
        "routed row weight residual location assertion",
        SURFACE_TEST_PATH,
        "maxRoutedRowWeightDifferenceSourceColumn",
        "row residual diagnostic",
        "The focused OpenSubdiv test asserts the row-weight residual location is populated.",
    ),
    Anchor(
        "readiness map",
        "row-error budget wording",
        READINESS_DOC_PATH,
        "row-error budget",
        "row residual diagnostic",
        "The readiness map frames remaining force residuals against the row-error budget.",
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
