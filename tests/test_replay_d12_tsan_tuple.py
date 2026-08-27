"""Tests for the standalone D12 TSan worker replay harness."""

import hashlib
import io
import json
import importlib.util
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts/replay_d12_tsan_tuple.py"
SPEC = importlib.util.spec_from_file_location("replay_d12_tsan_tuple",
                                              REPLAY_PATH)
REPLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPLAY)
RUNNER = REPLAY.RUNNER


def synthetic_rows(count, source_count=4):
    rows = []
    for index in range(count):
        rows.append({
            "face_row": index % 2,
            "local_corner_or_none": -1 if index % 3 else index % 3,
            "sample_id": "sample-{:04d}".format(index),
            "row_kind": RUNNER.ROW_ORDER[index % len(RUNNER.ROW_ORDER)],
            "source_ids": list(range(source_count)),
            "coefficients": [0.5 + 0.125 * (index + position)
                             for position in range(source_count)]})
    return rows


class ReplayFixture(object):
    """A self-consistent synthetic checkpoint, artifacts, and mesh corpus."""

    CONTENTS = ("content-a", "content-b", "content-c")
    LEVELS = (2, 3)

    def __init__(self, root, rows_per_case=6):
        self.root = pathlib.Path(root)
        self.mesh_root = self.root / "mesh"
        self.artifact_root = self.root / "artifacts"
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.rows = {}
        self.cases = []
        self.jobs = []
        for content_id in self.CONTENTS:
            mesh = self.mesh_root / content_id
            mesh.mkdir(parents=True, exist_ok=True)
            (mesh / "vertices.csv").write_text(
                "\n".join("{},{},{}".format(index, index + 0.5, index - 0.25)
                          for index in range(4)) + "\n", encoding="utf-8")
            (mesh / "faces.csv").write_text("0,1,2,3\n1,2,3,0\n",
                                            encoding="utf-8")
            self.jobs.append({"content_identity_key": content_id,
                              "mesh_path": str(mesh), "mutation": "none"})
            for level in self.LEVELS:
                rows = synthetic_rows(rows_per_case)
                digest = hashlib.sha256()
                for row in rows:
                    digest.update(RUNNER.D12WorkerInventoryVerifier.
                                  _provider_record_bytes(row))
                counts = {kind: 0 for kind in RUNNER.ROW_ORDER}
                for row in rows:
                    counts[row["row_kind"]] += 1
                self.rows[(content_id, level)] = rows
                self.cases.append({
                    "candidate": "bfr",
                    "content_identity_key": content_id,
                    "approximation_level": level,
                    "applicable_mode": "cache_disabled",
                    "row_kind_counts": counts,
                    "canonical_rows_sha256": digest.hexdigest(),
                    "complete_json_artifact": "{}-{}.json.gz".format(
                        content_id, level),
                    "complete_json_sha256": "0" * 64})
        self.cases.sort(key=lambda case: RUNNER.jcs_bytes([
            case["content_identity_key"], case["approximation_level"],
            "release", "cache_disabled"]))
        self.checkpoint = {"schema_version": 2,
                           "kind": "bfr_release_matrix_checkpoint",
                           "complete": True,
                           "binding": {"git_head": "f" * 40},
                           "numeric_cases": self.cases}

    def identities(self):
        return [REPLAY.case_identity(case) for case in self.cases]

    def artifact_report(self, artifact_root, case):
        return {"rows": self.rows[REPLAY.case_identity(case)]}

    def mesh(self, job):
        path = pathlib.Path(job["mesh_path"])
        vertices = []
        with (path / "vertices.csv").open("r", encoding="utf-8") as stream:
            for line in stream:
                vertices.append(tuple(float(value)
                                      for value in line.strip().split(",")))
        faces = [(0, 1, 2, 3), (1, 2, 3, 0)]
        return vertices, faces, None

    def patches(self):
        return (
            mock.patch.object(RUNNER, "_ordered_d12_cases",
                              side_effect=lambda checkpoint: self.cases),
            mock.patch.object(RUNNER, "_artifact_report",
                              side_effect=self.artifact_report),
            mock.patch.object(RUNNER.B2, "valid_content_jobs",
                              return_value=self.jobs),
            mock.patch.object(RUNNER.B2, "independent_mesh",
                              side_effect=self.mesh),
            mock.patch.object(REPLAY, "FROZEN_CASE_COUNT", len(self.cases)),
            mock.patch.object(REPLAY, "FROZEN_PROVIDER_RECORDS",
                              sum(REPLAY.case_provider_count(case)
                                  for case in self.cases)),
            mock.patch.object(REPLAY, "FROZEN_REPRESENTATION_RECORDS",
                              8 * sum(REPLAY.case_provider_count(case)
                                      for case in self.cases)))

    def publish(self, destination):
        """Publish the bundle with the exact frozen derivation."""
        with contextlib_exit_stack(self.patches()):
            descriptors, references = RUNNER.write_d12_serial_references(
                self.checkpoint, self.artifact_root, destination,
                selected_cases=self.identities())
        return descriptors, references


