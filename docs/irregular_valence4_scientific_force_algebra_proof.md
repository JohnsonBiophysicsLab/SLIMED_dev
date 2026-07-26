# Valence-4 Scientific Force-Algebra Proof

This review-gated successor to PR124 invokes the existing production scientific
force algebra with validated variable-cardinality rows. It does not copy,
replace, or alter the bending, area, or volume formulas.

`Mesh::element_energy_force_regular()` previously carried three internal
12-row allocations and a 12-iteration force loop even though its explicit
shape-function override already accepts a `7 x N` row matrix. This lane makes
those allocations and that loop use the supplied control-point cardinality.
Variable cardinality is accepted only when an explicit override is present,
and force-output dimensions must match exactly. The normal production call
continues to use twelve controls and its existing behavior.

The approved closed valence-4 octahedron proof:

- loads fresh OpenSubdiv `8 x 3 x 7 x 6` rows;
- canonicalizes them by original source ID through
  `prepare_source_keyed_kernel_call()`;
- invokes `Mesh::element_energy_force_regular()` on each face with six
  coordinates and three explicit seven-row samples;
- compares every source component of `fBend`, `fArea`, and `fVolume` against
  the independent force-formula proof; and
- requires finite, nonzero evidence for all three force kinds.

The proof reports:

```text
existing_scientific_force_algebra_invoked: true
scientific_force_algebra_function: Mesh::element_energy_force_regular
scientific_force_algebra_variable_cardinality: 6
actual_production_force_path_executed: false
not_production_routing: true
production_route_enabled: false
```

The real production face loop is unchanged. It does not recognize six-control
faces, populate `Face::oneRingVertices`, scatter these forces to vertices, or
write OpenMP thread buffers. Default builds remain OpenSubdiv-free.

## Residual Boundary

The next separately reviewed boundary is a production-shaped face-loop shadow
that consumes the guarded topology/source representation, invokes this
scientific algebra, and compares serial/OpenMP energy, force, normal, area, and
volume observables without enabling routing. Guarded route activation, broader
valence, formulas, reductions, checkpoint/output, and propagation remain
unapproved.
