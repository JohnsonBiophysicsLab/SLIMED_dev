# Valence-5 OpenSubdiv Integration-Composition Diagnostic

This opt-in proof follows the valence-5 force diagnostic from PR #145. It
tests whether evaluating OpenSubdiv over SLIMED's positive-depth child domains
is sufficient to reproduce the existing `11 = 4+3+4` composition.

Run it with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
  scripts/run_irregular_valence5_opensubdiv_integration_composition.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper emits a successful machine-readable
skip. With the dependency present, the proof compares a
`20 x 6 x 3 x 7 x 12` tensor:

- 20 approved icosahedron faces;
- the ordered depth-one `M1`, `M2`, `M3` children followed by the depth-two
  `M1`, `M2`, `M3` children carried through `M4`;
- three frozen quadrature samples;
- seven SLIMED value/derivative rows; and
- 12 original fixture source IDs.

The production reporter constructs each row as
`shapeFunction * childToOriginal` using the current subdivision matrices and
aggregates duplicate one-ring slots by original source ID. The OpenSubdiv
probe evaluates the corresponding affine child domains, derives the face
orientation from production and Ptex source identities, and applies the full
first- and second-derivative chain rule. All six orientation permutations are
emitted, while the comparator selects the identity-bound permutation rather
than choosing the smallest numerical residual.

## Result

The child-domain assignment is correct, but composed-row parity still fails.
The maximum row difference is `0.7357563654581705` under the fixed reviewed
absolute tolerance `5e-6`. Even the position row differs by
`0.02817109760678843`, so this is not a derivative scaling or force-formula
artifact.

The proof also observes a potentially relevant extraordinary smooth-vertex
mask-policy difference:

- SLIMED uses `3/(8n)` for valence five, giving neighbor weight `0.075` and
  center weight `0.625`;
- OpenSubdiv uses its eigenvalue-derived Loop mask, giving neighbor weight
  `0.08409321892578289` and center weight `0.5795339053710855`.

The report binds those values to the current production matrix and the
OpenSubdiv probe. It also records the full residual location, per-row and
per-domain maxima, and the value-row domain residual matrix. This evidence
does not prove that aligning only this mask would eliminate every composed-row
residual. The report therefore emits
`mask_policy_causal_sufficiency_proven:false`, keeps the failed composed rows
as the route blocker, and records the mask difference only as an observed
diagnostic clue.

This is proof-only diagnostic evidence. It emits `not_production_routing:true`,
`production_route_enabled:false`, and `production_scatter_executed:false`.
Production valence-5 routing remains disabled.

The follow-up counterfactual capability diagnostic is now complete. It confirms
that OpenSubdiv's public Loop scheme API does not expose a custom extraordinary
smooth-mask override, so an otherwise identical evaluator-bound counterfactual
cannot be constructed without an explicitly reviewed custom-scheme or library
decision. No rows were edited after evaluation and no numerical equivalence was
claimed. Production routing remains disabled.