def contextlib_exit_stack(patches):
    import contextlib
    stack = contextlib.ExitStack()
    try:
        for patch in patches:
            stack.enter_context(patch)
    except BaseException:
        # Never leave a half-entered set of patches applied to the shared
        # runner module; that would silently corrupt every later test.
        stack.close()
        raise
    return stack


class SerialReferenceReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="d12-replay-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.fixture = ReplayFixture(self.root / "fixture")
        self.bundle = self.root / "bundle"
        self.descriptors, self.derived = self.fixture.publish(self.bundle)

    def read(self, selected, replay_root=None, **kwargs):
        replay_root = replay_root or (self.root / ("replay-" + str(len(
            list(self.root.iterdir())))))
        replay_root.mkdir(parents=True, exist_ok=True)
        with contextlib_exit_stack(self.fixture.patches()):
            return REPLAY.read_published_serial_references(
                self.fixture.checkpoint, self.bundle, replay_root, selected,
                **kwargs)

    def test_published_bytes_reproduce_the_derived_references(self):
        selected = self.fixture.identities()
        references, published = self.read(selected)
        for identity in selected:
            derived = self.derived[identity]
            observed = references[identity]
            self.assertEqual(observed["provider"], derived["provider"])
            self.assertEqual(observed["representation"],
                             derived["representation"])
            self.assertEqual(observed["provider_count"],
                             derived["provider_count"])
            self.assertEqual(observed["representation_count"],
                             derived["representation_count"])
            self.assertEqual(observed["request_sha256"],
                             derived["request_sha256"])
        self.assertEqual(
            published["provider_serial_reference"]["sha256"],
            self.descriptors["provider_serial_reference"]["sha256"])

    def test_single_case_selection_extracts_the_exact_middle_slice(self):
        selected = [self.fixture.identities()[len(self.fixture.cases) // 2]]
        references, published = self.read(selected)
        self.assertEqual(set(references), set(selected))
        self.assertEqual(references[selected[0]]["representation"],
                         self.derived[selected[0]]["representation"])
        self.assertEqual(len(published["cases"]), 1)

    def test_whole_file_digest_matches_the_published_descriptor(self):
        _, published = self.read(self.fixture.identities(),
                                 whole_file_digest=True)
        self.assertEqual(
            published["representation_serial_reference"]["sha256"],
            self.descriptors["representation_serial_reference"]["sha256"])

    def test_request_ledger_is_copied_into_the_isolated_replay_root(self):
        selected = [self.fixture.identities()[0]]
        replay_root = self.root / "isolated"
        references, _ = self.read(selected, replay_root=replay_root)
        copied = pathlib.Path(references[selected[0]]["request_path"])
        self.assertTrue(copied.is_file())
        self.assertIn(str(replay_root), str(copied))
        published = pathlib.Path(self.derived[selected[0]]["request_path"])
        self.assertEqual(copied.read_bytes(), published.read_bytes())

    def test_tampered_provider_reference_fails_closed(self):
        path = self.bundle / REPLAY.PROVIDER_RELATIVE
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 0xFF
        path.write_bytes(bytes(raw))
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "frozen checkpoint digest"):
            self.read(self.fixture.identities())

    def test_tampered_representation_slice_fails_closed(self):
        path = self.bundle / REPLAY.REPRESENTATION_RELATIVE
        raw = path.read_bytes()
        target = raw.index(b'"positive_one"')
        path.write_bytes(raw[:target] + b'"positive_ONE"' +
                         raw[target + len(b'"positive_one"'):])
        with self.assertRaises(RUNNER.QualificationError):
            self.read(self.fixture.identities())

    def test_truncated_representation_reference_fails_closed(self):
        path = self.bundle / REPLAY.REPRESENTATION_RELATIVE
        path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "not a JSON array"):
            self.read(self.fixture.identities())

    def test_corrupt_representation_record_fails_closed(self):
        path = self.bundle / REPLAY.REPRESENTATION_RELATIVE
        raw = path.read_bytes()
        target = raw.index(b'"positive_one",')
        path.write_bytes(raw[:target] + b'"positive_one" ' +
                         raw[target + len(b'"positive_one",'):])
        with self.assertRaisesRegex(
                RUNNER.QualificationError,
                "not valid JSON|not canonical|record grammar drift"):
            self.read(self.fixture.identities())

    def test_unwrapped_representation_reference_fails_closed(self):
        path = self.bundle / REPLAY.REPRESENTATION_RELATIVE
        path.write_bytes(path.read_bytes()[1:-1])
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "not a JSON array"):
            self.read(self.fixture.identities())

    def test_reordered_representation_inputs_fail_closed(self):
        path = self.bundle / REPLAY.REPRESENTATION_RELATIVE
        raw = path.read_bytes()
        first = raw.index(b'"' + REPLAY.FROZEN_INPUT_IDS[0].encode() + b'"')
        replacement = b'"' + REPLAY.FROZEN_INPUT_IDS[1].encode() + b'"'
        path.write_bytes(raw[:first] + replacement +
                         raw[first + len(replacement):])
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "record grammar drift"):
            self.read(self.fixture.identities())

    def test_request_ledger_row_drift_fails_closed(self):
        identity = self.fixture.identities()[0]
        path = pathlib.Path(self.derived[identity]["request_path"])
        path.write_bytes(path.read_bytes() * 2)
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "request ledger row count"):
            self.read([identity])

    def test_missing_published_reference_fails_closed(self):
        (self.bundle / REPLAY.PROVIDER_RELATIVE).unlink()
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "published bundle lacks"):
            self.read(self.fixture.identities())

    def test_case_outside_the_frozen_universe_fails_closed(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "outside the frozen serial universe"):
            self.read([("content-absent", 2)])


class SelectedDerivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="d12-replay-derive-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.fixture = ReplayFixture(self.root / "fixture")

    def test_selection_restricts_the_frozen_derivation(self):
        selected = self.fixture.identities()[:2]
        with contextlib_exit_stack(self.fixture.patches()):
            _, references = RUNNER.write_d12_serial_references(
                self.fixture.checkpoint, self.fixture.artifact_root,
                self.root / "partial", selected_cases=selected)
        self.assertEqual(set(references), set(selected))

    def test_empty_selection_fails_closed(self):
        with contextlib_exit_stack(self.fixture.patches()):
            with self.assertRaisesRegex(RUNNER.QualificationError,
                                        "selection is empty"):
                RUNNER.write_d12_serial_references(
                    self.fixture.checkpoint, self.fixture.artifact_root,
                    self.root / "empty", selected_cases=[])

    def test_unselected_case_is_never_derived(self):
        selected = self.fixture.identities()[:1]
        with contextlib_exit_stack(self.fixture.patches()):
            _, references = RUNNER.write_d12_serial_references(
                self.fixture.checkpoint, self.fixture.artifact_root,
                self.root / "single", selected_cases=selected)
        requests = sorted(
            (self.root / "single" / REPLAY.REQUEST_ROOT).iterdir())
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(references), 1)

    def test_default_derivation_keeps_the_frozen_cardinality(self):
        with contextlib_exit_stack(self.fixture.patches()):
            with self.assertRaisesRegex(RUNNER.QualificationError,
                                        "D12 serial reference cardinality"):
                RUNNER.write_d12_serial_references(
                    self.fixture.checkpoint, self.fixture.artifact_root,
                    self.root / "default")


