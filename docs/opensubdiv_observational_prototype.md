# OpenSubdiv Observational Prototype Lane

Date: 2026-06-23.
Baseline: `origin/main` at `d5eeb0ea535fce24066735909cdfe0512c3e91c7`
after PR #47.

This lane is intentionally non-production. It does not change SLIMED C++
behavior, default Makefile targets, dependency policy, energy/force routing,
force scatter, checkpoint/output formats, OpenMP behavior, boundary/ghost
policy, or the current `LimitSurfaceEvaluator` implementation.

Post-PR64 refinement: the prototype evidence remains observational even though
SLIMED now supports the documented positive-depth 11-control `4+3+4`
production route through existing subdivision matrices and transpose
back-projection. The current supported route is not OpenSubdiv-backed. The
prototype reports below can inform future backend criteria, but they do not
replace the production gates in
`docs/opensubdiv_backend_interface_policy.md`.

## Local Dependency Result

OpenSubdiv is not available in this worktree environment:

- `brew list --versions opensubdiv` returned no installed version.
- `pkg-config --modversion opensubdiv` could not find an `opensubdiv.pc`.
- `/opt/homebrew/opt/opensubdiv`, `/opt/homebrew/include/opensubdiv`, and
  `/usr/local/include/opensubdiv` were absent.
- Searching `/opt/homebrew` and `/usr/local` found no OpenSubdiv headers or
  CMake package files.

Because dependency installation, source cloning, vendoring, and production
build integration all require a separate dependency-policy review, the probe
remains inert and opt-in by default.

The policy-approved smoke wrapper for this lane is:

```bash
scripts/run_opensubdiv_probe.sh --json
```

When `OPENSUBDIV_ROOT` is unset, it returns `status: skipped` with exit code
`0`. This is expected for default builds/tests and should not fail PR-ready
verification. To run against a user-provided install, set
`OPENSUBDIV_ROOT=/path/to/opensubdiv-install`; optional local compiler/linker
overrides are `OPENSUBDIV_CXXFLAGS`, `OPENSUBDIV_LDFLAGS`, and `CXX`.

## Present-Dependency Result

A scratch OpenSubdiv build outside the repo was able to compile and run the
committed probe:

- source: `https://github.com/PixarAnimationStudios/OpenSubdiv.git`
- commit: `9dab8a47bfbb1388ec8388fe61f5f916e6123f38`
- reported version: `v3_7_0`
- source path: `/tmp/slimed-opensubdiv-src`
- build path: `/tmp/slimed-opensubdiv-build`
- install path: `/tmp/slimed-opensubdiv-install`
- configure flags:
  `-DCMAKE_BUILD_TYPE=Release -DNO_EXAMPLES=ON -DNO_TUTORIALS=ON
  -DNO_REGRESSION=ON -DNO_TESTS=ON -DNO_PTEX=ON -DNO_DOC=ON -DNO_OMP=ON
  -DNO_TBB=ON -DNO_CUDA=ON -DNO_OPENCL=ON -DNO_CLEW=ON -DNO_OPENGL=ON
  -DNO_METAL=ON -DNO_DX=ON -DNO_GLFW=ON -DNO_GLEW=ON
  -DBUILD_SHARED_LIBS=ON`
- probe command:
  `OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install
  OPENSUBDIV_CXXFLAGS='-arch arm64'
  scripts/run_opensubdiv_probe.sh --json --require-opensubdiv`

The explicit `-arch arm64` flag was needed in this Codex environment because
the temporary OpenSubdiv library was built as arm64 while the first probe link
attempt produced an x86_64 object.

The present-dependency probe returned `status: passed`. It showed:

- a Loop `Far::TopologyDescriptor` can be built and adaptively refined for a
  triangular lattice;
- `Far::LimitStencilTable` can provide value, first-derivative, and
  second-derivative weight arrays for the sampled locations;
- the regular lattice samples expose 12 original source ids and finite
  position, `du`, `dv`, `duu`, `duv`, and `dvv` vectors; and
- the synthetic 11-control topology can be represented as an OpenSubdiv
  triangular topology and evaluated with finite derivative vectors.

This result is still not a production-backend approval. The irregular fixture
samples currently report three source ids for the selected face, not a broad
11-control source stencil. That is useful evidence that the topology can be
accepted and evaluated, but it does not yet prove the future force
back-projection contract or a stable original-control mapping for all 11
fixture controls.

