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
EVIDENCE = ROOT / "docs/anchored_row_dependency_provenance_evidence.json"
PLAN = ROOT / "docs/bfr_loop_backend_plan_macos.md"
EVIDENCE_FILE_SHA256 = "59e8cb382d472e8e291482d0f1ad52cd60708f231446cc2f132bc30e277428de"
DERIVATION_START_HEAD = "a482cbc445d506679a73c48847d4cda0bc55df18"

SCHEMA = "b2-gmp-mpfr-provenance-preflight-v1"
FREEZE_SCHEMA = "b2-gmp-mpfr-provenance-freeze-v1"
CANONICAL_PREFIX = pathlib.Path(
    "/private/tmp/slimed-b2-d12-dependencies-v1")
CANONICAL_BUILD_ROOT = pathlib.Path(
    "/private/tmp/slimed-b2-d12-dependency-build-v1")
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

# Derived by two exact source builds at CANONICAL_PREFIX from clean head
# a482cbc445d506679a73c48847d4cda0bc55df18.  The amendment remains proposed
# until exact-SHA reviews, merge, and explicit user approval all complete.
FROZEN_PHYSICAL_LIBRARY_SHA256 = {
    "gmp": "f872fbd53e7a265961e6c79ae846741637f59a28c04a839db55724bd12bbfb32",
    "mpfr": "2b51afa01ece4b200eacf92a318c38097595ab8cd656e0602cb0e55f9cce247e",
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

GIT_ENVIRONMENT = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "TMPDIR": "/private/tmp",
}

AUDIT_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "TMPDIR": "/private/tmp",
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


def strict_json(path: pathlib.Path, *, repository_lf: bool = False) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    raw = path.read_bytes()
    payload = raw[:-1] if repository_lf and raw.endswith(b"\n") else raw
    value = json.loads(payload.decode("utf-8"), object_pairs_hook=pairs)
    expected = canonical_bytes(value) + (b"\n" if repository_lf else b"")
    require(raw == expected, "evidence is not canonical JSON")
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


def exact_git_output(arguments: list[str]) -> str:
    return run(["/usr/bin/git", "-C", str(ROOT), *arguments],
               env=GIT_ENVIRONMENT, timeout=60).stdout


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


def _git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _parse_git_index(raw: str) -> dict[str, tuple[str, str]]:
    records: dict[str, tuple[str, str]] = {}
    for record in raw.split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, digest, stage = metadata.split(" ")
        require(stage == "0", "Git index has an unmerged entry")
        require(path not in records, "Git index path is duplicated")
        records[path] = (mode, digest)
    return records


def _parse_git_tree(raw: str) -> dict[str, tuple[str, str]]:
    records: dict[str, tuple[str, str]] = {}
    for record in raw.split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, object_type, digest = metadata.split(" ")
        require(object_type == "blob", "Git tree contains unsupported object")
        require(path not in records, "Git tree path is duplicated")
        records[path] = (mode, digest)
    return records


def git_observation() -> dict[str, Any]:
    top = pathlib.Path(exact_git_output(
        ["rev-parse", "--show-toplevel"]).strip())
    git_dir = pathlib.Path(exact_git_output(
        ["rev-parse", "--absolute-git-dir"]).strip())
    require(ROOT.resolve(strict=True) == ROOT and
            top.resolve(strict=True) == ROOT,
            "Git top-level differs from the proof worktree")
    require(git_dir.is_absolute() and git_dir.is_dir() and
            git_dir.resolve(strict=True) == git_dir,
            "Git directory is unavailable or aliased")
    head = exact_git_output(["rev-parse", "HEAD"]).strip()
    status = exact_git_output(
        ["status", "--porcelain=v1", "--untracked-files=all"])
    require(status == "", "derivation Git worktree is not clean")
    flags = exact_git_output(["ls-files", "-v", "-z"]).split("\0")
    require(all(not entry or entry.startswith("H ") for entry in flags),
            "Git index contains assume-unchanged or skip-worktree state")
    index = _parse_git_index(exact_git_output(["ls-files", "-s", "-z"]))
    tree = _parse_git_tree(exact_git_output(
        ["ls-tree", "-r", "-z", "--full-tree", head]))
    require(index == tree, "Git index differs from the exact HEAD tree")
    for relative, (mode, digest) in index.items():
        path = ROOT / relative
        if mode == "120000":
            require(path.is_symlink(), "tracked Git symlink shape drift")
            raw = os.readlink(path).encode("utf-8")
        else:
            require(mode in {"100644", "100755"},
                    "unsupported tracked Git file mode")
            require(path.is_file() and not path.is_symlink(),
                    "tracked Git file is unavailable or aliased")
            raw = path.read_bytes()
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            require(executable == (mode == "100755"),
                    "tracked Git executable mode drift")
        require(_git_blob_sha1(raw) == digest,
                "tracked Git worktree bytes differ from exact HEAD")
    return {"head": head, "worktree_clean": True}


