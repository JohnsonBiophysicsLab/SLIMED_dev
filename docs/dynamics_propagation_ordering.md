# Dynamics Propagation Ordering

This note characterizes the current `run_dynamics_flat()` and
`DynamicModel` ordering before dynamics evaluator plumbing. It is a baseline,
not a target design.

## Startup Order

`run_dynamics_flat()` currently performs these setup steps before constructing
`DynamicModel`:

1. Import `<input>.params`, construct `DynamicMesh`, and call
   `DynamicMesh::setup_flat()`.
2. Set every vertex z coordinate to `10.0`.
3. Optionally apply insertion and scaffolding setup.
4. Write initial face and vertex CSV files:
   `<input>face.csv`, `<input>vertex_begin.csv`, and
   `<input>vertex_type_begin.csv`.
5. Compute initial element area/volume and membrane reference area/volume.
6. Copy current coordinates to `coordPrev`, then to `coordRef`.
7. Call the file-local `evaluate_energy_force()` helper, which routes through
   `EnergyForceEvaluator::evaluate()` to `Mesh::Compute_Energy_And_Force()`.
8. Copy current coordinates and current forces into previous-state storage.
9. Add the initial `Record` row from the freshly computed area, energy, and
   mean force.
10. Construct `DynamicModel`.
11. Copy vertex coordinates into `matMesh`, derive `matSurface`, and create
    initial dynamics trajectory files when `meshpointOutput` is enabled.

The initial force/energy evaluation therefore happens before model
construction and before the first trajectory file row.

## Main Loop Order

For each `model.iteration` from `0` to `maxIterations - 1`,
`run_dynamics_flat()` currently performs:

1. Refresh `matSurface` from the current `matMesh`.
2. Call `DynamicModel::next_step()`, which mutates `matSurface`.
3. Project `matSurface` back to `matMesh`.
4. Postprocess periodic ghost vertices when the boundary condition is periodic.
5. Copy `matMesh` back to `mesh.vertices[*].coord`.
6. Append dynamics trajectory rows when `meshpointOutput` is enabled.
7. Add a `Record` row.
8. Call `mesh.Compute_Energy_And_Force()`.
9. Print the iteration banner.

The important baseline is that the per-iteration `record.add()` call happens
after the coordinate update and trajectory append, but before the force/energy
recomputation for those updated coordinates. As a result, the record row added
inside iteration `N` uses the `Param::area`, `Param::energy`, and current
vertex forces that were available before the recomputation at the end of
iteration `N`. The end-of-loop recomputation prepares the force components that
`DynamicModel::next_step()` will consume on the next iteration.

The end-of-loop recomputation is the only remaining direct dynamics production
call after the PR #26 setup routing. Its ordering dependencies are:

| Neighboring state/action | Current ordering around recomputation | Routing caution |
| --- | --- | --- |
| Trajectory rows | Optional trajectory rows are appended before `record.add()` and before recomputation. | A routing PR should not move trajectory output after recomputation or alter the initial trajectory file creation. |
| Records | `record.add()` runs immediately before recomputation. | Preserve the current record-before-recompute behavior; records intentionally see the pre-recompute energy/force state for that iteration. |
| Force fields for dynamics | Recomputed force components are consumed by the next `DynamicModel::next_step()` call. | The evaluator call can replace the direct call only if it leaves force clearing, force scatter, and boundary force handling identical. |
| Iteration banner | The `=========ITERATION:N==========================` banner prints after recomputation. | Preserve stdout order so existing smoke logs remain comparable. |
| Loop termination | The `for` loop increments `model.iteration` after the banner and exits when `model.iteration == maxIterations`. | Do not add a final extra evaluation outside the current loop or skip the last in-loop recomputation. |
| Coordinate snapshots | The dynamics loop does not update previous-coordinate, previous-force, previous-energy, NCG, or restart snapshot state. | Do not introduce minimization-style snapshot ownership while routing this call. |
| RNG state | `DynamicModel::next_step()` is the RNG-consuming step; recomputation is deterministic with respect to dynamics RNG state. | Routing should not move, duplicate, or remove `next_step()` calls, and should not touch RNG construction or call counts. |
| Dynamics checkpointing | There is no dynamics restart checkpoint write or load in this loop. | Evaluator routing should stay independent of minimization checkpoint helpers and file formats. |

Before routing this call through `EnergyForceEvaluator`, require evidence that a
one-line replacement preserves:

- finite dynamics smoke output, including `EnergyForce.csv`;
- unchanged trajectory and final-output file timing for a short committed
  dynamics fixture;
- existing `DynamicModelCharacterizationTest` force-consumption and RNG
  characterization;
- the evaluator equivalence tests that compare `EnergyForceEvaluator` to the
  direct mesh call;
- the full build/test gate for both serial minimization and dynamics binaries.

## Force Inputs To DynamicModel

`DynamicModel::next_step()` does not call `Compute_Energy_And_Force()`. It reads
the current per-vertex force components already stored on the mesh, using
`forceCurvature + forceArea` for each coordinate component. The x and y
components are then zeroed before displacement, so the current implementation
only applies z displacement from the force term plus the stochastic term.

Future evaluator routing should preserve the current caller ownership:
`run_dynamics_flat()` owns the recomputation cadence, while
`DynamicModel::next_step()` consumes the most recently computed force fields.

## RNG State

`DynamicModel` owns public members `randomSeed`, `gen`, and `normal_dist`.
The constructor copies `mesh.param.randomSeed` into `randomSeed`, then declares
local variables named `gen` and `normal_dist`. Those local declarations shadow
the members, so the member RNG used by `next_step()` remains the default
constructed `std::mt19937` stream, and the member normal distribution remains
the default normal distribution.

This is current behavior only. Do not change RNG ownership, seeding, OpenMP
sharing, or call counts as part of evaluator plumbing.

## Output And Checkpoint Assumptions

Dynamics output currently includes:

- initial mesh files before the first force/energy evaluation;
- optional `surfacepoint<input>.csv` and `meshpoint<input>.csv` files with an
  initial row after `matMesh` and `matSurface` are initialized;
- optional trajectory rows appended after each dynamic coordinate update and
  before that iteration's force/energy recomputation;
- `EnergyForce.csv` after the loop from `DynamicModel::record`;
- final vertex CSV files after the loop.

There is no dynamics-specific restart checkpoint write or load path in the
current `run_dynamics_flat()` flow. The checkpoint helpers in `src/io/output.cpp`
operate on minimization `Model` state and include minimization fields such as
optimizer state, thermal RNG, previous forces, NCG direction, scaffold state,
and record history.

## Refactor Boundary

For dynamics evaluator plumbing, keep ownership boundaries narrow:

- route the end-of-loop recomputation separately from the setup evaluation;
- leave `record.add()` timing unchanged;
- leave `DynamicModel::next_step()` RNG behavior and force consumption
  unchanged;
- leave trajectory file timing and final output filenames unchanged;
- do not introduce dynamics checkpoint format changes in the evaluator slice.