class TupleSelectionTests(unittest.TestCase):
    UNIVERSE = [("content-a", 2, "cache_disabled", 1),
                ("content-a", 2, "SurfaceFactoryCacheThreaded", 4),
                ("content-b", 3, "SurfaceFactoryCacheThreaded", 2)]

    def test_raw_and_alias_modes_both_resolve(self):
        self.assertEqual(
            REPLAY.parse_tuple_spec(
                "content-a:2:SurfaceFactoryCacheThreaded:4", self.UNIVERSE),
            self.UNIVERSE[1])
        self.assertEqual(
            REPLAY.parse_tuple_spec("content-a:2:threaded_cache:4",
                                    self.UNIVERSE),
            self.UNIVERSE[1])

    def test_unknown_tuple_is_rejected(self):
        for text in ("content-a:2:cache_disabled:9", "content-a:2:bogus:1",
                     "content-a:2:cache_disabled", "content-a:x:y:1"):
            with self.assertRaises(REPLAY.ReplayError):
                REPLAY.parse_tuple_spec(text, self.UNIVERSE)

    def test_first_tuple_and_explicit_tuple_are_exclusive(self):
        args = mock.Mock(first_tuple=True, tuple=["content-a:2:"
                                                  "cache_disabled:1"])
        with self.assertRaises(REPLAY.ReplayError):
            REPLAY.resolve_selection(args, self.UNIVERSE)

    def test_duplicate_selection_is_rejected(self):
        args = mock.Mock(first_tuple=False,
                         tuple=["content-a:2:cache_disabled:1"] * 2)
        with self.assertRaises(REPLAY.ReplayError):
            REPLAY.resolve_selection(args, self.UNIVERSE)

    def test_no_selection_is_rejected(self):
        args = mock.Mock(first_tuple=False, tuple=[])
        with self.assertRaises(REPLAY.ReplayError):
            REPLAY.resolve_selection(args, self.UNIVERSE)


class ReplayRootGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="d12-replay-root-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()

    def test_repository_paths_are_refused(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "outside the repository"):
            REPLAY.prepare_replay_root(ROOT / "scratch-replay", self.bundle)

    def test_published_bundle_overlap_is_refused(self):
        for candidate in (self.bundle, self.bundle / "inside"):
            with self.assertRaisesRegex(RUNNER.QualificationError,
                                        "disjoint from the published bundle"):
                REPLAY.prepare_replay_root(candidate, self.bundle)

    def test_non_empty_replay_root_is_refused(self):
        occupied = self.root / "occupied"
        occupied.mkdir()
        (occupied / "stale").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "empty directory"):
            REPLAY.prepare_replay_root(occupied, self.bundle)

    def test_fresh_root_is_created(self):
        created = REPLAY.prepare_replay_root(self.root / "fresh", self.bundle)
        self.assertTrue(created.is_dir())


class WorkerTupleSelectionTests(unittest.TestCase):
    """The frozen worker stage honours a restricted tuple universe."""

    PROVIDER = ("#!/bin/sh\nprintf 'D12PROV1'\n"
                "printf '\\000\\000\\000\\000\\001\\000\\000\\000"
                "\\001\\000\\000\\000\\000\\000\\000\\000'\nprintf 'p'\n")
    REPRESENTATION = ("#!/bin/sh\ncat >/dev/null\nexit 7\n")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="d12-replay-wt-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.output_root = self.root / "output"
        self.output_root.mkdir()
        self.provider = self.root / "provider"
        self.provider.write_text(self.PROVIDER, encoding="utf-8")
        os.chmod(self.provider, 0o755)
        self.representation = self.root / "representation"
        self.representation.write_text(self.REPRESENTATION, encoding="utf-8")
        os.chmod(self.representation, 0o755)
        request_root = self.output_root / REPLAY.REQUEST_ROOT
        request_root.mkdir(parents=True)
        self.references = {}
        self.universe = []
        for index, (content_id, level) in enumerate(
                (("content-a", 2), ("content-b", 3))):
            name = RUNNER.sha256_bytes(RUNNER.jcs_bytes(
                [content_id, level])) + ".tsv"
            path = request_root / name
            path.write_text("request-{}\n".format(index), encoding="utf-8")
            self.references[(content_id, level)] = {
                "provider": "b" * 64, "representation": "c" * 64,
                "provider_count": 1, "representation_count": 1,
                "request_path": str(path.resolve()),
                "request_sha256": RUNNER.sha256_file(path)}
            self.universe.append(
                (content_id, level, "cache_disabled", 1))
        self.jobs = [{"content_identity_key": content_id,
                      "mesh_path": "unused", "mutation": "none"}
                     for content_id, _ in
                     (("content-a", 2), ("content-b", 3))]
        self.environment = {"LANG": "C", "LC_ALL": "C",
                            "SOURCE_DATE_EPOCH": "0", "TZ": "UTC",
                            "ZERO_AR_DATE": "1"}
        self.artifact = RUNNER.D12ProcessObservationArtifact(
            self.output_root, {RUNNER.sha256_file(self.provider),
                               RUNNER.sha256_file(self.representation)})
        self.addCleanup(self.artifact.close)

    def run_streams(self, selected):
        with mock.patch.object(RUNNER.B2, "expected_threading_identities",
                               return_value=self.universe), \
                mock.patch.object(RUNNER.B2, "valid_content_jobs",
                                  return_value=self.jobs), \
                mock.patch.object(RUNNER, "_d12_rebuild_environment",
                                  return_value=self.environment):
            return RUNNER.execute_d12_worker_streams(
                str(self.provider), str(self.representation), {},
                self.output_root, self.references, self.artifact, "a" * 64,
                timeout_seconds=10, selected_tuple_identities=selected)

    def test_restricted_selection_blocks_on_the_selected_tuple(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "blocked by NON_RACE_EXIT"):
            self.run_streams([self.universe[1]])
        record = RUNNER.strict_json_bytes(
            (self.output_root / RUNNER._D12_WORKER_FAILURE_ROOT /
             "failure.json").read_bytes())
        self.assertEqual(record["tuple"]["content_identity_key"],
                         self.universe[1][0])

    def test_unfrozen_selection_fails_closed(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "selected worker tuple is not frozen"):
            self.run_streams([("content-z", 9, "cache_disabled", 1)])

    def test_duplicate_selection_fails_closed(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "selected worker tuple is not frozen"):
            self.run_streams([self.universe[0], self.universe[0]])

    def test_empty_selection_fails_closed(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "selected worker tuple is not frozen"):
            self.run_streams([])


