# OpenSubdiv Limit-Surface Feasibility

This note scopes an OpenSubdiv replacement path for SLIMED's current
hard-coded triangular Loop-subdivision limit-surface machinery. It is a
feasibility/design slice only: the production backend remains the current SLIMED
implementation, and no OpenSubdiv dependency is introduced here.

Baseline checked for this phase: `origin/main` includes PR #18 at commit
`7a455625ae3b22cc4cc59359df19c2633ad631bf`.

## Current SLIMED Contract

The current limit-surface contract is split across mesh initialization,
quadrature, area/volume integration, energy/force evaluation, boundary/ghost
setup, and dynamics projection:

- `Mesh::Mesh` precomputes quadrature points/weights, per-point shape-function
  matrices, and irregular-patch subdivision matrices into `Param`.
- `get_gauss_quadrature_weight_VWU` supports rules `1`, `2`, `4`, `5`, and `6`
  with 1, 3, 6, 7, and 12 barycentric samples respectively. Rule `3` currently
  fills weights but leaves `vwu` unchanged; that behavior is already
  characterized in tests.
- `get_shapefunction` returns a `7 x 12` matrix for one regular triangular
  patch. Row `0` is position weights; rows `1` and `2` are first derivatives;
  rows `3` and `4` are second derivatives; rows `5` and `6` are mixed
  derivatives. The mixed rows are expected to match.
- `set_one_ring_vertices_sorted` gives regular faces a 12-control-vertex
  support ordered as `{d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12}`.
  Irregular faces currently receive 11 entries when all three face vertices
  have valence/fan size 5.
- `calculate_element_area_volume` evaluates non-ghost regular 12-control faces
  directly with the precomputed shape functions. For 11-control irregular faces
  it repeatedly applies the precomputed `M`, `M1`, `M2`, `M3`, and `M4`
  matrices, accumulating three regular child patches per subdivision iteration
  and carrying one irregular child forward.
- `element_energy_force_regular` multiplies each `7 x 12` shape matrix by a
  `12 x 3` one-ring coordinate matrix. Its geometry outputs are the limit
  position `x`, tangents `a_1`/`a_2`, second derivatives `a_11`/`a_22`, and
  mixed derivatives `a_12`/`a_21`; these feed surface normal, metric terms,
  mean curvature, bending energy, and bending/area/volume force terms.
- `Compute_Energy_And_Force` scatters per-face force contributions back to
  `face.oneRingVertices` and then applies regularization, energy sums, optional
  scaffolding coupling, and boundary/ghost force policy. This phase must not
  move or alter that scatter/evaluator boundary.
- Boundary behavior is not just a subdivision option. `determine_ghost_vertices_faces`
  excludes ghost faces/vertices according to `BoundaryType::{Fixed, Periodic,
  Free}`; `manage_force_for_boundary_ghost_vertex` zeroes fixed/free/ghost
  forces as a later policy step; `DynamicMesh::postprocess_ghost_periodic`
  synchronizes periodic reflective and ghost rows after dynamics moves.
- `DynamicMesh::assign_mesh2surface` currently uses a separate mesh-to-surface
  projection matrix with a hard-coded regular valence-6 weight pattern. An
  OpenSubdiv geometry adapter would not replace this timing/policy without a
  separate dynamics-focused PR.

Existing characterization coverage already pins several important pieces:
`tests/test_surface_geometry_characterization.cpp` checks shape-function
partition of unity, derivative sums, mixed-derivative equality, quadrature rule
shapes/weights, irregular subdivision matrix dimensions, affine row sums, and a
periodic flat-mesh area/volume baseline.

## OpenSubdiv Facts

Primary-source facts checked from the official Pixar OpenSubdiv repository:

- License: OpenSubdiv uses the Tomorrow Open Source Technology License 1.0,
  described in the repository license as differing from Apache License 2.0 in
  its trademark section. It grants copyright and patent permissions with
  redistribution conditions. Source: [LICENSE.txt](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/LICENSE.txt).
- C++/build baseline: the release CMake file requires CMake 3.14 and defaults
  `CMAKE_CXX_STANDARD` to `14` with extensions off. SLIMED's current C++17
  target is therefore compatible with this baseline. Source:
  [CMakeLists.txt](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/CMakeLists.txt).
- Dependency shape: the official README says the core libraries are C++ and
  have no dependencies beyond the C++ standard library; CPU/GPU evaluators,
  viewers, and documentation have optional dependencies that can be disabled
  with CMake options such as `NO_OMP`, `NO_TBB`, `NO_CUDA`, `NO_OPENCL`,
  `NO_OPENGL`, `NO_PTEX`, and `NO_DOC`. Source:
  [README.md](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/README.md).
