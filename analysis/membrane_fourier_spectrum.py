#!/usr/bin/env python3
"""Fourier-space membrane modulation diagnostic.

This module intentionally uses only the Python standard library.  The direct
DFT implementation is meant for post-processing small diagnostic fixtures and
thermalized minimization samples, not for large production trajectories.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple


TAU = 2.0 * math.pi


@dataclass(frozen=True)
class SpectrumPoint:
    """Power at one 2D Fourier mode."""

    kx: int
    ky: int
    qx: float
    qy: float
    q: float
    power: float


@dataclass(frozen=True)
class RadialBin:
    """Radial average of the Fourier power spectrum."""

    index: int
    q_min: float
    q_max: float
    q_mean: float
    s_q: float
    count: int


@dataclass(frozen=True)
class TrajectoryStats:
    frames_read: int
    frames_used: int


@dataclass(frozen=True)
class SpectrumResult:
    spectrum: List[SpectrumPoint]
    radial: List[RadialBin]
    stats: TrajectoryStats


def parse_trajectory_row(row: str, line_number: int = 1) -> List[Tuple[float, float, float]]:
    """Parse one flattened trajectory row into ``(x, y, z)`` triples."""

    try:
        fields = next(csv.reader([row], skipinitialspace=True))
    except csv.Error as exc:
        raise ValueError(f"line {line_number}: invalid CSV row: {exc}") from exc

    values: List[float] = []
    for column, field in enumerate(fields, start=1):
        text = field.strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError as exc:
            raise ValueError(
                f"line {line_number}, column {column}: expected a floating-point value"
            ) from exc

    if not values:
        return []
    if len(values) % 3 != 0:
        raise ValueError(
            f"line {line_number}: expected x,y,z triples, found {len(values)} values"
        )

    return [
        (values[index], values[index + 1], values[index + 2])
        for index in range(0, len(values), 3)
    ]


def iter_trajectory_rows(path: Path) -> Iterator[Tuple[int, List[Tuple[float, float, float]]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(handle, start=1):
            points = parse_trajectory_row(row, line_number)
            if points:
                yield line_number, points


def _validate_grid(grid_shape: Tuple[int, int], spacing: Tuple[float, float]) -> None:
    nx, ny = grid_shape
    dx, dy = spacing
    if nx <= 0 or ny <= 0:
        raise ValueError("grid dimensions must be positive")
    if dx <= 0.0 or dy <= 0.0:
        raise ValueError("grid spacing must be positive")


def _extract_heights(
    points: Sequence[Tuple[float, float, float]], grid_shape: Tuple[int, int]
) -> List[float]:
    nx, ny = grid_shape
    expected = nx * ny
    if len(points) != expected:
        raise ValueError(
            f"grid shape {nx}x{ny} expects {expected} points, found {len(points)}"
        )
    return [point[2] for point in points]


def _grid_coordinates(
    grid_shape: Tuple[int, int], spacing: Tuple[float, float]
) -> List[Tuple[float, float]]:
    nx, ny = grid_shape
    dx, dy = spacing
    return [(ix * dx, iy * dy) for iy in range(ny) for ix in range(nx)]


def _solve_3x3(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> Tuple[float, float, float]:
    augmented = [list(row) + [rhs[index]] for index, row in enumerate(matrix)]

    for column in range(3):
        pivot_row = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot_row][column]) < 1.0e-12:
            raise ValueError("cannot fit a tilt plane for this grid")
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]

        pivot = augmented[column][column]
        for entry in range(column, 4):
            augmented[column][entry] /= pivot

        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            for entry in range(column, 4):
                augmented[row][entry] -= factor * augmented[column][entry]

    return augmented[0][3], augmented[1][3], augmented[2][3]


def fit_plane(
    heights: Sequence[float], coordinates: Sequence[Tuple[float, float]]
) -> Tuple[float, float, float]:
    """Fit ``z = a*x + b*y + c`` by least squares."""

    if len(heights) != len(coordinates):
        raise ValueError("height and coordinate counts differ")

    n = float(len(heights))
    sx = sum(point[0] for point in coordinates)
    sy = sum(point[1] for point in coordinates)
    sxx = sum(point[0] * point[0] for point in coordinates)
    sxy = sum(point[0] * point[1] for point in coordinates)
    syy = sum(point[1] * point[1] for point in coordinates)
    sz = sum(heights)
    sxz = sum(point[0] * height for point, height in zip(coordinates, heights))
    syz = sum(point[1] * height for point, height in zip(coordinates, heights))

    return _solve_3x3(
        ((sxx, sxy, sx), (sxy, syy, sy), (sx, sy, n)),
        (sxz, syz, sz),
    )


def detrend_heights(
    heights: Sequence[float],
    coordinates: Sequence[Tuple[float, float]],
    plane: str = "mean",
) -> List[float]:
    """Remove the requested height offset or tilt from one frame."""

    if plane == "none":
        return list(heights)
    if plane == "mean":
        mean_height = sum(heights) / float(len(heights))
        return [height - mean_height for height in heights]
    if plane == "tilt":
        slope_x, slope_y, intercept = fit_plane(heights, coordinates)
        return [
            height - (slope_x * x_coord + slope_y * y_coord + intercept)
            for height, (x_coord, y_coord) in zip(heights, coordinates)
        ]
    raise ValueError(f"unknown plane removal mode: {plane}")


def _signed_mode(index: int, size: int) -> int:
    return index if index < (size + 1) // 2 else index - size


def compute_power_spectrum(
    heights: Sequence[float],
    grid_shape: Tuple[int, int],
    spacing: Tuple[float, float],
    plane: str = "mean",
    coordinates: Sequence[Tuple[float, float]] | None = None,
) -> List[SpectrumPoint]:
    """Compute a direct 2D DFT power spectrum for one height frame."""

    _validate_grid(grid_shape, spacing)
    nx, ny = grid_shape
    dx, dy = spacing
    expected = nx * ny
    if len(heights) != expected:
        raise ValueError(f"grid shape {nx}x{ny} expects {expected} heights")

    if coordinates is None:
        coordinates = _grid_coordinates(grid_shape, spacing)
    adjusted = detrend_heights(heights, coordinates, plane)
    normalization = float(expected * expected)

    spectrum: List[SpectrumPoint] = []
    for ky_index in range(ny):
        ky_mode = _signed_mode(ky_index, ny)
        qy = TAU * ky_mode / (ny * dy)
        for kx_index in range(nx):
            kx_mode = _signed_mode(kx_index, nx)
            qx = TAU * kx_mode / (nx * dx)
            real = 0.0
            imag = 0.0
            for iy in range(ny):
                for ix in range(nx):
                    height = adjusted[iy * nx + ix]
                    angle = -TAU * (
                        (kx_index * ix / float(nx)) + (ky_index * iy / float(ny))
                    )
                    real += height * math.cos(angle)
                    imag += height * math.sin(angle)
            power = (real * real + imag * imag) / normalization
            spectrum.append(
                SpectrumPoint(
                    kx=kx_mode,
                    ky=ky_mode,
                    qx=qx,
                    qy=qy,
                    q=math.hypot(qx, qy),
                    power=power,
                )
            )
    return spectrum


def average_power_spectrum(
    frames: Sequence[Sequence[Tuple[float, float, float]]],
    grid_shape: Tuple[int, int],
    spacing: Tuple[float, float],
    plane: str = "mean",
) -> List[SpectrumPoint]:
    if not frames:
        raise ValueError("no frames selected")

    accumulated: List[float] | None = None
    template: List[SpectrumPoint] | None = None
    for frame in frames:
        heights = _extract_heights(frame, grid_shape)
        coordinates = [(point[0], point[1]) for point in frame]
        spectrum = compute_power_spectrum(
            heights,
            grid_shape,
            spacing,
            plane=plane,
            coordinates=coordinates,
        )
        if accumulated is None:
            accumulated = [0.0] * len(spectrum)
            template = spectrum
        for index, point in enumerate(spectrum):
            accumulated[index] += point.power

    assert accumulated is not None
    assert template is not None
    frame_count = float(len(frames))
    return [
        SpectrumPoint(
            kx=point.kx,
            ky=point.ky,
            qx=point.qx,
            qy=point.qy,
            q=point.q,
            power=accumulated[index] / frame_count,
        )
        for index, point in enumerate(template)
    ]


def radial_average(spectrum: Sequence[SpectrumPoint], radial_bins: int) -> List[RadialBin]:
    if radial_bins <= 0:
        raise ValueError("radial bin count must be positive")
    if not spectrum:
        return []

    q_max = max(point.q for point in spectrum)
    width = q_max / float(radial_bins) if q_max > 0.0 else 1.0
    power_sums = [0.0] * radial_bins
    q_sums = [0.0] * radial_bins
    counts = [0] * radial_bins

    for point in spectrum:
        index = 0 if q_max == 0.0 else min(int(point.q / width), radial_bins - 1)
        power_sums[index] += point.power
        q_sums[index] += point.q
        counts[index] += 1

    bins: List[RadialBin] = []
    for index in range(radial_bins):
        q_min = index * width
        q_upper = q_max if index == radial_bins - 1 else (index + 1) * width
        count = counts[index]
        q_mean = q_sums[index] / count if count else 0.5 * (q_min + q_upper)
        s_q = power_sums[index] / count if count else 0.0
        bins.append(
            RadialBin(
                index=index,
                q_min=q_min,
                q_max=q_upper,
                q_mean=q_mean,
                s_q=s_q,
                count=count,
            )
        )
    return bins


def load_selected_frames(
    trajectory: Path,
    grid_shape: Tuple[int, int],
    start_frame: int,
    stride: int,
) -> Tuple[List[List[Tuple[float, float, float]]], TrajectoryStats]:
    if start_frame < 0:
        raise ValueError("start frame must be nonnegative")
    if stride <= 0:
        raise ValueError("stride must be positive")

    frames: List[List[Tuple[float, float, float]]] = []
    frames_read = 0
    for frame_index, (_line_number, points) in enumerate(iter_trajectory_rows(trajectory)):
        frames_read += 1
        if frame_index < start_frame:
            continue
        if (frame_index - start_frame) % stride != 0:
            continue
        _extract_heights(points, grid_shape)
        frames.append(points)

    if not frames:
        raise ValueError("no frames selected from trajectory")
    return frames, TrajectoryStats(frames_read=frames_read, frames_used=len(frames))


def analyze_trajectory(
    trajectory: Path,
    grid_shape: Tuple[int, int],
    spacing: Tuple[float, float],
    start_frame: int = 0,
    stride: int = 1,
    plane: str = "mean",
    radial_bins: int = 20,
) -> SpectrumResult:
    _validate_grid(grid_shape, spacing)
    frames, stats = load_selected_frames(trajectory, grid_shape, start_frame, stride)
    spectrum = average_power_spectrum(frames, grid_shape, spacing, plane=plane)
    radial = radial_average(spectrum, radial_bins)
    return SpectrumResult(spectrum=spectrum, radial=radial, stats=stats)


def write_raw_spectrum(path: Path, spectrum: Sequence[SpectrumPoint]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("kx", "ky", "qx", "qy", "q", "power"))
        for point in spectrum:
            writer.writerow(
                (
                    point.kx,
                    point.ky,
                    _format_float(point.qx),
                    _format_float(point.qy),
                    _format_float(point.q),
                    _format_float(point.power),
                )
            )


def write_radial_spectrum(path: Path, bins: Sequence[RadialBin]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("bin", "q_min", "q_max", "q_mean", "S_q", "count"))
        for bin_entry in bins:
            writer.writerow(
                (
                    bin_entry.index,
                    _format_float(bin_entry.q_min),
                    _format_float(bin_entry.q_max),
                    _format_float(bin_entry.q_mean),
                    _format_float(bin_entry.s_q),
                    bin_entry.count,
                )
            )


def write_summary(
    path: Path,
    args: argparse.Namespace,
    result: SpectrumResult,
) -> None:
    zero_mode = next(
        (point for point in result.spectrum if point.kx == 0 and point.ky == 0),
        None,
    )
    nonzero = [point for point in result.spectrum if point.kx != 0 or point.ky != 0]
    peak = max(nonzero or result.spectrum, key=lambda point: point.power)
    total_power = sum(point.power for point in result.spectrum)

    lines = [
        "Fourier membrane modulation diagnostic",
        f"trajectory: {args.trajectory}",
        f"grid_shape: {args.grid_shape[0]} {args.grid_shape[1]}",
        f"spacing: {args.spacing[0]} {args.spacing[1]}",
        f"start_frame: {args.start_frame}",
        f"stride: {args.stride}",
        f"plane: {args.plane}",
        f"radial_bins: {args.radial_bins}",
        f"frames_read: {result.stats.frames_read}",
        f"frames_used: {result.stats.frames_used}",
        f"total_power: {_format_float(total_power)}",
        f"zero_mode_power: {_format_float(zero_mode.power if zero_mode else 0.0)}",
        f"peak_kx: {peak.kx}",
        f"peak_ky: {peak.ky}",
        f"peak_qx: {_format_float(peak.qx)}",
        f"peak_qy: {_format_float(peak.qy)}",
        f"peak_q: {_format_float(peak.q)}",
        f"peak_power: {_format_float(peak.power)}",
        "raw_spectrum: spectrum_raw.csv",
        "radial_spectrum: spectrum_radial.csv",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_float(value: float) -> str:
    return f"{value:.17g}"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute a small-fixture Fourier spectrum from membrane trajectory CSV rows."
    )
    parser.add_argument("--trajectory", required=True, type=Path, help="Flattened CSV trajectory")
    parser.add_argument("--outdir", required=True, type=Path, help="Directory for diagnostic outputs")
    parser.add_argument("--start-frame", type=int, default=0, help="First zero-based frame to use")
    parser.add_argument("--stride", type=int, default=1, help="Frame stride after start-frame")
    parser.add_argument(
        "--grid-shape",
        nargs=2,
        type=int,
        metavar=("NX", "NY"),
        required=True,
        help="Regular grid shape for each flattened frame",
    )
    parser.add_argument(
        "--spacing",
        nargs=2,
        type=float,
        metavar=("DX", "DY"),
        required=True,
        help="Grid spacing used to compute qx and qy",
    )
    parser.add_argument(
        "--plane",
        choices=("mean", "tilt", "none"),
        default="mean",
        help="Height detrending mode before the DFT",
    )
    parser.add_argument(
        "--radial-bins",
        type=int,
        default=20,
        help="Number of bins for radial S(q) averages",
    )
    return parser


def run(args: argparse.Namespace) -> SpectrumResult:
    result = analyze_trajectory(
        trajectory=args.trajectory,
        grid_shape=(args.grid_shape[0], args.grid_shape[1]),
        spacing=(args.spacing[0], args.spacing[1]),
        start_frame=args.start_frame,
        stride=args.stride,
        plane=args.plane,
        radial_bins=args.radial_bins,
    )

    args.outdir.mkdir(parents=True, exist_ok=True)
    write_raw_spectrum(args.outdir / "spectrum_raw.csv", result.spectrum)
    write_radial_spectrum(args.outdir / "spectrum_radial.csv", result.radial)
    write_summary(args.outdir / "spectrum_summary.txt", args, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        run(args)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
