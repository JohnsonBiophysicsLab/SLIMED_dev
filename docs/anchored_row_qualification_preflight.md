# Anchored-difference row qualification input preflight

Status: **proposal pending exact-SHA T2 review and explicit user approval; no
qualification execution authorized**

Date prepared: 2026-08-10

## Recorded architecture selection and boundary

After PR 199 merged the successful B2a feasibility preflight, the user
explicitly selected `anchored_difference_rows_v1` solely as the candidate for a
separate proof-only qualification package. The selection does not qualify the
candidate, reopen D9a, unblock B3, select Far, decide D9b, or authorize any
production code or route.

This document freezes the proposed qualification inputs before candidate
execution. No qualification runner, candidate result, oracle result, or
numerical output is produced by this package. Execution requires all of:

1. this exact input packet passes independent technical, scientific, and
   gatekeeper review;
2. the user explicitly approves the frozen inputs after those reviews; and
3. a separately scoped proof-only implementation package is authorized.

## Unchanged authority

The qualification must consume these authorities byte-for-byte and may not
regenerate, amend, widen, or selectively omit them:

- the six row kinds `position`, `du`, `dv`, `duu`, `duv`, and `dvv`;
- row-invariant tolerance `1.0e-12`;
- D10 targets:
  - position: `5.0e-6`;
  - each first derivative: `2.5e-5`;
  - each second derivative: `1.25e-4`;
- locality-only `flip_pair_row_changed_linf = 1.0e-12`;
- schema-2 B2 manifest file SHA-256
  `bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b`;
- manifest contract SHA-256
  `30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368`;
- the complete 17-entry execution manifest, frozen fixtures, face
  correspondence, sample order, radius/ray sequence, source-ID order, negative
  fixtures, and inner-radius exclusion `r < 2^-8`;
- exact OpenSubdiv `3.7.0`, MPFR `4.2.2`, 544-bit directed interval arithmetic,
  primary Stam eigenanalysis oracle, independent uniform-subdivision
  cross-check, analytic regular evaluator, and all independence/audit rules in
  Bfr plan section 3.2; and
- the approved D12 physical-host, build-provenance, timing, memory, threading,
  and failure-semantics contract.

Far remains a frozen artifact-inventory comparator only. It is not evaluated
as a candidate, used as an oracle, ranked, or promoted by this package.

## Candidate semantics under qualification

For each provider row with binary64 coefficients `c_i`, target `tau` (`1` for
position and `0` for derivatives), and anchor source `a`, the selected
representation evaluates

```text
position:   x_a + ordered_sum_i(c_i * (x_i - x_a))
derivative:       ordered_sum_i(c_i * (x_i - x_a)).
```

Every provider source and coefficient bit is retained. The anchor coefficient
is included and multiplies the exact zero difference. No residual-dependent
branch, coefficient normalization, source deletion, coefficient projection, or
per-row anchor selection is permitted.

For oracle comparison only, the validator expands the exact real functional
into the original source basis. It must not obtain `exact_sum` by summing at a
fixed MPFR precision. Every finite binary64 coefficient is decoded from its
bits into an arbitrary-precision signed integer numerator over the common
denominator `2^1074`; `tau` is represented in that same denominator, and every
addition and subtraction below is integer-exact:

```text
c'_i = c_i                                  for i != a
c'_a = c_a + tau - exact_sum_j(c_j).
```

This expansion is an algebraic identity for the selected representation. It is
never serialized as a replacement provider row, installed into a prepared
package, or described as repaired Bfr output. The report must publish the raw
Bfr invariant failure separately and state that the representation changes the
functional.

The exact dyadics are imported into the 544-bit MPFR oracle as certified
outward intervals: each lower endpoint uses `MPFR_RNDD`, each upper endpoint
uses `MPFR_RNDU`, and the validator checks endpoint order, MPFR return codes,
flags, finiteness, and containment of the integer-over-`2^1074` source value.
An exactly representable endpoint must have a zero ternary return; an inexact
endpoint must have the directionally correct ternary sign. Failure to decode,
accumulate, import, or certify any value is a fail-closed infrastructure
`INCOMPLETE`, never a rounded candidate value. Mutation tests must exercise
one-ulp coefficient changes, wide-exponent cancellation, wrong rounding mode,
wrong ternary signs, reversed endpoints, and nonfinite imports.

