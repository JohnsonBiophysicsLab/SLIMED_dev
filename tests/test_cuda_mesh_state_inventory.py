import importlib.util
import json
from pathlib import Path
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
        ):
            self.assertIn(anchor, public)
        self.assertIn("DeviceOperations", (ROOT / "include/cuda/detail/Cuda_mesh_state_core.hpp").read_text())
        self.assertIn("MemoryBudgetExceeded", core)
        self.assertIn("topology replacement requires fresh dependent generations", core)

    def test_step_is_storage_only_and_not_production_routed(self):
        paths = [
            ROOT / "include/cuda/Cuda_mesh_state.hpp",
            ROOT / "src/cuda/Cuda_mesh_state_common.cpp",
            ROOT / "src/cuda/Cuda_mesh_state.cu",
        ]
        text = "\n".join(path.read_text() for path in paths)
        self.assertNotIn("__global__", text)
        self.assertNotIn("Compute_energy_and_force", text)
        self.assertNotIn("#include \"mesh/", text)

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

    def test_committed_rtx_evidence_meets_exit_gate(self):
        evidence = json.loads(
            (ROOT / "analysis/cuda_mesh_state_report_rtx4050.json").read_text()
        )
        self.assertEqual(evidence["status"], "pass")
        self.assertTrue(evidence["compiled"])
        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["iterations"], 20)
        self.assertTrue(evidence["no_warm_allocations"])
        self.assertTrue(evidence["transfers_complete"])
        self.assertEqual(evidence["gpu"]["name"], "NVIDIA GeForce RTX 4050 Laptop GPU")


if __name__ == "__main__":
    unittest.main()
