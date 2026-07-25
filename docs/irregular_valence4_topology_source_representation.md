# Valence-4 Topology/Source Representation

This review-gated production-facing lane adds a backend-neutral representation
for the approved closed valence-4 octahedron. It converts production `Mesh`
topology into a face-indexed table containing:

- the stable production face index;
- the three canonical oriented face source IDs; and
- the six original source IDs `[0,1,2,3,4,5]`.

The representation is built only by an explicit call to
`build_guarded_valence4_topology_source_mapping`. It is not stored in
`Face::oneRingVertices`, is not consulted by the production energy/force path,
and does not enable OpenSubdiv routing.

## Guard Contract

The builder accepts only the scientifically approved stand-in topology:

- exactly six vertices and eight triangular faces;
- stable vertex/source IDs `0..5`;
- valence four at every source vertex;
- the canonical oriented octahedron face list;
- physical, non-boundary faces;
- exact six-source coverage for every face; and
- empty production `Face::oneRingVertices`.

Any mismatch returns `supported=false`, an empty face table, and a non-empty
rejection reason. The builder never mutates the mesh.

The `Face::oneRingVertices` exclusion is deliberate. Existing production code
interprets that field as an 11- or 12-control force/scatter contract. A
six-source valence-4 mapping therefore has a separate type so it cannot be
silently consumed by the current direct production formulas.

## Boundary

This lane does not:

- create OpenSubdiv rows or expose OpenSubdiv types;
- call or alter production force, scatter, or OpenMP reduction code;
- enable valence-4 geometry or force routing;
- change default dependency, build, test, or runtime behavior;
- change the approved fixture;
- change checkpoint, output, or propagation behavior; or
- approve any topology beyond the canonical octahedron.

The next separately reviewed step is a production-call parity proof that
combines this guarded source representation with the existing proof-only
OpenSubdiv valence-4 rows. Production valence-4 route activation remains
unapproved.
