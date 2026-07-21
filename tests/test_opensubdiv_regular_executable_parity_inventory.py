import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenSubdivRegularExecutableParityInventoryTest(unittest.TestCase):
    def test_inventory_has_no_missing_anchors_or_default_dependency_leaks(self):
        result = subprocess.run(
            ["python3", "scripts/inventory_opensubdiv_regular_executable_parity.py", "--check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_absent_dependency_wrapper_skips_cleanly(self):
        result = subprocess.run(
            ["env", "-u", "OPENSUBDIV_ROOT", "scripts/run_opensubdiv_regular_executable_parity.sh"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "skipped")
        self.assertTrue(report["not_production_routing"])

    def test_comparator_accepts_exact_four_way_parity(self):
        base = {
            "finite": True,
            "vertex_count": 1,
            "active_face_ids": [2],
            "global_energy": [1.0],
            "face_energy": [2.0],
            "vertex_forces": [3.0],
            "face_normals": [4.0],
            "face_area": [5.0],
            "face_legacy_volume": [6.0],
            "face_mean_curvature": [7.0],
        }
        modes = {
            "serial-direct.json": ("serial", False, False),
            "serial-candidate.json": ("serial", True, True),
            "openmp-direct.json": ("openmp", False, False),
            "openmp-candidate.json": ("openmp", True, True),
        }
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name, (mode, requested, installed) in modes.items():
                report = dict(base)
                report["execution_mode"] = mode
                report["candidate_rows_requested"] = requested
                report["candidate_rows_installed_in_opt_in_build"] = installed
                report["production_route_exercised"] = requested
                report["candidate_shape_face_count"] = 1 if requested else 0
                path = Path(directory) / name
                path.write_text(json.dumps(report), encoding="utf-8")
                paths[name] = path
            result = subprocess.run(
                [
                    "python3",
                    "scripts/compare_opensubdiv_regular_executable_parity.py",
                    "--serial-direct",
                    str(paths["serial-direct.json"]),
                    "--serial-candidate",
                    str(paths["serial-candidate.json"]),
                    "--openmp-direct",
                    str(paths["openmp-direct.json"]),
                    "--openmp-candidate",
                    str(paths["openmp-candidate.json"]),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["production_route_exercised"])
        self.assertTrue(report["route_activation_allowed"])


if __name__ == "__main__":
    unittest.main()
