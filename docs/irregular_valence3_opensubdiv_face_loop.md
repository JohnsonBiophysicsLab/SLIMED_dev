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

This is not an acceptance of the current volume pairing. Phase 2 proved that
the legacy x-only volume accumulator and the full-divergence-derived volume
force are not conjugate. The Phase-3 transaction therefore requires
`uVol == 0` and rejects a nonzero volume constraint before executing the row
provider or writing any Mesh state. The legacy volume geometry is still
staged and reported so its behavior remains observable, but its energy and
force contribution is disabled.

## Gates

Execution requires both:

1. `Valence3Phase3Request::scientificBaselineAcceptedExplicitRequest == true`;
2. the exact runtime token
   `SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3=1`.

The transaction then validates, in order:

- zero volume-constraint strength;
- exact quadrature order, ordered sample coordinates, and weights;
- the OpenSubdiv version, isolation level, topology, Ptex identity, and
  four-source boundary reported by the guarded row provider;
- stable face identity, source coverage, empty one-rings, coordinates, and
  source-keyed rows;
- staged per-face and global area/legacy-volume geometry;
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

Postconditions compare face normals, mean curvature, bending energy, and all
source-keyed bending/area/volume force components with the dry run at the
fixed non-overridable tolerance `1e-10`. A post-execution mismatch is a hard
runtime error, not an ordinary rejection.

## Negative contracts

The executable proof covers atomic rejection for:

- a missing explicit request;
- a missing or non-exact runtime token;
- a nonzero volume constraint;
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
volume_functional_decision_pending: true
```

No production caller, CUDA source, checkpoint format, or mixed-valence
dispatcher is changed by Phase 3.

## Remaining work before Phase 4

- Select a single volume functional and prove energy/force conjugacy.
- Complete the independent long-double oracle and refined quadrature study.
- Add serial/OpenMP repeat coverage for the actual Phase-3 transaction.
- Verify output and checkpoint behavior for the tetrahedron transaction.
- Decide whether the three-point rule is scientifically sufficient near four
  persistent valence-3 extraordinary vertices.
- Add a unified extraordinary-route selector before any default activation.

Until those gates are complete, rollback is simply removal of the Phase-3
runtime token; the default evaluator continues to reject the tetrahedron as
unsupported.
