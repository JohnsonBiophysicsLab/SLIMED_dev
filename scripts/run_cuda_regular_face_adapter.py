#!/usr/bin/env python3
"""Build and run the optional Step 5 regular-face CUDA residency adapter."""

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

import run_cuda_regular_weighted_sample_benchmark as benchmark
import run_cuda_regular_weighted_sample_forward as common


CUDA_SOURCE = Path("experiments/cuda_regular_face_adapter.cu")
NO_CUDA_DEVICE_EXIT_CODE = 77
DEFAULT_BATCH_SIZES = "4096,32768"
DEFAULT_RESIDENT_ITERATIONS = "1,4,16,64"
OPENMP_HOST_FLAG = "-fopenmp"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_positive_csv(text: str, label: str, maximum: int) -> list[int]:
    try:
        values = [int(item) for item in text.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"{label} must be comma-separated integers"
        ) from error
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError(f"{label} must be positive")
    if values != sorted(set(values)):
        raise argparse.ArgumentTypeError(f"{label} must be strictly increasing")
    if values[-1] > maximum:
        raise argparse.ArgumentTypeError(
            f"{label} value {values[-1]} exceeds checked maximum {maximum}"
        )
    return values


def parse_batch_sizes(text: str) -> list[int]:
    return parse_positive_csv(text, "batch sizes", benchmark.MAX_BATCH_SIZE)


def parse_resident_iterations(text: str) -> list[int]:
    return parse_positive_csv(text, "resident iterations", 1_000_000)


def production_sources(root: Path) -> list[str]:
    excluded = {"Run_flat.cpp", "Run_dynamics_flat.cpp"}
    return [
        str(path)
        for path in sorted((root / "src").rglob("*.cpp"))
        if path.name not in excluded
    ]


def include_flags(root: Path) -> list[str]:
    include_root = root / "include"
    directories = [include_root, *sorted(path for path in include_root.iterdir() if path.is_dir())]
    flags: list[str] = []
    for directory in directories:
        flags.extend(["-I", str(directory)])
    return flags


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
        *include_flags(root),
        str(root / CUDA_SOURCE),
        *production_sources(root),
        "-lgomp",
        "-lgsl",
        "-lgslcblas",
        "-Xcompiler=-pthread",
        "-lm",
        "-o",
        str(output),
    ]


def skip_report(reason: str, *, required: bool) -> int:
    print(
        json.dumps(
            {
                "status": "skipped",
                "experiment": "regular_face_cuda_residency_adapter",
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


def add_derived_evidence(report: dict[str, object]) -> None:
    cases = report["cases"]
    break_even: dict[str, int | None] = {}
    batches = sorted({int(item["batch_size"]) for item in cases})
    for batch_size in batches:
        matching = [
            item
            for item in cases
            if int(item["batch_size"]) == batch_size
            and float(item["resident_end_to_end_speedup_vs_openmp"]) > 1.0
        ]
        break_even[str(batch_size)] = (
            min(int(item["resident_iterations"]) for item in matching)
            if matching
            else None
        )
    report["break_even_resident_iterations_vs_openmp_by_batch"] = break_even
    report["recommendation"] = {
        "production_integration": "not_ready_without_end_to_end_device_resident_pipeline",
        "bounded_next_decision": (
            "stop_cuda_poc_after_readiness_report; production work requires a separately "
            "reviewed device-ownership, full-force, and scatter design"
        ),
    }


def run_adapter(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    nvcc = common.detect_nvcc(args.nvcc)
    if nvcc is None:
        return skip_report(
            "nvcc not found; optional CUDA adapter not run",
            required=args.require_cuda,
        )
    host_cxx = common.detect_host_cxx(args.host_cxx)
    if host_cxx is None:
        sys.stderr.write(
            "CUDA adapter failed: host C++ compiler not found; "
            "set CXX or pass --host-cxx\n"
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="slimed-cuda-adapter-") as temporary:
        binary = Path(temporary) / "cuda_regular_face_adapter"
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
                ",".join(str(value) for value in args.batch_sizes),
                ",".join(str(value) for value in args.resident_iterations),
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
            return skip_report(f"compiled, but {reason}", required=args.require_cuda)
        if execution.returncode != 0:
            sys.stderr.write(execution.stdout)
            sys.stderr.write(execution.stderr)
            return execution.returncode

        try:
            report = json.loads(execution.stdout)
        except json.JSONDecodeError as error:
            sys.stderr.write(f"CUDA adapter returned invalid JSON: {error}\n")
            sys.stderr.write(execution.stdout)
            return 1
        add_derived_evidence(report)
        report["provenance"] = {
            "runner": str(Path("scripts") / Path(__file__).name),
            "source": str(CUDA_SOURCE),
            "base_merge": "3a841f25f54472754e081830995cd03ed5ff2a4b",
            "command": [
                "python3",
                str(Path("scripts") / Path(__file__).name),
                "--require-cuda",
                "--batch-sizes",
                ",".join(str(value) for value in args.batch_sizes),
                "--resident-iterations",
                ",".join(str(value) for value in args.resident_iterations),
                "--warmups",
                str(args.warmups),
                "--repetitions",
                str(args.repetitions),
                "--omp-threads",
                str(args.omp_threads),
            ],
        }
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
                "host_cxx_flags": [*common.HOST_COMPILER_FLAGS, OPENMP_HOST_FLAG],
                "openmp_runtime": benchmark.openmp_linkage(binary),
                "openmp_requested_threads": args.omp_threads,
                "openmp_observed_threads": report["openmp_observed_threads"],
                "openmp_schedule": "static",
                "openmp_affinity": "OMP_PLACES=cores",
                "openmp_binding": "OMP_PROC_BIND=TRUE",
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
    argument_parser.add_argument("--root", help="repository root")
    argument_parser.add_argument("--nvcc", help="explicit nvcc path")
    argument_parser.add_argument("--host-cxx", help="explicit host C++ compiler")
    argument_parser.add_argument(
        "--batch-sizes",
        type=parse_batch_sizes,
        default=parse_batch_sizes(DEFAULT_BATCH_SIZES),
    )
    argument_parser.add_argument(
        "--resident-iterations",
        type=parse_resident_iterations,
        default=parse_resident_iterations(DEFAULT_RESIDENT_ITERATIONS),
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
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    if args.warmups < 1:
        argument_parser.error("--warmups must be at least 1")
    if args.repetitions < 30:
        argument_parser.error("--repetitions must be at least 30")
    if args.omp_threads < 1:
        argument_parser.error("--omp-threads must be positive")
    return run_adapter(args)


if __name__ == "__main__":
    raise SystemExit(main())
