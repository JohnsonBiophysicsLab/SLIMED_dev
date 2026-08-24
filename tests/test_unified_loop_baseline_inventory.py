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

    def collect_linearity(self, mainline_head, fork_point, merge_commits):
        def git_output(*arguments):
            if arguments == (
                    "rev-parse", "--verify",
                    f"{INVENTORY.MAINLINE_REF}^{{commit}}"):
                return mainline_head
            if arguments == (
                    "merge-base", INVENTORY.MAINLINE_REF, "HEAD"):
                return fork_point
            if arguments == (
                    "rev-list", "--min-parents=2", f"{fork_point}..HEAD"):
                return "\n".join(merge_commits)
            if arguments == (
                    "rev-list", "--min-parents=2",
                    f"{INVENTORY.BASE_SHA}..HEAD"):
                return mainline_head
            raise AssertionError(f"unexpected Git query: {arguments}")

        with mock.patch.object(INVENTORY, "_git_output", side_effect=git_output), \
                mock.patch.object(INVENTORY, "_git_success", return_value=True):
            return INVENTORY._collect_package_linearity()

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
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"linearity_ref": INVENTORY.BASE_SHA}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update({"mainline_ref_resolved": False}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"observed_mainline_head": "unavailable"}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"linearity_fork_point": "unavailable"}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"linearity_fork_is_ancestor": False}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"merge_commits_after_fork": ["0" * 40]}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"wp0_reviewed_endpoint": "0" * 40}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"observed_wp0_reviewed_endpoint_commit": "unavailable"}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"wp0_base_is_ancestor_of_endpoint": False}))
        self.assert_mutation_rejected(
            lambda r: r["baseline"].update(
                {"wp0_endpoint_is_ancestor_of_head": False}))
        self.assert_git_output_mutation_rejected(
            lambda args: args[:2] == ("merge-base", INVENTORY.BASE_SHA)
            and args[-1] == "HEAD",
            "0" * 40,
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args == (
                "rev-parse", "--verify",
                f"{INVENTORY.WP0_REVIEWED_ENDPOINT_SHA}^{{commit}}"),
            "unavailable",
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args == (
                "rev-parse", "--verify",
                f"{INVENTORY.MAINLINE_REF}^{{commit}}"),
            "unavailable",
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args == (
                "merge-base", INVENTORY.MAINLINE_REF, "HEAD"),
            "unavailable",
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args == (
                "merge-base", INVENTORY.BASE_SHA,
                INVENTORY.WP0_REVIEWED_ENDPOINT_SHA),
            "0" * 40,
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args[:2] == ("diff", "--name-only")
            and args[-1] == (
                f"{INVENTORY.BASE_SHA}.."
                f"{INVENTORY.WP0_REVIEWED_ENDPOINT_SHA}"),
            "\n".join(INVENTORY.EXPECTED_WP0_PATHS + ["src/mesh/Mesh.cpp"]),
        )
        self.assert_git_output_mutation_rejected(
            lambda args: args[:2] == ("diff", "--name-only")
            and args[-1] == (
                f"{INVENTORY.BASE_SHA}.."
                f"{INVENTORY.WP0_REVIEWED_ENDPOINT_SHA}"),
            "\n".join(INVENTORY.EXPECTED_WP0_PATHS[:-1]),
        )
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                INVENTORY.WP0_REVIEWED_ENDPOINT_SHA, "0" * 40, 1))

    def test_C_future_main_merge_is_outside_package_linearity_range(self) -> None:
        # Model HEAD as a merge commit already incorporated into origin/main.
        # A BASE_SHA..HEAD query would return that merge, while the package
        # range starts at HEAD and is therefore correctly empty.
        future_main_merge = "f" * 40
        linearity = self.collect_linearity(
            future_main_merge, future_main_merge, [])
        self.assertEqual(linearity["linearity_fork_point"], future_main_merge)
        self.assertEqual(linearity["merge_commits_after_fork"], [])

        candidate = copy.deepcopy(self.baseline)
        candidate["baseline"].update(linearity)
        candidate["baseline"].update({
            "observed_head": future_main_merge,
            "observed_head_commit": future_main_merge,
        })
        self.assertFalse(
            INVENTORY.validate_inventory(candidate, check_adr=False),
            "a merge commit already incorporated into mainline was misclassified",
        )

    def test_C_merge_on_unmerged_package_branch_is_rejected(self) -> None:
        mainline_head = "a" * 40
        package_merge = "b" * 40
        linearity = self.collect_linearity(
            mainline_head, mainline_head, [package_merge])
        candidate = copy.deepcopy(self.baseline)
        candidate["baseline"].update(linearity)
        errors = INVENTORY.validate_inventory(candidate, check_adr=False)
        self.assertIn("unexpected merge commit in package branch", errors)

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
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "regularLimitSurfaceRowCache_.invalidate();",
                "// regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "// invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "// invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "invalidate_topology_derived_state();\n"
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "\nprivate:\n    /**\n"
                "     * @brief Invalidate topology-derived state",
                "\npublic:\n    /**\n"
                "     * @brief Invalidate topology-derived state", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "\nprivate:\n    /**\n"
                "     * @brief Invalidate topology-derived state",
                "\nprotected:\n    /**\n"
                "     * @brief Invalidate topology-derived state", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "    void invalidate_topology_derived_state()\n"
                "    {",
                "    // void invalidate_topology_derived_state()\n"
                "    // {", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();\n",
                "", 1).replace(
                    "    std::uint64_t topologyGeneration_ = 0;",
                    "    void misplaced_reset()\n"
                    "    {\n"
                    "        regularLimitSurfaceRowCache_.invalidate();\n"
                    "    }\n\n"
                    "    std::uint64_t topologyGeneration_ = 0;", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();\n", "", 1)
                + "\nvoid misplaced_topology_invalidation()\n"
                "{\n"
                "    invalidate_topology_derived_state();\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "invalidate_topology_derived_state();\n"
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();\n", "", 1)
                + "\nvoid misplaced_flat_topology_invalidation()\n"
                "{\n"
                "    invalidate_topology_derived_state();\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_io.cpp",
            lambda text: text +
                "\nvoid Mesh::extra_topology_invalidation()\n"
                "{\n"
                "    invalidate_topology_derived_state();\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_io.cpp",
            lambda text: text +
                "\nvoid Mesh::extra_cache_reset()\n"
                "{\n"
                "    regularLimitSurfaceRowCache_.invalidate();\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_io.cpp",
            lambda text: text +
                "\nvoid Mesh::invalidate_topology_derived_state() {}\n")

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

    def test_I3_B2p_inputs_fail_closed_on_required_mutations(self) -> None:
        fixture = next(iter(INVENTORY.EXPECTED_B2P_FIXTURE_HASHES))

        original_is_file = Path.is_file

        def missing_file(path):
            if Path(path).resolve() == (ROOT / fixture).resolve():
                return False
            return original_is_file(path)

        with mock.patch.object(Path, "is_file", missing_file):
            candidate = INVENTORY.collect_inventory()
        self.assertIn(
            "B2p fixture missing or SHA256 drift",
            INVENTORY.validate_inventory(candidate, check_adr=False),
        )

        original_sha256 = INVENTORY._sha256

        def altered_byte_digest(path):
            return "0" * 64 if path == fixture else original_sha256(path)

        with mock.patch.object(
                INVENTORY, "_sha256", side_effect=altered_byte_digest):
            candidate = INVENTORY.collect_inventory()
        self.assertIn(
            "B2p fixture missing or SHA256 drift",
            INVENTORY.validate_inventory(candidate, check_adr=False),
        )

        self.assert_mutation_rejected(
            lambda r: r["I3_b2p_frozen_inputs"]["expected_fixture_sha256"]
            .update({fixture: "f" * 64}))
        self.assert_mutation_rejected(
            lambda r: r["I3_b2p_frozen_inputs"]["targets"]
            ["irregular_position_row_accuracy"].update({"adr": 6.0e-6}))
        self.assert_mutation_rejected(
            lambda r: r["I3_b2p_frozen_inputs"]["locality_sample_manifest"]
            ["samples"].pop())
        self.assert_mutation_rejected(
            lambda r: r["I3_b2p_frozen_inputs"]["locality_sample_manifest"]
            ["samples"].reverse())
        self.assert_mutation_rejected(
            lambda r: r["I3_b2p_frozen_inputs"]["locality_sample_manifest"]
            ["samples"][0].update({"u_numerator": 2}))
        self.assert_mutation_rejected(
            lambda r: r["I3_b2p_frozen_inputs"]["locality_sample_manifest"]
            ["samples"][0].pop("barycentric_numerators"))
        self.assert_mutation_rejected(
            lambda r: r["I3_b2p_frozen_inputs"]["locality_sample_manifest"]
            ["row_order"].pop())
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "| `irregular_position_row_accuracy` | `5.0e-6` |",
                "| `irregular_position_row_accuracy` | `6.0e-6` |", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "H_q = transpose(B) * H_y * B",
                "oracle-hessian-map-removed", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "intersect its five outward-rounded coefficient",
                "intersect an unspecified coefficient", 1))

        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "epsilon_i = max(abs(d_i - lo_i), abs(hi_i - d_i))",
                "epsilon_i = (hi_i - lo_i) / 2", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "required exact binary64 import of `d_i`",
                "approximate import of `d_i`", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "required exact binary64 import of `c_i`",
                "approximate import of `c_i`", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "E_coeff = sum_i epsilon_i",
                "E_coeff = sum_i half_width_i", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "E_a = sum_i ([lo_i,hi_i] - d_i) * P_i[a]",
                "E_a = midpoint_serialization_difference", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "E_geom = max_a(max(abs(lower(E_a)), abs(upper(E_a))) / lower(L_M))",
                "E_geom = midpoint_geometry_norm", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "exactly reimported before `E_coeff` and `E_geom` are evaluated",
                "converted only after all bounds have passed", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "u_i = max(abs(c_i - lo_i), abs(c_i - hi_i))",
                "u_i = abs(c_i - d_i)", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "U_coeff = sum_i u_i",
                "U_coeff = midpoint_l1_difference", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "D_a = sum_i ([lo_i,hi_i] - c_i) * P_i[a]",
                "D_a = midpoint_geometry_difference", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "U_geom = max_a(max(abs(lower(D_a)), abs(upper(D_a))) / lower(L_M))",
                "U_geom = midpoint_geometry_norm", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "Pointwise midpoint differences are diagnostic only",
                "Pointwise midpoint differences decide PASS", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "is a candidate FAIL and may never be relabeled oracle-uncovered",
                "is oracle-uncovered", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "explicit `MPFR_ROOT` and `OPENSUBDIV_ROOT` values",
                "ambient proof dependencies", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "must not count the two directory names as independent mesh-level",
                "may count the two directory names as independent mesh-level", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "kappa_infinity(V) = ||V||_infinity * ||V^-1||_infinity",
                "basis-condition-definition-removed", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "`mpfr_init2(...,544)`", "unspecified-interval-precision", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "mandatory primary computation is Stam eigenanalysis",
                "primary-oracle-role-removed", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text + "\n candidate_" + "comparison_result\n")
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "Approved - Frozen B2p targets and coverage challenge accepted "
                "for B2 proof. This does not qualify Bfr, decide D9a or D9b, "
                "widen a target, or authorize production.",
                "Pending - frozen by B2p before B2 runs", 1))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "Frozen B2p / D10 targets (approved)",
                "Frozen B2p / D10 proposal (not approved)", 1))

        self.assertEqual(
            self.baseline["I_tolerances_fixtures"]["tolerances"],
            INVENTORY.EXPECTED_TOLERANCES,
        )
        self.assertEqual(
            self.baseline["I_tolerances_fixtures"]["fixture_sha256"],
            INVENTORY.EXPECTED_FIXTURE_HASHES,
        )

    def test_I4_B2_readiness_inputs_fail_closed_on_required_mutations(self) -> None:
        fixture = next(iter(INVENTORY.EXPECTED_B2_READINESS_FIXTURE_HASHES))

        original_is_file = Path.is_file

        def missing_file(path):
            if Path(path).resolve() == (ROOT / fixture).resolve():
                return False
            return original_is_file(path)

        with mock.patch.object(Path, "is_file", missing_file):
            candidate = INVENTORY.collect_inventory()
        self.assertIn(
            "B2 readiness fixture missing or SHA256 drift",
            INVENTORY.validate_inventory(candidate, check_adr=False),
        )

        original_sha256 = INVENTORY._sha256

        def altered_digest(path):
            return "0" * 64 if path == fixture else original_sha256(path)

        with mock.patch.object(INVENTORY, "_sha256", side_effect=altered_digest):
            candidate = INVENTORY.collect_inventory()
        self.assertIn(
            "B2 readiness fixture missing or SHA256 drift",
            INVENTORY.validate_inventory(candidate, check_adr=False),
        )

        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["criteria"]
            ["b2_preparation_median_ms"].update({"bfr_plan": 1001.0}))
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["execution_case_ids"].pop())
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["source_row_ids"].reverse())
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["alias_pairs"][0]
            .__setitem__(1, "u8_09_nonplatonic"))
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]
            ["unique_content_identities"].pop())
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]
            ["forbidden_claim_tokens"].append("bfr_qualified"))
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["contract"].update(
                {"d12_plan_status": "Proposed"}))
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["contract"]
            ["mutation_ids"].pop())
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["contract"].update(
                {"manifest_contract_sha256": "0" * 64}))
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["contract"].update(
                {"alias_contracts_valid": False}))
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["contract"].update(
                {"coordinate_mutation_bits_valid": False}))
        self.assert_mutation_rejected(
            lambda r: r["I4_b2_readiness_pending_inputs"]["contract"].update(
                {"thread_tuple_count": 587}))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "`b2_preparation_median_ms` | `<= 1000.000`",
                "`b2_preparation_median_ms` | `<= 1001.000`", 1))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "`b2_preparation_peak_rss_delta_mib` | `64.000`",
                "`b2_preparation_peak_rss_delta_mib` | `65.000`", 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "12 + 4*U + 72*S + 12*C",
                "12 + 4*U + 72*S + 8*C", 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"execution_case_id": "u8_14_edge_flip_family"',
                '"execution_case_id": "u8_99_edge_flip_family"', 1))
        self.assert_text_mutation_rejected(
            "scripts/generate_b2_readiness_fixtures.py",
            lambda text: text.replace(
                '"u8_14_edge_flip_family", "U8-14",',
                '"u8_99_edge_flip_family", "U8-14",', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"alias_of": "u8_14_edge_flip_family"',
                '"alias_of": "u8_09_nonplatonic"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"reason": "N/A in B2: quadrature selection is WP5.1/WP5.2 '
                'and production activation is D9b."',
                '"reason": "N/A"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"id": "trend-r08-ray02"', '"id": "trend-r08-ray99"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"output_bits_hex": "3ff2c851eb851eb8"',
                '"output_bits_hex": "3ff2c851eb851eb9"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"hw_model": "Mac17,2"', '"hw_model": "Mac17,3"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"-DBUILD_SHARED_LIBS=OFF"',
                '"-DBUILD_SHARED_LIBS=ON"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"opensubdiv/bfr/surfaceFactoryCache.cpp"',
                '"opensubdiv/bfr/surfaceFactoryCache_extra.cpp"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"__.SYMDEF"', '"__.SYMDEF_WRONG"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"after_refiner_destruction"', '"after_refiner_leak"', 1))
        self.assert_text_mutation_rejected(
            "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json",
            lambda text: text.replace(
                '"workers": [\n      1,\n      2,\n      4\n    ]',
                '"workers": [\n      1,\n      4\n    ]', 1))
        self.assert_text_mutation_rejected(
            "docs/bfr_loop_backend_plan_macos.md",
            lambda text: text.replace(
                "D12 | Approved - B2 readiness criteria",
                "D12 | Proposed - B2 readiness criteria", 1))

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
                {"generic_vs_cached_regular_median": 1.10}))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "generic_vs_cached_regular_median <= TBD",
                "generic_vs_cached_regular_median <= 1.10", 1))
        self.assert_text_mutation_rejected(
            "docs/unified_irregular_loop_implementation_plan.md",
            lambda text: text.replace(
                "generic_vs_cached_regular_median <= TBD",
                "generic_vs_cached_regular_median <= 1.10", 1))
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
                "Proposed D8 performance inputs are frozen",
                "<!-- Proposed D8 performance inputs are frozen", 1).replace(
                "gates.\n\nAuthoritative fixture hashes:",
                "gates. -->\n\nAuthoritative fixture hashes:", 1))
        self.assert_text_mutation_rejected(
            "docs/adr_unified_loop_backend.md",
            lambda text: text.replace(
                "Proposed D8 performance inputs are frozen",
                "```text\nProposed D8 performance inputs are frozen", 1).replace(
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

    def test_M_D1_D2_approved_scope_limits_fail_closed(self) -> None:
        required_status_fragments = {
            "D1": (
                "Stock OpenSubdiv 3.7.0 Loop semantics",
                "forward-looking CPU proof baseline",
                "Completed rows are not modified to reproduce legacy masks",
                "does not select Far versus Bfr",
                "does not change the production default",
                "does not approve arbitrary production inputs",
            ),
            "D2": (
                "complete",
                "closed",
                "consistently oriented",
                "two-manifold triangular meshes",
                "Boundaries",
                "holes",
                "ghosts",
                "non-triangles",
                "non-manifold incidence",
                "inconsistent orientation",
                "must fail before mutation",
                "does not decide D2b",
                "does not authorize production activation",
            ),
        }
        for decision, fragments in required_status_fragments.items():
            status = INVENTORY.EXPECTED_DECISIONS[decision]
            for fragment in fragments:
                with self.subTest(decision=decision, fragment=fragment):
                    self.assertIn(fragment, status)
                    reduced_status = status.replace(fragment, "scope-limit-dropped", 1)
                    self.assert_text_mutation_rejected(
                        "docs/adr_unified_loop_backend.md",
                        lambda text, key=decision, old=status,
                        new=reduced_status: text.replace(
                            f"| {key} | {old} |",
                            f"| {key} | {new} |", 1),
                    )

    def test_M_other_decision_statuses_remain_frozen(self) -> None:
        frozen_statuses = {
            "D0": "Proposed - pending explicit user stack disposition",
            "D2b": "Proposed - pending explicit user production-scope approval",
            "D3": "Pending post-WP2.1 oracle, independent scientific review, and user decision",
            "D4": "Pending post-WP2.1 characterization, independent scientific review, and user decision",
            "D5": "Pending WP1.1a evidence and explicit user approval",
            "D8": "Proposed - pending explicit user performance-budget approval",
        }
        for decision, status in frozen_statuses.items():
            with self.subTest(decision=decision):
                self.assertEqual(INVENTORY.EXPECTED_DECISIONS[decision], status)
                self.assertEqual(self.baseline["decisions"][decision], status)


if __name__ == "__main__":
    unittest.main()
