# Valence-4 Production Route Preflight

This review-gated slice adds an inert production-facing preflight for the
approved closed valence-4 octahedron:

- `include/energy_force/Valence4_face_loop_route_preflight.hpp`;
- `src/energy_force/Valence4_face_loop_route_preflight.cpp`; and
- `tests/test_valence4_face_loop_route_preflight.cpp`.

The helper composes the existing guarded topology/source representation with
the production source-keyed adapter types. It returns an owned mapping package
for the approved eight-face, six-source topology while preserving the
reviewed `Face::oneRingVertices` boundary.

The preflight rejects unsupported topology before returning a route candidate.
The focused tests prove that the approved octahedron yields stable source
mapping views, those views can feed `prepare_source_keyed_kernel_call(...)`
with caller-provided rows and forces, and the default geometry/force route
still rejects because production one-rings remain empty.

This lane now also exposes an explicit route request boundary through
`evaluate_guarded_valence4_face_loop_route_request(...)`. The boundary is
review-gated and default-off: requests without
`reviewerApprovedExplicitRequest` are rejected before source-keyed
accumulation, while accepted requests only prepare caller-owned source-keyed
rows and accumulated forces. Acceptance additionally requires exactly three
samples per face, binding the request to the reviewed `8 x 3 x 7 x 6`
valence-4 evidence package; fewer or additional samples reject before any
prepared or accumulated output is returned. It does not install a default
evaluator caller, execute the production face loop, populate one-rings, or
mutate mesh force state.

The successor scientific-request boundary,
`evaluate_guarded_valence4_face_loop_scientific_request(...)`, remains
default-off behind the same explicit reviewer-approved request. It validates
the complete three-sample source-keyed row package before doing any scientific
work, reads coordinates from the real approved `Mesh`, and calls the existing
variable-cardinality `Mesh::element_energy_force_regular(...)` helper for each
face. The returned mean curvature, bending energy, normal, and source-keyed
`fBend`/`fArea`/`fVolume` contributions are caller-owned. Focused tests use a
fixture that owns the `Param` referenced by `Mesh`, prove finite nonzero
outputs, and verify that malformed late rows reject atomically.

## Boundary

This is production C++ structure, not production valence-4 force execution:

```text
production_route_preflight_helper_executed: true
explicit_route_request_boundary: true
default_off_request_rejected: true
reviewed_three_sample_cardinality_required: true
explicit_request_source_keyed_accumulation: true
scientific_request_boundary: true
production_scientific_algebra_executed: true
caller_owned_scientific_outputs: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_one_rings_populated: false
default_evaluator_callers: false
backend_neutral_opensubdiv_free: true
```

The helper does not call OpenSubdiv, `Mesh::Compute_Energy_And_Force()`, or
`accumulate_membrane_face_energy_and_forces(...)`. The scientific request
does call `Mesh::element_energy_force_regular()` with explicit
variable-cardinality shape rows, but it does not enter the real face loop or
scatter into `Vertex` force state. It leaves mesh-owned face observables,
one-rings, vertex forces, thread buffers, checkpoint/output state, propagation
state, and optimizer state unchanged.

## Residual Boundary

A real route remains a separate reviewer/user-gated implementation decision.
That successor must supply reviewed OpenSubdiv weighted samples through this
default-off request, then separately install source-keyed scatter through
original source IDs in the production OpenMP face loop. Route activation still
requires serial/OpenMP observable parity, unsupported-topology fallback, and a
fresh reviewer/user-gated decision.
