# B2b anchored-row result-evidence amendment

Status: **proposed frozen-input amendment; no execution authority**

This document is an additive amendment to
[`anchored_row_qualification_preflight.md`](anchored_row_qualification_preflight.md).
It repairs evidence-contract gaps found during exact-SHA review of the first
B2c development execution. It changes no candidate, fixture, sample, row,
tolerance, D10 target, B2b component target, oracle rule, D12 budget, decision,
route, or production state. It is not authoritative until it passes exact-SHA
verification, technical, scientific, and gatekeeper review and is explicitly
approved by the user.

The first development execution and all values observed from it are
non-authoritative. No target or acceptance rule in this amendment is derived
from those values.

## Closed criterion result fields

Every one of the 32 ordered criterion records retains its frozen pre-result
`key_ledger_sha256` and adds these required fields:

```text
result_ledger_sha256       64 lowercase hex | null
result_merkle_root_sha256  64 lowercase hex | null
```

An executed `PASS`, candidate-owned `FAIL`, oracle `UNCOVERED`, or exact
oracle-dependent propagated `UNCOVERED` has a
complete result record for every expected applicability key, so both digests
are non-null and `observed_cell_count == expected_cell_count`. The rule for an
executed infrastructure or D12 `INCOMPLETE` is deterministic: a complete
expected result set requires both commitments; a partial or absent set requires
both commitments to be null and cannot be represented as a complete ledger.
An omitted criterion has zero observed cells and null result digests.

The executable schema freezes, with `const` or exact closed alternatives, the
criterion ID, position, applicability, expected count, target, expectation,
allowed status, result-digest nullability, exact-value form, reason enum,
maximum form, witness form, first-failure form, and omission-blocker form for
each criterion. It also freezes every authority value, including the exact six
rows, `1.0e-12`, all D10 targets, all B2b component targets, relabels, anchors,
levels, sample order, radius/ray order, D12 budgets, dependency versions, and
physical-host fingerprint. A validator that accepts a changed authority value
or criterion target is invalid.

## Canonical result record and ledger

The sole result record is this RFC 8785 array:

```text
[key, outcome, exact_value, target, reason]
```

- `key` is the criterion's already frozen scientific, D12 operational, or
  infrastructure applicability key.
- `outcome` is `PASS`, `FAIL`, `UNCOVERED`, or `INCOMPLETE`, as permitted by
  the criterion's frozen ownership.
- `exact_value` is the criterion-specific closed exact descriptor. Binary64
  observations use a 16-lowercase-hex-digit bit label; signed exact dyadics use
  the signed form frozen below; structured observations use only the exact
  fields in the normative manifest.
- `target` is the criterion-specific closed target descriptor, or null for a
  categorical criterion.
- `reason` is null for `PASS` and otherwise one exact criterion-owned frozen
  reason code.

Records are sorted by unsigned lexicographic order of the RFC 8785 bytes of
`key`. Missing, extra, duplicated, substituted, or non-increasing keys fail
closed. `result_ledger_sha256` is SHA-256 of the RFC 8785 outer array of all
records, with no newline. A count, maximum, candidate-provided digest, or
pre-result key digest cannot substitute for this result ledger.

The complete outer-array bytes are persistent sidecars, not transient inputs.
For criterion ordinal `NN` and ID `criterion_id`, the only permitted relative
path is
`anchored-row-result-ledgers-v1/NN-criterion_id.result-ledger.json`, where
`NN` is two decimal digits `00` through `31`. Every criterion record has this
additional closed object:

```text
result_ledger_artifact:
  availability  standard frozen availability object
  relative_path exact canonical path when PRESENT, otherwise null
  byte_length   uint64 JSON integer when PRESENT, otherwise null
  record_count  uint64 JSON integer when PRESENT, otherwise null
```

When present, its bytes must be exactly the canonical outer array, its SHA-256
must equal `result_ledger_sha256`, its record count must equal the criterion's
observed and expected counts, and its Merkle root must equal
`result_merkle_root_sha256`. Non-present result sidecars require both result
digests to be null. The report-content digest binds every sidecar descriptor;
the exact-head artifact bundle publishes the report and all present sidecars.
The standalone validator consumes every sidecar byte and recomputes record
count, key order, key-ledger SHA-256, result-ledger SHA-256, Merkle root,
outcomes, maximum, first maximum tie, first failure, and verdict.

The runner owns report construction. A candidate executable may stream compact
observations in expected-key ordinal order, but it may not supply the
authoritative key, reference/expected value, error, aggregate, target, outcome,
reason, maximum, witness, or final digest. The stream begins with
ASCII `anchored-row-candidate-values-v1` and one zero byte. Each record is:

```text
uint64_be expected_key_ordinal
uint64_be payload_byte_length
payload_byte_length bytes of a criterion-specific RFC 8785 observation object
```

Ordinals start at zero, increase by one, and end at expected count minus one;
payload length is at most `2^20` and the total record count is at most `2^63-1`.
Short, extra, repeated, out-of-order, noncanonical, wrong-shape, or trailing
bytes fail closed. The runner regenerates every key from the validated corpus,
independently performs the exact/bitwise comparison, constructs the canonical
record, and computes both commitments. Every compact candidate record crosses
the process boundary; a candidate hash of unobserved records is insufficient.

Every candidate observation object is closed. The complete observation-only
vocabulary is:

```text
candidate_structure_observation_v1 =
  {kind, canonical_source_ids, provider_coefficient_bits,
   effective_coefficients}
candidate_binary64_observation_v1 = {kind, observed_bits}
candidate_dyadic_vector_observation_v1 = {kind, source_ids, values}
candidate_interval_vector_observation_v1 =
  {kind, source_ids, observed_intervals}
candidate_exact_geometry_observation_v1 = {kind, axis, observed}
candidate_emitted_geometry_observation_v1 = {kind, axis, observed_bits}
candidate_exact_integrand_observation_v1 =
  {kind, view:"exact_effective", observed_interval}
candidate_emitted_integrand_observation_v1 =
  {kind, view:"emitted_binary64", observed_bits}
candidate_basis_observation_v1 = {kind, emitted_basis_bits}
candidate_row_signature_observation_v1 =
  {kind, cache_disabled_entries, serial_cache_entries}
```

Each `kind` is exactly its left-hand type name. Source arrays are nonempty,
strictly increasing signed integers and parallel to their value arrays.
Dyadics are `signed_dyadic_v1`; intervals are `interval_rational_v1`;
`observed` is a signed dyadic or rational; every bits member is 16 lowercase
hex. Each row-signature entry is exactly
`[source_id,provider_coefficient_bits,effective_signed_dyadic]`, both entry
arrays are complete, strictly source-ordered, and contain no digest. The runner
independently imports/recomputes all observation members from raw candidate
process output before it derives the result vocabulary below.

The per-criterion observation mapping is exhaustive:

```text
bindings_and_independence                     none; runner Git/provenance input
complete_artifact_inventory                   none; runner artifact bytes
raw_bfr_d9a_reproduction                      none; runner checkpoint/raw rows
representation_structure                     candidate_structure_observation_v1
constant_field_bits                           candidate_binary64_observation_v1
relabel_exact_effective_coefficients          candidate_dyadic_vector_observation_v1
regular_analytic_exact_rows                   candidate_dyadic_vector_observation_v1
regular_analytic_emitted_geometry             candidate_emitted_geometry_observation_v1
regular_analytic_area_integrand               view-selected candidate_exact_integrand_observation_v1 | candidate_emitted_integrand_observation_v1
regular_analytic_legacy_volume_integrand      view-selected candidate_exact_integrand_observation_v1 | candidate_emitted_integrand_observation_v1
oracle_coverage_and_crosscheck                none; independent oracle bytes
exact_effective_d10_coeff                     candidate_dyadic_vector_observation_v1
exact_effective_d10_geometry                  candidate_exact_geometry_observation_v1
emitted_direct_geometry_d10                   candidate_emitted_geometry_observation_v1
anchor_sensitivity_exact_coeff                candidate_dyadic_vector_observation_v1
anchor_sensitivity_exact_geometry             candidate_exact_geometry_observation_v1
anchor_sensitivity_emitted_geometry           candidate_emitted_geometry_observation_v1
binary64_basis_probe_diagnostic               candidate_basis_observation_v1
binary64_direct_geometry_fidelity             candidate_emitted_geometry_observation_v1
relabel_emitted_geometry_fidelity             candidate_emitted_geometry_observation_v1
stabilization_6_7_exact_coeff                 candidate_dyadic_vector_observation_v1
stabilization_6_7_exact_geometry              candidate_exact_geometry_observation_v1
stabilization_6_7_emitted_geometry            candidate_emitted_geometry_observation_v1
stabilization_7_8_exact_coeff                 candidate_dyadic_vector_observation_v1
stabilization_7_8_exact_geometry              candidate_exact_geometry_observation_v1
stabilization_7_8_emitted_geometry            candidate_emitted_geometry_observation_v1
cache_mode_bit_identity                       candidate_row_signature_observation_v1
d12_preparation_cost                          none; runner process observation sidecar
d12_retained_payload                          none; runner process observation sidecar
d12_peak_rss                                  none; runner process observation sidecar
d12_cache_disabled_concurrency                none; runner complete worker-output sidecars
d12_instrumented_tsan                         none; runner sanitizer and complete worker-output sidecars
```

`none` means the candidate-values stream has no record for that criterion;
the named independent runner input still must cross its process/file boundary
and be fully rescanned. A schema that accepts a result exact-value object as a
candidate observation, or accepts candidate-supplied expected/error/aggregate
members, is invalid.

## Normative exact-value vocabulary

Every object below is closed (`additionalProperties: false`). Decimal and
hexadecimal strings are lowercase/canonical, have no leading zero except the
single string `"0"`, and never carry a sign unless the field says so.

- `signed_dyadic_v1` = `{kind:"signed_dyadic_v1", sign:-1|0|1,
  numerator_hex:string, denominator_power:1074|2148}`. `sign=0` requires
  `numerator_hex:"0"`; otherwise the numerator is positive and nonzero.
- `absolute_dyadic_v1` = `{kind:"absolute_dyadic_v1",
  numerator_hex:string, denominator_power:1074|2148}` with a nonnegative
  numerator.
- `rational_v1` = `{kind:"rational_v1", numerator:string,
  denominator:string}` with a canonical signed base-10 numerator, positive
  base-10 denominator, and coprime absolute numerator/denominator.
- `absolute_rational_v1` = `{kind:"absolute_rational_v1",
  numerator:string,denominator:string}` with a canonical nonnegative base-10
  numerator, positive denominator, and coprime pair.
- `rational_over_sqrt_v1` = `{kind:"rational_over_sqrt_v1",
  absolute_numerator:string, absolute_denominator:string,
  scale_squared_numerator:string, scale_squared_denominator:string}`. The
  absolute numerator is nonnegative; the other three numeric members are
  positive canonical base-10 integers; each numerator/denominator pair is
  coprime, and the value is `(absolute_numerator /
  absolute_denominator) / sqrt(scale_squared_numerator /
  scale_squared_denominator)`. Exact zero uses
  `absolute_numerator:"0"`, `absolute_denominator:"1"`, while both scale
  members remain positive and coprime. This form accepts the exact binary
  rationals of arbitrary exponent produced by directed 544-bit MPFR endpoints;
  no restriction to `2^1074` or `2^2148` is imposed.
- `binary64_pair_v1` = `{kind:"binary64_pair_v1",
  observed_bits:16hex, expected_bits:16hex}`.
- `digest_pair_v1` = `{kind:"digest_pair_v1", observed_sha256:sha256,
  expected_sha256:sha256}`.
- `interval_rational_v1` = `{kind:"interval_rational_v1",
  lower:rational_v1, upper:rational_v1}` with `lower <= upper`.
- `scalar_comparison_v1` = `{kind:"scalar_comparison_v1", observed:
  signed_dyadic_v1|rational_v1, expected:signed_dyadic_v1|rational_v1,
  absolute_error:absolute_dyadic_v1|absolute_rational_v1}`.
- `oracle_coefficient_l1_v1` = `{kind:"oracle_coefficient_l1_v1",
  source_ids:[signed integers],observed:[signed_dyadic_v1],
  oracle_intervals:[interval_rational_v1],
  absolute_error_uppers:[absolute_rational_v1],
  l1:absolute_rational_v1}`. All four arrays have the same positive length,
  source IDs are strictly increasing, and every observed dyadic uses
  denominator power 1074. For source `i`, the runner derives
  `absolute_error_uppers[i] = max(|observed_i-lower_i|,
  |observed_i-upper_i|)` exactly and requires `l1` to be the reduced exact sum
  of every upper. This is the sole covered-cell coefficient result form for
  criterion 11; propagated oracle-uncovered cells use null as specified below.
- `exact_coefficient_l1_v1` = `{kind:"exact_coefficient_l1_v1",
  source_ids:[signed integers],observed:[signed_dyadic_v1],
  expected:[signed_dyadic_v1],absolute_errors:[absolute_dyadic_v1],
  l1:absolute_dyadic_v1}`. All four arrays have the same positive length,
  source IDs are strictly increasing, and every dyadic has denominator power
  1074. The runner derives each error by exact signed-integer subtraction and
  absolute value over the common denominator and requires `l1` to equal their
  exact integer sum. This is the sole coefficient result form for criteria
  14, 20, and 23.
