import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_irregular_valence5_option_b_output_visibility.py"
INVENTORY = ROOT / "scripts/inventory_irregular_valence5_option_b_output_visibility.py"
WRAPPER = ROOT / "scripts/run_irregular_valence5_option_b_output_visibility.sh"
ANALYSIS_CONSUMERS = (
    ROOT / "analysis/plotvertex.py",
    ROOT / "analysis/plotvertex_gag.py",
    ROOT / "analysis/gag_scaffolding_plotvertex.py",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OptionBOutputVisibilityInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load(RUNNER_PATH, "option_b_output_visibility_runner_test")

    def canonical_inputs(self):
        global_energy = [0.0] * 10
        global_energy[0] = 12.5
        global_energy[5] = 0.75
        global_energy[9] = 13.25
        face_energy = []
        face_rows = [[
            "Face_index", "E_Curvature", "E_Area", "E_Volume", "E_Thickness",
            "E_Tilt", "E_Regularization", "E_HarmonicBond", "E_GagScaffolding",
            "E_IdealizedProteinLattice", "E_Total",
        ]]
        for face in range(20):
            curvature = float(face + 1)
            regularization = 0.25
            total = curvature + regularization
            channels = [curvature, 0.0, 0.0, 0.0, 0.0,
                        regularization, 0.0, 0.0, 0.0, total]
            face_energy.extend(channels)
            face_rows.append([str(face)] + [str(value) for value in channels])
        aggregate = [0.0] * 108
        energy_rows = [[
            "E_Curvature", "E_Area", "E_Volume", "E_Thickness", "E_Tilt",
            "E_Regularization", "E_HarmonicBond", "E_GagScaffolding",
            "E_IdealizedProteinLattice", "E_Total ((pN.nm))", "Mean Force (pN)",
        ], [str(value) for value in global_energy] + ["0"]]
        energy_report = {
            "status": "passed",
            "independent_long_double_oracle_passed": True,
            "canonical_observable_vector_tolerance_passed": True,
            "energy_geometry_parity_passed": False,
            "global_energy_stock": global_energy,
            "per_face_energy_stock": face_energy,
        }
        force_candidate = {
            "status": "passed",
            "opensubdiv_rows_evaluated_by_existing_force_algebra": True,
            "per_face_source_forces": [0.0] * (20 * 108),
            "aggregate_source_forces": aggregate,
        }
        force_report = {"status": "passed", "force_parity_passed": False}
        harness = {
            "status": "passed",
            "energy_force_writer_executed": True,
            "element_face_energy_writer_executed": True,
            "checkpoint_writer_executed": True,
            "checkpoint_loader_executed": True,
            "checkpoint_total_force_roundtrip_max_abs_difference": 0.0,
            "checkpoint_record_energy_roundtrip_max_abs_difference": 0.0,
        }
        for prefix, _ in self.runner.CHECKPOINT_PRESERVATION_FIELDS:
            harness[f"{prefix}_preserved"] = True
            harness[f"{prefix}_max_abs_difference"] = 0.0
        return energy_report, force_candidate, force_report, harness, energy_rows, face_rows

    def compare(self, values):
        return self.runner.compare_output_artifacts(*values)

    def test_repair_binds_complete_output_contract(self):
        report = self.compare(self.canonical_inputs())
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["output_writers_executed_and_parsed"])
        self.assertTrue(report["output_characterization_complete"])
        self.assertTrue(report["output_visible_evidence_complete"])
        self.assertTrue(report["output_contract_repair_authorized"])
        self.assertTrue(report["output_contract_repair_complete"])
        self.assertTrue(report["element_face_energy_csv_schema_matches"])
        self.assertTrue(report["checkpoint_force_family_components_serialized"])
        self.assertTrue(report["face_normals_output_visible"])
        self.assertEqual(report["writer_blockers"], [])

    def test_writer_execution_and_checkpoint_roundtrips_are_binding(self):
        baseline = self.canonical_inputs()
        for key in (
            "energy_force_writer_executed",
            "element_face_energy_writer_executed",
            "checkpoint_writer_executed",
            "checkpoint_loader_executed",
        ):
            mutated = copy.deepcopy(baseline)
            mutated[3][key] = False
            with self.subTest(key=key), self.assertRaisesRegex(
                RuntimeError, "real output writer harness did not pass"
            ):
                self.compare(mutated)
        for key, message in (
            ("checkpoint_total_force_roundtrip_max_abs_difference", "total-force"),
            ("checkpoint_record_energy_roundtrip_max_abs_difference", "energy-record"),
        ):
            mutated = copy.deepcopy(baseline)
            mutated[3][key] = 1.0e-15
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, message):
                self.compare(mutated)

    def test_face_schema_and_each_checkpoint_preservation_claim_are_binding(self):
        baseline = self.canonical_inputs()
        for prefix, _ in self.runner.CHECKPOINT_PRESERVATION_FIELDS:
            lost = copy.deepcopy(baseline)
            lost[3][f"{prefix}_preserved"] = False
            with self.subTest(prefix=prefix), self.assertRaisesRegex(
                RuntimeError, "preservation drift"
            ):
                self.compare(lost)
            inexact = copy.deepcopy(baseline)
            inexact[3][f"{prefix}_max_abs_difference"] = 1.0e-15
            with self.subTest(prefix=prefix), self.assertRaisesRegex(
                RuntimeError, "roundtrip drift"
            ):
                self.compare(inexact)

        widened = copy.deepcopy(baseline)
        widened[5][1].append("unexpected")
        with self.assertRaisesRegex(RuntimeError, "row width drift"):
            self.compare(widened)

        reordered = copy.deepcopy(baseline)
        reordered[5][1][0] = "7"
        with self.assertRaisesRegex(RuntimeError, "face order drift"):
            self.compare(reordered)

    def test_every_serialized_csv_field_family_is_envelope_bound(self):
        baseline = self.canonical_inputs()
        for column in range(11):
            mutated = copy.deepcopy(baseline)
            mutated[4][1][column] = str(float(mutated[4][1][column]) + 1.0)
            with self.subTest(csv="energy", column=column), self.assertRaisesRegex(
                RuntimeError, "EnergyForce.csv serialization envelope exceeded"
            ):
                self.compare(mutated)
        for column in range(1, 11):
            mutated = copy.deepcopy(baseline)
            mutated[5][1][column] = str(float(mutated[5][1][column]) + 1.0e-15)
            with self.subTest(csv="face", column=column), self.assertRaises(RuntimeError):
                self.compare(mutated)

    def test_scientific_gates_and_aggregate_recomputation_are_binding(self):
        baseline = self.canonical_inputs()
        parity = copy.deepcopy(baseline)
        parity[2]["force_parity_passed"] = True
        with self.assertRaisesRegex(RuntimeError, "force input proof did not pass"):
            self.compare(parity)
        energy_parity = copy.deepcopy(baseline)
        energy_parity[0]["energy_geometry_parity_passed"] = True
        with self.assertRaisesRegex(RuntimeError, "scientific gate drift"):
            self.compare(energy_parity)
        aggregate = copy.deepcopy(baseline)
        aggregate[1]["aggregate_source_forces"][0] = 1.0
        with self.assertRaisesRegex(RuntimeError, "aggregate source force drift"):
            self.compare(aggregate)

    def test_checkpoint_differences_reject_nonfinite_negative_and_boolean_values(self):
        baseline = self.canonical_inputs()
        for key in (
            "checkpoint_total_force_roundtrip_max_abs_difference",
            "checkpoint_record_energy_roundtrip_max_abs_difference",
        ):
            for value in (float("nan"), float("inf"), -1.0, False):
                mutated = copy.deepcopy(baseline)
                mutated[3][key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(
                    RuntimeError, "finite nonnegative number"
                ):
                    self.compare(mutated)

    def test_numeric_type_and_shape_guards_reject_false_greens(self):
        baseline = self.canonical_inputs()
        for position, key in ((0, "global_energy_stock"), (1, "aggregate_source_forces")):
            mutated = copy.deepcopy(baseline)
            mutated[position][key][0] = True
            with self.subTest(position=position), self.assertRaises(RuntimeError):
                self.compare(mutated)

    def test_dependency_absent_wrapper_skips(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(WRAPPER), "--json", "--check"], cwd=ROOT, env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")

    def test_wrapper_is_executable_in_git_checkout(self):
        self.assertTrue(WRAPPER.stat().st_mode & stat.S_IXUSR)

    def test_output_harness_compiles_with_available_cxx(self):
        compiler = shutil.which(os.environ.get("CXX", "")) if os.environ.get("CXX") else (
            shutil.which("g++") or shutil.which("c++")
        )
        gsl_config = shutil.which("gsl-config")
        if not compiler or not gsl_config:
            self.skipTest("C++ compiler or gsl-config not available")
        cflags = subprocess.run(
            [gsl_config, "--cflags"], check=True, text=True,
            stdout=subprocess.PIPE,
        ).stdout.split()
        result = subprocess.run(
            [compiler, "-std=c++17", "-Iinclude", "-Iinclude/energy_force",
             "-Iinclude/linalg", "-Iinclude/mesh", "-Iinclude/model",
             "-Iinclude/parameters", *cflags, "-fsyntax-only",
             str(ROOT / "experiments/irregular_valence5_option_b_output_visibility.cpp")],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_checked_in_energy_force_consumers_are_header_driven(self):
        for path in ANALYSIS_CONSUMERS:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertIn('pd.read_csv("EnergyForce.csv", index_col = False)', source)
                self.assertIn('"E_Curvature": "E_curv"', source)
                self.assertIn('"E_Regularization": "E_reg"', source)
                self.assertIn('"E_Total ((pN.nm))": "E_tot"', source)
                self.assertIn('"Mean Force (pN)": "F_mean"', source)
                self.assertNotIn("df_ef.columns =", source)

    def test_inventory_passes(self):
        inventory = load(INVENTORY, "option_b_output_visibility_inventory_test")
        report = inventory.collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])

    @unittest.skipUnless(os.environ.get("OPENSUBDIV_ROOT"), "OpenSubdiv not configured")
    def test_present_dependency_proof(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--check", "--require-opensubdiv"],
            cwd=ROOT, env=os.environ.copy(), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["output_writers_executed_and_parsed"])
        self.assertTrue(report["output_visible_evidence_complete"])
        self.assertTrue(report["output_contract_repair_complete"])
        self.assertEqual(report["energy_force_csv_energy_channel_count"], 10)
        self.assertEqual(report["energy_force_csv_omitted_global_channels"], [])
        self.assertEqual(report["element_face_energy_csv_header_width"], 11)
        self.assertEqual(report["element_face_energy_csv_data_row_width"], 11)
        self.assertEqual(report["checkpoint_format"], "SLIMED_RESTART_V2")
        self.assertTrue(report["checkpoint_v1_loader_compatible"])
        self.assertEqual(report["checkpoint_force_state_group_count"], 24)
        self.assertEqual(
            len(report["checkpoint_preservation_max_abs_differences"]), 29
        )
        self.assertTrue(all(
            difference == 0.0
            for difference in report[
                "checkpoint_preservation_max_abs_differences"
            ].values()
        ))
        self.assertEqual(report["checkpoint_total_force_roundtrip_max_abs_difference"], 0.0)
        self.assertEqual(report["checkpoint_record_energy_roundtrip_max_abs_difference"], 0.0)
        self.assertEqual(
            report["energy_force_csv_max_abs_serialization_difference"],
            0.0,
        )
        self.assertEqual(
            report["element_face_energy_csv_max_abs_serialization_difference"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
