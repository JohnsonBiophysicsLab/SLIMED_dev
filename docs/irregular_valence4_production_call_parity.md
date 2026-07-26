# Valence-4 Production-Call Boundary Proof

This proof-only lane combines the guarded canonical valence-4 topology/source
representation with OpenSubdiv rows generated in the same opt-in process.
It validates the exact tensor shape `8 faces x 3 samples x 7 rows x 6 sources`,
finite coefficients, duplicated mixed rows, canonical face orientation, and
original source IDs `[0,1,2,3,4,5]`.

The standalone harness then enters the real production
`Mesh::Compute_Energy_And_Force` boundary. Production rejects the unsupported
zero-one-ring topology before changing face geometry or vertex force state.
This is a binding negative result, not production valence-4 force execution.

## Evidence

- the approved octahedron is loaded through production mesh setup;
- `build_guarded_valence4_topology_source_mapping` supplies the source table;
- a separate canonical orientation oracle checks all eight faces;
- a fixed-index sentinel oracle checks the six-source, nine-component layout;
- fresh OpenSubdiv rows are consumed rather than replaying stored proof output;
- orientation and nonempty-one-ring mutations are rejected;
- production `Face::oneRingVertices` remain empty; and
- the production entry point rejects before mutation with its existing
  broader-valence diagnostic.

The dependency-absent path skips cleanly. OpenSubdiv availability alone never
changes default or runtime production behavior.

## Boundary

The report states:

- `proof_only:true`;
- `not_production_routing:true`;
- `production_route_enabled:false`; and
- `actual_production_force_path_executed:false`.

The proof does not pad six sources into the 12-control regular kernel, populate
`Face::oneRingVertices`, change formulas or scatter, change OpenMP scheduling
or reduction, alter fixtures, or change default dependency/build behavior.

The remaining production blocker is a separately reviewed variable-cardinality
source-keyed kernel adapter. It must accept backend-neutral weighted samples
and return source-keyed local forces without reusing the 11/12-control
`Face::oneRingVertices` contract. Real production serial/OpenMP observable
parity and guarded route activation remain later reviewer/user-gated steps.
