# B2c anchored-row qualification evidence

Status: **package implementation `INCOMPLETE`; all 20 oracle-independent
candidate criteria have exhaustive development evidence, but no qualification
result exists**

Candidate: `anchored_difference_rows_v1`

Approved B2b merge: `022df7a8e11bcc4aee4df2254cc994cf4efdeb4f`

## Scope and disposition

B2c's current partial implementation is isolated to the proof lane. It does not alter a provider row, fixture,
manifest, tolerance, production source, build route, B3 gate, D9a decision, or
Far disposition. The representation candidate has an actual binary64
executable with the frozen source order and observable subtraction,
multiplication, accumulation, and final-position round points. A separate
exact-dyadic boundary decodes each finite coefficient over `2^1074` and
certifies 544-bit MPFR lower/upper imports with `MPFR_RNDD` and `MPFR_RNDU`.

The repository still has no independently certified primary Stam
eigenanalysis implementation and no independent uniform-subdivision
cross-check implementation capable of serving the complete frozen oracle
request ledger. The pre-existing B2 `stam_oracle.cpp` only tests directed MPFR
primitives; P9 stopped B2 before such an oracle was implemented. B2c does not
rename that primitive test or the new exact-dyadic boundary as a scientific
oracle. Its capability result is explicitly:

```json
{"coverage":"UNCOVERED","implementation_state":"INCOMPLETE","kind":"independent_primary_capability","missing_algorithms":["stock_mask_interval_matrix_construction","interval_eigenpair_krawczyk_certification","repeated_eigenspace_spectral_projector_certification","quartic_box_spline_interval_evaluation","certified_parametric_branch_mapping","independent_uniform_five_depth_intersection"],"reason_code":"EIGENBASIS_CERTIFICATION_FAILED","status":"honest_incomplete","uniform_success_substituted_for_primary":false}
```

The checked-in runner therefore self-identifies as
`INCOMPLETE_MISSING_ORACLE_DEPENDENT_CELL_EXECUTION_D12_EXECUTION_AND_PRIMARY_STAM_UNIFORM_ORACLES`. Its
incomplete implementation report cannot be interpreted as a candidate `FAIL`,
a qualification `PASS`, a completed B2c execution, or evidence for a different
route.

## Report and failure semantics

The proof report uses schema ID
`anchored-row-qualification-report-v1`. The checked-in executable JSON Schema
closes every report object, freezes all 32 criterion IDs, and includes
state-conditioned availability, Git identity, dependency provenance,
scientific-key, and D12-operational-key definitions. The validator additionally
enforces:

- duplicate-key, extra-key, missing-key, wrong-type, nonfinite-number, and
  negative-zero rejection;
- RFC 8785 canonical bytes and the zeroed-field report-content SHA-256 rule;
- exact integer accumulation and anchor-only effective-coefficient change;
- all three fixed anchor identities and the identity/reverse/rotate relabel
  vocabulary;
- exact scientific and operational key arity, enums, and criterion-specific
  nullable dimensions;
- 294 artifact slots, 196 Bfr cases, 98 Far inventory-only cases, 98 Bfr
  cache pairs, 1,386,000 raw rows, 4,158,000 anchor views, 12,549,936 provider
  terms, and 37,649,808 anchor-term views; and
- deterministic `FAIL`/`INCOMPLETE`/`PASS` precedence with all decision and
  activation fields fixed false.

No unavailable value receives an invented all-zero hash. The report binds an
unavailable dependency or executable through its closed state/reason object.

## Execution

The representation binary exposes fail-closed exhaustive audit streams. For
every validated Bfr row it checks all three oriented-corner
anchors, both frozen rank relabelings plus identity, and the five frozen
constant fields through the actual emitted evaluator. Exact structural sums
and inverse-relabeled effective coefficients use a fixed 34-limb signed integer
with 2,176 bits of bounded headroom over the common `2^1074` denominator.
Exact coefficient-coordinate products and normalized component-target
comparisons use a separate proof-only unsigned-magnitude integer whose only
operations are addition, subtraction, multiplication, shifts, and comparison;
the emitted evaluator itself remains the frozen binary64 implementation.
Before numeric-ID arithmetic is used for the two rank bijections,
the validator proves that each fixture's vertex IDs are exactly the ascending
contiguous rank list `0..N-1`.

