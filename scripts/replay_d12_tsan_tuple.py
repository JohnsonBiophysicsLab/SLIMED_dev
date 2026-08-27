#!/usr/bin/env python3
"""Standalone diagnostic replay of the Package-2 D12 TSan worker stage.

A full ``--produce-d12-evidence`` run spends hours on the numeric process
ledger and the 98-case serial derivation before the first mandatory TSan tuple
ever executes, so one intermittent worker failure costs a full production
cycle to observe once.  That is an unusable feedback loop for diagnosing an
unknown failure.

Both serial references and all 98 request ledgers are published before the
worker stage begins, and they survive the fail-closed unwind.  This tool
replays the worker stage directly against those published bytes: it binds the
published provider reference to the frozen checkpoint case digests, extracts
the selected cases' canonical slices from the published representation
reference, binds the published request ledgers, and then executes the
identical frozen worker stage for the selected tuples.

The replay is deliberately environment-faithful.  It reuses the frozen closed
build environment, the frozen argv grammar, the immutable executable
authority, the retention bundle, and the classifier without alteration.  It
never sets ``TSAN_OPTIONS``, never writes into the published bundle, and never
re-publishes evidence.  Its output is a diagnostic observation only: it is not
qualification evidence and cannot establish or discharge any D12 criterion.
"""

from __future__ import print_function

import argparse
import hashlib
import importlib.util
import json
import mmap
import pathlib
import shutil
import struct
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_anchored_row_qualification.py"
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "anchored_row_qualification", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)

B2 = RUNNER.B2
require = RUNNER.require
QualificationError = RUNNER.QualificationError
jcs_bytes = RUNNER.jcs_bytes
sha256_bytes = RUNNER.sha256_bytes
sha256_file = RUNNER.sha256_file

REPLAY_KIND = "d12_tsan_worker_replay_v1"
REPLAY_MARKER = "anchored-row-d12-tsan-replay-v1/replay.json"
SERIAL_ROOT = "anchored-row-d12-v1/serial"
PROVIDER_RELATIVE = SERIAL_ROOT + "/provider-rows.b2rowv1"
REPRESENTATION_RELATIVE = SERIAL_ROOT + "/representation-outputs.json"
REQUEST_ROOT = "anchored-row-d12-v1/requests"
FROZEN_CASE_COUNT = 98
FROZEN_PROVIDER_RECORDS = 693000
FROZEN_REPRESENTATION_RECORDS = 5544000
REQUEST_FIELD_COUNT = 11
STDERR_PREVIEW_BYTES = 8192
BINARY64_TOKEN_RE = RUNNER.re.compile(r"^[0-9a-f]{16}$")
# The frozen derivation emits, per provider row, exactly these eight inputs in
# this exact JCS-sorted order.  The published slice must repeat that cycle.
FROZEN_INPUT_IDS = tuple(sorted(
    ("fixture_x", "fixture_y", "fixture_z", "positive_zero", "positive_one",
     "negative_one", "positive_2p20", "negative_2p20"), key=jcs_bytes))


class ReplayError(Exception):
    """A replay harness input is unusable."""


def threading_cache_mode(mode):
    """The exact mode/cache-mode mapping the frozen worker stage applies."""
    cache_mode = ("threaded_cache" if mode == "SurfaceFactoryCacheThreaded"
                  else mode)
    require(cache_mode in {"cache_disabled", "threaded_cache"},
            "unexpected D12 threading mode: " + repr(mode))
    return cache_mode


def frozen_tuple_universe():
    return [tuple(identity)
            for identity in B2.expected_threading_identities(
                B2.load_manifest())]


def ordered_serial_cases(checkpoint):
    """The exact 98 cases in published serial-reference order."""
    cases = [case for case in RUNNER._ordered_d12_cases(checkpoint)
             if RUNNER.normalized_cache_mode(
                 case["applicable_mode"]) == "cache_disabled"]
    require(len(cases) == FROZEN_CASE_COUNT,
            "published serial reference case universe drift")
    return cases


def case_identity(case):
    return (case["content_identity_key"], case["approximation_level"])


def case_provider_count(case):
    counts = case["row_kind_counts"]
    require(isinstance(counts, dict) and counts and
            all(type(value) is int and value >= 0
                for value in counts.values()),
            "checkpoint case row-kind counts are unusable")
    return sum(counts.values())


