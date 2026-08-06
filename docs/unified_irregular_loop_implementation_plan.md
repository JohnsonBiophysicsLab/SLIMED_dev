# Unified irregular Loop implementation control plan

Status: execution started; K1 implementation drafted, approvals pending

Date: 2026-08-05
Source decision analysis:
[`irregular_loop_architecture_reassessment.md`](irregular_loop_architecture_reassessment.md)

## 1. Purpose and target outcome

This document is the execution contract for replacing the current
Valence-3/4/5 proof-by-fixture architecture with one topology-driven Loop
limit-surface backend. It is written so that a coordinator can copy a work
package into a subagent prompt without silently expanding scope.

The target outcome is:

1. one full-mesh OpenSubdiv Loop topology/stencil package for supported closed
   oriented triangular meshes;
2. variable-cardinality source-keyed rows using original SLIMED vertex IDs;
3. one geometry, energy, and force kernel consuming the same rows, samples,
   quadrature weights, and volume functional;
4. preparation once per topology epoch and reuse during coordinate-only
   timesteps;
5. one guarded runtime backend selection rather than mutually exclusive
   valence routes; and
6. explicit legacy and CUDA compatibility boundaries.

This plan does not authorize production activation, a new scientific
baseline, merging the PR 176/182 stack, deleting legacy behavior, or changing
CUDA. Those
actions have separate gates below.

## 2. Current baseline and pending decisions

The original WP0.1 base was
`origin/main@906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a`; PR 183 merged that
record as `e9af3ddad494fc073040ee82bdf07944b9fee8cf`, which is the
authoritative base for this amendment. At the time this plan was amended:

- PR 176, `Advance Valence 3 Phase 2 mechanical proof`, is the open
  production-code stack root at
  `46c06080fb663bcb43f38cf32fc1b45daa8732e8`;
- PR 182, `Measure Valence 3 bipyramid quadrature convergence`, is open and
  clean at `9587e3dce4509029e611e2937bac570b410193c3`;
- PR 182 is stacked on PR 176 (`codex/valence3-phase2-scientific-packet`), not on
  current `main`. Its Valence-3 production face loop, Phase-5 convergence
  document, and asymmetric bipyramid fixture are unmerged stack evidence and
  must not be inventoried as current-main production behavior;
- PR 182 records negative convergence evidence only for its symmetric and
  asymmetric `3/4/4` triangular bipyramids, OpenSubdiv 3.7.0, isolation level
  5, nested depths 0 through 4, fixed parameters, and recorded targets. It
  does not establish a result for other topology/rule/depth combinations, and
  its dedicated Valence-3 provider is not the recommended architecture;
- current `main` contains the merged Valence-4/5 behavior and earlier
  Valence-3 provider proof; later exact Valence-3 production/convergence work
  exists only in the named stack;
- stock OpenSubdiv Valence-5 semantics were explicitly accepted for the
  narrow exact topology; and
- the regular, Valence-4, Valence-5, and CUDA paths still expose legacy
  x-only volume using the literal `0.16666666666`, while the unmerged PR 182
  Valence-3 stack uses full divergence with exact `1/6`.

No implementation package may start until its dependencies in this table are
resolved.

| Decision | Recommended answer | Authority required | Blocks |
| --- | --- | --- | --- |
| D0: PR 176/182 stack disposition | Do not merge PR 176 as an implementation milestone. Extract the symmetric/asymmetric bipyramid fixtures and scoped negative convergence record before superseding or closing the stack. | Explicit user decision | WP0.2 and final stack cleanup |
| D1: subdivision scheme | Stock OpenSubdiv Loop is the forward-looking CPU baseline; narrow Valence-5 acceptance is insufficient for the generic backend. At `N=6`, stock Loop and historical `3/(8N)` weights coincide exactly, so the checked-in `data/example` physical regular faces have no mask rebaseline; arbitrary production inputs remain unqualified. | Explicit user scientific decision, informed by prior Valence-5 acceptance | WP3+ |
| D2: initial proof topology scope | Closed, oriented, manifold, triangular meshes; reject unsupported boundaries, holes, and non-manifold inputs. | Explicit user decision | Closed-mesh WP3 proofs |
| D2b: periodic/ghost production scope | Require an explicit periodic ghost-band, Ptex/source-ID, and physical-face evaluation policy in WP3.2; otherwise declare the primary flat/periodic workload legacy-only. | Explicit user production-scope decision | WP3.2 completion, WP6+ |
| D3: canonical volume | Full divergence with exact `1/6` under the weights-sum-to-one triangle convention. | WP2.1 oracle, independent scientific review, and explicit user scientific decision | WP2.2 and WP4+ production claims; does not block WP2.1 characterization |
| D4: legacy volume compatibility | Candidate `legacy-x-volume` reproduces the x-only literal `0.16666666666`; never select by valence. Default and lifetime remain undecided. | WP2.1 characterization, independent scientific review, and explicit user decision | WP2.2, WP6+ |
| D5: legacy 11-control matrix | After WP1.1a evidence, quarantine all-valence-5 misuse. Treat intended `5/6/6` support as net-new work because the current all-`5/5/5` predicate never admitted it. | Explicit user decision after WP1.1a; any `5/6/6` implementation needs a separate scientific gate | WP1.1b |
| D6: dependency policy | Default builds remain OpenSubdiv-free through proof and opt-in phases. | Existing project policy | All packages |
| D7: CUDA timing | No CUDA implementation changes before the dedicated compatibility package. | Existing user instruction | WP8 |
| D8: performance budget | Under the same-binary protocol, `generic_vs_cached_regular_median <= TBD` remains pending the named measurement and approval; the direct-route candidate is `generic_vs_direct_regular_each_case <= 2.00`. Preparation occurs once per epoch and is reported separately. | Reproduced benchmark evidence plus explicit user approval | WP3.3 PASS, WP6.3 |

If an answer changes, update this table and every downstream prompt before
starting another package.

## 3. Non-negotiable rules

Subagent prompts should cite rule IDs rather than paraphrasing them.

### Scientific rules

- **S1 - one scheme:** Do not introduce another custom extraordinary mask or
  modify completed OpenSubdiv rows to resemble the legacy Warren-style mask.
- **S2 - one functional:** Geometry, volume energy, and volume force for a
  selected mode must use one explicitly named volume functional. Route- or
  valence-dependent hidden selection is forbidden.
- **S3 - conjugacy:** Every energy/force implementation must pass per-source,
  per-family, per-axis differentiation against an independent oracle.
- **S4 - fixed production quadrature:** Production sample locations and
  weights stay fixed for a topology epoch. Coordinate-dependent quadrature
  adaptation is proof-only unless a later scientific decision covers its
  energy/force consequences.
- **S5 - no tolerance fitting:** Tolerances are frozen before authoritative
  runs. An agent must report a negative result rather than widen, scale,
  reorder, or selectively omit a failed comparison.
