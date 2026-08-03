# Valence-3 Analysis and Implementation Plan

Date: 2026-08-03

Scope: analysis, staged plan, and proof-only Phase-1 start; no valence-3
production route is enabled by this document.

## Implementation status on 2026-08-03

The first guarded slice described below has now started:

- candidate-only canonical tetrahedron and closed mixed-valence 3/4/5
  fixtures are serialized under `data/fixtures/candidates/`;
- `OpenSubdiv_valence3_row_provider` generates double-precision, original-
  source-keyed rows only for the exact oriented tetrahedron, behind both
  `USE_OPENSUBDIV_VALENCE3` and an explicit request;
- an independent proof harness evaluates all original sources for both
  fixtures and sends the resulting seven-row samples through the existing
  `Mesh::element_energy_force_regular` algebra; and
- default-off behavior, topology/Ptex/sample identity, finite geometry and
  energy, and finite nonzero bending/area/volume force families are verified;
  bending and area are checked against their energy finite differences, while
  volume is checked against the full-divergence functional from which the
  existing force formula is derived.

With OpenSubdiv 3.7.0 at adaptive level 5 and the existing three-point rule,
the measured proof results were:

| Fixture | Limit area | Legacy volume | Bending energy | max `fBend` | max `fArea` | max `fVolume` |
|---|---:|---:|---:|---:|---:|---:|
| closed valence-3 tetrahedron | 0.3098636104909343 | 0.00585311414248918 | 1161.26192891631 | 161.055195154805 | 0.454400479884461 | 0.0406827885893523 |
| closed mixed 3/4/5 | 1.53823287240133 | 0.0551358786011809 | 1515.38896965707 | 207.205484212825 | 1.51319522792981 | 0.196180394783752 |

These values are diagnostic observations, not reviewed scientific baselines.
The mixed fixture deliberately exercises faces whose endpoint valences are
3/4/5, but it is not accepted by the narrow tetrahedron provider and does not
enable a composed production route. Quadrature convergence, finite-difference
force validation, scientific approval, a unified per-face dispatcher, and
atomic production publication remain future gates.

The finite-difference pass also exposed a pre-existing scientific mismatch
that blocks activation: the current variable-cardinality geometry path
intentionally preserves SLIMED's legacy x-only volume accumulator, whereas
`element_energy_force_regular` differentiates the full-divergence volume
functional. Bending, area, and the force-conjugate full-divergence volume all
matched their numerical gradients within the reviewed `2e-4` relative/scale
tolerance, but the volume force differed from the published legacy-volume
energy gradient by about `0.0407` on the tetrahedron and `0.592` on the mixed
fixture. The proof locks in observation of this discrepancy; Phase 2 must
choose and consistently apply one volume functional rather than hiding it by
widening a tolerance.

Reviewer hardening added after the first packet binds the provider at compile
time to `OPENSUBDIV_VERSION_NUMBER == 30700`, checks adaptive isolation levels
4/5/6 for convergent row sensitivity, evaluates both regular and asymmetrically
perturbed tetrahedron coordinates, runs two finite-difference step sizes,
validates every returned face normal, and exercises default-off, missing-
request, reversed-topology, and mixed-topology rejection contracts. The mixed
fixture now reports the canonical provider as not applicable and separately
proves rejection. A dedicated GitHub Actions job builds stock OpenSubdiv 3.7.0
CPU-only and runs the dependency-disabled and enabled proofs.

The first Phase-2 continuation is recorded in
`docs/irregular_valence3_phase2_mechanical_packet.md`. The real OpenSubdiv
rows now pass per-sample and stacked transpose identities, canonical
source-keyed preparation, production-shaped scatter, and repeated ascending
1/2/4-buffer reductions. True net-force and net-torque checks replace the
earlier aggregate-magnitude diagnostic: both exact tetrahedron coordinate
sets pass, while the non-provider-applicable mixed 3/4/5 characterization
exposes a roughly `5.20e-3` volume-force translation residual. That mixed
residual is preserved as a dispatcher/physics blocker rather than hidden by
a wider tolerance. The independent oracle, full energy-channel packet,
covariance/scale studies, nested quadrature study, and scientific baseline
decision remain open, so Phase 3 is still blocked.

