# Irregular Loop architecture reassessment

Implementation control note (2026-08-05): the preliminary, non-authorizing
decision statuses and current-main baseline are now recorded in
[`adr_unified_loop_backend.md`](adr_unified_loop_backend.md). Recommendations
in this reassessment do not decide D0/D1/D2/D2b/D5/D8. D3/D4 remain pending
WP2.1, independent scientific review, and explicit user decisions. D6/D7
only restate existing policy/instruction. The ADR authority column and
unified implementation plan control subsequent work.

## Evidence scope

This reassessment was originally performed on a two-PR working stack: PR 176
at `46c06080fb663bcb43f38cf32fc1b45daa8732e8` is the production-code root and
PR 182 at `9587e3dce4509029e611e2937bac570b410193c3` is its evidence-only leaf.
Neither is current production `main`. The original WP0.1 baseline was
`origin/main@906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a`; this external-review
amendment is based on merged PR 183 at
`origin/main@e9af3ddad494fc073040ee82bdf07944b9fee8cf`.

Current `main` contains the earlier proof-only Valence-3 row provider but not
the later Valence-3 production face loop, asymmetric bipyramid fixture, or
Phase-5 convergence document. Those are unmerged stack evidence and are
labeled as such below. No unmerged fact should be treated as current-main
production behavior.

PR 182's convergence evidence covers only its symmetric and asymmetric
`3/4/4` triangular bipyramids under OpenSubdiv 3.7.0, isolation level 5,
nested depths 0 through 4, fixed parameters, and recorded activation targets.
No conclusion is drawn for other topologies, deeper levels, or other rules.

## Executive conclusion

The current Valence-3/4/5 work should stop at its present proof boundary. The
next production implementation should **not** add another topology-specific
provider, extend the tetrahedron transaction one fixture at a time, or make
the three existing routes more alike. The best target is one topology-driven
Loop limit-surface backend for an entire closed triangular mesh, with one
source-keyed face kernel and one energy/volume functional.

Valence remains an important topological property and test dimension, but it
should not be a production dispatch key. OpenSubdiv's Loop implementation
already computes masks from the local topological neighborhood; its
`TopologyRefiner` represents arbitrary refined topology, and limit stencils
map requested face locations directly back to coarse control vertices. The
appropriate abstraction is therefore "Loop rows for this mesh topology and
sample plan," not "the Valence-3 evaluator" or "the Valence-5 evaluator."

Proposed D0 disposition, pending explicit user decision: treat PR 176/182 as
one stack. Do not merge the PR 176 production root merely by merging or closing
the PR 182 evidence leaf. Preserve the leaf's useful negative convergence
result and fixtures, then choose explicitly among preserving the stack as
evidence, extracting selected evidence, or superseding it with the generic
backend described here. PR 182 cannot reach `main` independently.

## What the negative review gets right

