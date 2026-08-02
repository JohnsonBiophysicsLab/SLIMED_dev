#!/usr/bin/env python3
"""Validate the protected CUDA residency/force-scatter implementation plan."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence


PLAN_PATH = Path(
    "docs/cuda_end_to_end_residency_force_scatter_implementation_plan.md"
)


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
        0,
        "Plan and protected contract",
        "### Step 0 / PR 0: Plan and protected contract",
        (
            "Add this plan, its dependency-free inventory, and tests.",
            "Do not modify production/build/CUDA source or enable a route.",
        ),
    ),
    PlanStep(
        1,
        "Optional backend shell and capability report",
        "### Step 1 / PR 1: Optional backend shell and capability report",
        (
            "Add an explicit optional CUDA build target and non-CUDA stub.",
            "Do not route an evaluator call or add a production kernel.",
        ),
    ),
    PlanStep(
        2,
        "Canonical mesh packer and eligibility preflight",
        "### Step 2 / PR 2: Canonical mesh packer and eligibility preflight",
        (
            "Build the stable source-incidence plan used by deterministic scatter.",
            "Do not allocate GPU scientific buffers or route production.",
        ),
    ),
    PlanStep(
        3,
        "Persistent device state and transactions",
        "### Step 3 / PR 3: Persistent device state and transactions",
        (
            "accepted/candidate coordinate double buffering, and commit/rollback.",
            "Do not implement force formulas or publish into `Mesh`.",
        ),
    ),
    PlanStep(
        4,
        "Regular geometry and global area/volume",
        "### Step 4 / PR 4: Regular geometry and global area/volume",
        (
            "Add deterministic global area/volume reductions.",
            "Do not publish to production objects or implement force scatter.",
        ),
    ),
    PlanStep(
        5,
        "Complete regular membrane force formula",
        "### Step 5 / PR 5: Complete regular membrane force formula",
        (
            "Port the actual weighted rows and full bending/area/volume formula.",
            "Keep scatter separate; do not write vertex force buffers.",
        ),
    ),
    PlanStep(
        6,
        "Deterministic source-keyed scatter",
        "### Step 6 / PR 6: Deterministic source-keyed scatter",
        (
            "Implement the reviewed incidence-based, fixed-order reduction",
            "Do not use floating-point atomics or enable publication.",
        ),
    ),
    PlanStep(
        7,
        "Regularization, totals, and boundary completion",
        "### Step 7 / PR 7: Regularization, totals, and boundary completion",
        (
            "regularization force/energy path,",
            "Do not support scaffolding or other excluded features.",
        ),
    ),
    PlanStep(
        8,
        "End-to-end shadow evaluator",
        "### Step 8 / PR 8: End-to-end shadow evaluator",
        (
            "Invoke the complete CUDA evaluator behind an explicit shadow-only mode.",
            "Never publish CUDA results or change the selected CPU result.",
        ),
    ),
    PlanStep(
        9,
        "Device-resident line-search operations",
        "### Step 9 / PR 9: Device-resident line-search operations",
        (
            "Return only decision scalars during trials.",
            "Bind accept/reject to device transaction commit/rollback.",
        ),
    ),
    PlanStep(
        10,
        "Coherent host synchronization and publication",
        "### Step 10 / PR 10: Coherent host synchronization and publication",
        (
            "Add named synchronization reasons",
            "Publish all current V2-visible fields atomically from validated staging.",
        ),
    ),
    PlanStep(
        11,
        "Real-workflow benchmark and readiness decision",
        "### Step 11 / PR 11: Real-workflow benchmark and readiness decision",
        (
            "Benchmark the actual eligible `run_flat` workflow",
            "Make a written go/no-go recommendation; do not enable default routing.",
        ),
    ),
    PlanStep(
        12,
        "Explicit opt-in route activation",
        "### Step 12 / PR 12: Explicit opt-in route activation",
        (
            "Start this step only after a separate owner prompt approves activation",
            "Do not add automatic selection or expand feature eligibility.",
        ),
    ),
)


ANCHORS: tuple[Anchor, ...] = (
    Anchor("scope", "planning only", "CUDA routing remains disabled."),
    Anchor("scope", "optional dependency", "make CUDA a required build or runtime dependency"),
    Anchor("architecture", "persistent mesh state", "one persistent device state per eligible mesh"),
    Anchor("architecture", "single stream", "a single ordered stream in the first implementation"),
    Anchor("architecture", "authority table", "Normal authority"),
    Anchor("state", "generation tracking", "track topology, numerical-plan, parameter, accepted-coordinate"),
    Anchor("state", "transaction states", "IdleAccepted -> CandidatePrepared -> Computing -> Validated"),
    Anchor("state", "atomic publication", "publish all vertex, face, and `Param` fields as one control-plane action"),
    Anchor("state", "required buffer schema", "### Required device buffer schema"),
    Anchor("formula", "complete formula", "port the actual regular-face bending"),
    Anchor("scatter", "flat component layout", "source_id * 9 + force_family * 3 + axis"),
    Anchor("scatter", "stable incidence", "`face_index`, then ascending `local_control`"),
    Anchor("scatter", "malformed one-ring rejection", "must not silently reinterpret malformed one-rings"),
    Anchor("scatter", "no atomics", "no floating-point atomics in the initial route"),
    Anchor("scatter", "fixed scalar tree", "### Deterministic scalar and face reductions"),
    Anchor("correctness", "double precision", "Use `double` throughout production numerical buffers and kernels."),
    Anchor("correctness", "absolute gate", "maximum absolute error `1.0e-12`"),
    Anchor("correctness", "repeatability", "at least 20 identical CUDA repetitions"),
    Anchor("compatibility", "default build", "default Make targets or invoke `nvcc` from a non-CUDA target"),
    Anchor("fallback", "whole evaluation", "whole-evaluation CPU fallback decided before any CUDA-visible mutation"),
    Anchor("fallback", "no silent retry", "No CUDA error after candidate computation begins triggers silent CPU retry."),
    Anchor("optimizer", "scalar-only trials", "Return only decision scalars during trials."),
    Anchor("optimizer", "deferred dynamics", "Do not route `run_dynamics_flat` in this program phase."),
    Anchor("performance", "real workflow", "transfer-inclusive speedup greater than `1.0x`"),
    Anchor("performance", "no mesh transfer", "no mesh-sized host/device transfer inside the repeated line-search trial"),
    Anchor("review", "dedicated reviewer", "dedicated CUDA production reviewer task"),
    Anchor("review", "owner approval", "repository owner for explicit approval to merge"),
    Anchor("review", "no merge", "The implementation task and reviewer must not merge."),
    Anchor("prompts", "master prompt", "## Copy-Ready Master Prompt"),
    Anchor("prompts", "reviewer prompt", "## Dedicated Reviewer Prompt"),
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
    """Validate ordered step headings and required evidence within sections."""

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
        help="return nonzero when a protected plan anchor or step is missing",
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
