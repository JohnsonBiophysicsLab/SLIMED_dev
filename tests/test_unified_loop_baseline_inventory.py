"""Mutation coverage for the fail-closed unified Loop baseline inventory."""

from __future__ import annotations

import copy
import importlib.util
import math
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_unified_loop_baseline.py"
SPEC = importlib.util.spec_from_file_location("unified_loop_inventory", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
INVENTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVENTORY)


def replace_last(text: str, old: str, new: str) -> str:
    prefix, separator, suffix = text.rpartition(old)
    return prefix + new + suffix if separator else text


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

    def assert_text_mutation_rejected(self, relative, transform) -> None:
        original_text = INVENTORY._text
        before = original_text(relative)
        after = transform(before)
        self.assertNotEqual(before, after, "source mutation changed nothing")

        def replacement(path):
            return after if path == relative else original_text(path)

        with mock.patch.object(INVENTORY, "_text", side_effect=replacement):
            candidate = INVENTORY.collect_inventory()
            errors = INVENTORY.validate_inventory(candidate)
        self.assertTrue(errors, "collection-layer source drift unexpectedly passed")

    def assert_git_output_mutation_rejected(self, matcher, replacement) -> None:
        original_output = INVENTORY._git_output

        def changed(*arguments):
            return replacement if matcher(arguments) else original_output(*arguments)

        with mock.patch.object(INVENTORY, "_git_output", side_effect=changed):
            candidate = INVENTORY.collect_inventory()
        self.assertTrue(
            INVENTORY.validate_inventory(candidate, check_adr=False),
            "collection-layer Git drift unexpectedly passed",
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
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text.replace(
                "        return;\n    }\n    if (valence4RouteRequested)",
                "        // return;\n    }\n    if (valence4RouteRequested)", 1))
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text.replace(
                "        return;\n    }\n\n    // Step 1.",
                "        // return;\n    }\n\n    // Step 1. fake return;", 1))
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text.replace(
                "evaluate_guarded_valence5_opensubdiv_production_route(*this)",
                "/* evaluate_guarded_valence5_opensubdiv_production_route(*this) */\n"
                "            evaluate_guarded_valence5_route_removed(*this)", 1))

    def test_C_current_main_and_pr176_pr182_stack_remain_separate(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"pr176_current_main_production": True}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"pr182_current_main_production": True}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"observed_pr182_pr176_merge_base": "0" * 40}))
        self.assert_mutation_rejected(
            lambda r: r["C_valence3_ancestry"].update(
                {"runtime_selector_absent_on_current_main": False}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update({"observed_head": "0" * 40}))
        # A stray merge on a package branch must still be caught, and a
        # degraded linearity reference must fail loudly rather than silently
        # weakening the check.
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"merge_commits_after_base": ["0" * 40]}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update({"mainline_ref_resolved": False}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"linearity_ref": INVENTORY.BASE_SHA}))
        self.assert_git_output_mutation_rejected(
            lambda args: args[:2] == ("merge-base", INVENTORY.BASE_SHA)
            and args[-1] == "HEAD",
            "0" * 40,
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args[:2] == ("diff", "--name-only")
            and args[-1].endswith("..HEAD"),
            "\n".join(INVENTORY.EXPECTED_WP0_PATHS + ["src/mesh/Mesh.cpp"]),
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args[:2] == ("diff", "--name-only")
            and args[-1].endswith("..HEAD"),
            "\n".join(INVENTORY.EXPECTED_WP0_PATHS[:-1]),
        )

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
        self.assert_text_mutation_rejected(
            "src/mesh/OpenSubdiv_valence4_row_provider.cpp",
            lambda text: text.replace("Sdc::SCHEME_LOOP", "Sdc::SCHEME_CATMARK", 1))

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
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "kLegacyVolumeQuadratureFactor = 0.16666666666",
                "kLegacyVolumeQuadratureFactor = 1.0 / 6.0", 1))

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
        self.assert_text_mutation_rejected(
            "src/mesh/OpenSubdiv_regular_evaluator.cpp",
            lambda text: text.replace(
                "kOpenSubdivRegularRowTolerance = 5.0e-6",
                "kOpenSubdivRegularRowTolerance = 6.0e-6", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/OpenSubdiv_valence4_row_provider.cpp",
            lambda text: text.replace(
                "std::abs(coefficientSum - expectedSum) > 1.0e-12",
                "std::abs(coefficientSum - expectedSum) > 2.0e-12", 1))
        fixture = next(iter(INVENTORY.EXPECTED_FIXTURE_HASHES))
        self.assert_mutation_rejected(
            lambda r: r["I_tolerances_fixtures"]["fixture_sha256"]
            .update({fixture: "0" * 64}))

    def test_I2_periodic_scope_n6_equivalence_and_performance_budget(self) -> None:
        self.assert_mutation_rejected(
            lambda r: r["I2_scope_performance"]["primary_workload"].update(
                {"boundary_type": "Free"}))
        self.assert_mutation_rejected(
            lambda r: r["I2_scope_performance"]["primary_workload"].update(
                {"mixed_valence_ghost_faces": 0}))
        self.assert_mutation_rejected(
            lambda r: r["I2_scope_performance"]["regular_n6_masks_coincide"]
            .update({"center": 0.0}))
        self.assert_mutation_rejected(
            lambda r: r["I2_scope_performance"]["performance_budget"].update(
                {"generic_vs_cached_regular_median": 1.20}))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "generic_vs_cached_regular_median <= 1.10",
                "generic_vs_cached_regular_median <= 1.20", 1))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "generic_vs_direct_regular_each_case <= 2.00",
                "generic_vs_direct_regular_each_case <= 2.20", 1))
        self.assert_text_mutation_rejected(
            "tests/test_surface_geometry_characterization.cpp",
            lambda text: text.replace(
                "EXPECT_EQ(ghostMixedValenceFaces, 336)",
                "EXPECT_EQ(ghostMixedValenceFaces, 0)", 1))
        self.assert_text_mutation_rejected(
            "tests/test_surface_geometry_characterization.cpp",
            lambda text: text.replace(
                "    EXPECT_EQ(ghostMixedValenceFaces, 336);",
                "    // EXPECT_EQ(ghostMixedValenceFaces, 336);", 1))
        self.assert_text_mutation_rejected(
            "tests/test_irregular_fixture_inventory.py",
            lambda text: text.replace(
                "        self.assertEqual(sum(flags), 960)",
                "        # self.assertEqual(sum(flags), 960)", 1))
        self.assert_text_mutation_rejected(
            "tests/test_irregular_fixture_inventory.py",
            lambda text: text.replace(
                "        self.assertEqual(sum(flags), 960)",
                '        """self.assertEqual(sum(flags), 960)"""', 1))
        for protocol_anchor in (
                "coordinate-only\nsteady state",
                "same-binary",
                "alternating-order",
                "warmup-plus-repeat",
                "Topology preparation is reported separately",
                "reviewed\nfor platform variance"):
            with self.subTest(protocol_anchor=protocol_anchor):
                self.assert_text_mutation_rejected(
                    "docs/adr_unified_loop_backend.md",
                    lambda text, anchor=protocol_anchor:
                    replace_last(text, anchor, "protocol-anchor-removed"))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "Proposed D8 performance budgets are frozen",
                "<!-- Proposed D8 performance budgets are frozen", 1).replace(
                "gates.\n\nAuthoritative fixture hashes:",
                "gates. -->\n\nAuthoritative fixture hashes:", 1))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "Proposed D8 performance budgets are frozen",
                "```text\nProposed D8 performance budgets are frozen", 1).replace(
                "gates.\n\nAuthoritative fixture hashes:",
                "gates.\n```\n\nAuthoritative fixture hashes:", 1))

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
        self.assert_text_mutation_rejected(
            "src/io/output.cpp",
            lambda text: text.replace(
                "        << energy.energyArea << ','\n"
                "        << energy.energyVolume << ','",
                "        << energy.energyVolume << ','\n"
                "        << energy.energyArea << ','", 1))

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
        for decision, authority, replacement in (
                ("D2b", "Explicit user production-scope decision",
                 "Maintainer production-scope decision"),
                ("D5", "Explicit user decision after WP1.1a; any `5/6/6` implementation needs a separate scientific gate",
                 "Maintainer decision"),
                ("D8", "Reproduced benchmark evidence plus explicit user approval",
                 "Benchmark evidence only")):
            with self.subTest(decision=decision):
                self.assert_text_mutation_rejected(
                    "docs/unified_irregular_loop_implementation_plan.md",
                    lambda text, old=authority, new=replacement:
                    text.replace(old, new, 1))
        original_corpus = INVENTORY._source_corpus()
        with mock.patch.object(
                INVENTORY, "_source_corpus",
                return_value=original_corpus +
                '\nconst char *unexpected = "SLIMED_USE_OPENSUBDIV_UNKNOWN";'):
            candidate = INVENTORY.collect_inventory()
        self.assertTrue(INVENTORY.validate_inventory(candidate, check_adr=False))


if __name__ == "__main__":
    unittest.main()
