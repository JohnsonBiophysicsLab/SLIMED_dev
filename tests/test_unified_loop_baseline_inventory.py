"""Mutation coverage for the fail-closed unified Loop baseline inventory."""

from __future__ import annotations

import copy
import importlib.util
import math
import re
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
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["legacy_11_control_predicate"]
            ["legacy_11_control_matrix_defect_assertion"]
            .update({"defect_confirmed": False}))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]["legacy_11_control_predicate"]
            ["wp1_1a_classifier_repair_record"]
            .update({"defect_confirmed": True}))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]
            ["legacy_11_control_predicate"]
            ["wp1_1a_classifier_repair_record"]
            .update({"required_active_source_contract_sha256": "0" * 64}))

        current_repair = self.baseline["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (current_repair["sentinel_initialization_observed"],
             current_repair["rejection_precedes_publication_observed"],
             current_repair["repair_confirmed"]),
            (False, False, False),
        )
        self.assertFalse(
            INVENTORY.validate_inventory(self.baseline, check_adr=False))

        original_text = INVENTORY._text
        classifier_source = """
LegacyOneRingClassification Mesh::classify_legacy_one_ring(
    const Face &face) const
{
    int d4 = -1;
    int d7 = -1;
    int d8 = -1;
    if (regular)
    {
        d4 = face.adjacentVertices[0];
        d7 = face.adjacentVertices[1];
        d8 = face.adjacentVertices[2];
    }
    else if (candidate)
    {
        d4 = face.adjacentVertices[0];
        d7 = face.adjacentVertices[1];
        d8 = face.adjacentVertices[2];
    }
    else
    {
        d4 = face.adjacentVertices[0];
        d7 = face.adjacentVertices[1];
        d8 = face.adjacentVertices[2];
    }
    result.orientedFaceVertices = {d4, d7, d8};
    std::swap(d7, d8);
    staged[3] = d4;
    staged[6] = d7;
    staged[7] = d8;
    const char marker = 'R';
    const char *rawReason =
        R"reason(INVALID_CORNER_VERTEX_INDEX)reason";
}
"""
        preflight_loop = """
    for (const Face &face : faces)
    {
        if (is_legacy_one_ring_rejection(classification.reasonCode))
        {
            const std::string message =
                "Legacy one-ring setup rejected face ";
            const char *reasonCodeName = "INVALID_CORNER_VERTEX_INDEX";
            throw std::runtime_error(message + reasonCodeName);
        }
    }
"""
        publication_loop = """
    for (std::size_t faceIndex = 0;
         faceIndex < faces.size(); ++faceIndex)
    {
        faces[faceIndex].adjacentVertices.swap(orientedFaceVertices);
        faces[faceIndex].oneRingVertices.swap(assembledOneRing);
    }
"""
        repaired_source = (
            '#include "mesh/Mesh.hpp"\n\n'
            'namespace repaired_fixture\n{\n}\n' + classifier_source + """
void Mesh::set_one_ring_vertices_sorted()
{
""" + preflight_loop + publication_loop + """
}
"""
        )
        _, repaired_contract_sha256, repaired_contract_is_unambiguous = (
            INVENTORY._reviewed_active_source_contract(repaired_source))
        self.assertTrue(repaired_contract_is_unambiguous)
        self.assertEqual(
            INVENTORY._reviewed_active_source_contract(
                repaired_source.replace(
                    "int d4 = -1;", "int   d4 = -1;", 1))[1],
            repaired_contract_sha256,
            "whitespace-only formatting changed the source contract",
        )
        self.assertNotEqual(
            INVENTORY._reviewed_active_source_contract(
                repaired_source.replace(
                    "int d4 = -1;", "intd4 = -1;", 1))[1],
            repaired_contract_sha256,
            "distinct C++ tokenization collapsed to the same source contract",
        )
        for equivalent_directive_source in (
                repaired_source.replace(
                    '#include "mesh/Mesh.hpp"',
                    '#include    "mesh/Mesh.hpp"', 1),
                repaired_source.replace(
                    '#include "mesh/Mesh.hpp"',
                    '#include "mesh/Mesh.hpp" // trailing comment', 1),
                repaired_source.replace(
                    '#include "mesh/Mesh.hpp"',
                    '#include \\\n    "mesh/Mesh.hpp"', 1)):
            self.assertEqual(
                INVENTORY._reviewed_active_source_contract(
                    equivalent_directive_source)[1],
                repaired_contract_sha256,
                "semantically equivalent directive formatting changed digest",
            )
        literal_fixture = r'''
auto ordinary = u8"slash\\quote\"";
auto character = U'\x5a';
auto raw = LR"tag(raw // /* " bytes)tag"_suffix;
// u8"comment literal"
/* R"(block comment literal)" */
'''
        _, _, literal_tokens, literal_fixture_is_complete, _ = (
            INVENTORY._cpp_lexical_surfaces(literal_fixture))
        self.assertTrue(literal_fixture_is_complete)
        self.assertEqual(
            [token for _, _, token in literal_tokens],
            [r'u8"slash\\quote\""', r"U'\x5a'",
             r'LR"tag(raw // /* " bytes)tag"_suffix'],
        )

        def collect_with_topology(source):
            def source_text(path):
                if path == "src/mesh/Mesh_setup_geometry.cpp":
                    return source
                return original_text(path)

            with mock.patch.object(
                    INVENTORY, "_text", side_effect=source_text), \
                    mock.patch.object(
                        INVENTORY, "_topology_invalidation_seam_errors",
                        return_value=[]), \
                    mock.patch.object(
                        INVENTORY,
                        "REVIEWED_MESH_SETUP_GEOMETRY_ACTIVE_SOURCE_SHA256",
                        repaired_contract_sha256):
                return INVENTORY.collect_inventory()

        def validate_topology(report):
            with mock.patch.object(
                    INVENTORY,
                    "REVIEWED_MESH_SETUP_GEOMETRY_ACTIVE_SOURCE_SHA256",
                    repaired_contract_sha256):
                return INVENTORY.validate_inventory(report, check_adr=False)

        def observe_topology(source):
            with mock.patch.object(
                    INVENTORY,
                    "REVIEWED_MESH_SETUP_GEOMETRY_ACTIVE_SOURCE_SHA256",
                    repaired_contract_sha256):
                return INVENTORY._legacy_classifier_repair_observations(source)

        repaired_report = collect_with_topology(repaired_source)
        repaired_record = repaired_report["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (repaired_record["sentinel_initialization_observed"],
             repaired_record["rejection_precedes_publication_observed"],
             repaired_record["repair_confirmed"]),
            (True, True, True),
        )
        self.assertFalse(validate_topology(repaired_report))
        self.assertEqual(
            repaired_record[
                "required_active_classifier_identifier_occurrences"],
            {"d4": 6, "d7": 7, "d8": 7},
        )
        self.assertEqual(
            repaired_record["required_active_source_contract_sha256"],
            repaired_contract_sha256,
        )
        tampered_contract = copy.deepcopy(repaired_report)
        tampered_contract["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"] \
            ["required_active_source_contract_sha256"] = "0" * 64
        self.assertTrue(validate_topology(tampered_contract))
        include_drift_report = collect_with_topology(
            repaired_source.replace(
                '"mesh/Mesh.hpp"', '"mesh/Other.hpp"', 1))
        include_drift_record = include_drift_report["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (include_drift_record["sentinel_initialization_observed"],
             include_drift_record[
                 "rejection_precedes_publication_observed"],
             include_drift_record["repair_confirmed"]),
            (False, False, False),
        )
        self.assertFalse(validate_topology(include_drift_report))
        self.assert_mutation_rejected(
            lambda r: r["D_topology_guards"]
            ["legacy_11_control_predicate"]
            ["wp1_1a_classifier_repair_record"]
            ["required_active_classifier_identifier_occurrences"]
            .update({"d4": 7}))

        rejection_line = (
            "        if (is_legacy_one_ring_rejection("
            "classification.reasonCode))")
        publication_mutations = [
            "faces[0].{field}.clear();",
            "faces[0].{field}.push_back(0);",
            "faces[0].{field} = {{}};",
            "faces[0].{field}[0] = 0;",
        ]
        for field in ("adjacentVertices", "oneRingVertices"):
            for mutation in publication_mutations:
                extra_write_source = repaired_source.replace(
                    rejection_line,
                    "        " + mutation.format(field=field) + "\n" +
                    rejection_line,
                    1)
                extra_write_report = collect_with_topology(extra_write_source)
                extra_write_record = extra_write_report["D_topology_guards"] \
                    ["legacy_11_control_predicate"] \
                    ["wp1_1a_classifier_repair_record"]
                self.assertEqual(
                    (extra_write_record["sentinel_initialization_observed"],
                     extra_write_record[
                         "rejection_precedes_publication_observed"],
                     extra_write_record["repair_confirmed"]),
                    (False, False, False),
                    f"active preflight mutation escaped: {field} {mutation}",
                )
                self.assertFalse(validate_topology(extra_write_report))

        masked_mutations = [
            "#if 0\n"
            "        faces[0].adjacentVertices.clear();\n"
            "#endif\n",
            "#if (0)\n"
            "        faces[0].adjacentVertices.clear();\n"
            "#endif\n",
            "#if 0\n"
            "        const auto hidden = R\"tag(inactive)tag\";\n"
            "#endif\n",
            "%:if 0\n"
            "        faces[0].adjacentVertices.clear();\n"
            "%:endif\n",
            "        // faces[0].oneRingVertices.clear(); "
            "\"ignored literal\" 'x' R\"(ignored raw)\"\n",
        ]
        for mutation in masked_mutations:
            masked_write_report = collect_with_topology(
                repaired_source.replace(
                    rejection_line, mutation + rejection_line, 1))
            masked_write_record = masked_write_report["D_topology_guards"] \
                ["legacy_11_control_predicate"] \
                ["wp1_1a_classifier_repair_record"]
            self.assertEqual(
                (masked_write_record["sentinel_initialization_observed"],
                 masked_write_record[
                     "rejection_precedes_publication_observed"],
                 masked_write_record["repair_confirmed"]),
                (True, True, True),
            )
            self.assertFalse(validate_topology(masked_write_report))

        duplicate_sentinel_report = collect_with_topology(
            repaired_source.replace(
                "int d4 = -1;", "int d4 = -1;\n    int d4 = -1;", 1))
        duplicate_sentinel_record = duplicate_sentinel_report[
            "D_topology_guards"]["legacy_11_control_predicate"][
                "wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (duplicate_sentinel_record["sentinel_initialization_observed"],
             duplicate_sentinel_record[
                 "rejection_precedes_publication_observed"],
             duplicate_sentinel_record["repair_confirmed"]),
            (False, False, False),
        )
        self.assertFalse(validate_topology(duplicate_sentinel_report))

        for name in ("d4", "d7", "d8"):
            nested_declaration_source = repaired_source.replace(
                f"    int {name} = -1;",
                f"    int {name} = -1;\n"
                f"    if (nested) {{ int spare, {name}; }}",
                1)
            nested_declaration_report = collect_with_topology(
                nested_declaration_source)
            nested_declaration_record = nested_declaration_report[
                "D_topology_guards"]["legacy_11_control_predicate"][
                    "wp1_1a_classifier_repair_record"]
            self.assertEqual(
                (nested_declaration_record[
                     "sentinel_initialization_observed"],
                 nested_declaration_record[
                     "rejection_precedes_publication_observed"],
                 nested_declaration_record["repair_confirmed"]),
                (False, False, False),
                f"nested declaration escaped: {name}",
            )
            self.assertFalse(validate_topology(nested_declaration_report))

            for declaration in (
                    f"int {name}(0);",
                    f"int {name}{{0}};",
                    f"decltype(0) {name};",
                    f"auto [{name}, spare] = pair;",
                    f"using {name} = int;"):
                extra_identifier_source = repaired_source.replace(
                    f"    int {name} = -1;",
                    f"    int {name} = -1;\n"
                    f"    if (nested) {{ {declaration} }}",
                    1)
                self.assertEqual(
                    observe_topology(extra_identifier_source),
                    (False, False),
                    f"active extra identifier escaped: {declaration}",
                )

            masked_identifier_sources = (
                repaired_source.replace(
                    f"    int {name} = -1;",
                    f"    int {name} = -1;\n"
                    f"    // int {name}(0);",
                    1),
                repaired_source.replace(
                    f"    int {name} = -1;",
                    f"    int {name} = -1;\n"
                    f"#if 0\n    int {name}(0);\n#endif",
                    1),
            )
            for masked_identifier_source in masked_identifier_sources:
                self.assertEqual(
                    observe_topology(masked_identifier_source),
                    (True, True),
                    f"masked identifier affected observation: {name}",
                )

        macro_alias_source = (
            "#define ADJACENT_FIELD adjacentVertices\n"
            "#define ONE_RING_FIELD oneRingVertices\n" +
            repaired_source.replace(
                rejection_line,
                "        faces[0].ADJACENT_FIELD.clear();\n"
                "        faces[0].ONE_RING_FIELD.clear();\n" +
                rejection_line,
                1))
        macro_alias_report = collect_with_topology(macro_alias_source)
        macro_alias_record = macro_alias_report["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (macro_alias_record["sentinel_initialization_observed"],
             macro_alias_record[
                 "rejection_precedes_publication_observed"],
             macro_alias_record["repair_confirmed"]),
            (False, False, False),
        )
        self.assertFalse(validate_topology(macro_alias_report))

        for masked_macro_prefix in (
                "// #define ADJACENT_FIELD adjacentVertices\n",
                "#if 0\n#define ADJACENT_FIELD adjacentVertices\n#endif\n"):
            self.assertEqual(
                observe_topology(masked_macro_prefix + repaired_source),
                (True, True),
                "masked macro directive affected repair observation",
            )

        def assert_repair_state(source, expected, message):
            report = collect_with_topology(source)
            record = report["D_topology_guards"] \
                ["legacy_11_control_predicate"] \
                ["wp1_1a_classifier_repair_record"]
            self.assertEqual(
                (record["sentinel_initialization_observed"],
                 record["rejection_precedes_publication_observed"],
                 record["repair_confirmed"]),
                expected,
                message,
            )
            self.assertFalse(validate_topology(report))

        literal_mutations = (
            ('"Legacy one-ring setup rejected face "',
             '"Legacy one-ring setup rejected edge "'),
            ('"INVALID_CORNER_VERTEX_INDEX"',
             '"INVALID_CORNER_VERTEX_ID"'),
            ("'R'", "'S'"),
            ('R"reason(INVALID_CORNER_VERTEX_INDEX)reason"',
             'R"reason(INVALID_CORNER_VERTEX_ID)reason"'),
        )
        for old_literal, new_literal in literal_mutations:
            literal_mutation_source = repaired_source.replace(
                old_literal, new_literal, 1)
            self.assertNotEqual(literal_mutation_source, repaired_source)
            self.assertNotEqual(
                INVENTORY._reviewed_active_source_contract(
                    literal_mutation_source)[1],
                repaired_contract_sha256,
                f"active literal mutation escaped digest: {old_literal}",
            )
            assert_repair_state(
                literal_mutation_source,
                (False, False, False),
                f"active literal mutation escaped repair state: {old_literal}",
            )

        joined_directive_source = repaired_source.replace(
            '#include "mesh/Mesh.hpp"\n\nnamespace',
            '#include "mesh/Mesh.hpp" namespace',
            1)
        self.assertNotEqual(joined_directive_source, repaired_source)
        self.assertNotEqual(
            INVENTORY._reviewed_active_source_contract(
                joined_directive_source)[1],
            repaired_contract_sha256,
            "directive/code line-boundary mutation escaped digest",
        )
        assert_repair_state(
            joined_directive_source,
            (False, False, False),
            "directive/code line-boundary mutation escaped repair state",
        )

        block_comment_join_source = repaired_source.replace(
            '#include "mesh/Mesh.hpp"\n\nnamespace',
            '#include "mesh/Mesh.hpp" /*\n*/ namespace',
            1)
        self.assertNotEqual(block_comment_join_source, repaired_source)
        self.assertNotEqual(
            INVENTORY._reviewed_active_source_contract(
                block_comment_join_source)[1],
            repaired_contract_sha256,
            "multiline block comment preserved a directive boundary",
        )
        assert_repair_state(
            block_comment_join_source,
            (False, False, False),
            "multiline block-comment join escaped repair state",
        )

        block_comment_join_variants = (
            '#include "mesh/Mesh.hpp" /*\n\n\n*/ namespace',
            '#include "mesh/Mesh.hpp" /*\\\n\n*/ namespace',
        )
        for joined_include in block_comment_join_variants:
            joined_source = repaired_source.replace(
                '#include "mesh/Mesh.hpp"\n\nnamespace',
                joined_include,
                1)
            self.assertNotEqual(
                INVENTORY._reviewed_active_source_contract(joined_source)[1],
                repaired_contract_sha256,
                "block-comment newline family escaped phase-3 digest",
            )
            self.assertEqual(
                observe_topology(joined_source),
                (False, False),
                "block-comment newline family escaped observations",
            )

        safe_block_comment_sources = (
            repaired_source.replace(
                "int d4 = -1;",
                "int/* first comment line\n\nthird comment line */d4 = -1;",
                1),
            "/* standalone comment\n\nwith multiple new-lines */\n" +
            repaired_source,
            repaired_source +
            "\n/* trailing standalone\n\nblock comment */",
            repaired_source.replace(
                "int d4 = -1;",
                "int/* multiline\nblock comment */ // real line boundary\n"
                "d4 = -1;",
                1),
        )
        for safe_block_comment_source in safe_block_comment_sources:
            self.assertEqual(
                INVENTORY._reviewed_active_source_contract(
                    safe_block_comment_source)[1],
                repaired_contract_sha256,
                "safe multiline block comment changed phase-3 digest",
            )
            assert_repair_state(
                safe_block_comment_source,
                (True, True, True),
                "safe multiline block comment changed repair state",
            )

        pragma_control = (
            "int b0d_before_pragma = 0;\n#pragma b0d_probe\n" +
            repaired_source)
        pragma_join = (
            "int b0d_before_pragma = 0; /*\n*/ #pragma b0d_probe\n" +
            repaired_source)
        self.assertNotEqual(
            INVENTORY._reviewed_active_source_contract(pragma_join)[1],
            INVENTORY._reviewed_active_source_contract(pragma_control)[1],
            "ordinary-code/#pragma phase-3 join preserved digest",
        )
        self.assertEqual(
            observe_topology(pragma_join),
            (False, False),
            "ordinary-code/#pragma phase-3 join escaped observations",
        )

        for horizontal_line_character in ("\v", "\f"):
            horizontal_join_source = repaired_source.replace(
                '#include "mesh/Mesh.hpp"\n\nnamespace',
                '#include "mesh/Mesh.hpp"' +
                horizontal_line_character + "namespace",
                1)
            self.assertNotEqual(
                INVENTORY._reviewed_active_source_contract(
                    horizontal_join_source)[1],
                repaired_contract_sha256,
                "VT/FF incorrectly split a directive logical line",
            )
            assert_repair_state(
                horizontal_join_source,
                (False, False, False),
                "VT/FF directive-boundary mutation escaped repair state",
            )

        unicode_whitespace_source = repaired_source.replace(
            "int d4 = -1;", "int\u00a0d4 = -1;", 1)
        self.assertNotEqual(
            INVENTORY._reviewed_active_source_contract(
                unicode_whitespace_source)[1],
            repaired_contract_sha256,
            "Unicode whitespace collapsed with ASCII C++ whitespace",
        )
        assert_repair_state(
            unicode_whitespace_source,
            (False, False, False),
            "Unicode whitespace mutation escaped repair state",
        )

        unicode_boundary_sources = (
            "\u00a0" + repaired_source,
            repaired_source + "\u00a0",
        )
        for unicode_boundary_source in unicode_boundary_sources:
            self.assertNotEqual(
                INVENTORY._reviewed_active_source_contract(
                    unicode_boundary_source)[1],
                repaired_contract_sha256,
                "leading/trailing Unicode whitespace escaped digest",
            )
            assert_repair_state(
                unicode_boundary_source,
                (False, False, False),
                "leading/trailing Unicode whitespace escaped repair state",
            )

        unicode_directive_sources = (
            "#if\u00a00\nint hidden_by_nbsp = does_not_compile;\n"
            "#endif\n" + repaired_source,
            "#\u00a0if 0\nint hidden_by_nbsp = does_not_compile;\n"
            "#endif\n" + repaired_source,
        )
        for unicode_directive_source in unicode_directive_sources:
            self.assertNotEqual(
                INVENTORY._reviewed_active_source_contract(
                    unicode_directive_source)[1],
                repaired_contract_sha256,
                "Unicode directive whitespace escaped digest",
            )
            assert_repair_state(
                unicode_directive_source,
                (False, False, False),
                "Unicode directive whitespace escaped repair state",
            )

        for newline in ("\r\n", "\r"):
            equivalent_newlines_source = repaired_source.replace("\n", newline)
            self.assertEqual(
                INVENTORY._reviewed_active_source_contract(
                    equivalent_newlines_source)[1],
                repaired_contract_sha256,
                "equivalent C++ new-line spelling changed digest",
            )
            assert_repair_state(
                equivalent_newlines_source,
                (True, True, True),
                "equivalent C++ new-line spelling changed repair state",
            )

        publication_signature = (
            "void Mesh::set_one_ring_vertices_sorted()\n{\n")
        out_of_scope_helper_source = """
void mutate_publication_fields_before_preflight(std::vector<Face> &faces)
{
    faces[0].adjacentVertices.clear();
    faces[0].oneRingVertices.clear();
}
""" + repaired_source.replace(
            publication_signature,
            publication_signature +
            "    mutate_publication_fields_before_preflight(faces);\n",
            1)
        assert_repair_state(
            out_of_scope_helper_source,
            (False, False, False),
            "out-of-scope publication helper escaped the source contract",
        )

        count_preserving_source = repaired_source.replace(
            "    staged[3] = d4;",
            "    { int d4; staged[3] = 0; }",
            1)
        count_preserving_active = (
            INVENTORY._reviewed_active_source_contract(
                count_preserving_source)[0])
        count_preserving_classifier = INVENTORY._unique_braced_scope_span(
            count_preserving_active,
            r"\bLegacyOneRingClassification\s+"
            r"Mesh::classify_legacy_one_ring\s*"
            r"\(\s*const\s+Face\s*&\s*face\s*\)\s*const\s*\{")
        self.assertIsNotNone(count_preserving_classifier)
        self.assertEqual(
            len(re.findall(
                r"\bd4\b", count_preserving_classifier[3])),
            6,
            "adversary did not preserve the reviewed d4 token count",
        )
        assert_repair_state(
            count_preserving_source,
            (False, False, False),
            "count-preserving nested d4 declaration escaped the contract",
        )

        ambiguous_conditionals = (
            "#if 1\nint conditionally_active_helper = 0;\n#endif\n",
            "#if 0\nint inactive_helper = 0;\n"
            "#else\nint potentially_active_helper = 0;\n#endif\n",
            "#endif\n",
        )
        for conditional_prefix in ambiguous_conditionals:
            conditional_source = conditional_prefix + repaired_source
            self.assertFalse(
                INVENTORY._reviewed_active_source_contract(
                    conditional_source)[2],
                "potentially active conditional was not ambiguous",
            )
            assert_repair_state(
                conditional_source,
                (False, False, False),
                "potentially active conditional escaped the contract",
            )

        trigraph_source = (
            "??=if 0\n"
            "int b0d_trigraph_hidden_but_cpp17_active = does_not_compile;\n"
            "??=endif\n" + repaired_source)
        self.assertNotEqual(
            INVENTORY._reviewed_active_source_contract(trigraph_source)[1],
            repaired_contract_sha256,
            "C++17-active trigraph spelling escaped the source digest",
        )
        assert_repair_state(
            trigraph_source,
            (False, False, False),
            "C++17-active trigraph spelling escaped repair state",
        )

        misordered_source = classifier_source + """
void Mesh::set_one_ring_vertices_sorted()
{
""" + publication_loop + preflight_loop + """
}
"""
        misordered_report = collect_with_topology(misordered_source)
        misordered_record = misordered_report["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (misordered_record["sentinel_initialization_observed"],
             misordered_record["rejection_precedes_publication_observed"],
             misordered_record["repair_confirmed"]),
            (False, False, False),
        )
        self.assertFalse(validate_topology(misordered_report))

        inactive_fake_report = collect_with_topology(
            "#if 0\n" + repaired_source + "#endif\n" +
            original_text("src/mesh/Mesh_setup_geometry.cpp"))
        inactive_fake_record = inactive_fake_report["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (inactive_fake_record["sentinel_initialization_observed"],
             inactive_fake_record[
                 "rejection_precedes_publication_observed"],
             inactive_fake_record["repair_confirmed"]),
            (False, False, False),
        )
        self.assertFalse(validate_topology(inactive_fake_report))

        detached_preflight = preflight_loop.replace(
            "        {\n"
            "            throw std::runtime_error(message);\n"
            "        }",
            "        {\n"
            "        }\n"
            "        throw std::runtime_error(message);", 1)
        detached_throw_source = classifier_source + """
void Mesh::set_one_ring_vertices_sorted()
{
""" + detached_preflight + publication_loop + """
}
"""
        detached_throw_report = collect_with_topology(detached_throw_source)
        detached_throw_record = detached_throw_report["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"]
        self.assertEqual(
            (detached_throw_record["sentinel_initialization_observed"],
             detached_throw_record[
                 "rejection_precedes_publication_observed"],
             detached_throw_record["repair_confirmed"]),
            (False, False, False),
        )
        self.assertFalse(validate_topology(detached_throw_report))

        inconsistent_current = copy.deepcopy(self.baseline)
        inconsistent_current["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"] \
            ["repair_confirmed"] = True
        self.assertTrue(INVENTORY.validate_inventory(
            inconsistent_current, check_adr=False))
        inconsistent_repaired = copy.deepcopy(repaired_report)
        inconsistent_repaired["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"] \
            ["repair_confirmed"] = False
        self.assertTrue(validate_topology(inconsistent_repaired))
        non_boolean = copy.deepcopy(self.baseline)
        non_boolean["D_topology_guards"] \
            ["legacy_11_control_predicate"] \
            ["wp1_1a_classifier_repair_record"] \
            ["sentinel_initialization_observed"] = "false"
        self.assertTrue(INVENTORY.validate_inventory(
            non_boolean, check_adr=False))

        def collapse_legacy_11_control_split(report) -> None:
            legacy = report["D_topology_guards"]["legacy_11_control_predicate"]
            legacy.pop("legacy_11_control_matrix_defect_assertion")
            legacy.pop("wp1_1a_classifier_repair_record")
            legacy["defect_confirmed"] = True

        self.assert_mutation_rejected(collapse_legacy_11_control_split)

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
            "src/mesh/Loop_topology_transaction.cpp",
            lambda text: text.replace(
                "        mesh_.invalidate_topology_derived_state();",
                "        // mesh_.invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Loop_topology_transaction.cpp",
            lambda text: text.replace(
                "        mesh_.invalidate_topology_derived_state();",
                "        if (false) { "
                "mesh_.invalidate_topology_derived_state(); }", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Loop_topology_transaction.cpp",
            lambda text: text.replace(
                "        mesh_.invalidate_topology_derived_state();",
                "        return result("
                "LoopTopologyTransactionReason::none);\n"
                "        mesh_.invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Loop_topology_transaction.cpp",
            lambda text: text.replace(
                "\n    try\n    {",
                "\n    return result("
                "LoopTopologyTransactionReason::none);\n\n"
                "    try\n    {", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Loop_topology_transaction.cpp",
            lambda text: text.replace(
                "\n    try\n    {",
                "\n    goto after_invalidation;\n\n"
                "    try\n    {", 1).replace(
                    "\n    for (std::size_t face = 0;",
                    "\nafter_invalidation:\n"
                    "    for (std::size_t face = 0;", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Loop_topology_transaction.cpp",
            lambda text: text.replace(
                "        mesh_.invalidate_topology_derived_state();",
                "#if 0\n"
                "        mesh_.invalidate_topology_derived_state();\n"
                "#endif", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Loop_topology_transaction.cpp",
            lambda text: text.replace(
                "        mesh_.invalidate_topology_derived_state();",
                '#include "mesh/L7c_early_return.hpp"\n'
                "        mesh_.invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                '#include "mesh/Loop_topology_transaction.hpp"',
                '// transaction definition include removed', 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;",
                "    // transaction friendship removed", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "private:\n    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;",
                "public:\n#pragma private:\n"
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "regularLimitSurfaceRowCache_.invalidate();",
                'const char* fake_reset = R"tag(" '
                'regularLimitSurfaceRowCache_.invalidate(); " )tag";', 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                'const char* fake_call = R"tag(" '
                'invalidate_topology_derived_state(); " )tag";', 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "#define FAKE_TOPOLOGY_CALL "
                "invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "regularLimitSurfaceRowCache_.invalidate();",
                "// continued decoy " + chr(92) + "\n"
                "        regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "// continued decoy " + chr(92) + "\n"
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                'const char* fake_call = R"tag(" '
                'invalidate_topology_derived_state(); " )tag";', 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                "#if 0\n"
                "        regularLimitSurfaceRowCache_.invalidate();\n"
                "#endif", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "#if 0\n"
                "    invalidate_topology_derived_state();\n"
                "#endif", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "#if 0\n"
                "    invalidate_topology_derived_state();\n"
                "#endif", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "#if 1\n"
                "    return;\n"
                "#endif\n"
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                '#include "mesh/L7b_early_return.hpp"\n'
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                '#include "mesh/L7b_early_return.hpp"\n'
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                '#include "mesh/L7b_early_return.hpp"\n'
                "        regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "    void invalidate_topology_derived_state()",
                '#include "mesh/L7b_public_access.hpp"\n'
                "    void invalidate_topology_derived_state()", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "    void invalidate_topology_derived_state()",
                '#import "mesh/L7b_public_access.hpp"\n'
                "    void invalidate_topology_derived_state()", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                '%:include_next "mesh/L7b_early_return.hpp"\n'
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "class Mesh",
                '#include "/private/tmp/L7b_private_alias.hpp"\n'
                "class Mesh", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                '#include "mesh/Mesh.hpp"',
                '#include "mesh/Mesh.hpp"\n'
                '#include "/private/tmp/L7b_private_alias.hpp"', 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "%:if 1\n"
                "    return;\n"
                "%:endif\n"
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                "#ifdef __cplusplus\n"
                "        return;\n"
                "#endif\n"
                "        regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "void Mesh::setup_from_vertices_faces",
                "#define invalidate_topology_derived_state() ((void)0)\n"
                "void Mesh::setup_from_vertices_faces", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "void Mesh::setup_flat",
                "#define invalidate_topology_derived_state() ((void)0)\n"
                "void Mesh::setup_flat", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "void Mesh::setup_from_vertices_faces",
                "%:define invalidate_topology_derived_state() ((void)0)\n"
                "void Mesh::setup_from_vertices_faces", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "class Mesh", "#define private public\nclass Mesh", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "class Mesh", "#define max min\nclass Mesh", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "    if (false) { invalidate_topology_derived_state(); }", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "    if (false) { invalidate_topology_derived_state(); }", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                "        if (false) { "
                "regularLimitSurfaceRowCache_.invalidate(); }", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                "        if (false) "
                "regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                "        while (false) "
                "regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                "        return;\n"
                "        regularLimitSurfaceRowCache_.invalidate();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        regularLimitSurfaceRowCache_.invalidate();",
                "        goto after_reset;\n"
                "        regularLimitSurfaceRowCache_.invalidate();\n"
                "        after_reset:", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "        ++topologyGeneration_;",
                "        // ++topologyGeneration_;", 1))
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
                "    invalidate_topology_derived_state();",
                "    invalidate_topology_derived_state();\n"
                "    --topologyGeneration_;", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh_setup_flat.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "    invalidate_topology_derived_state();\n"
                "    --topologyGeneration_;", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "    invalidate_topology_derived_state();",
                "    invalidate_topology_derived_state();\n"
                "#define L7B_JOIN_I(a, b) a##b\n"
                "#define L7B_JOIN(a, b) L7B_JOIN_I(a, b)\n"
                "    --L7B_JOIN(topology, Generation_);", 1))
        self.assert_text_mutation_rejected(
            "src/mesh/Mesh.cpp",
            lambda text: text.replace(
                "invalidate_topology_derived_state();",
                "invalidate_topology_derived_state();\n"
                "    invalidate_topology_derived_state();", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "\nprivate:\n"
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;\n\n    /**\n"
                "     * @brief Invalidate topology-derived state",
                "\npublic:\n"
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;\n\n    /**\n"
                "     * @brief Invalidate topology-derived state", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "\nprivate:\n"
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;\n\n    /**\n"
                "     * @brief Invalidate topology-derived state",
                "\npublic:\n"
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;\n"
                "    class NestedAccessDecoy { private: int value; };\n"
                "    /**\n"
                "     * @brief Invalidate topology-derived state", 1))
        self.assert_text_mutation_rejected(
            "include/mesh/Mesh.hpp",
            lambda text: text.replace(
                "\nprivate:\n"
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;\n\n    /**\n"
                "     * @brief Invalidate topology-derived state",
                "\nprotected:\n"
                "    friend class slimed::loop_topology::"
                "LoopTopologyTransaction;\n\n    /**\n"
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
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text +
                "\nvoid Mesh::extra_topology_invalidation()\n"
                "{\n"
                "    invalidate_topology_derived_state();\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text +
                "\nvoid Mesh::extra_cache_reset()\n"
                "{\n"
                "    regularLimitSurfaceRowCache_.invalidate();\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text +
                "\nvoid Mesh::clobber_topology_generation()\n"
                "{\n"
                "    ++topologyGeneration_;\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text +
                "\n#define L7B_JOIN_I(a, b) a##b\n"
                "#define L7B_JOIN(a, b) L7B_JOIN_I(a, b)\n"
                "void Mesh::clobber_topology_generation()\n"
                "{\n"
                "    ++L7B_JOIN(topology, Generation_);\n"
                "}\n")
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: text.replace(
                "void Mesh::clear_force_on_vertices_and_energy_on_faces()\n"
                "{",
                "void Mesh::clear_force_on_vertices_and_energy_on_faces()\n"
                "{\n"
                '#include "/private/tmp/L7b_clobber.inc"', 1))
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: '#import "/private/tmp/L7b_clobber.inc"\n' + text)
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: '#/**/import "/private/tmp/L7b_clobber.inc"\n'
            + text)
        self.assert_text_mutation_rejected(
            "src/energy_force/Compute_energy_and_force_on_mesh.cpp",
            lambda text: '/**/ #include "/private/tmp/L7b_clobber.inc"\n'
            + text)
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