- `binary64_scalar_v1` = `{kind:"binary64_scalar_v1",bits:16hex}`.
- `normalized_interval_bound_v1` = `{kind:
  "normalized_interval_bound_v1",difference_interval:interval_rational_v1,
  distance_upper:absolute_rational_v1,
  scale_squared_interval:interval_rational_v1,
  scale_lower:rational_v1,ideal_normalized:rational_over_sqrt_v1,
  normalized_upper:absolute_rational_v1}`. `scale_lower` is strictly positive;
  the scale-squared interval is nonnegative. The runner requires
  `distance_upper=max(abs(lower(difference_interval)),
  abs(upper(difference_interval)))`, certifies by exact squaring that
  `scale_lower^2` does not exceed the interval's lower endpoint, and requires
  `normalized_upper=distance_upper/scale_lower` as a reduced exact rational.
  `ideal_normalized` binds the same distance upper over the exact square root
  of the scale-squared lower endpoint and is ordered by the exact squaring
  rule above; the conservative rational `normalized_upper`, not the ideal
  value or an MPFR midpoint, owns PASS and maximum selection.
- `geometry_axis_v1` = `{kind:"geometry_axis_v1",axis:"x"|"y"|"z",
  view:"exact_effective"|"emitted_binary64",observed:signed_dyadic_v1|
  rational_v1|binary64_scalar_v1,reference_interval:interval_rational_v1,
  normalized_bound:normalized_interval_bound_v1}`. The result-key view fixes
  the observed alternative; the independently generated reference interval
  and exact difference operands are runner-owned.
- `integrand_exact_interval_v1` = `{kind:"integrand_exact_interval_v1",
  view:"exact_effective", observed_interval:interval_rational_v1,
  analytic_interval:interval_rational_v1,
  absolute_error_upper:absolute_rational_v1}`.
- `integrand_emitted_interval_v1` = `{kind:
  "integrand_emitted_interval_v1",view:"emitted_binary64",
  observed_bits:16hex,analytic_interval:interval_rational_v1,
  absolute_error_upper:absolute_rational_v1}`.
- `emitted_interval_scalar_v1` = `{kind:"emitted_interval_scalar_v1",
  observed_bits:16hex,analytic_interval:interval_rational_v1,
  absolute_error_upper:absolute_rational_v1}`; its bound is derived by the
  same exact emitted-versus-interval endpoint rule as the integrand form.
- `coefficient_vector_comparison_v1` = `{kind:
  "coefficient_vector_comparison_v1",source_ids:[signed integers],
  observed:[signed_dyadic_v1],expected:[signed_dyadic_v1],
  absolute_errors:[absolute_dyadic_v1],l1:absolute_dyadic_v1}`. All four
  arrays have the same positive length, source IDs are strictly increasing,
  and every dyadic uses denominator power 1074.
- `coefficient_interval_vector_v1` = `{kind:
  "coefficient_interval_vector_v1",source_union_ids:[signed integers],
  observed:[signed_dyadic_v1],analytic_intervals:[interval_rational_v1],
  absolute_error_uppers:[absolute_rational_v1],
  maximum_error_upper:absolute_rational_v1,
  first_maximum_source_id:signed integer}`. All four arrays have the same
  positive length in strictly increasing source-ID order, and
  `first_maximum_source_id` is the first source attaining the exact maximum.
- `row_signature_pair_v1` = `{kind:"row_signature_pair_v1",
  source_count:uint64,cache_disabled_sha256:sha256,
  serial_cache_sha256:sha256}`. Each digest is over the complete canonical
  RFC 8785 array of `[source_id,provider_coefficient_bits,
  exact_effective_signed_dyadic]` records in strictly increasing source-ID
  order for the result key's row and anchor; `source_count` equals its length.

Targets are closed objects, never bare mutable numbers:

- `null` for categorical/coverage records;
- `{kind:"exact_zero_l1_target_v1",numerator:"0",denominator:"1"}` for
  exact coefficient-vector equality;
- `{kind:"absolute_rational_target_v1", numerator:"1",
  denominator:"200000"}` for `5.0e-6`;
- the same form with denominator `2000000`, `400000`, or `80000` for
  `5.0e-7`, `2.5e-6`, or `1.25e-5` respectively;
- denominator `40000` or `8000` for `2.5e-5` or `1.25e-4` respectively;
- the exact D12 integer-target forms frozen below.

For every numeric maximum, the validator rescans the complete result sidecar
and compares the manifest-named exact measure, never displayed JSON numbers.
It converts the winning exact value to `maximum_binary64_bits` using correctly
rounded IEEE-754 binary64 round-to-nearest, ties-to-even. Exact rational and
dyadic values are converted by integer quotient/remainder with ties-to-even.

For a nonnegative `rational_over_sqrt_v1` value `q/sqrt(s)`, target comparison
is decided without floating point: `q/sqrt(s) <= t` exactly when
`q^2 <= t^2*s`, after expanding all three rationals to positive integers and
cross-multiplying. Two such values are ordered by comparing `q1^2*s2` with
`q2^2*s1`, again by exact integer cross-products. MPFR 4.2.2 at 544 bits may
only enclose the already selected winner under directed rounding until both
bounds round to the same display binary64; it may not choose PASS, FAIL, or
the maximum. Failure to certify display rounding, nonfinite output, or
negative zero is infrastructure `INCOMPLETE`; exact zero serializes as
positive-zero bits `0000000000000000`.

For integrand intervals `O=[o_lo,o_hi]` and `A=[a_lo,a_hi]`, the exact error
upper bound is `max(|o_lo-a_hi|,|o_hi-a_lo|)`. For an emitted finite binary64
value `b` imported as its exact dyadic, it is
`max(|b-a_lo|,|b-a_hi|)`. The runner derives and reduces that rational itself,
requires exact equality with `absolute_error_upper`, compares that bound to
`1/200000`, and uses the bound for maximum selection. Interval overlap, a
midpoint, or a displayed binary64 value cannot replace this gate.

## Normative 32-criterion encoding manifest

The table is the authority for ordinal, count, expectation constant, runner-
constructed result exact-value schema, target, allowed complete-result
outcome, non-PASS reason, and maximum measure. `row_D10` selects exactly
`1/200000`, `1/40000`, or `1/8000` by the six-row order. `row_component`
selects exactly `1/2000000`, `1/400000`, or `1/80000`. `numeric:<field>` means
the maximum is selected by exact comparison of that named field; `none` means
maximum/witness are null. The executable schema may only spell out this table,
not reinterpret it.

| Ord | Criterion ID | Count | Exact expectation constant | Exact-value schema | Target | Complete outcome / non-PASS reason | Maximum |
| ---: | --- | ---: | --- | --- | --- | --- | --- |
| 00 | `bindings_and_independence` | 1 | `exact_head_provenance_and_oracle_independence` | `binding_value_v1` | null | `PASS|INCOMPLETE` / `BINDING_UNAVAILABLE|BINDING_MISMATCH|WORKTREE_DIRTY|DEPENDENCY_PROVENANCE_MISMATCH|INDEPENDENCE_AUDIT_INCOMPLETE` | none |
| 01 | `complete_artifact_inventory` | 294 | `exact_schema2_artifact_inventory_no_unexpected_paths` | `artifact_value_v1` | `artifact_slot_target_v1` plus `unexpected_paths_target_v1` empty sidecar | `PASS|INCOMPLETE` / `ARTIFACT_MISSING|ARTIFACT_HASH_MISMATCH|ARTIFACT_CONTENT_MISMATCH|ARTIFACT_IDENTITY_MISMATCH|UNEXPECTED_ARTIFACT_PATH` | none |
| 02 | `raw_bfr_d9a_reproduction` | 196 | `exact_B2_raw_D9a_reproduction_124_cases` | `raw_d9a_value_v1` | exact approved B2 per-case value | `PASS|INCOMPLETE` / `RAW_D9A_REPRODUCTION_MISMATCH` | numeric:`maximum_row_sum_residual` |
| 03 | `representation_structure` | 4,158,000 | `exact_anchor_derivation_vector_binding_sum_one_position_zero_derivatives` | `structure_present_v1|structure_missing_anchor_v1` | null | `PASS|FAIL` / `ANCHOR_SOURCE_MISSING|REPRESENTATION_STRUCTURE_MISMATCH` | none |
| 04 | `constant_field_bits` | 62,370,000 | `five_challenges_exact_position_identity_zero_derivatives` | `binary64_pair_v1` | null | `PASS|FAIL` / `CONSTANT_FIELD_BITS_MISMATCH` | none |
| 05 | `relabel_exact_effective_coefficients` | 8,316,000 | `exact_inverse_relabel_coefficient_vector_identity` | `coefficient_vector_comparison_v1` | `exact_zero_l1_target_v1` | `PASS|FAIL` / `RELABEL_EXACT_MISMATCH` | none |
| 06 | `regular_analytic_exact_rows` | 152,640 | `regular_box_spline_exact_source_union_row` | `coefficient_interval_vector_v1` | `1/200000` | `PASS|FAIL` / `REGULAR_ANALYTIC_TARGET_EXCEEDED` | numeric:`maximum_error_upper` |
| 07 | `regular_analytic_emitted_geometry` | 457,920 | `regular_box_spline_emitted_axis` | `emitted_interval_scalar_v1` | `1/200000` | `PASS|FAIL` / `REGULAR_ANALYTIC_TARGET_EXCEEDED` | numeric:`absolute_error_upper` |
| 08 | `regular_analytic_area_integrand` | 50,880 | `regular_area_integrand_exact_and_emitted` | view-dependent `integrand_exact_interval_v1|integrand_emitted_interval_v1` | `1/200000` | `PASS|FAIL` / `REGULAR_INTEGRAND_TARGET_EXCEEDED` | numeric:`absolute_error_upper` |
| 09 | `regular_analytic_legacy_volume_integrand` | 50,880 | `regular_legacy_volume_integrand_exact_and_emitted` | view-dependent `integrand_exact_interval_v1|integrand_emitted_interval_v1` | `1/200000` | `PASS|FAIL` / `REGULAR_INTEGRAND_TARGET_EXCEEDED` | numeric:`absolute_error_upper` |
| 10 | `oracle_coverage_and_crosscheck` | 1,188,000 | `primary_Stam_plus_uniform_coverage` | outcome-dependent: `PASS` uses `oracle_covered_value_v1`; `UNCOVERED` uses null; infrastructure `INCOMPLETE` has no complete result ledger | null | complete ledger: `PASS|UNCOVERED` / `d10_oracle_reason_v1`; absent or partial ledger: `INCOMPLETE` / `oracle_infrastructure_reason_v1` | none |
| 11 | `exact_effective_d10_coeff` | 1,188,000 | `covered_primary_oracle_coefficient_l1` | outcome-dependent: covered `PASS|FAIL` uses `oracle_coefficient_l1_v1`; propagated `UNCOVERED` uses null | `row_D10` | `PASS|FAIL|UNCOVERED` / `D10_COEFFICIENT_TARGET_EXCEEDED|d10_oracle_reason_v1` | numeric:`l1` for `PASS|FAIL`; null for `UNCOVERED` |
| 12 | `exact_effective_d10_geometry` | 3,564,000 | `covered_primary_oracle_exact_geometry_axis` | outcome-dependent: covered `PASS|FAIL` uses `geometry_axis_v1`; propagated `UNCOVERED` uses null | `row_D10` | `PASS|FAIL|UNCOVERED` / `D10_GEOMETRY_TARGET_EXCEEDED|d10_oracle_reason_v1` | numeric:`normalized_bound.normalized_upper` for `PASS|FAIL`; null for `UNCOVERED` |
| 13 | `emitted_direct_geometry_d10` | 3,564,000 | `covered_primary_oracle_emitted_geometry_axis` | outcome-dependent: covered `PASS|FAIL` uses `geometry_axis_v1`; propagated `UNCOVERED` uses null | `row_D10` | `PASS|FAIL|UNCOVERED` / `D10_EMITTED_GEOMETRY_TARGET_EXCEEDED|d10_oracle_reason_v1` | numeric:`normalized_bound.normalized_upper` for `PASS|FAIL`; null for `UNCOVERED` |
| 14 | `anchor_sensitivity_exact_coeff` | 1,188,000 | `all_three_anchor_pairs_exact_coefficient_l1` | `exact_coefficient_l1_v1` | `row_component` | `PASS|FAIL` / `ANCHOR_SENSITIVITY_TARGET_EXCEEDED` | numeric:`l1` |
| 15 | `anchor_sensitivity_exact_geometry` | 3,564,000 | `all_three_anchor_pairs_exact_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `ANCHOR_SENSITIVITY_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 16 | `anchor_sensitivity_emitted_geometry` | 3,564,000 | `all_three_anchor_pairs_emitted_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `ANCHOR_SENSITIVITY_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 17 | `binary64_basis_probe_diagnostic` | 32,271,264 | `exact_group_l1_all_anchors_all_relabels` | `basis_value_v1` | `row_component` | `PASS|FAIL` / `BASIS_GROUP_L1_TARGET_EXCEEDED` | numeric:`group_l1` |
| 18 | `binary64_direct_geometry_fidelity` | 10,692,000 | `emitted_vs_exact_direct_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `BINARY64_FIDELITY_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 19 | `relabel_emitted_geometry_fidelity` | 7,128,000 | `inverse_relabel_emitted_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `RELABEL_FIDELITY_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 20 | `stabilization_6_7_exact_coeff` | 594,000 | `level_6_to_7_exact_coefficient_l1` | `exact_coefficient_l1_v1` | `row_component` | `PASS|FAIL` / `STABILIZATION_TARGET_EXCEEDED` | numeric:`l1` |
| 21 | `stabilization_6_7_exact_geometry` | 1,782,000 | `level_6_to_7_exact_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `STABILIZATION_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 22 | `stabilization_6_7_emitted_geometry` | 1,782,000 | `level_6_to_7_emitted_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `STABILIZATION_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 23 | `stabilization_7_8_exact_coeff` | 594,000 | `level_7_to_8_exact_coefficient_l1` | `exact_coefficient_l1_v1` | `row_component` | `PASS|FAIL` / `STABILIZATION_TARGET_EXCEEDED` | numeric:`l1` |
| 24 | `stabilization_7_8_exact_geometry` | 1,782,000 | `level_7_to_8_exact_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `STABILIZATION_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 25 | `stabilization_7_8_emitted_geometry` | 1,782,000 | `level_7_to_8_emitted_geometry_axis` | `geometry_axis_v1` | `row_component` | `PASS|FAIL` / `STABILIZATION_TARGET_EXCEEDED` | numeric:`normalized_bound.normalized_upper` |
| 26 | `cache_mode_bit_identity` | 2,079,000 | `complete_cache_disabled_equals_serial_cache_row_signature` | `row_signature_pair_v1` | null | `PASS|FAIL` / `CACHE_MODE_BITS_MISMATCH` | none |
| 27 | `d12_preparation_cost` | 3,136 | `unchanged_D12_total_representation_preparation` | `d12_duration_value_v1` | `d12_duration_target_v1` | `PASS|FAIL|INCOMPLETE` / `PREPARATION_MEDIAN_BUDGET_EXCEEDED|PREPARATION_SINGLE_RUN_BUDGET_EXCEEDED|PREPARATION_MEASUREMENT_NONFINITE_OR_NEGATIVE|PREPARATION_PROCESS_FAILURE|D12_PLATFORM_UNQUALIFIED|D12_PROVENANCE_INVALID|D12_OPERATIONAL_LEDGER_INCOMPLETE` | numeric-if-present:`duration_ns` |
| 28 | `d12_retained_payload` | 5,964 | `unchanged_D12_retained_representation_payload` | `d12_payload_value_v1` | `d12_payload_target_v1` | `PASS|FAIL|INCOMPLETE` / `RETAINED_PAYLOAD_BUDGET_EXCEEDED|RETAINED_PAYLOAD_INVALID|D12_PLATFORM_UNQUALIFIED|D12_PROVENANCE_INVALID|D12_OPERATIONAL_LEDGER_INCOMPLETE` | numeric-if-present:`payload_bytes` |
| 29 | `d12_peak_rss` | 4,179,364 | `unchanged_D12_representation_peak_RSS` | `d12_rss_value_v1` | `d12_rss_target_v1` | `PASS|FAIL|INCOMPLETE` / `PEAK_RSS_BUDGET_EXCEEDED|RSS_SAMPLE_MISSING_OR_API_FAILURE|D12_PLATFORM_UNQUALIFIED|D12_PROVENANCE_INVALID|D12_OPERATIONAL_LEDGER_INCOMPLETE` | numeric-if-present:`rss_delta_bytes` |
| 30 | `d12_cache_disabled_concurrency` | 13,720 | `cache_disabled_representation_output_reference_identity` | state-dependent `d12_concurrency_value_v1|d12_concurrency_abort_v1` | `d12_output_reference_target_v1` | `PASS|FAIL|INCOMPLETE` / `CACHE_DISABLED_CONCURRENCY_MISMATCH|CACHE_DISABLED_RACE|D12_REPRESENTATION_WORKLOAD_MISMATCH|D12_PLATFORM_UNQUALIFIED|D12_PROVENANCE_INVALID|D12_OPERATIONAL_LEDGER_INCOMPLETE` | none |
| 31 | `d12_instrumented_tsan` | 14,896 | `instrumented_provider_and_representation_TSan` | quantity-dependent `d12_tsan_instrumentation_summary_v1|d12_tsan_finding_summary_v1|d12_tsan_threaded_row_value_v1|null-after-abort` | quantity-dependent `d12_tsan_instrumentation_target_v1|d12_tsan_finding_target_v1|d12_output_reference_target_v1` | `PASS|FAIL|INCOMPLETE` / `CACHE_DISABLED_RACE|THREADED_CACHE_RACE|THREADED_CACHE_OUTPUT_MISMATCH|D12_REPRESENTATION_WORKLOAD_MISMATCH|D12_PLATFORM_UNQUALIFIED|D12_PROVENANCE_INVALID|D12_OPERATIONAL_LEDGER_INCOMPLETE` | none |

