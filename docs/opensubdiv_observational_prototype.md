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
   matching derivative weight counts. The 11-control fixture topology is
   accepted, but the selected sample reports only three source ids, so this
   does not yet prove an irregular force back-projection contract. A later
   production lane would still need a reviewed transpose/back-projection
   contract and force scatter ordering proof.

4. Can a regular case be compared against SLIMED's regular evaluator at
   quadrature-like sample points?

   Not completed in this lane. The probe uses SLIMED-like barycentric samples
   and records the provisional coordinate mapping, but numerical equivalence
   against `SlimedLoopLimitSurfaceEvaluator` must wait for a real OpenSubdiv
   install or an approved test-only dependency path.

5. Can the PR #45 11-control irregular fixture be represented at least as
   topology/source-id mapping?

   Partially proven. The installed run accepted the 11-control triangular
   topology and produced finite value and derivative vectors. It did not prove
   a stable all-11-control source stencil for force back-projection because the
   selected samples reported only three source ids.

## Next Review Gate

The next useful lane is review-gated:

```text
With an approved local OpenSubdiv install path, extend the observational
prototype or add a test-only executable that links against SLIMED's
SlimedLoopLimitSurfaceEvaluator to compare regular samples for position,
first derivatives, second derivatives, normals, area integrand, and legacy
volume integrand. Also revise the 11-control fixture sampling so it can prove
whether OpenSubdiv can expose original-control source ids and weights for all
controls needed by a future force back-projection contract. Do not change
production routing, force scatter, default Makefile targets, vendoring policy,
or dependency requirements in that lane.
```