The existing D10 `U_coeff` and `U_geom` comparisons are generalized only to
accept these exact MPFR candidate coefficients. The primary Stam oracle,
intervals, uncertainty bounds, fixture positions, normalization length, and
targets do not change.

## Frozen anchor-sensitivity protocol

The proof candidate's primary policy remains the first oriented coarse-face
corner `v0`. Qualification must also evaluate the same row with `v1` and `v2`
as diagnostic anchors. The ordered anchor set is exactly `[v0, v1, v2]` for
every face/sample/row.

- Anchor choice depends only on the frozen oriented triangle, never on a
  coefficient, coordinate magnitude, residual, oracle interval, or outcome.
- Every anchor must be present in the original provider source set.
- All three anchors must independently pass the complete oracle and evaluator
  gates. A passing alternative cannot replace a failing `v0`, and a failing
  alternative cannot be omitted.
- All three unordered pairs `(v0,v1)`, `(v0,v2)`, `(v1,v2)` are compared in
  exact source-union coefficient `l1`, exact geometry-normalized Cartesian
  `l-infinity`, and emitted-evaluator geometry-normalized Cartesian
  `l-infinity` norms.
- Relabeling uses exactly two bijections over the ascending frozen vertex-ID
  list of each fixture: rank reversal `p_rev(k)=N-1-k` and one-rank cyclic
  shift `p_rot(k)=(k+1) mod N`. Connectivity, oriented faces, source IDs, and
  source data are relabeled together; anchor selection is rerun from the
  relabeled oriented face. After inverse canonical relabeling, the exact
  dyadic effective coefficients must be identical. Emitted binary64 results
  need not be bitwise identical because relabeling changes source-ID traversal;
  their difference is instead a mandatory instance of the frozen binary64
  fidelity gate below.
- Face rotation, reflection, or parameter-frame substitution is not silently
  treated as relabeling; the existing canonical-frame Jacobian rules remain
  authoritative.

## Frozen binary64 evaluator

Every emitted-evaluator comparison uses this single instruction sequence. The
row entries are traversed in strictly increasing signed source-ID order, which
is also the validated provider order. With `FE_TONEAREST`, ties-to-even, and an
initial accumulator whose bits are positive zero, for each entry execute and
round separately:

```text
delta = binary64(x_i - x_a)
term  = binary64(c_i * delta)
acc   = binary64(acc + term)
```

For position only, finish with `result = binary64(x_a + acc)`; for a derivative
the result is `acc`. Each subtraction, multiplication, accumulator addition,
and final position addition is a distinct binary64 operation. Contraction,
FMA substitution, reassociation, vector reduction, excess/extended precision,
flush-to-zero, and result-dependent traversal are prohibited. The executable
must verify the rounding environment before and after each case and use
compiler controls plus volatile binary64 stores or an equivalently reviewed
barrier that makes the specified round points observable. A mode mismatch,
nonfinite intermediate, negative-zero mismatch in a bitwise categorical gate,
or compiler proof that does not establish these semantics fails closed.

## Frozen qualification targets

The `0.1 x D10` values below are **new B2b proposals**, not B2p's existing
oracle-midpoint/enclosure or independent-uniform-oracle allocations. B2a's
numerical output was already visible when these values were proposed, but the
values are chosen mechanically from the previously approved D10 scale and are
not fitted to the observed `2.029487689014786e-11` perturbation. They require
explicit user approval before B2c can run. The independent rationales are:

- anchor sensitivity receives one order of margin below D10 so the prescribed
  oriented-corner choice cannot consume the accuracy allowance;
- binary64 fidelity receives one order of margin so implementation rounding
  remains subordinate to the exact represented functional; and
- each refinement transition receives one order of margin so unresolved
  approximation drift cannot consume the final D10 allowance.

