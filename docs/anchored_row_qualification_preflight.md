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

For oracle comparison only, the validator may expand the exact real functional
into the original source basis after importing every provider binary64
coefficient exactly into MPFR:

```text
c'_i = c_i                                  for i != a
c'_a = c_a + tau - exact_sum_j(c_j).
```

This expansion is an algebraic identity for the selected representation. It is
never serialized as a replacement provider row, installed into a prepared
package, or described as repaired Bfr output. The report must publish the raw
Bfr invariant failure separately and state that the representation changes the
functional.

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
  exact source-union coefficient `l1` and geometry-normalized Cartesian
  `l-infinity` norms.
- Source-ID relabeling with the oriented face and source data relabeled together
  must preserve each represented functional bit-for-bit. Face rotation,
  reflection, or parameter-frame substitution is not silently treated as
  relabeling; the existing canonical-frame Jacobian rules remain authoritative.

## Frozen qualification targets

The factor `0.1` below is the existing B2p oracle-uncertainty allocation. It is
reused as a uniform budget partition before qualification execution; it is not
derived from B2a's observed `2.029487689014786e-11` normalized perturbation.

| Criterion | Position | Each first derivative | Each second derivative | Application |
| --- | ---: | ---: | ---: | --- |
| D10 effective-row accuracy | `5.0e-6` | `2.5e-5` | `1.25e-4` | Both rigorous `U_coeff` and `U_geom`, independently for every covered row and each of `v0`,`v1`,`v2`, at levels 7 and 8 and both Bfr cache modes. |
| End-to-end binary64 evaluator accuracy | `5.0e-6` | `2.5e-5` | `1.25e-4` | The basis-probed emitted binary64 functional must independently satisfy the full D10 coefficient `l1` and normalized geometry `l-infinity` oracle gates; component budgets below cannot be added to widen D10. |
| Pairwise anchor sensitivity | `5.0e-7` | `2.5e-6` | `1.25e-5` | Both exact effective-row coefficient `l1` and geometry-normalized `l-infinity`, for all three anchor pairs at every covered row. |
| Binary64 evaluation fidelity | `5.0e-7` | `2.5e-6` | `1.25e-5` | Difference between the emitted ordered binary64 anchored evaluation and the exact MPFR represented functional, tested on every source basis vector and all three fixture-coordinate axes. Both inferred coefficient `l1` and normalized geometry `l-infinity` must pass. |
| Successive-level stabilization | `5.0e-7` | `2.5e-6` | `1.25e-5` | Both coefficient `l1` and normalized geometry `l-infinity` for each of levels `6 -> 7` and `7 -> 8`, independently for all three anchors and both cache modes. |

Additional categorical gates:

- Constant fields `0`, `1`, `-1`, `2^20`, and `-2^20` must produce bitwise
  exact position identity and zero for every derivative; the separately
  retained numeric ceiling remains `1.0e-12` and cannot replace the bitwise
  requirement.
- The exact effective MPFR coefficient sum is `1` for position and `0` for all
  derivatives for every anchor. This is a structural representation property,
  not an accuracy PASS.
- Levels 7 and 8 must each pass the full D10 target. Merely passing their
  difference is insufficient.
- Both the exact effective functional and the end-to-end emitted binary64
  functional must independently pass the full D10 target. The 10% component
  budgets are diagnostics and fail-stops inside that ceiling, not allowances
  that may be added to it.
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
7. binary64 evaluator fidelity and pairwise anchor sensitivity;
8. two successive stabilization transitions;
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
`tests/**`, one dedicated external workflow, and evidence Markdown. It may not
touch `src/**`, `include/**`, production tests, build flags, route selectors,
fixtures, D10/D12 authority, B3, CUDA, or output/checkpoint schemas.

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
missing anchor/source/row, unreported oracle gap, or result-dependent target or
protocol change.
