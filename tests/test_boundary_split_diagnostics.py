import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "boundary_split_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location("boundary_split_diagnostics", SCRIPT_PATH)
diagnostics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = diagnostics
SPEC.loader.exec_module(diagnostics)


class BoundarySplitDiagnosticsTest(unittest.TestCase):
    def test_parser_tolerates_spaces_and_trailing_commas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vertex_path = Path(tmpdir) / "vertex_type_final.csv"
            vertex_path.write_text(
                "\n".join(
                    [
                        " 0.0, 0.0, 0.0, 0, -1, ",
                        "1.0, 0.0, 0.0, 2, -1,",
                        "1.0, 0.0, 0.0, 3, 1, ",
                        "1.000001, 0.0, 0.0, 3, 1,",
                        "5.0, 0.0, 0.0, 4, 99,",
                    ]
                )
            )

            vertices, skipped_headers = diagnostics.parse_vertex_csv(vertex_path)

        self.assertEqual(skipped_headers, 0)
        self.assertEqual(len(vertices), 5)
        self.assertEqual(vertices[0].type_name, "Real")
        self.assertEqual(vertices[2].type_name, "PeriodicReflectiveBoundary")
        self.assertEqual(vertices[4].reflective_index, 99)

    def test_diagnose_reports_duplicate_reflective_and_face_signals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            vertex_path = tmp / "vertex_type_final.csv"
            baseline_path = tmp / "vertex_type_begin.csv"
            face_path = tmp / "face.csv"
            output_path = tmp / "diagnostics.csv"

            vertex_path.write_text(
                "\n".join(
                    [
                        "0.0, 0.0, 0.0, 0, -1,",
                        "1.0, 0.0, 0.0, 2, -1,",
                        "1.0, 0.0, 0.0, 3, 1,",
                        "1.000001, 0.0, 0.0, 3, 1,",
                        "5.0, 0.0, 0.0, 4, 99,",
                    ]
                )
            )
            baseline_path.write_text(
                "\n".join(
                    [
                        "0.0, 0.0, 0.0, 0, -1,",
                        "1.0, 0.0, 0.0, 2, -1,",
                        "1.0, 0.0, 0.0, 3, 1,",
                        "1.0, 0.0, 0.0, 3, 1,",
                        "5.0, 0.0, 0.0, 4, 99,",
                    ]
                )
            )
            face_path.write_text("0,1,2\n0,4,99\n")

            vertices, _ = diagnostics.parse_vertex_csv(vertex_path)
            baseline_vertices, _ = diagnostics.parse_vertex_csv(baseline_path)
            faces, _ = diagnostics.parse_face_csv(face_path)
            rows, summary = diagnostics.diagnose_vertices(
                vertices,
                baseline_vertices=baseline_vertices,
                faces=faces,
                duplicate_tolerance=1e-9,
                split_tolerance=1e-7,
            )
            diagnostics.write_diagnostics_csv(rows, output_path)

            with output_path.open(newline="") as handle:
                written_rows = list(csv.DictReader(handle))

        record_types = {row["record_type"] for row in written_rows}
        self.assertEqual(summary["duplicate_coordinate_group_count"], 1)
        self.assertEqual(summary["invalid_reflective_index_count"], 1)
        self.assertEqual(summary["suspected_split_near_boundary_count"], 0)
        self.assertEqual(summary["reflective_displacement_mismatch_count"], 1)
        self.assertEqual(summary["invalid_face_indices_count"], 1)
        self.assertEqual(summary["mixed_family_face_count"], 1)
        self.assertIn("duplicate_coordinate_member", record_types)
        self.assertIn("reflective_pair_displacement", record_types)
        self.assertIn("reflective_displacement_mismatch", record_types)
        self.assertIn("invalid_face_indices", record_types)


if __name__ == "__main__":
    unittest.main()
