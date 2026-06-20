#!/usr/bin/env python3
"""Stage the benchmark-only OpenMP workload in a scratch directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Optional, Sequence


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy the benchmark-only OpenMP params fixture to a scratch "
            "directory as input.params."
        )
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("/tmp/slimed-openmp-benchmark-workload"),
        help="Scratch directory to create/use. Default: /tmp/slimed-openmp-benchmark-workload.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing input.params in the scratch directory.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    source = repo_root() / "data" / "benchmark" / "openmp_pure_mmc.params"
    destination_dir = args.workdir.resolve()
    destination = destination_dir / "input.params"

    if not source.is_file():
        raise SystemExit(f"Benchmark fixture not found: {source}")
    if destination.exists() and not args.force:
        raise SystemExit(
            f"{destination} already exists; pass --force to overwrite it."
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    print(f"Staged benchmark input: {destination}")
    print(f"Run continuum_membrane with working directory: {destination_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