## Force Back-Projection Mapping Follow-Up

The follow-up `--backprojection-report` mode keeps the probe opt-in and
docs/scripts-only. It adds patch-table diagnostics, expands patch control
vertices through generated control-vertex stencils, and compares three
11-control variants:

- the original compact fixture topology used by the first probe;
- an orientation-normalized version of the same 11-control face set; and
- the orientation-normalized fixture with an added outer annulus so the
  original 11 controls are not on the miniature mesh boundary.

The scratch OpenSubdiv `v3_7_0` build at `/tmp/slimed-opensubdiv-install` was
run with:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
python3 scripts/probe_opensubdiv_feasibility.py \
  --json --require-opensubdiv --backprojection-report
```

Observed source-control coverage:

| Case | Sample locations | Limit-stencil source ids | Derivative weights | Expected local controls represented | Interpretation |
| --- | ---: | ---: | --- | ---: | --- |
| regular triangular lattice | 3 | 12 | value, first, second | n/a | Regular Loop patch source mapping remains available and derivative-complete. |
| compact 11-control fixture | 3 | 3 | value, first, second | 3 of 11 | The original fixture face list is not consistently oriented as a manifold OpenSubdiv topology, so this result is a topology artifact. |
| oriented 11-control fixture | 3 | 9 | value, first, second | 9 of 11 | Orientation fixes the three-source collapse and exposes broader original-control weights, but not all 11 controls for this one sampled face. |
| oriented 11-control fixture with outer annulus | 3 | 9 | value, first, second | 9 of 11 | Padding the local boundary does not change the sampled face support; the missing controls are not recovered by a simple outer ring. |

The missing expected local controls in the oriented fixture were ids `8` and
`10` for sampled ptex face `0`. That suggests the current all-11 question is
mostly a sampling/support question: a single triangle patch sample does not
necessarily touch every SLIMED 11-control local fixture entry. The next
experiment should aggregate source coverage over the adjacent ptex faces or
over the regular child patches that correspond to SLIMED's irregular
subdivision route before asking whether a face-level force contract covers all
11 original controls.

This is not a production force back-projection implementation. It only shows
that OpenSubdiv can expose derivative-complete original-control weights for a
properly oriented irregular fixture sample, and that the first three-source
result was caused by the probe's topology construction/API path rather than by
a missing derivative-weight API.

## Aggregate Source-Coverage Follow-Up

The follow-up `--aggregate-source-coverage-report` mode remains opt-in and
inert without `OPENSUBDIV_ROOT`. It builds on the same scratch OpenSubdiv
`v3_7_0` install and samples every ptex face in each synthetic topology at a
documented nine-point barycentric grid:

- the PR #50 samples `{(v,w) = (1/3,1/3), (0.20,0.30), (0.05,0.85)}`;
- three interior grid points `{(0.20,0.20), (0.60,0.20), (0.20,0.60)}`; and
- three near-corner/interior points `{(0.10,0.10), (0.45,0.10), (0.10,0.45)}`.

The prototype now reports the observed coordinate mapping `s=v,t=w`. For
each evaluated location, the report unions original control ids with nonzero
value, first-derivative, and second-derivative weights. It also records the
sampled patch ids/types returned through `Far::PatchMap`, so the aggregate is
explicitly across adjacent ptex faces and the child patches reached by the
current OpenSubdiv patch table.

Observed aggregate coverage with:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
python3 scripts/probe_opensubdiv_feasibility.py \
  --json --require-opensubdiv --aggregate-source-coverage-report
```

| Case | Ptex faces | Samples | Sampled patch type | Value ids | First-derivative ids | Second-derivative ids | Interpretation |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| oriented 11-control fixture | 12 | 108 | `LOOP` | `0..10` | `0..10` | `0..10` | All original fixture controls, including ids `8` and `10`, are represented when coverage is aggregated across adjacent ptex faces/sample locations. |
| oriented 11-control fixture with outer annulus | 28 | 252 | `LOOP` | `0..18` (`0..10` all present) | `0..18` (`0..10` all present) | `0..18` (`0..10` all present) | Padding does not break the aggregate mapping; all original fixture controls remain represented. |

