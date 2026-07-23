#!/usr/bin/env python3
"""Inventory unsupported broader-valence topology shapes and current policy."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path


MESH_SETUP_PATH = Path("src/mesh/Mesh_setup_geometry.cpp")
MESH_PATH = Path("src/mesh/Mesh.cpp")
FORCE_PATH = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
SURFACE_TEST_PATH = Path("tests/test_surface_geometry_characterization.cpp")


@dataclass(frozen=True)
class Anchor:
    name: str
    path: Path
    needle: str
    meaning: str


ANCHORS = (
    Anchor(
        "regular one-ring predicate",
        MESH_SETUP_PATH,
        "vertices[node0].adjacentVertices.size() == 6",
        "Only faces whose three vertices all have valence 6 receive the 12-slot regular one-ring.",
    ),
    Anchor(
        "narrow irregular one-ring predicate",
        MESH_SETUP_PATH,
        "vertices[node0].adjacentVertices.size() == 5",
        "Only faces whose three vertices all have valence 5 receive the 11-slot irregular one-ring.",
    ),
    Anchor(
        "broader-valence geometry preflight",
        MESH_PATH,
        "Broader-valence routing remains disabled.",
        "Unsupported topologically interior physical one-rings fail before area/volume mutation.",
    ),
    Anchor(
        "fixed-boundary compatibility regression",
        SURFACE_TEST_PATH,
        "FixedBoundaryIncompleteOneRingsRemainOnLegacyBoundaryPath",
        "Incomplete one-rings incident to an open fixed boundary remain on the legacy boundary path.",
    ),
    Anchor(
        "area-volume regular branch",
        MESH_PATH,
        "case 12:",
        "Area and volume have an explicit 12-slot branch.",
    ),
    Anchor(
        "area-volume narrow irregular branch",
        MESH_PATH,
        "case 11:",
        "Area and volume have an explicit 11-slot branch.",
    ),
    Anchor(
        "area assignment after switch",
        MESH_PATH,
        "face.elementArea = area;",
        "Supported routes still store the computed area after the guarded switch.",
    ),
    Anchor(
        "volume assignment after switch",
        MESH_PATH,
        "face.elementVolume = volume;",
        "Supported routes still store the computed legacy volume after the guarded switch.",
    ),
    Anchor(
        "zero-depth 11-control preflight",
        FORCE_PATH,
        "if (face.oneRingVertices.size() == 11 && mesh.param.subDivideTimes <= 0)",
        "The current preflight diagnoses only zero-depth 11-control requests.",
    ),
    Anchor(
        "force regular branch",
        FORCE_PATH,
        "if (nOneRingVertices == 12)",
        "Force evaluation has an explicit 12-slot branch.",
    ),
    Anchor(
        "force narrow irregular branch",
        FORCE_PATH,
        "else if (nOneRingVertices == 11)",
        "Force evaluation has an explicit 11-slot branch.",
    ),
    Anchor(
        "curvature assignment after branches",
        FORCE_PATH,
        "face.energy.energyCurvature = eBend;",
        "Unsupported empty one-rings retain initialized zero curvature energy.",
    ),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def tetrahedron_faces() -> tuple[tuple[int, int, int], ...]:
    return ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))


def octahedron_faces() -> tuple[tuple[int, int, int], ...]:
    return (
        (0, 2, 3),
        (0, 3, 4),
        (0, 4, 5),
        (0, 5, 2),
        (1, 3, 2),
        (1, 4, 3),
        (1, 5, 4),
        (1, 2, 5),
    )


def bipyramid_faces(ring_size: int) -> tuple[tuple[int, int, int], ...]:
    ring = tuple(range(2, ring_size + 2))
    faces: list[tuple[int, int, int]] = []
    for index, current in enumerate(ring):
        following = ring[(index + 1) % ring_size]
        faces.append((0, current, following))
        faces.append((1, following, current))
    return tuple(faces)


def icosahedron_faces() -> tuple[tuple[int, int, int], ...]:
    return (
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    )


GENERATED_CASES = (
    ("closed tetrahedron", 4, tetrahedron_faces()),
    ("closed octahedron", 6, octahedron_faces()),
    ("closed triangular bipyramid", 5, bipyramid_faces(3)),
    ("closed pentagonal bipyramid", 7, bipyramid_faces(5)),
    ("closed hexagonal bipyramid", 8, bipyramid_faces(6)),
    ("closed heptagonal bipyramid", 9, bipyramid_faces(7)),
    ("closed nonagonal bipyramid", 11, bipyramid_faces(9)),
    ("approved closed valence-5 control", 12, icosahedron_faces()),
)


def summarize_topology(
    name: str,
    vertex_count: int,
    faces: tuple[tuple[int, int, int], ...],
) -> dict[str, object]:
    neighbors = [set() for _ in range(vertex_count)]
    edge_counts: Counter[tuple[int, int]] = Counter()
    for face in faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            neighbors[a].add(b)
            neighbors[b].add(a)
            edge_counts[tuple(sorted((a, b)))] += 1

    triplets: Counter[str] = Counter()
    stored_sizes: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    for face in faces:
        valences = tuple(len(neighbors[index]) for index in face)
        triplets["/".join(str(value) for value in sorted(valences))] += 1
        if all(value == 6 for value in valences):
            stored_size = 12
            route = "supported regular 12-control"
        elif all(value == 5 for value in valences):
            stored_size = 11
            route = "supported narrow positive-depth 11-control"
        else:
            stored_size = 0
            route = "unsupported broader valence"
        stored_sizes[str(stored_size)] += 1
        route_counts[route] += 1

    unsupported = route_counts.get("unsupported broader valence", 0) > 0
    return {
        "name": name,
        "vertex_count": vertex_count,
        "face_count": len(faces),
        "closed_two_face_edges": bool(edge_counts) and all(count == 2 for count in edge_counts.values()),
        "vertex_valence_counts": dict(sorted(Counter(len(value) for value in neighbors).items())),
        "face_valence_triplet_counts": dict(sorted(triplets.items())),
        "production_stored_one_ring_size_counts": dict(sorted(stored_sizes.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "current_diagnostic": (
            "runtime_error before geometry/force evaluation"
            if unsupported
            else "not applicable"
        ),
        "current_unsupported_effect": (
            "empty one-ring rejected; no geometry or membrane force mutation"
            if unsupported
            else "not applicable"
        ),
        "route_enabled": False if unsupported else True,
    }


def locate_anchors(root: Path) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    located: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    for anchor in ANCHORS:
        lines = (root / anchor.path).read_text(encoding="utf-8").splitlines()
        match = next(
            ((line_number, line.strip()) for line_number, line in enumerate(lines, 1) if anchor.needle in line),
            None,
        )
        if match is None:
            missing.append({"name": anchor.name, "path": anchor.path.as_posix(), "needle": anchor.needle})
        else:
            located.append(
                {
                    "name": anchor.name,
                    "path": anchor.path.as_posix(),
                    "line": match[0],
                    "source": match[1],
                    "meaning": anchor.meaning,
                }
            )
    return located, missing


def collect_inventory(root: Path) -> dict[str, object]:
    located, missing = locate_anchors(root)
    cases = [summarize_topology(*case) for case in GENERATED_CASES]
    return {
        "status": "passed" if not missing else "failed",
        "production_behavior": {
            "supported_stored_one_ring_sizes": [11, 12],
            "unsupported_stored_one_ring_size": 0,
            "unsupported_preflight_diagnostic": True,
            "regular_fallback_used": False,
            "broader_valence_route_enabled": False,
        },
        "generated_closed_topologies": cases,
        "located_anchors": located,
        "missing_anchors": missing,
    }


def check_inventory(report: dict[str, object]) -> list[str]:
    failures = [f"missing source anchor: {item['name']}" for item in report["missing_anchors"]]
    cases = {case["name"]: case for case in report["generated_closed_topologies"]}
    expected = {
        "closed tetrahedron": (4, "3/3/3"),
        "closed octahedron": (8, "4/4/4"),
        "closed triangular bipyramid": (6, "3/4/4"),
        "closed pentagonal bipyramid": (10, "4/4/5"),
        "closed hexagonal bipyramid": (12, "4/4/6"),
        "closed heptagonal bipyramid": (14, "4/4/7"),
        "closed nonagonal bipyramid": (18, "4/4/9"),
    }
    for name, (face_count, triplet) in expected.items():
        case = cases.get(name)
        if case is None:
            failures.append(f"missing generated case: {name}")
            continue
        if case["face_valence_triplet_counts"] != {triplet: face_count}:
            failures.append(f"{name} should expose {face_count} faces with triplet {triplet}")
        if case["production_stored_one_ring_size_counts"] != {"0": face_count}:
            failures.append(f"{name} should retain empty production one-rings")
        if case["current_diagnostic"] != "runtime_error before geometry/force evaluation":
            failures.append(f"{name} should record the fail-loud production diagnostic")
        if not case["closed_two_face_edges"]:
            failures.append(f"{name} should be a closed two-face-edge topology")

    control = cases.get("approved closed valence-5 control")
    if control is None or control["production_stored_one_ring_size_counts"] != {"11": 20}:
        failures.append("approved valence-5 control should retain twenty 11-slot one-rings")
    return failures


def print_text(report: dict[str, object]) -> None:
    print("# Irregular Broader-Valence Inventory")
    print()
    for case in report["generated_closed_topologies"]:
        print(f"## {case['name']}")
        print(f"- vertices: {case['vertex_count']}")
        print(f"- faces: {case['face_count']}")
        print(f"- face valence triplets: {case['face_valence_triplet_counts']}")
        print(f"- stored one-ring sizes: {case['production_stored_one_ring_size_counts']}")
        print(f"- current diagnostic: {case['current_diagnostic']}")
        print(f"- current unsupported effect: {case['current_unsupported_effect']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = collect_inventory(repo_root())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    failures = check_inventory(report) if args.check else []
    if failures:
        for failure in failures:
            print(f"check failure: {failure}")
        return 1
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
