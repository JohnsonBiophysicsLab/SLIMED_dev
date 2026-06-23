# OpenSubdiv Observational Prototype Lane

Date: 2026-06-23.
Baseline: `origin/main` at `d5eeb0ea535fce24066735909cdfe0512c3e91c7`
after PR #47.

This lane is intentionally non-production. It does not change SLIMED C++
behavior, default Makefile targets, dependency policy, energy/force routing,
force scatter, checkpoint/output formats, OpenMP behavior, boundary/ghost
policy, or the current `LimitSurfaceEvaluator` implementation.

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
  python3 scripts/probe_opensubdiv_feasibility.py --json
  --require-opensubdiv`

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
- evaluates finite position, first derivative, and second derivative vectors
  from the stencil weights.

The probe uses a provisional SLIMED-to-OpenSubdiv coordinate mapping of
`s=w, t=v`. That mapping is reported in the output and remains unproven until
an installed OpenSubdiv run can be compared against SLIMED's regular evaluator.

Example absent-dependency command:

```bash
python3 scripts/probe_opensubdiv_feasibility.py --json
```

The documented spelling is `--json`; legacy checklists that invoke
`--mode check` receive the same JSON status for compatibility.

Example opt-in command:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
python3 scripts/probe_opensubdiv_feasibility.py --json --require-opensubdiv
```

Example opt-in force back-projection report:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
python3 scripts/probe_opensubdiv_feasibility.py \
  --json --require-opensubdiv --backprojection-report
```

If the local install needs nonstandard flags, callers can provide
`OPENSUBDIV_CXXFLAGS`, `OPENSUBDIV_LDFLAGS`, or `CXX`. The script does not
modify the production Makefile and does not copy third-party source into the
repo.

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

   Partially proven. The regular lattice sample exposes 12 source ids and
   matching derivative weight counts. The original compact 11-control fixture
   reported only three source ids because its face list was not consistently
   oriented for OpenSubdiv manifold topology. An orientation-normalized fixture
   exposes nine original source ids with value, first-derivative, and
   second-derivative weights for the sampled ptex face. This proves more than
   the first probe, but it still does not prove an all-11 force
   back-projection contract. A later production lane would need a reviewed
   transpose/back-projection contract and force scatter ordering proof.

4. Can a regular case be compared against SLIMED's regular evaluator at
   quadrature-like sample points?

   Not completed in this lane. The probe uses SLIMED-like barycentric samples
   and records the provisional coordinate mapping, but numerical equivalence
   against `SlimedLoopLimitSurfaceEvaluator` must wait for a real OpenSubdiv
   install or an approved test-only dependency path.

5. Can the PR #45 11-control irregular fixture be represented at least as
   topology/source-id mapping?

   Partially proven. The installed run accepted the 11-control triangular
   topology and produced finite value and derivative vectors. With consistent
   face orientation, the selected samples report nine original-control source
   ids and derivative-complete weights. It did not prove stable all-11-control
   coverage for force back-projection because a single sampled ptex face did
   not include local fixture ids `8` and `10`.

## Next Review Gate

The next useful lane is review-gated:

```text
With an approved local OpenSubdiv install path, extend the observational
prototype or add a test-only executable that links against SLIMED's
SlimedLoopLimitSurfaceEvaluator to compare regular samples for position,
first derivatives, second derivatives, normals, area integrand, and legacy
volume integrand. Also revise the 11-control fixture sampling to aggregate
source coverage across the adjacent ptex faces or across the regular child
patches that match SLIMED's irregular subdivision route. The minimal missing
output is a per-sample and aggregate table of original-control ids, value
weights, first-derivative weights, and second-derivative weights, with explicit
pass/fail evidence for fixture ids 0 through 10. Do not change production
routing, force scatter, default Makefile targets, vendoring policy, or
dependency requirements in that lane.
```
