# Valence-4 Vertex-Force Publication

This review-gated lane adds the smallest mesh mutation boundary after the
source-keyed scatter-buffer proof. It remains default-off and does not install
the valence-4 production route.

## Contract

`publish_source_keyed_membrane_forces_to_vertices(...)` receives one reduced
force tuple for each original source ID. Before the first write it requires:

- source count equal to the production vertex count;
- `Vertex::index` equal to the original source ID position;
- finite `fBend`, `fArea`, and `fVolume` components;
- existing `3 x 1` destination matrices; and
- empty production `Face::oneRingVertices`.

The complete source vector is staged before publication. The helper then
overwrites only:

```text
Vertex::force.forceCurvature
Vertex::force.forceArea
Vertex::force.forceVolume
```

It does not calculate or update `forceTotal`. It does not alter other current
force families, previous forces, coordinates, topology, face geometry,
energies, normals, or one-rings.

`evaluate_guarded_valence4_vertex_force_publication(...)` is a separate
explicit request. It first completes the approved eight-face, three-sample
scientific request and source-keyed accumulation. Default-off and malformed
requests reject before publication.

## Evidence

The approved closed valence-4 octahedron tests bind:

- default-off and malformed-late-row rejection with no force mutation;
- destination identity, finiteness, one-ring, and shape rejection before any
  write;
- exact publication of all `6 x 3 x 3` membrane-force components;
- unchanged `forceTotal`, other current force families, all previous force
  families, and face state;
- fresh OpenSubdiv-present scientific rows on disposable mesh state; and
- actual OpenMP teams `1`, `2`, `3`, `4`, and `8`, five repeats each, with
  independent source/kind/axis and named-matrix publication oracles.

## Boundary

```text
proof_only: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
vertex_force_publication_executed: true
production_one_rings_populated: false
```

Default dependency behavior, OpenSubdiv ownership, formulas, quadrature,
scatter layout, OpenMP scheduling/reduction order, checkpoint/output,
propagation, fixtures, and broader-valence routing are unchanged.

The next separately reviewed boundary is atomic face-observable and geometry
publication. Only after that evidence is green should the real production face
loop be considered for guarded integration and full serial/OpenMP parity.