This proves only aggregate source coverage for the observational topology and
sample grid. It does not prove that a single SLIMED face-level force contract
should gather from every adjacent ptex face or that force contributions can be
transposed into SLIMED's current scatter order without a separate review.
It also does not prove physical validity for irregular force routing without a
representative physical fixture and reviewed expectations.

Before production adoption, SLIMED still needs:

- regular-patch numerical equivalence against `SlimedLoopLimitSurfaceEvaluator`
  for normals, area integrand, and legacy volume integrand;
- a reviewed force transpose/back-projection contract from OpenSubdiv value and
  derivative weights to SLIMED original vertex ids;
- an accumulation/scatter ordering proof preserving serial and OpenMP behavior;
- a backend interface decision behind `LimitSurfaceEvaluator`;
- an explicit build/dependency/licensing policy for OpenSubdiv; and
- scientific review before irregular force routing is enabled.

## Regular Equivalence Follow-Up

The follow-up `--regular-equivalence-report` mode remains opt-in and inert
without `OPENSUBDIV_ROOT`. It compares OpenSubdiv's regular triangular lattice
samples against frozen values generated from the current
`SlimedLoopLimitSurfaceEvaluator` for the same 12-control regular one-ring
fixture. The frozen SLIMED values are also covered by
`SurfaceLimitSurfaceEvaluatorContract.RegularLatticeProbeFrozenOutputsMatchCurrentEvaluator`
in `tests/test_surface_geometry_characterization.cpp`, so default tests can
detect accidental drift without linking OpenSubdiv.

The scratch OpenSubdiv `v3_7_0` build at `/tmp/slimed-opensubdiv-install` was
run with:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
python3 scripts/probe_opensubdiv_feasibility.py \
  --json --require-opensubdiv --regular-equivalence-report
```

Observed regular comparison:

| Case | Samples | Compared quantities | Coordinate mapping | Tolerance | Max absolute difference | Max relative difference |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| regular triangular lattice | 3 | value, `d/dv`, `d/dw`, `d2/dv2`, `d2/dw2`, and mixed derivative rows | `s=v, t=w` | `5e-6` | `3.87430191e-7` | `3.87430191e-7` |

This corrects the earlier provisional `s=w,t=v` note. For the sampled regular
face, OpenSubdiv's `s` parameter follows SLIMED's `v` derivative row, and
OpenSubdiv's `t` parameter follows SLIMED's `w` derivative row. OpenSubdiv
provides one mixed derivative, which matched both of SLIMED's duplicated mixed
rows within the stated tolerance.

This remains observational evidence, not a production backend approval. It
does not define force transpose semantics, force scatter or accumulation order,
boundary/ghost/periodic policy, irregular routing, dependency policy, or
default build integration.

## Regular Integrand Equivalence Follow-Up

The follow-up integrand extension keeps the same
`--regular-equivalence-report` mode and remains inert without
`OPENSUBDIV_ROOT`. It derives regular tangents, the unnormalized normal, unit
normal, area integrand, and legacy volume integrand from the already matched
OpenSubdiv value/derivative rows and compares them with frozen SLIMED regular
evaluator values.

The convention is intentionally the current SLIMED convention, not a revised
formula:

- OpenSubdiv `du` maps to SLIMED `d/dv`, and OpenSubdiv `dv` maps to SLIMED
  `d/dw`.
- The unnormalized normal is `cross(du, dv)`, equivalent to
  `cross(d/dv, d/dw)` under the observed `s=v,t=w` mapping.
- The area integrand is `norm(cross(du, dv))`.
- The legacy volume integrand is `position.x * cross(du, dv).x`, matching the
  current regular `LimitSurfaceEvaluator` compatibility path in
  `Mesh::enumerate_regular_patch_area_volume_with_limit_surface_evaluator()`.

The scratch OpenSubdiv `v3_7_0` build at `/tmp/slimed-opensubdiv-install` was
run with:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
python3 scripts/probe_opensubdiv_feasibility.py \
  --json --require-opensubdiv --regular-equivalence-report
```

Observed regular comparison:

| Case | Samples | Compared quantities | Coordinate mapping | Tolerance | Max raw row difference | Max derived integrand difference |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| regular triangular lattice | 3 | value, `d/dv`, `d/dw`, `d2/dv2`, `d2/dw2`, mixed derivative rows, `cross(d/dv,d/dw)`, unit normal, area integrand, and legacy volume integrand | `s=v, t=w` | `5e-6` | `3.87430191e-7` | `2.82479599e-7` |