The named reason types in the table are literal enums, not extension points:

```text
d10_oracle_reason_v1 =
  ORACLE_INDEPENDENCE_AUDIT_FAILED |
  MPFR_4_2_2_UNAVAILABLE | MPFR_VERSION_MISMATCH |
  DIRECTED_INTERVAL_PRIMITIVE_FAILED |
  INTERVAL_BRANCH_ORDERING_UNCERTIFIED | NO_ISOLATION_BY_DEPTH_12 |
  EIGENBASIS_CERTIFICATION_FAILED | PARAMETRIC_MAP_CHECK_FAILED |
  REGULAR_SUPPORT_NOT_REACHED_BY_DEPTH_30 | UNIFORM_CROSSCHECK_FAILED |
  TANGENT_PROJECTION_CHECK_FAILED | EMPTY_INTERVAL_INTERSECTION |
  ORACLE_MIDPOINT_NONFINITE | ORACLE_MIDPOINT_BINARY64_IMPORT_INEXACT |
  NORMALIZATION_LENGTH_NONPOSITIVE | ORACLE_UNCERTAINTY_BOUND_EXCEEDED |
  ORACLE_SERIALIZATION_BOUND_EXCEEDED

oracle_infrastructure_reason_v1 =
  ORACLE_REQUEST_LEDGER_UNAVAILABLE | ORACLE_REQUEST_LEDGER_INVALID |
  ORACLE_EXECUTION_UNAVAILABLE | ORACLE_RESULT_LEDGER_INCOMPLETE |
  ORACLE_RESULT_LEDGER_INVALID
```

`artifact_slot_target_v1` is the closed corresponding schema-2 expected slot
with exactly `kind`, `expected_slot_ordinal`, `content_id`, `candidate`,
`level`, `cache_mode`, `compressed_sha256`, `decompressed_json_sha256`, and
`canonical_b2rowv1_sha256`. `unexpected_paths_target_v1` has exactly `kind`,
the complete `d12_sidecar_descriptor`-shaped `sidecar`, and
`required_record_count:0`; its bytes are the canonical empty array. The
raw-D9a target is the exact closed
`raw_d9a_value_v1` loaded from the approved B2 checkpoint, not a numeric
placeholder. Every table spelling `row_D10` or `row_component` expands to the
literal denominator selected by the frozen six-row order as defined above.
The candidate-scientific reason set for a row is its literal table reason plus
`CANDIDATE_NONFINITE`; no generic or implementation-defined reason is legal.

`structure_present_v1` is the closed object `{kind:
"structure_present_v1",anchor_id:"v0"|"v1"|"v2",anchor_present:true,
canonical_source_ids:[signed integers],provider_coefficient_bits:[16hex],
provider_row_sha256:sha256,effective_coefficients:[signed_dyadic_v1],
observed_sum:signed_dyadic_v1,expected_sum:signed_dyadic_v1,
source_count:uint64}`. The three arrays have the same positive length,
`canonical_source_ids` is strictly increasing, `source_count` equals that
length, and every dyadic has denominator power 1074. `provider_row_sha256`
binds the complete validated canonical `B2ROWV1` source row. The runner
reimports every paired provider bit exactly, independently derives the anchor
source ID from the oriented face and key's `anchor_id`, constructs the full
effective vector, and requires exact member-by-member equality with
`effective_coefficients`.

`structure_missing_anchor_v1` is the closed object `{kind:
"structure_missing_anchor_v1",anchor_id:"v0"|"v1"|"v2",
anchor_present:false,canonical_source_ids:[signed integers],
provider_coefficient_bits:[16hex],provider_row_sha256:sha256,
missing_anchor_source_id:signed integer,effective_coefficients:null,
observed_sum:null,expected_sum:signed_dyadic_v1,source_count:uint64}`. The two
arrays and source count obey the same complete-row rules; the missing source
ID is the independently face-derived anchor and is absent from the canonical
source array. This variant always has record outcome `FAIL` and reason
`ANCHOR_SOURCE_MISSING`.

For the present variant, `expected_sum` is exactly one for key quantity
`position` and exactly zero for `du`, `dv`, `duu`, `duv`, or `dvv`;
`observed_sum` is independently summed over the complete exact effective
vector. It is `PASS` only when the anchor/vector binding and sum are exact.
No other quantity, discriminator, denominator, member, source count, or
partial vector is valid.

For criterion 10 the exact-value form is determined by the record outcome,
not chosen independently. A `PASS` record has the following closed
`oracle_covered_value_v1`; an `UNCOVERED` record has JSON null; no result
record exists for an absent or partial infrastructure-`INCOMPLETE` ledger.

```text
oracle_covered_value_v1:
  kind                         exact string "oracle_covered_value_v1"
  coverage                     exact string "COVERED"
  row_kind                     position | du | dv | duu | duv | dvv
  source_ids                   nonempty array of strictly increasing signed integers
  primary_depth_intervals      source-ordered array of five-interval arrays
  uniform_depth_intervals      source-ordered array of five-interval arrays
  intersected_primary_intervals array of interval_rational_v1
  first_isolating_depth        integer 0..12
  first_regular_support_depth  integer 0..26
  evaluated_depths             array of exactly five integers
  child_branches               array of T0 | T1 | T2 | Tc with length first_regular_support_depth
  certification               oracle_certification_v1

oracle_certification_v1:
  kind                         exact string "oracle_certification_v1"
  eigenbasis                   exact string "CERTIFIED"
  parametric_map               exact string "CERTIFIED"
  regular_support              exact string "CERTIFIED"
  interval_intersection        exact string "CERTIFIED"
  uniform_source_overlap       exact string "CERTIFIED"
  vertex_limit                 exact string "CERTIFIED"
  tangent_projection           exact string "CERTIFIED"
  uncertainty_bound            exact string "CERTIFIED"
  midpoint_serialization       exact string "CERTIFIED"
```

Both objects reject additional members. The three outer coefficient arrays
have exactly `source_ids.length` members in the same source-ID order; each
depth-array member has exactly five `interval_rational_v1` values aligned with
`evaluated_depths`. Each `intersected_primary_intervals[i]` is the nonempty
intersection of `primary_depth_intervals[i]`; every primary interval overlaps
the corresponding `uniform_depth_intervals` value for that source and depth.
The two depth members are independent observations. `first_isolating_depth`
is the first successful depth in the frozen isolation search `0..12`.
`first_regular_support_depth` is the plan's `d0`: the first depth at which the
selected triangle has the complete regular 12-control box-spline support. No
equality between them is assumed. `evaluated_depths` is exactly
`[d0,d0+1,d0+2,d0+3,d0+4]`, where
`d0 == first_regular_support_depth` and `d0+4 <= 30`. `child_branches` is the
exact frozen selected-child branch sequence to the regular-support `d0`; its
length is `d0`, including the unique empty array when `d0 == 0`. `row_kind`
equals the result key's quantity. The runner
recomputes the certification fields from the full primary and independent
uniform records; literal `CERTIFIED` strings cannot substitute for those
checks.

Every criterion-10 `UNCOVERED` record therefore has exactly
`[key,"UNCOVERED",null,null,reason]`, where `reason` is one frozen D10 oracle
reason. If non-oracle infrastructure prevents construction of the request or
a complete coverage partition, criterion 10 is `INCOMPLETE`, its result
sidecar and both result commitments are null, and its observed count records
only the honestly constructed partial count; partial result bytes cannot be
published as a complete ledger. A complete 1,188,000-record ledger cannot use
record outcome `INCOMPLETE`.

Any nonfinite candidate value uses criterion `FAIL` reason
`CANDIDATE_NONFINITE`; inability of the validator to construct or certify one
of the exact descriptors is infrastructure `INCOMPLETE` and causes later
candidate criteria to be omitted. No criterion may use an unlisted reason.

## Merkle commitment and witness membership

The result Merkle tree is defined over the same ordered canonical records. Let
`N` be the record count. Let `P=1` when `N=0`; otherwise `P` is the smallest
power of two greater than or equal to `N`. `N` and every byte length must fit
an unsigned 64-bit integer. For record index `i`, let `R_i` be its RFC 8785
bytes and use unsigned 64-bit big-endian integers:

```text
leaf(i)  = SHA256(0x00 || uint64(i) || uint64(len(R_i)) || R_i)
empty(i) = SHA256(0x02 || uint64(i))
node     = SHA256(0x01 || left_digest || right_digest)
```

The leaf layer contains `leaf(i)` for `0 <= i < N` and `empty(i)` for
`N <= i < P`. A zero-record ledger has the single root `empty(0)`. In `node`,
`left_digest` and `right_digest` are the raw 32 digest bytes, not hexadecimal
text. Internal nodes are built pairwise left-to-right until one root remains;
that root is `result_merkle_root_sha256`.

Every executed numeric criterion with at least one valid numeric record has
exactly one maximum witness with this closed shape; only the explicitly frozen
all-invalid D12 case may have a complete numeric-criterion ledger with null
maximum and witness:

```text
cell_key                 canonical applicability key
result_record            exact five-field canonical result record
leaf_index               nonnegative integer less than observed count
merkle_siblings          ordered array of 64-lowercase-hex sibling digests
maximum_exact            criterion-specific exact descriptor
maximum_binary64_bits    16 lowercase hex
```

`merkle_siblings` is ordered bottom-up, leaf level first, and contains exactly
`log2(P)` hexadecimal digests. At level `k`, bit `k` of `leaf_index` selects
direction: zero hashes `current` as the left child and sibling as right; one
hashes sibling as left and `current` as right. The validator rejects a short,
extra, wrong-direction, malformed, or padding-index proof. `leaf_index` must be
the record's actual canonical ledger ordinal, not merely an in-range integer.

The validator requires `result_record[0] == cell_key`, recomputes the leaf and
root from the proof, verifies the root equals the criterion commitment,
validates the key against the frozen corpus and criterion dimensions, and
validates `maximum_exact` field-by-field. It then rescans the complete sidecar,
recomputes the criterion-defined exact measure for every record, selects the
first canonical maximum tie, and requires that exact record, ordinal, proof,
and descriptor to be the reported witness. It independently recomputes
`first_failing_key` as the first record whose outcome is `FAIL`. Categorical
and unexecuted criteria have null maximum and witness. Raw D9a is explicitly a
numeric infrastructure criterion and therefore has a maximum witness even
though its expected raw invariant states include failures.

