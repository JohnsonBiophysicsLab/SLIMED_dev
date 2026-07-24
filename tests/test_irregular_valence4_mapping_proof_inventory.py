import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "scripts/inventory_irregular_valence4_mapping_proof.py"
PROBE_PATH = ROOT / "scripts/probe_opensubdiv_feasibility.py"
WRAPPER_PATH = ROOT / "scripts/run_irregular_valence4_opensubdiv_mapping_proof.sh"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_mapping_proof", INVENTORY_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourMappingProofInventoryTest(unittest.TestCase):
    def test_inventory_passes(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["approved_for_mapping_sample_transpose_proof"])
        self.assertFalse(report["scientifically_approved"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])

    def test_irregular_proof_map_cannot_false_green_on_coverage_failure(self):
        source = PROBE_PATH.read_text(encoding="utf-8")
        start = source.index("static bool print_irregular_transpose_proof_map(")
        end = source.index("\n}\n#endif", start)
        function_source = source[start:end]
        self.assertIn(
            "bool const proofMapPassed = identityPassed && fixtureCoveragePassed;",
            function_source,
        )
        self.assertIn("return proofMapPassed;", function_source)
        self.assertNotIn("return identityPassed;", function_source)

    def test_dependency_absent_wrapper_skips(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(WRAPPER_PATH), "--json"],
            cwd=ROOT,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "skipped")
        self.assertIn("OPENSUBDIV_ROOT is not set", payload["reason"])

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is not configured for this test process",
    )
    def test_present_dependency_proof(self):
        result = subprocess.run(
            [str(WRAPPER_PATH), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["deterministic_repeat_match"])
        proof = json.loads(payload["prototype_output"][0])
        self.assertTrue(proof["passed"])
        self.assertTrue(proof["approved_fixture"])
        self.assertTrue(proof["approved_for_mapping_sample_transpose_proof"])
        self.assertFalse(proof["scientifically_approved"])
        self.assertEqual(proof["ptex_face_count"], 8)
        self.assertEqual(len(proof["faces"]), 8)
        expected_faces = [
            [0, 2, 3],
            [0, 3, 4],
            [0, 4, 5],
            [0, 5, 2],
            [1, 3, 2],
            [1, 4, 3],
            [1, 5, 4],
            [1, 2, 5],
        ]
        self.assertEqual(
            [face["ptex_face_index"] for face in proof["faces"]],
            list(range(8)),
        )
        self.assertEqual(
            [face["oriented_fixture_vertex_ids"] for face in proof["faces"]],
            expected_faces,
        )
        self.assertTrue(
            all(
                face["all_samples_map_to_same_ptex_face_identity"]
                for face in proof["faces"]
            )
        )
        self.assertEqual(
            [sample["quadrature_weight"] for sample in proof["per_face_samples"]],
            [1.0 / 3.0] * 3,
        )
        expected_samples = [
            (1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0),
            (1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0),
            (4.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0),
        ]
        for sample, expected in zip(proof["per_face_samples"], expected_samples):
            self.assertAlmostEqual(sample["v"], expected[0], places=7)
            self.assertAlmostEqual(sample["w"], expected[1], places=7)
            self.assertAlmostEqual(sample["u"], expected[2], places=7)
        self.assertEqual(
            [sample["formula_factor"] for sample in proof["per_face_samples"]],
            [1.0 / 6.0] * 3,
        )
        self.assertTrue(
            proof["row_checks"]["patch_basis_limit_stencil_comparison_passed"]
        )
        self.assertTrue(
            proof["row_checks"]["all_mixed_derivative_rows_identical"]
        )
        self.assertTrue(
            proof["row_checks"][
                "position_partition_of_unity_and_derivative_sum_checks_passed"
            ]
        )
        self.assertEqual(
            proof["transpose_backprojection"]["backprojection_component_count"],
            18,
        )
        self.assertTrue(
            proof["transpose_backprojection"][
                "backprojection_has_exactly_18_components_with_all_six_support"
            ]
        )


if __name__ == "__main__":
    unittest.main()
