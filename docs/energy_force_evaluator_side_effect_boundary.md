# Energy Force Evaluator Side-Effect Boundary

This note characterizes the internal side-effect boundary of
`EnergyForceEvaluator` after PR #35. The production facade still delegates
directly to `Mesh::Compute_Energy_And_Force()`, so this is a current-state map,
not a proposal to split formulas or move calls.

Regenerate the source-side write inventory with:

```console
python3 scripts/inventory_energy_force_side_effects.py
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

## Scaffold-Enabled Characterization

`EnergyForceEvaluatorTest.SharedHelperRecordsScaffoldEnergyAndForceSideEffects`
protects the current scaffold-enabled helper path:

```text
evaluate_energy_force(Mesh&)
  -> EnergyForceEvaluator::evaluate(Mesh&)
     -> Mesh::Compute_Energy_And_Force()
     -> Mesh::calculate_scaffolding_energy_force(false)
```

The test uses a small flat mesh with one harmonic scaffold point bound to a
force-visible vertex. It verifies that the shared helper/facade route records
finite harmonic, Gag, and idealized-lattice energy components in
`Param::energy`, preserves disabled Gag/lattice terms as zero, adds the
harmonic contribution to the bonded vertex total force, and records the
equal/opposite scaffold force accumulators. This is intentionally a
harmonic-only fixture: it does not initialize Gag or idealized lattice topology,
does not propagate scaffold points, and does not change production C++ behavior.

## Side-Effect Map

| Surface | Current writes | Current reads and assumptions | Refactor caution |
| --- | --- | --- | --- |
| Element geometry | `Face::elementArea` and `Face::elementVolume` are refreshed by `calculate_element_area_volume()`. Ghost faces are skipped. | Reads current vertex coordinates, face one-ring topology, `Param::subMatrix`, `Param::subDivideTimes`, and shape/quadrature data. Regular `12`-control faces use the limit-surface evaluator path; irregular `11`-control faces use the existing subdivision path. | Preserve regular/irregular selection, Loop/OpenSubdiv contracts, quadrature order, ghost-face exclusion, and area/volume accumulation order. |
| Global area/volume | `Param::area` and `Param::vol` are reset and summed by `sum_membrane_area_and_volume(param.area, param.vol)`. | Reads current per-face area/volume and skips ghost faces. | Keep setup-time reference-area/reference-volume semantics separate from evaluator refresh semantics. |
| Current force and face energy clearing | Every `Vertex::force` is reset with `Force::set_all_zero()`. Every `Face::energy` is replaced with a default `Energy`. | Assumes previous-state fields have already been copied elsewhere if needed. | Do not move `coordPrev`, `forcePrev`, `energyPrev`, or `Param::energyPrev` into this boundary without a separate propagation baseline. |
| Per-face bending state | Non-boundary faces write `Face::normVector`, `Face::energy.energyCurvature`, and `Face::meanCurvature`. | Reads one-ring vertex coordinates, `Face::spontCurvature`, cached shape functions, quadrature coefficients, material constants, and current `Param::area`/`Param::vol` constraint values. | Preserve formula order, `sf(row, j)` access, fallback path, floating-point accumulation order, and boundary-face skip behavior. |
| Curvature/area/volume forces | Per-thread local arrays are reduced into `Vertex::force.forceCurvature`, `forceArea`, and `forceVolume`. | Reads face one-ring membership and current coordinates. | Preserve force scatter order, per-thread accumulation shape, OpenMP scheduling/reduction behavior, and serial/OpenMP numerical expectations. |
| Regularization | `Face::energy.energyRegularization`, `Vertex::force.forceRegularization`, and `Param::deformationCount` are updated by `energy_force_regularization()`. | Reads adjacent triangle coordinates, `Vertex::coordRef`, `Param::kCurv`, `Param::gamaShape`, `Param::gamaArea`, and `Param::usingRpi`. | Keep deformation classification, reference-coordinate reads, per-thread force accumulation, and count semantics unchanged. |
| Vertex total force | `Vertex::force.forceTotal` is recalculated after curvature/area/volume/regularization terms and updated again when scaffold bonds are enabled. | Reads all current force components on the vertex. | The scaffold path currently adds harmonic bond force to `forceTotal` after the first total-force calculation. Preserve that order until a dedicated physics change approves otherwise. |
| Face total energy and `Param::energy` | Each face calls `Energy::calculateTotalEnergy()`. A local `sumEnergy` accumulates face energies, global area/volume terms are applied, then `Param::energy` is replaced and total energy recalculated. | Reads `Param::isGlobalConstraint`, `Param::uSurf`, `Param::area0`, `Param::uVol`, `Param::vol0`, and the just-refreshed `Param::area`/`Param::vol`. | Do not split total-energy accounting from global constraint accounting without exact equivalence tests. |
| Optional harmonic/Gag/lattice scaffold energy | When `Param::isEnergyHarmonicBondIncluded` is true, `Param::energy.energyHarmonicBond`, `energyGagScaffolding`, and `energyIdealizedProteinLattice` are reset before `calculate_scaffolding_energy_force(false)`. That helper writes scaffold energy terms and recalculates `Param::energy.energyTotal`. | Reads scaffold points, scaffold-to-vertex correspondence, spring constants, Gag/lattice flags, and Gag reference/topology state. | Preserve disabled-scaffold behavior and the current distinction between harmonic membrane coupling, Gag internal energy, and idealized lattice energy. |
| Scaffold force state | `calculate_scaffolding_energy_force(false)` resets `forceTotalOnScaffolding` and `forceOnScaffoldingPoints`, writes bonded vertices' `forceHarmonicBond`, adds it to bonded vertices' `forceTotal`, and accumulates equal/opposite scaffold forces. | Reads `Param::scaffoldingPoints`, `Param::scaffoldingPoints_correspondingVertexIndex`, `Param::lbond`, `Param::springConst`, and current bonded vertex coordinates. | Do not mix evaluator refresh with scaffold propagation. `propagate_scaffolding()` remains caller-owned policy. |
| Boundary/ghost force handling | `manage_force_for_boundary_ghost_vertex()` replaces whole `Vertex::force` objects with zero force for fixed/free/periodic boundary cases according to the existing branch logic. | Reads `Param::boundaryCondition`, face boundary flags, vertex boundary/ghost flags, and `Param::nFaceX`/`Param::nFaceY` for free boundaries. | Preserve zeroing scope and ordering after scaffold force application. Boundary force handling is output- and trajectory-visible. |
| Output/checkpoint-visible state | No files are written directly, but `Param::area`, `Param::vol`, `Param::energy`, current vertex forces, face energy/geometry fields, and scaffold force fields become visible to records, output, checkpoints, and later propagation. | Caller timing determines when records/checkpoints consume refreshed state. | Do not move record/checkpoint/output calls into the evaluator. |

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
| Extract a geometry-refresh helper behind the facade | It is the first step in `Compute_Energy_And_Force()` and has a clear output pair: face area/volume plus `Param::area`/`Param::vol`. | Preserve ghost filtering, regular/irregular path selection, Loop evaluator behavior, setup-time reference semantics, and serial/OpenMP numerical baselines. |
| Extract force/energy clearing as a named pre-pass | It is already a separate mesh helper and covered by stale-force evaluator tests. | Keep it behind the facade and do not change when previous-state snapshots are taken. |
| Extend scaffold-enabled evaluator characterization to Gag or idealized lattice fixtures | Harmonic scaffold side effects are now covered through the shared helper/facade path, but no committed focused fixture currently initializes internal Gag/lattice topology for evaluator-level assertions. | Use existing scaffold fixtures where possible and avoid changing scaffold propagation, topology initialization, or Gag finite-difference behavior. |
| Defer propagation helper extraction | It would cross from core refresh into accepted-step, thermal, dynamics, records, and checkpoint policy. | Start only after a fresh behavior baseline and an explicit prompt approving propagation ownership changes. |

Suggested approved-production prompt:

```text
Create one narrow production slice behind EnergyForceEvaluator using the
side-effect map in docs/energy_force_evaluator_side_effect_boundary.md. Extract
only the geometry-refresh or clearing pre-pass responsibility, keep all caller
timing and propagation policy unchanged, and prove serial/OpenMP energy, force,
area, volume, scaffold-disabled behavior, output, and checkpoint-visible state
remain unchanged.
```
