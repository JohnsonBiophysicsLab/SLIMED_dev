import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = (
    ROOT
    / "experiments/irregular_valence4_topology_source_mapping_adapter.cpp"
)
INVENTORY = (
    ROOT
    / "scripts/inventory_irregular_valence4_topology_source_mapping_adapter.py"
)
WRAPPER = (
    ROOT
    / "scripts/run_irregular_valence4_topology_source_mapping_adapter.sh"
)


def load_inventory_module():
    spec = importlib.util.spec_from_file_location(
        "inventory_irregular_valence4_topology_source_mapping_adapter",
        INVENTORY,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValenceFourTopologySourceMappingAdapterInventoryTest(unittest.TestCase):
    def test_inventory_passes_and_scope_is_proof_only(self):
        report = load_inventory_module().collect(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertTrue(report["proof_only"])
        self.assertTrue(report["topology_source_mapping_adapter_design"])
        self.assertTrue(report["not_production_routing"])
        self.assertFalse(report["production_route_enabled"])
        self.assertFalse(report["scientifically_approved"])
        self.assertFalse(report["actual_production_force_path_executed"])
        self.assertFalse(report["production_paths_changed"])
        self.assertFalse(report["fixture_csvs_changed"])
        self.assertEqual(
            report["anchors"]["located"], report["anchors"]["expected"]
        )

    def test_mapping_and_mutation_gates_are_binding(self):
        source = EXPERIMENT.read_text(encoding="utf-8")
        passed_start = source.index("const bool passed =")
        output_start = source.index(
            "std::cout << '{';", passed_start
        )
        passed_source = source[passed_start:output_start]
        self.assertIn("canonical.passed", passed_source)
        self.assertIn("scatterPassed", passed_source)
        self.assertIn("productionOneRingsEmpty", passed_source)
        self.assertIn("mutationRejectionsPassed", passed_source)
        self.assertIn(
            "mapping.sourceIds != result.derivedSourceIds[faceIndex]",
            source,
        )
        self.assertIn(
            "expectedBySource[source][kind][axis]", source
        )
        self.assertNotIn(
            "oneRingVertices =", source
        )

    def test_dependency_absent_wrapper_skips(self):
        env = os.environ.copy()
        env.pop("OPENSUBDIV_ROOT", None)
        result = subprocess.run(
            [str(WRAPPER), "--json"],
            cwd=ROOT,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "skipped")

    @unittest.skipUnless(
        os.environ.get("OPENSUBDIV_ROOT"),
        "OPENSUBDIV_ROOT is required for the present-dependency proof",
    )
    def test_present_dependency_topology_source_mapping_adapter(self):
        result = subprocess.run(
            [str(WRAPPER), "--json", "--require-opensubdiv"],
            cwd=ROOT,
            env=os.environ.copy(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["proof_only"])
        self.assertTrue(payload["not_production_routing"])
        self.assertFalse(payload["production_route_enabled"])
        self.assertFalse(payload["scientifically_approved"])
        adapter = payload["adapter"]
        self.assertEqual(adapter["original_source_ids"], list(range(6)))
        self.assertEqual(
            adapter["per_face_source_ids"], [list(range(6))] * 8
        )
        self.assertTrue(
            adapter["production_topology_source_identity_passed"]
        )
        self.assertTrue(
            adapter["independent_sentinel_scatter_oracle_passed"]
        )
        self.assertTrue(adapter["mutation_rejections_passed"])
        self.assertFalse(adapter["production_one_rings_populated"])


if __name__ == "__main__":
    unittest.main()
