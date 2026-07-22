#!/usr/bin/env python3
"""Inventory the regular OpenSubdiv route cache-readiness contract."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


CACHE_DOC = Path("docs/opensubdiv_regular_cache_readiness.md")
PERFORMANCE_DOC = Path("docs/opensubdiv_regular_route_performance.md")
READINESS_DOC = Path("docs/opensubdiv_regular_backend_adapter_readiness.md")
EVALUATOR_IMPL = Path("src/mesh/OpenSubdiv_regular_evaluator.cpp")
MESH_IMPL = Path("src/mesh/Mesh.cpp")
FORCE_IMPL = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")


CACHE_COMPONENTS = (
    "backend-neutral immutable regular row table",
    "face eligibility and equivalence results",
    "topology and sample-plan fingerprint",
    "synchronized build diagnostics",
)

INVALIDATION_RULES = (
    {"change": "vertex coordinates only", "result": "cache hit"},
    {"change": "setup_flat topology", "result": "cache miss"},
    {"change": "setup_from_vertices_faces topology", "result": "cache miss"},
    {"change": "direct public container mutation", "result": "fingerprint-detected cache miss"},
    {"change": "Face::oneRingVertices source order", "result": "cache miss"},
    {"change": "boundary or ghost eligibility", "result": "cache miss"},
    {"change": "regular sample plan or evaluator options", "result": "cache miss"},
)

OWNERSHIP_RULES = (
    "mesh-scoped ownership behind a backend-neutral or opaque boundary",
    "no process-global Mesh pointer registry",
    "copy starts empty",
    "move transfers only a matching immutable cache",
    "destruction releases state without a global registry",
)

CONCURRENCY_RULES = (
    "published row tables are immutable",
    "one publisher per fingerprint",
    "concurrent readers do not mutate rows or diagnostics",
    "OpenMP reduction order remains unchanged",
)

PROTOTYPE_GATES = (
    "one build across consecutive unchanged evaluations",
    "coordinate-only cache hit with full observable parity",
    "topology and sample-plan mutation misses",
    "copy move destruction and concurrent mesh isolation",
    "runtime opt-out and unsupported fallback unchanged",
    "PR #106 benchmark matrix repeated",
)


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


ANCHORS = (
    Anchor("dedicated cache contract", CACHE_DOC, "OpenSubdiv regular route cache readiness", "The cache-readiness contract exists."),
    Anchor("immutable rows", CACHE_DOC, "The row table must be immutable after publication", "Published rows are read-only."),
    Anchor("coordinate reuse", CACHE_DOC, "Coordinate changes are", "Coordinates do not invalidate topology rows."),
    Anchor("public mutation backstop", CACHE_DOC, "hooks alone are insufficient", "A fingerprint covers public topology mutation."),
    Anchor("global registry rejection", CACHE_DOC, "global map keyed by `Mesh*` is rejected", "Lifetime is mesh-scoped."),
    Anchor("copy contract", CACHE_DOC, "a copied mesh starts with an empty cache", "Copy behavior is explicit."),
    Anchor("concurrent publication", CACHE_DOC, "At most one build for a fingerprint may publish", "Concurrent construction is defined."),
    Anchor("production gate", CACHE_DOC, "A production cache remains a separate reviewer and", "Production remains separately gated."),
    Anchor("measured performance basis", PERFORMANCE_DOC, "PR #105 baseline measurement", "The design follows measured active-route cost."),
    Anchor("current refiner construction", EVALUATOR_IMPL, "create_refiner_for_mesh(mesh)", "The current route reconstructs a refiner."),
    Anchor("current stencil construction", EVALUATOR_IMPL, "DoubleFactory::Create(refiner, locations", "The current route constructs limit stencils."),
    Anchor("area call site", MESH_IMPL, "build_opensubdiv_regular_shape_functions_by_face(*this)", "Area and volume request route rows."),
    Anchor("force call site", FORCE_IMPL, "build_opensubdiv_regular_shape_functions_by_face(mesh)", "Force accumulation requests route rows."),
    Anchor("existing ownership gate", READINESS_DOC, "caching or lifetime changes require a", "Existing readiness keeps caching separately reviewed."),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def locate_anchor(root: Path, anchor: Anchor):
    path = root / anchor.path
    if not path.is_file():
        return None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if anchor.needle in line:
            return LocatedAnchor(anchor, number, line.strip())
    return None


def collect_anchors(root: Path):
    located = []
    missing = []
    for anchor in ANCHORS:
        match = locate_anchor(root, anchor)
        if match is None:
            missing.append(anchor)
        else:
            located.append(match)
    return located, missing


def as_dicts(located: Sequence[LocatedAnchor], missing: Sequence[Anchor]):
    return {
        "status": "passed" if not missing else "failed",
        "cache_implemented": False,
        "production_cache_approved": False,
        "broader_valence_in_scope": False,
        "cache_components": list(CACHE_COMPONENTS),
        "invalidation_rules": list(INVALIDATION_RULES),
        "ownership_rules": list(OWNERSHIP_RULES),
        "concurrency_rules": list(CONCURRENCY_RULES),
        "prototype_gates": list(PROTOTYPE_GATES),
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


def print_text(payload):
    print("# OpenSubdiv Regular Cache Readiness Inventory")
    print()
    for key in ("cache_components", "ownership_rules", "concurrency_rules", "prototype_gates"):
        print(f"## {key.replace('_', ' ').title()}")
        for item in payload[key]:
            print(f"- {item}")
        print()
    print("## Invalidation Rules")
    for item in payload["invalidation_rules"]:
        print(f"- {item['change']}: {item['result']}")
    print()
    print("## Located Anchors")
    for item in payload["located"]:
        print(f"- {item['name']}: {item['path']}:{item['line']}")
    if payload["missing"]:
        print()
        print("## Missing Anchors")
        for item in payload["missing"]:
            print(f"- {item['name']}: {item['path']} missing `{item['needle']}`")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    located, missing = collect_anchors(repo_root())
    payload = as_dicts(located, missing)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_text(payload)
    return 1 if args.check and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
