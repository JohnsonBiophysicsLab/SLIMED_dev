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

## Narrow Positive Fixture Resolution

The user explicitly approved the generated closed valence-5 topology as the
scientific stand-in for narrow 11-control validation. Its coordinates and
connectivity are now serialized under `data/fixtures/closed_valence5`, and the
production-setup and serial/OpenMP results are recorded in
`docs/irregular_valence5_scientific_fixture.md`.

This resolves the positive fixture gate only for the existing positive-depth
11-control route. Broader-valence OpenSubdiv validation still needs an
independently approved route and scientific contract.

This characterization does not change production routing, default dependency
behavior, force formulas, scatter order, OpenMP reductions, checkpoint/output,
or propagation.