def _provider_record_length(view, offset, limit):
    """Length of the self-delimiting B2ROWV1 record starting at ``offset``."""
    require(offset + 15 <= limit and
            bytes(view[offset:offset + 7]) == b"B2ROWV1",
            "published provider reference record framing")
    sample_length, = struct.unpack_from("<I", view, offset + 11)
    cursor = offset + 15 + sample_length
    require(sample_length > 0 and cursor + 8 <= limit,
            "published provider reference sample framing")
    source_count, = struct.unpack_from("<I", view, cursor + 4)
    end = cursor + 8 + source_count * 12
    require(source_count > 0 and end <= limit,
            "published provider reference source framing")
    return end - offset


def bind_published_provider_reference(published_root, cases):
    """Bind every published provider case slice to its checkpoint digest."""
    path = pathlib.Path(published_root) / PROVIDER_RELATIVE
    require(path.is_file(),
            "published bundle lacks " + PROVIDER_RELATIVE)
    counts = [case_provider_count(case) for case in cases]
    require(sum(counts) == FROZEN_PROVIDER_RECORDS,
            "published provider reference record cardinality")
    slices = {}
    whole = hashlib.sha256()
    with path.open("rb") as stream:
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
            limit = len(view)
            whole.update(view)
            offset = 0
            for case, count in zip(cases, counts):
                start = offset
                for _ in range(count):
                    offset += _provider_record_length(view, offset, limit)
                digest = hashlib.sha256(view[start:offset]).hexdigest()
                require(digest == case["canonical_rows_sha256"],
                        "published provider case slice differs from the "
                        "frozen checkpoint digest: " +
                        repr(case_identity(case)))
                slices[case_identity(case)] = {
                    "byte_offset": start, "byte_length": offset - start,
                    "record_count": count, "sha256": digest}
            require(offset == limit,
                    "published provider reference has trailing bytes")
    return {
        "relative_path": PROVIDER_RELATIVE, "byte_length": path.stat().st_size,
        "record_count": FROZEN_PROVIDER_RECORDS,
        "sha256": whole.hexdigest(), "cases": slices,
        "binding": "EVERY_CASE_BOUND_TO_CHECKPOINT_DIGEST"}


def _representation_marker(case):
    """The exact canonical prefix shared by every record of one case."""
    probe = jcs_bytes([case["content_identity_key"],
                       case["approximation_level"], 0])
    require(probe.endswith(b"0]"),
            "representation record marker construction")
    return probe[:-2]


def bind_published_representation_reference(published_root, cases, selected,
                                            expected_counts,
                                            whole_file_digest=False):
    """Extract and fully verify the selected canonical case slices."""
    path = pathlib.Path(published_root) / REPRESENTATION_RELATIVE
    require(path.is_file(),
            "published bundle lacks " + REPRESENTATION_RELATIVE)
    order = {case_identity(case): index for index, case in enumerate(cases)}
    slices = {}
    whole = None
    with path.open("rb") as stream:
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
            limit = len(view)
            # The array bracket and the first record's bracket are adjacent,
            # so an unwrapped stream cannot masquerade as the whole array.
            require(limit > 4 and view[0:2] == b"[[" and
                    view[limit - 2:limit] == b"]]",
                    "published representation reference is not a JSON array")
            if whole_file_digest:
                whole = hashlib.sha256(view).hexdigest()
            for identity in selected:
                index = order[identity]
                case = cases[index]
                marker = _representation_marker(case)
                start = view.find(marker, 1)
                require(start > 0,
                        "published representation reference lacks case " +
                        repr(identity))
                if index + 1 < len(cases):
                    following = _representation_marker(cases[index + 1])
                    end = view.find(following, start)
                    require(end > start,
                            "published representation reference lacks the "
                            "case following " + repr(identity))
                    end -= 1
                    require(view[end:end + 1] == b",",
                            "published representation case slices are not "
                            "comma separated at " + repr(identity))
                else:
                    end = limit - 1
                require(view[start - 1:start] in (b"[", b","),
                        "published representation case slice is misaligned "
                        "at " + repr(identity))
                encoded = b"[" + bytes(view[start:end]) + b"]"
                try:
                    records = RUNNER.strict_json_bytes(encoded)
                except ValueError as error:
                    raise QualificationError(
                        "published representation case slice is not valid "
                        "JSON at " + repr(identity)) from error
                require(jcs_bytes(records) == encoded,
                        "published representation case slice is not "
                        "canonical at " + repr(identity))
                require(len(records) == expected_counts[identity],
                        "published representation case slice cardinality "
                        "drift at " + repr(identity))
                require(all(_representation_record_grammar(
                            record, identity, position)
                        for position, record in enumerate(records)),
                        "published representation case slice record grammar "
                        "drift at " + repr(identity))
                slices[identity] = {
                    "byte_offset": start, "byte_length": end - start,
                    "record_count": len(records),
                    "sha256": sha256_bytes(encoded)}
    return {
        "relative_path": REPRESENTATION_RELATIVE,
        "byte_length": path.stat().st_size,
        "record_count": FROZEN_REPRESENTATION_RECORDS,
        "sha256": whole, "cases": slices,
        "binding": "SELECTED_CASES_CANONICALLY_VERIFIED"}


