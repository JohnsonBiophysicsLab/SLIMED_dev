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

## Boundary

This is production C++ structure, not production valence-4 force execution:

```text
production_route_preflight_helper_executed: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_one_rings_populated: false
default_evaluator_callers: false
backend_neutral_opensubdiv_free: true
```

The helper does not call OpenSubdiv, `Mesh::element_energy_force_regular()`,
`Mesh::Compute_Energy_And_Force()`, or
`accumulate_membrane_face_energy_and_forces(...)`. It does not mutate
`Mesh`, `Face`, `Vertex`, thread buffers, checkpoint/output state,
propagation state, or optimizer state.

## Residual Boundary

A real route remains a separate reviewer/user-gated implementation decision.
That successor must supply backend-neutral weighted samples and source-keyed
forces, invoke the approved variable-cardinality scientific algebra, scatter
through original source IDs in the production OpenMP face loop, preserve
default-off behavior, and prove serial/OpenMP observable parity before route
activation can be described as production-ready.
