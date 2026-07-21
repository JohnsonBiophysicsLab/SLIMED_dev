# OpenSubdiv Production-Routing Readiness Map

Date: 2026-07-21.
Baseline: PR #104 serial/OpenMP executable parity proof for the guarded
double-row evaluator candidate.

This map now records the first narrowly guarded production regular-routing
seam. Default builds remain OpenSubdiv-free. The OpenSubdiv-backed route is
compiled only when the binary is built with
`USE_OPENSUBDIV_REGULAR=1 OPENSUBDIV_ROOT=...`, and runtime routing must also
be requested with `SLIMED_USE_OPENSUBDIV_REGULAR=1`. Supported non-boundary,
non-ghost 12-control regular faces whose generated rows match the frozen
regular rows then consume the reviewed double-precision OpenSubdiv rows. The
direct path remains active when runtime opt-in is absent and for boundary,
ghost, irregular, or non-equivalent faces. The activated route passes the direct/routed
force and geometry characterization plus the complete serial/OpenMP
executable-visible comparison under the unchanged tolerance.
In short, the guarded regular route is active only behind both explicit gates,
and the double-row recheck passes scatter parity without a tolerance change.
This does not change default production behavior, public OpenSubdiv types,
vendoring, submodules, generated dependency artifacts, formula semantics,
scatter order, OpenMP buffer/reduction shape, checkpoint/output behavior,
propagation behavior, optimizer behavior, or irregular/broader-valence routing.

The double-row route's serial/OpenMP executable-visible parity is tracked in
`docs/opensubdiv_regular_executable_parity.md`. That gate exercises the same
build-time and runtime route controls used by production binaries.

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
| Regular 12-control membrane force | Supported through the direct evaluator by default. OpenSubdiv-enabled binaries may route supported non-boundary, non-ghost regular faces only when runtime opt-in is explicit. | The guarded double-row route passes regular row, production-call force/scatter, geometry, output-visible, and serial/OpenMP executable parity under the current tolerance. | Guarded regular route active; preserve parity gates and direct fallback. |
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
- In an OpenSubdiv-enabled build, runtime opt-in installs reviewed rows only
  for supported non-boundary, non-ghost 12-control regular faces whose rows
  match the frozen regular plan under the current tolerance. Unsupported or
  non-equivalent faces emit a diagnostic and retain their existing path.
- `diagnose_opensubdiv_regular_production_call_parity` can be called only as a
  review-gated diagnostic. It requires the same runtime opt-in, builds the
  would-be routed rows, compares them against the direct regular path at the
  current per-face production helper shape, and reports deltas without
  installing routed rows. The current diagnostic exposes the bounded `fArea`,
  `fVolume`, and scatter-buffer deltas, including the face/local-row/source-id/axis
  or vertex/component/force-kind/axis location of the largest residual plus the signed
  direct/routed values at that residual. It also reports the maximum routed row
  weight difference against the frozen SLIMED rows for the same recheck,
  including the face, sample, derivative row, source column, resolved
  `Face::oneRingVertices[sourceColumn]` id, and signed direct/routed row values
  at the largest row residual, so the force/scatter residual can be
  read against the row-error budget. A direct-row override control now runs
  through the same production override/scatter seam with the frozen SLIMED rows
  and explicitly matches direct production semantics for area, legacy volume,
  mean curvature, bending energy, normals, `fBend`, `fArea`, `fVolume`, and
  scatter, while the OpenSubdiv-row force and scatter residuals report
  amplification ratios against the maximum row-weight residual. The same
  recheck also reports a tolerance envelope for the `fArea`,
  `fVolume`, and scatter residuals: component scales, residuals normalized to
  those scales, the current absolute tolerance, the required absolute and
  relative tolerances implied by the worst residual, the multiplier over the
  current gate, the residual source that sets that required tolerance, and an
  explicit `routedResidualToleranceReviewRequired` flag. It also emits a
  machine-readable `routedResidualReadinessDecision` plus
  `routedResidualActivationBlocker` and a current-policy activation gate via
  `routedResidualCurrentPolicySatisfied`,
  `routedResidualActivationAllowedByCurrentPolicy`, and
  `routedResidualActivationPolicyDecision` so the current state is recorded as a
  explicit readiness decision instead of an implicit activation policy.
  The opt-in C++ proof wrapper also emits the same current-policy state as a
  machine-readable `production_route_policy_diagnostic` report for reviewer
  decision packets. The production diagnostic now reports route installation
  when both build-time and runtime gates are active.
  The proof harness also compares the float compatibility factory
  with `Far::LimitStencilTableFactoryReal<double>`. The float rows reproduce
  the production diagnostic's approximately `1.457e-7` row residual, while
  the double rows match the frozen SLIMED rows to approximately `3.89e-16`.
  This isolated row-generation precision as the correction
  rather than an obvious `Face::oneRingVertices` scatter wiring bug or a reason
  to relax the scientific tolerance policy.
  The guarded evaluator now uses the double factory and passes the current
  direct-vs-routed tolerance gate and is the row source used by the guarded
  route.
