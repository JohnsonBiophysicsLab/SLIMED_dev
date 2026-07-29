import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_opensubdiv_integration_composition.py"
)
RUNNER = (
    ROOT
    / "scripts/run_irregular_valence5_opensubdiv_integration_composition.py"
)
WRAPPER = (
    ROOT
    / "scripts/run_irregular_valence5_opensubdiv_integration_composition.sh"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def proof_payload(runner):
    production = {
        "positive_depth_composed_row_shape": runner.ROW_SHAPE,
        "positive_depth_composed_rows": [0.0] * runner.ROW_COUNT,
        "positive_depth_extraordinary_vertex_mask": [
            0.075,
            0.075,
            0.625,
            0.075,
            0.0,
            0.075,
            0.075,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
        "adjacent_face_source_ids": [0, 1, 2] * 20,
    }
    opensubdiv = {
        "row_shape_all_orientations": runner.ALL_ORIENTATION_ROW_SHAPE,
        "orientation_permutations": runner.ORIENTATION_PERMUTATIONS,
        "domains": runner.EXPECTED_DOMAINS,
        "passed": True,
        "composed_rows_all_orientations": (
            [0.0] * runner.ALL_ORIENTATION_ROW_COUNT
        ),
        "oriented_fixture_faces": [0, 1, 2] * 20,
        "opensubdiv_valence5_vertex_edge_weight": 0.08409321892578289,
        "opensubdiv_valence5_vertex_center_weight": 0.5795339053710855,
    }
    return production, opensubdiv


class ValenceFiveIntegrationCompositionInventoryTest(unittest.TestCase):
    def test_inventory_passes(self):
        report = load_module(INVENTORY, "val5_composition_inventory").collect(
            ROOT
        )
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertEqual(report["forbidden_stale_claims"]["located"], 0)
        self.assertFalse(report["composed_row_parity_passed"])
        self.assertTrue(
            report["extraordinary_vertex_mask_policy_mismatch_observed"]
        )
        self.assertFalse(report["mask_policy_causal_sufficiency_proven"])
        self.assertEqual(
            report["next_gate"],
            "explicitly reviewed custom OpenSubdiv Loop scheme or library decision",
        )

    def test_component_and_domain_plan_mutations_are_binding(self):
        runner = load_module(RUNNER, "val5_composition_runner")
        production, opensubdiv = proof_payload(runner)
        passing = runner.compare(production, opensubdiv)
        self.assertTrue(passing["composed_row_parity_passed"])
        self.assertTrue(passing["extraordinary_vertex_mask_policy_mismatch"])
        self.assertFalse(passing["mask_policy_causal_sufficiency_proven"])

        opensubdiv["composed_rows_all_orientations"][0] = 1.0
        rejected = runner.compare(production, opensubdiv)
        self.assertFalse(rejected["composed_row_parity_passed"])
        self.assertEqual(
            rejected["route_blockers"],
            [
                "composed OpenSubdiv rows do not reproduce the "
                "positive-depth SLIMED rows"
            ],
        )

        opensubdiv["composed_rows_all_orientations"][0] = 0.0
        opensubdiv["domains"] = [dict(domain) for domain in runner.EXPECTED_DOMAINS]
        opensubdiv["domains"][0]["offset"] = [0.1, 0.5]
        rejected = runner.compare(production, opensubdiv)
        self.assertEqual(rejected["status"], "failed")
        self.assertIn("reviewed child-domain affine plan drift", rejected["errors"])

    def test_unrelated_residual_cannot_be_attributed_to_equal_masks(self):
        runner = load_module(RUNNER, "val5_composition_attribution")
        production, opensubdiv = proof_payload(runner)
        opensubdiv["opensubdiv_valence5_vertex_edge_weight"] = 0.075
        opensubdiv["opensubdiv_valence5_vertex_center_weight"] = 0.625
        opensubdiv["composed_rows_all_orientations"][0] = 1.0

        report = runner.compare(production, opensubdiv)

        self.assertFalse(report["extraordinary_vertex_mask_policy_mismatch"])
        self.assertFalse(report["mask_policy_causal_sufficiency_proven"])
        self.assertEqual(report["observed_diagnostic_clues"], [])
        self.assertEqual(
            report["route_blockers"],
            [
                "composed OpenSubdiv rows do not reproduce the "
                "positive-depth SLIMED rows"
            ],
        )
        self.assertEqual(
            report["remaining_boundary"],
            "composed row residual attribution diagnostic",
        )
        self.assertFalse(
            any("different valence-5" in blocker for blocker in report["route_blockers"])
        )

    def test_face_orientation_is_bound_by_source_identity(self):
        runner = load_module(RUNNER, "val5_composition_orientation")
        production, opensubdiv = proof_payload(runner)
        opensubdiv["oriented_fixture_faces"][0:3] = [1, 0, 2]
        report = runner.compare(production, opensubdiv)
        self.assertEqual(report["selected_orientation_indices"][0], 2)
        self.assertTrue(report["face_orientation_bound_by_source_identity"])

    def test_wider_tolerance_override_is_rejected(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--tolerance", "1"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("composed_row_parity_passed", result.stdout)
        self.assertIn("unrecognized arguments: --tolerance 1", result.stderr)

    def test_dependency_absent_wrapper_skips(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(WRAPPER), "--json"],
            cwd=ROOT,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is not configured for this test process",
    )
    def test_present_dependency_reports_unresolved_mask_attribution(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertFalse(report["composed_row_parity_passed"])
        self.assertTrue(report["extraordinary_vertex_mask_policy_mismatch"])
        self.assertFalse(report["mask_policy_causal_sufficiency_proven"])
        self.assertEqual(report["row_component_count"], 30240)
        self.assertEqual(
            report["remaining_boundary"],
            "counterfactual valence-5 extraordinary mask attribution diagnostic",
        )
        self.assertEqual(
            report["route_blockers"],
            [
                "composed OpenSubdiv rows do not reproduce the "
                "positive-depth SLIMED rows"
            ],
        )
        self.assertEqual(
            report["observed_diagnostic_clues"],
            [
                "SLIMED and OpenSubdiv use different valence-5 "
                "extraordinary smooth-vertex masks"
            ],
        )


if __name__ == "__main__":
    unittest.main()
