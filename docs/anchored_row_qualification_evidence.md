# B2c anchored-row qualification evidence

Status: **exact-SHA review of the strict duplicate-key repair exposed a lossy
floating-number JSON boundary; an exact-number remediation is in progress,
qualification remains `INCOMPLETE`, and numeric D12 must be rerun only after a
new exact-SHA gate**

Candidate: `anchored_difference_rows_v1`

Approved B2b oracle-uncovered contract merge:
`022df7a8e11bcc4aee4df2254cc994cf4efdeb4f`

Approved B2b GMP/MPFR dependency-provenance amendment: exact reviewed head
`29cd8992eb6862cdc55b66245ea6f4a525a48a74`, PR 209 merge
`6a5531415b7b280c1a8c34be22f6c58e2b6d521c`.

## Scope and frozen authority

B2c remains isolated to the proof lane. It does not alter provider rows,
fixtures, the six-row contract, the invariant tolerance, production sources,
the B3 gate, D9a, or the Far disposition. It does not qualify the candidate or
authorize production.

The authority consumed by this package remains:

- row order: `position`, `du`, `dv`, `duu`, `duv`, `dvv`;
- invariant tolerance: `1.0e-12`;
- D10 row targets: `5.0e-6`, `2.5e-5`, and `1.25e-4` for position,
  first derivatives, and second derivatives respectively;
- component targets: `5.0e-7`, `2.5e-6`, and `1.25e-5`;
- primary oracle: independently certified Stam evaluation plus independent
  uniform-subdivision coverage; and
- GMP 6.3.0 and MPFR 4.2.2 physical libraries: the source-derived hashes and
  canonical `/private/tmp/slimed-b2-d12-dependencies-v1` install tree frozen by
  the approved PR 209 provenance amendment; and
- no post-hoc normalization, Far fallback, D9a reopening, B3 work, or
  production activation.

## Implemented proof components

### Representation and exact boundary

The representation candidate is an executable binary64 implementation with
the frozen source order and observable subtraction, multiplication,
accumulation, and final-position round points. The exact-dyadic boundary
decodes every finite coefficient over the common `2^1074` denominator and
certifies 544-bit MPFR imports with directed `MPFR_RNDD` and `MPFR_RNDU`
endpoints.

The candidate exposes exhaustive streams for the three oriented-corner
anchors, identity/reverse/rotate relabelings, and the five frozen constant
fields. Exact structural and geometry checks use bounded proof-only integers;
the emitted evaluator itself remains the frozen binary64 computation.

### Stam primary oracle and uniform cross-check

Package 2 now contains a real MPFR oracle implementation rather than the old
primitive-only placeholder. The implementation constructs stock Loop local
subdivision matrices, builds analytic eigenvalue/eigenvector seeds, performs
interval residual, separation, inverse, Krawczyk, repeated-block, and spectral
projector checks, evaluates the quartic box-spline basis, follows a selected
subdivision path, and emits all six interval rows. It also computes
extraordinary vertex-limit, dyadic-interior, and tangent-projector checks.

A separately coded uniform route reconstructs the complete coarse topology
directly from the frozen faces, starts from complete-mesh original-source basis
columns, and derives the oriented patch without calling the primary fixture's
support, neighbor-cycle, or edge-opposite implementation. At every selected
child it memoizes only the requested controls and expands their exact stock
mask dependencies back into those complete-mesh basis columns. The executable
self-test compares that sparse backward closure against the complete one-step
stock operator for every valence 3 through 9 and every child branch. No
`4^depth` face set is materialized. The route then intersects five consecutive
depths with the primary intervals. A request whose selected path cannot satisfy
the frozen isolation contract is emitted as a per-cell `UNCOVERED`; it is not
evaluated through primary-owned stencils. Oracle cells are emitted
as either `COVERED` with the closed certified observation or `UNCOVERED` with a
frozen per-cell reason. The runner propagates actual criterion-10 uncovered
outcomes into criteria 11--13 and binds the result partitions to the matrix
ledgers.

