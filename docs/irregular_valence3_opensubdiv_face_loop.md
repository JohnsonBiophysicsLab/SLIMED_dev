# Valence-3 OpenSubdiv Phase-3 Guarded Face Loop

Date: 2026-08-03

Status: integration-only and default-off. This route is not installed in
`Mesh::Compute_Energy_And_Force()` and is not authorized for Phase-4
activation.

## Accepted integration baseline

The Phase-3 continuation accepts the following narrow baseline for guarded
integration evidence:

- stock OpenSubdiv 3.7.0 Loop rows;
- adaptive isolation level 5;
- the exact oriented four-vertex/four-face tetrahedron provider contract;
- the ordered `N=2` three-sample quadrature plan and weights of `1/3`; and
- bending and global-area physics through the existing SLIMED membrane
  algebra.

The volume pairing is now explicit and conjugate for this exact Valence-3
lane. Phase 2 proved that the legacy x-only accumulator did not differentiate
to the existing force. The transaction now stages the rotationally invariant
full-divergence volume
`V = (1/6) sum_q w_q x_q . (x_v,q cross x_w,q)`, which is the functional
already differentiated by `Mesh::element_energy_force_regular()`. Nonzero
volume constraints are accepted and covered by the same source-keyed force
and finite-difference proofs. This decision is scoped to Valence 3; it does
not silently change established Valence-4/5 or CUDA volume semantics.

## Gates

Execution requires both:

1. `Valence3Phase3Request::scientificBaselineAcceptedExplicitRequest == true`;
2. the exact runtime token
   `SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3=1`.

The transaction then validates, in order:

- full-divergence volume-functional identity;
- exact quadrature order, ordered sample coordinates, and weights;
- the OpenSubdiv version, isolation level, topology, Ptex identity, and
  four-source boundary reported by the guarded row provider;
- stable face identity, source coverage, empty one-rings, coordinates, and
  source-keyed rows;
- staged per-face and global area/full-divergence-volume geometry;
- a complete scientific dry run using explicit `7 x 4` rows; and
- every destination required by the shared guarded production face loop.

Only after all preflight checks pass does it call
`execute_guarded_source_keyed_production_face_loop()`. The shared executor
revalidates the complete transaction immediately before its first write,
publishes the membrane completion phases, and preserves empty one-rings.
The internal accumulation seam now invokes the legacy 11/12-control routing
assertion only for ordinary calls. A complete guarded source-keyed call uses
its already validated original-source boundary, preventing an incorrect
fallback into the empty-one-ring legacy diagnostic while leaving default
routing unchanged.
The guarded branch also skips the unrelated regular-row cache lookup. The
executable proof sets `SLIMED_USE_OPENSUBDIV_REGULAR=1` during the Phase-3
transaction and requires complete success, proving that an inherited regular
route token cannot throw after guarded publication has begun.

Postconditions compare face normals, mean curvature, bending energy, and all
source-keyed bending/area/volume force components with the dry run at the
fixed non-overridable tolerance `1e-10`. A post-execution mismatch is a hard
runtime error, not an ordinary rejection.

## Negative contracts

The executable proof covers atomic rejection for:

- a missing explicit request;
- a missing or non-exact runtime token;
- dependency-disabled builds; and
- the closed mixed valence 3/4/5 fixture, which remains outside the exact
  tetrahedron provider.

For every ordinary rejection, the serialized Mesh state and one-rings are
unchanged.

## Route boundary

Even after a successful integration-only transaction, the result reports:

```text
production_route_enabled: false
default_evaluator_caller: false
production_one_rings_populated: false
phase4_activation_authorized: false
volume_functional_decision_pending: false
full_divergence_volume_validated: true
```

The Phase-3 transaction itself remains integration-only. Phase 4 installs a
separate exact-token caller without changing CUDA sources or checkpoint
format; see `docs/irregular_valence3_phase4_activation.md`.

## Phase-4 follow-up gates

- Complete the independent long-double oracle and refined quadrature study.
- Preserve serial/OpenMP repeat coverage for the actual production caller.
- Preserve output and checkpoint round-trip behavior for the tetrahedron.
- Decide whether the three-point rule is scientifically sufficient near four
  persistent valence-3 extraordinary vertices.
- Add a unified extraordinary-route selector before any default activation.

Until those gates are complete, rollback is simply removal of the Phase-3
runtime token; the default evaluator continues to reject the tetrahedron as
unsupported.
