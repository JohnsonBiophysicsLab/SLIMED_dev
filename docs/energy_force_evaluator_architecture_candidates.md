# Energy Force Evaluator Architecture Cleanup Candidates

This note characterizes the next `EnergyForceEvaluator` architecture cleanup
candidates after PR #33 and records that the narrow helper-consolidation,
clearing pre-pass implementation placement, and geometry-refresh extraction
slices have been implemented. It is kept as a decision aid for future cleanup.

Regenerate the source call-site and helper inventory with:

```console
python3 scripts/inventory_energy_force_call_sites.py --helpers
```

For the internal side-effect boundary of the current facade call, see
`docs/energy_force_evaluator_side_effect_boundary.md` and regenerate its
write-surface and phase-map inventories with:

```console
python3 scripts/inventory_energy_force_side_effects.py
python3 scripts/inventory_energy_force_side_effects.py --phase-map
```

## Current Boundary

PR #33 left no production direct `Mesh::Compute_Energy_And_Force()` callers
outside `src/energy_force/Energy_force_evaluator.cpp`. The remaining production
refreshes all route through the shared `evaluate_energy_force(Mesh&)` helper
declared in `include/energy_force/Energy_force_evaluator.hpp` and implemented
next to the `EnergyForceEvaluator` facade:

| File | Shared helper refreshes |
| --- | --- |
| `src/Run_flat.cpp` | Initial setup, restart reload, and accepted deterministic/thermal/scaffold step refresh. |
| `src/Run_dynamics_flat.cpp` | Initial setup and end-of-loop dynamics refresh. |
| `src/model/Energy_minimization.cpp` | Line-search trial evaluation and thermal trial/rejection evaluation. |

`Energy_minimization.cpp` already uses the facade through this shared helper.
That file is therefore not a remaining direct-call-routing candidate. Any next
change there should be treated as production architecture cleanup around helper
ownership or trial-evaluation policy, not as mechanical routing.

## Candidate Slices

| Candidate slice | Why consider it | Risk | Expected files touched | Required validation | Approval needed |
| --- | --- | --- | --- | --- | --- |
| Keep the shared helper and move implementation work behind `EnergyForceEvaluator` | Partly implemented: the clearing pre-pass and geometry refresh are now named inside the existing implementation boundary. Remaining slices should avoid cross-mode coupling while enabling internal physics extraction behind the existing facade. | Medium: internal extraction can disturb formula order, force scatter, OpenMP reductions, scaffolding side effects, or boundary force handling. | `src/energy_force/*`, `include/energy_force/*`, focused tests/docs. | `make test`, `./bin/test_main`, evaluator equivalence tests, OpenMP/serial numerical baseline, accepted-step smoke if runner behavior is touched. | Yes, because production physics code changes. |
| Extract actual membrane term accumulation after clearing | This is the next visible boundary after the geometry-refresh and clearing helpers: the face loop computes bending energy plus curvature, area, and volume force terms before regularization and totals. | High: the region contains formulas, quadrature order, one-ring coordinate capture, regular/irregular path selection, per-thread force accumulation, and reduction into vertex force components. | `src/energy_force/Compute_energy_and_force_on_mesh.cpp`, possibly a new internal implementation file/header, focused tests/docs. | Fresh serial/OpenMP numerical baseline, evaluator equivalence tests, force-component comparisons, boundary/ghost checks, scaffold-disabled and scaffold-enabled checks, accepted-step smoke if timing moves. | Yes, explicit reviewer/domain approval recommended before starting. |
| Consolidate local `evaluate_energy_force(Mesh&)` wrappers into a shared helper | Implemented: removes three duplicated wrappers and makes routed refreshes visually uniform. | Low to medium: the helper is simple, but a shared header couples runners and model code through a named evaluator utility. | `include/energy_force/Energy_force_evaluator.hpp`, `src/energy_force/Energy_force_evaluator.cpp`, `src/Run_flat.cpp`, `src/Run_dynamics_flat.cpp`, `src/model/Energy_minimization.cpp`; docs/scripts updates. | Full test gate plus accepted-step smoke; compare helper inventory before/after; no output/checkpoint diffs expected. | Yes, because production C++ files and ownership boundaries change. |
| Replace local wrappers with direct `EnergyForceEvaluator evaluator; evaluator.evaluate(mesh);` at each call site | Removes helper indirection without adding a shared API. | Low: call timing should remain unchanged, but repeated object construction statements add visual noise at sensitive loop points. | `src/Run_flat.cpp`, `src/Run_dynamics_flat.cpp`, `src/model/Energy_minimization.cpp`; docs updates. | Full test gate plus accepted-step smoke; reviewer check that no neighboring state moved. | Yes, because production C++ call sites change. |
| Add a shared propagation helper that owns refresh plus adjacent snapshots | Could reduce duplicated ordering in runners if broader propagation ownership is desired. | High: easily changes previous-state snapshots, records, checkpoints, thermal rollback, dynamics record-before-recompute behavior, or restart-visible state. | Runners, `Model`, possible new propagation header/source, IO/checkpoint tests/docs. | Fresh behavior baseline for minimization, thermal, restart, dynamics trajectory, records, checkpoints, serial/OpenMP output. | Yes, explicit reviewer/user approval recommended before starting. |
| Test-fixture cleanup to route non-control direct calls through the facade | Makes tests mirror production routing while retaining at least one direct-vs-facade control. | Low: fixture setup only, but careless cleanup can weaken the evaluator equivalence test. | `tests/test_io.cpp`, `tests/test_optimization_algorithm.cpp`, docs. | `make test`, `./bin/test_main`; verify `EnergyForceEvaluatorTest.MatchesExistingMeshEnergyForceCall` still uses a direct control. | Usually yes, but can be a small test-only PR if reviewers agree. |
| Documentation-only refresh as architecture changes land | Keeps PR #25/#29/#30/#33 notes aligned with future production changes. | Low: no production behavior. | `docs/*`, optionally `scripts/inventory_energy_force_call_sites.py`. | `git diff --check`, Python syntax check if scripts changed. | No special approval beyond normal docs review. |