The executable independence audit checks the reviewed source allowlist,
compiler dependency closure, linked libraries and hashes, undefined symbols,
link-map ownership, MPFR/GMP calls, and forbidden OpenSubdiv/Far/Bfr symbols.
The remediation snapshots the compiler depfile and both audited MPFR/GMP
dylibs before execution, launches self-test, capability, and all scientific
requests with `DYLD_LIBRARY_PATH` fixed to those immutable copies, and rechecks
the copies after execution. The final version-2 runtime packet retains the
audited original paths but binds the relative paths and hashes of the copies
that were actually selected for execution. Process-tree timers begin before
blocking pipe reads.

These are implemented mechanisms, not accepted scientific evidence. The exact
SHA review below describes the prior failure. This remediation revision must
receive four new exact-SHA PASS verdicts before it becomes admissible evidence.

### D12 provider and representation execution

D12 now builds, audits, and executes separate TSan provider and representation
binaries. For every frozen threading tuple, the provider process writes the
complete provider stream and the representation process consumes the exact
serial request stream and writes all eight frozen representation inputs. Both
streams are compared with their independently generated serial references.

The persistent process-observation artifact contains exactly two TSan summary
records per tuple. Those records must bind different PIDs and the exact
authenticated provider/representation executable SHA-256 set. A successful
tuple cannot discard either process; a sanitizer abort retains the exact
process and report ownership. Process-group timeout cleanup treats all
`OSError` results from `killpg` as an already-unavailable cleanup target.

The dual-process contract follow-up is isolated in commit
`8c4b43a` (`Close D12 dual-process TSan contract`). It updates the stale
one-process test, adds the same-PID rejection, uses the production expected
executable set in successful and race tests, and widens the remaining cleanup
handlers. It has not yet received a new four-review exact-SHA verdict.

## Report and failure semantics

The report schema is `anchored-row-qualification-report-v1`. The generated
JSON Schema and the executable validator close every object, freeze all 32
criterion IDs and 34 ordered ledger partitions, enforce RFC 8785 bytes and the
zeroed-field report hash, and reject missing, extra, duplicate, reordered,
nonfinite, or negative-zero evidence.

Every executed or uncovered criterion owns a cryptographic result commitment
in addition to its pre-result key ledger. Oracle `UNCOVERED` cells retain null
candidate values, unchanged D10 targets, and exact frozen reasons. Candidate
`FAIL` has precedence over propagated `UNCOVERED`; otherwise uncovered oracle
coverage leaves the verdict `INCOMPLETE`. All decision and activation fields
remain false.

No unavailable executable, dependency, sidecar, or partition receives an
invented zero hash. Availability state and reason remain explicit.

Covered oracle sidecars are no longer self-authorizing. Generic canonical
ledger construction cannot mint covered-oracle authority. Standalone bundle
validation reruns the exact authenticated oracle over the frozen request
corpus, derives the complete criterion-10 record stream, and requires every
persisted record to equal that executable replay before accepting its
certification fields. A coordinated sidecar containing only literal
`CERTIFIED` strings is rejected.

The unique oracle request inventory is exactly 16,500 entries. The writer
asserts that cardinality before launching the oracle and persists a canonical
execution-audit sidecar containing, in exact request order, the request ID,
request-line hash, covered/uncovered state, exact uncovered reason, and
canonical observation hash. Its count, byte length, and SHA-256 are owned by
the version-2 runtime packet. Standalone validation re-executes all requests
against fresh copies of the bound runtime dylibs and requires the regenerated
execution-audit descriptor to equal the persisted descriptor before granting
covered-record authority.

## Existing candidate-only development evidence

The following bounded streaming ledgers were reproduced from the prior fully
validated 294-artifact corpus. They are candidate applicability evidence, not
oracle coverage, D12 qualification, or exact-head Package 2 qualification.

| Criterion | Cells | Failures | Canonical ledger SHA-256 |
| --- | ---: | ---: | --- |
| `representation_structure` | 4,158,000 | 0 | `3132ed72dfd9e1818fe494e360f02f498d89b18c1ff75945d03922e133e9f494` |
| `constant_field_bits` | 62,370,000 | 0 | `dec2bf982174967694ef52def124ffdc82d3b52952a314b4e9c6fec6d7fcde4d` |
| `relabel_exact_effective_coefficients` | 8,316,000 | 0 | `575e2227bf3d5ac5d4ee62fb0221bbbc82150632419cb3d8c79a30410156c138` |
| `cache_mode_bit_identity` | 2,079,000 | 0 | `a8c2c2bad40d685a8f0804791a1a49bd719aebba119f90e214b06cb360597411` |

