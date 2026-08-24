# B2b GMP/MPFR source-to-library provenance amendment

Status: **proof-only proposal authorized for implementation and exact-SHA
review on 2026-08-24; not yet merged or approved as a frozen B2b input**

This document is an additive amendment to
[`anchored_row_qualification_preflight.md`](anchored_row_qualification_preflight.md)
and
[`anchored_row_qualification_result_ledger_amendment.md`](anchored_row_qualification_result_ledger_amendment.md).
It closes one dependency-provenance gap found during exact-SHA review of the
Package 2 implementation. It changes no candidate, fixture, sample, row,
tolerance, D10 target, B2b component target, oracle rule, D12 budget, decision,
route, or production state.

The failed development commits `98c4f4c`, `953b0f9`, and `3c83ba3` added
different caller-supplied copies and digests of the same GMP/MPFR library
bytes. Coordinated replacement of every copy and its co-produced digest still
passed. Those observations are development evidence only and establish the
need for a different trust root; they are not candidate results.

## Authority and threat model

The authority is the reviewed dependency identity and source archive SHA-256,
not any caller-supplied installed file or digest:

| role | identity | upstream archive | SHA-256 |
|---|---|---|---|
| GMP | `gmp-6.3.0` | `https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz` | `a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898` |
| MPFR | `mpfr-4.2.2` | `https://ftp.gnu.org/gnu/mpfr/mpfr-4.2.2.tar.xz` | `b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01` |

The literal threat-model identifier is
`independent_rederivation_not_host_operator_resistance`. The proof detects
archive, build-environment, installed-byte, packet, transcript, and ordinary
operator drift and lets an independent reviewer rederive the bytes from the
reviewed source authority. It does not claim resistance to an operator who can
simultaneously replace the physical host, the reviewed repository, the
reviewed archive constants, and the review result. Exact-SHA review and the
later explicit approval bind this document and its constants; another
caller-supplied digest is not an authority.

## Canonical physical-host prefix

Mach-O `LC_ID_DYLIB` and `LC_LOAD_DYLIB` commands embed the install prefix, and
the resulting ad-hoc code signature is content-derived. Cross-prefix byte
comparison is therefore not the proof. The one physical D12 host uses exactly:

```text
/private/tmp/slimed-b2-d12-dependencies-v1
```

The path is absolute, lexically and physically canonical, has no symlinked
component, and is absent before each independent build. The first installed
tree is moved intact into the proof output before the second build; it is not
deleted or reused. The second verified tree remains at the canonical prefix
for the later separately authorized numeric run. The exact versioned library
paths are:

```text
/private/tmp/slimed-b2-d12-dependencies-v1/lib/libgmp.10.dylib
/private/tmp/slimed-b2-d12-dependencies-v1/lib/libmpfr.6.dylib
```

`libgmp.dylib` and `libmpfr.dylib` must be symlinks to those exact basenames.
GMP's `LC_ID_DYLIB` must be the first versioned path; MPFR's `LC_ID_DYLIB` must
be the second and its GMP `LC_LOAD_DYLIB` must name the first. A normalized
Mach-O comparison, ignored load command, stripped signature, install-name
rewrite, alternate prefix, alias, hardlink authority, or package-manager
library is forbidden.

MPFR retains its compile/object paths in the Mach-O symbol string table. The
source/build root is therefore also pinned exactly:

```text
/private/tmp/slimed-b2-d12-dependency-build-v1
```

Runs `A` and `B` are sequential. Before each run, this build root and the
canonical install prefix are both absent; each archive is freshly extracted
again into `gmp-source` or `mpfr-source` below the build root. After a run, the
complete source/build tree is moved intact into that run's proof-artifact
directory. The next run reuses only the literal path, never the first run's
files. An alternate build path, path normalization, debug/symbol-table rewrite,
or stripped binary is forbidden.

Before either extraction, each absolute non-aliased input archive is copied
through one no-follow file descriptor into the retained `source-archives`
directory while SHA-256 is computed. File identity, length, modification time,
and frozen digest must agree before and after the copy. Both runs extract only
these sealed copies, and each sealed archive is rehashed immediately before and
after each run. Reopening the original caller path after its initial check, or
letting runs `A` and `B` observe different archive bytes, is forbidden.

## Exact derivation environment

Derivation is permitted only on D12's already frozen physical fingerprint:

```text
macOS 26.5.1 build 25F80
arm64, hw.model Mac17,2, Apple M5
hw.memsize 25769803776
hw.ncpu/hw.physicalcpu/hw.logicalcpu 10/10/10
hw.perflevel0 physical/logical 4/4
hw.perflevel1 physical/logical 6/6
kern.hv_vmm_present 0
```