- Loop support: `Sdc::SchemeType` includes `SCHEME_LOOP`, and the split enum
  documents `SPLIT_TO_TRIS` as used by Loop. Source:
  [opensubdiv/sdc/types.h](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/sdc/types.h).
- Patch-basis derivatives: `Far::PatchTable::EvaluateBasis` can return
  position weights, first derivative weights `wDu`/`wDv`, and second derivative
  weights `wDuu`/`wDuv`/`wDvv` at a patch coordinate. Source:
  [opensubdiv/far/patchTable.h](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/far/patchTable.h).
- Limit stencil derivatives: `Far::LimitStencil` stores position, `du`, `dv`,
  `duu`, `duv`, and `dvv` weights, and `LimitStencilTable` exposes update
  helpers for first and second derivatives. Source:
  [opensubdiv/far/stencilTable.h](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/far/stencilTable.h).
- Boundary interpolation options are limited to `VTX_BOUNDARY_NONE`,
  `VTX_BOUNDARY_EDGE_ONLY`, and `VTX_BOUNDARY_EDGE_AND_CORNER`, with separate
  face-varying linear interpolation modes. Source:
  [opensubdiv/sdc/options.h](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/sdc/options.h).

Local environment check on 2026-06-20:

- `brew list --versions opensubdiv` returned no installed formula version.
- `/opt/homebrew/opt/opensubdiv` and `/opt/homebrew/include/opensubdiv` were
  absent.
- `pkg-config --modversion opensubdiv` returned no version.
- Searching `/opt/homebrew` and `/usr/local` found no OpenSubdiv headers or
  CMake package files.

Because the library is not locally installed, this phase did not add or compile
an OpenSubdiv-backed stub. Installing Homebrew packages, cloning source, or
vendoring third-party code should be a reviewed dependency decision.

## Capability Mapping

OpenSubdiv appears promising for the geometry-evaluation subset:

- Loop triangle subdivision is a first-class scheme, so the target surface
  family matches SLIMED's stated custom Loop machinery.
- Patch and limit-stencil APIs expose the position and derivative data needed
  for SLIMED's curvature path: position, two first derivatives, and three
  second derivative combinations. SLIMED currently carries both mixed rows
  (`a_12` and `a_21`); an adapter can derive both from the single OpenSubdiv
  `duv` result after confirming coordinate orientation.
- Limit stencils are especially attractive for static topology and moving
  vertices: they match SLIMED's pattern of repeatedly applying fixed weights to
  changing control coordinates.

The major gaps are integration and equivalence risks, not whether OpenSubdiv can
name the mathematical quantities:

- Parametric coordinates and orientation must be mapped from SLIMED's `v,w,u`
  barycentric convention to OpenSubdiv's patch `u,v`. A sign/order error would
  silently flip normals, curvature, and forces.
- SLIMED's 12-entry one-ring ordering is not the native OpenSubdiv patch-control
  indexing. A backend adapter must translate OpenSubdiv patch/stencil indices
  back to SLIMED vertex indices for force scatter.
- Boundary behavior is not equivalent out of the box. OpenSubdiv can express
  boundary interpolation/sharpness modes, but SLIMED's free/fixed/periodic
  ghost layers and periodic reflective synchronization are application-level
  conventions. The adapter must either evaluate only non-ghost physical faces
  using an already-expanded SLIMED topology, or own an explicit topology
  expansion/mirroring layer whose results are proven equivalent.
- Irregular handling is intentionally incomplete today: area/volume have an
  11-control subdivision approximation, while energy/force rejects
  non-boundary 11-control faces before the membrane force loop. Any OpenSubdiv
  irregular path must first define a reviewed force contract before replacing
  that guard.
- OpenSubdiv does not replace membrane energies, force accumulation, global
  constraints, scaffolding coupling, optimizer state, random thermal moves,
  output/checkpoint formats, or dynamics projection timing.

## Proposed Adapter Shape

Keep the first real code PR focused on a backend-neutral contract:

```text
LimitSurfaceEvaluator
  inputs:
    - face index or face descriptor
    - ordered SLIMED control vertex ids and coordinates
    - quadrature/sample locations in SLIMED's current convention
  outputs per sample:
    - weights or evaluated x
    - dx/dv and dx/dw
    - d2x/dv2, d2x/dw2, d2x/dvdw, d2x/dwdv
    - source vertex ids for force scatter
```

The production implementation should start as
`SlimedLoopLimitSurfaceEvaluator`, a wrapper around the current
`get_shapefunction`/`shapeFunctions` behavior, with tests proving byte-level or
near-exact equivalence for regular flat patches. Only after that contract is
isolated should an `OpenSubdivLimitSurfaceEvaluator` be added behind an
optional compile flag.

