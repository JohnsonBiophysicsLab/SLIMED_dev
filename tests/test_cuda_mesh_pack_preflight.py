import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "scripts" / "inventory_cuda_mesh_pack_preflight.py"
SPEC = importlib.util.spec_from_file_location(
    "inventory_cuda_mesh_pack_preflight", INVENTORY_PATH
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class CudaMeshPackPreflightInventoryTest(unittest.TestCase):
    def test_inventory_protects_contract_and_scope(self):
        result = inventory.report(ROOT)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["forbidden"], [])
        self.assertEqual(
            {item["category"] for item in result["located"]},
            {"api", "pack", "preflight", "overflow", "test", "scope", "review"},
        )

    def test_packer_has_no_cuda_api_or_scientific_allocation(self):
        text = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                Path("include/cuda/Cuda_mesh_pack.hpp"),
                Path("src/cuda/Cuda_mesh_pack.cpp"),
            )
        )
        for token in inventory.FORBIDDEN_PACK_TOKENS:
            self.assertNotIn(token, text)

    def test_production_routes_do_not_reference_step_2_api(self):
        for relative in inventory.PRODUCTION_SOURCES:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("Cuda_mesh_pack", text)
            self.assertNotIn("evaluate_cuda_eligibility", text)
            self.assertNotIn("build_regular_mesh_pack", text)


if __name__ == "__main__":
    unittest.main()
