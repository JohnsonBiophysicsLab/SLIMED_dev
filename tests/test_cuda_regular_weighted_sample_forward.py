import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_cuda_regular_weighted_sample_forward.py"
CUDA_SOURCE_PATH = ROOT / "experiments" / "cuda_regular_weighted_sample_forward.cu"
EVIDENCE_PATH = ROOT / "docs" / "cuda_regular_weighted_sample_forward.md"
SPEC = importlib.util.spec_from_file_location(
    "run_cuda_regular_weighted_sample_forward", RUNNER_PATH
)
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class CudaRegularWeightedSampleForwardTest(unittest.TestCase):
    def test_cuda_source_uses_production_shape_rows_and_frozen_dimensions(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("get_gauss_quadrature_weight_VWU(2", source)
        self.assertIn("get_shapefunction_vector(vwu, shapeFunctions)", source)
        self.assertIn("constexpr int kSamples = 3;", source)
        self.assertIn("constexpr int kRows = 7;", source)
        self.assertIn("constexpr int kControls = 12;", source)
        self.assertIn("constexpr int kAxes = 3;", source)

    def test_cpu_and_cuda_use_explicit_control_order_without_atomics(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertGreaterEqual(
            source.count("for (int control = 0; control < kControls; ++control)"),
            2,
        )
        self.assertIn("__global__ void forward_weighted_samples", source)
        self.assertNotIn("atomicAdd", source)
        self.assertIn("constexpr double kAbsoluteTolerance = 1.0e-12;", source)
        self.assertIn("max_relative_delta_diagnostic", source)

    def test_runner_build_is_native_opt_in_and_does_not_use_make(self):
        command = runner.build_command(
            ROOT,
            "/usr/local/cuda/bin/nvcc",
            Path("/tmp/proof"),
            "compute_89",
            "sm_89",
        )

        self.assertIn("-arch=compute_89", command)
        self.assertIn("-code=sm_89", command)
        self.assertIn(str(ROOT / runner.CUDA_SOURCE), command)
        self.assertIn(str(ROOT / runner.GAUSS_SOURCE), command)
        self.assertIn(str(ROOT / runner.LINALG_SOURCE), command)
        self.assertNotIn("make", command)

    def test_missing_nvcc_is_explicit_successful_skip_by_default(self):
        output = io.StringIO()
        with mock.patch.object(runner, "detect_nvcc", return_value=None):
            with contextlib.redirect_stdout(output):
                status = runner.main([])

        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "skipped")
        self.assertIn("nvcc not found", report["reason"])
        self.assertFalse(report["cuda_required"])

    def test_missing_nvcc_fails_require_cuda_mode_with_exit_77(self):
        output = io.StringIO()
        with mock.patch.object(runner, "detect_nvcc", return_value=None):
            with contextlib.redirect_stdout(output):
                status = runner.main(["--require-cuda"])

        report = json.loads(output.getvalue())
        self.assertEqual(status, runner.NO_CUDA_DEVICE_EXIT_CODE)
        self.assertEqual(report["status"], "skipped")
        self.assertTrue(report["cuda_required"])

    def test_nonpositive_batch_size_is_rejected_before_build(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main(["--batch-size", "0"])

    def test_environment_metadata_never_omits_unavailable_power_fields(self):
        metadata = runner.cpu_metadata()

        self.assertIn("host_cpu_model", metadata)
        self.assertIn("physical_cores", metadata)
        self.assertIn("logical_cpus", metadata)
        self.assertIn("host_power_mode", metadata)
        self.assertIn("ac_battery_state", metadata)
        self.assertIn("gpu_power_state", metadata)
        self.assertIn("openmp_observed_threads", metadata)

    def test_evidence_limits_scope_and_records_observed_cuda_result(self):
        evidence = EVIDENCE_PATH.read_text(encoding="utf-8")

        self.assertIn("standalone,\nopt-in correctness proof", evidence)
        self.assertIn("not change a Make target", evidence)
        self.assertIn("-arch=compute_89 -code=sm_89", evidence)
        self.assertIn("3.552713678800501e-15", evidence)
        self.assertIn("transpose, adjoint identity, control-order permutation", evidence)


if __name__ == "__main__":
    unittest.main()
