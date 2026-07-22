#!/usr/bin/env python3
"""Benchmark the guarded regular OpenSubdiv route against direct semantics.

The executable must already be built with ``USE_OPENSUBDIV_REGULAR=1``.  This
harness toggles only ``SLIMED_USE_OPENSUBDIV_REGULAR`` so both modes use the
same binary, compiler, dependency, workload, and thread count.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


L_FACE_PATTERN = re.compile(r"^(\s*lFace\s*=\s*)[^#\s]+(.*)$", re.MULTILINE)


def parse_csv_floats(value: str) -> List[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values or any(item <= 0 for item in values):
        raise argparse.ArgumentTypeError("expected positive comma-separated numbers")
    return values


def parse_csv_ints(value: str) -> List[int]:
    values = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not values or any(item <= 0 for item in values):
        raise argparse.ArgumentTypeError("expected positive comma-separated integers")
    return values


def rewrite_l_face(text: str, l_face: float) -> str:
    if len(L_FACE_PATTERN.findall(text)) != 1:
        raise ValueError("benchmark params must contain exactly one lFace assignment")
    return L_FACE_PATTERN.sub(rf"\g<1>{l_face:g}\g<2>", text, count=1)


def summarize(values: Iterable[float]) -> Dict[str, float]:
    samples = list(values)
    if not samples:
        raise ValueError("cannot summarize an empty sample set")
    return {
        "mean_seconds": statistics.mean(samples),
        "median_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "stdev_seconds": statistics.stdev(samples) if len(samples) > 1 else 0.0,
    }


def run_once(
    executable: Path,
    workdir: Path,
    mode: str,
    threads: int,
    log_path: Path,
) -> float:
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(threads)
    if mode == "routed":
        env["SLIMED_USE_OPENSUBDIV_REGULAR"] = "1"
    else:
        env.pop("SLIMED_USE_OPENSUBDIV_REGULAR", None)

    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            [str(executable)],
            cwd=workdir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"{mode} run failed with exit code {completed.returncode}; see {log_path}"
        )
    return elapsed


def git_value(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument(
        "--params",
        type=Path,
        default=repo / "data/benchmark/openmp_pure_mmc.params",
    )
    parser.add_argument("--l-face", type=parse_csv_floats, default=parse_csv_floats("12.5,7.5,5"))
    parser.add_argument("--threads", type=parse_csv_ints, default=parse_csv_ints("1,4"))
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=Path("/tmp/slimed-opensubdiv-regular-route-benchmark"),
    )
    args = parser.parse_args(argv)
    if args.warmups < 0 or args.repeats < 1:
        parser.error("warmups must be non-negative and repeats must be positive")
    return args


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    executable = args.executable.resolve()
    params = args.params.resolve()
    if not executable.is_file():
        raise SystemExit(f"executable not found: {executable}")
    if not params.is_file():
        raise SystemExit(f"params fixture not found: {params}")

    params_text = params.read_text(encoding="utf-8")
    session_root = args.work_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_runs: List[Dict[str, object]] = []
    summaries: List[Dict[str, object]] = []

    for l_face in args.l_face:
        for threads in args.threads:
            workdir = session_root / f"lface-{l_face:g}" / f"threads-{threads}"
            workdir.mkdir(parents=True, exist_ok=True)
            staged_params = rewrite_l_face(params_text, l_face)
            samples: Dict[str, List[float]] = {"direct": [], "routed": []}
            total_rounds = args.warmups + args.repeats
            for round_index in range(total_rounds):
                modes = ("direct", "routed") if round_index % 2 == 0 else ("routed", "direct")
                for mode in modes:
                    phase = "warmup" if round_index < args.warmups else "measured"
                    run_dir = workdir / f"{phase}-{round_index + 1}-{mode}"
                    run_dir.mkdir(parents=True, exist_ok=True)
                    (run_dir / "input.params").write_text(staged_params, encoding="utf-8")
                    log_path = run_dir / "run.log"
                    elapsed = run_once(executable, run_dir, mode, threads, log_path)
                    raw_runs.append(
                        {
                            "l_face": l_face,
                            "threads": threads,
                            "mode": mode,
                            "phase": phase,
                            "round": round_index + 1,
                            "wall_seconds": elapsed,
                            "log_path": str(log_path),
                        }
                    )
                    if phase == "measured":
                        samples[mode].append(elapsed)

            direct = summarize(samples["direct"])
            routed = summarize(samples["routed"])
            summaries.append(
                {
                    "l_face": l_face,
                    "threads": threads,
                    "direct": direct,
                    "routed": routed,
                    "routed_over_direct": routed["mean_seconds"] / direct["mean_seconds"],
                }
            )

    payload = {
        "kind": "guarded_regular_opensubdiv_route_performance_characterization",
        "not_a_scientific_protocol": True,
        "route_gate": "SLIMED_USE_OPENSUBDIV_REGULAR=1",
        "same_binary_for_direct_and_routed": True,
        "metadata": {
            "date_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_value(repo, "rev-parse", "HEAD"),
            "git_branch": git_value(repo, "rev-parse", "--abbrev-ref", "HEAD"),
            "executable": str(executable),
            "params": str(params),
            "work_root": str(session_root),
            "warmups": args.warmups,
            "repeats": args.repeats,
        },
        "summary": summaries,
        "runs": raw_runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": summaries}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
