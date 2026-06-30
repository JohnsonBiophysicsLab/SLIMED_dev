# OpenSubdiv Production-Routing Readiness Map

Date: 2026-06-30.
Baseline: post-PR82 regular OpenSubdiv proof evidence.

This map now records the first narrowly guarded production regular-routing
seam. Default builds remain OpenSubdiv-free. The OpenSubdiv-backed route is
compiled only when the binary is built with
`USE_OPENSUBDIV_REGULAR=1 OPENSUBDIV_ROOT=...`, and runtime routing must still
be requested with `SLIMED_USE_OPENSUBDIV_REGULAR=1`; however the routed rows
are intentionally disabled because the direct-vs-routed production
force/geometry characterization found semantics drift. Runtime opt-in therefore
falls back to the reviewed direct regular path until that mismatch is resolved.
This does not change default production behavior, public OpenSubdiv types,
vendoring, submodules, generated dependency artifacts, formula semantics,
scatter order, OpenMP buffer/reduction shape, checkpoint/output behavior,
propagation behavior, optimizer behavior, or irregular/broader-valence routing.

## Purpose

This map answers the routing question that the current evidence intentionally
does not answer: what remains before OpenSubdiv-derived samples and force rows
can enter production routing?

The answer is deliberately staged:

1. Regular 12-control routing first, because it has the in-tree evaluator,
   production formula/scatter characterization, and OpenSubdiv probe evidence.
2. Existing positive-depth 11-control support stays on the dependency-free
   subdivision-matrix route.
3. OpenSubdiv-backed irregular or broader-valence production support remains
   future-only until face-level fixtures, sample plans, actual formula
   back-projection, and scientific review exist.

PR #72 probe evidence and PR #76 through PR #82 proof evidence are
observational, opt-in, and non-production. They are useful for review planning,
but production routing still requires reviewer/user-gated code changes in a
separate PR.

## Current Boundary

| Route | Current production status | OpenSubdiv evidence status | Readiness result |
| --- | --- | --- | --- |
| Regular 12-control membrane force | Supported through `SlimedLoopLimitSurfaceEvaluator`, current quadrature, and current force formulas. A compile-time/runtime OpenSubdiv seam exists, but the routed rows are disabled and opt-in falls back to the direct regular path after direct-vs-routed characterization exposed semantics drift. | Regular row/integrand equivalence, compiled-seam row diagnostics, toy transpose, actual-force probe smoke, C++ adapter proof, production-call shadow, production-helper dry run, visible-observable dry run, serial/OpenMP-style accumulation parity, and guarded fallback tests are opt-in evidence. | No OpenSubdiv-derived rows are production-routed yet; default and unsupported routes remain unchanged. |
| Positive-depth `11 = 4+3+4` membrane force | Supported narrowly through dependency-free subdivision matrices and child-force back-projection. | OpenSubdiv aggregate source/transpose reports are observational only. | Keep current route; do not replace with OpenSubdiv in the regular readiness lane. |
| Zero-depth 11-control and unsupported irregular topologies | Guarded unsupported cases. | No production approval. | Must continue to fail loudly or use only reviewed diagnostics. |
| Broader extraordinary valence | Not production supported. | Synthetic broader-valence coverage can inform planning only. | Future-only until representative fixtures and scientific approval are available. |

Default validation remains dependency-free. OpenSubdiv-present checks stay
opt-in through `OPENSUBDIV_ROOT`, `scripts/run_opensubdiv_probe.sh`, and
`USE_OPENSUBDIV_REGULAR=1` builds with `SLIMED_USE_OPENSUBDIV_REGULAR=1`.

## Guarded Production Regular Seam

The first production seam is deliberately small:

- `src/mesh/OpenSubdiv_regular_evaluator.cpp` is compiled in default builds
  as an OpenSubdiv-free stub.
- The real OpenSubdiv code is compiled only with
  `USE_OPENSUBDIV_REGULAR=1`, which requires `OPENSUBDIV_ROOT`.
- Runtime routing is additionally gated by
  `SLIMED_USE_OPENSUBDIV_REGULAR=1`; setting this variable in a default build
  throws a loud runtime error.
- In an OpenSubdiv-enabled build, runtime opt-in currently prints a diagnostic
  and returns no routed rows because the OpenSubdiv-derived production rows do
  not yet preserve reviewed direct force/geometry semantics.
