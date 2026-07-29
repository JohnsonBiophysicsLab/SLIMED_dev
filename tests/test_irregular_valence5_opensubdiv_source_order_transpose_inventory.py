import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence5_opensubdiv_source_order_transpose.py"
)
COMPARATOR = (
    ROOT
    / "scripts/compare_irregular_valence5_opensubdiv_source_order_transpose.py"
)
WRAPPER = (
    ROOT / "scripts/run_irregular_valence5_opensubdiv_source_order_transpose.sh"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFiveSourceOrderTransposeInventoryTest(unittest.TestCase):
    def test_inventory_passes(self):
        report = load_module(INVENTORY, "val5_inventory").collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertTrue(report["proof_only"])
        self.assertFalse(report["production_route_enabled"])
        self.assertTrue(
            report["existing_dependency_free_production_baseline_executed"]
        )
        self.assertFalse(report["opensubdiv_production_force_path_executed"])

    def test_canonical_order_mutation_is_binding(self):
        comparator = load_module(COMPARATOR, "val5_comparator")
        production = {
            "fixture": "closed_valence5_icosahedron",
            "active_face_ids": list(range(20)),
            "one_ring_source_ids": [
                source
                for row in comparator.EXPECTED_ONE_RINGS
                for source in row
            ],
        }
        faces = []
        for face_index, row in enumerate(comparator.EXPECTED_ONE_RINGS):
            faces.append(
                {
                    "fixture_face_index": face_index,
                    "ptex_face_index": face_index,
                    "source_coverage_union": sorted(set(row)),
                    "backprojected_source_components": [0.0] * 36,
                    "weighted_control_dot": 0.0,
                    "weighted_sample_dot": 0.0,
                    "weighted_transpose_passed": True,
                }
            )
        proof = {
            "passed": True,
            "proof_only": True,
            "not_production_routing": True,
            "production_route_enabled": False,
            "production_force_path_executed": False,
            "faces": faces,
        }
        wrapper = {
            "status": "passed",
            "prototype_output": [
                json.dumps({"valence5_source_order_transpose": proof})
            ],
        }
        coordinates = [[float(source), 0.0, 0.0] for source in range(12)]
        passing = comparator.compare_reports(production, wrapper, coordinates)
        self.assertEqual(passing["status"], "passed", passing["errors"])

        mutated = copy.deepcopy(production)
        mutated["one_ring_source_ids"][0], mutated["one_ring_source_ids"][1] = (
            mutated["one_ring_source_ids"][1],
            mutated["one_ring_source_ids"][0],
        )
        rejected = comparator.compare_reports(mutated, wrapper, coordinates)
        self.assertEqual(rejected["status"], "failed")
        self.assertIn(
            "production 20x11 one-ring source order drift", rejected["errors"]
        )

        wrong_sources = copy.deepcopy(wrapper)
        wrong_payload = json.loads(wrong_sources["prototype_output"][0])
        wrong_payload["valence5_source_order_transpose"]["faces"][0][
            "source_coverage_union"
        ][0] = 3
        wrong_sources["prototype_output"][0] = json.dumps(wrong_payload)
        source_rejected = comparator.compare_reports(
            production, wrong_sources, coordinates
        )
        self.assertIn(
            "per-face OpenSubdiv source sets do not match production one-rings",
            source_rejected["errors"],
        )

        wrong_dot = copy.deepcopy(wrapper)
        wrong_payload = json.loads(wrong_dot["prototype_output"][0])
        wrong_payload["valence5_source_order_transpose"]["faces"][0][
            "weighted_sample_dot"
        ] = 1.0
        wrong_dot["prototype_output"][0] = json.dumps(wrong_payload)
        transpose_rejected = comparator.compare_reports(
            production, wrong_dot, coordinates
        )
        self.assertIn(
            "independent weighted-transpose oracle mismatch",
            transpose_rejected["errors"],
        )

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
    def test_present_dependency_full_proof(self):
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
        self.assertTrue(report["exact_production_one_ring_order_match"])
        self.assertTrue(report["per_face_opensubdiv_source_sets_match"])
        self.assertTrue(report["all_face_weighted_transposes_passed"])
        self.assertEqual(report["slot_backprojection_component_count"], 660)
        self.assertLessEqual(
            report["duplicate_slot_rescatter_max_abs_difference"], 1.0e-12
        )
        self.assertLessEqual(
            report["independent_weighted_transpose_max_abs_difference"], 5.0e-6
        )


if __name__ == "__main__":
    unittest.main()
