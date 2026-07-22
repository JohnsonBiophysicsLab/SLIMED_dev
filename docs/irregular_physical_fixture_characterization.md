# Approved Irregular Physical Fixture Characterization

The checked-in `data/example` mesh is the approved physical mesh for this
fixture lane. It contains 1,927 vertices and 3,680 triangular faces. Its
companion parameter file declares periodic boundaries, and its row-major flat
topology resolves to `nFaceX=40` and `nFaceY=46`.

`SurfaceIrregularFixtureCharacterization.ApprovedExampleMeshHasNoPhysicalIrregularFaceAfterProductionSetup`
loads the CSV files through `Mesh::setup_from_vertices_faces()`. This exercises
the production adjacency, periodic ghost, and one-ring setup rather than
inferring physical status from CSV connectivity alone.

## Result

- 960 faces are production ghosts.
- 2,720 faces are physical and have regular 12-control one-rings.
- 336 ghost faces carry the mixed-valence topology seen by the earlier inert
  inventory.
- Zero physical faces have an 11-control one-ring.
- Zero physical faces fall into an unsupported broader-valence bucket.

The approved mesh is therefore a negative irregular fixture. It resolves the
old uncertainty about the mixed-valence leads: they are periodic boundary
scaffolding, not physical irregular membrane faces.

## Exact Remaining Blocker

The repository still lacks a positive representative physical fixture with a
reviewed non-ghost irregular face. To validate the existing positive-depth
11-control route on physical data, a future fixture must provide reviewed
coordinates and connectivity that production setup classifies as non-ghost
and maps to the 11-control predicate. Broader-valence OpenSubdiv validation
needs the same physical status plus an independently approved route contract.

The generated closed valence-5 topology remains a topology-only sanity check.
Using it as scientific validation would require an explicit scientific waiver.

This characterization does not change production routing, default dependency
behavior, force formulas, scatter order, OpenMP reductions, checkpoint/output,
or propagation.
