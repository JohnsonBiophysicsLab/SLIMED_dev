#!/usr/bin/env python3
"""Emit the frozen alternate-library feasibility report for valence-5."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json


RETRIEVAL_DATE = "2026-07-30"
SLIMED_VALENCE5_NEIGHBOR_WEIGHT = 0.075
SLIMED_VALENCE5_CENTER_WEIGHT = 0.625
REQUIRED_CAPABILITIES = (
    "triangular_loop_support",
    "extraordinary_valence_support",
    "exact_limit_surface_evaluation",
    "first_parametric_derivatives",
    "second_parametric_derivatives",
    "public_custom_mask_scheme_evaluator_seam",
    "evaluator_bound_custom_rows",
    "source_identity_order_cardinality_compatible",
    "chain_rule_compatible",
)
EXACT_BLOCKER = (
    "no viable candidate in the reviewed finite non-exhaustive set provides "
    "exact extraordinary Loop "
    "limit-surface evaluation with first and second parametric derivatives "
    "and a public evaluator-bound custom-mask seam that preserves the SLIMED "
    "valence-5 source and chain-rule contract"
)


def _capabilities(
    *,
    triangular_loop_support: bool,
    extraordinary_valence_support: bool,
    finite_recursive_refinement: bool,
    exact_limit_surface_evaluation: bool = False,
    first_parametric_derivatives: bool = False,
    second_parametric_derivatives: bool = False,
    public_custom_refinement_mask: bool = False,
    limit_vertex_position_weights: bool = False,
    limit_vertex_tangent_weights: bool = False,
) -> dict[str, bool]:
    return {
        "triangular_loop_support": triangular_loop_support,
        "extraordinary_valence_support": extraordinary_valence_support,
        "finite_recursive_refinement": finite_recursive_refinement,
        "exact_limit_surface_evaluation": exact_limit_surface_evaluation,
        "first_parametric_derivatives": first_parametric_derivatives,
        "second_parametric_derivatives": second_parametric_derivatives,
        "public_custom_refinement_mask": public_custom_refinement_mask,
        "limit_vertex_position_weights": limit_vertex_position_weights,
        "limit_vertex_tangent_weights": limit_vertex_tangent_weights,
        "public_custom_mask_scheme_evaluator_seam": False,
        "evaluator_bound_custom_rows": False,
        "source_identity_order_cardinality_compatible": False,
        "chain_rule_compatible": False,
        "post_hoc_row_substitution_required": False,
    }


_CANDIDATE_RECORDS = (
    {
        "id": "cgal",
        "name": "CGAL",
        "version": "6.2",
        "release_or_commit": "cac3e9d75e254928db0e38a3161564216cb01919",
        "release_date": "2026-06-11",
        "archive_sha256": (
            "c91fe2e5e13df865a3fc06b0f9b83845c4e88fa243e09ee826a2d3cd774e9dca"
        ),
        "release_url": "https://www.cgal.org/2026/06/11/cgal62/",
        "source_archive_url": "https://github.com/CGAL/cgal/archive/refs/tags/v6.2.tar.gz",
        "license": "LGPL-3.0-or-later OR LicenseRef-Commercial",
        "license_url": "https://www.cgal.org/license.html",
        "cpp_minimum": "C++17",
        "installability": "header-oriented CMake package with documented dependencies",
        "installability_evidence": "official_documentation_and_release_source",
        "installability_probe_executed": False,
        "compile_link_probe_passed": False,
        "api_evidence": (
            {
                "url": (
                    "https://doc.cgal.org/latest/Subdivision_method_3/"
                    "group__PkgSurfaceSubdivisionMethod3Functions.html"
                ),
                "anchor": "CGAL::Subdivision_method_3::PTQ",
                "fact": "PTQ accepts a custom geometry mask and a finite iteration count",
            },
            {
                "url": "https://doc.cgal.org/latest/Subdivision_method_3/index.html",
                "anchor": "ever closer approximation",
                "fact": (
                    "the package recursively refines a mesh toward an "
                    "approximation rather than exposing an exact limit evaluator"
                ),
            },
            {
                "url": (
                    "https://github.com/CGAL/cgal/blob/v6.2/"
                    "Subdivision_method_3/examples/Subdivision_method_3/"
                    "Customized_subdivision.cpp"
                ),
                "anchor": "WLoop_mask_3",
                "fact": "the public customization seam changes refinement point masks",
            },
        ),
        "capabilities": _capabilities(
            triangular_loop_support=True,
            extraordinary_valence_support=True,
            finite_recursive_refinement=True,
            public_custom_refinement_mask=True,
        ),
        "blockers": (
            "custom PTQ masks govern finite refinement points, not an exact "
            "limit-surface evaluator",
            "no reviewed first/second parametric derivative evaluator API",
            "no evaluator-bound source-keyed row and chain-rule contract",
        ),
        "viable": False,
        "selected": False,
        "recommended": False,
    },
    {
        "id": "libigl",
        "name": "libigl",
        "version": "2.6.0",
        "release_or_commit": "40e7900ccbd767f1f360e0eb10f0f1a6432e0993",
        "release_date": "2025-05-15",
        "archive_sha256": (
            "fe3bf58571cccbef774947261284ccf6b7fdf04fcab5f7181e31931e42a0b14f"
        ),
        "release_url": "https://github.com/libigl/libigl/releases/tag/v2.6.0",
        "source_archive_url": (
            "https://github.com/libigl/libigl/archive/refs/tags/v2.6.0.tar.gz"
        ),
        "license": "MPL-2.0",
        "license_url": "https://libigl.github.io/license/",
        "cpp_minimum": "C++11",
        "installability": "header-only core with CMake and Eigen",
        "installability_evidence": "official_documentation_and_release_source",
        "installability_probe_executed": False,
        "compile_link_probe_passed": False,
        "api_evidence": (
            {
                "url": "https://libigl.github.io/dox/loop_8h.html",
                "anchor": "number_of_subdivs",
                "fact": "igl::loop performs a requested finite number of subdivision steps",
            },
            {
                "url": (
                    "https://github.com/libigl/libigl/blob/"
                    "40e7900ccbd767f1f360e0eb10f0f1a6432e0993/include/igl/loop.h"
                ),
                "anchor": "Eigen::SparseMatrix<SType>& S",
                "fact": "the public overload exports a one-step sparse refinement matrix",
            },
        ),
        "capabilities": _capabilities(
            triangular_loop_support=True,
            extraordinary_valence_support=True,
            finite_recursive_refinement=True,
        ),
        "blockers": (
            "public igl::loop is finite recursive refinement, not exact "
            "limit-surface evaluation",
            "no reviewed first/second parametric derivative evaluator API",
            "no public custom Loop mask/scheme/evaluator seam",
        ),
        "viable": False,
        "selected": False,
        "recommended": False,
    },
    {
        "id": "pmp-library",
        "name": "pmp-library",
        "version": "3.0.0",
        "release_or_commit": "f2fb04f4a4188a5c1ab137e83b96e62fa99c639f",
        "release_date": "2023-08-24",
        "archive_sha256": (
            "4533676c7ff8fe816253cb47e1a330e07e044101bdeb9b7b3a1fb437fdc0e4a1"
        ),
        "release_url": (
            "https://github.com/pmp-library/pmp-library/releases/tag/3.0.0"
        ),
        "source_archive_url": (
            "https://github.com/pmp-library/pmp-library/archive/refs/tags/3.0.0.tar.gz"
        ),
        "license": "MIT",
        "license_url": (
            "https://github.com/pmp-library/pmp-library/blob/"
            "f2fb04f4a4188a5c1ab137e83b96e62fa99c639f/LICENSE.txt"
        ),
        "cpp_minimum": "C++17",
        "installability": "compiled CMake library",
        "installability_evidence": "official_documentation_and_release_source",
        "installability_probe_executed": False,
        "compile_link_probe_passed": False,
        "api_evidence": (
            {
                "url": "https://www.pmp-library.org/subdivision.html",
                "anchor": "pmp::loop_subdivision()",
                "fact": "the public API performs Loop subdivision on a triangle mesh",
            },
            {
                "url": (
                    "https://github.com/pmp-library/pmp-library/blob/"
                    "f2fb04f4a4188a5c1ab137e83b96e62fa99c639f/src/pmp/"
                    "algorithms/subdivision.h"
                ),
                "anchor": "Perform one step of Loop subdivision",
                "fact": "the release header exposes exactly one fixed refinement step",
            },
        ),
        "capabilities": _capabilities(
            triangular_loop_support=True,
            extraordinary_valence_support=True,
            finite_recursive_refinement=True,
        ),
        "blockers": (
            "loop_subdivision performs one in-place refinement step, not exact "
            "limit-surface evaluation",
            "no reviewed first/second parametric derivative evaluator API",
            "the release API exposes no custom Loop mask/scheme/evaluator seam",
        ),
        "viable": False,
        "selected": False,
        "recommended": False,
    },
    {
        "id": "openmesh",
        "name": "OpenMesh",
        "version": "11.0",
        "release_or_commit": "f13a3bf79f8dc91cd453b74baa9dc6f97a5a3062",
        "release_date": "2024-05-14",
        "archive_sha256": (
            "c7f35d29673e6dbb6d65b214c10c4c6249521a8f1e8f8db6e8bdc2eed798aedc"
        ),
        "release_url": (
            "https://www.graphics.rwth-aachen.de/software/openmesh/download/"
        ),
        "source_archive_url": (
            "https://www.graphics.rwth-aachen.de/media/openmesh_static/"
            "Releases/11.0/OpenMesh-11.0.0.tar.gz"
        ),
        "license": "BSD-3-Clause",
        "license_url": (
            "https://www.graphics.rwth-aachen.de/software/openmesh/license/"
        ),
        "cpp_minimum": "C++11",
        "installability": "compiled CMake library with Linux, Windows, and macOS support",
        "installability_evidence": "official_documentation_and_release_source",
        "installability_probe_executed": False,
        "compile_link_probe_passed": False,
        "api_evidence": (
            {
                "url": (
                    "https://gitlab.vci.rwth-aachen.de:9000/OpenMesh/OpenMesh/"
                    "-/blob/f13a3bf79f8dc91cd453b74baa9dc6f97a5a3062/"
                    "src/OpenMesh/Core/Geometry/LoopSchemeMaskT.hh"
                ),
                "anchor": "LoopSchemeMaskT",
                "fact": (
                    "the fixed original-Loop helper provides limit-position "
                    "and two tangent weight families"
                ),
            },
            {
                "url": (
                    "https://gitlab.vci.rwth-aachen.de:9000/OpenMesh/OpenMesh/"
                    "-/blob/f13a3bf79f8dc91cd453b74baa9dc6f97a5a3062/"
                    "src/OpenMesh/Tools/Subdivider/Uniform/LoopT.hh"
                ),
                "anchor": "Uniform Loop",
                "fact": "LoopT executes a requested finite number of uniform subdivisions",
            },
            {
                "url": (
                    "https://www.graphics.rwth-aachen.de/software/openmesh/"
                    "download/"
                ),
                "anchor": "OpenMesh 11.0.0",
                "fact": "the official release source and supported platforms are published",
            },
        ),
        "capabilities": _capabilities(
            triangular_loop_support=True,
            extraordinary_valence_support=True,
            finite_recursive_refinement=True,
            limit_vertex_position_weights=True,
            limit_vertex_tangent_weights=True,
        ),
        "blockers": (
            "fixed original-Loop limit/tangent vertex weights are not an exact "
            "arbitrary face-point limit evaluator",
            "no reviewed second parametric derivative evaluator API",
            "LoopT and LoopSchemeMaskT expose no public evaluator-bound custom "
            "mask/scheme seam preserving the SLIMED contract",
        ),
        "viable": False,
        "selected": False,
        "recommended": False,
    },
)

_CANDIDATE_BY_ID = {candidate["id"]: candidate for candidate in _CANDIDATE_RECORDS}
CANONICAL_CANDIDATES = tuple(
    _CANDIDATE_BY_ID[candidate_id]
    for candidate_id in ("cgal", "libigl", "openmesh", "pmp-library")
)


def _candidate_errors(candidates: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    expected = [deepcopy(candidate) for candidate in CANONICAL_CANDIDATES]
    ids = [candidate.get("id") for candidate in candidates]
    expected_ids = [candidate["id"] for candidate in expected]
    if len(ids) != len(set(ids)):
        errors.append("candidate ids must be unique")
    if ids != expected_ids:
        errors.append("candidate set must be exactly ordered cgal, libigl, openmesh, pmp-library")
    if candidates != expected:
        errors.append("candidate evidence or capability facts drifted")

    for candidate in candidates:
        capabilities = candidate.get("capabilities", {})
        if not isinstance(capabilities, dict):
            errors.append(f"{candidate.get('id')} capabilities are missing")
            continue
        if capabilities.get("finite_recursive_refinement") and capabilities.get(
            "exact_limit_surface_evaluation"
        ):
            errors.append(
                f"{candidate.get('id')} cannot infer exact limit evaluation "
                "from finite refinement"
            )
        if capabilities.get("post_hoc_row_substitution_required"):
            errors.append("post-hoc row substitution is not a legitimate evaluator seam")
        viable = all(capabilities.get(key) is True for key in REQUIRED_CAPABILITIES)
        if candidate.get("viable") is not viable:
            errors.append(f"{candidate.get('id')} viability does not match required capabilities")
        if candidate.get("selected") or candidate.get("recommended"):
            errors.append("no candidate may be selected, preferred, or recommended")
    return errors


def evaluate(
    *,
    candidates: list[dict[str, object]] | None = None,
    architecture_option_authorized_for_investigation: str = "D",
    alternate_library_feasibility_lane_authorized: bool = True,
    authorization_scope: str = "observational_feasibility_only",
    predecessor_decision_selected: bool = False,
    predecessor_selected_option: str | None = None,
    predecessor_option_statuses: dict[str, str] | None = None,
    investigation_authorization_is_architecture_selection: bool = False,
    selected_library: str | None = None,
    library_selected: bool = False,
    preferred_candidate: str | None = None,
    recommendation_present: bool = False,
    dependency_policy_changed: bool = False,
    production_route_enabled: bool = False,
    scientifically_approved: bool = False,
    patch_or_vendoring_performed: bool = False,
    post_hoc_row_substitution_accepted: bool = False,
    normals_or_curvature_accepted_as_parametric_derivatives: bool = False,
    current_slimed_valence5_fallback_preserved: bool = True,
) -> dict[str, object]:
    evidence = (
        [deepcopy(candidate) for candidate in CANONICAL_CANDIDATES]
        if candidates is None
        else deepcopy(candidates)
    )
    errors = _candidate_errors(evidence)

    option_statuses = (
        {"A": "unselected", "B": "unselected", "C": "unselected", "D": "unselected"}
        if predecessor_option_statuses is None
        else deepcopy(predecessor_option_statuses)
    )
    if architecture_option_authorized_for_investigation != "D":
        errors.append("only architecture option D is authorized for investigation")
    if not alternate_library_feasibility_lane_authorized:
        errors.append("the alternate-library feasibility lane must be explicitly authorized")
    if authorization_scope != "observational_feasibility_only":
        errors.append("Option D authorization scope must remain observational feasibility only")
    if predecessor_decision_selected or predecessor_selected_option is not None:
        errors.append("PR149 predecessor history must remain no-option-selected")
    if option_statuses != {
        "A": "unselected",
        "B": "unselected",
        "C": "unselected",
        "D": "unselected",
    }:
        errors.append("all four PR149 architecture options must remain historically unselected")
    if investigation_authorization_is_architecture_selection:
        errors.append("Option D investigation authorization is not architecture selection")
    if selected_library is not None or library_selected:
        errors.append("this observational package cannot select a library")
    if preferred_candidate is not None:
        errors.append("this observational package cannot prefer a candidate")
    if recommendation_present:
        errors.append("this observational package cannot recommend or prefer a library")
    if dependency_policy_changed:
        errors.append("this package cannot change dependency policy")
    if production_route_enabled:
        errors.append("this package cannot enable production routing")
    if scientifically_approved:
        errors.append("this package cannot grant scientific approval")
    if patch_or_vendoring_performed:
        errors.append("this package cannot patch, fork, or vendor a candidate")
    if post_hoc_row_substitution_accepted:
        errors.append("post-hoc row substitution cannot satisfy the evaluator seam")
    if normals_or_curvature_accepted_as_parametric_derivatives:
        errors.append("normals or curvature cannot substitute for parametric derivatives")
    if not current_slimed_valence5_fallback_preserved:
        errors.append("the current SLIMED valence-5 fallback must remain preserved")

    viable_ids = [
        str(candidate["id"]) for candidate in evidence if candidate["viable"] is True
    ]
    if viable_ids:
        errors.append("the frozen evidence set contains no fully viable candidate")

    return {
        "status": "passed" if not errors else "failed",
        "proof_kind": "valence5_alternate_library_feasibility",
        "proof_only": True,
        "observational_only": True,
        "retrieval_date": RETRIEVAL_DATE,
        "approved_fixture": "closed valence-5 icosahedron",
        "slimed_valence5_mask": {
            "neighbor_weight": SLIMED_VALENCE5_NEIGHBOR_WEIGHT,
            "center_weight": SLIMED_VALENCE5_CENTER_WEIGHT,
        },
        "required_capabilities": list(REQUIRED_CAPABILITIES),
        "candidate_ids": [candidate.get("id") for candidate in evidence],
        "candidates": evidence,
        "viable_candidate_ids": viable_ids,
        "architecture_option_authorized_for_investigation": (
            architecture_option_authorized_for_investigation
        ),
        "alternate_library_feasibility_lane_authorized": (
            alternate_library_feasibility_lane_authorized
        ),
        "authorization_scope": authorization_scope,
        "predecessor_decision_selected": predecessor_decision_selected,
        "predecessor_selected_option": predecessor_selected_option,
        "predecessor_option_statuses": option_statuses,
        "investigation_authorization_is_architecture_selection": (
            investigation_authorization_is_architecture_selection
        ),
        "selected_library": selected_library,
        "library_selected": library_selected,
        "preferred_candidate": preferred_candidate,
        "recommendation_present": recommendation_present,
        "dependency_policy_changed": dependency_policy_changed,
        "production_route_enabled": production_route_enabled,
        "scientifically_approved": scientifically_approved,
        "patch_or_vendoring_performed": patch_or_vendoring_performed,
        "post_hoc_row_substitution_accepted": post_hoc_row_substitution_accepted,
        "normals_or_curvature_accepted_as_parametric_derivatives": (
            normals_or_curvature_accepted_as_parametric_derivatives
        ),
        "installability_not_executed": True,
        "current_slimed_valence5_fallback_preserved": (
            current_slimed_valence5_fallback_preserved
        ),
        "route_blockers": [EXACT_BLOCKER],
        "remaining_boundary": (
            "preserve the current SLIMED positive-depth valence-5 fallback; "
            "new upstream evidence or an explicit separately reviewed "
            "architecture, scientific, and dependency-policy decision is "
            "required before any alternate-library adapter or route work"
        ),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    report = evaluate()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"candidates: {', '.join(report['candidate_ids'])}")
        print(f"viable candidates: {len(report['viable_candidate_ids'])}")
        for blocker in report["route_blockers"]:
            print(f"blocker: {blocker}")
        for error in report["errors"]:
            print(f"error: {error}")
    return 1 if args.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
