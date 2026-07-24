#!/usr/bin/env python3
"""Run the proof-only valence-4 scatter and simulated OpenMP parity gate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FORCE_PROOF = (
    ROOT / "scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh"
)


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    for key in ("reason", "scatter_openmp_shape_passed"):
        if key in payload:
            print(f"{key}: {payload[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    if not env.get("OPENSUBDIV_ROOT"):
        emit(
            {
                "status": "skipped",
                "reason": (
                    "OPENSUBDIV_ROOT is not set; the valence-4 scatter/OpenMP "
                    "shape proof is explicit opt-in only."
                ),
                "next_step": (
                    "Set OPENSUBDIV_ROOT to an OpenSubdiv install prefix "
                    "and rerun."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    result = subprocess.run(
        [str(FORCE_PROOF), "--json", "--require-opensubdiv"],
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        emit(
            {
                "status": "failed",
                "reason": (
                    "prerequisite valence-4 force proof failed: "
                    + (result.stderr.strip() or result.stdout.strip())
                ),
            },
            args.json,
        )
        return 1

    try:
        force_payload = json.loads(result.stdout)
        proof = force_payload["proof"]
        scatter = proof["production_scatter_openmp_shape_proof"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        emit(
            {
                "status": "failed",
                "reason": f"scatter/OpenMP proof report is incomplete: {error}",
            },
            args.json,
        )
        return 1

    tolerance = float(scatter["absolute_tolerance"])
    passed = bool(
        force_payload.get("status") == "passed"
        and force_payload.get("proof_passed")
        and scatter.get("passed")
        and scatter.get("proof_only")
        and not scatter.get("production_topology_one_rings_populated")
        and not scatter.get("production_route_enabled")
        and scatter.get("face_contribution_count") == 8
        and scatter.get("nonzero_face_contribution_count") == 8
        and scatter.get("all_face_contributions_finite")
        and scatter.get("all_eight_faces_contribute")
        and scatter.get("source_count") == 6
        and scatter.get("force_components_per_source") == 9
        and scatter.get("total_force_components") == 54
        and scatter.get("sources_with_multi_face_collisions") == 6
        and scatter.get("collision_coverage_passed")
        and scatter.get("source_order_passed")
        and scatter.get("independent_layout_oracle_passed")
        and scatter.get("matches_nine_component_scatter_shape")
        and scatter.get("matches_simulated_serial_openmp_accumulation")
        and scatter.get("duplicate_aggregation_preserves_scatter")
        and float(scatter["max_direct_scatter_difference"]) <= tolerance
        and float(scatter["max_serial_simulated_openmp_difference"])
        <= tolerance
        and float(scatter["max_duplicate_scatter_difference"]) <= tolerance
    )
    if not passed:
        emit(
            {
                "status": "failed",
                "reason": "valence-4 scatter/OpenMP shape evidence did not pass",
                "proof": scatter,
            },
            args.json,
        )
        return 1

    emit(
        {
            "status": "passed",
            "proof_only": True,
            "scatter_openmp_shape_proof_only": True,
            "not_production_routing": True,
            "production_route_enabled": False,
            "scientifically_approved": False,
            "actual_face_one_ring_scatter_proven": False,
            "actual_openmp_runtime_proven": False,
            "scatter_openmp_shape_passed": True,
            "deterministic_energy_force_repeat_match": force_payload.get(
                "deterministic_energy_force_repeat_match"
            ),
            "proof": scatter,
        },
        args.json,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
