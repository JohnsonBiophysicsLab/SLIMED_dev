# OpenSubdiv Backend Interface And Dependency Policy

Date: 2026-06-24.
Baseline: `origin/main` at `9ddabd2880364297351a8e1893dddec298266ed5`.

This is a docs-only policy record for the approved OpenSubdiv sequence:
backend interface/dependency policy, then production force back-projection,
then production irregular routing. It does not change production C++ behavior,
default builds, `LimitSurfaceEvaluator`, formulas, scatter order, OpenMP
accumulation, boundary/ghost/periodic policy, volume semantics, RNG,
checkpoint/output behavior, optimizer timing, or OpenSubdiv dependency shape.

## Recommendation

Adopt OpenSubdiv through a staged, opt-in backend path, but do not add build
integration or production routing in this lane.

1. Keep default SLIMED builds dependency-free and keep
   `SlimedLoopLimitSurfaceEvaluator` as the only production backend.
2. Define the future backend seam around SLIMED row semantics and SLIMED vertex
   ids, not around OpenSubdiv patch-table or stencil types.
3. Continue using `scripts/probe_opensubdiv_feasibility.py` as the runtime
   observational probe for user-provided installs.
4. Add a separate experimental target only after this policy is approved. That
   target may use `OPENSUBDIV_ROOT`, but it must be absent from default
   `make serial`, `make omp`, `make dyna`, `make dyna_omp`, and `make test`.
5. Gate production force back-projection before any production irregular
   routing. Irregular routing remains postponed until the force transpose and
   scatter contract is reviewed against the actual production formulas.

## Minimal Backend Seam

The current production interface in `include/mesh/Limit_surface_evaluator.hpp`
is intentionally narrow: it evaluates one regular `12 x 3` control patch and
returns seven geometry rows. That remains the production contract until a
reviewed implementation PR changes it.

The minimal future seam should extend the existing concepts with a weighted
sample contract. It should be backend-neutral and should not expose OpenSubdiv
types in public SLIMED call sites:

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
| 0: docs/scripts probe | Current lane. No production build integration. | Docs, source inventories, opt-in probe runs, absent-dependency checks. | Build-file changes, C++ routing, vendoring, default dependency requirements. |
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
| Irregular fixture coverage | The 11-control fixture source coverage and derivative completeness remain documented, including that aggregate OpenSubdiv coverage is not yet a face-level production scatter contract. |
| Dependency/build isolation | The force lane does not make OpenSubdiv required for default builds. If it needs OpenSubdiv to run, it uses a separate experimental target or a user-provided install path. |

The existing irregular `nOneRingVertices == 11` force fallback into
`element_energy_force_regular(...)` is not compatibility behavior. It is a
known unsupported production gap and must not be used as a baseline for
approving new irregular physics.

## Next PR Prompt: Production Force Back-Projection

Use this prompt after policy approval:

```text
Create the production force back-projection proof for an OpenSubdiv-compatible
backend seam without enabling production irregular routing. Keep default builds
and production routing unchanged unless the PR is explicitly review-gated for
an opt-in experimental target. Starting from
docs/opensubdiv_backend_interface_policy.md and
docs/force_formula_scatter_equivalence.md, define a backend-neutral weighted
sample-row contract that can express the current seven SLIMED rows by original
SLIMED vertex id. Prove on regular fixtures that transposing backend value and
derivative weights through the actual bending, area, and volume force formulas
produces the same local force rows and `Face::oneRingVertices` scatter as the
current `element_energy_force_regular(...)` path. Preserve quadrature order,
mixed-derivative convention, local force row order, thread-local force buffer
shape, reduction order, serial/OpenMP behavior, boundary/ghost/periodic policy,
legacy volume semantics, checkpoint/output behavior, RNG behavior, optimizer
timing, and accepted-step timing. Include regular row/integrand equivalence,
toy transpose, production formula/scatter inventory, serial/OpenMP comparison,
and accepted-step smoke validation. Do not route production irregular faces
through OpenSubdiv in this PR.
```

## Postponed To Production Irregular Routing

The following work remains outside the force back-projection lane:

- Selecting the exact ptex faces/sample locations that represent one SLIMED
  irregular face.
- Routing production `11`-control faces through OpenSubdiv or any other
  irregular backend.
- Changing boundary, ghost, periodic, or unsupported-topology policy.
- Broad extraordinary-valence support beyond characterized fixtures.
- Replacing the known irregular force fallback with production behavior.
- Changing formulas, scatter order, OpenMP scheduling/reductions, volume
  semantics, propagation timing, optimizer timing, RNG behavior, checkpoint
  files, output files, or scaffold timing.

Production irregular routing should be its own review-gated PR after the
backend row-weight transpose contract is accepted.
