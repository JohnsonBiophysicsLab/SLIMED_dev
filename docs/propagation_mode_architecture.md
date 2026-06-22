# Propagation Mode Architecture Characterization

This note characterizes the propagation-mode boundaries after PR #26
(`b6a57c9`, "Merge pull request #26 from
JohnsonBiophysicsLab/codex/dynamics-setup-evaluator-routing"). It was
introduced as the PR #25 call-site map and is kept current as narrow
evaluator-routing slices land.

## Current Energy/Force Entry Points

`EnergyForceEvaluator` is a narrow facade over
`Mesh::Compute_Energy_And_Force()`. The evaluator preserves the mesh method's
current behavior: it refreshes element geometry, current face energies, current
vertex forces, `Param::energy`, optional scaffolding energy/force terms, and
boundary force handling. It does not own previous-state snapshots, optimizer
state, records, RNG, checkpoint/output cadence, or propagation policy.

Current production call sites:

| Mode/surface | Call path | Notes |
| --- | --- | --- |
| Minimization line search | `Model::linear_search_for_stepsize_to_minimize_energy()` -> local `evaluate_energy_force()` -> `EnergyForceEvaluator::evaluate()` -> `Mesh::Compute_Energy_And_Force()` | Trial coordinates are evaluated inside the line search. Rejected/failed trials may restore coordinates before returning. |
| Thermalized minimization | `Model::simulated_annealing_next_step()` -> local `evaluate_energy_force()` -> `EnergyForceEvaluator::evaluate()` -> `Mesh::Compute_Energy_And_Force()` | The thermal trial evaluates the displaced mesh and evaluates again after rollback when the Metropolis trial is rejected. |
| Flat minimization executable setup/restart | `run_flat()` -> local `evaluate_energy_force()` -> `EnergyForceEvaluator::evaluate()` -> `Mesh::Compute_Energy_And_Force()` | Used for initial force/energy setup before `Model` construction and after restart load. PR #22 routed these calls through the evaluator without moving their timing. |
| Flat minimization executable main loop | `run_flat()` -> `mesh.Compute_Energy_And_Force()` | Direct call used after applying the accepted deterministic/thermal/scaffolding step, before previous-state snapshots, NCG direction update, records, snapshots, checkpoints, and iteration increment. |
| Dynamics executable setup | `run_dynamics_flat()` -> local `evaluate_energy_force()` -> `EnergyForceEvaluator::evaluate()` -> `Mesh::Compute_Energy_And_Force()` | Used for initial force/energy setup before `DynamicModel` construction. |
| Dynamics executable main loop | `run_dynamics_flat()` -> `mesh.Compute_Energy_And_Force()` | The loop records current energy/force before this recomputation, then recomputes force/energy for the next dynamic displacement. Preserve this ordering until a dynamics-specific baseline says otherwise. |

Remaining production direct-call inventory:

| File | Surface | Relative risk | Refactor note |
| --- | --- | --- | --- |
| `src/Run_dynamics_flat.cpp` | End-of-loop evaluation after dynamics coordinate update | Medium | Keep the current `record.add()` before recomputation and preserve the force fields prepared for the next `DynamicModel::next_step()` call. Route in a separate PR from setup. |
| `src/Run_flat.cpp` | Accepted-step minimization refresh | Medium | Keep the existing order relative to previous-state snapshots, `energyPrev`, NCG direction update, records, snapshots, checkpoints, and iteration increment. Route separately from dynamics setup. |

Direct calls in tests remain intentional controls or fixture setup for
characterization. They do not need evaluator routing unless a future test is
specifically exercising the facade.

## Responsibility Map

| Responsibility | Current owner | Refactor caution |
| --- | --- | --- |
| Core energy/force refresh | `Mesh::Compute_Energy_And_Force()` through optional `EnergyForceEvaluator` facade | Do not alter formula selection, force scatter order, OpenMP reductions, boundary force handling, or floating-point accumulation order. |
| Element area/volume and `Param::area`/`Param::vol` refresh | `Mesh::Compute_Energy_And_Force()` and setup code in `run_flat()`/`run_dynamics_flat()` | Setup computes initial references before the first full energy/force evaluation. Keep reference-area/volume semantics separate from evaluator plumbing. |
| Deterministic minimization stepping | `run_flat()` plus `Model::determine_trial_step_size()`, `Model::linear_search_for_stepsize_to_minimize_energy()`, and `Model::update_vertex_using_NCG()` | Line-search status, accepted step size, coordinate restore paths, and NCG direction update order are behavior. |
| Line search | `Model::linear_search_for_stepsize_to_minimize_energy()` and `OptimizationAlgorithm` | The inner trial evaluations already use `EnergyForceEvaluator`; future work should avoid changing acceptance predicates or failure statuses. |
| Thermal acceptance/revert | `Model::simulated_annealing_next_step()` | Owns trial vertex selection, displacement distribution, Metropolis acceptance, rollback coordinates, second evaluation after rejection, diagnostics, and attempt count. |
| Thermal RNG | `Model::thermalRng`, seeded from `Param::randomSeed`, serialized by restart checkpoints | Any call count change changes reproducibility and checkpoint continuation. |
| Dynamics stepping | `DynamicModel::next_step()` and `run_dynamics_flat()` | Uses `DynamicModel` RNG members and force components from the previous recomputation to update limit-surface coordinates. The current constructor declares local RNG variables with the same names as members; do not "fix" this inside evaluator plumbing. |
| Force clearing | `Mesh::Compute_Energy_And_Force()` via `clear_force_on_vertices_and_energy_on_faces()` | Existing `EnergyForceEvaluatorTest.RepeatedEvaluationClearsStaleForceAndFaceEnergy` characterizes this boundary. |
| Previous coordinate/force/energy snapshots | `run_flat()` and `Model` helpers such as `update_previous_coord_for_vertex()` and `update_previous_force_for_vertex()` | Snapshot order defines line-search inputs, restart contents, and records. The evaluator must not take ownership of this state without a dedicated baseline. |
| State rollback | `Model::linear_search_for_stepsize_to_minimize_energy()` and `Model::simulated_annealing_next_step()` | Coordinate restoration and reevaluation after thermal rejection are propagation policy, not core physics. |
| Records | `Record` owned by `Model`/`DynamicModel` runners | `record.add()` timing differs by mode. In minimization it follows accepted state refresh; in dynamics the loop records before recomputing for the next step. |
| Checkpoint cadence and contents | `run_flat()` helpers plus `write_model_restart_checkpoint()`/`load_model_restart_checkpoint()` | Checkpoints store next iteration, optimizer fields, thermal RNG stream, thermal attempt count, spring/scaffold state, coordinates, current/previous force, NCG direction, and record history. |
| Output cadence and formats | `run_flat()`, `run_dynamics_flat()`, `src/io/output.cpp`, and mesh writer methods | Preserve filenames, iteration labels, and final output timing in evaluator-routing PRs. |

## Core Evaluation State Boundary

Current evaluation reads:

- Mesh topology and face one-ring relationships.
- Current vertex coordinates and boundary/ghost metadata.
- Shape-function and quadrature data, including the PR #20 regular
  limit-surface extraction path.
- `Param` constants for constraints, regularization, scaffolding, insertion,
  boundary conditions, and reference area/volume.
- Scaffolding state when harmonic/scaffold energies are enabled.

Current evaluation writes:

- Per-face element area, volume, normal, mean curvature, and energy terms.
- `Param::area`, `Param::vol`, and `Param::energy`.
- Current per-vertex force components and total force.
- Boundary/ghost force adjustments.
- Scaffolding energy/force side effects when enabled.

Current evaluation should not write:

- `coordPrev`, `coordRef`, `forcePrev`, `energyPrev`, `ncgDirection0`, `Record`
  history, `Model::iteration`, optimizer statuses, thermal RNG state, thermal
  diagnostics, checkpoint contents, or output files.

## Existing Characterization Coverage

`tests/test_energy_force_evaluator.cpp` already provides the narrow deterministic
coverage needed before production separation:

- `EnergyForceEvaluatorTest.MatchesExistingMeshEnergyForceCall` verifies the
  evaluator matches a direct `Mesh::Compute_Energy_And_Force()` call on the
  tiny flat fixture.
- `EnergyForceEvaluatorTest.RepeatedEvaluationClearsStaleForceAndFaceEnergy`
  verifies repeated evaluator calls clear stale current forces and face energy.
- `EnergyForceEvaluatorTest.FlatExampleProducesFiniteEnergyAndForce` protects a
  representative example-params evaluation from non-finite energy/force.

Those tests cover the current evaluator boundary after PR #20 without running
long simulations. Adding source-scanning tests for call-site names would be
brittle and would not protect numerical behavior; prefer extending C++ tests
only when a production call site is actually routed through the evaluator.

`tests/test_dynamics.cpp` and `docs/dynamics_propagation_ordering.md`
characterize the dynamics-specific force-consumption and record-before-recompute
ordering that should be preserved before routing the dynamics loop call site.

## Remaining Production Slices

The `run_dynamics_flat()` setup evaluation now uses a file-local evaluator
helper with no change to call timing. That slice keeps propagation policy,
dynamics RNG behavior, records, trajectory timing, checkpoints, and line-search
behavior outside the evaluator. It also avoids the dynamics loop, where
record-before-recompute ordering deserves a separate production PR even though
it already has a documentation/test baseline.

The next candidates are either the dynamics end-of-loop recomputation or the
`run_flat()` accepted-step refresh. Keep them separate unless a reviewer
explicitly asks for a single mechanical sweep.

## Stop Conditions For Later Refactors

Stop and collect a fresh baseline instead of continuing a production refactor if
any change would affect:

- RNG call counts, RNG state serialization, thermal trial selection, or
  thermal accept/reject probabilities.
- Line-search acceptance predicates, failure statuses, coordinate restore paths,
  or step-size update order.
- Thermal rejection rollback or the second energy/force evaluation after
  rollback.
- Checkpoint timing, checkpoint fields, restart load order, or output filenames
  and iteration labels.
- OpenMP pragmas, scheduling, reductions, per-thread force accumulation, or
  serial/OpenMP floating-point accumulation order.
- Force/energy formulas, regular/irregular patch selection, Loop/OpenSubdiv
  evaluator behavior, or PR #20 geometry extraction semantics.
- Record timing, especially the current difference between minimization and
  dynamics.
- Broad file moves, shared ownership changes, or style cleanup that would make
  baseline diffs harder to review.
