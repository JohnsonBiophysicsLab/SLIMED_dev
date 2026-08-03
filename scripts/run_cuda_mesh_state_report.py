#!/usr/bin/env python3
"""Build and run the optional persistent CUDA mesh-state evidence report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


NO_CUDA_EXIT_CODE = 77
REQUIRED_GEOMETRY_CASES = {
    "natural",
    "permuted",
    "curved",
    "boundary_ghost",
    "degenerate",
    "production_cpu",
}
REQUIRED_MEMBRANE_CASES = REQUIRED_GEOMETRY_CASES


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def executable(explicit: str | None, fallback: str) -> str | None:
    candidate = explicit or fallback
    path = Path(candidate)
    return str(path) if path.is_file() else shutil.which(candidate)


def build_command(
    make: str,
    *,
    stub: bool,
    nvcc: str | None,
    host_cxx: str,
    compute_arch: str,
    sm_code: str,
) -> list[str]:
    if stub:
        return [make, "cuda_mesh_state_stub_report", f"CXX={host_cxx}"]
    if nvcc is None:
        raise ValueError("nvcc is required for a CUDA build")
    return [
        make,
        "cuda_mesh_state_report",
        f"CUDA_NVCC={nvcc}",
        f"CUDA_HOST_CXX={host_cxx}",
        f"CUDA_COMPUTE_ARCH={compute_arch}",
        f"CUDA_SM_CODE={sm_code}",
    ]


def tool_version(command: str) -> str:
    result = subprocess.run(
        [command, "--version"], capture_output=True, text=True, check=False
    )
    return (result.stdout or result.stderr).strip()


def gpu_inventory() -> dict[str, str]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {"status": "nvidia-smi unavailable"}
    result = subprocess.run(
        [
            nvidia_smi,
            "--query-gpu=name,driver_version,memory.total,compute_cap",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {"status": "query failed", "message": result.stderr.strip()}
    fields = [field.strip() for field in result.stdout.splitlines()[0].split(",")]
    return dict(
        zip(
            ["name", "driver_version", "memory_total_mib", "compute_capability"],
            fields,
        )
    )


def teardown_complete(report: dict[str, object]) -> bool:
    return (
        report.get("closed") is True
        and report.get("cleanup_pending") is False
        and report.get("cleanup_error_code") == "none"
        and report.get("final_resident_bytes") == 0
        and report.get("allocation_free_balance") is True
        and report.get("successful_frees") == report.get("final_allocations")
    )


def geometry_complete(report: dict[str, object]) -> bool:
    error = report.get("geometry_max_abs_error")
    cases = report.get("geometry_cases")
    if not isinstance(cases, dict) or set(cases) != REQUIRED_GEOMETRY_CASES:
        return False
    for name in REQUIRED_GEOMETRY_CASES:
        case = cases.get(name)
        if not isinstance(case, dict):
            return False
        case_error = case.get("max_abs_error")
        if not (
            case.get("pass") is True
            and case.get("cpu_parity") is True
            and case.get("repeatable") is True
            and case.get("ghost_zero") is True
            and case.get("degenerate_zero") is True
            and case.get("permutation_equal") is True
            and isinstance(case_error, (int, float))
            and case_error <= 1.0e-12
        ):
            return False
    return (
        report.get("geometry_repeatable") is True
        and isinstance(error, (int, float))
        and error <= 1.0e-12
    )


def membrane_complete(report: dict[str, object]) -> bool:
    error = report.get("membrane_max_abs_error")
    cases = report.get("membrane_cases")
    if not isinstance(cases, dict) or set(cases) != REQUIRED_MEMBRANE_CASES:
        return False
    for name in REQUIRED_MEMBRANE_CASES:
        case = cases.get(name)
        if not isinstance(case, dict):
            return False
        case_error = case.get("max_abs_error")
        if not (
            case.get("pass") is True
            and case.get("cpu_parity") is True
            and case.get("repeatable") is True
            and case.get("structured_degeneracy") is True
            and case.get("recoverable") is True
            and case.get("permutation_equal") is True
            and isinstance(case_error, (int, float))
            and case_error <= 1.0e-12
        ):
            return False
    return (
        report.get("membrane_repeatable") is True
        and report.get("membrane_degeneracy_handled") is True
        and isinstance(error, (int, float))
        and error <= 1.0e-12
    )


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    make = executable(args.make, "make")
    host_cxx = executable(args.host_cxx, os.environ.get("CXX", "g++"))
    nvcc = None if args.stub else executable(args.nvcc, "nvcc")
    if make is None or host_cxx is None:
        sys.stderr.write("make and a host C++ compiler are required\n")
        return 1
    if not args.stub and nvcc is None:
        print(json.dumps({"status": "skipped", "reason": "nvcc not found"}))
        return NO_CUDA_EXIT_CODE if args.require_cuda else 0
    command = build_command(
        make,
        stub=args.stub,
        nvcc=nvcc,
        host_cxx=host_cxx,
        compute_arch=args.compute_arch,
        sm_code=args.sm_code,
    )
    build = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if build.returncode:
        sys.stderr.write(build.stdout + build.stderr)
        return build.returncode
    binary = root / "bin" / (
        "cuda_mesh_state_stub_report" if args.stub else "cuda_mesh_state_report"
    )
    execution = subprocess.run(
        [str(binary), "--device", str(args.device), "--iterations", str(args.iterations)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    lines = [line for line in execution.stdout.splitlines() if line.strip()]
    if not lines:
        sys.stderr.write("mesh-state report produced no JSON\n" + execution.stderr)
        return 1
    try:
        report = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        sys.stderr.write(f"invalid mesh-state JSON: {error}\n{execution.stdout}")
        return 1
    if report.get("status") == "pass":
        if not geometry_complete(report):
            sys.stderr.write(
                "mesh-state report claimed pass without geometry parity and repeatability\n"
            )
            return 1
        if not membrane_complete(report):
            sys.stderr.write(
                "mesh-state report claimed pass without complete membrane parity, repeatability, and recovery\n"
            )
            return 1
        if not teardown_complete(report):
            sys.stderr.write(
                "mesh-state report claimed pass without complete, balanced teardown\n"
            )
            return 1
    report["cuda_required"] = args.require_cuda
    report["build"] = {
        "target": command[1],
        "command": command,
        "nvcc": nvcc or "not used",
        "nvcc_version": tool_version(nvcc) if nvcc else "not used",
        "host_cxx": host_cxx,
        "host_cxx_version": tool_version(host_cxx),
        "compute_arch": args.compute_arch if not args.stub else "not used",
        "sm_code": args.sm_code if not args.stub else "not used",
    }
    if not args.stub:
        report["gpu"] = gpu_inventory()
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.write_text(encoded + "\n")
    print(encoded)
    if execution.returncode == NO_CUDA_EXIT_CODE:
        return NO_CUDA_EXIT_CODE if args.require_cuda and not args.stub else 0
    return execution.returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root")
    result.add_argument("--output")
    result.add_argument("--make")
    result.add_argument("--nvcc")
    result.add_argument("--host-cxx")
    result.add_argument("--compute-arch", default="compute_89")
    result.add_argument("--sm-code", default="sm_89")
    result.add_argument("--device", type=int, default=0)
    result.add_argument("--iterations", type=int, default=20)
    result.add_argument("--stub", action="store_true")
    result.add_argument("--require-cuda", action="store_true")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.device < 0 or args.iterations <= 0:
        parser().error("device must be nonnegative and iterations must be positive")
    if args.stub and args.require_cuda:
        parser().error("--stub and --require-cuda are mutually exclusive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
