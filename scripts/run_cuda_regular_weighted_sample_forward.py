#!/usr/bin/env python3
"""Build and run the optional CUDA regular weighted-sample forward proof."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence


CUDA_SOURCE = Path("experiments/cuda_regular_weighted_sample_forward.cu")
GAUSS_SOURCE = Path("src/mesh/Gauss_quadrature.cpp")
LINALG_SOURCE = Path("src/linear_algebra/Linear_algebra.cpp")
NO_CUDA_DEVICE_EXIT_CODE = 77
HOST_COMPILER_FLAGS = ["-std=c++17", "-O3"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_nvcc(explicit: str | None) -> str | None:
    if explicit:
        path = Path(explicit)
        return str(path) if path.is_file() else None
    return shutil.which("nvcc")


def detect_host_cxx(explicit: str | None) -> str | None:
    candidate = explicit or os.environ.get("CXX") or "g++"
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


def cuda_compiler_flags(
    compute_arch: str, sm_code: str, host_cxx: str
) -> list[str]:
    return [
        *HOST_COMPILER_FLAGS,
        f"-arch={compute_arch}",
        f"-code={sm_code}",
        f"-ccbin={host_cxx}",
    ]


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
        *cuda_compiler_flags(compute_arch, sm_code, host_cxx),
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


def cpu_metadata() -> dict[str, object]:
    cpu_model = "unavailable"
    physical_cores: int | str = "unavailable"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        records = cpuinfo.read_text(encoding="utf-8", errors="replace").split("\n\n")
        topology: set[tuple[str, str]] = set()
        for record in records:
            fields = dict(
                line.split(":", 1)
                for line in record.splitlines()
                if ":" in line
            )
            normalized = {key.strip(): value.strip() for key, value in fields.items()}
            if cpu_model == "unavailable" and normalized.get("model name"):
                cpu_model = normalized["model name"]
            if "physical id" in normalized and "core id" in normalized:
                topology.add((normalized["physical id"], normalized["core id"]))
        if topology:
            physical_cores = len(topology)

    return {
        "host_cpu_model": cpu_model,
        "physical_cores": physical_cores,
        "logical_cpus": os.cpu_count() or "unavailable",
        "platform": platform.platform(),
        "wsl_kernel": platform.release(),
        "host_power_mode": "unavailable in WSL correctness runner",
        "ac_battery_state": "unavailable in WSL correctness runner",
        "gpu_power_state": "unavailable; NVML is not required",
        "openmp_runtime": "not used in Step 2 serial CPU reference",
        "openmp_requested_threads": 1,
        "openmp_observed_threads": 1,
        "openmp_affinity": "not used",
        "openmp_binding": "not used",
    }


def skip_report(reason: str, *, required: bool) -> int:
    print(
        json.dumps(
            {
                "status": "skipped",
                "proof": "regular_weighted_sample_forward",
                "reason": reason,
                "cuda_required": required,
            },
            sort_keys=True,
        )
    )
    return NO_CUDA_DEVICE_EXIT_CODE if required else 0


def run_proof(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else repo_root()
    nvcc = detect_nvcc(args.nvcc)
    if nvcc is None:
        return skip_report("nvcc not found; optional CUDA proof not run", required=args.require_cuda)
    host_cxx = detect_host_cxx(args.host_cxx)
    if host_cxx is None:
        sys.stderr.write(
            "CUDA forward proof failed: host C++ compiler not found; "
            "set CXX or pass --host-cxx\n"
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="slimed-cuda-forward-") as temporary:
        binary = Path(temporary) / "cuda_regular_weighted_sample_forward"
        command = build_command(
            root, nvcc, binary, args.compute_arch, args.sm_code, host_cxx
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
            sys.stderr.write(f"CUDA proof returned invalid JSON: {error}\n")
            sys.stderr.write(execution.stdout)
            return 1
        report["environment"] = cpu_metadata()
        report["environment"]["cuda_compiler"] = nvcc
        report["environment"]["cuda_compiler_version"] = compiler_version(nvcc)
        report["environment"]["cuda_compiler_flags"] = cuda_compiler_flags(
            args.compute_arch, args.sm_code, host_cxx
        )
        report["environment"]["host_cxx"] = host_cxx
        report["environment"]["host_cxx_version"] = compiler_version(host_cxx)
        report["environment"]["host_cxx_flags"] = HOST_COMPILER_FLAGS
        report["environment"]["compile_command"] = command
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("status") == "passed" else 2


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--root", help="repository root; defaults to script parent")
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
