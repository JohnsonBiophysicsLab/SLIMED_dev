# B2 Bfr qualification evidence

Status: **provisional exact-worktree Bfr NOT QUALIFIED** — terminal row-invariant
failure; independent review pending

This proof-only B2 packet evaluates Bfr as the qualification target. Far is a
regression comparator only; it cannot be promoted, selected, or used as truth.
This result does not decide D9a or D9b and does not activate a production route.

## Frozen authority

- Exact repaired implementation head: `8282549ac2e0d0819edb095772e4b85aa204209d`.
- B2p merge: `b8ed8bd2dbbf994a4419695cf490b2a3e6f349a6`.
- D10 was explicitly approved on 2026-08-08 before B2 output.
- KB2r merged as `b8cb9470077c1c5e15449318eff7b61e7464cd51`;
  D12 was explicitly approved on 2026-08-10 before B2 output.
- Frozen schema-2 file SHA-256:
  `bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b`.
- Frozen canonical contract SHA-256:
  `30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368`.
- The row-invariant tolerance remained exactly `1.0e-12`.

The proof reads these inputs and does not regenerate them. The exact-positive-one
sample weight is retained solely as a B1 validation sentinel and is not used in
an integrand, quadrature, or integration claim.

## Exact Release result

The local exact-worktree replay completed all 294 numeric cases twice. The
canonical `B2ROWV1` rows matched between process passes for every case. The
three negative fixtures and an independently constructed temporary
pinched-vertex control were rejected before candidate construction or stdout
row emission. The control has valid edge-incidence/global-connectivity shape
but its vertex link is not one connected degree-2 cycle, and it is rejected as
`D2_INVALID_CLOSED_VERTEX_LINK`.

The frozen row-sum criterion failed and is terminal under P9:

- Bfr: 124 failing cases; failures by level 2 through 8 were
  `0, 0, 22, 24, 26, 26, 26`; maximum absolute row-sum error was
  `2.0368522054550406e-11`.
- A representative Bfr failure is `closed_valence3_tetrahedron`, level 4,
  face row 0, local corner 1, `trend-r08-ray01`, `dvv`, with absolute error
  `1.4781509349859334e-12`. Both Bfr cache modes produced the same result.
- Far comparator: 62 failing cases; failures by level 2 through 8 were
  `0, 0, 11, 12, 13, 13, 13`; maximum absolute row-sum error was
  `3.356106503815681e-10`. This finding does not promote Far.

The repair replay's resumable checkpoint is complete with 294 cases and
SHA-256
`894d6c2ae192fe67c48ddab63cbde11b21a0dff4eebdb90a2aed90aca9b8057c`.
It is bound to the two frozen manifest hashes, Git HEAD
`8282549ac2e0d0819edb095772e4b85aa204209d`, candidate binary SHA-256
`d7829797c4fb00fe002f48d1ae79313aedb61653f16ff72a1c16d5ee65d51560`,
and every compressed/decompressed case-artifact hash. It was produced at
`/private/tmp/b2-exact-8282549-checkpoint.json`; the 294 complete gzip
artifacts remain at `/private/tmp/b2-exact-8282549-artifacts`. Both are
local, non-repository artifacts. The earlier sandboxed, AC-observing
platform-guarded local evidence SHA-256 is
`3bab4c45a8a6c52a25b31efa1c2591cd2093abb722814f0c1a5bdaaf718b019d`.
That hash does not identify the later outside-sandbox battery observation.
The dedicated workflow rebuilds the evidence from scratch and uploads the case
JSON, checkpoint, finalized evidence, dependency archives, build transcripts,
compile/link ledgers, and persistent proof binaries/maps/dependency files.

The historical checkpoint also predates the mandatory before/after power and
thermal probes for each of its 588 full case processes. The earlier sandboxed
probe observed `kIOPSACPowerValue` and nominal thermal state, but its
virtualization sysctl query was denied. A later outside-sandbox native probe on
the same exact worktree completed the frozen macOS `26.5.1` build `25F80`,
`arm64`, `Apple M5`, `Mac17,2`, 25,769,803,776-byte, 10/4/6-core fingerprint
and observed nominal thermal state, but it reported
`kIOPSBatteryPowerValue`. The first observation is unqualified because its
fingerprint query was incomplete; the second is unqualified because power was
not AC. Independently, the historical checkpoint has zero of the required
1,176 boundary samples. Neither observation is D12 PASS.

