#!/usr/bin/env python3
"""Inventory the guarded OpenSubdiv-fed valence-4 production caller."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "c1d6f49dfc9e871633aa1ec210262d401f2e374b"
PREFLIGHT_HEADER = Path(
    "include/energy_force/Valence4_face_loop_route_preflight.hpp"
)
PREFLIGHT_SOURCE = Path(
    "src/energy_force/Valence4_face_loop_route_preflight.cpp"
)
CPP_TEST = Path("tests/test_valence4_face_loop_route_preflight.cpp")
EXPERIMENT = Path(
    "experiments/irregular_valence4_opensubdiv_production_caller.cpp"
)
RUNNER = Path(
    "scripts/run_irregular_valence4_opensubdiv_production_caller.py"
)
SHELL = Path(
    "scripts/run_irregular_valence4_opensubdiv_production_caller.sh"
)
DOC = Path("docs/irregular_valence4_opensubdiv_production_caller.md")
ROW_PROVIDER_DOC = Path("docs/irregular_valence4_opensubdiv_row_provider.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
INVENTORY = Path(
    "scripts/inventory_irregular_valence4_opensubdiv_production_caller.py"
)
ROW_PROVIDER_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_opensubdiv_row_provider.py"
)
PRODUCTION_CALLER_SHADOW_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_caller_shadow.py"
)
PRODUCTION_CALL_SHADOW_PARITY_INVENTORY = Path(
    "scripts/inventory_irregular_valence4_production_call_shadow_parity.py"
)
GLOBAL_OPENSUBDIV_INVENTORY = Path(
    "scripts/inventory_opensubdiv_regular_cpp_adapter_proof.py"
)
TEST = Path(
    "tests/test_irregular_valence4_opensubdiv_production_caller_inventory.py"
)
PRODUCTION_SOURCE = Path(
    "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
)

ALLOWED_PATHS = {
    PREFLIGHT_HEADER,
    PREFLIGHT_SOURCE,
    CPP_TEST,
    EXPERIMENT,
    RUNNER,
    SHELL,
    DOC,
    ROW_PROVIDER_DOC,
    READINESS,
    INVENTORY,
    ROW_PROVIDER_INVENTORY,
    PRODUCTION_CALLER_SHADOW_INVENTORY,
    PRODUCTION_CALL_SHADOW_PARITY_INVENTORY,
    GLOBAL_OPENSUBDIV_INVENTORY,
    TEST,
}

ANCHORS = {
    PREFLIGHT_HEADER: (
        "Valence4OpenSubdivProductionCallerRequest",
        "Valence4OpenSubdivProductionCallerResult",
        "reviewerApprovedExplicitCaller",
        "opensubdivRowProviderExecuted",
        "productionCallerShadowExecuted",
        "evaluate_guarded_valence4_opensubdiv_production_caller",
        "does not enter the default evaluator face loop",
    ),
    PREFLIGHT_SOURCE: (
        "reject_opensubdiv_production_caller_request",
        "OpenSubdiv production caller remains default-off",
        "build_guarded_opensubdiv_valence4_rows",
        "evaluate_guarded_valence4_production_caller_shadow",
        "opensubdivRowsGenerated = true",
        "productionCallerShadowExecuted = true",
        "actualProductionForcePathExecuted = false",
    ),
    CPP_TEST: (
        "OpenSubdivProductionCallerRemainsDefaultOff",
        "OpenSubdivProductionCallerRejectsExplicitRequestWithoutDependency",
        "OpenSubdivProductionCallerRunsProviderFedCompletionShadow",
        "opensubdivRowProviderExecuted",
        "productionCallerShadowExecuted",
    ),
    EXPERIMENT: (
        "guarded_valence4_opensubdiv_production_caller",
        "default_off_caller_rejected",
        "opensubdiv_row_provider_executed",
        "production_caller_shadow_executed",
        "production_caller_shadow_totals_consistent",
        "not_production_routing",
    ),
    RUNNER: (
        "provider_fed_production_caller",
        "serial_openmp_provider_fed_caller_parity_passed",
        "max_serial_openmp_provider_fed_force_delta",
        "OpenSubdiv production caller is explicit opt-in only",
    ),
    SHELL: (
        "run_irregular_valence4_opensubdiv_production_caller.py",
    ),
    DOC: (
        "OpenSubdiv-Fed Valence-4 Production Caller Prerequisite",
        "provider-fed caller",
        "does not enter `Mesh::Compute_Energy_And_Force()`",
        "route activation remains a separate reviewer/user decision",
    ),
    READINESS: (
        "provider-fed production-caller prerequisite",
        "evaluate_guarded_valence4_opensubdiv_production_caller",
        "serial/OpenMP provider-fed caller parity",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    outputs: list[str] = []
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
            return [], result.stderr.strip() or "git inventory failed"
        outputs.extend(result.stdout.splitlines())
    return sorted({line for line in outputs if line}), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for path, needles in ANCHORS.items():
        text = (
            (root / path).read_text(encoding="utf-8")
            if (root / path).is_file()
            else ""
        )
        for needle in needles:
            expected += 1
            if needle in text:
                located += 1
            else:
                errors.append(f"{path} missing {needle!r}")

    paths, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    unexpected = sorted(
        path for path in paths if Path(path) not in ALLOWED_PATHS
    )
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(unexpected))

    protected = any(
        path.startswith((".github/", "EXEs/", "data/fixtures/"))
        or path in {"Makefile", "scripts/verify_pr_ready.sh"}
        for path in paths
    )
    if protected:
        errors.append("default dependency/build/fixture surface changed")

    production_text = (root / PRODUCTION_SOURCE).read_text(encoding="utf-8")
    default_evaluator_route_caller = (
        "evaluate_guarded_valence4_opensubdiv_production_caller"
        in production_text
    )
    if default_evaluator_route_caller:
        errors.append("default evaluator calls guarded valence-4 caller")

    return {
        "status": "passed" if not errors else "failed",
        "exact_base": BASE,
        "provider_fed_production_caller": True,
        "opensubdiv_rows_feed_reviewed_caller_shadow": True,
        "serial_openmp_provider_fed_caller_parity_required": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "actual_production_force_path_executed": False,
        "production_face_loop_executed": False,
        "production_one_rings_populated": False,
        "default_evaluator_route_caller": default_evaluator_route_caller,
        "default_dependency_changed": protected,
        "changed_paths": paths,
        "anchors": {"located": located, "expected": expected},
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = collect(repo_root())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
