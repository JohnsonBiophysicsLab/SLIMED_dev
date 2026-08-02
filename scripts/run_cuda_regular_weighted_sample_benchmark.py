#!/usr/bin/env python3
"""Build and run the optional CUDA/OpenMP weighted-sample benchmark."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_cuda_regular_weighted_sample_forward as common


CUDA_SOURCE = Path("experiments/cuda_regular_weighted_sample_benchmark.cu")
GAUSS_SOURCE = Path("src/mesh/Gauss_quadrature.cpp")
LINALG_SOURCE = Path("src/linear_algebra/Linear_algebra.cpp")
NO_CUDA_DEVICE_EXIT_CODE = 77
DEFAULT_BATCH_SIZES = "1,16,256,4096,32768,131072,524288,1048576"
OPENMP_HOST_FLAG = "-fopenmp"
ROW_COMPONENTS_PER_BATCH = 3 * 7 * 3
CONTROL_COMPONENTS_PER_BATCH = 12 * 3
DEVICE_BYTES_PER_BATCH = 1584
WEIGHT_BYTES = 3 * 7 * 12 * 8
MAX_BATCH_SIZE = min(
    sys.maxsize // (ROW_COMPONENTS_PER_BATCH * 8),
    sys.maxsize // (CONTROL_COMPONENTS_PER_BATCH * 8),
    (sys.maxsize - WEIGHT_BYTES) // DEVICE_BYTES_PER_BATCH,
)


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
        f"-Xcompiler={OPENMP_HOST_FLAG}",
        "-I",
        str(root / "include"),
        str(root / CUDA_SOURCE),
        str(root / GAUSS_SOURCE),
        str(root / LINALG_SOURCE),
        "-lgomp",
        "-lgsl",
        "-lgslcblas",
        "-lm",
        "-o",
        str(output),
    ]


def parse_batch_sizes(text: str) -> list[int]:
    try:
        values = [int(item) for item in text.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "batch sizes must be comma-separated integers"
        ) from error
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("batch sizes must be positive")
    if values != sorted(set(values)):
        raise argparse.ArgumentTypeError("batch sizes must be strictly increasing")
    if values[-1] > MAX_BATCH_SIZE:
        raise argparse.ArgumentTypeError(
            f"batch size {values[-1]} exceeds checked maximum {MAX_BATCH_SIZE}"
        )
    return values


def skip_report(reason: str, *, required: bool) -> int:
    print(
        json.dumps(
            {
                "status": "skipped",
                "benchmark": "regular_weighted_sample_forward_transpose",
                "reason": reason,
                "cuda_required": required,
            },
            sort_keys=True,
        )
    )
    return NO_CUDA_DEVICE_EXIT_CODE if required else 0


def run_environment(threads: int) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "OMP_NUM_THREADS": str(threads),
            "OMP_DYNAMIC": "FALSE",
            "OMP_PROC_BIND": "TRUE",
            "OMP_PLACES": "cores",
            "OMP_SCHEDULE": "static",
        }
    )
    return environment


def openmp_linkage(binary: Path) -> str:
    completed = subprocess.run(
        ["ldd", str(binary)],
        capture_output=True,
        check=False,
        text=True,
    )
    matches = [
        line.strip()
        for line in completed.stdout.splitlines()
        if "libgomp" in line or "libomp" in line
    ]
    return "; ".join(matches) if matches else "unavailable"


def run_benchmark(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    nvcc = common.detect_nvcc(args.nvcc)
    if nvcc is None:
        return skip_report(
            "nvcc not found; optional CUDA benchmark not run",
            required=args.require_cuda,
        )
    host_cxx = common.detect_host_cxx(args.host_cxx)
    if host_cxx is None:
        sys.stderr.write(
            "CUDA benchmark failed: host C++ compiler not found; "
            "set CXX or pass --host-cxx\n"
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="slimed-cuda-benchmark-") as temporary:
        binary = Path(temporary) / "cuda_regular_weighted_sample_benchmark"
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

        linkage = openmp_linkage(binary)
        execution = subprocess.run(
            [
                str(binary),
                ",".join(str(value) for value in args.batch_sizes),
                str(args.warmups),
                str(args.repetitions),
                str(args.omp_threads),
                args.compute_arch,
                args.sm_code,
            ],
            cwd=root,
            env=run_environment(args.omp_threads),
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
            sys.stderr.write(f"CUDA benchmark returned invalid JSON: {error}\n")
            sys.stderr.write(execution.stdout)
            return 1

        metadata = common.cpu_metadata()
        metadata.update(
            {
                "cuda_compiler": nvcc,
                "cuda_compiler_version": common.compiler_version(nvcc),
                "cuda_compiler_flags": [
                    *common.cuda_compiler_flags(
                        args.compute_arch, args.sm_code, host_cxx
                    ),
                    f"-Xcompiler={OPENMP_HOST_FLAG}",
                ],
                "host_cxx": host_cxx,
                "host_cxx_version": common.compiler_version(host_cxx),
                "host_cxx_flags": [
                    *common.HOST_COMPILER_FLAGS,
                    OPENMP_HOST_FLAG,
                ],
                "compile_command": command,
                "openmp_runtime": linkage,
                "openmp_requested_threads": args.omp_threads,
                "openmp_observed_threads": report["openmp_observed_threads"],
                "openmp_schedule": "static",
                "openmp_affinity": "OMP_PLACES=cores",
                "openmp_binding": "OMP_PROC_BIND=TRUE",
                "openmp_dynamic": "OMP_DYNAMIC=FALSE",
                "same_host_power_configuration": (
                    "single sequential sweep; host power mode unavailable in WSL"
                ),
                "thermal_or_clock_throttling_observed": (
                    "unavailable; NVML telemetry is not exposed in this WSL setup"
                ),
            }
        )
        report["environment"] = metadata
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
    argument_parser.add_argument(
        "--batch-sizes",
        type=parse_batch_sizes,
        default=parse_batch_sizes(DEFAULT_BATCH_SIZES),
        help=f"strictly increasing comma-separated sizes; default {DEFAULT_BATCH_SIZES}",
    )
    argument_parser.add_argument("--warmups", type=int, default=5)
    argument_parser.add_argument("--repetitions", type=int, default=30)
    argument_parser.add_argument("--omp-threads", type=int, default=8)
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
    if args.warmups < 1:
        parser().error("--warmups must be at least 1")
    if args.repetitions < 30:
        parser().error("--repetitions must be at least 30")
    if args.omp_threads < 1:
        parser().error("--omp-threads must be positive")
    return run_benchmark(args)


if __name__ == "__main__":
    raise SystemExit(main())
