#!/usr/bin/env python3
"""Stage the accepted-step minimization smoke workload in a scratch directory."""

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
            "Copy the accepted-step minimization params fixture and scaffold "
            "CSV to a scratch directory as input.params and COM.csv."
        )
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("/tmp/slimed-accepted-step-smoke"),
        help="Scratch directory to create/use. Default: /tmp/slimed-accepted-step-smoke.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing input.params or COM.csv files in the scratch directory.",
    )
    return parser.parse_args(argv)


def copy_fixture(source: Path, destination: Path, force: bool) -> None:
    if not source.is_file():
        raise SystemExit(f"Fixture source not found: {source}")
    if destination.exists() and not force:
        raise SystemExit(
            f"{destination} already exists; pass --force to overwrite it."
        )
    shutil.copyfile(source, destination)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = repo_root()
    destination_dir = args.workdir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)

    copy_fixture(
        root / "data" / "benchmark" / "accepted_step_minimization.params",
        destination_dir / "input.params",
        args.force,
    )
    copy_fixture(
        root / "data" / "COM.csv",
        destination_dir / "COM.csv",
        args.force,
    )

    print(f"Staged accepted-step smoke input: {destination_dir / 'input.params'}")
    print(f"Staged accepted-step smoke scaffold: {destination_dir / 'COM.csv'}")
    print(f"Run continuum_membrane with working directory: {destination_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