The default test suite still does not require OpenSubdiv. The SLIMED-side
frozen normal, area-integrand, and legacy-volume-integrand values are covered
by
`SurfaceLimitSurfaceEvaluatorContract.RegularLatticeProbeFrozenIntegrandsMatchCurrentEvaluator`
in `tests/test_surface_geometry_characterization.cpp`.

This proves regular integrand equivalence only for the selected regular
lattice samples and the current legacy SLIMED volume convention. It still does
not define force transpose semantics, force scatter or accumulation order,
boundary/ghost/periodic policy, irregular routing, dependency policy, or
default build integration.

The regular tolerance is therefore a necessary backend criterion, not a
sufficient production approval.

## Force Transpose Contract Follow-Up

The follow-up `--force-transpose-report` mode remains opt-in and inert without
`OPENSUBDIV_ROOT`. It does not call SLIMED production force code, implement
force back-projection, change scatter ordering, or evaluate bending, area, or
volume force formulas. Instead, it checks the linear algebra contract that any
future force backend would rely on:

```text
g dot (W p) == (W^T g) dot p
```

Here `W` is the OpenSubdiv value/derivative weight map from original control
points to one sample's evaluated rows, `p` is the original control-point
coordinate vector, and `g` is a deterministic toy sample-space gradient. The
check proves only that OpenSubdiv's reported value and derivative weights can
be transposed as a linear map for a toy scalar functional.

The scratch OpenSubdiv `v3_7_0` build at `/tmp/slimed-opensubdiv-install` was
run with:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
python3 scripts/probe_opensubdiv_feasibility.py \
  --json --require-opensubdiv --force-transpose-report
