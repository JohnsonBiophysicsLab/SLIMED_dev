#!/usr/bin/env python3
"""Run the regular formula bridge, then the proof-only valence-4 force lane."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REGULAR_BRIDGE = ROOT / "scripts/run_opensubdiv_regular_cpp_adapter_proof.sh"
PROBE = ROOT / "scripts/run_opensubdiv_probe.sh"


def run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    for key in (
        "reason",
        "regular_formula_bridge_passed",
        "deterministic_energy_force_repeat_match",
        "proof_passed",
    ):
        if key in payload:
            print(f"{key}: {payload[key]}")


def parse_json_output(result: subprocess.CompletedProcess[str], label: str) -> dict:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} did not emit JSON: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    if not env.get("OPENSUBDIV_ROOT"):
        payload = {
            "status": "skipped",
            "reason": (
                "OPENSUBDIV_ROOT is not set; the valence-4 force-formula "
                "proof is explicit opt-in only."
            ),
            "next_step": (
                "Set OPENSUBDIV_ROOT to an OpenSubdiv install prefix and rerun."
            ),
        }
        emit(payload, args.json)
        return 2 if args.require_opensubdiv else 0

    try:
        bridge = parse_json_output(
            run(
                [
                    str(REGULAR_BRIDGE),
                    "--json",
                    "--require-opensubdiv",
                ],
                env,
            ),
            "regular production-helper bridge",
        )
        helper = bridge.get("production_helper_dry_run", {})
        bridge_passed = bool(
            bridge.get("passed")
            and helper.get("matches_proof_local_formula_rows")
            and helper.get("finite")
        )
        if not bridge_passed:
            raise RuntimeError(
                "regular production-helper bridge did not establish finite "
                "proof-local formula-row parity"
            )

        probe_payload = parse_json_output(
            run(
                [
                    str(PROBE),
                    "--valence4-force-formula-proof-report",
                    "--json",
                    "--require-opensubdiv",
                ],
                env,
            ),
            "valence-4 force-formula proof",
        )
        prototype_lines = probe_payload.get("prototype_output", [])
        if len(prototype_lines) != 1:
            raise RuntimeError(
                "valence-4 proof did not emit one canonical JSON report"
            )
        proof = json.loads(prototype_lines[0])
        deterministic = bool(
            probe_payload.get("deterministic_energy_force_repeat_match")
        )
        proof_passed = bool(proof.get("passed"))
        if not deterministic or not proof_passed:
            raise RuntimeError(
                "valence-4 proof or byte-identical energy/force repeat failed"
            )
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    payload = {
        "status": "passed",
        "approved_for_mapping_sample_transpose_proof": True,
        "proof_only": True,
        "force_formula_proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "scientifically_approved": False,
        "regular_formula_bridge_passed": bridge_passed,
        "regular_formula_bridge": {
            "harness": (
                "experiments/opensubdiv_regular_cpp_adapter_proof.cpp"
            ),
            "production_helper": "Mesh::element_energy_force_regular",
            "max_force_row_difference": helper.get(
                "max_force_row_difference_vs_proof_local_formula"
            ),
            "max_scalar_difference": helper.get(
                "max_scalar_difference_vs_proof_local_formula"
            ),
            "matches_proof_local_formula_rows": helper.get(
                "matches_proof_local_formula_rows"
            ),
            "not_production_routing": True,
        },
        "deterministic_energy_force_repeat_match": deterministic,
        "proof_passed": proof_passed,
        "proof": proof,
    }
    emit(payload, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
