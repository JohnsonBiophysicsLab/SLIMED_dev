#!/usr/bin/env python3
"""Inventory the proof-only Option B energy/geometry re-baselining package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


BASE = "24cbc8c79259e4ee6dec039b87d816c03ea75560"
RUNNER = Path("scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py")
WRAPPER = Path("scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.sh")
CANDIDATE = Path("experiments/irregular_valence5_option_b_energy_geometry.cpp")
ORACLE = Path("experiments/irregular_valence5_option_b_energy_geometry_oracle.cpp")
DOC = Path("docs/irregular_valence5_option_b_energy_geometry_rebaseline.md")
READINESS = Path("docs/opensubdiv_routing_readiness_map.md")
TEST = Path("tests/test_irregular_valence5_option_b_energy_geometry_rebaseline_inventory.py")
SELF = Path("scripts/inventory_irregular_valence5_option_b_energy_geometry_rebaseline.py")
PR151 = Path("scripts/inventory_irregular_valence5_post_option_d_architecture_gate.py")
PR152 = Path("scripts/inventory_irregular_valence5_option_b_scientific_rebaseline_assessment.py")
GLOBAL = Path("scripts/inventory_opensubdiv_routing_readiness.py")
GLOBAL_TEST = Path("tests/test_opensubdiv_routing_readiness_inventory.py")

ALLOWED_PATHS = {
    RUNNER, WRAPPER, CANDIDATE, ORACLE, DOC, READINESS, TEST, SELF,
    PR151, PR152, GLOBAL, GLOBAL_TEST,
}
PROTECTED_PREFIXES = (
    "include/", "src/", "EXEs/", "Makefile", ".github/",
    "data/fixtures/", "scripts/verify_pr_ready.sh",
)

ANCHORS = {
    RUNNER: (
        'VERTICES_SHA256 = "d0dae733433503f9e2aba4f8eda80fa2d6842d0f5a7b922d7ffce158f505cb45"',
        'FACES_SHA256 = "561b3ec0c4aa6b1e684ef87c2738d8c20a474225bd4960a4a672d306a3e70327"',
        "REVIEWED_RELATIVE_TOLERANCE = 5.0e-6",
        "ORACLE_ABSOLUTE_TOLERANCE = 1.0e-10",
        "CANONICAL_OBSERVABLE_ABSOLUTE_TOLERANCE = 1.0e-12",
        "CANONICAL_OBSERVABLE_DIGEST_DECIMAL_PLACES = 9",
        "EXPECTED_CANONICAL_OBSERVABLE_VECTOR",
        '"982d0be8559491842125cf5b56d35d06c4e90441c7f8e85214585a140f76622d"',
        "canonical_observable_vector",
        "canonical_observable_digest",
        "canonical_observable_location",
        "validate_expected_canonical_observables",
        "validate_candidate_oracle_observables",
        'report.get("global_energy"), 10',
        'per_key_deltas["global_energy"]',
        "require_trailing_token_rejection",
        "TRAILING_NONNUMERIC_TOKEN",
        "reject_duplicate_keys",
        "isinstance(item, bool)",
        "exact perturbed coordinate identity drift",
        "production 20x11 source order drift",
        "ordered outward face orientation drift",
        "fixture/Ptex face order drift",
        "ordered sample identity drift",
        "duplicated mixed-row identity drift",
        '"per_face_energy_semantics": "curvature_plus_regularization_only"',
        '"area_volume_constraint_energy_scope": "global_only"',
        '"output_visible_evidence_complete": False',
        '"option_b_selected": False',
        '"option_b_recommended": False',
        '"stock_semantics_scientifically_approved": False',
        '"sole_mask_causal_attribution_claimed": False',
        "canonical observable drift at",
        '"canonical_observable_digest_reporting_only": True',
        '"canonical_observable_vector_tolerance_passed": True',
        '"candidate_expected_canonical_max_abs_difference"',
        '"oracle_expected_canonical_max_abs_difference"',
        '"candidate_trailing_token_rejected"',
        '"oracle_trailing_token_rejected"',
        "scientific review of measured stock energy and geometry changes",
    ),
    WRAPPER: (
        "run_irregular_valence5_option_b_energy_geometry_rebaseline.py",
        '"$@"',
    ),
    CANDIDATE: (
        "element_energy_force_regular",
        "kLegacyVolumeFactor = 0.16666666666",
        "kSamplePlan",
        "package.samples[face][sample] != kSamplePlan[sample]",
        "input.peek() == std::char_traits<char>::eof()",
        '\\"global_energy\\"',
        "areaEnergy",
        "volumeEnergy",
        "face_curvature_energy",
        "face_regularization_energy",
        "face_normals",
        "face_mean_curvature",
        "face_area",
        "face_legacy_volume",
        "existing_slimed_regular_evaluator_executed",
    ),
    ORACLE: (
        "long double",
        "SamplePlan",
        "p.samples[face][sample] != SamplePlan[sample]",
        "in.peek() == std::char_traits<char>::eof()",
        "independent_long_double_oracle",
        "calls_element_energy_force_regular",
        "LegacyVolumeFactor = 0.16666666666L",
        "weightedNormal",
        "reciprocal1",
        '\\"global_energy\\"',
        "areaEnergy",
        "volumeEnergy",
        "face_curvature_energy",
    ),
    DOC: (
        "observational evidence only",
        "`option_b_selected:false`",
        "`stock_semantics_scientifically_approved:false`",
        "`output_visible_evidence_complete:false`",
        "Per-face production energy contains curvature and regularization only",
        "constraint energies are global additions",
        "`83.84946348746075`",
        "`4.386320459494776`",
        "`2.5747867579624395`",
        "do not attribute the",
        "There is no CLI tolerance capable of clearing a blocker",
        "all 200 ordered per-face energy components",
        "fixed absolute tolerance `1e-12`",
        "digest remains reporting-only",
        "co-mutation of global curvature by `1e-7`",
        "trailing nonnumeric tokens",
    ),
    READINESS: (
        "re-baselining lane is complete",
        "`2.2737367544323206e-13`",
        "Option B remains unselected, unrecommended, scientifically unapproved",
        "No output writer was executed or parsed",
        "bind all 330 ordered stock global",
        "rounded digest is",
        "reporting-only and cannot clear that gate",
        "package readers reject trailing",
        "not route",
    ),
    TEST: (
        "test_exact_identity_and_order_mutations_are_binding",
        "test_numeric_type_and_shape_guards_reject_false_greens",
        "test_flipped_normal_and_aggregation_mutations_are_located",
        "test_complete_observable_digest_and_oracle_comparison_are_binding",
        'candidate["global_energy"][1] += 1.0',
        '("geometry", 0)',
        '("face_energy", 5)',
        '("geometry", 4)',
        'report["candidate_trailing_token_rejected"]',
        'report["oracle_trailing_token_rejected"]',
        'co_mutated_candidate["global_energy"][0] += 1.0e-7',
        'co_mutated_oracle["global_energy"][0] += 1.0e-7',
        'sub_tolerance_candidate["global_energy"][0] += 0.5e-12',
        '"canonical_observable_digest_reporting_only"',
        "test_stale_readiness_claim_is_binding",
        "test_widened_tolerance_option_is_rejected",
        "test_present_dependency_proof",
    ),
    PR151: ("irregular_valence5_option_b_energy_geometry",),
    PR152: ("irregular_valence5_option_b_energy_geometry",),
    GLOBAL: ("Option B energy/geometry characterization completed",),
    GLOBAL_TEST: ("Option B energy/geometry characterization completed",),
}

FORBIDDEN_STALE_CLAIMS = {
    ORACLE: ("element_energy_force_regular(",),
    RUNNER: (
        'add_argument("--tolerance"',
        "args.tolerance",
        "EXPECTED_MEASUREMENT_FINGERPRINT",
        "measurement_fingerprint_matches",
        "candidate_digest != EXPECTED_CANONICAL_OBSERVABLE_DIGEST",
        "oracle_digest != EXPECTED_CANONICAL_OBSERVABLE_DIGEST",
    ),
    READINESS: (
        "Stock energy, geometry, output, and serial/OpenMP evidence remains pending.",
        "proof-only stock OpenSubdiv valence-5 energy and geometry observable re-baselining lane. It must not install",
    ),
    DOC: (
        "Option B is selected",
        "stock semantics are scientifically approved",
        "output-visible evidence is complete",
    ),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changed_paths(root: Path) -> tuple[list[str], str | None]:
    result = subprocess.run(
        ["git", "diff", "--name-only", BASE], cwd=root, check=False,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        return [], result.stderr.strip() or "git diff failed"
    return [line for line in result.stdout.splitlines() if line], None


def scan_forbidden(root: Path) -> list[str]:
    located: list[str] = []
    for path, needles in FORBIDDEN_STALE_CLAIMS.items():
        source = (root / path).read_text(encoding="utf-8")
        for needle in needles:
            if needle in source:
                located.append(f"{path}:{needle}")
    return located


def collect(root: Path) -> dict[str, object]:
    errors: list[str] = []
    expected = located = 0
    for path, needles in ANCHORS.items():
        source = (root / path).read_text(encoding="utf-8")
        for needle in needles:
            expected += 1
            if needle in source:
                located += 1
            else:
                errors.append(f"{path} missing {needle!r}")
    forbidden_expected = sum(len(needles) for needles in FORBIDDEN_STALE_CLAIMS.values())
    forbidden = scan_forbidden(root)
    forbidden_located = len(forbidden)
    errors.extend(f"contains forbidden stale claim {item}" for item in forbidden)
    changed, path_error = changed_paths(root)
    if path_error:
        errors.append(path_error)
    unexpected = sorted(set(map(Path, changed)) - ALLOWED_PATHS)
    if unexpected:
        errors.append("unexpected changed paths: " + ", ".join(map(str, unexpected)))
    missing = sorted(path for path in ALLOWED_PATHS if str(path) not in changed)
    if missing:
        errors.append("expected proof paths unchanged: " + ", ".join(map(str, missing)))
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
        "forbidden_stale_claims": {
            "located": forbidden_located, "expected": forbidden_expected
        },
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
