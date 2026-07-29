import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = (
    ROOT / "scripts/inventory_irregular_valence5_opensubdiv_fixture_coverage.py"
)
PROBE_PATH = ROOT / "scripts/probe_opensubdiv_feasibility.py"
WRAPPER_PATH = (
    ROOT / "scripts/run_irregular_valence5_opensubdiv_fixture_coverage.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence5_opensubdiv_fixture_coverage",
        INVENTORY_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFiveOpenSubdivFixtureCoverageInventoryTest(unittest.TestCase):
    def test_inventory_passes(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["fixture_coverage_proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["production_force_path_executed"])
        self.assertEqual(
            report["next_gate"],
            "counterfactual valence-5 extraordinary mask attribution diagnostic",
        )
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])

    def test_coverage_failure_is_binding(self):
        source = PROBE_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "completeCoverage && sampleCoverage",
            source,
        )
        self.assertIn(
            "if (!valence5FixtureCoveragePassed) {\n        return 14;",
            source,
        )
        self.assertIn(
            "if (!valence5_fixture_identity_matches(mesh))",
            source,
        )
        self.assertIn(
            "finiteEvaluatedSamples == requestedSamples",
            source,
        )

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
    def test_present_dependency_proof_and_malformed_fixture_rejection(self):
        env = os.environ.copy()
        result = subprocess.run(
            [str(WRAPPER_PATH), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["deterministic_repeat_match"])
        self.assertTrue(payload["fixture_coverage_proof_only"])
        self.assertFalse(payload["production_route_enabled"])
        proof = json.loads(payload["prototype_output"][0])
        coverage = proof["aggregate_source_coverage"]
        self.assertEqual(proof["control_vertex_count"], 12)
        self.assertEqual(proof["face_count"], 20)
        self.assertEqual(coverage["ptex_face_count"], 20)
        self.assertEqual(coverage["requested_sample_count"], 180)
        self.assertEqual(coverage["generated_stencil_count"], 180)
        self.assertEqual(coverage["evaluated_sample_count"], 180)
        self.assertEqual(coverage["finite_evaluated_sample_count"], 180)
        self.assertEqual(coverage["found_patch_lookup_count"], 180)
        self.assertTrue(
            coverage["all_stencil_weights_source_ids_and_results_finite"]
        )
        self.assertEqual(coverage["value_source_ids"], list(range(12)))
        self.assertEqual(
            coverage["first_derivative_source_ids"], list(range(12))
        )
        self.assertEqual(
            coverage["second_derivative_source_ids"], list(range(12))
        )
        self.assertTrue(coverage["complete_value_first_second_coverage"])
        self.assertTrue(coverage["all_requested_samples_evaluated"])
        self.assertTrue(coverage["passed"])
        self.assertTrue(proof["proof_only"])
        self.assertTrue(proof["not_production_routing"])
        self.assertTrue(proof["approved_fixture_identity_matches"])
        self.assertFalse(proof["production_route_enabled"])
        self.assertFalse(proof["production_force_path_executed"])

        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            source_dir = ROOT / "data/fixtures/closed_valence5"
            vertex_lines = (source_dir / "vertices.csv").read_text(
                encoding="utf-8"
            ).splitlines()
            face_lines = (source_dir / "faces.csv").read_text(
                encoding="utf-8"
            ).splitlines()

            def run_mutation(vertices, faces):
                (fixture_dir / "vertices.csv").write_text(
                    "\n".join(vertices) + "\n",
                    encoding="utf-8",
                )
                (fixture_dir / "faces.csv").write_text(
                    "\n".join(faces) + "\n",
                    encoding="utf-8",
                )
                return subprocess.run(
                    [
                        str(WRAPPER_PATH),
                        "--json",
                        "--require-opensubdiv",
                        "--valence5-fixture-dir",
                        str(fixture_dir),
                    ],
                    cwd=ROOT,
                    env=env,
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            coordinate_mutation = vertex_lines.copy()
            coordinate_mutation[0] = "-0.5,1.6180339887498948482,0"

            face_order_mutation = face_lines.copy()
            face_order_mutation[0], face_order_mutation[1] = (
                face_order_mutation[1],
                face_order_mutation[0],
            )

            winding_mutation = face_lines.copy()
            first_face = winding_mutation[0].split(",")
            winding_mutation[0] = ",".join(
                [first_face[0], first_face[2], first_face[1]]
            )

            mutations = [
                (vertex_lines, face_lines[:-1]),
                (coordinate_mutation, face_lines),
                (vertex_lines, face_order_mutation),
                (vertex_lines, winding_mutation),
            ]
            for vertices, faces in mutations:
                with self.subTest(vertices=vertices[0], first_face=faces[0]):
                    malformed = run_mutation(vertices, faces)
                    self.assertNotEqual(malformed.returncode, 0)
                    malformed_payload = json.loads(malformed.stdout)
                    self.assertEqual(malformed_payload["status"], "run_failed")
                    self.assertIn(
                        "must exactly match the 12 ordered coordinates and "
                        "20 ordered oriented triangular faces",
                        malformed_payload["stderr"],
                    )


if __name__ == "__main__":
    unittest.main()
