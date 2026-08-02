import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_irregular_valence5_option_b_serial_openmp.py"
WRAPPER = ROOT / "scripts/run_irregular_valence5_option_b_serial_openmp.sh"
HARNESS = ROOT / "experiments/irregular_valence5_option_b_serial_openmp.cpp"
INVENTORY_PATH = ROOT / "scripts/inventory_irregular_valence5_option_b_serial_openmp.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("option_b_serial_openmp", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def load_inventory():
    spec = importlib.util.spec_from_file_location(
        "option_b_serial_openmp_inventory", INVENTORY_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


inventory = load_inventory()


def valid_inputs():
    face_energy = [0.0] * 200
    face_geometry = [0.0] * 120
    per_face_forces = [0.0] * 2160
    for face in range(20):
        face_energy[face * 10] = 10.0 + face
        face_energy[face * 10 + 5] = 0.25 + face * 0.01
        face_geometry[face * 6 + 4] = 2.0 + face * 0.1
        face_geometry[face * 6 + 5] = -0.5 + face * 0.02
        per_face_forces[face * 108 + (face % 108)] = float(face + 1)
    aggregate = runner.recompute_aggregate(per_face_forces)
    energy = {
        "status": "passed",
        "independent_long_double_oracle_passed": True,
        "canonical_observable_vector_tolerance_passed": True,
        "energy_geometry_parity_passed": False,
        "per_face_energy_stock": face_energy,
        "per_face_geometry_stock": face_geometry,
    }
    force_candidate = {
        "status": "passed",
        "opensubdiv_rows_evaluated_by_existing_force_algebra": True,
        "per_face_source_forces": per_face_forces,
        "aggregate_source_forces": aggregate,
    }
    force_report = {
        "status": "passed",
        "force_parity_passed": False,
    }
    harness = {
        "status": "passed",
        "actual_openmp_executed": True,
        "production_shape_replayed": True,
        "finite": True,
        "nonzero_stock_force": True,
        "requested_thread_counts": [1, 2, 4],
        "actual_thread_counts": [1, 2, 4],
        "repeats_per_thread_count": 5,
        "max_serial_openmp_accumulation_difference": 1.0e-13,
        "max_fixed_thread_repeatability_difference": 0.0,
        "max_face_publication_difference": 0.0,
        "max_curvature_force_difference": 1.0e-14,
        "max_area_force_difference": 1.0e-14,
        "max_volume_force_difference": 1.0e-14,
        "max_curvature_energy_sum_difference": 1.0e-13,
        "max_regularization_energy_sum_difference": 0.0,
        "max_area_sum_difference": 1.0e-14,
        "max_legacy_volume_sum_difference": 0.0,
        "serial_expected_aggregate_force_difference": 0.0,
        "serial_aggregate_source_forces": aggregate,
        "serial_curvature_energy_sum": sum(face_energy[0::10]),
        "serial_regularization_energy_sum": sum(face_energy[5::10]),
        "serial_area_sum": sum(face_geometry[4::6]),
        "serial_legacy_volume_sum": sum(face_geometry[5::6]),
    }
    return energy, force_candidate, force_report, harness


class OptionBSerialOpenMpInventoryTest(unittest.TestCase):
    def test_valid_characterization_closes_only_stock_accumulation_lane(self):
        report = runner.compare_reports(*valid_inputs())
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["stock_serial_openmp_accumulation_evidence_complete"])
        self.assertFalse(report["stock_serial_openmp_evidence_pending"])
        self.assertFalse(report["option_b_selected"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["output_contract_repair_authorized"])

    def test_every_accumulated_channel_has_a_fixed_envelope(self):
        fields = (
            "max_serial_openmp_accumulation_difference",
            "max_curvature_force_difference",
            "max_area_force_difference",
            "max_volume_force_difference",
            "max_curvature_energy_sum_difference",
            "max_regularization_energy_sum_difference",
            "max_area_sum_difference",
            "max_legacy_volume_sum_difference",
        )
        for field in fields:
            inputs = valid_inputs()
            inputs[3][field] = 2.0e-10
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                runner.compare_reports(*inputs)

    def test_repeatability_uses_fixed_envelope_and_publication_requires_zero(self):
        inputs = valid_inputs()
        inputs[3]["max_fixed_thread_repeatability_difference"] = 1.0e-15
        self.assertEqual(runner.compare_reports(*inputs)["status"], "passed")
        inputs[3]["max_fixed_thread_repeatability_difference"] = 2.0e-10
        with self.assertRaises(RuntimeError):
            runner.compare_reports(*inputs)
        inputs = valid_inputs()
        inputs[3]["max_face_publication_difference"] = 1.0e-15
        with self.assertRaises(RuntimeError):
            runner.compare_reports(*inputs)

    def test_nonnegative_differences_reject_false_green_numbers(self):
        for value in (True, -1.0, float("nan"), float("inf")):
            inputs = valid_inputs()
            inputs[3]["max_area_force_difference"] = value
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                runner.compare_reports(*inputs)

    def test_scientific_nonparity_gates_are_binding(self):
        mutations = (
            (0, "independent_long_double_oracle_passed", False),
            (0, "canonical_observable_vector_tolerance_passed", False),
            (0, "energy_geometry_parity_passed", True),
            (1, "opensubdiv_rows_evaluated_by_existing_force_algebra", False),
            (2, "force_parity_passed", True),
            (3, "actual_openmp_executed", False),
            (3, "production_shape_replayed", False),
        )
        for index, field, value in mutations:
            inputs = list(valid_inputs())
            inputs[index] = copy.deepcopy(inputs[index])
            inputs[index][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                runner.compare_reports(*inputs)

    def test_thread_counts_and_repeats_are_binding(self):
        for field, value in (
            ("requested_thread_counts", [1, 2]),
            ("actual_thread_counts", [1, 1, 2]),
            ("repeats_per_thread_count", 4),
        ):
            inputs = valid_inputs()
            inputs[3][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                runner.compare_reports(*inputs)

    def test_aggregate_is_independently_recomputed(self):
        inputs = valid_inputs()
        inputs[1]["aggregate_source_forces"][0] += 1.0
        with self.assertRaises(RuntimeError):
            runner.compare_reports(*inputs)
        inputs = valid_inputs()
        inputs[3]["serial_aggregate_source_forces"][0] += 1.0
        with self.assertRaises(RuntimeError):
            runner.compare_reports(*inputs)

    def test_scalar_accumulations_are_independently_recomputed(self):
        for field in (
            "serial_curvature_energy_sum",
            "serial_regularization_energy_sum",
            "serial_area_sum",
            "serial_legacy_volume_sum",
        ):
            inputs = valid_inputs()
            inputs[3][field] += 1.0
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                runner.compare_reports(*inputs)

    def test_dependency_absent_wrapper_skips(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(WRAPPER), "--json"], cwd=ROOT, env=env, check=False,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")

    def test_wrapper_is_executable(self):
        self.assertTrue(WRAPPER.stat().st_mode & stat.S_IXUSR)

    def test_harness_compiles_with_openmp(self):
        with tempfile.TemporaryDirectory(prefix="option-b-serial-omp-compile-") as tmp:
            result = subprocess.run(
                ["c++", "-std=c++17", "-fopenmp", str(HARNESS),
                 "-o", str(Path(tmp) / "harness")],
                cwd=ROOT, check=False, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_harness_executes_and_rejects_trailing_tokens(self):
        energy, force_candidate, _, _ = valid_inputs()
        with tempfile.TemporaryDirectory(prefix="option-b-serial-omp-run-") as tmp:
            tmp_path = Path(tmp)
            binary = tmp_path / "harness"
            package = tmp_path / "package.txt"
            compile_result = subprocess.run(
                ["c++", "-std=c++17", "-fopenmp", str(HARNESS),
                 "-o", str(binary)],
                cwd=ROOT, check=False, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            runner.write_package(package, energy, force_candidate)
            valid = subprocess.run(
                [str(binary), str(package)], cwd=ROOT, check=False, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(
                valid.returncode, 0, valid.stderr or valid.stdout
            )
            self.assertEqual(json.loads(valid.stdout)["status"], "passed")
            with package.open("a", encoding="utf-8") as stream:
                stream.write("TRAILING\n")
            invalid = subprocess.run(
                [str(binary), str(package)], cwd=ROOT, check=False, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertNotEqual(invalid.returncode, 0)

    def test_inventory_passes(self):
        report = inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])

    @unittest.skipUnless(os.environ.get("OPENSUBDIV_ROOT"), "OpenSubdiv opt-in")
    def test_present_dependency_proof(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--check", "--require-opensubdiv"],
            cwd=ROOT, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertLessEqual(
            report["max_serial_openmp_accumulation_difference"], 1.0e-10
        )
        self.assertLessEqual(
            report["max_fixed_thread_repeatability_difference"], 1.0e-10
        )
        self.assertEqual(report["max_face_publication_difference"], 0.0)
        self.assertEqual(report["actual_thread_counts"], [1, 2, 4])


if __name__ == "__main__":
    unittest.main()