| Finding | Assessment | Consequence |
| --- | --- | --- |
| The legacy 11-control matrix and its dispatch guard describe different topology classes. | **Confirmed, critical.** `set_one_ring_vertices_sorted()` admits a face only when all three corners have valence 5, while `get_subdivision_matrices()` applies one valence-5 mask and two valence-6 masks. | The legacy all-valence-5 path is not a valid implementation of its own stated one-extraordinary-corner patch. D5 proposes quarantine rather than generalization; implementation awaits an explicit user decision. |
| The icosahedron's 11 slots contain only 9 distinct source vertices. | **Confirmed for the approved fixture.** The repository asserts this aliasing. | This is further evidence that the 11-control legacy representation is being used outside its intended topology. Duplicate source aggregation can be mathematically represented, but it does not make this subdivision matrix correct. |
| The legacy Warren-style mask and stock OpenSubdiv Loop mask differ materially. | **Confirmed, with a regular-valence qualification.** At `N=6`, the historical `3/(8N)` rule and stock Loop both give neighbor weight `1/16` and center weight `5/8`; the checked-in `data/example` physical regular faces therefore do not require a mask rebaseline. No claim is made for arbitrary production inputs. | There is no meaningful general extraordinary "parity fix" available through stock OpenSubdiv options. The project must choose a scheme. Periodic ghost-band scope remains a separate D2b decision. |
| The unmerged Valence-3 stack uses exact-`1/6` full-divergence volume while current-main regular, Valence 4, Valence 5, and CUDA use the legacy x-only literal `0.16666666666`. | **Confirmed, critical across the proposed stack.** The force algebra differentiates the full divergence functional. | Merging the stack unchanged would make geometry, volume energy, and volume force nonuniform across routes. This must be resolved globally before a mixed-valence route can be scientifically valid. |
| The OpenSubdiv routes are exact whole-mesh fixture routes, not general irregular handling. | **Confirmed with ancestry qualification.** Current-main Valence 4 requires the canonical octahedron and Valence 5 the canonical icosahedron; the unmerged Valence-3 production stack requires the four-source tetrahedron. The stacked top-level evaluator forbids simultaneous extraordinary routes. | A mixed 3/4/5 mesh and even most single-extraordinary-vertex meshes remain unsupported. Passing the Platonic fixtures proves row and transaction mechanics, not general topology support. |
| Valence 4 and 5 rebuild OpenSubdiv topology/stencil objects, and production transactions retain proof-style duplication. | **Confirmed in substance.** Only the Valence-3 provider has an immutable topology row cache. Valence 3 and 5 execute a scientific dry run followed by the guarded publication path. | Static-topology simulations pay preparation and/or duplicate-evaluation cost in the timestep path. Proof comparisons belong in tests or an opt-in diagnostic, not the production loop. |
| The implementation is heavily duplicated and policy has drifted. | **Confirmed.** Providers, face loops, build gates, version checks, caches, and volume semantics differ by valence. | Further per-valence work increases the probability of scientific and operational drift. |
| `d4/d7/d8` can remain uninitialized in the legacy setup branch. | **Confirmed as a static safety defect.** The branch tests three adjacent-vertex counts, then assigns the variables only if an adjacent-face count is exactly 5. Ghost skipping reduces exposure but does not make the assignment total. | Replace implicit assumptions with explicit closed-interior validation and fail before use. |
| The legacy route is inactive in the shipped defaults. | **Mostly confirmed.** `subDivideTimes` defaults to zero and is not read from the normal parameter input, so an 11-control face is rejected by the force guard. Tests and programmatic callers can still set a positive value, so the path is not literally unreachable. | Treat it as a dormant but callable compatibility defect, not dead code that can be ignored. |

## Important qualifications to the review

The review should not be adopted verbatim:

1. **Valence-5 scientific acceptance is not missing.** The earlier decision
   packet initially withheld approval, but the later selection record states
   that the user explicitly accepted stock OpenSubdiv semantics, and the
   Phase-3 record documents guarded production activation. The accepted scope
   is narrow and fixture-bound; it does not validate the overall architecture.
2. **Fail-loud behavior is valuable.** Exact-topology rejection prevented the
   proof implementation from silently claiming mixed-topology support. The
   problem is not the guards; it is treating guarded proofs as the shape of the
   final implementation.
3. **Two identical mixed-derivative rows are intentional interface
   compatibility, not inherently a geometry defect.** OpenSubdiv supplies one
   `Duv` row and a smooth surface has equal mixed partials. The current
   "rows drifted" comparison is nevertheless a weak test because both rows
   are created from the same source. The final interface should represent one
   mixed row explicitly and alias it into the legacy seven-row consumer only
   at the compatibility boundary.
4. **A generic Loop evaluator is topology-driven, not merely a scalar formula
   parameterized by valence `N`.** Boundary rules, orientation, creases, holes,
   and the complete neighborhood also matter. The correct unification unit is
   a mesh topology plus subdivision options.
5. **The CUDA duplicate-source message is not direct evidence that two active
   irregular backends implement conflicting rules.** The cited CUDA packer
   contract is for regular faces, while irregular CUDA routing is unsupported.
   It does show that the aliased legacy icosahedron representation has no
   compatible CUDA path and must not be treated as backend-portable.

