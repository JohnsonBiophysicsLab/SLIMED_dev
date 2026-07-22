import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


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

    def test_session_roots_are_unique_for_same_timestamp(self):
        nominal_time = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            work_root = Path(temp_dir)
            first = MODULE.create_session_root(work_root, nominal_time)
            second = MODULE.create_session_root(work_root, nominal_time)

            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, work_root)
            self.assertEqual(second.parent, work_root)
            self.assertTrue(first.name.startswith("20260722T120000Z-"))
            self.assertTrue(second.name.startswith("20260722T120000Z-"))

    def test_same_timestamp_sessions_remain_isolated_end_to_end(self):
        nominal_time = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        original_create_session_root = MODULE.create_session_root
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "probe.sh"
            executable.write_text("#!/bin/sh\ntouch child-output.txt\n", encoding="utf-8")
            executable.chmod(0o755)
            params = root / "input.params"
            params.write_text("lFace = 5\n", encoding="utf-8")
            work_root = root / "work"
            outputs = [root / "first.json", root / "second.json"]

            def fixed_nominal_time(path):
                return original_create_session_root(path, nominal_time)

            with mock.patch.object(
                MODULE, "create_session_root", side_effect=fixed_nominal_time
            ), redirect_stdout(io.StringIO()):
                for output in outputs:
                    self.assertEqual(
                        MODULE.main(
                            [
                                "--executable",
                                str(executable),
                                "--params",
                                str(params),
                                "--l-face",
                                "5",
                                "--threads",
                                "1",
                                "--warmups",
                                "0",
                                "--repeats",
                                "1",
                                "--work-root",
                                str(work_root),
                                "--output",
                                str(output),
                            ]
                        ),
                        0,
                    )

            session_roots = [
                Path(json.loads(output.read_text(encoding="utf-8"))["metadata"]["work_root"])
                for output in outputs
            ]
            self.assertNotEqual(session_roots[0], session_roots[1])
            for session_root in session_roots:
                self.assertEqual(len(list(session_root.rglob("child-output.txt"))), 2)


if __name__ == "__main__":
    unittest.main()
