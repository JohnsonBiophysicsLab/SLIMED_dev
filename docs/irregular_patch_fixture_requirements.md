# Irregular Patch Fixture Requirements

This note characterizes what can be tested safely for the current
11-neighbor irregular-patch backlog without changing production C++ behavior.
It is a fixture map, not an approval to route production energy/force through a
new irregular backend.

## Current Status

Area/volume and energy/force disagree for 11-control faces:

- `Mesh::calculate_element_area_volume()` recognizes
  `face.oneRingVertices.size() == 11`, repeatedly applies the existing
  irregular subdivision matrices, accumulates three regular child patches per
  subdivision depth, and carries the fourth irregular child forward.
- `Mesh::Compute_Energy_And_Force()` also recognizes the 11-control case, but
  the branch still contains `//@todo energy force irregular` and then calls
  `element_energy_force_regular(...)`.
- `SlimedLoopLimitSurfaceEvaluator` intentionally rejects an 11-control
  regular-patch evaluation. It is a regular 12-control backend only.

The proof-of-concept referenced in planning suggests the future production
shape: subdivide an 11-control patch into regular child patches, evaluate those
regular children, and map child forces back to the original one-ring vertices
through subdivision matrices. Do not copy that implementation into SLIMED; use
it only as design context for a reviewer-approved production route.

## Fixture Added

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
- The test should construct or assert coordinates directly. Current flat-mesh
  helpers reliably produce regular 12-control physical faces; they are not a
  stable way to discover an interior 11-control face.

## Energy/Force Gap

No default energy/force test is added for the irregular route in this lane.
The existing production branch is known wrong, and a robust non-brittle test
would require at least one of these decisions:

- an approved `element_energy_force_irregular(...)` contract;
- a force back-projection contract from subdivided regular child patches to the
  original 11 one-ring vertices;
- a tolerance and baseline policy for serial and OpenMP force accumulation; or
- a production diagnostic/hook that reports route selection without changing
  formulas or force scatter.

Source-text assertions against the TODO or the regular call are too brittle for
the default test suite. Death tests around the current 11-control force route
would characterize GSL/BLAS dimension-mismatch handling rather than membrane
semantics, so they are intentionally avoided.

## Recommended Next Prompt

```text
Create a narrow production irregular-patch energy/force routing PR for the
existing `nOneRingVertices == 11` case. Preserve regular 12-control behavior,
force scatter order, OpenMP reduction shape, boundary/ghost policy, volume
semantics, output/checkpoint formats, evaluator signatures, and default
dependencies. Use the synthetic 11-control characterization fixture as the
geometry seed, define an approved child-patch force back-projection contract,
and provide serial/OpenMP numerical evidence for area, volume, face curvature
energy, mean curvature, normals, per-vertex force components, and total energy.
Do not broaden valence support or introduce OpenSubdiv in the same PR.
```
