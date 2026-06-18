#!/usr/bin/env python3
"""Benchmark serial-vs-OpenMP wall-time scaling for SLIMED commands.

The harness intentionally measures external commands instead of importing
SLIMED code. That keeps it dependency-free and usable before OpenMP tuning
changes begin.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass
class CommandResult:
    phase: str
    command: str
    threads: int
    repeat: int
    omp_num_threads: str
    wall_seconds: float
    exit_code: int
    log_path: str = ""
    speedup: Optional[float] = None
    parallel_efficiency: Optional[float] = None


def parse_threads(value: str) -> List[int]:
    threads: List[int] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        try:
            thread_count = int(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"invalid thread count {part!r}; expected comma-separated integers"
            ) from exc
        if thread_count < 1:
            raise argparse.ArgumentTypeError("thread counts must be positive")
        if thread_count not in threads:
            threads.append(thread_count)
    if not threads:
        raise argparse.ArgumentTypeError("at least one thread count is required")
    return threads


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return parsed


def split_command(command: str) -> List[str]:
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise SystemExit(f"Could not parse command {command!r}: {exc}") from exc
    if not parts:
        raise SystemExit("Command cannot be empty")
    return parts


def run_text_command(args: Sequence[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return completed.stdout.strip()
    return completed.stdout.strip()


def detect_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_git_metadata(cwd: Path) -> Dict[str, str]:
    return {
        "commit": run_text_command(["git", "rev-parse", "HEAD"], cwd),
        "branch": run_text_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd),
        "dirty_status": run_text_command(["git", "status", "--short"], cwd),
    }


def detect_compilers(cwd: Path) -> Dict[str, object]:
    candidates = []
    for executable in ("g++-15", "g++", "clang++", "c++"):
        path = shutil.which(executable)
        if path is None:
            continue
        first_line = run_text_command([path, "--version"], cwd).splitlines()
        candidates.append(
            {
                "name": executable,
                "path": path,
                "version": first_line[0] if first_line else "",
            }
        )
    return {
        "CC": os.environ.get("CC", ""),
        "CXX": os.environ.get("CXX", ""),
        "candidates": candidates,
    }


def format_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.9f}"


def open_log(log_dir: Optional[Path], phase: str, threads: int, repeat: int):
    if log_dir is None:
        return None, ""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{phase}_threads-{threads}_repeat-{repeat}.log"
    return path.open("w", encoding="utf-8"), str(path)


def run_command(
    *,
    command: str,
    cwd: Path,
    env: Dict[str, str],
    phase: str,
    threads: int,
    repeat: int,
    log_dir: Optional[Path],
) -> CommandResult:
    command_args = split_command(command)
    log_handle, log_path = open_log(log_dir, phase, threads, repeat)
    stdout_target = log_handle if log_handle is not None else subprocess.DEVNULL

    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command_args,
            cwd=str(cwd),
            env=env,
            stdout=stdout_target,
            stderr=subprocess.STDOUT,
            check=False,
        )
        exit_code = completed.returncode
    except OSError as exc:
        if log_handle is not None:
            log_handle.write(f"Failed to start command: {exc}\n")
        exit_code = 127
    finally:
        wall_seconds = time.perf_counter() - start
        if log_handle is not None:
            log_handle.close()

    return CommandResult(
        phase=phase,
        command=command,
        threads=threads,
        repeat=repeat,
        omp_num_threads=env.get("OMP_NUM_THREADS", ""),
        wall_seconds=wall_seconds,
        exit_code=exit_code,
        log_path=log_path,
    )


def run_build_command(
    *,
    command: Optional[str],
    cwd: Path,
    env: Dict[str, str],
    phase: str,
    log_dir: Optional[Path],
) -> None:
    if not command:
        return
    result = run_command(
        command=command,
        cwd=cwd,
        env=env,
        phase=phase,
        threads=int(env.get("OMP_NUM_THREADS", "1")),
        repeat=0,
        log_dir=log_dir,
    )
    if result.exit_code != 0:
        log_hint = f" See {result.log_path}." if result.log_path else ""
        raise SystemExit(
            f"{phase} command failed with exit code {result.exit_code}: {command}.{log_hint}"
        )


def successful_wall_times(results: Iterable[CommandResult]) -> List[float]:
    return [result.wall_seconds for result in results if result.exit_code == 0]


def summarize_group(
    *,
    phase: str,
    threads: int,
    results: List[CommandResult],
    baseline_mean: Optional[float],
) -> Dict[str, object]:
    walls = successful_wall_times(results)
    summary: Dict[str, object] = {
        "phase": phase,
        "threads": threads,
        "repeats": len(results),
        "successful_repeats": len(walls),
        "failed_repeats": len(results) - len(walls),
        "mean_wall_seconds": None,
        "min_wall_seconds": None,
        "max_wall_seconds": None,
        "stdev_wall_seconds": None,
        "speedup": None,
        "parallel_efficiency": None,
    }
    if not walls:
        return summary
    mean_wall = mean(walls)
    summary.update(
        {
            "mean_wall_seconds": mean_wall,
            "min_wall_seconds": min(walls),
            "max_wall_seconds": max(walls),
            "stdev_wall_seconds": stdev(walls) if len(walls) > 1 else 0.0,
        }
    )
    if baseline_mean is not None and mean_wall > 0:
        speedup = baseline_mean / mean_wall
        summary["speedup"] = speedup
        summary["parallel_efficiency"] = speedup / threads
    return summary


def write_csv(path: Path, metadata: Dict[str, object], rows: List[CommandResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compiler = metadata["compiler"]
    compiler_label = ""
    if isinstance(compiler, dict):
        candidates = compiler.get("candidates", [])
        if isinstance(candidates, list) and candidates:
            first = candidates[0]
            if isinstance(first, dict):
                compiler_label = str(first.get("version", ""))

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "date_utc",
                "git_commit",
                "git_branch",
                "compiler",
                "phase",
                "threads",
                "repeat",
                "omp_num_threads",
                "wall_seconds",
                "exit_code",
                "speedup",
                "parallel_efficiency",
                "command",
                "cwd",
                "log_path",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "date_utc": metadata["date_utc"],
                    "git_commit": metadata["git"]["commit"],
                    "git_branch": metadata["git"]["branch"],
                    "compiler": compiler_label,
                    "phase": row.phase,
                    "threads": row.threads,
                    "repeat": row.repeat,
                    "omp_num_threads": row.omp_num_threads,
                    "wall_seconds": format_float(row.wall_seconds),
                    "exit_code": row.exit_code,
                    "speedup": format_float(row.speedup),
                    "parallel_efficiency": format_float(row.parallel_efficiency),
                    "command": row.command,
                    "cwd": metadata["working_directory"],
                    "log_path": row.log_path,
                }
            )


def write_json(
    path: Path,
    metadata: Dict[str, object],
    configuration: Dict[str, object],
    summaries: List[Dict[str, object]],
    rows: List[CommandResult],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata,
        "configuration": configuration,
        "summary": summaries,
        "runs": [
            {
                "phase": row.phase,
                "threads": row.threads,
                "repeat": row.repeat,
                "omp_num_threads": row.omp_num_threads,
                "wall_seconds": row.wall_seconds,
                "exit_code": row.exit_code,
                "speedup": row.speedup,
                "parallel_efficiency": row.parallel_efficiency,
                "command": row.command,
                "log_path": row.log_path,
            }
            for row in rows
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def print_dry_run(args: argparse.Namespace, cwd: Path) -> None:
    print("Benchmark dry run; no commands will be executed and no output files will be written.")
    print(f"Working directory: {cwd}")
    print(f"CSV path: {args.csv}")
    if args.json:
        print(f"JSON path: {args.json}")
    if args.baseline_build_command:
        print(f"Baseline build: {args.baseline_build_command}")
    if args.baseline_run_command:
        print(f"Baseline run: OMP_NUM_THREADS={args.baseline_threads} {args.baseline_run_command}")
    if args.build_command:
        print(f"OpenMP build: {args.build_command}")
    for thread_count in args.threads:
        for repeat_index in range(1, args.repeats + 1):
            print(
                "OpenMP run: "
                f"threads={thread_count} repeat={repeat_index} "
                f"OMP_NUM_THREADS={thread_count} {args.run_command}"
            )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure wall-time scaling for a selected SLIMED command under "
            "different OMP_NUM_THREADS values."
        )
    )
    parser.add_argument(
        "--build-command",
        help="Optional build command to run before threaded measurements, for example 'make omp'.",
    )
    parser.add_argument(
        "--run-command",
        required=True,
        help="Command to benchmark, for example './bin/continuum_membrane'.",
    )
    parser.add_argument(
        "--baseline-build-command",
        help="Optional build command for the serial baseline, for example 'make serial'.",
    )
    parser.add_argument(
        "--baseline-run-command",
        help="Optional serial baseline command used to calculate speedup and efficiency.",
    )
    parser.add_argument(
        "--baseline-threads",
        type=positive_int,
        default=1,
        help="OMP_NUM_THREADS value used for the serial baseline command. Default: 1.",
    )
    parser.add_argument(
        "--threads",
        type=parse_threads,
        default=parse_threads("1,2,4,8"),
        help="Comma-separated OpenMP thread counts. Default: 1,2,4,8.",
    )
    parser.add_argument(
        "--repeats",
        type=positive_int,
        default=3,
        help="Number of repeats for each measured command. Default: 3.",
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Path for per-run CSV output. Prefer a path under /tmp for local runs.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Optional path for JSON metadata and aggregate summary output.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Optional directory for combined stdout/stderr logs from build and run commands.",
    )
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=detect_repo_root(),
        help="Working directory for build and run commands. Default: repository root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned build/run sequence without executing commands or writing outputs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    cwd = args.working_dir.resolve()
    if not cwd.is_dir():
        raise SystemExit(f"Working directory does not exist: {cwd}")

    if args.dry_run:
        print_dry_run(args, cwd)
        return 0

    metadata: Dict[str, object] = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "working_directory": str(cwd),
        "git": detect_git_metadata(cwd),
        "compiler": detect_compilers(cwd),
        "initial_OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", ""),
    }
    configuration: Dict[str, object] = {
        "build_command": args.build_command,
        "run_command": args.run_command,
        "baseline_build_command": args.baseline_build_command,
        "baseline_run_command": args.baseline_run_command,
        "baseline_threads": args.baseline_threads,
        "threads": args.threads,
        "repeats": args.repeats,
        "csv": str(args.csv),
        "json": str(args.json) if args.json else "",
        "log_dir": str(args.log_dir) if args.log_dir else "",
    }

    all_results: List[CommandResult] = []
    baseline_results: List[CommandResult] = []

    base_env = os.environ.copy()
    if args.baseline_run_command:
        baseline_env = base_env.copy()
        baseline_env["OMP_NUM_THREADS"] = str(args.baseline_threads)
        run_build_command(
            command=args.baseline_build_command,
            cwd=cwd,
            env=baseline_env,
            phase="serial_baseline_build",
            log_dir=args.log_dir,
        )
        for repeat_index in range(1, args.repeats + 1):
            result = run_command(
                command=args.baseline_run_command,
                cwd=cwd,
                env=baseline_env,
                phase="serial_baseline",
                threads=args.baseline_threads,
                repeat=repeat_index,
                log_dir=args.log_dir,
            )
            baseline_results.append(result)
            all_results.append(result)

    build_env = base_env.copy()
    build_env["OMP_NUM_THREADS"] = str(args.threads[0])
    run_build_command(
        command=args.build_command,
        cwd=cwd,
        env=build_env,
        phase="openmp_build",
        log_dir=args.log_dir,
    )

    threaded_results_by_count: Dict[int, List[CommandResult]] = {}
    for thread_count in args.threads:
        threaded_results_by_count[thread_count] = []
        run_env = base_env.copy()
        run_env["OMP_NUM_THREADS"] = str(thread_count)
        for repeat_index in range(1, args.repeats + 1):
            result = run_command(
                command=args.run_command,
                cwd=cwd,
                env=run_env,
                phase="openmp",
                threads=thread_count,
                repeat=repeat_index,
                log_dir=args.log_dir,
            )
            threaded_results_by_count[thread_count].append(result)
            all_results.append(result)

    baseline_walls = successful_wall_times(baseline_results)
    baseline_mean = mean(baseline_walls) if baseline_walls else None
    for result in all_results:
        if baseline_mean is None or result.exit_code != 0 or result.wall_seconds <= 0:
            continue
        result.speedup = baseline_mean / result.wall_seconds
        result.parallel_efficiency = result.speedup / result.threads

    summaries: List[Dict[str, object]] = []
    if baseline_results:
        summaries.append(
            summarize_group(
                phase="serial_baseline",
                threads=args.baseline_threads,
                results=baseline_results,
                baseline_mean=baseline_mean,
            )
        )
    for thread_count, results in threaded_results_by_count.items():
        summaries.append(
            summarize_group(
                phase="openmp",
                threads=thread_count,
                results=results,
                baseline_mean=baseline_mean,
            )
        )

    write_csv(args.csv, metadata, all_results)
    if args.json:
        write_json(args.json, metadata, configuration, summaries, all_results)

    failed_results = [result for result in all_results if result.exit_code != 0]
    print(f"Wrote CSV results to {args.csv}")
    if args.json:
        print(f"Wrote JSON summary to {args.json}")
    if failed_results:
        print(f"{len(failed_results)} measured command(s) failed; see CSV/logs for details.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
