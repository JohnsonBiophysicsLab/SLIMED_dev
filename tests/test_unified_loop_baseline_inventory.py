"""Mutation coverage for the fail-closed unified Loop baseline inventory."""

from __future__ import annotations

import copy
import importlib.util
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_unified_loop_baseline.py"
SPEC = importlib.util.spec_from_file_location("unified_loop_inventory", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
INVENTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVENTORY)


class UnifiedLoopBaselineInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = INVENTORY.collect_inventory()
        errors = INVENTORY.validate_inventory(cls.baseline)
        if errors:
            raise AssertionError(f"baseline inventory failed: {errors}")

    def assert_mutation_rejected(self, mutate) -> None:
        candidate = copy.deepcopy(self.baseline)
        mutate(candidate)
        self.assertTrue(
            INVENTORY.validate_inventory(candidate, check_adr=False),
            "synthetic drift unexpectedly passed fail-closed validation",
        )

    def test_A_build_flags_dependency_and_macro_coupling(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["A_build_dependency"]["build_flags"].append(
                "USE_OPENSUBDIV_LOOP"))
        self.assert_mutation_rejected(
            lambda r: r["A_build_dependency"].update(
                {"dependency_root_required_for_each_flag": False}))
        self.assert_mutation_rejected(
            lambda r: r["A_build_dependency"].update(
                {"valence4_compile_macro": "USE_OPENSUBDIV_VALENCE4"}))

    def test_B_runtime_tokens_conflict_and_early_return(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["B_runtime_routes"]["runtime_flags"].append(
                "SLIMED_USE_OPENSUBDIV_LOOP"))
        self.assert_mutation_rejected(
            lambda r: r["B_runtime_routes"].update(
                {"regular_semantics_present": False}))
        self.assert_mutation_rejected(
            lambda r: r["B_runtime_routes"].update(
                {"v4_v5_conflict_rejected": False}))

    def test_C_current_main_and_pr182_remain_separate(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"pr182_current_main_production": True}))
        self.assert_mutation_rejected(
            lambda r: r["C_valence3_ancestry"].update(
                {"runtime_selector_absent_on_current_main": False}))

    def test_D_topology_face_order_count_valence_and_one_ring(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["valence3_tetrahedron"]
            ["oriented_faces"][0].reverse())
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["valence4_octahedron"]
            ["oriented_faces"].pop())
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["valence5_icosahedron"]
            ["oriented_faces"].__setitem__(0, [0, 5, 11]))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["valence3_tetrahedron"].update(
                {"source_faces_match_fixture": False}))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["valence5_icosahedron"].update(
                {"face_source_mapping_sha256": "0" * 64}))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["valence4_octahedron"].update(
                {"source_guard_present": False}))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["valence5_icosahedron"].update(
                {"valence": 6}))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["legacy_11_control_predicate"]
            .update({"admitted_corner_valences": [5, 6, 6]}))

    def test_E_scheme_boundary_and_version_policy(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["E_provider_policy"].update(
                {"all_three_providers_bind_scheme_boundary": False}))
        self.assert_mutation_rejected(
            lambda r: r["E_provider_policy"]["compile_version_pin"].update(
                {"valence5": 30700}))
        self.assert_mutation_rejected(
            lambda r: r["E_provider_policy"].update(
                {"ambient_version_qualified": True}))

    def test_F_cache_key_coordinate_mutex_and_invalidation(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["F_regular_cache"].update(
                {"coordinates_excluded": False}))
        self.assert_mutation_rejected(
            lambda r: r["F_regular_cache"].update({"mutex_guarded": False}))
        self.assert_mutation_rejected(
            lambda r: r["F_regular_cache"]["invalidations"].append(
                "coordinate_update"))
        self.assert_mutation_rejected(
            lambda r: r["F_regular_cache"]["key_fields"].append(
                "coordinates"))

    def test_G_geometry_energy_force_are_independent_anchors(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["G_volume_functionals"].update(
                {"x_only_anchors_present": False}))
        self.assert_mutation_rejected(
            lambda r: r["G_volume_functionals"].update(
                {"global_volume_energy": "missing"}))
        self.assert_mutation_rejected(
            lambda r: r["G_volume_functionals"].update(
                {"force_anchor_present": False}))
        self.assert_mutation_rejected(
            lambda r: r["G_volume_functionals"].update(
                {"one_functional_claim_valid": True}))
        self.assert_mutation_rejected(
            lambda r: r["G_volume_functionals"]["enumerated_factor_names"]
            .append("kFullDivergenceVolumeFunctional"))

    def test_H_source_ids_seven_rows_mixed_duplicate_and_transaction(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["H_source_keyed_seam"].update(
                {"variable_original_source_ids": False}))
        self.assert_mutation_rejected(
            lambda r: r["H_source_keyed_seam"].update(
                {"derivative_row_count": 6}))
        self.assert_mutation_rejected(
            lambda r: r["H_source_keyed_seam"].update(
                {"mixed_rows": [5]}))
        self.assert_mutation_rejected(
            lambda r: r["H_source_keyed_seam"].update(
                {"guarded_transaction": False}))

    def test_I_named_tolerance_and_fixture_bytes(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["I_tolerances_fixtures"]["tolerances"]
            ["valence3_row_invariants"].update({"value": 2.0e-12}))
        self.assert_mutation_rejected(
            lambda r: r["I_tolerances_fixtures"]["tolerances"]
            ["regular_row_and_route_parity"].update({"value": math.nan}))
        self.assert_mutation_rejected(
            lambda r: r["I_tolerances_fixtures"].update(
                {"source_anchors_present": False}))
        fixture = next(iter(INVENTORY.EXPECTED_FIXTURE_HASHES))
        self.assert_mutation_rejected(
            lambda r: r["I_tolerances_fixtures"]["fixture_sha256"]
            .update({fixture: "0" * 64}))

    def test_J_csv_checkpoint_order_precision_atomicity_and_metadata(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["J_output_checkpoint"]["energy_csv_fields"].reverse())
        self.assert_mutation_rejected(
            lambda r: r["J_output_checkpoint"].update({"precision": 16}))
        self.assert_mutation_rejected(
            lambda r: r["J_output_checkpoint"].update(
                {"checkpoint_atomic_rename": False}))
        self.assert_mutation_rejected(
            lambda r: r["J_output_checkpoint"].update(
                {"backend_or_functional_metadata_present": True}))

    def test_K_edge_flip_proof_only_and_cuda_frozen(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["K_deferred_lanes"].update(
                {"adaptive_production_call_count": 1}))
        self.assert_mutation_rejected(
            lambda r: r["K_deferred_lanes"].update(
                {"adaptive_runtime_flag_present": True}))
        self.assert_mutation_rejected(
            lambda r: r["K_deferred_lanes"].update(
                {"cuda_changed_from_exact_base": True}))

    def test_L_allowlists_and_missing_schema_fail_closed(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["L_fail_closed"]["allowed_runtime_flags"].append(
                "SLIMED_USE_OPENSUBDIV_UNKNOWN"))
        self.assert_mutation_rejected(
            lambda r: r["L_fail_closed"]["observed_volume_functional_tokens"]
            .append("full_divergence_volume"))
        self.assert_mutation_rejected(lambda r: r.pop("G_volume_functionals"))
        self.assert_mutation_rejected(lambda r: r.update({"schema_version": 2}))


if __name__ == "__main__":
    unittest.main()