| Criterion | Position | Each first derivative | Each second derivative | Application |
| --- | ---: | ---: | ---: | --- |
| D10 exact effective-row accuracy | `5.0e-6` | `2.5e-5` | `1.25e-4` | Rigorous `U_coeff` and `U_geom`, independently for every covered row and each of `v0`,`v1`,`v2`, at levels 7 and 8 and both Bfr cache modes. |
| D10 emitted-evaluator geometry accuracy | `5.0e-6` | `2.5e-5` | `1.25e-4` | Direct evaluation of all three frozen fixture-coordinate axes must independently satisfy the normalized geometry `l-infinity` oracle gate. No coefficient norm is inferred from this nonlinear rounded evaluator. |
| Pairwise anchor sensitivity | `5.0e-7` | `2.5e-6` | `1.25e-5` | Exact effective-row coefficient `l1`, exact geometry-normalized `l-infinity`, and direct emitted-evaluator geometry-normalized `l-infinity`, for all three anchor pairs at every covered row. |
| Binary64 evaluation fidelity | `5.0e-7` | `2.5e-6` | `1.25e-5` | Difference between the emitted evaluator and exact represented functional on every source basis vector and all three frozen fixture-coordinate axes, including both frozen relabelings. The sum of absolute basis-probe differences is a diagnostic fail-stop only; direct-axis normalized geometry is the scientific gate. |
| Successive-level stabilization | `5.0e-7` | `2.5e-6` | `1.25e-5` | For each of `6 -> 7` and `7 -> 8`: exact effective-row coefficient `l1` and exact normalized geometry, plus direct emitted-evaluator normalized geometry, independently for all anchors and both cache modes. |

Additional categorical gates:

- Constant fields `0`, `1`, `-1`, `2^20`, and `-2^20` must produce bitwise
  exact position identity and zero for every derivative; the separately
  retained numeric ceiling remains `1.0e-12` and cannot replace the bitwise
  requirement.
- The exact dyadic effective-coefficient sum is `1` for position and `0` for
  all derivatives for every anchor, and the outward MPFR interval must contain
  that exact value. This is a structural representation property, not an
  accuracy PASS.
- Levels 7 and 8 must each pass the full D10 target. Merely passing their
  difference is insufficient.
- The exact effective functional must pass the full D10 coefficient and
  geometry targets, and the end-to-end emitted evaluator must independently
  pass the full D10 direct-geometry target. Basis probing of rounded evaluation
  is not treated as a linear-functional coefficient bound. The new 10%
  component budgets are diagnostics and fail-stops inside the full ceilings,
  not allowances that may be added to them.
- The existing regular analytic row and integrand gate remains `5.0e-6` at
  levels 7 and 8 for every anchor and both cache modes.
- Cache-disabled and serial-cache represented evidence must be bitwise
  identical for every content/level/anchor tuple. Threaded-cache qualification
  retains the existing fully instrumented TSan rule.
- Every oracle-uncovered item remains explicitly uncovered and contributes no
  candidate PASS or FAIL. Coverage cannot be manufactured by an alternative
  anchor, Far, a midpoint diagnostic, or uniform subdivision alone.
- No scientific claim is made for `r < 2^-8`.

Targets apply per row and sample before aggregation. A median, percentile,
fixture average, favorable anchor, or favorable cache mode cannot hide a
failure.

## Execution matrix and ordering

The later proof must regenerate the complete exact-head B2 matrix. It validates
all 294 artifacts, then qualifies only the 196 Bfr-derived representation
cases. The fixed Bfr sweep remains levels 2 through 8 with sharp level 6 and
the existing cache modes. Levels 2 through 5 are reported; levels 6 through 8
own the stabilization gate; levels 7 and 8 own the full oracle gate.

For every valid row, the fail-closed order is:

1. dependency, exact-head, manifest, fixture, candidate-binary, source, and
   finite-value validation;
