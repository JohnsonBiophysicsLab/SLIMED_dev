# Valence-5 OpenSubdiv Extraordinary-Mask Counterfactual Capability

This opt-in proof follows the integration-composition diagnostic from PR #146.
It asks whether the installed OpenSubdiv public API can construct an
evaluator-bound counterfactual that differs only in the valence-5 extraordinary
smooth-vertex mask.

Run it with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
  scripts/run_irregular_valence5_opensubdiv_mask_counterfactual.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper emits a successful machine-readable
skip. With the dependency present, it first reruns the complete
`20 x 6 x 3 x 7 x 12` integration-composition baseline. That independently
binds all 30,240 finite components, the six child domains, source/orientation
identity, the fixed non-overrideable `5e-6` policy, and the observed masks:

- SLIMED neighbor/center weights: `0.075` / `0.625`;
- OpenSubdiv neighbor/center weights:
  `0.08409321892578289` / `0.5795339053710855`.

## Capability Result

OpenSubdiv 3.7.0 public `Sdc::Options` exposes only vertex-boundary,
face-varying, creasing, and Catmark triangle-subdivision setters. It exposes no
custom Loop extraordinary smooth-mask setter. The standard Loop weights are
computed inside `sdc/loopScheme.h`; the diagnostic independently recomputes
the installed formula and requires it to reproduce the exact observed
OpenSubdiv weights above.

Consequently, no independent counterfactual refiner, patch table, stencil
storage, or 30,240-component row tensor can be constructed through the public
API. The report deliberately emits `counterfactual.row_parity_passed:null`
rather than editing completed rows or claiming numerical equivalence. A
binding adversarial gate attempts a reporting-only replacement with the
SLIMED mask and requires rejection before any counterfactual rows exist.

The exact blocker is:

`OpenSubdiv public Loop scheme does not expose a custom extraordinary smooth-mask override`

This result does not establish whether mask alignment is causally sufficient.
It records `mask_policy_causal_sufficiency_proven:false`,
`scientifically_approved:false`, `not_production_routing:true`, and
`production_route_enabled:false`.

The remaining boundary is an
`explicitly reviewed custom OpenSubdiv Loop scheme or library decision`. That
decision could involve a supported upstream
extension, a separately maintained custom evaluator, or a reviewed library
patch. This proof does not authorize vendoring, patching OpenSubdiv, changing
production formulas, or enabling valence-5 routing.
