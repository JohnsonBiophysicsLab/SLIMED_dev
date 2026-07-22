# Approved Closed Valence-5 Scientific Stand-In

The serialized mesh in `data/fixtures/closed_valence5` is the explicitly
approved scientific stand-in for the narrow positive-depth 11-control route.
The approval applies only to that existing route. It does not approve
broader-valence support or OpenSubdiv-backed irregular production routing.

## Fixture Contract

The fixture contains 12 vertices and 20 outward-oriented triangular faces.
Production `Mesh::setup_from_vertices_faces()` runs with a fixed boundary
condition, classifies every face as physical, gives every vertex valence 5,
and produces an 11-slot one-ring for every face. Each local one-ring has nine
unique original vertex IDs: two source IDs occur in duplicate local slots.
The ordered 11-slot list is therefore part of the fixture contract, and force
scatter must deterministically aggregate duplicate source IDs through
`Face::oneRingVertices`.

`SurfaceIrregularFixtureCharacterization.ApprovedClosedValenceFiveFixtureExercisesAllPositiveDepthElevenControlFaces`
uses `Param::subDivideTimes = 2`. It independently evaluates the regular child
patches and transpose back-projection for all 20 faces, scatters expected
`fBend`, `fArea`, and `fVolume` rows through the production one-rings, then
compares those results with `Mesh::Compute_Energy_And_Force()`.

## Serial/OpenMP Evidence

`scripts/run_irregular_valence5_fixture_parity.sh` compiles the production
evaluator twice: once serially and once with `OMP` enabled. Both executables
load the serialized fixture, apply the same deterministic coordinate
perturbation, and emit energy, force, normal, area, legacy-volume, and mean
curvature snapshots.

The reviewed absolute tolerance is `1.0e-10`. The characterization run
reported a maximum absolute difference of `1.4210854715202004e-14`:

| Channel | Maximum absolute difference |
| --- | ---: |
| Global energy | `1.7763568394002505e-15` |
| Per-face energy | `0` |
| Per-vertex force components | `1.4210854715202004e-14` |
| Face normals | `0` |
| Face area | `6.661338147750939e-16` |
| Legacy face volume | `1.1102230246251565e-16` |
| Face mean curvature | `0` |

Face identity and all 220 ordered local source slots matched exactly. Forces
were finite and nonzero in both builds.

## Boundary

This lane changes no production C++ behavior, default dependency or build
policy, force formula, scatter implementation, OpenMP schedule or reduction,
checkpoint/output behavior, or propagation. It validates the existing narrow
11-control route on an approved closed scientific stand-in. Unsupported
broader valences and any future OpenSubdiv irregular route still require their
own physical contract, implementation, and reviewer/user approval.
