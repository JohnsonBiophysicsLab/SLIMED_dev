#!/usr/bin/env python3
"""Inventory the 11-control serial/OpenMP tolerance characterization lane.

This helper is source-text based and inert. It does not parse, compile, or run
production C++; it records the anchors that define what can be characterized
today for the supported positive-depth 11-control route.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


IMPLEMENTATION_PATH = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
SURFACE_TEST_PATH = Path("tests/test_surface_geometry_characterization.cpp")
FIXTURE_DISCOVERY_DOC_PATH = Path("docs/irregular_fixture_discovery_report.md")
TOLERANCE_DOC_PATH = Path("docs/irregular_serial_omp_tolerance_characterization.md")


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
        "production shape",
        "thread-local membrane buffer",
        IMPLEMENTATION_PATH,
        "std::vector<std::vector<double>> faceForceComponents",
        "The production membrane lane stores per-thread force components in vertex-major nine-component buffers.",
    ),
    Anchor(
        "production shape",
        "ascending thread reduction",
        IMPLEMENTATION_PATH,
        "for (int threadIndex = 0; threadIndex < nThreads; ++threadIndex)",
        "Thread buffers reduce in ascending thread-index order before writing vertex force components.",
    ),
    Anchor(
        "production shape",
        "supported 11-control call",
        IMPLEMENTATION_PATH,
        "mesh.element_energy_force_irregular_11(coordOneRingVertices,",
        "The supported irregular force route is still the existing positive-depth 11-control helper.",
    ),
    Anchor(
        "production shape",
        "child force transpose",
        IMPLEMENTATION_PATH,
        "add_back_projected_child_force(childToOriginal, childFBend, fBend);",
        "Regular child force rows transpose back onto the original 11 controls before scatter.",
    ),
    Anchor(
        "test evidence",
        "serial/OpenMP-compatible tolerance envelope test",
        SURFACE_TEST_PATH,
        "SyntheticIrregularPatchSerialOpenMpReductionToleranceEnvelope",
        "The test-side lane compares serial-like and OpenMP-compatible reduction orders using synthetic 11-control route outputs.",
    ),
    Anchor(
        "test evidence",
        "force tolerance constant",
        SURFACE_TEST_PATH,
        "constexpr double forceTolerance = 1.0e-10;",
        "The synthetic split-reduction comparison uses an explicit force-component tolerance.",
    ),
    Anchor(
        "fixture boundary",
        "no checked-in physical 11-control fixture",
        FIXTURE_DISCOVERY_DOC_PATH,
        "No checked-in physical 11-control candidate is currently discoverable",
        "The current lane cannot claim a representative production scientific fixture.",
    ),
    Anchor(
        "fixture boundary",
        "generated topology is not production fixture",
        FIXTURE_DISCOVERY_DOC_PATH,
        "This generated probe is not a production scientific fixture.",
        "The generated closed icosahedron remains topology-only evidence.",
    ),
    Anchor(
        "documentation",
        "tolerance characterization report",
        TOLERANCE_DOC_PATH,
        "This is a tests/docs/scripts-only characterization lane.",
        "The report states the non-production scope and the evidence limits.",
    ),
    Anchor(
        "documentation",
        "no production behavior change statement",
        TOLERANCE_DOC_PATH,
        "No production C++ behavior, build policy, dependencies, OpenSubdiv integration,",
        "The report explicitly records the boundaries requested for this lane.",
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
    print("# Irregular Serial/OpenMP Tolerance Inventory")
    print()
    for item in located:
        print(f"- {item.anchor.category}: {item.anchor.name}")
        print(f"  source: {item.anchor.path}:{item.line_number} `{item.line}`")
        print(f"  detail: {item.anchor.detail}")
    if missing:
        print()
        print("## Missing anchors")
        for item in missing:
            print(f"- {item.category}: {item.name}: {item.path} missing `{item.needle}`")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--check", action="store_true", help="Exit nonzero if an anchor is missing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    located, missing = collect_anchors(repo_root())
    if args.json:
        print(json.dumps(as_dicts(located, missing), indent=2, sort_keys=True))
    else:
        print_text(located, missing)
    return 1 if args.check and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