- The direct regular path remains active unless both explicit route gates are
  enabled, and remains the fallback for faces outside the reviewed route.
- The existing `calculate_element_area_volume` and
  `element_energy_force_regular` helpers still own area, legacy volume,
  `fBend`, `fArea`, `fVolume`, normal, and mean-curvature semantics.
- The existing force scatter and serial/OpenMP thread-local force-buffer
  reduction shape are unchanged.
- Boundary, ghost, irregular, and non-equivalent faces avoid routed overrides
  and continue through their existing direct or subdivision path.

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
| Actual `fBend`/`fArea`/`fVolume` comparison | The opt-in `--regular-actual-force-report`, C++ proof harness, production-call recheck, and activated-route test cover finite nonzero force rows through `Mesh::element_energy_force_regular`. With the double limit-stencil factory, row mismatch is approximately `3.89e-16`, `fArea` delta is approximately `5.46e-12`, `fVolume` delta is approximately `2.84e-13`, and scatter delta is approximately `1.46e-11`; all pass the existing `5e-6` policy. | Keep the route tests and executable parity gate green. |
| Energy, normal, area, and volume comparison | Current regular probes, in-tree tests, visible-observable dry run, production-call recheck, and serial/OpenMP executable gate cover energy, mean curvature, normal, area, and legacy volume semantics on deterministic fixtures. Runtime opt-in now exercises the guarded route; absence of either gate preserves the direct path. | Preserve tests that fail if routed observables drift. |
| Scatter through `Face::oneRingVertices` | `RegularForceRowsScatterInOneRingOrder`, the C++ proof harness, the production-call recheck, and the activated-route test use the reviewed one-ring order. The double-row route passes scatter parity under the current tolerance. | Preserve this scatter order and keep the parity assertion green. |
| Serial/OpenMP tolerance envelope | The executable parity harness compiles the real accumulator in serial and OpenMP modes, then compares direct and runtime-routed snapshots for global/per-face energy, every vertex force component, normals, area, legacy volume, and mean curvature. The maximum direct/routed delta is approximately `4.66e-10`; the maximum serial/OpenMP delta is approximately `2.33e-10`. Irregular serial/OpenMP tolerance work remains separate. | Preserve this gate and the existing reduction order. |
| Fallback diagnostics | Dependency-absent probes skip cleanly; unsupported production irregular routes are guarded. | Production routing must never silently change physics based on ambient OpenSubdiv availability. Dependency-absent, unsupported topology, boundary, ghost, periodic, and failed-equivalence cases need explicit reviewed diagnostics. |
| Default dependency isolation | Stage 0 remains docs/scripts/probe-only and `OPENSUBDIV_ROOT`-gated. | No default dependency, vendoring, submodule, generated artifact, package-manager assumption, or Makefile target behavior change can be bundled into the routing proof. |
| Reviewer/user gate | The regular activation is isolated in an explicit reviewed PR after the executable parity gate. | Future route expansion or policy changes require their own reviewer/user approval. |

## Activated Regular Evidence Package

The guarded regular production route provides:

- a tiny production route selection boundary that is inactive unless explicitly
  built with OpenSubdiv and requested at runtime;
- confirmation that the routed route consumes the frozen regular fixtures and
  sample coordinates already proven by the proof lane;
- OpenSubdiv row/integrand equivalence for the routed sample plan;
- source-id row-weight reports keyed by original SLIMED ids from the routed
  production call site;
- duplicate aggregation checks for row weights at that call site;
- diagnostic-only production-call parity recheck output from
  `diagnose_opensubdiv_regular_production_call_parity`;
- actual bending, area, and volume force-row equivalence for `fBend`,
  `fArea`, and `fVolume` from the routed production call site;
- energy, normal, mean-curvature, area, and legacy-volume comparison through
  the production evaluator timing;
- scatter comparison through `Face::oneRingVertices`;
- serial/OpenMP tolerance report preserving thread-local force buffer shape
  and reduction order from the routed production path;
- dependency-absent and unsupported-route diagnostics; and
- explicit no-default-dependency and no-vendoring evidence.

The PR #72 through PR #103 evidence package can be cited as prerequisite
evidence, but it cannot be cited as production routing proof until a real
routed production path is installed and compared.

The exact regular 12-control sample plan is documented in
`docs/opensubdiv_regular_sample_plan.md`. That document is a readiness anchor,
not approval to route production faces through OpenSubdiv.

The regular backend-adapter checklist in
`docs/opensubdiv_regular_backend_adapter_readiness.md` ties the PR #68
weighted-sample seam, PR #69 mapping contract, PR #72 regular actual-force
evidence, PR #74 sample plan, PR #76 through PR #103 proof evidence, and this
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
