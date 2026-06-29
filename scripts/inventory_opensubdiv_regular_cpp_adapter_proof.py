#!/usr/bin/env python3
"""Inventory the experimental C++ regular OpenSubdiv adapter proof.

This helper is intentionally source-text based. It does not compile
OpenSubdiv or execute production force code. It verifies that the experimental
C++ proof stays opt-in and that default production build/routing surfaces do
not gain an OpenSubdiv dependency.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


CPP_PROOF_PATH = Path("experiments/opensubdiv_regular_cpp_adapter_proof.cpp")
WRAPPER_PATH = Path("scripts/run_opensubdiv_regular_cpp_adapter_proof.sh")
DOC_PATH = Path("docs/opensubdiv_regular_adapter_proof.md")
MAKEFILE_PATH = Path("Makefile")
PRODUCTION_PATHS = (
    Path("include"),
    Path("src"),
    Path("EXEs"),
    MAKEFILE_PATH,
)


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


CPP_PROOF_INVARIANTS: tuple[dict[str, str], ...] = (
    {"invariant": "proof-only kind", "needle": "test_only_regular_opensubdiv_cpp_adapter_proof"},
    {"invariant": "original source ids", "needle": "original_slimed_vertex_ids_not_backend_local_ids"},
    {"invariant": "duplicate aggregation", "needle": "row_weight(WeightedRow row, int sourceId) const"},
    {"invariant": "frozen sample coordinates", "needle": "frozen_regular_second_order_triangular_quadrature"},
    {"invariant": "quadrature formula factor", "needle": "0.5 * sample.weight"},
    {"invariant": "s=v,t=w convention", "needle": '\\"coordinate_mapping\\":\\"s=v,t=w\\"'},
    {"invariant": "seven derivative rows", "needle": '\\"adapter_row_count\\":7'},
    {"invariant": "duplicated mixed row convention", "needle": "MixedDerivativeWV"},
    {"invariant": "actual force rows", "needle": '\\"actual_force_rows\\":{'},
    {"invariant": "fBend evidence", "needle": '\\"max_abs_f_bend\\":'},
    {"invariant": "fArea evidence", "needle": '\\"max_abs_f_area\\":'},
    {"invariant": "fVolume evidence", "needle": '\\"max_abs_f_volume\\":'},
    {"invariant": "proof-only force algebra", "needle": "proof-only local copy of current bending, area, and volume force sample algebra"},
    {"invariant": "one-ring scatter identity", "needle": '\\"face_one_ring_scatter_identity\\":'},
    {"invariant": "not production routing", "needle": '\\"not_production_routing\\":true'},
)


ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        "c++ proof",
        "standalone experimental source",
        CPP_PROOF_PATH,
        "Experimental, review-gated OpenSubdiv regular adapter proof.",
        "The C++ proof source is explicitly marked experimental.",
    ),
    Anchor(
        "c++ proof",
        "proof-only kind",
        CPP_PROOF_PATH,
        "test_only_regular_opensubdiv_cpp_adapter_proof",
        "The emitted evidence is machine-readable and proof-only.",
    ),
    Anchor(
        "c++ proof",
        "weighted sample shape",
        CPP_PROOF_PATH,
        "LimitSurfaceWeightedSample-style seven rows keyed by original SLIMED source ids",
        "The proof surface is the SLIMED weighted-sample contract shape.",
    ),
    Anchor(
        "c++ proof",
        "source-id policy",
        CPP_PROOF_PATH,
        "original_slimed_vertex_ids_not_backend_local_ids",
        "The proof rejects backend-local ids at the public boundary.",
    ),
    Anchor(
        "c++ proof",
        "duplicate aggregation implementation",
        CPP_PROOF_PATH,
        "value += rowWeights[rowIndex][col];",
        "Duplicate source ids are summed deterministically.",
    ),
    Anchor(
        "c++ proof",
        "frozen sample coordinates",
        CPP_PROOF_PATH,
        "frozen_regular_samples",
        "The C++ proof uses the frozen regular quadrature rows.",
    ),
    Anchor(
        "c++ proof",
        "s=v,t=w convention",
        CPP_PROOF_PATH,
        "coordinate_mapping",
        "The C++ proof emits the OpenSubdiv-to-SLIMED coordinate convention.",
    ),
    Anchor(
        "c++ proof",
        "seven rows",
        CPP_PROOF_PATH,
        "std::array<const float *, 7>",
        "The C++ proof maps OpenSubdiv rows into seven SLIMED rows.",
    ),
    Anchor(
        "c++ proof",
        "duplicated mixed rows",
        CPP_PROOF_PATH,
        "stencil.GetDuvWeights(),",
        "The C++ proof maps OpenSubdiv duv into both mixed rows.",
    ),
    Anchor(
        "c++ proof",
        "actual force rows",
        CPP_PROOF_PATH,
        '\\"actual_force_rows\\"',
        "The C++ proof emits actual fBend/fArea/fVolume force-row evidence.",
    ),
    Anchor(
        "c++ proof",
        "proof-only force algebra",
        CPP_PROOF_PATH,
        "proof-only local copy of current bending, area, and volume force sample algebra",
        "The force formula evidence is explicitly scoped to the experimental proof.",
    ),
    Anchor(
        "c++ proof",
        "one-ring scatter identity",
        CPP_PROOF_PATH,
        "face_one_ring_scatter_identity",
        "The C++ proof records Face::oneRingVertices scatter identity.",
    ),
    Anchor(
        "wrapper",
        "explicit root gate",
        WRAPPER_PATH,
        "OPENSUBDIV_ROOT is not set",
        "The wrapper skips unless the caller explicitly supplies OPENSUBDIV_ROOT.",
    ),
    Anchor(
        "wrapper",
        "non-default compile",
        WRAPPER_PATH,
        "experiments/opensubdiv_regular_cpp_adapter_proof.cpp",
        "The wrapper compiles only the standalone experimental C++ proof.",
    ),
    Anchor(
        "wrapper",
        "OpenSubdiv library",
        WRAPPER_PATH,
        "-losdCPU",
        "The OpenSubdiv link is local to the explicit wrapper invocation.",
    ),
    Anchor(
        "docs",
        "c++ proof documented",
        DOC_PATH,
        "Experimental C++ Harness",
        "The adapter proof doc records the opt-in C++ proof boundary.",
    ),
    Anchor(
        "docs",
        "default build unchanged",
        DOC_PATH,
        "does not add a Makefile target",
        "The doc states that default build and production routing are unchanged.",
    ),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def locate_anchor(root: Path, anchor: Anchor) -> LocatedAnchor | None:
    path = root / anchor.path
    if not path.exists():
        return None
    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        if anchor.needle in line:
            return LocatedAnchor(anchor, line_number, line.strip())
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


def production_leaks(root: Path) -> list[str]:
    leaks: list[str] = []
    needles = ("opensubdiv", "OpenSubdiv", "OPENSUBDIV", "osdCPU")
    for path in PRODUCTION_PATHS:
        full_path = root / path
        files: list[Path]
        if full_path.is_dir():
            files = [candidate for candidate in full_path.rglob("*") if candidate.is_file()]
        else:
            files = [full_path]
        for candidate in files:
            text = read_text(candidate)
            for line_number, line in enumerate(text.splitlines(), start=1):
                if any(needle in line for needle in needles):
                    leaks.append(f"{candidate.relative_to(root)}:{line_number}:{line.strip()}")
    return leaks


def status_payload(root: Path) -> dict[str, object]:
    located, missing = collect_anchors(root)
    leaks = production_leaks(root)
    return {
        "anchors_checked": len(ANCHORS),
        "anchors_located": len(located),
        "missing": [
            {
                "category": anchor.category,
                "name": anchor.name,
                "path": str(anchor.path),
                "needle": anchor.needle,
            }
            for anchor in missing
        ],
        "production_open_subdiv_leaks": leaks,
        "passed": not missing and not leaks,
    }


def emit_report(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print("# OpenSubdiv Regular C++ Adapter Proof Inventory")
    print(f"anchors_checked: {payload['anchors_checked']}")
    print(f"anchors_located: {payload['anchors_located']}")
    print(f"production_open_subdiv_leaks: {len(payload['production_open_subdiv_leaks'])}")
    print(f"passed: {payload['passed']}")
    if payload["missing"]:
        print("\nmissing:")
        for item in payload["missing"]:
            print(f"- {item['path']} :: {item['needle']}")
    if payload["production_open_subdiv_leaks"]:
        print("\nproduction_open_subdiv_leaks:")
        for leak in payload["production_open_subdiv_leaks"]:
            print(f"- {leak}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory the opt-in experimental C++ OpenSubdiv adapter proof."
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Return non-zero if anchors are missing or production leaks are found.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = status_payload(repo_root())
    emit_report(payload, args.json)
    if args.check and not payload["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