- The direct regular path remains active for all regular production
  calculations while the OpenSubdiv row mismatch is unresolved.
- The existing `calculate_element_area_volume` and
  `element_energy_force_regular` helpers still own area, legacy volume,
  `fBend`, `fArea`, `fVolume`, normal, and mean-curvature semantics.
- The existing force scatter and serial/OpenMP thread-local force-buffer
  reduction shape are unchanged.
- Boundary, ghost, and other non-routable regular faces avoid empty overrides
  and continue through the direct path.

## Regular 12-Control Readiness Criteria

The regular route is the first admissible OpenSubdiv production-routing target.
Before OpenSubdiv-derived regular samples or rows can be routed into production,
every criterion below must be green or explicitly review-waived.

| Criterion | Current evidence | Remaining before production routing |
| --- | --- | --- |
| OpenSubdiv-derived sample identity | `--regular-equivalence-report`, `docs/opensubdiv_regular_sample_plan.md`, the C++ proof harness, and `diagnose_opensubdiv_regular_row_semantics` cover the frozen regular `gaussQuadratureN=2` sample rows, half-weight factors, orientation, seven-row convention, source-id order, duplicate aggregation, and comparison boundary. | The first routed production PR must show that the installed route consumes this same frozen sample plan, or carry an explicitly reviewed replacement plan. |
| Seven-row derivative mapping | `docs/opensubdiv_mapping_contract.md` records the `s=v,t=w` mapping and seven SLIMED rows: position, `d/dv`, `d/dw`, `d2/dv2`, `d2/dw2`, `d2/dvdw`, and `d2/dwdv`. | Production code must carry explicit derivative convention metadata and preserve or review-replace the duplicated mixed-row convention. |
| Source-id ordering | The backend-neutral seam exposes row weights keyed by original SLIMED source ids; current regular tests and the proof harness cover natural/permuted 12-control orders and OpenSubdiv-derived source ids. | The first routed production PR must prove the installed route addresses the same ids as `Face::oneRingVertices[j]`, or document and test a reviewed replacement order. |
| Duplicate aggregation | The regular source-id seam and proof harness aggregate repeated source-id contributions deterministically instead of assuming backend stencil order. | The first routed production PR must keep this aggregation at the production boundary. |
| Quadrature/sample identity | Current regular formulas consume `Param::shapeFunctions` in existing quadrature order with `0.5 * param.gaussQuadratureCoeff(i, 0)`, and the proof harness reports the same frozen plan. | The OpenSubdiv production path must use the same sample locations and quadrature weights, or carry an explicitly reviewed formula/sample change. |
| Actual `fBend`/`fArea`/`fVolume` comparison | The opt-in `--regular-actual-force-report` and the C++ proof harness emit finite nonzero local force rows, production-call shadow evidence, and production-helper dry-run parity against `Mesh::element_energy_force_regular` through a local `Param`. The in-tree row diagnostic now compares compiled-seam OpenSubdiv rows against SLIMED rows before installation. In-tree direct-vs-routed characterization exposed unacceptable drift when those rows were installed at the production call site. | Keep OpenSubdiv-derived rows disabled until local `fBend`, `fArea`, and `fVolume` rows compare against the current direct regular path from the real routed call site without loosening tests. |
| Energy, normal, area, and volume comparison | Current regular probe, in-tree tests, and proof-local visible-observable dry run cover row/integrand values plus local energy, mean curvature, normal, area, and legacy volume semantics on deterministic fixtures. Production opt-in fallback now preserves the direct path. | A routed backend must compare output-visible energies, normals, area, and volume through real production call timing, not only a temporary proof binary, before installing routed rows. |
| Scatter through `Face::oneRingVertices` | `RegularForceRowsScatterInOneRingOrder` and the C++ proof harness verify that local regular force rows land on the reviewed one-ring order. | The first routed production PR must preserve that scatter order or ship with a reviewed replacement order and tests. |
| Serial/OpenMP tolerance envelope | Current docs characterize the thread-local buffer shape and ascending thread-index reduction order, and PR #82 added proof-local serial/OpenMP-style accumulation parity for the current `nVertices*9` force-buffer shape. Irregular serial/OpenMP tolerance work remains separate. | Establish real routed regular OpenSubdiv serial/OpenMP comparisons for energies, forces, normals, area, and volume while preserving reduction shape or documenting an approved replacement. |
| Fallback diagnostics | Dependency-absent probes skip cleanly; unsupported production irregular routes are guarded. | Production routing must never silently change physics based on ambient OpenSubdiv availability. Dependency-absent, unsupported topology, boundary, ghost, periodic, and failed-equivalence cases need explicit reviewed diagnostics. |
| Default dependency isolation | Stage 0 remains docs/scripts/probe-only and `OPENSUBDIV_ROOT`-gated. | No default dependency, vendoring, submodule, generated artifact, package-manager assumption, or Makefile target behavior change can be bundled into the routing proof. |
| Reviewer/user gate | Existing evidence maps state that OpenSubdiv remains opt-in/probe-only. | The production route change must be an explicit reviewed PR; this readiness map is not approval to route. |

