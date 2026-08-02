import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_cuda_regular_weighted_sample_benchmark.py"
CUDA_SOURCE_PATH = ROOT / "experiments" / "cuda_regular_weighted_sample_benchmark.cu"
EVIDENCE_PATH = ROOT / "analysis" / "cuda_regular_weighted_sample_benchmark_rtx4050.json"
DOCUMENT_PATH = ROOT / "docs" / "cuda_regular_weighted_sample_benchmark.md"
SPEC = importlib.util.spec_from_file_location(
    "run_cuda_regular_weighted_sample_benchmark", RUNNER_PATH
)
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class CudaRegularWeightedSampleBenchmarkTest(unittest.TestCase):
    def test_source_times_all_required_comparators(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("evaluate_serial", source)
        self.assertIn("evaluate_openmp", source)
        self.assertIn("measure_cuda_events", source)
        self.assertIn('print_distribution("host_to_device"', source)
        self.assertIn('print_distribution("device_to_host"', source)
        self.assertIn('print_distribution("cuda_end_to_end"', source)
        self.assertIn("std::chrono::steady_clock", source)
        self.assertIn("cudaEventElapsedTime", source)

    def test_source_enforces_correctness_repetitions_and_memory_budget(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("constexpr double kAbsoluteTolerance = 1.0e-12;", source)
        self.assertIn("benchmark correctness prerequisite failed", source)
        self.assertIn('parse_positive_int(argv[3], "repetitions", 30)', source)
        self.assertIn("requiredBytes > freeDeviceBytes / 2", source)
        self.assertIn("std::size_t checked_multiply", source)
        self.assertIn("std::size_t checked_add", source)
        self.assertIn("validate_batch_cardinality(batchSize)", source)
        self.assertIn("batch size exceeds OpenMP loop range", source)
        self.assertIn("break_even_vs_serial_batch", source)
        self.assertIn("break_even_vs_openmp_batch", source)

    def test_openmp_comparator_has_explicit_static_binding_contract(self):
        source = CUDA_SOURCE_PATH.read_text(encoding="utf-8")
        runner_source = RUNNER_PATH.read_text(encoding="utf-8")

        self.assertIn("#pragma omp parallel for schedule(static)", source)
        self.assertIn("omp_get_num_threads", source)
        self.assertIn('"OMP_DYNAMIC": "FALSE"', runner_source)
        self.assertIn('"OMP_PROC_BIND": "TRUE"', runner_source)
        self.assertIn('"OMP_PLACES": "cores"', runner_source)

    def test_runner_build_is_native_openmp_opt_in_and_not_make(self):
        command = runner.build_command(
            ROOT,
            "/usr/local/cuda/bin/nvcc",
            Path("/tmp/benchmark"),
            "compute_89",
            "sm_89",
            "/usr/bin/g++",
        )

        self.assertIn("-arch=compute_89", command)
        self.assertIn("-code=sm_89", command)
        self.assertIn("-Xcompiler=-fopenmp", command)
        self.assertIn("-lgomp", command)
        self.assertNotIn("make", command)

    def test_default_batch_sweep_is_logarithmic_and_has_large_safe_case(self):
        values = runner.parse_batch_sizes(runner.DEFAULT_BATCH_SIZES)

        self.assertEqual(values[0], 1)
        self.assertEqual(values[-1], 1048576)
        self.assertGreaterEqual(len(values), 8)
        self.assertTrue(all(right > left for left, right in zip(values, values[1:])))

    def test_batch_parser_rejects_nonpositive_duplicate_and_reordered_values(self):
        for value in ("0,1", "1,1", "16,1", "one,2"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    runner.parse_batch_sizes(value)

    def test_oversized_batch_is_rejected_before_allocation_or_build(self):
        exploit = "10248191152060862009"

        with self.assertRaisesRegex(Exception, "exceeds checked maximum"):
            runner.parse_batch_sizes(exploit)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main(["--batch-sizes", exploit])

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

    def test_missing_nvcc_is_explicit_successful_skip_by_default(self):
        output = io.StringIO()
        with mock.patch.object(runner.common, "detect_nvcc", return_value=None):
            with contextlib.redirect_stdout(output):
                status = runner.main([])

        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "skipped")
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

    def test_machine_readable_evidence_is_complete_and_conservative(self):
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(
            evidence["provenance"]["runner"],
            "scripts/run_cuda_regular_weighted_sample_benchmark.py",
        )
        self.assertEqual(evidence["method"]["warmups"], 5)
        self.assertEqual(evidence["method"]["repetitions"], 30)
        self.assertEqual(evidence["method"]["openmp_threads_observed"], 8)
        self.assertEqual(len(evidence["cases"]), 8)
        self.assertEqual(
            evidence["break_even"]["transfer_inclusive_vs_serial_batch"], 4096
        )
        self.assertIsNone(
            evidence["break_even"]["transfer_inclusive_vs_openmp_batch"]
        )
        self.assertEqual(
            evidence["recommendation"]["production_integration"],
            "not_supported_without_better_transfer_amortization",
        )
        for case in evidence["cases"]:
            for metric in (
                "serial_cpu_ms",
                "openmp_cpu_ms",
                "cuda_kernel_ms",
                "host_to_device_ms",
                "device_to_host_ms",
                "cuda_end_to_end_ms",
            ):
                self.assertIn("median", case[metric])
                self.assertIn("p95", case[metric])

    def test_document_records_limits_and_no_openmp_break_even(self):
        document = " ".join(DOCUMENT_PATH.read_text(encoding="utf-8").split())

        self.assertIn("No transfer-inclusive break-even against OpenMP", document)
        self.assertIn("does not support production CUDA integration", document)
        self.assertIn("thermal/clock throttling telemetry were unavailable", document)
        self.assertIn("five warm-ups and 30 measured repetitions", document)


if __name__ == "__main__":
    unittest.main()
