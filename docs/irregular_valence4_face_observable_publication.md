# Valence-4 Face-Observable Publication

This review-gated lane adds the face-state publication boundary that follows
the guarded vertex-force publication. It remains default-off and does not
install or execute the valence-4 production route.

## Contract

`publish_valence4_face_scientific_observables_to_faces(...)` receives one
caller-owned scientific result for every production face. Before the first
write it requires:

- exact face cardinality and source face-index coverage;
- stable `Face::index` identity;
- finite mean curvature, bending energy, and normal components; and
- empty production `Face::oneRingVertices`.

The helper canonicalizes input by face index and allocates every replacement
`3 x 1` normal before the first mesh write. It then overwrites only:

```text
Face::meanCurvature
Face::energy.energyCurvature
Face::normVector
```

`Face::elementArea` and `Face::elementVolume` remain owned by the separate
production geometry pass and are not recalculated or overwritten here. Other
current and previous energy fields, topology, flags, spontaneous curvature,
all vertex fields and forces, and one-rings remain unchanged.

`evaluate_guarded_valence4_face_observable_publication(...)` first completes
the approved eight-face, three-sample scientific request. Missing approval or
malformed late rows reject before publication.

## Evidence

The approved closed valence-4 octahedron tests bind:

- default-off and malformed-late-row rejection without mesh mutation;
- cardinality, duplicate identity, nonfinite late normal, face identity, and
  nonempty one-ring rejection before any write;
- input-order independence through explicit face-index canonicalization;
- replacement of pre-existing wrong-shaped normals only after complete
  validation and allocation;
- exact mean-curvature, bending-energy, and normal publication;
- unchanged area, legacy volume, other current energy fields, all previous
  energy fields, topology, vertex coordinates, and every vertex force family;
  and
- fresh OpenSubdiv-present scientific rows on a separate disposable mesh.

## Boundary

```text
proof_only: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
face_observable_publication_executed: true
vertex_force_publication_executed_separately: true
production_one_rings_populated: false
```

Default dependency behavior, OpenSubdiv ownership, formulas, quadrature,
source scatter, OpenMP scheduling/reduction order, checkpoint/output,
propagation, fixtures, and broader-valence routing are unchanged.

The next separately reviewed boundary is guarded production face-loop
integration that composes the already reviewed vertex-force and
face-observable publications and proves full serial/OpenMP parity before any
route activation.
