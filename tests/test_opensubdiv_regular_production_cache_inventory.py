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
        self.assertFalse(result["invalidation_seam_errors"])

    def test_topology_setups_use_one_private_invalidation_seam(self):
        mesh_header = (ROOT / inventory.MESH).read_text(encoding="utf-8")
        area = (ROOT / inventory.AREA).read_text(encoding="utf-8")
        setup = (ROOT / inventory.SETUP).read_text(encoding="utf-8")
        self.assertIn(ROOT / inventory.FORCE, inventory._other_cpp_paths())

        mutations = (
            (
                mesh_header.replace(
                    "regularLimitSurfaceRowCache_.invalidate();",
                    "// regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "invalidate_topology_derived_state();",
                    "// invalidate_topology_derived_state();",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "invalidate_topology_derived_state();",
                    "// invalidate_topology_derived_state();",
                    1,
                ),
            ),
            (
                mesh_header,
                area.replace(
                    "invalidate_topology_derived_state();",
                    "regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "invalidate_topology_derived_state();",
                    "#define FAKE_TOPOLOGY_CALL "
                    "invalidate_topology_derived_state();",
                    1,
                ),
                setup,
            ),
            (
                mesh_header.replace(
                    "regularLimitSurfaceRowCache_.invalidate();",
                    "// continued decoy " + chr(92) + "\n"
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "invalidate_topology_derived_state();",
                    "// continued decoy " + chr(92) + "\n"
                    "    invalidate_topology_derived_state();",
                    1,
                ),
                setup,
            ),
            (
                mesh_header.replace(
                    "regularLimitSurfaceRowCache_.invalidate();",
                    'const char* fake_reset = R"tag(" '
                    'regularLimitSurfaceRowCache_.invalidate(); " )tag";',
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "invalidate_topology_derived_state();",
                    'const char* fake_call = R"tag(" '
                    'invalidate_topology_derived_state(); " )tag";',
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "invalidate_topology_derived_state();",
                    'const char* fake_call = R"tag(" '
                    'invalidate_topology_derived_state(); " )tag";',
                    1,
                ),
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    "#if 0\n"
                    "        regularLimitSurfaceRowCache_.invalidate();\n"
                    "#endif",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "    invalidate_topology_derived_state();",
                    "#if 0\n"
                    "    invalidate_topology_derived_state();\n"
                    "#endif",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "    invalidate_topology_derived_state();",
                    "#if 1\n"
                    "    return;\n"
                    "#endif\n"
                    "    invalidate_topology_derived_state();",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "    invalidate_topology_derived_state();",
                    '#include "mesh/L7b_early_return.hpp"\n'
                    "    invalidate_topology_derived_state();",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "    invalidate_topology_derived_state();",
                    '#include "mesh/L7b_early_return.hpp"\n'
                    "    invalidate_topology_derived_state();",
                    1,
                ),
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    '#include "mesh/L7b_early_return.hpp"\n'
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "    void invalidate_topology_derived_state()",
                    '#include "mesh/L7b_public_access.hpp"\n'
                    "    void invalidate_topology_derived_state()",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "class Mesh",
                    '#include "/private/tmp/L7b_private_alias.hpp"\n'
                    "class Mesh",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    '#include "mesh/Mesh.hpp"',
                    '#include "mesh/Mesh.hpp"\n'
                    '#include "/private/tmp/L7b_private_alias.hpp"',
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "    invalidate_topology_derived_state();",
                    "%:if 1\n"
                    "    return;\n"
                    "%:endif\n"
                    "    invalidate_topology_derived_state();",
                    1,
                ),
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    "#ifdef __cplusplus\n"
                    "        return;\n"
                    "#endif\n"
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "void Mesh::setup_from_vertices_faces",
                    "#define invalidate_topology_derived_state() ((void)0)\n"
                    "void Mesh::setup_from_vertices_faces",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "void Mesh::setup_from_vertices_faces",
                    "%:define invalidate_topology_derived_state() ((void)0)\n"
                    "void Mesh::setup_from_vertices_faces",
                    1,
                ),
                setup,
            ),
            (
                mesh_header.replace(
                    "class Mesh",
                    "#define private public\nclass Mesh",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "class Mesh",
                    "#define max min\nclass Mesh",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "void Mesh::setup_flat",
                    "#define invalidate_topology_derived_state() ((void)0)\n"
                    "void Mesh::setup_flat",
                    1,
                ),
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "    invalidate_topology_derived_state();",
                    "#if 0\n"
                    "    invalidate_topology_derived_state();\n"
                    "#endif",
                    1,
                ),
            ),
            (
                mesh_header,
                area.replace(
                    "    invalidate_topology_derived_state();",
                    "    if (false) { "
                    "invalidate_topology_derived_state(); }",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "    invalidate_topology_derived_state();",
                    "    if (false) { "
                    "invalidate_topology_derived_state(); }",
                    1,
                ),
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    "        if (false) { "
                    "regularLimitSurfaceRowCache_.invalidate(); }",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    "        if (false) "
                    "regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    "        while (false) "
                    "regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    "        return;\n"
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();",
                    "        goto after_reset;\n"
                    "        regularLimitSurfaceRowCache_.invalidate();\n"
                    "        after_reset:",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "        ++topologyGeneration_;",
                    "        // ++topologyGeneration_;",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "invalidate_topology_derived_state();",
                    "regularLimitSurfaceRowCache_.invalidate();",
                    1,
                ),
            ),
            (
                mesh_header,
                area.replace(
                    "    invalidate_topology_derived_state();",
                    "    invalidate_topology_derived_state();\n"
                    "    --topologyGeneration_;",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "    invalidate_topology_derived_state();",
                    "    invalidate_topology_derived_state();\n"
                    "#define L7B_JOIN_I(a, b) a##b\n"
                    "#define L7B_JOIN(a, b) L7B_JOIN_I(a, b)\n"
                    "    --L7B_JOIN(topology, Generation_);",
                    1,
                ),
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "    invalidate_topology_derived_state();",
                    "    invalidate_topology_derived_state();\n"
                    "    --topologyGeneration_;",
                    1,
                ),
            ),
            (
                mesh_header,
                area.replace(
                    "invalidate_topology_derived_state();",
                    "invalidate_topology_derived_state();\n"
                    "    invalidate_topology_derived_state();",
                    1,
                ),
                setup,
            ),
            (
                mesh_header.replace(
                    "\nprivate:\n    /**\n"
                    "     * @brief Invalidate topology-derived state",
                    "\npublic:\n    /**\n"
                    "     * @brief Invalidate topology-derived state",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "\nprivate:\n    /**\n"
                    "     * @brief Invalidate topology-derived state",
                    "\npublic:\n"
                    "    class NestedAccessDecoy { private: int value; };\n"
                    "    /**\n"
                    "     * @brief Invalidate topology-derived state",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "\nprivate:\n    /**\n"
                    "     * @brief Invalidate topology-derived state",
                    "\nprotected:\n    /**\n"
                    "     * @brief Invalidate topology-derived state",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "    void invalidate_topology_derived_state()\n"
                    "    {",
                    "    // void invalidate_topology_derived_state()\n"
                    "    // {",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header.replace(
                    "        regularLimitSurfaceRowCache_.invalidate();\n",
                    "",
                    1,
                ).replace(
                    "    std::uint64_t topologyGeneration_ = 0;",
                    "    void misplaced_reset()\n"
                    "    {\n"
                    "        regularLimitSurfaceRowCache_.invalidate();\n"
                    "    }\n\n"
                    "    std::uint64_t topologyGeneration_ = 0;",
                    1,
                ),
                area,
                setup,
            ),
            (
                mesh_header,
                area.replace(
                    "    invalidate_topology_derived_state();\n",
                    "",
                    1,
                ) + "\nvoid misplaced_topology_invalidation()\n"
                "{\n"
                "    invalidate_topology_derived_state();\n"
                "}\n",
                setup,
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "invalidate_topology_derived_state();",
                    "invalidate_topology_derived_state();\n"
                    "    invalidate_topology_derived_state();",
                    1,
                ),
            ),
            (
                mesh_header,
                area,
                setup.replace(
                    "    invalidate_topology_derived_state();\n",
                    "",
                    1,
                ) + "\nvoid misplaced_flat_topology_invalidation()\n"
                "{\n"
                "    invalidate_topology_derived_state();\n"
                "}\n",
            ),
        )

        for mutated_header, mutated_area, mutated_setup in mutations:
            with self.subTest():
                self.assertTrue(
                    inventory.invalidation_seam_errors_for_sources(
                        mutated_header, mutated_area, mutated_setup
                    )
                )
        for extra_source in (
            "void Mesh::extra_caller() { invalidate_topology_derived_state(); }",
            "void Mesh::extra_reset() { regularLimitSurfaceRowCache_.invalidate(); }",
            "void Mesh::invalidate_topology_derived_state() {}",
            "void Mesh::clobber_generation() { ++topologyGeneration_; }",
            "#define L7B_JOIN_I(a, b) a##b\n"
            "#define L7B_JOIN(a, b) L7B_JOIN_I(a, b)\n"
            "void Mesh::clobber_generation() "
            "{ ++L7B_JOIN(topology, Generation_); }",
        ):
            with self.subTest(extra_source=extra_source):
                self.assertTrue(
                    inventory.invalidation_seam_errors_for_sources(
                        mesh_header, area, setup, (extra_source,)
                    )
                )

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
