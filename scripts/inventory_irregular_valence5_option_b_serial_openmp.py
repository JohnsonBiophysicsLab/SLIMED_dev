#!/usr/bin/env python3
"""Inventory the proof-only Option B stock serial/OpenMP evidence lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "3a841f25f54472754e081830995cd03ed5ff2a4b"
RUNNER = Path("scripts/run_irregular_valence5_option_b_serial_openmp.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_serial_openmp.sh")
HARNESS = Path("experiments/irregular_valence5_option_b_serial_openmp.cpp")
DOC = Path("docs/irregular_valence5_option_b_serial_openmp_evidence.md")
TEST = Path("tests/test_irregular_valence5_option_b_serial_openmp_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_serial_openmp.py")
ENERGY_DOC = Path("docs/irregular_valence5_option_b_energy_geometry_rebaseline.md")
OUTPUT_DOC = Path("docs/irregular_valence5_option_b_output_visibility.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")
PRODUCTION_FORCE = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
PRODUCTION_GEOMETRY = Path("src/mesh/Mesh.cpp")

ALLOWED_PATHS = {
    RUNNER, WRAPPER, HARNESS, DOC, TEST, SELF, ENERGY_DOC, OUTPUT_DOC,
    READINESS, GLOBAL, GLOBAL_TEST,
}
REQUIRED_CHANGED_PATHS = {RUNNER, WRAPPER, HARNESS, DOC, TEST, SELF}
PROTECTED_PREFIXES = (
    "include/", "src/", "EXEs/", "Makefile", ".github/", "data/fixtures/",
    "scripts/verify_pr_ready.sh",
)

ANCHORS = {
    RUNNER: (
        "SERIAL_OPENMP_ABSOLUTE_TOLERANCE = 1.0e-10",
        "AGGREGATE_FORCE_ABSOLUTE_TOLERANCE = 1.0e-12",
        "FIXED_THREAD_REPEATABILITY_ABSOLUTE_TOLERANCE = 1.0e-10",
        "REQUESTED_THREAD_COUNTS = [1, 2, 4]",
        "REPEATS_PER_THREAD_COUNT = 5",
        "finite_nonnegative",
        "recompute_aggregate",
        "energy/geometry scientific gate drift",
        "force scientific gate drift",
        "stock serial/OpenMP accumulation tolerance exceeded",
        '"stock_serial_openmp_accumulation_evidence_complete": True',
        '"stock_fixed_thread_repeatability_evidence_complete": True',
        '"stock_serial_openmp_evidence_pending": False',
        '"option_b_selected": False',
        '"production_route_enabled": False',
        '"output_contract_repair_authorized": False',
        'parser.add_argument("--require-opensubdiv"',
    ),
    WRAPPER: (
        "run_irregular_valence5_option_b_serial_openmp.py",
        '"$@"',
    ),
    HARNESS: (
        "#include <omp.h>",
        "omp_set_dynamic(0)",
        "#pragma omp parallel num_threads(requestedThreads)",
        "#pragma omp for schedule(static)",
        "reduction(+ : curvature, regularization, area, legacyVolume)",
        "kThreadCounts{{1, 2, 4}}",
        "kRepeats = 5",
        "max_serial_openmp_accumulation_difference",
        "max_fixed_thread_repeatability_difference",
        "max_face_publication_difference",
        "serial_aggregate_source_forces",
        "input.peek() == std::char_traits<char>::eof()",
    ),
    DOC: (
        "proof-only lane",
        "real OpenMP",
        "1, 2, and 4",
        "five times",
        "`2.2737367544323206e-13`",
        "fixed `1e-10`",
        "tolerance-bound",
        "output-contract repair remains unauthorized",
        "Option B remains unselected",
    ),
    TEST: (
        "test_every_accumulated_channel_has_a_fixed_envelope",
        "test_repeatability_uses_fixed_envelope_and_publication_requires_zero",
        "test_nonnegative_differences_reject_false_green_numbers",
        "test_scientific_nonparity_gates_are_binding",
        "test_thread_counts_and_repeats_are_binding",
        "test_aggregate_is_independently_recomputed",
        "test_scalar_accumulations_are_independently_recomputed",
        "test_dependency_absent_wrapper_skips",
        "test_harness_compiles_with_openmp",
        "test_harness_executes_and_rejects_trailing_tokens",
        "test_present_dependency_proof",
    ),
    ENERGY_DOC: (
        "stock serial/OpenMP accumulation and fixed-thread",
        "output-contract repair lane; Option B remains unselected",
    ),
    OUTPUT_DOC: (
        "stock serial/OpenMP lane is now complete",
        "does not repair or authorize the",
    ),
    READINESS: (
        "proof-only stock-semantics serial/OpenMP lane is complete",
        "`2.2737367544323206e-13`",
        "aggregate-force drift is",
    ),
    GLOBAL: (
        "Option B stock serial/OpenMP evidence completed",
        "proof-only stock-semantics serial/OpenMP lane is complete",
    ),
    GLOBAL_TEST: (
        "Option B stock serial/OpenMP evidence completed",
    ),
    PRODUCTION_FORCE: (
        "faceForceComponents(",
        "nThreads, std::vector<double>(nVertices * 9, 0.0)",
        "for (int threadIndex = 0; threadIndex < nThreads; ++threadIndex)",
    ),
    PRODUCTION_GEOMETRY: (
        "void Mesh::sum_membrane_area_and_volume",
        "reduction(+",
    ),
}

FORBIDDEN = {
    RUNNER: (
        'add_argument("--tolerance"',
        '"option_b_selected": True',
        '"production_route_enabled": True',
        '"output_contract_repair_authorized": True',
        '"output_visible_evidence_complete": True',
    ),
    DOC: (
        "Option B is selected",
        "output-contract repair is authorized",
        "production route is enabled",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    result = subprocess.run(
        ["git", "diff", "--name-only", BASE], cwd=root, check=False,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=root,
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode or untracked.returncode:
        return [], result.stderr.strip() or untracked.stderr.strip() or "git diff failed"
    return sorted({
        line for line in (result.stdout + untracked.stdout).splitlines() if line
    }), None


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    located = 0
    expected = 0
    for path, needles in ANCHORS.items():
        source = (root / path).read_text(encoding="utf-8")
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{path} missing {needle!r}")
    forbidden = []
    for path, needles in FORBIDDEN.items():
        source = (root / path).read_text(encoding="utf-8")
        for needle in needles:
            if needle in source:
                forbidden.append(f"{path}:{needle}")
    errors.extend(f"contains forbidden claim {item}" for item in forbidden)

    mode_result = subprocess.run(
        ["git", "ls-files", "--stage", str(WRAPPER)], cwd=root, check=False,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    wrapper_mode = (
        mode_result.stdout.split(maxsplit=1)[0]
        if mode_result.returncode == 0 and mode_result.stdout.strip()
        else None
    )
    if wrapper_mode != "100755":
        errors.append(
            f"{WRAPPER} must be executable in Git (mode 100755, got {wrapper_mode})"
        )

    changed, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    changed_set = set(map(Path, changed))
    unexpected = sorted(changed_set - ALLOWED_PATHS)
    missing = sorted(REQUIRED_CHANGED_PATHS - changed_set)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(map(str, unexpected)))
    if missing:
        errors.append("required proof paths unchanged: " + ", ".join(map(str, missing)))
    protected = [path for path in changed if path.startswith(PROTECTED_PREFIXES)]
    if protected:
        errors.append("protected production/default surface changed: " + ", ".join(protected))
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "base": BASE,
        "proof_only": True,
        "option_b_selected": False,
        "production_route_enabled": False,
        "changed_paths": changed,
        "protected_paths_changed": protected,
        "anchors": {"located": located, "expected": expected},
        "forbidden_claims": {"located": len(forbidden)},
        "wrapper_git_mode": wrapper_mode,
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
        print(f"anchors: {report['anchors']['located']}/{report['anchors']['expected']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
