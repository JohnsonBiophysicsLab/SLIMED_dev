#!/usr/bin/env python3
"""Inventory post-PR61 irregular routing evidence anchors.

This helper is intentionally source-text based. It does not parse or execute
production C++; it records the current support/guard/evidence matrix for the
11-control irregular membrane force route so reviewers can see when later
changes move an expected characterization anchor.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


IMPLEMENTATION_PATH = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
MESH_PATH = Path("src/mesh/Mesh.cpp")
LIMIT_SURFACE_PATH = Path("include/mesh/Limit_surface_evaluator.hpp")
SURFACE_TEST_PATH = Path("tests/test_surface_geometry_characterization.cpp")
FIXTURE_DOC_PATH = Path("docs/irregular_patch_fixture_requirements.md")
PROOF_MAP_DOC_PATH = Path("docs/irregular_subdivision_transpose_proof_map.md")
BROADER_VALENCE_DOC_PATH = Path("docs/irregular_broader_valence_inventory.md")


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


ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        "production support",
        "positive-depth 11-control route preflight",
        IMPLEMENTATION_PATH,
        "assert_supported_membrane_force_routing(mesh);",
        "supported route entry guard",
        "The membrane force path checks unsupported irregular requests before the face loop.",
    ),
    Anchor(
        "production support",
        "positive-depth 11-control route call",
        IMPLEMENTATION_PATH,
        "mesh.element_energy_force_irregular_11(coordOneRingVertices,",
        "supported route implementation",
        "The 11-control route calls the dedicated irregular helper instead of falling through to the regular helper.",
    ),
    Anchor(
        "production support",
        "subdivision-depth loop",
        IMPLEMENTATION_PATH,
        "for (int depth = 0; depth < param.subDivideTimes; ++depth)",
        "supported route implementation",
        "The irregular helper iterates over the configured positive subdivision depth.",
    ),
    Anchor(
        "production support",
        "child force back-projection",
        IMPLEMENTATION_PATH,
        "add_back_projected_child_force(childToOriginal, childFBend, fBend);",
        "supported route implementation",
        "Regular child-patch force rows are transposed back onto the 11 original rows.",
    ),
    Anchor(
        "guard",
        "zero-depth 11-control diagnostic",
        IMPLEMENTATION_PATH,
        "11-control one-ring patches require Param::subDivideTimes > 0",
        "guarded unsupported route",
        "Zero-depth 11-control force requests are rejected with an explicit diagnostic.",
    ),
    Anchor(
        "guard",
        "regular fallback disabled diagnostic",
        IMPLEMENTATION_PATH,
        "regular 12-control force fallback remains disabled",
        "guarded unsupported route",
        "Unsupported irregular force requests cannot silently reuse the regular 12-control helper.",
    ),
    Anchor(
        "guard",
        "regular evaluator rejects irregular control count",
        SURFACE_TEST_PATH,
        "SlimedLoopRegularPatchRejectsIrregularControlCount",
        "guard characterized by test",
        "The regular limit-surface evaluator remains a 12-control backend.",
    ),
    Anchor(
        "test evidence",
        "synthetic irregular area/volume fixture",
        SURFACE_TEST_PATH,
        "SyntheticIrregularPatchAreaVolumeUsesSubdivisionFixture",
        "current synthetic evidence",
        "The public area/volume route is checked against test-side irregular subdivision matrices.",
    ),
    Anchor(
        "test evidence",
        "zero-depth irregular force guard",
        SURFACE_TEST_PATH,
        "SyntheticIrregularPatchEnergyForceRequiresSubdivisionDepth",
        "current synthetic evidence",
        "The zero-depth force guard is checked before any regular fallback can run.",
    ),
    Anchor(
        "test evidence",
        "positive-depth irregular force back-projection",
        SURFACE_TEST_PATH,
        "SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces",
        "current synthetic evidence",
        "The production 11-control route is checked against test-side child regular forces and transpose back-projection.",
    ),
    Anchor(
        "preservation evidence",
        "serial/OpenMP executable tolerance baseline",
        FIXTURE_DOC_PATH,
        "of `1.4210854715202004e-14`.",
        "resolved narrow evidence",
        "The approved 11-control stand-in has an actual serial/OpenMP executable baseline under the reviewed tolerance.",
    ),
    Anchor(
        "guard",
        "broader extraordinary-valence diagnostic",
        MESH_PATH,
        "Broader-valence routing remains disabled.",
        "guarded unsupported route",
        "Unsupported physical one-rings fail before geometry or force state is mutated.",
    ),
    Anchor(
        "test evidence",
        "broader extraordinary-valence diagnostic test",
        SURFACE_TEST_PATH,
        "UnsupportedBroaderValenceFailsBeforeGeometryMutation",
        "guard characterized by test",
        "The public geometry entry point rejects an empty physical one-ring before mutation.",
    ),
    Anchor(
        "documented gap",
        "OpenSubdiv remains observational",
        PROOF_MAP_DOC_PATH,
        "OpenSubdiv evidence remains observational",
        "remaining evidence gap",
        "OpenSubdiv-backed replacement still needs an approved sample/source-id/back-projection plan.",
    ),
    Anchor(
        "preservation evidence",
        "approved representative 11-control fixture",
        FIXTURE_DOC_PATH,
        "`data/fixtures/closed_valence5`",
        "resolved narrow evidence",
        "The approved serialized closed valence-5 stand-in supplies the representative positive-depth 11-control fixture.",
    ),
    Anchor(
        "dependency boundary",
        "regular evaluator boundary",
        LIMIT_SURFACE_PATH,
        "Irregular 11-control patches are",
        "no backend/dependency change",
        "The in-tree regular evaluator contract does not become a broad irregular backend.",
    ),
)


ROUTE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "route": "regular 12-control membrane force",
        "current_behavior": "supported",
        "evidence": "regular evaluator/scatter characterization tests",
        "remaining_gap": "preserve regular baselines when any backend changes",
    },
    {
        "route": "11-control membrane force with Param::subDivideTimes > 0",
        "current_behavior": "supported narrowly",
        "evidence": "synthetic transpose tests plus approved closed valence-5 fixture and actual serial/OpenMP executable parity",
        "remaining_gap": "preserve the approved fixture and 1.0e-10 executable tolerance baseline",
    },
    {
        "route": "11-control membrane force with Param::subDivideTimes <= 0",
        "current_behavior": "guarded unsupported",
        "evidence": "zero-depth diagnostic test",
        "remaining_gap": "none for current guard; policy change would need review",
    },
    {
        "route": "other irregular force topologies",
        "current_behavior": "guarded unsupported/not broadened",
        "evidence": "generated closed topology inventory plus fail-loud production geometry preflight",
        "remaining_gap": "separate scientific fixture, expected outputs, source mapping, and backend policy",
    },
    {
        "route": "OpenSubdiv-backed irregular replacement",
        "current_behavior": "not production",
        "evidence": "observational proof-map docs/probe only",
        "remaining_gap": "dependency policy, sample plan, source-id map, force equivalence",
    },
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
        "route_matrix": list(ROUTE_MATRIX),
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
    print("# Irregular Routing Evidence Inventory")
    print()
    print("## Route matrix")
    for row in ROUTE_MATRIX:
        print(f"- {row['route']}")
        print(f"  current_behavior: {row['current_behavior']}")
        print(f"  evidence: {row['evidence']}")
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