## Required Regular Evidence Package

A future regular production-routing PR should provide, at minimum:

- a tiny production route selection boundary that is disabled unless explicitly
  built or invoked by the reviewed PR;
- confirmation that the routed route consumes the frozen regular fixtures and
  sample coordinates already proven by the proof lane;
- OpenSubdiv row/integrand equivalence for the routed sample plan;
- source-id row-weight reports keyed by original SLIMED ids from the routed
  production call site;
- duplicate aggregation checks for row weights at that call site;
- actual bending, area, and volume force-row equivalence for `fBend`,
  `fArea`, and `fVolume` from the routed production call site;
- energy, normal, mean-curvature, area, and legacy-volume comparison through
  the production evaluator timing;
- scatter comparison through `Face::oneRingVertices`;
- serial/OpenMP tolerance report preserving thread-local force buffer shape
  and reduction order from the routed production path;
- dependency-absent and unsupported-route diagnostics; and
- explicit no-default-dependency and no-vendoring evidence.

The PR #72 through PR #82 evidence package can be cited as prerequisite
evidence, but it cannot be cited as production routing proof until a real
routed production path is installed and compared.

The exact regular 12-control sample plan is documented in
`docs/opensubdiv_regular_sample_plan.md`. That document is a readiness anchor,
not approval to route production faces through OpenSubdiv.

The regular backend-adapter checklist in
`docs/opensubdiv_regular_backend_adapter_readiness.md` ties the PR #68
weighted-sample seam, PR #69 mapping contract, PR #72 regular actual-force
evidence, PR #74 sample plan, PR #76 through PR #82 proof evidence, and this
readiness map into a concrete pre-routing adapter boundary. It is also
evidence/readiness only, not production routing approval.

## Irregular And Broader-Valence Future Boundary

Irregular OpenSubdiv routing starts after regular production readiness, not
beside it. For the current supported 11-control class, any OpenSubdiv
replacement must compare against the dependency-free subdivision-matrix route
where that route applies. For broader valence, no production claim is available
until representative fixtures and scientific approval exist.

Future irregular or broader-valence production work must establish:

- a representative physical fixture, or an explicit scientific waiver for a
  narrower synthetic claim;
- exact ptex faces, child patches, sample coordinates, quadrature weights,
  orientation, and source-id ordering for one SLIMED face;
- actual formula/back-projection evidence for bending, area, and volume;
- comparison against the current subdivision-matrix `11 = 4+3+4` route where
  applicable;
- serial/OpenMP tolerance evidence for forces, energies, normals, area, and
  volume;
- boundary, ghost, periodic, zero-depth, unsupported-topology, and
  dependency-absent diagnostics; and
- reviewer and scientific signoff before describing irregular forces as
  physically validated.

Aggregate all-ptex source visibility and toy transpose reports are planning
evidence only. They are not a face-level production scatter contract.

## Inventory Check

Run the readiness-anchor inventory with:

```console
python3 scripts/inventory_opensubdiv_routing_readiness.py --check
```

Run the regular sample-plan inventory with:

```console
python3 scripts/inventory_opensubdiv_regular_sample_plan.py --check
```

Run the regular backend-adapter readiness inventory with:

```console
python3 scripts/inventory_opensubdiv_regular_adapter_readiness.py --check
```

The inventory is source-text based. A missing anchor means the readiness map or
one of its evidence links has drifted enough to need human review before a
future OpenSubdiv routing PR uses it as a gate.
