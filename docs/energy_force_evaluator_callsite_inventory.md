# Energy Force Evaluator Call-Site Inventory

This note characterizes the direct `Mesh::Compute_Energy_And_Force()` callers
and `EnergyForceEvaluator` usage after PR #32. It is a docs/scripts-only map for
future consolidation work; it does not change production C++ behavior.

Regenerate the source inventory with:

```console
python3 scripts/inventory_energy_force_call_sites.py
```

The script reports current line numbers for reviewer convenience, but the
classification is path/context based and should not be treated as a line-number
assertion.

## Current Classification

| Classification | Current locations | Follow-up |
| --- | --- | --- |
| Production path already routed through evaluator facade | `src/Run_flat.cpp`, `src/Run_dynamics_flat.cpp`, `src/model/Energy_minimization.cpp` | Keep using file-local `evaluate_energy_force()` helpers unless a later PR deliberately changes ownership boundaries. |
| Facade implementation call | `src/energy_force/Energy_force_evaluator.cpp` | Keep as the only production direct call from the facade into `Mesh::Compute_Energy_And_Force()`. |
| Core implementation/API declaration | `src/energy_force/Compute_energy_and_force_on_mesh.cpp`, `include/mesh/Mesh.hpp` | Not routing candidates; these define and declare the existing physics method. |
| Intentional test/control direct call | `tests/test_energy_force_evaluator.cpp`, `tests/test_io.cpp`, `tests/test_optimization_algorithm.cpp` | Leave direct calls when they provide the control baseline or fixture setup. Route only in a test-specific cleanup PR with equivalent assertions. |
| Documentation reference | `docs/`, `src/energy_force/README.md` | Keep references current when production ownership changes. |
| Remaining production direct call requiring future review | None found after PR #32. | New production direct calls should be routed through `EnergyForceEvaluator` or explicitly justified. |

## Direct Test Calls

| Test surface | Why the direct call remains intentional |
| --- | --- |
| `EnergyForceEvaluatorTest.MatchesExistingMeshEnergyForceCall` | Compares the facade against the legacy direct mesh method; removing the direct control would weaken the equivalence test. |
| `tests/test_io.cpp` flat example helpers | Builds a finite-energy fixture for IO/checkpoint behavior, not evaluator routing behavior. It can stay direct unless the fixture setup itself becomes part of an evaluator cleanup. |
| `ThermalFluctuationTest.EnabledSwitchAttemptsMetropolisTrial` | Seeds an initial energy/force state before exercising thermal trial behavior; the test target is thermal bookkeeping and movement, not call routing. |

## Recommended Next Slices

There is no remaining mechanical production caller to route after PR #32. The
next useful work should be characterization or implementation behind the
facade, not another caller replacement.

Safe low-conflict options:

- Extend the inventory script only when new source roots or test fixture
  patterns appear.
- Add a focused test cleanup PR if reviewers want test fixture setup to use the
  evaluator, while preserving at least one direct-vs-facade equivalence test.
- Start a production implementation slice behind `EnergyForceEvaluator`, with a
  fresh numerical baseline for geometry extraction, force scatter order,
  OpenMP reductions, boundary force handling, scaffolding side effects, output
  cadence, and restart-visible state.

Suggested production follow-up prompt:

```text
Create a narrow production slice behind EnergyForceEvaluator without changing
caller timing: characterize the internal Mesh::Compute_Energy_And_Force()
sub-steps, choose one internal responsibility to extract behind the facade, and
prove serial/OpenMP energy, force, area, volume, output, and checkpoint-visible
state remain unchanged.
```
