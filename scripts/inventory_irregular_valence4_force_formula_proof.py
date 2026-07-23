#!/usr/bin/env python3
"""Inventory the approved proof-only valence-4 force-formula lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "286bbc1de871ec29f85ddd1d037536631768ec4c"
PROBE = Path("scripts/probe_opensubdiv_feasibility.py")
RUNNER = Path("scripts/run_irregular_valence4_opensubdiv_force_formula_proof.py")
WRAPPER = Path("scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh")
DOC = Path("docs/irregular_valence4_force_formula_proof.md")
TEST = Path("tests/test_irregular_valence4_force_formula_proof_inventory.py")

ALLOWED_PATHS = {
    PROBE,
    RUNNER,
    WRAPPER,
    Path("scripts/inventory_irregular_valence4_force_formula_proof.py"),
    Path("scripts/inventory_opensubdiv_force_transpose_evidence.py"),
    DOC,
    Path("docs/opensubdiv_force_transpose_evidence.md"),
    TEST,
    Path("tests/test_irregular_valence4_mapping_proof_inventory.py"),
}

ANCHORS = {
    PROBE: (
        "SLIMED_VALENCE4_FORCE_FORMULA_PROOF_REPORT",
        "evaluate_valence4_scalar_energies",
        "compare_valence4_force_to_finite_difference",
        "force_formula_proof_only",
        "scientifically_approved",
        "legacy visible-volume position.x*cross.x",
        "all_54_source_axis_comparisons_passed",
        "allMixedRowsIdentical",
    ),
    RUNNER: (
        "run_opensubdiv_regular_cpp_adapter_proof.sh",
        "matches_proof_local_formula_rows",
        "deterministic_energy_force_repeat_match",
        '"force_formula_proof_only": True',
        '"production_route_enabled": False',
        '"scientifically_approved": False',
    ),
    WRAPPER: (
        "run_irregular_valence4_opensubdiv_force_formula_proof.py",
    ),
    DOC: (
        "approved_for_mapping_sample_transpose_proof: true",
        "proof_only: true",
        "force_formula_proof_only: true",
        "not_production_routing: true",
        "production_route_enabled: false",
        "scientifically_approved: false",
        "position.x * cross.x",
        "7.353244912078338e-06",
    ),
    TEST: (
        "all_54_source_axis_comparisons_passed",
        "deterministic_energy_force_repeat_match",
        "test_mapping_mixed_rows_are_a_binding_pass_condition",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", BASE],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if tracked.returncode != 0:
        return [], tracked.stderr.strip() or "git diff failed"
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if untracked.returncode != 0:
        return [], untracked.stderr.strip() or "git ls-files failed"
    paths = {
        line
        for output in (tracked.stdout, untracked.stdout)
        for line in output.splitlines()
        if line
    }
    return sorted(paths), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for path, needles in ANCHORS.items():
        source = (
            (root / path).read_text(encoding="utf-8")
            if (root / path).is_file()
            else ""
        )
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{path} missing {needle!r}")

    paths, diff_error = changed_paths(root)
    if diff_error:
        errors.append(diff_error)
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append(
            "proof lane changed paths outside its allowlist: "
            + ", ".join(unexpected)
        )

    fixture_csvs_changed = any(
        path.endswith("/vertices.csv") or path.endswith("/faces.csv")
        for path in paths
    )
    production_paths_changed = any(
        path.startswith(("src/", "include/", "EXEs/", ".github/"))
        or path == "Makefile"
        for path in paths
    )
    if fixture_csvs_changed:
        errors.append("fixture CSVs must remain unchanged")
    if production_paths_changed:
        errors.append("production/build/runtime paths must remain unchanged")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "approved_for_mapping_sample_transpose_proof": True,
        "proof_only": True,
        "force_formula_proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "scientifically_approved": False,
        "changed_paths": paths,
        "fixture_csvs_changed": fixture_csvs_changed,
        "production_paths_changed": production_paths_changed,
        "anchors": {"located": located, "expected": expected},
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = collect(repo_root())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"exact base: {report['exact_base']}")
        print(
            f"anchors: {report['anchors']['located']}/"
            f"{report['anchors']['expected']}"
        )
        print(f"changed paths: {len(report['changed_paths'])}")
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
