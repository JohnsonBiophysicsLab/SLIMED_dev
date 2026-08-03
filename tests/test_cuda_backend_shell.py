import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_cuda_backend_report.py"
INVENTORY_PATH = ROOT / "scripts" / "inventory_cuda_backend_shell.py"

RUNNER_SPEC = importlib.util.spec_from_file_location(
    "run_cuda_backend_report", RUNNER_PATH
)
runner = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = runner
RUNNER_SPEC.loader.exec_module(runner)

INVENTORY_SPEC = importlib.util.spec_from_file_location(
    "inventory_cuda_backend_shell", INVENTORY_PATH
)
inventory = importlib.util.module_from_spec(INVENTORY_SPEC)
sys.modules[INVENTORY_SPEC.name] = inventory
INVENTORY_SPEC.loader.exec_module(inventory)


class CudaBackendShellTest(unittest.TestCase):
    def test_inventory_protects_scope_and_ownership_contracts(self):
        result = inventory.report(ROOT)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["forbidden"], [])
        self.assertEqual(
            {item["category"] for item in result["located"]},
            {
                "api",
                "stub",
                "cuda",
                "build",
                "runner",
                "evidence",
                "scope",
                "review",
            },
        )

    def test_committed_native_report_records_complete_context_lifetimes(self):
        report = json.loads(
            (ROOT / "analysis/cuda_backend_report_rtx4050.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(report["status"], "available")
        self.assertTrue(report["compiled"])
        self.assertTrue(report["available"])
        self.assertEqual(report["requested_context_lifecycle_iterations"], 20)
        self.assertEqual(report["completed_context_lifecycle_iterations"], 20)
        self.assertEqual(report["device"]["compute_capability_major"], 8)
        self.assertEqual(report["device"]["compute_capability_minor"], 9)
        self.assertTrue(report["device"]["primary_context_retained"])
        self.assertTrue(report["device"]["nonblocking_stream_owned"])
        self.assertEqual(report["error"]["code"], "none")
        self.assertEqual(
            report["provenance"]["base_sha"],
            "0b2b6dd425cb47e703c02dce0d32f89e23721b0d",
        )
        self.assertEqual(
            report["provenance"]["tested_implementation_sha"],
            "07d3aaebb0a714ed8be46a0bd78d306308cf720a",
        )

    def test_public_header_contains_no_cuda_types_or_headers(self):
        header = (ROOT / "include/cuda/Cuda_backend.hpp").read_text(
            encoding="utf-8"
        )

        for token in inventory.FORBIDDEN_PUBLIC_HEADER_TOKENS:
            self.assertNotIn(token, header)

    def test_cuda_shell_has_no_kernel_or_scientific_allocation(self):
        source = (ROOT / "src/cuda/Cuda_backend.cu").read_text(encoding="utf-8")

        for token in inventory.FORBIDDEN_CUDA_IMPLEMENTATION_TOKENS:
            self.assertNotIn(token, source)

    def test_build_commands_select_only_explicit_report_target(self):
        cuda_command = runner.build_command(
            "/usr/bin/make",
            stub=False,
            nvcc="/usr/local/cuda/bin/nvcc",
            host_cxx="/usr/bin/g++",
            compute_arch="compute_89",
            sm_code="sm_89",
        )
        stub_command = runner.build_command(
            "/usr/bin/make",
            stub=True,
            nvcc=None,
            host_cxx="/usr/bin/g++",
            compute_arch="compute_89",
            sm_code="sm_89",
        )

        self.assertEqual(cuda_command[1], "cuda_backend_report")
        self.assertIn("CUDA_NVCC=/usr/local/cuda/bin/nvcc", cuda_command)
        self.assertIn("CUDA_COMPUTE_ARCH=compute_89", cuda_command)
        self.assertIn("CUDA_SM_CODE=sm_89", cuda_command)
        self.assertEqual(
            stub_command,
            ["/usr/bin/make", "cuda_backend_stub_report", "CXX=/usr/bin/g++"],
        )

    def test_missing_nvcc_is_successful_skip_by_default(self):
        output = io.StringIO()
        with mock.patch.object(
            runner, "detect_executable", side_effect=["/usr/bin/make", "/usr/bin/g++", None]
        ):
            with contextlib.redirect_stdout(output):
                status = runner.main([])

        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "skipped")
        self.assertFalse(report["compiled"])
        self.assertFalse(report["cuda_required"])

    def test_missing_nvcc_is_exit_77_when_required(self):
        output = io.StringIO()
        with mock.patch.object(
            runner, "detect_executable", side_effect=["/usr/bin/make", "/usr/bin/g++", None]
        ):
            with contextlib.redirect_stdout(output):
                status = runner.main(["--require-cuda"])

        report = json.loads(output.getvalue())
        self.assertEqual(status, runner.NO_CUDA_EXIT_CODE)
        self.assertTrue(report["cuda_required"])

    def test_report_parser_uses_last_nonempty_json_line(self):
        report = runner.parse_report('build output\n{"available": true}\n')

        self.assertTrue(report["available"])

    def test_invalid_cli_cardinality_is_rejected_before_build(self):
        for arguments in (["--device", "-1"], ["--lifecycle-iterations", "0"]):
            with self.subTest(arguments=arguments):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        runner.main(arguments)

    def test_stub_and_require_cuda_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main(["--stub", "--require-cuda"])


if __name__ == "__main__":
    unittest.main()