## Infrastructure result keys

The three required infrastructure criteria may not hash summary strings.
Their result keys are closed arrays:

```text
["bindings_and_independence", "exact_head_and_provenance"]
["complete_artifact_inventory", content_id, candidate, level, cache_mode]
["raw_bfr_d9a_reproduction", content_id, level, cache_mode]
```

`bindings_and_independence` has exactly one record. Its exact value binds the
actual start/end Git commits, start/end clean-worktree observations, validator,
row-provider, representation-candidate, exact-boundary and independent-oracle
availability/hashes, dependency identities, and independence-audit state.

Its value is the closed `binding_value_v1` object with exactly these members:
`kind`, `git_start`, `git_end`, `worktree_start_clean`,
`worktree_end_clean`, `validator_sha256`, `row_provider_availability`,
`row_provider_sha256`, `representation_availability`,
`representation_sha256`, `exact_boundary_availability`,
`exact_boundary_sha256`, `independent_oracle_availability`,
`independent_oracle_sha256`, `oracle_independence_audit`,
`manifest_file_sha256`, `manifest_contract_sha256`, `gmp_identity`,
`mpfr_identity`, `opensubdiv_identity`, and `provenance_complete`. Hashes are
SHA-256 or null according to their paired standard availability enum; Git
members are 40 lowercase hex; the dependency identities are exactly
`gmp-6.3.0`, `mpfr-4.2.2`, and `opensubdiv-3.7.0`. Target is null. Outcome is
`PASS` only when every required binding is present/valid and the independence
audit is `PASS`; otherwise it is `INCOMPLETE` with exactly one of
`BINDING_UNAVAILABLE`, `BINDING_MISMATCH`, `WORKTREE_DIRTY`,
`DEPENDENCY_PROVENANCE_MISMATCH`, or `INDEPENDENCE_AUDIT_INCOMPLETE`.

`complete_artifact_inventory` selects its 294 slots in frozen manifest order
but, like every result ledger, serializes records in canonical JCS-key order.
Its closed `artifact_value_v1` has exactly `kind`, `expected_slot_ordinal`,
`relative_path`, `availability`, `compressed_sha256`,
`decompressed_json_sha256`, `canonical_b2rowv1_sha256`, and
`expected_identity_matches`; target is the corresponding closed expected-slot
object from the schema-2 manifest. Outcome is `PASS` on exact equality or
`INCOMPLETE` with `ARTIFACT_MISSING`, `ARTIFACT_HASH_MISMATCH`,
`ARTIFACT_CONTENT_MISMATCH`, or `ARTIFACT_IDENTITY_MISMATCH`.

Unexpected paths are bound by a separate required sidecar named
`anchored-row-result-ledgers-v1/unexpected-artifact-paths.json`. It is the
canonical JCS-sorted array of `[relative_path,availability,sha256]` records and
must be the canonical empty array for a passing inventory. Its availability,
byte length, SHA-256, and empty/nonempty count are bound inside the
`complete_artifact_inventory` criterion's target object. Any nonempty list
makes that criterion `INCOMPLETE/UNEXPECTED_ARTIFACT_PATH`; absence cannot be
asserted independently by each expected-slot record.

`raw_bfr_d9a_reproduction` has exactly 196 Bfr records. Its closed
`raw_d9a_value_v1` has exactly `kind`, `case_identity`, `raw_invariant_state`
(`PASS|FAIL`), `maximum_row_sum_residual` (`absolute_dyadic_v1`),
`failing_row_count`, and `canonical_raw_rows_sha256`. Target is the same closed
shape loaded from the exact approved B2 checkpoint. A case whose frozen raw
invariant state is `FAIL` nevertheless has result outcome `PASS` when all raw
fields reproduce; only a mismatch is criterion `INCOMPLETE` with
`RAW_D9A_REPRODUCTION_MISMATCH`. The 196 outcomes must derive exactly 124 raw
`FAIL` states. The frozen global maximum is binary64 bits
`3db6653ab1800000` and exact numerator
`5994eac6000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000`
over `2^1074`. Raw D9a is numeric: its witness must prove the first canonical
case attaining that exact maximum. The failing count and maximum may not appear
only in an expectation string or aggregate summary. The literal mutation
suite must decode `3db6653ab1800000` to its exact binary64 integer ratio and
prove it equals `(0x5994eac6 << 1008) / 2^1074`; deleting or adding even one
trailing zero, or changing either literal independently, must fail.

## Oracle result ownership

The oracle request remains exactly 1,188,000 frozen keys. If the primary
Stam/uniform executable is absent, cannot start, or cannot produce a complete
partition, criterion 10 is infrastructure
`INCOMPLETE/ORACLE_EXECUTION_UNAVAILABLE` or
`INCOMPLETE/ORACLE_RESULT_LEDGER_INCOMPLETE` as applicable; its result sidecar
and both commitments are null. No per-cell certification result is invented.

Only after the independent oracle executable actually processes every request
key may `COVERED` be a present empty key ledger and `UNCOVERED` a present full
key ledger identical to the request. If that execution attempts and fails the
frozen eigenbasis certification for every key, the criterion result ledger has
exactly 1,188,000 `UNCOVERED` records with reason
`EIGENBASIS_CERTIFICATION_FAILED`; each has `exact_value=null` and
`target=null`. The empty covered partition is present, not absent. No
uniform-only, candidate, absent-executable, or infrastructure observation may
be relabeled as primary-oracle coverage.

### Oracle-dependent UNCOVERED propagation

Criteria 11--13 consume criterion 10's coverage decision; they cannot invent
coverage or a candidate comparison. For each criterion-10 `UNCOVERED` key,
criterion 11 contains exactly one propagated record and criteria 12 and 13
contain exactly the three `x`, `y`, and `z` propagated records. Each has
`outcome="UNCOVERED"`, `exact_value=null`, the unchanged row-D10 target, and
the identical frozen oracle reason. Its key differs from the oracle key only
in the criterion-owned view and, for criteria 12 and 13, axis. The base
content, cache mode, level, face, local corner, sample, row kind, anchor, and
identity relabel are byte-identical. The validator streams a bounded-memory
canonical digest of `[oracle_request_key,reason]` for criterion 10 and for
each dependent criterion, collapses each complete ordered `x,y,z` group once,
and requires exact count and digest equality. It also derives the criterion-10
`PASS` and `UNCOVERED` key streams from the persisted result sidecar and
requires their counts and RFC 8785 key-ledger digests to equal the matrix
`covered` and `uncovered` partitions; matrix labels cannot override outcomes.

Covered cells retain their candidate-owned `PASS|FAIL` comparison. Within
each of criteria 11--13, any covered-cell `FAIL` has precedence; otherwise any
propagated cell makes the criterion `UNCOVERED`; only an all-covered,
all-passing ledger is `PASS`. An aggregate `UNCOVERED` has null maximum and
witness even if some covered cells pass. A propagated cell contributes no
candidate PASS or FAIL. Criteria 14--26 remain independently executable; an
oracle `UNCOVERED` is not an infrastructure omission blocker. The overall
verdict remains `INCOMPLETE` unless another candidate criterion establishes
`FAIL`.

## Binary64 basis diagnostic ownership

`binary64_basis_probe_diagnostic` owns exactly 32,271,264 source-contribution
records: every applicable row at levels 7 and 8, both cache modes, all three
anchors, identity, rank reversal, rank rotation, and every source in the row
support. For a relabeled group, source IDs and the anchor are mapped into the
frozen relabeled rank order, evaluation occurs in that order, and every emitted
result is inverse-mapped to its canonical source ID before comparison. For one
row/anchor/relabel group, the runner computes exactly

```text
source_error_j = |emitted_basis_j - exact_effective_coefficient_j|
group_l1       = sum_j source_error_j
```

over the common `2^1074` denominator. The closed `basis_value_v1` contains
exactly `kind`, `emitted_basis_bits`, `exact_effective` (`signed_dyadic_v1`),
`source_error` (`absolute_dyadic_v1`), and `group_l1`
(`absolute_dyadic_v1`). The separate canonical `target` field is the unchanged
row-order `0.1 x D10` target; it is not duplicated inside `exact_value`. The
one group decision is repeated on its source-contribution records so
individually small source errors cannot hide an aggregate failure. Maximum
selection compares exact `group_l1`; ties use the first canonical contributing
key.

The 32,271,264 count is mechanically derived from the frozen checkpoint's
10,757,088 identity-relabel source contributions multiplied by the three
pre-existing frozen relabels. It is a pre-result applicability cardinality,
not an observed numerical result or fitted target.

## Closed B2c D12 representation-work envelope

An old B2 D12 document plus a boolean is never B2c evidence. A present B2c D12
artifact must be the RFC 8785 canonical bytes of one closed
`anchored_row_representation_d12` object. Its `content_sha256` is computed over
the entire object with only that member replaced by 64 zeroes. The exact root
members and no others are:

| Member | Closed contents |
| --- | --- |
| `schema_id` | exact string `anchored-row-representation-d12-v1` |
| `content_sha256` | self-zeroed canonical content digest |
| `candidate` | exact string `anchored_difference_rows_v1` |
| `git` | `head`, `head_query_ok`, `worktree_clean`; exact reviewed 40-hex head, both booleans true |
| `binaries` | `provider_release`, `provider_tsan`, `representation_release`, `representation_tsan`; each has availability, SHA-256, compiler-command SHA-256, link-map SHA-256, dynamic-dependency SHA-256, and a canonical source inventory of `[relative_path,sha256]` |
| `dependencies` | closed GMP, MPFR, OpenSubdiv records; each binds exact version, archive SHA-256, source identity, build-root provenance SHA-256, install provenance SHA-256, link provenance SHA-256, and installed library SHA-256; identities are exactly `6.3.0`, `4.2.2`, and `3.7.0` |
| `build_profiles` | exact Release and TSan compiler paths/versions/flags, SDK path/version, CMake path/version, Make path/version, and proof compile/link command arrays; Release includes the frozen strict flags and TSan includes `-fsanitize=thread` in both compile and link |
| `platform` | `platform_state`, exact expected fingerprint, exact observed fingerprint, field-by-field mismatches, compiler identity, `github_hosted`, virtualization observation, and canonical process-boundary power/thermal observations; the expected fingerprint and every observation field are those already frozen by D12 |
| `authority` | manifest file/contract hashes, exact six rows, tolerance, D10/component targets, D12 budgets/cardinalities, sample policy, fixture inventory, and representation workload ID; every value equals the approved authority |
| `workload` | closed representation construction/evaluation protocol below; complete provider and representation serial-reference/worker sidecar descriptor arrays, exact `process_observation_sidecar`, the eight exact input IDs, and `construction_and_evaluation_included:true` |
| `criteria` | exactly the five ordered D12 criterion records with the table's IDs/counts/value/target/outcome rules and this amendment's sidecar descriptors, result hashes, Merkle roots, maxima, witnesses, and first failures |
| `serial_only_context` | closed complete-tuple object below |

Every nested object has `additionalProperties:false`; all arrays have exact
item schemas and canonical order. Missing provenance is explicit availability
and makes the artifact incomplete. The artifact bytes, content hash, exact
head, actual observed fingerprint, and all nested binary/source/dependency
bindings are independently validated before any D12 result is consumed.

The frozen representation workload ID is
`anchored-difference-v1-d12-workload-v1`. Within every existing D12 preparation
process/repetition, the clock starts before refiner/provider preparation and
ends only after completed package validation, which follows publication. For
every canonical face/sample six-row
group, the provider rows are validated, the oriented `v0` anchored
representation derives its anchor source from the oriented face without
retaining an anchor ID or a new coefficient row, and all
six rows are evaluated in frozen source order on exactly eight inputs: fixture
coordinate axes `x`,`y`,`z` followed by constant challenges `0`,`1`,`-1`,
`2^20`,`-2^20`. All arithmetic uses the already frozen binary64 evaluator
order. No other anchor, input, repeat, or favorable subset is timed.

This workload adds no D12 key or changes a cardinality. The existing RSS stages
map exactly as follows: `pre_refiner_baseline` is before all work;
`after_refiner` is after refiner construction; `after_factory_cache` is after
cache creation; each `after_face_insert` sample is taken only after that
face/sample's provider rows, anchored representation, and eight-input
evaluation complete; `after_package_publication` is after the completed
immutable package. The existing **three** destruction stages remain in their
already frozen order and are, exactly,
`after_package_destruction`, `after_factory_cache_destruction`, and
`after_refiner_destruction`; no fourth stage may be invented. Retained payload
remains exactly the approved formula because the representation retains only
the original provider coefficients and derives oriented `v0` from the face;
it stores no anchor ID, new coefficient row, or evaluation output. Any such
additional retained value is invalid.

The eight exact input IDs, in evaluation order, are `fixture_x`, `fixture_y`,
`fixture_z`, `positive_zero`, `positive_one`, `negative_one`,
`positive_2p20`, and `negative_2p20`. The canonical representation-output
reference ledger contains records `[content_id,level,face_id,local_corner,
sample_id,row_kind,input_id,output_bits]` in unsigned JCS-key-byte order for
the fixed serial cache-disabled Release workload. The input ID is one of that
literal enum and `output_bits` is 16 lowercase hex.

Complete bytes, rather than only their digests, are published under the
following frozen artifact contract:

```text
anchored-row-d12-v1/serial/provider-rows.b2rowv1
anchored-row-d12-v1/serial/representation-outputs.json
anchored-row-d12-v1/process/process-observations.json
anchored-row-d12-v1/workers/{cache_mode}/{content_id}/level-{level}/workers-{worker_count}/round-{round_2digits}/worker-{worker_index}-provider.b2rowv1
anchored-row-d12-v1/workers/{cache_mode}/{content_id}/level-{level}/workers-{worker_count}/round-{round_2digits}/worker-{worker_index}-representation.json
```

`cache_mode` is exactly `cache_disabled` or `threaded_cache`; content IDs,
levels, worker counts/indices, and rounds are the frozen tuple values. Every
path has a standard availability/relative-path/byte-length/record-count/
SHA-256 descriptor in the D12 artifact. Provider sidecars are concatenations
of complete canonical length-prefixed `B2ROWV1` records in frozen workload
order. Representation sidecars are RFC 8785 outer arrays of the complete
records above, with no newline, in the same row order expanded by the eight
input IDs.

The serial provider reference has exactly 693,000 row records and the serial
representation reference exactly 5,544,000 output records. Across the 13,720
cache-disabled worker/round cells, provider sidecars contain exactly
97,020,000 row records and representation sidecars exactly 776,160,000 output
records. The threaded-cache populations have the same two exact counts. These
are pre-result cardinalities: `693000 * (1+2+4) * 20` provider rows and eight
outputs per row for each mode. A missing, extra, reordered, duplicated,
digest-only, or noncanonical record fails the owning D12 criterion.

Every child process writes its raw records through the runner-owned pipe; the
runner receives and validates each `B2ROWV1` record and every output bit,
constructs the persistent sidecar itself, rescans the completed bytes, and
only then computes the provider and representation digests. A worker-supplied
digest is ignored as evidence. Every concurrent worker/round compares its two
complete streams to the serial provider and representation references;
pairwise agreement without both serial agreements is insufficient. TSan
compiles and instruments both provider and representation translation units
and executes this identical complete eight-input workload.

The required process-observation artifact at the fixed path above is the RFC
8785 outer array, with no newline, of exactly **4,189,640** records: every
3,136 duration key, 5,964 retained-payload key, 4,179,364 RSS key, and the
1,176 TSan process-summary keys (588 instrumentation plus 588 finding-count).
Records are sorted by unsigned lexicographic RFC 8785 bytes of their
operational key and have the exact form
`[operational_key,raw_payload,process_provenance]`. Missing, extra, duplicate,
or non-increasing keys are invalid. The complete artifact has one required
`d12_sidecar_descriptor` in the closed
`workload.process_observation_sidecar` member with that literal path and record
count; it is not duplicated in the worker `sidecars` array. The runner
publishes and rescans all bytes before using a raw observation.

`raw_payload` is exactly one closed variant selected by the operational key's
quantity:

```text
d12_duration_raw_v1 =
  {kind:"d12_duration_raw_v1",state:"VALID_UINT64_NS"|"NONFINITE"|
   "NEGATIVE"|"TIMEOUT"|"SIGNAL"|"ALLOCATION_FAILURE"|"PROCESS_FAILURE",
   token:string|null}
d12_payload_raw_v1 =
  {kind:"d12_payload_raw_v1",state:"VALID_UINT64_BYTES"|"MISSING_COUNT"|
   "NON_SIX_ROW_SAMPLE"|"ARITHMETIC_OVERFLOW"|"PROCESS_FAILURE",
   token:string|null}
d12_rss_raw_v1 =
  {kind:"d12_rss_raw_v1",state:"VALID_UINT64_BYTES"|"SAMPLE_MISSING"|
   "API_FAILURE"|"PROCESS_FAILURE",baseline_token:string|null,
   observed_token:string|null}
d12_tsan_instrumentation_raw_v1 =
  {kind:"d12_tsan_instrumentation_raw_v1",state:"COMPLETE"|"INCOMPLETE",
   instrumented_translation_units_sha256:sha256|null}
d12_tsan_finding_raw_v1 =
  {kind:"d12_tsan_finding_raw_v1",state:"COMPLETE"|"SANITIZER_ABORT"|
   "EXECUTION_UNAVAILABLE",finding_count_token:string|null,
   sanitizer_report_sha256:sha256|null}
```

A valid integer token is its canonical unsigned base-10 value. A negative
token is canonical signed base-10. Nonfinite tokens are exactly `nan`, `+inf`,
or `-inf`; all other failure states use null. A complete finding-count token is
canonical unsigned base-10. The SHA members are present exactly for complete
instrumentation or a sanitizer report respectively. `process_provenance` is
the closed `d12_process_provenance_v1` object with exactly `kind`,
`process_tuple_sha256`, `executable_sha256`, `argv_sha256`,
`environment_sha256`, `pid:uint64|null`, `start_utc`, `end_utc`,
`exit_kind:"EXITED"|"SIGNALED"|"TIMEOUT"|"NOT_STARTED"`,
`exit_code:signed integer|null`, `signal:signed integer|null`, and
`stderr_sha256`. State-conditioned nullability and process outcome must agree.

For each present `d12_raw_observation_binding_v1`, `relative_path` is exactly
the process-observation path, `byte_offset` points to the first byte of that
record inside the outer-array bytes, `byte_length` is exactly that record's
RFC 8785 byte length, and `sha256` is the digest of those record bytes alone.
The validator rescans the complete outer array, verifies the enclosing commas/
brackets and key order, then requires the bound slice to be the unique record
whose operational key equals the owning result key. A freestanding matching
slice cannot substitute for the complete artifact.

Every raw D12 observation is bound by a closed
`d12_raw_observation_binding_v1` object with exactly `kind`, standard
`availability`, canonical `relative_path`, `byte_offset:uint64`,
`byte_length:uint64`, and `sha256`; present slices are nonempty and must match
the published process-observation sidecar bytes. The five D12 exact-value
families are closed discriminated unions:

- `d12_duration_value_v1` is either `{kind:"d12_duration_valid_v1",
  quantity:"preparation_duration_ns"|"preparation_median_ns",
  duration_ns:uint64,platform_state,raw_observation}` or
  `{kind:"d12_duration_invalid_v1",quantity,
  duration_ns:null,invalid_state:"NONFINITE"|"NEGATIVE"|"TIMEOUT"|
  "SIGNAL"|"ALLOCATION_FAILURE"|"PROCESS_FAILURE",platform_state,
  raw_observation}`. Its target is exactly
  `{kind:"d12_duration_target_v1",median_ns:1000000000,
  single_ns:10000000000}`.
- `d12_payload_value_v1` is either `{kind:"d12_payload_valid_v1",
  payload_bytes:uint64,face_id:uint64,platform_state,raw_observation}` or
  `{kind:"d12_payload_invalid_v1",payload_bytes:null,face_id:uint64|null,
  invalid_state:"MISSING_COUNT"|"NON_SIX_ROW_SAMPLE"|
  "ARITHMETIC_OVERFLOW"|"PROCESS_FAILURE",platform_state,
  raw_observation}`. Its target is exactly
  `{kind:"d12_payload_target_v1",maximum_bytes:131072}`.
- `d12_rss_value_v1` is either `{kind:"d12_rss_valid_v1",
  baseline_rss_bytes:uint64,observed_rss_bytes:uint64,
  rss_delta_bytes:uint64,stage,platform_state,raw_observation}` or
  `{kind:"d12_rss_invalid_v1",baseline_rss_bytes:uint64|null,
  observed_rss_bytes:null,rss_delta_bytes:null,stage,
  invalid_state:"SAMPLE_MISSING"|"API_FAILURE"|"PROCESS_FAILURE",
  platform_state,raw_observation}`. Its target is exactly
  `{kind:"d12_rss_target_v1",maximum_delta_bytes:67108864}`.
- `d12_concurrency_value_v1` has exactly `kind`, the complete provider and
  representation sidecar descriptors, `provider_observed_sha256`,
  `provider_expected_sha256`, `representation_observed_sha256`,
  `representation_expected_sha256`, and `platform_state`. Both sidecars must
  be `PRESENT`, both observed digests must be non-null and equal the rescanned
  complete sidecar bytes, and both expected digests must be non-null. This
  value is forbidden for `CACHE_DISABLED_RACE`; only
  `d12_concurrency_abort_v1` may encode that state. Its target is exactly `{kind:
  "d12_output_reference_target_v1",provider_expected_sha256:sha256,
  representation_expected_sha256:sha256}`.
- `d12_concurrency_abort_v1` applies only to a criterion-30 cache-disabled
  `row_digest` key whose same-tuple TSan process aborted. It has exactly
  `{kind:"d12_concurrency_abort_v1",provider_sidecar,
  representation_sidecar,provider_observed_sha256:null,
  provider_expected_sha256:sha256,representation_observed_sha256:null,
  representation_expected_sha256:sha256,tsan_finding_summary_key,
  platform_state}`. Both sidecar descriptors are in the standard
  `UNAVAILABLE/EXECUTION_UNAVAILABLE` state with null path, byte length, record
  count, and SHA-256. `tsan_finding_summary_key` is the unique criterion-31
  cache-disabled same-tuple `tsan_finding_count` operational key; its result
  must be `FAIL/CACHE_DISABLED_RACE` and owns the actual sanitizer report.
  Criterion 30 duplicates no report bytes or digest. The abort value always
  has result reason `CACHE_DISABLED_RACE` and target
  `d12_output_reference_target_v1`.
- `d12_tsan_instrumentation_summary_v1` applies only when key quantity is
  `instrumentation_coverage` and has exactly `{kind:
  "d12_tsan_instrumentation_summary_v1",instrumentation_complete:boolean,
  instrumented_translation_units_sha256:sha256|null,
  expected_translation_units_sha256:sha256,platform_state,raw_observation}`.
  It owns no worker sidecar. Its target is exactly `{kind:
  "d12_tsan_instrumentation_target_v1",instrumentation_complete:true,
  expected_translation_units_sha256:sha256}`.
- `d12_tsan_finding_summary_v1` applies only when key quantity is
  `tsan_finding_count` and has exactly `{kind:
  "d12_tsan_finding_summary_v1",finding_count:uint64|null,
  sanitizer_abort:boolean,sanitizer_report_sha256:sha256|null,
  platform_state,raw_observation}`. It owns the sanitizer report and no worker
  sidecar. Its target is exactly `{kind:"d12_tsan_finding_target_v1",
  finding_count:0}`. A sanitizer abort requires `sanitizer_abort:true`, a
  present report digest, null finding count only when the report cannot
  enumerate findings, and candidate reason `CACHE_DISABLED_RACE` or
  `THREADED_CACHE_RACE` according to the tuple mode.
- `d12_tsan_threaded_row_value_v1` applies only when key quantity is
  `row_digest` and has exactly `{kind:"d12_tsan_threaded_row_value_v1",
  provider_sidecar,representation_sidecar,provider_observed_sha256,
  provider_expected_sha256,representation_observed_sha256,
  representation_expected_sha256,platform_state}`. Both complete sidecars are
  present and rescanned. Its target is the exact
  `d12_output_reference_target_v1`.

When a TSan process aborts, its criterion-31 finding-summary record solely owns
the report. For a cache-disabled tuple, every unavailable criterion-30
row-digest result uses `d12_concurrency_abort_v1` and reason
`CACHE_DISABLED_RACE`. Criterion 31 has no cache-disabled row-digest keys. For
a threaded-cache tuple, every expected criterion-31 row-digest key that the
abort prevented is still present as exactly
`[key,"FAIL",null,d12_output_reference_target_v1,
"THREADED_CACHE_RACE"]`. The runner derives all unavailable keys from the
frozen tuple expansion and their same-tuple finding summary. A criterion-31
row record from a nonaborted threaded process must use
`d12_tsan_threaded_row_value_v1` and cannot be null; a criterion-30 record may
never use the null-after-abort form.

For duration, payload, and RSS, the invalid-state discriminator and record
reason are a fixed one-to-one mapping: `NONFINITE|NEGATIVE` to
`PREPARATION_MEASUREMENT_NONFINITE_OR_NEGATIVE`; all other duration invalid
states to `PREPARATION_PROCESS_FAILURE`; every payload invalid state to
`RETAINED_PAYLOAD_INVALID`; and every RSS invalid state to
`RSS_SAMPLE_MISSING_OR_API_FAILURE`. A valid numeric overrun uses the specific
budget reason. No invalid object may invent a zero numeric value.

For a D12 numeric criterion, the maximum and witness are computed over all and
only valid numeric records. If at least one valid record exists, the first
canonical exact maximum and witness are required even when another invalid
record fixes `FAIL`. If none exists, maximum and witness are null and the first
invalid record is the required `first_failing_key`. Raw D9a and every other
executed numeric scientific criterion always have at least one numeric record
and retain their mandatory maximum witness.

On the qualified physical host, result outcome is `PASS` or candidate `FAIL`
with only the already frozen D12 failure reasons. On a complete hosted or other
unqualified run, every expected record is retained with outcome `INCOMPLETE`,
its unchanged target, its observed exact value, and exact reason
`D12_PLATFORM_UNQUALIFIED`. Invalid provenance or an incomplete ledger has no
complete result sidecar and uses criterion `INCOMPLETE` with respectively
`D12_PROVENANCE_INVALID` or `D12_OPERATIONAL_LEDGER_INCOMPLETE`. A workload or
reference mismatch on a qualified host uses candidate reason
`D12_REPRESENTATION_WORKLOAD_MISMATCH`; it cannot be relabeled platform state.

`serial_only_context` has exactly these members and no others:

```text
tuple_count                              588
all_tuple_keys_sha256                    sha256
cache_disabled_concurrency_cell_count    13720
cache_disabled_concurrency_ledger_sha256 sha256
cache_disabled_concurrency_pass          boolean
cache_disabled_tsan_summary_cell_count   588
cache_disabled_tsan_summary_sha256       sha256
cache_disabled_tsan_pass                 boolean
threaded_tsan_summary_cell_count         588
threaded_tsan_summary_sha256             sha256
threaded_tsan_row_digest_cell_count      13720
threaded_tsan_row_digest_sha256          sha256
all_tsan_cell_count                      14896
all_tsan_result_ledger_sha256            sha256
failure_records                          canonical array [operational_key,reason]
failure_records_sha256                   sha256
```

