# Valence-5 OpenSubdiv Custom-Scheme Feasibility

This proof-only decision diagnostic follows the PR #147 mask-counterfactual
capability result for the approved closed valence-5 icosahedron. It answers a
narrow architecture question: can a standalone non-production adapter use the
installed OpenSubdiv 3.7.0 public API to generate evaluator-bound rows with
SLIMED's valence-5 extraordinary smooth mask, without patching or vendoring the
library and without replacing completed rows?

Run it with:

```console
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
  scripts/run_irregular_valence5_opensubdiv_custom_scheme_feasibility.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper emits a successful machine-readable
skip. With the dependency present, it reruns the evaluator-bound predecessor,
keeps the fixed non-overrideable `5e-6` policy, and inspects only the installed
public Far/Sdc headers.

## Result

No valid standalone public-extension path exists in the reviewed API.
`Sdc::SchemeType` is closed over `SCHEME_BILINEAR`, `SCHEME_CATMARK`, and
`SCHEME_LOOP`; `Sdc::Scheme<SCHEME_TYPE>` dispatches through that type;
`TopologyRefiner` and `TopologyRefinerFactory` accept the fixed scheme type and
`Sdc::Options`; and the public surface exposes neither custom scheme
registration nor custom smooth-mask injection. Loop's smooth mask remains a
fixed `Scheme<SCHEME_LOOP>` specialization.

The exact blocker is:

`OpenSubdiv 3.7.0 public Far/Sdc pipeline closes scheme selection over the fixed SchemeType set and exposes no custom Loop smooth-mask injection or scheme registration hook`

The report therefore requires
`valid_standalone_public_extension_path_exists:false`,
`custom_scheme_adapter_constructed:false`,
`evaluator_bound_slimed_mask_rows_generated:false`, and an evaluator-bound row
count of zero. Adversarial gates reject a fabricated public extension,
post-hoc or JSON-only row substitution, a scientific mask choice, and a
library patch or vendoring request.

## Bounded Options

The decision package records, but does not select, these options:

- a public non-production OpenSubdiv extension adapter is blocked by the
  installed API;
- a standalone custom evaluator would not be an OpenSubdiv evaluator-bound
  public-extension counterfactual and needs separate architecture and
  scientific review;
- a fork, patch, or vendored OpenSubdiv build is outside the approved
  dependency policy;
- adopting the standard OpenSubdiv mask requires a scientific decision; and
- keeping valence-5 production routing disabled is the current truthful state.

This diagnostic does not establish mask causality, choose between SLIMED and
standard OpenSubdiv mask semantics, or approve a route. It keeps
`mask_policy_causal_sufficiency_proven:false`,
`scientifically_approved:false`, `not_production_routing:true`, and
`production_route_enabled:false`.

The remaining boundary is a
`separately reviewed custom-scheme or library architecture decision; production valence-5 routing remains disabled`.