def _representation_record_grammar(record, identity, position):
    """The exact frozen shape of one published representation record."""
    return (isinstance(record, list) and len(record) == 8 and
            record[0] == identity[0] and record[1] == identity[1] and
            type(record[2]) is int and record[2] >= 0 and
            (record[3] is None or
             (type(record[3]) is int and record[3] >= 0)) and
            isinstance(record[4], str) and record[4] and
            record[5] in RUNNER.ROW_ORDER and
            record[6] == FROZEN_INPUT_IDS[position % len(FROZEN_INPUT_IDS)] and
            isinstance(record[7], str) and
            BINARY64_TOKEN_RE.fullmatch(record[7]) is not None)


def bind_published_request(published_root, replay_root, identity,
                           provider_count):
    """Copy one published request ledger into the isolated replay root."""
    content_id, level = identity
    relative = (REQUEST_ROOT + "/" +
                sha256_bytes(jcs_bytes([content_id, level])) + ".tsv")
    source = pathlib.Path(published_root) / relative
    require(source.is_file(),
            "published bundle lacks request ledger " + relative)
    raw = source.read_bytes()
    lines = raw.split(b"\n")
    require(lines and lines[-1] == b"",
            "published request ledger is not newline terminated")
    lines = lines[:-1]
    require(len(lines) == provider_count,
            "published request ledger row count differs from the provider "
            "case slice at " + repr(identity))
    prefix = (content_id + "\t" + str(level) + "\t").encode("utf-8")
    require(all(line.startswith(prefix) and
                line.count(b"\t") == REQUEST_FIELD_COUNT - 1
                for line in lines),
            "published request ledger identity or arity drift at " +
            repr(identity))
    destination = pathlib.Path(replay_root) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    digest = sha256_file(destination)
    require(digest == sha256_bytes(raw) == sha256_file(source),
            "replay request ledger copy is not byte identical")
    return {"relative_path": relative, "path": str(destination.resolve()),
            "byte_length": len(raw), "record_count": len(lines),
            "sha256": digest}


def read_published_serial_references(checkpoint, published_root, replay_root,
                                     selected, whole_file_digest=False):
    """Build the frozen ``references`` mapping from the published bytes."""
    cases = ordered_serial_cases(checkpoint)
    known = {case_identity(case): case for case in cases}
    for identity in selected:
        require(identity in known,
                "selected tuple names a case outside the frozen serial "
                "universe: " + repr(identity))
    provider = bind_published_provider_reference(published_root, cases)
    expected_counts = {
        identity: provider["cases"][identity]["record_count"] * 8
        for identity in selected}
    representation = bind_published_representation_reference(
        published_root, cases, selected, expected_counts, whole_file_digest)
    references = {}
    requests = {}
    for identity in selected:
        provider_slice = provider["cases"][identity]
        representation_slice = representation["cases"][identity]
        request = bind_published_request(
            published_root, replay_root, identity,
            provider_slice["record_count"])
        requests[identity] = request
        references[identity] = {
            "provider": provider_slice["sha256"],
            "representation": representation_slice["sha256"],
            "provider_count": provider_slice["record_count"],
            "representation_count": representation_slice["record_count"],
            "request_path": request["path"],
            "request_sha256": request["sha256"]}
    return references, {
        "source": str(pathlib.Path(published_root).resolve()),
        "provider_serial_reference": {
            key: value for key, value in provider.items() if key != "cases"},
        "representation_serial_reference": {
            key: value for key, value in representation.items()
            if key != "cases"},
        "cases": [{
            "content_identity_key": identity[0],
            "approximation_level": identity[1],
            "provider": provider["cases"][identity],
            "representation": representation["cases"][identity],
            "request": requests[identity]} for identity in selected]}