The 13,720 cache-disabled-concurrency cells belong to criterion 30 and are not
TSan summary cells. Criterion 31 partitions exactly into 588 cache-disabled
summary cells, 588 threaded-cache summary cells, and 13,720 threaded-cache
row-digest cells. Every count and digest must match the corresponding complete
D12 result ledger. Each filtered digest is defined identically: select from
the complete canonical criterion result ledger exactly the records whose
operational keys satisfy that member's mode/quantity predicate, retain their
original five-field result records, preserve unsigned JCS-key-byte order,
serialize the selected records as one RFC 8785 outer array with no newline,
and SHA-256 those complete bytes. The predicates are exact:

```text
cache_disabled_concurrency_ledger  criterion 30, every record
cache_disabled_tsan_summary        criterion 31, cache_disabled,
                                   quantity instrumentation_coverage or tsan_finding_count
threaded_tsan_summary              criterion 31, threaded_cache,
                                   quantity instrumentation_coverage or tsan_finding_count
threaded_tsan_row_digest           criterion 31, threaded_cache,
                                   quantity row_digest
all_tsan_result_ledger             criterion 31, every record
```

The empty selected set serializes as `[]`; no digest of concatenated hashes,
keys alone, or an implementation-private filtered file is valid.
`failure_records` contains every
threaded-cache failing operational key and its exact reason, in canonical key
order, and no cache-disabled or non-TSan record. Its digest is SHA-256 of the
RFC 8785 outer array bytes with no newline and must equal the report verdict's
`threaded_only_failure_ledger_sha256` byte-for-byte when serial-only
eligibility is true; otherwise both report ledger digest and any eligibility
claim are null/false as already frozen. The report derives
serial-only eligibility solely from this object and the full criterion set; it
may not hardcode the disposition. Hosted or otherwise unqualified evidence is
`PRESENT/UNQUALIFIED_PLATFORM` and makes all five D12 criteria `INCOMPLETE`
regardless of observed numbers. Only a complete exact-head qualified physical
artifact may produce D12 `PASS` or candidate-owned `FAIL`.

## Documentation-owned mutation path anchor

The exact UTF-8 bytes between the two marker lines below, excluding the marker
lines themselves and including the final LF after the last data line, are the
documentation-owned schema-path universe
`anchored-row-result-evidence-schema-paths-v1`. Lines are unsigned-byte
lexicographically sorted. They are literal reviewed input; they are not
generated from the later executable schema. The canonical SHA-256 is
`0e82d15b0244aaa779a1ca600fdc8b43ac501ab91aa615e8adb8dcd8682ecf66`.

