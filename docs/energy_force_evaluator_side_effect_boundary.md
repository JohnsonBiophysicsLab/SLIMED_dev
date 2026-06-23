# Energy Force Evaluator Side-Effect Boundary

This note characterizes the internal side-effect boundary of
`EnergyForceEvaluator` after PR #41. The production facade still delegates
directly to `Mesh::Compute_Energy_And_Force()`, which now starts with named
geometry-refresh and clearing pre-pass helpers. This is a current-state map,
not a proposal to split formulas or move calls.

Regenerate the source-side write inventory with:

```console
python3 scripts/inventory_energy_force_side_effects.py
```

Regenerate the coarse post-PR41 phase map with:

```console
python3 scripts/inventory_energy_force_side_effects.py --phase-map
```

## Current Call Boundary

Production energy/force refreshes route through:

```text
evaluate_energy_force(Mesh&)
  -> EnergyForceEvaluator::evaluate(Mesh&)
     -> Mesh::Compute_Energy_And_Force()
```

The helper and facade own no propagation policy. Callers still own accepted
steps, trial rollback, snapshots, records, checkpoints, output cadence,
optimizer state, RNG state, and scaffold propagation timing.

## Post-PR41 Phase Map

`Mesh::Compute_Energy_And_Force()` currently runs these phases in order:

```text
EnergyForceEvaluator::evaluate(mesh)
  -> Mesh::Compute_Energy_And_Force()
     1. refresh_energy_force_geometry(*this)
        -> calculate_element_area_volume()
        -> sum_membrane_area_and_volume(param.area, param.vol)
     2. clear_force_on_vertices_and_energy_on_faces()
     3. per-face membrane accumulation
        -> non-boundary faces only
        -> element_energy_force_regular(...)
        -> Face::energy.energyCurvature, Face::meanCurvature, Face::normVector
        -> thread-local curvature/area/volume force components
     4. per-thread force scatter reduction
        -> Vertex::force.forceCurvature
        -> Vertex::force.forceArea
        -> Vertex::force.forceVolume
     5. energy_force_regularization()
        -> Face::energy.energyRegularization
        -> Vertex::force.forceRegularization
        -> Param::deformationCount
     6. vertex total-force calculation
        -> Vertex::force.forceTotal before scaffold force additions
     7. face and Param energy totalization
        -> Energy::calculateTotalEnergy() on faces
        -> global area and volume energy terms
        -> Param::energy replacement and total recalculation
     8. optional scaffold energy/force
        -> reset scaffold energy components
        -> calculate_scaffolding_energy_force(false)
        -> harmonic/Gag/idealized-lattice energy and force side effects
     9. boundary and ghost force handling
        -> manage_force_for_boundary_ghost_vertex()
```

The map is intentionally phase-level. It should not be read as approval to
change formula order, scatter order, OpenMP reduction shape, scaffold timing,
or boundary force zeroing.

## Scaffold-Enabled Characterization

`EnergyForceEvaluatorTest.SharedHelperRecordsScaffoldEnergyAndForceSideEffects`
and
`EnergyForceEvaluatorTest.SharedHelperRecordsIdealizedLatticeScaffoldEnergy`
protect the current scaffold-enabled helper path:

```text
evaluate_energy_force(Mesh&)
  -> EnergyForceEvaluator::evaluate(Mesh&)
     -> Mesh::Compute_Energy_And_Force()
     -> Mesh::calculate_scaffolding_energy_force(false)
```

The harmonic test uses a small flat mesh with one scaffold point bound to a
force-visible vertex. It verifies that the shared helper/facade route records
finite harmonic, Gag, and idealized-lattice energy components in
`Param::energy`, preserves disabled Gag/lattice terms as zero, adds the
harmonic contribution to the bonded vertex total force, and records the
equal/opposite scaffold force accumulators.

The idealized-lattice test uses a synthetic two-subunit reference fixture in
`tests/fixtures/idealized_two_subunit_lattice.dat`. The fixture initializes the
idealized lattice topology, then perturbs one scaffold COM before calling the
shared helper. This verifies that evaluator-facing scaffold accounting records
a finite, nonzero idealized-lattice energy term while preserving harmonic and
Gag components as zero. The fixture is mechanical coverage for current
evaluator side effects, not scientific validation of a Gag assembly.

No committed evaluator-facing test currently enables Gag-specific reaction
targets. That remains intentionally candidate-only until a reviewer or domain
owner supplies a representative reference-state file plus matching NERDSS
reaction `.inp` parameters.

## Side-Effect Map