## What should be retained

The proof program produced reusable engineering assets:

- source-keyed sparse rows and transpose-correct force scatter;
- atomic preflight/publication and fail-before-mutation behavior;
- finite-difference energy/force conjugacy checks;
- topology, orientation, row-sum, finiteness, OpenMP, output, and checkpoint
  adversarial tests;
- exact Valence-3/4/5 and mixed-topology fixtures;
- explicit OpenSubdiv version/dependency gates;
- the Valence-3 full-divergence volume derivation; and
- the topology-cache concept demonstrated by the Valence-3 provider.

These pieces should be moved behind a generic interface rather than copied
again.

## Proposed scientific and software decisions

### 1. Candidate stock OpenSubdiv Loop semantics (D1/D2b/D5)

The D1 proposal is to use stock OpenSubdiv Loop masks as the forward-looking CPU scientific
baseline. This is consistent with the recorded Valence-5 acceptance and
avoids maintaining a private subdivision scheme, but that narrow acceptance
does not decide the generic full-mesh baseline. D5 separately proposes keeping the legacy matrix path
only as a temporary compatibility backend for reproducibility of old runs.
Both choices require explicit user decisions. Do not attempt to patch completed
OpenSubdiv rows to imitate the legacy mask.

The primary `data/example` workload is flat and periodic. Repository evidence
records 2,720 physical faces, 960 ghost faces, and all 336 mixed-valence faces
inside the ghost band. D2's initial closed-manifold proof scope therefore does
not by itself authorize a production claim for the primary workload. D2b must
either define a reviewed periodic ghost/Ptex/source-ID and physical-face
evaluation policy or explicitly classify that workload as legacy-only.

### 2. Candidate canonical signed-volume functional (D3/D4)

For a closed, consistently oriented surface, use the full divergence
functional at every sample:

```text
V_face = (1/6) * sum_q weight_q * dot(x_q, cross(x_u_q, x_v_q))
```

The `1/6` combines the `1/3` divergence-theorem factor with the reference
triangle's `1/2` area under the repository's weights-sum-to-one convention.
Geometry, constraint energy, and force must consume and differentiate this
same expression. Open meshes need an explicit policy: either volume
constraints are disabled/rejected or a separately specified closure is used.

Because this changes regular, Valence-4/5, and CUDA-era numerical baselines,
it is not selected here. WP2.1 must characterize the exact-`1/6` candidate and
the current x-only literal `0.16666666666`; independent scientific review and
explicit user D3/D4 decisions follow. A candidate `legacy-x-volume` mode would
reproduce the decimal literal rather than silently mixing functionals by route.

### 3. Use a fixed topology-derived quadrature plan in production

The PR 182 Phase-5 result is useful but deliberately narrow: for its symmetric
and asymmetric `3/4/4` triangular bipyramid fixtures, depths 0 through 4, and
fixed global/force targets, the current three-point plan did not meet the last
two-transition convergence gate and depth 4 remained insufficient. This is
stacked negative evidence for those two fixtures, not a general theorem about
quadrature near extraordinary topology, and it does not imply that stock Loop
evaluation is wrong.

Investigate a graded composite rule that refines toward extraordinary corners
and uses a higher-order symmetric triangle rule on smooth subdomains. Select a
fixed plan when the topology cache is built and keep it fixed between topology
changes. A coordinate-dependent adaptive rule that changes samples during a
timestep can introduce discontinuous energies and forces and should not be
the first production design.

### 4. Separate preparation, evaluation, and publication

```text
oriented triangle topology + scheme options + quadrature policy
                              |
                              v
                 cached Loop topology/stencil package
                       |                     |
 source-keyed rows per face/sample    current coordinates
                       |                     |
                       +----------+----------+
                                  |
                                  v
               one geometry/energy/force face kernel
                              |
                              v
             thread-local source scatter and atomic publish
```

Topology and row preparation happens once per topology epoch. Coordinate
changes reuse the rows. Remeshing or an accepted edge flip increments the
topology epoch and invalidates the package explicitly.

