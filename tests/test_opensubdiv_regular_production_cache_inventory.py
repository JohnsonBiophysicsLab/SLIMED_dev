import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_opensubdiv_regular_production_cache.py"
SPEC = importlib.util.spec_from_file_location(
    "inventory_opensubdiv_regular_production_cache", SCRIPT
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class OpenSubdivRegularProductionCacheInventoryTest(unittest.TestCase):
    def test_all_contract_anchors_are_present(self):
        result = inventory.payload()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["located"]), len(inventory.ANCHORS))
        self.assertFalse(result["missing"])

    def test_default_surfaces_do_not_gain_cache_dependency(self):
        result = inventory.payload()
        self.assertFalse(result["default_surface_leaks"])
        self.assertFalse(result["backend_header_leaks"])
        self.assertFalse(result["default_opensubdiv_dependency"])

    def test_scope_keeps_broader_changes_out(self):
        result = inventory.payload()
        self.assertTrue(result["production_cache_implemented"])
        self.assertFalse(result["broader_valence_in_scope"])
        self.assertFalse(result["formula_or_scatter_change"])
        self.assertFalse(result["openmp_reduction_change"])

    def test_exact_identity_excludes_vertex_coordinates(self):
        source = (ROOT / inventory.EVALUATOR).read_text(encoding="utf-8")
        fingerprint = source[
            source.index("regular_limit_surface_cache_key"):
            source.index("struct RefinerDeleter")
        ]
        self.assertNotIn("vertex.coord", fingerprint)
        for needle in (
            "face.adjacentVertices",
            "face.oneRingVertices",
            "mesh.param.VWU",
            "mesh.param.gaussQuadratureCoeff",
            "mesh.param.shapeFunctions",
            "OPENSUBDIV_VERSION_NUMBER",
            "VTX_BOUNDARY_EDGE_ONLY",
        ):
            self.assertIn(needle, fingerprint)

    def test_hash_is_only_a_prefilter_for_exact_identity(self):
        source = (ROOT / inventory.EVALUATOR).read_text(encoding="utf-8")
        self.assertIn("cache.fingerprint_ == requestedKey.fingerprint", source)
        self.assertIn("cache.identity_ == requestedKey.identity", source)


if __name__ == "__main__":
    unittest.main()
