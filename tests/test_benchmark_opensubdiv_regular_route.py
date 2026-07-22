import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/benchmark_opensubdiv_regular_route.py"
SPEC = importlib.util.spec_from_file_location("benchmark_opensubdiv_regular_route", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class OpenSubdivRegularRouteBenchmarkTest(unittest.TestCase):
    def test_parse_lists(self):
        self.assertEqual(MODULE.parse_csv_floats("12.5, 7.5,5"), [12.5, 7.5, 5.0])
        self.assertEqual(MODULE.parse_csv_ints("1,4"), [1, 4])

    def test_rewrite_l_face_preserves_comment(self):
        text = "before = 1\nlFace = 5.0 # mesh scale\nafter = 2\n"
        self.assertEqual(
            MODULE.rewrite_l_face(text, 7.5),
            "before = 1\nlFace = 7.5 # mesh scale\nafter = 2\n",
        )

    def test_rewrite_l_face_requires_assignment(self):
        with self.assertRaises(ValueError):
            MODULE.rewrite_l_face("sideX = 100\n", 5.0)

    def test_rewrite_l_face_rejects_duplicate_assignments(self):
        with self.assertRaises(ValueError):
            MODULE.rewrite_l_face("lFace = 5\nlFace = 7.5\n", 5.0)

    def test_summary(self):
        summary = MODULE.summarize([1.0, 2.0, 3.0])
        self.assertEqual(summary["mean_seconds"], 2.0)
        self.assertEqual(summary["median_seconds"], 2.0)
        self.assertEqual(summary["min_seconds"], 1.0)
        self.assertEqual(summary["max_seconds"], 3.0)


if __name__ == "__main__":
    unittest.main()
