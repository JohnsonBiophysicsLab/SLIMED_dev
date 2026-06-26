# OpenSubdiv Backend Interface And Dependency Policy

Date: 2026-06-24.
Baseline: `origin/main` at `9ddabd2880364297351a8e1893dddec298266ed5`.

This began as a docs-only policy record for the approved OpenSubdiv sequence:
backend interface/dependency policy, then production force back-projection,
then production irregular routing. The current production code now includes a
narrow dependency-free 11-control subdivision/back-projection route for the
documented `11 = 4+3+4` case when `Param::subDivideTimes > 0`. The OpenSubdiv
policy remains unchanged: default builds stay OpenSubdiv-free, and any
OpenSubdiv-backed replacement still needs a separate backend/sample-plan
review. The only build-policy hook added here is a non-default script wrapper
for the existing observational probe; it requires the caller to set
`OPENSUBDIV_ROOT` and is not used by `make` targets or PR-ready verification.

## Recommendation

Adopt OpenSubdiv through a staged, opt-in backend path, but do not add build
integration or production routing in this lane.

1. Keep default SLIMED builds dependency-free and keep
   `SlimedLoopLimitSurfaceEvaluator` as the only production backend.
2. Keep the backend seam around SLIMED row semantics and SLIMED vertex ids,
   not around OpenSubdiv patch-table or stencil types. The public seam now
   includes evaluated rows plus row weights keyed by caller-provided SLIMED
   source ids.
3. Continue using `scripts/probe_opensubdiv_feasibility.py` as the runtime
   observational probe for user-provided installs.
4. Use `scripts/run_opensubdiv_probe.sh` as the current explicit opt-in smoke
   for user-provided OpenSubdiv installs. Add a Makefile target or production
   build integration only in a later reviewed lane.
5. Keep OpenSubdiv-backed routing gated behind production force
   back-projection and sample-plan review. The current dependency-free
   11-control route uses existing subdivision matrices and does not approve
   production OpenSubdiv routing.

## Current Production Route Versus Future Backend Criteria

As of the PR #64 baseline, SLIMED has one supported irregular production
route: positive-depth 11-control membrane-force patches matching the documented
`11 = 4+3+4` split. That route is dependency-free. It reuses the existing
irregular subdivision matrices, evaluates regular child patches, and
transposes child bending/area/volume force rows back through those matrices to
the original 11 `Face::oneRingVertices` entries.

That support does not make OpenSubdiv production-ready. It also does not
broaden SLIMED's irregular contract. These cases remain guarded or unsupported
until a separate reviewed PR changes them:

- 11-control membrane-force requests with `Param::subDivideTimes <= 0`;
- irregular neighborhoods outside the documented `11 = 4+3+4` matrix shape;
- OpenSubdiv-backed replacement of the current subdivision-matrix route;
- broader extraordinary-valence force, area, or volume support; and
- dependency-present behavior that differs from dependency-absent behavior.

Any future OpenSubdiv backend replacement must pass every criterion below, or
record an explicit reviewer-approved waiver. Observational probe output is
useful evidence for these gates, but it is not physics validation unless a
representative physical fixture exists and has reviewed expectations.

| Gate | Required evidence before OpenSubdiv can replace or broaden production routing |
| --- | --- |
| Physical fixture availability | A representative non-ghost physical irregular fixture, or a documented scientific decision that a synthetic fixture is sufficient for the specific claim. Fixture discovery alone is not validation. |
| Derivative and coordinate conventions | Approved mapping from OpenSubdiv `s,t`/`du,dv,duu,duv,dvv` to SLIMED `v,w,u` rows, including orientation, sign, row order, and the current duplicated mixed-row convention. |
| Ptex/sample coverage plan | Exact ptex faces, child patches, sample coordinates, and quadrature weights that represent one SLIMED face. Aggregate all-ptex source visibility is not enough by itself. |
| Source-id mapping | Row weights keyed by original SLIMED vertex ids, with tests proving the selected plan covers the exact controls expected by the SLIMED face and preserves the reviewed local ordering or documents a replacement ordering. |
| Transpose/back-projection shape | A reviewed map from sample-space bending, area, and volume gradients through backend row weights to SLIMED force rows. The shape must be compared against the existing subdivision-matrix transpose route where that route applies. |
| Regular equivalence tolerance | Frozen regular fixtures comparing value rows, first derivatives, pure and mixed second derivatives, tangent cross product, unit normal, area integrand, and legacy volume integrand against `SlimedLoopLimitSurfaceEvaluator` with stated tolerances. |
| Serial/OpenMP comparison tolerance | Serial and OpenMP comparisons on the approved fixtures, with stated tolerances for energies, forces, normals, area, and volume. The evidence must preserve or explicitly review thread-local buffer shape, scheduling assumptions, and reduction order. |
| Dependency/build/install/vendoring policy | A reviewed install/discovery policy such as `OPENSUBDIV_ROOT` or a non-default target. Default builds must remain OpenSubdiv-free until a dedicated dependency lane changes that policy. No vendored source, submodule, generated dependency artifact, or package-manager assumption may appear without license and maintenance review. |
| Backend interface ownership | OpenSubdiv types stay behind a backend-neutral SLIMED interface. The backend owns topology preparation, sample row weights, source-id mapping, and unsupported-topology diagnostics; force code owns formulas, scatter, reduction, and output-visible state. |
| Reviewer and scientific signoff | Reviewer approval for the backend interface and dependency policy, plus scientific signoff for any claim that irregular forces are physically validated. Evidence language must distinguish mechanical equivalence from physics validation. |
| Rollback/fallback behavior | Dependency-absent, unsupported topology, unsupported boundary/ghost/periodic, and failed-equivalence cases must fail loudly or fall back to the existing reviewed route only through explicit diagnostics. Silent fallback to the regular 12-control helper remains forbidden. |