```

Observed regular transpose shape:

| Case | Samples | Source ids per sample | Local control components | OpenSubdiv sample gradient components | SLIMED-compatible sample gradient components | Max transpose difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| regular triangular lattice | 3 | 12 | 36 | 18 | 21 | `1.11022302e-15` |

The OpenSubdiv row contract is `value, du, dv, duu, duv, dvv`. Under the
observed regular mapping, `du=d/dv`, `dv=d/dw`, `duu=d2/dv2`, and
`dvv=d2/dw2`. For the SLIMED-compatible 21-component toy gradient,
OpenSubdiv's single `duv` row is used for both current SLIMED mixed rows
`d2/dvdw` and `d2/dwdv`. This is a transpose-shape observation only; a
production adapter would still need a reviewed mixed-derivative convention.

The regular samples back-project to the same 12 original source ids already
matched by the regular equivalence reports:

```text
[9,10,11,15,16,17,18,22,23,24,29,30]
```

This means the regular case can express a sample-space gradient over the
matched OpenSubdiv value/derivative rows as contributions on the same 12 local
controls used by SLIMED's current regular one-ring evaluator.

Observed irregular fixture transpose shape:

| Case | Samples | Source ids per sampled face | Interpretation |
| --- | ---: | ---: | --- |
| compact 11-control fixture | 3 | 3 | The original unoriented compact topology still collapses the sampled face to three source ids; this remains a topology artifact and is not a force contract. |
| oriented 11-control fixture | 3 | 9 | A single sampled face transposes to nine original controls, not all 11 fixture controls. |
| oriented 11-control fixture with outer annulus | 3 | 9 | Padding the local boundary does not change the single sampled face support. |

These irregular results are consistent with the aggregate source-coverage
follow-up: all 11 original fixture controls appear only when aggregating across
adjacent ptex faces/sample locations. They do not prove a SLIMED face-level
force scatter contract for irregular patches.

Current SLIMED regular force contract observed in
`src/energy_force/Compute_energy_and_force_on_mesh.cpp`:

- `element_energy_force_regular(...)` evaluates seven local shape rows:
  position, `d/dv`, `d/dw`, `d2/dv2`, `d2/dw2`, `d2/dvdw`, and `d2/dwdv`.
- Per sample, bending uses first and second derivative rows through the current
  `da1`/`da2` formulas and writes local `fBend(j,:)` for each regular local
  control column.
- Area uses the first derivative rows and writes local `fArea(j,:)`.
- Volume uses position plus first derivative rows and writes local
  `fVol(j,:)`.
- The face loop scatters local rows in `Face::oneRingVertices[j]` order into
  per-thread vertex force component buffers, then reduces thread buffers into
  `Vertex::force.forceCurvature`, `forceArea`, and `forceVolume`.

What this follow-up proves:

- OpenSubdiv's regular value, first-derivative, and second-derivative weights
  can be transposed for a toy scalar functional at the same three regular
  samples used by the existing equivalence report.
- The regular transpose shape is compatible with 12 local controls and 36
  local control components.
- The current SLIMED seven-row mixed-derivative shape can be represented in a
  toy check by duplicating OpenSubdiv's single `duv` row into the two SLIMED
  mixed rows.

What remains unproven before backend work:

- Production bending, area, and volume force formula equivalence.
- Production force back-projection through the actual SLIMED force formulas.
- Scatter and floating-point accumulation ordering, including serial/OpenMP
  behavior.
- Irregular face-level force support over the 11-control fixture.
- Boundary, ghost, and periodic policy.
- Dependency, licensing, and default build policy for OpenSubdiv.
- Scientific review of any force-routing or backend-interface decision.

## Production Force Formula And Scatter Characterization Follow-Up

The follow-up `docs/force_formula_scatter_equivalence.md` records the
production-side contract that remains after the PR #54 toy transpose proof. It
maps the current seven regular evaluator rows to the bending, area, and volume
force terms, records how the 12 local force rows scatter through
`Face::oneRingVertices`, and describes the serial/OpenMP thread-local force
buffer reduction shape.

This follow-up adds no OpenSubdiv dependency and changes no production routing.
The source-anchor inventory can be regenerated with:

```bash
python3 scripts/inventory_force_formula_scatter_contract.py --fail-on-missing
```

The focused default test
`SurfaceLimitSurfaceEvaluatorContract.RegularForceRowsScatterInOneRingOrder`
checks a permuted regular one-ring fixture by comparing direct
`element_energy_force_regular(...)` local force rows against the production
`Compute_Energy_And_Force()` scatter into `Vertex::force.forceCurvature`,
`forceArea`, and `forceVolume`.

## Added Probe

`scripts/probe_opensubdiv_feasibility.py` checks for an explicitly supplied or
commonly installed OpenSubdiv prefix. Without OpenSubdiv it exits successfully
with a `skipped` status, so it is safe for local/default validation.

When `OPENSUBDIV_ROOT` points at an install containing
`include/opensubdiv/far/topologyDescriptor.h` and `lib/libosdCPU.*`, the script
generates a temporary C++17 file outside the repo and attempts a Far-only Loop
probe. The generated probe:

- builds a `Far::TopologyDescriptor` for a small triangular lattice using
  `Sdc::SCHEME_LOOP`;
- builds a second topology carrying the PR #45 synthetic 11-control source ids
  and coordinates as an observational irregular fixture;
- requests `Far::LimitStencilTable` samples with first and second derivative
  weights;
- emits source control-vertex ids, derivative weight counts, and derivative
  vectors for each sample; and
- evaluates finite position, first derivative, second derivative,
  tangent-cross, unit-normal, area-integrand, and legacy-volume-integrand
  values from the stencil weights.

The probe reports the observed regular SLIMED-to-OpenSubdiv coordinate mapping
of `s=v, t=w`.

Example absent-dependency command:

```bash
scripts/run_opensubdiv_probe.sh --json
```

This wrapper requires `OPENSUBDIV_ROOT` for present-dependency probes. Without
that variable it returns `status: skipped` with exit code `0`. The documented
JSON spelling is `--json`; legacy checklists that invoke `--mode check`
receive the same JSON status for compatibility.

Example opt-in command:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_probe.sh --json --require-opensubdiv
```

Example opt-in force back-projection report:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv --backprojection-report
```

Example opt-in aggregate source-coverage report:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv --aggregate-source-coverage-report
```

If the local install needs nonstandard flags, callers can provide
`OPENSUBDIV_CXXFLAGS`, `OPENSUBDIV_LDFLAGS`, or `CXX`. The script does not
modify the production Makefile and does not copy third-party source into the
repo.

Example opt-in regular-equivalence report:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv --regular-equivalence-report
```

Example opt-in force transpose contract report:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv --force-transpose-report
```

