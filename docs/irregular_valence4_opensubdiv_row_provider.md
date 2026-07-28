# Guarded Valence-4 OpenSubdiv Row Provider

This lane adds the smallest missing production-route prerequisite after the
production caller completion shadow. It does not activate a route.

## Why the provider comes first

The merged caller shadow already exercises the exact post-membrane completion
phase used by `Mesh::Compute_Energy_And_Force()`, including atomic publication,
regularization, total forces, total energy, and boundary handling. Adding
another caller before production can generate its own valence-4 rows would
still leave the caller dependent on proof-provided input.

The smaller truthful prerequisite is therefore a guarded production
OpenSubdiv row provider. `build_guarded_opensubdiv_valence4_rows(...)` returns
only backend-neutral `SourceKeyedFaceRows`; no OpenSubdiv type crosses the
header boundary.

## Guarded contract

The provider:

- rejects unless `reviewerApprovedExplicitRequest` is true;
- rejects explicit requests in dependency-free builds;
- consumes the reviewed canonical topology/source mapping;
- requires exactly eight Ptex faces in canonical production face order;
- generates original-source rows through
  `Far::LimitStencilTableFactoryReal<double>`;
- uses the frozen three-sample triangular plan
  `(v,w) = (1/6,1/6), (1/6,4/6), (4/6,1/6)`;
- emits seven rows in value, `dv`, `dw`, `dvv`, `dww`, `dvw`, `dwv` order,
  with OpenSubdiv `duv` duplicated into both mixed rows;
- aggregates every stencil by exact original source ID `[0..5]`;
- validates the complete `8 x 3 x 7 x 6` finite tensor before returning it;
- requires every value row to preserve partition of unity and every
  derivative row to sum to zero within `1e-12`;
- returns an empty row package on every rejection; and
- never mutates `Mesh`, populates `Face::oneRingVertices`, invokes the
  production face loop, or enables routing.

Default builds compile the deterministic OpenSubdiv-free rejection stub. The
OpenSubdiv implementation is compiled only under the existing
`USE_OPENSUBDIV_REGULAR=1` and `OPENSUBDIV_ROOT=...` build gate; this lane adds
no build target, dependency, vendor source, or ambient runtime behavior.

## Evidence

The present-dependency wrapper builds the provider through the existing
OpenSubdiv gate and compares all 1,008 double-precision coefficients against
the separately generated, previously reviewed float force-proof tensor. This
is a compatibility comparison, not an exact independent oracle: strict
constant-field invariants guard the double rows, while the cross-precision
comparison uses the existing `5e-6` parity policy.

```text
exact_tensor_shape: 8x3x7x6
sample_and_face_identity_match: true
provider_row_precision: double
comparison_reference: reviewed float force-proof rows
max_abs_difference_vs_reviewed_float_force_proof: 7.55e-7
constant_field_invariant_tolerance: 1e-12
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_one_rings_populated: false
```

Focused C++ tests bind the default-off and dependency-absent behavior, complete
present package, mixed-row identity, canonical source coverage, topology-drift
rejection, empty one-rings, and unchanged mesh coordinates.

## Remaining boundary

The next separate reviewer/user-gated unit is a guarded real production
face-loop caller that obtains rows from this provider and runs the already
reviewed atomic scientific/publication/completion path. This provider does not
authorize that caller or route activation. Default dependency behavior,
broader valence, formulas, scatter semantics, OpenMP reductions,
checkpoint/output, and propagation remain unchanged.