if __name__ == "__main__":
    unittest.main()


class EndToEndReplayTests(unittest.TestCase):
    """Drive the whole replay against a published bundle and a failing worker."""

    PROVIDER = ("#!/bin/sh\n"
                "echo 'ThreadSanitizer: unexpected memory mapping' >&2\n"
                "echo 'FATAL: replay diagnostic bytes' >&2\n"
                "exit 66\n")
    REPRESENTATION = "#!/bin/sh\ncat >/dev/null\nexit 0\n"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="d12-replay-e2e-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.fixture = ReplayFixture(self.root / "fixture")
        self.bundle = self.root / "bundle"
        self.descriptors, self.derived = self.fixture.publish(self.bundle)
        self.checkpoint_path = self.root / "checkpoint.json"
        self.checkpoint_path.write_bytes(
            RUNNER.jcs_bytes(self.fixture.checkpoint))
        self.provider = self.root / "provider-tsan"
        self.provider.write_text(self.PROVIDER, encoding="utf-8")
        os.chmod(self.provider, 0o755)
        self.representation = self.root / "representation-tsan"
        self.representation.write_text(self.REPRESENTATION, encoding="utf-8")
        os.chmod(self.representation, 0o755)
        self.identity = self.fixture.identities()[0]
        self.universe = [(self.identity[0], self.identity[1],
                          "cache_disabled", 1)]
        self.environment = {"LANG": "C", "LC_ALL": "C",
                            "SOURCE_DATE_EPOCH": "0", "TZ": "UTC",
                            "ZERO_AR_DATE": "1"}

    def args(self, **overrides):
        from types import SimpleNamespace
        values = {
            "checkpoint": str(self.checkpoint_path),
            "published_bundle": str(self.bundle),
            "replay_root": str(self.root / "replay"),
            "provider_tsan_binary": str(self.provider),
            "representation_tsan_binary": str(self.representation),
            "tuple": ["{}:{}:cache_disabled:1".format(*self.identity)],
            "first_tuple": False,
            "expected_binding_head": None,
            "instrumentation_digest": None,
            "timeout_seconds": 30,
            "digest_published_references": False,
            "expected_provider_serial_sha256": None,
            "expected_representation_serial_sha256": None,
            "verify_derivation": False,
            "artifact_dir": str(self.fixture.artifact_root),
            "list_tuples": False,
            "json": False}
        values.update(overrides)
        return SimpleNamespace(**values)

    def run_replay(self, **overrides):
        patches = list(self.fixture.patches()) + [
            mock.patch.object(RUNNER.B2, "expected_threading_identities",
                              return_value=self.universe),
            mock.patch.object(RUNNER, "_d12_rebuild_environment",
                              return_value=self.environment)]
        with contextlib_exit_stack(patches):
            return REPLAY.replay(self.args(**overrides))

    def test_failing_worker_is_replayed_classified_and_retained(self):
        report = self.run_replay()
        self.assertEqual(report["disposition"], "BLOCKED")
        self.assertFalse(report["admissible_as_evidence"])
        self.assertTrue(report["environment_faithful"])
        failure = report["failure"]
        self.assertEqual(failure["state"], "RETAINED")
        self.assertEqual(failure["blocking_reason"], "NON_RACE_EXIT")
        self.assertEqual(len(failure["processes"]), 1)
        process = failure["processes"][0]
        self.assertEqual(process["role"], "provider")
        self.assertEqual(process["classification"], "NON_RACE_EXIT")
        self.assertEqual(process["exit_code"], 66)
        self.assertIsNone(process["signal"])
        self.assertFalse(process["timed_out"])
        self.assertFalse(process["race_report_detected"])
        self.assertIn("unexpected memory mapping", process["stderr_preview"])
        self.assertTrue(pathlib.Path(process["stderr_path"]).is_file())

    def test_replay_binds_the_published_serial_reference_bytes(self):
        report = self.run_replay()
        published = report["published_serial_references"]
        self.assertEqual(
            published["provider_serial_reference"]["sha256"],
            self.descriptors["provider_serial_reference"]["sha256"])
        self.assertEqual(
            published["provider_serial_reference"]["binding"],
            "EVERY_CASE_BOUND_TO_CHECKPOINT_DIGEST")
        self.assertEqual(len(published["cases"]), 1)
        case = published["cases"][0]
        self.assertEqual(case["content_identity_key"], self.identity[0])
        self.assertEqual(case["representation"]["sha256"],
                         self.derived[self.identity]["representation"])

    def test_replay_never_writes_into_the_published_bundle(self):
        before = sorted(str(path.relative_to(self.bundle))
                        for path in self.bundle.rglob("*"))
        digests = {path: RUNNER.sha256_file(path)
                   for path in self.bundle.rglob("*") if path.is_file()}
        self.run_replay()
        after = sorted(str(path.relative_to(self.bundle))
                       for path in self.bundle.rglob("*"))
        self.assertEqual(before, after)
        for path, digest in digests.items():
            self.assertEqual(RUNNER.sha256_file(path), digest)

    def test_independent_derivation_cross_check_passes(self):
        report = self.run_replay(verify_derivation=True)
        self.assertEqual(report["independent_derivation"],
                         {"state": "IDENTICAL", "cases": 1})

    def test_expected_serial_digest_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "provider serial reference digest drift"):
            self.run_replay(expected_provider_serial_sha256="0" * 64)

    def test_replay_marker_is_written_and_rendered(self):
        report = self.run_replay()
        marker = REPLAY.write_marker(report)
        self.assertTrue(marker.is_file())
        self.assertEqual(RUNNER.strict_json_bytes(marker.read_bytes())["kind"],
                         REPLAY.REPLAY_KIND)
        import io
        stream = io.StringIO()
        REPLAY.render(report, stream)
        rendered = stream.getvalue()
        self.assertIn("BLOCKED", rendered)
        self.assertIn("NON_RACE_EXIT", rendered)
        self.assertIn("unexpected memory mapping", rendered)
        self.assertIn("not admissible as qualification evidence", rendered)


