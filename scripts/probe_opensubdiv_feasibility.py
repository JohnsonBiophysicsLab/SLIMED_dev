#!/usr/bin/env python3
"""Opt-in OpenSubdiv Far feasibility probe for SLIMED.

This script is intentionally inert for default builds. It only compiles a
temporary OpenSubdiv prototype when an OpenSubdiv install is discoverable or
when OPENSUBDIV_ROOT is supplied by the caller.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap


PROBE_SOURCE = r"""
#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>

#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace OpenSubdiv;

struct Point {
    float x;
    float y;
    float z;
};

struct MeshCase {
    std::string name;
    int numVertices = 0;
    std::vector<int> vertsPerFace;
    std::vector<int> vertIndices;
    std::vector<Point> points;
    int sampleFace = 0;
};

static void append_face(MeshCase &mesh, int a, int b, int c) {
    mesh.vertsPerFace.push_back(3);
    mesh.vertIndices.push_back(a);
    mesh.vertIndices.push_back(b);
    mesh.vertIndices.push_back(c);
}

static MeshCase make_regular_lattice_case() {
    MeshCase mesh;
    mesh.name = "regular_triangular_lattice";
    const int n = 6;
    mesh.numVertices = (n + 1) * (n + 1);
    mesh.points.reserve(mesh.numVertices);
    for (int j = 0; j <= n; ++j) {
        for (int i = 0; i <= n; ++i) {
            mesh.points.push_back(Point{
                static_cast<float>(i + 0.5 * j),
                static_cast<float>(0.8660254037844386 * j),
                static_cast<float>(0.03 * std::sin(0.7 * (i + j)))});
        }
    }

    auto id = [n](int i, int j) { return j * (n + 1) + i; };
    for (int j = 0; j < n; ++j) {
        for (int i = 0; i < n; ++i) {
            if (i == 2 && j == 2) {
                mesh.sampleFace = static_cast<int>(mesh.vertsPerFace.size());
            }
            append_face(mesh, id(i, j), id(i + 1, j), id(i, j + 1));
            append_face(mesh, id(i + 1, j), id(i + 1, j + 1), id(i, j + 1));
        }
    }
    return mesh;
}

static MeshCase make_irregular_fixture_case() {
    MeshCase mesh;
    mesh.name = "synthetic_11_control_fixture_topology";
    mesh.numVertices = 11;
    mesh.points = {
        {-0.70f, -0.86f, 0.01f},
        {-0.18f, -0.92f, -0.02f},
        {0.00f, 0.00f, 0.04f},
        {0.58f, -0.78f, 0.03f},
        {-0.78f, -0.05f, -0.03f},
        {-0.12f, 0.56f, 0.02f},
        {0.64f, 0.08f, -0.01f},
        {1.16f, -0.58f, 0.05f},
        {-0.30f, 1.12f, -0.04f},
        {0.54f, 1.06f, 0.03f},
        {1.20f, 0.46f, 0.00f},
    };

    mesh.sampleFace = 0;
    append_face(mesh, 2, 5, 6);
    append_face(mesh, 1, 2, 5);
    append_face(mesh, 9, 5, 6);
    append_face(mesh, 3, 6, 2);
    append_face(mesh, 0, 1, 2);
    append_face(mesh, 0, 2, 3);
    append_face(mesh, 4, 5, 1);
    append_face(mesh, 4, 9, 5);
    append_face(mesh, 7, 3, 6);
    append_face(mesh, 7, 6, 9);
    append_face(mesh, 4, 8, 9);
    append_face(mesh, 3, 7, 10);
    return mesh;
}

static Far::TopologyRefiner *create_refiner(MeshCase const &mesh) {
    typedef Far::TopologyDescriptor Descriptor;

    Descriptor desc;
    desc.numVertices = mesh.numVertices;
    desc.numFaces = static_cast<int>(mesh.vertsPerFace.size());
    desc.numVertsPerFace = mesh.vertsPerFace.data();
    desc.vertIndicesPerFace = mesh.vertIndices.data();

    Sdc::Options options;
    options.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);

    return Far::TopologyRefinerFactory<Descriptor>::Create(
        desc,
        Far::TopologyRefinerFactory<Descriptor>::Options(
            Sdc::SCHEME_LOOP, options));
}