The OpenSubdiv path should prefer generated limit stencils for SLIMED's Gauss
samples over repeated runtime patch-basis lookup, because topology is static
within a run while vertex coordinates move. The adapter must preserve SLIMED
vertex ids for force scatter; returning only evaluated points is insufficient.

## Contract Slice Added After PR #15

The first code seam is `LimitSurfaceEvaluator` in
`include/mesh/Limit_surface_evaluator.hpp`. Its value object,
`LimitSurfaceEvaluation`, names the seven geometry outputs currently consumed
from SLIMED's regular Loop shape-function matrix: position, first derivatives
with respect to `v` and `w`, pure second derivatives, and the two mixed rows.
`SlimedLoopLimitSurfaceEvaluator` is a wrapper around the existing
`get_shapefunction` regular 12-control implementation.

This contract intentionally covers only regular `12 x 3` one-ring control
patches. The current irregular `11 x 3` path remains documented as future work:
area/volume still use subdivision matrices, while energy/force behavior is not
changed by this seam. No OpenSubdiv headers, build flags, dependencies, or
production defaults are introduced here.

## Regular Area/Volume Adoption After PR #17

The first production call-site adoption is intentionally narrow:
`Mesh::calculate_element_area_volume()` routes only the regular `12 x 3`
one-ring case through `SlimedLoopLimitSurfaceEvaluator` for position and first
derivatives. The irregular `11 x 3` subdivision path still uses the previous
direct shape-function helper, and energy/force scatter remains unchanged.

Characterization tests compare the adopted regular area/volume path against the
previous direct row-multiplication formula on deterministic nonplanar controls,
including the current volume accumulation semantics. Boundary, ghost, periodic,
irregular, force, dynamics, and OpenSubdiv behavior remain deferred.

## Post-PR17 Adoption Map

Already migrated:

- Regular non-ghost `12 x 3` area/volume evaluation in
  `Mesh::calculate_element_area_volume()` now routes through
  `SlimedLoopLimitSurfaceEvaluator`.
- The adopted path uses the cached `Param::shapeFunctions` matrices, keeps the
  existing OpenMP reduction shape, and preserves the legacy volume accumulation
  factor `0.16666666666` plus the current first-component `dot_row` behavior.

Mechanically safe characterization targets:

- Direct regular shape-function products for representative `12 x 3` control
  patches can be compared with `SlimedLoopLimitSurfaceEvaluator` outputs in
  tests without changing production behavior.
- The geometry extraction subset inside `element_energy_force_regular` can be
  characterized as evaluator-equivalent for cached quadrature matrices, because
  both forms compute the same seven `sf * controlPoints` rows before any force
  formulas or scatter occur.
- Documentation-only mapping of regular, irregular, boundary, ghost, periodic,
  OpenMP, and OpenSubdiv boundaries is safe and helps gate future slices.

Deferred production adoption categories:

- `element_energy_force_regular` is not a safe next production migration by
  itself. Although its initial geometry rows are evaluator-equivalent, the same
  loop immediately uses shape-function entries in bending, area, and volume
  force formulas, accumulates face energy/mean curvature/normal, and fills
  `fBend`, `fArea`, and `fVolume`.
- `Compute_Energy_And_Force` scatters per-face force components into per-thread
  buffers and then reduces them over vertices. Any change that moves this
  boundary needs a separate numerical-baseline PR covering floating-point
  summation order, OpenMP reductions, and force component ordering.
- Irregular `11 x 3` area/volume still uses subdivision matrices and direct
  regular child-patch evaluation. Irregular energy/force currently fails with
  an unsupported-route diagnostic and remains a scientific-review topic before
  backend migration.
- Boundary, ghost, periodic, and dynamics projection behavior must stay
  separate from evaluator adoption because they encode application policy, not
  only surface evaluation.
- OpenSubdiv remains dependency-gated and should not be introduced until the
  SLIMED backend has regular-interior equivalence baselines for geometry,
  source-index mapping, and force scatter.
- Volume-semantics changes, including the legacy quadrature factor or the
  current `dot_row` behavior, require an explicit scientific/numerical review
  rather than being bundled with evaluator plumbing.

## Energy/Force Numerical Baseline Checklist

Before any production `element_energy_force_regular` migration to
`LimitSurfaceEvaluator`, the PR must provide evidence for the current
regular-patch behavior at two levels.

Geometry-only baseline:

- Use deterministic non-ghost regular `12 x 3` fixtures whose one-ring ordering
  matches `Face::oneRingVertices`; include flat, gently curved, mixed-sign, and
  anisotropic coordinate scales.
- For every cached `Param::shapeFunctions` row used by the configured Gauss
  quadrature rule, compare evaluator outputs against the current
  `multiplication(sf, matOneRingVertices, sfDotOneRingV)` extraction in
  `element_energy_force_regular`.
