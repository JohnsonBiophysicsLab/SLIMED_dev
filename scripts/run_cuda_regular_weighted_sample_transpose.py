#!/usr/bin/env python3
"""Build and run the optional CUDA regular weighted-sample transpose proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_cuda_regular_weighted_sample_forward as common


CUDA_SOURCE = Path("experiments/cuda_regular_weighted_sample_transpose.cu")
GAUSS_SOURCE = Path("src/mesh/Gauss_quadrature.cpp")
LINALG_SOURCE = Path("src/linear_algebra/Linear_algebra.cpp")
NO_CUDA_DEVICE_EXIT_CODE = 77


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_command(
    root: Path,
    nvcc: str,
    output: Path,
    compute_arch: str,
    sm_code: str,
    host_cxx: str,
) -> list[str]:
    return [
        nvcc,
        *common.cuda_compiler_flags(compute_arch, sm_code, host_cxx),
        "-I",
        str(root / "include"),
        str(root / CUDA_SOURCE),
        str(root / GAUSS_SOURCE),
        str(root / LINALG_SOURCE),
        "-lgsl",
        "-lgslcblas",
        "-lm",
        "-o",
        str(output),
    ]


def skip_report(reason: str, *, required: bool) -> int:
    print(
        json.dumps(
            {
                "status": "skipped",
                "proof": "regular_weighted_sample_transpose",
                "reason": reason,
                "cuda_required": required,
            },
            sort_keys=True,
        )
    )
    return NO_CUDA_DEVICE_EXIT_CODE if required else 0


def run_proof(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    nvcc = common.detect_nvcc(args.nvcc)
    if nvcc is None:
        return skip_report(
            "nvcc not found; optional CUDA transpose proof not run",
            required=args.require_cuda,
        )
    host_cxx = common.detect_host_cxx(args.host_cxx)
    if host_cxx is None:
        sys.stderr.write(
            "CUDA transpose proof failed: host C++ compiler not found; "
            "set CXX or pass --host-cxx\n"
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="slimed-cuda-transpose-") as temporary:
        binary = Path(temporary) / "cuda_regular_weighted_sample_transpose"
        command = build_command(
            root,
            nvcc,
            binary,
            args.compute_arch,
            args.sm_code,
            host_cxx,
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
            return 1

        execution = subprocess.run(
            [
                str(binary),
                str(args.batch_size),
                args.compute_arch,
                args.sm_code,
            ],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
        if execution.returncode == NO_CUDA_DEVICE_EXIT_CODE:
            reason = execution.stdout.strip() or execution.stderr.strip()
            return skip_report(
                f"compiled, but {reason}", required=args.require_cuda
            )
        if execution.returncode != 0:
            sys.stderr.write(execution.stdout)
            sys.stderr.write(execution.stderr)
            return execution.returncode

        try:
            report = json.loads(execution.stdout)
        except json.JSONDecodeError as error:
            sys.stderr.write(f"CUDA transpose proof returned invalid JSON: {error}\n")
            sys.stderr.write(execution.stdout)
            return 1
        report["environment"] = common.cpu_metadata()
        report["environment"]["openmp_runtime"] = (
            "not used in Step 3 serial CPU reference"
        )
        report["environment"]["cuda_compiler"] = nvcc
        report["environment"]["cuda_compiler_version"] = (
            common.compiler_version(nvcc)
        )
        report["environment"]["cuda_compiler_flags"] = (
            common.cuda_compiler_flags(args.compute_arch, args.sm_code, host_cxx)
        )
        report["environment"]["host_cxx"] = host_cxx
        report["environment"]["host_cxx_version"] = (
            common.compiler_version(host_cxx)
        )
        report["environment"]["host_cxx_flags"] = common.HOST_COMPILER_FLAGS
        report["environment"]["compile_command"] = command
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("status") == "passed" else 2


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        "--root", help="repository root; defaults to script parent"
    )
    argument_parser.add_argument("--nvcc", help="explicit nvcc path")
    argument_parser.add_argument(
        "--host-cxx",
        help="explicit host C++ compiler used by nvcc; defaults to CXX or g++",
    )
    argument_parser.add_argument("--batch-size", type=int, default=257)
    argument_parser.add_argument("--compute-arch", default="compute_89")
    argument_parser.add_argument("--sm-code", default="sm_89")
    argument_parser.add_argument(
        "--require-cuda",
        action="store_true",
        help="treat missing nvcc/device as exit 77 instead of a successful skip",
    )
    return argument_parser


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.batch_size <= 0:
        parser().error("--batch-size must be positive")
    return run_proof(args)


if __name__ == "__main__":
    raise SystemExit(main())
