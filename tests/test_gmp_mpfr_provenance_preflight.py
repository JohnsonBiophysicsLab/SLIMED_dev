import copy
import importlib.util
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_gmp_mpfr_provenance_preflight.py"
SPEC = importlib.util.spec_from_file_location("gmp_mpfr_preflight", RUNNER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


SHA_A = "1" * 64
SHA_B = "2" * 64
SHA_C = "3" * 64


def descriptor(path, sha=SHA_C, length=7):
    return {"relative_path": path, "byte_length": length, "sha256": sha}


def build_record(run_id, name):
    root = f"run-{run_id.lower()}"
    source = str(MODULE.CANONICAL_BUILD_ROOT / f"{name}-source")
    transcript = f"{root}/{name}-transcript"
    configure = [f"{source}/configure",
                 f"--prefix={MODULE.CANONICAL_PREFIX}"]
    if name == "mpfr":
        configure.append(f"--with-gmp={MODULE.CANONICAL_PREFIX}")
    configure.extend(["--enable-shared", "--disable-static"])
    names = (
        "configure.argv", "build.argv", "install.argv", "environment",
        "configure.log", "build.log", "install.log", "config.status",
        "config.log", "Makefile")
    return {
        "canonical_source_root": source,
        "configure_argv": configure,
        "build_argv": ["/usr/bin/make", "-j1"],
        "install_argv": ["/usr/bin/make", "install"],
        "environment": dict(sorted(MODULE.BUILD_ENVIRONMENT.items())),
        "transcripts": {
            item: descriptor(f"{transcript}/{item}") for item in names
        },
    }


def library_record(run_id, name, sha):
    root = f"run-{run_id.lower()}/libraries"
    contract = MODULE.LIBRARIES[name]
    return {
        "canonical_path": str(MODULE.CANONICAL_PREFIX / "lib" /
                              contract["versioned_name"]),
        "link_path": str(MODULE.CANONICAL_PREFIX / "lib" /
                         contract["link_name"]),
        "link_target": contract["versioned_name"],
        "byte_length": 1234,
        "mode": "0755",
        "sha256": sha,
        "otool_d_sha256": SHA_B,
        "otool_l_sha256": SHA_C,
        "artifacts": {
            "library": descriptor(f"{root}/{contract['versioned_name']}",
                                  sha=sha, length=1234),
            "otool_d": descriptor(f"{root}/{name}.otool-D.txt", sha=SHA_B),
            "otool_l": descriptor(f"{root}/{name}.otool-L.txt", sha=SHA_C),
        },
    }


def valid_report():
    runs = []
    derived = {"gmp": SHA_A, "mpfr": SHA_B}
    for run_id in ("A", "B"):
        runs.append({
            "run_id": run_id,
            "builds": {name: build_record(run_id, name)
                       for name in ("gmp", "mpfr")},
            "libraries": {name: library_record(run_id, name, derived[name])
                          for name in ("gmp", "mpfr")},
        })
    return {
        "schema": MODULE.SCHEMA,
        "authority": {
            "amendment": "docs/anchored_row_dependency_provenance_amendment.md",
            "plan": "docs/bfr_loop_backend_plan_macos.md",
            "threat_model": "independent_rederivation_not_host_operator_resistance",
        },
        "git": {"head": MODULE.DERIVATION_START_HEAD, "worktree_clean": True},
        "platform": copy.deepcopy(MODULE.EXPECTED_PLATFORM),
        "compiler": {
            "c": str(MODULE.COMPILER), "cxx": str(MODULE.COMPILER_CXX),
            "version": MODULE.COMPILER_VERSION, "sdkroot": str(MODULE.SDKROOT),
        },
        "archives": copy.deepcopy(MODULE.ARCHIVES),
        "build_contract": {
            "canonical_prefix": str(MODULE.CANONICAL_PREFIX),
            "canonical_build_root": str(MODULE.CANONICAL_BUILD_ROOT),
            "environment": dict(sorted(MODULE.BUILD_ENVIRONMENT.items())),
            "gmp_configure_suffix": ["--enable-shared", "--disable-static"],
            "mpfr_configure_suffix": [
                f"--with-gmp={MODULE.CANONICAL_PREFIX}",
                "--enable-shared", "--disable-static"],
            "make_argv": ["/usr/bin/make", "-j1"],
            "install_argv": ["/usr/bin/make", "install"],
            "independent_build_count": 2,
        },
        "runs": runs,
        "derived_libraries": derived,
        "rebuild_match": True,
        "candidate_executed": False,
        "oracle_executed": False,
        "numeric_d12_executed": False,
        "qualification_decided": False,
        "d9a_reopened": False,
        "b3_unblocked": False,
        "far_selected": False,
        "production_authorized": False,
    }


def frozen_report():
    report = valid_report()
    for run in report["runs"]:
        for name, digest in MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256.items():
            run["libraries"][name]["sha256"] = digest
            run["libraries"][name]["artifacts"]["library"]["sha256"] = digest
    report["derived_libraries"] = copy.deepcopy(
        MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256)
    return report


def materialize_report_artifacts(report, root):
    library_bytes = {"gmp": b"gmp-frozen-test-library",
                     "mpfr": b"mpfr-frozen-test-library"}
    digests = {name: MODULE.hashlib.sha256(raw).hexdigest()
               for name, raw in library_bytes.items()}
    for run in report["runs"]:
        for name in ("gmp", "mpfr"):
            build = run["builds"][name]
            contents = {
                "configure.argv": "".join(
                    value + "\n" for value in build["configure_argv"]).encode(),
                "build.argv": "".join(
                    value + "\n" for value in build["build_argv"]).encode(),
                "install.argv": "".join(
                    value + "\n" for value in build["install_argv"]).encode(),
                "environment": "".join(
                    f"{key}={build['environment'][key]}\n"
                    for key in sorted(build["environment"])).encode(),
                "configure.log": b"configure output\n",
                "build.log": b"build output\n",
                "install.log": b"install output\n",
                "config.status": b"config status\n",
                "config.log": b"config log\n",
                "Makefile": b"all:\n\t@true\n",
            }
            for key, descriptor_value in build["transcripts"].items():
                path = root / descriptor_value["relative_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents[key])
                descriptor_value["byte_length"] = len(contents[key])
                descriptor_value["sha256"] = MODULE.hashlib.sha256(
                    contents[key]).hexdigest()

            library = run["libraries"][name]
            canonical = pathlib.Path(library["canonical_path"])
            if name == "gmp":
                dependencies = [str(canonical), "/usr/lib/libSystem.B.dylib"]
            else:
                dependencies = [
                    str(canonical),
                    str(MODULE.CANONICAL_PREFIX / "lib" /
                        MODULE.LIBRARIES["gmp"]["versioned_name"]),
                    "/usr/lib/libSystem.B.dylib"]
            otool_d = f"{canonical}:\n{canonical}\n".encode()
            otool_l = (f"{canonical}:\n" + "".join(
                f"\t{item} (compatibility version 1.0.0)\n"
                for item in dependencies)).encode()
            artifact_bytes = {
                "library": library_bytes[name],
                "otool_d": otool_d,
                "otool_l": otool_l,
            }
            for key, descriptor_value in library["artifacts"].items():
                path = root / descriptor_value["relative_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(artifact_bytes[key])
                if key == "library":
                    path.chmod(0o755)
                descriptor_value["byte_length"] = len(artifact_bytes[key])
                descriptor_value["sha256"] = MODULE.hashlib.sha256(
                    artifact_bytes[key]).hexdigest()
            library["byte_length"] = len(library_bytes[name])
            library["sha256"] = digests[name]
            library["otool_d_sha256"] = MODULE.hashlib.sha256(otool_d).hexdigest()
            library["otool_l_sha256"] = MODULE.hashlib.sha256(otool_l).hexdigest()
    report["derived_libraries"] = digests
    return digests


class GmpMpfrProvenancePreflightTest(unittest.TestCase):
    def test_authority_literals_and_self_test(self):
        result = MODULE.self_test()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["canonical_prefix"],
                         "/private/tmp/slimed-b2-d12-dependencies-v1")
        self.assertEqual(result["canonical_build_root"],
                         "/private/tmp/slimed-b2-d12-dependency-build-v1")
        self.assertFalse(result["candidate_executed"])
        self.assertFalse(result["numeric_d12_executed"])
        text = MODULE.AMENDMENT.read_text(encoding="utf-8")
        self.assertIn(
            "gmp_libgmp_10_dylib_sha256=" +
            MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256["gmp"], text)
        self.assertIn(
            "mpfr_libmpfr_6_dylib_sha256=" +
            MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256["mpfr"], text)
        self.assertEqual(MODULE.sha256_file(MODULE.EVIDENCE),
                         MODULE.EVIDENCE_FILE_SHA256)

    def test_complete_synthetic_report_validates_before_freeze(self):
        MODULE.validate_report(valid_report(), require_frozen=False)

    def test_report_mutation_matrix_rejects(self):
        mutations = []
        value = valid_report()
        value["archives"]["gmp"]["sha256"] = SHA_A
        mutations.append(value)
        value = valid_report()
        value["build_contract"]["canonical_prefix"] = "/private/tmp/elsewhere"
        mutations.append(value)
        value = valid_report()
        value["build_contract"]["canonical_build_root"] = "/private/tmp/elsewhere"
        mutations.append(value)
        value = valid_report()
        value["runs"] = value["runs"][:1]
        mutations.append(value)
        value = valid_report()
        value["runs"][1]["libraries"]["gmp"]["sha256"] = SHA_C
        value["runs"][1]["libraries"]["gmp"]["artifacts"]["library"]["sha256"] = SHA_C
        mutations.append(value)
        value = valid_report()
        value["runs"][0]["builds"]["mpfr"]["environment"]["CPATH"] = "/tmp/evil"
        mutations.append(value)
        value = valid_report()
        value["runs"][0]["builds"]["gmp"]["configure_argv"].append("CFLAGS=-ffast-math")
        mutations.append(value)
        value = valid_report()
        value["runs"][0]["libraries"]["mpfr"]["link_target"] = "libgmp.10.dylib"
        mutations.append(value)
        value = valid_report()
        value["candidate_executed"] = True
        mutations.append(value)
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                with self.assertRaises(MODULE.PreflightError):
                    MODULE.validate_report(mutation, require_frozen=False)

    def test_archive_bytes_must_match_frozen_digest(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            path = pathlib.Path(temporary).resolve() / "gmp.tar.xz"
            path.write_bytes(b"not the frozen archive")
            with self.assertRaisesRegex(
                    MODULE.PreflightError, "digest differs"):
                MODULE.validate_archive("gmp", path)

    def test_archive_snapshot_is_frozen_and_rejects_alias(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = pathlib.Path(temporary).resolve()
            source = root / "gmp.tar.xz"
            raw = b"frozen archive bytes"
            source.write_bytes(raw)
            destination = root / "snapshots" / "gmp.tar.xz"
            authority = copy.deepcopy(MODULE.ARCHIVES)
            authority["gmp"]["sha256"] = MODULE.hashlib.sha256(raw).hexdigest()
            with mock.patch.dict(MODULE.ARCHIVES, authority, clear=True):
                record = MODULE.snapshot_archive("gmp", source, destination)
            self.assertEqual(destination.read_bytes(), raw)
            self.assertEqual(record["sha256"],
                             MODULE.hashlib.sha256(raw).hexdigest())
            alias = root / "gmp-alias.tar.xz"
            alias.symlink_to(source.name)
            with mock.patch.dict(MODULE.ARCHIVES, authority, clear=True):
                with self.assertRaisesRegex(MODULE.PreflightError, "aliased"):
                    MODULE.snapshot_archive("gmp", alias,
                                            root / "second-snapshot.tar.xz")
            hardlink = root / "gmp-hardlink.tar.xz"
            os.link(source, hardlink)
            with mock.patch.dict(MODULE.ARCHIVES, authority, clear=True):
                with self.assertRaisesRegex(MODULE.PreflightError, "aliased"):
                    MODULE.snapshot_archive("gmp", hardlink,
                                            root / "third-snapshot.tar.xz")

    def test_derive_uses_one_sealed_snapshot_for_both_runs(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = pathlib.Path(temporary).resolve()
            gmp = root / "input-gmp.tar.xz"
            mpfr = root / "input-mpfr.tar.xz"
            gmp.write_bytes(b"gmp archive")
            mpfr.write_bytes(b"mpfr archive")
            output = root / "proof"
            prefix = root / "prefix"
            build_root = root / "build-root"
            authority = copy.deepcopy(MODULE.ARCHIVES)
            authority["gmp"]["sha256"] = MODULE.sha256_file(gmp)
            authority["mpfr"]["sha256"] = MODULE.sha256_file(mpfr)
            calls = []
            validated_paths = []
            original_validate_archive = MODULE.validate_archive

            def recording_validate_archive(name, path):
                validated_paths.append(path)
                return original_validate_archive(name, path)

            def fake_build(run_id, archives, _output):
                calls.append({key: value for key, value in archives.items()})
                (_output / f"run-{run_id.lower()}").mkdir()
                prefix.mkdir()
                return {"run_id": run_id, "builds": {}, "libraries": {
                    "gmp": {"sha256": authority["gmp"]["sha256"]},
                    "mpfr": {"sha256": authority["mpfr"]["sha256"]}}}

            args = mock.Mock(output_dir=str(output), gmp_archive=str(gmp),
                             mpfr_archive=str(mpfr))
            with mock.patch.dict(MODULE.ARCHIVES, authority, clear=True), \
                    mock.patch.object(MODULE, "CANONICAL_PREFIX", prefix), \
                    mock.patch.object(MODULE, "CANONICAL_BUILD_ROOT", build_root), \
                    mock.patch.object(MODULE, "validate_prefix_parent"), \
                    mock.patch.object(MODULE, "platform_fingerprint",
                                      return_value=MODULE.EXPECTED_PLATFORM), \
                    mock.patch.object(MODULE, "compiler_identity",
                                      return_value={"test": "compiler"}), \
                    mock.patch.object(MODULE, "git_observation",
                                      return_value={"head": "a" * 40,
                                                    "worktree_clean": True}), \
                    mock.patch.object(MODULE, "build_pair",
                                      side_effect=fake_build), \
                    mock.patch.object(MODULE, "validate_archive",
                                      side_effect=recording_validate_archive), \
                    mock.patch.object(MODULE, "validate_report"):
                MODULE.derive(args)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0], calls[1])
            for name, path in calls[0].items():
                self.assertEqual(path.parent, output / "source-archives")
                self.assertEqual(MODULE.sha256_file(path),
                                 authority[name]["sha256"])
            self.assertNotIn(gmp, validated_paths)
            self.assertNotIn(mpfr, validated_paths)
            self.assertTrue(validated_paths)
            self.assertTrue(all(path.parent == output / "source-archives"
                                for path in validated_paths))

    def test_duplicate_json_key_and_noncanonical_json_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "evidence.json"
            path.write_text('{"a":1,"a":1}', encoding="utf-8")
            with self.assertRaisesRegex(MODULE.PreflightError, "duplicate"):
                MODULE.strict_json(path)
            path.write_text('{ "a": 1 }', encoding="utf-8")
            with self.assertRaisesRegex(MODULE.PreflightError, "canonical"):
                MODULE.strict_json(path)

    def test_closed_environment_does_not_inherit_compiler_controls(self):
        with mock.patch.dict("os.environ", {
                "CPATH": "/tmp/evil", "CFLAGS": "-ffast-math",
                "CCC_OVERRIDE_OPTIONS": "+-fno-inline"}, clear=False):
            environment = MODULE.closed_environment()
        self.assertEqual(environment, MODULE.BUILD_ENVIRONMENT)
        self.assertNotIn("CPATH", environment)
        self.assertNotIn("CFLAGS", environment)
        self.assertNotIn("CCC_OVERRIDE_OPTIONS", environment)

    def test_both_library_artifacts_share_one_run_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            prefix = root / "canonical-prefix"
            library_root = prefix / "lib"
            library_root.mkdir(parents=True)
            for name, contract in MODULE.LIBRARIES.items():
                versioned = library_root / contract["versioned_name"]
                versioned.write_bytes((name + "-library").encode())
                versioned.chmod(0o755)
                (library_root / contract["link_name"]).symlink_to(
                    contract["versioned_name"])

            def fake_run(command, **_kwargs):
                target = pathlib.Path(command[-1])
                if command[1] == "-D":
                    output = f"{target}:\n{target}\n"
                else:
                    dependencies = [str(target)]
                    if target.name.startswith("libmpfr"):
                        dependencies.append(str(
                            library_root / "libgmp.10.dylib"))
                    output = f"{target}:\n" + "".join(
                        f"\t{item} (compatibility version 1.0.0)\n"
                        for item in dependencies)
                return subprocess.CompletedProcess(command, 0, output, "")

            artifact_root = root / "proof"
            artifact_root.mkdir()
            shared = artifact_root / "run-a" / "libraries"
            with mock.patch.object(MODULE, "CANONICAL_PREFIX", prefix), \
                    mock.patch.object(MODULE, "validate_prefix_parent"), \
                    mock.patch.object(MODULE, "run", side_effect=fake_run):
                gmp = MODULE.inspect_library("gmp", shared, artifact_root)
                mpfr = MODULE.inspect_library("mpfr", shared, artifact_root)
            self.assertEqual(gmp["sha256"],
                             gmp["artifacts"]["library"]["sha256"])
            self.assertEqual(mpfr["sha256"],
                             mpfr["artifacts"]["library"]["sha256"])

    def test_nonfrozen_digest_and_missing_install_cannot_verify(self):
        with self.assertRaisesRegex(MODULE.PreflightError,
                                    "differ from frozen"):
            MODULE.validate_report(valid_report(), require_frozen=True)
        with mock.patch.object(MODULE, "CANONICAL_PREFIX",
                               pathlib.Path("/private/tmp/absent-b2b-prefix")):
            with self.assertRaisesRegex(MODULE.PreflightError, "unavailable"):
                MODULE.audit_installed_library("gmp")

    def test_frozen_digest_report_validates(self):
        report = valid_report()
        for run in report["runs"]:
            for name, digest in MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256.items():
                run["libraries"][name]["sha256"] = digest
                run["libraries"][name]["artifacts"]["library"]["sha256"] = digest
        report["derived_libraries"] = copy.deepcopy(
            MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256)
        MODULE.validate_report(report, require_frozen=True)

    def test_freeze_summary_binds_complete_derivation(self):
        reviewed = MODULE.strict_json(MODULE.EVIDENCE, repository_lf=True)
        MODULE.validate_freeze_summary(reviewed)
        for mutation in (
                {**reviewed, "numeric_d12_executed": True},
                {**reviewed, "derived_libraries": {
                    **reviewed["derived_libraries"], "gmp": SHA_A}},
                {**reviewed, "runs": list(reversed(reviewed["runs"]))}):
            with self.assertRaises(MODULE.PreflightError):
                MODULE.validate_freeze_summary(mutation)

    def test_retained_artifact_bundle_is_byte_and_semantically_bound(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = pathlib.Path(temporary).resolve()
            report = valid_report()
            digests = materialize_report_artifacts(report, root)
            with mock.patch.dict(MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256,
                                 digests, clear=True):
                MODULE.validate_retained_artifacts(report, root)

                configure = (root / report["runs"][0]["builds"]["gmp"]
                             ["transcripts"]["configure.argv"]["relative_path"])
                original = configure.read_bytes()
                configure.write_bytes(original + b"--poison\n")
                descriptor_value = report["runs"][0]["builds"]["gmp"][
                    "transcripts"]["configure.argv"]
                descriptor_value["byte_length"] = configure.stat().st_size
                descriptor_value["sha256"] = MODULE.sha256_file(configure)
                with self.assertRaisesRegex(MODULE.PreflightError, "semantic"):
                    MODULE.validate_retained_artifacts(report, root)

    def test_retained_artifact_missing_digest_alias_and_hardlink_reject(self):
        for attack in ("missing", "digest", "symlink", "hardlink"):
            with self.subTest(attack=attack), \
                    tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
                root = pathlib.Path(temporary).resolve()
                report = valid_report()
                digests = materialize_report_artifacts(report, root)
                descriptor_value = report["runs"][0]["builds"]["gmp"][
                    "transcripts"]["configure.log"]
                path = root / descriptor_value["relative_path"]
                if attack == "missing":
                    path.unlink()
                elif attack == "digest":
                    descriptor_value["sha256"] = "0" * 64
                elif attack == "symlink":
                    raw = path.read_bytes()
                    target = path.with_name("configure-log-target")
                    target.write_bytes(raw)
                    path.unlink()
                    path.symlink_to(target.name)
                else:
                    raw = path.read_bytes()
                    target = path.with_name("configure-log-hardlink")
                    path.unlink()
                    target.write_bytes(raw)
                    os.link(target, path)
                with mock.patch.dict(MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256,
                                     digests, clear=True):
                    with self.assertRaises(MODULE.PreflightError):
                        MODULE.validate_retained_artifacts(report, root)

    def test_freeze_summary_requires_real_artifacts_and_archives(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = pathlib.Path(temporary).resolve()
            report = valid_report()
            digests = materialize_report_artifacts(report, root)
            report_bytes = MODULE.canonical_bytes(report)
            with mock.patch.dict(MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256,
                                 digests, clear=True), \
                    mock.patch.object(MODULE, "validate_source_archives") as audit:
                summary = MODULE.freeze_summary(
                    report, report_bytes, root,
                    pathlib.Path("gmp.tar.xz"), pathlib.Path("mpfr.tar.xz"))
            audit.assert_called_once()
            self.assertEqual(summary["derivation_bundle"]["sha256"],
                             MODULE.hashlib.sha256(report_bytes).hexdigest())
            with self.assertRaises(MODULE.PreflightError):
                MODULE.validate_freeze_summary(summary)

    def test_installed_tree_audit_rejects_links_modes_hardlinks_and_otool(self):
        attacks = ("wrong-link", "missing-link", "mode", "hardlink", "otool")
        for attack in attacks:
            with self.subTest(attack=attack), \
                    tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
                root = pathlib.Path(temporary).resolve()
                prefix = root / "prefix"
                library_root = prefix / "lib"
                library_root.mkdir(parents=True)
                for name, contract in MODULE.LIBRARIES.items():
                    versioned = library_root / contract["versioned_name"]
                    versioned.write_bytes((name + "-library").encode())
                    versioned.chmod(0o755)
                    (library_root / contract["link_name"]).symlink_to(
                        contract["versioned_name"])
                if attack == "wrong-link":
                    link = library_root / "libgmp.dylib"
                    link.unlink()
                    link.symlink_to("libmpfr.6.dylib")
                elif attack == "missing-link":
                    (library_root / "libgmp.dylib").unlink()
                elif attack == "mode":
                    (library_root / "libgmp.10.dylib").chmod(0o600)
                elif attack == "hardlink":
                    os.link(library_root / "libgmp.10.dylib",
                            library_root / "gmp-hardlink")

                def fake_run(command, **_kwargs):
                    target = pathlib.Path(command[-1])
                    if command[1] == "-D":
                        identity = ("/wrong/install/name" if attack == "otool"
                                    and target.name.startswith("libgmp")
                                    else str(target))
                        output = f"{target}:\n{identity}\n"
                    else:
                        dependencies = [str(target)]
                        if target.name.startswith("libmpfr"):
                            dependencies.append(str(
                                library_root / "libgmp.10.dylib"))
                        output = f"{target}:\n" + "".join(
                            f"\t{item} (compatibility version 1.0.0)\n"
                            for item in dependencies)
                    return subprocess.CompletedProcess(command, 0, output, "")

                with mock.patch.object(MODULE, "CANONICAL_PREFIX", prefix), \
                        mock.patch.object(MODULE, "validate_prefix_parent"), \
                        mock.patch.object(MODULE, "run", side_effect=fake_run):
                    with self.assertRaises(MODULE.PreflightError):
                        MODULE.audit_installed_library("gmp")

    def test_installed_tree_audit_rejects_symlinked_prefix(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = pathlib.Path(temporary).resolve()
            real = root / "real"
            (real / "lib").mkdir(parents=True)
            alias = root / "alias"
            alias.symlink_to(real.name)
            with mock.patch.object(MODULE, "CANONICAL_PREFIX", alias), \
                    mock.patch.object(MODULE, "validate_prefix_parent"):
                with self.assertRaisesRegex(MODULE.PreflightError, "aliased"):
                    MODULE.audit_installed_library("gmp")

    def test_git_observation_ignores_redirects_and_rejects_hidden_flags(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            repo = pathlib.Path(temporary).resolve()
            subprocess.run(["/usr/bin/git", "init", "-q", str(repo)], check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("reviewed\n", encoding="utf-8")
            subprocess.run(["/usr/bin/git", "-C", str(repo), "add", "tracked.txt"],
                           check=True)
            subprocess.run([
                "/usr/bin/git", "-C", str(repo), "-c", "user.name=review",
                "-c", "user.email=review@example.invalid", "commit", "-qm",
                "reviewed"], check=True)
            expected = subprocess.run(
                ["/usr/bin/git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True).stdout.strip()
            with mock.patch.object(MODULE, "ROOT", repo), \
                    mock.patch.dict(os.environ, {
                        "GIT_DIR": str(MODULE.ROOT / ".git"),
                        "GIT_WORK_TREE": str(MODULE.ROOT)}, clear=False):
                self.assertEqual(MODULE.git_observation()["head"], expected)
            subprocess.run(["/usr/bin/git", "-C", str(repo), "update-index",
                            "--assume-unchanged", "tracked.txt"], check=True)
            with mock.patch.object(MODULE, "ROOT", repo):
                with self.assertRaisesRegex(MODULE.PreflightError,
                                            "assume-unchanged"):
                    MODULE.git_observation()

    def test_pending_constant_is_never_admissible(self):
        with mock.patch.dict(MODULE.FROZEN_PHYSICAL_LIBRARY_SHA256,
                             {"gmp": "PENDING", "mpfr": "PENDING"}, clear=True):
            with self.assertRaisesRegex(MODULE.PreflightError, "pending"):
                MODULE.validate_report(valid_report(), require_frozen=True)
            with self.assertRaisesRegex(MODULE.PreflightError, "pending"):
                MODULE.verify_installed(pathlib.Path("gmp"),
                                        pathlib.Path("mpfr"))

    def test_canonical_encoding_is_stable(self):
        report = valid_report()
        encoded = MODULE.canonical_bytes(report)
        self.assertEqual(encoded, MODULE.canonical_bytes(json.loads(encoded)))
        self.assertNotIn(b"\n", encoded)


if __name__ == "__main__":
    unittest.main()
