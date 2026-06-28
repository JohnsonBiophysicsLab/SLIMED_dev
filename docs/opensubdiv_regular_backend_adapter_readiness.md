# OpenSubdiv Regular Backend Adapter Readiness Checklist

Date: 2026-06-28.
Baseline: PR #74 merge commit
`92375abed3b81f1062af2ff51d867fde2e692ed4`.

This is a docs/scripts/tests-only adapter-readiness lane. It does not change
production C++ behavior, C++ backend interfaces, default build policy,
OpenSubdiv dependency policy, vendoring, Makefile target behavior, force
formulas, force scatter ordering, OpenMP behavior, checkpoint/output behavior,
propagation behavior, optimizer behavior, or production OpenSubdiv routing.

## Purpose

This checklist turns the PR #68 through PR #74 evidence into a concrete
review boundary for a future regular OpenSubdiv-backed adapter. It answers a
narrow question: what must a regular adapter prove before any production route
can consume OpenSubdiv-derived samples or rows?

The answer is intentionally still non-production. The future adapter boundary
must remain reviewable in SLIMED terms:

- the public sample result is the existing seven-row
  `LimitSurfaceWeightedSample`;
- row weights are keyed by original SLIMED source ids;
- regular sample coordinates and quadrature order match the frozen SLIMED
  regular plan;
- force formulas and scatter order remain owned by the existing production
  force path; and
- OpenSubdiv presence cannot silently change default behavior.

## Evidence Lineage

| Lane | Evidence now available | Adapter-readiness meaning |
| --- | --- | --- |
| PR #68 weighted-sample seam | `LimitSurfaceEvaluator::evaluate_weighted(...)` returns seven evaluated rows plus row weights keyed by caller-provided source ids. | A future adapter can be reviewed at a backend-neutral source-id boundary without exposing OpenSubdiv types to production force code. |
| PR #69 mapping contract | `docs/opensubdiv_mapping_contract.md` records the `s=v,t=w` derivative mapping, source-id contract, and back-projection requirements. | The adapter must state its coordinate convention, row order, source ids, and transpose boundary before routing. |
| PR #72 regular actual-force evidence | `docs/opensubdiv_force_transpose_evidence.md` separates row/integrand evidence, toy transpose evidence, and regular actual-force probe smoke. | The probe is prerequisite evidence, not production C++ routing or an adapter integration. |
| PR #73 routing readiness map | `docs/opensubdiv_routing_readiness_map.md` records regular-first readiness gates and keeps irregular/broader-valence routing future-only. | The regular adapter is still not route-ready until production comparison and reviewer/user gates are satisfied. |
| PR #74 regular sample plan | `docs/opensubdiv_regular_sample_plan.md` freezes quadrature rows, `s=v,t=w`, seven rows, source order, duplicate aggregation, and comparison boundaries. | The adapter must match the frozen regular sample plan or carry an explicitly reviewed replacement. |

## Adapter Boundary

A regular OpenSubdiv-backed adapter may eventually prepare OpenSubdiv topology,
patch tables, stencils, or other backend-owned objects internally. Before
production routing can use it, its public comparison surface must still be the
SLIMED weighted-sample contract:

```text
sample coordinate: SLIMED v,w,u row from the frozen regular quadrature plan
evaluated rows: position, d/dv, d/dw, d2/dv2, d2/dw2, d2/dvdw, d2/dwdv
row weights: row_weight(SLIMED derivative row, original SLIMED vertex id)
source order: Face::oneRingVertices[j] for the regular 12-control support
```

The adapter must not ask production force code to understand OpenSubdiv ptex
ids, patch-control ids, stencil offsets, or dependency-present fallback rules.
Those details remain behind the adapter until a separate reviewed routing PR
changes production behavior.

## Readiness Checklist