def validate_archive(name: str, path: pathlib.Path) -> dict[str, Any]:
    archive_stat = path.lstat() if path.exists() or path.is_symlink() else None
    require(path.is_absolute() and archive_stat is not None and
            stat.S_ISREG(archive_stat.st_mode) and not path.is_symlink() and
            archive_stat.st_nlink == 1 and path.resolve(strict=True) == path,
            f"{name} archive is unavailable or aliased")
    digest = sha256_file(path)
    require(digest == ARCHIVES[name]["sha256"],
            f"{name} archive digest differs from frozen authority")
    return {**ARCHIVES[name], "byte_length": path.stat().st_size}


def snapshot_archive(name: str, source: pathlib.Path,
                     destination: pathlib.Path) -> dict[str, Any]:
    require(source.is_absolute(), f"{name} archive path is not absolute")
    before = source.lstat() if source.exists() or source.is_symlink() else None
    require(before is not None and stat.S_ISREG(before.st_mode) and
            not source.is_symlink() and before.st_nlink == 1 and
            source.resolve(strict=True) == source,
            f"{name} archive is unavailable or aliased")
    require(not destination.exists() and not destination.is_symlink(),
            f"{name} archive snapshot already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(source, flags)
    digest = hashlib.sha256()
    byte_length = 0
    try:
        opened = os.fstat(descriptor)
        require((opened.st_dev, opened.st_ino, opened.st_size,
                 opened.st_nlink) ==
                (before.st_dev, before.st_ino, before.st_size, 1),
                f"{name} archive changed before snapshot")
        with destination.open("xb") as output:
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                byte_length += len(chunk)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after_path = source.lstat() if source.exists() or source.is_symlink() else None
    require(after_path is not None and
            (after_path.st_dev, after_path.st_ino, after_path.st_size,
             after_path.st_mtime_ns, after_path.st_nlink) ==
            (before.st_dev, before.st_ino, before.st_size,
             before.st_mtime_ns, 1) and
            (after_open.st_dev, after_open.st_ino, after_open.st_size,
             after_open.st_mtime_ns, after_open.st_nlink) ==
            (before.st_dev, before.st_ino, before.st_size,
             before.st_mtime_ns, 1),
            f"{name} archive changed during snapshot")
    require(byte_length == before.st_size,
            f"{name} archive snapshot length drift")
    require(digest.hexdigest() == ARCHIVES[name]["sha256"],
            f"{name} archive snapshot digest differs from frozen authority")
    return validate_archive(name, destination)


def closed_environment() -> dict[str, str]:
    return dict(BUILD_ENVIRONMENT)


def expected_build_contract() -> dict[str, Any]:
    return {
        "canonical_prefix": str(CANONICAL_PREFIX),
        "canonical_build_root": str(CANONICAL_BUILD_ROOT),
        "environment": dict(sorted(BUILD_ENVIRONMENT.items())),
        "gmp_configure_suffix": ["--enable-shared", "--disable-static"],
        "mpfr_configure_suffix": [f"--with-gmp={CANONICAL_PREFIX}",
                                  "--enable-shared", "--disable-static"],
        "make_argv": ["/usr/bin/make", "-j1"],
        "install_argv": ["/usr/bin/make", "install"],
        "independent_build_count": 2,
    }


def validate_prefix_parent() -> None:
    require(CANONICAL_PREFIX.is_absolute(), "canonical prefix is not absolute")
    require(CANONICAL_PREFIX.parent == pathlib.Path("/private/tmp"),
            "canonical prefix parent drift")
    for component in (pathlib.Path("/private"), pathlib.Path("/private/tmp")):
        require(component.is_dir() and not component.is_symlink(),
                "canonical prefix parent is unavailable or aliased")
        require(component.resolve(strict=True) == component,
                "canonical prefix parent is not physically canonical")
    require(CANONICAL_BUILD_ROOT.is_absolute() and
            CANONICAL_BUILD_ROOT.parent == pathlib.Path("/private/tmp"),
            "canonical build root drift")


def require_canonical_directory(path: pathlib.Path, message: str) -> None:
    require(path.is_absolute() and path.is_dir() and not path.is_symlink(),
            message)
    require(path.resolve(strict=True) == path, message)


def _otool_dependencies(text: str, library: pathlib.Path) -> list[str]:
    lines = text.splitlines()
    require(lines and lines[0] == f"{library}:",
            "otool dependency header drift")
    result = []
    for line in lines[1:]:
        stripped = line.strip()
        require(" (" in stripped, "otool dependency record malformed")
        result.append(stripped.split(" (", 1)[0])
    require(result, "otool dependency inventory is empty")
    return result


def audit_installed_library(name: str,
                            expected: dict[str, Any] | None = None
                            ) -> tuple[dict[str, Any], str, str]:
    contract = LIBRARIES[name]
    validate_prefix_parent()
    require_canonical_directory(CANONICAL_PREFIX,
                                f"{name} install prefix is unavailable or aliased")
    library_root = CANONICAL_PREFIX / "lib"
    require_canonical_directory(library_root,
                                f"{name} library root is unavailable or aliased")
    link = library_root / contract["link_name"]
    versioned = library_root / contract["versioned_name"]
    link_stat = link.lstat() if link.exists() or link.is_symlink() else None
    require(link_stat is not None and stat.S_ISLNK(link_stat.st_mode),
            f"{name} unversioned library is not a symlink")
    require(os.readlink(link) == contract["versioned_name"],
            f"{name} unversioned symlink target drift")
    versioned_stat = versioned.lstat() if versioned.exists() else None
    require(versioned_stat is not None and stat.S_ISREG(versioned_stat.st_mode) and
            not versioned.is_symlink(),
            f"{name} versioned library unavailable")
    require(versioned.resolve(strict=True) == versioned,
            f"{name} versioned library path is aliased")
    require(versioned_stat.st_nlink == 1,
            f"{name} versioned library must not be hardlinked")
    mode = f"{stat.S_IMODE(versioned_stat.st_mode):04o}"
    require(mode == "0755", f"{name} versioned library mode drift")
    otool_d = run(["/usr/bin/otool", "-D", str(versioned)],
                  env=AUDIT_ENVIRONMENT, timeout=60).stdout
    otool_l = run(["/usr/bin/otool", "-L", str(versioned)],
                  env=AUDIT_ENVIRONMENT, timeout=60).stdout
    expected_id = str(versioned)
    id_lines = otool_d.splitlines()
    require(id_lines == [f"{versioned}:", expected_id],
            f"{name} LC_ID_DYLIB differs from canonical path")
    dependencies = _otool_dependencies(otool_l, versioned)
    require(dependencies[0] == expected_id,
            f"{name} LC_ID_DYLIB projection drift")
    if name == "mpfr":
        expected_gmp = str(library_root / LIBRARIES["gmp"]["versioned_name"])
        require(expected_gmp in dependencies,
                "MPFR LC_LOAD_DYLIB does not name canonical GMP")
    projection = {
        "canonical_path": str(versioned),
        "link_path": str(link),
        "link_target": os.readlink(link),
        "byte_length": versioned_stat.st_size,
        "mode": mode,
        "sha256": sha256_file(versioned),
        "otool_d_sha256": hashlib.sha256(otool_d.encode()).hexdigest(),
        "otool_l_sha256": hashlib.sha256(otool_l.encode()).hexdigest(),
    }
    if expected is not None:
        require(projection == expected,
                f"{name} installed projection differs from frozen authority")
    return projection, otool_d, otool_l


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
        "canonical_source_root": str(source.resolve()),
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
    versioned = CANONICAL_PREFIX / "lib" / contract["versioned_name"]
    projection, otool_d, otool_l = audit_installed_library(name)
    output.mkdir(parents=True, exist_ok=True)
    copied = output / contract["versioned_name"]
    shutil.copy2(versioned, copied)
    (output / f"{name}.otool-D.txt").write_text(otool_d, encoding="utf-8")
    (output / f"{name}.otool-L.txt").write_text(otool_l, encoding="utf-8")
    return {
        **projection,
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
    require(not CANONICAL_BUILD_ROOT.exists(),
            "canonical build root must be absent before each independent build")
    run_root = output / f"run-{run_id.lower()}"
    require(not run_root.exists(), "independent build output already exists")
    run_root.mkdir(parents=True)
    result: dict[str, Any] = {"run_id": run_id, "builds": {}}
    CANONICAL_BUILD_ROOT.mkdir()
    for name in ("gmp", "mpfr"):
        source = CANONICAL_BUILD_ROOT / f"{name}-source"
        extract_archive(archives[name], source)
        result["builds"][name] = build_dependency(
            name, source, run_root / f"{name}-transcript", output)
    result["libraries"] = {
        name: inspect_library(name, run_root / "libraries", output)
        for name in ("gmp", "mpfr")
    }
    retained_sources = run_root / "source-trees"
    require(not retained_sources.exists(), "retained source tree already exists")
    CANONICAL_BUILD_ROOT.rename(retained_sources)
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
    if require_frozen:
        require(report["git"]["head"] == DERIVATION_START_HEAD,
                "derivation start head drift")
    require(report["platform"] == EXPECTED_PLATFORM, "physical fingerprint drift")
    require(report["compiler"] == {
        "c": str(COMPILER), "cxx": str(COMPILER_CXX),
        "version": COMPILER_VERSION, "sdkroot": str(SDKROOT)},
        "compiler authority drift")
    require(report["archives"] == ARCHIVES, "archive authority drift")
    require(report["build_contract"] == expected_build_contract(),
            "build contract drift")
    require(isinstance(report["runs"], list) and len(report["runs"]) == 2,
            "exactly two independent runs required")
    require([item.get("run_id") for item in report["runs"]] == ["A", "B"],
            "independent build order drift")
    for item in report["runs"]:
        require(set(item) == {"run_id", "builds", "libraries"},
                "run members drift")
        require(set(item["builds"]) == {"gmp", "mpfr"}, "build set drift")
        require(set(item["libraries"]) == {"gmp", "mpfr"}, "library set drift")
        for name in ("gmp", "mpfr"):
            build = item["builds"][name]
            require(set(build) == {
                "canonical_source_root", "configure_argv", "build_argv",
                "install_argv", "environment", "transcripts"},
                f"{name} build record members drift")
            expected_source = str(CANONICAL_BUILD_ROOT / f"{name}-source")
            require(build["canonical_source_root"] == expected_source,
                    f"{name} source root drift")
            configure = build["configure_argv"]
            require(isinstance(configure, list), f"{name} configure argv malformed")
            expected_suffix = [f"--prefix={CANONICAL_PREFIX}"]
            if name == "mpfr":
                expected_suffix.append(f"--with-gmp={CANONICAL_PREFIX}")
            expected_suffix.extend(["--enable-shared", "--disable-static"])
            require(configure == [expected_source + "/configure", *expected_suffix],
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
                        len(descriptor["sha256"]) == 64 and
                        all(ch in "0123456789abcdef"
                            for ch in descriptor["sha256"]),
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


def _canonical_artifact_file(root: pathlib.Path, relative: str
                             ) -> pathlib.Path:
    require(isinstance(relative, str) and relative and
            not relative.startswith("/") and
            all(part not in {"", ".", ".."}
                for part in pathlib.PurePosixPath(relative).parts),
            "proof artifact relative path is noncanonical")
    path = root.joinpath(*pathlib.PurePosixPath(relative).parts)
    parent = root
    for part in pathlib.PurePosixPath(relative).parts[:-1]:
        parent = parent / part
        require_canonical_directory(parent,
                                    "proof artifact directory is aliased")
    file_stat = path.lstat() if path.exists() or path.is_symlink() else None
    require(file_stat is not None and stat.S_ISREG(file_stat.st_mode) and
            not path.is_symlink(), "proof artifact is missing or aliased")
    require(file_stat.st_nlink == 1, "proof artifact must not be hardlinked")
    require(path.resolve(strict=True) == path,
            "proof artifact path is not physically canonical")
    return path


def _require_descriptor_bytes(root: pathlib.Path,
                              descriptor: dict[str, Any]) -> pathlib.Path:
    path = _canonical_artifact_file(root, descriptor["relative_path"])
    require(path.stat().st_size == descriptor["byte_length"],
            "proof artifact byte length drift")
    require(sha256_file(path) == descriptor["sha256"],
            "proof artifact digest drift")
    return path


def validate_retained_artifacts(report: Any,
                                artifact_root: pathlib.Path) -> None:
    validate_report(report, require_frozen=True)
    require_canonical_directory(artifact_root,
                                "proof artifact root is unavailable or aliased")
    seen_paths: set[str] = set()
    seen_files: set[tuple[int, int]] = set()

    def bind(descriptor: dict[str, Any]) -> pathlib.Path:
        relative = descriptor["relative_path"]
        require(relative not in seen_paths,
                "proof artifact descriptor path is duplicated")
        seen_paths.add(relative)
        path = _require_descriptor_bytes(artifact_root, descriptor)
        file_stat = path.stat()
        identity = (file_stat.st_dev, file_stat.st_ino)
        require(identity not in seen_files,
                "proof artifact descriptors alias one physical file")
        seen_files.add(identity)
        return path

    for run_record in report["runs"]:
        for name in ("gmp", "mpfr"):
            build = run_record["builds"][name]
            transcript_paths = {
                key: bind(descriptor)
                for key, descriptor in build["transcripts"].items()
            }
            expected_text = {
                "configure.argv": "".join(
                    value + "\n" for value in build["configure_argv"]),
                "build.argv": "".join(
                    value + "\n" for value in build["build_argv"]),
                "install.argv": "".join(
                    value + "\n" for value in build["install_argv"]),
                "environment": "".join(
                    f"{key}={build['environment'][key]}\n"
                    for key in sorted(build["environment"])),
            }
            for transcript_name, expected in expected_text.items():
                require(transcript_paths[transcript_name].read_text(
                    encoding="utf-8") == expected,
                    f"{name} retained {transcript_name} semantic drift")

            library = run_record["libraries"][name]
            artifacts = {
                key: bind(descriptor)
                for key, descriptor in library["artifacts"].items()
            }
            copied_stat = artifacts["library"].stat()
            require(stat.S_IMODE(copied_stat.st_mode) == 0o755,
                    f"{name} retained library mode drift")
            otool_d = artifacts["otool_d"].read_text(encoding="utf-8")
            otool_l = artifacts["otool_l"].read_text(encoding="utf-8")
            canonical_path = pathlib.Path(library["canonical_path"])
            require(otool_d.splitlines() == [
                f"{canonical_path}:", str(canonical_path)],
                f"{name} retained LC_ID_DYLIB transcript drift")
            dependencies = _otool_dependencies(otool_l, canonical_path)
            require(dependencies[0] == str(canonical_path),
                    f"{name} retained LC_ID_DYLIB projection drift")
            if name == "mpfr":
                expected_gmp = str(CANONICAL_PREFIX / "lib" /
                                   LIBRARIES["gmp"]["versioned_name"])
                require(expected_gmp in dependencies,
                        "retained MPFR LC_LOAD_DYLIB projection drift")
    require(len(seen_paths) == 52,
            "proof artifact inventory does not contain exactly 52 files")


def validate_source_archives(gmp_archive: pathlib.Path,
                             mpfr_archive: pathlib.Path) -> None:
    validate_archive("gmp", gmp_archive)
    validate_archive("mpfr", mpfr_archive)


def freeze_summary(report: Any, report_bytes: bytes,
                   artifact_root: pathlib.Path,
                   gmp_archive: pathlib.Path,
                   mpfr_archive: pathlib.Path) -> dict[str, Any]:
    require(report_bytes == canonical_bytes(report),
            "derivation bundle bytes are not canonical")
    validate_report(report, require_frozen=True)
    validate_retained_artifacts(report, artifact_root)
    validate_source_archives(gmp_archive, mpfr_archive)
    comparable_fields = (
        "canonical_path", "link_path", "link_target", "byte_length", "mode",
        "sha256", "otool_d_sha256", "otool_l_sha256")
    runs = []
    for run in report["runs"]:
        runs.append({
            "run_id": run["run_id"],
            "builds_sha256": hashlib.sha256(
                canonical_bytes(run["builds"])).hexdigest(),
            "run_record_sha256": hashlib.sha256(
                canonical_bytes(run)).hexdigest(),
            "libraries": {
                name: {field: run["libraries"][name][field]
                       for field in comparable_fields}
                for name in ("gmp", "mpfr")
            },
        })
    return {
        "schema": FREEZE_SCHEMA,
        "authority": report["authority"],
        "git": report["git"],
        "platform": report["platform"],
        "compiler": report["compiler"],
        "archives": report["archives"],
        "build_contract": report["build_contract"],
        "derivation_bundle": {
            "byte_length": len(report_bytes),
            "sha256": hashlib.sha256(report_bytes).hexdigest(),
        },
        "runs": runs,
        "derived_libraries": report["derived_libraries"],
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


def validate_freeze_summary(summary: Any) -> None:
    require(isinstance(summary, dict), "freeze summary must be an object")
    required = {
        "schema", "authority", "git", "platform", "compiler", "archives",
        "build_contract", "derivation_bundle", "runs", "derived_libraries",
        "rebuild_match", "candidate_executed", "oracle_executed",
        "numeric_d12_executed", "qualification_decided", "d9a_reopened",
        "b3_unblocked", "far_selected", "production_authorized",
    }
    require(set(summary) == required, "freeze summary members drift")
    require(summary["schema"] == FREEZE_SCHEMA, "freeze summary schema drift")
    require(summary["authority"] == {
        "amendment": "docs/anchored_row_dependency_provenance_amendment.md",
        "plan": "docs/bfr_loop_backend_plan_macos.md",
        "threat_model": "independent_rederivation_not_host_operator_resistance",
    }, "freeze summary authority drift")
    require(summary["platform"] == EXPECTED_PLATFORM,
            "freeze summary platform drift")
    require(summary["compiler"] == {
        "c": str(COMPILER), "cxx": str(COMPILER_CXX),
        "version": COMPILER_VERSION, "sdkroot": str(SDKROOT)},
        "freeze summary compiler drift")
    require(summary["archives"] == ARCHIVES, "freeze summary archives drift")
    require(summary["build_contract"] == expected_build_contract(),
            "freeze summary build contract drift")
    require(summary["derived_libraries"] == FROZEN_PHYSICAL_LIBRARY_SHA256,
            "freeze summary derived digest drift")
    require(isinstance(summary["derivation_bundle"], dict) and
            set(summary["derivation_bundle"]) == {"byte_length", "sha256"} and
            isinstance(summary["derivation_bundle"]["byte_length"], int) and
            summary["derivation_bundle"]["byte_length"] > 0 and
            isinstance(summary["derivation_bundle"]["sha256"], str) and
            len(summary["derivation_bundle"]["sha256"]) == 64,
            "derivation bundle descriptor malformed")
    require(isinstance(summary["runs"], list) and
            [run.get("run_id") for run in summary["runs"]] == ["A", "B"],
            "freeze summary run order drift")
    for run in summary["runs"]:
        require(set(run) == {
            "run_id", "builds_sha256", "run_record_sha256", "libraries"},
            "freeze summary run members drift")
        for digest_field in ("builds_sha256", "run_record_sha256"):
            require(isinstance(run[digest_field], str) and
                    len(run[digest_field]) == 64,
                    "freeze summary run digest malformed")
        require(set(run["libraries"]) == {"gmp", "mpfr"},
                "freeze summary library set drift")
    for name in ("gmp", "mpfr"):
        require(summary["runs"][0]["libraries"][name] ==
                summary["runs"][1]["libraries"][name],
                f"freeze summary {name} rebuild differs")
        require(summary["runs"][0]["libraries"][name]["sha256"] ==
                FROZEN_PHYSICAL_LIBRARY_SHA256[name],
                f"freeze summary {name} digest drift")
    require(summary["rebuild_match"] is True,
            "freeze summary rebuild match drift")
    require(isinstance(summary["git"], dict) and
            summary["git"] == {
                "head": DERIVATION_START_HEAD, "worktree_clean": True},
            "freeze summary clean-head binding drift")
    for field in ("candidate_executed", "oracle_executed",
                  "numeric_d12_executed", "qualification_decided",
                  "d9a_reopened", "b3_unblocked", "far_selected",
                  "production_authorized"):
        require(summary[field] is False, f"freeze summary {field} drift")
    require(hashlib.sha256(canonical_bytes(summary) + b"\n").hexdigest() ==
            EVIDENCE_FILE_SHA256,
            "freeze summary differs from the reviewed evidence authority")


def verify_frozen_bundle(report: Any, report_bytes: bytes,
                         artifact_root: pathlib.Path,
                         gmp_archive: pathlib.Path,
                         mpfr_archive: pathlib.Path) -> dict[str, Any]:
    summary = freeze_summary(report, report_bytes, artifact_root,
                             gmp_archive, mpfr_archive)
    validate_freeze_summary(summary)
    reviewed = strict_json(EVIDENCE, repository_lf=True)
    validate_freeze_summary(reviewed)
    require(summary == reviewed,
            "derivation bundle differs from the reviewed freeze summary")
    return summary


def derive(args: argparse.Namespace) -> dict[str, Any]:
    output = pathlib.Path(args.output_dir).resolve()
    require(str(output).startswith("/private/tmp/"),
            "derivation output must be below /private/tmp")
    require(not output.exists(), "derivation output already exists")
    validate_prefix_parent()
    require(not CANONICAL_PREFIX.exists(), "canonical prefix already exists")
    require(not CANONICAL_BUILD_ROOT.exists(), "canonical build root already exists")
    input_archives = {
        "gmp": pathlib.Path(args.gmp_archive),
        "mpfr": pathlib.Path(args.mpfr_archive),
    }
    platform = platform_fingerprint()
    require(platform == EXPECTED_PLATFORM,
            "derivation host differs from frozen physical fingerprint")
    compiler = compiler_identity()
    git = git_observation()
    require(git["worktree_clean"] is True,
            "derivation requires an empty exact-head worktree")
    output.mkdir(parents=True)
    archive_root = output / "source-archives"
    archives = {
        name: archive_root / f"{ARCHIVES[name]['identity']}.tar.xz"
        for name in ("gmp", "mpfr")
    }
    snapshot_records = {
        name: snapshot_archive(name, input_archives[name], archives[name])
        for name in ("gmp", "mpfr")
    }
    require({name: {key: value for key, value in record.items()
                    if key != "byte_length"}
             for name, record in snapshot_records.items()} == ARCHIVES,
            "source archive snapshot records drift")
    for name in ("gmp", "mpfr"):
        validate_archive(name, archives[name])
    first = build_pair("A", archives, output)
    for name in ("gmp", "mpfr"):
        validate_archive(name, archives[name])
    preserved = output / "run-a" / "installed-tree"
    require(not preserved.exists(), "run A installed tree already exists")
    CANONICAL_PREFIX.rename(preserved)
    second = build_pair("B", archives, output)
    for name in ("gmp", "mpfr"):
        validate_archive(name, archives[name])
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
        "build_contract": expected_build_contract(),
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


def verify_installed(gmp_archive: pathlib.Path,
                     mpfr_archive: pathlib.Path) -> dict[str, str]:
    require(all(value != "PENDING"
                for value in FROZEN_PHYSICAL_LIBRARY_SHA256.values()),
            "frozen physical library digests are pending")
    validate_source_archives(gmp_archive, mpfr_archive)
    summary = strict_json(EVIDENCE, repository_lf=True)
    validate_freeze_summary(summary)
    result = {}
    for name in LIBRARIES:
        expected = summary["runs"][1]["libraries"][name]
        projection, _otool_d, _otool_l = audit_installed_library(
            name, expected)
        require(projection["sha256"] == FROZEN_PHYSICAL_LIBRARY_SHA256[name],
                f"frozen {name} installed library digest drift")
        result[name] = projection["sha256"]
    return result


def self_test() -> dict[str, Any]:
    require(AMENDMENT.is_file() and PLAN.is_file() and EVIDENCE.is_file(),
            "authority document unavailable")
    require(sha256_file(EVIDENCE) == EVIDENCE_FILE_SHA256,
            "frozen evidence-summary file hash drift")
    text = AMENDMENT.read_text(encoding="utf-8")
    for literal in (str(CANONICAL_PREFIX), str(CANONICAL_BUILD_ROOT),
                    ARCHIVES["gmp"]["sha256"],
                    ARCHIVES["mpfr"]["sha256"], COMPILER_VERSION,
                    "independent_rederivation_not_host_operator_resistance"):
        require(literal in text, f"amendment lacks frozen literal {literal}")
    summary = strict_json(EVIDENCE, repository_lf=True)
    validate_freeze_summary(summary)
    return {
        "status": "ok",
        "schema": SCHEMA,
        "canonical_prefix": str(CANONICAL_PREFIX),
        "canonical_build_root": str(CANONICAL_BUILD_ROOT),
        "archives": {name: value["sha256"] for name, value in ARCHIVES.items()},
        "frozen_library_digests": FROZEN_PHYSICAL_LIBRARY_SHA256,
        "derivation_bundle": summary["derivation_bundle"],
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
    modes.add_argument("--freeze-summary")
    modes.add_argument("--verify-installed", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--gmp-archive")
    parser.add_argument("--mpfr-archive")
    parser.add_argument("--output-dir")
    parser.add_argument("--artifact-root")
    args = parser.parse_args()
    try:
        if args.self_test:
            result = self_test()
        elif args.derive:
            require(args.gmp_archive and args.mpfr_archive and args.output_dir,
                    "--derive requires both archives and --output-dir")
            result = derive(args)
        elif args.verify_report:
            require(args.artifact_root and args.gmp_archive and
                    args.mpfr_archive,
                    "--verify-report requires --artifact-root and both archives")
            report_path = pathlib.Path(args.verify_report)
            report_bytes = report_path.read_bytes()
            report = strict_json(report_path)
            verify_frozen_bundle(
                report, report_bytes, pathlib.Path(args.artifact_root),
                pathlib.Path(args.gmp_archive),
                pathlib.Path(args.mpfr_archive))
            result = {"status": "ok", "derived_libraries":
                      report["derived_libraries"]}
        elif args.freeze_summary:
            require(args.artifact_root and args.gmp_archive and
                    args.mpfr_archive,
                    "--freeze-summary requires --artifact-root and both archives")
            report_path = pathlib.Path(args.freeze_summary)
            report_bytes = report_path.read_bytes()
            report = strict_json(report_path)
            result = freeze_summary(
                report, report_bytes, pathlib.Path(args.artifact_root),
                pathlib.Path(args.gmp_archive),
                pathlib.Path(args.mpfr_archive))
            validate_freeze_summary(result)
        else:
            require(args.gmp_archive and args.mpfr_archive,
                    "--verify-installed requires both frozen source archives")
            result = {"status": "ok", "installed_libraries":
                      verify_installed(pathlib.Path(args.gmp_archive),
                                       pathlib.Path(args.mpfr_archive))}
    except (OSError, ValueError, PreflightError, subprocess.TimeoutExpired) as exc:
        print(f"B2 dependency provenance preflight failed: {exc}", file=sys.stderr)
        return 1
    if (args.json or args.derive or args.verify_report or args.freeze_summary or
            args.verify_installed):
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print("B2 GMP/MPFR provenance preflight: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
