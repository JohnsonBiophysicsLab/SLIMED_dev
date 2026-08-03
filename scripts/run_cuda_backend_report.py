#!/usr/bin/env python3
"""Build and run the optional CUDA backend capability/lifetime report."""

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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_executable(explicit: str | None, fallback: str) -> str | None:
    candidate = explicit or fallback
    path = Path(candidate)
    if path.is_file():
        return str(path)
    return shutil.which(candidate)


def compiler_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        check=False,
        text=True,
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0 or not output:
        return f"unavailable (exit {completed.returncode})"
    return output


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
        return [make, "cuda_backend_stub_report", f"CXX={host_cxx}"]
    if nvcc is None:
        raise ValueError("nvcc is required for the CUDA report build command")
    return [
        make,
        "cuda_backend_report",
        f"CUDA_NVCC={nvcc}",
        f"CUDA_HOST_CXX={host_cxx}",
        f"CUDA_COMPUTE_ARCH={compute_arch}",
        f"CUDA_SM_CODE={sm_code}",
    ]


def skip_report(reason: str, *, required: bool) -> int:
    print(
        json.dumps(
            {
                "status": "skipped",
                "compiled": False,
                "available": False,
                "cuda_required": required,
                "reason": reason,
            },
            sort_keys=True,
        )
    )
    return NO_CUDA_EXIT_CODE if required else 0


def parse_report(stdout: str) -> dict[str, object]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("backend report produced no JSON output")
    return json.loads(lines[-1])


def run_report(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    make = detect_executable(args.make, "make")
    if make is None:
        sys.stderr.write("CUDA backend report failed: make was not found\n")
        return 1
    host_cxx = detect_executable(args.host_cxx, os.environ.get("CXX", "g++"))
    if host_cxx is None:
        sys.stderr.write(
            "CUDA backend report failed: host C++ compiler was not found\n"
        )
        return 1

    nvcc = None if args.stub else detect_executable(args.nvcc, "nvcc")
    if not args.stub and nvcc is None:
        return skip_report(
            "nvcc not found; optional CUDA backend report not built",
            required=args.require_cuda,
        )

    command = build_command(
        make,
        stub=args.stub,
        nvcc=nvcc,
        host_cxx=host_cxx,
        compute_arch=args.compute_arch,
        sm_code=args.sm_code,
    )
    build = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    if build.returncode != 0:
        sys.stderr.write(build.stdout)
        sys.stderr.write(build.stderr)
        return build.returncode

    binary_name = "cuda_backend_stub_report" if args.stub else "cuda_backend_report"
    execution = subprocess.run(
        [
            str(root / "bin" / binary_name),
            "--device",
            str(args.device),
            "--lifecycle-iterations",
            str(args.lifecycle_iterations),
        ],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    try:
        report = parse_report(execution.stdout)
    except (ValueError, json.JSONDecodeError) as error:
        sys.stderr.write(f"CUDA backend report returned invalid JSON: {error}\n")
        sys.stderr.write(execution.stdout)
        sys.stderr.write(execution.stderr)
        return 1

    report["cuda_required"] = args.require_cuda
    report["build"] = {
        "target": command[1],
        "command": command,
        "nvcc": nvcc if nvcc is not None else "not used",
        "nvcc_version": compiler_version(nvcc) if nvcc is not None else "not used",
        "host_cxx": host_cxx,
        "host_cxx_version": compiler_version(host_cxx),
        "compute_arch": args.compute_arch if not args.stub else "not used",
        "sm_code": args.sm_code if not args.stub else "not used",
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if execution.returncode == NO_CUDA_EXIT_CODE:
        return NO_CUDA_EXIT_CODE if args.require_cuda and not args.stub else 0
    if execution.returncode != 0:
        return execution.returncode
    return 0 if report.get("available") is True else 2


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--root", help="repository root")
    argument_parser.add_argument("--make", help="explicit make executable")
    argument_parser.add_argument("--nvcc", help="explicit nvcc executable")
    argument_parser.add_argument("--host-cxx", help="explicit host C++ compiler")
    argument_parser.add_argument("--compute-arch", default="compute_89")
    argument_parser.add_argument("--sm-code", default="sm_89")
    argument_parser.add_argument("--device", type=int, default=0)
    argument_parser.add_argument("--lifecycle-iterations", type=int, default=20)
    argument_parser.add_argument(
        "--stub",
        action="store_true",
        help="build and run the non-CUDA stub report",
    )
    argument_parser.add_argument(
        "--require-cuda",
        action="store_true",
        help="return exit 77 rather than a successful skip when CUDA is unavailable",
    )
    return argument_parser


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.device < 0:
        parser().error("--device must be nonnegative")
    if args.lifecycle_iterations <= 0:
        parser().error("--lifecycle-iterations must be positive")
    if args.stub and args.require_cuda:
        parser().error("--stub and --require-cuda are mutually exclusive")
    return run_report(args)


if __name__ == "__main__":
    raise SystemExit(main())
