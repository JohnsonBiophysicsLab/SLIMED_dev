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


PLAN_STEPS: tuple[PlanStep, ...] = (
    PlanStep(1, "Plan and validation contract", ("scope", "environment", "gates")),
    PlanStep(2, "Forward W * p correctness proof", ("CPU reference", "CUDA proof")),
    PlanStep(3, "Transpose W^T * g proof", ("adjoint identity", "determinism")),
    PlanStep(4, "Comparative benchmark evidence", ("kernel-only", "end-to-end")),
    PlanStep(5, "Opt-in SLIMED adapter experiment", ("fallback", "readiness")),
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
    Anchor("correctness", "repeatability count", "At least 20 identical CUDA repetitions"),
    Anchor("correctness", "nonfinite rejection", "nonfinite inputs"),
    Anchor("performance", "kernel timing", "CUDA kernel-only time measured with CUDA events"),
    Anchor("performance", "transfer inclusive timing", "transfer-inclusive end-to-end CUDA wall time"),
    Anchor("performance", "repeat count", "at least 30 timed repetitions"),
    Anchor("performance", "integration threshold", "transfer-inclusive speedup greater than"),
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


def as_dicts(
    located: Sequence[LocatedAnchor], missing: Sequence[Anchor]
) -> dict[str, object]:
    return {
        "status": "passed" if not missing else "failed",
        "plan_steps": [
            {
                "number": step.number,
                "title": step.title,
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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="return a nonzero status when a protected plan anchor is missing",
    )
    args = parser.parse_args()

    located, missing = locate_anchors(repo_root())
    print(json.dumps(as_dicts(located, missing), indent=2, sort_keys=True))
    return 1 if args.check and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
