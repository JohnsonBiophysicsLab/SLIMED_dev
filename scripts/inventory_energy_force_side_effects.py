#!/usr/bin/env python3
"""Inventory obvious EnergyForceEvaluator-sensitive state writes.

This is a characterization helper, not a parser. It scans the current
energy/force implementation files for assignment-like lines that touch the
state surfaces documented in docs/energy_force_evaluator_side_effect_boundary.md.
The output includes line numbers for review convenience, but callers should not
assert exact line numbers.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Pattern, Sequence


SCAN_TARGETS: dict[Path, tuple[str, ...]] = {
    Path("src/energy_force/Energy_force_evaluator.cpp"): (
        "EnergyForceEvaluator::evaluate",
        "evaluate_energy_force",
    ),
    Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"): (
        "refresh_energy_force_geometry",
        "Mesh::clear_force_on_vertices_and_energy_on_faces",
        "Mesh::Compute_Energy_And_Force",
        "Mesh::energy_force_regularization",
        "Mesh::manage_force_for_boundary_ghost_vertex",
    ),
    Path("src/energy_force/Scaffolding_points.cpp"): (
        "Mesh::calculate_scaffolding_energy_force",
    ),
    Path("src/mesh/Mesh.cpp"): (
        "Mesh::calculate_element_area_volume",
        "Mesh::sum_membrane_area_and_volume",
    ),
}

SCAN_FILES = tuple(SCAN_TARGETS)

SIDE_EFFECT_CALL_PATTERN = re.compile(
    r"\b(assign|calculate_element_area_volume|calculate_total_force|"
    r"clear_force_on_vertices_and_energy_on_faces|"
    r"sum_membrane_area_and_volume|"
    r"set_all_zero|set)\s*\("
)

ASSIGNMENT_PATTERN = re.compile(r"(?<![=!<>])=(?!=)|\+=|-=|\*=|/=")
SKIP_LINE_PATTERN = re.compile(r"^\s*(//|\*|/\*)")


@dataclass(frozen=True)
class Category:
    name: str
    detail: str
    patterns: tuple[Pattern[str], ...]


@dataclass(frozen=True)
class Occurrence:
    path: Path
    line_number: int
    category: str
    detail: str
    line: str


@dataclass(frozen=True)
class PhaseAnchor:
    order: int
    name: str
    path: Path
    pattern: Pattern[str]
    detail: str


@dataclass(frozen=True)
class PhaseOccurrence:
    anchor: PhaseAnchor
    line_number: int
    line: str


def compile_patterns(*patterns: str) -> tuple[Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


CATEGORIES = (
    Category(
        "evaluation entry points",
        "The public evaluator boundary reaches the legacy mesh method here.",
        compile_patterns(r"\bCompute_Energy_And_Force\s*\("),
    ),
    Category(
        "element geometry writes",
        "Per-face area/volume are refreshed from current coordinates.",
        compile_patterns(
            r"\bcalculate_element_area_volume\s*\(",
            r"\bface\.elementArea\b",
            r"\bface\.elementVolume\b",
        ),
    ),
    Category(
        "global area/volume writes",
        "Param::area and Param::vol are reset and summed by reference.",
        compile_patterns(
            r"\bsum_membrane_area_and_volume\s*\(",
            r"^\s*(area|volume)\s*(=|\+=)",
        ),
    ),
    Category(
        "current force writes",
        "Current vertex force components/totals are reset, assigned, or accumulated.",
        compile_patterns(r"\bvertices(?:\[.*?\])?\.force\b", r"\bvertex\.force\b"),
    ),
    Category(
        "face energy and curvature writes",
        "Face energy, normals, and mean curvature are refreshed during evaluation.",
        compile_patterns(
            r"\bface\.energy\b",
            r"\bface\.meanCurvature\b",
            r"\bface\.normVector\b",
        ),
    ),
    Category(
        "param energy writes",
        "Param::energy is replaced or scaffold energy components are updated.",
        compile_patterns(r"\bparam\.energy\b", r"\bsumEnergy\.energy"),
    ),
    Category(
        "deformation count writes",
        "Regularization updates deformation counters.",
        compile_patterns(r"\bparam\.deformationCount\b"),
    ),
    Category(
        "scaffolding force writes",
        "Scaffold force accumulators and per-point forces are reset or accumulated.",
        compile_patterns(r"\bforceTotalOnScaffolding\b", r"\bforceOnScaffoldingPoints\b"),
    ),
    Category(
        "boundary force handling",
        "Boundary branches replace force objects with zero force.",
        compile_patterns(r"\bboundaryCondition\b", r"\bzeroForce\b"),
    ),
)

PHASE_ANCHORS = (
    PhaseAnchor(
        1,
        "facade dispatch",
        Path("src/energy_force/Energy_force_evaluator.cpp"),
        re.compile(r"\bmesh\.Compute_Energy_And_Force\s*\("),
        "Public evaluator facade reaches the legacy mesh implementation.",
    ),
    PhaseAnchor(
        2,
        "geometry refresh",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\brefresh_energy_force_geometry\s*\(\*this\)"),
        "Refreshes per-face area/volume and global Param::area/Param::vol first.",
    ),
    PhaseAnchor(
        3,
        "force and face-energy clearing",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"^\s*clear_force_on_vertices_and_energy_on_faces\s*\("),
        "Clears current vertex forces and face energies before recomputation.",
    ),
    PhaseAnchor(
        4,
        "per-face membrane term accumulation",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\belement_energy_force_regular\s*\("),
        "Computes bending energy plus curvature, area, and volume force terms.",
    ),
    PhaseAnchor(
        5,
        "per-thread force scatter reduction",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\bcomponentSums\[component\]\s*\+=\s*localForceComponents\b"),
        "Uses thread-local accumulation before writing vertex force components.",
    ),
    PhaseAnchor(
        6,
        "regularization term",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\benergy_force_regularization\s*\("),
        "Updates regularization energy, force, and deformation counters.",
    ),
    PhaseAnchor(
        7,
        "vertex total force",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\bvertex\.force\.calculate_total_force\s*\("),
        "Totals membrane and regularization force components before scaffolding.",
    ),
    PhaseAnchor(
        8,
        "face and param energy totalization",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\bparam\.energy\s*=\s*sumEnergy\b"),
        "Sums face energies, applies global constraints, and replaces Param::energy.",
    ),
    PhaseAnchor(
        9,
        "optional scaffold energy and force",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\bcalculate_scaffolding_energy_force\s*\(\s*false\s*\)"),
        "Adds optional harmonic, Gag, or idealized-lattice scaffold side effects.",
    ),
    PhaseAnchor(
        10,
        "boundary and ghost force handling",
        Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
        re.compile(r"\bmanage_force_for_boundary_ghost_vertex\s*\("),
        "Zeroes fixed, free, boundary, or ghost forces after scaffold application.",
    ),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def iter_scan_files(root: Path, requested_files: Sequence[Path]) -> Iterable[Path]:
    for path in requested_files:
        candidate = root / path
        if candidate.is_file():
            yield candidate


def classify_line(line: str) -> list[Category]:
    if SKIP_LINE_PATTERN.search(line):
        return []

    matched_categories: list[Category] = []
    for category in CATEGORIES:
        if any(pattern.search(line) for pattern in category.patterns):
            matched_categories.append(category)
    return matched_categories


def iter_uncommented_function_lines(
    path: Path,
    function_names: Sequence[str],
) -> Iterator[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    active_function: Optional[str] = None
    pending_function: Optional[str] = None
    brace_depth = 0
    in_block_comment = False

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line

        if in_block_comment:
            if "*/" in line:
                line = line.split("*/", 1)[1]
                in_block_comment = False
            else:
                continue

        while "/*" in line:
            before, after = line.split("/*", 1)
            if "*/" in after:
                line = before + after.split("*/", 1)[1]
                continue
            line = before
            in_block_comment = True
            break

        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if active_function is None and pending_function is None:
            for function_name in function_names:
                if function_name in line and "(" in line:
                    pending_function = function_name
                    break

        if pending_function is not None:
            if "{" not in line:
                continue
            active_function = pending_function
            pending_function = None
            brace_depth = 0

        if active_function is None:
            continue

        yield line_number, line

        brace_depth += line.count("{")
        brace_depth -= line.count("}")
        if brace_depth <= 0:
            active_function = None


def collect_occurrences(root: Path, requested_files: Sequence[Path]) -> list[Occurrence]:
    occurrences: list[Occurrence] = []
    for path in iter_scan_files(root, requested_files):
        relative_path = path.relative_to(root)
        target_functions = SCAN_TARGETS.get(relative_path)
        if not target_functions:
            continue
        for line_number, line in iter_uncommented_function_lines(path, target_functions):
            categories = classify_line(line)
            if not categories:
                continue

            assignment_like = bool(ASSIGNMENT_PATTERN.search(line)) or bool(
                SIDE_EFFECT_CALL_PATTERN.search(line)
            )
            facade_reference = any(category.name == "evaluation entry points" for category in categories)
            boundary_reference = any(category.name == "boundary force handling" for category in categories)
            if not assignment_like and not facade_reference and not boundary_reference:
                continue

            for category in categories:
                occurrences.append(
                    Occurrence(
                        path=relative_path,
                        line_number=line_number,
                        category=category.name,
                        detail=category.detail,
                        line=line.strip(),
                    )
                )
    return occurrences


def print_inventory(occurrences: Sequence[Occurrence]) -> None:
    current_category: Optional[str] = None
    for occurrence in sorted(
        occurrences,
        key=lambda item: (item.category, item.path.as_posix(), item.line_number),
    ):
        if occurrence.category != current_category:
            current_category = occurrence.category
            print(f"\n## {current_category}")
        print(f"- {occurrence.path}:{occurrence.line_number} {occurrence.line}")
        print(f"  {occurrence.detail}")


def collect_phase_map(root: Path) -> tuple[list[PhaseOccurrence], list[PhaseAnchor]]:
    occurrences: list[PhaseOccurrence] = []
    missing: list[PhaseAnchor] = []
    for anchor in PHASE_ANCHORS:
        path = root / anchor.path
        if not path.is_file():
            missing.append(anchor)
            continue
        matched = False
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if anchor.pattern.search(line):
                occurrences.append(
                    PhaseOccurrence(
                        anchor=anchor,
                        line_number=line_number,
                        line=line.strip(),
                    )
                )
                matched = True
                break
        if not matched:
            missing.append(anchor)
    return occurrences, missing


def print_phase_map(
    occurrences: Sequence[PhaseOccurrence],
    missing: Sequence[PhaseAnchor],
) -> None:
    print("# Energy/force evaluator phase map")
    for occurrence in sorted(occurrences, key=lambda item: item.anchor.order):
        anchor = occurrence.anchor
        print(
            f"{anchor.order}. {anchor.name}: "
            f"{anchor.path}:{occurrence.line_number} {occurrence.line}"
        )
        print(f"   {anchor.detail}")
    if missing:
        print("\nMissing expected phase anchor(s):")
        for anchor in sorted(missing, key=lambda item: item.order):
            print(f"- {anchor.order}. {anchor.name}: {anchor.path}")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory obvious state writes inside the current "
            "EnergyForceEvaluator/Mesh::Compute_Energy_And_Force boundary."
        )
    )
    parser.add_argument(
        "--files",
        nargs="*",
        type=Path,
        default=SCAN_FILES,
        help=(
            "Optional repo-relative files to scan. Defaults to the known "
            "evaluator, mesh update, and scaffolding implementation files."
        ),
    )
    parser.add_argument(
        "--phase-map",
        action="store_true",
        help=(
            "Print the coarse post-PR41 evaluator phase map using stable "
            "function-level anchors instead of assignment-line inventory."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.phase_map:
        occurrences, missing = collect_phase_map(repo_root())
        print_phase_map(occurrences, missing)
        return 1 if missing else 0

    occurrences = collect_occurrences(repo_root(), args.files)
    print_inventory(occurrences)
    print(
        "\nSummary: "
        f"{len(occurrences)} evaluator-sensitive write/reference occurrence(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
