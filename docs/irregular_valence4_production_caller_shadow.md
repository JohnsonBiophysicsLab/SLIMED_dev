# Valence-4 Production Caller Completion Shadow

This review-gated lane exercises the approved closed valence-4 octahedron at
the production caller's post-membrane timing boundary. It remains an explicit
shadow and does not install a production route.

## Shared production phase

`Mesh::complete_energy_force_after_membrane_accumulation()` contains the
unchanged completion block formerly inline in
`Mesh::Compute_Energy_And_Force()`:

1. regularization energy and force;
2. per-vertex total-force publication;
3. per-face and global energy totalization;
4. optional scaffolding energy and force; and
5. boundary and ghost force handling.

The production evaluator calls this helper at the same location, immediately
after the existing membrane face accumulation. Formula order, force scatter,
OpenMP reductions, scaffold timing, and boundary handling are unchanged.

## Guarded shadow

`evaluate_guarded_valence4_production_caller_shadow(...)` is default-off and
requires an explicit reviewer-approved request. Before the first write it:

- validates the complete `8 x 3 x 7 x 6` source-keyed row package;
- stages all eight faces' area and current legacy visible volume;
- evaluates the unchanged scientific algebra against staged global area and
  volume;
- validates all eight current force destinations, finite reference
  coordinates, eight face identities, and empty production one-rings.

Only after no-write validation succeeds does the shadow clear current force
and face-energy state, atomically publish the reviewed geometry/scientific
transaction, and invoke the exact shared production completion phase.
Malformed input is rejected before clearing current state.

The approved physical stand-in initializes each vertex reference coordinate
from its current coordinate before regularization, matching the production
precondition rather than skipping the regularization phase.

## Evidence

The focused C++ tests require:

- default-off and malformed-row rejection before any clear or mutation;
- malformed completion-only force destinations and reference coordinates to
  reject before any clear or mutation;
- stale current thickness force and face energy to be cleared;
- exact per-vertex total-force recomposition;
- exact per-face and global total-energy recomposition;
- unchanged coordinates and empty `Face::oneRingVertices`; and
- all route and real-face-loop flags to remain false.

The OpenSubdiv-present wrapper compiles serial and OpenMP binaries from the
same production sources. It requires caller-shadow total force and total
energy parity within `1e-12`, in addition to the existing membrane,
face-observable, geometry, and independent OpenMP reduction evidence.

```text
production_caller_completion_shadow_executed: true
production_caller_shadow_cleared_stale_state: true
production_caller_shadow_totals_consistent: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
```

This does not approve a real production face-loop caller or valence-4 route.
The next boundary is a separate reviewer/user decision on guarded route
activation. Default dependency behavior, broader-valence routing, production
formulas, scatter semantics, OpenMP reduction policy, checkpoint/output, and
propagation remain unchanged.
