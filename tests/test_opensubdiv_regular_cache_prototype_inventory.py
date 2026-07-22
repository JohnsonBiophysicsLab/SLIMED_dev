import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_opensubdiv_regular_cache_prototype.py"
SPEC = importlib.util.spec_from_file_location(
    "inventory_opensubdiv_regular_cache_prototype", SCRIPT
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class OpenSubdivRegularCachePrototypeInventoryTest(unittest.TestCase):
    def test_all_prototype_anchors_are_present(self):
        result = inventory.payload()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["located"]), len(inventory.ANCHORS))
        self.assertFalse(result["missing"])

    def test_unique_cache_type_does_not_leak_into_production(self):
        self.assertEqual(inventory.production_leaks(), [])

    def test_payload_keeps_production_and_broader_valence_blocked(self):
        result = inventory.payload()
        self.assertFalse(result["cache_implemented_in_production"])
        self.assertFalse(result["production_cache_approved"])
        self.assertFalse(result["broader_valence_in_scope"])

    def test_source_covers_cache_acceptance_gates(self):
        source = (ROOT / inventory.SOURCE).read_text(encoding="utf-8")
        for needle in (
            "oneBuildForUnchanged",
            "coordinateOnlyHit",
            "coordinateMutationIsObservable",
            "coordinateOnlyObservableParity",
            "topologyMutationMiss",
            "samplePlanMutationMiss",
            "adjacentTopologyMutationMiss",
            "faceIndexMutationMiss",
            "eligibilityFlagsMutationMiss",
            "quadratureMutationMiss",
            "referenceRowsMutationMiss",
            "serializedMutationReadersSeeRebuild",
            "VTX_BOUNDARY_EDGE_ONLY",
            "copyStartsEmpty",
            "moveTransfersMatchingTable",
            "twoMeshIsolation",
            "concurrentReadersOnePublisher",
            "runtimeOptOutIgnoresPopulatedCache",
            "unsupportedFallbackPreserved",
            "rowsMatchFrozenRegular",
            "repeatedAreaForceOneBuild",
            "fullObservableParity",
            "element_energy_force_regular",
            "enumerate_regular_patch_area_volume_with_limit_surface_evaluator",
            "face.isBoundary || face.isGhost || face.oneRingVertices.size() != 12u",
        ):
            self.assertIn(needle, source)

    def test_absent_dependency_wrapper_skips_cleanly(self):
        environment = os.environ.copy()
        environment.pop("OPENSUBDIV_ROOT", None)
        completed = subprocess.run(
            [str(ROOT / inventory.WRAPPER)],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "skipped")
        self.assertTrue(result["not_production_cache"])


if __name__ == "__main__":
    unittest.main()