| Gate | Must prove before production routing | Current anchor | Current status |
| --- | --- | --- | --- |
| Regular sample coordinates and quadrature order | The adapter uses the frozen three regular sample rows, `1/3` quadrature weights, and `0.5 * weight` formula factors. | `docs/opensubdiv_regular_sample_plan.md` and `scripts/inventory_opensubdiv_regular_sample_plan.py` | Characterized, not routed. |
| Coordinate and derivative convention | The adapter records `s=v,t=w`, tangent orientation `firstDerivativeV x firstDerivativeW`, and all seven derivative rows including duplicated mixed row convention. | `docs/opensubdiv_mapping_contract.md` and the regular sample-plan inventory | Characterized, not routed. |
| Original source-id order | Row weights are keyed by original SLIMED ids and match `Face::oneRingVertices[j]` for the regular 12-control support. | Weighted-sample seam, mapping contract, and force/scatter contract | Characterized through the in-tree seam, not OpenSubdiv production routing. |
| Deterministic duplicate aggregation | Duplicate original source ids are summed deterministically before formula comparison or scatter comparison. | `LimitSurfaceWeightedSample::row_weight(...)` and regular source-id tests | Characterized through the in-tree seam, not OpenSubdiv production routing. |
| Actual force rows | OpenSubdiv-derived rows compare through actual `fBend`, `fArea`, and `fVolume` formula rows, not only row/integrand or toy-transpose probes. | `docs/opensubdiv_force_transpose_evidence.md` and `--regular-actual-force-report` | Probe smoke exists; production adapter proof remains missing. |
| Output-visible state | Energies, normals, mean curvature, area, and legacy volume compare at production call timing. | Routing readiness map and force/scatter contract | Required before routing; not satisfied by this checklist. |
| Scatter and reduction | Local OpenSubdiv-derived regular rows scatter through `Face::oneRingVertices` while preserving the current serial/OpenMP thread-local buffer shape and reduction order, or a reviewed replacement. | `docs/force_formula_scatter_equivalence.md` and routing readiness map | Required before routing; not satisfied by this checklist. |
| Dependency-present behavior | OpenSubdiv-present evidence is opt-in through `OPENSUBDIV_ROOT`; default builds, tests, and Makefile targets remain OpenSubdiv-free. | Backend interface policy and `scripts/run_opensubdiv_probe.sh` | Required boundary remains unchanged. |
| Dependency-absent behavior | Missing OpenSubdiv skips probes cleanly and never changes production physics or routing. | `scripts/run_opensubdiv_probe.sh --json` absent-wrapper behavior | Required boundary remains unchanged. |
| Non-production review gate | No production route uses OpenSubdiv-derived rows until a separate reviewed PR proves the checklist against production routing and scatter. | Routing readiness map and this checklist | Explicit blocker for adapter routing. |

## Prototype Boundary

The next safe implementation step, if one is requested later, is an inert
adapter prototype or report that emits the same checklist evidence without
changing any production call site. That prototype must stop before adding:

- production C++ routing;
- default build or dependency behavior;
- OpenSubdiv C++ integration hooks in production targets;
- backend interface ownership or signature changes;
- sample, ptex, source-id, scatter, force-formula, or scientific decisions;
- OpenMP reduction changes; or
- checkpoint, output, propagation, optimizer, boundary, ghost, or periodic
  behavior changes.

If any of those decisions are needed, the correct result is a blocker report
and a new prompt for an explicitly reviewed implementation lane.

## Required Future Adapter Evidence Package

A future regular adapter-routing PR should provide all of the following before
claiming production readiness:

- machine-readable regular sample-plan evidence for the routed adapter rows;
- row weights keyed by original SLIMED ids for every selected sample;
- comparison of all seven derivative rows under `s=v,t=w`, including both
  mixed rows;
- deterministic duplicate source-id aggregation checks;
- actual `fBend`, `fArea`, and `fVolume` comparison against the direct regular
  route;
- output-visible energy, mean-curvature, normal, area, and legacy-volume
  comparison at production call timing;
- scatter comparison through `Face::oneRingVertices`;
- serial/OpenMP tolerance evidence preserving the current accumulation shape;
- dependency-absent and dependency-present diagnostics; and
- an explicit reviewer/user gate for production routing.

## Inventory Check

Run the adapter-readiness inventory with:

```console
python3 scripts/inventory_opensubdiv_regular_adapter_readiness.py --check
```

The inventory is source-text based and dependency-free. A missing anchor means
the regular adapter-readiness checklist or one of its upstream evidence links
has drifted enough to need human review before a future OpenSubdiv routing PR
uses it as a gate.
