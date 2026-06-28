# OpenSubdiv Production-Routing Readiness Map

Date: 2026-06-27.
Baseline: post-PR72 documentation and probe evidence.

This is a docs/scripts-only readiness map. It does not change production C++
behavior, C++ backend interfaces, default build policy, OpenSubdiv dependency
policy, vendoring, Makefile target behavior, formula semantics, scatter order,
OpenMP behavior, checkpoint/output behavior, propagation behavior, optimizer
behavior, or production OpenSubdiv routing.

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

PR #72 probe evidence is observational and non-production. It is useful for
review planning, but production routing still requires reviewer/user-gated code
changes in a separate PR.

## Current Boundary

| Route | Current production status | OpenSubdiv evidence status | Readiness result |
| --- | --- | --- | --- |
| Regular 12-control membrane force | Supported through `SlimedLoopLimitSurfaceEvaluator`, current quadrature, and current force formulas. | Regular row/integrand equivalence, toy transpose, and regular actual-force probe smoke are opt-in evidence. | Not route-ready until OpenSubdiv-derived rows are compared through production routing/scatter under an approved gate. |
| Positive-depth `11 = 4+3+4` membrane force | Supported narrowly through dependency-free subdivision matrices and child-force back-projection. | OpenSubdiv aggregate source/transpose reports are observational only. | Keep current route; do not replace with OpenSubdiv in the regular readiness lane. |
| Zero-depth 11-control and unsupported irregular topologies | Guarded unsupported cases. | No production approval. | Must continue to fail loudly or use only reviewed diagnostics. |
| Broader extraordinary valence | Not production supported. | Synthetic broader-valence coverage can inform planning only. | Future-only until representative fixtures and scientific approval are available. |

Default validation remains dependency-free. OpenSubdiv-present checks stay
opt-in through `OPENSUBDIV_ROOT` and `scripts/run_opensubdiv_probe.sh`.

## Regular 12-Control Readiness Criteria

The regular route is the first admissible OpenSubdiv production-routing target.
Before OpenSubdiv-derived regular samples or rows can be routed into production,
every criterion below must be green or explicitly review-waived.

| Criterion | Current evidence | Remaining before production routing |
| --- | --- | --- |
| OpenSubdiv-derived sample identity | `--regular-equivalence-report` can compare regular value rows, derivative rows, tangent cross product, unit normal, area integrand, and legacy volume integrand against frozen SLIMED rows. `docs/opensubdiv_regular_sample_plan.md` freezes the current regular `gaussQuadratureN=2` sample rows, half-weight factors, orientation, seven-row convention, source-id order, duplicate aggregation, and comparison boundary. | A routed backend path must prove OpenSubdiv-derived rows match that frozen sample plan, or carry an explicitly reviewed replacement plan. |
| Seven-row derivative mapping | `docs/opensubdiv_mapping_contract.md` records the `s=v,t=w` mapping and seven SLIMED rows: position, `d/dv`, `d/dw`, `d2/dv2`, `d2/dw2`, `d2/dvdw`, and `d2/dwdv`. | Production code must carry explicit derivative convention metadata and preserve or review-replace the duplicated mixed-row convention. |
| Source-id ordering | The backend-neutral seam exposes row weights keyed by original SLIMED source ids; current regular tests cover natural and permuted 12-control orders. | A routed backend must prove that OpenSubdiv-derived row weights address the same source ids as `Face::oneRingVertices[j]`, or document and test a reviewed replacement order. |
| Duplicate aggregation | The regular source-id seam can aggregate repeated source-id contributions instead of assuming backend stencil order. | OpenSubdiv-derived duplicate source-id contributions must be summed deterministically before formula/scatter comparison. |
| Quadrature/sample identity | Current regular formulas consume `Param::shapeFunctions` in existing quadrature order with `0.5 * param.gaussQuadratureCoeff(i, 0)`. | The OpenSubdiv production path must use the same sample locations and quadrature weights, or carry an explicitly reviewed formula/sample change. |
| Actual `fBend`/`fArea`/`fVolume` comparison | The opt-in `--regular-actual-force-report` emits `kind: opensubdiv_regular_rows_actual_formula_evidence` and finite nonzero local force rows in the temporary probe. In-tree tests compare actual regular formula rows through the backend-neutral seam. | A production-routed OpenSubdiv path must compare OpenSubdiv-derived local `fBend`, `fArea`, and `fVolume` rows against the current direct regular path before changing routing. |
| Energy, normal, area, and volume comparison | Current regular probe and in-tree tests cover row/integrand values plus local energy, mean curvature, normal, area, and legacy volume semantics on deterministic fixtures. | A routed backend must compare output-visible energies, normals, area, and volume through production call timing, not only a temporary probe. |
| Scatter through `Face::oneRingVertices` | `RegularForceRowsScatterInOneRingOrder` verifies that local regular force rows land on the reviewed one-ring order. | OpenSubdiv-derived rows must preserve that scatter order or ship with a reviewed replacement order and tests. |
| Serial/OpenMP tolerance envelope | Current docs characterize the thread-local buffer shape and ascending thread-index reduction order. Irregular serial/OpenMP tolerance work remains separate. | Establish regular OpenSubdiv serial/OpenMP tolerances for energies, forces, normals, area, and volume while preserving reduction shape or documenting an approved replacement. |
| Fallback diagnostics | Dependency-absent probes skip cleanly; unsupported production irregular routes are guarded. | Production routing must never silently change physics based on ambient OpenSubdiv availability. Dependency-absent, unsupported topology, boundary, ghost, periodic, and failed-equivalence cases need explicit reviewed diagnostics. |
| Default dependency isolation | Stage 0 remains docs/scripts/probe-only and `OPENSUBDIV_ROOT`-gated. | No default dependency, vendoring, submodule, generated artifact, package-manager assumption, or Makefile target behavior change can be bundled into the routing proof. |
| Reviewer/user gate | Existing evidence maps state that OpenSubdiv remains opt-in/probe-only. | The production route change must be an explicit reviewed PR; this readiness map is not approval to route. |

## Required Regular Evidence Package

A future regular production-routing PR should provide, at minimum:

- frozen regular fixtures and sample coordinates;
- OpenSubdiv row/integrand equivalence for the routed sample plan;
- source-id row-weight reports keyed by original SLIMED ids;
- duplicate aggregation checks for row weights;
- actual bending, area, and volume force-row equivalence for `fBend`,
  `fArea`, and `fVolume`;
- energy, normal, mean-curvature, area, and legacy-volume comparison through
  the production evaluator timing;
- scatter comparison through `Face::oneRingVertices`;
- serial/OpenMP tolerance report preserving thread-local force buffer shape
  and reduction order;
- dependency-absent and unsupported-route diagnostics; and
- explicit no-default-dependency and no-vendoring evidence.

The existing PR #72 regular actual-force probe can be cited as a prerequisite
signal, but it cannot be cited as production routing proof.

The exact regular 12-control sample plan is documented in
`docs/opensubdiv_regular_sample_plan.md`. That document is a readiness anchor,
not approval to route production faces through OpenSubdiv.

The regular backend-adapter checklist in
`docs/opensubdiv_regular_backend_adapter_readiness.md` ties the PR #68
weighted-sample seam, PR #69 mapping contract, PR #72 regular actual-force
evidence, this readiness map, and the PR #74 sample plan into a concrete
pre-routing adapter boundary. It is also evidence/readiness only, not
production routing approval.

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