The C and C++ compiler paths are
`/Library/Developer/CommandLineTools/usr/bin/clang` and
`/Library/Developer/CommandLineTools/usr/bin/clang++`; the first C++ version
line is exactly
`Apple clang version 21.0.0 (clang-2100.1.1.101)`. The SDK is exactly
`/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk`.

Every configure, build, and install subprocess receives an empty inherited
environment followed by exactly this closed map:

```text
AR=/usr/bin/ar
CC=/Library/Developer/CommandLineTools/usr/bin/clang
CXX=/Library/Developer/CommandLineTools/usr/bin/clang++
LANG=C
LC_ALL=C
NM=/usr/bin/nm
PATH=/usr/bin:/bin:/usr/sbin:/sbin
RANLIB=/usr/bin/ranlib
SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk
SOURCE_DATE_EPOCH=0
STRIP=/usr/bin/strip
TZ=UTC
ZERO_AR_DATE=1
```

For each of independent runs `A` and `B`, the two archives are freshly
extracted into the now-empty canonical build root. Commands are exact arrays,
not shell strings:

```text
GMP:  /private/tmp/slimed-b2-d12-dependency-build-v1/gmp-source/configure
      --prefix=/private/tmp/slimed-b2-d12-dependencies-v1
      --enable-shared --disable-static
MPFR: /private/tmp/slimed-b2-d12-dependency-build-v1/mpfr-source/configure
      --prefix=/private/tmp/slimed-b2-d12-dependencies-v1
      --with-gmp=/private/tmp/slimed-b2-d12-dependencies-v1
      --enable-shared --disable-static
build:   /usr/bin/make -j1
install: /usr/bin/make install
```

The proof retains each configure/build/install array, closed environment,
logs, `config.status`, `config.log`, and top-level `Makefile`. Both runs must
produce identical byte length, mode, SHA-256, `otool -D` digest, and `otool -L`
digest for each versioned library. Any disagreement leaves the amendment
unfrozen and Package 2 blocked.

## Derived physical-host authority

The following values are filled only after both clean builds agree. They are
then immutable B2b inputs and must appear byte-for-byte in the proof script,
the canonical evidence record, and the later Package 2 validator:

```text
gmp_libgmp_10_dylib_sha256=f872fbd53e7a265961e6c79ae846741637f59a28c04a839db55724bd12bbfb32
mpfr_libmpfr_6_dylib_sha256=2b51afa01ece4b200eacf92a318c38097595ab8cd656e0602cb0e55f9cce247e
```

These values were derived on 2026-08-24 by both ordered clean builds from exact
start head `53c7cab5186347af618896962f1f082ce9111cbf`. GMP was 481,392
bytes and MPFR was 580,208 bytes in each run. Derivation alone does not approve
the values; they remain proposed until this amendment's exact-SHA gates, merge,
and explicit user approval complete.

Routine physical qualification does not rebuild dependencies. It cheaply
requires the exact canonical paths, symlinks, load commands, and frozen
versioned-library SHA-256 values before snapshotting or launching any oracle or
candidate process. The routine audit walks the physical prefix and `lib`
directory without resolving away an alias, rejects symlinked directory
components and hardlinked versioned leaves, requires mode `0755`, exact byte
length, exact unversioned-link target, exact `LC_ID_DYLIB`, MPFR's exact GMP
`LC_LOAD_DYLIB`, and the frozen `otool -D`/`otool -L` transcript digests. The
same invocation must receive both frozen source archive paths and compare their
bytes directly to the archive SHA-256 constants above; hashing a co-produced
envelope is insufficient.

The GitHub-hosted `macos-26` workflow continues to download and verify the same
literal archives and rebuild them from source on every clean runner. Hosted
CPU configuration may differ from the physical Mac17,2 derivation, so hosted
libraries are not compared to the physical-host digests and cannot satisfy
numeric D12. Hosted success proves exact-head correctness, dependency
provisioning, and independence audit only.

## Canonical evidence

[`run_gmp_mpfr_provenance_preflight.py`](../scripts/run_gmp_mpfr_provenance_preflight.py)
emits a complete canonical derivation bundle with kind
`b2-gmp-mpfr-provenance-preflight-v1`. It binds:

- this amendment and the macOS Bfr plan;
- exact Git head and an empty worktree at derivation start;
- the complete physical fingerprint and compiler/SDK identity;
- both archive identities, URLs, and SHA-256 values;
- the canonical install and build roots, exact closed environment, and exact
  command arrays;
- ordered independent runs `A` and `B`, transcript hashes, canonical library
  paths/symlinks/modes/lengths/hashes, and `otool` transcript hashes;
- the equal derived GMP and MPFR digests; and
- false values for candidate/oracle execution, numeric D12 execution,
  qualification, D9a reopening, B3 unblocking, Far selection, and production.

