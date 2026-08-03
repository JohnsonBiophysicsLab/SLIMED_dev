#!/usr/bin/env python3
"""Inventory the Step-1 CUDA backend shell and protected scope boundaries."""

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
    Anchor("api", Path("include/cuda/Cuda_backend.hpp"), "enum class ErrorCode"),
    Anchor("api", Path("include/cuda/Cuda_backend.hpp"), "struct DeviceCapabilities"),
    Anchor("api", Path("include/cuda/Cuda_backend.hpp"), "class DeviceContext final"),
    Anchor("api", Path("include/cuda/Cuda_backend.hpp"), "DeviceContext(const DeviceContext &) = delete"),
    Anchor("stub", Path("src/cuda/Cuda_backend_stub.cpp"), "ErrorCode::NotCompiled"),
    Anchor("stub", Path("src/cuda/Cuda_backend_stub.cpp"), 'operation = "compile_time"'),
    Anchor("api", Path("src/cuda/Cuda_backend_common.cpp"), 'return "not_compiled"'),
    Anchor("cuda", Path("src/cuda/Cuda_backend.cu"), "cuDevicePrimaryCtxRetain"),
    Anchor("cuda", Path("src/cuda/Cuda_backend.cu"), "cuDevicePrimaryCtxRelease"),
    Anchor("cuda", Path("src/cuda/Cuda_backend.cu"), "cuStreamCreate(&stream, CU_STREAM_NON_BLOCKING)"),
    Anchor("cuda", Path("src/cuda/Cuda_backend.cu"), "cuStreamDestroy"),
    Anchor("cuda", Path("src/cuda/Cuda_backend.cu"), "cudaRuntimeGetVersion"),
    Anchor("cuda", Path("include/cuda/detail/Cuda_context_lifetime.hpp"), "if (retained_ && !pushed_ && stream_ == 0)"),
    Anchor("cuda", Path("tests/test_cuda_backend.cpp"), "FailedCreationPopIsRetriedWithoutAnExtraPush"),
    Anchor("build", Path("Makefile"), "cuda_backend_report:"),
    Anchor("build", Path("Makefile"), "cuda_backend_stub_report:"),
    Anchor("build", Path("Makefile"), "-arch=$(CUDA_COMPUTE_ARCH) -code=$(CUDA_SM_CODE)"),
    Anchor("runner", Path("scripts/run_cuda_backend_report.py"), "NO_CUDA_EXIT_CODE = 77"),
    Anchor("runner", Path("scripts/run_cuda_backend_report.py"), '"cuda_backend_report"'),
    Anchor("evidence", Path("analysis/cuda_backend_report_rtx4050.json"), '"completed_context_lifecycle_iterations": 20'),
    Anchor("scope", Path("docs/cuda_backend_shell.md"), "Production evaluator routing remains disabled."),
    Anchor("scope", Path("docs/cuda_backend_shell.md"), "No scientific device buffer is"),
    Anchor("review", Path("docs/cuda_backend_shell.md"), "dedicated CUDA production reviewer"),
)

FORBIDDEN_PUBLIC_HEADER_TOKENS = (
    "#include <cuda",
    "CUcontext",
    "CUstream",
    "cudaStream_t",
    "cudaError_t",
)

FORBIDDEN_CUDA_IMPLEMENTATION_TOKENS = (
    "__global__",
    "cudaMalloc",
    "cudaMemcpy",
    "cuMemAlloc",
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
    header_text = (root / "include/cuda/Cuda_backend.hpp").read_text(encoding="utf-8")
    for token in FORBIDDEN_PUBLIC_HEADER_TOKENS:
        if token in header_text:
            forbidden.append({"path": "include/cuda/Cuda_backend.hpp", "token": token})

    cuda_text = (root / "src/cuda/Cuda_backend.cu").read_text(encoding="utf-8")
    for token in FORBIDDEN_CUDA_IMPLEMENTATION_TOKENS:
        if token in cuda_text:
            forbidden.append({"path": "src/cuda/Cuda_backend.cu", "token": token})

    production_sources = [
        root / "src/energy_force/Energy_force_evaluator.cpp",
        root / "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
        root / "src/model/Energy_minimization.cpp",
        root / "src/Run_flat.cpp",
        root / "src/Run_dynamics_flat.cpp",
    ]
    for path in production_sources:
        text = path.read_text(encoding="utf-8")
        if "cuda_backend" in text or "Cuda_backend" in text:
            forbidden.append(
                {"path": str(path.relative_to(root)), "token": "CUDA backend route reference"}
            )

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
