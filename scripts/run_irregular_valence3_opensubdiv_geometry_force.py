#!/usr/bin/env python3
"""Build and run the proof-only Valence-3 OpenSubdiv science harness."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/irregular_valence3_opensubdiv_geometry_force.cpp"
TETRA = ROOT / "data/fixtures/candidates/closed_valence3_tetrahedron"
MIXED = ROOT / "data/fixtures/candidates/closed_mixed_valence345"
BIPYRAMID = (
    ROOT / "data/fixtures/candidates/closed_valence3_triangular_bipyramid"
)
ASYMMETRIC_BIPYRAMID = (
    ROOT / "data/fixtures/candidates/asymmetric_valence3_triangular_bipyramid"
)

EXPECTED_BIPYRAMID_FACES = [
    [0, 2, 3],
    [0, 3, 4],
    [0, 4, 2],
    [1, 3, 2],
    [1, 4, 3],
    [1, 2, 4],
]
EXPECTED_SYMMETRIC_BIPYRAMID_VERTICES = [
    [Decimal("0"), Decimal("0"), Decimal("1")],
    [Decimal("0"), Decimal("0"), Decimal("-1")],
    [Decimal("1"), Decimal("0"), Decimal("0")],
    [Decimal("-0.5"), Decimal("0.86602540378443865"), Decimal("0")],
    [Decimal("-0.5"), Decimal("-0.86602540378443865"), Decimal("0")],
]
EXPECTED_DEPTHS = [0, 1, 2, 3, 4]
EXPECTED_SAMPLES = [3, 12, 48, 192, 768]
EXPECTED_STUDY_CONTRACT: dict[str, object] = {
    "k_curv": 47.5,
    "u_surf": 130.0,
    "u_vol": 65.0,
    "spontaneous_curvature": 0.17,
    "area0": 0.95,
    "vol0": 0.09,
    "adaptive_isolation_level": 5,
    "maximum_depth": 4,
    "global_change_target": 1.0e-6,
    "force_change_target": 1.0e-5,
    "row_invariant_target": 1.0e-12,
    "global_change_denominator": "max(1e-12,abs(previous),abs(current))",
    "force_change_denominator": "max(1,abs(previous),abs(current))",
}
EXPECTED_CONVERGENCE: dict[str, dict[str, list[float]]] = {
    "closed_valence3_triangular_bipyramid": {
        "area": [
            1.0833627134931465,
            1.1435594439222496,
            1.1487970342011955,
            1.1493845865425816,
            1.1494413957683474,
        ],
        "volume": [
            0.10597381596532714,
            0.11113351781328082,
            0.11157193942436726,
            0.11162340563907751,
            0.11162858228124527,
        ],
        "bending": [
            1337.553719758506,
            1383.4891654889163,
            1392.9132951434287,
            1390.6490421046456,
            1390.3229016830487,
        ],
        "total": [
            1338.862772266585,
            1386.213859358769,
            1395.7853555274887,
            1393.5379125544398,
            1393.2134032011097,
        ],
        "global_changes": [
            0.05263979126667584,
            0.00685742698962656,
            0.001610163743407077,
            0.00023286725851271646,
        ],
        "force_changes": [
            0.3578839778990914,
            0.030876498875537315,
            0.014312545942470273,
            0.0012813709797863779,
        ],
    },
    "asymmetric_valence3_triangular_bipyramid": {
        "area": [
            1.0961815450774315,
            1.1567455961252535,
            1.1620448731439783,
            1.1626400894373452,
            1.162697655107095,
        ],
        "volume": [
            0.1075104362968244,
            0.11274495382157347,
            0.11318973254602055,
            0.11324194502084432,
            0.11324719672432296,
        ],
        "bending": [
            1345.9666747741842,
            1393.1994641324934,
            1402.7341179343068,
            1400.3614566743443,
            1400.0260097909122,
        ],
        "total": [
            1347.5394894869935,
            1396.3108505876362,
            1406.0047281006946,
            1403.650237720286,
            1403.3165542804725,
        ],
        "global_changes": [
            0.0523572782560774,
            0.006894626539523376,
            0.0016745963461937828,
            0.00023772548947482714,
        ],
        "force_changes": [
            1.9529190356076531,
            0.4006744681990247,
            0.06615148797753403,
            0.015142500944417207,
        ],
    },
}


def read_decimal_csv(path: Path) -> list[list[Decimal]]:
    with path.open(newline="") as stream:
        return [[Decimal(value) for value in row] for row in csv.reader(stream)]


def read_int_csv(path: Path) -> list[list[int]]:
    with path.open(newline="") as stream:
        return [[int(value) for value in row] for row in csv.reader(stream)]


def validate_bipyramid_fixture_data(
    symmetric_vertices: list[list[Decimal]],
    symmetric_faces: list[list[int]],
    asymmetric_vertices: list[list[Decimal]],
    asymmetric_faces: list[list[int]],
) -> tuple[bool, str]:
    if symmetric_vertices != EXPECTED_SYMMETRIC_BIPYRAMID_VERTICES:
        return False, "symmetric bipyramid coordinates drifted"
    if symmetric_faces != EXPECTED_BIPYRAMID_FACES:
        return False, "symmetric bipyramid face identity or orientation drifted"
    if asymmetric_faces != EXPECTED_BIPYRAMID_FACES:
        return False, "asymmetric bipyramid face identity or orientation drifted"
    if len(symmetric_vertices) != 5 or any(
        len(row) != 3 for row in symmetric_vertices
    ):
        return False, "symmetric bipyramid coordinate cardinality drifted"
    if len(asymmetric_vertices) != 5 or any(
        len(row) != 3 for row in asymmetric_vertices
    ):
        return False, "asymmetric bipyramid coordinate cardinality drifted"
    expected_delta = [Decimal("0.071"), Decimal("-0.043"), Decimal("0.029")]
    actual_delta = [
        asymmetric_vertices[0][axis] - symmetric_vertices[0][axis]
        for axis in range(3)
    ]
    if (
        actual_delta != expected_delta
        or asymmetric_vertices[1:] != symmetric_vertices[1:]
    ):
        return False, "serialized asymmetric perturbation drifted"

    adjacency = [set() for _ in symmetric_vertices]
    directed_edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for face in symmetric_faces:
        for corner in range(3):
            left = face[corner]
            right = face[(corner + 1) % 3]
            adjacency[left].add(right)
            adjacency[right].add(left)
            directed_edges.setdefault(tuple(sorted((left, right))), []).append(
                (left, right)
            )
    if [len(neighbors) for neighbors in adjacency] != [3, 3, 4, 4, 4]:
        return False, "bipyramid vertex valence drifted"
    if (
        len(directed_edges) != 9
        or len(symmetric_vertices) - len(directed_edges) + len(symmetric_faces)
        != 2
    ):
        return False, "bipyramid edge count or Euler characteristic drifted"
    if any(
        len(uses) != 2 or uses[0] != (uses[1][1], uses[1][0])
        for uses in directed_edges.values()
    ):
        return False, "bipyramid is not a closed oppositely oriented edge manifold"

    for vertices, label in (
        (symmetric_vertices, "symmetric"),
        (asymmetric_vertices, "asymmetric"),
    ):
        points = [[float(value) for value in row] for row in vertices]
        center = [
            sum(point[axis] for point in points) / len(points)
            for axis in range(3)
        ]
        for face in symmetric_faces:
            a, b, c = (points[source] for source in face)
            ab = [b[axis] - a[axis] for axis in range(3)]
            ac = [c[axis] - a[axis] for axis in range(3)]
            normal = [
                ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2],
                ab[0] * ac[1] - ab[1] * ac[0],
            ]
            face_center = [
                (a[axis] + b[axis] + c[axis]) / 3.0
                for axis in range(3)
            ]
            outward = sum(
                normal[axis] * (face_center[axis] - center[axis])
                for axis in range(3)
            )
            if not math.isfinite(outward) or outward <= 0.0:
                return False, f"{label} bipyramid winding is not outward"
    return True, "serialized bipyramid fixtures validated"


def validate_serialized_bipyramids() -> tuple[bool, str]:
    return validate_bipyramid_fixture_data(
        read_decimal_csv(BIPYRAMID / "vertices.csv"),
        read_int_csv(BIPYRAMID / "faces.csv"),
        read_decimal_csv(ASYMMETRIC_BIPYRAMID / "vertices.csv"),
        read_int_csv(ASYMMETRIC_BIPYRAMID / "faces.csv"),
    )


def close_measurement(actual: object, expected: float) -> bool:
    return (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and math.isfinite(float(actual))
        and math.isclose(float(actual), expected, rel_tol=5.0e-10, abs_tol=5.0e-12)
    )


def validate_convergence_payload(payload: dict[str, object]) -> tuple[bool, str]:
    try:
        if payload["status"] != "passed":
            return False, "enabled harness did not pass"
        if payload["broader_topology_quadrature_targets_met"] is not False:
            return False, "top-level scientific target decision drifted"
        if payload["broader_topology_activation_blocked"] is not True:
            return False, "top-level activation blocker drifted"
        contract = payload["quadrature_study_contract"]
        if not isinstance(contract, dict):
            return False, "quadrature study contract is missing"
        if set(contract) != set(EXPECTED_STUDY_CONTRACT):
            return False, "quadrature study contract schema drifted"
        for key, expected in EXPECTED_STUDY_CONTRACT.items():
            actual = contract[key]
            if isinstance(expected, str):
                if actual != expected:
                    return False, f"study contract {key} drifted"
            elif not close_measurement(actual, float(expected)):
                return False, f"study contract {key} drifted"

        reports = payload["quadrature_convergence"]
        if not isinstance(reports, list) or len(reports) != 2:
            return False, "exactly two convergence reports are required"
        by_name = {
            report["name"]: report
            for report in reports
            if isinstance(report, dict) and isinstance(report.get("name"), str)
        }
        if set(by_name) != set(EXPECTED_CONVERGENCE):
            return False, "convergence fixture identity drifted"

        for name, expected in EXPECTED_CONVERGENCE.items():
            report = by_name[name]
            required_true = (
                "passed",
                "study_completed",
                "activation_blocked",
                "all_plans_validated",
                "all_rows_structurally_valid",
                "all_finite",
            )
            required_false = (
                "scientific_targets_met",
                "all_rows_valid",
                "two_successive_global_targets_met",
                "two_successive_force_targets_met",
            )
            if any(report[field] is not True for field in required_true):
                return False, f"{name} completion or blocker field drifted"
            if any(report[field] is not False for field in required_false):
                return False, f"{name} scientific failure field drifted"

            levels = report["levels"]
            if not isinstance(levels, list) or len(levels) != 5:
                return False, f"{name} requires five convergence levels"
            for index, level in enumerate(levels):
                if not isinstance(level, dict):
                    return False, f"{name} convergence level is not an object"
                if (
                    level["depth"] != EXPECTED_DEPTHS[index]
                    or level["samples_per_face"] != EXPECTED_SAMPLES[index]
                ):
                    return False, f"{name} depth or sample sequence drifted"
                if (
                    level["plan_validated"] is not True
                    or level["rows_structurally_valid"] is not True
                    or level["finite"] is not True
                ):
                    return False, f"{name} level structure is incomplete"
                if level["rows_valid"] is not (index < 4):
                    return False, f"{name} row-invariant decision drifted"
                measurements = (
                    ("area", expected["area"][index]),
                    ("full_divergence_volume", expected["volume"][index]),
                    ("bending_energy", expected["bending"][index]),
                    ("total_energy", expected["total"][index]),
                )
                if any(
                    not close_measurement(level[field], value)
                    for field, value in measurements
                ):
                    return False, f"{name} level measurement drifted"
                residual = level["maximum_row_invariant_residual"]
                if (
                    not isinstance(residual, (int, float))
                    or isinstance(residual, bool)
                    or not math.isfinite(float(residual))
                ):
                    return False, f"{name} row residual is nonfinite"
                if index == 4 and not (
                    float(residual)
                    > float(EXPECTED_STUDY_CONTRACT["row_invariant_target"])
                    and math.isclose(
                        float(residual),
                        1.0516032489249483e-12,
                        rel_tol=5.0e-6,
                        abs_tol=1.0e-15,
                    )
                ):
                    return False, f"{name} depth-4 row blocker drifted"

            for field in ("global_changes", "force_changes"):
                payload_field = (
                    "global_relative_changes"
                    if field == "global_changes"
                    else "force_relative_changes"
                )
                actual_values = report[payload_field]
                expected_values = expected[field]
                if not isinstance(actual_values, list) or len(actual_values) != 4:
                    return False, f"{name} {field} sequence is incomplete"
                if any(
                    not close_measurement(actual, wanted)
                    for actual, wanted in zip(actual_values, expected_values)
                ):
                    return False, f"{name} {field} measurements drifted"
        return True, "complete convergence blocker validated"
    except (IndexError, KeyError, TypeError, ValueError) as error:
        return False, f"convergence schema error: {error}"


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


def gsl_flags(option: str, env: dict[str, str]) -> list[str]:
    result = run(["gsl-config", option], env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "gsl-config failed")
    return shlex.split(result.stdout)


def build(binary: Path, env: dict[str, str], enabled: bool) -> None:
    compiler = env.get("CXX") or shutil.which("g++") or shutil.which("c++")
    if not compiler or not shutil.which("gsl-config"):
        raise RuntimeError("a C++17 compiler and gsl-config are required")
    sources = sorted(
        source
        for source in (ROOT / "src").rglob("*.cpp")
        if source.name not in {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    )
    command = [
        compiler,
        "-std=c++17",
        "-Iinclude",
        "-Iinclude/energy_force",
        "-Iinclude/linalg",
        "-Iinclude/mesh",
        "-Iinclude/model",
        "-Iinclude/parameters",
        *gsl_flags("--cflags", env),
    ]
    if enabled:
        root = env.get("OPENSUBDIV_ROOT")
        if not root:
            raise RuntimeError("OPENSUBDIV_ROOT is required for the enabled proof")
        command.extend(
            [
                "-DUSE_OPENSUBDIV_VALENCE3",
                f"-I{root}/include",
            ]
        )
    command.extend([str(EXPERIMENT), *(str(source) for source in sources)])
    command.extend(gsl_flags("--libs", env))
    if enabled:
        root = env["OPENSUBDIV_ROOT"]
        command.extend(
            [
                f"-L{root}/lib",
                f"-L{root}/lib64",
                f"-Wl,-rpath,{root}/lib",
                f"-Wl,-rpath,{root}/lib64",
                "-losdCPU",
            ]
        )
    command.extend(["-o", str(binary)])
    result = run(command, env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def execute(binary: Path, env: dict[str, str]) -> dict[str, object]:
    result = run(
        [
            str(binary),
            str(TETRA / "vertices.csv"),
            str(TETRA / "faces.csv"),
            str(MIXED / "vertices.csv"),
            str(MIXED / "faces.csv"),
            str(BIPYRAMID / "vertices.csv"),
            str(BIPYRAMID / "faces.csv"),
            str(ASYMMETRIC_BIPYRAMID / "vertices.csv"),
            str(ASYMMETRIC_BIPYRAMID / "faces.csv"),
        ],
        env,
    )
    if result.returncode:
        raise RuntimeError(
            f"harness exited {result.returncode}: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    return json.loads(result.stdout)


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    if "default_off_contract" in payload:
        print(f"default_off_contract: {payload['default_off_contract']}")
    if "reason" in payload:
        print(f"reason: {payload['reason']}")
    for fixture in payload.get("fixtures", []):
        print(
            f"{fixture['name']}: area={fixture['area']:.17g}, "
            f"volume={fixture['full_divergence_volume']:.17g}, "
            f"max_abs_force={fixture['max_abs_force']}"
        )
    for convergence in payload.get("quadrature_convergence", []):
        print(
            f"{convergence['name']} quadrature: "
            f"evidence_packet_passed={convergence['passed']}, "
            f"study_completed={convergence['study_completed']}, "
            f"scientific_targets_met={convergence['scientific_targets_met']}, "
            f"activation_blocked={convergence['activation_blocked']}, "
            f"global_changes={convergence['global_relative_changes']}, "
            f"force_changes={convergence['force_relative_changes']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-opensubdiv", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    try:
        fixtures_valid, fixture_reason = validate_serialized_bipyramids()
        if not fixtures_valid:
            raise RuntimeError(fixture_reason)
        with tempfile.TemporaryDirectory(prefix="slimed-valence3-") as temp:
            temp_path = Path(temp)
            default_binary = temp_path / "valence3-default"
            build(default_binary, env, enabled=False)
            default_payload = execute(default_binary, env)
            default_passed = (
                default_payload.get("status") == "passed"
                and default_payload.get("dependency_disabled_contract_passed")
                is True
            )
            if not env.get("OPENSUBDIV_ROOT"):
                payload = {
                    "status": "passed" if default_passed else "failed",
                    "default_off_contract": default_passed,
                    "enabled_status": "skipped",
                    "reason": (
                        "OPENSUBDIV_ROOT is not set; the default-off contract "
                        "ran, while the enabled proof remains opt-in."
                    ),
                }
                emit(payload, args.json)
                if args.require_opensubdiv:
                    return 2
                return 0 if default_passed else 1

            enabled_binary = temp_path / "valence3-enabled"
            build(enabled_binary, env, enabled=True)
            enabled_payload = execute(enabled_binary, env)
        evidence_valid, evidence_reason = validate_convergence_payload(
            enabled_payload
        )
        passed = evidence_valid and default_passed
        enabled_payload["default_off_contract"] = default_passed
        enabled_payload["convergence_evidence_validated"] = evidence_valid
        if not evidence_valid:
            enabled_payload["evidence_validation_error"] = evidence_reason
        enabled_payload["status"] = "passed" if passed else "failed"
        emit(enabled_payload, args.json)
        return 0 if passed else 1
    except (RuntimeError, json.JSONDecodeError) as error:
        emit({"status": "failed", "reason": str(error)}, args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