Example opt-in 11-control transpose proof-map report:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv --irregular-transpose-proof-map-report
```

The proof-map report is summarized in
`docs/irregular_subdivision_transpose_proof_map.md`. It stacks the same
SLIMED-compatible toy transpose identity across every ptex face and the
documented sample grid for the 11-control fixture variants. It is still
observational evidence only: the orientation-normalized fixture can expose all
11 local source ids at aggregate level, but production must still approve the
face-level sample plan, formula transpose, scatter order, and fallback policy
before 11-control force routing.

Example opt-in broader-valence source-coverage report:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv --broader-valence-coverage-report
```

This report adds synthetic triangular fan topologies with extraordinary center
valences `3`, `5`, `7`, and `9`. Each case uses a center vertex, an inner fan,
and an outer annulus, then aggregates value, first-derivative, and
second-derivative source ids across every ptex face and the same documented
nine-point sample grid used by the 11-control aggregate report. The expected
local source ids are the synthetic fan's original control ids, so the report
answers a narrow visibility question: whether OpenSubdiv can expose original
source ids for representative broader valence classes in a way that a future
backend could inspect.

This is not physics validation and not production support. The current SLIMED
production contract remains unchanged: regular 12-control faces and the
positive-depth documented 11-control `4+3+4` route through existing
subdivision matrices are the supported paths, while zero-depth 11-control
requests and unsupported broader topologies remain guarded. Any future
broader-valence backend still needs the approved ptex/sample plan,
source-ordering policy, formula transpose proof, scatter/reduction comparison,
dependency policy, and scientific review from
`docs/opensubdiv_backend_interface_policy.md`.

Observed broader-valence coverage with the scratch OpenSubdiv `v3_7_0` install
at `/tmp/slimed-opensubdiv-install`:

| Case | Ptex faces | Samples | Expected original ids | Single sampled face ids | Aggregate value/first/second ids | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| valence-3 fan | 9 | 81 | 7 | 7 of 7 | all 7 | A single sampled face and the aggregate grid both expose every synthetic source id. |
| valence-5 fan | 15 | 135 | 11 | 9 of 11 | all 11 | Aggregate coverage recovers the full fan/annulus source set; a single sampled face does not. |
| valence-7 fan | 21 | 189 | 15 | 11 of 15 | all 15 | Broader valence increases the face-local/aggregate distinction. |
| valence-9 fan | 27 | 243 | 19 | 13 of 19 | all 19 | Aggregate source visibility remains derivative-complete for this synthetic topology. |

The useful observation is the pattern, not the synthetic numbers themselves:
source visibility for broader valence can depend on the selected ptex/sample
plan. A production backend would need to justify exactly which ptex faces and
sample locations represent one SLIMED face before any force scatter claim.

The approved valence-4 stand-in now has a separate proof-only report:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_irregular_valence4_opensubdiv_mapping_proof.sh \
  --json --require-opensubdiv
