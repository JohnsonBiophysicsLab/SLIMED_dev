#!/usr/bin/env python3
"""Inventory the proof-only Option B scientific re-baselining assessment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "38a745d74880da05f1c50e80798e6bbddcc42c41"
RUNNER = Path(
    "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.py"
)
WRAPPER = Path(
    "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.sh"
)
DOC = Path(
    "docs/irregular_valence5_option_b_scientific_rebaseline_assessment.md"
)
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL_INVENTORY = Path("scripts/inventory_opensubdiv_routing_readiness.py")
TEST = Path(
    "tests/test_irregular_valence5_option_b_scientific_rebaseline_assessment_inventory.py"
)
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")
POST_GATE_INVENTORY = Path(
    "scripts/inventory_irregular_valence5_post_option_d_architecture_gate.py"
)
SELF = Path(
    "scripts/inventory_irregular_valence5_option_b_scientific_rebaseline_assessment.py"
)

ALLOWED_PATHS = {
    RUNNER,
    WRAPPER,
    DOC,
    READINESS,
    GLOBAL_INVENTORY,
    TEST,
    GLOBAL_TEST,
    POST_GATE_INVENTORY,
    SELF,
}

ANCHORS = {
    RUNNER: (
        'PR151_MERGE_COMMIT = "38a745d74880da05f1c50e80798e6bbddcc42c41"',
        "REVIEWED_TOLERANCE = 5.0e-6",
        "CURRENT_SERIAL_OMP_TOLERANCE = 1.0e-10",
        '"proof_kind": "approved_closed_valence5_11_control_serial_openmp_parity"',
        '"scientific_stand_in_scope": "narrow_positive_depth_11_control"',
        '"not_broader_valence_routing": True',
        "current SLIMED serial/OpenMP maximum exceeds reviewed tolerance",
        "current SLIMED serial/OpenMP maximum does not bind channel deltas",
        '"fBend": 7.108303140663388',
        '"fArea": 0.46106761515265404',
        '"fVolume": 0.062309089012307695',
        "EXPECTED_ROW_MAXIMUM = 0.7357563654581705",
        '"assessment_scope": "observational_scientific_rebaseline_planning_only"',
        '"option_b_selected": option_b_selected',
        '"option_b_recommended": option_b_recommended',
        '"physical_rebaselining_plan_proposed": True',
        '"physical_rebaselining_plan_authorized":',
        '"decision_ready": False',
        '"stock_energy"',
        '"stock_geometry"',
        '"stock_output"',
        '"stock_serial_openmp"',
        "this assessment cannot select Option B",
        "this assessment cannot approve changed scientific semantics",
        "this assessment cannot enable production routing",
        "Option B remains unselected",
    ),
    WRAPPER: (
        "OPENSUBDIV_ROOT is not set; Option B assessment is opt-in only.",
        "run_irregular_valence5_opensubdiv_force_parity.sh",
        "run_irregular_valence5_opensubdiv_integration_composition.sh",
        "run_irregular_valence5_fixture_parity.sh",
        "run_irregular_valence5_option_b_scientific_rebaseline_assessment.py",
    ),
    DOC: (
        "authorized checking Option B, not selecting it",
        "`option_b_selected:false`",
        "`stock_semantics_scientifically_approved:false`",
        "`physical_rebaselining_plan_authorized:false`",
        "`0.7357563654581705`",
        "`7.108303140663388`",
        "This is a proposed plan, not an authorized plan",
        "`decision_ready:false`",
        "Option B remains unselected",
    ),
    READINESS: (
        "Option B assessment is complete",
        "observational scientific re-baselining planning only",
        "Option B remains unselected and scientifically unapproved",
        "Stock energy, geometry, output, and serial/OpenMP evidence remains pending",
    ),
    GLOBAL_INVENTORY: (
        "Option B assessment completed",
        "Option B remains unselected after assessment",
        "Option B pending re-baselining channels",
    ),
    TEST: (
        "test_canonical_assessment_binds_known_deltas_and_selects_nothing",
        "test_predecessor_residual_and_tolerance_drift_fail",
        "test_selection_approval_implementation_and_route_false_greens_fail",
        "test_absent_wrapper_skips_cleanly",
        "test_present_wrapper_reproduces_assessment",
        "test_inventory_and_global_readiness_pass",
    ),
    GLOBAL_TEST: (
        "Option B assessment completed",
        "Option B remains unselected after assessment",
        "Option B pending re-baselining channels",
    ),
    POST_GATE_INVENTORY: (
        "docs/irregular_valence5_option_b_scientific_rebaseline_assessment.md",
        "scripts/inventory_irregular_valence5_option_b_scientific_rebaseline_assessment.py",
        "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.py",
        "scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.sh",
        "tests/test_irregular_valence5_option_b_scientific_rebaseline_assessment_inventory.py",
    ),
}

FORBIDDEN = {
    DOC: (
        "Option B is selected",
        "Option B is approved",
        "stock OpenSubdiv semantics are scientifically approved",
        "production valence-5 route is enabled",
    ),
    READINESS: (
        "Option B is selected",
        "Option B is approved",
        "Option B is automatically next",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    paths: list[str] = []
    for command in (
        ["git", "diff", "--name-only", BASE],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        result = subprocess.run(
            command,
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
        errors.append(
            "unexpected changed paths: " + ", ".join(map(str, unexpected))
        )
    missing_changed = sorted(
        path for path in ALLOWED_PATHS if str(path) not in changed
    )
    if missing_changed:
        errors.append(
            "expected assessment paths are unchanged: "
            + ", ".join(map(str, missing_changed))
        )
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
            f"Option B assessment inventory: {report['status']} "
            f"({report['located_anchors']}/{report['expected_anchors']})"
        )
        for error in report["errors"]:
            print(f" - {error}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