- **S6 - oracle independence:** Hardcoded expected values may lock a
  regression, but may not be the sole convergence or physics oracle.
- **S7 - signed orientation:** Volume behavior under orientation reversal and
  translation must be specified and tested for closed meshes.

### Architecture rules

- **A1 - topology, not valence dispatch:** Production acceptance may inspect
  valence for validation and diagnostics, but may not select separate
  Valence-3/4/5 evaluators.
- **A2 - full-mesh preparation:** Create one topology representation for the
  complete supported mesh. Do not fabricate Platonic or isolated per-face
  surrogate meshes in production.
- **A3 - backend-neutral seam:** OpenSubdiv types stay inside the backend.
  Public SLIMED consumers see original source IDs, sample metadata, sparse
  derivative rows, and diagnostics.
- **A4 - variable source cardinality:** No production contract assumes 4, 6,
  9, 11, or 12 sources. Each sparse row identifies its original SLIMED source
  IDs explicitly.
- **A5 - one mixed derivative:** Store one `duv` row internally. Duplicate it
  only at the legacy seven-row compatibility seam.
- **A6 - topology epoch:** Cache identity includes connectivity, orientation,
  ghost/hole/boundary policy, subdivision options, quadrature policy,
  OpenSubdiv version, and every other row-affecting setting. Coordinate-only
  updates must hit the cache.
- **A7 - one hot-loop evaluation:** Production evaluates each face/sample
  once. Scientific dry-run duplication belongs in tests or an explicit
  diagnostic mode.
- **A8 - explicit invalidation:** Setup, remeshing, accepted edge flips,
  orientation changes, and topology-tag changes invalidate the prepared
  package through one reviewed mechanism.
- **A9 - stable naming:** New production names use `Loop` or
  `OpenSubdiv_loop`, not `Valence3`, `Valence4`, or `Valence5`.

### Safety and compatibility rules

- **C1 - fail before mutation:** Unsupported topology, stale cache identity,
  malformed rows, nonfinite values, or conflicting configuration must be
  rejected before mesh, face, force, energy, output, or checkpoint mutation.
- **C2 - no silent fallback:** A requested backend or functional cannot
  silently fall back to a scientifically different one.
- **C3 - default dependency isolation:** Default `make` targets and the full
  default test suite pass without OpenSubdiv installed.
- **C4 - output stability:** Proof packages do not change checkpoint formats,
  CSV schemas, energy channel counts, or restart semantics.
- **C5 - CUDA freeze:** Packages WP0-WP7 must not modify `src/cuda`,
  `include/cuda`, CUDA build targets, or CUDA scientific baselines. They may
  add read-only inventories proving CUDA remains unchanged.
- **C6 - legacy reproduction is explicit:** Compatibility behavior is selected
  by a named mode and recorded in diagnostics/output metadata where possible;
  it is not inferred from face valence.
- **C7 - no broad cleanup:** Each package changes only files required for its
  gate. Naming cleanup, deletion, and performance cleanup occur in their named
  packages.

### Process rules

- **P1 - one package, one branch, one PR:** A PR has one primary scientific or
  architectural claim. The coordinator alone changes branches, stages,
  commits, pushes, and opens/retargets PRs in the shared checkout. Stacked PRs
  must declare their non-main base and cannot activate production before all
  ancestors merge.
- **P2 - serialized shared-worktree writes:** Every implementation prompt
  lists allowed and forbidden paths. Only one implementation agent may edit
  the shared worktree at a time. Read-only audits may run concurrently only
  after the coordinator records the exact HEAD and promises not to switch it
  during their review. Disjoint file ownership does not make shared HEAD or
  index operations safe. Parallel git writers require coordinator-created,
  explicitly isolated worktrees and are otherwise forbidden.
- **P3 - preserve user changes:** Unrelated dirty or untracked files are not
  staged, reformatted, moved, or deleted.
- **P4 - exact-head review:** The reviewer receives the full commit SHA and
  returns `PASS - MERGEABLE` or `FAIL - NOT MERGEABLE` with blocking findings.
  Review of an older SHA is invalid after any push.
- **P5 - independent reviewer:** The final reviewer must not be the agent that
  authored the implementation. Scientific baseline packages also require a
  distinct scientific reviewer.
- **P6 - current-main synthesis:** Before approval, merge or rebase synthesis
  against current `main` must be conflict-free and must run the applicable
  authoritative suites.
- **P7 - coordinator-only git and PR authority:** In the shared checkout,
  subagents do not switch branches, stage, commit, push, or open, close, or
  retarget PRs. They return working-tree diffs and evidence to the coordinator.
  The coordinator performs git/PR operations and requests review, but does not
  merge, close, or retarget a PR without explicit user instruction.
- **P8 - machine-readable evidence:** Nontrivial scientific runners emit
  complete JSON and independently validate it. Mutation tests must show that
  missing fields, nonfinite values, changed topology, changed policy, and
  accidental success fail.
- **P9 - negative evidence is a valid result:** When a gate fails honestly,
  publish the blocker and stop downstream activation work.
- **P10 - no unsupported claims:** Terms such as `generic`, `production`,
  `converged`, `parity`, and `scientifically validated` may appear only when
  their named gates have passed.

## 4. Agent roles and separation of duties

| Role | Responsibility | Forbidden |
| --- | --- | --- |
| Coordinator | Assign packages, enforce dependencies/file ownership, monitor agents, collect exact SHAs, and update checkpoint ledger. | Implementing around a failed gate or merging without user authority. |
| Implementer | Make the smallest allowed working-tree change and add focused tests/evidence; hand the diff and results to the coordinator. | Branch switching, staging, committing, pushing, opening/retargeting PRs, self-approving, changing tolerances after seeing results, or editing forbidden paths. |
| Verification agent | Reproduce commands from a clean state, inspect JSON schemas and mutation tests, and report exact results. | Fixing implementation defects while acting as verifier. |
| Technical reviewer | Review design, safety, concurrency, cache identity, interfaces, tests, ancestry, and current-main synthesis. | Relying only on the implementer's summary. |
| Scientific reviewer | Review the functional, oracle independence, fixtures, quadrature, tolerances, and interpretation of negative results. | Granting production activation or changing code. |
| Gatekeeper | Compare all evidence with the gate checklist and issue the formal PASS/FAIL. | Authoring the package under review. |

Review staffing is risk-tiered without weakening P4 exact-head review:

- **T0 documentation/inventory:** implementer plus one independent reviewer;
  that reviewer may combine verification, technical review, and gatekeeping.
- **T1 mechanical/safety/interface:** implementer plus one independent
  technical reviewer; that reviewer may reproduce verification and act as
  gatekeeper. This applies to WP1.1a, WP3.1, WP3.3, and WP7 when no formula,
  baseline, production route, or compatibility behavior changes.
