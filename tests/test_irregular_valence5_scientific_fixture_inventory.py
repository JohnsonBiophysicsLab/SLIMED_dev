import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_irregular_valence5_scientific_fixture.py"
SPEC = importlib.util.spec_from_file_location(
    "inventory_irregular_valence5_scientific_fixture", SCRIPT
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class IrregularValence5ScientificFixtureInventoryTest(unittest.TestCase):
    def test_fixture_contract_and_anchors_pass(self):
        report = inventory.collect(ROOT)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["vertex_count"], 12)
        self.assertEqual(report["face_count"], 20)
        self.assertEqual(report["vertex_valence_counts"], {5: 12})
        self.assertEqual(report["edge_incidence_counts"], {2: 30})
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertTrue(report["not_broader_valence_routing"])

    def test_check_mode_passes(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