2. raw Bfr evidence reproduction, including the recorded D9a failure;
3. structural representation and constant-field checks;
4. regular analytic gate where applicable;
5. independent oracle coverage and validation;
6. exact effective-row D10 accuracy for all anchors;
7. exact and emitted pairwise anchor sensitivity, both frozen relabelings, and
   binary64 evaluator fidelity;
8. exact-row and emitted-geometry checks for both successive stabilization
   transitions;
9. unchanged D12 cost, memory, cache, and threading evidence; and
10. complete report finalization.

Under P9, a decisive candidate failure stops later non-decisive stages and is
published honestly. Infrastructure or uncovered-oracle state is `INCOMPLETE`,
not candidate PASS or FAIL. No failed criterion may be relabeled as oracle
uncertainty, anchor sensitivity, or platform incompleteness.

## Operational and provenance boundary

The representation stores no new per-row coefficient and derives its anchor
from the oriented face, so the existing D12 logical row-payload formula remains
unchanged. The later proof must nevertheless measure representation
construction/evaluation work separately and include all preparation work in the
unchanged D12 timing and RSS boundaries. Hosted macOS evidence remains
`UNQUALIFIED_PLATFORM` for numeric D12 gates; only the already frozen physical
host protocol can provide an operational PASS.

The independent oracle remains a separate executable that cannot link
OpenSubdiv or import the representation implementation. The validator may
consume both outputs but cannot share candidate arithmetic with the oracle.
Every exact effective-row transformation, anchor ordering, norm, target, and
criterion order must have focused mutation tests.

## Later package scope and verdict

Only after this input packet is reviewed and explicitly approved may a separate
proof implementation be proposed under `experiments/**`, `scripts/**`,
`tests/**`, evidence Markdown, and the existing dedicated external workflow
`.github/workflows/bfr_qualification.yml`. B2c may modify that workflow but may
not create a second workflow or alter any other `.github/**` path. It may add
its own proof-only `anchored-row-qualification-report-v1` JSON schema under
`scripts/**`; that new report is not a production output/checkpoint schema and
must not modify, replace, or relax any existing B2 or production schema. It may
not touch `src/**`, `include/**`, production tests, build flags, route
selectors, fixtures, D10/D12 authority, B3, CUDA, or existing output/checkpoint
schemas.

## Frozen B2c report contract

The B2c report is UTF-8 JSON with schema identifier
`anchored-row-qualification-report-v1`. Its canonical byte representation is
RFC 8785 JSON Canonicalization Scheme (JCS): Unicode strings and object keys,
IEEE-754 finite JSON numbers, escaping, member sorting, and number formatting
all follow RFC 8785, with no BOM, prefix, suffix, or trailing newline. B2c must
materialize an executable JSON Schema matching this section exactly, use
`additionalProperties: false` for every object, reject duplicate keys, and
reject every missing, extra, wrong-type, nonfinite, negative-zero numeric, or
noncanonical field. Any value whose exact binary64 bits matter also carries a
required 16-lowercase-hex-digit big-endian bit label that must decode to the
numeric value. Hashes are lowercase 64-character SHA-256 hex strings; enum
spelling is exact. The validator is separate from the candidate and oracle
executables and has mutation tests for every required key and verdict
transition.

Every external binding uses the same strict availability object:

```text
state       = PRESENT | MISSING | UNAVAILABLE | INVALID
sha256      = 64 lowercase hex only when PRESENT, otherwise JSON null
reason_code = JSON null only when PRESENT, otherwise a nonempty frozen enum
```

An all-zero or invented hash is invalid. The executable schema uses conditional
requirements so unavailable metadata is represented by `null`, never omitted
or fabricated. `MISSING` means an expected path or object does not exist;
`UNAVAILABLE` means a required tool/platform/dependency could not be obtained;
`INVALID` means bytes exist but fail identity, schema, provenance, or hash
validation. Any of these states is infrastructure `INCOMPLETE` unless a
separately established candidate failure takes verdict precedence.

These top-level records are required for every report. Early candidate or
infrastructure stops use the explicit availability and criterion states below:

| Record | Required binding |
| --- | --- |
| `identity` | schema ID; availability bindings for exact Git head before/after execution and clean-worktree observation; base and approved-B2b merge SHAs; candidate name exactly `anchored_difference_rows_v1`; start/end UTC; validator binary/script SHA-256. A complete run requires matching present heads and clean-worktree true; unavailable Git identity remains representable but forces `INCOMPLETE`. |
| `binaries` | availability objects for the actual B2 row-provider, representation-candidate, and independent-oracle binaries; when present, their SHA-256 plus complete source-file path/SHA inventories, compiler/link command and version digests, and GMP `6.3.0`, MPFR `4.2.2`, OpenSubdiv `3.7.0`, archive, build, install, link-map, and dynamic-dependency provenance. Candidate and oracle source/dependency inventories are distinct and the oracle independence audit is required. |
| `authority` | both expected frozen manifest hashes; exact six-row list; `1.0e-12`; D10 and new B2b targets; inner-radius rule; canonical sample/radius/ray/source order; expected frozen fixture-file hash inventory plus an actual availability/hash binding for every file; D12 contract and physical fingerprint. |
| `checkpoint` | one availability object for the exact schema-2 checkpoint; when present, its SHA-256, bound Git head, bound B2 row-provider binary SHA-256, and release-completeness state. The separately bound representation-candidate binary consumes these rows and cannot masquerade as their producer. |
| `artifacts` | exactly 294 expected-slot records in canonical manifest order. Each always carries the expected case identity, candidate label, cache mode, and level plus an availability state; a present slot also carries compressed SHA-256, decompressed JSON SHA-256, and canonical `B2ROWV1` digest, while the three hash fields are `null` for a non-present slot. A separate `unexpected_paths` array records every extra or nested path and its availability/hash rather than silently omitting it. |
| `matrix` | expected and observed counts: 294 artifact slots, 196 Bfr cases, 98 Far validation-only cases, 98 Bfr cache pairs, 1,386,000 raw Bfr rows, 4,158,000 anchor-row views, 12,549,936 provider terms, and 37,649,808 anchor-term views. It also carries expected/observed counts and cell-key-ledger SHA-256 values per criterion and partition. Pre-result ledgers are derived from the validated frozen corpus before candidate or oracle numeric results are read; observed key sets must match as specified below. |
| `criteria` | exactly one record for every named criterion below, with criterion ID, target and norm or categorical expectation, applicability, expected/observed cell counts, key-ledger SHA-256, status, maximum/witness when applicable, first failing key, and omission blocker. A maximum/witness is required for an executed numeric criterion and forbidden for an unexecuted one. |
| `d12_artifact` | availability/execution state plus exact-head, physical-fingerprint, and artifact SHA-256 binding. A qualified executed artifact uses `PRESENT`; `MISSING`, `UNAVAILABLE`, and `INVALID` use null bindings and force `INCOMPLETE` absent candidate failure. JSON null bindings are also allowed with `OMITTED_AFTER_CANDIDATE_FAILURE` and a named earlier failing criterion. Hosted evidence is explicitly `UNQUALIFIED_PLATFORM` and has its actual artifact hash but cannot satisfy physical D12. |
| `verdict` | exactly `PASS`, `FAIL`, or `INCOMPLETE`; first decisive criterion; ordered list of every failed, incomplete, uncovered, and omitted criterion; report-content SHA-256 computed over the RFC 8785 bytes of the entire report with only this field's digest member set to 64 zeroes. |

### Cell-key and ledger encoding

Every scientific cell key is a JSON array with these fields in this exact
order and type; an inapplicable position is JSON `null` rather than omitted:

```text
0  content_id       string
1  cache_mode       cache_disabled | serial_cache | cache_pair | null
2  level            integer 2..8
3  face_id          nonnegative integer
4  local_corner     nonnegative integer | null
5  sample_id        string
6  quantity         position | du | dv | duu | duv | dvv |
                    area_integrand | legacy_volume_integrand
7  view             exact_effective | emitted_binary64 | structural | null
8  anchor           v0 | v1 | v2 | null
9  relabel          identity | rank_reverse | rank_rotate_1 | null
10 basis_source_id  signed integer | null
11 axis             x | y | z | null
12 anchor_pair      v0_v1 | v0_v2 | v1_v2 | null
13 transition       6_7 | 7_8 | null
```