| Surface | Current writes | Current reads and assumptions | Refactor caution |
| --- | --- | --- | --- |
| Element geometry | `Face::elementArea` and `Face::elementVolume` are refreshed by `calculate_element_area_volume()`. Ghost faces are skipped. | Reads current vertex coordinates, face one-ring topology, `Param::subMatrix`, `Param::subDivideTimes`, and shape/quadrature data. Regular `12`-control faces use the limit-surface evaluator path; irregular `11`-control faces use the existing subdivision path. | Preserve regular/irregular selection, Loop/OpenSubdiv contracts, quadrature order, ghost-face exclusion, and area/volume accumulation order. |
| Global area/volume | `Param::area` and `Param::vol` are reset and summed by `sum_membrane_area_and_volume(param.area, param.vol)`. | Reads current per-face area/volume and skips ghost faces. | Keep setup-time reference-area/reference-volume semantics separate from evaluator refresh semantics. |
| Current force and face energy clearing | `Mesh::clear_force_on_vertices_and_energy_on_faces()` resets every `Vertex::force` with `Force::set_all_zero()` and replaces every `Face::energy` with a default `Energy`. | Assumes previous-state fields have already been copied elsewhere if needed. | Do not move `coordPrev`, `forcePrev`, `energyPrev`, or `Param::energyPrev` into this boundary without a separate propagation baseline. |
| Per-face bending state | Non-boundary faces write `Face::normVector`, `Face::energy.energyCurvature`, and `Face::meanCurvature`. | Reads one-ring vertex coordinates, `Face::spontCurvature`, cached shape functions, quadrature coefficients, material constants, and current `Param::area`/`Param::vol` constraint values. | Preserve formula order, `sf(row, j)` access, fallback path, floating-point accumulation order, and boundary-face skip behavior. |
| Curvature/area/volume forces | Per-thread local arrays are reduced into `Vertex::force.forceCurvature`, `forceArea`, and `forceVolume`. | Reads face one-ring membership and current coordinates. | Preserve force scatter order, per-thread accumulation shape, OpenMP scheduling/reduction behavior, and serial/OpenMP numerical expectations. |
| Regularization | `Face::energy.energyRegularization`, `Vertex::force.forceRegularization`, and `Param::deformationCount` are updated by `energy_force_regularization()`. | Reads adjacent triangle coordinates, `Vertex::coordRef`, `Param::kCurv`, `Param::gamaShape`, `Param::gamaArea`, and `Param::usingRpi`. | Keep deformation classification, reference-coordinate reads, per-thread force accumulation, and count semantics unchanged. |
| Vertex total force | `Vertex::force.forceTotal` is recalculated after curvature/area/volume/regularization terms and updated again when scaffold bonds are enabled. | Reads all current force components on the vertex. | The scaffold path currently adds harmonic bond force to `forceTotal` after the first total-force calculation. Preserve that order until a dedicated physics change approves otherwise. |
| Face total energy and `Param::energy` | Each face calls `Energy::calculateTotalEnergy()`. A local `sumEnergy` accumulates face energies, global area/volume terms are applied, then `Param::energy` is replaced and total energy recalculated. | Reads `Param::isGlobalConstraint`, `Param::uSurf`, `Param::area0`, `Param::uVol`, `Param::vol0`, and the just-refreshed `Param::area`/`Param::vol`. | Do not split total-energy accounting from global constraint accounting without exact equivalence tests. |
| Optional harmonic/Gag/lattice scaffold energy | When `Param::isEnergyHarmonicBondIncluded` is true, `Param::energy.energyHarmonicBond`, `energyGagScaffolding`, and `energyIdealizedProteinLattice` are reset before `calculate_scaffolding_energy_force(false)`. That helper writes scaffold energy terms and recalculates `Param::energy.energyTotal`. | Reads scaffold points, scaffold-to-vertex correspondence, spring constants, Gag/lattice flags, and Gag reference/topology state. Idealized-lattice evaluator coverage now uses a synthetic two-subunit topology; Gag-specific coverage still needs a reference-state plus reaction-file fixture. | Preserve disabled-scaffold behavior and the current distinction between harmonic membrane coupling, Gag internal energy, and idealized lattice energy. |
| Scaffold force state | `calculate_scaffolding_energy_force(false)` resets `forceTotalOnScaffolding` and `forceOnScaffoldingPoints`, writes bonded vertices' `forceHarmonicBond`, adds it to bonded vertices' `forceTotal`, and accumulates equal/opposite scaffold forces. | Reads `Param::scaffoldingPoints`, `Param::scaffoldingPoints_correspondingVertexIndex`, `Param::lbond`, `Param::springConst`, and current bonded vertex coordinates. | Do not mix evaluator refresh with scaffold propagation. `propagate_scaffolding()` remains caller-owned policy. |
| Boundary/ghost force handling | `manage_force_for_boundary_ghost_vertex()` replaces whole `Vertex::force` objects with zero force for fixed/free/periodic boundary cases according to the existing branch logic. | Reads `Param::boundaryCondition`, face boundary flags, vertex boundary/ghost flags, and `Param::nFaceX`/`Param::nFaceY` for free boundaries. | Preserve zeroing scope and ordering after scaffold force application. Boundary force handling is output- and trajectory-visible. |
| Output/checkpoint-visible state | No files are written directly, but `Param::area`, `Param::vol`, `Param::energy`, current vertex forces, face energy/geometry fields, and scaffold force fields become visible to records, output, checkpoints, and later propagation. | Caller timing determines when records/checkpoints consume refreshed state. | Do not move record/checkpoint/output calls into the evaluator. |

