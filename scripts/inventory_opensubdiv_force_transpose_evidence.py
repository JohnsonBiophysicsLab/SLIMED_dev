#!/usr/bin/env python3
"""Inventory OpenSubdiv force-transpose evidence anchors.

This helper is intentionally source-text based. It does not parse C++, run
OpenSubdiv, or execute production force code. It records where the repo
distinguishes toy-linear transpose evidence from actual bending/area/volume
force-transpose evidence through the current regular evaluator seam from the
OpenSubdiv-backed evidence still required before production OpenSubdiv routing
can be claimed correct.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


EVIDENCE_DOC_PATH = Path("docs/opensubdiv_force_transpose_evidence.md")
MAPPING_DOC_PATH = Path("docs/opensubdiv_mapping_contract.md")
FORCE_DOC_PATH = Path("docs/force_formula_scatter_equivalence.md")
PROOF_MAP_DOC_PATH = Path("docs/irregular_subdivision_transpose_proof_map.md")
POLICY_DOC_PATH = Path("docs/opensubdiv_backend_interface_policy.md")
PROBE_PATH = Path("scripts/probe_opensubdiv_feasibility.py")
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


EVIDENCE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "claim": "regular OpenSubdiv row/integrand equivalence",
        "current_status": "opt-in observational evidence",
        "anchor": "--regular-equivalence-report",
        "remaining_gap": "does not transpose actual force formulas",
    },
    {
        "claim": "regular OpenSubdiv transpose shape",
        "current_status": "toy linear functional only",
        "anchor": "--force-transpose-report",
        "remaining_gap": "does not compute fBend, fArea, fVol, quadrature, or scatter",
    },
    {
        "claim": "regular OpenSubdiv actual formula smoke",
        "current_status": "opt-in temporary-probe evidence",
        "anchor": "--regular-actual-force-report",
        "remaining_gap": "not production routing, backend integration, OpenMP scatter, or irregular evidence",
    },
    {
        "claim": "production regular formula/scatter shape",
        "current_status": "in-tree actual formula characterization",
        "anchor": "RegularActualForceBackProjectionMatchesDirectFormulaRows",
        "remaining_gap": "not OpenSubdiv-backed and does not enable production OpenSubdiv routing",
    },
    {
        "claim": "positive-depth 11-control force transpose",
        "current_status": "dependency-free subdivision-matrix route",
        "anchor": "SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces",
        "remaining_gap": "not OpenSubdiv-backed and not broader irregular support",
    },
    {
        "claim": "irregular OpenSubdiv source/transpose visibility",
        "current_status": "aggregate all-ptex toy evidence only",
        "anchor": "--irregular-transpose-proof-map-report",
        "remaining_gap": "no face-level sample plan or actual force formulas",
    },
)


ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        "evidence map",
        "dedicated force-transpose map",
        EVIDENCE_DOC_PATH,
        "OpenSubdiv Force Transpose Evidence Map",
        "new evidence map",
        "The dedicated evidence map is present.",
    ),
    Anchor(
        "evidence map",
        "non-production boundary",
        EVIDENCE_DOC_PATH,
        "This is a docs/scripts-only evidence lane.",
        "policy boundary",
        "The lane records that production behavior and dependency policy are unchanged.",
    ),
    Anchor(
        "evidence map",
        "toy versus actual distinction",
        EVIDENCE_DOC_PATH,
        "actual bending, area, and volume force transpose evidence",
        "required distinction",
        "The map distinguishes toy-linear transpose from actual formula transpose.",
    ),
    Anchor(
        "evidence map",
        "toy transpose caveat",
        EVIDENCE_DOC_PATH,
        "kind: toy_linear_functional_only",
        "current evidence",
        "The regular OpenSubdiv transpose report is documented as toy-only.",
    ),
    Anchor(
        "evidence map",
        "regular actual formula smoke",
        EVIDENCE_DOC_PATH,
        "kind: opensubdiv_regular_rows_actual_formula_evidence",
        "opt-in actual formula evidence",
        "The map documents OpenSubdiv regular rows feeding actual force formula algebra.",
    ),
    Anchor(
        "evidence map",
        "regular actual formula non-production caveat",
        EVIDENCE_DOC_PATH,
        "not production C++ routing",
        "policy boundary",
        "The map keeps the regular actual formula smoke outside production routing.",
    ),
    Anchor(
        "evidence map",
        "irregular observational caveat",
        EVIDENCE_DOC_PATH,
        "kind: observational_all_ptex_grid_toy_transpose",
        "current evidence",
        "The irregular proof-map report is documented as aggregate observational evidence.",
    ),
    Anchor(
        "evidence map",
        "OpenSubdiv actual formula blocker",
        EVIDENCE_DOC_PATH,
        "OpenSubdiv-backed regular actual-force transpose through the production",
        "remaining OpenSubdiv blocker",
        "The map names the missing OpenSubdiv-backed bending/area/volume formula proof.",
    ),
    Anchor(
        "evidence map",
        "current 11 route preserved",
        EVIDENCE_DOC_PATH,
        "positive-depth `11 = 4+3+4` force evaluation",
        "current route preserved",
        "The map keeps the current dependency-free positive-depth 11-control route separate from OpenSubdiv.",
    ),
    Anchor(
        "probe",
        "regular equivalence option",
        PROBE_PATH,
        "--regular-equivalence-report",
        "opt-in OpenSubdiv evidence",
        "The probe can report regular row/integrand equivalence.",
    ),
    Anchor(
        "probe",
        "toy force transpose option",
        PROBE_PATH,
        "--force-transpose-report",
        "opt-in OpenSubdiv evidence",
        "The probe can report the regular toy transpose shape.",
    ),
    Anchor(
        "probe",
        "toy force transpose kind",
        PROBE_PATH,
        "toy_linear_functional_only",
        "toy-only caveat",
        "The probe labels the regular transpose report as a toy linear functional.",
    ),
    Anchor(
        "probe",
        "regular actual force option",
        PROBE_PATH,
        "--regular-actual-force-report",
        "opt-in OpenSubdiv evidence",
        "The probe can run regular OpenSubdiv rows through actual force formula algebra.",
    ),
    Anchor(
        "probe",
        "regular actual force kind",
        PROBE_PATH,
        "opensubdiv_regular_rows_actual_formula_evidence",
        "actual formula smoke caveat",
        "The probe labels the report as regular actual formula evidence only.",
    ),
    Anchor(
        "probe",
        "regular actual force non-production caveat",
        PROBE_PATH,
        "not_production_routing",
        "policy boundary",
        "The probe marks the regular actual formula smoke as non-production routing.",
    ),
    Anchor(
        "probe",
        "irregular proof-map option",
        PROBE_PATH,
        "--irregular-transpose-proof-map-report",
        "opt-in OpenSubdiv evidence",
        "The probe can report irregular aggregate source visibility and toy transpose shape.",
    ),
    Anchor(
        "probe",
        "irregular proof-map kind",
        PROBE_PATH,
        "observational_all_ptex_grid_toy_transpose",
        "observational caveat",
        "The probe labels irregular evidence as all-ptex aggregate toy transpose.",
    ),
    Anchor(
        "force/scatter contract",
        "OpenSubdiv actual production formulas caveat",
        FORCE_DOC_PATH,
        "OpenSubdiv-backed force transpose/back-projection equivalence",
        "remaining OpenSubdiv blocker",
        "The force/scatter contract keeps OpenSubdiv-backed formula transpose evidence separate.",
    ),
    Anchor(
        "force/scatter contract",
        "regular formula test",
        FORCE_DOC_PATH,
        "RegularActualForceBackProjectionMatchesDirectFormulaRows",
        "production characterization",
        "Focused tests characterize current formula/scatter behavior through the in-tree seam.",
    ),
    Anchor(
        "mapping contract",
        "actual formula requirement",
        MAPPING_DOC_PATH,
        "actual SLIMED bending, area, and volume force formulas",
        "remaining blocker",
        "The mapping contract requires actual force formula proof before routing.",
    ),
    Anchor(
        "mapping contract",
        "new evidence map cross-reference",
        MAPPING_DOC_PATH,
        "docs/opensubdiv_force_transpose_evidence.md",
        "cross-reference",
        "The mapping contract points reviewers to the focused evidence map.",
    ),
    Anchor(
        "proof map",
        "toy scalar functional caveat",
        PROOF_MAP_DOC_PATH,
        "Proven only for a toy scalar functional, not production force formulas.",
        "toy-only caveat",
        "The irregular proof map distinguishes toy transpose from production formula proof.",
    ),
    Anchor(
        "backend policy",
        "new evidence map cross-reference",
        POLICY_DOC_PATH,
        "docs/opensubdiv_force_transpose_evidence.md",
        "cross-reference",
        "The backend policy points reviewers to the focused evidence map.",
    ),
    Anchor(
        "production test",
        "regular formula back-projection test",
        SURFACE_TEST_PATH,
        "RegularActualForceBackProjectionMatchesDirectFormulaRows",
        "production characterization",
        "Regular formula/scatter behavior is covered for the current evaluator seam.",
    ),
    Anchor(
        "production test",
        "one-ring scatter test",
        SURFACE_TEST_PATH,
        "RegularForceRowsScatterInOneRingOrder",
        "production characterization",
        "Current local-row-to-one-ring scatter order is covered.",
    ),
    Anchor(
        "production test",
        "11-control child force transpose test",
        SURFACE_TEST_PATH,
        "SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces",
        "current route evidence",
        "The current dependency-free 11-control route has synthetic transpose characterization.",
    ),
    Anchor(
        "production implementation",
        "11-control child force transpose",
        IMPLEMENTATION_PATH,
        "add_back_projected_child_force(childToOriginal, childFBend, fBend);",
        "current route evidence",
        "Production child regular force rows are transposed through subdivision weights.",
    ),
    Anchor(
        "production implementation",
        "current scatter order",
        IMPLEMENTATION_PATH,
        "int iVertex = face.oneRingVertices[j];",
        "scatter contract",
        "Local force rows scatter through the reviewed one-ring order.",
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
        "evidence_matrix": list(EVIDENCE_MATRIX),
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
    print("# OpenSubdiv Force Transpose Evidence Inventory")
    print()
    print("## Evidence matrix")
    for row in EVIDENCE_MATRIX:
        print(f"- {row['claim']}")
        print(f"  current_status: {row['current_status']}")
        print(f"  anchor: {row['anchor']}")
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
        help="Exit nonzero when an expected evidence anchor is not found.",
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