## Criterion disposition

| D9a criterion | Bfr disposition | Notes |
| --- | --- | --- |
| Regular analytic `5.0e-6` rows/integrands | `NOT_RUN_TERMINAL_BFR_FAILURE` | Non-decisive after P9 stop |
| `1.0e-12` row invariants | **FAIL** | 124 Bfr cases failed; tolerance unchanged |
| Original-source reconstruction | PASS | Complete for all executed numeric rows |
| Internal independent-setting convergence | `NOT_RUN_TERMINAL_BFR_FAILURE` | Non-decisive after P9 stop |
| Frozen D10 primary Stam interval oracle | `NOT_RUN_TERMINAL_BFR_FAILURE` | No full oracle-coverage claim |
| D12 preparation cost | `UNQUALIFIED_PLATFORM` | Provenance-bound replay raw maximum median `62,876,125 ns`; raw maximum single `80,888,875 ns` |
| D12 retained payload | `UNQUALIFIED_PLATFORM` | Raw maximum `82,720 bytes/face` |
| D12 peak RSS delta | `UNQUALIFIED_PLATFORM` | Provenance-bound replay raw maximum `13,025,280 bytes` |
| Cache-disabled concurrency | `NOT_RUN_TERMINAL_BFR_FAILURE` | Full frozen matrix not run |
| Fully instrumented threaded-cache TSan | `NOT_RUN_TERMINAL_BFR_FAILURE` | Full frozen matrix not run |

The frozen D12 budgets were `1,000,000,000 ns` median,
`10,000,000,000 ns` single, `131,072 bytes/face`, and `67,108,864 bytes` RSS.
The raw observations are within those limits, but on an unqualified platform
the budgets neither pass nor fail. These observations do not override the
scientific row-invariant failure.

The execution status is `COMPLETE_TERMINAL_BFR_FAILURE` and the scientific
`bfr_verdict` is `FAIL`. Scientific failure exits zero so CI can preserve and
publish the evidence; malformed inputs, incomplete execution, dependency
failures, and other infrastructure failures exit nonzero. No unexecuted
criterion is represented as PASS, and no oracle-uncovered row is counted.

A D12 PASS artifact can be produced only by a fresh exact-reviewed-head replay
on the frozen physical fingerprint with all 1,176 outside-timing IOPS and
NSProcessInfo boundary samples qualified. The GitHub-hosted `macos-26` job is
deliberately a correctness, dependency, independence, and reproduction
artifact. Even if its raw resource observations fit the budgets, it emits
`UNQUALIFIED_PLATFORM` and cannot overwrite or masquerade as the separately
reviewed physical-host artifact.

Technical, scientific, verification, and gatekeeper reviews remain PENDING.
Accordingly the result is provisional evidence, not a D9a decision. The lane
is blocked pending independent review and the user's architectural decision.

## Proof programs and limits

`scripts/run_bfr_qualification.py --self-test --json` validates the frozen
manifest, canonical digest, 17-row source matrix, aliases, the 14-content
threading expansion (588 tuples), radii/rays, row order, approval anchors,
source separation, and validation-only sentinel policy. It uses only the
standard library and is tested under Python 3.9.6 and 3.14.6.

`--require-proof-dependencies` accepts explicit `MPFR_ROOT`,
GMP/MPFR build roots and source archives, separate OpenSubdiv Release/TSan
build and install roots, `OPENSUBDIV_SOURCE`, the OpenSubdiv source archive,
and a persistent proof-artifact directory. It never
downloads dependencies or searches ambient prefixes. It fails closed on a
version/root/commit/member-order/dependency/symbol mismatch. For both
OpenSubdiv profiles it audits the exact environment and configure/build/install
argv, CMake cache, configure/build/install logs, all 47 ordered translation
units and compile commands, link command, raw archive members, installed
archive, and hashes. GMP/MPFR archive, configure/build/install, library, and
header provenance are also retained. Candidate/oracle commands, binaries,
dependency files, linker maps, `nm -u`, and `otool -L` identities remain in the
published workflow artifact.

## Neutral near-vertex inter-method observation

The mandatory observation pairs Bfr level 8 (`approxLevelSharp=6`,
cache-disabled) with uncached Far isolation level 8. These are each method's
highest frozen setting; the integers are explicitly noncommensurable. Rows are
aligned by content, face, local corner, trend sample, derivative order, and
original coarse source. The all-valence-6 control contributes artifact
bindings but correctly has no near-vertex trend rows.

