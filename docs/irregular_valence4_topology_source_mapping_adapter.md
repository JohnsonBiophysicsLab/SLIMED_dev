# Valence-4 Topology/Source-Mapping Adapter Design

This proof-only lane follows the approved octahedron mapping, force, scatter,
and production/OpenMP shadow evidence. It answers one narrow question: can
production `Mesh` topology identity be bound deterministically to the original
OpenSubdiv source IDs without populating `Face::oneRingVertices` or enabling a
production route?

The machine-readable contract is:

```text
proof_only: true
topology_source_mapping_adapter_design: true
not_production_routing: true
production_route_enabled: false
scientifically_approved: false
actual_production_force_path_executed: false
```

## Evidence

Run the adapter proof with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_irregular_valence4_topology_source_mapping_adapter.sh \
  --json --require-opensubdiv
```

The wrapper first runs the existing OpenSubdiv mapping proof. For each of the
eight oriented fixture faces, it requires original-source coverage
`[0,1,2,3,4,5]`.

The standalone C++ harness independently loads the approved octahedron through
production `Mesh::setup_from_vertices_faces`. For each production face it
derives candidate source IDs as the sorted union of the three face vertices
and their production adjacency lists. The result must exactly equal the
OpenSubdiv original-source coverage and each production `Vertex::index`.

The proof also requires:

- all six production vertices to have valence four;
- all eight oriented faces to match the OpenSubdiv report;
- every face to remain physical and non-boundary;
- every production `Face::oneRingVertices` vector to remain empty;
- an independent exact sentinel scatter over the six-source, nine-component
  force-buffer layout; and
- duplicate, missing, out-of-range, and orientation mutations to be rejected.

Without `OPENSUBDIV_ROOT`, the wrapper returns a clean `status: skipped`.
No default build or dependency behavior changes.

## Boundary

This is an adapter design proof for the approved octahedron only. It does not:

- create a generic valence-4 topology adapter;
- populate production `Face::oneRingVertices`;
- call a production valence-4 force path;
- enable OpenSubdiv routing;
- change formulas, scatter code, OpenMP scheduling, or reductions;
- change checkpoint, output, propagation, or fixture files; or
- establish scientific equivalence for broader-valence meshes.

The next production-facing step, if separately approved, is a guarded
topology/source-mapping representation that preserves these rejection and
fallback boundaries. Production valence-4 routing remains unapproved.