## Minimal Backend Seam

The current production interface in `include/mesh/Limit_surface_evaluator.hpp`
is intentionally narrow: it evaluates one regular `12 x 3` control patch and
returns seven geometry rows. This lane adds the backend-neutral weighted
sample seam beside that geometry path: `LimitSurfaceEvaluator::evaluate_weighted(...)`
returns the same seven evaluated SLIMED rows plus row weights keyed by original
SLIMED source ids supplied by the caller. It does not add OpenSubdiv types,
OpenSubdiv build integration, or OpenSubdiv production routing.

Future backends should implement that same weighted sample contract without
exposing OpenSubdiv types in public SLIMED call sites:

```text
LimitSurfaceBackend
  construction/preparation:
    - consumes SLIMED mesh topology after boundary/ghost/periodic setup
    - records only SLIMED vertex ids at the public boundary
    - may cache backend topology/stencils internally for static topology

  per SLIMED face/sample:
    inputs:
      - SLIMED face id or face descriptor
      - sample coordinate in current SLIMED v,w,u convention
      - current control vertex coordinates addressed by SLIMED ids

    outputs:
      - evaluated rows:
          position
          d/dv
          d/dw
          d2/dv2
          d2/dw2
          d2/dvdw
          d2/dwdv
      - row weights keyed by original SLIMED vertex id for the same seven rows
      - explicit mapping metadata:
          OpenSubdiv du -> SLIMED d/dv
          OpenSubdiv dv -> SLIMED d/dw
          OpenSubdiv duu -> SLIMED d2/dv2
          OpenSubdiv dvv -> SLIMED d2/dw2
          OpenSubdiv duv -> both SLIMED mixed rows, if reviewed
      - source coverage diagnostics for regular and irregular fixtures
```

The seam should preserve two separate responsibilities:

- The backend owns topology preparation, sample row evaluation, row weights,
  source-id mapping, and unsupported-topology diagnostics.
- The energy/force implementation owns bending, area, and volume formulas,
  force row assembly, thread-local buffers, reduction order, and scatter into
  `Vertex::force.forceCurvature`, `forceArea`, and `forceVolume`.

Returning evaluated positions and derivatives alone is insufficient for force
work. The next production force lane needs row weights keyed by SLIMED vertex
ids so that a sample-space gradient can be transposed without changing
`Face::oneRingVertices` scatter semantics by accident.

The seam must also represent one SLIMED face as an explicit sample plan. The
observational irregular evidence shows that a single OpenSubdiv ptex face
sample may not cover all 11 local controls; aggregate coverage appears only
across adjacent ptex faces/sample locations. A production backend must
therefore state which ptex faces and sample locations contribute to one SLIMED
face before it can be used for irregular force routing.

## Staged Build And Dependency Policy

OpenSubdiv should not become a default dependency now. The safe staging is:

| Stage | Policy | Allowed work | Forbidden work |
| --- | --- | --- | --- |
| 0: docs/scripts probe | Current lane. No production build integration. | Docs, source inventories, opt-in probe runs, absent-dependency checks, and a non-default script wrapper requiring `OPENSUBDIV_ROOT`. | Build-file changes, C++ routing, vendoring, default dependency requirements. |
| 1: separate experimental target | First implementation lane after approval. | A non-default `opensubdiv_*` target or test binary using `OPENSUBDIV_ROOT`; no production object/link changes. | Default `make`/test dependency changes, production evaluator routing, package-manager assumptions. |
| 2: optional compile-time backend | After target and force-contract gates pass. | `USE_OPENSUBDIV=1`-style opt-in build path, hidden behind backend-neutral interfaces. | Making OpenSubdiv required for default builds or CI. |
| 3: reviewed production selection | Only after force back-projection is proven. | Explicit production routing for approved face classes with fallback diagnostics. | Silent irregular fallback, unreviewed boundary/ghost/periodic changes. |

Runtime probing remains appropriate for scripts and diagnostics. Production
code should not runtime-probe system paths to decide physics behavior; the
production binary must be built with an explicit backend configuration once
OpenSubdiv is approved.

## Dependency Rules For This Repo Today

The safe dependency policy today is user-provided install prefix first:

- Do not vendor OpenSubdiv source in this repo now.
- Do not add an OpenSubdiv source submodule now.
- Do not commit generated OpenSubdiv build directories, installed libraries,
  generated headers, downloaded archives, or package-manager artifacts.
- Continue to use `OPENSUBDIV_ROOT` for opt-in probes and future experimental
  targets. Allow `OPENSUBDIV_CXXFLAGS`, `OPENSUBDIV_LDFLAGS`, and `CXX` for
  local architecture or linker quirks.
- Prefer OpenSubdiv Far/core-only usage for SLIMED experiments. Disable or
  avoid GPU/viewer/documentation dependencies such as TBB, CUDA, OpenCL,
  OpenGL, Metal, Ptex, GLFW, zlib, and docs unless a later PR explicitly needs
  them.
- Keep SLIMED's C++ standard at C++17. Prior OpenSubdiv notes record that
  OpenSubdiv's core baseline is compatible with this.
- Record OpenSubdiv as Tomorrow Open Source Technology License 1.0, not MIT.
  Before distributing linked binaries or vendored/source-submodule code,
  perform a license review and add any required license/trademark notices.
- Default `make serial`, `make omp`, `make dyna`, `make dyna_omp`,
  `make test`, and `./bin/test_main` must pass without OpenSubdiv installed.

A source submodule is a later maintenance decision, not the first safe step.
It would need license review, update ownership, CI build-time policy, and a
rule that generated third-party artifacts are never committed.

## Opt-In Probe Smoke

The standardized OpenSubdiv smoke is a non-default script command:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv \
  --regular-equivalence-report \
  --aggregate-source-coverage-report \
  --force-transpose-report \
  --irregular-transpose-proof-map-report \
  --broader-valence-coverage-report