class ReproducedRaceTests(EndToEndReplayTests):
    """A reproduced data race is a finding, never a clean run."""

    PROVIDER = ("#!/bin/sh\n"
                "echo 'WARNING: ThreadSanitizer: data race (pid=1)' >&2\n"
                "exit 66\n")
    REPRESENTATION = "#!/bin/sh\ncat >/dev/null\nexit 0\n"

    def test_race_gets_its_own_disposition(self):
        report = self.run_replay()
        self.assertEqual(report["disposition"], "REPRODUCED_RACE")
        self.assertEqual(len(report["sanitizer_aborts"]), 1)
        self.assertNotIn("failure", report)

    def test_race_does_not_exit_zero(self):
        report = self.run_replay()
        self.assertEqual(REPLAY.EXIT_CODES[report["disposition"]], 3)
        self.assertEqual(REPLAY.EXIT_CODES["REPRODUCED_CLEAN"], 0)
        self.assertEqual(REPLAY.EXIT_CODES["BLOCKED"], 1)

    def test_race_is_rendered_as_a_finding(self):
        import io
        stream = io.StringIO()
        REPLAY.render(self.run_replay(), stream)
        rendered = stream.getvalue()
        self.assertIn("REPRODUCED_RACE", rendered)
        self.assertIn("not a clean run", rendered)
        self.assertIn("sanitizer abort", rendered)

    # Inherited end-to-end assertions describe a blocking failure, so they do
    # not apply to the race fixture.
    test_failing_worker_is_replayed_classified_and_retained = None
    test_replay_marker_is_written_and_rendered = None


class MalformedCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="d12-replay-ckpt-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)

    def write(self, raw):
        path = self.root / "checkpoint.json"
        path.write_bytes(raw)
        return str(path)

    def test_non_object_checkpoint_fails_closed(self):
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "not a JSON object"):
            REPLAY.load_checkpoint(self.write(b"[]"))

    def test_null_binding_fails_closed(self):
        raw = (b'{"schema_version":2,"kind":"bfr_release_matrix_checkpoint",'
               b'"complete":true,"binding":null}')
        checkpoint, binding = REPLAY.load_checkpoint(self.write(raw))
        self.assertIsNone(binding)
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "head binding drift"):
            REPLAY.load_checkpoint(self.write(raw), expected_head="f" * 40)

    def test_non_object_binding_fails_closed(self):
        raw = (b'{"schema_version":2,"kind":"bfr_release_matrix_checkpoint",'
               b'"complete":true,"binding":["f"]}')
        with self.assertRaisesRegex(RUNNER.QualificationError,
                                    "binding is not a JSON object"):
            REPLAY.load_checkpoint(self.write(raw))

    def test_absent_binding_is_accepted_as_unknown(self):
        raw = (b'{"schema_version":2,"kind":"bfr_release_matrix_checkpoint",'
               b'"complete":true}')
        _, binding = REPLAY.load_checkpoint(self.write(raw))
        self.assertIsNone(binding)


class RetainedExecutableBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="d12-replay-exe-")
        self.addCleanup(self.temporary.cleanup)
        self.bundle = pathlib.Path(self.temporary.name) / "bundle"
        self.failure_root = self.bundle / RUNNER._D12_WORKER_FAILURE_ROOT
        self.failure_root.mkdir(parents=True)
        self.expected = {"provider": RUNNER.sha256_bytes(b"provider-bytes"),
                         "representation":
                             RUNNER.sha256_bytes(b"representation-bytes")}

    def retain(self, role, payload):
        (self.failure_root / (role + ".executable.bin")).write_bytes(payload)

    def test_absent_failure_bundle_is_unbound(self):
        empty = pathlib.Path(self.temporary.name) / "empty"
        empty.mkdir()
        self.assertIsNone(
            REPLAY.bind_retained_executables(empty, self.expected))

    def test_every_present_role_is_verified(self):
        self.retain("provider", b"provider-bytes")
        self.retain("representation", b"representation-bytes")
        binding = REPLAY.bind_retained_executables(self.bundle, self.expected)
        self.assertEqual(binding["state"], "IDENTICAL")
        self.assertEqual(binding["unverified_roles"], [])

    def test_missing_provider_still_verifies_representation(self):
        self.retain("representation", b"tampered-representation-bytes")
        with self.assertRaisesRegex(
                RUNNER.QualificationError,
                "representation executable differs"):
            REPLAY.bind_retained_executables(self.bundle, self.expected)

    def test_partial_binding_names_the_unverified_role(self):
        self.retain("provider", b"provider-bytes")
        binding = REPLAY.bind_retained_executables(self.bundle, self.expected)
        self.assertEqual(binding["state"], "PARTIAL")
        self.assertEqual(binding["sha256"], {
            "provider": self.expected["provider"]})
        self.assertEqual(binding["unverified_roles"], ["representation"])


class UnvalidatedRetentionTests(EndToEndReplayTests):
    """A validation mismatch must never discard the diagnostic bytes."""

    def test_validation_failure_still_surfaces_the_stderr(self):
        broken = mock.patch.object(
            RUNNER, "validate_d12_worker_failure_artifact",
            side_effect=RUNNER.QualificationError("synthetic validator drift"))
        with broken:
            report = self.run_replay()
        failure = report["failure"]
        self.assertEqual(report["disposition"], "BLOCKED")
        self.assertEqual(failure["state"], "RETAINED_UNVALIDATED")
        self.assertEqual(failure["validation_error"],
                         "synthetic validator drift")
        self.assertEqual([item["role"] for item in failure["processes"]],
                         ["provider"])
        process = failure["processes"][0]
        self.assertIn("unexpected memory mapping", process["stderr_preview"])
        self.assertTrue(pathlib.Path(process["stderr_path"]).is_file())
        self.assertIsNone(process["classification"])

    def test_unvalidated_retention_is_rendered_with_its_bytes(self):
        import io
        broken = mock.patch.object(
            RUNNER, "validate_d12_worker_failure_artifact",
            side_effect=RUNNER.QualificationError("synthetic validator drift"))
        with broken:
            report = self.run_replay()
        stream = io.StringIO()
        REPLAY.render(report, stream)
        rendered = stream.getvalue()
        self.assertIn("FAILED VALIDATION", rendered)
        self.assertIn("synthetic validator drift", rendered)
        self.assertIn("unexpected memory mapping", rendered)

    test_failing_worker_is_replayed_classified_and_retained = None
    test_independent_derivation_cross_check_passes = None
    test_replay_marker_is_written_and_rendered = None


