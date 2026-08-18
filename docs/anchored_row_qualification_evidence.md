# B2c anchored-row qualification evidence

Status: **Package 2 implementation exists, but exact-SHA review is `FAIL`;
qualification remains `INCOMPLETE` and numeric D12 execution is blocked**

Candidate: `anchored_difference_rows_v1`

Approved B2b oracle-uncovered contract merge:
`022df7a8e11bcc4aee4df2254cc994cf4efdeb4f`

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

A separately coded uniform route refines a selected dependency patch and
intersects five consecutive depths with the primary intervals. Oracle cells
are emitted as either `COVERED` with the closed certified observation or
`UNCOVERED` with a frozen per-cell reason. The runner propagates actual
criterion-10 uncovered outcomes into criteria 11--13 and binds the result
partitions to the matrix ledgers.

The executable independence audit now checks the reviewed source allowlist,
compiler dependency closure, linked libraries and hashes, undefined symbols,
link-map ownership, MPFR/GMP calls, and forbidden OpenSubdiv/Far/Bfr symbols.
Execution snapshots the proof binaries and most input/provenance artifacts,
and process-tree timers begin before blocking pipe reads.

These are implemented mechanisms, not accepted scientific evidence. The exact
SHA review below found that the uniform route and persisted certification
boundary still do not satisfy the frozen oracle contract.

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

## Exact-SHA review at `c4ab2a0502db2fa470907dc1c647f45f8fe7899d`

The technical/scientific/verification/gatekeeper review set did **not** admit
this implementation. The tree and proof-only scope were clean, 96 focused
tests passed, all 3,506 literal mutations were rejected, and current-source
oracle probes reached six-row `COVERED` output on several extraordinary
fixtures. Those positives did not close the following blockers:

1. The primary and uniform routes consume shared refinement/coarse-mapping
   stencils. The uniform route does not independently begin from the complete
   coarse mesh and expand the exact backward stock-mask dependency closure.
2. Isolation-frame selection can apply coordinates and the Jacobian from the
   requested face to a different face containing the tracked extraordinary
   vertex.
3. Persisted ledger construction/validation can supply the private
   certification authority to a self-consistent fabricated covered record;
   literal `CERTIFIED` fields are therefore not yet replaced by an
   independently replayable certificate transcript.
4. The claimed directed-rounding mutation protocol compares correct RNDD and
   RNDU evaluations but does not replace one production rounding mode at a
   time and prove rejection.
5. Some frozen per-cell `UNCOVERED` reasons are not reachable from their
   actual failure sites.
6. The full oracle dependency/runtime chain is not completely immutable
   across execution: the compiler dependency transcript and loaded MPFR/GMP
   dylib bytes are not all snapshotted and re-bound post-execution.
7. Verification found a concrete frozen-corpus failure for nonzero local
   corners. Valence-7/8 and adjacent-extraordinary requests terminate with
   `map::at: key not found` instead of producing `COVERED` or an honest
   per-cell `UNCOVERED` record.

The hosted smoke probes cover only face 0/corner 0 examples and therefore do
not detect item 7. A green hosted job at this state would demonstrate build and
provisioning health, not correctness of the complete frozen oracle ledger.

## Hosted and physical-host disposition

The mandatory `macos-26` workflow has not yet been run at the post-TSan exact
head. When run, it can establish exact-head build correctness, dependency
provisioning, and execution of the independence audit. It can never satisfy
numeric D12 because a GitHub-hosted runner is `UNQUALIFIED_PLATFORM`; its only
honest numeric disposition is `INCOMPLETE`.

The available physical machine matches the frozen D12 fingerprint in plan
section 3.4: macOS `26.5.1` build `25F80`, `arm64`, `Mac17,2`, Apple M5,
25,769,803,776 bytes of memory, 10 logical CPUs split 4+6, and Apple Clang
`21.0.0 (clang-2100.1.1.101)`. That match is necessary but not sufficient.
Numeric execution additionally requires AC power, nominal thermal state, an
empty worktree, and an exact head that has passed technical, scientific,
verification, and gatekeeper review.

Because the current review verdict is `FAIL`, no physical-host numeric D12
run may begin. Running it now would create evidence at a scientifically
inadmissible SHA and conflict with the implementation plan.

## Required next work

1. Repair the seven exact-SHA oracle blockers above and add full-corpus tests,
   especially every `all_non6_corners` request and adjacent extraordinary
   cases.
2. Run four fresh independent exact-SHA reviews and obtain PASS verdicts.
3. Run the hosted `macos-26` workflow at that reviewed exact head and retain
   its correctness, provisioning, and independence-audit artifacts.
4. On the frozen physical host, confirm the worktree is empty, AC power and
   nominal thermal state are continuously observed, then execute numeric D12
   without selective reruns or discarded repeats.
5. Submit the exact physical-host artifact for independent technical and
   scientific review before any qualification decision.

Until those steps complete, Package 2 remains `INCOMPLETE`, D9a remains
closed, B3 remains blocked, Far remains unselected, and production remains
unauthorized.
