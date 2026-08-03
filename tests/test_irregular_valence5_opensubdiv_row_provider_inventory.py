import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module(
    "run_irregular_valence5_opensubdiv_row_provider",
    "scripts/run_irregular_valence5_opensubdiv_row_provider.py",
)
inventory = load_module(
    "inventory_irregular_valence5_opensubdiv_row_provider",
    "scripts/inventory_irregular_valence5_opensubdiv_row_provider.py",
)


def synthetic_packages():
    provider_faces = []
    proof_faces = []
    for face in range(20):
        provider_samples = []
        proof_samples = []
        for sample in range(3):
            provider_rows = [[0.0] * 9 for _ in range(7)]
            provider_rows[6] = list(provider_rows[5])
            provider_samples.append({"sample": sample, "rows": provider_rows})
            proof_samples.append({
                "sample": sample,
                "rows": [[0.0] * 12 for _ in range(7)],
            })
        oriented = [face % 12, (face + 1) % 12, (face + 2) % 12]
        provider_faces.append({
            "face": face,
            "oriented_face_vertices": oriented,
            "source_ids": list(range(9)),
            "samples": provider_samples,
        })
        proof_faces.append({
            "fixture_face_index": face,
            "oriented_fixture_vertex_ids": oriented,
            "source_coverage_union": list(range(9)),
            "samples": proof_samples,
        })
    return {"rows": provider_faces}, {"faces": proof_faces}


class IrregularValence5OpenSubdivRowProviderInventoryTest(unittest.TestCase):
    def test_synthetic_rows_compare_exactly(self):
        provider, proof = synthetic_packages()

        maximum, identities, mappings = runner.compare_rows(provider, proof)

        self.assertEqual(maximum, 0.0)
        self.assertTrue(identities)
        self.assertTrue(mappings)

    def test_source_mapping_drift_is_visible(self):
        provider, proof = synthetic_packages()
        proof["faces"][0]["source_coverage_union"] = list(range(1, 10))

        maximum, identities, mappings = runner.compare_rows(provider, proof)

        self.assertEqual(maximum, 0.0)
        self.assertTrue(identities)
        self.assertFalse(mappings)

    def test_nonfinite_and_boolean_coefficients_fail(self):
        provider, proof = synthetic_packages()
        for invalid in (math.nan, math.inf, True):
            with self.subTest(invalid=invalid):
                mutated = copy.deepcopy(provider)
                mutated["rows"][0]["samples"][0]["rows"][0][0] = invalid
                with self.assertRaises(RuntimeError):
                    runner.compare_rows(mutated, proof)

    def test_mixed_row_drift_fails(self):
        provider, proof = synthetic_packages()
        provider["rows"][0]["samples"][0]["rows"][6][0] = 1.0

        with self.assertRaises(RuntimeError):
            runner.compare_rows(provider, proof)

    def test_phase1_inventory_passes(self):
        report = inventory.collect(ROOT)

        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["phase2_integration_authorized"])

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is required for the real stock provider comparison",
    )
    def test_enabled_provider_matches_accepted_proof_when_available(self):
        result = subprocess.run(
            [
                str(ROOT / "scripts/run_irregular_valence5_opensubdiv_row_provider.sh"),
                "--json",
                "--check",
                "--require-opensubdiv",
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertLessEqual(
            payload["max_abs_difference_vs_accepted_float_proof"],
            payload["comparison_tolerance"],
        )
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(payload["phase2_integration_authorized"])


if __name__ == "__main__":
    unittest.main()