The schema freezes which nullable dimensions are populated for each criterion;
for example, a basis cell has one `basis_source_id` and null `axis`, while a
direct-geometry cell has one axis and null basis source. Each key is first
encoded as its RFC 8785 byte string. Keys are rejected if duplicated, sorted by
unsigned lexicographic order of those UTF-8 byte strings, placed in one JSON
array in that order, and the SHA-256 is taken over the RFC 8785 bytes of that
outer array with no newline. This is the sole cell-ledger encoding.

Oracle applicability has one pre-result `oracle_request` ledger containing
every frozen cell submitted to the oracle. After the independent oracle runs,
the observed `COVERED` and `UNCOVERED` ledgers must be disjoint, contain no key
outside the request, and have an exact set union equal to `oracle_request`.
Coverage is never predicted from candidate output or placed into a pre-result
coverage-state ledger.

The exact criterion-ID set is:

```text
bindings_and_independence
complete_artifact_inventory
raw_bfr_d9a_reproduction
representation_structure
constant_field_bits
relabel_exact_effective_coefficients
regular_analytic_exact_rows
regular_analytic_emitted_geometry
regular_analytic_area_integrand
regular_analytic_legacy_volume_integrand
oracle_coverage_and_crosscheck
exact_effective_d10_coeff
exact_effective_d10_geometry
emitted_direct_geometry_d10
anchor_sensitivity_exact_coeff
anchor_sensitivity_exact_geometry
anchor_sensitivity_emitted_geometry
binary64_basis_probe_diagnostic
binary64_direct_geometry_fidelity
relabel_emitted_geometry_fidelity
stabilization_6_7_exact_coeff
stabilization_6_7_exact_geometry
stabilization_6_7_emitted_geometry
stabilization_7_8_exact_coeff
stabilization_7_8_exact_geometry
stabilization_7_8_emitted_geometry
cache_mode_bit_identity
d12_preparation_cost
d12_retained_payload
d12_peak_rss
d12_cache_disabled_concurrency
d12_instrumented_tsan
```

Each criterion owns one exhaustive record per applicable frozen cell; no
summary-only PASS is valid. Oracle-uncovered cells remain present with state
`UNCOVERED` and make the overall result `INCOMPLETE` unless an earlier candidate
failure already fixes `FAIL`. The four regular criterion records use the
existing regular coverage only. The two row records cover all six row
quantities in their named exact/emitted views. Each integrand record covers
both `exact_effective` and `emitted_binary64` views, all three Cartesian source
axes needed by the frozen formulas, every anchor, both cache modes, levels 7
and 8, and its own `area_integrand` or `legacy_volume_integrand` quantity key at
the unchanged `5.0e-6` gate. Far contributes artifact validation records and no
candidate criterion cell.

The allowed criterion status enum is exactly:

```text
PASS
FAIL
INCOMPLETE
UNCOVERED
OMITTED_AFTER_CANDIDATE_FAILURE
OMITTED_AFTER_INFRASTRUCTURE_FAILURE
```

Status ownership and verdict effects are frozen by group:

