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
    Path(".github"),
    Path("scripts/verify_pr_ready.sh"),
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
    {"invariant": "production-call shadow", "needle": '\\"production_call_shadow\\":{'},
    {"invariant": "production coordinate input order", "needle": "coordOneRingVertices[j] copied from Face::oneRingVertices[j]"},
    {"invariant": "production force buffer layout", "needle": "fBend offsets 0..2, fArea offsets 3..5, fVolume offsets 6..8"},
    {"invariant": "production shadow pass flag", "needle": '\\"matches_current_regular_production_call_shape\\":'},
    {"invariant": "production helper dry run", "needle": '\\"production_helper_dry_run\\":{'},
    {"invariant": "production helper API", "needle": "Mesh::element_energy_force_regular"},
    {"invariant": "OpenSubdiv rows installed locally", "needle": '\\"open_subdiv_rows_used_as_local_shape_functions\\":true'},
    {"invariant": "default dependency unchanged", "needle": '\\"default_build_dependency_added\\":false'},
    {"invariant": "no production route installed", "needle": '\\"route_installed_in_production\\":false'},
    {"invariant": "production helper dry-run pass flag", "needle": '\\"matches_proof_local_formula_rows\\":'},
    {"invariant": "visible observable dry run", "needle": '\\"visible_observable_dry_run\\":{'},
    {"invariant": "visible observable production API", "needle": "Mesh::calculate_element_area_volume regular 12-control path"},
    {"invariant": "visible area evidence", "needle": '\\"production_area\\":'},
    {"invariant": "legacy visible volume evidence", "needle": '\\"production_legacy_visible_volume\\":'},
    {"invariant": "visible observable pass flag", "needle": '\\"matches_production_regular_area_volume\\":'},
    {"invariant": "serial OpenMP accumulation parity", "needle": '\\"serial_openmp_accumulation_parity\\":{'},
    {"invariant": "serial OpenMP production shape reference", "needle": "accumulate_membrane_face_energy_and_forces per-thread nVertices*9 buffers reduced by vertex, component, then thread index"},
    {"invariant": "serial OpenMP pass flag", "needle": '\\"matches_serial_openmp_accumulation_shape\\":'},
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
        "c++ proof",
        "production-call shadow",
        CPP_PROOF_PATH,
        '\\"production_call_shadow\\":{',
        "The C++ proof emits proof-local evidence matching the current regular production-call shape.",
    ),
    Anchor(
        "c++ proof",
        "production input order",
        CPP_PROOF_PATH,
        "coordOneRingVertices[j] copied from Face::oneRingVertices[j]",
        "The shadow evidence preserves the current production coordinate input order.",
    ),
    Anchor(
        "c++ proof",
        "production local force matrix shape",
        CPP_PROOF_PATH,
        '\\"local_force_matrix_rows\\":',
        "The shadow evidence records the 12x3 local force-row shape used before scatter.",
    ),
    Anchor(
        "c++ proof",
        "production force buffer layout",
        CPP_PROOF_PATH,
        "fBend offsets 0..2, fArea offsets 3..5, fVolume offsets 6..8",
        "The shadow evidence records the current 9-component vertex force-buffer layout.",
    ),
    Anchor(
        "c++ proof",
        "production shadow pass flag",
        CPP_PROOF_PATH,
        '\\"matches_current_regular_production_call_shape\\":',
        "The emitted report fails if the proof-local production-call shadow does not match.",
    ),
    Anchor(
        "c++ proof",
        "production helper dry run",
        CPP_PROOF_PATH,
        '\\"production_helper_dry_run\\":{',
        "The C++ proof emits proof-local parity evidence against Mesh::element_energy_force_regular.",
    ),
    Anchor(
        "c++ proof",
        "production helper dry-run API",
        CPP_PROOF_PATH,
        "Mesh::element_energy_force_regular",
        "The dry-run comparison names the current regular production helper.",
    ),
    Anchor(
        "c++ proof",
        "OpenSubdiv rows installed locally",
        CPP_PROOF_PATH,
        '\\"open_subdiv_rows_used_as_local_shape_functions\\":true',
        "OpenSubdiv-derived rows are installed only on a local Param for the proof call.",
    ),
    Anchor(
        "c++ proof",
        "production helper dry-run pass flag",
        CPP_PROOF_PATH,
        '\\"matches_proof_local_formula_rows\\":',
        "The emitted report fails if the production helper dry run diverges from the proof rows.",
    ),
    Anchor(
        "c++ proof",
        "visible observable dry run",
        CPP_PROOF_PATH,
        '\\"visible_observable_dry_run\\":{',
        "The C++ proof emits proof-local area/volume observable evidence.",
    ),
    Anchor(
        "c++ proof",
        "visible observable production API",
        CPP_PROOF_PATH,
        "Mesh::calculate_element_area_volume regular 12-control path",
        "The observable evidence names the current regular area/volume output path.",
    ),
    Anchor(
        "c++ proof",
        "legacy visible volume boundary",
        CPP_PROOF_PATH,
        "legacy visible volume preserves current regular area/volume x-component quadrature behavior",
        "The report labels the current legacy visible-volume convention precisely.",
    ),
    Anchor(
        "c++ proof",
        "serial OpenMP accumulation parity",
        CPP_PROOF_PATH,
        '\\"serial_openmp_accumulation_parity\\":{',
        "The C++ proof emits proof-local serial/OpenMP-style accumulation evidence.",
    ),
    Anchor(
        "c++ proof",
        "serial OpenMP production shape reference",
        CPP_PROOF_PATH,
        "accumulate_membrane_face_energy_and_forces per-thread nVertices*9 buffers reduced by vertex, component, then thread index",
        "The accumulation parity evidence names the current production buffer/reduction shape.",
    ),
    Anchor(
        "c++ proof",
        "serial OpenMP pass flag",
        CPP_PROOF_PATH,
        '\\"matches_serial_openmp_accumulation_shape\\":',
        "The emitted report fails if proof-local serial and OpenMP-style accumulation diverge.",
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
        "The wrapper compiles the experimental proof binary only on explicit invocation.",
    ),
    Anchor(
        "wrapper",
        "production sources linked only in wrapper",
        WRAPPER_PATH,
        "repo_sources",
        "Production sources are linked only into the opt-in temporary proof binary.",
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
    Anchor(
        "docs",
        "production shadow documented",
        DOC_PATH,
        "Production-Call Shadow Evidence",
        "The doc records that this lane compares against production call shape without routing production through OpenSubdiv.",
    ),
    Anchor(
        "docs",
        "production helper dry run documented",
        DOC_PATH,
        "Production-Helper Dry-Run Evidence",
        "The doc records the proof-local production helper dry-run boundary.",
    ),
    Anchor(
        "docs",
        "visible observable dry run documented",
        DOC_PATH,
        "Visible Observable Dry-Run Evidence",
        "The doc records proof-local output-visible area/volume evidence.",
    ),
    Anchor(
        "docs",
        "serial OpenMP accumulation documented",
        DOC_PATH,
        "Serial/OpenMP Accumulation Parity Evidence",
        "The doc records proof-local serial/OpenMP-style accumulation parity evidence.",
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
        elif full_path.is_file():
            files = [full_path]
        else:
            continue
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
