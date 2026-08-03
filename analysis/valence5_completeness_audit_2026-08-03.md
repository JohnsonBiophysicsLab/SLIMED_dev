# Valence-5 Option B completeness audit

Date: 2026-08-03  
Audited baseline: `main` at `d28fdda`, including merged Phase 3 PR #169 (`8ce1431`, merge `0c1e070`)  
Production/CUDA changes made by this audit: none

## Verdict

**EXTRA WORK TBD.**

The accepted, narrowly scoped Valence-5 Option B production implementation is
substantively complete for its one approved object: the exact closed,
positive-depth, ordered 12-vertex/20-face icosahedral fixture. Phases 1, 2,
and 3 are present, the default evaluator is routed behind an explicit runtime
gate, stock OpenSubdiv Loop rows feed the existing membrane algebra through
original source IDs, the dependency-free fallback remains available, and the
historical enabled evidence covers geometry, energy, force, serial/OpenMP,
CSV, and V1/V2 restart behavior.

No production correctness defect was found in that canonical route during
this read-only audit. It nevertheless should not be declared globally
complete because its current regression evidence is not healthy on `main`, no
OpenSubdiv-present run could be reproduced in the current environment, and
the implementation cannot participate in the requested mixed Valence-3/4/5
local-patch topology. These are concrete follow-up items, not reasons to undo
the accepted stock semantics or the guarded Phase 3 route.

## Accepted scope and present implementation

### Phase 1: stock row provider

`src/mesh/OpenSubdiv_valence5_row_provider.cpp` implements the accepted stock
provider with the following bound contract:

- exactly 12 source vertices and 20 oriented physical faces;
- every source vertex has valence 5 and the face/index order matches the
  checked-in canonical fixture;
- stock `Sdc::SCHEME_LOOP`, with the closed-mesh-irrelevant boundary option
  explicitly set to `VTX_BOUNDARY_EDGE_ONLY`;
- adaptive patch construction at the fixed provider depth, with one reviewed
  Ptex identity per physical face;
- the ordered three-point plan `(1/6,1/6)`, `(1/6,4/6)`, `(4/6,1/6)`;
- double-precision limit stencils with first and second derivatives;
- seven SLIMED rows per sample, with `Duv` duplicated for both mixed rows;
- exactly nine sorted original source IDs for every face;
- finite coefficients, partition-of-unity/zero-derivative-sum checks, exact
  source coverage, and staged publication only after the complete package
  passes.

The API compiles to an explicit dependency-disabled stub unless
`USE_OPENSUBDIV_VALENCE5=1` is supplied. The Makefile requires an explicit
`OPENSUBDIV_ROOT` for that build, so ambient installation does not silently
change default physics.

This is stock OpenSubdiv extraordinary semantics, not a disguised parity
route. The accepted record explicitly recognizes that OpenSubdiv's valence-5
vertex mask and SLIMED's historical positive-depth `11 = 4 + 3 + 4` mask do
not match.

### Phase 2: geometry, membrane algebra, source scatter, and completion

`src/energy_force/Valence5_opensubdiv_face_loop.cpp` binds the provider to the
shared production transaction:

- exact `gaussQuadratureN == 2`, sample coordinates, and three `1/3` weights
  are required;
- provider rows are canonicalized by original source ID through
  `Source_keyed_kernel_call` rather than through the legacy 11-slot one-ring;
- current coordinates are evaluated through the nine-source position/first-
  derivative rows to stage per-face area and legacy volume;
- a pre-mutation scientific dry run calls the same
  `element_energy_force_regular` formula with caller-owned row overrides;
- the generic guarded face-loop seam validates all vertex/face identities,
  finite destinations, row/sample cardinalities, geometry totals, and shape
  matrices before the first mesh write;
- the transaction publishes staged geometry, clears current state, executes
  the production membrane loop, reduces per-thread source-keyed force
  buffers in ascending thread order, and runs unchanged regularization,
  total-force, total-energy, and boundary completion;
- face observables and source forces are compared with the dry run under the
  fixed `1e-10` production tolerance.

Legacy `Face::oneRingVertices` are neither populated nor reordered. Existing
nonempty one-rings are explicitly marked as bypassed, and force contributions
are scattered to the matching original `Mesh::vertices[sourceId]` entries.