The complete bundle and retained trees remain external proof artifacts. Its
canonical byte length and SHA-256, both per-run build-record digests, exact
library projections, authority, environment, and no-activation fields are
committed in the smaller
`b2-gmp-mpfr-provenance-freeze-v1` summary at
`docs/anchored_row_dependency_provenance_evidence.json`. Its bytes are the
canonical object followed by exactly one repository LF. The embedded start
head is the clean contract/tool commit immediately preceding the evidence
freeze commit. Reviewers compare the summary to the complete bundle, rerun the
derivation from the archived inputs, or validate the frozen installed tree
independently. Neither file is a qualification report.

Complete-bundle validation is impossible without the retained artifact root
and both source archives. The validator resolves every one of the exact 52
declared transcript/library/`otool` records beneath one physically canonical
root, rejects missing files, symlink or hardlink aliases, then compares exact
byte length and SHA-256. It additionally parses the retained command and closed
environment transcripts and the Mach-O install/load projections; descriptor
shape alone is never evidence. The regenerated freeze summary must equal the
reviewed checked-in summary byte-for-byte and must retain its reviewed file
SHA-256. A report copied without its sidecars, or coordinated edits to a
sidecar and its report descriptor, therefore fail.

The exact review commands are:

```text
python3 scripts/run_gmp_mpfr_provenance_preflight.py --verify-report REPORT \
  --artifact-root ARTIFACT_ROOT --gmp-archive GMP_ARCHIVE \
  --mpfr-archive MPFR_ARCHIVE
python3 scripts/run_gmp_mpfr_provenance_preflight.py --verify-installed \
  --gmp-archive GMP_ARCHIVE --mpfr-archive MPFR_ARCHIVE
```

Derivation Git identity is observed with absolute `/usr/bin/git` under a closed
environment containing no inherited `GIT_*` values. The audit requires the
canonical executing worktree, canonical Git directory, empty status including
untracked files, no skip-worktree or assume-unchanged index flags, index equality
with the exact HEAD tree, and byte/mode equality for every tracked blob. An
alternate clean repository selected through ambient Git variables is forbidden.

```text
complete_derivation_bundle_bytes=16153
complete_derivation_bundle_sha256=9a2e1a7b2f64ee0092c3550771ea60baaec9a50b63597450f7d9bd5e0eb1b09a
checked_in_freeze_summary_sha256=59f0da12d1e65e19423cf18e5607c384a3048d71dfc3cc1ef4f5e1dbd8a1d51e
```

## Required attacks

Tests and exact-SHA review must reject at least:

- either wrong archive byte or digest, version, URL, or archive-role swap;
- archive aliasing, replacement during snapshot, or different sealed archive
  bytes observed by the two independent runs;
- noncanonical, relative, aliased, hardlinked, or different install prefixes;
- an existing/reused canonical install or build root before either build;
- inherited or missing environment entries and changed compiler/SDK/tool path;
- missing, extra, reordered, or changed configure/build/install arguments;
- one-run evidence, run reorder, transcript omission, or duplicate JSON keys;
- a report without its exact 52 retained files, a descriptor/sidecar coordinated
  mutation, semantic command/environment drift, traversal, symlink, or hardlink;
- ambient `GIT_DIR`, `GIT_WORK_TREE`, or `PATH` redirection, hidden index flags,
  index/tree drift, tracked byte drift, or executable-mode drift;
- versioned-library name, unversioned symlink, mode, length, digest, install ID,
  load dependency, or `otool` transcript drift;
- coordinated packet/snapshot/installed-library substitution that differs from
  the frozen source-derived digest;
- a source archive accepted only because a co-produced report repeats its
  digest; and
- any candidate/oracle execution, numeric D12 result, qualification, D9a, B3,
  Far, or production implication.

## Governance and stop conditions

This amendment is a T2 B2b input change because it strengthens what counts as
valid GMP/MPFR D12 provenance. Its allowed scope is this amendment, the macOS
Bfr plan, the standalone proof script, its focused test, the canonical derived
evidence JSON, and the two invocation lines in the existing dedicated Bfr
workflow. It may not modify `src/**`, `include/**`, `experiments/**`, fixtures,
candidate/oracle executables, scientific targets, D12 budgets, decisions, B3,
Far routing, or production.

Gate: exact-SHA verification, technical, scientific, and gatekeeper PASS,
followed by merge and explicit user approval as a frozen B2b input. Only then
may Package 2 rebase the approved authority and implement its cheap runtime
enforcement. The Package 2 code-bearing head requires another four exact-SHA
reviews before hosted execution; the hosted gate must pass before any physical
numeric D12 run.

Stop immediately if either independent build differs; the canonical prefix or
physical fingerprint cannot be used; an archive is unavailable or mismatched;
the proposal requires normalized Mach-O bytes; a derived digest is selected
from candidate output; or any step implies qualification, D9a reopening, B3,
Far selection, or production authorization.