- Require exact equality when the test routes through the same SLIMED matrix
  multiplication helper. If a future backend changes arithmetic order, use an
  explicitly reviewed absolute/relative tolerance and record the largest
  observed component deltas for all seven rows: `x`, `a_1`, `a_2`, `a_11`,
  `a_22`, `a_12`, and `a_21`.
- Keep geometry comparisons local to test calculations. They must not mutate
  mesh coordinates, cached shape functions, face state, forces, energies, or
  global area/volume parameters.

Energy/force baseline:

- Compare full reference outputs for at least one deterministic flat regular
  periodic mesh and one deterministic nonplanar regular mesh: total area,
  volume, face curvature energy, mean curvature, normals, per-vertex bending
  force, area force, volume force, regularization force, total force, and total
  energy.
- Run serial and OpenMP builds on the same fixtures. OpenMP comparisons must
  state thread counts, schedules/default environment, and whether expected
  deltas are exact or tolerance-based due to reduction order.
- Preserve force scatter order from `face.oneRingVertices` into the per-thread
  accumulation buffers unless a separate baseline explicitly approves an order
  change.
- Include smoke coverage for the committed example parameter file and for a
  checkpoint/restart path if the migrated code can affect restart-visible
  forces, energies, area, volume, normals, or output rows.
- Document compiler, platform, command lines, and tolerance policy in the PR
  body. Tolerances beyond straightforward double-precision equivalence of
  isolated geometry rows are scientific decisions and need reviewer approval.

Stop conditions:

- Do not proceed in a production migration PR if equivalence requires exposing
  new production internals only for tests, duplicating the large bending/area/
  volume force algorithm in test code, changing OpenMP reductions or schedules,
  changing checkpoint/output formats, or resolving irregular `11 x 3` semantics
  as a side effect.
- Legacy volume semantics remain frozen for evaluator work, including the
  quadrature factor `0.16666666666` and the existing regular area/volume
  behavior. Any proposed volume change needs its own numerical-baseline PR.

## Build/Dependency Options

Viable paths, in increasing ownership:

- System install: discover OpenSubdiv with a Makefile flag such as
  `USE_OPENSUBDIV=1` and user-provided include/library paths or `pkg-config`
  if available. Default builds remain dependency-free.
- Local source build outside the repo: document a CMake install prefix under a
  user-controlled path and point SLIMED to it. This is best for feasibility
  experiments without vendoring.
- Vendored source: only after license review and a clear maintenance decision.
  Do not vendor generated build directories, examples, documentation output, or
  unused GPU/viewer dependencies.

No option should make OpenSubdiv required for default `make serial`, `make omp`,
`make dyna`, `make dyna_omp`, or `make test` until numerical equivalence is
proven and reviewed.

## Recommended Next PR Sequence

1. Done: add a backend-neutral `LimitSurfaceEvaluator` contract and a
   `SlimedLoopLimitSurfaceEvaluator` wrapper around the current regular-patch
   shape-function path. Keep `Mesh` call sites numerically unchanged.
2. Done: add focused tests for regular-patch evaluator outputs: shape dimensions,
   partition of unity, derivative sums, mixed-derivative equality, and exact
   agreement with current `Param::shapeFunctions`.
3. Done: adopt the contract in one regular area/volume path only after proving
   equivalence to direct shape-function row multiplication.
4. Done: characterize the regular energy/force geometry-extraction subset with
   multiple deterministic `12 x 3` fixtures and cached quadrature rows, without
   changing production behavior.
5. Done for geometry-only fixture readiness: characterize an explicit
   11-control irregular area/volume patch and document why the current
   energy/force route remains a known gap. See
   `docs/irregular_patch_fixture_requirements.md`.
6. Decide whether regular energy/force geometry extraction should migrate only
   after a force/energy numerical-baseline PR, because production code there is
   coupled to force formulas, scatter, accumulation order, and OpenMP behavior.
7. Decide the OpenSubdiv dependency path. For a system-install experiment,
   introduce an opt-in `USE_OPENSUBDIV=1` build flag that default builds ignore.
8. Prototype an OpenSubdiv stencil generator for non-ghost regular faces only,
   with explicit `v,w,u` to `u,v` mapping tests and force-scatter source-index
   tests. Compare flat regular-patch area, normal, mean curvature, and force
   outputs against the SLIMED backend.
9. Expand to boundary/periodic/ghost topology only after regular interior
   equivalence is demonstrated. Keep dynamics projection and ghost
   postprocessing in a separate PR.

## Current Recommendation

Do not switch production code to OpenSubdiv yet. The library has the relevant
Loop and derivative primitives, but SLIMED's boundary/ghost conventions,
one-ring force scatter, irregular behavior, and lack of a local dependency mean
the safe next step is a small SLIMED-backend seam plus characterization tests,
followed by an opt-in OpenSubdiv experiment after dependency approval.