```text
BEGIN anchored-row-result-evidence-schema-paths-v1
array|authority.actual_fixture_files
array|authority.anchor_order
array|authority.canonical_sample_order
array|authority.expected_fixture_files
array|authority.radius_exponents
array|authority.ray_sequence
array|authority.relabels
array|authority.rows
array|authority.source_order
array|binary_binding.sources
array|candidate_dyadic_vector_observation_v1.source_ids
array|candidate_dyadic_vector_observation_v1.values
array|candidate_interval_vector_observation_v1.observed_intervals
array|candidate_interval_vector_observation_v1.source_ids
array|candidate_row_signature_observation_v1.cache_disabled_entries
array|candidate_row_signature_observation_v1.serial_cache_entries
array|candidate_structure_observation_v1.canonical_source_ids
array|candidate_structure_observation_v1.effective_coefficients
array|candidate_structure_observation_v1.provider_coefficient_bits
array|coefficient_interval_vector_v1.absolute_error_uppers
array|coefficient_interval_vector_v1.analytic_intervals
array|coefficient_interval_vector_v1.observed
array|coefficient_interval_vector_v1.source_union_ids
array|coefficient_vector_comparison_v1.absolute_errors
array|coefficient_vector_comparison_v1.expected
array|coefficient_vector_comparison_v1.observed
array|coefficient_vector_comparison_v1.source_ids
array|d12.criteria
array|d12.process_observations
array|d12.tuple_keys
array|d12_binary.source_inventory
array|d12_build_profile.compile_commands
array|d12_build_profile.flags
array|d12_build_profile.link_commands
array|d12_concurrency_abort_v1.tsan_finding_summary_key
array|d12_platform.field_mismatches
array|d12_platform.power_thermal_observations
array|d12_process_observation_record_v1
array|d12_workload.input_ids
array|d12_workload.sidecars
array|exact_coefficient_l1_v1.absolute_errors
array|exact_coefficient_l1_v1.expected
array|exact_coefficient_l1_v1.observed
array|exact_coefficient_l1_v1.source_ids
array|matrix.ledgers
array|matrix.unexpected_paths
array|maximum_witness.merkle_siblings
array|oracle.covered_keys
array|oracle.request_keys
array|oracle.uncovered_keys
array|oracle_coefficient_l1_v1.absolute_error_uppers
array|oracle_coefficient_l1_v1.observed
array|oracle_coefficient_l1_v1.oracle_intervals
array|oracle_coefficient_l1_v1.source_ids
array|oracle_covered_value_v1.child_branches
array|oracle_covered_value_v1.evaluated_depths
array|oracle_covered_value_v1.intersected_primary_intervals
array|oracle_covered_value_v1.primary_depth_intervals
array|oracle_covered_value_v1.primary_depth_intervals[]
array|oracle_covered_value_v1.source_ids
array|oracle_covered_value_v1.uniform_depth_intervals
array|oracle_covered_value_v1.uniform_depth_intervals[]
array|report.artifacts
array|report.criteria
array|result_ledger.outer_records
array|serial_only_context.failure_records
array|structure_missing_anchor_v1.canonical_source_ids
array|structure_missing_anchor_v1.provider_coefficient_bits
array|structure_present_v1.canonical_source_ids
array|structure_present_v1.effective_coefficients
array|structure_present_v1.provider_coefficient_bits
authority|authority.anchor_order
authority|authority.canonical_sample_order
authority|authority.component_targets.first_derivative
authority|authority.component_targets.position
authority|authority.component_targets.second_derivative
authority|authority.d10.first_derivative
authority|authority.d10.position
authority|authority.d10.second_derivative
authority|authority.d12_contract.peak_rss_delta_bytes
authority|authority.d12_contract.preparation_median_ns
authority|authority.d12_contract.preparation_single_ns
authority|authority.d12_contract.retained_payload_bytes
authority|authority.dependencies.gmp
authority|authority.dependencies.mpfr
authority|authority.dependencies.opensubdiv
authority|authority.expected_fixture_files
authority|authority.inner_radius_rule
authority|authority.manifest_contract_sha256
authority|authority.manifest_file_sha256
authority|authority.physical_fingerprint
authority|authority.radius_exponents
authority|authority.ray_sequence
authority|authority.relabels
authority|authority.row_invariant_tolerance
authority|authority.rows
authority|authority.source_order
criterion|00|bindings_and_independence|1
criterion|01|complete_artifact_inventory|294
criterion|02|raw_bfr_d9a_reproduction|196
criterion|03|representation_structure|4158000
criterion|04|constant_field_bits|62370000
criterion|05|relabel_exact_effective_coefficients|8316000
criterion|06|regular_analytic_exact_rows|152640
criterion|07|regular_analytic_emitted_geometry|457920
criterion|08|regular_analytic_area_integrand|50880
criterion|09|regular_analytic_legacy_volume_integrand|50880
criterion|10|oracle_coverage_and_crosscheck|1188000
criterion|11|exact_effective_d10_coeff|1188000
criterion|12|exact_effective_d10_geometry|3564000
criterion|13|emitted_direct_geometry_d10|3564000
criterion|14|anchor_sensitivity_exact_coeff|1188000
criterion|15|anchor_sensitivity_exact_geometry|3564000
criterion|16|anchor_sensitivity_emitted_geometry|3564000
criterion|17|binary64_basis_probe_diagnostic|32271264
criterion|18|binary64_direct_geometry_fidelity|10692000
criterion|19|relabel_emitted_geometry_fidelity|7128000
criterion|20|stabilization_6_7_exact_coeff|594000
criterion|21|stabilization_6_7_exact_geometry|1782000
criterion|22|stabilization_6_7_emitted_geometry|1782000
criterion|23|stabilization_7_8_exact_coeff|594000
criterion|24|stabilization_7_8_exact_geometry|1782000
criterion|25|stabilization_7_8_emitted_geometry|1782000
criterion|26|cache_mode_bit_identity|2079000
criterion|27|d12_preparation_cost|3136
criterion|28|d12_retained_payload|5964
criterion|29|d12_peak_rss|4179364
criterion|30|d12_cache_disabled_concurrency|13720
criterion|31|d12_instrumented_tsan|14896
ledger|00|bindings_and_independence|all
ledger|01|complete_artifact_inventory|all
ledger|02|raw_bfr_d9a_reproduction|all
ledger|03|representation_structure|all
ledger|04|constant_field_bits|all
ledger|05|relabel_exact_effective_coefficients|all
ledger|06|regular_analytic_exact_rows|all
ledger|07|regular_analytic_emitted_geometry|all
ledger|08|regular_analytic_area_integrand|all
ledger|09|regular_analytic_legacy_volume_integrand|all
ledger|10|oracle_coverage_and_crosscheck|covered
ledger|10|oracle_coverage_and_crosscheck|oracle_request
ledger|10|oracle_coverage_and_crosscheck|uncovered
ledger|11|exact_effective_d10_coeff|all
ledger|12|exact_effective_d10_geometry|all
ledger|13|emitted_direct_geometry_d10|all
ledger|14|anchor_sensitivity_exact_coeff|all
ledger|15|anchor_sensitivity_exact_geometry|all
ledger|16|anchor_sensitivity_emitted_geometry|all
ledger|17|binary64_basis_probe_diagnostic|all
ledger|18|binary64_direct_geometry_fidelity|all
ledger|19|relabel_emitted_geometry_fidelity|all
ledger|20|stabilization_6_7_exact_coeff|all
ledger|21|stabilization_6_7_exact_geometry|all
ledger|22|stabilization_6_7_emitted_geometry|all
ledger|23|stabilization_7_8_exact_coeff|all
ledger|24|stabilization_7_8_exact_geometry|all
ledger|25|stabilization_7_8_emitted_geometry|all
ledger|26|cache_mode_bit_identity|all
ledger|27|d12_preparation_cost|all
ledger|28|d12_retained_payload|all
ledger|29|d12_peak_rss|all
ledger|30|d12_cache_disabled_concurrency|all
ledger|31|d12_instrumented_tsan|all
object|absolute_dyadic_v1|denominator_power
object|absolute_dyadic_v1|kind
object|absolute_dyadic_v1|numerator_hex
object|absolute_rational_target_v1|denominator
object|absolute_rational_target_v1|kind
object|absolute_rational_target_v1|numerator
object|absolute_rational_v1|denominator
object|absolute_rational_v1|kind
object|absolute_rational_v1|numerator
object|anchored_row_representation_d12|authority
object|anchored_row_representation_d12|binaries
object|anchored_row_representation_d12|build_profiles
object|anchored_row_representation_d12|candidate
object|anchored_row_representation_d12|content_sha256
object|anchored_row_representation_d12|criteria
object|anchored_row_representation_d12|dependencies
object|anchored_row_representation_d12|git
object|anchored_row_representation_d12|platform
object|anchored_row_representation_d12|schema_id
object|anchored_row_representation_d12|serial_only_context
object|anchored_row_representation_d12|workload
object|artifact_slot_target_v1|cache_mode
object|artifact_slot_target_v1|candidate
object|artifact_slot_target_v1|canonical_b2rowv1_sha256
object|artifact_slot_target_v1|compressed_sha256
object|artifact_slot_target_v1|content_id
object|artifact_slot_target_v1|decompressed_json_sha256
object|artifact_slot_target_v1|expected_slot_ordinal
object|artifact_slot_target_v1|kind
object|artifact_slot_target_v1|level
object|artifact_value_v1|availability
object|artifact_value_v1|canonical_b2rowv1_sha256
object|artifact_value_v1|compressed_sha256
object|artifact_value_v1|decompressed_json_sha256
object|artifact_value_v1|expected_identity_matches
object|artifact_value_v1|expected_slot_ordinal
object|artifact_value_v1|kind
object|artifact_value_v1|relative_path
object|artifact|availability
object|artifact|b2rowv1_sha256
object|artifact|cache_mode
object|artifact|candidate
object|artifact|compressed_sha256
object|artifact|content_id
object|artifact|json_sha256
object|artifact|level
object|authority|actual_fixture_files
object|authority|anchor_order
object|authority|canonical_sample_order
object|authority|component_targets
object|authority|d10
object|authority|d12_contract
object|authority|expected_fixture_files
object|authority|inner_radius_rule
object|authority|manifest_contract_sha256
object|authority|manifest_file_sha256
object|authority|physical_fingerprint
object|authority|radius_exponents
object|authority|ray_sequence
object|authority|relabels
object|authority|row_invariant_tolerance
object|authority|rows
object|authority|source_order
object|availability|reason_code
object|availability|sha256
object|availability|state
object|basis_value_v1|emitted_basis_bits
object|basis_value_v1|exact_effective
object|basis_value_v1|group_l1
object|basis_value_v1|kind
object|basis_value_v1|source_error
object|binaries|exact_dyadic_boundary
object|binaries|independent_oracle
object|binaries|oracle_independence_audit
object|binaries|representation_candidate
object|binaries|row_provider
object|binary64_pair_v1|expected_bits
object|binary64_pair_v1|kind
object|binary64_pair_v1|observed_bits
object|binary64_scalar_v1|bits
object|binary64_scalar_v1|kind
object|binary_binding|availability
object|binary_binding|capability
object|binary_binding|compiler_command
object|binary_binding|compiler_version
object|binary_binding|dependencies
object|binary_binding|dynamic_dependencies
object|binary_binding|link_map
object|binary_binding|sources
object|binding_value_v1|exact_boundary_availability
object|binding_value_v1|exact_boundary_sha256
object|binding_value_v1|git_end
object|binding_value_v1|git_start
object|binding_value_v1|gmp_identity
object|binding_value_v1|independent_oracle_availability
object|binding_value_v1|independent_oracle_sha256
object|binding_value_v1|kind
object|binding_value_v1|manifest_contract_sha256
object|binding_value_v1|manifest_file_sha256
object|binding_value_v1|mpfr_identity
object|binding_value_v1|opensubdiv_identity
object|binding_value_v1|oracle_independence_audit
object|binding_value_v1|provenance_complete
object|binding_value_v1|representation_availability
object|binding_value_v1|representation_sha256
object|binding_value_v1|row_provider_availability
object|binding_value_v1|row_provider_sha256
object|binding_value_v1|validator_sha256
object|binding_value_v1|worktree_end_clean
object|binding_value_v1|worktree_start_clean
object|candidate_basis_observation_v1|emitted_basis_bits
object|candidate_basis_observation_v1|kind
object|candidate_binary64_observation_v1|kind
object|candidate_binary64_observation_v1|observed_bits
object|candidate_dyadic_vector_observation_v1|kind
object|candidate_dyadic_vector_observation_v1|source_ids
object|candidate_dyadic_vector_observation_v1|values
object|candidate_emitted_geometry_observation_v1|axis
object|candidate_emitted_geometry_observation_v1|kind
object|candidate_emitted_geometry_observation_v1|observed_bits
object|candidate_emitted_integrand_observation_v1|kind
object|candidate_emitted_integrand_observation_v1|observed_bits
object|candidate_emitted_integrand_observation_v1|view
object|candidate_exact_geometry_observation_v1|axis
object|candidate_exact_geometry_observation_v1|kind
object|candidate_exact_geometry_observation_v1|observed
object|candidate_exact_integrand_observation_v1|kind
object|candidate_exact_integrand_observation_v1|observed_interval
object|candidate_exact_integrand_observation_v1|view
object|candidate_interval_vector_observation_v1|kind
object|candidate_interval_vector_observation_v1|observed_intervals
object|candidate_interval_vector_observation_v1|source_ids
object|candidate_row_signature_observation_v1|cache_disabled_entries
object|candidate_row_signature_observation_v1|kind
object|candidate_row_signature_observation_v1|serial_cache_entries
object|candidate_structure_observation_v1|canonical_source_ids
object|candidate_structure_observation_v1|effective_coefficients
object|candidate_structure_observation_v1|kind
object|candidate_structure_observation_v1|provider_coefficient_bits
object|checkpoint|availability
object|checkpoint|git_head
object|checkpoint|release_complete
object|checkpoint|row_provider_binary_sha256
object|coefficient_interval_vector_v1|absolute_error_uppers
object|coefficient_interval_vector_v1|analytic_intervals
object|coefficient_interval_vector_v1|first_maximum_source_id
object|coefficient_interval_vector_v1|kind
object|coefficient_interval_vector_v1|maximum_error_upper
object|coefficient_interval_vector_v1|observed
object|coefficient_interval_vector_v1|source_union_ids
object|coefficient_vector_comparison_v1|absolute_errors
object|coefficient_vector_comparison_v1|expected
object|coefficient_vector_comparison_v1|kind
object|coefficient_vector_comparison_v1|l1
object|coefficient_vector_comparison_v1|observed
object|coefficient_vector_comparison_v1|source_ids
object|criterion|applicability
object|criterion|criterion_id
object|criterion|expectation
object|criterion|expected_cell_count
object|criterion|first_failing_key
object|criterion|key_ledger_sha256
object|criterion|maximum
object|criterion|observed_cell_count
object|criterion|omission_blocker
object|criterion|result_ledger_artifact
object|criterion|result_ledger_sha256
object|criterion|result_merkle_root_sha256
object|criterion|status
object|criterion|target
object|criterion|witness
object|d12_artifact_binding|availability
object|d12_artifact_binding|exact_head
object|d12_artifact_binding|execution_state
object|d12_artifact_binding|omission_blocker
object|d12_artifact_binding|physical_fingerprint_sha256
object|d12_artifact_binding|representation_work
object|d12_binary|availability
object|d12_binary|compiler_command_sha256
object|d12_binary|dynamic_dependency_sha256
object|d12_binary|link_map_sha256
object|d12_binary|sha256
object|d12_binary|source_inventory
object|d12_build_profile|cmake_path
object|d12_build_profile|cmake_version
object|d12_build_profile|compile_commands
object|d12_build_profile|compiler_path
object|d12_build_profile|compiler_version
object|d12_build_profile|flags
object|d12_build_profile|link_commands
object|d12_build_profile|make_path
object|d12_build_profile|make_version
object|d12_build_profile|sdk_path
object|d12_build_profile|sdk_version
object|d12_concurrency_abort_v1|kind
object|d12_concurrency_abort_v1|platform_state
object|d12_concurrency_abort_v1|provider_expected_sha256
object|d12_concurrency_abort_v1|provider_observed_sha256
object|d12_concurrency_abort_v1|provider_sidecar
object|d12_concurrency_abort_v1|representation_expected_sha256
object|d12_concurrency_abort_v1|representation_observed_sha256
object|d12_concurrency_abort_v1|representation_sidecar
object|d12_concurrency_abort_v1|tsan_finding_summary_key
object|d12_concurrency_value_v1|kind
object|d12_concurrency_value_v1|platform_state
object|d12_concurrency_value_v1|provider_expected_sha256
object|d12_concurrency_value_v1|provider_observed_sha256
object|d12_concurrency_value_v1|provider_sidecar
object|d12_concurrency_value_v1|representation_expected_sha256
object|d12_concurrency_value_v1|representation_observed_sha256
object|d12_concurrency_value_v1|representation_sidecar
object|d12_dependency|archive_sha256
object|d12_dependency|build_root_provenance_sha256
object|d12_dependency|install_provenance_sha256
object|d12_dependency|installed_library_sha256
object|d12_dependency|link_provenance_sha256
object|d12_dependency|source_identity
object|d12_dependency|version
object|d12_duration_invalid_v1|duration_ns
object|d12_duration_invalid_v1|invalid_state
object|d12_duration_invalid_v1|kind
object|d12_duration_invalid_v1|platform_state
object|d12_duration_invalid_v1|quantity
object|d12_duration_invalid_v1|raw_observation
object|d12_duration_raw_v1|kind
object|d12_duration_raw_v1|state
object|d12_duration_raw_v1|token
object|d12_duration_target_v1|kind
object|d12_duration_target_v1|median_ns
object|d12_duration_target_v1|single_ns
object|d12_duration_valid_v1|duration_ns
object|d12_duration_valid_v1|kind
object|d12_duration_valid_v1|platform_state
object|d12_duration_valid_v1|quantity
object|d12_duration_valid_v1|raw_observation
object|d12_git|head
object|d12_git|head_query_ok
object|d12_git|worktree_clean
object|d12_output_reference_target_v1|kind
object|d12_output_reference_target_v1|provider_expected_sha256
object|d12_output_reference_target_v1|representation_expected_sha256
object|d12_payload_invalid_v1|face_id
object|d12_payload_invalid_v1|invalid_state
object|d12_payload_invalid_v1|kind
object|d12_payload_invalid_v1|payload_bytes
object|d12_payload_invalid_v1|platform_state
object|d12_payload_invalid_v1|raw_observation
object|d12_payload_raw_v1|kind
object|d12_payload_raw_v1|state
object|d12_payload_raw_v1|token
object|d12_payload_target_v1|kind
object|d12_payload_target_v1|maximum_bytes
object|d12_payload_valid_v1|face_id
object|d12_payload_valid_v1|kind
object|d12_payload_valid_v1|payload_bytes
object|d12_payload_valid_v1|platform_state
object|d12_payload_valid_v1|raw_observation
object|d12_platform|compiler_identity
object|d12_platform|expected_fingerprint
object|d12_platform|field_mismatches
object|d12_platform|github_hosted
object|d12_platform|observed_fingerprint
object|d12_platform|platform_state
object|d12_platform|power_thermal_observations
object|d12_platform|virtualization_observation
object|d12_process_provenance_v1|argv_sha256
object|d12_process_provenance_v1|end_utc
object|d12_process_provenance_v1|environment_sha256
object|d12_process_provenance_v1|executable_sha256
object|d12_process_provenance_v1|exit_code
object|d12_process_provenance_v1|exit_kind
object|d12_process_provenance_v1|kind
object|d12_process_provenance_v1|pid
object|d12_process_provenance_v1|process_tuple_sha256
object|d12_process_provenance_v1|signal
object|d12_process_provenance_v1|start_utc
object|d12_process_provenance_v1|stderr_sha256
object|d12_raw_observation_binding_v1|availability
object|d12_raw_observation_binding_v1|byte_length
object|d12_raw_observation_binding_v1|byte_offset
object|d12_raw_observation_binding_v1|kind
object|d12_raw_observation_binding_v1|relative_path
object|d12_raw_observation_binding_v1|sha256
object|d12_rss_invalid_v1|baseline_rss_bytes
object|d12_rss_invalid_v1|invalid_state
object|d12_rss_invalid_v1|kind
object|d12_rss_invalid_v1|observed_rss_bytes
object|d12_rss_invalid_v1|platform_state
object|d12_rss_invalid_v1|raw_observation
object|d12_rss_invalid_v1|rss_delta_bytes
object|d12_rss_invalid_v1|stage
object|d12_rss_raw_v1|baseline_token
object|d12_rss_raw_v1|kind
object|d12_rss_raw_v1|observed_token
object|d12_rss_raw_v1|state
object|d12_rss_target_v1|kind
object|d12_rss_target_v1|maximum_delta_bytes
object|d12_rss_valid_v1|baseline_rss_bytes
object|d12_rss_valid_v1|kind
object|d12_rss_valid_v1|observed_rss_bytes
object|d12_rss_valid_v1|platform_state
object|d12_rss_valid_v1|raw_observation
object|d12_rss_valid_v1|rss_delta_bytes
object|d12_rss_valid_v1|stage
object|d12_sidecar_descriptor|availability
object|d12_sidecar_descriptor|byte_length
object|d12_sidecar_descriptor|record_count
object|d12_sidecar_descriptor|relative_path
object|d12_sidecar_descriptor|sha256
object|d12_tsan_finding_raw_v1|finding_count_token
object|d12_tsan_finding_raw_v1|kind
object|d12_tsan_finding_raw_v1|sanitizer_report_sha256
object|d12_tsan_finding_raw_v1|state
object|d12_tsan_finding_summary_v1|finding_count
object|d12_tsan_finding_summary_v1|kind
object|d12_tsan_finding_summary_v1|platform_state
object|d12_tsan_finding_summary_v1|raw_observation
object|d12_tsan_finding_summary_v1|sanitizer_abort
object|d12_tsan_finding_summary_v1|sanitizer_report_sha256
object|d12_tsan_finding_target_v1|finding_count
object|d12_tsan_finding_target_v1|kind
object|d12_tsan_instrumentation_raw_v1|instrumented_translation_units_sha256
object|d12_tsan_instrumentation_raw_v1|kind
object|d12_tsan_instrumentation_raw_v1|state
object|d12_tsan_instrumentation_summary_v1|expected_translation_units_sha256
object|d12_tsan_instrumentation_summary_v1|instrumentation_complete
object|d12_tsan_instrumentation_summary_v1|instrumented_translation_units_sha256
object|d12_tsan_instrumentation_summary_v1|kind
object|d12_tsan_instrumentation_summary_v1|platform_state
object|d12_tsan_instrumentation_summary_v1|raw_observation
object|d12_tsan_instrumentation_target_v1|expected_translation_units_sha256
object|d12_tsan_instrumentation_target_v1|instrumentation_complete
object|d12_tsan_instrumentation_target_v1|kind
object|d12_tsan_threaded_row_value_v1|kind
object|d12_tsan_threaded_row_value_v1|platform_state
object|d12_tsan_threaded_row_value_v1|provider_expected_sha256
object|d12_tsan_threaded_row_value_v1|provider_observed_sha256
object|d12_tsan_threaded_row_value_v1|provider_sidecar
object|d12_tsan_threaded_row_value_v1|representation_expected_sha256
object|d12_tsan_threaded_row_value_v1|representation_observed_sha256
object|d12_tsan_threaded_row_value_v1|representation_sidecar
object|d12_workload|construction_and_evaluation_included
object|d12_workload|input_ids
object|d12_workload|process_observation_sidecar
object|d12_workload|provider_serial_reference
object|d12_workload|representation_serial_reference
object|d12_workload|sidecars
object|d12_workload|workload_id
object|dependencies|gmp
object|dependencies|mpfr
object|dependencies|opensubdiv
object|dependency_binding|build_provenance
object|dependency_binding|dynamic_dependencies
object|dependency_binding|install_provenance
object|dependency_binding|link_map
object|dependency_binding|source_archive
object|dependency_binding|version
object|digest_pair_v1|expected_sha256
object|digest_pair_v1|kind
object|digest_pair_v1|observed_sha256
object|emitted_interval_scalar_v1|absolute_error_upper
object|emitted_interval_scalar_v1|analytic_interval
object|emitted_interval_scalar_v1|kind
object|emitted_interval_scalar_v1|observed_bits
object|exact_coefficient_l1_v1|absolute_errors
object|exact_coefficient_l1_v1|expected
object|exact_coefficient_l1_v1|kind
object|exact_coefficient_l1_v1|l1
object|exact_coefficient_l1_v1|observed
object|exact_coefficient_l1_v1|source_ids
object|exact_zero_l1_target_v1|denominator
object|exact_zero_l1_target_v1|kind
object|exact_zero_l1_target_v1|numerator
object|geometry_axis_v1|axis
object|geometry_axis_v1|kind
object|geometry_axis_v1|normalized_bound
object|geometry_axis_v1|observed
object|geometry_axis_v1|reference_interval
object|geometry_axis_v1|view
object|git_identity|git_commit
object|git_identity|reason_code
object|git_identity|state
object|hash_binding|availability
object|hash_binding|path
object|identity|approved_b2b_merge_git_commit
object|identity|base_merge_git_commit
object|identity|candidate
object|identity|end_utc
object|identity|git_end
object|identity|git_start
object|identity|implementation_state
object|identity|schema_id
object|identity|start_utc
object|identity|validator
object|identity|worktree_end
object|identity|worktree_start
object|integrand_emitted_interval_v1|absolute_error_upper
object|integrand_emitted_interval_v1|analytic_interval
object|integrand_emitted_interval_v1|kind
object|integrand_emitted_interval_v1|observed_bits
object|integrand_emitted_interval_v1|view
object|integrand_exact_interval_v1|absolute_error_upper
object|integrand_exact_interval_v1|analytic_interval
object|integrand_exact_interval_v1|kind
object|integrand_exact_interval_v1|observed_interval
object|integrand_exact_interval_v1|view
object|interval_rational_v1|kind
object|interval_rational_v1|lower
object|interval_rational_v1|upper
object|matrix|expected_anchor_rows
object|matrix|expected_anchor_terms
object|matrix|expected_artifacts
object|matrix|expected_bfr_cases
object|matrix|expected_cache_pairs
object|matrix|expected_far_cases
object|matrix|expected_provider_terms
object|matrix|expected_raw_bfr_rows
object|matrix|ledgers
object|matrix|observed_anchor_rows
object|matrix|observed_anchor_terms
object|matrix|observed_artifacts
object|matrix|observed_bfr_cases
object|matrix|observed_cache_pairs
object|matrix|observed_far_cases
object|matrix|observed_provider_terms
object|matrix|observed_raw_bfr_rows
object|matrix|unexpected_paths
object|maximum_witness|cell_key
object|maximum_witness|leaf_index
object|maximum_witness|maximum_binary64_bits
object|maximum_witness|maximum_exact
object|maximum_witness|merkle_siblings
object|maximum_witness|result_record
object|normalized_interval_bound_v1|difference_interval
object|normalized_interval_bound_v1|distance_upper
object|normalized_interval_bound_v1|ideal_normalized
object|normalized_interval_bound_v1|kind
object|normalized_interval_bound_v1|normalized_upper
object|normalized_interval_bound_v1|scale_lower
object|normalized_interval_bound_v1|scale_squared_interval
object|oracle_certification_v1|eigenbasis
object|oracle_certification_v1|interval_intersection
object|oracle_certification_v1|kind
object|oracle_certification_v1|midpoint_serialization
object|oracle_certification_v1|parametric_map
object|oracle_certification_v1|regular_support
object|oracle_certification_v1|tangent_projection
object|oracle_certification_v1|uncertainty_bound
object|oracle_certification_v1|uniform_source_overlap
object|oracle_certification_v1|vertex_limit
object|oracle_coefficient_l1_v1|absolute_error_uppers
object|oracle_coefficient_l1_v1|kind
object|oracle_coefficient_l1_v1|l1
object|oracle_coefficient_l1_v1|observed
object|oracle_coefficient_l1_v1|oracle_intervals
object|oracle_coefficient_l1_v1|source_ids
object|oracle_covered_value_v1|certification
object|oracle_covered_value_v1|child_branches
object|oracle_covered_value_v1|coverage
object|oracle_covered_value_v1|evaluated_depths
object|oracle_covered_value_v1|first_isolating_depth
object|oracle_covered_value_v1|first_regular_support_depth
object|oracle_covered_value_v1|intersected_primary_intervals
object|oracle_covered_value_v1|kind
object|oracle_covered_value_v1|primary_depth_intervals
object|oracle_covered_value_v1|row_kind
object|oracle_covered_value_v1|source_ids
object|oracle_covered_value_v1|uniform_depth_intervals
object|pre_result_ledger|availability
object|pre_result_ledger|criterion_id
object|pre_result_ledger|expected_count
object|pre_result_ledger|key_ledger_sha256
object|pre_result_ledger|observed_count
object|pre_result_ledger|omission_blocker
object|pre_result_ledger|partition
object|rational_over_sqrt_v1|absolute_denominator
object|rational_over_sqrt_v1|absolute_numerator
object|rational_over_sqrt_v1|kind
object|rational_over_sqrt_v1|scale_squared_denominator
object|rational_over_sqrt_v1|scale_squared_numerator
object|rational_v1|denominator
object|rational_v1|kind
object|rational_v1|numerator
object|raw_d9a_value_v1|canonical_raw_rows_sha256
object|raw_d9a_value_v1|case_identity
object|raw_d9a_value_v1|failing_row_count
object|raw_d9a_value_v1|kind
object|raw_d9a_value_v1|maximum_row_sum_residual
object|raw_d9a_value_v1|raw_invariant_state
object|report|artifacts
object|report|authority
object|report|binaries
object|report|checkpoint
object|report|criteria
object|report|d12_artifact
object|report|identity
object|report|matrix
object|report|verdict
object|result_ledger_artifact|availability
object|result_ledger_artifact|byte_length
object|result_ledger_artifact|record_count
object|result_ledger_artifact|relative_path
object|row_signature_pair_v1|cache_disabled_sha256
object|row_signature_pair_v1|kind
object|row_signature_pair_v1|serial_cache_sha256
object|row_signature_pair_v1|source_count
object|row_target|first_derivative
object|row_target|position
object|row_target|second_derivative
object|scalar_comparison_v1|absolute_error
object|scalar_comparison_v1|expected
object|scalar_comparison_v1|kind
object|scalar_comparison_v1|observed
object|serial_only_context|all_tsan_cell_count
object|serial_only_context|all_tsan_result_ledger_sha256
object|serial_only_context|all_tuple_keys_sha256
object|serial_only_context|cache_disabled_concurrency_cell_count
object|serial_only_context|cache_disabled_concurrency_ledger_sha256
object|serial_only_context|cache_disabled_concurrency_pass
object|serial_only_context|cache_disabled_tsan_pass
object|serial_only_context|cache_disabled_tsan_summary_cell_count
object|serial_only_context|cache_disabled_tsan_summary_sha256
object|serial_only_context|failure_records
object|serial_only_context|failure_records_sha256
object|serial_only_context|threaded_tsan_row_digest_cell_count
object|serial_only_context|threaded_tsan_row_digest_sha256
object|serial_only_context|threaded_tsan_summary_cell_count
object|serial_only_context|threaded_tsan_summary_sha256
object|serial_only_context|tuple_count
object|signed_dyadic_v1|denominator_power
object|signed_dyadic_v1|kind
object|signed_dyadic_v1|numerator_hex
object|signed_dyadic_v1|sign
object|source_binding|path
object|source_binding|sha256
object|structure_missing_anchor_v1|anchor_id
object|structure_missing_anchor_v1|anchor_present
object|structure_missing_anchor_v1|canonical_source_ids
object|structure_missing_anchor_v1|effective_coefficients
object|structure_missing_anchor_v1|expected_sum
object|structure_missing_anchor_v1|kind
object|structure_missing_anchor_v1|missing_anchor_source_id
object|structure_missing_anchor_v1|observed_sum
object|structure_missing_anchor_v1|provider_coefficient_bits
object|structure_missing_anchor_v1|provider_row_sha256
object|structure_missing_anchor_v1|source_count
object|structure_present_v1|anchor_id
object|structure_present_v1|anchor_present
object|structure_present_v1|canonical_source_ids
object|structure_present_v1|effective_coefficients
object|structure_present_v1|expected_sum
object|structure_present_v1|kind
object|structure_present_v1|observed_sum
object|structure_present_v1|provider_coefficient_bits
object|structure_present_v1|provider_row_sha256
object|structure_present_v1|source_count
object|unexpected_paths_target_v1|kind
object|unexpected_paths_target_v1|required_record_count
object|unexpected_paths_target_v1|sidecar
object|verdict|b3_unblocked
object|verdict|d9a_reopened
object|verdict|failed
object|verdict|far_selected
object|verdict|first_decisive_criterion
object|verdict|incomplete
object|verdict|omitted
object|verdict|production_authorized
object|verdict|qualification_decided
object|verdict|report_content_sha256
object|verdict|serial_only_qualification_eligible
object|verdict|serial_only_reason
object|verdict|status
object|verdict|threaded_only_failure_ledger_sha256
object|verdict|uncovered
object|worktree_observation|clean
object|worktree_observation|reason_code
object|worktree_observation|state
END anchored-row-result-evidence-schema-paths-v1
```