## Geometry-Refresh Extraction Readiness

The narrow geometry-refresh extraction is implemented as the opening phase of
`Mesh::Compute_Energy_And_Force()`:

```text
Mesh::Compute_Energy_And_Force()
  -> refresh_energy_force_geometry(mesh)
     -> calculate_element_area_volume()
     -> non-ghost regular faces: get_one_ring_vertex_matrix()
        -> enumerate_regular_patch_area_volume_with_limit_surface_evaluator()
     -> non-ghost irregular faces: get_one_ring_vertex_matrix()
        -> subdivision matrices M/M1/M2/M3/M4
        -> enumerate_gauss_quadrature_point_area_volume()
     -> writes Face::elementArea and Face::elementVolume
     -> sum_membrane_area_and_volume(param.area, param.vol)
     -> resets and sums Param::area and Param::vol over non-ghost faces
  -> clear_force_on_vertices_and_energy_on_faces()
  -> face energy/force accumulation, regularization, totals, scaffolding, boundary handling
```

This boundary is smaller than a broad mesh-geometry rewrite because it is named
as an internal helper next to the existing energy-force implementation without
changing formula ownership, caller timing, force scatter, or output policy. The
production extraction moved only the two existing calls above behind
`refresh_energy_force_geometry(mesh)`, then calls that helper at the same point
before `clear_force_on_vertices_and_energy_on_faces()`.

Fields refreshed by this candidate:

- `Face::elementArea` and `Face::elementVolume` for non-ghost faces.
- `Param::area` and `Param::vol` through the existing by-reference summation.

Fields intentionally outside this candidate:

- `Face::energy`, `Face::normVector`, `Face::meanCurvature`, and all vertex
  force components.
- `Param::energy`, deformation counters, scaffold force state, boundary force
  policy, previous-state snapshots, records, checkpoints, and propagation state.

Current evidence:

- `SurfaceFlatMeshCharacterization.PeriodicFlatMeshKeepsInteriorRegularAndPlanar`
  observes ghost-face exclusion and flat regular-patch area/volume.
- `SurfaceFlatMeshCharacterization.RegularAreaVolumeUsesLimitSurfaceEvaluatorEquivalentToDirectRows`
  observes the regular limit-surface path against direct shape-function rows.
- `EnergyForceEvaluatorTest.SharedHelperRefreshesStaleGeometryAreaAndVolume`
  observes that the shared evaluator helper overwrites stale non-ghost face
  geometry and stale `Param::area`/`Param::vol` from current coordinates while
  preserving the current ghost-face skip behavior.
- `scripts/inventory_energy_force_side_effects.py` inventories the current
  geometry and clearing writes by scanning the implementation files that now
  contain those helpers.

Missing evidence before any broader geometry rewrite:

- No evaluator-facing test distinguishes every possible irregular `11`-control
  subdivision result from a mathematically improved irregular backend.
- No test should be treated as approval to change the legacy volume factor,
  `dot_row`/first-component volume behavior, subdivision depth semantics,
  OpenMP reductions, or OpenSubdiv dependency shape.
- Boundary, ghost, periodic, dynamics projection, and scaffold propagation
  behavior remain separate policy surfaces, not part of this extraction.

## Remaining Energy/Force Term Boundary

After the clearing and geometry-refresh extractions, the next tempting boundary
is the actual membrane term accumulation between the clearing helper and the
regularization helper. That region is not one low-risk operation. It combines
one-ring coordinate capture, regular/irregular path selection, quadrature,
bending formulas, global area/volume force formulas, face writes, per-thread
force accumulation, and later reduction into vertex force components.

Candidate classification:

| Candidate | Risk class | Why |
| --- | --- | --- |
| Name a docs-only phase as `membrane term accumulation` | Low-risk characterization only | The label helps discussion and script output without changing production C++ behavior. |
| Extract the face loop and force-reduction block as-is | Requires scientific/physics review | Even a mechanical move can perturb floating-point accumulation order, OpenMP scheduling assumptions, force scatter shape, face skip behavior, or the timing of `Face::normVector` and `Face::meanCurvature` writes. |
| Extract `element_energy_force_regular()` call preparation into a helper | Requires ownership/signature decisions | The current loop builds one-ring coordinate matrices from `Mesh`, reads `Param`, mutates `Face`, and returns multiple force matrices whose sizes assume the existing 12-control formula path. A helper boundary needs a reviewer-approved data contract. |
| Split bending, area, and volume terms inside `element_energy_force_regular()` | Requires scientific/physics review | The formulas share geometry intermediates, quadrature weights, scratch matrices, and accumulation order. Splitting them would need exact equivalence baselines plus domain review of the mathematical contract. |
| Extract global energy totalization after regularization | Medium to high risk | This looks smaller than the face loop, but it couples face total-energy calls, global area/volume energy, `Param::energy` replacement, and total-energy recalculation. It needs focused equivalence tests before production movement. |
| Extract scaffold energy/force application from the main method | Medium risk plus ownership decisions | The scaffold helper already exists, but the caller-owned reset of scaffold energy components and the post-total-force harmonic force addition are order-sensitive. Gag-specific evaluator coverage is still missing. |
| Extract boundary/ghost force handling behind an evaluator-named helper | Low naming risk but behavior-sensitive | The implementation already lives in `Mesh::manage_force_for_boundary_ghost_vertex()`. Moving or renaming the call is less risky than formula extraction, but the call must remain after scaffold force application. |

Evidence gaps before a production term extraction:

- No focused fixture currently proves that a moved face-loop helper preserves
  serial and OpenMP force accumulation order beyond the broad evaluator
  equivalence tests.
- No Gag-specific evaluator fixture initializes reaction targets and asserts
  Gag energy side effects through the facade.
- Existing tests observe harmonic scaffold and synthetic idealized-lattice
  accounting, but they do not approve changing scaffold force timing.
- Existing geometry tests protect the regular limit-surface row path, but they
  do not approve changing irregular subdivision semantics or adding an
  OpenSubdiv backend.
- A future production extraction should start from a fresh numerical baseline
  and should keep formulas, force scatter, boundary handling, and scaffold
  timing byte-for-byte equivalent unless a domain reviewer explicitly approves
  otherwise.

## Fields Currently Outside The Boundary

The evaluator refresh should not mutate these caller-owned or policy-owned
fields as part of docs-only characterization:

| State | Current owner |
| --- | --- |
| `Vertex::coord`, `Vertex::coordPrev`, `Vertex::forcePrev`, `Face::energyPrev`, `Param::energyPrev` | Runners and `Model` propagation helpers. |
| NCG direction, line-search status, trial-step size, rollback decisions | `Model` and `OptimizationAlgorithm`. |
| Thermal RNG state, thermal diagnostics, and thermal attempt count | `Model` thermal code and checkpoint IO. |
| `Record` history, output files, checkpoint files, iteration counters | `run_flat()`, `run_dynamics_flat()`, `Record`, and IO helpers. |
| Scaffold coordinate propagation and spring-constant scaling | `run_flat()` and scaffold propagation helpers. |

## Recommended Next Production Slices

Any production extraction behind `EnergyForceEvaluator` should require explicit
reviewer/user approval before implementation.

| Slice | Why it is next | Required guardrails |
| --- | --- | --- |
| Extract a geometry-refresh helper behind the facade | Implemented: it remains the first step in `Compute_Energy_And_Force()` and has a clear output pair: face area/volume plus `Param::area`/`Param::vol`. | Preserve ghost filtering, regular/irregular path selection, Loop evaluator behavior, setup-time reference semantics, and serial/OpenMP numerical baselines. |
| Characterize the membrane term accumulation boundary | Implemented here as docs/scripts-only phase mapping. No production formulas or call timing changed. | Treat any future production extraction as review-gated because it touches formulas, scatter order, OpenMP reductions, and global constraint forces. |
| Extend scaffold-enabled evaluator characterization to Gag fixtures | Harmonic and synthetic idealized-lattice scaffold side effects are now covered through the shared helper/facade path, but no committed focused fixture currently initializes Gag-specific reaction targets for evaluator-level assertions. | Use existing scaffold fixtures where possible and avoid changing scaffold propagation, topology initialization, or Gag finite-difference behavior. |
| Defer propagation helper extraction | It would cross from core refresh into accepted-step, thermal, dynamics, records, and checkpoint policy. | Start only after a fresh behavior baseline and an explicit prompt approving propagation ownership changes. |

Suggested approved-production prompt:

```text
Create one narrow production slice behind EnergyForceEvaluator using the
side-effect map in docs/energy_force_evaluator_side_effect_boundary.md. Extract
only one named internal responsibility, keep all formulas, force scatter,
OpenMP reduction shape, scaffold timing, boundary handling, caller timing, and
propagation policy unchanged, and prove serial/OpenMP energy, force, area,
volume, scaffold-disabled behavior, output, and checkpoint-visible state remain
unchanged.
```