## Target interfaces

The names are illustrative; the contracts are the important part.

```cpp
struct LoopTopologyKey {
    ConnectivityFingerprint connectivity;
    LoopSchemeOptions scheme;
    QuadraturePolicy quadrature;
    int opensubdivVersion;
};

struct SourceKeyedLimitSample {
    int faceIndex;
    ParametricLocation uv;
    SparseRow position;
    SparseRow du;
    SparseRow dv;
    SparseRow duu;
    SparseRow duv;
    SparseRow dvv;
};

class LoopLimitSurfaceBackend {
public:
    PreparedLoopTopology prepare(const MeshTopology&, const LoopPolicy&);
    const FaceSampleRows& rows(const PreparedLoopTopology&, int face) const;
};
```

Requirements:

- source IDs refer to original mesh vertices and cardinality is variable;
- one package may contain regular and extraordinary faces of any supported
  valence;
- no exact vertex/face-count or Platonic-solid identity appears in the
  production interface;
- closed-manifold, orientation, boundary, ghost, and non-manifold policy is
  validated once during preparation;
- the cache key contains every setting that can change rows;
- a coordinate-only update never rebuilds the `TopologyRefiner`, patch table,
  or limit stencil table; and
- the production evaluator performs one face evaluation, not a dry run plus a
  second publication evaluation.

Rows remain sparse at rest. For a requested face/sample batch, form one
deterministically ordered union of original source IDs, densify only those
rows into a compact row-by-union-source matrix for the existing dense
geometry kernel, and scatter through exactly the same ordered IDs. This
representation seam prevents both a global dense table and source-order drift.

OpenSubdiv provides the intended building blocks: `Sdc::SCHEME_LOOP`, a
`TopologyRefiner` for arbitrary topology and refinement, and
`LimitStencilTableFactory` for requested face locations and derivatives.
The generic backend should create one full-mesh refiner so mixed topology is
represented naturally, rather than constructing isolated per-valence
surrogates.

## Potential implementation plan

### Phase 0 - freeze and record the architecture decision

1. Pause Valence-3 production generalization and adaptive edge-flip changes.
2. Await the explicit user D0 disposition before marking PR 182 superseded or
   proof-only; do not call it a production implementation milestone.
3. Record stock OpenSubdiv Loop, the closed-manifold scope, and legacy matrix
   quarantine as D1/D2/D5 proposals requiring explicit user decisions.
   Restate D6/D7 only as existing constraints. Record D3/D4 as pending WP2.1,
   independent scientific review, and explicit user decisions.
4. Preserve current-main exact Valence-4/5 compatibility routes during
   migration; do not broaden them. Preserve the unmerged exact Valence-3 stack
   as separately labeled evidence until PR 182's disposition is decided.

Exit gate: exact-head review of the amended decision ledger and a complete
statement of the evidence/authority required for D0-D5, D2b, D8, and later
D3/D4 decisions. D6/D7 are restatements. Unresolved choices block only their
named downstream packages; they do not block Phase 1a safety or Phase 2
characterization.

### Phase 1a - unconditional legacy index/classifier safety

No D5 decision is required. Sentinel-initialize `d4/d7/d8`, make every index
state total before use, add a pure observational topology classifier, and
reject only ambiguous or unassigned states that could otherwise produce
undefined behavior. Preserve all currently accepted topology and ordering
contracts, including the aliased all-Valence-5 icosahedron. The classifier may
record that aliasing but may not quarantine it.

Exit gate: sanitizer and focused tests prove that no uninitialized or ambiguous
index reaches geometry mutation, while accepted baselines remain unchanged.

### Phase 1b - D5-dependent quarantine or net-new `5/6/6` lane

Prerequisites: Phase 1a merged and explicit user D5 decision.

1. If quarantine is selected, reject the accepted all-Valence-5 11-control
   legacy route before matrix evaluation and update its regression contract.
2. If `5/6/6` support is separately selected, treat it as a net-new scientific
   lane: the current all-`5/5/5` predicate never admitted that topology.
