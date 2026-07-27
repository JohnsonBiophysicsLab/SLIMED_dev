# Valence-4 Production-Shaped Scatter Buffer

This review-gated lane connects the guarded valence-4 scientific request to a
backend-neutral, caller-owned force-buffer contract. It does not install a
production route.

## Contract

`scatter_source_keyed_face_forces_to_component_buffer(...)` consumes one
validated source-keyed face contribution and writes into the current
production-shaped layout:

```text
source_id * 9 + force_kind * 3 + axis
```

`reduce_source_keyed_force_component_buffers(...)` validates every buffer and
reduces them in ascending buffer order, matching the current production
thread-buffer reduction order. Both helpers reject malformed cardinality,
duplicate or out-of-range source IDs, and nonfinite inputs. Scatter updates are
staged before publication, so rejection leaves the caller buffer unchanged
without copying the complete vertex buffer for every face.

The scatter and reduction helpers own no storage and do not inspect OpenMP
state or `Mesh`. Their guarded publication successor validates a complete
reduced source vector and every destination before overwriting only
`forceCurvature`, `forceArea`, and `forceVolume`. It requires empty production
one-rings and leaves `forceTotal` and all other mesh state unchanged.

## Evidence

The OpenSubdiv-present source-keyed adapter proof feeds fresh `8 x 3 x 7 x 6`
rows through the guarded scientific request, then passes its prepared
source-keyed forces through the new component-buffer helpers. The reduced
result matches the independent source-force reference under `1e-12`.

The existing production-topology/OpenMP shadow now invokes the same scatter
helper inside actual OpenMP teams of `1`, `2`, `3`, `4`, and `8` threads and
uses the same reduction helper afterward. Five repeats per team remain stable.
The independent sentinel oracle reads raw caller-owned thread-buffer slots with
its own destination expression, preventing matching helper index mistakes from
creating a false green.

## Boundary

```text
proof_only: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_vertex_force_state_mutated: true
production_face_loop_executed: false
```

No OpenSubdiv type enters the helper API. Default dependency/build behavior,
the existing production face loop, formulas, quadrature, OpenMP scheduling and
reductions, checkpoint/output, propagation, fixtures, and broader-valence
routing are unchanged.

The reviewed successor publishes only the three membrane-force families on
disposable approved state. The remaining step is atomic face-observable and
geometry publication, followed by a separately reviewed real face-loop
integration and full serial/OpenMP observable parity before route activation.