## Shared Helper Entry Point

The shared helper-consolidation slice made `evaluate_energy_force(mesh)` a
named project-level operation at the existing evaluator boundary. The helper
owns no propagation policy: it constructs `EnergyForceEvaluator` and calls
`evaluate(mesh)`. Runners and `Model` code still own every refresh call
location and all neighboring snapshots, records, checkpoints, optimizer state,
output cadence, and thermal/dynamics policy.

Do not combine helper consolidation with propagation helper extraction. The
current runner/model code owns important neighboring state:

- `run_flat()` owns accepted-step snapshots, `energyPrev`, NCG direction,
  records, output cadence, checkpoints, and iteration increment.
- `Energy_minimization.cpp` owns line-search trial restore paths and thermal
  acceptance/rejection reevaluation.
- `run_dynamics_flat()` owns record-before-recompute behavior and force
  preparation for the next dynamics step.

Moving any of that state into a shared helper would need a separate baseline
and explicit review.

## Missing Evidence Before Production Cleanup

Before a production helper-consolidation or behind-facade extraction PR, collect
or preserve:

- the internal side-effect boundary in
  `docs/energy_force_evaluator_side_effect_boundary.md`;
- evaluator equivalence and stale-force clearing tests;
- scaffold-enabled harmonic evaluator characterization through
  `EnergyForceEvaluatorTest.SharedHelperRecordsScaffoldEnergyAndForceSideEffects`;
- accepted-step smoke output from the committed PR #32 fixture;
- restart/checkpoint evidence if `run_flat()` neighboring state moves;
- dynamics smoke evidence if `run_dynamics_flat()` ordering moves;
- thermal attempt/rollback evidence if `Energy_minimization.cpp` trial
  evaluation moves;
- serial and OpenMP-sensitive numerical comparisons if code inside
  `Mesh::Compute_Energy_And_Force()` is split.
- a reviewer-approved data contract if the face-loop extraction crosses the
  current `Mesh`/`Face`/`Param` ownership boundary or changes helper
  signatures.

## Recommended Next Production Prompt

```text
Create a narrow production cleanup without changing evaluator call timing.
Prefer one slice only: extract one internal responsibility behind
EnergyForceEvaluator, or perform docs/test cleanup around the now-shared
evaluate_energy_force(Mesh&) helper. If the slice touches membrane term
accumulation, get reviewer/domain approval first and preserve formulas,
floating-point accumulation order, force scatter, OpenMP reductions,
regular/irregular Loop behavior, scaffolding side effects, boundary handling,
and output cadence. Do not move propagation snapshots, records, checkpoints,
RNG calls, or optimizer state. Provide before/after helper inventory, full test
validation, and the PR #32 accepted-step smoke if any runner or Model call site
is touched.
```
