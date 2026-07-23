# Irregular Patch Fixture Requirements

This note characterizes what can be tested safely for the current
11-neighbor irregular-patch backlog. It is a fixture and guard map, not an
approval to route production energy/force through a new irregular backend.

## Current Status

Area/volume and energy/force now share the same documented 11-control
subdivision route when `Param::subDivideTimes > 0`:

- `Mesh::calculate_element_area_volume()` recognizes
  `face.oneRingVertices.size() == 11`, repeatedly applies the existing
  irregular subdivision matrices, accumulates three regular child patches per
  subdivision depth, and carries the fourth irregular child forward.
- `Mesh::Compute_Energy_And_Force()` recognizes the same 11-control case when
  subdivision depth is positive, evaluates the three regular child patches per
  depth with `element_energy_force_regular(...)`, and back-projects child
  force rows through the transpose of the child-to-original subdivision
  weights before scattering through the original `Face::oneRingVertices`.
- A serial preflight still rejects 11-control faces when
  `Param::subDivideTimes <= 0` so the route cannot silently fall back into the
  regular 12-control helper without a subdivision plan.
- `SlimedLoopLimitSurfaceEvaluator` intentionally rejects an 11-control
  regular-patch evaluation. It is a regular 12-control backend only.

The implemented route is intentionally limited to the existing `11 = 4+3+4`
matrix contract. It does not add OpenSubdiv, broaden valence support, change
regular 12-control formulas, or define a new extraordinary-patch backend
policy.

The narrow representative-fixture and serial/OpenMP evidence gaps are now
closed by the explicitly approved stand-in in
`data/fixtures/closed_valence5`. Production setup gives all 20 physical faces
an ordered 11-slot one-ring with nine unique source IDs and deterministic
duplicate aggregation through `Face::oneRingVertices`.

## Fixtures And Evidence

`SurfaceSubdivisionCharacterization.SyntheticIrregularPatchAreaVolumeUsesSubdivisionFixture`
constructs a synthetic non-ghost face with exactly 11 ordered one-ring control
vertices and sets `Param::subDivideTimes = 2`. It verifies that the public
area/volume path:

- accepts the explicit 11-control `Face::oneRingVertices` fixture;
- uses the existing irregular subdivision matrices;
- produces finite positive area for the synthetic patch; and
- matches an independent test-side application of the current matrix contract.

This is mechanical coverage for the current geometry route only. It makes no
scientific claim about the selected coordinates, the ideal subdivision depth,
or a correct irregular force law.

`SurfaceSubdivisionCharacterization.SyntheticIrregularPatchEnergyForceRequiresSubdivisionDepth`
uses the same fixture with `Param::subDivideTimes = 0` to verify that
`Compute_Energy_And_Force()` reports the unsupported zero-depth 11-control
force route before the old regular fallback can run.

`SurfaceSubdivisionCharacterization.SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces`
uses the fixture with `Param::subDivideTimes = 2` to verify that the production
11-control route matches an independent test-side child-regular-force
transpose back onto the original one-ring force rows.

`SurfaceIrregularFixtureCharacterization.ApprovedClosedValenceFiveFixtureExercisesAllPositiveDepthElevenControlFaces`
loads the serialized closed valence-5 stand-in through production mesh setup.
It checks independent subdivision, transpose back-projection, and force
scatter for all 20 physical faces, including the repeated local source slots.

`scripts/run_irregular_valence5_fixture_parity.sh` compares actual serial and
OpenMP executables for energy, force components, normals, area, legacy volume,
mean curvature, face identity, and all 220 ordered local source slots. The
reviewed absolute policy is `1.0e-10`, with a maximum observed absolute delta
of `1.4210854715202004e-14`.

## Fixture Requirements

A robust 11-neighbor fixture needs these inputs to be explicit:

- The face must be non-ghost. Ghost faces are skipped before regular or
  irregular area/volume routing.
- `face.oneRingVertices` must contain exactly 11 entries in the ordering used
  by the current irregular branch of `set_one_ring_vertices_sorted()`:
  `{d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12}`.
- `Param::subDivideTimes` must be greater than zero. The current default is
  zero, which leaves the irregular area/volume branch with no accumulated
  regular child patches.
- The approved fixture serializes coordinates and connectivity directly.
  Current flat-mesh helpers still reliably produce regular 12-control physical
  faces and are not substitutes for this reviewed 11-control contract.

## Remaining Energy/Force Review Surface

The approved stand-in resolves the narrow positive-depth 11-control fixture
and serial/OpenMP executable-evidence requirements. Remaining review items are
outside that route:

- preserve the approved fixture, ordered-source, duplicate-aggregation, and
  `1.0e-10` executable baselines when the implementation changes;
- review the candidate-only closed valence-4 regular octahedron under
  `data/fixtures/candidates/closed_valence4_octahedron`; its exact polyhedral
  metadata and fail-loud production contract do not constitute scientific
  approval or membrane/OpenSubdiv force validation;
- define broader extraordinary-valence support policy, if any;
  and
- separately review any future OpenSubdiv-backed irregular sample plan,
  source mapping, force equivalence, and backend policy.

The committed guard test checks the production diagnostic message for
zero-depth 11-control requests instead of characterizing GSL/BLAS
dimension-mismatch handling.

## Recommended Next Prompt

```text
Review the candidate-only closed valence-4 regular-octahedron packet for
explicit scientific approval before designing any route. If approved, define
expected membrane/backend geometry and force outputs plus source mapping while
preserving the fail-loud unsupported-topology guard, the approved closed
valence-5 fixture, and its serial/OpenMP baseline. Do not enable
broader-valence routing or change formulas, default dependencies, scatter,
OpenMP reductions, checkpoint/output, or propagation in the approval lane.
```