def verify_against_derivation(checkpoint, artifact_root, selected,
                              references, requests_by_identity):
    """Re-derive the selected cases and require exact published identity."""
    with tempfile.TemporaryDirectory(
            prefix="anchored-row-d12-replay-derive-") as scratch:
        _, derived = RUNNER.write_d12_serial_references(
            checkpoint, artifact_root, scratch,
            selected_cases=sorted(selected))
        require(set(derived) == set(references),
                "independent derivation case universe drift")
        for identity, reference in sorted(references.items()):
            other = derived[identity]
            require(other["provider"] == reference["provider"] and
                    other["representation"] == reference["representation"] and
                    other["provider_count"] ==
                        reference["provider_count"] and
                    other["representation_count"] ==
                        reference["representation_count"] and
                    other["request_sha256"] == reference["request_sha256"] and
                    pathlib.Path(other["request_path"]).read_bytes() ==
                        pathlib.Path(
                            requests_by_identity[identity]).read_bytes(),
                    "published serial reference differs from an independent "
                    "derivation at " + repr(identity))
    return {"state": "IDENTICAL", "cases": len(references)}


def parse_tuple_spec(text, universe):
    """Resolve ``content:level:mode:workers`` against the frozen universe."""
    fields = str(text).rsplit(":", 3)
    if len(fields) != 4:
        raise ReplayError(
            "tuple spec must be content_identity_key:level:mode:workers: " +
            repr(text))
    content_id, raw_level, raw_mode, raw_workers = fields
    try:
        level = int(raw_level)
        workers = int(raw_workers)
    except ValueError:
        raise ReplayError(
            "tuple level/workers must be integers: " + repr(text))
    candidates = [identity for identity in universe
                  if identity[0] == content_id and identity[1] == level and
                  identity[3] == workers and
                  raw_mode in (identity[2],
                               threading_cache_mode(identity[2]))]
    if len(candidates) != 1:
        raise ReplayError(
            "tuple spec does not name exactly one frozen tuple: " +
            repr(text))
    return candidates[0]


def resolve_selection(args, universe):
    if args.first_tuple:
        if args.tuple:
            raise ReplayError("--first-tuple excludes explicit --tuple")
        return [universe[0]]
    if not args.tuple:
        raise ReplayError("select tuples with --tuple or --first-tuple")
    selected = []
    for text in args.tuple:
        identity = parse_tuple_spec(text, universe)
        if identity in selected:
            raise ReplayError("duplicate tuple selection: " + repr(text))
        selected.append(identity)
    return selected


def load_checkpoint(path, expected_head=None):
    checkpoint = RUNNER.strict_json_bytes(
        pathlib.Path(path).resolve().read_bytes())
    require(checkpoint.get("schema_version") == 2 and
            checkpoint.get("kind") == "bfr_release_matrix_checkpoint" and
            checkpoint.get("complete") is True,
            "replay requires a complete release matrix checkpoint")
    binding = checkpoint.get("binding", {}).get("git_head")
    if expected_head is not None:
        require(binding == expected_head,
                "replay checkpoint/head binding drift")
    return checkpoint, binding


def prepare_replay_root(path, published_root):
    """Refuse to replay into the repository or into a published bundle."""
    root = pathlib.Path(path).resolve()
    require(root != ROOT and ROOT not in root.parents,
            "replay root must live outside the repository")
    published = pathlib.Path(published_root).resolve()
    require(root != published and published not in root.parents and
            root not in published.parents,
            "replay root must be disjoint from the published bundle")
    if root.exists():
        require(root.is_dir() and not any(root.iterdir()),
                "replay root must be an empty directory")
    else:
        root.mkdir(parents=True)
    return root


def bind_retained_executables(published_root, expected_executables):
    """Bind the replay binaries to the ones a published failure retained."""
    failure_root = (pathlib.Path(published_root) /
                    RUNNER._D12_WORKER_FAILURE_ROOT)
    if not failure_root.is_dir():
        return None
    observed = {}
    for role, digest in sorted(expected_executables.items()):
        retained = failure_root / (role + ".executable.bin")
        if not retained.is_file():
            return {"state": "PARTIAL", "sha256": observed}
        retained_sha256 = sha256_file(retained)
        require(retained_sha256 == digest,
                "replay " + role + " executable differs from the executable "
                "retained by the published failure")
        observed[role] = retained_sha256
    return {"state": "IDENTICAL", "sha256": observed}