Phase 3 subsequently started as a guarded integration-only transaction under
the explicit continuation direction. Its accepted scope is stock OpenSubdiv
3.7.0, isolation level 5, the exact tetrahedron, and the existing ordered
three-point rule for bending and area. Because no volume-functional decision
has been accepted, the transaction requires `uVol == 0` and atomically rejects
nonzero volume constraints. It validates and executes the shared source-keyed
production face loop behind `SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3=1`, but it
does not install a default caller or authorize Phase 4. See
`docs/irregular_valence3_opensubdiv_face_loop.md`.

## Executive Recommendation

Implement valence 3 as a new, canonical-tetrahedron, source-keyed OpenSubdiv
lane. Reuse the backend-neutral row, force-algebra, scatter, and atomic
publication seams already proven by the valence-4 and valence-5 routes. Do not
extend `Face::oneRingVertices`, do not add a regular 12-control fallback, and
do not treat either the valence-4 activation or the valence-5 scientific
decision as automatic approval of valence-3 physics.

The recommended starting semantics are stock OpenSubdiv Loop subdivision,
but only as a **candidate scientific baseline**. Valence 3 has no existing
SLIMED production evaluator to preserve or match. Its stock Loop smooth-vertex
mask also differs more strongly from SLIMED's historical `3/(8n)` convention
than the already material valence-5 difference. In addition, every vertex of
the canonical tetrahedron is extraordinary, so the bending-energy path needs
an explicit quadrature- and curvature-convergence decision before production
activation.

The implementation should therefore follow the valence-5 three-phase shape,
preceded by a valence-3-specific scientific phase:

1. approve and serialize a canonical tetrahedron fixture;
2. generate and prove stock OpenSubdiv rows without production mutation;
3. establish force, energy, geometry, curvature, and quadrature evidence and
   explicitly select a scientific baseline;
4. integrate that accepted baseline through the shared guarded face loop; and
5. activate it behind independent build and runtime gates in a separate change.

Unsetting a future valence-3 runtime gate is a rollback to today's fail-loud
unsupported-topology behavior. It is **not** a rollback to a working legacy
valence-3 force implementation, because none exists.

## Evidence Used

This plan is grounded in the following repository evidence:

- `docs/irregular_broader_valence_inventory.md` identifies the closed
  tetrahedron as four `3/3/3` faces with empty production one-rings and a
  fail-loud diagnostic before geometry or force mutation.
- `docs/opensubdiv_observational_prototype.md` reports derivative-complete
  source visibility for a synthetic valence-3 fan, but explicitly limits that
  evidence to aggregate feasibility rather than physics or routing.
- `docs/irregular_valence4_opensubdiv_mapping_proof.md` and the valence-4
  provider establish the exact Ptex/sample/source-ID/transpose pattern for a
  closed all-extraordinary topology with empty one-rings.
- `docs/irregular_valence4_opensubdiv_production_caller.md` establishes the
  guarded variable-cardinality production transaction and source-keyed
  scatter path.
- `docs/irregular_valence5_opensubdiv_integration_composition.md` proves that
  matching topology and child-domain coordinates does not imply matching
  subdivision semantics when extraordinary masks differ.
- `docs/irregular_valence5_option_b_energy_geometry_rebaseline.md` and the
  Phase 1 through Phase 3 documents establish the independent-oracle,
  scientific-rebaseline, atomic integration, activation, output, restart,
  serial/OpenMP, and rollback sequence.
- `docs/opensubdiv_mapping_contract.md` and
  `docs/opensubdiv_backend_interface_policy.md` remain the governing backend
  contract: seven SLIMED rows, original source IDs, explicit sample identity,
  transpose through actual force formulas, default dependency isolation, and
  fail-loud unsupported behavior.

Primary external references are listed at the end of this document.

## Geometry and Topology Analysis

### Canonical closed fixture

The narrow first fixture should be a regular tetrahedron, not a general
"contains a valence-3 vertex" mesh. A proposed unit-circumradius
serialization is:

