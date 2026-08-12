# B2c result-ledger review hardening

Status: **review-remediation evidence-format proposal; no qualification or
architecture decision**

This note freezes the result commitment introduced to repair the exact-SHA
B2c review failure.  It changes no fixture, sample, row, tolerance, target,
candidate policy, oracle rule, D12 budget, decision, route, or production
state.  If exact-SHA review classifies this evidence-format addition as a B2b
plan amendment rather than B2c report hardening, it requires a later explicit
user approval before an authoritative qualification execution.

## Persistent report binding

Every criterion record retains the frozen pre-result `key_ledger_sha256` and
adds `result_ledger_sha256`.  The latter is SHA-256 of the RFC 8785 bytes of
this closed object:

```json
{
  "encoding": "anchored-row-result-ledger-v1",
  "key_ledger_sha256": "<64 lowercase hex>",
  "observed_count": 0,
  "status": "<criterion status>",
  "stream_commitment": {}
}
```

The actual `observed_count` replaces zero.  An executed `PASS`, `FAIL`, or
`UNCOVERED` requires a non-null result commitment and exact equality between
the observed and frozen expected cell counts.  An omitted criterion has no
result commitment.

## Validator-owned canonical stream

Where the Python validator owns each comparison, the committed stream is the
RFC 8785 outer array of records in unsigned-lexicographic canonical-key order:

```text
[key, outcome, exact_value, target, reason]
```

`outcome` is `PASS`, `FAIL`, `COVERED`, or `UNCOVERED` as applicable.
`exact_value` is a closed exact rational/dyadic descriptor or a binary64 bit
label.  `reason` is null for a passing cell.  Missing, duplicated, substituted,
or non-increasing keys fail before a report can be written.  The stream
commitment is:

```json
{
  "canonical_result_stream_encoding": "rfc8785-key-outcome-exact-target-reason-v1",
  "canonical_result_stream_sha256": "<SHA-256 of the outer array>"
}
```

The absent primary oracle is not an absent result stream: all 1,188,000
request keys receive `UNCOVERED` and exact reason
`EIGENBASIS_CERTIFICATION_FAILED`; the covered stream is the canonical empty
array.

## Candidate-owned compact stream

For the tens of millions of executable evaluator cells, the candidate hashes
the following deterministic binary stream internally while it performs the
exact/bitwise comparison.  The runner independently regenerates the complete
canonical applicability-key ledger and binds that digest to this stream.

1. ASCII `anchored-row-candidate-outcome-v1` followed by one zero byte.
2. One record for every cell in the same canonical key order.
3. One outcome byte (`1` for pass, `0` for fail).
4. Three UTF-8 strings—`exact_value`, `target`, and `reason`—each preceded
   by its unsigned 64-bit big-endian byte length.  No padding or newline is
   present.

The stream commitment is:

```json
{
  "candidate_result_stream_encoding": "anchored-row-candidate-outcome-v1",
  "candidate_result_stream_sha256": "<candidate SHA-256>"
}
```

The candidate SHA-256 implementation has a known-answer self-test.  Candidate
aggregate counts and display maxima are diagnostics only; the result
commitment, exact maximum descriptor, deterministic maximum key, and first
failing key are validated independently before report finalization.

For `binary64_basis_probe_diagnostic`, every source contribution is committed,
but the pass/fail outcome is owned by the exact per-row/per-anchor/per-relabel
L1 sum.  Identity, rank reversal, and rank rotation are all present.  The
maximum witness binds the exact group numerator over `2^1074`, a contributing
canonical basis key, the displayed binary64 bits, and the final result
commitment.

## Authority boundary

This hardening cannot make unavailable primary Stam/uniform oracle work
covered, cannot turn hosted D12 observations into a numeric PASS or FAIL, and
cannot qualify `anchored_difference_rows_v1`.  D9a remains closed as Bfr not
qualified, B3 remains blocked, Far remains unselected, and production remains
unauthorized.
