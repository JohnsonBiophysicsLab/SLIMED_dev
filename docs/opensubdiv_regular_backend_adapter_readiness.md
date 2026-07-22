# OpenSubdiv Regular Backend Adapter Readiness Checklist

Date: 2026-07-21.
Baseline: guarded regular production-route activation lane.

This checklist now records the first explicitly guarded regular production
routing seam. It does not change default production behavior, default build
policy, vendoring, submodules, generated dependency artifacts, force formulas,
force scatter ordering, OpenMP behavior, checkpoint/output behavior,
propagation behavior, optimizer behavior, or irregular/broader-valence
OpenSubdiv routing.

## Purpose

This checklist tracks the evidence and runtime boundaries for the guarded
regular OpenSubdiv-backed adapter. It answers a narrow question: what must
remain true while the explicit regular production route consumes
OpenSubdiv-derived rows?

The adapter boundary remains reviewable in SLIMED terms:

- the public sample result is the existing seven-row
  `LimitSurfaceWeightedSample`;
- row weights are keyed by original SLIMED source ids;
- regular sample coordinates and quadrature order match the frozen SLIMED
  regular plan;
- force formulas and scatter order remain owned by the existing production
  force path; and
- OpenSubdiv presence cannot silently change default behavior.

The production seam is opt-in twice: the binary must be built with
`USE_OPENSUBDIV_REGULAR=1 OPENSUBDIV_ROOT=...`, and runtime routing must be
requested with `SLIMED_USE_OPENSUBDIV_REGULAR=1`. Supported non-boundary,
non-ghost 12-control regular faces consume double-precision OpenSubdiv rows
only when those rows match the frozen SLIMED regular rows under the existing
`5e-6` policy. Boundary, ghost, irregular, and non-equivalent faces emit the
guarded diagnostic where applicable and retain their existing direct or
subdivision path.

## Evidence Lineage

| Lane | Evidence now available | Adapter-readiness meaning |
| --- | --- | --- |
| PR #68 weighted-sample seam | `LimitSurfaceEvaluator::evaluate_weighted(...)` returns seven evaluated rows plus row weights keyed by caller-provided source ids. | A future adapter can be reviewed at a backend-neutral source-id boundary without exposing OpenSubdiv types to production force code. |
| PR #69 mapping contract | `docs/opensubdiv_mapping_contract.md` records the `s=v,t=w` derivative mapping, source-id contract, and back-projection requirements. | The adapter must state its coordinate convention, row order, source ids, and transpose boundary before routing. |
| PR #72 regular actual-force evidence | `docs/opensubdiv_force_transpose_evidence.md` separates row/integrand evidence, toy transpose evidence, and regular actual-force probe smoke. | The probe is prerequisite evidence, not production C++ routing or an adapter integration. |
| PR #73 routing readiness map | `docs/opensubdiv_routing_readiness_map.md` records regular-first readiness gates and keeps irregular/broader-valence routing future-only. | The regular adapter satisfied its production comparison and reviewer/user gates; broader-valence routing remains future-only. |
| PR #74 regular sample plan | `docs/opensubdiv_regular_sample_plan.md` freezes quadrature rows, `s=v,t=w`, seven rows, source order, duplicate aggregation, and comparison boundaries. | The adapter must match the frozen regular sample plan or carry an explicitly reviewed replacement. |
| PR #75 regular backend readiness | `docs/opensubdiv_regular_backend_adapter_readiness.md` and its inventory keep adapter evidence review-gated. | The historical proof boundary remains recorded while the guarded regular route is active behind both explicit gates. |
| PR #76 through PR #82 proof lane | `docs/opensubdiv_regular_adapter_proof.md`, `scripts/probe_opensubdiv_feasibility.py --regular-adapter-proof-report`, and `scripts/run_opensubdiv_regular_cpp_adapter_proof.sh` emit test-only regular adapter proof evidence. | OpenSubdiv rows can be remapped into the weighted-sample contract and compared against production-call shape, current regular production helper semantics, visible regular area/legacy-volume observables, and proof-local serial/OpenMP-style accumulation shape. |
| Guarded production regular seam | `src/mesh/OpenSubdiv_regular_evaluator.cpp`, `diagnose_opensubdiv_regular_row_semantics`, `USE_OPENSUBDIV_REGULAR=1`, `SLIMED_USE_OPENSUBDIV_REGULAR=1`, and `OpenSubdivRegularProductionRoutingGuard` tests compile the backend seam and compare OpenSubdiv regular rows against SLIMED rows. | Runtime opt-in installs reviewed rows for equivalent supported regular faces; unsupported or non-equivalent faces retain the reviewed direct/subdivision route. |

## Adapter Boundary

The regular OpenSubdiv-backed adapter prepares OpenSubdiv topology and stencils
internally. Its production comparison surface remains the SLIMED
weighted-sample contract:

```text
sample coordinate: SLIMED v,w,u row from the frozen regular quadrature plan
evaluated rows: position, d/dv, d/dw, d2/dv2, d2/dw2, d2/dvdw, d2/dwdv
row weights: row_weight(SLIMED derivative row, original SLIMED vertex id)
source order: Face::oneRingVertices[j] for the regular 12-control support
```

The adapter must not ask production force code to understand OpenSubdiv ptex
ids, patch-control ids, stencil offsets, or dependency-present fallback rules.
Those details remain behind the adapter. Any extension beyond the guarded
regular route requires a separate reviewed routing PR.

## Readiness Checklist

