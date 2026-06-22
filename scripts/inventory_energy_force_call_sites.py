#!/usr/bin/env python3
"""Inventory energy/force evaluator and direct mesh call sites."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


DIRECT_PATTERN = re.compile(r"\bCompute_Energy_And_Force\s*\(")
EVALUATOR_PATTERN = re.compile(r"\bEnergyForceEvaluator\b")
SKIP_DIRS = {".git", "bin", "obj"}
SOURCE_SUFFIXES = {".cpp", ".hpp", ".h", ".md", ".py"}


@dataclass(frozen=True)
class Occurrence:
    path: Path
    line_number: int
    kind: str
    classification: str
    detail: str
    line: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def iter_scan_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            yield path


def classify_direct(path: Path, line: str) -> tuple[str, str]:
    normalized = path.as_posix()
    stripped = line.strip()
    if normalized == "src/energy_force/Energy_force_evaluator.cpp":
        return (
            "facade implementation call",
            "The evaluator facade delegates to the existing mesh method here.",
        )
    if normalized == "src/energy_force/Compute_energy_and_force_on_mesh.cpp":
        return (
            "core implementation definition",
            "This is the mesh method implementation, not a caller to route.",
        )
    if normalized == "include/mesh/Mesh.hpp":
        return (
            "api declaration",
            "This declares the existing mesh method.",
        )
    if normalized.startswith("tests/"):
        return (
            "intentional test/control direct call",
            "Tests use the direct call as a control or fixture setup baseline.",
        )
    if normalized.startswith("scripts/"):
        return (
            "analysis script reference",
            "Analysis tooling names the method while classifying call sites.",
        )
    if normalized.startswith("docs/") or normalized.startswith("src/energy_force/README.md"):
        return (
            "documentation reference",
            "Documentation names the existing method or routed call path.",
        )
    if stripped.startswith("//") or stripped.startswith("*"):
        return (
            "comment reference",
            "Comment text references the method name.",
        )
    return (
        "remaining production direct call requiring future review",
        "Production code calls the mesh method outside the facade.",
    )


def classify_evaluator(path: Path, line: str) -> tuple[str, str]:
    normalized = path.as_posix()
    stripped = line.strip()
    if normalized in {
        "src/Run_flat.cpp",
        "src/Run_dynamics_flat.cpp",
        "src/model/Energy_minimization.cpp",
    }:
        return (
            "production path already routed through evaluator facade",
            "A production refresh path uses a file-local evaluator helper.",
        )
    if normalized == "src/energy_force/Energy_force_evaluator.cpp":
        return (
            "facade implementation",
            "This is the evaluator facade implementation.",
        )
    if normalized == "include/energy_force/Energy_force_evaluator.hpp":
        return (
            "facade api declaration",
            "This declares the evaluator facade.",
        )
    if normalized.startswith("tests/"):
        return (
            "intentional evaluator test/control usage",
            "Tests exercise or compare the evaluator facade.",
        )
    if normalized.startswith("scripts/"):
        return (
            "analysis script reference",
            "Analysis tooling names the evaluator while classifying usage.",
        )
    if normalized.startswith("docs/"):
        return (
            "documentation reference",
            "Documentation names the evaluator or routed call path.",
        )
    if stripped.startswith("//") or stripped.startswith("*"):
        return (
            "comment reference",
            "Comment text references the evaluator.",
        )
    return (
        "unclassified evaluator usage",
        "Review whether this should be documented as production or test usage.",
    )


def collect_occurrences(root: Path) -> list[Occurrence]:
    occurrences: list[Occurrence] = []
    for path in iter_scan_files(root):
        relative_path = path.relative_to(root)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            direct_match = DIRECT_PATTERN.search(line)
            evaluator_match = EVALUATOR_PATTERN.search(line)
            if direct_match:
                classification, detail = classify_direct(relative_path, line)
                occurrences.append(
                    Occurrence(
                        path=relative_path,
                        line_number=line_number,
                        kind="direct mesh method",
                        classification=classification,
                        detail=detail,
                        line=line.strip(),
                    )
                )
            if evaluator_match:
                classification, detail = classify_evaluator(relative_path, line)
                occurrences.append(
                    Occurrence(
                        path=relative_path,
                        line_number=line_number,
                        kind="evaluator",
                        classification=classification,
                        detail=detail,
                        line=line.strip(),
                    )
                )
    return occurrences


def print_inventory(occurrences: Sequence[Occurrence]) -> None:
    current_classification: Optional[str] = None
    for occurrence in sorted(
        occurrences,
        key=lambda item: (item.classification, item.path.as_posix(), item.line_number, item.kind),
    ):
        if occurrence.classification != current_classification:
            current_classification = occurrence.classification
            print(f"\n## {current_classification}")
        print(
            f"- {occurrence.path}:{occurrence.line_number} "
            f"[{occurrence.kind}] {occurrence.line}"
        )
        print(f"  {occurrence.detail}")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify Compute_Energy_And_Force() call sites and "
            "EnergyForceEvaluator usage without relying on fixed line numbers."
        )
    )
    parser.add_argument(
        "--fail-on-production-direct",
        action="store_true",
        help="Exit nonzero if a production direct call outside the facade is found.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    occurrences = collect_occurrences(repo_root())
    print_inventory(occurrences)

    production_direct = [
        occurrence
        for occurrence in occurrences
        if occurrence.classification == "remaining production direct call requiring future review"
    ]
    print(
        "\nSummary: "
        f"{len(production_direct)} remaining production direct call(s) requiring review."
    )
    if args.fail_on_production_direct and production_direct:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