The independent long-double oracle and the fixed scientific vectors in the
Phase 2 runner bind the accepted stock baseline. The historical OpenSubdiv
3.7.0 evidence reported an oracle maximum difference of
`3.552713678800501e-14`, serial/OpenMP membrane-force difference of
`1.021405182655144e-14`, and energy/geometry difference of
`6.175615574477433e-16`, all under the fixed `1e-10` production policy.

### Phase 3: default evaluator activation and rollback

`Mesh::Compute_Energy_And_Force()` inspects
`SLIMED_USE_OPENSUBDIV_VALENCE5` before executing the ordinary geometry and
legacy membrane path. With the exact token `1`, it calls
`evaluate_guarded_valence5_production_route`; any rejection is raised as a
loud runtime error before the default evaluator writes mesh state. A
simultaneous Valence-4 and Valence-5 extraordinary request is also rejected
before mutation.

With the runtime gate absent, the evaluator continues through the unchanged
dependency-free positive-depth 11-control fallback. Therefore rollback is
simply unsetting `SLIMED_USE_OPENSUBDIV_VALENCE5`; no rebuild, checkpoint
conversion, or mesh migration is required. Requesting the route in a default,
dependency-disabled build fails loudly and atomically.

The Phase 3 harness calls the public evaluator, compares it with the direct
reviewed transaction, verifies fallback equivalence across dependency-free and
enabled builds, exercises serial and OpenMP binaries, requires exact repeated
serial output, invokes both CSV writers, and performs an exact V2 checkpoint
round trip.

### Output and restart compatibility

The accepted output repair is shared production I/O rather than a private
Valence-5 format. It preserves all ten global and per-face energy channels at
17-digit precision. `SLIMED_RESTART_V2` includes current, previous, and NCG
force families plus face normals, mean curvature, area, legacy volume, and
all face-energy channels; the loader still accepts V1 and rejects trailing
tokens. No Valence-5-specific schema or checkpoint migration is introduced.

## Verification performed in this audit

The workspace was concurrently dirty with unrelated CUDA, naming, and
Valence-3 work. No tracked or untracked user/agent changes were modified.

1. `scripts/run_irregular_valence5_option_b_phase3_activation.sh --check --json`
   built and ran the dependency-free Phase 3 harness. Result: `status: skipped`
   only because `OPENSUBDIV_ROOT` was unset, while
   `dependency_absent_request_rejected_atomically: true` and
   `fallback_preserved: true` passed.
2. `SourceKeyedKernelCallTest.*`: 5/5 C++ tests passed.
3. The two CSV contract tests plus four V1/V2 checkpoint/restart tests: 6/6
   passed when run in a clean audit-specific temporary directory. Initial
   failures were stale `/tmp` permission artifacts, not code failures.
4. The full available default C++ binary had one failure when rerun with a
   clean `TMPDIR`:
   `EnergyForceEvaluatorTest.SharedHelperRecordsScaffoldEnergyAndForceSideEffects`.
   This is the already documented unrelated scaffold expected-vector defect;
   no Valence-5 or output/restart test then failed.
5. `tests.test_opensubdiv_routing_readiness_inventory`: 6/6 passed.
6. The complete `test_irregular_valence5*_inventory.py` discovery ran 139
   tests: 11 failed and 14 OpenSubdiv-present tests skipped. The failures are
   not numerical Valence-5 failures; they are stale historical inventory
   assumptions described below.

The current environment had no `OPENSUBDIV_ROOT`, and no usable OpenSubdiv
installation was found at the documented WSL locations. Consequently the
real double-row provider, enabled Phase 2 oracle, and enabled Phase 3
serial/OpenMP route were not independently rerun in this audit.

## Prioritized remaining work

### P1 - Make the Valence-5 regression suite valid on current `main`

Eleven of 139 Valence-5 inventory tests fail on the current repository. The
affected Phase 1, energy/geometry, output, Phase 2, Phase 3, scientific
decision/selection, serial/OpenMP, and post-Option-D inventories compute
`git diff --name-only` from their historical PR base and treat every later
legitimate path as a scope violation. Some also require obsolete historical
wording that later accepted phases intentionally superseded.

This means the tests are useful as frozen PR archaeology but invalid as
ongoing main-branch regressions. A new change cannot obtain a clean
Valence-5 inventory result even when it does not touch Valence-5 code.

Concrete fix:

1. Separate immutable historical evidence validation from current-state
   regression tests.