- **T2 scientific/production:** separate implementer, verification agent,
  technical reviewer, scientific reviewer, and gatekeeper. WP1.1b (either
  compatibility quarantine or net-new `5/6/6`), WP2.1, WP5.1, WP5.2, WP6.2,
  and any formula/baseline/default/compatibility change are always T2.

A package escalates to T2 whenever its diff or findings cross the stated
boundary. Follow-up commits still invalidate the prior exact-head verdict, but
the same independent reviewer may re-review a T0/T1 correction.

## 5. Standard package lifecycle

Every work package follows these checkpoints.

### Ready checkpoint

- Dependencies are merged or the exact stacked base is recorded.
- Pending decisions required by the package are resolved.
- Exact base branch/SHA, target branch, planned branch name, allowed files,
  forbidden files, tests, and reviewers are named.
- Baseline tree status is recorded, including unrelated user changes.
- The authoritative tolerances and fixture hashes are frozen.

### Implementation checkpoint

- The implementation stays inside declared ownership.
- Default-disabled behavior and fail-before-mutation behavior are tested first.
- Positive-path evidence is added only after negative guards pass.
- No generated dependency artifacts or OpenSubdiv install files are committed.

### Verification checkpoint

- Focused tests pass.
- Default dependency-free full suite passes.
- OpenSubdiv 3.7 present-dependency suite passes when applicable.
- Serial and OpenMP tests run where forces or reductions are touched.
- Sanitizers run where topology indexing, cache lifetime, or memory ownership
  changes.
- `git diff --check` passes and the diff contains no forbidden path.
- Evidence JSON passes independent schema validation and mutation tests.

### Review checkpoint

- The coordinator stages only declared files, commits, pushes, and records the
  exact head SHA.
- Technical reviewer issues a clear PASS/FAIL.
- Scientific reviewer issues a clear PASS/FAIL where required.
- GitHub checks are green.
- Current-main synthesis is clean and tests pass.
- Any follow-up commit invalidates earlier approvals and restarts exact-head
  review.

### Merge checkpoint

- Gatekeeper records gate status and evidence links.
- User explicitly instructs merge.
- The merge target and stacked ancestry are rechecked.
- After merge, the coordinator updates the ledger and rebases/recreates only
  the next authorized package.

### Authoritative command profiles

Prompts must list concrete commands from these profiles and add
package-specific runners. Commands run from the repository root in the
supported Linux/WSL environment.

**V0 - docs/inventory package**

```bash
python3 -m py_compile <changed-python-files>
python3 <inventory-runner> --check --json
python3 -m unittest <focused-inventory-test-module>
git diff --check
```

If the focused test is pytest-style rather than `unittest.TestCase`, run it
with the repository/CI Python test mechanism declared by that package; do not
claim it ran merely because the file compiled.

**V1 - default dependency-free PR readiness**

```bash
scripts/verify_pr_ready.sh
```

This builds `serial`, `omp`, `dyna`, `dyna_omp`, and `test` in a temporary
copy, then runs `./bin/test_main`. It does not authorize deleting or cleaning
the active shared worktree.

**V2 - coverage parity for production C++ changes**

```bash
make clean
make test COVERAGE=1 CXX=g++
./bin/test_main
```

Run V2 in a temporary verification copy or CI, not by destructively cleaning
a shared agent worktree. Coverage generation/upload is a CI concern unless a
package explicitly owns it.

**V3 - OpenSubdiv-present proof**

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv-3.7.0 \
  python3 <package-runner> --require-opensubdiv --json