3. Require exact topology/orientation proof, 11 correctly ordered distinct
   sources, matrix/force conjugacy, and independent scientific review for the
   net-new lane; never label it retained historical compatibility.

Exit gate: the explicit D5 outcome is implemented without broadening another
route or silently changing an accepted fixture.

### Phase 2 - candidate functional characterization and independent oracle

1. Specify full-divergence signed volume and derive its discrete gradient.
2. Build an independent finite-difference, automatic-differentiation, or
   higher-precision oracle for area, bending energy, volume energy, and all
   force components.
3. Test translation invariance of closed-surface volume, rigid-motion energy
   invariance, net force/torque, orientation reversal, and zero-volume-penalty
   behavior.
4. Characterize the re-baseline against regular, Valence-3/4/5, and mixed
   fixtures before changing production defaults.
5. Characterize a possible explicit legacy-x compatibility mode reproducing
   the literal `0.16666666666`; do not select its default or lifetime.

Exit gate: candidate functionals reproduce their gradients on every fixture,
then receive independent scientific review. Production work remains blocked
until explicit user D3/D4 decisions.

### Phase 3 - generic cached row backend, proof-only

Prerequisites: explicit user D1/D2 decisions. Volume semantics remain excluded
until D3/D4 are explicitly decided.

1. Introduce one OpenSubdiv build gate, initially
   `USE_OPENSUBDIV_LOOP`, and one version policy.
2. Build a full-mesh Loop `TopologyRefiner` from arbitrary oriented triangular
   connectivity.
3. Generate source-keyed position and derivative rows for all physical faces
   and the selected fixed quadrature locations in one preparation step.
   Keep them sparse at rest and use the deterministic union-source densification
   seam described above at evaluation time.
4. Cache by connectivity, subdivision options, quadrature plan, boundary/hole
   policy, and OpenSubdiv version.
5. Explicitly invalidate on setup, remeshing, edge flip, orientation change,
   or topology-tag change.
6. Compare the generic backend with the existing regular and exact
   Valence-3/4/5 providers without routing production.
7. As a hard stop, compare full-mesh generic rows and integrands for canonical
   `6/6/6` faces against `SlimedLoopLimitSurfaceEvaluator`; the frozen maximum
   absolute tolerance is `5.0e-6` and must not be widened to pass.
8. Resolve D2b before claiming the primary flat/periodic workload: prove its
   ghost-band/source policy or reject that scope explicitly.

Exit gate: a single package accepts mixed closed meshes, rejects malformed
topology atomically, and records a cache hit on coordinate-only reevaluation.

### Phase 4 - one variable-cardinality face kernel

1. Extract the reusable mathematics from
   `element_energy_force_regular()` into a kernel that consumes source-keyed
   rows rather than 12-control or fixture-specific arrays.
2. Use the same rows and samples for geometry, energy, and force.
3. Represent one mixed derivative internally; adapt to seven legacy rows only
   at a compatibility seam.
4. Scatter through original source IDs using thread-local buffers and the
   existing deterministic reduction contract.
5. Keep atomic preflight/publication, but move dry-run parity to test or an
   opt-in diagnostic mode.

Exit gate: finite-difference conjugacy, serial/OpenMP equivalence, and exact
repeatability pass on regular, isolated extraordinary, Platonic, bipyramid,
mixed 3/4/5, and perturbed fixtures.

### Phase 5 - quadrature selection and convergence

1. Establish a deeper independent reference calculation for each fixture.
2. Compare high-order symmetric triangle rules, graded corner refinement, and
   OpenSubdiv patch-domain decomposition.
3. Treat a singular or unbounded higher curvature derivative at the
   extraordinary point as a hypothesis to test, not an assumption. A negative
   result for the uniform rule routes to the predeclared graded-corner and
   patch-domain candidates; only failure of all candidate families is a global
   stop.
4. Select the least expensive **fixed** rule that meets global geometry,
   energy, and per-source force targets over at least two successive reference
   refinements.