```text
r = 1/sqrt(3)

vertex 0 = (-r, -r, -r)
vertex 1 = (-r,  r,  r)
vertex 2 = ( r, -r,  r)
vertex 3 = ( r,  r, -r)

outward faces =
  (0, 2, 1)
  (0, 1, 3)
  (0, 3, 2)
  (1, 2, 3)
```

The fixture contract should independently prove:

| Property | Expected value |
| --- | ---: |
| vertices / edges / faces | `4 / 6 / 4` |
| Euler characteristic | `4 - 6 + 4 = 2` |
| incidence per edge | exactly `2`, oppositely directed |
| vertex valence | `3` at all four vertices |
| face valence triplet | `3/3/3` on all four faces |
| circumradius | `1` |
| edge length | `2*sqrt(2/3)` |
| one straight-sided face area | `2*sqrt(3)/3` |
| total straight-sided area | `8*sqrt(3)/3` |
| straight-sided signed volume | `8/(9*sqrt(3))` |

These are input-polyhedron checks only. They are not expected limit-surface or
SLIMED membrane outputs.

The initial packet should live under
`data/fixtures/candidates/closed_valence3_tetrahedron` and remain
`scientifically_approved:false` until the scientific phase is complete.

### What changes after subdivision

All four coarse tetrahedron vertices remain valence-3 extraordinary vertices.
The six edge vertices created by the first Loop refinement have valence 4;
additional refinement produces regular valence-6 vertices away from the four
persistent extraordinary points. Every coarse face is incident on three
extraordinary corners. This is more concentrated than a typical isolated
extraordinary-vertex test and makes a coarse three-sample bending integral a
scientific assumption that must be tested, not merely copied from valence 4
or 5.

### Proposed face/source contract

For the canonical tetrahedron:

- Ptex face ID must equal the stable SLIMED face index `0..3`;
- the ordered quadrature samples initially remain the current `N=2` plan;
- the coordinate convention remains `OpenSubdiv s=v, t=w`, with
  `u=1-v-w`;
- every dense public row is keyed by original SLIMED source IDs
  `[0,1,2,3]`;
- missing backend entries may be represented as exact zero coefficients, but
  no row may reference a source outside `0..3`;
- value-row coefficients must sum to `1` and all derivative rows to `0`
  within `1e-12`;
- `duv` must populate both SLIMED mixed rows, which must be identical; and
- `Face::oneRingVertices` must remain empty and be explicitly bypassed.

The expected provider tensor is therefore:

```text
4 faces x 3 samples x 7 derivative rows x 4 original sources
```

This expected support must be measured with OpenSubdiv 3.7.0 before it is
frozen. The older synthetic valence-3 fan result is encouraging, but it is not
evidence for tetrahedron face identity or exact four-source rows.

## Loop Mask and Surface Analysis

For a smooth interior vertex of valence `n`, the stock Loop even-vertex
neighbor weight is

```text
beta(n) = (1/n) * [5/8 - (3/8 + (1/4)cos(2*pi/n))^2]
center(n) = 1 - n*beta(n)
```

SLIMED's existing irregular subdivision matrix instead hard-codes the simpler
`3/(8n)` convention for its valence-5 row and `n=6` regular rows. It is not a
general valence-3 evaluator. The comparison is:

| valence | stock Loop neighbor | stock center | `3/(8n)` neighbor | historical center |
| ---: | ---: | ---: | ---: | ---: |
| 3 | `3/16 = 0.1875` | `7/16 = 0.4375` | `1/8 = 0.125` | `5/8 = 0.625` |
| 4 | `31/256 = 0.12109375` | `33/64 = 0.515625` | `3/32 = 0.09375` | `5/8 = 0.625` |
| 5 | `0.08409321892578289` | `0.5795339053710855` | `0.075` | `0.625` |
| 6 | `1/16 = 0.0625` | `5/8 = 0.625` | `1/16 = 0.0625` | `5/8 = 0.625` |

The valence-3 stock/historical-style difference is substantial: `+1/16` per
neighbor and `-3/16` at the center. The valence-5 work already demonstrated
that a smaller mask difference coincided with material row, force, energy,
and geometry changes, without proving sole-mask causality. Therefore:

- stock OpenSubdiv output must not be labeled parity with a hypothetical
  SLIMED valence-3 route;