The later B2c implementation must embed the approved amendment Git commit and
this exact SHA-256. CI parses these bytes, independently derives the equivalent
required-object-member, ordered-array, criterion, ledger-partition, and frozen
authority lines from the executable schema, and requires exact set and byte
equality before expanding M01--M23. A missing or extra line on either side is a
test failure. Thus coordinated edits to the implementation schema and its test
generator cannot delete an approved path or criterion without disagreeing with
this already approved Markdown byte anchor.


## Required mutation matrix

The immutable mutation manifest ID is
`anchored-row-result-evidence-mutations-v1`. Its expansion is owned by this
approved documentation packet, not generated from the implementation schema.
The implementation report records the exact merged Git commit that contains
this amendment and the embedded documentation-owned path-anchor SHA-256 above.
CI independently compares the executable schema's object/array paths with
those already checked-in bytes; changing both code-owned files cannot change
the documentation-owned path universe or approved commit binding.

The following operators and operands are exact. `C` expands to all 32 criterion
ordinals/IDs in the approved anchor. `L` expands to its 34 literal pre-result
ledger lines. `O` expands to every literal `object` name in the anchor and
`R(O)` to that object's complete literal member lines. `A` expands to every
literal `array` line, and frozen-value mutations use every literal `authority`
line. The original-preflight paths needed by this amendment are duplicated in
the anchor deliberately, so no later code/schema pair decides the universe.

```text
M01 delete-required-object-member      for every O x R(O)
M02 add-unknown-object-member          for every O
M03 replace-required-type              for every O x R(O)
M04 insert-array-item                  for every A at first,middle,last
M05 delete-array-item                  for every nonempty A at first,middle,last
M06 duplicate-array-item               for every nonempty A at first,middle,last
M07 swap-adjacent-array-items          for every A with length >= 2 at first,middle,last
M08 criterion-id-position-count        for every C: wrong ID, wrong ordinal, count-1, count+1
M09 criterion-authority                for every C: expectation, applicability, target, allowed status, nullability
M10 ledger-slot                        for every L: wrong ID, wrong partition, wrong count, wrong key digest
M11 result-sidecar                     for every C: missing, extra, byte-length, record-count, SHA, trailing-byte
M12 result-record                      for every complete C: missing, extra, duplicate, reorder, key, outcome, exact_value, target, reason
M13 maximum-witness                    for every numeric C: noncorpus key, wrong record, wrong ordinal, wrong exact, wrong display bits, nonfirst tie
M14 merkle-proof                       for every numeric C: short, extra, wrong sibling, reversed direction, wrong index, padding index, wrong root
M15 first-failure                      for every FAIL-capable C: null, passing key, later failure, noncorpus key
M16 authority-value                    each six-row item, tolerance, each D10/component/D12 target, each dependency version, each anchor/relabel/level/order, each manifest/fixture/fingerprint field
M17 oracle-partition                   gap, overlap, outside-request, covered-as-uncovered, wrong reason, missing reason, uniform-as-primary, propagation gap, propagation extra, propagation wrong reason, propagation axis gap, propagation covered-partition drift
M18 basis-aggregation                  distributed per-source error, identity-only failure, reverse-only failure, rotate-only failure, signed coefficient, wrong inverse map, wrong group L1
M19 raw-D9a                            case state, case digest, failing-row count, 124 count, exact numerator, maximum bits, maximum witness
M20 D12-envelope                       malformed, duplicate-key, content hash, cross-head, dirty, old-B2, boolean-only, missing provenance, fingerprint, hosted-as-qualified, workload, reference digest, instrumentation, operational gap
M21 causality-verdict                  every legal/illegal group status, earlier/later blocker, FAIL precedence, ordered INCOMPLETE/UNCOVERED, all-PASS
M22 serial-only                        missing tuple, cache-disabled failure, output mismatch, nonrace failure, incomplete evidence, exact race-only eligibility
M23 canonical-encoding                 BOM, prefix, suffix, newline, non-JCS number, negative zero, nonfinite, duplicate JSON key
```

For `first,middle,last`, duplicates collapse only when the indices are equal;
the literal manifest records the remaining unique mutation once. Large ledgers
use deterministic representative ordinals `0`, `floor((N-1)/2)`, and `N-1`,
plus the maximum-witness and first-failure ordinals. M01--M03 remain exhaustive
over every required object path; the representative rule applies only to array
item mutations. The test suite asserts exact equality with the literal
manifest, not merely a count, and runs locally and in the single existing
exact-head hosted workflow.

## Authority boundary

Approval of this amendment authorizes only the evidence contract. It does not
authorize a B2c implementation or execution, qualify
`anchored_difference_rows_v1`, reopen D9a, unblock B3, select Far, decide D9b,
or authorize production. A later code-bearing B2c SHA still requires separate
implementation authorization, exact-head replay, technical/scientific/
gatekeeper PASS, and an explicit qualification decision.
