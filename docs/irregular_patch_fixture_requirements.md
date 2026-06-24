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

`SurfaceSubdivisionCharacterization.SyntheticIrregularPatchEnergyForceRequiresSubdivisionDepth`
uses the same fixture with `Param::subDivideTimes = 0` to verify that
`Compute_Energy_And_Force()` reports the unsupported zero-depth 11-control
force route before the old regular fallback can run.

`SurfaceSubdivisionCharacterization.SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces`
uses the fixture with `Param::subDivideTimes = 2` to verify that the production
11-control route matches an independent test-side child-regular-force
transpose back onto the original one-ring force rows.

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

## Remaining Energy/Force Review Surface

This lane adds a default energy/force success test for the documented
subdivision/back-projection route, but it does not resolve every broader
irregular-surface decision. Remaining review items include:

- scientific approval of the existing subdivision-depth approximation as the
  intended 11-control force law;
- tolerance and baseline policy beyond the synthetic 11-control fixture for
  serial and OpenMP force accumulation;
- broader extraordinary-valence support, if any; and
- any future OpenSubdiv-backed sample plan or backend policy.

The committed guard test checks the production diagnostic message for
zero-depth 11-control requests instead of characterizing GSL/BLAS
dimension-mismatch handling.

## Recommended Next Prompt

```text
Extend validation for the production 11-control subdivision/back-projection
route without changing dependency policy. Preserve regular 12-control
behavior, force scatter order, OpenMP reduction shape, boundary/ghost policy,
volume semantics, output/checkpoint formats, evaluator signatures, and default
dependencies. Add serial/OpenMP numerical evidence beyond the synthetic
fixture for area, volume, face curvature energy, mean curvature, normals,
per-vertex force components, and total energy. Do not broaden valence support
or introduce OpenSubdiv in the same PR.
```
