import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_cuda_regular_face_adapter.py"
CUDA_SOURCE_PATH = ROOT / "experiments" / "cuda_regular_face_adapter.cu"
EVIDENCE_PATH = ROOT / "analysis" / "cuda_regular_face_adapter_rtx4050.json"
DOCUMENT_PATH = ROOT / "docs" / "cuda_regular_face_adapter.md"
SPEC = importlib.util.spec_from_file_location("run_cuda_regular_face_adapter", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class CudaRegularFaceAdapterTest(unittest.TestCase):
    def test_source_reuses_proven_kernels_and_stages_actual_regular_rows(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn('#include "cuda_regular_weighted_sample_benchmark.cu"', source)
        self.assertIn("production_regular_weights()", source)
        self.assertIn("regular_face_controls", source)
        self.assertIn("source ids 9,15,10,16,22,11,17,23,29,18,24,30", source)
        self.assertIn("Mesh::element_energy_force_regular", source)
        self.assertIn("production_formula_dry_run", source)

    def test_source_models_resident_state_and_transfer_amortization(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("advance_resident_state", source)
        self.assertIn("launch_resident_iteration", source)
        self.assertIn("cudaResidentKernel", source)
        self.assertIn("cudaResidentEndToEnd", source)
        self.assertIn("device_local_deterministic_update_surrogate", source)
        self.assertIn("upper_bound_not_a_production_integrator", source)

    def test_source_freezes_correctness_and_readiness_boundaries(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("kAbsoluteTolerance", source)
        self.assertIn("resident adapter correctness prerequisite failed", source)
        self.assertIn("proof_local_raii_device_buffers", source)
        self.assertIn("cuda_absence_is_machine_readable_skip", source)
        self.assertIn("full_gpu_force_formula", source)
        self.assertIn("scatter_and_reduction", source)
        self.assertIn("not_ready_without_end_to_end_device_resident_pipeline", source)

    def test_runner_is_opt_in_native_cuda_and_does_not_change_make(self):
        command = runner.build_command(
            ROOT,
            "/usr/local/cuda/bin/nvcc",
            Path("/tmp/cuda-adapter"),
            "compute_89",
            "sm_89",
            "/usr/bin/g++",
        )

        self.assertIn("-arch=compute_89", command)
        self.assertIn("-code=sm_89", command)
        self.assertIn("-Xcompiler=-fopenmp", command)
        self.assertIn(str(ROOT / "src" / "energy_force" / "Compute_energy_and_force_on_mesh.cpp"), command)
        self.assertNotIn("make", command)

    def test_parsers_reject_invalid_or_unbounded_sweeps(self):
        for parser, value in (
            (runner.parse_batch_sizes, "0,1"),
            (runner.parse_batch_sizes, "2,1"),
            (runner.parse_batch_sizes, "1,1"),
            (runner.parse_resident_iterations, "0,1"),
            (runner.parse_resident_iterations, "4,1"),
            (runner.parse_resident_iterations, "1,1000001"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    parser(value)

    def test_missing_nvcc_is_machine_readable_optional_skip(self):
        output = io.StringIO()
        with mock.patch.object(runner.common, "detect_nvcc", return_value=None):
            with contextlib.redirect_stdout(output):
                status = runner.main([])

        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "skipped")
        self.assertFalse(report["cuda_required"])

    def test_require_cuda_preserves_exit_77(self):
        output = io.StringIO()
        with mock.patch.object(runner.common, "detect_nvcc", return_value=None):
            with contextlib.redirect_stdout(output):
                status = runner.main(["--require-cuda"])

        report = json.loads(output.getvalue())
        self.assertEqual(status, runner.NO_CUDA_DEVICE_EXIT_CODE)
        self.assertTrue(report["cuda_required"])

    def test_runner_rejects_underpowered_measurement_counts(self):
        for arguments in (
            ["--warmups", "0"],
            ["--repetitions", "29"],
            ["--omp-threads", "0"],
        ):
            with self.subTest(arguments=arguments):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        runner.main(arguments)

    def test_evidence_is_correct_and_conservative(self):
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["experiment"], "regular_face_cuda_residency_adapter")
        self.assertIn(
            "Mesh::element_energy_force_regular",
            evidence["adapter_output_comparison"],
        )
        self.assertTrue(evidence["production_formula_dry_run"]["finite"])
        self.assertTrue(evidence["production_formula_dry_run"]["nonzero"])
        self.assertEqual(evidence["warmups"], 5)
        self.assertEqual(evidence["repetitions"], 30)
        self.assertEqual(evidence["openmp_observed_threads"], 8)
        self.assertEqual(len(evidence["cases"]), 8)
        self.assertEqual(
            evidence["recommendation"]["production_integration"],
            "not_ready_without_end_to_end_device_resident_pipeline",
        )
        for case in evidence["cases"]:
            self.assertLessEqual(case["correctness_forward_max_abs"], 1.0e-12)
            self.assertLessEqual(case["correctness_transpose_max_abs"], 1.0e-12)
            for metric in (
                "serial_cpu",
                "openmp_cpu",
                "cuda_resident_kernel",
                "cuda_resident_end_to_end",
            ):
                self.assertIn("median_ms", case[metric])
                self.assertIn("p95_ms", case[metric])

    def test_document_records_scope_and_all_readiness_dimensions(self):
        document = " ".join(DOCUMENT_PATH.read_text(encoding="utf-8").split())

        self.assertIn("does not enable production CUDA routing", document)
        self.assertIn("device-resident producer surrogate", document)
        self.assertIn("Memory ownership", document)
        self.assertIn("Fallback and error handling", document)
        self.assertIn("Scatter and reduction", document)
        self.assertIn("not ready for production integration", document)


if __name__ == "__main__":
    unittest.main()
