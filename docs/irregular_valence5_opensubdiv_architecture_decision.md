# Valence-5 OpenSubdiv Architecture Decision

## Scope

This proof/decision-only package records the bounded architecture state for the
approved closed valence-5 icosahedron after the PR #148 custom-scheme
feasibility result. It does not select an architecture, choose a scientific
mask, change dependency policy, patch or vendor a library, or enable a route.

The machine-readable report requires:

- `decision_selected:false`;
- `selected_option:null`;
- `scientifically_approved:false`;
- `dependency_policy_changed:false`;
- `library_patch_or_vendoring_performed:false`;
- `production_route_enabled:false`;
- `valence5_opensubdiv_route_enabled:false`; and
- `current_slimed_valence5_route_preserved:true`.

The current dependency-free SLIMED positive-depth valence-5 route is preserved
behavior. It is not a selected OpenSubdiv architecture and is reported as
`current_fallback_is_selected_opensubdiv_architecture:false`.

## Reviewed Facts

The decision report executes and binds the merged feasibility and force-parity
predecessors. Present-dependency mode requires:

- detected OpenSubdiv version `3.7.0` and
  `OPENSUBDIV_VERSION_NUMBER == 30700`;
- no public scheme-registration hook;
- no public custom Loop smooth-mask injection hook;
- no valid standalone public-extension path;
- zero evaluator-bound SLIMED custom-mask rows;
- `mask_policy_causal_sufficiency_proven:false`;
- the unchanged reviewed absolute tolerance `5e-6`;
- force parity still failing with maximum absolute residual
  `7.108303140663388`; and
- production and valence-5 OpenSubdiv route flags remaining false.

The exact public API blocker remains:

`OpenSubdiv 3.7.0 public Far/Sdc pipeline closes scheme selection over the fixed SchemeType set and exposes no custom Loop smooth-mask injection or scheme registration hook`.

The exact force-parity blocker remains:

`direct whole-Ptex OpenSubdiv rows do not match the existing positive-depth 11=4+3+4 force composition`.

## Ordered Options

The report contains exactly four options in order `A`, `B`, `C`, `D`. Every
option has `status:"unselected"` and none is preferred.

| ID | Unselected option | Bounded review requirement |
| --- | --- | --- |
| A | Hybrid preservation of the existing dependency-free SLIMED positive-depth valence-5 evaluator while retaining the guarded OpenSubdiv regular and canonical valence-4 routes. | Preserves current scientific semantics and dependency policy. Choosing it as an architecture still requires an explicit reviewer/user decision. |
| B | Adopt stock OpenSubdiv extraordinary semantics. | Requires separate scientific approval and complete force, energy, geometry, output, and serial/OpenMP re-baselining. |
| C | Patch, fork, or vendor OpenSubdiv. | Requires separate dependency-policy, maintenance, license, scientific, and full output re-baselining reviews. |
| D | Evaluate an alternate subdivision library. | Requires a new library feasibility lane before scientific, dependency-policy, or production claims. |

Missing, duplicate, unknown, reordered, selected, preferred, or implicitly
recommended options fail the report. Adversarial gates also reject scientific
approval, patch/vendor or alternate-library selection, dependency changes,
route activation, and removal of the current SLIMED fallback.

## Remaining Gate

The package stops at:

`explicit reviewer/user architecture selection; scientific approval and output re-baselining for changed semantics; dependency, maintenance, and license review for changed library policy`.

Dependency absence skips cleanly. Dependency presence reproduces the exact
four-option, no-selection decision. No option is approved or automatically
next, and valence-5 OpenSubdiv routing remains disabled.
