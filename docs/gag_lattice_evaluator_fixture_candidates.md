# Gag And Idealized-Lattice Evaluator Fixture Candidates

This note records the docs/tests-only characterization performed after PR #37.
It distinguishes actual evaluator-facing coverage added for idealized lattice
accounting from the Gag-specific fixture inputs that are still missing.

## Current Coverage

`EnergyForceEvaluatorTest.SharedHelperRecordsIdealizedLatticeScaffoldEnergy`
uses `tests/fixtures/idealized_two_subunit_lattice.dat`, a synthetic
two-subunit reference state with one bound interface pair. The test initializes
the idealized topology at the reference COM positions, perturbs one COM by
`0.5` nm, and evaluates through the shared `evaluate_energy_force(Mesh&)`
helper. With `gagKsigma = 3.0` and angle/torsion constants disabled, the
expected idealized internal energy is:

```text
0.5 * 3.0 * (0.5)^2 = 0.375
```

The test verifies that:

- the shared helper/facade path records finite harmonic, Gag, and
  idealized-lattice components in `Param::energy`;
- the harmonic and Gag components remain zero for this fixture;
- `energyIdealizedProteinLattice` records the expected nonzero internal
  lattice energy;
- `energyTotal` increases by the same amount relative to an unscaffolded
  baseline mesh; and
- scaffold force accumulator storage is populated without changing production
  C++ behavior.

This fixture is intentionally mechanical. It characterizes current evaluator
side effects for a deterministic idealized topology, but it is not scientific
validation of a Gag lattice.

## Candidate Map

| Mode | Required inputs for nonzero evaluator-visible energy | Current repo state | Low-conflict status |
| --- | --- | --- | --- |
| Harmonic scaffold | `isEnergyHarmonicBondIncluded = true`, scaffold COMs, scaffold-to-vertex correspondence, `springConst`, and `lbond`. | Covered by `SharedHelperRecordsScaffoldEnergyAndForceSideEffects`. | Covered. |
| Idealized protein lattice | Harmonic scaffold gate enabled, `isIdealizedProteinLatticeEnergyIncluded = true`, `idealizedProteinLatticeFileName`, scaffold COMs matching the reference count, initialized topology, and nonzero Gag stiffness constants for the selected idealized terms. | Covered by the synthetic two-subunit fixture and a post-initialization COM perturbation. | Covered as evaluator-side-effect characterization only. |
| Gag scaffold | Harmonic scaffold gate enabled, `isGagScaffoldingEnergyIncluded = true`, `gagReferenceStateFileName`, matching scaffold COMs, `gagReactionFileName` with reaction targets for bound interface pairs, initialized topology, and nonzero Gag stiffness constants for sigma/angle/torsion terms. | COM-only scaffold CSVs are committed. No representative reference-state `.dat` or matching NERDSS reaction `.inp` fixture is committed. | Candidate-only; do not synthesize biological reaction parameters without domain signoff. |

## Recommended Gag Fixture Prompt

```text
Provide or approve a small representative Gag scaffold fixture for evaluator
characterization. Include the selected-complex/reference-state `.dat` file, the
matching NERDSS reaction `.inp` file containing sigma and assocAngles for each
bound interface pair, the intended Gag stiffness constants, and whether the
test should assert a positive energy after a controlled COM perturbation or a
known exact energy value. Keep the resulting slice docs/tests-only and do not
change production C++ behavior, scaffold propagation, topology initialization,
finite-difference settings, or evaluator call timing.
```
