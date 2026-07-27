# Valence-4 Atomic Face-Loop Publication

This review-gated lane composes the guarded vertex-force and face-observable
publication boundaries into one default-off transaction. It does not install
or execute the valence-4 production route.

## Contract

`publish_valence4_face_loop_scientific_result_atomically(...)` accepts only a
complete scientific result produced by the reviewed valence-4 request. Before
the first mesh write it validates:

- exact source/vertex and face cardinality;
- stable vertex and face index identity;
- finite `fBend`, `fArea`, `fVolume`, mean-curvature, bending-energy, and
  normal values;
- exact, duplicate-free face-index coverage;
- existing `3 x 1` vertex force destinations; and
- empty production `Face::oneRingVertices`.

All replacement normals are allocated before the commit phase. The commit
then writes only:

```text
Vertex::force.forceCurvature
Vertex::force.forceArea
Vertex::force.forceVolume
Face::meanCurvature
Face::energy.energyCurvature
Face::normVector
```

Coordinates, topology, one-rings, all other current and previous force and
energy families, area, legacy volume, and flags remain unchanged.

`evaluate_guarded_valence4_face_loop_publication(...)` rejects by default,
evaluates the scientific request once after explicit approval, and invokes
the atomic transaction only after that request succeeds.

## Evidence

The canonical closed valence-4 octahedron tests require:

- default-off rejection without mutation;
- malformed late-row rejection without mutation;
- late nonfinite face data rejection before vertex writes;
- late wrong-shaped vertex destinations rejection before face writes;
- exact combined output against separate, independently exercised
  vertex-force and face-observable publication meshes; and
- fresh OpenSubdiv-present rows with force and face-observable deltas no
  greater than `1e-12`.

## Boundary

```text
proof_only: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
atomic_face_loop_publication_executed: true
production_one_rings_populated: false
```

No production face-loop caller invokes this transaction. Default dependency
behavior, formulas, source scatter, OpenMP scheduling/reduction order,
checkpoint/output, propagation, fixtures, optimizer behavior, boundary
handling, and broader-valence routing are unchanged.

The successor production-call shadow now invokes this atomic transaction in
serial and OpenMP builds, compares complete force, face-observable, area, and
legacy-volume output, and binds that result to the independent actual OpenMP
runtime proof. Route activation remains a later explicit reviewer/user
decision.
