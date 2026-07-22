#!/usr/bin/env python3
"""Inventory the production regular OpenSubdiv row-cache contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("include/mesh/Regular_limit_surface_row_cache.hpp")
MESH = Path("include/mesh/Mesh.hpp")
EVALUATOR = Path("src/mesh/OpenSubdiv_regular_evaluator.cpp")
AREA = Path("src/mesh/Mesh.cpp")
FORCE = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
SETUP = Path("src/mesh/Mesh_setup_flat.cpp")
TEST = Path("tests/test_surface_geometry_characterization.cpp")
DOC = Path("docs/opensubdiv_regular_production_cache.md")

ANCHORS = {
    "mesh-owned cache": (MESH, "regularLimitSurfaceRowCache_"),
    "backend-neutral table": (CACHE, "RegularLimitSurfaceRowTable"),
    "immutable shared publication": (
        CACHE,
        "std::shared_ptr<const RegularLimitSurfaceRowTable>",
    ),
    "copy starts empty": (CACHE, "A copied mesh starts without backend state."),
    "move transfers state": (CACHE, "transfer_from(other)"),
    "synchronized cache": (CACHE, "mutable std::mutex mutex_"),
    "exact identity snapshot": (CACHE, "std::vector<std::uint8_t> identity_"),
    "schema key": (EVALUATOR, "Cache schema version."),
    "OpenSubdiv version key": (EVALUATOR, "OPENSUBDIV_VERSION_NUMBER"),
    "Loop scheme key": (EVALUATOR, "Sdc::SCHEME_LOOP"),
    "boundary option key": (EVALUATOR, "VTX_BOUNDARY_EDGE_ONLY"),
    "face topology key": (EVALUATOR, "face.adjacentVertices"),
    "source order key": (EVALUATOR, "face.oneRingVertices"),
    "sample coordinate key": (EVALUATOR, "mesh.param.VWU"),
    "quadrature key": (EVALUATOR, "mesh.param.gaussQuadratureCoeff"),
    "reference row key": (EVALUATOR, "mesh.param.shapeFunctions"),
    "runtime bypass": (
        EVALUATOR,
        "if (!opensubdiv_regular_production_routing_requested())",
    ),
    "one publisher lock": (EVALUATOR, "std::lock_guard<std::mutex> lock(cache.mutex_)"),
    "collision-safe identity check": (
        EVALUATOR,
        "cache.identity_ == requestedKey.identity",
    ),
    "area cache lookup": (
        AREA,
        "cached_opensubdiv_regular_shape_functions_by_face(*this)",
    ),
    "force cache lookup": (
        FORCE,
        "cached_opensubdiv_regular_shape_functions_by_face(mesh)",
    ),
    "flat setup invalidation": (SETUP, "regularLimitSurfaceRowCache_.invalidate()"),
    "import setup invalidation": (AREA, "regularLimitSurfaceRowCache_.invalidate()"),
    "repeated evaluation test": (
        TEST,
        "ReusesOneImmutableTableAcrossAreaForceAndCoordinateUpdates",
    ),
    "non-ghost coordinate source": (TEST, "!mesh.vertices[source].isGhost"),
    "coordinate mutation observable": (
        TEST,
        "directBeforeMutation, directAfterMutation",
    ),
    "coordinate direct parity": (
        TEST,
        "cachedAfterMutation, directAfterMutation",
    ),
    "mutation rebuild test": (
        TEST,
        "FingerprintRebuildsForTopologyAndSamplePlanMutation",
    ),
    "copy move setup test": (
        TEST,
        "SetupInvalidatesWhileCopyStartsEmptyAndMoveTransfers",
    ),
    "concurrent publication test": (
        TEST,
        "ConcurrentReadersPublishOnceAndRuntimeOptOutBypassesCache",
    ),
    "performance evidence": (DOC, "1.95x"),
    "scope boundary": (DOC, "does not add a"),
}

FORBIDDEN_DEFAULT_SURFACES = (
    Path("Makefile"),
    Path(".github"),
    Path("scripts/verify_pr_ready.sh"),
)


def locate(path: Path, needle: str):
    full = ROOT / path
    if not full.is_file():
        return None
    for number, line in enumerate(full.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return {"path": path.as_posix(), "line": number, "source": line.strip()}
    return None


def forbidden_default_dependency_changes():
    leaks = []
    marker = "RegularLimitSurfaceRowCache"
    for relative in FORBIDDEN_DEFAULT_SURFACES:
        full = ROOT / relative
        paths = [full] if full.is_file() else sorted(full.rglob("*")) if full.is_dir() else []
        for path in paths:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if marker in text:
                leaks.append(path.relative_to(ROOT).as_posix())
    return leaks


def backend_header_leaks():
    leaks = []
    for relative in (CACHE, MESH):
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        if "#include <opensubdiv/" in text or '#include "opensubdiv/' in text:
            leaks.append(relative.as_posix())
    return leaks


def payload():
    located = {}
    missing = []
    for name, (path, needle) in ANCHORS.items():
        match = locate(path, needle)
        if match is None:
            missing.append({"name": name, "path": path.as_posix(), "needle": needle})
        else:
            located[name] = match
    default_leaks = forbidden_default_dependency_changes()
    header_leaks = backend_header_leaks()
    return {
        "status": "passed" if not missing and not default_leaks and not header_leaks else "failed",
        "kind": "production_regular_opensubdiv_row_cache_inventory",
        "production_cache_implemented": True,
        "default_opensubdiv_dependency": False,
        "broader_valence_in_scope": False,
        "formula_or_scatter_change": False,
        "openmp_reduction_change": False,
        "located": located,
        "missing": missing,
        "default_surface_leaks": default_leaks,
        "backend_header_leaks": header_leaks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = payload()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("# Production Regular OpenSubdiv Row Cache Inventory")
        print(f"status: {result['status']}")
        print(f"anchors: {len(result['located'])}/{len(ANCHORS)}")
        print(f"default surface leaks: {len(result['default_surface_leaks'])}")
        print(f"backend header leaks: {len(result['backend_header_leaks'])}")
    return 1 if args.check and result["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