- `3/(8n)` may be evaluated only as a sensitivity counterfactual, not as a
  current baseline;
- post-hoc editing of OpenSubdiv rows is forbidden; and
- choosing stock, a custom evaluator, or continued unsupported behavior is a
  scientific/architecture decision, not a tolerance decision.

Loop surfaces are regular away from extraordinary points but have weaker
smoothness and potentially problematic curvature behavior at extraordinary
points. SLIMED's membrane force uses first and second parametric derivatives,
mean curvature, and bending energy. The three current quadrature samples lie
strictly inside each coarse face, so they do not request derivatives at the
extraordinary vertices themselves. That avoids the singular point but does
not prove that three samples resolve the integral near all twelve
face-corner incidences of the tetrahedron.

## Recommended Architecture

### Reuse

Reuse these existing components unchanged wherever possible:

- `SourceKeyedFaceRows` and `prepare_source_keyed_kernel_call()`;
- variable-cardinality explicit shape-function overrides in
  `Mesh::element_energy_force_regular()`;
- `Guarded_source_keyed_production_face_loop` validation and execution;
- production-shaped `sourceCount * 9` thread-local buffers and ascending
  thread-index reduction;
- current bending, area, legacy-volume, regularization, total-force,
  total-energy, boundary, output, and checkpoint behavior; and
- the valence-5 independent long-double replay pattern.

### Keep valence-specific

Keep these responsibilities in a valence-3 wrapper/provider:

- exact four-vertex/four-face topology and orientation;
- Ptex identity and exact source coverage;
- the scientific baseline and its expected values;
- valence-3 build/runtime gates and structured diagnostics; and
- the fixture-specific sample or refined-subface integration plan.

### Avoid

Do not:

- populate, clear, reorder, or consume `Face::oneRingVertices`;
- generalize `get_subdivision_matrices()` by changing its existing valence-5
  semantics in the first valence-3 changes;
- pad four sources to 11 or 12 local slots;
- silently select OpenSubdiv because it is installed;
- copy OpenSubdiv patch-control indices into public force code;
- activate mixed valence or arbitrary valence-3 neighborhoods; or
- widen valence-4/5 tolerances to accommodate valence 3.

## Staged Implementation Plan

### Phase 0 — fixture, mask, and quadrature decision evidence

Deliverables:

1. Add the candidate fixture and metadata with exact topology, orientation,
   Euclidean geometry, hashes, and approval flags.
2. Extend the broader-valence inventory to bind the serialized candidate to
   today's empty-one-ring, fail-before-mutation behavior.
3. Add an opt-in OpenSubdiv probe for all four tetrahedron Ptex faces using:
   - the current ordered three-sample plan;
   - a denser nine-point characterization grid; and
   - nested affine subtriangle quadrature at increasing depths.
4. Report double-precision value, first-derivative, and second-derivative rows,
   source unions, row sums, row `L1` norms, maximum absolute coefficients,
   Ptex identity, and isolation-depth stability.
5. Implement an independent standard-Loop uniform-refinement oracle for limit
   positions and integral convergence. It must implement the published stock
   vertex and edge rules without calling OpenSubdiv or SLIMED's production
   evaluator.
6. Report the `3/(8n)` result only as a clearly labeled mask-sensitivity
   experiment.

Scientific gates:

- all samples and rows are finite and deterministic;
- source IDs never escape `0..3`;
- row invariants and duplicate mixed-row identity pass;
- OpenSubdiv row/position results are stable across reviewed adaptive
  isolation levels;
- area, legacy volume, mean-curvature integral, bending energy, and their
  source gradients are characterized under nested subtriangle refinement; and
- the team explicitly decides whether the production candidate remains the
  current `N=2` plan, uses a refined valence-3-specific integration plan, or
  stays unsupported.

Proposed convergence policy for the initial study is a relative change below
`1e-6` in global area, volume, and energy and below `1e-5` in force components
over two successive refinement depths. These are study targets, not approved
tolerances. The final non-overridable thresholds must be frozen from measured
evidence and scientific review. Failure to converge blocks Phase 1 from being
described as a physical implementation, though a mechanical row proof may
continue.

### Phase 1 — guarded valence-3 row provider

Proposed files:

```text
include/mesh/Valence3_topology_source_mapping.hpp
src/mesh/Valence3_topology_source_mapping.cpp
include/mesh/OpenSubdiv_valence3_row_provider.hpp
src/mesh/OpenSubdiv_valence3_row_provider.cpp
experiments/irregular_valence3_opensubdiv_row_provider.cpp
scripts/run_irregular_valence3_opensubdiv_row_provider.py
scripts/run_irregular_valence3_opensubdiv_row_provider.sh
tests/test_irregular_valence3_opensubdiv_row_provider_inventory.py
docs/irregular_valence3_opensubdiv_row_provider.md
```

Build contract:

- add `USE_OPENSUBDIV_VALENCE3=1`;
- require `OPENSUBDIV_ROOT` when it is enabled;
- link only the existing required OpenSubdiv CPU/Far library surface;
- keep all default targets OpenSubdiv-free; and
- record and bind the tested OpenSubdiv version, initially 3.7.0. A changed
  version requires requalification rather than silently inheriting expected
  rows.

Provider contract:

- require an explicit caller request;
- accept only the exact candidate topology, stable IDs, outward orientation,
  closed manifold state, physical faces, valence `3`, and empty one-rings;
- use `Sdc::SCHEME_LOOP` with the reviewed closed-mesh options;
- generate `LimitStencilTableFactoryReal<double>` value, first-, and
  second-derivative weights;
- use `PatchMap`/`PatchTable` to verify Ptex identity, not as a substitute for
  the authoritative source-keyed limit rows;
- emit caller-owned `4 x sampleCount x 7 x 4` rows keyed by original source
  ID;
- validate finite coefficients, constant-field invariants, sample ordering,
  source bounds, and mixed-row duplication before returning any rows; and
- never evaluate forces, mutate mesh state, populate one-rings, or enable a
  production route.

Negative tests must cover face order, winding, vertex/face identity, valence,
source count, boundary/ghost flags, non-manifold edges, nonempty one-rings,
sample drift, missing derivatives, nonfinite rows, dependency absence, and a
missing explicit request.

### Phase 2 — mechanical transpose and scientific baseline packet

This phase should remain proof-only and should not install a default caller.

Mechanical evidence:

1. Prove per-sample and stacked
   `g dot (W p) == (W^T g) dot p` with asymmetric controls and gradients.
2. Invoke the existing `Mesh::element_energy_force_regular()` scientific
   algebra with explicit `7 x 4` rows.
3. Compare source-keyed `fBend`, `fArea`, and `fVolume` with an independent
   replay, per face/source/family/axis so cancellation cannot hide errors.
4. Prove source-keyed scatter into the existing four-source `nVertices * 9`
   buffer and ascending-buffer reduction.

Scientific evidence must use both the exactly symmetric regular tetrahedron
and a fixed asymmetric coordinate perturbation. It must include:

- all ten global energy channels and all per-face energy channels;
- per-face normal, area, legacy volume, and mean curvature;
- all current per-vertex force families;
- candidate-versus-independent-oracle agreement;
- central finite differences of total energy against analytic forces over
  multiple step sizes;
- zero net internal force and zero net torque checks when the enabled energy
  terms are translation/rotation invariant;
- rotation and translation covariance;
- scale laws for area, volume, curvature, energy, and force;
- equal face observables and symmetry-related force vectors for the unperturbed
  tetrahedron;
- nested quadrature convergence and sensitivity to OpenSubdiv adaptive
  isolation depth;
- serial/OpenMP runs at fixed thread counts `1`, `2`, and `4` with repeats;
- output CSV visibility and V1/V2 checkpoint compatibility; and
- dependency-present, dependency-absent, and unsupported-topology behavior.

Use a separate long-double oracle package as in valence 5. It should consume
serialized rows, coordinates, parameters, and regularization inputs and must
not call `element_energy_force_regular()` or share the candidate's aggregation
helpers.

Phase 2 ends with an explicit decision record choosing one of:

1. accept stock OpenSubdiv with the existing three-point plan;
2. accept stock OpenSubdiv with a valence-3-specific refined integration plan;
3. authorize a separately maintained custom evaluator/mask investigation; or
4. keep valence 3 unsupported.

