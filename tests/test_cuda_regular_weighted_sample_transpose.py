import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_cuda_regular_weighted_sample_transpose.py"
CUDA_SOURCE_PATH = ROOT / "experiments" / "cuda_regular_weighted_sample_transpose.cu"
EVIDENCE_PATH = ROOT / "docs" / "cuda_regular_weighted_sample_transpose.md"
SPEC = importlib.util.spec_from_file_location(
    "run_cuda_regular_weighted_sample_transpose", RUNNER_PATH
)
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class CudaRegularWeightedSampleTransposeTest(unittest.TestCase):
    def test_source_binds_production_rows_and_frozen_dimensions(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("get_gauss_quadrature_weight_VWU(2", source)
        self.assertIn("get_shapefunction_vector(vwu, shapeFunctions)", source)
        self.assertIn("constexpr int kSamples = 3;", source)
        self.assertIn("constexpr int kRows = 7;", source)
        self.assertIn("constexpr int kControls = 12;", source)
        self.assertIn("constexpr int kAxes = 3;", source)

    def test_transpose_is_one_writer_explicit_order_without_atomics(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("__global__ void transpose_weighted_samples", source)
        self.assertIn("for (int sample = 0; sample < kSamples; ++sample)", source)
        self.assertIn("for (int row = 0; row < kRows; ++row)", source)
        self.assertNotIn("atomicAdd", source)
        self.assertIn("constexpr double kAbsoluteTolerance = 1.0e-12;", source)
        self.assertIn("constexpr long double kAdjointTolerance = 1.0e-12L;", source)

    def test_adjoint_permutation_and_determinism_gates_are_executable(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("constexpr int kDeterminismRepetitions = 20;", source)
        self.assertIn("kPermutation[kControls]", source)
        self.assertIn("std::memcmp", source)
        self.assertIn("AdjointCheck adjoint_check", source)
        self.assertIn("maximumCpuAdjointResidual <= kAdjointTolerance", source)
        self.assertIn("maximumCudaAdjointResidual <= kAdjointTolerance", source)
        self.assertIn("host_mapping_contract_not_in_device_kernel", source)

    def test_literal_sentinel_checks_flattened_forward_and_transpose_indices(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("weights[251] = 2.0;", source)
        self.assertIn("controls[35] = 3.0;", source)
        self.assertIn("rowGradients[62] = 5.0;", source)
        self.assertIn("index == 62 ? 6.0 : 0.0", source)
        self.assertIn("index == 35 ? 10.0 : 0.0", source)
        self.assertIn("validate_index_sentinel();", source)

    def test_runner_build_is_native_opt_in_and_does_not_use_make(self):
        command = runner.build_command(
            ROOT,
            "/usr/local/cuda/bin/nvcc",
            Path("/tmp/proof"),
            "compute_89",
            "sm_89",
            "/usr/bin/g++",
        )

        self.assertIn("-arch=compute_89", command)
        self.assertIn("-code=sm_89", command)
        self.assertIn("-ccbin=/usr/bin/g++", command)
        self.assertIn(str(ROOT / runner.CUDA_SOURCE), command)
        self.assertIn(str(ROOT / runner.GAUSS_SOURCE), command)
        self.assertIn(str(ROOT / runner.LINALG_SOURCE), command)
        self.assertNotIn("make", command)

    def test_missing_nvcc_is_explicit_successful_skip_by_default(self):
        output = io.StringIO()
        with mock.patch.object(runner.common, "detect_nvcc", return_value=None):
            with contextlib.redirect_stdout(output):
                status = runner.main([])

        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "skipped")
        self.assertEqual(report["proof"], "regular_weighted_sample_transpose")
        self.assertIn("nvcc not found", report["reason"])
        self.assertFalse(report["cuda_required"])

    def test_missing_nvcc_fails_require_cuda_mode_with_exit_77(self):
        output = io.StringIO()
        with mock.patch.object(runner.common, "detect_nvcc", return_value=None):
            with contextlib.redirect_stdout(output):
                status = runner.main(["--require-cuda"])

        report = json.loads(output.getvalue())
        self.assertEqual(status, runner.NO_CUDA_DEVICE_EXIT_CODE)
        self.assertTrue(report["cuda_required"])

    def test_nonpositive_batch_size_is_rejected_before_build(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main(["--batch-size", "0"])

    def test_runner_reports_complete_compiler_and_openmp_metadata(self):
        source = RUNNER_PATH.read_text(encoding="utf-8")

        self.assertIn('report["environment"]["cuda_compiler_version"]', source)
        self.assertIn('report["environment"]["cuda_compiler_flags"]', source)
        self.assertIn('report["environment"]["host_cxx_version"]', source)
        self.assertIn('report["environment"]["host_cxx_flags"]', source)
        self.assertIn("not used in Step 3 serial CPU reference", source)
        metadata = runner.common.cpu_metadata()
        self.assertIn("openmp_binding", metadata)

    def test_evidence_limits_scope_and_records_observed_result(self):
        evidence = EVIDENCE_PATH.read_text(encoding="utf-8")
        normalized = " ".join(evidence.split())

        self.assertIn("standalone, opt-in", normalized)
        self.assertIn("does not alter a Make target", normalized)
        self.assertIn("5.329070518200751e-15", evidence)
        self.assertIn("20/20", evidence)
        self.assertIn("production routing remains disabled", normalized)


if __name__ == "__main__":
    unittest.main()