static void accumulate(Point const *points,
                       Far::LimitStencil const &stencil,
                       float const *weights,
                       float out[3]) {
    out[0] = out[1] = out[2] = 0.0f;
    Far::Index const *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i) {
        Point const &point = points[indices[i]];
        out[0] += weights[i] * point.x;
        out[1] += weights[i] * point.y;
        out[2] += weights[i] * point.z;
    }
}

static bool finite3(float const values[3]) {
    return std::isfinite(values[0]) && std::isfinite(values[1]) &&
           std::isfinite(values[2]);
}

static int run_case(MeshCase const &mesh) {
    Far::TopologyRefiner *refiner = create_refiner(mesh);
    if (!refiner) {
        std::cerr << "failed to create refiner for " << mesh.name << "\n";
        return 2;
    }

    Far::TopologyRefiner::AdaptiveOptions adaptiveOptions(3);
    refiner->RefineAdaptive(adaptiveOptions);

    const float slimedV[3] = {1.0f / 3.0f, 0.20f, 0.05f};
    const float slimedW[3] = {1.0f / 3.0f, 0.30f, 0.85f};
    float s[3];
    float t[3];
    for (int i = 0; i < 3; ++i) {
        s[i] = slimedW[i];
        t[i] = slimedV[i];
    }

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = mesh.sampleFace;
    location.numLocations = 3;
    location.s = s;
    location.t = t;

    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;

    Far::LimitStencilTable const *stencils =
        Far::LimitStencilTableFactory::Create(
            *refiner, locations, 0, 0, stencilOptions);
    if (!stencils) {
        std::cerr << "failed to create limit stencils for " << mesh.name
                  << "\n";
        delete refiner;
        return 3;
    }

    std::cout << "{\"case\":\"" << mesh.name << "\",";
    std::cout << "\"control_vertex_count\":" << mesh.numVertices << ",";
    std::cout << "\"face_count\":" << mesh.vertsPerFace.size() << ",";
    std::cout << "\"sample_face\":" << mesh.sampleFace << ",";
    std::cout << "\"slimed_to_opensubdiv_uv\":\"s=w,t=v (prototype mapping)\",";
    std::cout << "\"samples\":[";

    for (int sample = 0; sample < stencils->GetNumStencils(); ++sample) {
        Far::LimitStencil stencil = stencils->GetLimitStencil(sample);
        if (!stencil.GetDuWeights() || !stencil.GetDvWeights() ||
            !stencil.GetDuuWeights() || !stencil.GetDuvWeights() ||
            !stencil.GetDvvWeights()) {
            std::cerr << "missing derivative weights for " << mesh.name
                      << "\n";
            delete stencils;
            delete refiner;
            return 4;
        }

        float position[3], du[3], dv[3], duu[3], duv[3], dvv[3];
        accumulate(mesh.points.data(), stencil, stencil.GetWeights(), position);
        accumulate(mesh.points.data(), stencil, stencil.GetDuWeights(), du);
        accumulate(mesh.points.data(), stencil, stencil.GetDvWeights(), dv);
        accumulate(mesh.points.data(), stencil, stencil.GetDuuWeights(), duu);
        accumulate(mesh.points.data(), stencil, stencil.GetDuvWeights(), duv);
        accumulate(mesh.points.data(), stencil, stencil.GetDvvWeights(), dvv);
        if (!finite3(position) || !finite3(du) || !finite3(dv) ||
            !finite3(duu) || !finite3(duv) || !finite3(dvv)) {
            std::cerr << "non-finite evaluated value for " << mesh.name
                      << "\n";
            delete stencils;
            delete refiner;
            return 5;
        }

        if (sample > 0) {
            std::cout << ",";
        }
        std::cout << "{\"index\":" << sample << ",";
        std::cout << "\"source_ids\":[";
        Far::Index const *indices = stencil.GetVertexIndices();
        for (int i = 0; i < stencil.GetSize(); ++i) {
            if (i > 0) {
                std::cout << ",";
            }
            std::cout << indices[i];
        }
        std::cout << "],\"weight_count\":" << stencil.GetSize();
        std::cout << ",\"position_x\":" << std::setprecision(9)
                  << position[0];
        std::cout << "}";
    }
    std::cout << "]}" << std::endl;

    delete stencils;
    delete refiner;
    return 0;
}