| Gate | Must preserve for production routing | Current anchor | Current status |
| --- | --- | --- | --- |
| Regular sample coordinates and quadrature order | The adapter uses the frozen three regular sample rows, `1/3` quadrature weights, and `0.5 * weight` formula factors. | `docs/opensubdiv_regular_sample_plan.md` and `scripts/inventory_opensubdiv_regular_sample_plan.py` | Preserved by the guarded equivalent-row route. |
| Coordinate and derivative convention | The adapter records `s=v,t=w`, tangent orientation `firstDerivativeV x firstDerivativeW`, and all seven derivative rows including duplicated mixed row convention. | `docs/opensubdiv_mapping_contract.md` and the regular sample-plan inventory | Preserved by the guarded equivalent-row route. |
| Original source-id order | Row weights are keyed by original SLIMED ids and match `Face::oneRingVertices[j]` for the regular 12-control support. | Weighted-sample seam, mapping contract, force/scatter contract, and `diagnose_opensubdiv_regular_row_semantics` | Preserved by the active guarded regular route and its row diagnostics. |
| Deterministic duplicate aggregation | Duplicate original source ids are summed deterministically before formula comparison or scatter comparison. | `LimitSurfaceWeightedSample::row_weight(...)` and regular source-id tests | Preserved by the active guarded regular route. |
| Actual force rows | OpenSubdiv-derived rows compare through actual `fBend`, `fArea`, and `fVolume` formula rows, not only row/integrand or toy-transpose probes. | `docs/opensubdiv_force_transpose_evidence.md`, `--regular-actual-force-report`, and `--regular-adapter-proof-report` | Test-only adapter proof and active guarded production evidence pass under the current policy. |
| Regular production helper dry run | OpenSubdiv-derived regular rows compare against the current `Mesh::element_energy_force_regular` call semantics. | `docs/opensubdiv_regular_adapter_proof.md` and `scripts/run_opensubdiv_regular_cpp_adapter_proof.sh` | Historical proof-local evidence is backed by active guarded direct/routed characterization. |
| Output-visible state | Energies, normals, mean curvature, area, and legacy volume compare at production call timing. | Routing readiness map and force/scatter contract | Guarded route output-visible parity passes; unsupported faces retain their existing path. |
| Scatter and reduction | Local OpenSubdiv-derived regular rows scatter through `Face::oneRingVertices` while preserving the current serial/OpenMP thread-local buffer shape and reduction order. | `docs/force_formula_scatter_equivalence.md`, routing readiness map, and executable parity harness | Active guarded serial/OpenMP executable parity passes under the current policy. |
| Dependency-present behavior | OpenSubdiv-present evidence is opt-in through `OPENSUBDIV_ROOT`; default builds and tests remain OpenSubdiv-free. | Backend interface policy, `scripts/run_opensubdiv_probe.sh`, and `USE_OPENSUBDIV_REGULAR=1` builds | Required boundary remains unchanged. |
| Dependency-absent behavior | Missing OpenSubdiv skips probes cleanly and never changes production physics or routing. | `scripts/run_opensubdiv_probe.sh --json` absent-wrapper behavior and default-route guard tests | Required boundary remains unchanged. |
| Production review gate | Only equivalent non-boundary, non-ghost 12-control regular faces are allowed on the guarded route. | Routing readiness map and this checklist | Guarded regular routing is active; irregular, broader-valence, default, optimizer, propagation, checkpoint/output, and OpenMP policy changes remain blocked. |

## Current Activation Boundary

The current safe production boundary is the doubly gated equivalent-row route.
Any follow-up must stop before adding:

- default build or dependency behavior;
- backend interface ownership or signature changes;
- sample, ptex, source-id, scatter, force-formula, or scientific decisions;
- OpenMP reduction changes; or
- checkpoint, output, propagation, optimizer, boundary, ghost, or periodic
  behavior changes.

The opt-in route currently rebuilds and refines its OpenSubdiv topology when
geometry or force rows are requested. Correctness and parity gates pass, but
the route is not performance-tuned; caching or lifetime changes require a
separate ownership and invalidation review. Reproducible direct-versus-routed
measurements and the cache design questions are recorded in
`docs/opensubdiv_regular_route_performance.md`.

If any of those decisions are needed, the correct result is a blocker report
and a new prompt for an explicitly reviewed implementation lane.

The historical proof-lane implementation records the evidence lineage through
`scripts/probe_opensubdiv_feasibility.py --regular-adapter-proof-report` and
`scripts/run_opensubdiv_regular_cpp_adapter_proof.sh`. It is
`OPENSUBDIV_ROOT`-gated, compiles only temporary proof binaries, emits proof-only
`kind` fields, remaps OpenSubdiv rows by original SLIMED source id into the
seven-row weighted-sample contract, checks deterministic duplicate aggregation,
emits actual `fBend`/`fArea`/`fVolume` rows, verifies
`Face::oneRingVertices` scatter identity, and now compares the OpenSubdiv-fed
rows against the current regular production helper in a dry-run local `Param`.
It also reports proof-local visible regular area/legacy-volume observables and
serial/OpenMP-style accumulation parity for the current `nVertices*9`
force-buffer shape.
The guarded production route consumes the same reviewed row contract only for
supported equivalent regular faces; the proof reports remain non-production
diagnostics.

## Preserved Production Evidence Package

The guarded regular route must continue to provide all of the following:

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
- an explicit reviewer/user gate for any route expansion or policy change.

## Inventory Check

Run the adapter-readiness inventory with:

```console
python3 scripts/inventory_opensubdiv_regular_adapter_readiness.py --check
```

The inventory is source-text based and dependency-free. A missing anchor means
the regular adapter-readiness checklist or one of its upstream evidence links
has drifted enough to need human review before a future OpenSubdiv routing PR
uses it as a gate.
