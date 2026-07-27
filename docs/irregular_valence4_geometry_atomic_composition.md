# Valence-4 Geometry-Aware Atomic Composition

This review-gated lane composes the approved canonical closed valence-4
octahedron's nonmutating geometry stage with the existing source-keyed
scientific evaluation and atomic force/face-observable publication. It remains
default-off, caller-owned, and outside `Mesh::Compute_Energy_And_Force()`.

## Evaluation Contract

`evaluate_guarded_valence4_geometry_aware_atomic_composition(...)` first runs
`stage_guarded_valence4_face_geometry(...)` against the complete fresh
source-keyed row package. It then creates a copied `Param`, replaces only the
copy's `area` and `vol` with the staged global totals, and binds a temporary
`Mesh` evaluator to that copied parameter state.

The existing `Mesh::element_energy_force_regular(...)` formula is invoked
unchanged through that temporary evaluator. Consequently `fArea` and
`fVolume` use the same staged global area and legacy volume that the
transaction later publishes. The live mesh's stale `Param::area` and
`Param::vol` are neither read by the geometry-dependent force terms nor
temporarily overwritten.

Because constructing `Mesh` initializes parameter-owned derived tables, the
composition restores the complete copied `Param` after construction before
installing staged `area` and `vol`. A regression with sample-dependent rows
and the valid nonuniform quadrature plan `{0.8, 0.1, 0.1}` requires exact
agreement with direct scientific evaluation using that same plan.

## Atomic Commit

Before the first write, the composition validates:

- explicit reviewer-approved composition;
- canonical topology, orientation, source identities, and empty production
  one-rings;
- exact eight-face and six-source coverage;
- exact three-sample, seven-row source-keyed input;
- finite per-face and global geometry with matching accumulation;
- exact binding between staged totals and scientific-evaluation totals;
- finite force and face-observable outputs;
- every vertex force destination shape;
- every face identity; and
- all replacement normal allocations.

The no-throw commit phase updates only:

- `Face::elementArea` and `Face::elementVolume`;
- `Param::area` and `Param::vol`;
- `Vertex::force.forceCurvature`, `forceArea`, and `forceVolume`; and
- reviewed face mean curvature, bending energy, and normal.

Late malformed rows, nonfinite late geometry, identity drift, destination
shape drift, or incomplete coverage leave faces, vertices, `Param::area`, and
`Param::vol` unchanged.

## Evidence

Focused C++ tests cover default-off rejection, independent oriented-triangle
geometry, stale-global independence, complete reviewed publication, malformed
last-row rejection, and late geometry-package rejection before any write.

The OpenSubdiv-present proof supplies fresh `8 x 3 x 7 x 6` rows, deliberately
seeds stale live global geometry, and requires:

```text
geometry_aware_atomic_composition_executed: true
staged_geometry_used_for_scientific_evaluation: true
stale_mesh_globals_ignored: true
only_reviewed_geometry_scientific_families_published_atomically: true
```

Absent-dependency mode continues to skip cleanly.

## Boundary

```text
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_one_rings_populated: false
default_evaluator_caller: false
```

No one-ring population, real production caller, route activation, broader
valence, default dependency/build/CI/fixture behavior, formula, scatter,
OpenMP reduction, checkpoint/output, or propagation behavior changes here.

The residual boundary is a separately reviewed real-caller shadow/parity lane
that invokes this complete transaction at production timing without enabling
the route. Only after that caller evidence and serial/OpenMP parity are green
should guarded valence-4 route activation be considered.
