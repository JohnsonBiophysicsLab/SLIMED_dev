# Closed Valence-4 Fixture Candidate Packet

The serialized regular octahedron under
`data/fixtures/candidates/closed_valence4_octahedron` is a candidate packet
for a broader-valence physical fixture contract. It is not an approved
scientific fixture. It requires explicit scientific approval before it can
support any physics, backend, or routing claim.

The metadata makes this state machine-readable with
`scientifically_approved: false` and `production_route_enabled: false`.

## Candidate Contract

The packet serializes six unit coordinate-axis vertices and eight
outward-oriented triangular faces. Its connectivity has twelve edges, exactly
two oppositely directed face incidences per edge, vertex valence 4 everywhere,
and face valence triplet `4/4/4` on all eight faces. The six coordinates are
unique and finite, the vertex-edge graph is connected, and
`V - E + F = 6 - 12 + 8 = 2`.

For these canonical axis coordinates, the unambiguous straight-sided input
polyhedron quantities are:

| Quantity | Exact value |
| --- | ---: |
| Circumradius | `1` |
| Edge length | `sqrt(2)` |
| Area of one face | `sqrt(3)/2` |
| Total polyhedral surface area | `4*sqrt(3)` |
| Signed enclosed polyhedral volume | `4/3` |

`candidate_metadata.json` records these values and the candidate/approval
boundary. `scripts/inventory_irregular_valence4_fixture_candidate.py --check`
independently derives the topology, orientation, edge lengths, face areas,
total area, signed volume, and circumradius from the CSV files and compares
them with the metadata. These are input-polyhedron geometry values, not SLIMED
outputs.

## Current Production Result

`SurfaceIrregularFixtureCharacterization.CandidateClosedValenceFourFixtureRemainsUnsupportedBeforeGeometryMutation`
loads the serialized candidate through
`Mesh::setup_from_vertices_faces()` with a fixed boundary condition. Production
setup classifies all eight faces as physical and leaves all eight
`Face::oneRingVertices` vectors empty. The PR114 preflight then raises the
unsupported-routing diagnostic before changing any seeded face area or volume.

Broader-valence routing stays disabled. There is no regular fallback and this
packet does not change production C++, formulas, scatter, OpenMP reductions,
checkpoint/output, propagation, OpenSubdiv routing, dependencies, or builds.

## Approval Boundary

The exact Euclidean polyhedral quantities above do not validate SLIMED
membrane geometry, limit-surface behavior, OpenSubdiv behavior, energy, or
force. This lane makes no membrane-force or OpenSubdiv-force correctness claim.
A later lane needs explicit scientific approval plus separately reviewed
expected outputs and source-mapping/backend policy before this candidate can be
promoted or routed.
