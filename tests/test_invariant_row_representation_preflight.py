import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_invariant_row_representation_preflight.py"
SPEC = importlib.util.spec_from_file_location(
    "run_invariant_row_representation_preflight", RUNNER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InvariantRowRepresentationPreflightTests(unittest.TestCase):
    def _row(self, kind="position"):
        return {
            "face_row": 0,
            "sample_id": "synthetic-sample",
            "row_kind": kind,
            "source_ids": [2, 5, 9],
            "coefficients": ([0.500000000000002, 0.25, 0.25]
                             if kind == "position"
                             else [1.000000000000002, -0.5, -0.5]),
        }

    def test_self_test_freezes_scope_and_prohibitions(self):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--self-test", "--json"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        self.assertEqual(completed.returncode, 0,
                         completed.stderr + completed.stdout)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["row_invariant_tolerance"], 1.0e-12)
        self.assertEqual(report["six_row_order"], list(MODULE.ROW_ORDER))
        self.assertEqual(report["expected_case_count"], 294)
        self.assertFalse(report["post_hoc_normalization_permitted"])
        self.assertFalse(report["architecture_selection_permitted"])
        self.assertFalse(report["production_activation_permitted"])

    def test_anchor_is_first_oriented_face_corner_not_coefficient_extremum(self):
        row = self._row()
        represented = MODULE.represent_row(row, [5, 9, 2])
        self.assertEqual(represented["anchor_source_id"], 5)
        self.assertEqual(represented["provider_anchor_coefficient_bits_hex"],
                         MODULE.binary64_bits_hex(0.25))
        self.assertEqual([term["source_id"]
                          for term in represented["difference_terms"]], [2, 5, 9])

    def test_all_coefficients_are_bitwise_unchanged(self):
        row = self._row()
        represented = MODULE.represent_row(row, [2, 5, 9])
        MODULE.validate_representation_against_row(represented, row)
        expected = [MODULE.binary64_bits_hex(value)
                    for value in row["coefficients"]]
        actual = [term["coefficient_bits_hex"]
                  for term in represented["difference_terms"]]
        self.assertEqual(actual, expected)

    def test_all_six_rows_reproduce_constant_fields_by_construction(self):
        for kind in MODULE.ROW_ORDER:
            row = self._row(kind)
            represented = MODULE.represent_row(row, [2, 9, 5])
            MODULE.validate_representation_against_row(represented, row)
            for constant in MODULE.CONSTANT_FIELD_CHALLENGES:
                sources = {source_id: constant for source_id in row["source_ids"]}
                expected = constant if kind == "position" else 0.0
                self.assertEqual(
                    MODULE.binary64_bits_hex(
                        MODULE.evaluate_anchored_row(represented, sources)),
                    MODULE.binary64_bits_hex(expected))

    def test_representation_changes_the_operator_instead_of_normalizing_row(self):
        row = self._row("du")
        represented = MODULE.represent_row(row, [2, 5, 9])
        sources = {2: 7.0, 5: -2.0, 9: 3.0}
        provider = MODULE.evaluate_provider_row(row, sources)
        anchored = MODULE.evaluate_anchored_row(represented, sources)
        self.assertNotEqual(MODULE.binary64_bits_hex(provider),
                            MODULE.binary64_bits_hex(anchored))
        self.assertEqual(represented["provider_anchor_coefficient_bits_hex"],
                         MODULE.binary64_bits_hex(row["coefficients"][0]))
        self.assertEqual(row["coefficients"],
                         [1.000000000000002, -0.5, -0.5])

    def test_source_relabeling_preserves_evaluated_functional(self):
        row = self._row("dvv")
        face = [5, 9, 2]
        sources = {2: 1.25, 5: -3.5, 9: 8.0}
        first = MODULE.evaluate_anchored_row(
            MODULE.represent_row(row, face), sources)
        relabel = {2: 11, 5: 4, 9: 7}
        entries = sorted((relabel[source_id], coefficient)
                         for source_id, coefficient in
                         zip(row["source_ids"], row["coefficients"]))
        relabeled_row = copy.deepcopy(row)
        relabeled_row["source_ids"] = [entry[0] for entry in entries]
        relabeled_row["coefficients"] = [entry[1] for entry in entries]
        relabeled_face = [relabel[source_id] for source_id in face]
        relabeled_sources = {relabel[source_id]: value
                             for source_id, value in sources.items()}
        second = MODULE.evaluate_anchored_row(
            MODULE.represent_row(relabeled_row, relabeled_face),
            relabeled_sources)
        self.assertEqual(MODULE.binary64_bits_hex(first),
                         MODULE.binary64_bits_hex(second))

    def test_missing_anchor_duplicate_source_and_nonfinite_coefficient_fail(self):
        row = self._row()
        with self.assertRaises(MODULE.PreflightError):
            MODULE.represent_row(row, [1, 5, 9])
        duplicate = copy.deepcopy(row)
        duplicate["source_ids"] = [2, 2, 9]
        with self.assertRaises(MODULE.PreflightError):
            MODULE.represent_row(duplicate, [2, 5, 9])
        nonfinite = copy.deepcopy(row)
        nonfinite["coefficients"][1] = float("nan")
        with self.assertRaises(MODULE.PreflightError):
            MODULE.represent_row(nonfinite, [2, 5, 9])

    def test_unknown_or_missing_six_row_kind_fails(self):
        row = self._row()
        row["row_kind"] = "mixed_duplicate"
        with self.assertRaises(MODULE.PreflightError):
            MODULE.represent_row(row, [2, 5, 9])

    def test_validation_detects_mutated_retained_coefficient(self):
        row = self._row()
        represented = MODULE.represent_row(row, [2, 5, 9])
        represented["difference_terms"][1]["coefficient"] += 1.0
        represented["difference_terms"][1]["coefficient_bits_hex"] = \
            MODULE.binary64_bits_hex(
                represented["difference_terms"][1]["coefficient"])
        with self.assertRaises(MODULE.PreflightError):
            MODULE.validate_representation_against_row(represented, row)

    def test_self_test_rejects_evidence_arguments(self):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--self-test", "--json",
             "--expected-binding-head", MODULE.FROZEN_B2_INPUT_HEAD],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        self.assertNotEqual(completed.returncode, 0)
        failure = json.loads(completed.stderr)
        self.assertEqual(failure["status"], "failed")


if __name__ == "__main__":
    unittest.main()
