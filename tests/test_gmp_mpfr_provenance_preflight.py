import copy
import importlib.util
import json
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
        "git": {"head": "a" * 40, "worktree_clean": True},
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
        self.assertIn("gmp_libgmp_10_dylib_sha256=PENDING", text)
        self.assertIn("mpfr_libmpfr_6_dylib_sha256=PENDING", text)

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
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "gmp.tar.xz"
            path.write_bytes(b"not the frozen archive")
            with self.assertRaisesRegex(
                    MODULE.PreflightError, "digest differs"):
                MODULE.validate_archive("gmp", path)

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
                    output = (f"{target}:\n\t{library_root / 'libgmp.10.dylib'} "
                              "(compatibility version 1.0.0)\n")
                return subprocess.CompletedProcess(command, 0, output, "")

            artifact_root = root / "proof"
            artifact_root.mkdir()
            shared = artifact_root / "run-a" / "libraries"
            with mock.patch.object(MODULE, "CANONICAL_PREFIX", prefix), \
                    mock.patch.object(MODULE, "run", side_effect=fake_run):
                gmp = MODULE.inspect_library("gmp", shared, artifact_root)
                mpfr = MODULE.inspect_library("mpfr", shared, artifact_root)
            self.assertEqual(gmp["sha256"],
                             gmp["artifacts"]["library"]["sha256"])
            self.assertEqual(mpfr["sha256"],
                             mpfr["artifacts"]["library"]["sha256"])

    def test_pending_digest_cannot_verify_report_or_install(self):
        with self.assertRaisesRegex(MODULE.PreflightError, "pending"):
            MODULE.validate_report(valid_report(), require_frozen=True)
        with self.assertRaisesRegex(MODULE.PreflightError, "pending"):
            MODULE.verify_installed()

    def test_canonical_encoding_is_stable(self):
        report = valid_report()
        encoded = MODULE.canonical_bytes(report)
        self.assertEqual(encoded, MODULE.canonical_bytes(json.loads(encoded)))
        self.assertNotIn(b"\n", encoded)


if __name__ == "__main__":
    unittest.main()
