# run_flat Accepted-Step Ordering

This note characterizes the `run_flat()` accepted-step evaluator routing after
the direct production `Mesh::Compute_Energy_And_Force()` caller was replaced by
the file-local evaluator helper. It records the preserved ordering for future
mechanical refactor slices.

## Direct Call Inventory

Outside the `EnergyForceEvaluator` implementation itself, production refreshes
in `run_flat()`, the minimization line search, thermal trial evaluation, and
both `run_dynamics_flat()` production surfaces route through file-local
`evaluate_energy_force()` helpers.

Test direct calls remain intentional controls or fixture setup.

## Main Deterministic Loop Order

For the non-pure-MMC branch, each accepted deterministic minimization iteration
currently performs:

1. Check `Model::should_continue_optimization()` from the existing
   `Record` history and current `model.iteration`.
2. Call `Model::determine_trial_step_size()`, which reads current force and
   energy state to update `model.oa.trialStepSize`.
3. If the trial step is negative and thermal fluctuations are enabled, attempt
   `Model::simulated_annealing_next_step()`. An accepted thermal move in this
   fallback path snapshots previous state, updates `energyPrev`, resets and
   updates NCG direction, records, prints, increments `model.iteration`, and
   continues without reaching the direct accepted-step refresh.
4. Call `Model::linear_search_for_stepsize_to_minimize_energy()`. Trial
   evaluations inside the line search already use `EnergyForceEvaluator`.
   Failed searches restore coordinates or stop before the accepted-step
   refresh. Accepted searches leave `model.stepSize` and trial state for the
   accepted deterministic step.
5. Print `model.to_string_current_step()`.
6. Reapply the accepted deterministic displacement with
   `Model::update_vertex_using_NCG()`.
7. Optionally call `Model::simulated_annealing_next_step()`. The thermal helper
   evaluates the displaced thermal trial and, on rejection, restores coordinates
   and evaluates again. If a thermal attempt happened, `run_flat()` resets the
   NCG direction before continuing.
8. Optionally scale the harmonic spring constant and reset the NCG direction.
9. Optionally propagate scaffolding, reset closest-vertex correspondence, and
   reset the NCG direction.
10. Call the accepted-step refresh through the file-local evaluator helper:
    `evaluate_energy_force(mesh)`.
11. Copy current coordinates to `coordPrev`.
12. Copy current face energy into previous face energy storage.
13. Set `mesh.param.energyPrev = mesh.param.energy`.
14. Update the NCG direction from previous force, current force, and the current
    direction vector.
15. Copy current forces to `forcePrev`.
16. Set `model.oa.trialStepSize = model.stepSize`.
17. Add a `Record` row from current area, current energy, and current mean
    force.
18. Optionally write an initial-step mesh/scaffold snapshot for the first five
    iterations.
19. Optionally update reference coordinates based on recent record deltas.
20. Update NCG stuck/disabled state.
21. Print the iteration record.
22. Optionally write the periodic vertex/scaffold snapshot for
    `model.iteration`.
23. Optionally write a restart checkpoint for `model.iteration + 1`.
24. Increment `model.iteration`.

The refresh therefore owns only current energy/force recomputation for the
post-acceptance state. Previous-state snapshots, `energyPrev`, NCG state,
records, output cadence, checkpoints, and loop termination remain caller-owned
behavior.

## Neighboring State Risks

| Neighboring state/action | Current ordering around refresh | Routing caution |
| --- | --- | --- |
| Accepted/rejected line-search trials | Rejected or failed searches stop before the refresh. Accepted searches reach the refresh after the deterministic displacement is applied in the main loop. | A routing PR should be a one-call replacement only; it must not move line-search acceptance, rollback, or status handling. |
| Thermalized minimization | The post-deterministic thermal helper evaluates accepted trial coordinates, and reevaluates after rollback when rejected. The main-loop refresh still runs afterward. | Do not change thermal RNG calls, Metropolis diagnostics, rejection rollback, or the number/timing of evaluations. |
| Pure MMC mode | The pure-MMC branch snapshots and records after `simulated_annealing_next_step(true)` and does not use the accepted-step direct refresh. | Do not route or restructure pure-MMC behavior in the accepted-step slice. |
| `coordPrev` and face-energy snapshots | Snapshot calls run immediately after the refresh. | The evaluator must not take ownership of previous-coordinate or previous-energy state. |
| `energyPrev` | `energyPrev` is assigned after current energy is refreshed and after face-energy snapshots. | Preserve assignment timing and value source for line-search and restart continuity. |
| NCG direction and `forcePrev` | `update_ncg_direction()` reads current force before `update_previous_force_for_vertex()` overwrites `forcePrev`. | Preserve the order: refresh, coordinate/energy snapshots, `energyPrev`, direction update, then force snapshot. |
| Records | `record.add()` runs after the refresh and force snapshot, using current area, energy, and mean force. | Preserve minimization record-after-recompute behavior, which differs from dynamics record-before-recompute behavior. |
| Initial-step snapshots | Early mesh/scaffold snapshots happen after the record row is added. | Do not move output before the accepted-state refresh. |
| Reference updates | Reference coordinates can update after comparing the newly added row with the previous row. | Preserve record index assumptions and comparison timing. |
| Checkpoints | Checkpoints are written near the end of the iteration for `model.iteration + 1` and include current/previous coordinates, current/previous force, NCG direction, optimizer state, thermal state, scaffold state, and records. | The refresh replacement must not alter checkpoint cadence or serialized field values. |
| Iteration logging and termination | `Record::print_iteration()` runs before snapshots/checkpoint and before `model.iteration++`; loop termination is checked at the next loop head. | Preserve stdout order and avoid adding any final extra evaluation. |

## Evidence Required For Routing

This production route is preserved by showing:

- The evaluator equivalence tests still pass, especially direct-call parity and
  repeated-evaluation clearing of stale force/energy state.
- The committed accepted-step minimization smoke staged by
  `scripts/stage_accepted_step_smoke.py` produces finite `EnergyForce.csv`
  data rows, including at least one post-initial record from the accepted-step
  branch. Validate the CSV with `scripts/check_accepted_step_smoke.py`.
- A thermal-enabled fixture with a fixed seed preserves thermal attempt count,
  diagnostics, restart serialization, and accepted/rejected rollback behavior.
- A restart checkpoint smoke path preserves `coord`, `coordPrev`, current and
  previous force, NCG direction, optimizer fields, thermal RNG state, scaffold
  state, and record history across the accepted-step boundary.
- The full validation gate passes for tests plus the serial executable build.

The production implementation is a narrow replacement of
`mesh.Compute_Energy_And_Force()` with the existing `evaluate_energy_force(mesh)`
helper in `run_flat()`. If future work requires moving any neighboring state
update, stop and collect a fresh behavior baseline instead.