def replay_instrumentation_digest(expected_executables, supplied=None):
    if supplied is not None:
        require(RUNNER.SHA256_RE.fullmatch(supplied) is not None,
                "supplied instrumentation digest is not a SHA-256")
        return supplied
    return sha256_bytes(jcs_bytes([
        REPLAY_KIND, expected_executables["provider"],
        expected_executables["representation"]]))


def summarize_failure(replay_root, expected_executables, references,
                      environment, timeout_seconds, selected, job_list,
                      error):
    """Independently validate and summarize the retained failure bundle."""
    failure_root = replay_root / RUNNER._D12_WORKER_FAILURE_ROOT
    if not (failure_root / "failure.json").is_file():
        return {"state": "UNRETAINED", "error": str(error)}
    record_sha256 = sha256_file(failure_root / "failure.json")
    record = RUNNER.validate_d12_worker_failure_artifact(
        replay_root, record_sha256, expected_executables, references,
        expected_environment=environment,
        expected_timeout_seconds=timeout_seconds,
        expected_tuple_identities=selected, expected_jobs=job_list)
    processes = []
    for item in record["processes"]:
        role = item["role"]
        stderr_path = failure_root / (role + ".stderr.bin")
        stdout_path = failure_root / (role + ".stdout.bin")
        stderr_raw = stderr_path.read_bytes()
        processes.append({
            "role": role,
            "classification": item["classification"],
            "exit_kind": item["process"]["exit_kind"],
            "exit_code": item["process"]["exit_code"],
            "signal": item["process"]["signal"],
            "timed_out": item["process"]["timed_out"],
            "race_report_detected": item["race_report_detected"],
            "argv": item["argv"],
            "stdout_bytes": stdout_path.stat().st_size,
            "stdout_path": str(stdout_path),
            "stderr_bytes": len(stderr_raw),
            "stderr_path": str(stderr_path),
            "stderr_sha256": sha256_bytes(stderr_raw),
            "stderr_preview": stderr_raw[:STDERR_PREVIEW_BYTES].decode(
                "utf-8", "replace")})
    return {
        "state": "RETAINED",
        "blocking_reason": record["blocking_reason"],
        "record_sha256": record_sha256,
        "root": str(failure_root),
        "tuple": record["tuple"],
        "processes": processes,
        "error": str(error)}


