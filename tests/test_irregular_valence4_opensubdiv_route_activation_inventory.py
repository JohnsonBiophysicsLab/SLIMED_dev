import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_opensubdiv_route_activation.py"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_opensubdiv_route_activation",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourOpenSubdivRouteActivationInventoryTest(
    unittest.TestCase
):
    def test_inventory_binds_canonical_guarded_activation(self):
        report = load_inventory_module().collect(ROOT)

        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["canonical_closed_valence4_only"])
        self.assertTrue(report["build_gate_unchanged"])
        self.assertTrue(report["runtime_gate_present"])
        self.assertTrue(report["exact_runtime_gate_token"])
        self.assertTrue(report["negative_runtime_tokens_tested"])
        self.assertFalse(report["ambient_dependency_routing"])
        self.assertTrue(report["default_entry_calls_guarded_route"])
        self.assertTrue(report["atomic_dependency_rejection_tested"])
        self.assertTrue(report["atomic_topology_rejection_tested"])
        self.assertTrue(report["successful_route_parity_tested"])
        self.assertFalse(report["production_one_rings_populated"])
        self.assertFalse(report["broader_valence_routing"])
        self.assertFalse(report["production_formula_changed"])
        self.assertFalse(report["scatter_semantics_changed"])
        self.assertFalse(report["openmp_reduction_changed"])
        self.assertFalse(
            report["checkpoint_output_propagation_changed"]
        )
        self.assertEqual(
            report["anchors"]["located"],
            report["anchors"]["expected"],
        )


if __name__ == "__main__":
    unittest.main()