Across 73,440 aligned rows (12,240 per derivative order), the maximum
coefficient L1 / normalized-geometry L-infinity spreads were: position
`0.0017544988475447618 / 0.0011570703213699958`; `du`
`0.4888219681803726 / 0.29026062322985213`; `dv`
`0.4888220764477891 / 0.2843687302618921`; `duu`
`346.02613495569506 / 122.12768950539758`; `duv`
`283.91666714085886 / 184.87842875319146`; and `dvv`
`346.0261349557122 / 128.9784922529451`. The evidence also records medians,
radii 1--8 trends, maximum observations, and 28 artifact bindings. This is an
observed spread only: it is not an accuracy ranking, floor, or bound.

The fresh full dependency-audit JSON SHA-256 is
`ee66b8ec4004f44a91a03e8e9ecfb82551943890cdeded83fbf5f7880307c462`.
The provenance-bound, sorted and round-trip-validated terminal evidence JSON
SHA-256 is
`9175920dd7eedc2a44962c76959079d94793671be7e726e8e18e47783201df40`.

The candidate's `--platform-probe` uses the frozen native protocols directly:
sysctl/uname for the complete physical fingerprint,
`IOPSCopyPowerSourcesInfo` plus `IOPSGetProvidingPowerSourceType` for AC power,
and `NSProcessInfo.thermalState` for nominal thermal state. The runner samples
it immediately before and after both full processes for every numeric case,
outside the candidate preparation timings. A query failure, fingerprint or
compiler mismatch, non-AC/non-nominal observation, virtualization evidence, or
GitHub-hosted runner yields `UNQUALIFIED_PLATFORM`; resource criteria then
receive no PASS or FAIL verdict.

The separate numeric program exercises 544-bit two-endpoint MPFR arithmetic
with directed primitive rounding and fail-closed flag handling. Its primitive
self-test is not a full Stam eigencertification or oracle-coverage result. P9
stopped the full Stam oracle, analytic, convergence, cache-concurrency, and
TSan science because they could not change the terminal Bfr verdict.

## Reproduction commands

```text
/usr/bin/python3 scripts/run_bfr_qualification.py --self-test --json
/opt/homebrew/bin/python3 scripts/run_bfr_qualification.py --self-test --json
/usr/bin/python3 -m unittest tests.test_bfr_qualification
/opt/homebrew/bin/python3 -m unittest tests.test_bfr_qualification
```

Finalize and validate an already-complete Release checkpoint:

```text
python3 scripts/run_bfr_qualification.py \
  --finalize-release-checkpoint \
  --release-checkpoint /path/to/bfr-release-checkpoint.json \
  --candidate-binary /path/to/bfr-candidate \
  --artifact-dir /path/to/bfr-case-json \
  --output /path/to/bfr-qualification-evidence.json
```

Run the dependency audit and full resumable Release matrix:

```text
python3 scripts/run_bfr_qualification.py --run-release-matrix \
  --mpfr-root "$MPFR_ROOT" \
  --gmp-build-root "$GMP_BUILD_ROOT" \
  --mpfr-build-root "$MPFR_BUILD_ROOT" \
  --opensubdiv-root "$OPENSUBDIV_ROOT" \
  --opensubdiv-tsan-root "$OPENSUBDIV_TSAN_ROOT" \
  --opensubdiv-source "$OPENSUBDIV_SOURCE" \
  --opensubdiv-release-build-root "$OPENSUBDIV_RELEASE_BUILD_ROOT" \
  --opensubdiv-tsan-build-root "$OPENSUBDIV_TSAN_BUILD_ROOT" \
  --gmp-archive /path/to/gmp-6.3.0.tar.xz \
  --mpfr-archive /path/to/mpfr-4.2.2.tar.xz \
  --opensubdiv-archive /path/to/opensubdiv-v3_7_0.tar.gz \
  --proof-artifact-dir /path/to/bfr-proof-artifacts \
  --release-checkpoint /path/to/bfr-release-checkpoint.json \
  --artifact-dir /path/to/bfr-case-json \
  --output /path/to/bfr-qualification-evidence.json
```

No near-vertex accuracy ranking is made. Inter-method spread is not an accuracy
floor because the methods may have correlated approximation errors. Bfr and
Far approximation-level integers are not commensurable. No Phase-1 remeshing
saving is claimed, and no Phase-2 locality projection is part of this terminal
failure packet.
