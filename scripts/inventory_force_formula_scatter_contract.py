#!/usr/bin/env python3
"""Inventory the current regular force formula and scatter contract.

This helper is intentionally source-text based. It does not parse C++ or run
production code; it only records the implementation anchors that a future
OpenSubdiv force backend must preserve or deliberately replace after review.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


IMPLEMENTATION_PATH = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
EVALUATOR_PATH = Path("include/mesh/Limit_surface_evaluator.hpp")


@dataclass(frozen=True)
class Anchor:
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
        "thread-local membrane force component buffer",
        IMPLEMENTATION_PATH,
        "std::vector<std::vector<double>> faceForceComponents",
        "Per OpenMP thread, forces are accumulated in flat vertex-major buffers with 9 components per vertex.",
    ),
    Anchor(
        "face loop parallel shape",
        IMPLEMENTATION_PATH,
        "#pragma omp parallel for",
        "The membrane face loop is OpenMP-parallel when OMP is enabled and serial otherwise.",
    ),
    Anchor(
        "regular force helper call",
        IMPLEMENTATION_PATH,
        "mesh.element_energy_force_regular(coordOneRingVertices,",
        "Regular 12-control faces call the existing force formula helper with one-ring coordinates in face.oneRingVertices order.",
    ),
    Anchor(
        "irregular force fallback call",
        IMPLEMENTATION_PATH,
        "//@todo energy force irregular",
        "The 11-control branch remains a known fallback into the regular helper, not an approved irregular force contract.",
    ),
    Anchor(
        "local row to vertex id",
        IMPLEMENTATION_PATH,
        "int iVertex = face.oneRingVertices[j];",
        "Local force row j scatters to the mesh vertex id stored in face.oneRingVertices[j].",
    ),
    Anchor(
        "curvature component scatter",
        IMPLEMENTATION_PATH,
        "localForceComponents[baseIndex + axis] += fBend(j, axis);",
        "fBend rows accumulate into the first three per-vertex force buffer components.",
    ),
    Anchor(
        "area component scatter",
        IMPLEMENTATION_PATH,
        "localForceComponents[baseIndex + 3 + axis] += fArea(j, axis);",
        "fArea rows accumulate into the middle three per-vertex force buffer components.",
    ),
    Anchor(
        "volume component scatter",
        IMPLEMENTATION_PATH,
        "localForceComponents[baseIndex + 6 + axis] += fVol(j, axis);",
        "fVol rows accumulate into the last three per-vertex force buffer components.",
    ),
    Anchor(
        "thread reduction order",
        IMPLEMENTATION_PATH,
        "for (int threadIndex = 0; threadIndex < nThreads; ++threadIndex)",
        "Per-vertex reductions visit thread buffers in ascending thread index before writing Vertex::force components.",
    ),
    Anchor(
        "regular evaluator guard",
        IMPLEMENTATION_PATH,
        "matOneRingVertices.nrow() == limitSurfaceEvaluator.regular_patch_control_point_count();",
        "The evaluator path is used exactly for the regular 12-control local matrix shape.",
    ),
    Anchor(
        "position row copy",
        IMPLEMENTATION_PATH,
        "copy_column_vector(evaluation.position, x);",
        "Evaluator row 0 provides the position term used by volume force.",
    ),
    Anchor(
        "first derivative v row copy",
        IMPLEMENTATION_PATH,
        "copy_column_vector(evaluation.firstDerivativeV, a_1);",
        "Evaluator row 1 provides a_1, used by bending, area, and volume terms.",
    ),
    Anchor(
        "first derivative w row copy",
        IMPLEMENTATION_PATH,
        "copy_column_vector(evaluation.firstDerivativeW, a_2);",
        "Evaluator row 2 provides a_2, used by bending, area, and volume terms.",
    ),
    Anchor(
        "second derivative vv row copy",
        IMPLEMENTATION_PATH,
        "copy_column_vector(evaluation.secondDerivativeVV, a_11);",
        "Evaluator row 3 contributes to bending via normal/basis derivative formulas and da1.",
    ),
    Anchor(
        "second derivative ww row copy",
        IMPLEMENTATION_PATH,
        "copy_column_vector(evaluation.secondDerivativeWW, a_22);",
        "Evaluator row 4 contributes to bending via normal/basis derivative formulas and da2.",
    ),
    Anchor(
        "mixed derivative vw row copy",
        IMPLEMENTATION_PATH,
        "copy_column_vector(evaluation.mixedDerivativeVW, a_12);",
        "Evaluator row 5 contributes to bending via xa_2 and da2.",
    ),
    Anchor(
        "mixed derivative wv row copy",
        IMPLEMENTATION_PATH,
        "copy_column_vector(evaluation.mixedDerivativeWV, a_21);",
        "Evaluator row 6 contributes to bending via xa_1 and da1.",
    ),
    Anchor(
        "bending local force output",
        IMPLEMENTATION_PATH,
        "f_be.set_row_from_col(j, tempf_be, 0);",
        "Bending writes one local force row for each of the 12 controls before quadrature weighting.",
    ),
    Anchor(
        "area local force output",
        IMPLEMENTATION_PATH,
        "f_cons.set_row_from_col(j, tempf_cons, 0);",
        "Area constraint writes one local force row for each of the 12 controls before quadrature weighting.",
    ),
    Anchor(
        "volume local force output",
        IMPLEMENTATION_PATH,
        "f_conv.set_row_from_col(j, tempf_conv, 0);",
        "Volume constraint writes one local force row for each of the 12 controls before quadrature weighting.",
    ),
    Anchor(
        "quadrature accumulation",
        IMPLEMENTATION_PATH,
        "fBend += halfGaussQuadratureCoeff * f_be;",
        "Local force matrices accumulate in quadrature-sample order with 0.5 * gauss weight.",
    ),
    Anchor(
        "limit-surface derivative enum",
        EVALUATOR_PATH,
        "enum class LimitSurfaceDerivativeRow",
        "The evaluator contract names the seven row semantics used by the production force formula.",
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
                "name": item.name,
                "path": item.path.as_posix(),
                "needle": item.needle,
                "detail": item.detail,
            }
            for item in missing
        ],
    }


def print_text(located: Sequence[LocatedAnchor], missing: Sequence[Anchor]) -> None:
    print("# Regular Force Formula And Scatter Contract Inventory")
    print()
    for item in located:
        print(f"- {item.anchor.name}")
        print(f"  source: {item.anchor.path}:{item.line_number} `{item.line}`")
        print(f"  contract: {item.anchor.detail}")
    if missing:
        print()
        print("## Missing anchors")
        for item in missing:
            print(f"- {item.name}: {item.path} missing `{item.needle}`")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit nonzero when an expected contract anchor is not found.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    located, missing = collect_anchors(repo_root())
    if args.json:
        print(json.dumps(as_dicts(located, missing), indent=2, sort_keys=True))
    else:
        print_text(located, missing)
    return 1 if missing and args.fail_on_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