class SelectionOrderTests(SerialReferenceReadbackTests):
    """Slice extraction must not depend on the caller's selection order."""

    def test_reverse_order_selection_extracts_the_same_slices(self):
        forward = self.fixture.identities()
        reverse = list(reversed(forward))
        references, published = self.read(reverse)
        self.assertEqual(set(references), set(forward))
        for identity in forward:
            self.assertEqual(references[identity]["representation"],
                             self.derived[identity]["representation"])
            self.assertEqual(references[identity]["provider"],
                             self.derived[identity]["provider"])
        self.assertEqual(
            [case["content_identity_key"] for case in published["cases"]],
            [identity[0] for identity in reverse])

    def test_interleaved_subset_extracts_the_same_slices(self):
        forward = self.fixture.identities()
        subset = [forward[-1], forward[0], forward[len(forward) // 2]]
        references, _ = self.read(subset)
        self.assertEqual(set(references), set(subset))
        for identity in subset:
            self.assertEqual(references[identity]["representation"],
                             self.derived[identity]["representation"])


class MainEntryPointTests(unittest.TestCase):
    UNIVERSE = [("content-a", 2, "cache_disabled", 1)]

    def test_list_tuples_needs_no_other_input(self):
        import io
        buffer = io.StringIO()
        with mock.patch.object(REPLAY, "frozen_tuple_universe",
                               return_value=self.UNIVERSE), \
                mock.patch.object(sys, "stdout", buffer):
            self.assertEqual(REPLAY.main(["--list-tuples"]), 0)
        self.assertEqual(buffer.getvalue(), "content-a:2:cache_disabled:1\n")

    def test_list_tuples_is_not_triggered_by_a_flag_shaped_value(self):
        # Argparse now owns the flag, so a bare "--tuple --list-tuples" is
        # rejected outright instead of silently listing the universe.
        listed = io.StringIO()
        with mock.patch.object(REPLAY, "frozen_tuple_universe",
                               return_value=self.UNIVERSE), \
                mock.patch.object(sys, "stdout", listed), \
                mock.patch.object(sys, "stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                REPLAY.main(["--tuple", "--list-tuples"])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(listed.getvalue(), "")

    def test_list_tuples_supplied_as_a_tuple_value_is_not_a_listing(self):
        listed = io.StringIO()
        stream = io.StringIO()
        with mock.patch.object(REPLAY, "frozen_tuple_universe",
                               return_value=self.UNIVERSE), \
                mock.patch.object(sys, "stdout", listed), \
                mock.patch.object(sys, "stderr", stream):
            self.assertEqual(REPLAY.main(["--tuple=--list-tuples"]), 2)
        self.assertEqual(listed.getvalue(), "")
        self.assertEqual(json.loads(stream.getvalue())["status"],
                         "harness_failed")

    def test_missing_required_inputs_fail_closed(self):
        stream = io.StringIO()
        with mock.patch.object(sys, "stderr", stream):
            self.assertEqual(REPLAY.main(["--checkpoint", "x"]), 2)
        failure = json.loads(stream.getvalue())
        self.assertEqual(failure["status"], "harness_failed")
        for flag in ("--published-bundle", "--replay-root",
                     "--provider-tsan-binary",
                     "--representation-tsan-binary"):
            self.assertIn(flag, failure["error"])
        self.assertNotIn("--checkpoint", failure["error"])

    def test_marker_publication_failure_fails_closed(self):
        stream = io.StringIO()
        report = {"disposition": "REPRODUCED_CLEAN", "replay_root": "/nope"}
        with mock.patch.object(REPLAY, "replay", return_value=report), \
                mock.patch.object(REPLAY, "write_marker",
                                  side_effect=OSError("read-only root")), \
                mock.patch.object(sys, "stderr", stream):
            self.assertEqual(REPLAY.main([
                "--checkpoint", "c", "--published-bundle", "b",
                "--replay-root", "r", "--provider-tsan-binary", "p",
                "--representation-tsan-binary", "q"]), 2)
        self.assertEqual(json.loads(stream.getvalue())["status"],
                         "harness_failed")