2. Keep digest/anchor checks for each historical packet, but stop recomputing
   old PR path budgets against current `HEAD`.
3. Add a small current-state Phase 3 contract inventory that checks the
   canonical fixture, build/runtime gates, fallback, fixed baseline identity,
   and runner availability without assuming the tree still equals an old PR.
4. Require this current-state inventory in CI.

Until that is done, “all Valence-5 tests pass on main” is false.

### P1 - Add reproducible OpenSubdiv-present continuous verification

The merged documentation records successful OpenSubdiv 3.7.0 WSL runs, but
the repository's GitHub workflows run only the default `make test` path and do
not install or exercise OpenSubdiv. All enabled Python tests are guarded by
`OPENSUBDIV_ROOT` and were skipped here.

Concrete fix:

1. Add an explicit CI or scheduled job with a pinned OpenSubdiv version/commit
   and run the Phase 1 provider, Phase 2 oracle, and Phase 3 activation runners
   with `--require-opensubdiv`.
2. Cover both serial and OpenMP enabled builds and retain the current fixed
   tolerances and scientific vectors.
3. Also build the combined extraordinary configuration used by future
   Valence-3/4/5 work, so shared source-keyed code and route arbitration are
   checked together.

This is a verification gap, not evidence that the current stock calculations
are wrong.

### P1 for the present program - Generalize from a whole-fixture route to a mixed local-patch route

The Valence-5 route is intentionally whole-mesh and identity locked. The
provider rejects anything other than the exact icosahedron: 12 vertices, 20
faces in fixed order, and every vertex of valence 5. The default evaluator
selects one extraordinary route for the entire transaction, and explicitly
rejects simultaneous Valence-4/Valence-5 requests.

Therefore the existing Valence-5 implementation cannot validate or evaluate
the requested local patch containing Valence 3, 4, and 5 irregularity. Merely
adding a Valence-3 provider does not close this gap; Valence-5's own topology
guard and the evaluator's route arbitration still reject a mixed object.

Concrete next design step:

1. Introduce a single mesh-level extraordinary dispatcher that partitions
   faces by reviewed local topology and composes all accepted source-keyed row
   packages into one complete transaction.
2. Preserve per-face source IDs, Ptex/sample identity, and atomic full-mesh
   validation before mutation.
3. Establish a checked-in mixed 3/4/5 fixture and independent finite-
   difference/oracle checks for geometry, all force families, global and
   per-face energy, serial/OpenMP accumulation, output, and restart.
4. Keep the canonical icosahedron as a regression control and require exact
   equivalence between the old Valence-5-only dispatcher result and the new
   composed dispatcher on that fixture.

This expansion requires new scientific review; it is outside the accepted
canonical Option B scope.

### P2 - Remove stale Phase-2 naming and documentation after Phase 3

The public header is still named `Valence5_opensubdiv_face_loop.hpp`, the
namespace remains `opensubdiv_valence5_phase2`, and the result type remains
`Valence5Phase2Result` even for the Phase 3 production caller. More
importantly, the Phase 2 function comment still says it is “deliberately not
installed in `Mesh::Compute_Energy_And_Force()`,” while the same header now
declares the installed Phase 3 route and the evaluator does call it.

Concrete fix: adopt the same neutral route/provider/caller naming convention
chosen for Valences 3 and 4, retain compatibility aliases where needed, and
rewrite the comment to distinguish the proof-only Phase 2 entry point from
the Phase 3 production wrapper. This is clarity/maintainability work; it does
not require changing stock physics.

### P2 - Preserve an auditable approval record

The repository proves that Phase 3 was merged as PR #169, while the accepted
plan required a dedicated reviewer PASS and explicit user approval. The
checked-in Phase 3 document describes the activated result but does not record
the reviewer verdict or approval identity. If those records live only in a
conversation or PR UI, add a durable link or short approval record to the
Phase 3 documentation. This is a governance traceability gap, not a runtime
defect.

## Final completeness statement

The correct narrow statement is:

> Canonical closed Valence-5 Option B production routing is implemented and
> historically validated behind explicit build/runtime gates, with a complete
> fallback and output/restart contract.

The incorrect broader statement is:

> Valence-5 support is complete for arbitrary or mixed meshes and is fully
> regression-green on current main.

Close the two P1 verification items before labeling the existing route fully
maintained, and complete the mixed-dispatch work before using it as evidence
for a local Valence-3/4/5 patch.
