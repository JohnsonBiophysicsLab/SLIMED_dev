#!/usr/bin/env python3
"""Inventory regular OpenSubdiv backend-adapter readiness anchors.

This helper is intentionally source-text based. It does not parse C++, compile
OpenSubdiv, or execute production force code. It records the checklist a
regular OpenSubdiv-backed adapter must satisfy before any broader production
route can consume OpenSubdiv-derived samples or rows.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


ADAPTER_DOC_PATH = Path("docs/opensubdiv_regular_backend_adapter_readiness.md")
PROOF_DOC_PATH = Path("docs/opensubdiv_regular_adapter_proof.md")
SAMPLE_PLAN_DOC_PATH = Path("docs/opensubdiv_regular_sample_plan.md")
READINESS_DOC_PATH = Path("docs/opensubdiv_routing_readiness_map.md")
MAPPING_DOC_PATH = Path("docs/opensubdiv_mapping_contract.md")
FORCE_EVIDENCE_DOC_PATH = Path("docs/opensubdiv_force_transpose_evidence.md")
FORCE_SCATTER_DOC_PATH = Path("docs/force_formula_scatter_equivalence.md")
POLICY_DOC_PATH = Path("docs/opensubdiv_backend_interface_policy.md")
EVALUATOR_HEADER_PATH = Path("include/mesh/Limit_surface_evaluator.hpp")
EVALUATOR_IMPL_PATH = Path("src/mesh/Limit_surface_evaluator.cpp")
OPENSUBDIV_EVALUATOR_IMPL_PATH = Path("src/mesh/OpenSubdiv_regular_evaluator.cpp")
PROBE_PATH = Path("scripts/probe_opensubdiv_feasibility.py")
WRAPPER_PATH = Path("scripts/run_opensubdiv_probe.sh")
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


EVIDENCE_LINEAGE: tuple[dict[str, str], ...] = (
    {
        "lane": "PR #68 weighted-sample seam",
        "anchor": "LimitSurfaceEvaluator::evaluate_weighted(...)",
        "adapter_meaning": "review adapter rows at a backend-neutral source-id boundary",
    },
    {
        "lane": "PR #69 mapping contract",
        "anchor": "docs/opensubdiv_mapping_contract.md",
        "adapter_meaning": "state coordinate, row-order, source-id, and transpose boundaries",
    },
    {
        "lane": "PR #72 regular actual-force evidence",
        "anchor": "docs/opensubdiv_force_transpose_evidence.md",
        "adapter_meaning": "treat probe smoke as prerequisite evidence, not routing",
    },
    {
        "lane": "PR #73 routing readiness map",
        "anchor": "docs/opensubdiv_routing_readiness_map.md",
        "adapter_meaning": "keep regular production routing behind reviewer gates",
    },
    {
        "lane": "PR #74 regular sample plan",
        "anchor": "docs/opensubdiv_regular_sample_plan.md",
        "adapter_meaning": "match the frozen regular sample plan or review-replace it",
    },
    {
        "lane": "PR #75 regular backend readiness",
        "anchor": "docs/opensubdiv_regular_backend_adapter_readiness.md",
        "adapter_meaning": "keep regular adapter proof work review-gated and non-production",
    },
    {
        "lane": "PR #76 through PR #82 proof lane",
        "anchor": "--regular-adapter-proof-report and run_opensubdiv_regular_cpp_adapter_proof.sh",
        "adapter_meaning": "emit test-only regular adapter, production-helper, visible-observable, and serial/OpenMP-style proof evidence through original SLIMED source ids",
    },
    {
        "lane": "Guarded production regular seam",
        "anchor": "diagnose_opensubdiv_regular_row_semantics and USE_OPENSUBDIV_REGULAR=1",
        "adapter_meaning": "compile and diagnose the guarded seam while keeping OpenSubdiv-derived rows disabled until routed semantics match",
    },
)


ADAPTER_READINESS_CHECKLIST: tuple[dict[str, str], ...] = (
    {
        "gate": "regular sample coordinates and quadrature order",
        "must_prove": "frozen sample rows, weights, and half-weight formula factors",
        "current_status": "characterized; guarded seam falls back to direct route",
    },
    {
        "gate": "coordinate and derivative convention",
        "must_prove": "s=v,t=w, orientation, seven rows, and duplicated mixed rows",
        "current_status": "characterized; guarded seam falls back to direct route",
    },
    {
        "gate": "original source-id order",
        "must_prove": "row weights keyed by original SLIMED ids in Face::oneRingVertices order",
        "current_status": "in-tree seam and opt-in row diagnostics characterized; OpenSubdiv production rows disabled",
    },
    {
        "gate": "deterministic duplicate aggregation",
        "must_prove": "duplicate original source ids are summed before comparison",
        "current_status": "in-tree seam characterized, not OpenSubdiv production routing",
    },
    {
        "gate": "actual force rows",
        "must_prove": "OpenSubdiv-derived rows compare through fBend, fArea, and fVolume",
        "current_status": "test-only adapter proof exists; production route disabled after semantics drift",
    },
    {
        "gate": "regular production helper dry run",
        "must_prove": "OpenSubdiv-derived rows compare against Mesh::element_energy_force_regular without installing a production route",
        "current_status": "proof-local dry-run evidence exists; routed rows disabled at production call sites",
    },
    {
        "gate": "output-visible state",
        "must_prove": "energies, normals, mean curvature, area, and legacy volume at production timing",
        "current_status": "proof-local visible-observable dry run exists; runtime opt-in fallback preserves direct path",
    },
    {
        "gate": "scatter and reduction",
        "must_prove": "Face::oneRingVertices scatter and current serial/OpenMP accumulation shape",
        "current_status": "test-only scatter identity and serial/OpenMP-style accumulation parity exist; production serial/OpenMP evidence remains required",
    },
    {
        "gate": "dependency-present behavior",
        "must_prove": "OpenSubdiv-present evidence stays OPENSUBDIV_ROOT-gated and opt-in",
        "current_status": "required boundary remains unchanged",
    },
    {
        "gate": "dependency-absent behavior",
        "must_prove": "missing OpenSubdiv skips probes and never changes production physics",
        "current_status": "required boundary remains unchanged",
    },
    {
        "gate": "production review gate",
        "must_prove": "separate reviewed PR before broader routing uses OpenSubdiv-derived rows",
        "current_status": "regular 12-control seam installed; routed rows disabled",
    },
)


ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        "adapter checklist",
        "dedicated checklist",
        ADAPTER_DOC_PATH,
        "OpenSubdiv Regular Backend Adapter Readiness Checklist",
        "adapter readiness",
        "The dedicated regular adapter-readiness checklist is present.",
    ),
    Anchor(
        "adapter checklist",
        "guarded production boundary",
        ADAPTER_DOC_PATH,
        "first explicitly guarded regular production",
        "policy boundary",
        "The checklist records the guarded regular seam and unchanged defaults.",
    ),
    Anchor(
        "adapter checklist",
        "guarded seam gate",
        ADAPTER_DOC_PATH,
        "The production seam is opt-in twice",
        "policy boundary",
        "The checklist records compile-time and runtime gates.",
    ),
    Anchor(
        "adapter checklist",
        "guarded seam row diagnostics",
        ADAPTER_DOC_PATH,
        "diagnose_opensubdiv_regular_row_semantics",
        "opt-in row diagnostics",
        "The checklist records the guarded seam row-semantic diagnostic.",
    ),
    Anchor(
        "adapter checklist",
        "PR68 lineage",
        ADAPTER_DOC_PATH,
        "PR #68 weighted-sample seam",
        "evidence lineage",
        "The checklist ties the adapter boundary to the weighted-sample seam.",
    ),
    Anchor(
        "adapter checklist",
        "PR69 lineage",
        ADAPTER_DOC_PATH,
        "PR #69 mapping contract",
        "evidence lineage",
        "The checklist ties the adapter boundary to the mapping contract.",
    ),
    Anchor(
        "adapter checklist",
        "PR72 lineage",
        ADAPTER_DOC_PATH,
        "PR #72 regular actual-force evidence",
        "evidence lineage",
        "The checklist ties the adapter boundary to regular actual-force smoke evidence.",
    ),
    Anchor(
        "adapter checklist",
        "PR73 lineage",
        ADAPTER_DOC_PATH,
        "PR #73 routing readiness map",
        "evidence lineage",
        "The checklist ties the adapter boundary to the routing readiness map.",
    ),
    Anchor(
        "adapter checklist",
        "PR74 lineage",
        ADAPTER_DOC_PATH,
        "PR #74 regular sample plan",
        "evidence lineage",
        "The checklist ties the adapter boundary to the frozen regular sample plan.",
    ),
    Anchor(
        "adapter checklist",
        "PR75 lineage",
        ADAPTER_DOC_PATH,
        "PR #75 regular backend readiness",
        "evidence lineage",
        "The checklist ties the proof lane to the regular adapter-readiness gate.",
    ),
    Anchor(
        "adapter checklist",
        "current proof lineage",
        ADAPTER_DOC_PATH,
        "PR #76 through PR #82 proof lane",
        "evidence lineage",
        "The checklist ties the proof lane to the opt-in regular adapter proof report.",
    ),
    Anchor(
        "adapter checklist",
        "weighted sample public result",
        ADAPTER_DOC_PATH,
        "public sample result is the existing seven-row",
        "adapter boundary",
        "The checklist keeps the adapter public surface in SLIMED weighted-sample terms.",
    ),
    Anchor(
        "adapter checklist",
        "source id boundary",
        ADAPTER_DOC_PATH,
        "row weights are keyed by original SLIMED source ids",
        "adapter boundary",
        "The checklist requires original SLIMED source ids at the adapter boundary.",
    ),
    Anchor(
        "adapter checklist",
        "sample coordinate boundary",
        ADAPTER_DOC_PATH,
        "sample coordinate: SLIMED v,w,u row",
        "adapter boundary",
        "The adapter boundary starts from the frozen SLIMED sample coordinates.",
    ),
    Anchor(
        "adapter checklist",
        "seven rows",
        ADAPTER_DOC_PATH,
        "d2/dv2, d2/dw2, d2/dvdw, d2/dwdv",
        "row contract",
        "The checklist requires all seven derivative rows.",
    ),
    Anchor(
        "adapter checklist",
        "one-ring source order",
        ADAPTER_DOC_PATH,
        "source order: Face::oneRingVertices[j]",
        "source-id order",
        "The checklist requires the regular one-ring order at the public boundary.",
    ),
    Anchor(
        "adapter checklist",
        "duplicate aggregation",
        ADAPTER_DOC_PATH,
        "Deterministic duplicate aggregation",
        "source-id aggregation",
        "The checklist requires deterministic duplicate source-id aggregation.",
    ),
    Anchor(
        "adapter checklist",
        "regular actual force rows",
        ADAPTER_DOC_PATH,
        "actual `fBend`, `fArea`, and `fVolume`",
        "actual force evidence",
        "The checklist requires actual force-row comparison before routing.",
    ),
    Anchor(
        "adapter checklist",
        "regular production helper dry run",
        ADAPTER_DOC_PATH,
        "Regular production helper dry run",
        "production helper evidence",
        "The checklist records the proof-local dry-run comparison against the current regular production helper.",
    ),
    Anchor(
        "adapter proof",
        "dedicated proof doc",
        PROOF_DOC_PATH,
        "OpenSubdiv Regular Adapter Proof",
        "test-only proof",
        "The dedicated regular adapter-proof document is present.",
    ),
    Anchor(
        "adapter proof",
        "non-production boundary",
        PROOF_DOC_PATH,
        "docs/scripts/tests/experiments-only proof lane",
        "policy boundary",
        "The proof document records that production behavior and default build policy are unchanged.",
    ),
    Anchor(
        "adapter proof",
        "production helper dry-run evidence",
        PROOF_DOC_PATH,
        "Production-Helper Dry-Run Evidence",
        "production helper evidence",
        "The proof document records the proof-local production helper dry-run boundary.",
    ),
    Anchor(
        "adapter proof",
        "proof kind",
        PROOF_DOC_PATH,
        "test_only_regular_opensubdiv_adapter_proof",
        "test-only proof",
        "The proof document records the machine-readable report kind.",
    ),
    Anchor(
        "adapter proof",
        "original source ids",
        PROOF_DOC_PATH,
        "original SLIMED vertex ids",
        "source-id contract",
        "The proof document requires original SLIMED ids at the report boundary.",
    ),
    Anchor(
        "adapter proof",
        "duplicate aggregation",
        PROOF_DOC_PATH,
        "deterministic duplicate source-id aggregation",
        "source-id aggregation",
        "The proof document records duplicate aggregation evidence.",
    ),
    Anchor(
        "adapter proof",
        "actual force rows",
        PROOF_DOC_PATH,
        "`fBend`, `fArea`, and `fVolume` row evidence",
        "actual force evidence",
        "The proof document records actual force-row evidence.",
    ),
    Anchor(
        "adapter proof",
        "one-ring scatter identity",
        PROOF_DOC_PATH,
        "`Face::oneRingVertices` scatter identity",
        "scatter contract",
        "The proof document records one-ring scatter identity evidence.",
    ),
    Anchor(
        "adapter checklist",
        "dependency present absent",
        ADAPTER_DOC_PATH,
        "Dependency-present behavior",
        "dependency boundary",
        "The checklist distinguishes OpenSubdiv-present behavior.",
    ),
    Anchor(
        "adapter checklist",
        "dependency absent",
        ADAPTER_DOC_PATH,
        "Dependency-absent behavior",
        "dependency boundary",
        "The checklist distinguishes OpenSubdiv-absent behavior.",
    ),
    Anchor(
        "adapter checklist",
        "prototype stop boundary",
        ADAPTER_DOC_PATH,
        "The next safe implementation step",
        "prototype boundary",
        "The checklist states that a future prototype remains inert unless separately reviewed.",
    ),
    Anchor(
        "sample plan",
        "dedicated sample plan",
        SAMPLE_PLAN_DOC_PATH,
        "OpenSubdiv Regular 12-Control Sample Plan",
        "sample plan",
        "The frozen regular sample-plan document exists.",
    ),
    Anchor(
        "sample plan",
        "s equals v t equals w",
        SAMPLE_PLAN_DOC_PATH,
        "The regular comparison convention is `s=v,t=w`.",
        "derivative convention",
        "The sample plan freezes the regular OpenSubdiv comparison convention.",
    ),
    Anchor(
        "sample plan",
        "duplicated mixed rows",
        SAMPLE_PLAN_DOC_PATH,
        "Rows 5 and 6 currently duplicate the mixed derivative",
        "row contract",
        "The sample plan freezes the duplicated mixed-row convention.",
    ),
    Anchor(
        "routing readiness",
        "dedicated readiness map",
        READINESS_DOC_PATH,
        "OpenSubdiv Production-Routing Readiness Map",
        "readiness map",
        "The regular adapter checklist links to the broader routing readiness map.",
    ),
    Anchor(
        "routing readiness",
        "guarded regular route disabled",
        READINESS_DOC_PATH,
        "No OpenSubdiv-derived rows are production-routed yet",
        "guarded route",
        "The routing map records that routed rows remain disabled.",
    ),
    Anchor(
        "routing readiness",
        "compiled seam row diagnostics",
        READINESS_DOC_PATH,
        "diagnose_opensubdiv_regular_row_semantics",
        "opt-in row diagnostics",
        "The routing map records the compiled-seam row diagnostic.",
    ),
    Anchor(
        "mapping contract",
        "dedicated mapping contract",
        MAPPING_DOC_PATH,
        "OpenSubdiv Sample/Source-Id/Back-Projection Mapping Contract",
        "mapping contract",
        "The mapping contract exists as an upstream adapter boundary.",
    ),
    Anchor(
        "mapping contract",
        "row weight lookup",
        MAPPING_DOC_PATH,
        "row_weight(SLIMED derivative row, original SLIMED vertex id)",
        "source-id contract",
        "The mapping contract requires original-SLIMED-id row weights.",
    ),
    Anchor(
        "force evidence",
        "regular actual force smoke",
        FORCE_EVIDENCE_DOC_PATH,
        "kind: opensubdiv_regular_rows_actual_formula_evidence",
        "opt-in evidence",
        "The force evidence map records regular actual-force probe smoke.",
    ),
    Anchor(
        "force evidence",
        "non-production caveat",
        FORCE_EVIDENCE_DOC_PATH,
        "not production C++ routing",
        "policy boundary",
        "The regular actual-force evidence remains non-production.",
    ),
    Anchor(
        "force/scatter contract",
        "one-ring scatter",
        FORCE_SCATTER_DOC_PATH,
        "face.oneRingVertices[j]",
        "scatter contract",
        "The force/scatter contract records the reviewed scatter order.",
    ),
    Anchor(
        "backend policy",
        "default dependency isolation",
        POLICY_DOC_PATH,
        "default builds stay OpenSubdiv-free",
        "dependency boundary",
        "The backend policy keeps default builds OpenSubdiv-free.",
    ),
    Anchor(
        "interface anchor",
        "weighted sample struct",
        EVALUATOR_HEADER_PATH,
        "struct LimitSurfaceWeightedSample",
        "weighted seam",
        "The public weighted-sample seam exists.",
    ),
    Anchor(
        "interface anchor",
        "source id storage",
        EVALUATOR_HEADER_PATH,
        "std::vector<int> sourceIds;",
        "source-id seam",
        "The weighted-sample seam stores source ids.",
    ),
    Anchor(
        "interface anchor",
        "weighted evaluator method",
        EVALUATOR_HEADER_PATH,
        "virtual LimitSurfaceWeightedSample evaluate_weighted(",
        "weighted seam",
        "The evaluator can return weighted samples through a backend-neutral method.",
    ),
    Anchor(
        "implementation anchor",
        "duplicate aggregation implementation",
        EVALUATOR_IMPL_PATH,
        "weight += rowWeights.get(rowIndex, sourceIndex);",
        "source-id aggregation",
        "The current row-weight lookup aggregates duplicate source ids.",
    ),
    Anchor(
        "OpenSubdiv evaluator",
        "row diagnostic API",
        OPENSUBDIV_EVALUATOR_IMPL_PATH,
        "diagnose_opensubdiv_regular_row_semantics",
        "opt-in row diagnostics",
        "The guarded OpenSubdiv seam exposes a diagnostic without enabling routing.",
    ),
    Anchor(
        "surface tests",
        "row diagnostic comparison",
        SURFACE_TEST_PATH,
        "OptInRowDiagnosticsCompareOpenSubdivRowsAgainstSlimedRows",
        "opt-in row diagnostics",
        "The opt-in test compares compiled-seam OpenSubdiv rows to SLIMED rows.",
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
        "The probe can emit regular actual-force smoke evidence.",
    ),
    Anchor(
        "probe",
        "regular adapter proof option",
        PROBE_PATH,
        "--regular-adapter-proof-report",
        "opt-in OpenSubdiv evidence",
        "The probe can emit regular adapter proof evidence.",
    ),
    Anchor(
        "probe",
        "regular adapter proof kind",
        PROBE_PATH,
        "test_only_regular_opensubdiv_adapter_proof",
        "test-only proof",
        "The probe labels the regular adapter proof as test-only.",
    ),
    Anchor(
        "probe",
        "one-ring source ids",
        PROBE_PATH,
        "regular_lattice_face_one_ring_source_ids",
        "source-id order",
        "The probe remaps regular OpenSubdiv rows into Face::oneRingVertices order.",
    ),
    Anchor(
        "probe wrapper",
        "absent dependency skip",
        WRAPPER_PATH,
        '"status": "skipped"',
        "dependency boundary",
        "The wrapper skips cleanly when OPENSUBDIV_ROOT is absent.",
    ),
    Anchor(
        "production tests",
        "regular source id coverage",
        SURFACE_TEST_PATH,
        "WeightedSampleAggregatesDuplicateSourceIds",
        "source-id aggregation",
        "Focused tests characterize duplicate aggregation through the in-tree seam.",
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
        "evidence_lineage": list(EVIDENCE_LINEAGE),
        "adapter_readiness_checklist": list(ADAPTER_READINESS_CHECKLIST),
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
    print("# OpenSubdiv Regular Backend Adapter Readiness Inventory")
    print()
    print("## Evidence lineage")
    for row in EVIDENCE_LINEAGE:
        print(f"- {row['lane']}")
        print(f"  anchor: {row['anchor']}")
        print(f"  adapter_meaning: {row['adapter_meaning']}")
    print()
    print("## Adapter readiness checklist")
    for row in ADAPTER_READINESS_CHECKLIST:
        print(f"- {row['gate']}")
        print(f"  must_prove: {row['must_prove']}")
        print(f"  current_status: {row['current_status']}")
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
        help="Exit nonzero when an expected adapter-readiness anchor is not found.",
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