5. Separate row-algebra residuals from integration convergence; neither target
   may be widened to make the other pass.
6. Test valences beyond 3/4/5 and randomized legal edge-flip topologies to
   ensure the implementation is topology-driven rather than fixture-driven.

Exit gate: the rule meets fixed scientific targets for symmetric and
asymmetric meshes against the independent oracle. Fixed expected values may
remain as regression locks, but they must not be the convergence oracle.

### Phase 6 - guarded production migration

Prerequisites: all applicable D1-D5 gates, including D2b for periodic/ghost
scope, independently reviewed WP2.1 evidence, explicit user D3/D4 decisions,
and a reproduced, reviewed, explicitly approved D8 budget.

1. Add one runtime selector such as
   `SLIMED_SUBDIVISION_BACKEND=opensubdiv-loop|legacy`.
2. Treat the three old valence environment variables as temporary deprecated
   aliases with conflict detection and warnings.
3. Route complete supported closed meshes through the generic backend; do not
   mix volume functionals or subdivision schemes face by face.
4. Preserve output/checkpoint schemas and the legacy backend for a bounded
   compatibility window.
5. Benchmark preparation separately from per-timestep evaluation and require
   no OpenSubdiv topology/stencil construction in a coordinate-only timestep.
   Use a same-binary alternating-order protocol with preparation performed once
   per topology epoch and reported separately. Candidate D8 ceilings are a
   generic coordinate-only median no more than `1.10x` the current cached
   regular route and every case no more than `2.00x` the direct analytic route;
   they become gates only after reproduction and explicit user approval.
6. Repeat output, restart, serial/OpenMP, sanitizer, and long-run dynamics
   suites before activation.

CUDA should remain unchanged during the proof phases. The eventual volume or
backend migration must include a dedicated backward-compatibility lane: either
CPU and CUDA use the same canonical functional, or the program rejects a
backend/functional combination that would silently diverge. Do not add a
second CUDA-only scientific baseline.

Exit gate: dedicated reviewer approval and explicit user authorization for
the new default.

### Phase 7 - adaptive edge flipping, only after topology epochs work

Edge flipping is feasible only after cache invalidation and variable topology
are first-class. A candidate flip must preserve a closed oriented manifold,
avoid duplicate edges/faces, keep vertex valence at least 3, preserve material
and insertion labels, and improve a declared quality objective. The objective
should combine triangle angle/aspect quality with a valence penalty rather
than assuming "closer to valence 6" is always physically neutral.

Every accepted flip changes the control cage and therefore the Loop limit
surface. It is a remeshing operation, not a free evaluator optimization. The
plan must define state transfer, energy discontinuity policy, topology-cache
rebuild, rollback, and before/after scientific diagnostics before enabling it
in dynamics.

## Candidate acceptance matrix after the required decisions

| Category | Required evidence |
| --- | --- |
| Topology | Arbitrary closed oriented triangular meshes; mixed valences; explicit rejection of non-manifold and unsupported boundary cases. |
| Rows | Partition of unity and derivative sum rules; finite rows; stable original-source IDs; one documented mixed derivative. |
| Geometry | Positive area, signed-volume orientation behavior, rigid-motion invariants, and agreement with an independent oracle. |
| Energy/force | Per-source, per-family, per-axis finite differences; full volume conjugacy; net force and torque bounds. |
| Quadrature | Fixed targets reached over successive refinements on symmetric, asymmetric, mixed, and randomized fixtures. |
| State safety | Fail before mutation; exact output/checkpoint preservation; deterministic rollback. |
| Concurrency | Serial and 1/2/4-thread equivalence under fixed tolerances and repeated runs. |
| Performance | Topology preparation once per topology epoch; no dry-run duplication or refiner/stencil rebuild per timestep; reproduced D8 budget before production PASS. |
| Compatibility | Explicit legacy scheme and legacy volume selection; no route-dependent hidden functional. |

## Repository evidence inspected

