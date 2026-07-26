# Valence-4 Production Kernel Call Proof

This review-gated lane moves only the proven backend-neutral source-keyed call
boundary from PR123 into an isolated production module:

- `include/energy_force/Source_keyed_kernel_call.hpp`;
- `src/energy_force/Source_keyed_kernel_call.cpp`.

The production helper accepts a complete variable-cardinality request
containing face identity, canonical orientation, original source IDs, seven
derivative rows per sample, and source-keyed `fBend`, `fArea`, and `fVolume`
contributions. It returns an owned canonical request or throws before returning
any partial output. A second helper returns an owned source-keyed force table.

The approved octahedron proof calls this production helper with fresh
OpenSubdiv rows. It demonstrates:

- exact source-ID permutation invariance;
- deterministic split/reversed duplicate derivative-row aggregation;
- duplicate topology and force source rejection;
- cardinality, coverage, nonfinite, orientation, mixed-row, and nonempty
  one-ring rejection;
- an independent fixed-index `6 x 9` and long-double force oracle with zero
  delta; and
- unchanged production `Face::oneRingVertices`, vertex forces, geometry, and
  OpenMP buffers.

Focused default GTests independently exercise the helper and a fixed-index
oracle without an OpenSubdiv dependency. The opt-in present-dependency harness
sets `production_kernel_call_helper_executed:true`.

## Exact Boundary

This is an actual call to a production helper, but it is not an actual
production force-path call:

```text
production_kernel_call_helper_executed: true
actual_production_force_path_executed: false
not_production_routing: true
production_route_enabled: false
```

The helper consumes force contributions already computed by the established
proof oracle. It does not duplicate or move the scientific force formulas.
The production mesh face loop does not call this helper.

The successor scientific force algebra lane invokes
`Mesh::element_energy_force_regular()` directly with the validated six-source
rows through an explicit variable-cardinality override while the default
production call remains 12-control. That successor remains proof-only:
production face-loop integration, serial/OpenMP observable parity, broader
valence, and route activation remain separate review boundaries.

No default dependency, Makefile, CI, verifier, formula, quadrature, scatter,
OpenMP scheduling/reduction, thread-buffer, checkpoint, output, propagation,
optimizer, boundary, fixture, or generated/vendor behavior changes in this
lane.