def replay(args):
    universe = frozen_tuple_universe()
    selected = resolve_selection(args, universe)
    published_root = pathlib.Path(args.published_bundle).resolve()
    require(published_root.is_dir(), "published bundle root is unavailable")
    replay_root = prepare_replay_root(args.replay_root, published_root)
    checkpoint, head = load_checkpoint(
        args.checkpoint, args.expected_binding_head)
    provider_binary = pathlib.Path(args.provider_tsan_binary).resolve()
    representation_binary = pathlib.Path(
        args.representation_tsan_binary).resolve()
    expected_executables = {
        "provider": sha256_file(provider_binary),
        "representation": sha256_file(representation_binary)}
    require(len(set(expected_executables.values())) == 2,
            "replay provider/representation executables are identical")
    instrumentation_digest = replay_instrumentation_digest(
        expected_executables, args.instrumentation_digest)
    environment = RUNNER._d12_rebuild_environment()
    job_list = B2.valid_content_jobs(B2.load_manifest())

    selected_cases = sorted({(identity[0], identity[1])
                             for identity in selected})
    started = RUNNER.iso_utc_now()
    references, published = read_published_serial_references(
        checkpoint, published_root, replay_root, selected_cases,
        whole_file_digest=args.digest_published_references)
    if args.expected_provider_serial_sha256 is not None:
        require(published["provider_serial_reference"]["sha256"] ==
                args.expected_provider_serial_sha256,
                "published provider serial reference digest drift")
    if args.expected_representation_serial_sha256 is not None:
        require(published["representation_serial_reference"]["sha256"] ==
                args.expected_representation_serial_sha256,
                "published representation serial reference digest drift; "
                "pass --digest-published-references to compute it")
    derivation = None
    if args.verify_derivation:
        derivation = verify_against_derivation(
            checkpoint, pathlib.Path(args.artifact_dir).resolve(),
            selected_cases, references,
            {identity: references[identity]["request_path"]
             for identity in selected_cases})
    bound = RUNNER.iso_utc_now()

    report = {
        "kind": REPLAY_KIND,
        "admissible_as_evidence": False,
        "environment_faithful": True,
        "git_head": head,
        "replay_root": str(replay_root),
        "checkpoint": str(pathlib.Path(args.checkpoint).resolve()),
        "timeout_seconds": args.timeout_seconds,
        "environment": environment,
        "executables": {
            "provider": {"path": str(provider_binary),
                         "sha256": expected_executables["provider"]},
            "representation": {
                "path": str(representation_binary),
                "sha256": expected_executables["representation"]}},
        "retained_executable_binding": bind_retained_executables(
            published_root, expected_executables),
        "instrumentation_digest": instrumentation_digest,
        "instrumentation_digest_supplied":
            args.instrumentation_digest is not None,
        "tuples": [{"content_identity_key": identity[0],
                    "approximation_level": identity[1],
                    "mode": identity[2], "worker_count": identity[3]}
                   for identity in selected],
        "published_serial_references": published,
        "independent_derivation": derivation,
        "started_utc": started,
        "reference_binding_completed_utc": bound}

    process_artifact = RUNNER.D12ProcessObservationArtifact(
        replay_root, set(expected_executables.values()))
    try:
        with tempfile.TemporaryDirectory(
                prefix="anchored-row-d12-replay-snapshot-") as snapshot:
            worker_paths = {}
            for role, original in (("provider", provider_binary),
                                   ("representation",
                                    representation_binary)):
                destination = pathlib.Path(snapshot) / role
                shutil.copyfile(str(original), str(destination))
                destination.chmod(0o500)
                require(sha256_file(destination) == sha256_file(original) ==
                        expected_executables[role],
                        "replay executable changed while snapshotting")
                worker_paths[role] = str(destination)
            try:
                sidecars, aborts = RUNNER.execute_d12_worker_streams(
                    worker_paths["provider"],
                    worker_paths["representation"], checkpoint, replay_root,
                    references, process_artifact, instrumentation_digest,
                    timeout_seconds=args.timeout_seconds,
                    selected_tuple_identities=selected)
            except QualificationError as error:
                report["disposition"] = "BLOCKED"
                report["failure"] = summarize_failure(
                    replay_root, expected_executables, references,
                    environment, args.timeout_seconds, selected, job_list,
                    error)
                report["ended_utc"] = RUNNER.iso_utc_now()
                return report
        report["disposition"] = "REPRODUCED_CLEAN"
        report["worker_sidecar_count"] = len(sidecars)
        report["sanitizer_aborts"] = [
            {"content_identity_key": key[0], "approximation_level": key[1],
             "cache_mode": key[2], "worker_count": key[3],
             "sanitizer_report_sha256": digest}
            for key, digest in sorted(aborts.items())]
        report["process_observations"] = process_artifact.finish()
    finally:
        process_artifact.close()
    report["ended_utc"] = RUNNER.iso_utc_now()
    return report


def write_marker(report):
    marker = pathlib.Path(report["replay_root"]) / REPLAY_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(jcs_bytes(report))
    return marker


