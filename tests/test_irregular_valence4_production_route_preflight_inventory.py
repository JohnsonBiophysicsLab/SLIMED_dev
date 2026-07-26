import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_production_route_preflight.py"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_production_route_preflight",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourProductionRoutePreflightInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_inert_production_scope(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["production_route_preflight_helper_executed"])
        self.assertTrue(report["explicit_route_request_boundary"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertTrue(report["backend_neutral_opensubdiv_free"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_explicit_route_request_boundary_is_default_off(self):
        report = load_inventory_module().collect(ROOT)
        self.assertTrue(report["default_off_request_rejected"])
        self.assertTrue(report["explicit_request_source_keyed_accumulation"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_face_loop_executed"])

    def test_preflight_has_no_default_evaluator_caller(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["default_evaluator_callers"], [])
        self.assertFalse(
            report["default_evaluator_or_route_surfaces_changed"]
        )
        self.assertFalse(report["production_one_ring_mutation"])
        self.assertFalse(report["production_force_path_called"])

    def test_allowed_path_boundary(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(
            sorted(report["changed_paths"]),
            [
                "docs/irregular_valence4_production_route_preflight.md",
                "docs/opensubdiv_routing_readiness_map.md",
                "include/energy_force/Valence4_face_loop_route_preflight.hpp",
                "scripts/inventory_irregular_valence4_production_route_preflight.py",
                "src/energy_force/Valence4_face_loop_route_preflight.cpp",
                "tests/test_irregular_valence4_production_route_preflight_inventory.py",
                "tests/test_valence4_face_loop_route_preflight.cpp",
            ],
        )


if __name__ == "__main__":
    unittest.main()