```

The package runner must also exercise dependency-absent/default-off behavior.
It must not auto-download, vendor, or discover an ambient installation.

**V4 - serial/OpenMP evidence**

```text
Run the package's deterministic harness with OMP_NUM_THREADS=1, 2, and 4,
at least five repeats each. Compare every named observable and force family;
record the maximum difference and its frozen tolerance in JSON.
```

**V5 - current-main synthesis**

```text
Create a temporary integration branch or worktree at current main, merge the
exact PR head without committing unrelated work, and run the package's V0-V4
profiles as applicable. Record both parent SHAs. Never use reset --hard or
checkout -- to alter the user's active worktree.
```

When a command profile is impossible in the local environment, the agent
reports it as pending and relies on a named CI/reviewer run. It may not replace
the command silently with a weaker check.

## 6. Checkpoint ledger

The coordinator should update this table rather than infer state from old
conversation messages.

| Checkpoint | Deliverable | Initial status | Required approvals |
| --- | --- | --- | --- |
| K0 | Reassessment and this control plan | Drafted locally | Technical review |
| K1 | ADR: stack D0, D1/D2/D2b/D5/D8 choices, D6/D7 restatements, D3/D4 deferred | PR 183 merged; external-review amendment in progress | User + technical + scientific as decision class requires |
| K2a | Unconditional legacy index/classifier safety | Ready after plan amendment | T1 technical |
| K2b | Legacy all-valence-5 quarantine and optional net-new `5/6/6` decision | Pending WP1.1a evidence and D5 | T2: verification + technical + scientific + gatekeeper + user |
| K3 | Candidate volume-functional characterization and independent oracle | Pending | Technical + independent scientific + explicit user D3/D4 decisions |
| K4 | Backend-neutral generic row interface | Pending | Technical |
| K5 | Full-mesh OpenSubdiv Loop provider and cache proof | Pending | Technical |
| K6 | Variable-cardinality one-pass face kernel | Pending | Technical + scientific |
| K7 | Fixed quadrature policy and convergence evidence | Pending | Scientific + technical |
| K8 | Full-mesh shadow route on mixed topology | Pending | Technical + scientific |
| K9 | Runtime opt-in generic production route | Pending | Technical + scientific + user merge approval |
| K10 | Default backend decision | Pending | User explicit activation decision |
| K11 | Legacy route retirement | Pending | Technical + user compatibility decision |
| K12 | CUDA/backward-compatibility lane | Deferred | Technical + scientific + user |
| K13 | Adaptive edge-flip lane | Deferred | Technical + scientific + user |

## 7. Work packages

### WP0.1 - architecture ADR and tolerance ledger

Objective: record proposed decisions, existing-policy restatements, and
binding authority gates without changing production code or deciding D0-D5,
D2b, or D8.

Dependencies: K0 technical review. Exact base:
`origin/main@906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a`. Target: `main`.
Planned branch: `codex/unified-loop-adr`. The coordinator preserves the
pre-existing untracked `analysis/cuda_benchmark_graphs/` and
`scripts/plot_cuda_benchmark_comparison.py` and stages only WP0.1 files.

Allowed files:

- `docs/adr_unified_loop_backend.md`
- this plan and the reassessment;
- a new read-only inventory under `scripts/inventory_unified_loop_baseline.py`;
- its focused inventory test.

Forbidden: `src/**`, `include/**`, `Makefile`, CUDA paths, numerical baseline
files, route flags, or PR 176/182 stack state changes.

Steps:

1. Inventory current-main behavior separately from unmerged Valence-3 stack
   evidence. Record the exact base and every stack/PR SHA cited.
2. Inventory every active build/runtime backend flag, exact-topology guard,
   provider, cache, volume expression, version check, output schema, and
   authoritative tolerance.
3. Record D0, D1, D2, D2b, D5, and D8 as proposals pending their named
   explicit user decisions, including rejected alternatives and unresolved
   production/performance/compatibility scope. Record D6/D7 only as existing
   constraints. Record D3/D4 as pending
   post-oracle questions with their required WP2.1 evidence and independent
   review; do not decide them in this package.
4. Freeze a tolerance ledger by name, source file, rationale, and owning gate.
5. Record fixture hashes and the source of every scientific expected value.
6. Define the initial boundary/hole/ghost/non-manifold rejection policy.
7. Emit JSON showing that the ADR and inventory agree.

Evidence:

- inventory passes on current main and rejects a mutated/missing policy anchor;
- no production file changes;
- technical and scientific reviewers agree the decision questions are
  complete;
- D0/D1/D2/D2b/D5/D8 remain visibly bound to their named explicit user gates;
  D6/D7 remain existing constraints and D3/D4 remain visibly pending until
  WP2.1, independent scientific review, and explicit user decisions.

Stop conditions:

- stock Loop versus custom scheme remains undecided;
- the D3/D4 question or required post-oracle evidence cannot be stated;
- the D4 characterization questions, evidence, or later lifetime-decision
  gate cannot be stated; or
- the inventory finds an additional active backend not covered by the ADR.

Branch: `codex/unified-loop-adr`, created only by the coordinator from the
exact base above.

### WP0.1a - external-review control-plan amendment

Objective: incorporate the post-PR-183 review without changing production:
bind D0 to the PR 176/182 stack, add D2b and D8, split unconditional WP1.1a
from decision-dependent WP1.1b, name the WP3.1 sparse/dense seam, add regular
equivalence and performance gates, and route uniform-quadrature null results
to the predeclared graded/patch-domain candidates.

Exact base: `main@e9af3ddad494fc073040ee82bdf07944b9fee8cf`.
Allowed paths are the same five ADR/plan/inventory/test paths as WP0.1.
Production, CUDA, build flags, fixtures, tolerances, and PR 176/182 source are
forbidden. PR 182's body may receive only the explicit stacked-base disclosure.

Frozen candidate D8 inputs:

- protocol: same binary/compiler/OpenSubdiv build/fixture/thread count,
  alternating direct/cached/generic ordering, warmup, at least three repeats;
- `generic_vs_cached_regular_median <= TBD` pending the named D8 measurement;
- `generic_vs_direct_regular_each_case <= 2.00`;
- topology preparation and memory are reported separately, with exactly one
  preparation per topology epoch.

The direct-route numeric ceiling is a decision input. The cached-route median
ceiling remains explicitly pending; no number replaces `TBD` until the named
D8 measurement and approval. Neither becomes an acceptance criterion until D8
is explicitly approved.

### WP0.2 - PR 176/182 stack evidence disposition

Objective: decide the production-code root and evidence leaf together,
preserving the scoped two-bipyramid evidence without carrying the
Valence-3-specific provider/route forward as the generic architecture.

Dependencies: user decision D0 and WP0.1.

This is a coordination package. It makes no source changes until the user
chooses one of:

1. mark PR 176 superseded, extract the symmetric fixture from PR 176 plus the
   asymmetric fixture and negative convergence report from PR 182, then close
   both PRs;
2. retitle/retarget the stack as proof-only historical evidence while keeping
   every production route disabled; or
3. merge the stack explicitly as historical evidence, accepting its
   maintenance cost and the inventory conflict while prohibiting production
   generalization from that provider.

Required review: exact diff/ancestry review after any retarget or content
change. No agent may close, retarget, or merge either PR autonomously. PR 176
is the blocking root decision; PR 182 cannot reach `main` independently.

### WP1.1a - unconditional legacy index/classifier safety

Objective: remove undefined/uninitialized index behavior and produce evidence
for D5 without changing the accepted all-Valence-5 compatibility result.

Dependencies: merged plan amendment only. D5 is deliberately not required.

Allowed files:

- `src/mesh/Mesh_setup_geometry.cpp`
- the narrow setup/geometry headers only if required;
- focused topology and surface-geometry tests;
- one safety note under `docs/`.

Forbidden:

- OpenSubdiv providers or routes;
- energy/force formulas;
- volume formulas or baselines;
- CUDA;
- output/checkpoint code;
- broad naming cleanup.

Steps:

1. Extract a pure observational classifier for corner valence, adjacent-face
   cardinality, candidate extraordinary corner, duplicate source IDs, and
   whether every required index can be assigned uniquely.
2. Replace uninitialized `d4/d7/d8` locals with total/sentinel state and reject
   only cases that would otherwise read an unassigned or ambiguous index.
3. Prove from the current predicate that `5/6/6` has never executed; record it
   as a net-new candidate rather than retained compatibility.
4. Preserve the currently accepted all-Valence-5 fixture behavior and regular
   one-ring ordering exactly; WP1.1a may diagnose aliasing but may not quarantine
   it before D5.
5. Add adversarial tests for missing adjacent-face matches, ambiguous matches,
   boundary count mismatch, reversed faces, and fail-before-mutation.

Evidence:

- sanitizer-enabled focused tests;
- regular fixture outputs unchanged exactly;
- accepted icosahedron behavior is unchanged under the existing route;
- `5/6/6` is proven unreachable under the current predicate;
- default full suite passes;
- no OpenSubdiv or CUDA diff.

Stop conditions:

- a supported existing fixture changes;
- rejection occurs after partial one-ring mutation.

Suggested branch: `codex/legacy-index-safety`.

### WP1.1b - legacy quarantine or net-new `5/6/6` lane

Objective: act on D5 after WP1.1a evidence.

Dependencies: WP1.1a merged and explicit user D5 decision.

Options:

1. quarantine the all-Valence-5 aliased 11-slot construction before one-ring
   publication and reject every unsupported irregular legacy case; or
2. in a separate T2 scientific package, design net-new `5/6/6` support with
   exact topology/orientation proof, 11 distinct ordered sources, matrix/force
   conjugacy, and no claim of historical compatibility.

The first option reverses an accepted fixture and therefore requires the D5
user decision. The second is new scientific implementation, not retention,
and requires independent scientific review plus explicit user approval.

### WP2.1 - candidate volume-functional characterization and oracle

Objective: characterize candidate functionals and establish independent
evidence before any production semantic or baseline decision.

Dependencies: WP0.1; may run in parallel with WP1.1a because file ownership is
disjoint.

Allowed files:

- new proof code under `experiments/`;
- new runner/inventory under `scripts/`;
- new fixtures only when documented;
- focused tests;
- `docs/candidate_signed_volume_functional.md`.

Forbidden:

- production geometry/force code;
- existing expected values;
- route flags;
- CUDA;
- tolerance changes.

Steps:

1. State the candidate full-divergence discrete functional, exact `1/6`
   coefficient, and sign convention; separately record the current legacy
   x-only literal `0.16666666666` without normalizing it to exact `1/6`.
2. Derive its gradient independently of the production force routine.
3. Implement at least two independent checks: central finite differences and
   either automatic differentiation or a separately coded higher-precision
   evaluator.
4. Evaluate regular, tetrahedron, octahedron, icosahedron, symmetric and
   asymmetric bipyramids, mixed 3/4/5, and orientation-reversed fixtures.
5. Check translation invariance, orientation sign, zero `uVol`, nonzero
   X/Y/Z perturbations, net force, and force/energy conjugacy.
6. Characterize full-divergence versus legacy-x baselines without selecting a
   new default.
7. Emit complete JSON and mutation tests for missing axis, zeroed X/Y,
   nonfinite values, orientation drift, and false conjugacy.

Evidence:

- scientific reviewer approves the derivation and oracle independence;
- technical reviewer reproduces every fixture;
- authoritative tolerance ledger is unchanged;
- report clearly distinguishes characterization from baseline approval.
- completion explicitly leaves D3/D4 undecided pending independent scientific
  review and explicit user decisions.

Stop conditions:

- independent oracles disagree beyond frozen tolerances;
- force is not the negative gradient of the named energy;
- a fixture's orientation or closure is ambiguous;
- evidence passes only after dropping an axis or force family.

Suggested branch: `codex/volume-functional-oracle`.

### WP2.2 - explicit volume-mode seam

Objective: represent canonical and legacy volume as named policies without
changing the default.

Dependencies: completed WP2.1, independent scientific PASS, and explicit user
decisions D3-D4.

Allowed files: a new backend-neutral volume policy header/source, focused
configuration tests, documentation, and minimal call-site plumbing required
to report the selected policy.

Forbidden: default selection changes, OpenSubdiv provider work, CUDA
implementation, output schema changes, or per-valence selection.

Steps:

1. Define `FullDivergence` and `LegacyXOnly` policies.
2. Select policy only through explicit configuration, never face topology.
3. Reject unsupported backend/policy combinations before mutation.
4. Keep the current default until the production migration gate.
5. Add diagnostics showing the active policy and tests proving no implicit
   fallback.

Gate: technical PASS, scientific confirmation that the seam implements the
approved definitions, and exact default-output preservation.

### WP3.1 - backend-neutral generic row interface

Objective: define the public contract before OpenSubdiv implementation.

Dependencies: explicit user decisions D1-D2 after WP0.1; D6 remains a
restated existing constraint.

Recommended files:

- `include/mesh/Loop_limit_surface_backend.hpp`
- `include/mesh/Source_keyed_limit_rows.hpp`
- contract-only tests and documentation.

Forbidden: OpenSubdiv includes in public headers, production route changes,
per-valence types, CUDA, or actual topology preparation.

Required contract:

- `LoopTopologyKey` and monotonic topology epoch;
- original-source sparse-at-rest rows for position, `du`, `dv`, `duu`, `duv`,
  `dvv`;
- one deterministic union source list per face; at evaluation, densify each
  requested sample into a compact row-by-union-source matrix consumed by the
  dense face algebra, then scatter by the same original IDs;
- per-face sample coordinates and weights;
- structural validation and rejection diagnostics;
- immutable prepared package ownership;
- explicit boundary/ghost/hole policy;
- cache identity/invalidation hooks;
- no exact fixture identity or fixed source cardinality.

Tests:

- compile-time proof that public headers contain no OpenSubdiv type/include;
- construction with different source cardinalities;
- stale epoch, duplicate source, missing derivative, nonfinite coefficient,
  wrong face ID, and invalid weight rejection;
- single mixed-row compatibility expansion tested separately.

Stop condition: any consumer must know OpenSubdiv patch-table types or a
valence-specific class to use the interface.

Suggested branch: `codex/generic-loop-row-interface`.

### WP3.2 - full-mesh OpenSubdiv Loop provider proof

Objective: implement the generic interface for proof-only full-mesh topology.

Dependencies: WP3.1 merged and D1-D2 explicitly decided by the user. The
closed proof may proceed while D2b is pending, but WP3.2 cannot claim primary
production-workload scope until D2b is decided and its policy passes.

Recommended implementation:

- `src/mesh/OpenSubdiv_loop_limit_surface_backend.cpp`
- one opt-in runner and experiment;
- no production caller.

Steps:

1. Create one `TopologyRefiner` from complete oriented triangle connectivity
   with explicitly reviewed Loop and boundary options.
2. Request all approved face/sample locations in one preparation operation.
3. Convert limit stencils and derivatives into immutable original-source
   sparse rows.
4. Accept regular, tetrahedron, octahedron, icosahedron, bipyramids, mixed
   3/4/5, and at least one non-Platonic closed triangulation through the same
   entry point.
5. Reject open, non-manifold, duplicate-edge, reversed/inconsistent winding,
   ghost-policy, and stale-topology inputs atomically.
6. Pin and emit the reviewed OpenSubdiv version and all scheme options.
7. Compare existing exact providers only as reference oracles; do not call
   them from the generic provider.
8. For a canonical `6/6/6` face, compare position, first/pure/mixed second
   derivative rows and area/legacy-volume integrands against
   `SlimedLoopLimitSurfaceEvaluator` under the frozen
   `regular_row_and_route_parity = 5.0e-6` tolerance.
9. If D2b includes the flat/periodic workload, prove one reviewed ghost-band,
   Ptex/source-ID, physical-face-only evaluation, and force/state-transfer
   policy on `data/example`; otherwise emit an explicit legacy-only rejection.

Evidence:

- derivative row algebra and source coverage for every fixture;
- no fixed vertex/face/source count in the production implementation;
- default-off stub and absent-dependency behavior;
- full default suite and OpenSubdiv-present proof;
- independent JSON validation and mutation tests.
- regular `6/6/6` full-mesh rows satisfy the frozen analytic-route equivalence
  gate; this is a stop condition, not merely a fixture-matrix row.

Stop conditions:

- mixed topology requires multiple refiners or a valence switch;
- original source IDs cannot be reconstructed unambiguously;
- a supported closed face lacks derivative-complete rows;
- any canonical regular-face row/integrand exceeds `5.0e-6` versus the existing
  analytic regular route;
- D2b is silently bypassed while claiming the primary workload is supported;
- OpenSubdiv types escape the backend seam.

Suggested branch: `codex/full-mesh-loop-provider`.

### WP3.3 - topology cache and invalidation proof

Objective: ensure topology preparation is not a timestep operation.

Dependencies: WP3.2. A structural cache proof may start while D8 evidence is
pending, but performance PASS requires the approved D8 budget.

Steps:

1. Implement immutable prepared-package caching keyed by the complete
   `LoopTopologyKey`.
2. Count refiner, patch-table, and stencil-table construction explicitly in a
   proof harness.
3. Prove coordinate-only updates produce cache hits and bitwise-identical
   rows.
4. Prove every topology-affecting mutation misses or invalidates the cache.
5. Test concurrent reads and serialized invalidation under ThreadSanitizer or
   an equivalent race-focused harness where available.
6. Record preparation time, memory, and coordinate-only retrieval time
   separately; do not hide preparation in averaged timestep numbers.
7. Reproduce the same-binary alternating-order regular benchmark and compare
   the generic path with both the current cached OpenSubdiv route and direct
   analytic route.

Gate:

- exactly one preparation per topology epoch;
- zero refiner/patch/stencil construction during coordinate-only evaluation;
- no stale package acceptance;
- after D8 approval, the coordinate-only generic median satisfies the approved
  numeric ceiling that replaces `TBD`, and every frozen case is `<=2.00x` the
  direct analytic route;
- technical reviewer PASS.

### WP4.1 - variable-cardinality face-kernel extraction

Objective: extract mathematics from `element_energy_force_regular()` without
changing production routing or scientific outputs.

Dependencies: WP2.1, WP3.1, independent scientific review, and explicit user
D3-D4 volume-policy decisions; provider implementation is not required if
synthetic source-keyed rows exercise the interface.

Steps:

1. Create a backend-neutral kernel consuming coordinates, source-keyed rows,
   weights, material parameters, and named volume policy.
2. Return per-face geometry, bending energy, and per-source bending/area/volume
   forces without mutating `Mesh`.
3. Represent one mixed derivative internally.
4. Adapt existing regular 12-control rows into the kernel and require exact or
   frozen-tolerance equivalence under the current selected policy.
5. Adapt existing exact Valence-3/4/5 proof rows in tests only.
6. Add independent derivative checks for variable source cardinalities.

Forbidden: production route switch, OpenSubdiv type coupling, duplicated
dry-run execution, CUDA, output/checkpoint changes.

Stop conditions:

- equivalence requires valence-specific branches in the kernel;
- geometry and force require different rows or samples;
- any force family cannot be attributed to original source IDs;
- default outputs change outside the approved volume re-baseline.

Suggested branch: `codex/source-keyed-membrane-kernel`.

### WP4.2 - one-pass transaction and deterministic scatter

Objective: prove complete staging and publication using the generic kernel,
without selecting it in the public evaluator.

Dependencies: WP3.2-WP3.3 and WP4.1.

Steps:

1. Preflight all topology, row, destination, and policy inputs before writes.
2. Evaluate each face/sample exactly once into immutable staged results.
3. Reduce per-source forces through existing thread-local component buffers.
4. Publish face observables, global geometry/energy, and vertex force families
   atomically.
5. Test serial and OpenMP 1/2/4 threads, repeats, failure injection at every
   stage, and exact rollback after rejection.
6. Retain old route versus new transaction comparison in a proof harness, not
   as a second production evaluation.

Gate: technical and scientific PASS; no production caller yet.

### WP5.1 - quadrature candidate/oracle study

Objective: find a scientifically adequate fixed plan without altering row or
force tolerances.

Dependencies: WP3.2 and WP4.1; may use a proof-only uncached provider if cache
work is still under review.

Candidates:

- higher-order symmetric triangle cubature;
- uniform composite subdivision;
- graded composite refinement toward extraordinary corners; and
- integration over the OpenSubdiv patch-domain decomposition.

Hypothesis under test: uniform low-order rules can fail bending-energy/force
convergence near extraordinary points because higher curvature derivatives
are singular or unbounded there. PR 182 is evidence only for its two tested
`3/4/4` bipyramids, not a general proof. A uniform-rule null result therefore
routes to the graded and patch-domain candidates; it does not by itself block
K7.

Steps:

1. Establish deeper reference levels and an independent convergence oracle.
2. Run symmetric/asymmetric regular, Valence-3/4/5, bipyramid, mixed 3/4/5,
   non-Platonic, and coordinate-perturbed fixtures.
3. Measure area, signed volume, bending energy, total energy, and every
   per-source force family/axis.
4. Report error versus reference, work/sample count, row residuals, and
   preparation/evaluation cost separately.
5. Require two successive reference refinements below frozen targets.
6. Publish negative results without changing production or the generic
   provider interface.

Stop conditions:

- graded, patch-domain, and every other predeclared candidate family all fail
  the frozen budget/targets; a uniform-only null result is not this condition;
- conclusions depend on a single symmetric fixture;
- a plan changes with coordinates without an approved differentiability
  policy;
- row residual and integration error are conflated.

### WP5.2 - fixed quadrature policy selection

Objective: record one plan or an explicit scientific blocker.

Dependencies: WP5.1 exact-head technical and scientific review.

Deliverable: ADR amendment stating the selected rule, topology classification
inputs, fixed sample/weight generation, error targets, performance budget,
and rejection policy.

Authority: scientific reviewer recommendation plus explicit user selection.
If no candidate passes, K7 remains blocked and WP6 cannot start.

### WP6.1 - full-mesh shadow integration

Objective: exercise the generic backend through the real evaluator boundary
without publishing its results.

Dependencies: K3-K7 all green.

Steps:

1. Add one opt-in shadow gate unrelated to valence.
2. Execute the generic path once and compare it with the active compatibility
   path or independent accepted baseline.
3. Cover mixed topology, outputs, restart, serial/OpenMP, long-run repeated
   coordinate updates, cache reuse, and failure atomicity.
4. Report expected scientific differences honestly; shadow success means the
   route executed and evidence is complete, not automatic parity.
5. Measure per-step cost with topology preparation excluded and included as
   separate metrics.

Forbidden: publishing generic forces/energy, changing defaults, CUDA changes,
or deleting exact routes.

Gate: technical and scientific PASS plus user approval to proceed to opt-in
publication.

### WP6.2 - single runtime opt-in production route

Objective: publish the generic transaction only under one explicit selector.

Dependencies: WP6.1, user authorization, and an explicit D2b scope decision.

Selector target:

```text
SLIMED_SUBDIVISION_BACKEND=opensubdiv-loop|legacy
```

Steps:

1. Add one compile-time OpenSubdiv Loop gate and one runtime selector.
2. Map old valence flags only as temporary deprecated aliases for their exact
   compatibility fixtures; reject conflicts.
3. Route the complete supported closed mesh through one backend. If D2b
   includes the primary flat/periodic workload, route it under the reviewed
   ghost/source policy; if D2b declares it legacy-only, reject the generic
   selector explicitly for that workload. Do not mix schemes or volume
   policies face by face.
4. Preserve gate-absent default exactly.
5. Repeat default/OSD-present, output/checkpoint, restart, serial/OpenMP,
   sanitizer, cache, and long-run dynamics evidence.
6. Provide one-command rollback with no state migration.

Gate: exact-head technical and scientific reviewer PASS, GitHub green,
current-main synthesis, and explicit user merge instruction.

### WP6.3 - default backend decision

This is a decision packet, not an automatic implementation continuation.

Required evidence:

- accepted scientific baseline and quadrature;
- opt-in production soak results;
- approved D8 performance and memory budget, reproduced on the frozen
  same-binary protocol;
- explicit D2b result showing whether the primary flat/periodic workload is
  supported or permanently legacy-only;
- dependency/install/license review;
- old-run compatibility and rollback period;
- CUDA/backend compatibility decision;
- no open severity-1/2 correctness findings.

Only the user may authorize a default change.

### WP7 - deprecation and deletion

Objective: remove duplicate valence providers/routes only after the generic
route is accepted and the compatibility window is complete.

Delete in separate mechanically reviewable PRs:

1. deprecated runtime aliases;
2. exact production route callers while retaining fixtures;
3. duplicate providers and face loops;
4. dead legacy matrix code if compatibility is no longer required; and
5. obsolete docs/scripts after an archive index is recorded.

Every deletion PR must prove no live reference, default build/test success,
OpenSubdiv-present success, output/checkpoint stability, and current-main
synthesis. Deletion is not bundled with activation.

### WP8 - CUDA and backward compatibility

Objective: resolve CPU/CUDA scientific compatibility after the canonical CPU
path is stable.

Dependencies: user explicitly starts this package; K3-K9 evidence available.

First action is a read-only decision matrix, not CUDA implementation:

- Can CUDA consume the same source-keyed rows and fixed quadrature?
- Can canonical full-divergence geometry/force be implemented conjugately?
- Which old checkpoints/runs require legacy-x reproduction?
- Should unsupported combinations fail or fall back explicitly?

Only after review may a CUDA implementation PR touch CUDA paths. CPU and CUDA
must not silently implement different named functionals.

### WP9 - adaptive edge flipping

Objective: begin only after topology epochs and cache invalidation are proven.

Feasibility gate:

- closed manifold and orientation preserved;
- no duplicate edge/face or valence below 3;
- boundary, insertion, material, and ghost labels preserved;
- declared triangle-quality and valence objective improves;
- state-transfer and energy-discontinuity policy approved;
- topology epoch increments and cache rebuilds exactly once;
- rejected flips restore exact state.

Edge flipping is remeshing and changes the Loop control surface. It is not an
evaluator optimization and requires its own scientific decision, PR sequence,
reviewers, and explicit user activation.

## 8. Fixture and evidence matrix

Each applicable package declares which rows it covers. `N/A` requires a
written reason.

| Fixture/class | Topology purpose | Required checks |
| --- | --- | --- |
| Regular closed/periodic mesh | Regular baseline and optimized-path comparison | Rows, geometry, all force families, output, cache |
| Tetrahedron | All-Valence-3 closed extreme | Rows, orientation, full volume, FD force |
| Octahedron | All-Valence-4 closed case | Same |
| Icosahedron | All-Valence-5 accepted stock baseline and legacy quarantine | Same plus legacy rejection/compatibility |
| Symmetric 3/4/4 bipyramid | Multiple extraordinary corners and quadrature | Convergence, row invariants, cache |
| Asymmetric 3/4/4 bipyramid | Cancellation-resistant quadrature/force | Per-source/axis evidence |
| Closed mixed 3/4/5 | Primary anti-fixture-lock requirement | One full-mesh provider and transaction |
| Intended 5/6/6 local patch in a closed mesh | Legacy matrix intent and generic local support | Exact classification and generic rows |
| Non-Platonic closed triangulation | Generality beyond named fixtures | Variable cardinality and mixed valences |
| Coordinate-perturbed variants | Symmetry/cancellation resistance | Finite differences and convergence |
| Reversed/inconsistent winding | Orientation guard | Atomic rejection or defined sign behavior |
| Open boundary mesh | Initial unsupported scope | Fail-before-mutation diagnostic |
| Non-manifold/duplicate edge | Safety | Fail-before-mutation diagnostic |
| Topology-mutated/edge-flipped mesh | Cache invalidation | Epoch miss and rebuild |

## 9. Required reviewer output

Use this exact structure when prompting a reviewer:

```text
Review target: <PR URL>
Exact head: <40-character SHA>
Work package: <WP ID>
Base and ancestry: <base branch/SHA>
Rules to enforce: <rule IDs>
Required commands: <commands>
Scientific claims: <claims or "none">
Forbidden paths: <paths>

Return exactly one decision:
- PASS - MERGEABLE
- FAIL - NOT MERGEABLE

For FAIL, list each blocking finding with file/line, violated rule or gate,
and required evidence. Confirm whether current-main synthesis and exact-head
CI were checked. Do not approve a different SHA.
```

Scientific reviewers additionally answer:

1. Is the functional named and applied consistently?
2. Is the oracle independent?
3. Were tolerances frozen before results?
4. Do fixtures resist symmetry/cancellation?
5. Does the evidence support every scientific adjective used?
6. Is a negative result represented as a blocker rather than a pass?

## 10. Copy-ready subagent prompt template

```text
You are implementing <WP ID and title> from
docs/unified_irregular_loop_implementation_plan.md.

Objective:
<copy objective>

Authority and non-authority:
- You may inspect, edit declared files, and test this package.
- The coordinator alone changes branches, stages, commits, pushes, and opens,
  closes, or retargets PRs in the shared checkout.
- You may not activate production, change scientific baselines, or expand
  scope without explicit coordinator/user instruction.

Dependencies and baseline:
- Required merged checkpoints: <K IDs>
- Base branch and SHA: <exact values>
- Related open PRs: <URLs and relationship>

Rules:
- Enforce <rule IDs>.
- Read the reassessment, this plan, and <package-specific docs> before edits.

File ownership:
- Allowed: <exact paths/globs>
- Forbidden: <exact paths/globs>
- Preserve all unrelated dirty/untracked files.

Implementation steps:
1. <copy package steps>

Required evidence:
- <commands, fixtures, JSON fields, mutation tests>

Stop and report; do not improvise if:
- <copy stop conditions>

Deliverables:
- Focused implementation and tests
- Evidence report with exact commands/results
- Working-tree diff limited to allowed files
- Proposed commit/PR summary and work-package/gate checklist
- Handoff to coordinator for staging, commit, push, PR, and exact-head review

Before handoff:
- git diff --check
- no forbidden-path diff
- applicable default and OpenSubdiv-present suites
- current-main synthesis or explicit reason it must wait
```

## 11. Initial subagent prompts

These are the first safe assignments. They do not authorize their execution;
the coordinator may dispatch them after confirming file ownership.

### Prompt A - WP0.1 ADR/inventory agent

```text
Implement WP0.1 only. This is docs/inventory work. Do not edit src, include,
Makefile, CUDA, route flags, or numerical baselines. Inventory all active Loop
backends, flags, topology guards, caches, volume functionals, version policies,
tolerances, fixtures, and output/checkpoint contracts. Draft
docs/adr_unified_loop_backend.md with D0/D1/D2/D2b/D5/D8 left as explicit user
approve/reject choices under their named evidence gates and D6/D7 recorded
only as existing constraints. Preserve PR 176/182 as one unmerged stack;
do not merge, close, retarget, or alter either PR.
D3/D4 must remain pending post-oracle independent review and explicit user
decisions. Add a machine-readable inventory and
mutation-tested focused test. Enforce S1-S7, A1-A9, C1-C7, and P1-P10. Stop if
another active backend or hidden functional is found. Return the focused diff
and evidence to the coordinator; do not stage, commit, push, or open a PR.

Original WP0.1 base: origin/main@906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a
External-review amendment base: origin/main@e9af3ddad494fc073040ee82bdf07944b9fee8cf
Target: main
Coordinator-owned branch: codex/unified-loop-plan-amendments
Treat PR176@46c06080fb663bcb43f38cf32fc1b45daa8732e8 as the unmerged stack
root and PR182@9587e3dce4509029e611e2937bac570b410193c3 as its leaf evidence,
not current-main behavior. Preserve and do not stage the unrelated
analysis/cuda_benchmark_graphs/ and scripts/plot_cuda_benchmark_comparison.py.
```

### Prompt B1 - WP1.1a unconditional safety agent

```text
After the amended WP0.1, implement WP1.1a only; no D5 decision is required. Own
src/mesh/Mesh_setup_geometry.cpp plus focused topology tests and one safety
note. Do not edit OpenSubdiv providers/routes, energy/force or volume formulas,
CUDA, outputs, checkpoints, or unrelated naming. Make d4/d7/d8 state total and
sentinel-initialized before any read; add a pure observational classifier; and
reject only ambiguous or unassigned states that could otherwise trigger
undefined behavior. Preserve every currently accepted topology and exact
regular/all-valence-5 ordering, including the aliased icosahedron fixture.
Diagnose but do not quarantine all-valence-5 and do not add 5/6/6 support.
Run sanitizer-focused tests, the default full suite, and no-forbidden-diff
checks. Stop if ordering cannot be proven or an accepted baseline moves. Return
the diff/evidence to the coordinator for commit and exact-head review; do not
change git state.
```

### Prompt B2 - WP1.1b D5-dependent quarantine or net-new lane agent

```text
Do not dispatch until WP1.1a is merged and the user has explicitly decided D5.
Implement only the selected WP1.1b outcome. If quarantine is selected, reject
the accepted all-valence-5 alias before geometry mutation and update its
focused contract tests. If a 5/6/6 lane is separately authorized, treat it as
net-new scientific work: require exact topology/orientation proof, 11 distinct
ordered sources, matrix/force conjugacy, independent scientific review, and no
claim of historical compatibility. Do not modify generic OpenSubdiv routes,
volume formulas, CUDA, outputs, or checkpoints. Return the focused diff and
evidence to the coordinator; do not change git state.
```

### Prompt C - WP2.1 volume oracle agent

```text
Implement WP2.1 only in experiments, scripts, tests, fixtures, and
docs/candidate_signed_volume_functional.md. Do not modify production, CUDA,
routes, defaults, or expected baselines. Independently derive and evaluate the
candidate full-divergence signed-volume functional and gradient with exact
`1/6`; separately characterize the legacy x-only literal `0.16666666666` and
never normalize or change it. Use central finite differences plus a separately
coded AD or higher-precision oracle. Cover every
fixture/axis/orientation named in WP2.1, emit complete JSON, and add mutation
tests for missing axes, zeroed X/Y, nonfinite data, orientation drift, and
false conjugacy. Freeze tolerances before authoritative results. A mismatch is
a valid blocker; do not widen thresholds. Do not decide D3/D4. Return the
diff/evidence to the coordinator for technical and independent scientific
exact-head review; do not change git state.
```

### Prompt D - WP3.1 interface agent

```text
After explicit user D1/D2 decisions, implement WP3.1 only. Define backend-neutral immutable
Loop topology and source-keyed limit-row contracts. Public headers must not
include or expose OpenSubdiv, valence-specific classes, fixed source counts, or
production routing. Represent one mixed derivative and explicit topology
epoch/cache identity. Add structural/adversarial contract tests for variable
cardinality, stale epoch, duplicate sources, missing rows, nonfinite values,
invalid weights, and compatibility expansion. Stop if consumers must know
backend patch types. Return the diff/evidence to the coordinator for
exact-head technical review; do not change git state.
```

WP1.1a and WP2.1 are logically independent after WP0.1, but implementation
agents edit the shared worktree sequentially unless the coordinator explicitly
creates isolated worktrees. WP3.1 may overlap only as a read-only audit while
WP2.1 edits; implementation starts after D1-D2 are explicitly decided by the
user and volume semantics are excluded. All later implementation packages are dependency-
linked and run sequentially by default.

## 12. Coordinator status update format

Use a compact status record after every agent or reviewer response:

```text
Work package: <WP>
Branch/PR: <branch and URL>
Exact head: <SHA>
Files changed: <paths>
Tests: <pass/fail and commands>
Technical review: <pending/PASS/FAIL, exact SHA>
Scientific review: <N/A/pending/PASS/FAIL, exact SHA>
GitHub checks: <pending/pass/fail>
Current-main synthesis: <pending/pass/fail>
Gate: <blocked/ready/PASS>
Blocker/next authorized action: <one sentence>
```

The coordinator must not describe a package as complete while any required
field is pending.

## 13. Final gate sequence

```text
K0 plan
  -> K1 ADR/reviews + explicit user D0/D1/D2/D2b/D5/D8 decisions as gated
      (D6/D7 restated; D3/D4 pending WP2.1)
      -> K2a unconditional index/classifier safety
          -> K2b legacy quarantine or net-new 5/6/6 after D5
      -> K3 WP2.1 evidence -> independent scientific review
          -> explicit user D3/D4 decisions before policy implementation
      -> K4 generic interface
          -> K5 full-mesh rows/cache
              -> K6 one-pass kernel/transaction
                  -> K7 quadrature convergence
                      -> K8 shadow route
                          -> K9 opt-in production
                              -> K12 CUDA compatibility decision/implementation
                                  when required for the proposed default
                              -> K10 user default decision
                                  -> K11 deprecation
                              -> K13 edge flipping only by separate instruction
```

K2a and K3 may overlap after the amended K1; K2b waits for D5. K4 may overlap
proof-only K3 work only if D1
and D2 are explicitly decided by the user and volume semantics are excluded
from K4. K5 through K10
are sequential scientific/architectural gates except that K12 is inserted
before K10 when the proposed default would otherwise permit a scientifically
different CUDA/backend combination. K10 may instead approve an explicit
rejection of that combination. K12 implementation and K13 do not begin by
inference from K9 or K10; each requires a new explicit user instruction.