```

It loads the serialized octahedron CSVs, maps oriented fixture face rows to
Ptex IDs `0..7`, freezes three SLIMED samples per face in face-major order,
emits dense `7 x 6` rows keyed by source IDs `0..5`, compares patch-basis and
limit-stencil rows, checks deterministic duplicate aggregation and coverage
unions, and proves per-sample plus stacked linear transpose identities. The
approval is limited to this mechanical evidence; `scientifically_approved`
and `production_route_enabled` remain false.

## Feasibility Questions

1. Can a Loop-scheme OpenSubdiv Far topology be built from SLIMED-style
   vertices/faces?

   Proven for the scratch OpenSubdiv `v3_7_0` build above. The opt-in probe
   constructs a triangular lattice and the PR #45 source-id fixture.

2. Can OpenSubdiv generate/evaluate limit stencils or patch-table basis values
   with first/second derivative weights?

   Proven for the scratch OpenSubdiv `v3_7_0` build above. The probe requests
   `LimitStencilTable` position, `du`/`dv`, and `duu`/`duv`/`dvv` weights and
   fails loudly if any derivative array is missing.

3. Can prototype code expose source control-vertex indices/weights clearly
   enough to support force back-projection later?

   Proven for aggregate observational coverage, but not for production force
   routing. The regular lattice sample exposes 12 source ids and matching
   derivative weight counts. The original compact 11-control fixture reported
   only three source ids for one sampled face because its face list was not
   consistently oriented for OpenSubdiv manifold topology. An
   orientation-normalized fixture exposes nine original source ids for sampled
   ptex face `0`, then exposes all ids `0..10` with value, first-derivative,
   and second-derivative weights when aggregated across all ptex faces and the
   documented sample grid. A later production lane still needs a reviewed
   transpose/back-projection contract and force scatter ordering proof.

4. Can a regular case be compared against SLIMED's regular evaluator at
   quadrature-like sample points?

   Proven observationally for the scratch OpenSubdiv `v3_7_0` build above.
   The regular lattice comparison matched value, first derivatives, pure second
   derivatives, and both SLIMED mixed derivative rows for three sample points
   with max absolute and relative differences of `3.87430191e-7` against a
   `5e-6` tolerance. The observed coordinate mapping is `s=v, t=w`.

5. Can a toy sample-space gradient be transposed back to the same 12 regular
   local controls used by SLIMED?

   Proven observationally for a toy linear functional only. The
   `--force-transpose-report` mode checks `g dot (W p) == (W^T g) dot p`
   for OpenSubdiv's regular value/derivative rows and for a
   SLIMED-compatible seven-row shape that duplicates OpenSubdiv's `duv` row
   into both mixed derivative slots. The regular lattice samples report 12
   source ids, 36 local control components, 21 SLIMED-compatible sample
   gradient components, and a max transpose difference of `1.11022302e-15`.
   This does not prove production force formulas or scatter ordering.

   Future replacement work must still provide the full criteria set from
   `docs/opensubdiv_backend_interface_policy.md`: physical fixture status,
   derivative/coordinate convention, ptex/sample plan, source-id mapping,
   transpose/back-projection shape, regular equivalence tolerance,
   serial/OpenMP comparison tolerance,
   dependency/build/install/vendoring policy, backend interface ownership,
   reviewer/scientific signoff, and rollback/fallback behavior.

6. Can the PR #45 11-control irregular fixture be represented at least as
   topology/source-id mapping?

   Proven for aggregate observational source coverage. The installed run
   accepted the 11-control triangular topology and produced finite value and
   derivative vectors. With consistent face orientation, the selected ptex face
   reports nine original-control source ids and derivative-complete weights.
   Aggregating over all ptex faces and the documented sample grid reports ids
   `0..10` for value, first-derivative, and second-derivative weights,
   including the previously missing ids `8` and `10`.

7. Can the aggregate 11-control source weights be transposed as a local
   proof-map shape?

   Proven observationally for a toy stacked linear functional only. The
   `--irregular-transpose-proof-map-report` mode checks
   `sum_samples g dot (W_sample p) == p dot sum_samples (W_sample^T g)` over
   all ptex faces and the documented sample grid. For the
   orientation-normalized fixture, the useful evidence is that the aggregate
   toy back-projection covers local ids `0..10`. This still does not choose a
   production face-level sample plan, route irregular forces, or prove bending,
   area, and volume formula equivalence.

8. What evidence would be needed before broader extraordinary valences could be
   considered?

   The new `--broader-valence-coverage-report` mode characterizes source-id
   visibility for synthetic extraordinary-valence fan topologies only when an
   OpenSubdiv install is explicitly supplied. It is intended to show what a
   future backend would need to report for valence classes outside the current
   `11 = 4+3+4` route: derivative-complete source ids keyed to original SLIMED
   controls, explicit ptex/sample coverage, and enough metadata to compare a
   proposed face-level sample plan against SLIMED's scatter contract. Passing
   this report would still be necessary-but-insufficient evidence; it would not
   approve production formulas, volume semantics, force back-projection,
   boundary/ghost behavior, or OpenMP reduction behavior.

## Next Review Gate

The next useful lane is review-gated:

```text
With an approved local OpenSubdiv install path, decide the next review gate
before backend work: either design a production force-formula equivalence and
scatter-order proof, or define the backend interface and dependency policy in
a separate non-default build lane. That decision must explain exactly which
ptex faces/sample locations contribute to one SLIMED face, how derivative rows
map to SLIMED's `v,w,u` convention, and how contributions scatter back to
original vertex ids without changing serial or OpenMP accumulation order. Do
not change production routing, force scatter, default Makefile targets,
vendoring policy, or dependency requirements in that lane.
```
