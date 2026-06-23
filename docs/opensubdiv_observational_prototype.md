# OpenSubdiv Observational Prototype Lane

Date: 2026-06-23.
Baseline: `origin/main` at `ea50f7504bde35fab5eaebd9996e028dbeef8df9`
after PR #46.

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
build integration all require a separate dependency-policy review, this lane
adds only an inert opt-in probe script.

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
- emits source control-vertex ids and weight counts for each sample; and
- evaluates finite position, first derivative, and second derivative vectors
  from the stencil weights.

The probe uses a provisional SLIMED-to-OpenSubdiv coordinate mapping of
`s=w, t=v`. That mapping is reported in the output and remains unproven until
an installed OpenSubdiv run can be compared against SLIMED's regular evaluator.

Example absent-dependency command:

```bash
python3 scripts/probe_opensubdiv_feasibility.py --json
```

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

   Not proven locally because OpenSubdiv is absent. The opt-in probe now
   contains the exact topology-descriptor construction for a triangular lattice
   and the PR #45 source-id fixture.

2. Can OpenSubdiv generate/evaluate limit stencils or patch-table basis values
   with first/second derivative weights?

   Not proven locally. The probe requests `LimitStencilTable` position,
   `du`/`dv`, and `duu`/`duv`/`dvv` weights and fails loudly if any derivative
   array is missing in an installed environment.

3. Can prototype code expose source control-vertex indices/weights clearly
   enough to support force back-projection later?

   Not proven locally. The probe prints source ids and weight counts for every
   evaluated sample when OpenSubdiv is present. A later production lane would
   still need a reviewed transpose/back-projection contract and force scatter
   ordering proof.

4. Can a regular case be compared against SLIMED's regular evaluator at
   quadrature-like sample points?

   Not completed in this lane. The probe uses SLIMED-like barycentric samples
   and records the provisional coordinate mapping, but numerical equivalence
   against `SlimedLoopLimitSurfaceEvaluator` must wait for a real OpenSubdiv
   install or an approved test-only dependency path.

5. Can the PR #45 11-control irregular fixture be represented at least as
   topology/source-id mapping?

   Partially prepared but not proven locally. The probe carries the same 11
   source ids and synthetic coordinates from
   `tests/test_surface_geometry_characterization.cpp`; an installed run must
   still verify OpenSubdiv's accepted topology, finite derivative values, and
   stable original-control stencil ids.

## Next Review Gate

The next useful lane is still dependency-gated:

```text
With an approved local OpenSubdiv install path, run
scripts/probe_opensubdiv_feasibility.py using OPENSUBDIV_ROOT and capture the
regular and 11-control fixture stencil reports. If the probe passes, extend it
or add a test-only executable that links against SLIMED's
SlimedLoopLimitSurfaceEvaluator to compare regular samples for position,
first derivatives, second derivatives, normals, area integrand, and legacy
volume integrand. Do not change production routing, force scatter, default
Makefile targets, vendoring policy, or dependency requirements in that lane.
```
