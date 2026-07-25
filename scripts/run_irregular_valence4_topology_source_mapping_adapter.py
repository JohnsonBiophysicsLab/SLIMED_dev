#!/usr/bin/env python3
"""Run the proof-only valence-4 topology/source-mapping adapter design."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MAPPING_PROOF = (
    ROOT / "scripts/run_irregular_valence4_opensubdiv_mapping_proof.sh"
)
EXPERIMENT = (
    ROOT
    / "experiments/irregular_valence4_topology_source_mapping_adapter.cpp"
)
FIXTURE = ROOT / "data/fixtures/candidates/closed_valence4_octahedron"


def run(
    command: list[str], env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
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
        "production_topology_source_identity_passed",
        "independent_sentinel_scatter_oracle_passed",
    ):
        if key in payload:
            print(f"{key}: {payload[key]}")


def compiler() -> str | None:
    if os.environ.get("CXX"):
        return os.environ["CXX"]
    if platform.system() == "Darwin" and shutil.which("g++-15"):
        return "g++-15"
    return shutil.which("g++") or shutil.which("c++")


def gsl_flags(option: str) -> list[str]:
    result = subprocess.run(
        ["gsl-config", option],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gsl-config failed")
    return shlex.split(result.stdout)


def parse_mapping_proof(payload: dict[str, object]) -> dict[str, object]:
    output = payload.get("prototype_output")
    if not isinstance(output, list) or len(output) != 1:
        raise RuntimeError("mapping proof did not emit one prototype report")
    report = json.loads(output[0])
    if (
        payload.get("status") != "passed"
        or not payload.get("proof_only")
        or not payload.get("not_production_routing")
        or not report.get("passed")
        or not report.get("proof_only")
        or report.get("production_route_enabled")
    ):
        raise RuntimeError("prerequisite mapping proof did not pass")
    return report


def write_mapping(path: Path, report: dict[str, object]) -> None:
    sources = report.get("expected_original_fixture_vertex_ids")
    faces = report.get("faces")
    if sources != list(range(6)):
        raise RuntimeError("mapping proof source ids are not exactly 0..5")
    if not isinstance(faces, list) or len(faces) != 8:
        raise RuntimeError("mapping proof did not expose eight faces")

    lines = ["6 " + " ".join(str(source) for source in sources), "8"]
    for expected_face, face in enumerate(faces):
        if (
            not isinstance(face, dict)
            or face.get("fixture_face_index") != expected_face
        ):
            raise RuntimeError("mapping proof faces are not ordered 0..7")
        oriented = face.get("oriented_fixture_vertex_ids")
        coverage = face.get("source_coverage_union")
        if (
            not isinstance(oriented, list)
            or len(oriented) != 3
            or coverage != list(range(6))
            or not face.get("source_coverage_union_contains_all_six")
        ):
            raise RuntimeError(
                f"mapping proof face {expected_face} is incomplete"
            )
        lines.append(
            " ".join(
                str(value)
                for value in [
                    expected_face,
                    *oriented,
                    len(coverage),
                    *coverage,
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_harness(binary: Path, env: dict[str, str]) -> None:
    cxx = compiler()
    if not cxx:
        raise RuntimeError("no C++ compiler was found")
    if not shutil.which("gsl-config"):
        raise RuntimeError("gsl-config is required to build the adapter harness")

    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    command = [
        cxx,
        "-std=c++17",
        "-DOMP",
        "-fopenmp",
        "-Iinclude",
        "-Iinclude/energy_force",
        "-Iinclude/linalg",
        "-Iinclude/mesh",
        "-Iinclude/model",
        "-Iinclude/parameters",
        *gsl_flags("--cflags"),
        str(EXPERIMENT),
        *(str(source) for source in sources),
        *gsl_flags("--libs"),
        "-o",
        str(binary),
    ]
    result = run(command, env)
    if result.returncode != 0:
        raise RuntimeError(
            "topology/source-mapping adapter compile failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )


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
                    "OPENSUBDIV_ROOT is not set; the valence-4 "
                    "topology/source-mapping adapter is explicit opt-in only."
                ),
                "next_step": (
                    "Set OPENSUBDIV_ROOT to an OpenSubdiv install prefix "
                    "and rerun."
                ),
            },
            args.json,
        )
        return 2 if args.require_opensubdiv else 0

    try:
        mapping_result = run(
            [str(MAPPING_PROOF), "--json", "--require-opensubdiv"], env
        )
        if mapping_result.returncode != 0:
            raise RuntimeError(
                "prerequisite mapping proof failed: "
                + (
                    mapping_result.stderr.strip()
                    or mapping_result.stdout.strip()
                )
            )
        mapping_report = parse_mapping_proof(
            json.loads(mapping_result.stdout)
        )

        with tempfile.TemporaryDirectory(
            prefix="slimed-valence4-topology-source-mapping-"
        ) as temporary:
            temp = Path(temporary)
            mapping = temp / "topology_source_mapping.txt"
            binary = temp / "irregular_valence4_topology_source_mapping"
            write_mapping(mapping, mapping_report)
            build_harness(binary, env)
            result = run(
                [
                    str(binary),
                    str(FIXTURE / "vertices.csv"),
                    str(FIXTURE / "faces.csv"),
                    str(mapping),
                ],
                env,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "topology/source-mapping adapter failed: "
                    + (result.stderr.strip() or result.stdout.strip())
                )
            adapter = json.loads(result.stdout)
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1

    expected_sources = list(range(6))
    passed = bool(
        adapter.get("passed")
        and adapter.get("proof_only")
        and adapter.get("topology_source_mapping_adapter_design")
        and adapter.get("not_production_routing")
        and not adapter.get("production_route_enabled")
        and not adapter.get("scientifically_approved")
        and not adapter.get("actual_production_force_path_executed")
        and adapter.get("production_topology_source_identity_passed")
        and adapter.get("production_one_rings_expected_empty")
        and not adapter.get("production_one_rings_populated")
        and adapter.get("original_source_ids") == expected_sources
        and adapter.get("per_face_source_ids") == [expected_sources] * 8
        and adapter.get("independent_sentinel_scatter_oracle_passed")
        and adapter.get("duplicate_source_rejected")
        and adapter.get("missing_source_rejected")
        and adapter.get("out_of_range_source_rejected")
        and adapter.get("oriented_face_mismatch_rejected")
        and adapter.get("mutation_rejections_passed")
    )
    if not passed:
        emit(
            {
                "status": "failed",
                "reason": "topology/source-mapping evidence did not pass",
                "adapter": adapter,
            },
            args.json,
        )
        return 1

    emit(
        {
            "status": "passed",
            "proof_only": True,
            "topology_source_mapping_adapter_design": True,
            "not_production_routing": True,
            "production_route_enabled": False,
            "scientifically_approved": False,
            "actual_production_force_path_executed": False,
            "production_topology_source_identity_passed": True,
            "independent_sentinel_scatter_oracle_passed": True,
            "prerequisite_mapping_proof_passed": True,
            "adapter": adapter,
        },
        args.json,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
