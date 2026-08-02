#!/usr/bin/env python3
"""Inventory the proof-only Option B output-visibility characterization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "12ebc9669c815bd117551194cf4fc1c99144654a"
RUNNER = Path("scripts/run_irregular_valence5_option_b_output_visibility.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_output_visibility.sh")
HARNESS = Path("experiments/irregular_valence5_option_b_output_visibility.cpp")
DOC = Path("docs/irregular_valence5_option_b_output_visibility.md")
TEST = Path("tests/test_irregular_valence5_option_b_output_visibility_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_output_visibility.py")
ENERGY_DOC = Path("docs/irregular_valence5_option_b_energy_geometry_rebaseline.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")

ALLOWED_PATHS = {
    RUNNER, WRAPPER, HARNESS, DOC, TEST, SELF, ENERGY_DOC, READINESS, GLOBAL,
    GLOBAL_TEST,
}
REQUIRED_CHANGED_PATHS = {RUNNER, WRAPPER, HARNESS, DOC, TEST, SELF}
PROTECTED_PREFIXES = (
    "include/", "src/", "EXEs/", "Makefile", ".github/", "data/fixtures/",
    "scripts/verify_pr_ready.sh",
)

ANCHORS = {
    RUNNER: (
        "OUTPUT_FORCE_ROUNDTRIP_ABSOLUTE_TOLERANCE = 0.0",
        "OUTPUT_RECORD_ENERGY_ROUNDTRIP_ABSOLUTE_TOLERANCE = 0.0",
        "ENERGY_FORCE_CSV_SERIALIZATION_ABSOLUTE_ENVELOPE = 3.0e-3",
        "ELEMENT_FACE_ENERGY_CSV_SERIALIZATION_ABSOLUTE_ENVELOPE = 5.0e-5",
        "AGGREGATE_FORCE_ABSOLUTE_TOLERANCE = 1.0e-12",
        "finite_nonnegative_number",
        "compare_output_artifacts",
        "energy/geometry scientific gate drift",
        "stock aggregate source force drift",
        '"output_writers_executed_and_parsed": True',
        '"output_characterization_complete": True',
        '"output_visible_evidence_complete": False',
        '"output_contract_repair_authorized": False',
        '"stock_serial_openmp_evidence_pending": True',
        '"element_face_energy_csv_header_width": 5',
        '"element_face_energy_csv_data_row_width": 4',
        '"checkpoint_force_family_components_serialized": False',
        '"face_normals_output_visible": False',
        '"aggregate_source_force_recomputed": True',
        "EnergyForce.csv omits global volume, thickness, and tilt channels",
        "ElementFaceEnergy.csv declares five columns but emits four",
        "no production output writer serializes face normals",
        "review and explicitly authorize an output-contract repair lane",
        'parser.add_argument("--require-opensubdiv"',
    ),
    WRAPPER: (
        "run_irregular_valence5_option_b_output_visibility.py",
        '"$@"',
    ),
    HARNESS: (
        "write_energy_force_data_to_csv(model, argv[2])",
        "write_element_face_energy_to_csv(model)",
        "write_model_restart_checkpoint(model, argv[3], 1)",
        "load_model_restart_checkpoint(restartModel, argv[3])",
        "checkpoint_total_force_roundtrip_max_abs_difference",
        "checkpoint_record_energy_roundtrip_max_abs_difference",
        "checkpoint_curvature_force_preserved",
        "checkpoint_area_force_preserved",
        "checkpoint_volume_force_preserved",
        "checkpoint_face_normals_preserved",
        "checkpoint_face_mean_curvature_preserved",
        "checkpoint_face_area_preserved",
        "checkpoint_face_legacy_volume_preserved",
        "checkpoint_face_energy_preserved",
        "input.peek() != std::char_traits<char>::eof()",
        '\\"production_route_enabled\\\":false',
    ),
    DOC: (
        "observational output-visibility characterization",
        "all three real production writers",
        "`0.002616418819570754`",
        "`4.713969291714193e-05`",
        "header declares five",
        "both round-trip maxima are exactly zero",
        "Option B remains unselected",
        "Output-contract repair is not authorized",
        "stock serial/OpenMP evidence remains pending",
    ),
    TEST: (
        "test_characterization_binds_incomplete_output_contract",
        "test_writer_execution_and_checkpoint_roundtrips_are_binding",
        "test_face_schema_and_each_checkpoint_coverage_claim_are_binding",
        "test_every_serialized_csv_field_family_is_envelope_bound",
        "test_scientific_gates_and_aggregate_recomputation_are_binding",
        "test_checkpoint_differences_reject_nonfinite_negative_and_boolean_values",
        "test_dependency_absent_wrapper_skips",
        "test_wrapper_is_executable_in_git_checkout",
        "test_output_harness_compiles_with_available_cxx",
        "test_present_dependency_proof",
    ),
    ENERGY_DOC: (
        "output writer characterization now executes and parses",
        "output-visible evidence remains incomplete",
    ),
    READINESS: (
        "output writer characterization is complete",
        "output-contract repair",
    ),
    GLOBAL: (
        "Option B output writer characterization completed",
        "output-contract repair remains",
    ),
    GLOBAL_TEST: (
        "Option B output writer characterization completed",
        "Option B output repair remains gated",
    ),
}

FORBIDDEN = {
    RUNNER: (
        'add_argument("--tolerance"',
        '"output_visible_evidence_complete": True',
        '"output_contract_repair_authorized": True',
        '"option_b_selected": True',
        '"production_route_enabled": True',
    ),
    DOC: (
        "Option B is selected",
        "output-visible evidence is complete",
        "output-contract repair is authorized",
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
        return [], result.stderr.strip() or "git diff failed"
    paths = {
        line for line in (result.stdout + untracked.stdout).splitlines() if line
    }
    return sorted(paths), None


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
