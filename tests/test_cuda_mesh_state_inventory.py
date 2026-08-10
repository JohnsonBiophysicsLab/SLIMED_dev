import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CudaMeshStateInventoryTest(unittest.TestCase):
    def test_public_contract_and_core_have_required_anchors(self):
        public = (ROOT / "include/cuda/Cuda_mesh_state.hpp").read_text()
        core = (ROOT / "src/cuda/Cuda_mesh_state_common.cpp").read_text()
        for anchor in (
            "TransactionPhase",
            "CandidatePrepared",
            "TransferReason",
            "allocationEpoch",
            "acceptedCoordinateSlot",
            "prepare_candidate",
            "commit()",
            "rollback()",
            "GeometryCandidateResult",
            "compute_candidate_geometry",
            "MembraneCandidateResult",
            "compute_candidate_membrane",
        ):
            self.assertIn(anchor, public)
        self.assertIn("DeviceOperations", (ROOT / "include/cuda/detail/Cuda_mesh_state_core.hpp").read_text())
        self.assertIn("MemoryBudgetExceeded", core)
        self.assertIn("topology replacement requires fresh dependent generations", core)

    def test_step_contains_membrane_formula_but_is_not_production_routed(self):
        paths = [
            ROOT / "include/cuda/Cuda_mesh_state.hpp",
            ROOT / "include/cuda/detail/Cuda_regular_geometry_cpu.hpp",
            ROOT / "src/cuda/Cuda_regular_geometry_cpu.cpp",
            ROOT / "src/cuda/Cuda_mesh_state_common.cpp",
            ROOT / "src/cuda/Cuda_mesh_state.cu",
        ]
        text = "\n".join(path.read_text() for path in paths)
        self.assertIn("regular_geometry_kernel", text)
        self.assertIn("deterministic_geometry_reduction_kernel", text)
        self.assertIn("regular_membrane_kernel", text)
        self.assertIn("deterministic_membrane_reduction_kernel", text)
        self.assertIn("occurrenceForces", text)
        self.assertNotIn("Compute_energy_and_force", text)
        self.assertNotIn("#include \"mesh/", text)
        self.assertNotIn("forceTotal", text)

    def test_make_targets_are_explicit_and_mutually_exclusive(self):
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("cuda_mesh_state_report:", makefile)
        self.assertIn("cuda_mesh_state_stub_report:", makefile)
        native_rule = makefile.split("cuda_mesh_state_report:", 1)[1].split(
            "cuda_mesh_state_stub_report:", 1
        )[0]
        self.assertIn("Cuda_mesh_state.cu", native_rule)
        self.assertNotIn("Cuda_mesh_state_stub.cpp", native_rule)

    def test_runner_commands_select_only_requested_backend(self):
        path = ROOT / "scripts/run_cuda_mesh_state_report.py"
        spec = importlib.util.spec_from_file_location("mesh_state_runner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        native = module.build_command(
            "make",
            stub=False,
            nvcc="nvcc",
            host_cxx="g++",
            compute_arch="compute_89",
            sm_code="sm_89",
        )
        stub = module.build_command(
            "make",
            stub=True,
            nvcc=None,
            host_cxx="g++",
            compute_arch="compute_89",
            sm_code="sm_89",
        )
        self.assertEqual(native[1], "cuda_mesh_state_report")
        self.assertEqual(stub[1], "cuda_mesh_state_stub_report")

    def test_runner_rejects_false_green_teardown(self):
        path = ROOT / "scripts/run_cuda_mesh_state_report.py"
        spec = importlib.util.spec_from_file_location("mesh_state_runner_teardown", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        complete = {
            "closed": True,
            "cleanup_pending": False,
            "cleanup_error_code": "none",
            "final_resident_bytes": 0,
            "allocation_free_balance": True,
            "successful_frees": 19,
            "final_allocations": 19,
        }
        self.assertTrue(module.teardown_complete(complete))
        for key, invalid in (
            ("closed", False),
            ("cleanup_pending", True),
            ("cleanup_error_code", "cleanup_failed"),
            ("final_resident_bytes", 1),
            ("allocation_free_balance", False),
            ("successful_frees", 18),
        ):
            with self.subTest(key=key):
                report = complete.copy()
                report[key] = invalid
                self.assertFalse(module.teardown_complete(report))

    def test_runner_rejects_false_green_geometry(self):
        path = ROOT / "scripts/run_cuda_mesh_state_report.py"
        spec = importlib.util.spec_from_file_location("mesh_state_runner_geometry", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        complete_case = {
            "pass": True,
            "cpu_parity": True,
            "repeatable": True,
            "max_abs_error": 1.0e-12,
            "ghost_zero": True,
            "degenerate_zero": True,
            "permutation_equal": True,
        }
        complete = {
            "geometry_repeatable": True,
            "geometry_max_abs_error": 1.0e-12,
            "geometry_cases": {
                name: complete_case.copy()
                for name in module.REQUIRED_GEOMETRY_CASES
            },
        }
        self.assertTrue(module.geometry_complete(complete))
        for key, invalid in (
            ("geometry_repeatable", False),
            ("geometry_max_abs_error", 1.0001e-12),
            ("geometry_max_abs_error", "0"),
        ):
            with self.subTest(key=key, invalid=invalid):
                report = complete.copy()
                report[key] = invalid
                self.assertFalse(module.geometry_complete(report))
        for name in module.REQUIRED_GEOMETRY_CASES:
            for key, invalid in (
                ("pass", False),
                ("cpu_parity", False),
                ("repeatable", False),
                ("max_abs_error", 1.0001e-12),
                ("ghost_zero", False),
                ("degenerate_zero", False),
                ("permutation_equal", False),
            ):
                with self.subTest(case=name, key=key):
                    report = json.loads(json.dumps(complete))
                    report["geometry_cases"][name][key] = invalid
                    self.assertFalse(module.geometry_complete(report))
        missing = json.loads(json.dumps(complete))
        missing["geometry_cases"].pop("curved")
        self.assertFalse(module.geometry_complete(missing))

    def test_runner_rejects_false_green_membrane(self):
        path = ROOT / "scripts/run_cuda_mesh_state_report.py"
        spec = importlib.util.spec_from_file_location("mesh_state_runner_membrane", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        complete_case = {
            "pass": True,
            "cpu_parity": True,
            "repeatable": True,
            "structured_degeneracy": True,
            "recoverable": True,
            "permutation_equal": True,
            "max_abs_error": 1.0e-12,
        }
        complete = {
            "membrane_repeatable": True,
            "membrane_degeneracy_handled": True,
            "membrane_max_abs_error": 1.0e-12,
            "membrane_cases": {
                name: complete_case.copy()
                for name in module.REQUIRED_MEMBRANE_CASES
            },
        }
        self.assertTrue(module.membrane_complete(complete))
        for key, invalid in (
            ("membrane_repeatable", False),
            ("membrane_degeneracy_handled", False),
            ("membrane_max_abs_error", 1.0001e-12),
            ("membrane_max_abs_error", "0"),
        ):
            with self.subTest(key=key, invalid=invalid):
                report = complete.copy()
                report[key] = invalid
                self.assertFalse(module.membrane_complete(report))
        for name in module.REQUIRED_MEMBRANE_CASES:
            for key, invalid in (
                ("pass", False),
                ("cpu_parity", False),
                ("repeatable", False),
                ("structured_degeneracy", False),
                ("recoverable", False),
                ("permutation_equal", False),
                ("max_abs_error", 1.0001e-12),
            ):
                with self.subTest(case=name, key=key):
                    report = json.loads(json.dumps(complete))
                    report["membrane_cases"][name][key] = invalid
                    self.assertFalse(module.membrane_complete(report))

    def test_committed_rtx_evidence_meets_exit_gate(self):
        evidence = json.loads(
            (ROOT / "analysis/cuda_mesh_state_report_rtx4050.json").read_text()
        )
        self.assertEqual(evidence["status"], "pass")
        self.assertTrue(evidence["compiled"])
        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["iterations"], 20)
        self.assertLessEqual(evidence["geometry_max_abs_error"], 1.0e-12)
        self.assertTrue(evidence["geometry_repeatable"])
        self.assertLessEqual(evidence["membrane_max_abs_error"], 1.0e-12)
        self.assertTrue(evidence["membrane_repeatable"])
        self.assertTrue(evidence["membrane_degeneracy_handled"])
        self.assertEqual(
            set(evidence["geometry_cases"]),
            {
                "natural",
                "permuted",
                "curved",
                "boundary_ghost",
                "degenerate",
                "production_cpu",
            },
        )
        for case in evidence["geometry_cases"].values():
            self.assertTrue(case["pass"])
            self.assertTrue(case["cpu_parity"])
            self.assertTrue(case["repeatable"])
            self.assertLessEqual(case["max_abs_error"], 1.0e-12)
            self.assertTrue(case["ghost_zero"])
            self.assertTrue(case["degenerate_zero"])
            self.assertTrue(case["permutation_equal"])
        self.assertEqual(
            set(evidence["membrane_cases"]),
            {
                "natural",
                "permuted",
                "curved",
                "boundary_ghost",
                "degenerate",
                "production_cpu",
            },
        )
        for case in evidence["membrane_cases"].values():
            self.assertTrue(case["pass"])
            self.assertTrue(case["cpu_parity"])
            self.assertTrue(case["repeatable"])
            self.assertTrue(case["structured_degeneracy"])
            self.assertTrue(case["recoverable"])
            self.assertTrue(case["permutation_equal"])
            self.assertLessEqual(case["max_abs_error"], 1.0e-12)
        self.assertTrue(evidence["no_warm_allocations"])
        self.assertTrue(evidence["transfers_complete"])
        self.assertTrue(evidence["closed"])
        self.assertFalse(evidence["cleanup_pending"])
        self.assertEqual(evidence["cleanup_error_code"], "none")
        self.assertEqual(evidence["final_resident_bytes"], 0)
        self.assertTrue(evidence["allocation_free_balance"])
        self.assertEqual(
            evidence["successful_frees"], evidence["final_allocations"]
        )
        self.assertEqual(evidence["gpu"]["name"], "NVIDIA GeForce RTX 4050 Laptop GPU")

    def test_opt_in_experiment_controls_are_not_production_callers(self):
        path = ROOT / "scripts/inventory_energy_force_call_sites.py"
        spec = importlib.util.spec_from_file_location("energy_force_inventory", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        classification, _ = module.classify_direct(
            Path("experiments/irregular_valence5_option_b_phase3_activation.cpp"),
            "mesh.Compute_Energy_And_Force();",
        )
        self.assertEqual(
            classification, "intentional experiment/control direct call"
        )


if __name__ == "__main__":
    unittest.main()