The regular analytic development replay also produced:

| Criterion | Cells | Failures | Maximum absolute error | Canonical ledger SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `regular_analytic_exact_rows` | 152,640 | 0 | `4.0438331695548237e-16` | `fb3aa638476c8fb51b6420b74332b8f47ce17b8041251fdf7c9ce350fb4777e2` |
| `regular_analytic_emitted_geometry` | 457,920 | 0 | `1.1932044959398847e-15` | `7ad97040ed0a6bf8b44c04eec43690a5fd7bc086f51592cfef5f18c4f5427ef3` |
| `regular_analytic_area_integrand` | 50,880 | 0 | `1.164920199724114e-15` | `19752de9524c3dda9b07671bfb7c504896e2ab6d748fb624dddf1ebb9b7d0fbc` |
| `regular_analytic_legacy_volume_integrand` | 50,880 | 0 | `3.277470150033568e-15` | `ccb982f45e38cc44f38949c4de391646979d311348fe6fb1580d7e7e3c9a5a81` |

These values must be regenerated and rebound at the eventual reviewed
execution SHA. A checked-in digest is never accepted as a substitute for the
persisted sidecar bytes.

## Exact-SHA review at `b10797362d7fba06f548bef98855c7e8c51a8bcd`

The four-review set did **not** admit this implementation. Verification found
the bounded mechanisms and test gates green, but technical, scientific, and
gatekeeper review identified five remaining authority defects:

1. the main scientific call omitted the immutable runtime-library root even
   though replay probes could use it, so the production run could still load
   the audited live MPFR/GMP paths;
2. the directed-rounding test performed a parallel raw-MPFR demonstration
   rather than mutating the endpoint choices used by the production interval
   primitives;
3. the independent uniform route still seeded a local `N+6` forward operator
   rather than owning the complete-topology, sparse backward dependency route
   frozen by section 3.2;
4. eigenbasis and tangent catch boundaries collapsed exact directed-interval
   and branch-ordering failures into broader reasons; and
5. the asserted 16,500-request development replay had neither an executable
   exact-cardinality assertion nor a persisted audit artifact/digest bound to
   standalone replay.

No hosted or physical numeric run was started at that failed SHA.

## Remediation after the `b107973` review

This remediation revision makes the following fail-closed changes and remains
subject to exact-SHA review:

1. every oracle execution path, including self-test and capability probes,
   receives the persistent audited MPFR/GMP snapshot root; the final runtime
   packet binds those loaded files rather than mutable originals;
2. the uniform route reconstructs complete coarse topology independently and
   recursively computes only demanded stock-mask controls as a memoized
   backward source-basis closure;
3. the directed-rounding mutation self-test now changes the endpoint selector
   inside each production primitive. It replaces each lower and upper
   endpoint mode separately for add, subtract, multiply, divide, square root,
   cosine, and the matrix accumulator, and requires the mutated interval to
   exclude a higher-precision reference;
4. MPFR flag/domain failures and uncertain child/cosine branches retain the
   frozen `DIRECTED_INTERVAL_PRIMITIVE_FAILED` and
   `INTERVAL_BRANCH_ORDERING_UNCERTIFIED` reasons across eigenbasis,
   projector, and parametric-map catch boundaries; and
5. the exact 16,500-request assertion and canonical execution sidecar are
   generated by the production writer and independently regenerated by the
   standalone executable replay.

The earlier unbound development replay counts are not qualification evidence
and are no longer presented as a substitute for this persisted audit. The new
sidecar will be created only by an authorized exact-head qualification
execution after the remediation itself passes review.

The conservative refined-isolation disposition can reduce coverage and leave
the eventual verdict `INCOMPLETE`. That is an allowed scientific result, not a
qualification shortcut. No tolerance, fixture, sample, or acceptance target
has been changed in response.

## Exact-SHA review at `98c4f4c1491eaf16b44b57c3469e29ce84369316`

