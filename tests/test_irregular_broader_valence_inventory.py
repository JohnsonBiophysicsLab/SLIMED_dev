import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_irregular_broader_valence.py"


class IrregularBroaderValenceInventoryTest(unittest.TestCase):
    def run_inventory(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_check_mode_passes(self):
        result = self.run_inventory("--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_payload_records_unsupported_shapes_and_missing_diagnostic(self):
        result = self.run_inventory("--json", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        behavior = payload["production_behavior"]
        self.assertEqual(behavior["supported_stored_one_ring_sizes"], [11, 12])
        self.assertEqual(behavior["unsupported_stored_one_ring_size"], 0)
        self.assertFalse(behavior["unsupported_preflight_diagnostic"])
        self.assertFalse(behavior["regular_fallback_used"])
        self.assertFalse(behavior["broader_valence_route_enabled"])

        cases = {case["name"]: case for case in payload["generated_closed_topologies"]}
        for name in (
            "closed tetrahedron",
            "closed octahedron",
            "closed triangular bipyramid",
            "closed pentagonal bipyramid",
            "closed hexagonal bipyramid",
            "closed heptagonal bipyramid",
            "closed nonagonal bipyramid",
        ):
            self.assertEqual(cases[name]["current_diagnostic"], "none")
            self.assertEqual(set(cases[name]["production_stored_one_ring_size_counts"]), {"0"})
            self.assertFalse(cases[name]["route_enabled"])

    def test_approved_valence5_fixture_remains_supported_control(self):
        result = self.run_inventory("--json", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        control = next(
            case for case in payload["generated_closed_topologies"]
            if case["name"] == "approved closed valence-5 control"
        )
        self.assertEqual(control["face_valence_triplet_counts"], {"5/5/5": 20})
        self.assertEqual(control["production_stored_one_ring_size_counts"], {"11": 20})
        self.assertEqual(control["current_diagnostic"], "not applicable")


if __name__ == "__main__":
    unittest.main()
