#!/usr/bin/env python3
"""Inventory the CUDA PoC plan and its protected implementation gates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


PLAN_PATH = Path("docs/cuda_poc_implementation_plan.md")


@dataclass(frozen=True)
class PlanStep:
    number: int
    title: str
    heading: str
    required_evidence: tuple[str, ...]


@dataclass(frozen=True)
class Anchor:
    category: str
    name: str
    needle: str


@dataclass(frozen=True)
class LocatedAnchor:
    anchor: Anchor
    line_number: int
    line: str


@dataclass(frozen=True)
class LocatedPlanStep:
    step: PlanStep
    line_number: int


@dataclass(frozen=True)
class PlanStepIssue:
    step: PlanStep
    detail: str


PLAN_STEPS: tuple[PlanStep, ...] = (
    PlanStep(
        1,
        "Plan and validation contract",
        "### Step 1 / PR 1: Plan and validation contract",
        (
            "Add this implementation plan.",
            "Add a dependency-free inventory and tests",
            "Do not add CUDA source or modify production/build files.",
        ),
    ),
    PlanStep(
        2,
        "Forward W * p correctness proof",
        "### Step 2 / PR 2: Forward `W * p` correctness proof",
        (
            "Add an opt-in standalone `.cu` experiment",
            "Add the explicit-order CPU reference",
            "Add a runner that skips with a clear reason when CUDA is unavailable.",
            "Leave all default Make targets and production paths unchanged.",
        ),
    ),
    PlanStep(
        3,
        "Transpose W^T * g proof",
        "### Step 3 / PR 3: Transpose `W^T * g` proof",
        (
            "Add back-projection without floating-point atomics.",
            "Check the long-double adjoint identity",
            "Keep duplicate source-id aggregation outside the device kernel",
        ),
    ),
    PlanStep(
        4,
        "Comparative benchmark evidence",
        "### Step 4 / PR 4: Comparative benchmark evidence",
        (
            "Add serial CPU, OpenMP CPU, CUDA kernel-only, transfer, and end-to-end timing.",
            "Sweep batch sizes with warm-ups and at least 30 measured repetitions.",
            "Record median, p95, device/compiler metadata, memory footprint, and break-even",
        ),
    ),
    PlanStep(
        5,
        "Opt-in SLIMED adapter experiment",
        "### Step 5 / PR 5: Opt-in SLIMED adapter experiment",
        (
            "Stage actual regular-face rows into the proven contiguous proof layout.",
            "Compare adapter outputs against the current CPU formula seam",
            "Produce a readiness recommendation covering correctness, performance,",
            "Do not enable default or production CUDA routing.",
        ),
    ),
)


ANCHORS: tuple[Anchor, ...] = (
    Anchor("scope", "proof-only boundary", "This is a proof-only CUDA lane."),
    Anchor("scope", "no production replacement", "replace `Mesh::element_energy_force_regular`"),
    Anchor("kernel", "forward equation", "weighted[b,q,r,c] = sum(j=0..11)"),
    Anchor("kernel", "transpose equation", "controlGradient[b,j,c] ="),
    Anchor("environment", "native architecture", "`-arch=compute_89 -code=sm_89`"),
    Anchor("environment", "no PTX JIT", "must not depend on PTX JIT"),
    Anchor("compatibility", "optional CUDA", "CUDA discovery is opt-in"),
    Anchor("compatibility", "default target protection", "no default Make target may invoke"),
    Anchor("correctness", "fixed absolute gate", "`1.0e-12`"),
    Anchor("correctness", "long double adjoint oracle", "long-double host oracle"),
    Anchor("correctness", "normalized adjoint residual", "adjoint residual is"),
    Anchor("correctness", "adjoint zero scale", "scale floor of one"),
    Anchor("correctness", "relative delta policy", "reported for diagnosis only"),
    Anchor("correctness", "repeatability count", "At least 20 identical CUDA repetitions"),
    Anchor("correctness", "nonfinite rejection", "nonfinite inputs"),
    Anchor("performance", "kernel timing", "CUDA kernel-only time measured with CUDA events"),
    Anchor("performance", "transfer inclusive timing", "transfer-inclusive end-to-end CUDA wall time"),
    Anchor("performance", "repeat count", "at least 30 timed repetitions"),
    Anchor("performance", "integration threshold", "transfer-inclusive speedup greater than"),
    Anchor("performance", "cpu model metadata", "host CPU model"),
    Anchor("performance", "openmp metadata", "requested and observed OpenMP thread counts"),
    Anchor("performance", "power metadata", "current host power mode"),
    Anchor("performance", "recommendation boundary", "tested CPU, core/thread configuration"),
    Anchor("review", "dedicated reviewer", "Send the PR to the dedicated CUDA PoC reviewer task."),
    Anchor("review", "owner approval", "Ask the repository owner for explicit approval before merging."),
    Anchor("review", "author cannot merge", "The author and reviewer must not merge PRs."),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def locate_anchors(root: Path) -> tuple[list[LocatedAnchor], list[Anchor]]:
    path = root / PLAN_PATH
    if not path.is_file():
        return [], list(ANCHORS)
    lines = path.read_text(encoding="utf-8").splitlines()
    located: list[LocatedAnchor] = []
    missing: list[Anchor] = []
    for anchor in ANCHORS:
        match = next(
            (
                LocatedAnchor(anchor, line_number, line.strip())
                for line_number, line in enumerate(lines, start=1)
                if anchor.needle in line
            ),
            None,
        )
        if match is None:
            missing.append(anchor)
        else:
            located.append(match)
    return located, missing


def validate_plan_text(
    text: str,
) -> tuple[list[LocatedPlanStep], list[PlanStepIssue]]:
    """Validate ordered step headings and evidence within each step section."""

    lines = text.splitlines()
    located: list[LocatedPlanStep] = []
    issues: list[PlanStepIssue] = []
    search_from = 0
    for step in PLAN_STEPS:
        heading_index = next(
            (
                index
                for index in range(search_from, len(lines))
                if lines[index].strip() == step.heading
            ),
            None,
        )
        if heading_index is None:
            issues.append(PlanStepIssue(step, "missing or out-of-order heading"))
            continue

        located.append(LocatedPlanStep(step, heading_index + 1))
        section_end = next(
            (
                index
                for index in range(heading_index + 1, len(lines))
                if lines[index].startswith("### Step ")
            ),
            len(lines),
        )
        section = "\n".join(lines[heading_index + 1 : section_end])
        for evidence in step.required_evidence:
            if evidence not in section:
                issues.append(
                    PlanStepIssue(step, f"missing required evidence: {evidence}")
                )
        search_from = section_end
    return located, issues


def locate_plan_steps(
    root: Path,
) -> tuple[list[LocatedPlanStep], list[PlanStepIssue]]:
    path = root / PLAN_PATH
    if not path.is_file():
        return [], [PlanStepIssue(step, "plan document is missing") for step in PLAN_STEPS]
    return validate_plan_text(path.read_text(encoding="utf-8"))


def as_dicts(
    located: Sequence[LocatedAnchor],
    missing: Sequence[Anchor],
    located_steps: Sequence[LocatedPlanStep],
    step_issues: Sequence[PlanStepIssue],
) -> dict[str, object]:
    return {
        "status": "passed" if not missing and not step_issues else "failed",
        "plan_steps": [
            {
                "number": step.number,
                "title": step.title,
                "heading": step.heading,
                "required_evidence": list(step.required_evidence),
            }
            for step in PLAN_STEPS
        ],
        "located": [
            {
                "category": item.anchor.category,
                "name": item.anchor.name,
                "line": item.line_number,
                "source": item.line,
            }
            for item in located
        ],
        "missing": [
            {
                "category": anchor.category,
                "name": anchor.name,
                "needle": anchor.needle,
            }
            for anchor in missing
        ],
        "located_steps": [
            {"number": item.step.number, "line": item.line_number}
            for item in located_steps
        ],
        "step_issues": [
            {"number": item.step.number, "detail": item.detail}
            for item in step_issues
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="return a nonzero status when a protected plan anchor is missing",
    )
    args = parser.parse_args()

    root = repo_root()
    located, missing = locate_anchors(root)
    located_steps, step_issues = locate_plan_steps(root)
    print(
        json.dumps(
            as_dicts(located, missing, located_steps, step_issues),
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.check and (missing or step_issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