The validator streams complete canonical scientific keys directly into four
SHA-256 ledgers, rejects a duplicate or non-increasing key, and never retains
the tens of millions of keys in memory. A development replay over the
available, fully revalidated 294-artifact old-head corpus executed these
bounded criteria in about 95 seconds and produced:

| Criterion | Cells | Failures | Canonical ledger SHA-256 |
| --- | ---: | ---: | --- |
| `representation_structure` | 4,158,000 | 0 | `3132ed72dfd9e1818fe494e360f02f498d89b18c1ff75945d03922e133e9f494` |
| `constant_field_bits` | 62,370,000 | 0 | `dec2bf982174967694ef52def124ffdc82d3b52952a314b4e9c6fec6d7fcde4d` |
| `relabel_exact_effective_coefficients` | 8,316,000 | 0 | `575e2227bf3d5ac5d4ee62fb0221bbbc82150632419cb3d8c79a30410156c138` |
| `cache_mode_bit_identity` | 2,079,000 | 0 | `a8c2c2bad40d685a8f0804791a1a49bd719aebba119f90e214b06cb360597411` |

The same development replay executed the four exact regular-box-spline gates
with no failures:

| Criterion | Cells | Failures | Maximum absolute error | Canonical ledger SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `regular_analytic_exact_rows` | 152,640 | 0 | `4.0438331695548237e-16` | `fb3aa638476c8fb51b6420b74332b8f47ce17b8041251fdf7c9ce350fb4777e2` |
| `regular_analytic_emitted_geometry` | 457,920 | 0 | `1.1932044959398847e-15` | `7ad97040ed0a6bf8b44c04eec43690a5fd7bc086f51592cfef5f18c4f5427ef3` |
| `regular_analytic_area_integrand` | 50,880 | 0 | `1.164920199724114e-15` | `19752de9524c3dda9b07671bfb7c504896e2ab6d748fb624dddf1ebb9b7d0fbc` |
| `regular_analytic_legacy_volume_integrand` | 50,880 | 0 | `3.277470150033568e-15` | `ccb982f45e38cc44f38949c4de391646979d311348fe6fb1580d7e7e3c9a5a81` |

The compact exact component audit processed 396,000 paired high-level rows in
about 102 seconds. It did not emit or reparse the 10,757,088 basis probes or
the geometry values: the actual binary64 evaluator accumulated the frozen
comparisons internally, while the validator independently materialized the
complete canonical pre-result ledgers. All 12 component criteria passed:

| Criterion | Cells | Failures | Maximum normalized error | Canonical ledger SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `anchor_sensitivity_exact_coeff` | 1,188,000 | 0 | `4.073848235749272e-11` | `e8eac011dfcf7f383afca576fa59c18ce996588a4a502a56b89739bcb6b41ba1` |
| `anchor_sensitivity_exact_geometry` | 3,564,000 | 0 | `2.0293204775959214e-11` | `c809d3379479a88a34ff47d38c380ee7b5c0705d6fca6dc418a73bd08320048d` |
| `anchor_sensitivity_emitted_geometry` | 3,564,000 | 0 | `2.029310053330846e-11` | `7130d508a75052f306909c33fad50b7e0dbb8825dbb5ee1f181ced33abf541dd` |
| `binary64_basis_probe_diagnostic` | 10,757,088 | 0 | `1.2859052811822237e-14` | `86e9a5a1d01eace5f5185e17b916d7452787e8ba11547abb4e53b3e2bd235b53` |
| `binary64_direct_geometry_fidelity` | 10,692,000 | 0 | `1.5825605585155187e-14` | `2f8775b6e54fb0b27fb5039f457a2164191f12613c4ff2388c6f591ffe4e203d` |
| `relabel_emitted_geometry_fidelity` | 7,128,000 | 0 | `1.5083718607505153e-14` | `4a9f7756f530db8a728fcbbcba97da13a645399c94fc76b49251fa9e09d9e699` |
| `stabilization_6_7_exact_coeff` | 594,000 | 0 | `0` | `fe9f4cdba31f25473f88f208a84c7b25100637b3e61f738af901fd486a6e5e98` |
| `stabilization_6_7_exact_geometry` | 1,782,000 | 0 | `0` | `91b3bfca62a6520582f55f0fb34f36e6d66dec526a5db80e4a1ad6a5e374814d` |
| `stabilization_6_7_emitted_geometry` | 1,782,000 | 0 | `0` | `787ffc4ca3c80f7988a5f6bb7a7cbe877f9dedd065dca060397046746a25d465` |
| `stabilization_7_8_exact_coeff` | 594,000 | 0 | `0` | `550e3c702901bd7f12a8d76c9218f702212b9ad84bd7b1c5350fe9d5059e6ebe` |
| `stabilization_7_8_exact_geometry` | 1,782,000 | 0 | `0` | `902dd1994133ddeaad38c9613cdf6494930990cde77a5cb1cb60f52350990549` |
| `stabilization_7_8_emitted_geometry` | 1,782,000 | 0 | `0` | `faca0c20efbd651c3b88fe22ee03ee51a68241528d8fc207db688db7d1f30276` |

These are development replay results, not exact-head B2c qualification
evidence. The dedicated workflow regenerates them from its freshly validated
exact-head artifacts; no checked-in digest is accepted as a substitute.

The dedicated existing workflow builds the candidate and exact-dyadic
boundary with pinned Apple Clang, `-fno-fast-math`, and `-ffp-contract=off`
after the frozen GMP 6.3.0, MPFR 4.2.2, and OpenSubdiv 3.7.0 inputs are
provisioned. It then revalidates the complete B2 checkpoint and all 294
artifacts, reproduces the raw D9a observation, writes canonical B2c evidence,
and asserts that the only permitted current disposition is implementation
`INCOMPLETE`. It publishes explicit unavailable cell-ledger partitions and the
exact causal validator blocker; it does not label unconstructed oracle request
cells `COVERED` or `UNCOVERED`.

Hosted macOS D12 evidence remains `UNQUALIFIED_PLATFORM`; it cannot pass or
fail the frozen physical-host numeric budgets. The workflow publishes raw
evidence and does not automatically select, qualify, or activate anything.

## Required next scientific work

A source audit identified [Jos Stam's official exact-evaluation
distribution](https://www.dgp.toronto.edu/~stam/reality/Research/SubdivEval/index.html)
(`lpdata50.dat`, `lpdata50NT.dat`, and `lptest.c`) and the Loop evaluation
paper's [analytic eigenstructure and quartic box-spline
appendices](https://www.research.autodesk.com/app/uploads/2023/03/evaluation-of-loop-subdivision.pdf_recTbaWEwaYZLjOEo.pdf).
Those
materials are useful only as floating seeds and external cross-checks under the
frozen B2b independence rules. They do not supply the required
repository-constructed stock Loop subdivision matrices, 544-bit interval
eigenpair isolation, Krawczyk inclusions, repeated-eigenspace spectral
projectors, interval-certified branch ordering and parameter maps, or the
independent uniform-refinement five-depth intersection certificates. No code
in this package fabricates those certificates from the published floating
tables.

A corrective implementation still needs exact-head execution of the five D12
criteria on the frozen qualified physical host. It also needs to implement and
independently audit the complete
frozen primary Stam eigenanalysis and uniform-refinement cross-check before
oracle-dependent B2c cells can execute. That work may not reuse candidate
arithmetic, link the row provider, substitute Far, widen a target, change the
frozen corpus, or infer qualification from the present `INCOMPLETE` report.
It requires a new exact-SHA review of the resulting implementation and evidence.
