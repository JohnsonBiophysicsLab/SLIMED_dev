import math
import tempfile
import unittest
from pathlib import Path

from analysis import membrane_fourier_spectrum as spectrum


def make_points(nx, ny, height_fn):
    points = []
    for iy in range(ny):
        for ix in range(nx):
            points.append((float(ix), float(iy), float(height_fn(ix, iy))))
    return points


class MembraneFourierSpectrumTests(unittest.TestCase):
    def test_parser_handles_trailing_commas(self):
        points = spectrum.parse_trajectory_row(" 0, 0, 1, 1, 0, 2, \n")

        self.assertEqual([(0.0, 0.0, 1.0), (1.0, 0.0, 2.0)], points)

    def test_mean_removal_zeroes_zero_mode(self):
        points = make_points(2, 2, lambda _ix, _iy: 5.0)
        heights = [point[2] for point in points]
        coordinates = [(point[0], point[1]) for point in points]

        result = spectrum.compute_power_spectrum(
            heights,
            grid_shape=(2, 2),
            spacing=(1.0, 1.0),
            plane="mean",
            coordinates=coordinates,
        )
        zero_mode = next(point for point in result if point.kx == 0 and point.ky == 0)

        self.assertAlmostEqual(0.0, zero_mode.power)
        self.assertTrue(all(point.power < 1.0e-24 for point in result))

    def test_tilt_plane_removal_zeroes_linear_field(self):
        points = make_points(3, 3, lambda ix, iy: 2.0 * ix - 0.5 * iy + 7.0)
        heights = [point[2] for point in points]
        coordinates = [(point[0], point[1]) for point in points]

        result = spectrum.compute_power_spectrum(
            heights,
            grid_shape=(3, 3),
            spacing=(1.0, 1.0),
            plane="tilt",
            coordinates=coordinates,
        )

        self.assertTrue(all(point.power < 1.0e-24 for point in result))

    def test_sinusoidal_height_field_peaks_at_expected_mode(self):
        nx = 8
        ny = 8
        expected_mode = 2
        points = make_points(
            nx,
            ny,
            lambda ix, _iy: math.sin(2.0 * math.pi * expected_mode * ix / nx),
        )
        heights = [point[2] for point in points]
        coordinates = [(point[0], point[1]) for point in points]

        result = spectrum.compute_power_spectrum(
            heights,
            grid_shape=(nx, ny),
            spacing=(1.0, 1.0),
            plane="mean",
            coordinates=coordinates,
        )
        nonzero = [point for point in result if point.kx != 0 or point.ky != 0]
        peak = max(nonzero, key=lambda point: point.power)

        self.assertEqual(expected_mode, abs(peak.kx))
        self.assertEqual(0, peak.ky)
        self.assertAlmostEqual(
            2.0 * math.pi * expected_mode / nx,
            abs(peak.qx),
        )
        self.assertAlmostEqual(0.0, peak.qy)

    def test_radial_binning_produces_finite_nonnegative_values(self):
        points = make_points(4, 4, lambda ix, iy: ix - iy)
        result = spectrum.average_power_spectrum(
            [points],
            grid_shape=(4, 4),
            spacing=(1.0, 1.0),
            plane="mean",
        )

        radial = spectrum.radial_average(result, radial_bins=4)

        self.assertEqual(4, len(radial))
        self.assertEqual(len(result), sum(bin_entry.count for bin_entry in radial))
        for bin_entry in radial:
            self.assertTrue(math.isfinite(bin_entry.s_q))
            self.assertGreaterEqual(bin_entry.s_q, 0.0)
            self.assertGreaterEqual(bin_entry.count, 0)

    def test_cli_smoke_writes_expected_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            trajectory = tmp_path / "trajectory.csv"
            outdir = tmp_path / "fourier"
            points = make_points(2, 2, lambda ix, iy: ix + 2.0 * iy)
            row = ",".join(str(value) for point in points for value in point)
            trajectory.write_text(row + ",\n", encoding="utf-8")

            exit_code = spectrum.main(
                [
                    "--trajectory",
                    str(trajectory),
                    "--outdir",
                    str(outdir),
                    "--grid-shape",
                    "2",
                    "2",
                    "--spacing",
                    "1.0",
                    "1.0",
                    "--radial-bins",
                    "3",
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertTrue((outdir / "spectrum_raw.csv").is_file())
            self.assertTrue((outdir / "spectrum_radial.csv").is_file())
            self.assertTrue((outdir / "spectrum_summary.txt").is_file())


if __name__ == "__main__":
    unittest.main()
