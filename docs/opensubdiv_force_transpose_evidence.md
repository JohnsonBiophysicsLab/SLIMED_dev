# OpenSubdiv Force Transpose Evidence Map

Date: 2026-06-26.
Baseline: `origin/main` at `cd9d9e3e365dfdbc225881f469b7837f9c49322b`
after PR #70.

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

The opt-in probe now covers regular OpenSubdiv row/integrand equivalence,
toy-linear transpose, and regular-sample actual formula smoke evidence. SLIMED
also has production-side formula/scatter characterization and a dependency-free
positive-depth `11 = 4+3+4` subdivision-matrix route, but none of this enables
OpenSubdiv production routing.

## Current Evidence Matrix

| Evidence item | Current anchor | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Regular OpenSubdiv row/integrand equivalence | `scripts/probe_opensubdiv_feasibility.py --regular-equivalence-report` | Observed regular OpenSubdiv value, derivative, tangent, normal, area-integrand, and legacy-volume-integrand values can match frozen SLIMED regular values under the documented `s=v,t=w` mapping. | It does not pass sample gradients through bending, area, or volume force formulas. |
| Regular OpenSubdiv toy transpose | `scripts/probe_opensubdiv_feasibility.py --force-transpose-report` emits `kind: toy_linear_functional_only`. | A deterministic toy gradient satisfies `g dot (W p) == (W^T g) dot p` for OpenSubdiv regular row weights and a SLIMED-compatible seven-row shape. | It does not compute `fBend`, `fArea`, `fVol`, per-control formula terms, quadrature accumulation, or production scatter. |
| Regular OpenSubdiv actual formula smoke | `scripts/probe_opensubdiv_feasibility.py --regular-actual-force-report` emits `kind: opensubdiv_regular_rows_actual_formula_evidence`. | OpenSubdiv-derived regular value/derivative row weights for the SLIMED second-order triangular quadrature can drive a local copy of the current bending, area, and volume force sample algebra, producing finite nonzero `fBend`, `fArea`, and `fVolume` rows keyed by original source ids. | It is a temporary probe smoke, not production C++ routing, not an API/backend integration, not an OpenMP scatter comparison, and not irregular force evidence. |
| Production regular formula/scatter characterization | `SurfaceLimitSurfaceEvaluatorContract.RegularActualForceBackProjectionMatchesDirectFormulaRows`, `RegularForceRowsScatterInOneRingOrder`, `docs/force_formula_scatter_equivalence.md`, and `scripts/inventory_force_formula_scatter_contract.py`. | Current bending, area, and volume formulas consume seven SLIMED rows, quadrature-accumulate local force matrices, match direct local shape rows against source-id row-weight lookup for natural and permuted 12-control orders, and scatter through `Face::oneRingVertices` into the thread-local force buffer. | It uses the in-tree SLIMED evaluator/source-id seam; it is not evidence that OpenSubdiv row weights have been routed through those actual formulas or that production OpenSubdiv routing is enabled. |
| Positive-depth 11-control production route | `SurfaceSubdivisionCharacterization.SyntheticIrregularPatchEnergyForceBackProjectsChildRegularForces` and `scripts/inventory_irregular_routing_evidence.py`. | The dependency-free `11 = 4+3+4` route transposes child regular bending, area, and volume force rows through existing subdivision matrices back to the 11 original rows. | It is not OpenSubdiv-backed and does not approve broader irregular topologies, zero-depth 11-control requests, or dependency-present behavior. |
| Irregular OpenSubdiv observational proof map | `scripts/probe_opensubdiv_feasibility.py --irregular-transpose-proof-map-report` emits `kind: observational_all_ptex_grid_toy_transpose`. | Aggregate all-ptex/sample-grid source visibility and toy transpose shape can be inspected for the 11-control fixture variants. | It does not select a ptex/sample plan for one SLIMED face and does not run actual force formulas or production scatter. |

## Remaining OpenSubdiv Force Transpose Evidence

Before production OpenSubdiv backend routing can claim actual SLIMED force
transpose correctness, a later lane must provide all of the following evidence
or record explicit reviewer-approved waivers:

1. A backend sample plan for one SLIMED face, including ptex faces, child
   patches, sample coordinates, quadrature weights, orientation, and row order.
   For the regular 12-control route, the current frozen sample plan is recorded
   in `docs/opensubdiv_regular_sample_plan.md`.
2. Row weights keyed by original SLIMED vertex ids for every selected sample,
   not transient OpenSubdiv control ids.
3. A reviewed derivative convention from OpenSubdiv rows to SLIMED's seven rows,
   including the current duplicated mixed-row convention.
4. OpenSubdiv-backed regular actual-force transpose through the production
   bending, area, and volume formulas. The opt-in regular actual-force probe is
   smoke evidence that OpenSubdiv regular rows can feed the formula algebra,
   and the in-tree regular evaluator/source-id seam is characterized for
   natural and permuted 12-control orders, but an OpenSubdiv backend must still
   prove any production path without changing routing in this evidence lane.
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

Passing the toy transpose and regular actual-force reports is therefore a
prerequisite signal, not a production force-transpose proof.

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

The regular actual-force smoke command is:

```console
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
  scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv \
  --regular-equivalence-report \
  --force-transpose-report \
  --regular-actual-force-report
```

The `--regular-actual-force-report` path compiles only the temporary probe
program. It does not link OpenSubdiv into SLIMED, alter the default build, or
route any production face through OpenSubdiv.

## Inventory Check

Run the evidence-anchor inventory with:

```console
python3 scripts/inventory_opensubdiv_force_transpose_evidence.py --fail-on-missing
```

The script is intentionally source-text based. Missing anchors mean the docs,
tests, probe, or production route have drifted enough that this evidence map
needs human review before it is used as a gate for production OpenSubdiv
routing.