The evidence packet may recommend an option, but it must not infer approval.
Stock semantics are not scientifically approved until the decision is
recorded.

### Phase 3 — guarded source-keyed face-loop integration

Only after a Phase 2 baseline is explicitly accepted, add:

```text
include/energy_force/Valence3_opensubdiv_face_loop.hpp
src/energy_force/Valence3_opensubdiv_face_loop.cpp
experiments/irregular_valence3_opensubdiv_face_loop.cpp
scripts/run_irregular_valence3_opensubdiv_face_loop.py
scripts/run_irregular_valence3_opensubdiv_face_loop.sh
tests/test_irregular_valence3_opensubdiv_face_loop_inventory.py
docs/irregular_valence3_opensubdiv_face_loop.md
```

Use an integration-only gate such as:

```text
SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE2=1
```

The transaction must validate, before its first mesh write:

- the exact accepted topology, sample plan, weights, source rows, and
  scientific baseline identity;
- finite current coordinates and every production destination;
- staged per-face area and legacy volume plus global totals;
- a complete scientific dry run; and
- the complete four-source scatter package.

It should then call the shared guarded source-keyed production face loop,
publish the existing completion phases, and compare postconditions with the
dry run under a fixed non-overridable tolerance. Ordinary input rejection must
remain atomic. A post-execution invariant failure is a hard runtime error.

Avoid cloning the complete valence-5 transaction. Extract only genuinely
topology-independent quadrature validation, geometry staging, dry-run, and
postcondition helpers after golden tests prove valence-5 behavior unchanged.
Keep topology/provider/scientific policy in thin valence-specific wrappers.
If that extraction would broaden the change, use the existing shared
`Guarded_source_keyed_production_face_loop` directly and defer refactoring.

Phase 3 must still report:

```text
production_route_enabled: false
default_evaluator_caller: false
production_one_rings_populated: false
```

### Phase 4 — explicit production activation

Activation is a separate reviewed change. Add the exact-token runtime gate:

```text
SLIMED_USE_OPENSUBDIV_VALENCE3=1
```

Update `Mesh::Compute_Energy_And_Force()` so it counts all requested
extraordinary routes (valence 3, 4, and 5) and rejects when the count exceeds
one. Do this before any geometry or force mutation. A small route-selection
enum/helper is preferable to growing pairwise conflict checks.

Required activation behavior:

- gate absent: tetrahedron retains today's unsupported-topology diagnostic;
- gate present, dependency-disabled build: reject before mutation;
- gate present, exact approved tetrahedron: execute the reviewed Phase 3
  transaction;
- gate present, topology/sample/version/baseline drift: reject before
  mutation;
- simultaneous extraordinary gates: reject before mutation; and
- regular, valence-4, valence-5, boundary, ghost, periodic, checkpoint,
  propagation, and output behavior remain unchanged.

Because simulations call the evaluator repeatedly while topology is static,
activation must include a benchmark. If refiner/patch/stencil construction is
material, cache an immutable source-keyed row package by a collision-safe key
containing topology, orientation, sample plan, scheme/options, and
OpenSubdiv-version identity. Coordinates must not be part of the row cache.
Cache insertion must occur only after complete validation, and cache hits must
not weaken route preflight.

Activation requires explicit user/scientific approval after the full default
and OpenSubdiv-enabled serial/OpenMP suites pass.

### Phase 5 — broader valence-3 topology (out of scope)

The canonical tetrahedron route must not imply support for:

- a single valence-3 vertex in an otherwise regular mesh;
- mixed face triplets such as `3/4/4`;
- boundaries, creases, non-manifold vertices, holes, or ghost-expanded fans;
- arbitrary face/source counts; or
- a generic "all OpenSubdiv topologies" route.

Those cases need their own representative fixtures, sample/source support,
curvature behavior, scientific outputs, and route policy. Only after at least
two non-isomorphic approved topologies should a generic topology-driven
provider be considered.

## Verification Matrix