All four exact-SHA reviewers rejected this revision for one shared executable
integration defect. The production writer published the version-2 runtime
execution packet as the independent oracle's dynamic-dependency evidence, but
standalone independence validation compared every supplied packet directly to
the older version-1 dependency-only object. A genuine version-2 report
therefore failed with `oracle dynamic-dependency audit packet drift` before
the immutable runtime libraries or 16,500-request sidecar could be admitted.

The follow-up validator accepts a version-2 packet only after binding its
canonical loaded-library files and execution sidecar, matching its exact
`otool -L` transcript and digest to the authenticated oracle binary, and
matching each audited library path and role to that transcript. It continues
to require exact version-1 equality for dependency-only packets. The loaded
snapshot bytes, rather than mutable post-execution originals, own the version-2
library digests. A writer-to-standalone regression covers the successful path,
audited-path drift, loaded-snapshot drift, sidecar drift, and harmless mutation
of an original library after execution.

No hosted or physical numeric run was started at `98c4f4c`.

## Exact-SHA review at `953b0f9ece520376d6c8710730c96a551ae878c9`

Technical, scientific, and verification review accepted the version-2
writer-to-standalone integration repair, but the independent gatekeeper found
a second coordinated provenance gap. Replacing one loaded runtime snapshot and
updating only its digest inside the same version-2 packet still passed: the
packet owned both the claimed digest and the bytes checked against it. The
exact-SHA verdict was therefore `FAIL`, and no hosted or physical run began.

The follow-up makes the separately retained GMP and MPFR installed-library
artifacts mandatory inputs at qualification writing and standalone replay.
Their role-specific hashes must equal the loaded snapshot hashes before the
version-2 packet is published and whenever it is validated. The writer records
their identities before scientific execution and rechecks them afterward. A
coordinated packet-plus-snapshot substitution now fails against this distinct
installed-library authority, while later mutation of an obsolete original
runtime path remains harmless when the authenticated install artifact and
loaded snapshot remain unchanged.

That caller-supplied installed-copy boundary was subsequently replaced by the
approved source-derived B2b authority. PR 209 independently rebuilt GMP 6.3.0
and MPFR 4.2.2 twice from the frozen archive hashes under one closed build
contract and canonical install prefix. The two runs produced byte-identical
versioned Mach-O libraries, freezing GMP SHA-256
`f872fbd53e7a265961e6c79ae846741637f59a28c04a839db55724bd12bbfb32`
and MPFR SHA-256
`2b51afa01ece4b200eacf92a318c38097595ab8cd656e0602cb0e55f9cce247e`.
Package 2 now rejects an alternate path, archive, installed byte sequence, mode,
symlink projection, Mach-O install/load projection, or envelope digest even
when caller-controlled packet and snapshot claims are changed together.

## Exact-SHA review at `77e597eb3cb960c2da20f908a0c218e632794498`

All four reviews rejected this first PR 209 integration. The entry points
validated the source-derived installed tree, but discarded the returned frozen
digests before the later oracle audit and snapshot established their runtime
baseline. A coordinated replacement in that interval could therefore make the
packet, loaded snapshots, and installed copies agree on non-frozen bytes. The
D12 producer also compared a canonical three-field clean-worktree observation
to a stale two-field literal and could not reach its provenance gate.

The follow-up carries the frozen binding into the installed-library digest
operation itself, requiring the exact canonical versioned paths, regular
single-link `0755` leaves, exact unversioned symlink targets, and PR 209 hashes.
Execution repeats the full source/archive/install audit at the actual snapshot
boundary and after scientific use; packet publication and standalone oracle
audit independently require the same frozen binding. Standalone bundle and D12
production validation repeat the source audit before and after their use. A
valid-at-T0/substituted-at-T1 regression exercises the previously accepting
sequence, and the D12 writer regression uses the canonical clean-worktree
record including `reason_code: null`.

## Hosted and physical-host disposition

The mandatory `macos-26` workflow completed successfully at exact SHA
`81396e5a88c3d91da674a6430bd2cb466aa7d24d` (run `32171942441`). It established
exact-head build correctness, pinned GMP/MPFR/OpenSubdiv provisioning, Release
and TSan reproduction, and execution of the then-current independence audit.
Its observed virtual Apple-M1 fingerprint was correctly classified
`UNQUALIFIED_PLATFORM`; `oracle_coverage_complete`,
`threading_tsan_complete`, and `package_review_complete` remained false, and
the budget verdict was `NEITHER_PASS_NOR_FAIL`. The run is useful hosted
correctness evidence but is not evidence for the later remediation and can
never satisfy numeric D12.

