import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "inventory_opensubdiv_regular_cache_readiness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "inventory_opensubdiv_regular_cache_readiness", SCRIPT
)
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class OpenSubdivRegularCacheReadinessInventoryTest(unittest.TestCase):
    def test_cache_components_are_backend_neutral_and_immutable(self):
        components = set(inventory.CACHE_COMPONENTS)
        self.assertIn("backend-neutral immutable regular row table", components)
        self.assertIn("topology and sample-plan fingerprint", components)

    def test_invalidation_distinguishes_coordinates_from_topology(self):
        rules = {item["change"]: item["result"] for item in inventory.INVALIDATION_RULES}
        self.assertEqual(rules["vertex coordinates only"], "cache hit")
        self.assertEqual(rules["setup_flat topology"], "cache miss")
        self.assertIn("fingerprint", rules["direct public container mutation"])
        self.assertEqual(rules["Face::oneRingVertices source order"], "cache miss")

    def test_ownership_rejects_global_pointer_registry(self):
        self.assertIn("no process-global Mesh pointer registry", inventory.OWNERSHIP_RULES)
        self.assertIn("copy starts empty", inventory.OWNERSHIP_RULES)
        self.assertIn(
            "move transfers only a matching immutable cache", inventory.OWNERSHIP_RULES
        )

    def test_concurrency_preserves_existing_reduction(self):
        self.assertIn("published row tables are immutable", inventory.CONCURRENCY_RULES)
        self.assertIn("one publisher per fingerprint", inventory.CONCURRENCY_RULES)
        self.assertIn(
            "topology and sample-plan mutation is serialized against cache access",
            inventory.CONCURRENCY_RULES,
        )
        self.assertIn("OpenMP reduction order remains unchanged", inventory.CONCURRENCY_RULES)

    def test_prototype_gates_cover_reuse_invalidation_and_isolation(self):
        gates = set(inventory.PROTOTYPE_GATES)
        self.assertIn("one build across consecutive unchanged evaluations", gates)
        self.assertIn("coordinate-only cache hit with full observable parity", gates)
        self.assertIn("topology and sample-plan mutation misses", gates)
        self.assertIn("copy move destruction and concurrent mesh isolation", gates)
        self.assertIn("PR #106 benchmark matrix repeated", gates)

    def test_all_inventory_anchors_are_present(self):
        located, missing = inventory.collect_anchors(inventory.repo_root())
        self.assertFalse(missing)
        self.assertEqual(len(located), len(inventory.ANCHORS))

    def test_payload_keeps_production_and_broader_valence_blocked(self):
        located, missing = inventory.collect_anchors(inventory.repo_root())
        payload = inventory.as_dicts(located, missing)
        self.assertEqual(payload["status"], "passed")
        self.assertFalse(payload["cache_implemented"])
        self.assertFalse(payload["production_cache_approved"])
        self.assertFalse(payload["broader_valence_in_scope"])


if __name__ == "__main__":
    unittest.main()
