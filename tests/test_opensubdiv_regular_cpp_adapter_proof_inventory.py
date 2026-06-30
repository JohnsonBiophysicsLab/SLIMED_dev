import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inventory_opensubdiv_regular_cpp_adapter_proof.py"
)
SPEC = importlib.util.spec_from_file_location(
    "inventory_opensubdiv_regular_cpp_adapter_proof", SCRIPT_PATH
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class OpenSubdivRegularCppAdapterProofInventoryTest(unittest.TestCase):
    def test_cpp_proof_covers_weighted_sample_invariants(self):
        invariants = {row["invariant"]: row["needle"] for row in inventory.CPP_PROOF_INVARIANTS}
        source = (inventory.repo_root() / inventory.CPP_PROOF_PATH).read_text(encoding="utf-8")

        self.assertIn("proof-only kind", invariants)
        self.assertIn("original source ids", invariants)
        self.assertIn("duplicate aggregation", invariants)
        self.assertIn("frozen sample coordinates", invariants)
        self.assertIn("quadrature formula factor", invariants)
        self.assertIn("s=v,t=w convention", invariants)
        self.assertIn("seven derivative rows", invariants)
        self.assertIn("duplicated mixed row convention", invariants)
        self.assertIn("actual force rows", invariants)
        self.assertIn("fBend evidence", invariants)
        self.assertIn("fArea evidence", invariants)
        self.assertIn("fVolume evidence", invariants)
        self.assertIn("proof-only force algebra", invariants)
        self.assertIn("one-ring scatter identity", invariants)
        self.assertIn("production-call shadow", invariants)
        self.assertIn("production coordinate input order", invariants)
        self.assertIn("production force buffer layout", invariants)
        self.assertIn("production shadow pass flag", invariants)
        self.assertIn("production helper dry run", invariants)
        self.assertIn("production helper API", invariants)
        self.assertIn("OpenSubdiv rows installed locally", invariants)
        self.assertIn("default dependency unchanged", invariants)
        self.assertIn("no production route installed", invariants)
        self.assertIn("production helper dry-run pass flag", invariants)
        self.assertIn("visible observable dry run", invariants)
        self.assertIn("visible observable production API", invariants)
        self.assertIn("visible area evidence", invariants)
        self.assertIn("legacy visible volume evidence", invariants)
        self.assertIn("visible observable pass flag", invariants)
        self.assertIn("serial OpenMP accumulation parity", invariants)
        self.assertIn("serial OpenMP production shape reference", invariants)
        self.assertIn("serial OpenMP pass flag", invariants)
        self.assertIn("not production routing", invariants)
        for needle in invariants.values():
            self.assertIn(needle, source)

    def test_cpp_proof_covers_regular_production_call_shadow_shape(self):
        source = (inventory.repo_root() / inventory.CPP_PROOF_PATH).read_text(encoding="utf-8")

        self.assertIn('\\"production_call_shadow\\":{', source)
        self.assertIn("kProductionRegularControlPointCount = 12", source)
        self.assertIn("kProductionDerivativeRowCount = 7", source)
        self.assertIn("kProductionSpatialDimension = 3", source)
        self.assertIn("kProductionForceComponentsPerVertex = 9", source)
        self.assertIn("coordOneRingVertices[j] copied from Face::oneRingVertices[j]", source)
        self.assertIn("row j -> Face::oneRingVertices[j]", source)
        self.assertIn("productionCallShadowPassed", source)

    def test_cpp_proof_covers_regular_production_helper_dry_run(self):
        source = (inventory.repo_root() / inventory.CPP_PROOF_PATH).read_text(encoding="utf-8")

        self.assertIn('\\"production_helper_dry_run\\":{', source)
        self.assertIn("run_regular_production_helper_dry_run", source)
        self.assertIn("Mesh::element_energy_force_regular", source)
        self.assertIn("productionMesh.param.shapeFunctions.clear()", source)
        self.assertIn("make_shape_function_matrix", source)
        self.assertIn("open_subdiv_rows_used_as_local_shape_functions", source)
        self.assertIn("default_build_dependency_added", source)
        self.assertIn("route_installed_in_production", source)
        self.assertIn("max_force_row_difference_vs_proof_local_formula", source)
        self.assertIn("matches_proof_local_formula_rows", source)

    def test_cpp_proof_covers_regular_visible_observable_dry_run(self):
        source = (inventory.repo_root() / inventory.CPP_PROOF_PATH).read_text(encoding="utf-8")

        self.assertIn('\\"visible_observable_dry_run\\":{', source)
        self.assertIn("run_regular_visible_observable_dry_run", source)
        self.assertIn("Mesh::calculate_element_area_volume regular 12-control path", source)
        self.assertIn("productionMesh.calculate_element_area_volume()", source)
        self.assertIn("legacy_visible_volume", source)
        self.assertIn("force_fixture_full_dot_volume", source)
        self.assertIn("max_area_volume_difference_vs_production_regular_path", source)
        self.assertIn("matches_production_regular_area_volume", source)

    def test_cpp_proof_covers_serial_openmp_accumulation_parity(self):
        source = (inventory.repo_root() / inventory.CPP_PROOF_PATH).read_text(encoding="utf-8")

        self.assertIn('\\"serial_openmp_accumulation_parity\\":{', source)
        self.assertIn("run_serial_openmp_accumulation_parity_proof", source)
        self.assertIn("proof-local serial versus OpenMP-style per-thread force-buffer accumulation", source)
        self.assertIn("accumulate_membrane_face_energy_and_forces per-thread nVertices*9 buffers", source)
        self.assertIn("add_rows_to_production_force_buffer", source)
        self.assertIn("simulated_openmp_thread_buffers", source)
        self.assertIn("max_serial_openmp_accumulation_difference", source)
        self.assertIn("matches_serial_openmp_accumulation_shape", source)
        self.assertIn("route_installed_in_production", source)

    def test_wrapper_is_explicit_opensubdiv_root_only(self):
        source = (inventory.repo_root() / inventory.WRAPPER_PATH).read_text(encoding="utf-8")

        self.assertIn("OPENSUBDIV_ROOT is not set", source)
        self.assertIn("--require-opensubdiv", source)
        self.assertIn("experiments/opensubdiv_regular_cpp_adapter_proof.cpp", source)
        self.assertIn("repo_sources", source)
        self.assertIn("-losdCPU", source)
        self.assertNotIn("make ", source)

    def test_default_production_surfaces_stay_opensubdiv_free(self):
        self.assertEqual(inventory.production_leaks(inventory.repo_root()), [])

    def test_inventory_anchors_are_present(self):
        located, missing = inventory.collect_anchors(inventory.repo_root())

        self.assertFalse(missing)
        self.assertGreaterEqual(len(located), len(inventory.ANCHORS))


if __name__ == "__main__":
    unittest.main()