The available physical machine matches the frozen D12 fingerprint in plan
section 3.4: macOS `26.5.1` build `25F80`, `arm64`, `Mac17,2`, Apple M5,
25,769,803,776 bytes of memory, 10 logical CPUs split 4+6, and Apple Clang
`21.0.0 (clang-2100.1.1.101)`. That match is necessary but not sufficient.
Numeric execution additionally requires AC power, nominal thermal state, an
empty worktree, and an exact head that has passed technical, scientific,
verification, and gatekeeper review.

At that historical review point the verdict was `FAIL`, so physical-host
numeric D12 remained blocked until the later exact-SHA remediation gate.

## Exact-head hosted and physical execution at `192cb350`

The dependency-runtime remediation at exact SHA
`192cb3505bc4e1ce29a10253a2844b5e34a0be79` subsequently passed independent
technical, scientific, verification, and gatekeeper review. PR 207 was
force-with-lease updated to that exact linear head. GitHub Actions run
`32780683538` completed the mandatory `macos-26` correctness, dependency
provisioning, Release/TSan reproduction, invariant-representation analysis,
Package 2 executable audit, and artifact publication successfully. Its retained
artifact is named
`bfr-hosted-reproduction-192cb3505bc4e1ce29a10253a2844b5e34a0be79`.

The physical machine matched every frozen D12 field and was on AC power with
nominal `NSProcessInfo.thermalState`. A first complete 294-case B2 attempt was
retained as an explicitly unqualified infrastructure attempt because the Codex
sandbox denied the read-only `kern.hv_vmm_present` query. No case was discarded
or selectively rerun. A fresh complete run outside that sandbox produced a
`QUALIFIED` platform record with zero mismatches, exactly 294 cases and 1,176
qualified boundary observations. Its checkpoint is 1,603,916 bytes with
SHA-256 `4d1f90ea065901dcf9b7219997717ceac1c3207826778190e6d443610dd799f2`;
its B2 evidence is 2,868,511 bytes with SHA-256
`0efa692a7ebbc09f30bce8ccd60c860286a0f18f117e723b4d6a47871039af72`.
The inherited B2 D12 summary was `PASS`, with zero exceeded cases.

Package 2 D12 envelope production then stopped before any provider or
representation TSan worker execution with
`D12 full process-boundary probe is malformed or lossy`. The hardened B2c
decoder requires the actual platform-probe subprocess return code, but
`run_bfr_qualification.py::candidate_platform_probe` returned the successful
child JSON without adding its independently observed return code. The child
cannot authoritatively report its own process return code, so the correct fix is
at the parent observation boundary. The local remediation adds that observed
field only after requiring the child payload to have the exact closed key set,
and rejects a child-supplied counterfeit. Its focused regression, all 14 B2
tests, and all 99 anchored-row qualification tests pass. The physical attempt
therefore found an evidence-contract integration defect, not a candidate
numeric failure; no qualification, D9a reopening, B3 unblocking, Far selection,
or production activation follows.

Exact-SHA review of the first parent-owned return-code repair at
`7321355fbbcd1a26db3213f8b3d7688109a2f188` confirmed that genuine successful
probes gained the independently observed return code and passed the production
B2c decoder. It also found that ordinary `json.loads` collapsed duplicate
top-level or nested keys before the exact-keyset check. A child could therefore
publish conflicting duplicate `status` fields and have the last value accepted
as a successful probe. The follow-up replaces that lossy boundary with strict
recursive duplicate-key and non-standard numeric-constant rejection and adds
production-decoder attacks for both top-level and nested duplicates.

Exact-SHA review of that strict-key repair at
`fa4ea6bea991433c99504492b38f78b87a4d2759` confirmed that the duplicate-key
and non-standard-constant attacks were closed, but found that the default JSON
floating-point decoder could round `1.00000000000000001` to binary64 `1.0`.
Because Python equates that float to integer schema version `1`, the production
B2c decoder accepted the lossy value. The follow-up rejects every floating token
at the child boundary because the platform-probe grammar is integer/string/bool
only, and independently requires `schema_version` to have exact integer type
when persisted evidence is revalidated.

