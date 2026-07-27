import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py"
RUNNER = ROOT / "scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_source_keyed_kernel_adapter", INVENTORY
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourSourceKeyedKernelAdapterInventoryTest(unittest.TestCase):
    def test_inventory_passes_with_proof_only_scope(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertEqual(report["anchors"]["located"], report["anchors"]["expected"])

    def test_default_and_production_surfaces_are_unchanged(self):
        report = load_inventory_module().collect(ROOT)
        self.assertFalse(report["production_or_default_surfaces_changed"])
        self.assertFalse(report["backend_neutral_adapter_has_opensubdiv_leak"])
        self.assertFalse(report["production_one_ring_mutation"])

    def test_absent_dependency_skips_cleanly(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(RUNNER), "--json"],
            cwd=ROOT,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is required for the present-dependency proof",
    )
    def test_present_dependency_adapter_passes(self):
        result = subprocess.run(
            [str(RUNNER), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["adapter_passed"])
        self.assertFalse(report["actual_production_force_path_executed"])
        adapter = report["adapter"]
        self.assertTrue(adapter["independent_fixed_source_layout_oracle_passed"])
        self.assertLessEqual(adapter["max_scatter_oracle_delta"], 1.0e-12)
        self.assertTrue(adapter["canonicalized_by_original_source_id"])
        self.assertTrue(adapter["source_binding_permutation_invariant"])
        self.assertTrue(adapter["permuted_row_columns_canonicalized"])
        self.assertTrue(adapter["permuted_force_columns_canonicalized"])
        self.assertTrue(adapter["independent_permuted_scatter_oracle_passed"])
        self.assertLessEqual(adapter["max_permutation_adapted_delta"], 1.0e-12)
        self.assertLessEqual(adapter["max_permutation_scatter_delta"], 1.0e-12)
        self.assertLessEqual(adapter["max_permutation_oracle_delta"], 1.0e-12)
        self.assertTrue(adapter["duplicate_row_entries_aggregated_by_source_id"])
        self.assertLessEqual(
            adapter["max_duplicate_row_aggregation_delta"], 1.0e-12
        )
        self.assertLessEqual(
            adapter["max_duplicate_row_scatter_delta"], 1.0e-12
        )
        self.assertTrue(adapter["negative_gates"]["all_passed"])
        self.assertTrue(adapter["production_one_rings_empty"])
        self.assertFalse(adapter["production_one_rings_mutated"])
        composition = adapter["guarded_scientific_request_composition"]
        self.assertTrue(composition["fresh_opensubdiv_rows_consumed"])
        self.assertTrue(
            composition["default_off_geometry_staging_rejected"]
        )
        self.assertTrue(composition["geometry_staging_executed"])
        self.assertTrue(
            composition["geometry_staging_mesh_state_unchanged"]
        )
        self.assertLessEqual(
            composition["max_geometry_staging_difference"], 1.0e-12
        )
        self.assertTrue(composition["default_off_request_rejected"])
        self.assertTrue(composition["explicit_request_accepted"])
        self.assertTrue(composition["production_scientific_algebra_executed"])
        self.assertTrue(composition["caller_owned_output"])
        self.assertTrue(composition["mesh_state_unchanged"])
        self.assertTrue(composition["mesh_state_mutation_gate_binding"])
        self.assertTrue(
            composition["production_shaped_source_scatter_executed"]
        )
        self.assertTrue(
            composition["default_off_vertex_force_publication_rejected"]
        )
        self.assertTrue(composition["vertex_force_publication_executed"])
        self.assertTrue(
            composition["only_membrane_force_families_published"]
        )
        self.assertTrue(
            composition[
                "default_off_face_observable_publication_rejected"
            ]
        )
        self.assertTrue(
            composition["face_observable_publication_executed"]
        )
        self.assertTrue(composition["only_face_observables_published"])
        self.assertTrue(
            composition["default_off_atomic_publication_rejected"]
        )
        self.assertTrue(
            composition["atomic_face_loop_publication_executed"]
        )
        self.assertTrue(
            composition[
                "only_reviewed_families_published_atomically"
            ]
        )
        self.assertTrue(
            composition[
                "default_off_geometry_aware_composition_rejected"
            ]
        )
        self.assertTrue(
            composition["geometry_aware_atomic_composition_executed"]
        )
        self.assertTrue(
            composition[
                "staged_geometry_used_for_scientific_evaluation"
            ]
        )
        self.assertTrue(composition["stale_mesh_globals_ignored"])
        self.assertTrue(
            composition[
                "only_reviewed_geometry_scientific_families_published_atomically"
            ]
        )
        self.assertTrue(composition["route_remained_disabled"])
        self.assertLessEqual(composition["max_observable_difference"], 1.0e-12)
        self.assertLessEqual(composition["max_source_force_difference"], 1.0e-12)
        self.assertLessEqual(
            composition["max_production_shaped_scatter_difference"],
            1.0e-12,
        )
        self.assertLessEqual(
            composition["max_published_force_difference"],
            1.0e-12,
        )
        self.assertLessEqual(
            composition["max_published_face_observable_difference"],
            1.0e-12,
        )
        self.assertLessEqual(
            composition["max_atomic_published_force_difference"],
            1.0e-12,
        )
        self.assertLessEqual(
            composition[
                "max_atomic_published_face_observable_difference"
            ],
            1.0e-12,
        )
        self.assertLessEqual(
            composition["max_geometry_aware_force_difference"],
            1.0e-12,
        )
        self.assertLessEqual(
            composition[
                "max_geometry_aware_face_observable_difference"
            ],
            1.0e-12,
        )
        self.assertLessEqual(
            composition["max_geometry_aware_geometry_difference"],
            1.0e-12,
        )


if __name__ == "__main__":
    unittest.main()
