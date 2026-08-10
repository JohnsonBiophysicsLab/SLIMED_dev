# Invariant-preserving row-representation architecture preflight

Status: **authorized proof-only T2 preflight; architecture not selected**

Date authorized: 2026-08-10

## Decision boundary

D9a remains **Bfr not qualified**. This package does not reopen D9a, qualify
Bfr, select a replacement architecture, promote Far, start B3, decide D9b, or
activate production. It prepares one different representation for exact-SHA
technical, scientific, and gatekeeper review before the user makes any
architecture decision.

The user authorization freezes all of the following:

- the row-invariant tolerance remains exactly `1.0e-12`;
- the D10 inputs and their two frozen manifest hashes remain unchanged;
- the six row kinds remain `position`, `du`, `dv`, `duu`, `duv`, and `dvv`;
- original coarse-mesh source identities remain the functional domain;
- post-hoc coefficient normalization is forbidden;
- Far remains a regression comparator only;
- B3 implementation and every production route remain forbidden; and
- an exact-SHA technical, scientific, and gatekeeper verdict is required before
  the representation can be selected.

## Candidate hypothesis

The proof candidate is `anchored_difference_rows_v1`. For each face/sample/row,
the anchor is the first corner of the oriented coarse face. The representation
retains every provider coefficient with identical binary64 bits, including the
anchor coefficient. The anchor term multiplies the exact zero difference
`x_anchor - x_anchor`.

For scalar source data `x`, the represented position row is

```text
x_anchor + ordered_sum(c_i * (x_i - x_anchor)), all i
```

and every derivative row is

```text
ordered_sum(c_i * (x_i - x_anchor)), all i.
```

This is a different representation, not a repair pass over an explicit row.
No coefficient is adjusted, omitted, synthesized, redistributed, projected, or
normalized. Constant fields are reproduced structurally because every
difference is zero. The candidate does change the evaluated functional relative
to direct coefficient-times-coordinate evaluation; that perturbation is a
mandatory observation and cannot be dismissed as roundoff.

The public production contract is not edited by this package. The six-row and
source-ID requirements are frozen scientific inputs to the experiment; whether
a future contract should encode an anchored functional is part of the later
architecture decision.

## Proof inputs and execution

The runner is
[`run_invariant_row_representation_preflight.py`](../scripts/run_invariant_row_representation_preflight.py).
It consumes the complete schema-2 B2 Release checkpoint and all 294 compressed
case artifacts. Before analyzing a row, it independently revalidates:

- exact checkpoint schema and exact-head binding;
- the frozen manifest file SHA-256
  `bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b`;
- the frozen manifest contract SHA-256
  `30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368`;
- all 294 expected case identities in canonical order;
- every compressed artifact hash, decompressed JSON hash, canonical `B2ROWV1`
  digest, row/sample/source schema, and frozen fixture reconstruction; and
- the complete artifact-directory inventory, rejecting missing, extra, or
  nested files.

The Bfr rows are the qualification-target inputs. All Far artifacts must still
validate so that the package cannot silently alter or omit the frozen matrix,
but no Far row is represented or ranked.

The hosted workflow regenerates the complete matrix at the exact pull-request
head, runs the preflight against that binding, and uploads
`invariant-row-representation-preflight.json` beside the B2 evidence.

## Frozen preflight acceptance boundary

The representation is only **feasible for later scientific review** if all of
these hold:

1. All 294 frozen artifacts validate and the matrix contains exactly 196 Bfr
   cases plus 98 Far comparator cases.
2. The preflight reproduces D9a's 124 failing Bfr cases and maximum ordered
   row-sum residual `2.0368522054550406e-11` at the unchanged `1.0e-12` gate.
3. Every Bfr row has its first oriented coarse-face corner in its original
   source set.
4. All six row kinds, every original source ID, and every provider coefficient
   are retained bitwise; the anchor coefficient multiplies an exact zero.
5. The complete constant-field challenge set produces exact binary64 position
   identity and zero derivatives.
6. The represented rows are bitwise identical between cache-disabled and
   serial `SurfaceFactoryCache` evidence for all 98 content/level pairs.
7. The raw-versus-represented operator difference is finite and is reported on
   both actual fixture coordinates and the frozen centered/normalized frame.
8. No tolerance, D10 input, row kind, production file, route, or decision
   status changes.

There is intentionally no after-the-fact ceiling on the operator perturbation.
This preflight reports it; a later candidate qualification must freeze an
independent scientific oracle and acceptance target before it runs.

Stop immediately on an absent anchor, changed source identity, coefficient-bit
mutation or omission, nonfinite result, incomplete artifact set, failure to reproduce D9a,
cache-mode disagreement, or any need to relax a frozen input.

## Preliminary replay on the reviewed B2 artifacts

A local pre-commit development replay consumed the complete B2 artifact set
bound to implementation head `8282549ac2e0d0819edb095772e4b85aa204209d` and
checkpoint SHA-256
`894d6c2ae192fe67c48ddab63cbde11b21a0dff4eebdb90a2aed90aca9b8057c`.
It is a preliminary implementation check, not the required exact-head verdict.

The replay examined 1,386,000 Bfr rows and 12,549,936 coefficient terms. It
found no missing anchor, source-ID change, retained coefficient mutation or omission, constant-
field failure, or cache-mode disagreement. It reproduced 124 failing cases,
60,656 failing rows, and the recorded maximum ordered residual. The maximum
raw-versus-represented operator difference was
`3.283595617631363e-11` on actual fixture coordinates and
`2.029487689014786e-11` in the centered/normalized frame. The canonical
representation digest was
`280ba3582c120bca036d3995ec61711a775ee77fc5671a38dd4b3cb3bdccc131`.

These observations establish neither scientific adequacy nor architecture
selection. They exist so reviewers can assess the candidate's actual numerical
effect rather than treating structural invariance as sufficient evidence.

## Required verdict

After the hosted exact-head artifact is complete, independent reviewers must
answer separately:

- **technical:** is the artifact binding, total fixture coverage, mutation
  resistance, source mapping, bit preservation, and no-production boundary
  reproducible?
- **scientific:** is this genuinely a representation change rather than hidden
  normalization, are structural invariants distinguished from accuracy, and is
  the reported perturbation adequate only as a preflight observation?
- **gatekeeper:** do both reviews apply to the same exact commit, are all hosted
  checks green, and does the package refrain from selecting the architecture?

Even three PASS verdicts authorize only presentation of the candidate to the
user. Only the user may select it or authorize a separately scoped qualification
package.
