#!/usr/bin/env python3
"""Check the experimental regular OpenSubdiv cache prototype boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("experiments/opensubdiv_regular_cache_prototype.cpp")
WRAPPER = Path("scripts/run_opensubdiv_regular_cache_prototype.sh")
DOC = Path("docs/opensubdiv_regular_cache_prototype.md")

ANCHORS = {
    "test-only kind": (SOURCE, "test_only_opensubdiv_regular_cache_prototype"),
    "immutable shared table": (SOURCE, "std::shared_ptr<const RegularRowTable>"),
    "complete fingerprint": (SOURCE, "regular_cache_fingerprint"),
    "OpenSubdiv version key": (SOURCE, "OPENSUBDIV_VERSION_NUMBER"),
    "coordinate hit": (SOURCE, "coordinateOnlyHit"),
    "topology miss": (SOURCE, "topologyMutationMiss"),
    "sample-plan miss": (SOURCE, "samplePlanMutationMiss"),
    "copy empty": (SOURCE, "copyStartsEmpty"),
    "move transfer": (SOURCE, "moveTransfersMatchingTable"),
    "two-mesh isolation": (SOURCE, "twoMeshIsolation"),
    "one publisher": (SOURCE, "concurrentReadersOnePublisher"),
    "opt-out populated cache": (SOURCE, "runtimeOptOutIgnoresPopulatedCache"),
    "fallback": (SOURCE, "unsupportedFallbackPreserved"),
    "row parity": (SOURCE, "rowsMatchFrozenRegular"),
    "dependency gate": (WRAPPER, "OPENSUBDIV_ROOT"),
    "no production cache": (DOC, "does not add cache ownership to `Mesh`"),
    "production follow-up gate": (DOC, "separate reviewer/user-gated production"),
}

PRODUCTION_PATHS = (
    Path("include"),
    Path("src"),
    Path("EXEs"),
    Path("Makefile"),
    Path(".github"),
    Path("scripts/verify_pr_ready.sh"),
)
UNIQUE_MARKER = "PrototypeRegularRowCache"


def locate(path: Path, needle: str):
    full = ROOT / path
    if not full.is_file():
        return None
    for number, line in enumerate(full.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return {"path": path.as_posix(), "line": number, "source": line.strip()}
    return None


def production_leaks():
    leaks = []
    for relative in PRODUCTION_PATHS:
        full = ROOT / relative
        paths = [full] if full.is_file() else sorted(full.rglob("*")) if full.is_dir() else []
        for path in paths:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if UNIQUE_MARKER in text:
                leaks.append(path.relative_to(ROOT).as_posix())
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
    leaks = production_leaks()
    return {
        "status": "passed" if not missing and not leaks else "failed",
        "kind": "test_only_opensubdiv_regular_cache_prototype_inventory",
        "cache_implemented_in_production": False,
        "production_cache_approved": False,
        "broader_valence_in_scope": False,
        "located": located,
        "missing": missing,
        "production_leaks": leaks,
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
        print("# OpenSubdiv Regular Cache Prototype Inventory")
        print(f"status: {result['status']}")
        print(f"anchors: {len(result['located'])}/{len(ANCHORS)}")
        print(f"production leaks: {len(result['production_leaks'])}")
    return 1 if args.check and result["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
