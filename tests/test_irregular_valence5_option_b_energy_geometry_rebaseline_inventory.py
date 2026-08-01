import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.py"
WRAPPER = ROOT / "scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.sh"
INVENTORY = ROOT / "scripts/inventory_irregular_valence5_option_b_energy_geometry_rebaseline.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def canonical_identity(module):
    vertices = module.fixture_rows(module.VERTICES, 3, float)
    faces = module.fixture_rows(module.FACES, 3, int)
    source_order = module.load_module(module.SOURCE_ORDER, "test_source_order")
    rings = [list(row) for row in source_order.EXPECTED_ONE_RINGS]
    production = {
        "fixture": "closed_valence5_icosahedron",
        "scientific_stand_in_scope": "narrow_positive_depth_11_control",
        "vertex_count": 12,
        "face_count": 20,
        "eleven_control_face_count": 20,
        "all_valence_five": True,
        "all_faces_physical": True,
        "deterministic_duplicate_aggregation_shape": True,
        "active_face_ids": list(range(20)),
        "one_ring_source_ids": [source for ring in rings for source in ring],
        "scientific_coordinates": module.expected_perturbed_coordinates(vertices),
    }
    proof_faces = []
    for face, ring in enumerate(rings):
        proof_faces.append({
            "fixture_face_index": face,
            "ptex_face_index": face,
            "oriented_fixture_vertex_ids": faces[face],
            "source_coverage_union": sorted(set(ring)),
            "samples": [
                {"sample": sample, "rows": [[0.0] * 12 for _ in range(7)]}
                for sample in range(3)
            ],
        })
    proof = {
        "passed": True,
        "proof_only": True,
        "not_production_routing": True,
        "production_route_enabled": False,
        "production_force_path_executed": False,
        "coordinate_mapping": "s=v,t=w,u=1-v-w",
        "row_order": ["position", "dv", "dw", "dvv", "dww", "dvw", "dwv"],
        "sample_count_per_face": 3,
        "quadrature_weight": 1.0 / 3.0,
        "faces": proof_faces,
    }
    return production, proof


class OptionBEnergyGeometryInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load(RUNNER, "option_b_energy_geometry")

    def test_inventory_passes(self):
        inventory = load(INVENTORY, "option_b_energy_geometry_inventory")
        report = inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])
        self.assertEqual(report["forbidden_stale_claims"]["located"], 0)

    def test_exact_identity_and_order_mutations_are_binding(self):
        production, proof = canonical_identity(self.runner)
        self.runner.validate_identity(production, proof)
        mutations = []
        changed = copy.deepcopy(production)
        changed["scientific_coordinates"][0] += 1.0e-4
        mutations.append(changed)
        changed = copy.deepcopy(production)
        changed["one_ring_source_ids"][0], changed["one_ring_source_ids"][1] = changed["one_ring_source_ids"][1], changed["one_ring_source_ids"][0]
        mutations.append(changed)
        for changed in mutations:
            with self.subTest(production=changed):
                with self.assertRaises(RuntimeError):
                    self.runner.validate_identity(changed, proof)

        for mutate in ("orientation", "ptex", "sample", "cardinality", "mixed"):
            changed = copy.deepcopy(proof)
            if mutate == "orientation":
                changed["faces"][0]["oriented_fixture_vertex_ids"][0:2] = reversed(changed["faces"][0]["oriented_fixture_vertex_ids"][0:2])
            elif mutate == "ptex":
                changed["faces"][0]["ptex_face_index"] = 1
            elif mutate == "sample":
                changed["faces"][0]["samples"][0]["sample"] = 2
            elif mutate == "cardinality":
                changed["faces"][0]["samples"][0]["rows"].pop()
            else:
                changed["faces"][0]["samples"][0]["rows"][6][0] = 1.0
            with self.subTest(mutate=mutate), self.assertRaises(RuntimeError):
                self.runner.validate_identity(production, changed)

    def test_numeric_type_and_shape_guards_reject_false_greens(self):
        for value in (False, "1.0", math.inf, math.nan):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.runner.finite_list([value], 1, "mutation")
        with self.assertRaises(RuntimeError):
            self.runner.finite_list([], 1, "missing")
        with self.assertRaises(RuntimeError):
            self.runner.finite_list([1.0, 2.0], 1, "long")
        with self.assertRaises(RuntimeError):
            self.runner.strict_json('{"status":"passed","status":"failed"}', "duplicate")

    def test_flipped_normal_and_aggregation_mutations_are_located(self):
        current = [1.0, 0.0, 0.0, 2.0, 3.0, 4.0]
        stock = [-1.0, 0.0, 0.0, 2.0, 3.0, 4.0]
        _, location, parity = self.runner.differences(
            current, stock, self.runner.GEOMETRY_CHANNELS, True
        )
        self.assertFalse(parity)
        self.assertEqual(location["face"], 0)
        self.assertEqual(location["channel"], "normal_x")
        self.assertEqual(location["current"], 1.0)
        self.assertEqual(location["stock"], -1.0)
        face_energy = self.runner.build_face_energy(
            [1.0, 2.0], [0.25, 0.5]
        )
        self.assertEqual(face_energy[1], 0.0)
        self.assertEqual(face_energy[2], 0.0)

    def test_complete_observable_digest_and_oracle_comparison_are_binding(self):
        baseline = {
            "global_energy": [0.125 * index for index in range(10)],
            "face_energy": [0.025 * index for index in range(200)],
            "geometry": [0.05 * index for index in range(120)],
        }
        expected = self.runner.canonical_observable_digest(baseline)
        with mock.patch.object(
            self.runner, "EXPECTED_CANONICAL_OBSERVABLE_DIGEST", expected
        ):
            self.runner.validate_candidate_oracle_observables(
                copy.deepcopy(baseline), copy.deepcopy(baseline)
            )

            candidate = copy.deepcopy(baseline)
            candidate["global_energy"][1] += 1.0
            with self.assertRaisesRegex(RuntimeError, "independent long-double"):
                self.runner.validate_candidate_oracle_observables(
                    candidate, copy.deepcopy(baseline)
                )

            for key, index in (
                ("geometry", 0),       # face 0 normal_x
                ("face_energy", 5),    # face 0 regularization
                ("geometry", 4),       # face 0 area
            ):
                candidate = copy.deepcopy(baseline)
                oracle = copy.deepcopy(baseline)
                candidate[key][index] += 1.0
                oracle[key][index] += 1.0
                with self.subTest(key=key, index=index), self.assertRaisesRegex(
                    RuntimeError, "complete canonical observable digest"
                ):
                    self.runner.validate_candidate_oracle_observables(
                        candidate, oracle
                    )

    def test_stale_readiness_claim_is_binding(self):
        inventory = load(INVENTORY, "option_b_stale_readiness")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in inventory.FORBIDDEN_STALE_CLAIMS:
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, destination)
            readiness = root / inventory.READINESS
            readiness.write_text(
                readiness.read_text(encoding="utf-8")
                + "\nStock energy, geometry, output, and serial/OpenMP evidence remains pending.\n",
                encoding="utf-8",
            )
            located = inventory.scan_forbidden(root)
        self.assertTrue(any("Stock energy, geometry" in item for item in located))

    def test_widened_tolerance_option_is_rejected(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--tolerance", "1"], cwd=ROOT,
            env={key: value for key, value in os.environ.items() if key != "OPENSUBDIV_ROOT"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_dependency_absent_wrapper_skips(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run([str(WRAPPER), "--json"], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")

    @unittest.skipUnless(os.environ.get("OPENSUBDIV_ROOT"), "OpenSubdiv not configured")
    def test_present_dependency_proof(self):
        result = subprocess.run([str(WRAPPER), "--json", "--check", "--require-opensubdiv"], cwd=ROOT, env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["energy_geometry_parity_passed"])
        self.assertTrue(report["independent_long_double_oracle_passed"])
        self.assertLessEqual(report["candidate_oracle_max_abs_difference"], 1.0e-10)
        self.assertLessEqual(
            report["candidate_oracle_global_energy_max_abs_difference"],
            1.0e-10,
        )
        self.assertEqual(report["canonical_observable_component_count"], 330)
        self.assertEqual(
            report["canonical_observable_digest"],
            self.runner.EXPECTED_CANONICAL_OBSERVABLE_DIGEST,
        )
        self.assertTrue(report["candidate_trailing_token_rejected"])
        self.assertTrue(report["oracle_trailing_token_rejected"])
        self.assertFalse(report["output_visible_evidence_complete"])
        self.assertFalse(report["option_b_selected"])
        self.assertFalse(report["stock_semantics_scientifically_approved"])


if __name__ == "__main__":
    unittest.main()