```

`OPENSUBDIV_CXXFLAGS` is optional and should only be used for local compiler or
architecture requirements. `OPENSUBDIV_LDFLAGS` and `CXX` may also be supplied
for local linker/compiler selection. The wrapper passes those variables through
to `scripts/probe_opensubdiv_feasibility.py`.

Expected absent-dependency behavior:

```bash
scripts/run_opensubdiv_probe.sh --json
```

returns `status: skipped` with exit code `0` when `OPENSUBDIV_ROOT` is unset.
This is the expected behavior in default developer and CI environments.

Expected present-dependency behavior is `status: passed` from the probe when
`OPENSUBDIV_ROOT` points at an install containing `include/opensubdiv/...` and
`lib/libosdCPU.*` or `lib64/libosdCPU.*`. `--require-opensubdiv` is appropriate
only for an explicitly OpenSubdiv-present smoke; it must not be used in default
build/test gates.

The direct Python probe remains available for manual diagnostics and legacy
notes, but the wrapper is the policy-approved command for this lane because it
does not auto-discover ambient system installs. Neither command vendors,
downloads, configures, or installs OpenSubdiv.

OpenSubdiv is licensed under the Tomorrow Open Source Technology License 1.0.
Do not describe it as MIT. Before distributing linked binaries, vendored
source, or submodules, perform a separate license and trademark-notice review.

## Gates Before Production Force Back-Projection

The next lane, production force back-projection, should start only after these
gates are green or explicitly review-waived:

| Gate | Required evidence |
| --- | --- |
| Regular row equivalence | OpenSubdiv rows match `SlimedLoopLimitSurfaceEvaluator` for regular samples: position, `d/dv`, `d/dw`, `d2/dv2`, `d2/dw2`, and both mixed rows under the documented `s=v,t=w` mapping. |
| Regular integrand equivalence | Tangent cross product, unit normal, area integrand, and current legacy volume integrand match frozen SLIMED regular outputs. |
| Toy transpose | `g dot (W p) == (W^T g) dot p` passes for OpenSubdiv's regular rows and the SLIMED-compatible seven-row shape, including the reviewed mixed-row duplication convention. |
| Production formula/scatter characterization | `docs/force_formula_scatter_equivalence.md` and `scripts/inventory_force_formula_scatter_contract.py --check` still locate the current bending/area/volume formula inputs, 12-row local outputs, `Face::oneRingVertices` scatter, component buffer layout, and thread reduction order. |
| Serial/OpenMP equality policy | The production force lane either proves serial/OpenMP outputs unchanged for the accepted fixtures or documents exact tolerated floating-point deltas with reviewer approval. It must preserve thread-local buffer shape and reduction order unless explicitly approved otherwise. |
| Accepted-step smokes | The committed accepted-step smoke remains passing if the force lane touches code that can affect accepted-step state, output-visible forces, energies, area, volume, normals, or checkpoints. |
| Irregular fixture coverage | The 11-control fixture source coverage and derivative completeness remain documented, including that aggregate OpenSubdiv coverage is not itself a face-level production scatter contract. |
| Broader-valence coverage | Representative synthetic extraordinary-valence classes report derivative-complete source-id visibility through an opt-in OpenSubdiv probe. This is evidence for future backend planning only; production broader-valence support still needs a physical fixture/sample plan, force transpose proof, scatter-order comparison, and scientific signoff. |
| Irregular transpose proof map | `docs/irregular_subdivision_transpose_proof_map.md` and the opt-in `--irregular-transpose-proof-map-report` distinguish aggregate 11-control toy transpose/source coverage from the in-repo subdivision-matrix production route. |
| Dependency/build isolation | The force lane does not make OpenSubdiv required for default builds. If it needs OpenSubdiv to run, it uses a separate experimental target or a user-provided install path. |

The previous irregular `nOneRingVertices == 11` force fallback into
`element_energy_force_regular(...)` was not compatibility behavior. The current
production route supports the documented positive-depth 11-control `4+3+4`
case through existing subdivision matrices and transpose back-projection. It
still rejects zero-depth 11-control requests and unsupported topologies, and the
former regular fallback must not be used as a baseline for approving broader
irregular physics.

## Next PR Prompt: Production Force Back-Projection

Use this prompt after policy approval:

```text
Create the production force back-projection proof for an OpenSubdiv-compatible
backend seam without enabling production irregular routing. Keep default builds
and production routing unchanged unless the PR is explicitly review-gated for
an opt-in experimental target. Starting from
docs/opensubdiv_backend_interface_policy.md,
docs/force_formula_scatter_equivalence.md, and
docs/irregular_subdivision_transpose_proof_map.md, define a backend-neutral
weighted sample-row contract that can express the current seven SLIMED rows by
original SLIMED vertex id. Prove on regular fixtures that transposing backend
value and derivative weights through the actual bending, area, and volume force
formulas produces the same local force rows and `Face::oneRingVertices`
scatter as the current `element_energy_force_regular(...)` path. Preserve
quadrature order, derivative convention, mixed-derivative convention, local
force row order, thread-local force buffer shape, reduction order,
serial/OpenMP behavior, boundary/ghost/periodic policy, legacy volume
semantics, checkpoint/output behavior, RNG behavior, optimizer timing, and
accepted-step timing. Include regular row/integrand equivalence, toy
transpose, irregular aggregate proof-map context, production formula/scatter
inventory, serial/OpenMP comparison, and accepted-step smoke validation. Do not
route production irregular faces through OpenSubdiv in this PR.
```

## Postponed To Backend Or Broader Irregular Routing

The following work remains outside the force back-projection lane:

- Selecting the exact ptex faces/sample locations that represent one SLIMED
  irregular face for an OpenSubdiv backend.
- Routing production `11`-control faces through OpenSubdiv or any backend other
  than the existing subdivision-matrix route.
- Broader extraordinary-valence production support beyond the current
  positive-depth 11-control `4+3+4` route. Opt-in synthetic source-coverage
  reports can inform this decision, but they are not validation or routing
  approval.
- Changing boundary, ghost, periodic, or unsupported-topology policy.
- Replacing the zero-depth unsupported irregular force guard or broadening the
  current subdivision-matrix route.
- Changing formulas, scatter order, OpenMP scheduling/reductions, volume
  semantics, propagation timing, optimizer timing, RNG behavior, checkpoint
  files, output files, or scaffold timing.

OpenSubdiv-backed or broader irregular routing should be its own review-gated
PR after the backend row-weight transpose and sample-plan contracts are
accepted.
