#!/usr/bin/env python3
"""Check EnergyForce.csv from the accepted-step minimization smoke."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Optional, Sequence


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that an accepted-step smoke run wrote finite EnergyForce.csv "
            "rows, including at least one post-initial minimization record."
        )
    )
    parser.add_argument(
        "energy_force_csv",
        type=Path,
        help="Path to the EnergyForce.csv file produced by continuum_membrane.",
    )
    parser.add_argument(
        "--min-data-rows",
        type=int,
        default=2,
        help="Minimum data rows required after the header. Default: 2.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.min_data_rows < 1:
        raise SystemExit("--min-data-rows must be at least 1")
    if not args.energy_force_csv.is_file():
        raise SystemExit(f"EnergyForce.csv not found: {args.energy_force_csv}")

    with args.energy_force_csv.open(newline="") as infile:
        rows = list(csv.reader(infile))

    if not rows:
        raise SystemExit(f"{args.energy_force_csv} is empty")

    header = [column.strip() for column in rows[0]]
    data_rows = rows[1:]
    if len(data_rows) < args.min_data_rows:
        raise SystemExit(
            f"Expected at least {args.min_data_rows} data rows, found {len(data_rows)}"
        )

    for row_number, row in enumerate(data_rows, start=2):
        if len(row) != len(header):
            raise SystemExit(
                f"Row {row_number} has {len(row)} columns; expected {len(header)}"
            )
        for column_name, raw_value in zip(header, row):
            value = float(raw_value.strip())
            if not math.isfinite(value):
                raise SystemExit(
                    f"Row {row_number} column {column_name!r} is not finite: {raw_value}"
                )

    print(
        f"{args.energy_force_csv}: {len(data_rows)} finite data rows "
        f"({len(data_rows) - 1} post-initial accepted-step record(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