| Layer | Required checks |
| --- | --- |
| default build | no OpenSubdiv required; existing tests pass; tetrahedron still fails before mutation |
| opt-in build | `USE_OPENSUBDIV_VALENCE3=1` requires `OPENSUBDIV_ROOT`; tested version recorded |
| fixture | exact hashes, topology, outward winding, Euclidean values, deterministic setup |
| provider | `4 x samples x 7 x 4`, finite double rows, invariants, Ptex IDs, exact source bounds |
| mapping | original IDs only, deterministic aggregation, no one-ring mutation |
| transpose | per-row, per-sample, per-face, and stacked identities |
| force algebra | independent per-source `fBend/fArea/fVolume` replay and finite differences |
| geometry | area, volume, normals, mean curvature, symmetry, rigid/scale laws |
| integration | nested quadrature and adaptive-isolation convergence |
| transaction | complete preflight before first write; dry-run/postcondition agreement |
| parallel | serial/OpenMP `1/2/4` threads, repeats, fixed reduction policy |
| persistence | ten-channel CSVs and V1/V2 restart behavior unchanged |
| routing | exact-token gates, absence, wrong tokens, dependency absence, conflicts, rollback |
| regression | regular, valence-4, valence-5, boundary/ghost/periodic, CUDA unsupported-route policy |

Mechanical tolerances should begin with the existing policies (`1e-12` for
row invariants and transpose identities; `1e-10` for production dry-run,
oracle, and serial/OpenMP comparisons). Scientific envelopes for fixed
expected valence-3 outputs must be derived from multi-platform evidence and
then frozen per scope. No production or proof runner should expose a CLI
tolerance that can clear a blocker.

## Exit Criteria

Valence 3 is implementation-complete only when all of the following are true:

1. the tetrahedron is an explicitly approved scientific fixture;
2. the exact sample/integration plan and stock/custom mask semantics are
   explicitly selected;
3. the row provider, source mapping, force transpose, independent oracle,
   finite-difference, convergence, serial/OpenMP, output, and restart gates
   pass;
4. the guarded transaction rejects all ordinary invalid inputs before the
   first mutation;
5. the default dependency-free build and all existing routes are unchanged;
6. the production gate is exact-token, conflict-safe, and fully reversible;
7. rollback behavior is documented truthfully as restoration of the current
   unsupported diagnostic; and
8. activation has separate reviewer and user/scientific approval.

Until then, the correct production state is:

```text
valence3_scientifically_approved: false
valence3_implementation_authorized: false
valence3_production_route_enabled: false
current_fail_loud_behavior_preserved: true
```

## External References

- Charles Loop, [Smooth Subdivision Surfaces Based on
  Triangles](https://www.microsoft.com/en-us/research/publication/smooth-subdivision-surfaces-based-on-triangles/),
  M.S. thesis, 1987.
- Jos Stam, [Evaluation of Loop Subdivision
  Surfaces](https://research.cs.wisc.edu/graphics/Courses/559-f2001/Papers/559-Papers/Stam-Loop.pdf).
- I. Ginkel and G. Umlauf, [Loop Subdivision with Curvature
  Control](https://diglib.eg.org/items/f95255f4-638f-4783-952f-32544000f064),
  SGP 2006. This is the basis for treating extraordinary-point curvature as
  a separate scientific risk rather than assuming that finite sampled second
  derivatives settle bending-integral behavior.
- OpenSubdiv 3.7.0, [Sdc Overview](https://opensubdiv.org/docs/sdc_overview.html):
  supported schemes, mask ownership, and the intentionally closed scheme
  customization surface.
- OpenSubdiv 3.7.0, [Far Overview](https://opensubdiv.org/docs/far_overview.html):
  topology refinement, Ptex/sample identity, factorized limit stencils, and
  analytical derivative weights.
- OpenSubdiv 3.7.0, [LimitStencilTable API](https://opensubdiv.org/docs/doxy_html/a01072.html):
  value, first-derivative, and second-derivative stencil storage.
- OpenSubdiv 3.4 release notes, [Triangular Patches for Loop Subdivision and
  Double Precision in Far](https://opensubdiv.org/docs/release_34.html).
- OpenSubdiv 3.7.0 source,
  [`sdc/loopScheme.h`](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/v3_7_0/opensubdiv/sdc/loopScheme.h),
  for the implementation-bound stock Loop masks used by the tested provider.
