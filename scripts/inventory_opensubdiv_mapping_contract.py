#!/usr/bin/env python3
"""Inventory the OpenSubdiv mapping-contract documentation anchors.

This helper is intentionally source-text based. It does not parse C++ or run
production code; it only records the docs/interface anchors that a future
OpenSubdiv backend PR must refresh before claiming the mapping contract is
satisfied.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


CONTRACT_DOC_PATH = Path("docs/opensubdiv_mapping_contract.md")
POLICY_DOC_PATH = Path("docs/opensubdiv_backend_interface_policy.md")
PROOF_MAP_DOC_PATH = Path("docs/irregular_subdivision_transpose_proof_map.md")
FORCE_DOC_PATH = Path("docs/force_formula_scatter_equivalence.md")
EVALUATOR_PATH = Path("include/mesh/Limit_surface_evaluator.hpp")


@dataclass(frozen=True)
class Anchor:
    category: str
    name: str
    path: Path
    needle: str
    detail: str


@dataclass(frozen=True)
class LocatedAnchor:
    anchor: Anchor
    line_number: int
    line: str


ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        "mapping contract",
        "contract document",
        CONTRACT_DOC_PATH,
        "OpenSubdiv Sample/Source-Id/Back-Projection Mapping Contract",
        "The dedicated contract doc is present.",
    ),
    Anchor(
        "mapping contract",
        "non-production boundary",
        CONTRACT_DOC_PATH,
        "This is a docs/scripts-only contract lane.",
        "The lane records that production behavior and dependency policy are unchanged.",
    ),
    Anchor(
        "mapping contract",
        "backend-neutral seam",
        CONTRACT_DOC_PATH,
        "seam remains",
        "The public seam stays in SLIMED row/source-id terms, not OpenSubdiv types.",
    ),
    Anchor(
        "row convention",
        "observed coordinate mapping",
        CONTRACT_DOC_PATH,
        "s=v,t=w",
        "The docs pin the observed regular OpenSubdiv-to-SLIMED coordinate mapping.",
    ),
    Anchor(
        "row convention",
        "du to first derivative v",
        CONTRACT_DOC_PATH,
        "`du` under the observed `s=v,t=w` mapping",
        "OpenSubdiv du maps to SLIMED d/dv before any production routing.",
    ),
    Anchor(
        "row convention",
        "duv mixed-row duplication",
        CONTRACT_DOC_PATH,
        "`duv`, if mixed-row duplication is reviewed",
        "The current two SLIMED mixed rows require an explicit reviewed convention.",
    ),
    Anchor(
        "source-id contract",
        "original SLIMED ids",
        CONTRACT_DOC_PATH,
        "Source ids at the public backend boundary must be original SLIMED vertex ids",
        "The backend may not expose transient OpenSubdiv patch-control indices as public force ids.",
    ),
    Anchor(
        "source-id contract",
        "row weight lookup",
        CONTRACT_DOC_PATH,
        "row_weight(SLIMED derivative row, original SLIMED vertex id)",
        "Future force code needs row weights keyed by SLIMED source id.",
    ),
    Anchor(
        "sample plan",
        "ptex face plan",
        CONTRACT_DOC_PATH,
        "child patches, sample coordinates",
        "A future backend must state the sample plan for one SLIMED face.",
    ),
    Anchor(
        "sample plan",
        "aggregate coverage caveat",
        CONTRACT_DOC_PATH,
        "aggregate all-ptex source visibility is useful evidence",
        "The docs distinguish aggregate source visibility from production scatter readiness.",
    ),
    Anchor(
        "back-projection",
        "transpose identity",
        CONTRACT_DOC_PATH,
        "g dot (W p) == (W^T g) dot p",
        "The linear transpose shape is documented.",
    ),
    Anchor(
        "back-projection",
        "actual production formulas",
        CONTRACT_DOC_PATH,
        "actual SLIMED bending, area, and volume force formulas",
        "Toy transpose evidence is not enough for production force routing.",
    ),
    Anchor(
        "scatter/reduction",
        "one-ring scatter",
        CONTRACT_DOC_PATH,
        "Face::oneRingVertices[j]",
        "The docs pin the current local-row-to-source-id scatter contract.",
    ),
    Anchor(
        "scatter/reduction",
        "thread-local reduction",
        CONTRACT_DOC_PATH,
        "thread-local force",
        "A backend must preserve or explicitly replace the current accumulation shape.",
    ),
    Anchor(
        "irregular boundary",
        "positive-depth 11 route",
        CONTRACT_DOC_PATH,
        "dependency-free positive-depth",
        "The current supported irregular route remains dependency-free.",
    ),
    Anchor(
        "irregular boundary",
        "11 split",
        CONTRACT_DOC_PATH,
        "11 = 4+3+4",
        "The docs retain the current narrow 11-control subdivision-matrix contract.",
    ),
    Anchor(
        "irregular boundary",
        "guarded unsupported cases",
        CONTRACT_DOC_PATH,
        "Zero-depth 11-control requests",
        "The mapping contract does not broaden guarded routes.",
    ),
    Anchor(
        "dependency policy",
        "default builds",
        CONTRACT_DOC_PATH,
        "Default builds remain OpenSubdiv-free.",
        "The contract does not alter build or dependency policy.",
    ),
    Anchor(
        "policy cross-reference",
        "mapping contract link from backend policy",
        POLICY_DOC_PATH,
        "docs/opensubdiv_mapping_contract.md",
        "The backend policy points reviewers to the focused mapping contract.",
    ),
    Anchor(
        "proof-map cross-reference",
        "mapping contract link from proof map",
        PROOF_MAP_DOC_PATH,
        "docs/opensubdiv_mapping_contract.md",
        "The irregular proof map points reviewers to the focused mapping contract.",
    ),
    Anchor(
        "force contract cross-reference",
        "mapping contract link from force/scatter doc",
        FORCE_DOC_PATH,
        "docs/opensubdiv_mapping_contract.md",
        "The force/scatter contract points reviewers to the focused mapping contract.",
    ),
    Anchor(
        "interface anchor",
        "weighted sample struct",
        EVALUATOR_PATH,
        "struct LimitSurfaceWeightedSample",
        "The backend-neutral weighted sample seam exists in the public evaluator interface.",
    ),
    Anchor(
        "interface anchor",
        "source id storage",
        EVALUATOR_PATH,
        "std::vector<int> sourceIds;",
        "The seam carries caller-visible SLIMED source ids.",
    ),
    Anchor(
        "interface anchor",
        "row weight storage",
        EVALUATOR_PATH,
        "Matrix rowWeights;",
        "The seam carries seven-row weights keyed by source id.",
    ),
    Anchor(
        "interface anchor",
        "weighted evaluator method",
        EVALUATOR_PATH,
        "virtual LimitSurfaceWeightedSample evaluate_weighted(",
        "The public evaluator method returns evaluated rows plus row weights.",
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
        "located": [
            {
                "category": item.anchor.category,
                "name": item.anchor.name,
                "path": item.anchor.path.as_posix(),
                "line": item.line_number,
                "source": item.line,
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
                "detail": item.detail,
            }
            for item in missing
        ],
    }


def print_text(located: Sequence[LocatedAnchor], missing: Sequence[Anchor]) -> None:
    print("# OpenSubdiv Mapping Contract Inventory")
    print()
    for item in located:
        print(f"- {item.anchor.category}: {item.anchor.name}")
        print(f"  source: {item.anchor.path}:{item.line_number} `{item.line}`")
        print(f"  contract: {item.anchor.detail}")
    if missing:
        print()
        print("## Missing anchors")
        for item in missing:
            print(f"- {item.category}: {item.name}: {item.path} missing `{item.needle}`")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit nonzero when an expected contract anchor is not found.",
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
