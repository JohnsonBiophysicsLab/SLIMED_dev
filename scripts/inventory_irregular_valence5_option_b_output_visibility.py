#!/usr/bin/env python3
"""Inventory the authorized Option B production output-contract repair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "73bfbf1e90626eaf829d85c2a77916aaf816076f"
RUNNER = Path("scripts/run_irregular_valence5_option_b_output_visibility.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_output_visibility.sh")
HARNESS = Path("experiments/irregular_valence5_option_b_output_visibility.cpp")
DOC = Path("docs/irregular_valence5_option_b_output_visibility.md")
TEST = Path("tests/test_irregular_valence5_option_b_output_visibility_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_output_visibility.py")
OUTPUT = Path("src/io/output.cpp")
IO_HEADER = Path("include/io/io.hpp")
IO_TEST = Path("tests/test_io.cpp")
ENERGY_DOC = Path("docs/irregular_valence5_option_b_energy_geometry_rebaseline.md")
SERIAL_DOC = Path("docs/irregular_valence5_option_b_serial_openmp_evidence.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
GLOBAL = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")

ALLOWED_PATHS = {
    RUNNER, WRAPPER, HARNESS, DOC, TEST, SELF, OUTPUT, IO_HEADER, IO_TEST,
    ENERGY_DOC, SERIAL_DOC, READINESS, GLOBAL, GLOBAL_TEST,
}
REQUIRED_CHANGED_PATHS = ALLOWED_PATHS - {WRAPPER}
PROTECTED_PREFIXES = (
    "include/", "src/", "EXEs/", "Makefile", ".github/", "data/fixtures/",
    "scripts/verify_pr_ready.sh",
)

ANCHORS = {
    OUTPUT: (
        'outfile << "SLIMED_RESTART_V2\\n"',
        'tag == "SLIMED_RESTART_V2"',
        'tag != "SLIMED_RESTART_V1"',
        'outfile << "faces " << model.mesh.faces.size()',
        'write_force_terms(outfile, vertex.force)',
        'write_force_terms(outfile, vertex.forcePrev)',
        'write_force_terms(outfile, model.ncgDirection0[vertex.index])',
        'std::setprecision(17)',
        'E_Volume,E_Thickness,E_Tilt',
        'E_IdealizedProteinLattice,E_Total',
    ),
    IO_HEADER: (
        "all ten Energy channels",
        "V2 checkpoints store",
        "Load a V1 or V2 restart checkpoint",
    ),
    IO_TEST: (
        "EnergyForceWriterEmitsCompleteFullPrecisionContract",
        "ElementFaceEnergyWriterEmitsCompleteAlignedContract",
        "RestartReadsExpectedCheckpointFields",
        "LoaderRemainsBackwardCompatibleWithV1",
        "LoaderRejectsTrailingTokens",
    ),
    RUNNER: (
        '"proof_kind": "valence5_option_b_output_contract_repair"',
        '"output_visible_evidence_complete": True',
        '"output_contract_repair_authorized": True',
        '"output_contract_repair_complete": True',
        '"checkpoint_format": "SLIMED_RESTART_V2"',
        '"checkpoint_v1_loader_compatible": True',
        '"checkpoint_force_family_components_serialized": True',
        '"production_route_enabled": False',
        "scientific review and explicit Option B selection",
    ),
    HARNESS: (
        "write_energy_force_data_to_csv(model, argv[2])",
        "write_element_face_energy_to_csv(model)",
        "write_model_restart_checkpoint(model, argv[3], 1)",
        "load_model_restart_checkpoint(restartModel, argv[3])",
        "checkpoint_curvature_force_preserved",
        "checkpoint_face_normals_preserved",
        "checkpoint_face_energy_preserved",
    ),
    DOC: (
        "explicitly authorized output-contract repair",
        "SLIMED_RESTART_V2",
        "loader accepts both V1 and V2",
        "output-visible evidence gap identified by PR #157 is closed",
        "production valence-5 routing remains disabled",
    ),
    TEST: (
        "test_repair_binds_complete_output_contract",
        "test_face_schema_and_each_checkpoint_preservation_claim_are_binding",
        "test_every_serialized_csv_field_family_is_envelope_bound",
        "test_present_dependency_proof",
    ),
    READINESS: (
        "authorized output-contract repair is complete",
        "next boundary is scientific review and explicit Option B selection",
    ),
    GLOBAL: (
        "Option B output contract repair completed",
        "Option B selection remains gated after output repair",
    ),
    GLOBAL_TEST: (
        "Option B output contract repair completed",
        "Option B selection remains gated after output repair",
    ),
}

FORBIDDEN = {
    RUNNER: (
        'add_argument("--tolerance"',
        '"option_b_selected": True',
        '"production_route_enabled": True',
        '"valence5_opensubdiv_route_enabled": True',
    ),
    DOC: (
        "Option B is selected",
        "production valence-5 routing is enabled",
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
    paths = {line for line in (result.stdout + untracked.stdout).splitlines() if line}
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
        errors.append("required repair paths unchanged: " + ", ".join(map(str, missing)))
    protected = [
        path for path in changed
        if path.startswith(PROTECTED_PREFIXES) and Path(path) not in ALLOWED_PATHS
    ]
    if protected:
        errors.append("unreviewed protected surface changed: " + ", ".join(protected))

    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "base": BASE,
        "repair_authorized": True,
        "repair_complete": not errors,
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