| Criterion group | Criterion IDs | Allowed executed outcome and ownership |
| --- | --- | --- |
| Required infrastructure | `bindings_and_independence`, `complete_artifact_inventory`, `raw_bfr_d9a_reproduction` | `PASS` or `INCOMPLETE`; never candidate `FAIL`. A missing/invalid binding, corpus mismatch, or failure to reproduce the frozen raw D9a observation is infrastructure incomplete. Later records may be `OMITTED_AFTER_INFRASTRUCTURE_FAILURE`. |
| Oracle validity/coverage | `oracle_coverage_and_crosscheck` | `PASS`, `UNCOVERED`, or `INCOMPLETE`; never candidate `FAIL`. `UNCOVERED` is valid independent-oracle noncoverage; eigensystem, isolation, cross-check, provenance, or enclosure failure is `INCOMPLETE`. |
| Candidate scientific | `representation_structure`, `constant_field_bits`, `relabel_exact_effective_coefficients`, all four `regular_analytic_*` IDs, all three D10 IDs, all three `anchor_sensitivity_*` IDs, all three binary64 fidelity/diagnostic IDs, all six stabilization IDs, and `cache_mode_bit_identity` | `PASS` or candidate-owned `FAIL` after required inputs validate. Any exceeded numeric/categorical target, nonfinite candidate arithmetic, evaluator-semantics mismatch, structural failure, or cache disagreement is `FAIL`. If it cannot execute because of prior infrastructure, it is omitted with the infrastructure blocker rather than mislabeled. |
| D12 hybrid | all five `d12_*` IDs | `PASS` or candidate-owned `FAIL` only from exact-head evidence on the qualified frozen physical host; a measured budget overrun or fully instrumented race is `FAIL`. Missing/unqualified platform, missing instrumentation, invalid provenance, or unavailable evidence is `INCOMPLETE`. Hosted raw measurements cannot PASS or FAIL numeric budgets. |

An omitted status is legal only for a criterion ordered after its named blocker,
requires zero observed cells and null maximum/witness, and has no independent
verdict effect. `FAIL` is forbidden for infrastructure and oracle groups;
`UNCOVERED` is forbidden outside the oracle group; `INCOMPLETE` in a candidate
scientific record is represented as its causal infrastructure record plus
`OMITTED_AFTER_INFRASTRUCTURE_FAILURE`, not as an ambiguous candidate outcome.

Verdict precedence is fail-closed and deterministic:

1. any established candidate `FAIL` makes the overall verdict `FAIL`, even if
   another criterion is incomplete or uncovered;
2. otherwise, any required `INCOMPLETE`, `UNCOVERED`, unqualified physical D12
   state, or missing infrastructure makes it `INCOMPLETE`; and
3. `PASS` requires every applicable scientific record to pass, every expected
   and observed ledger/count to match, and the physical-host D12 artifact to be
   qualified and bound to the exact reviewed head.

After the first established candidate failure, later non-decisive scientific or
D12 execution may stop under P9. Its criterion records may not disappear: each
must use `OMITTED_AFTER_CANDIDATE_FAILURE`, zero observed cells, and the exact
earlier blocker ID. Binding, full 294-artifact validation, raw D9a reproduction,
and report finalization can never be omitted after a candidate failure. After
an infrastructure failure, any stage that cannot honestly execute uses
`OMITTED_AFTER_INFRASTRUCTURE_FAILURE` with the exact blocker; expected
artifact slots and all top-level records still remain in the report with
explicit availability states. An infrastructure failure before any candidate
result permits no candidate `FAIL` and resolves to `INCOMPLETE`.

The qualification report must resolve to exactly one of:

- `PASS`: every applicable frozen scientific criterion passes and the required
  physical-host D12 evidence is qualified;
- `FAIL`: a named candidate criterion fails; or
- `INCOMPLETE`: required infrastructure, oracle coverage, or physical-platform
  evidence is unavailable without a candidate failure.

Exact-SHA verification, technical, scientific, and gatekeeper review follow the
completed proof. Even a reviewed `PASS` does not automatically qualify the
architecture, revise D9a, unblock B3, or authorize production. The user makes a
later explicit qualification decision and separately authorizes whatever plan
amendment would follow.

## Stop conditions

Stop before execution if review or approval would require any target widening,
fixture/manifest change, oracle coupling, adaptive anchor choice, favorable
sample omission, Far comparison as truth, post-hoc normalization, implicit Bfr
requalification, B3 work, or production change. Stop during the later proof on
any provenance mismatch, numeric/bit-label disagreement, nonfinite arithmetic,
inexact dyadic accumulation, uncertified outward import, evaluator-order or
rounding-environment mismatch, missing anchor/source/row/report key, extra
artifact or report key, ledger-count mismatch, unreported oracle gap, or
result-dependent target or protocol change.
