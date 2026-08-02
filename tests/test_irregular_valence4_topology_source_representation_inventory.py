import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_topology_source_representation.py"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_topology_source_representation",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourTopologySourceRepresentationInventoryTest(
    unittest.TestCase
):
    def test_inventory_passes_and_scope_is_guarded(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["guarded_production_representation"])
        self.assertTrue(report["backend_neutral"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_representation_is_not_called_by_production_paths(self):
        report = load_inventory_module().collect(ROOT)
        self.assertFalse(report["route_installed_in_production"])
        self.assertFalse(report["production_callers_changed"])

    def test_fixture_files_and_default_build_policy_are_unchanged(self):
        report = load_inventory_module().collect(ROOT)
        self.assertFalse(report["fixture_csvs_changed"])
        changed = set(report["changed_paths"])
        self.assertIn("Makefile", changed)
        self.assertTrue(
            load_inventory_module().phase1_makefile_change_is_exact_and_guarded(ROOT)
        )
        self.assertNotIn("scripts/verify_pr_ready.sh", changed)
        self.assertNotIn("include/mesh/Mesh.hpp", changed)
        self.assertNotIn("include/mesh/Face.hpp", changed)


if __name__ == "__main__":
    unittest.main()