Exact-SHA review of the exact-number follow-up at
`fb7361ba388f00267167bae2820b4787bbaa2c92` passed technical, scientific,
verification, and gatekeeper review. The exact head was pushed unchanged and
the mandatory hosted `macos-26` workflow completed successfully as run
`32906285607`. As required, that hosted result established correctness and
provisioning but made no qualified numeric claim.

## Retained physical B2/D12 execution at `fb7361ba`

The authorized physical execution used a fresh external root while the
repository remained clean at exact SHA
`fb7361ba388f00267167bae2820b4787bbaa2c92`. The machine matched the frozen
macOS `26.5.1`/`25F80`, `Mac17,2`, Apple M5, memory, CPU, architecture, and
Apple Clang fingerprint. It remained on AC power with nominal thermal probes.
No failed repeat was discarded or selectively rerun.

The fresh B2 matrix completed all 294 cases and all 1,176 process-boundary
probes on a `QUALIFIED` platform. Its complete checkpoint SHA-256 is
`f0b658f690bf5861b53d23c34525cfa6e94ca9efce5f7b3df56d72f440b1a25b`;
its B2 evidence SHA-256 is
`0f4564fdd44b3fe047e50ca9c6ed9f766e4f370792c2c6079dcddd3ca6e62a1d`.
The inherited numeric D12 summary was `PASS` with zero exceeded cases: maximum
median `68,868,708` ns, maximum single run `94,450,042` ns, maximum RSS delta
`16,662,528` bytes, and maximum retained payload `82,720` bytes per face.

Package 2 D12 then ran uninterrupted for approximately three hours and
48 minutes. It published all 98 request ledgers and both serial references
before the first mandatory TSan tuple could be atomically published. The
provider serial reference is 102,170,376 bytes with SHA-256
`750391e177588fe25dc27dacacd9099da87cfd9685d3c29943d6ed52966ebbfc`;
the representation serial reference is 500,818,417 bytes with SHA-256
`4fa9f44188ce0e0a38d3b6c474f0184d54ca78cb6f97557cd4a1910de1e4ff28`.
The runner then exited `1` with
`D12 TSan worker failed without a sanitizer data-race report`. Zero worker
sidecars and no final `d12-evidence.json` were published. This is a blocking,
incomplete D12 result, not a race-only serial-support disposition and not a
candidate qualification result.

The failing worker's stdout was held in a temporary file and stderr was read
only into runner memory. Both were destroyed when the fail-closed exception
unwound, so the retained bundle cannot identify the failed role, return code,
signal, exact command, or diagnostic bytes. The proof-only follow-up therefore
atomically publishes one immutable first-failure directory before raising. Its
closed record binds the exact tuple and role, executable SHA-256, argv and
closed environment with their digests, PID and timestamps, exit/signal/timeout
state, failure class, and exact raw stdout/stderr paths, byte lengths, and
SHA-256 values. The writer immediately revalidates the committed directory;
the terminal failure includes the canonical record's SHA-256. Tampering, a
partial or aliased directory, a second overwrite, noncanonical metadata, or
descriptor drift fails closed. Genuine data-race reports retain their existing
separate semantics and successful tuples remain unchanged.

## Required next work

1. Commit the isolated TSan non-race failure-retention remediation and its
   provider, representation, timeout, unexpected-stderr, tamper, race, and
   success-path regressions.
2. Run four fresh independent exact-SHA reviews and obtain PASS verdicts.
3. Preserve the failed `fb7361ba` physical artifact permanently. Do not retry,
   overwrite, reinterpret, or discard it.
4. Only after a separately authorized reviewed-head transition, run a new full
   hosted correctness workflow and a new complete physical B2/D12 execution at
   that different exact SHA. A new execution cannot retroactively convert the
   retained `fb7361ba` result into a pass.
5. Submit any newly produced exact physical-host artifact for independent
   technical and scientific review before any qualification decision.

Until those steps complete, Package 2 remains `INCOMPLETE`, D9a remains
closed, B3 remains blocked, Far remains unselected, and production remains
unauthorized.
