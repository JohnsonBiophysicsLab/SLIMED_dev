#!/usr/bin/env python3
"""Inventory the Step-2 canonical CUDA mesh pack and preflight boundaries."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Anchor:
    category: str
    path: Path
    needle: str


ANCHORS: tuple[Anchor, ...] = (
    Anchor("api", Path("include/cuda/Cuda_mesh_pack.hpp"), "struct RegularMeshPack"),
    Anchor("api", Path("include/cuda/Cuda_mesh_pack.hpp"), "struct MeshPackGenerations"),
    Anchor("api", Path("include/cuda/Cuda_mesh_pack.hpp"), "enum class EligibilityIssueCode"),
    Anchor("pack", Path("src/cuda/Cuda_mesh_pack.cpp"), '"mesh_pack.topology_generation"'),
    Anchor("pack", Path("src/cuda/Cuda_mesh_pack.cpp"), "evaluatedFaces.push_back(face)"),
    Anchor("pack", Path("src/cuda/Cuda_mesh_pack.cpp"), "pack.sourceOffsets.resize"),
    Anchor("pack", Path("src/cuda/Cuda_mesh_pack.cpp"), "pack.sourceOccurrences.resize"),
    Anchor("pack", Path("src/cuda/Cuda_mesh_pack.cpp"), "incidence plan must contain every canonical occurrence exactly once"),
    Anchor("preflight", Path("src/cuda/Cuda_mesh_pack.cpp"), "CudaNotExplicitlySelected"),
    Anchor("preflight", Path("src/cuda/Cuda_mesh_pack.cpp"), "UnsupportedRegularTopology"),
    Anchor("preflight", Path("src/cuda/Cuda_mesh_pack.cpp"), "AlternateEvaluatorUnsupported"),
    Anchor("preflight", Path("src/cuda/Cuda_mesh_pack.cpp"), "InsertionUnsupported"),
    Anchor("overflow", Path("include/cuda/detail/Cuda_checked_arithmetic.hpp"), "checked_multiply"),
    Anchor("test", Path("tests/test_cuda_mesh_pack.cpp"), "ExactRoundTripPreservesCanonicalInputs"),
    Anchor("test", Path("tests/test_cuda_mesh_pack.cpp"), "independent_incidence_oracle"),
    Anchor("test", Path("tests/test_cuda_mesh_pack.cpp"), "ContainerPermutationDoesNotChangeCanonicalPack"),
    Anchor("test", Path("tests/test_cuda_mesh_pack.cpp"), "ReportsAllRejectionsInStableMatrixOrder"),
    Anchor("scope", Path("docs/cuda_mesh_pack_preflight.md"), "Production evaluator routing remains disabled."),
    Anchor("scope", Path("docs/cuda_mesh_pack_preflight.md"), "allocates no GPU"),
    Anchor("review", Path("docs/cuda_mesh_pack_preflight.md"), "dedicated CUDA production reviewer"),
)

FORBIDDEN_PACK_TOKENS = (
    "#include <cuda",
    "#include \"cuda_runtime",
    "__global__",
    "cudaMalloc",
    "cudaMemcpy",
    "cuMemAlloc",
    "cuLaunchKernel",
)

PRODUCTION_SOURCES = (
    Path("src/energy_force/Energy_force_evaluator.cpp"),
    Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp"),
    Path("src/model/Energy_minimization.cpp"),
    Path("src/Run_flat.cpp"),
    Path("src/Run_dynamics_flat.cpp"),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def report(root: Path) -> dict[str, object]:
    located: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    for anchor in ANCHORS:
        path = root / anchor.path
        if not path.is_file():
            missing.append(
                {"category": anchor.category, "path": str(anchor.path), "needle": anchor.needle}
            )
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        match = next(
            (
                (line_number, line.strip())
                for line_number, line in enumerate(lines, start=1)
                if anchor.needle in line
            ),
            None,
        )
        if match is None:
            missing.append(
                {"category": anchor.category, "path": str(anchor.path), "needle": anchor.needle}
            )
        else:
            located.append(
                {
                    "category": anchor.category,
                    "path": str(anchor.path),
                    "line": match[0],
                    "source": match[1],
                }
            )

    forbidden: list[dict[str, str]] = []
    for relative in (Path("include/cuda/Cuda_mesh_pack.hpp"), Path("src/cuda/Cuda_mesh_pack.cpp")):
        text = (root / relative).read_text(encoding="utf-8")
        for token in FORBIDDEN_PACK_TOKENS:
            if token in text:
                forbidden.append({"path": str(relative), "token": token})

    route_tokens = ("Cuda_mesh_pack", "evaluate_cuda_eligibility", "build_regular_mesh_pack")
    for relative in PRODUCTION_SOURCES:
        text = (root / relative).read_text(encoding="utf-8")
        for token in route_tokens:
            if token in text:
                forbidden.append({"path": str(relative), "token": token})

    return {
        "status": "passed" if not missing and not forbidden else "failed",
        "located": located,
        "missing": missing,
        "forbidden": forbidden,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inventory = report(repo_root())
    print(json.dumps(inventory, indent=2, sort_keys=True))
    return 1 if args.check and inventory["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
