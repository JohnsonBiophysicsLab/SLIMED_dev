# OpenSubdiv Backend Decision For Irregular Patches

Decision date: 2026-06-23.
Baseline: `origin/main` at `ac0c0ab95871f2619fa96b8a8b6c8c1943b0344c`
after PR #45.

This is a docs-only decision record. It does not add OpenSubdiv, change build
files, change production C++ behavior, or fix irregular-patch energy/force
routing.

## Recommendation

OpenSubdiv is promising enough to justify a narrow prototype before SLIMED
implements production irregular-patch energy/force routing. The shortest safe
route is:

1. Build an observational OpenSubdiv proof of concept behind, or next to, the
   current `LimitSurfaceEvaluator` boundary.
2. Prove regular-patch equivalence against SLIMED's existing evaluator for the
   same Gauss samples, derivative rows, orientation, and force source indices.
3. Exercise the synthetic 11-control irregular fixture from
   `tests/test_surface_geometry_characterization.cpp` and verify that generated
   OpenSubdiv stencils can express value, first derivative, second derivative,
   and source-vertex mapping for the irregular face.
4. Only then choose between production backend adoption, a local 11-case force
   fix, or a loud unsupported-case rejection.

Do not expand local case-by-case irregular force code first unless the prototype
shows OpenSubdiv cannot supply a reviewable stencil/patch path for SLIMED's
Loop triangular meshes.

## Current SLIMED Facts

The existing regular limit-surface contract is explicit:

- `LimitSurfaceEvaluation` names position, two first derivatives, two pure
  second derivatives, and two mixed derivative rows.
- `SlimedLoopLimitSurfaceEvaluator` accepts only the regular 12-control patch
  used by `Face::oneRingVertices`.
- `Mesh::calculate_element_area_volume()` already separates regular 12-control
  faces from 11-control irregular faces. The irregular area/volume path applies
  `irregM`, evaluates three regular child patches through `irregM1`/`irregM2`/
  `irregM3`, then carries the remaining irregular child through `irregM4`.
- `Mesh::Compute_Energy_And_Force()` now mirrors the documented positive-depth
  11-control `4+3+4` split for membrane forces by building regular child
  patches, evaluating the regular force helper, and transposing child
  bending/area/volume force rows through the subdivision matrices.
- Zero-depth 11-control requests and unsupported irregular topologies are still
  rejected before the membrane force loop instead of calling
  `element_energy_force_regular(...)`.
- `element_energy_force_regular(...)` still loops over 12 shape-function
  columns when forming force contributions, so it must not be used directly as
  an 11-control fallback.

PR #45 added a deterministic 11-control geometry fixture and matrix-contract
checks. Later force-routing work adds the narrow subdivision-transpose
production path for that documented fixture shape, while broader valence and
OpenSubdiv-backed routing remain separate decisions.

## OpenSubdiv Evidence

Primary-source checks from the OpenSubdiv release branch support a prototype:

- OpenSubdiv targets high-performance subdivision evaluation on CPU/GPU for
  deforming surfaces with static topology. Its core libraries are C++ with no
  dependencies beyond the C++ standard library, while Osd CPU/GPU backends and
  example viewers have optional OpenMP, TBB, CUDA, OpenCL, OpenGL, Metal, Ptex,
  zlib, GLFW, and documentation dependencies.
- `Sdc::SchemeType` includes `SCHEME_LOOP`, and Loop uses triangle splitting.
- `Far::PatchTable::EvaluateBasis(...)` exposes position weights, first
  derivative weights, and second derivative weights at patch coordinates:
  `wP`, `wDu`, `wDv`, `wDuu`, `wDuv`, and `wDvv`.
- `Far::LimitStencil` and `Far::LimitStencilTable` expose equivalent value,
  first derivative, and second derivative stencil weights, with update helpers
  for values, first derivatives, and second derivatives.
- Boundary interpolation options exist, but they are subdivision-shape options,
  not replacements for SLIMED's fixed/free/periodic ghost policy.
- The license is the Tomorrow Open Source Technology License 1.0. It is derived
  from Apache 2.0 with a different trademark section; do not describe it as MIT.

Sources checked:

- https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/README.md
- https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/LICENSE.txt
- https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/sdc/types.h
- https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/sdc/options.h
- https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/far/patchTable.h
- https://github.com/PixarAnimationStudios/OpenSubdiv/blob/release/opensubdiv/far/stencilTable.h

## Decision Questions

### 1. Unified regular and irregular Loop values

OpenSubdiv can plausibly provide a unified Loop limit-surface value path for
SLIMED triangular meshes. The Far layer can build topology from control faces
and evaluate limit positions through patch tables or stencils. That is a better
fit than extending SLIMED's local 11-case subdivision matrices for each
additional irregular neighborhood by hand.

This is not proven for SLIMED until a prototype maps SLIMED face ordering,
Gauss samples, and boundary-expanded topology into OpenSubdiv and verifies
regular-patch equivalence.

### 2. Derivatives and force back-propagation

OpenSubdiv exposes the derivative quantities SLIMED needs: position, two first
derivatives, and three second derivative combinations. SLIMED currently carries
two mixed rows, `VW` and `WV`; an OpenSubdiv adapter can duplicate the single
`uv` result only after confirming parameter orientation and sign conventions.