- [`Mesh_setup_geometry.cpp`](../src/mesh/Mesh_setup_geometry.cpp) contains the
  all-three-corners-valence-5 legacy branch, while
  [`Gauss_quadrature.cpp`](../src/mesh/Gauss_quadrature.cpp) constructs the
  one-valence-5/two-valence-6 subdivision matrix.
- [`Mesh.cpp`](../src/mesh/Mesh.cpp),
  [`Valence4_face_loop_route_preflight.cpp`](../src/energy_force/Valence4_face_loop_route_preflight.cpp),
  and [`Valence5_opensubdiv_face_loop.cpp`](../src/energy_force/Valence5_opensubdiv_face_loop.cpp)
  retain the legacy x-only volume expression. The unmerged
  [PR 182 stack's Valence-3 face loop](https://github.com/JohnsonBiophysicsLab/SLIMED_dev/blob/9587e3dce4509029e611e2937bac570b410193c3/src/energy_force/Valence3_opensubdiv_face_loop.cpp)
  uses full divergence.
- [`Compute_energy_and_force_on_mesh.cpp`](../src/energy_force/Compute_energy_and_force_on_mesh.cpp)
  implements mutually exclusive whole-mesh extraordinary route selection.
- The three current row providers are
  [`OpenSubdiv_valence3_row_provider.cpp`](../src/mesh/OpenSubdiv_valence3_row_provider.cpp),
  [`OpenSubdiv_valence4_row_provider.cpp`](../src/mesh/OpenSubdiv_valence4_row_provider.cpp),
  and [`OpenSubdiv_valence5_row_provider.cpp`](../src/mesh/OpenSubdiv_valence5_row_provider.cpp).
- [`irregular_valence5_option_b_selection_record.md`](irregular_valence5_option_b_selection_record.md)
  records scientific acceptance of stock Valence-5 semantics, and
  [`irregular_valence5_option_b_phase3_activation.md`](irregular_valence5_option_b_phase3_activation.md)
  records its narrow guarded activation.
- [PR 176](https://github.com/JohnsonBiophysicsLab/SLIMED_dev/tree/46c06080fb663bcb43f38cf32fc1b45daa8732e8)
  is the unmerged production-code stack root. The unmerged
  [PR 182 Phase-5 convergence record](https://github.com/JohnsonBiophysicsLab/SLIMED_dev/blob/9587e3dce4509029e611e2937bac570b410193c3/docs/irregular_valence3_phase5_quadrature_convergence.md)
  records the bipyramid non-convergence result.

## OpenSubdiv basis for this recommendation

- [OpenSubdiv `Sdc::Scheme`](https://graphics.pixar.com/opensubdiv/docs/doxy_html/a00085.html)
  describes scheme masks as functions of topological neighborhoods and exposes
  `SCHEME_LOOP` through the Sdc layer.
- [`TopologyRefiner`](https://graphics.pixar.com/opensubdiv/docs/doxy_html/a01121.html)
  stores arbitrary refined topology and supports uniform or adaptive
  refinement, including selected faces.
- [`LimitStencilTableFactory`](https://graphics.pixar.com/opensubdiv/docs/doxy_html/a01098.html)
  creates limit stencils at requested locations, which is the direct basis for
  a cached source-keyed row table.
- The [FAR overview](https://graphics.pixar.com/opensubdiv/docs_3x_alpha/far_overview.html)
  explains that accumulated stencils map limit samples to coarse control
  vertices and that adaptive refinement is used around extraordinary regions.

## Final recommendation

Do not continue "Valence 3" as a separate production feature. Treat the
existing Valence-3/4/5 work as a set of proofs, fixtures, and compatibility
baselines feeding one generic Loop backend. First complete unconditional
Phase 1a safety. After an explicit user D5 decision, implement the selected
Phase 1b quarantine or separately gated net-new lane. Use WP2.1 evidence, independent
scientific review, and explicit user D3/D4 decisions before selecting a volume
functional. Then build the
full-mesh cached row provider, one variable-cardinality face kernel, and a
scientifically converged fixed quadrature policy. Only after those foundations
pass mixed-topology tests should production routing or adaptive edge flipping
resume.
