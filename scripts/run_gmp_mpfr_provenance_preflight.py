#!/usr/bin/env python3
"""Derive and verify the frozen physical-host GMP/MPFR library authority.

This is a proof-only B2b preflight.  It never launches a candidate, an oracle,
or a D12 workload.  Derivation performs two clean source builds at one literal
install prefix and requires byte-identical installed libraries before emitting
the evidence record used to freeze their digests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "docs/anchored_row_dependency_provenance_amendment.md"
PLAN = ROOT / "docs/bfr_loop_backend_plan_macos.md"

SCHEMA = "b2-gmp-mpfr-provenance-preflight-v1"
CANONICAL_PREFIX = pathlib.Path(
    "/private/tmp/slimed-b2-d12-dependencies-v1")
COMPILER = pathlib.Path(
    "/Library/Developer/CommandLineTools/usr/bin/clang")
COMPILER_CXX = pathlib.Path(
    "/Library/Developer/CommandLineTools/usr/bin/clang++")
COMPILER_VERSION = "Apple clang version 21.0.0 (clang-2100.1.1.101)"
SDKROOT = pathlib.Path(
    "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk")

ARCHIVES = {
    "gmp": {
        "identity": "gmp-6.3.0",
        "sha256": "a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898",
        "url": "https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz",
    },
    "mpfr": {
        "identity": "mpfr-4.2.2",
        "sha256": "b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01",
        "url": "https://ftp.gnu.org/gnu/mpfr/mpfr-4.2.2.tar.xz",
    },
}

EXPECTED_PLATFORM = {
    "architecture": "arm64",
    "chip": "Apple M5",
    "hw_logicalcpu": 10,
    "hw_memsize_bytes": 25769803776,
    "hw_model": "Mac17,2",
    "hw_ncpu": 10,
    "hw_perflevel0_logicalcpu": 4,
    "hw_perflevel0_physicalcpu": 4,
    "hw_perflevel1_logicalcpu": 6,
    "hw_perflevel1_physicalcpu": 6,
    "hw_physicalcpu": 10,
    "kern_hv_vmm_present": 0,
    "macos_build": "25F80",
    "macos_version": "26.5.1",
}

# Filled only after two exact source builds at CANONICAL_PREFIX agree and the
# generated evidence has been reviewed.  PENDING is rejected by --verify.
FROZEN_PHYSICAL_LIBRARY_SHA256 = {
    "gmp": "PENDING",
    "mpfr": "PENDING",
}

BUILD_ENVIRONMENT = {
    "AR": "/usr/bin/ar",
    "CC": str(COMPILER),
    "CXX": str(COMPILER_CXX),
    "LANG": "C",
    "LC_ALL": "C",
    "NM": "/usr/bin/nm",
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "RANLIB": "/usr/bin/ranlib",
    "SDKROOT": str(SDKROOT),
    "SOURCE_DATE_EPOCH": "0",
    "STRIP": "/usr/bin/strip",
    "TZ": "UTC",
    "ZERO_AR_DATE": "1",
}

LIBRARIES = {
    "gmp": {
        "link_name": "libgmp.dylib",
        "versioned_name": "libgmp.10.dylib",
    },
    "mpfr": {
        "link_name": "libmpfr.dylib",
        "versioned_name": "libmpfr.6.dylib",
    },
}


class PreflightError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PreflightError(message)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")


def strict_json(path: pathlib.Path) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    require(raw == canonical_bytes(value), "evidence is not canonical JSON")
    return value


def run(command: list[str], *, cwd: pathlib.Path | None = None,
        env: dict[str, str] | None = None, timeout: int = 1800,
        stdout_path: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command, cwd=str(cwd) if cwd else None, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=timeout, check=False)
    if stdout_path is not None:
        stdout_path.write_text(completed.stdout, encoding="utf-8")
    require(completed.returncode == 0,
            "command failed: " + " ".join(command) + "\n" + completed.stdout[-4000:])
    return completed


def exact_command_output(command: list[str]) -> str:
    return run(command, timeout=60).stdout.strip()


def sysctl_int(name: str) -> int:
    return int(exact_command_output(["/usr/sbin/sysctl", "-n", name]))


def platform_fingerprint() -> dict[str, Any]:
    sw_vers = {
        key: exact_command_output(["/usr/bin/sw_vers", flag])
        for key, flag in (("macos_version", "-productVersion"),
                          ("macos_build", "-buildVersion"))
    }
    chip = exact_command_output([
        "/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"])
    return {
        "architecture": exact_command_output(["/usr/bin/uname", "-m"]),
        "chip": chip,
        "hw_logicalcpu": sysctl_int("hw.logicalcpu"),
        "hw_memsize_bytes": sysctl_int("hw.memsize"),
        "hw_model": exact_command_output(["/usr/sbin/sysctl", "-n", "hw.model"]),
        "hw_ncpu": sysctl_int("hw.ncpu"),
        "hw_perflevel0_logicalcpu": sysctl_int("hw.perflevel0.logicalcpu"),
        "hw_perflevel0_physicalcpu": sysctl_int("hw.perflevel0.physicalcpu"),
        "hw_perflevel1_logicalcpu": sysctl_int("hw.perflevel1.logicalcpu"),
        "hw_perflevel1_physicalcpu": sysctl_int("hw.perflevel1.physicalcpu"),
        "hw_physicalcpu": sysctl_int("hw.physicalcpu"),
        "kern_hv_vmm_present": sysctl_int("kern.hv_vmm_present"),
        **sw_vers,
    }


def compiler_identity() -> dict[str, str]:
    require(COMPILER.is_file() and COMPILER_CXX.is_file(),
            "frozen compiler is unavailable")
    require(SDKROOT.is_dir(), "frozen SDK is unavailable")
    version = exact_command_output([str(COMPILER_CXX), "--version"]).splitlines()[0]
    require(version == COMPILER_VERSION, "frozen compiler version mismatch")
    return {"c": str(COMPILER), "cxx": str(COMPILER_CXX),
            "version": version, "sdkroot": str(SDKROOT)}


def git_observation() -> dict[str, Any]:
    head = exact_command_output(["/usr/bin/git", "-C", str(ROOT),
                                 "rev-parse", "HEAD"])
    status = exact_command_output(["/usr/bin/git", "-C", str(ROOT),
                                   "status", "--porcelain=v1",
                                   "--untracked-files=all"])
    return {"head": head, "worktree_clean": status == ""}


def validate_archive(name: str, path: pathlib.Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"{name} archive is unavailable or aliased")
    digest = sha256_file(path)
    require(digest == ARCHIVES[name]["sha256"],
            f"{name} archive digest differs from frozen authority")
    return {**ARCHIVES[name], "byte_length": path.stat().st_size}


def closed_environment() -> dict[str, str]:
    return dict(BUILD_ENVIRONMENT)


def validate_prefix_parent() -> None:
    require(CANONICAL_PREFIX.is_absolute(), "canonical prefix is not absolute")
    require(CANONICAL_PREFIX.parent == pathlib.Path("/private/tmp"),
            "canonical prefix parent drift")
    for component in (pathlib.Path("/private"), pathlib.Path("/private/tmp")):
        require(component.is_dir() and not component.is_symlink(),
                "canonical prefix parent is unavailable or aliased")
        require(component.resolve(strict=True) == component,
                "canonical prefix parent is not physically canonical")


def configure_argv(name: str, source: pathlib.Path) -> list[str]:
    argv = [str(source / "configure"), f"--prefix={CANONICAL_PREFIX}"]
    if name == "mpfr":
        argv.append(f"--with-gmp={CANONICAL_PREFIX}")
    argv.extend(["--enable-shared", "--disable-static"])
    return argv


def write_lines(path: pathlib.Path, values: list[str]) -> None:
    path.write_text("".join(value + "\n" for value in values), encoding="utf-8")


def artifact_descriptor(path: pathlib.Path,
                        output_root: pathlib.Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    root = output_root.resolve(strict=True)
    require(resolved.is_relative_to(root), "proof artifact escapes output root")
    relative = resolved.relative_to(root).as_posix()
    require(relative and not relative.startswith("/") and ".." not in relative.split("/"),
            "proof artifact path is noncanonical")
    return {"relative_path": relative, "byte_length": resolved.stat().st_size,
            "sha256": sha256_file(resolved)}


def extract_archive(archive: pathlib.Path, destination: pathlib.Path) -> None:
    require(not destination.exists(), "source extraction destination already exists")
    destination.mkdir(parents=True)
    run(["/usr/bin/tar", "-xf", str(archive), "-C", str(destination),
         "--strip-components=1"], timeout=300)
    require((destination / "configure").is_file(),
            "extracted source lacks configure")


def build_dependency(name: str, source: pathlib.Path,
                     transcript: pathlib.Path,
                     output_root: pathlib.Path) -> dict[str, Any]:
    transcript.mkdir(parents=True)
    configure = configure_argv(name, source)
    build = ["/usr/bin/make", "-j1"]
    install = ["/usr/bin/make", "install"]
    write_lines(transcript / "configure.argv", configure)
    write_lines(transcript / "build.argv", build)
    write_lines(transcript / "install.argv", install)
    write_lines(transcript / "environment", [
        f"{key}={BUILD_ENVIRONMENT[key]}" for key in sorted(BUILD_ENVIRONMENT)])
    env = closed_environment()
    run(configure, cwd=source, env=env, timeout=900,
        stdout_path=transcript / "configure.log")
    run(build, cwd=source, env=env, timeout=1800,
        stdout_path=transcript / "build.log")
    run(install, cwd=source, env=env, timeout=900,
        stdout_path=transcript / "install.log")
    for retained in ("config.status", "config.log", "Makefile"):
        candidate = source / retained
        require(candidate.is_file(), f"{name} lacks {retained}")
        shutil.copy2(candidate, transcript / retained)
    transcript_names = (
        "configure.argv", "build.argv", "install.argv", "environment",
        "configure.log", "build.log", "install.log", "config.status",
        "config.log", "Makefile")
    return {
        "source_root_relative": source.resolve().relative_to(
            output_root.resolve()).as_posix(),
        "configure_argv": configure,
        "build_argv": build,
        "install_argv": install,
        "environment": dict(sorted(BUILD_ENVIRONMENT.items())),
        "transcripts": {
            retained: artifact_descriptor(transcript / retained, output_root)
            for retained in transcript_names
        },
    }


def inspect_library(name: str, output: pathlib.Path,
                    output_root: pathlib.Path) -> dict[str, Any]:
    contract = LIBRARIES[name]
    link = CANONICAL_PREFIX / "lib" / contract["link_name"]
    versioned = CANONICAL_PREFIX / "lib" / contract["versioned_name"]
    for component in (CANONICAL_PREFIX, CANONICAL_PREFIX / "lib"):
        require(component.is_dir() and not component.is_symlink() and
                component.resolve(strict=True) == component,
                f"{name} install path has an alias")
    require(link.is_symlink(), f"{name} unversioned library is not a symlink")
    require(os.readlink(link) == contract["versioned_name"],
            f"{name} unversioned symlink target drift")
    require(versioned.is_file() and not versioned.is_symlink(),
            f"{name} versioned library unavailable")
    require(stat.S_IMODE(versioned.stat().st_mode) == 0o755,
            f"{name} versioned library mode drift")
    otool_d = run(["/usr/bin/otool", "-D", str(versioned)], timeout=60).stdout
    otool_l = run(["/usr/bin/otool", "-L", str(versioned)], timeout=60).stdout
    expected_id = str(CANONICAL_PREFIX / "lib" / contract["versioned_name"])
    require(expected_id in otool_d.splitlines()[1:],
            f"{name} LC_ID_DYLIB is not the canonical prefix")
    if name == "mpfr":
        expected_gmp = str(CANONICAL_PREFIX / "lib" /
                           LIBRARIES["gmp"]["versioned_name"])
        require(expected_gmp in otool_l,
                "MPFR LC_LOAD_DYLIB does not name canonical GMP")
    output.mkdir(parents=True, exist_ok=True)
    copied = output / contract["versioned_name"]
    shutil.copy2(versioned, copied)
    (output / f"{name}.otool-D.txt").write_text(otool_d, encoding="utf-8")
    (output / f"{name}.otool-L.txt").write_text(otool_l, encoding="utf-8")
    return {
        "canonical_path": str(versioned),
        "link_path": str(link),
        "link_target": os.readlink(link),
        "byte_length": versioned.stat().st_size,
        "mode": "0755",
        "sha256": sha256_file(versioned),
        "otool_d_sha256": hashlib.sha256(otool_d.encode()).hexdigest(),
        "otool_l_sha256": hashlib.sha256(otool_l.encode()).hexdigest(),
        "artifacts": {
            "library": artifact_descriptor(copied, output_root),
            "otool_d": artifact_descriptor(output / f"{name}.otool-D.txt",
                                             output_root),
            "otool_l": artifact_descriptor(output / f"{name}.otool-L.txt",
                                             output_root),
        },
    }


def build_pair(run_id: str, archives: dict[str, pathlib.Path],
               output: pathlib.Path) -> dict[str, Any]:
    require(not CANONICAL_PREFIX.exists(),
            "canonical prefix must be absent before each independent build")
    run_root = output / f"run-{run_id.lower()}"
    require(not run_root.exists(), "independent build output already exists")
    run_root.mkdir(parents=True)
    result: dict[str, Any] = {"run_id": run_id, "builds": {}}
    for name in ("gmp", "mpfr"):
        source = run_root / f"{name}-source"
        extract_archive(archives[name], source)
        result["builds"][name] = build_dependency(
            name, source, run_root / f"{name}-transcript", output)
    result["libraries"] = {
        name: inspect_library(name, run_root / "libraries", output)
        for name in ("gmp", "mpfr")
    }
    return result


def validate_report(report: Any, *, require_frozen: bool) -> None:
    require(isinstance(report, dict), "evidence must be an object")
    required = {
        "schema", "authority", "git", "platform", "compiler", "archives",
        "build_contract", "runs", "derived_libraries", "rebuild_match",
        "candidate_executed", "oracle_executed", "numeric_d12_executed",
        "qualification_decided", "d9a_reopened", "b3_unblocked",
        "far_selected", "production_authorized",
    }
    require(set(report) == required, "evidence members drift")
    require(report["schema"] == SCHEMA, "evidence schema drift")
    require(report["authority"] == {
        "amendment": "docs/anchored_row_dependency_provenance_amendment.md",
        "plan": "docs/bfr_loop_backend_plan_macos.md",
        "threat_model": "independent_rederivation_not_host_operator_resistance",
    }, "authority drift")
    require(isinstance(report["git"], dict) and
            set(report["git"]) == {"head", "worktree_clean"},
            "Git observation members drift")
    require(isinstance(report["git"]["head"], str) and
            len(report["git"]["head"]) == 40 and
            all(ch in "0123456789abcdef" for ch in report["git"]["head"]),
            "Git head malformed")
    require(report["git"]["worktree_clean"] is True,
            "derivation Git worktree was not clean")
    require(report["platform"] == EXPECTED_PLATFORM, "physical fingerprint drift")
    require(report["compiler"] == {
        "c": str(COMPILER), "cxx": str(COMPILER_CXX),
        "version": COMPILER_VERSION, "sdkroot": str(SDKROOT)},
        "compiler authority drift")
    require(report["archives"] == ARCHIVES, "archive authority drift")
    require(report["build_contract"] == {
        "canonical_prefix": str(CANONICAL_PREFIX),
        "environment": dict(sorted(BUILD_ENVIRONMENT.items())),
        "gmp_configure_suffix": ["--enable-shared", "--disable-static"],
        "mpfr_configure_suffix": [f"--with-gmp={CANONICAL_PREFIX}",
                                  "--enable-shared", "--disable-static"],
        "make_argv": ["/usr/bin/make", "-j1"],
        "install_argv": ["/usr/bin/make", "install"],
        "independent_build_count": 2,
    }, "build contract drift")
    require(isinstance(report["runs"], list) and len(report["runs"]) == 2,
            "exactly two independent runs required")
    require([item.get("run_id") for item in report["runs"]] == ["A", "B"],
            "independent build order drift")
    source_roots: set[str] = set()
    for item in report["runs"]:
        require(set(item) == {"run_id", "builds", "libraries"},
                "run members drift")
        require(set(item["builds"]) == {"gmp", "mpfr"}, "build set drift")
        require(set(item["libraries"]) == {"gmp", "mpfr"}, "library set drift")
        for name in ("gmp", "mpfr"):
            build = item["builds"][name]
            require(set(build) == {
                "source_root_relative", "configure_argv", "build_argv",
                "install_argv", "environment", "transcripts"},
                f"{name} build record members drift")
            expected_source = (
                f"run-{item['run_id'].lower()}/{name}-source")
            require(build["source_root_relative"] == expected_source,
                    f"{name} source root drift")
            require(expected_source not in source_roots,
                    "independent source roots collide")
            source_roots.add(expected_source)
            configure = build["configure_argv"]
            require(isinstance(configure, list), f"{name} configure argv malformed")
            expected_suffix = [f"--prefix={CANONICAL_PREFIX}"]
            if name == "mpfr":
                expected_suffix.append(f"--with-gmp={CANONICAL_PREFIX}")
            expected_suffix.extend(["--enable-shared", "--disable-static"])
            require(configure[1:] == expected_suffix and
                    pathlib.PurePosixPath(configure[0]).name == "configure" and
                    pathlib.PurePosixPath(configure[0]).is_absolute(),
                    f"{name} configure argv drift")
            require(build["build_argv"] == ["/usr/bin/make", "-j1"],
                    f"{name} build argv drift")
            require(build["install_argv"] == ["/usr/bin/make", "install"],
                    f"{name} install argv drift")
            require(build["environment"] == dict(sorted(BUILD_ENVIRONMENT.items())),
                    f"{name} closed environment drift")
            transcript_names = {
                "configure.argv", "build.argv", "install.argv", "environment",
                "configure.log", "build.log", "install.log", "config.status",
                "config.log", "Makefile"}
            require(set(build["transcripts"]) == transcript_names,
                    f"{name} transcript inventory drift")
            for transcript_name, descriptor in build["transcripts"].items():
                require(set(descriptor) == {"relative_path", "byte_length", "sha256"},
                        f"{name} transcript descriptor members drift")
                expected_prefix = (
                    f"run-{item['run_id'].lower()}/{name}-transcript/")
                require(descriptor["relative_path"] ==
                        expected_prefix + transcript_name,
                        f"{name} transcript path drift")
                require(isinstance(descriptor["byte_length"], int) and
                        descriptor["byte_length"] > 0,
                        f"{name} transcript byte length malformed")
                require(isinstance(descriptor["sha256"], str) and
                        len(descriptor["sha256"]) == 64 and
                        all(ch in "0123456789abcdef"
                            for ch in descriptor["sha256"]),
                        f"{name} transcript digest malformed")
            library = item["libraries"][name]
            require(set(library) == {
                "canonical_path", "link_path", "link_target", "byte_length",
                "mode", "sha256", "otool_d_sha256", "otool_l_sha256",
                "artifacts"}, f"{name} library record members drift")
            require(library["canonical_path"] == str(
                CANONICAL_PREFIX / "lib" / LIBRARIES[name]["versioned_name"]),
                f"{name} canonical path drift")
            require(library["link_path"] == str(
                CANONICAL_PREFIX / "lib" / LIBRARIES[name]["link_name"]),
                f"{name} link path drift")
            require(library["link_target"] == LIBRARIES[name]["versioned_name"],
                    f"{name} link target drift")
            require(library["mode"] == "0755", f"{name} mode drift")
            for field in ("sha256", "otool_d_sha256", "otool_l_sha256"):
                require(isinstance(library[field], str) and
                        len(library[field]) == 64 and
                        all(ch in "0123456789abcdef" for ch in library[field]),
                        f"{name} {field} malformed")
            require(isinstance(library["byte_length"], int) and
                    library["byte_length"] > 0, f"{name} byte length malformed")
            require(set(library["artifacts"]) == {
                "library", "otool_d", "otool_l"},
                f"{name} artifact inventory drift")
            expected_artifacts = {
                "library": LIBRARIES[name]["versioned_name"],
                "otool_d": f"{name}.otool-D.txt",
                "otool_l": f"{name}.otool-L.txt",
            }
            for artifact_name, descriptor in library["artifacts"].items():
                require(set(descriptor) == {"relative_path", "byte_length", "sha256"},
                        f"{name} artifact descriptor members drift")
                require(descriptor["relative_path"] ==
                        f"run-{item['run_id'].lower()}/libraries/" +
                        expected_artifacts[artifact_name],
                        f"{name} artifact path drift")
                require(isinstance(descriptor["byte_length"], int) and
                        descriptor["byte_length"] > 0,
                        f"{name} artifact byte length malformed")
                require(isinstance(descriptor["sha256"], str) and
                        len(descriptor["sha256"]) == 64,
                        f"{name} artifact digest malformed")
            require(library["artifacts"]["library"]["sha256"] ==
                    library["sha256"], f"{name} copied library digest drift")
            require(library["artifacts"]["library"]["byte_length"] ==
                    library["byte_length"], f"{name} copied library length drift")
            require(library["artifacts"]["otool_d"]["sha256"] ==
                    library["otool_d_sha256"], f"{name} otool-D digest drift")
            require(library["artifacts"]["otool_l"]["sha256"] ==
                    library["otool_l_sha256"], f"{name} otool-L digest drift")
    derived: dict[str, str] = {}
    for name in ("gmp", "mpfr"):
        first = report["runs"][0]["libraries"][name]
        second = report["runs"][1]["libraries"][name]
        comparable_fields = (
            "canonical_path", "link_path", "link_target", "byte_length", "mode",
            "sha256", "otool_d_sha256", "otool_l_sha256")
        require({field: first[field] for field in comparable_fields} ==
                {field: second[field] for field in comparable_fields},
                f"{name} independent rebuild differs")
        derived[name] = first["sha256"]
    require(report["derived_libraries"] == derived,
            "derived library digest summary drift")
    require(report["rebuild_match"] is True, "rebuild match must be true")
    if require_frozen:
        require(all(FROZEN_PHYSICAL_LIBRARY_SHA256[name] != "PENDING"
                    for name in ("gmp", "mpfr")),
                "frozen physical library digests are pending")
        require(derived == FROZEN_PHYSICAL_LIBRARY_SHA256,
                "derived libraries differ from frozen physical authority")
    for field in ("candidate_executed", "oracle_executed",
                  "numeric_d12_executed", "qualification_decided",
                  "d9a_reopened", "b3_unblocked", "far_selected",
                  "production_authorized"):
        require(report[field] is False, f"{field} must remain false")


def derive(args: argparse.Namespace) -> dict[str, Any]:
    output = pathlib.Path(args.output_dir).resolve()
    require(str(output).startswith("/private/tmp/"),
            "derivation output must be below /private/tmp")
    require(not output.exists(), "derivation output already exists")
    validate_prefix_parent()
    require(not CANONICAL_PREFIX.exists(), "canonical prefix already exists")
    archives = {
        "gmp": pathlib.Path(args.gmp_archive).resolve(),
        "mpfr": pathlib.Path(args.mpfr_archive).resolve(),
    }
    archive_records = {
        name: validate_archive(name, path) for name, path in archives.items()
    }
    require({name: {key: value for key, value in record.items()
                    if key != "byte_length"}
             for name, record in archive_records.items()} == ARCHIVES,
            "archive records drift")
    platform = platform_fingerprint()
    require(platform == EXPECTED_PLATFORM,
            "derivation host differs from frozen physical fingerprint")
    compiler = compiler_identity()
    git = git_observation()
    require(git["worktree_clean"] is True,
            "derivation requires an empty exact-head worktree")
    output.mkdir(parents=True)
    first = build_pair("A", archives, output)
    preserved = output / "run-a" / "installed-tree"
    require(not preserved.exists(), "run A installed tree already exists")
    CANONICAL_PREFIX.rename(preserved)
    second = build_pair("B", archives, output)
    report = {
        "schema": SCHEMA,
        "authority": {
            "amendment": "docs/anchored_row_dependency_provenance_amendment.md",
            "plan": "docs/bfr_loop_backend_plan_macos.md",
            "threat_model": "independent_rederivation_not_host_operator_resistance",
        },
        "git": git,
        "platform": platform,
        "compiler": compiler,
        "archives": ARCHIVES,
        "build_contract": {
            "canonical_prefix": str(CANONICAL_PREFIX),
            "environment": dict(sorted(BUILD_ENVIRONMENT.items())),
            "gmp_configure_suffix": ["--enable-shared", "--disable-static"],
            "mpfr_configure_suffix": [f"--with-gmp={CANONICAL_PREFIX}",
                                      "--enable-shared", "--disable-static"],
            "make_argv": ["/usr/bin/make", "-j1"],
            "install_argv": ["/usr/bin/make", "install"],
            "independent_build_count": 2,
        },
        "runs": [first, second],
        "derived_libraries": {
            name: first["libraries"][name]["sha256"]
            for name in ("gmp", "mpfr")
        },
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
    validate_report(report, require_frozen=False)
    report_path = output / "b2-gmp-mpfr-provenance-evidence.json"
    report_path.write_bytes(canonical_bytes(report))
    return report


def verify_installed() -> dict[str, str]:
    require(all(value != "PENDING"
                for value in FROZEN_PHYSICAL_LIBRARY_SHA256.values()),
            "frozen physical library digests are pending")
    result = {}
    for name, contract in LIBRARIES.items():
        path = CANONICAL_PREFIX / "lib" / contract["versioned_name"]
        require(path.is_file() and not path.is_symlink(),
                f"frozen {name} installed library unavailable")
        digest = sha256_file(path)
        require(digest == FROZEN_PHYSICAL_LIBRARY_SHA256[name],
                f"frozen {name} installed library digest drift")
        result[name] = digest
    return result


def self_test() -> dict[str, Any]:
    require(AMENDMENT.is_file() and PLAN.is_file(), "authority document unavailable")
    text = AMENDMENT.read_text(encoding="utf-8")
    for literal in (str(CANONICAL_PREFIX), ARCHIVES["gmp"]["sha256"],
                    ARCHIVES["mpfr"]["sha256"], COMPILER_VERSION,
                    "independent_rederivation_not_host_operator_resistance"):
        require(literal in text, f"amendment lacks frozen literal {literal}")
    return {
        "status": "ok",
        "schema": SCHEMA,
        "canonical_prefix": str(CANONICAL_PREFIX),
        "archives": {name: value["sha256"] for name, value in ARCHIVES.items()},
        "frozen_library_digests": FROZEN_PHYSICAL_LIBRARY_SHA256,
        "candidate_executed": False,
        "oracle_executed": False,
        "numeric_d12_executed": False,
        "qualification_decided": False,
        "d9a_reopened": False,
        "b3_unblocked": False,
        "far_selected": False,
        "production_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--derive", action="store_true")
    modes.add_argument("--verify-report")
    modes.add_argument("--verify-installed", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--gmp-archive")
    parser.add_argument("--mpfr-archive")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    try:
        if args.self_test:
            result = self_test()
        elif args.derive:
            require(args.gmp_archive and args.mpfr_archive and args.output_dir,
                    "--derive requires both archives and --output-dir")
            result = derive(args)
        elif args.verify_report:
            report = strict_json(pathlib.Path(args.verify_report).resolve())
            validate_report(report, require_frozen=True)
            result = {"status": "ok", "derived_libraries":
                      report["derived_libraries"]}
        else:
            result = {"status": "ok", "installed_libraries": verify_installed()}
    except (OSError, ValueError, PreflightError, subprocess.TimeoutExpired) as exc:
        print(f"B2 dependency provenance preflight failed: {exc}", file=sys.stderr)
        return 1
    if args.json or args.derive or args.verify_report or args.verify_installed:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print("B2 GMP/MPFR provenance preflight: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
