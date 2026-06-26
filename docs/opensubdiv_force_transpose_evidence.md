# OpenSubdiv Force Transpose Evidence Map

Date: 2026-06-26.
Baseline: `origin/main` at `653bb409e3abb7595a164e43fda71bcbfb2ed66a`
after PR #69.

This is a docs/scripts-only evidence lane. It does not change production C++
behavior, default build policy, OpenSubdiv dependency policy, force formulas,
force scatter ordering, OpenMP behavior, backend routing, checkpoint/output
formats, propagation behavior, or `LimitSurfaceEvaluator` behavior.

## Purpose

This note separates three kinds of evidence that are easy to blur:

- OpenSubdiv row/integrand equivalence for regular samples;
- toy-linear transpose evidence for OpenSubdiv row weights; and
- actual bending, area, and volume force transpose evidence through SLIMED's
  production formulas and scatter order.

Only the first two OpenSubdiv items are currently evidenced by the opt-in
probe. SLIMED also has production-side formula/scatter characterization and a
dependency-free positive-depth `11 = 4+3+4` subdivision-matrix route, but
neither of those proves OpenSubdiv-backed actual force transpose correctness.

## Current Evidence Matrix

| Evidence item | Current anchor | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Regular OpenSubdiv row/integrand equivalence | `scripts/probe_opensubdiv_feasibility.py --regular-equivalence-report` | Observed regular OpenSubdiv value, derivative, tangent, normal, area-integrand, and legacy-volume-integrand values can match frozen SLIMED regular values under the documented `s=v,t=w` mapping. | It does not pass sample gradients through bending, area, or volume force formulas. |
| Regular OpenSubdiv toy transpose | `scripts/probe_opensubdiv_feasibility.py --force-transpose-report` emits `kind: toy_linear_functional_only`. | A deterministic toy gradient satisfies `g dot (W p) == (W^T g) dot p` for OpenSubdiv regular row weights and a SLIMED-compatible seven-row shape. | It does not compute `fBend`, `fArea`, `fVol`, per-control formula terms, quadrature accumulation, or production scatter. |
| Production regular formula/scatter characterization | `docs/force_formula_scatter_equivalence.md`, `scripts/inventory_force_formula_scatter_contract.py`, and the focused regular tests. | Current bending, area, and volume formulas consume seven SLIMED rows, produce local force matrices, and scatter them through `Face::oneRingVertices` into the thread-local force buffer. | It uses the in-tree SLIMED evaluator/source-id seam; it is not evidence that OpenSubdiv row weights have been routed through those actual formulas. |
| Positive-depth 11-control production route | `SurfaceSubdivisionCharacterization.SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces` and `scripts/inventory_irregular_routing_evidence.py`. | The dependency-free `11 = 4+3+4` route transposes child regular bending, area, and volume force rows through existing subdivision matrices back to the 11 original rows. | It is not OpenSubdiv-backed and does not approve broader irregular topologies, zero-depth 11-control requests, or dependency-present behavior. |
| Irregular OpenSubdiv observational proof map | `scripts/probe_opensubdiv_feasibility.py --irregular-transpose-proof-map-report` emits `kind: observational_all_ptex_grid_toy_transpose`. | Aggregate all-ptex/sample-grid source visibility and toy transpose shape can be inspected for the 11-control fixture variants. | It does not select a ptex/sample plan for one SLIMED face and does not run actual force formulas or production scatter. |

## Missing Actual Force Transpose Evidence

Before production OpenSubdiv backend routing can claim actual SLIMED force
transpose correctness, a later lane must provide all of the following evidence
or record explicit reviewer-approved waivers:

1. A backend sample plan for one SLIMED face, including ptex faces, child
   patches, sample coordinates, quadrature weights, orientation, and row order.
2. Row weights keyed by original SLIMED vertex ids for every selected sample,
   not transient OpenSubdiv control ids.
3. A reviewed derivative convention from OpenSubdiv rows to SLIMED's seven rows,
   including the current duplicated mixed-row convention.
4. Regular actual-force transpose through the production bending, area, and
   volume formulas, producing the same local `fBend`, `fArea`, `fVol`, energy,
   normal, area, and volume results as the current regular path within stated
   tolerances.
5. Scatter evidence that transposed OpenSubdiv-derived local force rows land on
   `Face::oneRingVertices[j]` in the reviewed order, or a documented and tested
   replacement order.
6. Serial/OpenMP tolerance evidence preserving the current thread-local force
   buffer shape and ascending thread-index reduction order unless review
   approves a different accumulation contract.
7. For the current supported 11-control class, comparison against the existing
   dependency-free subdivision-matrix transpose route where that route applies.
8. Unsupported dependency-absent, zero-depth 11-control, broader-valence,
   boundary, ghost, and periodic cases that fail loudly or fall back only
   through reviewed diagnostics.
9. Representative physical fixture decisions and scientific signoff before any
   claim of physically validated irregular forces.

Passing the toy transpose report is therefore a prerequisite signal, not a
production force-transpose proof.

## Safe Evidence Boundary

The current production route remains:

- regular 12-control force evaluation through the existing evaluator and force
  formulas;
- positive-depth `11 = 4+3+4` force evaluation through dependency-free
  subdivision matrices and child-force back-projection; and
- guarded unsupported behavior for zero-depth 11-control requests and broader
  irregular topologies.

Default builds remain OpenSubdiv-free. OpenSubdiv-present evidence remains
opt-in through a user-provided `OPENSUBDIV_ROOT` and the non-default probe
wrapper. No production code should use OpenSubdiv presence to change physics
behavior until a separate backend routing PR passes the missing evidence above.

## Inventory Check

Run the evidence-anchor inventory with:

```console
python3 scripts/inventory_opensubdiv_force_transpose_evidence.py --fail-on-missing
```

The script is intentionally source-text based. Missing anchors mean the docs,
tests, probe, or production route have drifted enough that this evidence map
needs human review before it is used as a gate for production OpenSubdiv
routing.