int main() {
    int status = run_case(make_regular_lattice_case());
    if (status != 0) {
        return status;
    }
    status = run_case(make_irregular_fixture_case());
    if (status != 0) {
        return status;
    }
    return 0;
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe an optional OpenSubdiv Far install without touching SLIMED builds."
    )
    parser.add_argument(
        "--opensubdiv-root",
        default=os.environ.get("OPENSUBDIV_ROOT"),
        help="OpenSubdiv install prefix. Defaults to OPENSUBDIV_ROOT.",
    )
    parser.add_argument(
        "--require-opensubdiv",
        action="store_true",
        help="Return non-zero instead of skip status when OpenSubdiv is absent.",
    )
    parser.add_argument(
        "--cxx",
        default=os.environ.get("CXX", "c++"),
        help="C++ compiler to use for the temporary probe.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the probe status as JSON.",
    )
    return parser.parse_args()


def candidate_roots(explicit_root: str | None) -> list[Path]:
    roots: list[Path] = []
    if explicit_root:
        roots.append(Path(explicit_root))
    roots.extend(
        [
            Path("/opt/homebrew/opt/opensubdiv"),
            Path("/usr/local/opt/opensubdiv"),
            Path("/usr/local"),
            Path("/usr"),
        ]
    )
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def find_install(root: Path) -> tuple[Path, Path] | None:
    include_dir = root / "include"
    header = include_dir / "opensubdiv" / "far" / "topologyDescriptor.h"
    if not header.exists():
        return None

    for lib_dir in (root / "lib", root / "lib64"):
        if glob.glob(str(lib_dir / "libosdCPU.*")):
            return include_dir, lib_dir
    return None


def status_payload(status: str, details: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {"status": status}
    payload.update(details)
    return payload


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(f"status: {payload['status']}")
    for key, value in payload.items():
        if key != "status":
            print(f"{key}: {value}")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    args = parse_args()

    install: tuple[Path, Path] | None = None
    checked_roots = candidate_roots(args.opensubdiv_root)
    for root in checked_roots:
        install = find_install(root)
        if install:
            break

    if not install:
        payload = status_payload(
            "skipped",
            {
                "reason": "OpenSubdiv headers/libs were not found",
                "checked_roots": [str(root) for root in checked_roots],
                "next_step": "Set OPENSUBDIV_ROOT to an install prefix and rerun.",
            },
        )
        emit(payload, args.json)
        return 2 if args.require_opensubdiv else 0

    include_dir, lib_dir = install
    with tempfile.TemporaryDirectory(prefix="slimed-opensubdiv-probe-") as tmp:
        tmp_path = Path(tmp)
        source_path = tmp_path / "opensubdiv_probe.cpp"
        binary_path = tmp_path / "opensubdiv_probe"
        source_path.write_text(textwrap.dedent(PROBE_SOURCE), encoding="utf-8")

        command = [
            args.cxx,
            "-std=c++17",
        ]
        command.extend(shlex.split(os.environ.get("OPENSUBDIV_CXXFLAGS", "")))
        command.extend(
            [
                str(source_path),
                "-I",
                str(include_dir),
                "-L",
                str(lib_dir),
                f"-Wl,-rpath,{lib_dir}",
            ]
        )
        command.extend(shlex.split(os.environ.get("OPENSUBDIV_LDFLAGS", "")))
        command.extend(["-losdCPU", "-o", str(binary_path)])

        compile_result = run_command(command)
        if compile_result.returncode != 0:
            payload = status_payload(
                "compile_failed",
                {
                    "command": command,
                    "stdout": compile_result.stdout,
                    "stderr": compile_result.stderr,
                },
            )
            emit(payload, args.json)
            return compile_result.returncode

        run_result = run_command([str(binary_path)])
        if run_result.returncode != 0:
            payload = status_payload(
                "run_failed",
                {
                    "stdout": run_result.stdout,
                    "stderr": run_result.stderr,
                    "returncode": run_result.returncode,
                },
            )
            emit(payload, args.json)
            return run_result.returncode

    payload = status_payload(
        "passed",
        {
            "include_dir": str(include_dir),
            "lib_dir": str(lib_dir),
            "prototype_output": run_result.stdout.strip().splitlines(),
        },
    )
    emit(payload, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