Force back-propagation is plausible but not automatic. OpenSubdiv stencils give
linear weights from original control vertices to evaluated sample quantities.
For forces, SLIMED still needs a reviewed transpose/back-projection contract
that maps bending, area, and volume sample contributions back through value and
derivative weights to original vertex ids while preserving the existing scatter
order and OpenMP accumulation shape.

### 3. Regular versus irregular local geometry

If OpenSubdiv is adopted as a backend, regular and irregular local geometry
should be hidden behind `LimitSurfaceEvaluator` for sample evaluation. Callers
should ask for evaluated geometry rows plus source vertex ids/weights, not
switch on 12 versus 11 locally.

SLIMED should still keep explicit diagnostics and baselines for regular and
irregular fixtures. Boundary, ghost, periodic synchronization, scaffold timing,
volume semantics, and unsupported-topology rejection remain application policy
outside the backend.

### 4. Shortest safe route

Choose route B, with one caveat:

- B: OpenSubdiv prototype/backend seam first, then route irregular forces
  through it if the prototype succeeds.
- D is the interim production posture while irregular energy/force cases are
  reachable before the backend is ready: fail loudly instead of routing through
  the regular evaluator.

Route A, a local 11-case force fix now, is tempting because the bug is known.
It is not the shortest reviewable route unless the OpenSubdiv prototype fails:
it would require defining child-patch force back-projection and numerical
tolerances under the current local subdivision matrices, then might be replaced
immediately by a backend-level stencil path.

Route C, supporting only regular and the currently characterized 11 local case
without OpenSubdiv, is acceptable only as a fallback after the prototype shows
OpenSubdiv is not suitable for this repo.

### 5. Next proof of concept

The next lane should be a non-production prototype. It may live under a
scratch/example path or a guarded test-only target, but it should not alter the
default Makefile or production binaries until dependency policy is approved.

Concrete prototype prompt:

```text
Create an observational OpenSubdiv Loop prototype for SLIMED. Do not change
production C++ behavior or default builds. Build a tiny triangular control mesh
with one all-regular interior face and one valence-5/11-control irregular
fixture matching tests/test_surface_geometry_characterization.cpp. Construct a
Far::TopologyDescriptor from SLIMED vertex ids and triangular faces, create a
Loop TopologyRefiner, generate patch tables or limit stencils for SLIMED's
current Gauss samples, and emit for each sample: source vertex ids, position
weights, du/dv weights, duu/duv/dvv weights, evaluated position, first
derivatives, and second derivatives. Compare regular-face outputs against
SlimedLoopLimitSurfaceEvaluator for the same cached shape functions and record
max deltas for position, first derivatives, pure second derivatives, mixed
derivatives, normals, area integrand, and legacy volume integrand. For the
11-control fixture, verify finite values, stable source-id mapping to original
control vertices, and enough derivative weights to define a future
force-back-projection contract. Document parameter-coordinate mapping,
orientation/sign choices, boundary options, OpenSubdiv version, license, build
flags, and whether the prototype uses core Far only or any optional Osd backend.
```

Expected outputs:

- A text or JSON report of regular equivalence deltas.
- A source-index map from OpenSubdiv stencil entries back to SLIMED vertices.
- A table showing how SLIMED `v,w,u` samples map to OpenSubdiv `u,v` patch
  coordinates.
- An 11-control fixture report showing finite value/derivative evaluation and
  original-control back-projection support.
- A clear pass/fail recommendation for production backend adoption.

### 6. Dependency, licensing, and build risk

The current repo uses a Makefile and C++17. OpenSubdiv's core C++ baseline is
compatible with C++17, but this repo has no existing OpenSubdiv discovery,
vendoring, or package policy. Adding it would require an explicit dependency
PR.

Risks to resolve before production adoption:

- Whether to require a system OpenSubdiv install, vendor source, or keep the
  backend optional.
- Whether a core Far-only build can be linked without optional Osd graphics/GPU
  dependencies in the supported developer and CI environments.
- How to express discovery in the current Makefile without disrupting serial,
  OpenMP, dynamics, and test targets.
- How to record the Tomorrow Open Source Technology License 1.0 and its
  trademark caveat in repo licensing/docs.
- How to prevent optional OpenMP/TBB/CUDA/OpenCL/OpenGL/Metal/Ptex/GLFW/zlib
  dependencies from becoming accidental defaults.

### 7. Work to postpone for scientific review

Postpone these until the prototype and user/scientific review are complete:

- Production OpenSubdiv-backed irregular energy/force routing beyond the
  current dependency-free 11-control subdivision-matrix route.
- Force scatter/back-projection from OpenSubdiv backend stencils to original
  control vertices.
- Broader extraordinary-valence support beyond the characterized regular and
  11-control cases.
- Any change to formulas, quadrature order, force accumulation order, OpenMP
  reductions, RNG, output/checkpoint formats, propagation timing, optimizer
  timing, boundary/ghost/periodic semantics, or volume semantics.
- Vendoring, package-manager assumptions, or default build integration for
  OpenSubdiv.

## Follow-Up Decision Gate

After the prototype, decide one of:

- Adopt OpenSubdiv behind `LimitSurfaceEvaluator` for regular and broader
  irregular geometry, with backend force back-projection as the next reviewed
  production slice.
- Keep OpenSubdiv out and continue with the local 11-case route using the
  existing subdivision matrices, adding more validation or broader valence
  support only through separate review-gated PRs.
- Reject unsupported irregular energy/force cases loudly until one of the
  broader paths has numerical evidence.