def render(report, stream):
    def line(text=""):
        stream.write(text + "\n")

    published = report["published_serial_references"]
    line("D12 TSan worker replay: " + report["disposition"])
    line("  diagnostic only; not admissible as qualification evidence")
    line("  replay root      : " + report["replay_root"])
    line("  published bundle : " + published["source"])
    line("  git head         : " + str(report["git_head"]))
    line("  environment      : frozen closed build environment (faithful)")
    line("  provider ref     : {} bytes, all {} cases bound to the frozen "
         "checkpoint digests".format(
             published["provider_serial_reference"]["byte_length"],
             FROZEN_CASE_COUNT))
    line("  representation   : {} bytes, {} case slice(s) canonically "
         "verified".format(
             published["representation_serial_reference"]["byte_length"],
             len(published["cases"])))
    for case in published["cases"]:
        line("  case             : {} level {} -> {} provider rows, {} "
             "representation records".format(
                 case["content_identity_key"], case["approximation_level"],
                 case["provider"]["record_count"],
                 case["representation"]["record_count"]))
        line("      request      : {} ({} bytes)".format(
            case["request"]["relative_path"], case["request"]["byte_length"]))
    if report["independent_derivation"] is not None:
        line("  derivation check : {} for {} case(s)".format(
            report["independent_derivation"]["state"],
            report["independent_derivation"]["cases"]))
    if report["retained_executable_binding"] is not None:
        line("  executable bind  : {} to the retained failure "
             "executables".format(
                 report["retained_executable_binding"]["state"]))
    for identity in report["tuples"]:
        line("  tuple            : {} level {} {} workers {}".format(
            identity["content_identity_key"], identity["approximation_level"],
            identity["mode"], identity["worker_count"]))
    failure = report.get("failure")
    if failure is None:
        line("  sidecars         : {}".format(
            report.get("worker_sidecar_count", 0)))
        for abort in report.get("sanitizer_aborts", []):
            line("  sanitizer abort  : {} level {} {} workers {} -> {}".format(
                abort["content_identity_key"], abort["approximation_level"],
                abort["cache_mode"], abort["worker_count"],
                abort["sanitizer_report_sha256"]))
        return
    if failure["state"] == "UNRETAINED":
        line("  retention        : NONE")
        line("  error            : " + failure["error"])
        return
    line("  blocking reason  : " + failure["blocking_reason"])
    line("  failure.json     : {} ({})".format(
        failure["root"] + "/failure.json", failure["record_sha256"]))
    for process in failure["processes"]:
        line("  --- {} : {}".format(process["role"],
                                    process["classification"]))
        line("      exit         : {} code={} signal={} timed_out={}".format(
            process["exit_kind"], process["exit_code"], process["signal"],
            process["timed_out"]))
        line("      race marker  : {}".format(
            process["race_report_detected"]))
        line("      argv         : " + " ".join(process["argv"]))
        line("      stdout       : {} bytes at {}".format(
            process["stdout_bytes"], process["stdout_path"]))
        line("      stderr       : {} bytes at {}".format(
            process["stderr_bytes"], process["stderr_path"]))
        if process["stderr_preview"]:
            line("      stderr bytes :")
            for text in process["stderr_preview"].splitlines():
                line("        | " + text)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--published-bundle", required=True,
                        help="existing D12 output root holding the published "
                             "serial references and request ledgers")
    parser.add_argument("--replay-root", required=True,
                        help="empty directory, disjoint from the bundle")
    parser.add_argument("--provider-tsan-binary", required=True)
    parser.add_argument("--representation-tsan-binary", required=True)
    parser.add_argument("--tuple", action="append", default=[],
                        metavar="CONTENT:LEVEL:MODE:WORKERS")
    parser.add_argument("--first-tuple", action="store_true")
    parser.add_argument("--expected-binding-head")
    parser.add_argument("--instrumentation-digest")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--digest-published-references", action="store_true",
                        help="also hash the whole representation reference")
    parser.add_argument("--expected-provider-serial-sha256")
    parser.add_argument("--expected-representation-serial-sha256")
    parser.add_argument("--verify-derivation", action="store_true",
                        help="independently re-derive the selected cases and "
                             "require exact identity (needs --artifact-dir)")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--list-tuples", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if "--list-tuples" in argv:
        for identity in frozen_tuple_universe():
            sys.stdout.write("{}:{}:{}:{}\n".format(*identity))
        return 0
    args = parse_args(argv)
    try:
        require(args.timeout_seconds > 0, "replay timeout must be positive")
        require(not args.verify_derivation or args.artifact_dir,
                "--verify-derivation requires --artifact-dir")
        require(args.expected_representation_serial_sha256 is None or
                args.digest_published_references,
                "--expected-representation-serial-sha256 requires "
                "--digest-published-references")
        report = replay(args)
    except (ReplayError, QualificationError, RUNNER.B2A.PreflightError,
            B2.QualificationError, OSError, ValueError, KeyError) as error:
        sys.stderr.write(json.dumps(
            {"kind": REPLAY_KIND, "status": "harness_failed",
             "error": str(error)}, sort_keys=True) + "\n")
        return 2
    write_marker(report)
    if args.json:
        sys.stdout.buffer.write(jcs_bytes(report) + b"\n")
    else:
        render(report, sys.stdout)
    return 0 if report["disposition"] == "REPRODUCED_CLEAN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
