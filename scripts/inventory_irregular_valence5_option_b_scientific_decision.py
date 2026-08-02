#!/usr/bin/env python3
"""Inventory the lightweight Option B scientific decision packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "93b18c683a19e3c35b595e8c85ae111b04caa967"
RUNNER = Path("scripts/run_irregular_valence5_option_b_scientific_decision.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_scientific_decision.sh")
DOC = Path("docs/irregular_valence5_option_b_scientific_decision.md")
TEST = Path("tests/test_irregular_valence5_option_b_scientific_decision_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_scientific_decision.py")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")
OUTPUT_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_option_b_output_visibility.py"
)
ALLOWED_PATHS = {
    RUNNER, WRAPPER, DOC, TEST, SELF, READINESS, GLOBAL, GLOBAL_TEST,
    OUTPUT_INVENTORY,
}
ANCHORS = {
    RUNNER: (
        'BASE_MERGE_COMMIT = "93b18c683a19e3c35b595e8c85ae111b04caa967"',
        '"evidence_complete": True',
        '"decision_ready_for_user": True',
        '"decision_recorded": False',
        '"option_b_selected": option_b_selected',
        '"scientific_approval_granted": scientific_approval_granted',
        '"current_slimed_valence5_fallback_preserved": True',
        '"numerical_consistency_is_scientific_acceptance": False',
        "this packet cannot enable production routing",
    ),
    WRAPPER: ("run_irregular_valence5_option_b_scientific_decision.py", '"$@"'),
    DOC: (
        "evidence program is complete",
        "does not select or recommend Option B",
        "`decision_ready_for_user:true`",
        "mask-policy causal sufficiency has not been proven",
        "engineering results establish reproducibility and operational compatibility, not physical correctness",
        "explicitly accept, reject, or defer Option B",
        "separate production-routing and re-baselining plan",
    ),
    TEST: (
        "test_canonical_packet_is_decision_ready_but_authorizes_nothing",
        "test_evidence_identity_measurements_and_source_digests_are_binding",
        "test_selection_approval_implementation_and_route_false_greens_fail",
    ),
    READINESS: (
        "`evidence_complete:true` and `decision_ready_for_user:true`",
        "keeping `decision_recorded:false`",
        "explicit accept, reject, or defer decision for Option B",
        "current fallback remains preserved",
    ),
    GLOBAL: (
        "Option B evidence is decision ready",
        "Option B decision remains unrecorded",
        "Option B explicit three-way decision",
    ),
    GLOBAL_TEST: (
        "Option B evidence is decision ready",
        "Option B decision remains unrecorded",
        "Option B explicit three-way decision",
    ),
    OUTPUT_INVENTORY: (
        "DECISION_RUNNER",
        "DECISION_INVENTORY",
        "DECISION_DOC",
        "DECISION_TEST",
    ),
}
FORBIDDEN = {
    DOC: (
        "Option B is selected",
        "Option B is scientifically approved",
        "production routing is enabled",
    )
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    paths: list[str] = []
    for command in (
        ["git", "-c", f"safe.directory={root}", "diff", "--name-only", BASE],
        [
            "git", "-c", f"safe.directory={root}", "ls-files", "--others",
            "--exclude-standard",
        ],
    ):
        result = subprocess.run(
            command, cwd=root, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return [], result.stderr.strip() or "git path inventory failed"
        paths.extend(result.stdout.splitlines())
    return sorted(set(paths)), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    expected = 0
    located = 0
    for relative, needles in ANCHORS.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{relative} missing {needle!r}")
    for relative, needles in FORBIDDEN.items():
        source = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            if needle in source:
                errors.append(f"{relative} contains forbidden {needle!r}")
    changed, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    unexpected = sorted(set(map(Path, changed)) - ALLOWED_PATHS)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(map(str, unexpected)))
    missing = sorted(path for path in ALLOWED_PATHS if str(path) not in changed)
    if missing:
        errors.append("expected decision paths are unchanged: " + ", ".join(map(str, missing)))
    return {
        "status": "passed" if not errors else "failed",
        "base": BASE,
        "located_anchors": located,
        "expected_anchors": expected,
        "changed_paths": changed,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = collect(repo_root())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"Option B scientific decision inventory: {report['status']} "
            f"({report['located_anchors']}/{report['expected_anchors']})"
        )
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
